#!/usr/bin/env python3
"""Metadata provenance cleaner for SubagentStop hook.

Removes BibTeX bibliographic metadata that cannot be verified against API output,
preventing hallucinated data from persisting in the bibliography.

This is the "fix" counterpart to metadata_validator.py - instead of blocking,
it automatically removes unverifiable fields while preserving verified data.

Features:
1. Removes unverifiable fields (journal, booktitle, volume, number, pages, publisher, doi)
2. Corrects year from API data via DOI lookup when mismatched
3. Downgrades entry types to @misc when required fields are removed
4. Tags cleaned entries with METADATA_CLEANED in keywords field

Preserved fields (never removed):
- author, title (identity fields - entry is meaningless without them)
- year (corrected rather than removed, via DOI lookup)
- note, keywords, abstract_source, howpublished, url, abstract (LLM-generated)

Usage: python metadata_cleaner.py <bib_file> <json_dir> [<json_dir> ...]
Output: JSON to stdout with cleaning summary
Exit codes: 0 = success, 2 = file not found/read error
"""

import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pybtex.database import parse_file, BibliographyData
from pybtex.database.output.bibtex import Writer
from pybtex.scanner import PybtexSyntaxError

from bib_validator import LATEX_ESCAPES


# Fields that should be cleaned if not verifiable
CLEANABLE_FIELDS = {
    'journal', 'booktitle', 'volume', 'number', 'pages', 'publisher', 'doi'
}

# Circuit breaker (item-13 A4.3): if a .bib would lose fields from more than
# BREAKER_FRACTION of its entries AND from at least BREAKER_MIN_ENTRIES, the
# cleaner writes nothing (a systemic index failure must not mass-strip verified
# data). Constants, not config - thresholds are a safety floor, not a knob.
BREAKER_MIN_ENTRIES = 5
BREAKER_FRACTION = 0.30

# A6: strip any existing METADATA_CLEANED marker before writing a fresh one.
# pybtex round-trips the underscore as \_ (and \\_ on a second pass), so match
# METADATA + any run of backslashes + _CLEANED. All markers are appended at the
# keywords tail, so removing from the first marker to end drops them all.
_MARKER_RE = re.compile(r",?\s*METADATA\\*_CLEANED:.*$", re.DOTALL)

# Fields exempt from cleaning (LLM-generated content is OK)
EXEMPT_FIELDS = {
    'note', 'keywords', 'abstract_source', 'howpublished', 'url', 'abstract'
}

# Identity fields - never remove these (entry is meaningless without them)
IDENTITY_FIELDS = {'author', 'title'}

# Correctable fields - can be updated from API data rather than removed
CORRECTABLE_FIELDS = {'year'}

# Required fields by entry type - if missing after cleaning, downgrade to @misc
REQUIRED_FIELDS = {
    'article': {'journal'},
    'incollection': {'booktitle', 'publisher'},
    'inproceedings': {'booktitle'},
    'book': {'publisher'},
    'inbook': {'publisher'},
    'phdthesis': {'school'},
    'mastersthesis': {'school'},
    'techreport': {'institution'},
}


@dataclass
class MetadataIndex:
    """Index of all metadata values from JSON files."""
    journals: dict = field(default_factory=dict)
    volumes: dict = field(default_factory=dict)
    issues: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    publishers: dict = field(default_factory=dict)
    years: dict = field(default_factory=dict)
    dois: dict = field(default_factory=dict)
    entries: list = field(default_factory=list)
    skipped_files: list = field(default_factory=list)   # unparseable after salvage
    salvaged_files: list = field(default_factory=list)  # recovered from log pollution


def normalize_pages(pages: str) -> str:
    """Normalize page ranges for comparison."""
    if not pages:
        return ""
    normalized = re.sub(r'\s*[-–—]+\s*', '-', str(pages))
    return normalized.strip()


# \^{u} -> \^u so the no-brace LATEX_ESCAPES keys (and the accent safety net
# below) can match the braced accent form real bibs actually use (No\^{u}s).
_INNER_BRACE_ACCENT = re.compile(r'(\\["\'`^~])\{([A-Za-z])\}')


def normalize_journal(name: str) -> str:
    """Normalize journal name for comparison. Decodes HTML entities and LaTeX
    escapes so LaTeX-encoded bib values (e.g. 'Philosophy \\& Technology',
    'No\\^{u}s') compare equal to CrossRef's precomposed/entity forms
    ('Philosophy &amp; Technology', 'Noûs')."""
    if not name:
        return ""
    s = html.unescape(name)                       # &amp;->&, &#251;->û
    s = _INNER_BRACE_ACCENT.sub(r'\1\2', s)        # \^{u} -> \^u so dict keys match
    for latex, uni in LATEX_ESCAPES.items():       # \^u -> û, \c{c} -> ç, {\ss} -> ß
        s = s.replace(latex, uni)
    s = re.sub(r'\\["\'`^~=.]\{?([A-Za-z])\}?', r'\1', s)  # safety net: unknown accent -> base letter
    s = re.sub(r'\\+&', '&', s)                    # \& and \\& -> &
    s = s.replace('{', '').replace('}', '')        # residual braces
    # NFKD-fold so decoded-Unicode and CrossRef-precomposed reduce to base letters
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    normalized = s.lower().strip()
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return " ".join(normalized.split())


def normalize_doi(doi: str) -> str:
    """Normalize DOI for comparison."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    prefixes = ["https://doi.org/", "http://doi.org/", "doi:", "doi.org/"]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def _salvage_json(text: str) -> Optional[dict]:
    """Recover a JSON result object from log-polluted text.

    Researchers redirected `verify_paper.py ... > f.json 2>&1`, prepending
    `[verify_paper.py] ...` stderr lines to a well-formed JSON object. Iterate
    over EVERY '{' offset attempting json.JSONDecoder().raw_decode; accept the
    first decoded value that is a dict containing a "results" key (the shape
    every producer script emits). Trailing content after the object is ignored
    (stderr can interleave after as well as before). Returns None when no such
    object exists (truncated file, or only look-alike fragments without
    "results") - the file is then skipped, never guessed at.
    """
    decoder = json.JSONDecoder()
    idx = text.find('{')
    while idx != -1:
        try:
            obj, _end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            idx = text.find('{', idx + 1)
            continue
        if isinstance(obj, dict) and 'results' in obj:
            return obj
        idx = text.find('{', idx + 1)
    return None


def find_api_entry_by_doi(doi: str, index: 'MetadataIndex') -> Optional[dict]:
    """Find the API entry that matches the given DOI.

    Entry-scoped verification records (verify_*.json - a direct CrossRef
    lookup on this exact DOI) outrank broad search-result dumps, which can
    carry another API's bad metadata for the same DOI (year-corruption fix).
    Among records of equal rank, pool order (filename sort) still decides."""
    if not doi:
        return None
    norm_doi = normalize_doi(doi)
    fallback = None
    for api_entry in index.entries:
        api_doi = api_entry.get("doi")
        if api_doi and normalize_doi(api_doi) == norm_doi:
            if api_entry.get("entry_scoped"):
                return api_entry
            if fallback is None:
                fallback = api_entry
    return fallback


def parse_s2_result(data: dict, source_file: str) -> list[dict]:
    """Parse Semantic Scholar JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        journal_info = item.get("journal") or {}
        entries.append({
            "title": item.get("title"),
            "container_title": journal_info.get("name") or item.get("venue"),
            "volume": str(journal_info.get("volume")) if journal_info.get("volume") else None,
            "issue": None,
            "pages": journal_info.get("pages"),
            "publisher": None,
            "year": item.get("year"),
            "doi": item.get("doi"),
        })
    return entries


def parse_openalex_result(data: dict, source_file: str) -> list[dict]:
    """Parse OpenAlex JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        source = item.get("source") or {}
        entries.append({
            "title": item.get("title"),
            "container_title": source.get("name"),
            "volume": None,
            "issue": None,
            "pages": None,
            "publisher": None,
            "year": item.get("publication_year"),
            "doi": item.get("doi"),
        })
    return entries


def parse_crossref_result(data: dict, source_file: str) -> list[dict]:
    """Parse CrossRef JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        entries.append({
            "title": item.get("title"),
            "container_title": item.get("container_title"),
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "pages": item.get("page"),
            "publisher": item.get("publisher"),
            "year": item.get("year"),
            "doi": item.get("doi"),
        })
    return entries


def parse_arxiv_result(data: dict, source_file: str) -> list[dict]:
    """Parse arXiv JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        year = None
        if item.get("published"):
            try:
                year = int(item["published"][:4])
            except (ValueError, TypeError):
                pass
        entries.append({
            "title": item.get("title"),
            "container_title": item.get("journal_ref"),
            "volume": None,
            "issue": None,
            "pages": None,
            "publisher": None,
            "year": year,
            "doi": item.get("doi"),
        })
    return entries


def parse_philpapers_result(data: dict, source_file: str) -> list[dict]:
    """Parse PhilPapers JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        entries.append({
            "title": item.get("title"),
            "container_title": item.get("journal") or item.get("source"),
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "pages": item.get("pages"),
            "publisher": item.get("publisher"),
            "year": item.get("year"),
            "doi": None,
        })
    return entries


def detect_api_source(data: dict, filename: str) -> str:
    """Detect which API produced this JSON file."""
    source = data.get("source", "").lower()

    if "semantic_scholar" in source or "s2" in source:
        return "s2"
    elif "openalex" in source:
        return "openalex"
    elif "crossref" in source:
        return "crossref"
    elif "arxiv" in source:
        return "arxiv"
    elif "philpapers" in source:
        return "philpapers"

    fname = filename.lower()
    if "s2_" in fname or fname.startswith("s2"):
        return "s2"
    elif "openalex" in fname or "oa_" in fname:
        return "openalex"
    elif "crossref" in fname or "verify_" in fname:
        return "crossref"
    elif "arxiv" in fname:
        return "arxiv"
    elif "philpapers" in fname or "pp_" in fname:
        return "philpapers"

    return "unknown"


def build_metadata_index(json_dirs) -> MetadataIndex:
    """Build a presence-based index of metadata from JSON files across one or
    more directories.

    json_dirs may be a single Path (back-compat) or a list of Paths (item-13
    union: the review root AND intermediate_files/json both feed one index, so
    directory shadowing no longer starves verification). Files failing
    json.loads are salvaged via _salvage_json (log-pollution tolerance);
    unsalvageable files are recorded in index.skipped_files, salvaged ones in
    index.salvaged_files.
    """
    index = MetadataIndex()

    if isinstance(json_dirs, (str, Path)):
        json_dirs = [json_dirs]

    seen: set = set()
    for json_dir in json_dirs:
        json_dir = Path(json_dir)
        if not json_dir.exists():
            continue
        for json_file in sorted(json_dir.glob("*.json")):
            resolved = str(json_file.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)

            try:
                raw = json_file.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                index.skipped_files.append(json_file.name)
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = _salvage_json(raw)
                if data is None:
                    index.skipped_files.append(json_file.name)
                    continue
                index.salvaged_files.append(json_file.name)

            api_source = detect_api_source(data, json_file.name)

            if api_source == "s2":
                entries = parse_s2_result(data, json_file.name)
            elif api_source == "openalex":
                entries = parse_openalex_result(data, json_file.name)
            elif api_source == "crossref":
                entries = parse_crossref_result(data, json_file.name)
            elif api_source == "arxiv":
                entries = parse_arxiv_result(data, json_file.name)
            elif api_source == "philpapers":
                entries = parse_philpapers_result(data, json_file.name)
            else:
                entries = parse_s2_result(data, json_file.name)

            # Source-authority tagging (year-corruption fix): record where
            # each pooled record came from. verify_* files are entry-scoped
            # CrossRef lookups (item-13 A4.1) and outrank broad search dumps
            # for correction purposes (same "verify_" filename convention
            # detect_api_source already relies on).
            entry_scoped = "verify_" in json_file.name.lower()
            for entry in entries:
                entry["source_file"] = json_file.name
                entry["entry_scoped"] = entry_scoped
                index.entries.append(entry)

                if entry.get("container_title"):
                    norm = normalize_journal(entry["container_title"])
                    if norm not in index.journals:
                        index.journals[norm] = []
                    index.journals[norm].append(entry["container_title"])

                if entry.get("volume"):
                    vol = str(entry["volume"]).strip()
                    if vol not in index.volumes:
                        index.volumes[vol] = []
                    index.volumes[vol].append(json_file.name)

                if entry.get("issue"):
                    iss = str(entry["issue"]).strip()
                    if iss not in index.issues:
                        index.issues[iss] = []
                    index.issues[iss].append(json_file.name)

                if entry.get("pages"):
                    norm = normalize_pages(entry["pages"])
                    if norm not in index.pages:
                        index.pages[norm] = []
                    index.pages[norm].append(entry["pages"])

                if entry.get("publisher"):
                    pub = entry["publisher"].lower().strip()
                    if pub not in index.publishers:
                        index.publishers[pub] = []
                    index.publishers[pub].append(entry["publisher"])

                if entry.get("year"):
                    yr = str(entry["year"])
                    if yr not in index.years:
                        index.years[yr] = []
                    index.years[yr].append(json_file.name)

                if entry.get("doi"):
                    norm = normalize_doi(entry["doi"])
                    index.dois[norm] = json_file.name

    return index


def is_field_verifiable(field_name: str, value: str, index: MetadataIndex) -> bool:
    """Check if a field value can be verified against the metadata index."""
    if field_name in ('journal', 'booktitle'):
        norm = normalize_journal(value)
        return norm in index.journals

    elif field_name == 'volume':
        return str(value).strip() in index.volumes

    elif field_name == 'number':
        return str(value).strip() in index.issues

    elif field_name == 'pages':
        norm = normalize_pages(value)
        return norm in index.pages

    elif field_name == 'publisher':
        return value.lower().strip() in index.publishers

    elif field_name == 'doi':
        norm = normalize_doi(value)
        return norm in index.dois

    # Unknown field - assume verifiable (don't remove)
    return True


def _normalize_title(title: str) -> str:
    """Unicode-aware, punctuation/subtitle-insensitive title key (item-13 B3).

    NFKD-normalize, drop combining marks (accent-insensitive so a bib title
    'Davidovic' matches an API 'Davidović'), keep every letter/digit including
    non-Latin (Greek, Cyrillic, Latin Extended-A stroke letters), casefold, and
    collapse punctuation/whitespace runs to single spaces. The old ASCII-only
    fold both erased non-Latin titles to '' (matching everything) and equated
    distinct stroke letters (Đ/Ł both dropped)."""
    if not title:
        return ""
    out = []
    for ch in unicodedata.normalize('NFKD', title):
        if unicodedata.combining(ch):
            continue
        out.append(ch if ch.isalnum() else ' ')
    return ' '.join(''.join(out).casefold().split())


def find_api_entry_for_bib_entry(entry, index: MetadataIndex) -> Optional[dict]:
    """Find THIS bib entry's own API record in the index (entry-scoped
    evidence, item-13 A4.1): first by DOI (exact normalized match), else by
    normalized title + year. Returns None when no affirmative match exists -
    the entry is then left completely untouched by the cleaner."""
    doi_value = entry.fields.get('doi')
    if doi_value:
        api = find_api_entry_by_doi(doi_value, index)
        if api is not None:
            return api
    norm_title = _normalize_title(entry.fields.get('title', ''))
    if not norm_title:
        return None
    bib_year = str(entry.fields.get('year', '')).strip()
    for api_entry in index.entries:
        if _normalize_title(api_entry.get('title') or '') != norm_title:
            continue
        api_year = str(api_entry.get('year') or '').strip()
        # B3: the title+year fallback requires BOTH years present AND equal.
        # A missing year on either side is NOT a match - a bare title is too
        # weak an identifier to authorize destructive cleaning.
        if not bib_year or not api_year or bib_year != api_year:
            continue
        return api_entry
    return None


def _field_matches_api(field_lower: str, value: str, api_entry: dict) -> bool:
    """Does this cleanable field's value match the entry's OWN matched API
    record (normalized)? Empty API values never match (can't confirm)."""
    if field_lower in ('journal', 'booktitle'):
        nv = normalize_journal(value)
        return bool(nv) and nv == normalize_journal(api_entry.get('container_title') or '')
    if field_lower == 'volume':
        nv = str(value).strip()
        return bool(nv) and nv == str(api_entry.get('volume') or '').strip()
    if field_lower == 'number':
        nv = str(value).strip()
        return bool(nv) and nv == str(api_entry.get('issue') or '').strip()
    if field_lower == 'pages':
        nv = normalize_pages(value)
        return bool(nv) and nv == normalize_pages(api_entry.get('pages') or '')
    if field_lower == 'publisher':
        nv = value.lower().strip()
        return bool(nv) and nv == str(api_entry.get('publisher') or '').lower().strip()
    if field_lower == 'doi':
        nv = normalize_doi(value)
        return bool(nv) and nv == normalize_doi(api_entry.get('doi') or '')
    return True


def _plan_type_downgrade(entry, surviving_fields: set, api_entry: dict) -> Optional[tuple]:
    """Post-removal type-downgrade decision (item-13 A4.2). Returns
    (old_type, 'misc') or None.

    @article guard: an article that would lose its required 'journal' is NOT
    demoted when it retains a DOI matching its own API record - a verified DOI
    proves the work is identifiable and @article degrades cleanly to
    author/year/title. Container types keep the existing demotion (their
    formatter's dangling 'In.' is suppressed downstream)."""
    entry_type = entry.type.lower()
    if entry_type not in REQUIRED_FIELDS:
        return None
    if REQUIRED_FIELDS[entry_type].issubset(surviving_fields):
        return None
    if entry_type == 'article':
        doi_value = entry.fields.get('doi')
        if ('doi' in surviving_fields and doi_value and api_entry.get('doi')
                and normalize_doi(doi_value) == normalize_doi(api_entry['doi'])):
            return None
    return (entry.type, 'misc')


def plan_entry_cleaning(entry, index: MetadataIndex, api_entry: dict) -> dict:
    """Compute (WITHOUT mutating) the cleaning plan for a MATCHED entry, so the
    circuit breaker can inspect the whole .bib before anything is written.

    A cleanable field is KEPT when it matches the entry's own API record OR
    appears in the global buckets (a value legitimately sourced from another
    file); otherwise it is a matched-entry mismatch - the hallucination class
    the cleaner exists for - and removed."""
    plan = {
        "removed_field_names": [],
        "removed_fields": [],
        "year_corrected": None,
        "type_downgraded": None,
    }

    if api_entry.get("year"):
        api_year = str(api_entry["year"])
        bib_year = entry.fields.get('year', '')
        if bib_year and bib_year != api_year:
            plan["year_corrected"] = (bib_year, api_year)

    surviving: set = set()
    for field_name in list(entry.fields.keys()):
        field_lower = field_name.lower()
        if (field_lower in IDENTITY_FIELDS or field_lower in EXEMPT_FIELDS
                or field_lower in CORRECTABLE_FIELDS or field_lower not in CLEANABLE_FIELDS):
            surviving.add(field_lower)
            continue
        value = entry.fields[field_name]
        keep = _field_matches_api(field_lower, value, api_entry) or \
            is_field_verifiable(field_lower, value, index)
        if keep:
            surviving.add(field_lower)
        else:
            plan["removed_field_names"].append(field_name)
            plan["removed_fields"].append(f"{field_name}={value}")

    plan["type_downgraded"] = _plan_type_downgrade(entry, surviving, api_entry)
    return plan


def _apply_cleaned_marker(entry, plan: dict) -> None:
    """Set a single METADATA_CLEANED tag on keywords, REPLACING any existing
    marker(s) rather than appending (item-13 A6) - a re-parsed bib re-cleaned
    on a second SubagentStop must not accumulate duplicate markers."""
    all_changes = list(plan["removed_field_names"])
    if plan["year_corrected"]:
        all_changes.append(f"year:{plan['year_corrected'][0]}->{plan['year_corrected'][1]}")
    if plan["type_downgraded"]:
        all_changes.append(f"type:@{plan['type_downgraded'][0]}->@{plan['type_downgraded'][1]}")
    if not all_changes:
        return
    cleaned_tag = f"METADATA_CLEANED: {', '.join(all_changes)}"
    existing = entry.fields.get('keywords')
    if existing:
        base = _MARKER_RE.sub("", existing).rstrip().rstrip(",")
        entry.fields['keywords'] = f"{base}, {cleaned_tag}" if base else cleaned_tag
    else:
        entry.fields['keywords'] = cleaned_tag


def apply_entry_cleaning(entry, plan: dict) -> None:
    """Mutate the pybtex entry per a plan from plan_entry_cleaning, then tag."""
    if plan["year_corrected"]:
        entry.fields['year'] = plan["year_corrected"][1]
    for fname in plan["removed_field_names"]:
        if fname in entry.fields:
            del entry.fields[fname]
    if plan["type_downgraded"]:
        entry.type = 'misc'
        entry.original_type = 'misc'  # pybtex Writer uses original_type
    _apply_cleaned_marker(entry, plan)


def write_bibtex(bib_data: BibliographyData, output_path: Path) -> None:
    """Write BibliographyData to file with consistent formatting."""
    writer = Writer()
    with open(output_path, 'w', encoding='utf-8') as f:
        writer.write_file(bib_data, f)


def _count_entries_as_unmatched(bib_path: Path, result: dict) -> dict:
    """B1 truthfulness: when there is no usable index (no dirs, or no parseable
    results), still PARSE the .bib and count every entry as UNMATCHED so the
    result is honest, never a silent no-op that reads like 'nothing to clean'.
    No entry is mutated and no METADATA_CLEANED marker is written on this path.
    """
    try:
        bib_data = parse_file(str(bib_path), bib_format='bibtex')
    except Exception as e:
        result["warnings"].append(f"Could not parse {bib_path.name} to count entries: {e}")
        return result
    result["entries_total"] = len(bib_data.entries)
    result["matched_entries"] = 0
    result["unmatched_entries"] = len(bib_data.entries)
    return result


def clean_bibtex(bib_path: Path, json_dirs) -> dict:
    """Clean unverifiable metadata from a BibTeX file.

    Args:
        bib_path: Path to BibTeX file
        json_dirs: a single Path (back-compat) OR a list of Paths holding JSON
            API output. All existing dirs' parseable/salvageable files feed one
            presence-based index (item-13 union: fixes directory shadowing).

    Returns a result dict. Item-13 keys: skipped_files, salvaged_files (A3);
    matched_entries, unmatched_entries, breaker_tripped, and the
    planned_*/applied_* metrics (A4, populated by the W3 loop).
    """
    result = {
        "success": True,
        "cleaned_entries": {},  # entry_key -> [removed fields]
        "total_fields_removed": 0,
        "years_corrected": 0,
        "types_downgraded": 0,
        "entries_cleaned": 0,
        "entries_total": 0,
        "matched_entries": 0,
        "unmatched_entries": 0,
        "breaker_tripped": False,
        # planned_* is computed BEFORE the breaker check (W3); applied_* only on
        # writes. On a breaker trip applied_* stay 0 but planned_* survive so the
        # aborted plan (by field name) is fully recorded.
        "planned_entries_cleaned": 0,
        "planned_fields_removed_by_name": {},
        "planned_demotions": 0,
        "applied_entries_cleaned": 0,
        "applied_fields_removed_by_name": {},
        "applied_demotions": 0,
        "skipped_files": [],
        "salvaged_files": [],
        "errors": [],
        "warnings": []
    }

    if isinstance(json_dirs, (str, Path)):
        json_dirs = [json_dirs]

    # Check files exist
    if not bib_path.exists():
        result["success"] = False
        result["errors"].append(f"BibTeX file not found: {bib_path}")
        return result

    existing_dirs = [Path(d) for d in json_dirs if Path(d).exists()]
    if not existing_dirs:
        shown = ", ".join(str(d) for d in json_dirs) if json_dirs else "(none passed)"
        result["warnings"].append(f"No JSON directory found ({shown}) - skipping cleaning")
        return _count_entries_as_unmatched(bib_path, result)  # B1: still count

    # Build metadata index (union across dirs, salvage log-polluted files)
    index = build_metadata_index(existing_dirs)
    result["skipped_files"] = list(index.skipped_files)
    result["salvaged_files"] = list(index.salvaged_files)
    if index.salvaged_files:
        result["warnings"].append(
            "Salvaged " + str(len(index.salvaged_files))
            + " log-polluted JSON file(s): " + ", ".join(index.salvaged_files)
        )
    if index.skipped_files:
        result["warnings"].append(
            "Skipped " + str(len(index.skipped_files))
            + " unparseable JSON file(s): " + ", ".join(index.skipped_files)
        )

    if not index.entries:
        result["warnings"].append("No API results found in JSON directory - skipping cleaning")
        return _count_entries_as_unmatched(bib_path, result)  # B1: still count

    # Parse BibTeX file
    try:
        bib_data = parse_file(str(bib_path), bib_format='bibtex')
    except PybtexSyntaxError as e:
        result["success"] = False
        result["errors"].append(f"BibTeX syntax error: {e}")
        return result
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"BibTeX parsing error: {e}")
        return result

    result["entries_total"] = len(bib_data.entries)

    # Entry-scoped planning: only entries with an affirmative API match are
    # cleaned; unmatched entries pass through untouched and are counted.
    plans = []  # (entry_key, entry, plan)
    for entry_key, entry in bib_data.entries.items():
        api_entry = find_api_entry_for_bib_entry(entry, index)
        if api_entry is None:
            result["unmatched_entries"] += 1
            continue
        result["matched_entries"] += 1
        plans.append((entry_key, entry, plan_entry_cleaning(entry, index, api_entry)))

    # B2: compute the PLANNED metrics (by field name) BEFORE the breaker check,
    # so an aborted plan is fully recorded even when nothing is written
    # (applied_* stay 0 on a trip; planned_* survive).
    for _, _, plan in plans:
        if plan["removed_field_names"]:
            result["planned_entries_cleaned"] += 1
        for fname in plan["removed_field_names"]:
            result["planned_fields_removed_by_name"][fname] = (
                result["planned_fields_removed_by_name"].get(fname, 0) + 1)
        if plan["type_downgraded"]:
            result["planned_demotions"] += 1

    # Circuit breaker: refuse a mass strip (systemic index failure). Keyed on
    # the planned count computed above.
    entries_with_strips = result["planned_entries_cleaned"]
    total = len(bib_data.entries)
    if (entries_with_strips >= BREAKER_MIN_ENTRIES and total > 0
            and entries_with_strips / total > BREAKER_FRACTION):
        result["breaker_tripped"] = True
        result["warnings"].append(
            f"Circuit breaker tripped: would strip fields from {entries_with_strips}"
            f"/{total} entries (> {BREAKER_FRACTION:.0%} and >= {BREAKER_MIN_ENTRIES}); "
            f"wrote nothing to {bib_path.name}."
        )
        return result  # applied_* stay 0; planned_* survive

    # Apply the planned changes, tallying applied_* alongside the legacy totals.
    for entry_key, entry, plan in plans:
        if not (plan["removed_field_names"] or plan["year_corrected"] or plan["type_downgraded"]):
            continue
        apply_entry_cleaning(entry, plan)
        result["entries_cleaned"] += 1
        result["applied_entries_cleaned"] += 1
        result["cleaned_entries"][entry_key] = plan["removed_fields"]
        result["total_fields_removed"] += len(plan["removed_field_names"])
        for fname in plan["removed_field_names"]:
            result["applied_fields_removed_by_name"][fname] = (
                result["applied_fields_removed_by_name"].get(fname, 0) + 1)
        if plan["year_corrected"]:
            result["years_corrected"] += 1
        if plan["type_downgraded"]:
            result["types_downgraded"] += 1
            result["applied_demotions"] += 1

    if result["applied_entries_cleaned"]:
        write_bibtex(bib_data, bib_path)

    return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "success": False,
            "errors": ["Usage: python metadata_cleaner.py <bib_file> <json_dir> [<json_dir> ...]"]
        }))
        sys.exit(2)

    bib_path = Path(sys.argv[1])
    json_dirs = [Path(a) for a in sys.argv[2:]]

    result = clean_bibtex(bib_path, json_dirs)
    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
