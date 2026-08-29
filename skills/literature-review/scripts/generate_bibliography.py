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
    ascii_variants, contract_fold, fallback_key, normalize_doi, title_key,
    translit_fold,
)
from metadata_cleaner import marker_removed_fields  # noqa: E402

sys.path.pop(0)

# The References-boundary scanner, imported rather than reimplemented: this
# script has a read side (_strip_references_section) and a write side
# (apply_references), lint_md has a third, and all three must agree on what
# counts as the boundary. They did not - lint_md was fence-aware and this
# script was not - see find_refs_heading's docstring for what that cost.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint_md import find_refs_heading  # noqa: E402

sys.path.pop(0)

# Proximity window for surname↔year matching (chars)
_MATCH_WINDOW = 60


def clean_bibtex_str(s: str) -> str:
    """Normalize a BibTeX string: LaTeX accents → braces → \\& → \\url{}."""
    # Step 0a: ellipsis command BEFORE the escapes loop -- LATEX_ESCAPES
    # contains \l (l-slash), which otherwise fires inside \ldots and
    # delivered 'isłdots' into a References line. The terminator matters:
    # `\ldotsfoo` is a DIFFERENT (unknown) control sequence and must not be
    # rewritten to '...foo'. Guard on non-LETTER, not on `\b` -- a TeX
    # control word terminates at any non-letter, so `\b` was stricter than
    # TeX and regressed `page 3\ldots42` and `\ldots_x` into the very `\l`
    # l-slash fold this line exists to prevent.
    s = re.sub(r"\\ldots(?![A-Za-z])(\{\})?", "...", s)
    # Step 0b: text-style commands -- drop the command token, keep the
    # argument (the existing brace strip below unwraps it). Without this a
    # References line read 'Precis of \textitUtopophobia'.
    s = re.sub(r"\\(textit|emph|textbf|textsc)\b\s*", "", s)

    # Step 1: LaTeX accent-inside-braces → Unicode
    # Handle both {\'e} and \'e forms
    for latex, uni in sorted(LATEX_ESCAPES.items(), key=lambda kv: -len(kv[0])):
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

    Deliberately NOT bib_identity.title_key: this
    folds author-written review prose, and it must keep punctuation because the
    60-character _MATCH_WINDOW is sliced from whichever haystack produced a
    hit - this function's output (norm_text), bib_identity.translit_fold's
    (translit_text, symmetric transliteration matching) or
    bib_identity.contract_fold's (contract_text, digraph contraction),
    all of which keep punctuation for the same reason. Pinned by this file's
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
    assigned, plain `2010` otherwise.

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

    Normalizes first: rendering the raw field meant
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
    # A chapter's `series` (disambiguate_container's per-parent enrichment) is
    # deliberately NOT rendered: Chicago author-date treats a series as
    # optional, and the delivered .bib keeps the field for toolchains whose
    # styles do render it. Best-effort enrichment stays machine-readable
    # without adding unverified decoration to the References.
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
    # demotion stripped the booktitle, suppress the dangling "In." connective:
    # emit editors/pages without the orphaned "In".
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
    # Barrier-authored, so their presence means the entry passed the
    # web gate this run. Chicago provides for both, and the archive link is
    # link-rot insurance rather than content attestation -- availability
    # matches the URL string, and news and org hosts reassign URLs.
    urldate = _get_field(entry, "urldate")
    archiveurl = _get_field(entry, "archiveurl")

    parts = [f'{author_str} {year}. {_quoted_title(title)}']
    if howpublished:
        if howpublished.startswith("http"):
            parts.append(f"[{howpublished}]({howpublished}).")
        else:
            parts.append(f"{howpublished}.")
    if urldate:
        parts.append(f"Accessed {urldate}.")
    if archiveurl:
        parts.append(f"Archived at [{archiveurl}]({archiveurl}).")
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
# that a survivor UNIONs in from a loser. Markers/keywords/notes are
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
    never title-deduped). Key construction is bib_identity.fallback_key,
    shared with dedupe_bib.
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
    the winner's marker (mirrored from dedupe_bib)."""
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
    """Union the loser's substantive fields into the winner.

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
    """Chicago letters, mirrored from dedupe_bib.merge_entries: this dedup pass
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
    order: {"key", "entry", "surname", "year", "suffix", "windows"} where
    suffix is the entry's Chicago letter ("" when it has none -
    the discriminator _resolve_collisions filters candidates by) and windows
    is list[str] - the ±_MATCH_WINDOW haystack slice around each surname hit
    whose window contains the year. EVERY year-bearing window is collected,
    not just the first hit - windows may come from any of the three
    haystacks (norm, translit, or contract). Collision resolution
    (_resolve_collisions) does not consume this list's contents - it
    re-parses citation instances straight from
    review_text via _citation_instances - so windows is only ever used for
    its truthiness (a match exists) and length (how many hits); it does not
    carry hit spans.
    """
    norm_text = _normalize_for_matching(review_text)
    # Second haystack, transliterated (ä->ae etc.) before the NFKD strip, so
    # a bib surname's ae-spelling meets a prose surname's diacritic (norm_text
    # alone only catches the reverse direction).
    translit_text = translit_fold(review_text)
    # Third haystack, digraph-contracted (ae->a, oe->o, ue->u on top of the
    # translit fold): needle-side ascii_variants already contracts the BIB
    # surname, which covers bib-digraph-meets-prose-plain ("Fraenken" bib
    # meeting "Franken" prose); the filed direction is the reverse (bib
    # "Franken", prose "Fraenken") and needs the haystack contracted too.
    contract_text = contract_fold(review_text)
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
            # was spuriously INCLUDED instead.
            # Fall back to a script-preserving key, searched over the review
            # text folded the same way, so the entry is judged on its name.
            #
            # Known limit, deliberate: the year test below is a substring
            # match, so a non-numeric or bracketed year ("n.d.", "[2021]")
            # still cannot match in this haystack. A related residual sits on
            # the other side of the guard: a surname that folds to
            # punctuation PLUS something ("Παπαδόπουλος-Smith" -> "-Smith")
            # keeps an alnum character, so it takes the primary path
            # unchanged. Accepted: 0 of 8,494 first-author entries hit it.
            norm_surname = title_key(surname)
            if not norm_surname:
                continue
            if script_text is None:
                script_text = title_key(review_text)
            needles = {norm_surname}
            haystacks = (script_text,)
        else:
            # Symmetric transliteration matching:
            # every needle variant (the plain NFKD fold, the ae-spelling, and
            # the contracted fold) is tried against all three haystacks, so a
            # bib "Mueller" meets prose "Müller", a bib "Fränken" meets prose
            # "Fraenken", and a bib "Franken" meets prose "Fraenken" (neither
            # side diacritic'd - the contract haystack's job) alike - not
            # just the directions norm_text/translit_text alone cover.
            needles = ascii_variants(surname)
            haystacks = (norm_text, translit_text, contract_text)

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
            # The Chicago letter this entry carries, "" when it has
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

# A year carrying a Chicago letter, ANYWHERE in the prose, found
# without parsing a citation at all. Deliberately case-insensitive on the
# letter ("2010B") and free of any surname context: see _sighted_letters.
_YEAR_LETTER_RE = re.compile(
    r"(?<!\d)(?P<year>(?:1[6-9]|20)\d{2})(?P<letter>[A-Za-z])\b")

# A BARE letter continuing the token before it: "(2010a, b)", "(2010a-b)",
# "(2010a and b)" - forms where the second letter carries no year of its own,
# so _YEAR_LETTER_RE alone cannot see it. \A-anchored on the text immediately
# after the previous letter. The separator class excludes ")" and "." on
# purpose: without that, "Menary (2010a). B. Smith replies" would sight "b"
# and permanently protect the 2010b entry, silently switching the letter
# filter back off. (A multi-letter word after the citation is harmless either
# way - the trailing \b rejects it - so the initial is the case that bites.)
#
# That exclusion closes the PARENTHESISED form only, and the docstring above
# should not be read as closing the case. The unparenthesised one still
# chains: "Menary 2010a and B. Smith replies" sights "b" via the " and "
# separator. Left as is - it falls on the protecting side, like every other
# spurious sighting, and tightening it would need sentence segmentation.
_BARE_LETTER_RE = re.compile(
    r"\A[\s,;&/-]*(?:and|or)?[\s,;&/-]*(?P<letter>[A-Za-z])\b")

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
#
# The two alternatives CAPTURE the name they matched. That is not for the
# rejection decision - which is unchanged, and is still just "did this match" -
# but for _rejected_span_surnames, which walks the same pattern backwards to
# recover the author list this match landed in the middle of.
_NON_INITIAL_PRECEDING_RE = re.compile(
    r"(?:(?P<conj_name>[A-ZÀ-Þ][\w'’À-ÿ-]+),?\s+(?:and|&)\s+"
    r"|(?!(?:" + _SENTENCE_LEAD_INS + r")\b)"
    r"(?P<comma_name>[A-ZÀ-Þ][\w'’À-ÿ-]+),\s+)$"
)

# How far back _rejected_span_surnames walks. Long enough for any real author
# list, short enough that the backward scan stays bounded per match on a
# 100 KB review. A list longer than this loses its earliest names, which costs
# protection, not accuracy - the recovered names are a keep-side net.
_LIST_LOOKBACK = 200


def _strip_possessive(s: str) -> str:
    """Drop a trailing possessive marker ('s / ’s) from a captured name.

    ACCEPTED RESIDUAL: a bare-apostrophe possessive on a surname already
    ending in -s -- "Rivers' (2020)" rather than "Rivers's (2020)" -- keeps
    its trailing quote and folds to a variant that will not match the bib's
    plain "Rivers". Not fixed: the correct rule (a bare quote at a word
    boundary is possessive only for surnames already ending in -s) risks false
    positives against surnames that end in a quote orthographically, and no
    test case exists to validate either direction.

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


def _parser_verdicts(review_text: str):
    """Yield (match, rejected) for every _CITE_INSTANCE_RE match.

    One scanner, so the parser's ACCEPTED half (_citation_instances) and its
    REJECTED half (_unresolvable_mentions) cannot drift apart: a future
    rejection rule added here reaches both, and a citation can never be
    simultaneously absent from the instances and absent from the mentions.
    """
    for m in _CITE_INSTANCE_RE.finditer(review_text):
        yield m, bool(_NON_INITIAL_PRECEDING_RE.search(review_text[:m.start()]))


def _continuation_years(tail: str) -> list[tuple[str, str]]:
    """(year, suffix) for every year continuing the citation whose match ends
    where `tail` begins: "Menary (2006, 2010, 2013)", "Wiens (2015a; 2015b)".

    ONE walker, called by BOTH halves of the parser. It used to live inside
    _citation_instances' accepted branch only, below its `if rejected:
    continue`, so a REJECTED multi-year citation contributed its head year to
    the bare-mention net and silently lost every tail year. Reproduced:

        bib    menary2011a, menary2011b - same author, same year, distinct works
        prose  "Menary (2011a) argues X.
                See Clark, Menary (2010, 2011), and Sutton on this."
        kept   menary2011a only - menary2011b dropped though the prose carries
               a letterless, ambiguous 2011 mention of exactly that group

    lint_md reports nothing, because "(2010, 2011)" resolves on base year
    against the surviving "2011a." reference line. The two-year parenthesis is
    not an exotic form: 8 of 32 delivered reviews already use it in accepted
    position.
    """
    out = []
    while True:
        cont = _CONTINUATION_RE.match(tail)
        if not cont:
            break
        out.append((cont.group("year"), cont.group("suffix") or ""))
        tail = tail[cont.end():]
    return out


def _rejected_span_surnames(review_text: str, m) -> list[str]:
    """Every surname the REJECTED citation `m` names, first author first.

    A rejected match binds at a NON-INITIAL name of an author list - that is
    the whole content of the rejection - so the surname the regex captured is
    the second or third author, never the first. The collision groups it has
    to protect are keyed by FIRST-author surname, so keying the protection on
    the captured name alone points it at the wrong group and the sibling
    citation drops the cited work anyway. Reproduced:

        bib    muldoonSolo2023 (Muldoon), muldoonWu2023 (Muldoon and Wu)
        prose  "Muldoon (2023) presents the solo account.
                Muldoon & Wu (2023) present the joint account."
        kept   muldoonSolo2023 only - muldoonWu2023 dropped though cited

    The parser cannot read "Muldoon & Wu" as one list (see
    _CITE_INSTANCE_RE), so it binds at Wu, _NON_INITIAL_PRECEDING_RE rejects
    it for exactly the right reason, and the mention was filed under Wu while
    the group is Muldoon. Identical shape for "Muldoon, Wu, and Li (2023)",
    where the captured name is the middle author.

    So walk _NON_INITIAL_PRECEDING_RE backwards - the same pattern that
    rejected the match, peeled one list member at a time - and return the
    recovered leading names plus the match's own surname and its second-author
    capture. Returning the WHOLE span rather than only the recovered first
    author is deliberate: "See Clark, Menary (2010), and Sutton" is genuinely
    ambiguous between one three-author list and three separate citations, and
    under the cardinal rule an ambiguous mention protects every group it could
    name. Measured cost over the 41 delivered reviews: zero (see the report).

    Fixing the PARSER instead - teaching _CITE_INSTANCE_RE that "&" is a
    two-author "and" - was considered and DECLINED, and the reason is worth
    keeping because it will be proposed again as the minimum fix. It is
    drop-INCREASING, not protective: "Clark & Menary (2010)" would stop being
    a rejected fragment and become an accepted instance naming Clark in first
    position, which is uncorroborated second-position evidence against a
    Menary group and therefore no protection at all. That is precisely what
    the "and" spelling does today (verified: the same prose with "and" already
    drops menary2010extended where "&" keeps it), so parsing "&" would import
    the asymmetry into the safe half rather than remove it. It buys nothing on
    the defect above, which this net closes outright. The asymmetry itself -
    the collision resolver's drop never fires on an ampersand author list -
    is a separate accuracy question, on the keep side, and is routed onward
    rather than settled here.
    """
    names = []
    head = review_text[max(0, m.start() - _LIST_LOOKBACK):m.start()]
    while True:
        pm = _NON_INITIAL_PRECEDING_RE.search(head)
        if not pm:
            break
        # Possessive-stripped like every other captured name: the surname
        # character class admits apostrophes, so "Nussbaum's and Sen (2010)"
        # recovers "Nussbaum's", whose variants intersect no group.
        names.append(_strip_possessive(
            pm.group("conj_name") or pm.group("comma_name")))
        head = head[:pm.start()]
    names.reverse()
    names.append(_strip_possessive(m.group("surname")))
    if m.group("second"):
        names.append(_strip_possessive(m.group("second")))
    seen = set()
    out = []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def _unresolvable_mentions(review_text: str) -> list[dict]:
    """Citations of a surname+year that the parser saw and REJECTED, carrying
    no Chicago letter. Each: {"surname_variants", "surname", "year"}.

    This closes a residual on a real Issue B path rather than a theoretical
    one. "Menary (2010a) argues X. See Clark, Menary (2010), and
    Sutton" used to lose a work: the first cite licenses the drop, the second
    is rejected by _NON_INITIAL_PRECEDING_RE so it contributes no instance,
    and it carries no letter for _sighted_letters to see. lint_md then resolves
    the surviving "Menary (2010)" against the "2010a." reference line and exits
    0, so the reader is pointed at the wrong work with nothing reported. Same
    shape for the forms that regex rejects for the same reason, e.g.
    "Clark & Menary (2010)".

    A bare mention of THIS group's author-year is exactly what
    ambiguous-keep-all means, so it disables dropping for that group - and for
    that group only, which is what makes this affordable.

    Two scoping decisions, both load-bearing, both measured:

    - LETTERLESS ONLY. A rejected cite that DOES carry a letter
      ("See Clark, Menary (2010b), and Sutton") is already covered by
      _sighted_letters, which protects the one member the letter names instead
      of the whole group. Requiring the year to carry no letter expresses a
      `(?![0-9A-Za-z])` condition through the parser's own suffix group rather
      than a second regex. It is tested PER YEAR, not per
      citation: "Menary (2011a, 2011)" hands its head to _sighted_letters and
      its tail to this net, and a whole-citation test threw both away.
    - SCOPED BY THE REJECTED MATCH'S OWN SPAN, not by proximity. The obvious
      alternative - "a bare year anywhere within _MATCH_WINDOW of a member's
      surname" - was built and measured, and it DESTROYS collision
      resolution: an ordinary "Muldoon and Wu (2023) argue X." puts a bare
      2023 next to Muldoon, so both drop branches stop firing on their own
      canonical fixtures,
      and 15 extra references are retained across 13 of the 41 delivered
      reviews. That is the outcome _sighted_letters' docstring predicted for an
      unscoped bare-year sighting. Keying on the REJECTED match has no such
      cost: zero corpus difference, because every bare year that belongs to a
      citation the parser accepted is handled by the instance machinery as
      before.

      "Span", not "captured surname" - a correction of the first design.
      A rejected match binds at a non-initial name by definition, so the
      captured surname is never the first author the collision groups are
      keyed by. _rejected_span_surnames recovers the rest of the list; see
      there for the case that made this a Critical and for why the tempting
      parser-side fix is declined.

    Known limit, stated rather than closed: a bare mention with no citation
    shape at all ("In 2010, Menary argued that ...", "the 2010 crisis") is not
    a rejected match and is not seen here. Covering it needs the proximity rule
    measured above, which costs collision resolution.
    """
    out = []
    for m, rejected in _parser_verdicts(review_text):
        if not rejected:
            continue
        surnames = _rejected_span_surnames(review_text, m)
        years = [(m.group("year"), m.group("suffix") or "")]
        years += _continuation_years(review_text[m.end():])
        for year, suffix in years:
            # LETTERLESS ONLY, applied per year rather than per citation: in
            # "Menary (2010b, 2011)" the head is _sighted_letters' business and
            # the tail is this net's, and the old whole-citation test threw
            # both away together.
            if suffix:
                continue
            for surname in surnames:
                out.append({"surname_variants": ascii_variants(surname),
                            "surname": surname, "year": year})
    return out


def _citation_instances(review_text: str) -> list[dict]:
    """Parse author-year citation instances from the ORIGINAL text.
    Each: {"surname_variants", "form", "second_text", "first_text", "year",
    "suffix", "continuation"}.
    form: 'solo' | 'and' | 'etal'. second_text may be a multiword particled
    surname - compared whole-to-whole against candidate second-surname
    variants, never tokenized; first_text is the raw leading token ('' when
    absent) and is applied only when informative (see candidate rule).

    continuation: True for the later years of a multi-year citation
    ("Menary (2006, 2010, 2013)"), False for the head match that carried the
    surname. _resolve_collisions lets a continuation ADD support but never
    lets one license a drop - see the loop below.

    Matches whose preceding text shows they bind at a non-initial name
    (C1: _NON_INITIAL_PRECEDING_RE) are rejected outright and contribute no
    instance - see that regex's docstring for why."""
    out = []
    for m, rejected in _parser_verdicts(review_text):
        if rejected:
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
            # The Chicago letter the PROSE carries, "" when none.
            "suffix": (m.group("suffix") or ""),
            "continuation": False,
        })
        # One surname, several years: "Menary (2006, 2010, 2013)", "Wiens
        # (2015a; 2015b)" -- the shape 8 of 32 delivered reviews already use.
        # _CITE_INSTANCE_RE matches only the first year, so without this the
        # later works have no supporting instance and _resolve_collisions drops
        # them: a regression F would INTRODUCE rather than fix.
        #
        # A spurious continuation (", 1995" in "Following Smith 2020, 1995 was
        # a watershed", which is not a citation at all) must not cost a cited
        # work. Do NOT restate that as a slogan: two rounds of this branch
        # shipped the sentence "continuations can only ADD support, never
        # remove it, so a spurious one costs a kept work and never a dropped
        # one", and both times it was false - ADDING support is itself a way to
        # move a group out of keep-all and into the drop branch, which is how a
        # continuation deleted a cited work twice -- the second time measured
        # end-to-end on an UNLETTERED bib with lint exiting 0.
        #
        # What holds the property up is an enumeration a later editor can
        # re-check line by line against _resolve_collisions - one line per
        # piece of group state a continuation instance can write:
        #
        #   supported             WRITTEN - keeps a member in the drop branch
        #   first_pos_seen        WRITTEN - routes to keep-all-and-warn
        #   unmatched_letters     WRITTEN - disables the drop branch outright
        #   form_mismatch_letters WRITTEN - changes the message, never a branch
        #   first_pos_supported   NOT written - the drop license
        #   second_pos_seen       NOT written - the drop-everything license
        #
        # Every state a continuation reaches either protects a member or only
        # talks; both drop licenses are closed to it. A later edit that adds a
        # seventh piece of state must extend this list and say which column it
        # is in.
        #
        # Every other key inherited from out[-1] is invariant across a
        # continuation run - surname_variants, form, second_text and first_text
        # all belong to the single author-list this parenthesis opened with, and
        # only the year and its letter vary. There is no positional key to copy:
        # the resolver derives its own flags. A continuation OF a continuation
        # correctly inherits continuation=True.
        for c_year, c_suffix in _continuation_years(review_text[m.end():]):
            out.append({**out[-1], "year": c_year, "suffix": c_suffix,
                        "continuation": True})
    return out


def _sighted_letters(review_text: str) -> dict:
    """{year: {letter, ...}} - every Chicago letter the PROSE attaches to a
    year, found WITHOUT parsing a citation.

    This is the letters' keep-all safety net, and it is deliberately separate
    from _citation_instances. The letter filter in _resolve_collisions can
    only protect a group through an instance that parsed as a first-position
    citation intersecting the group; every other way a lettered citation can
    be written slips past it and the cited work is dropped. Measured examples,
    all of which used to lose a work: a bare-letter continuation
    ("Menary (2010a, b)", "(2010a-b)"), a separator the continuation parser
    does not take ("2010a and 2010b"), an uppercase letter (which makes the
    whole instance match fail), a citation rejected by
    _NON_INITIAL_PRECEDING_RE ("See Clark, Menary (2010b), and Sutton"), a
    second-position sighting ("Rowlands and Menary (2010b)") and a citation
    with no surname at all ("The 2010b volume collects the replies"). A scan
    over raw text sees all of them, because it needs no citation structure.

    Two properties are intentional, and both point the same way - toward
    keeping a work rather than dropping one:

    - The scan is PERMISSIVE, and the map is keyed by YEAR ALONE. A stray
      "2010b" anywhere in the document protects every 2010b entry, even when
      the mention is not a citation and even when it belongs to a different
      author. Under the cardinal rule (a path that drops a cited work is never
      acceptable) a false protection costs a possibly-uncited reference line,
      reported as "[COLLISION] kept"; a missed sighting costs a cited work.

      The rate is NOT bounded by the corpus measurement below, and must not be
      quoted as if it were. Over the delivered reviews with the real assigner's
      letters stamped (52 md/bib pairs, 152 letters) it is exactly ONE extra
      reference retained - an uncited Lawford-Smith 2012 work protected by an
      unrelated Valentini 2012b - with zero cited works lost. But that corpus
      samples the PRE-F prose distribution, where writers had no letters to
      copy. Once F ships, two lettered groups sharing a year disable each
      other's drops by construction: every lettered group contains an "a" and a
      "b", so a prose "Clark (2010a)" is protected by anyone else's "2010b".
      Expect the rate to scale with lettered groups per year, not to stay at
      one. It is still the right side of the cardinal rule - the failure is a
      retained reference, announced on stderr - and keying on (surname, year)
      is not the trade: it defeats the rows this net exists for, since
      "The 2010b volume" supplies no usable surname at all and the bare-letter
      chain has none without re-introducing the citation parsing the scan is
      deliberately independent of.
    - "the 2010s" parses as year 2010, letter "s", and the bare-letter chain
      will read the "a" of "a decade of ferment" straight after it. The "s"
      half IS harmless - a group would need 19 members before any letter "s"
      is assigned - but do NOT extend that argument to the "a", as an earlier
      version of this docstring did: "a" is the letter the FIRST member of
      every lettered group carries, so a decade token followed by "a" disables
      F's drop for that whole year. Reproduced: "Debates in the 2010s, a
      decade of ferment, matured. As Menary (2010b) argues, ..." keeps
      menary2010cognitive that "As Menary (2010b) argues" alone drops. The
      guard is only that the chain stops at "." and ")", so "The 2010s. A
      decade of ferment." does not chain.

      Measured over the 41 delivered reviews, in the design's favour but not
      as a bound: 11 decade tokens, of which 0 chain into an a-f letter, and
      of the 20 distinct (year, letter a-f) pairs sighted corpus-wide all 20
      are genuine lettered citations. The cost is real and unbounded; it is
      accepted because it falls on the protecting side.

    A citation carrying NO letter that the parser also rejects
    ("Menary (2010a) ... See Clark, Menary (2010), and Sutton") leaves nothing
    to sight, and this scan cannot see it. That residual is closed elsewhere,
    by _unresolvable_mentions, which scopes the protection by the surname the
    rejected match itself captured. It is NOT closed by treating a bare year as
    a sighting here: _collect_matches already requires the year near the
    surname, so a proximity rule protects every member always - measured, it
    disables both collision-drop branches on their own canonical fixtures.
    """
    sighted: dict = {}
    for m in _YEAR_LETTER_RE.finditer(review_text):
        letters = sighted.setdefault(m.group("year"), set())
        # Lowercased on insertion: _entry_suffix lowercases too, and a bib
        # letter is always compared against this map ("2010B" must protect
        # the entry carrying "b").
        letters.add(m.group("letter").lower())
        tail = review_text[m.end():]
        while True:
            cont = _BARE_LETTER_RE.match(tail)
            if not cont:
                break
            letters.add(cont.group("letter").lower())
            tail = tail[cont.end():]
    return sighted


# Title-only citations, which a reference list can omit: spans a reader would
# recognize as a work's name -- double-quoted (straight or curly, the forms
# the writers emit), single-curly-quoted, or *italicized* (markdown; a
# **bold** span matches between its inner asterisks, which is accepted --
# a bolded exact title still names the work). The 4..300 length bounds
# skip degenerate spans and runaway matches when a closing delimiter is
# missing. Straight single quotes are deliberately absent: apostrophes
# make them unbounded.
_TITLE_SPAN_RES = (
    re.compile(r'"([^"\n]{4,300})"'),
    re.compile(r'\u201c([^\u201d\n]{4,300})\u201d'),
    re.compile(r'\u2018([^\u2019\n]{4,300})\u2019'),
    re.compile(r'\*([^*\n]{4,300})\*'),
)

# Word-character probe for the span-context guard in _title_mentions. Used
# with re.match(s, pos) so it can test a single position without slicing.
_WORD_CH_RE = re.compile(r'\w')

# Minimum folded word count for a title to be nettable. Measured over the
# 36 delivered reviews + the production pair: at 4 words the net fires
# exactly twice, both genuine References omissions (heersmink2016internet
# in production run 42b02936; rawls1971theory in nonideal-theory-justice);
# at fewer words it manufactures phantom references from terms of art
# ('deceptive alignment' italicized as a term, scare-quoted 'data'). A
# false ADD is a phantom reference -- the class collision resolution and the
# Chicago letters police -- so precision wins over recall here; short-titled
# works remain covered by
# ordinary author-year citation, which the writer convention requires
# alongside any title mention. NOTE the corpus bound honestly: 0 false
# fires over 37 documents is a rule-of-three 95% upper bound of ~8% per
# document, which is why the surname conjunct below also gates the net.
_TITLE_MENTION_MIN_WORDS = 4


def _title_mentions(prose: str, bib_data) -> dict:
    """{citation_key: folded_title} for entries the prose cites BY TITLE:
    a quoted or italicized span whose title_key fold EQUALS the entry's
    cleaned, folded title, where the entry's first author/editor surname
    also appears in the folded prose. Span equality, not containment -- a
    title appearing as plain running text is a canonical phrase, not a
    citation (measured: containment alone fires 31 times, mostly falsely).

    The running-text safety rests on span equality PLUS two span-level
    guards, not equality alone. `"`/`*` are non-directional delimiters:
    when a short span fails the {4,300} floor (e.g. `*not*`), the regex
    engine retries the FAILED span's closing delimiter as the next match's
    opener, and can capture plain running text up to the following
    delimiter (e.g. "Rawls is *not* a theory of justice *however* in the
    strict sense." mis-captures " a theory of justice " between the two
    failed italics). Two guards narrow that class, and neither closes it
    alone:

    1. Edge whitespace. A real quoted or italicized title is never written
       with a space just inside its delimiter (CommonMark's flanking rule
       already forbids whitespace-adjacent emphasis delimiters, and no
       writer quotes " Title " with padding), so any raw capture that
       disagrees with its own `.strip()` is rejected. This costs nothing
       and needs no narrowing of {4,300} (narrowing it to {1,300} only
       closes 2 of the 4 measured mis-pairing shapes).
    2. Word-boundary context. When the failed short span abuts words on
       both sides (`*not*a theory of justice*however*`, `"AI"a theory of
       justice"fails"`) the mis-capture is whitespace-clean and passes
       guard 1 -- a confirmed phantom-ADD. A genuine title mention is
       never word-abutted on the OUTSIDE of its delimiters, so a match
       whose immediately preceding or following character is a word
       character is rejected. Bold `**Title**` still fires: the abutting
       characters are asterisks, and `("Title")` abuts parentheses.

    Honest residual, stated without hedging: this is an enumeration of
    shapes, not a closure proof, and one shape still produces a phantom
    ADD. Guard 2 tests BOTH sides, so evading it needs the mis-capture to
    be punctuation-abutted at both ends -- the failed short span must end
    in punctuation AND the text after the closer must begin with it.
    Measured: `*...*a theory of justice*however*` is CAUGHT (the closer
    abuts `h`), while

        Rawls wrote *no.*a theory of justice*(1971)* in reply.

    FIRES. The other three conjuncts do not mitigate it -- they are
    satisfied, not violated: the capture folds to EXACTLY the entry's
    4-word title, and Rawls is named in the document. An italicized
    parenthetical year right after the title text is the realistic form of
    this shape, so it is not purely hypothetical.

    It is accepted, not closed, because the required shape is narrow: a
    short span that fails the {4,300} floor AND ends in punctuation, whose
    closing delimiter is immediately followed by the title text with no
    space, followed in turn by a span that opens on punctuation. Closing it
    needs a different mechanism (a real inline-markdown parse), not another
    character-class guard.

    One accepted false rejection, in the safe direction: `\\w` counts `_`,
    so an underscore-delimited emphasis wrapper (`_*A Theory of Justice*_`)
    is read as word-abutted and dropped. It is not a form this pipeline's
    writers emit -- format_entry renders titles with quotes and asterisks,
    and the corpus mentions follow -- and narrowing the class to
    `[^\\W_]` would loosen a net guard to buy back a shape nobody writes.

    Known limits, deliberate: a prose quote of the pre-colon main title
    only ("The Extended Mind" for "The Extended Mind: ...") does not
    match; neither does a title under 4 folded words, nor a title
    mention whose author is named nowhere in the document. Guard 2 adds
    two more, both measured with a shape probe rather than assumed:

      - a footnote marker abutting the closer, `"A Theory of Justice"¹`
        -- Unicode superscripts/subscripts are N-category codepoints and
        `\\w` matches them, so the span is read as word-abutted; and
      - a missing-space typo before the opener, `wrote"A Theory of
        Justice"`, which is genuinely indistinguishable from the
        intraword mis-pairing guard 2 exists to reject.

    All of these are recall losses in the SAFE direction (a missed keep,
    never a phantom add) and stay covered by ordinary author-year
    citation, which the writer convention requires alongside any title
    mention.

    On the evidence for that: the corpus re-run over the delivered reviews
    showing no change is a PRECISION result -- it proves the guard costs
    nothing on the shapes those documents happen to contain. It is not
    general recall safety, because it cannot speak to shapes the corpus
    lacks. The recall evidence is the shape probe, and the probe's gaps are
    exactly the two bullets above.

    Two further scoping notes, both deliberate. The surname conjunct is a
    DOCUMENT-GLOBAL token check, not a proximity-bounded one: the surname
    may appear anywhere in the prose, sections away from the title span.
    It is precision insurance against term-of-art collisions, not a
    locality claim, and bounding it would lose the ordinary case where a
    section names the author once and quotes the title later. And the span
    regexes exclude `\\n`, so a title mention hard-wrapped across two lines
    is invisible to the net -- a recall gap, accepted for the same reason
    as the limits above: the writer convention requires an author-year
    citation alongside any title mention.
    """
    folded_spans = set()
    for rx in _TITLE_SPAN_RES:
        for m in rx.finditer(prose):
            g = m.group(1)
            if g != g.strip():
                continue  # non-directional-delimiter mis-pairing guard
            # Word-boundary context guard: see docstring guard 2.
            if m.start() and _WORD_CH_RE.match(prose, m.start() - 1):
                continue
            if _WORD_CH_RE.match(prose, m.end()):
                continue
            fs = title_key(g)
            if fs:
                folded_spans.add(fs)
    if not folded_spans:
        return {}
    folded_prose = " " + title_key(prose) + " "
    out = {}
    for key, entry in bib_data.entries.items():
        tk = title_key(clean_bibtex_str(entry.fields.get("title", "") or ""))
        if len(tk.split()) < _TITLE_MENTION_MIN_WORDS:
            continue
        if tk not in folded_spans:
            continue
        persons = entry.persons.get("author", []) or entry.persons.get("editor", [])
        if not persons:
            continue  # cannot corroborate authorship -- precision side
        sk = title_key(_get_full_surname(persons[0]))
        if sk and (" " + sk + " ") in folded_prose:
            out[key] = tk
    return out


def _letter_is_sighted(rec: dict, sighted: dict) -> bool:
    """Does the prose mention this entry's rendered label ("2010b")?

    An entry with no letter can never be protected this way, so THIS net is
    inert on an unlettered bib.

    That is not the same claim as "the Chicago letters leave surname-collision
    resolution untouched", and the two were conflated here once. The letter
    work also parses multi-year continuations, which is a second mechanism and
    one that fires on unlettered bibs: what keeps collision resolution intact
    there is the `not inst["continuation"]` guard on second_pos_seen in
    _resolve_collisions, not this letter gate. Checked against the pre-letter
    commit (13860fb) rather than an intermediate one: "Bloggs and Muldoon
    (2019, 2023) argue" against an unlettered Muldoon-first-author pair is
    keep-all before the letters and keep-all after, and it is the continuation
    guard that makes that true.
    """
    letter = rec.get("suffix") or ""
    return bool(letter) and letter in sighted.get(rec["year"], ())


def _ascii(s: str) -> str:
    return s.encode("ascii", "backslashreplace").decode("ascii")


def _print_letter_rescue(rec: dict) -> None:
    """Report a member kept only because the prose sights its letter."""
    print("  [COLLISION] kept " + _ascii(rec["key"])
          + ": no citation instance supports it, but the prose mentions "
          + _ascii(rec["year"] + (rec.get("suffix") or ""))
          + " - keeping it rather than dropping a cited work",
          file=sys.stderr)


def _print_title_rescue(rec: dict) -> None:
    """Report a member kept only because the prose mentions its title."""
    print("  [TITLE] kept " + _ascii(rec["key"])
          + ": no citation instance supports it, but the prose mentions "
          "its title - keeping it rather than dropping a cited work",
          file=sys.stderr)


def _cited_letters_phrase(year: str, letters) -> str:
    """"the cited letter 2010c matches" / "the cited letters 2010c, 2010d
    match" - the singular/plural halves of the unmatched-letter warning."""
    tokens = ", ".join(_ascii(year + s) for s in sorted(letters))
    if len(letters) == 1:
        return "the cited letter " + tokens + " matches"
    return "the cited letters " + tokens + " match"


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
    hold two COPIES of one work - which the suffix filter must not read
    as two lettered works. Duplication is tested on the same two axes dedup
    itself uses: a shared non-empty normalized DOI, or a shared fallback key.
    Either one alone is enough, so this is a pairwise scan rather than a single
    tuple identity (groups are tiny). The DOI-set refusal is deliberately
    NOT replicated: here the permissive direction is the safe one, because any
    hint of duplication disables the filter and falls through to keep-all.

    KNOWN LIMIT, recorded rather than closed. These are
    the same two axes the barrier's assigner uses for work identity, so a
    duplicate pair that evades BOTH - titles that diverge far enough for
    title_key to differ, with a DOI on only one copy - also gets distinct
    letters from the assigner and sails through this predicate. Measured: three
    copies lettered a/b/c, prose "Menary (2010b)", the richer copy dropped
    pre-dedup with no [SUFFIX] and no [DEDUP] line. Widening the predicate is
    not the fix: the containment is that dedupe_bib.py runs BEFORE this script
    in Phase 6, and any pair the assigner does link carries one letter and is
    caught by the distinct-letters conjunct instead. No CITED work is lost in
    the measured case (the copies are one work), which is why this is a
    documented limit and not a keep-all rule.
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


def _resolve_collisions(records: list[dict], review_text: str,
                        title_mentioned: frozenset = frozenset()) -> list[dict]:
    """Group colliding records by
    variant-intersection connected components per year; resolve each group
    by per-citation-instance candidate sets parsed from the ORIGINAL text;
    keep the union of supported members; drop only what no instance
    supports - and only when the group parsed at least one instance.

    ACCEPTED RESIDUAL (narrow): when a bib still holds an unmerged duplicate
    pair, a drop here removes the richer member before dedup could union its
    journal/volume/pages/doi into the survivor, so the survivor keeps only its
    own scant fields. Protected on the real pipeline -- SKILL.md Phase 6 runs
    dedupe_bib.py BEFORE this script, so the pair is already one entry with
    fields unioned. Reachable only on a standalone or manual invocation.

    ACCEPTED RESIDUAL (keep-all resurrection): the protective keep-all branch
    carries a suffix group's UNCITED sibling through even when the synthesis
    outline excluded it as EVIDENCE-NONE, so an evidence-excluded entry can
    reach delivered References. Observed once on a live run, whose orchestrator
    removed the entry by hand. Recorded, not queued. If it recurs, the two
    directions worth evaluating are assembly-time letter re-derivation over the
    delivered set (assembly can renumber prose and References together, which
    render-time suppression cannot) and a report bucket naming every keep-all
    resurrection, so nobody has to find one by hand.

    First-position evidence is tracked as TWO flags with opposite roles -
    first_pos_seen (protective, set by any naming instance) and
    first_pos_supported (licensing, set only by a non-continuation instance
    that discriminated a member). Collapsing them into one variable is what
    let a multi-year citation's tail delete a cited work; see their
    declaration below for the full account.

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
    first-position form.

    The Chicago letter adds a FOURTH discriminator, and TWO safety
    nets that outrank all of them. No member is ever dropped while the prose
    mentions its rendered label ("2010b"), whether or not that mention parsed
    as a citation (_sighted_letters). And no member of a group is dropped while
    the prose carries a LETTERLESS citation of that group's author-year which
    the parser rejected (_unresolvable_mentions) - such a mention names the
    group without saying which member, which is what ambiguous-keep-all is
    for.

    The title net adds a discriminator-independent rule: no member is dropped
    while the prose mentions its TITLE in quoted/italicized form
    (_title_mentions) -
    a title names exactly one work, so it outranks every author-year
    ambiguity. The function has exactly two drop sites (the
    first_pos_supported branch and the second_pos_seen branch); both carry the
    rescue, and a future third drop site must too."""
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
    sighted: dict = {}  # {year: {letter}} - parsed with instances, see below
    unresolvable: list = []  # letterless cites the parser rejected, ditto
    keep = []
    for members in groups:
        if len(members) == 1:
            keep.append(members[0])
            continue
        if instances is None:
            instances = _citation_instances(review_text)
            sighted = _sighted_letters(review_text)
            unresolvable = _unresolvable_mentions(review_text)
        member_variants = frozenset().union(*(r["_variants"] for r in members))
        # A letterless citation of THIS group's author-year that the parser
        # rejected. It names the group without saying which member, so it is
        # an ambiguous mention and must disable dropping for this group - the
        # residual named in _unresolvable_mentions. Held as the surname text,
        # not a flag, so
        # the warning can name what an operator has to go and look at.
        bare_mentions = {mm["surname"] for mm in unresolvable
                         if mm["year"] == members[0]["year"]
                         and (mm["surname_variants"] & member_variants)}
        # Is this group STRUCTURALLY COMPLETE - every member
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
        #
        # A FOURTH conjunct - "every member came from the same suffix-assignment
        # namespace" - has been proposed twice and is DECLINED, with the
        # reason recorded because it will be proposed again. On assigner output it is unreachable: every
        # signature group letters from "a" (LETTERS[index], index from 0), so two
        # lettered signature groups landing in one collision group both carry an
        # "a" and conjunct 2 already fails. It would bite only on stale or
        # hand-edited letters. Against that: year_suffix.author_signature takes
        # RAW BibTeX author strings while this function holds pybtex Person
        # objects, whose raw field is lossy to reconstruct, so the conjunct means
        # a parallel signature implementation, declined once already for the
        # same reason.
        letters = [r.get("suffix") or "" for r in members]
        group_letters = {ltr for ltr in letters if ltr}
        fully_lettered = (all(letters) and len(set(letters)) == len(letters)
                          and _members_are_distinct_works(members))
        year = members[0]["year"]
        supported = set()
        # TWO first-position flags, because they play OPPOSITE roles and one
        # variable cannot carry both. Collapsing them is a real defect, and
        # one a first fix half-closed by tightening the single flag for one
        # role while silently weakening the other:
        #
        #   first_pos_seen -- PROTECTIVE. "Some citation named this group in
        #     first position." It routes the group into the keep-all-and-warn
        #     branch, which is what keeps it OUT of the second-position
        #     drop-everything branch. Set by ANY intersecting instance,
        #     continuation included: a continuation is still the prose naming
        #     this group, and withholding the flag pushed "Muldoon (2019, 2023)
        #     argues" - an explicit citation, whose support this very function
        #     had already printed - into the drop branch and deleted BOTH
        #     candidate works.
        #   first_pos_supported -- LICENSING. "A NON-continuation first-position
        #     instance actually discriminated some member." Only this opens the
        #     drop branch. A continuation is the tail of a citation whose only
        #     certain content is the head year, so it must never move a group
        #     out of keep-all on its own - it did, twice, through `supported`
        #     ("Following Smith 2020, 1995 was a watershed"; and three ordinary
        #     forms combined on an unlettered bib, silent through lint).
        #
        # first_pos_supported implies first_pos_seen (it is set inside the same
        # block, which sets first_pos_seen unconditionally first), so the drop
        # gate below names only the licensing flag.
        first_pos_seen = False
        first_pos_supported = False
        second_pos_seen = False
        # Letters the prose used that this group could not resolve. Per-group
        # (not function-scope): at function scope one group's typo would leak
        # into every later group. Holds the letters, not just a flag, so the
        # warning can name the citation the operator has to go and fix; its
        # truthiness is what the branch conditions below read.
        unmatched_letters = set()
        # The subset of those whose letter DOES name a member, where the
        # citation's author form is what excluded it. Message-only: it changes
        # the diagnostic, never the branch, because the conservative keep-all
        # is right in both cases.
        form_mismatch_letters = set()
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
                if (not inst["continuation"]) and inst["form"] == "and" and (
                        ascii_variants(inst["second_text"]) & member_variants) and (
                        _second_position_corroborated(inst, member_variants, records)):
                    second_pos_seen = True
                continue
            # Unconditional, continuations included: this flag is protective
            # (see its declaration above), so a continuation year
            # ("Menary (2006, 2010)") must set it. The drop license is
            # first_pos_supported, which a continuation cannot set.
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
            # A Chicago letter is the only token that can separate
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
            # means the letters did not come from one clean assignment run.
            # Four causes, of which only the last has actually been observed:
            #
            #   - a legacy or hand-edited bib;
            #   - a bib assembled from two runs;
            #   - a DIFFERENT author sharing this surname and year, who was
            #     never in the lettered group at all;
            #   - STRUCTURAL, and the one measured: the assigner groups on the
            #     FULL AUTHOR-LIST signature while this function groups on
            #     FIRST-AUTHOR SURNAME variants. A same-author CO-AUTHORED
            #     sibling in the same year is therefore its own one-work
            #     signature group, gets no letter (groups of one are never
            #     lettered), and lands in the same collision group as its
            #     lettered solo siblings. It follows directly from the two
            #     grouping keys, so it recurs whenever an author has both solo
            #     and co-authored work in one year.
            #
            # Measured over the 41 delivered reviews with the real assigner's
            # letters stamped: 124 collision groups of >=2 members - 51 (41%)
            # fully lettered, 68 with NO member lettered (ordinary surname
            # collisions, which the letters have nothing to say about), 4 all
            # lettered but failing conjunct 2 or 3, and exactly ONE genuinely
            # mixed. That one is the co-author case (political-polarization:
            # mason2018uncivil "b" and mason2018ideologues "a", plus an
            # unlettered Mason-and-Wronski 2018). The first three causes are
            # hypotheses; do not restate them as frequencies. Note the 41% is a
            # CEILING on the live-run firing rate: it assigns over the merged
            # bib, while the pipeline assigns over the domain bibs, where more
            # groups are suppressed.
            #
            # In any of those a suffixed instance would otherwise select the
            # lettered member and drop every unlettered one. Incomplete groups
            # fall through to the surname-collision behaviour unchanged.
            #
            # The flag also fires when the group's FORM matched no member, so
            # cands was already empty before the filter ran. Gating on `cands`
            # would restore the collision drop there, but on a citation whose
            # author list matches no record - strictly less safe, and against
            # the rule "partial ambiguity never drops a cited work". Only the
            # diagnostic distinguishes the two cases.
            if fully_lettered and inst["suffix"]:
                matched = [r for r in cands if r.get("suffix") == inst["suffix"]]
                if matched:
                    cands = matched
                else:
                    unmatched_letters.add(inst["suffix"])
                    if inst["suffix"] in group_letters:
                        form_mismatch_letters.add(inst["suffix"])
                    cands = []
            if cands:
                supported.update(r["key"] for r in cands)
                # The drop license, and the only line that grants it. Writing
                # `supported` is NOT enough: flipping it from empty to
                # non-empty used to reach the drop branch just as surely as
                # first_pos_seen did, which is how a continuation kept costing
                # cited works after the flag guard was added.
                if not inst["continuation"]:
                    first_pos_supported = True
                if len(cands) > 1:
                    print("  [COLLISION] ambiguous: instance '"
                          + _ascii(min(inst["surname_variants"]))
                          + " " + year + "' (" + inst["form"] + ") matches "
                          + ", ".join(sorted(_ascii(r["key"]) for r in cands)),
                          file=sys.stderr)
        if first_pos_supported and not unmatched_letters and not bare_mentions:
            # At least one NON-CONTINUATION first-position instance
            # discriminated some members - keep those, drop the rest.
            #
            # `supported` still decides WHO is kept, and a continuation may
            # have put a member there; what a continuation may not do is decide
            # THAT anyone is dropped. Gating on `supported` alone did exactly
            # that, and that was the whole of the defect a review found here.
            #
            # An unmatched letter anywhere in the group disables
            # dropping for the WHOLE group, even when other instances did
            # discriminate ("Menary (2010a) ...; Menary (2010c) ..."). That is
            # deliberate, not an oversight: the letter that matched nothing
            # names a work we cannot identify, so we do not know which member
            # -- if any -- it was meant to support, and dropping on the
            # remaining evidence could delete exactly that work.
            for rec in members:
                if rec["key"] in supported:
                    keep.append(rec)
                elif _letter_is_sighted(rec, sighted):
                    _print_letter_rescue(rec)
                    keep.append(rec)
                elif rec["key"] in title_mentioned:
                    _print_title_rescue(rec)
                    keep.append(rec)
                else:
                    print("  [COLLISION] dropped " + _ascii(rec["key"])
                          + ": shares surname/year with "
                          + ", ".join(sorted(_ascii(r["key"]) for r in members
                                             if r is not rec))
                          + " and no citation instance supports it",
                          file=sys.stderr)
        elif first_pos_seen or unmatched_letters or bare_mentions:
            # A first-position form was parsed for this group but matched
            # no candidate (e.g. "Muldoon and Gordon" against a and-Wu/
            # and-Qi pair) - genuinely ambiguous, not evidence against
            # anyone. A second-position sighting elsewhere in the text
            # must NOT override this into a drop.
            #
            # The `or unmatched_letters` disjunct is redundant TODAY, for a
            # structural reason a later editor can re-check rather than take on
            # trust: every unmatched_letters.add() sits inside the same
            # per-instance block as the UNCONDITIONAL `first_pos_seen = True`
            # that precedes it, so no letter can go unmatched with the flag
            # unset. It is kept as a guard against an edit that breaks that
            # ordering - and it has been load-bearing once already, in the round
            # when first_pos_seen was conditional on `not continuation`: a
            # continuation carrying an unmatched letter reached here with the
            # flag unset, and deleting the disjunct then dropped two works with
            # the whole test file still green.
            keep.extend(members)
            # Name the actual cause. The generic message ("no parseable
            # citation form discriminates") is FALSE for every case below: the
            # form parsed fine and something else went unresolved, and that
            # message lands on the stderr channel a live-run operator reads.
            # Each cause gets its own clause and they can co-occur.
            clauses = []
            missing = unmatched_letters - form_mismatch_letters
            if missing:
                clauses.append(_cited_letters_phrase(year, missing)
                               + " no entry")
            if form_mismatch_letters:
                # On live runs this is the common one, and the undistinguished
                # message claimed a letter matched no entry when it matched one
                # exactly.
                clauses.append(
                    _cited_letters_phrase(year, form_mismatch_letters)
                    + " an entry, but no entry matches the citation's"
                    " author form")
            if bare_mentions:
                clauses.append(
                    "the prose also cites "
                    + ", ".join(sorted(_ascii(s) + " " + year
                                       for s in bare_mentions))
                    + " with no letter, in a form the citation parser cannot"
                    " resolve")
            if not clauses:
                # A form DID name this group (that is what put us in this
                # branch) - it just did not separate the members. Distinct from
                # the final else, where nothing named them at all; both used to
                # print the same sentence.
                clauses.append("the citation forms naming them do not"
                               " discriminate between them")
            print("  [COLLISION] ambiguous: "
                  + ", ".join(sorted(_ascii(r["key"]) for r in members))
                  + " share surname/year and " + "; ".join(clauses)
                  + " - all kept, possible phantom references",
                  file=sys.stderr)
        elif second_pos_seen:
            # No first-position instance names this group at all - the
            # only parsed explanation for the loose surname/year matches
            # is a co-author position, so nothing here is actually cited.
            # Same letter-sighting rescue as the branch above: this path drops
            # EVERY member, so an entry whose rendered label the prose shows
            # would vanish from References while the prose still names it.
            for rec in members:
                if _letter_is_sighted(rec, sighted):
                    _print_letter_rescue(rec)
                    keep.append(rec)
                    continue
                if rec["key"] in title_mentioned:
                    _print_title_rescue(rec)
                    keep.append(rec)
                    continue
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


def _strip_references_section(review_text: str) -> str:
    """Everything before a `## References` heading, or the whole text.

    That section is this script's OWN previous output, not prose, and matching
    over it made the letter drop ONE-SHOT. Every kept entry renders as
    "Menary, Richard. 2010b. ..." - a year carrying a letter with a "." after
    it, which _sighted_letters reads as a genuine mention. So on a second run
    the reference list sights every letter it printed, no member of any group
    can be dropped again, and a phantom reference becomes a self-perpetuating
    fixed point. SKILL.md Phase 6 step 5 tells the operator to re-run step 4
    after a lint failure, so this fired in normal operation: measured over a
    three-run cycle, the pre-F resolver converged at run 2 and F never
    converged at all.

    It also stops _collect_matches counting reference lines as surname/year
    windows, which is the same error one stage earlier - an entry mentioned
    ONLY in the stale reference list used to re-match itself on every run.
    That is the intended direction: a work no longer named in the prose is a
    phantom, and dropping it is what this script is for.

    `apply_references` owns the same boundary for the write side; both call
    lint_md.find_refs_heading, so the two sides and the linter cannot drift
    apart. That scanner is fence-aware and LAST-heading-wins; both properties
    fall on the keep side here, since each makes this function strip LESS
    prose than the fence-blind first-match regex it replaced.
    """
    span = find_refs_heading(review_text)
    return review_text[:span[0]] if span else review_text


def find_cited_entries(review_text: str, bib_data) -> list[tuple[str, object]]:
    """Find BibTeX entries cited in the review text.

    Matching runs in three stages before this function's own dedup.
    _collect_matches finds every candidate whose surname+year proximity
    pattern appears in the prose (dual-haystack: plain NFKD and
    transliterated, tried symmetrically). _resolve_collisions
    then groups candidates sharing (first-author surname, year) and resolves
    each group against citation instances parsed from the prose: a
    discriminating instance (second-author surname, et al., a solo author's
    first initial, or the Chicago letter, the only token that
    separates two works by the SAME author in the same year) drops the members
    it does not support; an ambiguous or unparseable group is kept whole with a
    stderr warning - partial ambiguity never silently drops a cited work. A
    member whose rendered label ("2010b") appears anywhere in the prose is
    never dropped, however the citation carrying it was written
    (_sighted_letters); nor is any member of a group the prose cites
    letterlessly in a form the parser rejects (_unresolvable_mentions).
    Third, the title net (_title_mentions): an entry whose title the
    prose quotes or italicizes is never dropped by the resolver, and is
    appended here if no author-year instance matched it at all.

    Returns list of (key, entry) tuples for cited entries, deduplicated by DOI
    and, as a fallback, by (normalized title, year, first-author surname).
    Winner of a duplicate pair is the entry with more populated substantive
    fields (tie-break: lexicographically-first citation key); the survivor
    additionally UNIONs in any substantive field only the loser had.
    DOI identity is tracked per dedup GROUP: a fallback-key merge is refused when
    the two groups' non-empty DOI sets differ.

    A `## References` section already in the file is NOT prose and is stripped
    before any matching (_strip_references_section) - see that function for the
    convergence failure it fixes.
    """
    prose = _strip_references_section(review_text)
    title_mentioned = _title_mentions(prose, bib_data)
    records = _resolve_collisions(
        _collect_matches(prose, bib_data), prose, frozenset(title_mentioned))

    # Entries the prose cites by TITLE alone (or whose author-year
    # never matched -- e.g. the year pushed outside _MATCH_WINDOW by the
    # quoted title itself) never enter _collect_matches at all. Append them
    # here so they reach References; they flow through the same dedup loop
    # as every other record (verified: that loop and everything after it
    # read only record["key"] and record["entry"], so the minimal record
    # shape is safe), so a title-mentioned duplicate still merges
    # (and two same-title copies with DIFFERENT DOIs both survive, per the
    # dedup layer's DOI-set refusal -- pinned by test). kept_keys is
    # computed AFTER _resolve_collisions so rescued members are never
    # double-added.
    kept_keys = {r["key"] for r in records}
    for key, entry in bib_data.entries.items():
        if key in title_mentioned and key not in kept_keys:
            print("  [TITLE] added " + _ascii(key)
                  + ": the prose cites its title", file=sys.stderr)
            records.append({"key": key, "entry": entry})

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
        # grounds must not steal the first group's title pointer.
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
    """Replace or append ## References section in the review text.

    Shares the read side's boundary (lint_md.find_refs_heading) - a heading
    inside a fenced example is not a boundary, so a review that quotes one
    keeps its prose instead of being truncated at the quote.
    """
    span = find_refs_heading(review_text)

    if span:
        # Replace from ## References to EOF
        return review_text[:span[0]].rstrip("\n") + "\n\n" + references_section + "\n"
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
