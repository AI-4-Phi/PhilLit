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

# Import LATEX_ESCAPES from bib_validator (single source of truth)
_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_validator import LATEX_ESCAPES  # noqa: E402

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
    """NFKD-normalize and strip combining marks for diacritical-tolerant matching."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _get_field(entry, name: str) -> str:
    """Get a cleaned field value, or empty string if missing."""
    raw = entry.fields.get(name, "")
    return clean_bibtex_str(raw).strip() if raw else ""


def _quoted_title(title: str) -> str:
    """Wrap title in quotes with proper terminal punctuation per Chicago style.

    If title already ends with ? or !, the period is absorbed.
    """
    if title.endswith(("?", "!", ".")):
        return f'"{title}"'
    return f'"{title}."'


def _format_doi(doi: str) -> str:
    """Format DOI as a full URL."""
    doi = doi.strip()
    if doi.startswith("http"):
        return doi
    return f"https://doi.org/{doi}"


def _normalize_doi(doi: str) -> str:
    """Normalize DOI for deduplication: lowercase, strip URL prefix."""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "https://dx.doi.org/"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi


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
    year = _get_field(entry, "year")
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
    year = _get_field(entry, "year")
    return (surname, year)


# Substantive fields that count toward the dedup "richer entry wins" policy and
# that a survivor UNIONs in from a loser (spec v2.1). Markers/keywords/notes are
# excluded so METADATA_CLEANED noise cannot win a duplicate contest.
_SUBSTANTIVE_FIELDS = (
    "journal", "booktitle", "volume", "number", "pages",
    "publisher", "doi", "url", "abstract",
)


def _normalize_title_for_key(title: str) -> str:
    """Fold to ascii, lowercase, collapse non-alphanumerics to single spaces."""
    t = _normalize_for_matching(title).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _fallback_key(entry) -> tuple[str, str, str] | None:
    """Title-axis dedup key: (normalized_title, year, first-author surname).

    Returns None if any component is empty (an entry with no fallback key is
    never title-deduped — GPT S4).
    """
    title = _normalize_title_for_key(_get_field(entry, "title"))
    year = _get_field(entry, "year").strip()
    persons = entry.persons.get("author", []) or entry.persons.get("editor", [])
    surname = ""
    if persons:
        surname = _normalize_title_for_key(_get_full_surname(persons[0]))
    if not title or not year or not surname:
        return None
    return (title, year, surname)


def _substantive_field_count(entry) -> int:
    """Count populated substantive fields (dedup winner metric)."""
    return sum(1 for f in _SUBSTANTIVE_FIELDS if _get_field(entry, f))


def _union_substantive_fields(winner, loser) -> None:
    """Union the loser's substantive fields into the winner (spec v2.1 / ADV-A0).

    Copies every field in _SUBSTANTIVE_FIELDS that the loser has and the winner
    lacks (or has empty). Operates on raw field values so the merged entry
    re-serializes cleanly.
    """
    for f in _SUBSTANTIVE_FIELDS:
        if not _get_field(winner, f) and _get_field(loser, f):
            winner.fields[f] = loser.fields[f]


def _remap_index(mapping: dict, old_key: str, new_key: str) -> None:
    """Repoint any dedup-index entries from old_key to new_key (winner swap)."""
    for k, v in list(mapping.items()):
        if v == old_key:
            mapping[k] = new_key


def find_cited_entries(review_text: str, bib_data) -> list[tuple[str, object]]:
    """Find BibTeX entries cited in the review text.

    Returns list of (key, entry) tuples for cited entries, deduplicated by DOI
    and, as a fallback, by (normalized title, year, first-author surname).
    Winner of a duplicate pair is the entry with more populated substantive
    fields (tie-break: lexicographically-first citation key); the survivor
    additionally UNIONs in any substantive field only the loser had (spec v2.1).
    DOI identity is tracked per dedup GROUP: a fallback-key merge is refused when
    the two groups' non-empty DOI sets differ (GPT-B4).
    """
    norm_text = _normalize_for_matching(review_text)
    cited = {}  # key -> entry
    seen_dois = {}  # normalized_doi -> citation_key
    seen_titles = {}  # (title, year, surname) -> citation_key
    group_dois = {}  # citation_key -> set of normalized DOIs across the group

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
        if not norm_surname:
            continue

        # Word-boundary, case-insensitive surname match
        try:
            pattern = re.compile(r"\b" + re.escape(norm_surname) + r"\b", re.IGNORECASE)
        except re.error:
            continue

        matched = False
        for m in pattern.finditer(norm_text):
            start = max(0, m.start() - _MATCH_WINDOW)
            end = min(len(norm_text), m.end() + _MATCH_WINDOW)
            window = norm_text[start:end]
            if year in window:
                matched = True
                break

        if not matched:
            continue

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
                _union_substantive_fields(entry, existing_entry)
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
                _union_substantive_fields(existing_entry, entry)
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
