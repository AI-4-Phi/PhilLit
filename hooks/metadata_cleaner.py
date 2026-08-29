#!/usr/bin/env python3
"""Metadata provenance cleaner for SubagentStop hook.

Removes BibTeX bibliographic metadata that cannot be verified against API output,
preventing hallucinated data from persisting in the bibliography.

This is a fix, not a block: it automatically removes unverifiable fields while
preserving verified data. (An earlier blocking design, metadata_validator.py,
was never wired into any hook and was deleted 2026-08-02.)

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

import json
import os
import re
import sys
import traceback
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pybtex.database import parse_file, BibliographyData
from pybtex.database.output.bibtex import Writer
from pybtex.scanner import PybtexSyntaxError

from bib_identity import (
    normalize_doi,
    normalize_journal,
    normalize_pages,
    title_key,
    venue_key,
    year_key,
)

# Historic private names, kept so existing call sites and tests are unchanged.
# These are aliases, not copies: tests assert `is` identity.
_year_key = year_key
_normalize_title = title_key


# Fields that should be cleaned if not verifiable
CLEANABLE_FIELDS = {
    'journal', 'booktitle', 'volume', 'number', 'pages', 'publisher', 'doi'
}

# The three strip-policy classes partition CLEANABLE_FIELDS (pinned by test).
# DETAIL fields locate a work within an edition; their absence from a
# search-API record is the norm, so absence must never strip them - only a
# contradiction from an identity-verified record may. journal and
# booktitle are claim-bearing (a fabricated venue is the observed exploit) and
# keep the older policy; doi has its own, stricter licence.
DETAIL_FIELDS = frozenset({'volume', 'number', 'pages', 'publisher'})

# Circuit breaker: if a .bib would lose fields from more than
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

# The marker's removed-field grammar, shared with dedupe_bib.py and
# generate_bibliography.py. This module owns the marker
# format (_apply_cleaned_marker writes it); parse it here, in one place.
_MARKER_BODY_RE = re.compile(r"METADATA\\*_CLEANED:\s*(.*)$", re.DOTALL)


def marker_removed_fields(keywords: str) -> frozenset[str]:
    """Lowercase field names a METADATA_CLEANED marker records as REMOVED.

    Change tokens (`year:2007->2019`, `type:@a->@b`) contain ':' and are not
    removals. Tolerates pybtex's backslash-escaped form (METADATA\\_CLEANED)
    - the Writer escapes '_' on round-trip. Empty/absent marker -> empty set.
    """
    if not keywords:
        return frozenset()
    m = _MARKER_BODY_RE.search(keywords)
    if not m:
        return frozenset()
    names = set()
    for token in m.group(1).split(","):
        token = token.strip()
        if token and ":" not in token:
            names.add(token.lower())
    return frozenset(names)


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
    # Same container titles as `journals`, keyed by the looser venue_key so a
    # bibliography's expanded conference name verifies against the canonical
    # series name an API reports. Kept as a SEPARATE bucket rather than
    # re-keying `journals`: exact-name verification must stay available and
    # unchanged, and the loose key is only ever a fallback.
    venues: dict = field(default_factory=dict)
    volumes: dict = field(default_factory=dict)
    issues: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    publishers: dict = field(default_factory=dict)
    years: dict = field(default_factory=dict)
    dois: dict = field(default_factory=dict)
    entries: list = field(default_factory=list)
    skipped_files: list = field(default_factory=list)   # unparseable after salvage
    salvaged_files: list = field(default_factory=list)  # recovered from log pollution


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
    Among records of equal rank, pool order (filename sort) still decides.

    find_api_entry_for_bib_entry's conflict/abstention logic DEPENDS on this
    preference: it inspects `entry_scoped` on the single record returned here,
    so an authoritative record must win over pool order or the authority model
    silently degrades to filename order. Do not make this first-match.

    Known limitation: this preference governs the api_entry used for ALL
    field corrections (container_title, volume, pages, etc.), not just
    year - plan_entry_cleaning only gates the *year* overwrite on
    entry_scoped (see the Option C comment there). A sparse verify_*
    record (e.g. a --doi lookup that resolved only partial metadata) can
    therefore shadow a richer broad-dump record for this entry's other
    fields. Accepted for now since CrossRef verify records are typically
    complete; revisit if this proves to reduce correction coverage in
    practice."""
    if not doi:
        return None
    norm_doi = normalize_doi(doi)
    # An empty normalized DOI matches nothing. normalize_doi maps "doi:",
    # "https://doi.org/", "DOI: " and "  " all to "", so without this guard
    # any two records carrying a malformed DOI match each other and one
    # becomes the other's "API record". Same non-empty rule _field_matches_api
    # applies per field, hoisted out of the loop: the scan is dead work when
    # the key is empty.
    if not norm_doi:
        return None
    fallback = None
    for api_entry in index.entries:
        api_doi = api_entry.get("doi")
        if api_doi and normalize_doi(api_doi) == norm_doi:
            if api_entry.get("entry_scoped"):
                return api_entry
            if fallback is None:
                fallback = api_entry
    return fallback


# A year that may be WRITTEN into a .bib. Deliberately narrower than the
# comparison grammar in bib_identity.year_key: canonical form only (no leading zeros, no sign),
# 1-4 digits, non-zero. `str.isdigit()` must NOT be used here - it accepts
# Arabic-Indic and superscript digits that _INTEGRAL_YEAR_RE rejects, and
# `lstrip("-")` would swallow "--2007", so the write gate would re-admit
# exactly what the comparison grammar was tightened to exclude.
_WRITABLE_YEAR_RE = re.compile(r"[1-9][0-9]{0,3}\Z")


# Date fields whose year IS the citation year of the version of record.
# `created` is CrossRef's registration timestamp and never qualifies;
# `published-online` alone qualifies only because verify_paper.py reaches it
# solely when there is no print date at all (see its _YEAR_FIELDS order).
_VERSION_OF_RECORD_BASES = frozenset(
    {"published-print", "published", "published-online"})


def _year_is_overwritable(record: dict) -> bool:
    """May this record's year OVERWRITE a populated bibliography year?

    Requires POSITIVE provenance: the producer must say which date field the
    year came from, and it must be a version-of-record field. A record with no
    `year_basis` is refused - not because it is known bad, but because it is
    unknown, and the failure it guards against was measured, not hypothetical.

    Before verify_paper.py recorded a basis it took CrossRef's `published`
    first, which is the EARLIEST of print and online. 27 of 42 year rewrites
    across the local corpora therefore replaced a correct print-issue year with
    the online-first year. Those records are still on disk in delivered
    reviews; nothing in them distinguishes the good years from the bad, so the
    only safe rule is to require the evidence the fixed producer now supplies.
    Refusals are counted in `years_declined` and warned about, never silent.
    """
    return record.get("year_basis") in _VERSION_OF_RECORD_BASES


# The reprint-capable entry class: the works that get re-registered under a
# later edition's DOI. Chapters ride their volume's edition, so incollection/
# inbook share the failure with book - the same set stamp_evidence.py models.
_REPRINT_CAPABLE_TYPES = frozenset({"book", "incollection", "inbook"})

# User-facing explanation per decline reason. The reasons exist because
# different causes want different fixes (the Option C design note above), so
# each maps to its own remediation; the report never folds one into another.
_DECLINE_REASON_MESSAGES = {
    "unscoped": ("where the only DOI-matched evidence was a broad search "
                 "dump, not a targeted CrossRef lookup"),
    "no-version-of-record-date": (
        "where the CrossRef record does not say which date field its year "
        "came from, so it may be an online-first date rather than the "
        "citation year (re-run verification to resolve)"),
    "book-year-moved-later": (
        "where a book-class entry's year would have moved LATER - a reprint "
        "edition's DOI carries the reprint's print year, not the work's "
        "(kept the earlier bibliography year)"),
    "book-year-direction-unknown": (
        "where a book-class entry's year could not be compared for "
        "direction (unparseable bibliography year; fix it or re-verify "
        "the entry)"),
}


def _book_year_decline_reason(record: dict, entry_type: str,
                              api_year: str, bib_year_key: str) -> Optional[str]:
    """Reason to REFUSE this year write under the reprint-edition direction
    bound - or None when the write stays licensed.

    A reprint edition gets its own DOI, and CrossRef's `published-print` for
    that DOI is genuinely the reprint's year while being the wrong citation
    year for the WORK: *The Law of Peoples* is Harvard UP 1999, JSTOR's
    paperback DOI carries published-print 2001, and the resulting rewrite
    manufactured a spurious Chicago a/b collision ("Rawls 2001b" for a 1999
    book). Chicago author-date cites the original publication year, and a
    reprint can only move a year FORWARD - so for the reprint-capable class
    a later year is refused ("book-year-moved-later") while an earlier one
    (a correction back toward the original edition) stays allowed. This
    bound is what made fixing the missing published-print request on the
    search path safe: requesting print dates there extends print-year
    overwrites from "books verified by DOI lookup" to every search-verified
    book.

    Bookness is POSITIVE evidence from either side: the record's
    `suggested_bibtex_type` (verify_paper.py derives it onto every record;
    covers per-chapter DOIs of a reprint volume, which map to incollection)
    OR the bib entry's own type (covers records written before the producer
    emitted the field, and wrong-granularity DOIs pasted into a @book
    entry). A bib year the direction test cannot parse ("n.d.", "[2021]")
    gives no direction evidence, so for this class the guard fails closed
    under its own reason ("book-year-direction-unknown" - the remediation
    is fixing the malformed year, not hunting reprint DOIs); declines are
    counted, never silent.
    """
    if ((record.get("suggested_bibtex_type") or "").lower()
            not in _REPRINT_CAPABLE_TYPES
            and (entry_type or "").lower() not in _REPRINT_CAPABLE_TYPES):
        return None
    if not _WRITABLE_YEAR_RE.match(bib_year_key):
        return "book-year-direction-unknown"
    if int(api_year) > int(bib_year_key):
        return "book-year-moved-later"
    return None


def _year_of(record: dict) -> str:
    """Canonical year of a pooled record, or "" when it supplies none.

    Tests `is None` rather than truthiness: a raw `0`/`0.0` is falsy but IS a
    value, and `record.get("year") or ""` therefore made numeric zero read as
    yearless while the string "0" read as year-bearing - reintroducing the
    int/str split _year_key exists to erase.
    """
    raw = record.get("year")
    return "" if raw is None else _year_key(raw)


def find_doi_year_conflicts(doi: str, index: 'MetadataIndex') -> dict:
    """Distinct CANONICAL year values (with their source files) across pooled
    entries sharing this DOI, compared via _year_key so an int/float encoding
    split is not a disagreement. Returns {} unless at least two distinct
    canonical years exist.

    Option D of the year-corruption fix: a same-DOI disagreement should be
    visible in the cleaning report however it is resolved - silent
    resolution is what let bad broad-dump years overwrite verified ones."""
    if not doi:
        return {}
    norm_doi = normalize_doi(doi)
    # Empty normalizes to "" and would collide with every other malformed
    # DOI - see find_api_entry_by_doi.
    if not norm_doi:
        return {}
    years: dict = {}
    for api_entry in index.entries:
        api_doi = api_entry.get("doi")
        if not api_doi or normalize_doi(api_doi) != norm_doi:
            continue
        raw_year = api_entry.get("year")
        year = _year_key(raw_year) if raw_year else ""
        if year:
            years.setdefault(year, set()).add(api_entry.get("source_file") or "?")
    if len(years) < 2:
        return {}
    return {y: sorted(files) for y, files in years.items()}


def parse_s2_result(data: dict, source_file: str) -> list[dict]:
    """Parse Semantic Scholar JSON format.

    Also the fallback parser for unrecognized sources, so `journal` may arrive
    as a bare STRING rather than S2's {name, volume, pages} object (CORE writes
    it that way). Coerce instead of dropping: the string IS the container
    title, and treating it as `{}` would both lose the datum and — before the
    isinstance guard — raise AttributeError.
    """
    results = data.get("results", [])
    entries = []
    for item in results:
        journal_info = item.get("journal")
        if isinstance(journal_info, str):
            journal_info = {"name": journal_info}
        elif not isinstance(journal_info, dict):
            journal_info = {}
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


def _openalex_pages(biblio: dict) -> Optional[str]:
    """OpenAlex reports first_page/last_page separately; the index stores a range."""
    first = str(biblio.get("first_page") or "").strip()
    last = str(biblio.get("last_page") or "").strip()
    if first and last:
        return first if first == last else f"{first}-{last}"
    # A lone last_page is NOT evidence of a page value. A record that supplies
    # only an end page has not attested a page range or a page, so accepting it
    # would let a bibliography verify a page number the source never gave.
    # (Why such records exist is not established here -- a mis-parsed article
    # number is one suggested explanation, unverified.) first_page alone IS a
    # real single-page citation and is kept.
    return first or None


def parse_openalex_result(data: dict, source_file: str) -> list[dict]:
    """Parse OpenAlex JSON format.

    `biblio` (volume/issue/first_page/last_page) and the source's publisher are
    read through rather than hardcoded to None. Hardcoding them DISCARDED
    evidence OpenAlex supplies, so a page range or volume the bibliography got
    right had to be re-verified by some other source or be deleted - the same
    trap the CORE parser's comment warns about. Older result files that predate
    the producer emitting `biblio` simply carry nothing here, which is the old
    behaviour.
    """
    results = data.get("results", [])
    entries = []
    for item in results:
        source = item.get("source") or {}
        biblio = item.get("biblio") or {}
        if not isinstance(biblio, dict):
            biblio = {}
        entries.append({
            "title": item.get("title"),
            "container_title": source.get("name"),
            "volume": str(biblio["volume"]).strip() if biblio.get("volume") else None,
            "issue": str(biblio["issue"]).strip() if biblio.get("issue") else None,
            "pages": _openalex_pages(biblio),
            "publisher": source.get("publisher") or None,
            "year": item.get("publication_year"),
            "doi": item.get("doi"),
        })
    return entries


def parse_crossref_result(data: dict, source_file: str) -> list[dict]:
    """Parse CrossRef JSON format.

    `year_basis` is read through when the producer supplies it: it names the
    CrossRef date field the year came from, and only a version-of-record field
    licenses OVERWRITING a bibliography's own year (see _year_is_overwritable).
    """
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
            "year_basis": item.get("year_basis"),
            # Read through so the reprint-edition direction bound can tell a
            # book from an article (see _book_year_decline_reason). verify_paper
            # writes it on every record; absence just means the bound never
            # fires, which is the old behavior.
            "suggested_bibtex_type": item.get("suggested_bibtex_type"),
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


def parse_core_result(data: dict, source_file: str) -> list[dict]:
    """Parse CORE JSON format (search_core.py's `_format_work`).

    CORE's `journal` is a plain string (the first journal's title), and it
    carries `publisher` — both of which the S2 fallback parser used to lose or
    choke on.
    """
    results = data.get("results", [])
    entries = []
    for item in results:
        entries.append({
            "title": item.get("title"),
            "container_title": item.get("journal"),
            # Read through rather than hardcoding None: search_core.py's
            # _format_work does not emit these today, but CORE work objects
            # carry them, and a hardcoded None would silently DISCARD that
            # evidence the day the writer starts including it — which means
            # more stripping, not less.
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "pages": item.get("pages"),
            "publisher": item.get("publisher"),
            "year": item.get("year"),
            "doi": item.get("doi"),
        })
    return entries


def detect_api_source(data: dict, filename: str) -> str:
    """Detect which API produced this JSON file."""
    raw_source = data.get("source")
    source = raw_source.lower() if isinstance(raw_source, str) else ""

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
    elif "core" in source:
        return "core"

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
    elif "core_" in fname or fname.startswith("core"):
        return "core"

    return "unknown"


def build_metadata_index(json_dirs) -> MetadataIndex:
    """Build a presence-based index of metadata from JSON files across one or
    more directories.

    json_dirs may be a single Path (back-compat) or a list of Paths (the
    review root AND intermediate_files/json both feed one index, so
    directory shadowing no longer starves verification). Files failing
    json.loads are salvaged via _salvage_json (log-pollution tolerance);
    unsalvageable files are recorded in index.skipped_files, salvaged ones in
    index.salvaged_files.

    Every file is processed in ISOLATION: one that is not a JSON *object*, or
    whose contents a parser cannot handle, joins index.skipped_files and the
    build continues. Without that isolation a single malformed file killed the
    index — and so ALL cleaning — for the whole review; a string-shaped CORE
    `journal` did exactly that on 27 of 42 real corpora.
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
            except Exception:   # noqa: BLE001 - per-file fail-soft
                # json.loads can also raise a plain ValueError (integer digit
                # limit) or RecursionError (deep nesting). Neither is a
                # JSONDecodeError, so before this they escaped and killed the
                # whole index - the 3G failure class one layer up, in the
                # live destructive path. Salvage is pointless for these
                # (the text parsed as JSON, it is the VALUE that is refused),
                # so skip the file.
                index.skipped_files.append(json_file.name)
                continue

            # Not an API envelope at all (e.g. a researcher's own top-level
            # list, as in final_selection.json) — nothing to index.
            if not isinstance(data, dict):
                index.skipped_files.append(json_file.name)
                continue

            # TRANSACTIONAL: stage into a throwaway index and merge only on
            # complete success. Ingesting straight into `index` would leave a
            # half-read file's records behind when a later record raises — so
            # a file reported as skipped would still be supplying DOI matches
            # and presence evidence that authorize destructive cleaning.
            staged = MetadataIndex()
            try:
                _index_one_file(staged, data, json_file.name)
            except Exception:
                # Fail SOFT, per file: an unexpected shape costs this file's
                # records, never the whole index. clean_bibtex surfaces the
                # name in result["warnings"], so the skip is never silent.
                index.skipped_files.append(json_file.name)
                continue
            _merge_index(index, staged)

    return index


def _merge_index(dst: MetadataIndex, src: MetadataIndex) -> None:
    """Fold a fully-parsed file's staged index into the shared one.

    Merging in file order preserves the previous semantics exactly: bucket
    lists accumulate in the order files are read, and `dois` keeps its
    last-writer-wins behaviour."""
    dst.entries.extend(src.entries)
    for bucket in ("journals", "venues", "volumes", "issues", "pages",
                   "publishers", "years"):
        target, source = getattr(dst, bucket), getattr(src, bucket)
        for key, values in source.items():
            target.setdefault(key, []).extend(values)
    dst.dois.update(src.dois)


def _index_one_file(index: MetadataIndex, data: dict, filename: str) -> None:
    """Parse one API JSON envelope and fold its records into `index`.

    Split out of build_metadata_index so a single try/except can isolate the
    whole per-file path — dispatch, parsing, and ingestion alike.
    """
    api_source = detect_api_source(data, filename)

    if api_source == "s2":
        entries = parse_s2_result(data, filename)
    elif api_source == "openalex":
        entries = parse_openalex_result(data, filename)
    elif api_source == "crossref":
        entries = parse_crossref_result(data, filename)
    elif api_source == "arxiv":
        entries = parse_arxiv_result(data, filename)
    elif api_source == "philpapers":
        entries = parse_philpapers_result(data, filename)
    elif api_source == "core":
        entries = parse_core_result(data, filename)
    else:
        entries = parse_s2_result(data, filename)

    # Source-authority tagging (year-corruption fix): record where each pooled
    # record came from, and which records may OVERWRITE a populated year.
    # Authority is keyed on the envelope's CONTENT, not on its filename
    # (ROADMAP 3I): a CrossRef envelope that resolved exactly ONE work is a
    # targeted single-work lookup, which is precisely the evidence class the
    # gate trusts; a multi-result envelope is a broad dump, which is precisely
    # the class it exists to refuse.
    #
    # The old rule was `"verify_" in filename.lower() and api_source ==
    # "crossref"`, and the filename half was wrong in both directions.
    # Measured over the 45 local corpora (7109 JSON files):
    #   * 262 files are genuine single-work CrossRef lookups saved WITHOUT a
    #     `verify_` name (`cr_*.json`, `<author>_<year>.json`, ...). Every one
    #     was trusted to acquit (its journal/volume/pages still protected
    #     fields from stripping) but not to convict (it could not correct a
    #     wrong year). They gain authority here.
    #   * 181 `verify_*` CrossRef files lose the tag - and ALL 181 carry
    #     `results: []` (not_found / error envelopes), contributing zero
    #     records to the index. So no record loses authority, which is why the
    #     filename rule needs no legacy fallback.
    # `api_source == "crossref"` is retained and load-bearing: 11 multi-result
    # `verify_*.json` files in the corpora are Semantic Scholar dumps, the very
    # source class that caused the original corruption.
    #
    # Deliberately NOT required, though both were proposed: that the lookup
    # mode be `doi`, and that the requested DOI equal the record's.
    # `verify_paper.py --title` is still a targeted single-work query (227 such
    # files here), and once a record's DOI matches the bib entry's, the record
    # IS CrossRef's own metadata for that DOI - identification path does not
    # change provenance. The requested-vs-returned DOI check would buy nothing
    # either: 2 of 981 differ locally, both benign aliases (a `10.1037//` typo
    # CrossRef canonicalized, and a JSTOR->publisher redirect).
    results = data.get("results")
    entry_scoped = (api_source == "crossref"
                    and isinstance(results, list) and len(results) == 1)
    for entry in entries:
        entry["source_file"] = filename
        entry["entry_scoped"] = entry_scoped
        index.entries.append(entry)

        if entry.get("container_title"):
            norm = normalize_journal(entry["container_title"])
            if norm not in index.journals:
                index.journals[norm] = []
            index.journals[norm].append(entry["container_title"])
            vkey = venue_key(entry["container_title"])
            if vkey:
                if vkey not in index.venues:
                    index.venues[vkey] = []
                index.venues[vkey].append(entry["container_title"])

        if entry.get("volume"):
            vol = str(entry["volume"]).strip()
            if vol not in index.volumes:
                index.volumes[vol] = []
            index.volumes[vol].append(filename)

        if entry.get("issue"):
            iss = str(entry["issue"]).strip()
            if iss not in index.issues:
                index.issues[iss] = []
            index.issues[iss].append(filename)

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
            index.years[yr].append(filename)

        if entry.get("doi"):
            norm = normalize_doi(entry["doi"])
            index.dois[norm] = filename


def is_field_verifiable(field_name: str, value: str, index: MetadataIndex) -> bool:
    """Check if a field value can be verified against the metadata index.

    Only the journal/booktitle branch is LIVE in production since the
    strip-rule fix: plan_entry_cleaning consults this bucket for venue fields
    alone, so the detail-field branches below are exercised by unit tests
    only. Do not read their presence as evidence that bucket rescue still
    applies to them - an unrelated paper's matching issue number is
    coincidence, not corroboration, and rewiring it would restore exactly the
    defect that fix removed."""
    if field_name in ('journal', 'booktitle'):
        if normalize_journal(value) in index.journals:
            return True
        # Fallback: the same venue named in a different citation form. See
        # bib_identity.venue_key for the folds and their measured bounds.
        vkey = venue_key(value)
        return bool(vkey) and vkey in index.venues

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


# Fields an api_entry supplies for verification. Used to compare how COMPLETE
# two equally-authoritative records are before swapping between them.
_AUTHORITY_FIELDS = ("container_title", "volume", "issue", "pages", "publisher")


def _supplied_fields(record: dict) -> set:
    """Which verification-bearing fields this record actually supplies.

    Whitespace is not a supplied value - it verifies nothing.
    """
    return {name for name in _AUTHORITY_FIELDS
            if str(record.get(name) or "").strip()}


def _record_completeness(record: dict) -> int:
    """How many verification-bearing fields this record actually supplies."""
    return len(_supplied_fields(record))


class CleaningAbstention:
    """Third outcome of find_api_entry_for_bib_entry: this entry's DOI matched
    indexed records - its existence is confirmed - but the year evidence is
    contradictory, so the cleaner declines to clean. Falsy on purpose: for
    every cleaning decision an abstention behaves exactly like no-match; only
    the cleaning ledger records the difference (api_matched: True +
    cleaning_abstained), so a year-scoped refusal is never converted into an
    existence-scoped penalty downstream."""
    __slots__ = ("reason", "normalized_doi")

    def __init__(self, reason: str, normalized_doi: str):
        self.reason = reason  # "scoped_year_disagreement" | "pooled_year_conflict"
        self.normalized_doi = normalized_doi

    def __bool__(self) -> bool:
        return False


def find_api_entry_for_bib_entry(entry, index: MetadataIndex):
    """Find THIS bib entry's own API record in the index (entry-scoped
    evidence): first by DOI (exact normalized match), else by
    normalized title + year. Returns the matched record dict, None when no
    affirmative match exists, or a CleaningAbstention - in both of the
    latter cases the entry is left completely untouched by the cleaner.

    A DOI whose pooled evidence CONFLICTS on year, with no entry-scoped
    verify_* record to settle it, returns a CleaningAbstention - and does so
    without trying the title+year fallback (see the inline comment on that
    branch). Abstention deliberately trades correction coverage for safety:
    when the pool is self-inconsistent, filename order is not a valid
    authority rule. But the DOI itself DID match, so the abstention carries
    the normalized DOI for the ledger to attest existence (Option C).

    Note the conflict test is EXISTENCE-based, not plurality-based: two
    records saying 2007 and one saying 2019 still abstain. That is
    intentional for a destructive fixer - do not "optimize" it into majority
    rule without evidence that the majority is right."""
    doi_value = entry.fields.get('doi')
    if doi_value:
        api = find_api_entry_by_doi(doi_value, index)
        if api is not None:
            # An entry-scoped verify_* record is a direct CrossRef lookup on
            # this DOI: it carries correction authority and settles a
            # same-DOI disagreement on its own.
            if api.get("entry_scoped"):
                # A scoped record settles a same-DOI disagreement only when it
                # actually SUPPLIES a year, and only when the scoped records
                # agree. Two verify_* snapshots can differ (CrossRef corrects
                # records between crawls; a partial response can be persisted;
                # print vs online dates get selected differently) - letting
                # filename order pick the winner would restore the
                # arbitrary-authority bug one tier up, where it CAN rewrite
                # the bib year.
                scoped = [
                    other for other in index.entries
                    if other.get("entry_scoped")
                    and _field_matches_api('doi', doi_value, other)
                ]
                # Canonicalize BEFORE testing emptiness: `" "` is raw-truthy
                # but is not a year, and must not read as a disagreement.
                scoped_years = {
                    key for key in (_year_of(other) for other in scoped) if key
                }
                if len(scoped_years) > 1:
                    return CleaningAbstention(
                        "scoped_year_disagreement", normalize_doi(doi_value))
                if scoped_years:
                    # Prefer a scoped record that HAS a year, so a partial
                    # snapshot sorting first cannot silently suppress the
                    # correction a complete one would authorize - but NEVER
                    # swap to a LESS complete record: the winner governs
                    # verification of every field, so trading completeness
                    # for a year would delete metadata the first record
                    # verified. Residual: two records supplying the SAME
                    # fields with different VALUES are still first-wins - a
                    # superset gate protects coverage, not agreement.
                    if not _year_of(api):
                        for other in scoped:
                            # A SUPERSET, not a bigger count: an equally-sized
                            # but disjoint record cannot verify what `api`
                            # could, so swapping to it deletes exactly the
                            # fields this gate exists to protect.
                            if (_year_of(other)
                                    and _supplied_fields(other)
                                    >= _supplied_fields(api)):
                                return other
                    return api
                # Every scoped record is yearless: none of them can say which
                # of two disagreeing broad years is right, so fall through to
                # the pooled-conflict check rather than granting authority.
            # Reached either with no entry-scoped record at all, OR with a
            # yearless one that cannot settle a year disagreement. Do NOT
            # re-gate this on entry_scoped: that is exactly the hole the
            # yearless fall-through above was added to close.
            # The pooled sources disagree: there is no basis
            # to prefer either record, so abstain. Return None WITHOUT falling
            # through to the title+year heuristic below - when the bib's own
            # year already equals the bad value (common, since an earlier run
            # may have written it), that weaker signal would "confirm" the
            # wrong source and reintroduce the very failure this prevents.
            if find_doi_year_conflicts(doi_value, index):
                return CleaningAbstention(
                    "pooled_year_conflict", normalize_doi(doi_value))
            return api
    norm_title = _normalize_title(entry.fields.get('title', ''))
    if not norm_title:
        return None
    raw_bib_year = str(entry.fields.get('year', '')).strip()
    bib_year = _year_key(raw_bib_year) if raw_bib_year else ""
    for api_entry in index.entries:
        if _normalize_title(api_entry.get('title') or '') != norm_title:
            continue
        raw_api_year = api_entry.get('year')
        api_year = _year_key(raw_api_year) if raw_api_year else ""
        # B3: the title+year fallback requires BOTH years present AND equal.
        # A missing year on either side is NOT a match - a bare title is too
        # weak an identifier to authorize destructive cleaning.
        if not bib_year or not api_year or bib_year != api_year:
            continue
        return api_entry
    return None


def _compare_scalar(value, api_value) -> str:
    """Three-way state for a field compared as a whitespace-stripped scalar
    (volume, number). Match requires a non-empty bib value: an empty field
    confirms nothing, so it can never be corroborated by a record."""
    nv = str(value).strip()
    api = str(api_value or '').strip()
    if nv and nv == api:
        return 'match'
    return 'contradict' if api else 'no-evidence'


# Leading digit run of a normalized page value. A value that does not START
# with digits (roman numerals `xii--xv`, article ids `e12345`) has no
# comparable first page. Anchored in the pattern as well as by .match(), so a
# later switch to .search() cannot silently find `12345` inside `e12345`.
_FIRST_PAGE_RE = re.compile(r'\A\d+')


def _first_page(normalized_pages: str) -> str:
    """First page of a normalized page value, '' when it has none."""
    m = _FIRST_PAGE_RE.match(normalized_pages)
    return m.group(0) if m else ''


def _field_compare(field_lower: str, value: str, api_entry: dict) -> str:
    """Three-way comparison of a cleanable field against the entry's OWN
    matched API record: 'match' | 'contradict' | 'no-evidence'.

    'no-evidence' means the record does not carry the field at all. It is NOT a
    weak 'contradict': search-API records rarely carry pages/issue/publisher,
    and 80% of the pre-fix strips were absence-driven on values a CrossRef
    truth anchor found majority-TRUE (see
    docs/known-issues/cleaner-strip-rule-absence-vs-contradiction.md). Which
    states may strip is plan_entry_cleaning's decision, per field class - this
    function only reports the evidence.

    A field with no comparison rule reports 'match', mirroring the
    default-keep every earlier version of this comparison carried: an unknown
    field must never be condemned by a rule that was never written for it."""
    if field_lower in ('journal', 'booktitle'):
        api_container = api_entry.get('container_title') or ''
        vkey, api_vkey = venue_key(value), venue_key(api_container)
        if vkey and vkey == api_vkey:
            return 'match'
        nv = normalize_journal(value)
        if nv and nv == normalize_journal(api_container):
            return 'match'
        return 'contradict' if str(api_container).strip() else 'no-evidence'
    if field_lower == 'volume':
        return _compare_scalar(value, api_entry.get('volume'))
    if field_lower == 'number':
        return _compare_scalar(value, api_entry.get('issue'))
    if field_lower == 'pages':
        nv = normalize_pages(value)
        api = normalize_pages(api_entry.get('pages') or '')
        if nv and nv == api:
            return 'match'
        # A record value with no alphanumeric character at all carries no page
        # information, however non-empty it looks: normalize_pages(" - ") is
        # "-", which would sail past a bare `not api` test and then condemn a
        # true page range through the fall-through below. The guard is
        # deliberately narrow - `e12345` and roman numerals stay alphanumeric
        # and keep contradicting.
        if not api or not any(ch.isalnum() for ch in api):
            return 'no-evidence'
        # CrossRef truncates a page RANGE to its first page, so a differing
        # TAIL is not a contradiction (bogen1988saving: true `303--352` against
        # a record's `303`). The tolerance needs both sides to HAVE a first
        # page, and it is bounded to the shape it was written for: at least
        # one side must be a bare first page (no range separator, which
        # normalize_pages has already reduced to '-'). When BOTH sides carry a
        # range, a shared first page is not truncation - `100--999` against
        # `100--101` is a real disagreement about the work's extent, and
        # reading it as a match was an over-match. Unequal first pages
        # contradict either way.
        first_nv, first_api = _first_page(nv), _first_page(api)
        if first_nv and first_api:
            truncation_shape = '-' not in nv or '-' not in api
            if first_nv == first_api and truncation_shape:
                return 'match'
        return 'contradict'
    if field_lower == 'publisher':
        nv = value.lower().strip()
        api = str(api_entry.get('publisher') or '').lower().strip()
        # PREFIX containment either way, because publisher names are reported at
        # different depths of the same imprint ('Springer' vs 'Springer
        # International Publishing') and sometimes with a location concatenated
        # onto the tail ('Oxford University PressNew York'). A prefix test, not
        # a substring test: 'Press' is a substring of 'Oxford University Press'
        # but names no publisher, and suffix containment would verify it.
        # Both sides must be non-empty: '' is a prefix of everything, which
        # would make absence read as a match.
        #
        # But a BARE prefix is not enough - unbounded, it verified 'O' against
        # 'Oxford University Press', keeping a one-letter fabrication and (via
        # _verified_identifier) buying EVIDENCE-EXISTENCE on the identifier
        # "o". So a strict prefix counts only when it stops somewhere
        # credible: at a WORD BOUNDARY in the longer name (the Springer case),
        # or - for the concatenation artifact, which has no boundary by
        # construction - when the prefix is itself MULTI-TOKEN ('oxford
        # university press'). A single token cut mid-word contradicts:
        # 'Brill' is not 'Brillante Editores'.
        if nv and api:
            if nv == api:
                return 'match'
            shorter, longer = sorted((nv, api), key=len)
            # Not equal + prefix => strictly longer, so the index is safe.
            if longer.startswith(shorter) and (
                    not longer[len(shorter)].isalnum()
                    or len(shorter.split()) >= 2):
                return 'match'
        return 'contradict' if api else 'no-evidence'
    if field_lower == 'doi':
        nv = normalize_doi(value)
        api = normalize_doi(api_entry.get('doi') or '')
        if nv and nv == api:
            return 'match'
        return 'contradict' if api else 'no-evidence'
    return 'match'


def _field_matches_api(field_lower: str, value: str, api_entry: dict) -> bool:
    """Does this cleanable field's value match the entry's OWN matched API
    record (normalized)? Empty API values never match (can't confirm).

    Exactly the 'match' state of _field_compare, so the two can never drift.
    The strip-rule fix widened the pages and publisher comparisons in
    _field_compare, but this function's four call expressions in this module,
    across three other callers, only ever pass 'doi' or 'publisher' - never
    'pages'. Only _verified_identifier's publisher check inherits that
    widening:
    'Springer' against 'Springer International Publishing' now verifies a
    book identity there - but only as far as the boundary/multi-token bound
    on prefix containment reaches, so a one-letter 'O' does not. The other
    three - _plan_type_downgrade's @article
    DOI guard, _verified_identifier's own DOI check, and the
    scoped-year-disagreement scan in find_api_entry_for_bib_entry - all
    pass only 'doi', which never widened, so they are unchanged."""
    return _field_compare(field_lower, value, api_entry) == 'match'


def _plan_type_downgrade(entry, surviving_fields: set, api_entry: dict) -> Optional[tuple]:
    """Post-removal type-downgrade decision. Returns
    (old_type, 'misc') or None.

    @article guard: an article that would lose its required 'journal' is NOT
    demoted when it retains a DOI matching its own API record - a verified DOI
    proves the work is identifiable and @article degrades cleanly to
    author/year/title. Container types keep the existing demotion (their
    formatter's dangling 'In.' is suppressed downstream).

    The DOI comparison goes through `_field_matches_api`, NOT a local
    `normalize_doi(a) == normalize_doi(b)`: normalize_doi maps `doi:`,
    `https://doi.org/` and `"  "` all to `""`, so a raw equality test reads
    two MALFORMED DOIs as a verified match and suppresses a demotion that
    should happen. `_field_matches_api` already carries the `bool(nv)`
    non-empty guard every other comparison site uses."""
    entry_type = entry.type.lower()
    if entry_type not in REQUIRED_FIELDS:
        return None
    if REQUIRED_FIELDS[entry_type].issubset(surviving_fields):
        return None
    if entry_type == 'article':
        doi_value = entry.fields.get('doi')
        if ('doi' in surviving_fields and doi_value
                and _field_matches_api('doi', doi_value, api_entry)):
            return None
    return (entry.type, 'misc')


def plan_entry_cleaning(entry, index: MetadataIndex, api_entry: dict) -> dict:
    """Compute (WITHOUT mutating) the cleaning plan for a MATCHED entry, so the
    circuit breaker can inspect the whole .bib before anything is written.

    Each cleanable field is compared three ways against the entry's own API
    record (_field_compare) and judged by its class:

      * DETAIL_FIELDS - removed only on a CONTRADICTION from an
        identity-verified record. Absence removes nothing.
      * journal / booktitle - policy unchanged: removed unless the record
        matches or the value appears in the global buckets (legitimately
        sourced from another file), so absence still removes.
      * doi - removed only on a contradiction from an ENTRY-SCOPED record.

    `unverified_fields` and `venue_stripped_no_evidence` are telemetry, not
    inputs to any decision here or downstream (see write_cleaning_ledger)."""
    plan = {
        "removed_field_names": [],
        "removed_fields": [],
        "year_corrected": None,
        "year_correction_declined": None,
        "type_downgraded": None,
        "unverified_fields": [],
        "venue_stripped_no_evidence": [],
    }

    # Year-corruption fix (Option C): overwriting a populated year takes TWO
    # independent licences, because it has failed in two independent ways.
    #   1. WHO says so - only an entry-scoped record (a targeted single-work
    #      CrossRef lookup). Broad search dumps are discovery evidence, not
    #      correction authority: they were never queried for this entry, and
    #      their per-DOI metadata is sometimes wrong (a Semantic Scholar dump
    #      rewrote Sparrow 2007 to 2019).
    #   2. WHAT they are saying - the record's year must be a version-of-record
    #      year, not an online-first or registration date. CrossRef's own
    #      `published` field is the EARLIEST of print and online, so a record
    #      built from it carries the pre-issue year and "corrects" correct
    #      bibliographies (Mind 130(517): print 2021, online 2019).
    # (See the entry_scoped-preference docstring on find_api_entry_by_doi for
    # the corresponding limitation on non-year fields.)
    if _year_of(api_entry):
        # Compare AND write the canonical form: a record carrying 2007.0 must
        # neither read as a disagreement with a bib year of 2007 nor land in
        # the .bib as "2007.0". _year_key is exact, so the written value is
        # always one the record actually supplied.
        api_year = _year_of(api_entry)
        bib_year = entry.fields.get('year', '')
        # A comparison KEY is not automatically a writable value. `" "` is
        # raw-truthy but canonicalizes to "", and "n.d."/"2007."/"--2007" and
        # non-ASCII digits round-trip verbatim - writing any of those would
        # corrupt or empty a populated year. Only a plausible publication
        # year may be written; see _WRITABLE_YEAR_RE.
        if (_WRITABLE_YEAR_RE.match(api_year)
                and bib_year and _year_key(bib_year) != api_year):
            if api_entry.get("entry_scoped") and _year_is_overwritable(api_entry):
                # Third licence, direction-shaped (the reprint-edition
                # direction bound): both provenance licences pass on
                # a reprint edition's record - the DOI is entry-scoped and
                # published-print is the doctrinal basis - yet the year is
                # wrong for the WORK. Basis membership cannot see this; only
                # the direction of the move can.
                bound_reason = _book_year_decline_reason(
                    api_entry, entry.type, api_year, _year_key(bib_year))
                if bound_reason:
                    plan["year_correction_declined"] = (
                        bib_year, api_year,
                        api_entry.get("source_file") or "?",
                        bound_reason)
                else:
                    plan["year_corrected"] = (bib_year, api_year)
            else:
                # COUNTABLE, not silent. A refusal is itself information, and
                # until it is recorded there is no way to tell "corruption
                # prevented" from "a legitimate correction refused". Recorded
                # behind the SAME writability and difference guards as the
                # correction itself, so non-changes ("n.d.", an equal year)
                # never inflate the count. The reason travels with it: the two
                # licences fail for different causes and want different fixes
                # (re-verify the entry vs. re-run under the fixed producer).
                reason = ("unscoped" if not api_entry.get("entry_scoped")
                          else "no-version-of-record-date")
                plan["year_correction_declined"] = (
                    bib_year, api_year, api_entry.get("source_file") or "?",
                    reason)

    # Is this record THIS work's own metadata beyond doubt? Only then may its
    # detail fields convict. A title+year match to a broad dump is not: it can
    # land on a different artifact about the same work - jamieson2014reason
    # matched a Choice review of the book, whose pages and DOI are legitimately
    # its own and contradicted the bib's true ones.
    doi_value = entry.fields.get("doi")
    identity_verified = bool(api_entry.get("entry_scoped")) or (
        bool(doi_value)
        and _field_compare("doi", doi_value, api_entry) == "match")

    surviving: set = set()
    for field_name in list(entry.fields.keys()):
        field_lower = field_name.lower()
        if (field_lower in IDENTITY_FIELDS or field_lower in EXEMPT_FIELDS
                or field_lower in CORRECTABLE_FIELDS or field_lower not in CLEANABLE_FIELDS):
            surviving.add(field_lower)
            continue
        value = entry.fields[field_name]
        state = _field_compare(field_lower, value, api_entry)
        if field_lower in ('journal', 'booktitle'):
            keep = state == 'match' or is_field_verifiable(field_lower, value, index)
            if not keep and state == 'no-evidence':
                plan["venue_stripped_no_evidence"].append(field_name)
        elif field_lower == 'doi':
            # Only a targeted lookup can condemn a DOI: a broad dump's
            # differing DOI is most likely its own artifact's (jamieson).
            # Written as entry_scoped deliberately; note it is EQUIVALENT to
            # identity_verified here, since a contradicting DOI kills that
            # variable's own doi-match disjunct. No test can separate the two -
            # do not go looking for one.
            # Residual, named and accepted: a fabricated DOI on an entry that
            # was never verify_*-checked survives cleaning.
            keep = not (state == 'contradict' and api_entry.get('entry_scoped'))
        elif field_lower in DETAIL_FIELDS:
            # The global bucket (is_field_verifiable) is deliberately NOT
            # consulted for these: an unrelated paper's matching issue number
            # is coincidence, not corroboration, and it used to keep values the
            # entry's own record contradicted.
            keep = not (state == 'contradict' and identity_verified)
        else:
            # Unreachable while the three classes partition CLEANABLE_FIELDS
            # (pinned by test). Default-keep, matching _field_compare's unknown
            # field: a newly cleanable field must not start life being deleted
            # under no policy at all.
            keep = True
        if keep:
            surviving.add(field_lower)
            # Telemetry for detail fields and doi only. A venue kept by the
            # global bucket is bucket-verified rather than unverified, and its
            # absence strips have their own key above.
            if state != 'match' and field_lower not in ('journal', 'booktitle'):
                plan["unverified_fields"].append(field_name)
        else:
            plan["removed_field_names"].append(field_name)
            plan["removed_fields"].append(f"{field_name}={value}")

    plan["type_downgraded"] = _plan_type_downgrade(entry, surviving, api_entry)
    return plan


def _apply_cleaned_marker(entry, plan: dict) -> None:
    """Set a single METADATA_CLEANED tag on keywords, REPLACING any existing
    marker(s) rather than appending - a re-parsed bib re-cleaned
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


def _verified_identifier(entry, api_entry: dict):
    """(kind, normalized_value) the entry's own matched API record confirms.

    Value binding: the ledger attests a VALUE, never just a
    field's presence or kind. 'doi' outranks 'publisher' when both would be
    confirmable. Returns (None, None) when neither identifier is confirmed."""
    doi_val = entry.fields.get("doi", "")
    if doi_val and _field_matches_api("doi", doi_val, api_entry):
        return "doi", normalize_doi(doi_val)
    if entry.type.lower() in ("book", "incollection", "inbook"):
        pub = entry.fields.get("publisher", "")
        if pub and _field_matches_api("publisher", pub, api_entry):
            return "publisher", pub.lower().strip()
    return None, None


def write_cleaning_ledger(bib_path: Path, ledger_entries: dict, breaker_tripped: bool) -> str:
    """Atomically write the per-bib cleaning ledger (tmp + os.replace) - the
    positive-match attestation source the evidence barrier later consumes.
    Overwrites any prior ledger
    for this bib stem so a re-clean reflects only the final pass.

    An entry record's `unverified_fields` and `venue_stripped_no_evidence` are
    owner-facing TELEMETRY, not a control: this file is agent-writable, so
    nothing downstream may gate on them. They exist to measure the accepted
    residual of the strip-rule fix (kept values no record corroborates, and
    venues stripped for want of evidence), and are present only when
    non-empty."""
    bib_path = Path(bib_path)
    ledger_dir = bib_path.parent / "intermediate_files" / "json"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        # 2 since the cleaner strip-rule fix, which added the optional
        # telemetry keys documented above. (1 held through the
        # `cleaning_abstained` addition, recorded 2026-08-18 as deliberate
        # because producer and consumer shipped together.) The barrier accepts
        # {1, 2} and hard-rejects anything else, so a further bump must land in
        # both -- and a v1 ledger still reads, as one with no telemetry.
        "schema_version": 2,
        "bib_file": bib_path.name,
        "breaker_tripped": bool(breaker_tripped),
        "entries": ledger_entries,
    }
    final = ledger_dir / f"cleaning_ledger-{bib_path.stem}.json"
    tmp = final.with_name(final.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(final))
    return str(final)


def _write_ledger_safe(result: dict, bib_path: Path, ledger_entries: dict, breaker_tripped: bool) -> None:
    """Write the cleaning ledger, but never let this break cleaning itself -
    a plumbing gate fails open. On
    failure result['ledger_path'] stays None and the failure surfaces only as
    a warning; the missing ledger then demotes downstream, which is the safe
    direction."""
    try:
        result["ledger_path"] = write_cleaning_ledger(bib_path, ledger_entries, breaker_tripped)
    except OSError as e:
        result["warnings"].append(f"Could not write cleaning ledger: {e}")


def _ledger_entry_for_unmatched(entry) -> dict:
    return {
        "api_matched": False,
        "verified_identifier": None,
        "verified_identifier_value": None,
        "entry_type": entry.type.lower(),
    }


def _count_entries_as_unmatched(bib_path: Path, result: dict) -> dict:
    """B1 truthfulness: when there is no usable index (no dirs, or no parseable
    results), still PARSE the .bib and count every entry as UNMATCHED so the
    result is honest, never a silent no-op that reads like 'nothing to clean'.
    No entry is mutated and no METADATA_CLEANED marker is written on this path.

    This path still parses the .bib successfully, so it is a parse-successful
    exit like any other - the ledger is written here too (every entry
    recorded unmatched with a null identifier)."""
    try:
        bib_data = parse_file(str(bib_path), bib_format='bibtex')
    except Exception as e:
        result["warnings"].append(f"Could not parse {bib_path.name} to count entries: {e}")
        return result
    result["entries_total"] = len(bib_data.entries)
    result["matched_entries"] = 0
    result["unmatched_entries"] = len(bib_data.entries)
    ledger_entries = {
        entry_key: _ledger_entry_for_unmatched(entry)
        for entry_key, entry in bib_data.entries.items()
    }
    _write_ledger_safe(result, bib_path, ledger_entries, False)
    return result


def clean_bibtex(bib_path: Path, json_dirs) -> dict:
    """Clean unverifiable metadata from a BibTeX file.

    Args:
        bib_path: Path to BibTeX file
        json_dirs: a single Path (back-compat) OR a list of Paths holding JSON
            API output. All existing dirs' parseable/salvageable files feed one
            presence-based index (one union: fixes directory shadowing).

    Returns a result dict: skipped_files, salvaged_files, matched_entries,
    unmatched_entries, breaker_tripped, and the planned_*/applied_* metrics.
    """
    result = {
        "success": True,
        "cleaned_entries": {},  # entry_key -> [removed fields]
        "total_fields_removed": 0,
        "years_corrected": 0,
        # Countable residual: corrections refused because the only DOI-matched
        # evidence was a broad dump, with no entry-scoped CrossRef lookup.
        # Each item is [bib_year, api_year, source_file].
        "years_declined": [],
        # True when JSON files were present but NONE of them yielded a usable
        # record - "cleaning ran and found nothing to fix" and "the evidence
        # base collapsed" must not read identically to a machine consumer.
        "index_starved": False,
        "types_downgraded": 0,
        "entries_cleaned": 0,
        "entries_total": 0,
        "matched_entries": 0,
        "unmatched_entries": 0,
        # Option C: abstained entries are a SUBSET of unmatched_entries (the
        # cleaner declined; metrics stay identical to a no-match) - counted
        # separately so the refusal is countable, never silent.
        "abstained_entries": 0,
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
        "warnings": [],
        "ledger_path": None,
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
            + " unusable JSON file(s): " + ", ".join(index.skipped_files)
        )

    if not index.entries:
        result["index_starved"] = True
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
    ledger_entries = {}  # entry_key -> cleaning-ledger record
    for entry_key, entry in bib_data.entries.items():
        # Emit the same-DOI year-disagreement warning BEFORE the match check:
        # a conflicted DOI with no entry-scoped record now abstains, and this
        # warning is the only signal that it did.
        doi_value = entry.fields.get('doi', '')
        conflicts = find_doi_year_conflicts(doi_value, index)
        if conflicts:
            detail = "; ".join(
                f"{year} ({', '.join(files)})"
                for year, files in sorted(conflicts.items()))
            result["warnings"].append(
                f"{entry_key}: indexed sources disagree on year for DOI "
                f"{normalize_doi(doi_value)}: {detail}")

        api_entry = find_api_entry_for_bib_entry(entry, index)
        if isinstance(api_entry, CleaningAbstention):
            # The DOI matched - existence is confirmed - but the year
            # evidence is contradictory, so cleaning declines. The
            # ledger attests existence with an additive refusal reason;
            # cleaner behaviour and metrics are IDENTICAL to no-match (no
            # plan, still counted unmatched). compute_tier's value binding
            # re-checks the DOI, so no extra trust is granted downstream.
            result["unmatched_entries"] += 1
            result["abstained_entries"] += 1
            ledger_entries[entry_key] = {
                "api_matched": True,
                "verified_identifier": "doi",
                "verified_identifier_value": api_entry.normalized_doi,
                "entry_type": entry.type.lower(),
                "cleaning_abstained": api_entry.reason,
            }
            continue
        if api_entry is None:
            result["unmatched_entries"] += 1
            ledger_entries[entry_key] = _ledger_entry_for_unmatched(entry)
            continue
        result["matched_entries"] += 1
        # Planned BEFORE the ledger record is built: the record carries the
        # plan's telemetry keys.
        plan = plan_entry_cleaning(entry, index, api_entry)
        verified_kind, verified_value = _verified_identifier(entry, api_entry)
        record = {
            "api_matched": True,
            "verified_identifier": verified_kind,
            "verified_identifier_value": verified_value,
            "entry_type": entry.type.lower(),
        }
        # Telemetry only, never a control (see write_cleaning_ledger). Omitted
        # when empty so a fully-corroborated bib's ledger reads as it did
        # before the strip-rule fix.
        if plan["unverified_fields"]:
            record["unverified_fields"] = list(plan["unverified_fields"])
        if plan["venue_stripped_no_evidence"]:
            record["venue_stripped_no_evidence"] = list(
                plan["venue_stripped_no_evidence"])
        ledger_entries[entry_key] = record
        plans.append((entry_key, entry, plan))

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
        if plan["year_correction_declined"]:
            result["years_declined"].append(list(plan["year_correction_declined"]))

    # Recorded with the other PLANNED metrics, i.e. BEFORE the breaker check: a
    # refusal is a planning-time fact, and a breaker trip (which writes nothing)
    # must not also erase the record of what the gate declined.
    if result["years_declined"]:
        # Every reason is counted BY NAME, with an explicit bucket for
        # anything unrecognized - deriving one bucket by subtraction let a
        # future reason be silently reported under the wrong explanation.
        reasons = Counter(d[3] for d in result["years_declined"])
        parts = []
        for reason, message in _DECLINE_REASON_MESSAGES.items():
            count = reasons.pop(reason, 0)
            if count:
                parts.append(f"{count} {message}")
        if reasons:
            parts.append(f"{sum(reasons.values())} for other reasons "
                         f"({', '.join(sorted(reasons))})")
        result["warnings"].append(
            f"Declined {len(result['years_declined'])} year correction(s): "
            + "; ".join(parts) + ".")

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
        _write_ledger_safe(result, bib_path, ledger_entries, True)
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

    _write_ledger_safe(result, bib_path, ledger_entries, False)

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

    try:
        result = clean_bibtex(bib_path, json_dirs)
    except Exception as e:
        # The contract with subagent_stop_bib.sh is JSON on stdout. A bare
        # traceback makes the hook's `jq` fail, and the hook treats that as
        # "nothing cleaned" — silence byte-identical to a clean run. Report
        # the failure in-band instead.
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({
            "success": False,
            "errors": [f"metadata_cleaner crashed on {bib_path.name}: "
                       f"{type(e).__name__}: {e}"],
        }, indent=2))
        sys.exit(2)

    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
