#!/usr/bin/env python3
"""Generate a formatted bibliography from BibTeX and append to a literature review.

Reads a literature review markdown file and a BibTeX file, identifies cited works
via surname+year proximity matching, formats them in Chicago Author-Date style,
and appends (or replaces) a ## References section.

Usage:
    python generate_bibliography.py review.md literature.bib
"""

import re
import sys
import unicodedata
from pathlib import Path

from pybtex.database import parse_file

# Import LATEX_ESCAPES from bib_validator and identity keys from bib_identity
# (single source of truth)
_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_validator import LATEX_ESCAPES  # noqa: E402
from bib_identity import (  # noqa: E402
    ascii_variants, fallback_key, normalize_doi, title_key, translit_fold,
)
from metadata_cleaner import marker_removed_fields  # noqa: E402

sys.path.pop(0)

# Proximity window for surname↔year matching (chars)
_MATCH_WINDOW = 60


def clean_bibtex_str(s: str) -> str:
    """Normalize a BibTeX string: LaTeX accents → braces → \\& → \\url{}."""
    # Step 1: LaTeX accent-inside-braces → Unicode
    # Handle both {\'e} and \'e forms
    for latex, uni in LATEX_ESCAPES.items():
        # Braced form: {\cmd}
        s = s.replace("{" + latex + "}", uni)
        # Unbraced form: \cmd (but not if already handled by braced replacement)
        s = s.replace(latex, uni)

    # Step 2: Strip remaining BibTeX braces
    s = s.replace("{", "").replace("}", "")

    # Step 3: \& → & (handles both \& and double-escaped \\&)
    s = re.sub(r"\\+&", "&", s)

    # Step 4: After step 2, \url{X} became \urlX — strip the residual \url prefix
    s = re.sub(r"\\url\s*", "", s)

    return s


def _clean_name_parts(parts: list[str]) -> list[str]:
    """Apply clean_bibtex_str to each name part."""
    return [clean_bibtex_str(p) for p in parts]


def _get_full_surname(person) -> str:
    """Construct full surname from prelast_names + last_names."""
    parts = _clean_name_parts(person.prelast_names + person.last_names)
    return " ".join(p for p in parts if p)


def _get_first_names(person) -> str:
    """Get cleaned first + middle names as a string."""
    parts = _clean_name_parts(person.first_names + person.middle_names)
    return " ".join(p for p in parts if p)


def _normalize_for_matching(s: str) -> str:
    """NFKD-normalize and strip combining marks for diacritical-tolerant matching.

    Deliberately NOT bib_identity.title_key (ROADMAP item 4, Decision 1): this
    folds author-written review prose, and it must keep punctuation because the
    60-character _MATCH_WINDOW is sliced from whichever haystack produced a
    hit - this function's output (norm_text) or bib_identity.translit_fold's
    output (translit_text, item 3 B/E: symmetric transliteration matching),
    both of which keep punctuation for the same reason. Pinned by this file's
    tests in tests/test_generate_bibliography.py.
    """
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _get_field(entry, name: str) -> str:
    """Get a cleaned field value, or empty string if missing."""
    raw = entry.fields.get(name, "")
    return clean_bibtex_str(raw).strip() if raw else ""


def _entry_suffix(entry) -> str:
    """The entry's Chicago letter, or "" when absent or malformed.

    One rule, two consumers: _display_year renders it into the delivered
    References and _collect_matches discriminates citations by it. If the
    two ever disagreed, a reference would render "2010a" while the resolver
    read that entry as unlettered - dropping a cited work or keeping a
    phantom. Only a single ASCII a-z letter counts; anything else reads as
    absent rather than emitting nonsense into a delivered reference.

    Deliberately NOT used by _carry_year_suffix, which is a merge policy
    over raw values (it must preserve whatever a copy carries), not a
    display or matching rule.
    """
    suffix = _get_field(entry, "year_suffix").strip().lower()
    if len(suffix) == 1 and suffix.isalpha() and suffix.isascii():
        return suffix
    return ""


def _display_year(entry) -> str:
    """The year as a reader sees it: `2010b` when a Chicago letter was
    assigned (item 3 F), plain `2010` otherwise.

    The letter lives in its own field, never in `year`: the \\d{4} guards in
    check_evidence.py and resolve_context.py reject a suffixed year outright.
    Only a single a-z letter is honoured (_entry_suffix), so a malformed
    field renders as if absent rather than emitting nonsense into a
    delivered reference.
    """
    year = _get_field(entry, "year")
    suffix = _entry_suffix(entry)
    if year and suffix:
        return year + suffix
    return year


def _quoted_title(title: str) -> str:
    """Wrap title in quotes with proper terminal punctuation per Chicago style.

    If title already ends with ? or !, the period is absorbed.
    """
    if title.endswith(("?", "!", ".")):
        return f'"{title}"'
    return f'"{title}."'


def _format_doi(doi: str) -> str:
    """Format DOI as a full URL.

    Normalizes first (ROADMAP item 4 follow-up): rendering the raw field meant
    a bib carrying `doi = {doi:10.1000/x}` emitted the broken hyperlink
    `https://doi.org/doi:10.1000/x` into the delivered References. A value that
    is a URL but not a known DOI prefix still passes through untouched rather
    than being glued onto https://doi.org/. Note normalize_doi lowercases;
    DOI resolution is case-insensitive, so this only affects display.
    """
    doi = normalize_doi(doi)
    if doi.startswith("http"):
        return doi
    return f"https://doi.org/{doi}"


# Alias, not a copy - pinned by tests/test_generate_bibliography.py.
_normalize_doi = normalize_doi


def format_author_list(persons, is_editor: bool = False) -> str:
    """Format a list of pybtex Person objects in Chicago Author-Date style.

    Returns the formatted author/editor string ending with a period.
    """
    if not persons:
        return ""

    def fmt_first(p):
        """First author: Surname, First."""
        surname = _get_full_surname(p)
        first = _get_first_names(p)
        if first:
            return f"{surname}, {first}"
        return surname

    def fmt_subsequent(p):
        """Subsequent authors: First Surname."""
        surname = _get_full_surname(p)
        first = _get_first_names(p)
        if first:
            return f"{first} {surname}"
        return surname

    n = len(persons)

    if n == 1:
        result = fmt_first(persons[0])
    elif n == 2:
        result = f"{fmt_first(persons[0])}, and {fmt_subsequent(persons[1])}"
    elif n <= 10:
        parts = [fmt_first(persons[0])]
        for p in persons[1:-1]:
            parts.append(fmt_subsequent(p))
        parts_str = ", ".join(parts)
        result = f"{parts_str}, and {fmt_subsequent(persons[-1])}"
    else:
        # 11+: first seven, then "et al."
        parts = [fmt_first(persons[0])]
        for p in persons[1:7]:
            parts.append(fmt_subsequent(p))
        result = ", ".join(parts) + ", et al."

    # Append editor marker
    if is_editor:
        ed = "eds." if n > 1 else "ed."
        result += f", {ed}"

    # Ensure trailing period
    if not result.endswith("."):
        result += "."

    return result


def format_entry(entry, key: str) -> str:
    """Format a single BibTeX entry in Chicago Author-Date style."""
    entry_type = entry.type.lower()

    # Determine authors or editors
    authors = entry.persons.get("author", [])
    editors = entry.persons.get("editor", [])
    is_editor_volume = not authors and bool(editors)
    persons = authors if authors else editors

    if not persons:
        return ""

    author_str = format_author_list(persons, is_editor=is_editor_volume)
    year = _display_year(entry)
    title = _get_field(entry, "title")

    # Build the reference based on entry type
    if entry_type == "article":
        return _format_article(author_str, year, title, entry)
    elif entry_type == "book":
        return _format_book(author_str, year, title, entry)
    elif entry_type == "incollection":
        return _format_incollection(author_str, year, title, entry, editors)
    elif entry_type == "inproceedings":
        return _format_inproceedings(author_str, year, title, entry)
    elif entry_type == "phdthesis":
        return _format_phdthesis(author_str, year, title, entry)
    else:
        # @misc and unknown types
        return _format_misc(author_str, year, title, entry)


def _format_article(author_str, year, title, entry) -> str:
    journal = _get_field(entry, "journal")
    volume = _get_field(entry, "volume")
    number = _get_field(entry, "number")
    pages = _get_field(entry, "pages")
    doi = _get_field(entry, "doi")

    parts = [f'{author_str} {year}. {_quoted_title(title)}']
    if journal:
        journal_part = f"*{journal}*"
        if volume:
            journal_part += f" {volume}"
        if number:
            journal_part += f" ({number})"
        if pages:
            journal_part += f": {pages}"
        journal_part += "."
        parts.append(journal_part)
    if doi:
        parts.append(_format_doi(doi))

    return " ".join(parts)


def _format_book(author_str, year, title, entry) -> str:
    address = _get_field(entry, "address")
    publisher = _get_field(entry, "publisher")
    doi = _get_field(entry, "doi")

    parts = [f"{author_str} {year}. *{title}*."]
    if address and publisher:
        parts.append(f"{address}: {publisher}.")
    elif publisher:
        parts.append(f"{publisher}.")
    if doi:
        parts.append(_format_doi(doi))

    return " ".join(parts)


def _format_incollection(author_str, year, title, entry, editors) -> str:
    booktitle = _get_field(entry, "booktitle")
    journal = _get_field(entry, "journal")

    # Fallback: if booktitle missing but journal present, format as article
    if not booktitle and journal:
        return _format_article(author_str, year, title, entry)

    pages = _get_field(entry, "pages")
    address = _get_field(entry, "address")
    publisher = _get_field(entry, "publisher")
    doi = _get_field(entry, "doi")

    parts = [f'{author_str} {year}. {_quoted_title(title)}']

    # Build the container clause only when a container title survives. When a
    # demotion stripped the booktitle, suppress the dangling "In." connective
    # (item 13 A7): emit editors/pages without the orphaned "In".
    if booktitle:
        container = f"In *{booktitle}*"
        if editors:
            ed_str = format_author_list(editors).rstrip(".")
            container += f", edited by {ed_str}"
        if pages:
            container += f", {pages}"
        container += "."
        parts.append(container)
    elif editors:
        ed_str = format_author_list(editors).rstrip(".")
        container = f"Edited by {ed_str}"
        if pages:
            container += f", {pages}"
        container += "."
        parts.append(container)

    if address and publisher:
        parts.append(f"{address}: {publisher}.")
    elif publisher:
        parts.append(f"{publisher}.")
    if doi:
        parts.append(_format_doi(doi))

    return " ".join(parts)


def _format_inproceedings(author_str, year, title, entry) -> str:
    booktitle = _get_field(entry, "booktitle")
    doi = _get_field(entry, "doi")

    parts = [f'{author_str} {year}. {_quoted_title(title)}']
    if booktitle:
        parts.append(f"In *{booktitle}*.")
    if doi:
        parts.append(_format_doi(doi))

    return " ".join(parts)


def _format_phdthesis(author_str, year, title, entry) -> str:
    school = _get_field(entry, "school")
    parts = [f'{author_str} {year}. {_quoted_title(title)}']
    if school:
        parts.append(f"PhD diss., {school}.")
    return " ".join(parts)


def _format_misc(author_str, year, title, entry) -> str:
    doi = _get_field(entry, "doi")
    howpublished = _get_field(entry, "howpublished")

    parts = [f'{author_str} {year}. {_quoted_title(title)}']
    if howpublished:
        if howpublished.startswith("http"):
            parts.append(f"[{howpublished}]({howpublished}).")
        else:
            parts.append(f"{howpublished}.")
    if doi:
        parts.append(_format_doi(doi))

    return " ".join(parts)


def _sort_key(entry_tuple):
    """Sort key: full surname of first author/editor, then year."""
    _key, entry = entry_tuple
    persons = entry.persons.get("author", []) or entry.persons.get("editor", [])
    if not persons:
        return ("", "")
    surname = _get_full_surname(persons[0]).lower()
    year = _display_year(entry)
    return (surname, year)


# Substantive fields that count toward the dedup "richer entry wins" policy and
# that a survivor UNIONs in from a loser (spec v2.1). Markers/keywords/notes are
# excluded so METADATA_CLEANED noise cannot win a duplicate contest.
_SUBSTANTIVE_FIELDS = (
    "journal", "booktitle", "volume", "number", "pages",
    "publisher", "doi", "url", "abstract", "sep_context", "iep_context",
)


# Alias, not a copy - pinned by tests/test_generate_bibliography.py.
_normalize_title_for_key = title_key


def _fallback_key(entry) -> tuple[str, str, str] | None:
    """Title-axis dedup key: (normalized_title, year, first-author surname).

    Returns None if any component is empty (an entry with no fallback key is
    never title-deduped — GPT S4). Key construction is bib_identity.fallback_key,
    shared with dedupe_bib (ROADMAP item 4).
    """
    persons = entry.persons.get("author", []) or entry.persons.get("editor", [])
    surname = _get_full_surname(persons[0]) if persons else ""
    return fallback_key(_get_field(entry, "title"), _get_field(entry, "year"), surname)


def _substantive_field_count(entry) -> int:
    """Count populated substantive fields (dedup winner metric)."""
    return sum(1 for f in _SUBSTANTIVE_FIELDS if _get_field(entry, f))


def _entry_removed_fields(entry) -> set[str]:
    """Fields this entry's METADATA_CLEANED marker records as removed."""
    return set(marker_removed_fields(entry.fields.get("keywords", "") or ""))


def _apply_cleaner_verdicts(winner, loser) -> None:
    """Strip loser-flagged fields from the winner and fold the names into
    the winner's marker (item 3 A, mirrored from dedupe_bib)."""
    removed = _entry_removed_fields(loser)
    if not removed:
        return
    for f in list(winner.fields.keys()):
        if f.lower() in removed:
            del winner.fields[f]
    already = _entry_removed_fields(winner)
    to_add = sorted(removed - already)
    if not to_add:
        return
    kw = (winner.fields.get("keywords", "") or "").rstrip().rstrip(",")
    if "_CLEANED" in kw.replace("\\", ""):
        winner.fields["keywords"] = kw + ", " + ", ".join(to_add)
    else:
        marker = "METADATA_CLEANED: " + ", ".join(to_add)
        winner.fields["keywords"] = (kw + ", " + marker) if kw else marker


def _union_substantive_fields(winner, loser) -> None:
    """Union the loser's substantive fields into the winner (spec v2.1 / ADV-A0).

    Copies every field in _SUBSTANTIVE_FIELDS that the loser has and the winner
    lacks (or has empty). Operates on raw field values so the merged entry
    re-serializes cleanly.
    """
    blocked = _entry_removed_fields(winner) | _entry_removed_fields(loser)
    for f in _SUBSTANTIVE_FIELDS:
        if f in blocked:
            continue
        if not _get_field(winner, f) and _get_field(loser, f):
            winner.fields[f] = loser.fields[f]


def _carry_year_suffix(winner, winner_key: str, loser, loser_key: str) -> None:
    """Item 3 F, mirrored from dedupe_bib.merge_entries: this dedup pass
    picks its winner by _substantive_field_count, a DIFFERENT criterion than
    dedupe_bib's (abstract-then-importance), so the survivor here can be a
    different copy than the one dedupe_bib kept - and this function's output
    IS what format_entry renders into the delivered References. year_suffix
    is deliberately excluded from _SUBSTANTIVE_FIELDS (same reason as
    dedupe_bib's _KNOWN_FIELDS entry: unioning it there would be coupled to
    no particular journal/identity check), so it needs this same explicit
    unanimous / copy-up / conflict policy independently, not inherited from
    the union above.
    """
    winner_suffix = _get_field(winner, "year_suffix").strip()
    loser_suffix = _get_field(loser, "year_suffix").strip()
    if winner_suffix and loser_suffix and winner_suffix != loser_suffix:
        print(
            f"  [SUFFIX] conflict: '{winner_key}' and '{loser_key}' carry "
            f"'{winner_suffix}' and '{loser_suffix}' - keeping "
            f"'{winner_suffix}', not picking one",
            file=sys.stderr)
    elif not winner_suffix and loser_suffix:
        winner.fields["year_suffix"] = loser.fields["year_suffix"]


def _remap_index(mapping: dict, old_key: str, new_key: str) -> None:
    """Repoint any dedup-index entries from old_key to new_key (winner swap)."""
    for k, v in list(mapping.items()):
        if v == old_key:
            mapping[k] = new_key


def _collect_matches(review_text: str, bib_data) -> list[dict]:
    """Find bib entries whose surname+year proximity pattern matches in
    review_text. The matching pre-pass of find_cited_entries.

    Returns one record per MATCHED entry, in bib_data.entries iteration
    order: {"key", "entry", "surname", "year", "windows"} where windows is
    list[str] - the ±_MATCH_WINDOW haystack slice around each surname hit
    whose window contains the year. EVERY year-bearing window is collected,
    not just the first hit - windows may come from either haystack (norm or
    translit). Collision resolution (_resolve_collisions) does not consume
    this list's contents - it re-parses citation instances straight from
    review_text via _citation_instances - so windows is only ever used for
    its truthiness (a match exists) and length (how many hits); it does not
    carry hit spans.
    """
    norm_text = _normalize_for_matching(review_text)
    # Second haystack, transliterated (ä->ae etc.) before the NFKD strip, so
    # a bib surname's ae-spelling meets a prose surname's diacritic (item 3
    # B, review P0: norm_text alone only catches the reverse direction).
    translit_text = translit_fold(review_text)
    # Script-preserving haystack for non-Latin surnames, built only if some
    # entry needs it (see the empty-fold fallback below).
    script_text = None
    records = []

    for key, entry in bib_data.entries.items():
        # Get first person (author or editor fallback)
        persons = entry.persons.get("author", [])
        if not persons:
            persons = entry.persons.get("editor", [])
        if not persons:
            continue

        surname = _get_full_surname(persons[0])
        year = _get_field(entry, "year")
        if not surname or not year:
            continue

        norm_surname = _normalize_for_matching(surname)
        if not any(c.isalnum() for c in norm_surname):
            # The ASCII fold kept nothing that can identify anyone. A wholly
            # non-Latin surname (Greek, Cyrillic) folds to '', and skipping
            # here deleted a cited work from the References outright; a
            # hyphenated one folds to '-' and matched a garbage pattern
            # (\b-\b hits essentially every inter-word hyphen), so the entry
            # was spuriously INCLUDED instead (ROADMAP item 4 + follow-up).
            # Fall back to a script-preserving key, searched over the review
            # text folded the same way, so the entry is judged on its name.
            #
            # Known limit, deliberate: the year test below is a substring
            # match, so a non-numeric or bracketed year ("n.d.", "[2021]")
            # still cannot match in this haystack.
            norm_surname = title_key(surname)
            if not norm_surname:
                continue
            if script_text is None:
                script_text = title_key(review_text)
            needles = {norm_surname}
            haystacks = (script_text,)
        else:
            # Symmetric transliteration matching (item 3 B, review P0):
            # every needle variant (the plain NFKD fold AND the ae-spelling)
            # is tried against both haystacks, so a bib "Mueller" meets
            # prose "Müller" and a bib "Fränken" meets prose "Fraenken"
            # alike - not just the direction norm_text alone covers.
            needles = ascii_variants(surname)
            haystacks = (norm_text, translit_text)

        # Word-boundary, case-insensitive surname match. The proximity
        # window is always sliced from the haystack that produced the hit
        # (translit_text's offsets differ from norm_text's: ae/ss lengthen
        # the text, so a window can't be sliced from the "wrong" haystack).
        # Every year-bearing window is kept, not just the first hit.
        windows = []
        for needle in needles:
            try:
                pattern = re.compile(r"\b" + re.escape(needle) + r"\b", re.IGNORECASE)
            except re.error:
                continue
            for haystack in haystacks:
                for m in pattern.finditer(haystack):
                    start = max(0, m.start() - _MATCH_WINDOW)
                    end = min(len(haystack), m.end() + _MATCH_WINDOW)
                    window = haystack[start:end]
                    if year in window:
                        windows.append(window)

        if not windows:
            continue

        records.append({
            "key": key,
            "entry": entry,
            "surname": surname,
            "year": year,
            # Item 3 F: the Chicago letter this entry carries, "" when it has
            # none. The window test above stays on the bare year - prose
            # "2010a" contains "2010", so MATCHING is unchanged and only
            # _resolve_collisions' DISCRIMINATION is new.
            "suffix": _entry_suffix(entry),
            "windows": windows,
        })

    return records


# A second surname may carry lowercase particles: "and de la Cruz",
# "and van der Waals" (review 2.7). The FIRST surname stays single-token -
# a particled first surname ("van der Deijl") never intersects an
# instance's variants, so its group safely falls to warn-and-keep-all
# rather than dropping anything (document as a known limit).
_PARTICLED_SURNAME = r"(?:[a-zà-ÿ'’-]+\s+)*[A-ZÀ-Þ][\w'’À-ÿ-]+"
_CITE_INSTANCE_RE = re.compile(
    r"(?:(?P<first>[A-ZÀ-Þ][\w.À-ÿ]*)\s+)?"          # initial/first name (optional)
    r"(?P<surname>[A-ZÀ-Þ][\w'’À-ÿ-]+)"
    r"(?:'s|’s)?"
    r"(?:(?P<etal>\s+et al\.?)"
    r"|(?:,?\s+and\s+(?P<second>" + _PARTICLED_SURNAME + r")))?"
    r"(?:'s|’s)?"
    r"[\s,]*\(?\s*(?P<year>(?:1[6-9]|20)\d{2})(?P<suffix>[a-z])?\b"
)

# A year continuation inside the SAME citation: ";" or "," then another year.
# \A-anchored, so it only ever matches text immediately following the previous
# year -- "Menary (2010), 2011 saw a shift" does not continue, because the ")"
# sits between them.
_CONTINUATION_RE = re.compile(
    r"\A\s*[;,]\s*(?P<year>(?:1[6-9]|20)\d{2})(?P<suffix>[a-z])?\b")

# _CITE_INSTANCE_RE has no left anchor, so it can start matching at the
# SECOND name of a longer list ("Smith, Jones, and Lee (2020)" ->
# surname="Jones", second="Lee") or right after an ampersand ("Jones & Lee
# (2020)" -> surname="Lee", form=solo), manufacturing an instance that
# names the wrong person(s) as first author. Reject a match whose
# immediately preceding text ends in a capitalized name followed by
# ", and "/" & " (a dropped list member) or a bare ", " (a name-comma
# lead-in the surname group swallowed past). Fails toward keep-all: a
# rejected match yields no instance for its group, which then falls to
# _resolve_collisions' ambiguous-keep-all branch rather than a drop -
# never the reverse.
#
# The bare-comma half needs one exclusion. A sentence-initial transition word
# ("However, Muldoon (2023) argues...") has the identical shape - one
# capitalized word, a comma, a space - so it was rejecting legitimate
# citations whose only sighting was such a lead-in, and the group then fell to
# keep-all-and-warn. Transitions are a closed-enough class to list; the
# `and`/`&` half is unaffected because no transition word is followed by
# "and"/"&" in that position. An unlisted transition still degrades to
# keep-all, never to a drop, so the list being incomplete is safe.
_SENTENCE_LEAD_INS = (
    "However|Moreover|Nevertheless|Nonetheless|Furthermore|Therefore|Thus|"
    "Hence|Accordingly|Consequently|Instead|Conversely|Similarly|Likewise|"
    "Indeed|Admittedly|Arguably|Notably|Crucially|Importantly|Interestingly|"
    "Strikingly|Famously|Relatedly|Alternatively|Meanwhile|Overall|Finally|"
    "Ultimately|First|Second|Third|Fourth|Fifth|Recently|Historically|"
    "Traditionally|Classically|Typically|Generally|Specifically|Broadly|"
    "Roughly|Strictly|Formally|Initially|Subsequently|Originally|Again|"
    "Still|Yet|Rather|Otherwise|Equally|Correspondingly|Unsurprisingly|"
    "Surprisingly|Curiously|Tellingly|Plainly|Clearly|Obviously|Presumably"
)
_NON_INITIAL_PRECEDING_RE = re.compile(
    r"(?:[A-ZÀ-Þ][\w'’À-ÿ-]+,?\s+(?:and|&)\s+"
    r"|(?!(?:" + _SENTENCE_LEAD_INS + r")\b)[A-ZÀ-Þ][\w'’À-ÿ-]+,\s+)$"
)


def _strip_possessive(s: str) -> str:
    """Drop a trailing possessive marker ('s / ’s) from a captured name.

    The surname/second character classes admit apostrophes (for names like
    O'Brien), so the regex's own trailing `(?:'s|’s)?` groups never get a
    chance to match - greedy `+` already swallowed "Moore's" whole, with
    nothing downstream forcing backtracking. The doubled `(?:'s|’s)?` in
    _CITE_INSTANCE_RE (once after surname, once after the etal/and
    alternation) is the evidence the possessive was meant to be stripped;
    this restores that intent without touching the character class (which
    would risk mangling genuine apostrophed surnames)."""
    for suf in ("'s", "’s"):
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


def _citation_instances(review_text: str) -> list[dict]:
    """Parse author-year citation instances from the ORIGINAL text.
    Each: {"surname_variants", "form", "second_text", "first_text", "year",
    "suffix"}.
    form: 'solo' | 'and' | 'etal'. second_text may be a multiword particled
    surname - compared whole-to-whole against candidate second-surname
    variants, never tokenized; first_text is the raw leading token ('' when
    absent) and is applied only when informative (see candidate rule).

    Matches whose preceding text shows they bind at a non-initial name
    (C1: _NON_INITIAL_PRECEDING_RE) are rejected outright and contribute no
    instance - see that regex's docstring for why."""
    out = []
    for m in _CITE_INSTANCE_RE.finditer(review_text):
        if _NON_INITIAL_PRECEDING_RE.search(review_text[:m.start()]):
            continue
        surname = _strip_possessive(m.group("surname"))
        if m.group("etal"):
            form, second = "etal", ""
        elif m.group("second"):
            form, second = "and", _strip_possessive(m.group("second"))
        else:
            form, second = "solo", ""
        out.append({
            "surname_variants": ascii_variants(surname),
            "form": form,
            "second_text": second,
            "first_text": (m.group("first") or "").rstrip("."),
            "year": m.group("year"),
            # Item 3 F: the Chicago letter the PROSE carries, "" when none.
            "suffix": (m.group("suffix") or ""),
        })
        # One surname, several years: "Menary (2006, 2010, 2013)", "Wiens
        # (2015a; 2015b)" -- the shape 8 of 32 delivered reviews already use.
        # _CITE_INSTANCE_RE matches only the first year, so without this the
        # later works have no supporting instance and _resolve_collisions drops
        # them: a regression F would INTRODUCE rather than fix. Continuations
        # can only ADD support, never remove it, so a spurious one costs a kept
        # work (safe) and never a dropped one.
        #
        # Every key inherited from out[-1] is invariant across a continuation
        # run - surname_variants, form, second_text and first_text all belong
        # to the single author-list this parenthesis opened with, and only the
        # year and its letter vary. There is no positional key to copy: the
        # resolver derives first_pos_seen itself.
        tail = review_text[m.end():]
        while True:
            cont = _CONTINUATION_RE.match(tail)
            if not cont:
                break
            out.append({**out[-1], "year": cont.group("year"),
                        "suffix": (cont.group("suffix") or "")})
            tail = tail[cont.end():]
    return out


def _ascii(s: str) -> str:
    return s.encode("ascii", "backslashreplace").decode("ascii")


def _persons_of(rec):
    e = rec["entry"]
    return e.persons.get("author", []) or e.persons.get("editor", [])


def _first_text_informative(first_text: str, members: list[dict]) -> bool:
    """A captured pre-surname token discriminates only when it names SOME
    group member's first author - sentence-leading words ("As Muldoon...")
    are captured too and must read as prose, not as a first name."""
    ft = ascii_variants(first_text)
    ftl = first_text.lower()
    for rec in members:
        persons = _persons_of(rec)
        if not persons:
            continue
        fn = ascii_variants(_get_first_names(persons[0]))
        if ft & fn or ftl in {v[0] for v in fn if v}:
            return True
    return False


def _second_position_corroborated(inst: dict, member_variants: frozenset, records: list[dict]) -> bool:
    """Is a second-position sighting backed by an actual bib record, or just
    a narrative co-mention (I1)?

    "Bloggs and Muldoon (2023)" is positive evidence against a Muldoon
    group only when some bib record's own author list explains it: first
    author variant-intersects the instance's (first-position) surname, and
    second author variant-intersects this group's variants, same year.
    Without that, the sighting is an uncorroborated narrative aside -
    "Following Kripke and Putnam (1975), reference is causal" with no
    Kripke-Putnam bib record - and must not license a drop of the Putnam
    group. Searches all of _collect_matches' MATCHED records, not just
    this group, since the corroborating entry's first author (e.g.
    "Bloggs") is a different surname/group entirely. An entry that never
    matched anything in the prose can't corroborate either - the safe
    direction, since that only means falling through to keep-all."""
    for rec in records:
        if rec["year"] != inst["year"]:
            continue
        if not (inst["surname_variants"] & rec["_variants"]):
            continue
        persons = _persons_of(rec)
        if len(persons) >= 2 and (
                ascii_variants(_get_full_surname(persons[1])) & member_variants):
            return True
    return False


def _members_are_distinct_works(members: list[dict]) -> bool:
    """Do these collision-group members name pairwise-distinct works?

    _resolve_collisions runs BEFORE find_cited_entries' dedup, so a group can
    hold two COPIES of one work - which item 3 F's suffix filter must not read
    as two lettered works. Duplication is tested on the same two axes dedup
    itself uses: a shared non-empty normalized DOI, or a shared fallback key.
    Either one alone is enough, so this is a pairwise scan rather than a single
    tuple identity (groups are tiny). The GPT-B4 DOI-set refusal is deliberately
    NOT replicated: here the permissive direction is the safe one, because any
    hint of duplication disables the filter and falls through to keep-all.
    """
    dois, fkeys = [], []
    for rec in members:
        doi = _get_field(rec["entry"], "doi")
        dois.append(_normalize_doi(doi) if doi else "")
        fkeys.append(_fallback_key(rec["entry"]))
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            if dois[i] and dois[i] == dois[j]:
                return False
            if fkeys[i] is not None and fkeys[i] == fkeys[j]:
                return False
    return True


def _resolve_collisions(records: list[dict], review_text: str) -> list[dict]:
    """Item 3 E (external-review design): group colliding records by
    variant-intersection connected components per year; resolve each group
    by per-citation-instance candidate sets parsed from the ORIGINAL text;
    keep the union of supported members; drop only what no instance
    supports - and only when the group parsed at least one instance.

    first-position and second-position evidence are tracked SEPARATELY per
    group (post-review fix): a second-position-only sighting ("Bloggs and
    Muldoon (2023)" against a Muldoon-first-author group) must drop the
    group only when NO first-position instance exists for it at all, AND
    the sighting is corroborated by an actual bib record (I1,
    _second_position_corroborated) - an uncorroborated narrative co-mention
    ("Following Kripke and Putnam (1975)" with no Kripke bib entry) is not
    evidence against the group. An unrelated second-position sighting
    elsewhere in the text must never flip an unresolved first-position
    instance (e.g. "Muldoon and Gordon (2023)", which matches no candidate)
    from ambiguous-keep-all into a drop - partial ambiguity never drops a
    cited work, and "cited" includes works named only via an unresolvable
    first-position form."""
    for rec in records:
        rec["_variants"] = ascii_variants(rec["surname"]) or \
            frozenset({rec["surname"].lower()})
    groups: list[list[dict]] = []
    for rec in records:
        hits = [g for g in groups if g[0]["year"] == rec["year"]
                and any(rec["_variants"] & r["_variants"] for r in g)]
        for g in hits[1:]:
            hits[0].extend(g)
            groups.remove(g)
        if hits:
            hits[0].append(rec)
        else:
            groups.append([rec])

    instances = None  # parsed lazily, once, only if some group collides
    keep = []
    for members in groups:
        if len(members) == 1:
            keep.append(members[0])
            continue
        if instances is None:
            instances = _citation_instances(review_text)
        member_variants = frozenset().union(*(r["_variants"] for r in members))
        # Item 3 F: is this group STRUCTURALLY COMPLETE - every member
        # lettered, all letters distinct, and the members distinct WORKS?
        # Only then may a prose letter drop anything (see the filter below).
        #
        # The third conjunct is not redundant. This function runs BEFORE
        # find_cited_entries' dedup, so a group can hold two COPIES of one
        # work carrying conflicting letters - precisely the state
        # _carry_year_suffix exists to report. Filtering on the letter there
        # drops one copy before the merge can happen, which silences the
        # [SUFFIX] conflict warning and, when the prose cites the loser's
        # letter, leaves the SPARSER copy as the delivered reference
        # (measured: prose "Smith (2020b)" kept a journal-less duplicate over
        # its journal- and abstract-bearing twin).
        letters = [r.get("suffix") or "" for r in members]
        fully_lettered = (all(letters) and len(set(letters)) == len(letters)
                          and _members_are_distinct_works(members))
        year = members[0]["year"]
        supported = set()
        first_pos_seen = False
        second_pos_seen = False
        # Letters the prose used that match no member of THIS group. Per-group
        # (not function-scope): at function scope one group's typo would leak
        # into every later group. Holds the letters, not just a flag, so the
        # warning can name the citation the operator has to go and fix; its
        # truthiness is what the branch conditions below read.
        unmatched_letters = set()
        for inst in instances:
            if inst["year"] != year:
                continue
            if not (inst["surname_variants"] & member_variants):
                # Not cited as first author here - but if this group's
                # surname is the SECOND author of an "and" instance (e.g.
                # "Bloggs and Muldoon (2023)" against a Muldoon-first-
                # author group) AND that sighting is corroborated by an
                # actual bib record (I1), that is positive evidence against
                # the group, not narrative silence: note it separately from
                # first-position evidence (see docstring) rather than
                # folding it into one any_instance flag. An uncorroborated
                # sighting (no bib record explains it) is left unset here,
                # so it falls through to ambiguous-keep-all like any other
                # unparseable narrative mention.
                if inst["form"] == "and" and (
                        ascii_variants(inst["second_text"]) & member_variants) and (
                        _second_position_corroborated(inst, member_variants, records)):
                    second_pos_seen = True
                continue
            first_pos_seen = True
            cands = []
            for rec in members:
                if not (inst["surname_variants"] & rec["_variants"]):
                    continue
                persons = _persons_of(rec)
                n = len(persons)
                if inst["form"] == "etal" and n >= 3:
                    cands.append(rec)
                elif inst["form"] == "and" and n == 2 and (
                        ascii_variants(inst["second_text"])
                        & ascii_variants(_get_full_surname(persons[1]))):
                    cands.append(rec)
                elif inst["form"] == "solo" and n == 1:
                    if inst["first_text"] and _first_text_informative(
                            inst["first_text"], members):
                        fn = ascii_variants(_get_first_names(persons[0]))
                        init = {v[0] for v in fn if v}
                        if not (ascii_variants(inst["first_text"]) & fn
                                or inst["first_text"].lower() in init):
                            continue
                    cands.append(rec)
            # Item 3 F: a Chicago letter is the only token that can separate
            # two works by the SAME author in the same year. When the prose
            # carries one, it filters the candidate set; when it matches no
            # member at all (a writer typo, or a letter for a work that never
            # made it into the bib), the group must fall through to
            # ambiguous-keep-all - a drop here would delete a cited work,
            # which is the failure Issue B exists to prevent.
            #
            # The filter applies ONLY to a structurally complete group - see
            # fully_lettered above for all three conjuncts. The barrier's assigner
            # letters a group whole or suppresses it whole (year_suffix.py's
            # whole-group suppression), so a PARTIALLY lettered group here
            # means the letters did not come from one clean assignment run:
            # a legacy or hand-edited bib, a bib assembled from two runs, or
            # -- the common case -- a DIFFERENT author who happens to share
            # this surname and year and so was never in the lettered group at
            # all. In any of those a suffixed instance would otherwise select
            # the lettered member and drop every unlettered one. Incomplete
            # groups fall through to item 3 E's behaviour unchanged.
            if fully_lettered and inst["suffix"]:
                matched = [r for r in cands if r.get("suffix") == inst["suffix"]]
                if matched:
                    cands = matched
                else:
                    unmatched_letters.add(inst["suffix"])
                    cands = []
            if cands:
                supported.update(r["key"] for r in cands)
                if len(cands) > 1:
                    print("  [COLLISION] ambiguous: instance '"
                          + _ascii(min(inst["surname_variants"]))
                          + " " + year + "' (" + inst["form"] + ") matches "
                          + ", ".join(sorted(_ascii(r["key"]) for r in cands)),
                          file=sys.stderr)
        if first_pos_seen and supported and not unmatched_letters:
            # At least one first-position instance discriminated some
            # members - keep those, drop the rest.
            #
            # Item 3 F: an unmatched letter anywhere in the group disables
            # dropping for the WHOLE group, even when other instances did
            # discriminate ("Menary (2010a) ...; Menary (2010c) ..."). That is
            # deliberate, not an oversight: the letter that matched nothing
            # names a work we cannot identify, so we do not know which member
            # -- if any -- it was meant to support, and dropping on the
            # remaining evidence could delete exactly that work.
            for rec in members:
                if rec["key"] in supported:
                    keep.append(rec)
                else:
                    print("  [COLLISION] dropped " + _ascii(rec["key"])
                          + ": shares surname/year with "
                          + ", ".join(sorted(_ascii(r["key"]) for r in members
                                             if r is not rec))
                          + " and no citation instance supports it",
                          file=sys.stderr)
        elif first_pos_seen or unmatched_letters:
            # A first-position form was parsed for this group but matched
            # no candidate (e.g. "Muldoon and Gordon" against a and-Wu/
            # and-Qi pair) - genuinely ambiguous, not evidence against
            # anyone. A second-position sighting elsewhere in the text
            # must NOT override this into a drop.
            #
            # The `or unmatched_letters` disjunct is currently redundant:
            # a letter can only go unmatched inside the block that has
            # already set first_pos_seen = True. It is kept as a guard
            # against a later edit reordering those assignments, which would
            # otherwise silently route an unmatched-letter group into the
            # second-position DROP branch below.
            keep.extend(members)
            if unmatched_letters:
                # The generic message ("no parseable citation form
                # discriminates") is FALSE here: the form parsed fine, the
                # letter matched no member. Name the citation as the prose
                # wrote it, so a live-run operator can find the writer's typo.
                print("  [COLLISION] ambiguous: "
                      + ", ".join(sorted(_ascii(r["key"]) for r in members))
                      + " share surname/year and the cited letter "
                      + ", ".join(_ascii(year + s)
                                  for s in sorted(unmatched_letters))
                      + " matches no entry - all kept, possible phantom"
                      " references",
                      file=sys.stderr)
            else:
                print("  [COLLISION] ambiguous: "
                      + ", ".join(sorted(_ascii(r["key"]) for r in members))
                      + " share surname/year and no parseable citation form"
                      " discriminates - all kept, possible phantom references",
                      file=sys.stderr)
        elif second_pos_seen:
            # No first-position instance names this group at all - the
            # only parsed explanation for the loose surname/year matches
            # is a co-author position, so nothing here is actually cited.
            for rec in members:
                print("  [COLLISION] dropped " + _ascii(rec["key"])
                      + ": shares surname/year with "
                      + ", ".join(sorted(_ascii(r["key"]) for r in members
                                         if r is not rec))
                      + " and no citation instance supports it",
                      file=sys.stderr)
        else:
            keep.extend(members)
            print("  [COLLISION] ambiguous: "
                  + ", ".join(sorted(_ascii(r["key"]) for r in members))
                  + " share surname/year and no parseable citation form"
                  " discriminates - all kept, possible phantom references",
                  file=sys.stderr)

    order = {id(r): i for i, r in enumerate(records)}
    keep.sort(key=lambda r: order[id(r)])
    return keep


def find_cited_entries(review_text: str, bib_data) -> list[tuple[str, object]]:
    """Find BibTeX entries cited in the review text.

    Matching runs in two stages before this function's own dedup.
    _collect_matches finds every candidate whose surname+year proximity
    pattern appears in the prose (dual-haystack: plain NFKD and
    transliterated, tried symmetrically). _resolve_collisions (item 3 E)
    then groups candidates sharing (first-author surname, year) and resolves
    each group against citation instances parsed from the prose: a
    discriminating instance (second-author surname, et al., or a solo
    author's first initial) drops the members it does not support; an
    ambiguous or unparseable group is kept whole with a stderr warning -
    partial ambiguity never silently drops a cited work.

    Returns list of (key, entry) tuples for cited entries, deduplicated by DOI
    and, as a fallback, by (normalized title, year, first-author surname).
    Winner of a duplicate pair is the entry with more populated substantive
    fields (tie-break: lexicographically-first citation key); the survivor
    additionally UNIONs in any substantive field only the loser had (spec v2.1).
    DOI identity is tracked per dedup GROUP: a fallback-key merge is refused when
    the two groups' non-empty DOI sets differ (GPT-B4).
    """
    records = _resolve_collisions(_collect_matches(review_text, bib_data), review_text)

    cited = {}  # key -> entry
    seen_dois = {}  # normalized_doi -> citation_key
    seen_titles = {}  # (title, year, surname) -> citation_key
    group_dois = {}  # citation_key -> set of normalized DOIs across the group

    for record in records:
        key = record["key"]
        entry = record["entry"]

        # Deduplication (defense-in-depth; dedupe_bib.py handles this upstream).
        # Two entries are duplicates when their DOIs match OR their fallback keys
        # match — EXCEPT never merge two GROUPS whose non-empty DOI sets differ.
        doi = _get_field(entry, "doi")
        norm_doi = _normalize_doi(doi) if doi else ""
        new_dois = {norm_doi} if norm_doi else set()
        fkey = _fallback_key(entry)

        existing_key = None
        if norm_doi and norm_doi in seen_dois:
            existing_key = seen_dois[norm_doi]
        elif fkey is not None and fkey in seen_titles:
            candidate = seen_titles[fkey]
            cand_dois = group_dois.get(candidate, set())
            # Distinct non-empty DOI sets => genuinely different works; keep both.
            if not (new_dois and cand_dois and new_dois != cand_dois):
                existing_key = candidate

        if existing_key is not None:
            existing_entry = cited[existing_key]
            merged_dois = group_dois.get(existing_key, set()) | new_dois
            new_score = _substantive_field_count(entry)
            old_score = _substantive_field_count(existing_entry)
            if new_score > old_score or (new_score == old_score and key < existing_key):
                # New entry wins the pair; union the loser's substantive fields in.
                _apply_cleaner_verdicts(entry, existing_entry)
                _union_substantive_fields(entry, existing_entry)
                _carry_year_suffix(entry, key, existing_entry, existing_key)
                del cited[existing_key]
                cited[key] = entry
                _remap_index(seen_dois, existing_key, key)
                _remap_index(seen_titles, existing_key, key)
                group_dois.pop(existing_key, None)
                group_dois[key] = merged_dois
                if norm_doi:
                    seen_dois[norm_doi] = key
                if fkey is not None:
                    seen_titles[fkey] = key
                print(f"  [DEDUP] {key} replaces {existing_key} (duplicate)", file=sys.stderr)
            else:
                # Existing entry wins; union the loser's (new) substantive fields in.
                _apply_cleaner_verdicts(existing_entry, entry)
                _union_substantive_fields(existing_entry, entry)
                _carry_year_suffix(existing_entry, existing_key, entry, key)
                group_dois[existing_key] = merged_dois
                if norm_doi:
                    # A DOI the loser carried now resolves to the surviving winner.
                    seen_dois[norm_doi] = existing_key
                print(f"  [DEDUP] {key} skipped, keeping {existing_key} (duplicate)", file=sys.stderr)
            continue

        # New dedup group.
        if norm_doi:
            seen_dois[norm_doi] = key
        # Only claim the title key if unclaimed — a merge refused on DOI-set
        # grounds must not steal the first group's title pointer (GPT-B4).
        if fkey is not None and fkey not in seen_titles:
            seen_titles[fkey] = key
        group_dois[key] = new_dois
        cited[key] = entry

    return list(cited.items())


def generate_references(entries: list[tuple[str, object]]) -> str:
    """Format cited entries as a ## References section."""
    # Sort by first author surname, then year
    sorted_entries = sorted(entries, key=_sort_key)

    lines = ["## References", ""]
    for key, entry in sorted_entries:
        formatted = format_entry(entry, key)
        if formatted:
            lines.append(formatted)
            lines.append("")

    return "\n".join(lines).rstrip("\n")


def apply_references(review_text: str, references_section: str) -> str:
    """Replace or append ## References section in the review text."""
    # Check for existing ## References
    pattern = re.compile(r"^## References\s*$", re.MULTILINE)
    match = pattern.search(review_text)

    if match:
        # Replace from ## References to EOF
        return review_text[:match.start()].rstrip("\n") + "\n\n" + references_section + "\n"
    else:
        # Append
        return review_text.rstrip("\n") + "\n\n" + references_section + "\n"


def main():
    if len(sys.argv) != 3:
        print("Usage: generate_bibliography.py <review.md> <literature.bib>", file=sys.stderr)
        sys.exit(1)

    review_path = Path(sys.argv[1])
    bib_path = Path(sys.argv[2])

    if not review_path.exists():
        print(f"Error: Review file not found: {review_path}", file=sys.stderr)
        sys.exit(1)
    if not bib_path.exists():
        print(f"Error: BibTeX file not found: {bib_path}", file=sys.stderr)
        sys.exit(1)

    review_text = review_path.read_text(encoding="utf-8")
    bib_data = parse_file(str(bib_path), bib_format="bibtex")

    cited = find_cited_entries(review_text, bib_data)

    total = len(bib_data.entries)
    matched = len(cited)
    print(f"Matched {matched}/{total} BibTeX entries as cited", file=sys.stderr)

    if not cited:
        print("Warning: No cited entries found. No references generated.", file=sys.stderr)
        sys.exit(0)

    # Log matched entries
    for key, _entry in sorted(cited, key=lambda x: x[0]):
        print(f"  + {key}", file=sys.stderr)

    references = generate_references(cited)
    result = apply_references(review_text, references)
    review_path.write_text(result, encoding="utf-8")

    print(f"Wrote ## References ({matched} entries) to {review_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
