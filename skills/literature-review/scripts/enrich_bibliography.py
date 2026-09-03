#!/usr/bin/env python3
"""
Batch orchestrator for bibliography enrichment.

Enriches BibTeX entries with abstracts from multiple sources (S2, OpenAlex, CORE).
Entries without abstracts are flagged as INCOMPLETE.

Usage:
    python enrich_bibliography.py input.bib --output enriched.bib
    python enrich_bibliography.py reviews/project/literature-domain-1.bib

Processing:
    1. For each entry without abstract: Call get_abstract resolution
    2. If abstract found: Add `abstract` and `abstract_source` fields
    3. If not found: Add `INCOMPLETE` and `no-abstract` to keywords

Output:
    Modified BibTeX file with enriched metadata.

Exit Codes:
    0: Success
    1: Input file not found
    2: Configuration error
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv

# Add philosophy-research scripts to path for imports
PHIL_SCRIPTS = Path(__file__).parent.parent.parent / "philosophy-research" / "scripts"
sys.path.insert(0, str(PHIL_SCRIPTS))

from rate_limiter import ExponentialBackoff, get_limiter

# stamp_evidence lives alongside this script (same skills/literature-review/scripts dir).
sys.path.insert(0, str(Path(__file__).parent))
import bib_fields  # noqa: E402 - same directory

_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_identity import first_author_name  # noqa: E402

sys.path.pop(0)

from stamp_evidence import (
    ATTESTED_ABSTRACT_SOURCES,
    abstract_hash,
    normalize_abstract_for_hash,
)


def log_progress(message: str) -> None:
    """Emit progress to stderr."""
    print(f"[enrich_bibliography.py] {message}", file=sys.stderr, flush=True)


# =============================================================================
# BibTeX Parsing
# =============================================================================

def parse_bibtex_entries(content: str) -> list[dict]:
    """
    Parse BibTeX content into entries.

    Returns list of dicts with:
        - raw: Original entry text
        - entry_type: article, book, etc.
        - key: Citation key
        - fields: Dict of field name -> value
    """
    entries = []

    # A UTF-8 BOM survives read_text(encoding='utf-8') as U+FEFF, and
    # str.lstrip() does NOT strip it (Cf, not whitespace) -- so the first
    # chunk below started with the BOM, failed startswith('@'), and the
    # first entry was silently dropped (in a single-entry file, that is a
    # zero-entry parse, i.e. a destroyed bib -- see enrich_bibliography's
    # non-empty-input refusal).
    content = content.lstrip('\ufeff')

    # Split at line-initial entry openers. The old pattern (@\w+\{[^@]+)
    # truncated an entry at ANY interior '@' -- the metadata cleaner's
    # type-demotion marker ('type:@incollection->@misc') cut the entry
    # mid-keywords, the reassembled file failed pybtex validation, and the
    # whole domain lost its enrichment ledger (production review
    # 42b029364b084b6b, domain 2). A value line that itself starts with
    # '@entry{' would still over-split; a line-initial opener is the
    # documented boundary and interior '@' is now inert.
    chunks = re.split(r'(?m)^[ \t]*(?=@\w+\s*\{)', content)
    raw_entries = [c for c in chunks if c.lstrip().startswith('@')]

    for raw in raw_entries:
        # Extract entry type
        type_match = re.match(r'@(\w+)\{', raw)
        if not type_match:
            continue

        entry_type = type_match.group(1).lower()

        # Handle @comment entries specially (no key, no comma)
        if entry_type == 'comment':
            entries.append({
                'raw': raw,
                'entry_type': 'comment',
                'key': 'comment',
                'fields': {},
            })
            continue

        # Extract key for regular entries
        header_match = re.match(r'@\w+\{([^,]+),', raw)
        if not header_match:
            continue

        key = header_match.group(1).strip()

        # Fields are read by the shared depth-counting scanner: braced or
        # quoted (pybtex's Writer emits quoted values on round-trip, and the
        # cleaner round-trips domain bibs -- a brace-only reader once made
        # every cleaned field invisible, production 42b02936), bare, and
        # nested to any depth. A private one-level regex here dropped the
        # same 39 fields over the corpus as the barrier's did (see
        # bib_fields), so an accented first author looked author-less to the
        # abstract lookup. add_field_to_entry stays the write-side owner.
        fields = bib_fields.parse_entry_fields(raw)

        entries.append({
            'raw': raw,
            'entry_type': entry_type,
            'key': key,
            'fields': fields,
        })

    return entries


def has_abstract(entry: dict) -> bool:
    """Check if entry has a non-empty abstract."""
    abstract = entry['fields'].get('abstract', '')
    return bool(abstract and len(abstract.strip()) > 10)


def is_incomplete(entry: dict) -> bool:
    """Check if entry is marked INCOMPLETE."""
    keywords = entry['fields'].get('keywords', '')
    return 'INCOMPLETE' in keywords


def get_doi(entry: dict) -> Optional[str]:
    """Extract DOI from entry."""
    doi = entry['fields'].get('doi', '')
    if doi:
        # Clean up DOI
        doi = doi.strip()
        if doi.startswith('https://doi.org/'):
            doi = doi[16:]
        elif doi.startswith('http://doi.org/'):
            doi = doi[15:]
        return doi
    return None


def _is_one_brace_group(name: str) -> bool:
    """True when the first `{` closes only at the final character, i.e. the
    whole name is one outer brace group (nested groups allowed). Escaped
    braces (`\\{`) are counted like any other -- unreachable in author
    fields, documented limitation."""
    if len(name) < 2 or name[0] != '{' or name[-1] != '}':
        return False
    depth = 0
    for i, ch in enumerate(name):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and i != len(name) - 1:
                return False
    return depth == 0


def get_author_last_name(entry: dict) -> Optional[str]:
    """First author's surname as search text for abstract matching.

    Brace-aware on the list split (bib_identity). A first name that is one
    outer brace group is returned whole, commas inside included: pybtex
    treats such a group as ONE surname regardless of its punctuation
    (`{Smith, Jones and Lee Institute}`), and this is how
    `generate_bibliography` renders it. Otherwise the token rule stands:
    text before the first comma, else the last whitespace token.
    Case-protection braces around plain letters are removed from the result
    because it is used as search text; LaTeX escape groups are kept."""
    first = first_author_name(entry['fields'].get('author', ''))
    if not first:
        return None
    if _is_one_brace_group(first):
        surname = first[1:-1]
    elif ',' in first:
        surname = first.split(',')[0]
    else:
        parts = first.split()
        surname = parts[-1] if parts else ''
    # Remove case-protection braces around plain letters ({B}rown -> Brown),
    # never a group holding a LaTeX escape ({\"u}, {\aa}) and never the
    # argument of a one-letter accent command (\c{c}) -- those stay as the
    # bib wrote them, exactly as before this change.
    surname = re.sub(r"(?<!\\[A-Za-z])(?<![\\'\"^`~=.])\{([A-Za-z]+)\}", r"\1", surname)
    surname = surname.strip()
    return surname or None


def get_year(entry: dict) -> Optional[int]:
    """Extract year from entry."""
    year = entry['fields'].get('year', '')
    try:
        return int(year)
    except (ValueError, TypeError):
        return None


# =============================================================================
# Abstract Resolution
# =============================================================================

def resolve_abstract_for_entry(
    entry: dict,
    s2_api_key: Optional[str],
    openalex_email: Optional[str],
    core_api_key: Optional[str],
    debug: bool = False
) -> tuple[Optional[str], Optional[str]]:
    """
    Try to resolve abstract for a BibTeX entry.

    Returns:
        Tuple of (abstract, source) or (None, None)
    """
    # Import here to avoid circular imports
    import get_abstract

    doi = get_doi(entry)
    title = entry['fields'].get('title', '')
    author = get_author_last_name(entry)
    year = get_year(entry)

    # Skip if no identifiers
    if not doi and not title:
        return None, None

    return get_abstract.resolve_abstract(
        doi=doi,
        title=title or None,
        author=author or None,
        year=year,
        s2_api_key=s2_api_key,
        openalex_email=openalex_email,
        core_api_key=core_api_key,
        debug=debug
    )


def resolve_ndpr_abstract(
    title: str,
    author: Optional[str] = None,
    debug: bool = False
) -> tuple[Optional[str], Optional[str]]:
    """
    Try to find and extract a book summary from NDPR.

    Returns (summary_text, "ndpr") on a match, (None, None) when NDPR has
    no matching review. Transport failures PROPAGATE (search_ndpr and
    fetch_ndpr raise RuntimeError on network errors): swallowing them here
    made an outage indistinguishable from a genuine no-match, so NDPR
    demotion counts were unattributable in any run report. Each caller
    picks its own failure direction -- the enrichment pass logs and moves
    on; the corroboration probe reads it as a transport non-answer; and
    the barrier heal path (`evidence_barrier._heal_abstract`, which calls
    this directly for a claimed-`ndpr` ledger source) already wraps the
    call in its own try/except and reads it as a failed heal.
    """
    import search_ndpr
    import fetch_ndpr

    match = search_ndpr.search_ndpr(title, author, debug=debug)
    if not match:
        if debug:
            log_progress(f"  NDPR: no sitemap match for '{title}'")
        return None, None

    result = fetch_ndpr.fetch_ndpr_review(match["url"], debug=debug)
    summary = result.get("summary_text", "")

    if summary and len(summary) > 50:
        return summary, "ndpr"

    return None, None


# =============================================================================
# Live corroboration of an entry's abstract
# =============================================================================

# Corroboration outcomes. Only CORROBORATED is evidence; the other three
# are distinct KINDS of non-evidence, and keeping them apart is the point:
# MISMATCH means "fetched and differed" (the forgery signal the barrier's
# corroboration gate measures) and must never absorb "there was nothing to
# compare".
CORROBORATED = "corroborated"
MISMATCH = "mismatch"
SOURCE_EMPTY = "source_empty"
TRANSPORT_FAILED = "transport_failed"

# Probe ORDER for the API sources -- local knowledge (cheapest and most
# reliable first), so it stays here. WHICH source names are recognized at
# all is not local: that is stamp_evidence.ATTESTED_ABSTRACT_SOURCES, and
# corroborate_abstract tests membership against the canonical set rather
# than re-deriving it. Kept honest by
# test_corroboration_covers_every_attested_source: a fifth attested source
# added there without teaching corroboration to probe it would otherwise be
# read as UNKNOWN, probed against the other three, and could report a
# MISMATCH off a source the entry never claimed -- a false forgery signal
# in the metric the barrier's corroboration gate enforces on.
_API_SOURCES = ("s2", "openalex", "core")


def corroborate_abstract(
    fields: dict,
    s2_api_key: Optional[str],
    openalex_email: Optional[str],
    core_api_key: Optional[str],
    debug: bool = False,
) -> tuple[str, Optional[str]]:
    """Does a live fetch still return THIS entry's abstract text?

    Returns (outcome, matched_source): (CORROBORATED, source) as soon as
    some source serves text whose stamp_evidence.abstract_hash equals the
    hash of the entry's own abstract; otherwise (MISMATCH | SOURCE_EMPTY |
    TRANSPORT_FAILED, None), preferring the most informative thing seen --
    a mismatch outranks a transport failure, which outranks "no source has
    an abstract".

    The claimed source (`abstract_source`) is probed first, then the rest
    of s2/openalex/core; `ndpr` is probed only when it is the claimed
    source, since NDPR resolution is a title search over review essays and
    asking it about an arbitrary paper invites a wrong-work match. Each
    source gets one retry on a transport failure, on top of the probe's
    own backoff, so one flaky connection cannot read as evidence.

    Identity comes ONLY from the entry's own fields (doi/title/author/
    year): there is no caller-supplied URL or identifier surface, so a
    forged bib cannot point corroboration at a document of its choosing.
    """
    import get_abstract  # local import: mirrors resolve_abstract_for_entry

    existing = fields.get('abstract') or ''
    if not normalize_abstract_for_hash(existing):
        # Nothing to corroborate: absent, or normalizing to nothing at all
        # (whitespace and backslashes only, which the hash folds away -- any
        # fetched text that also normalized to nothing would "match", so the
        # comparison would be vacuous rather than evidence). Fail closed,
        # but NOT as MISMATCH: that bucket has to mean "fetched and
        # differed" or the corroboration rate it feeds means nothing.
        if debug:
            log_progress("  corroboration: entry carries no comparable abstract text")
        return SOURCE_EMPTY, None

    target = abstract_hash(existing)

    # get_doi/get_author_last_name/get_year read entry['fields'] and
    # nothing else, so a bare view over the fields dict reuses them
    # instead of duplicating the extraction rules.
    view = {'fields': fields}
    doi = get_doi(view)
    title = (fields.get('title') or '').strip()
    author = get_author_last_name(view)
    year = get_year(view)

    claimed = (fields.get('abstract_source') or '').strip().lower()
    candidates = [s for s in _API_SOURCES if s != claimed]
    if claimed in ATTESTED_ABSTRACT_SOURCES:
        candidates.insert(0, claimed)

    ctx = get_abstract.build_source_context(s2_api_key)
    saw_mismatch = False
    saw_transport = False

    for source in candidates:
        for _attempt in range(2):  # one retry on transport, then give up
            status, fetched = _probe_candidate(
                source, get_abstract, ctx,
                doi=doi, title=title, author=author, year=year,
                s2_api_key=s2_api_key, openalex_email=openalex_email,
                core_api_key=core_api_key, debug=debug,
            )
            if status != get_abstract.PROBE_TRANSPORT:
                break
        if status == get_abstract.PROBE_OK:
            if abstract_hash(fetched or '') == target:
                return CORROBORATED, source
            saw_mismatch = True
            if debug:
                log_progress(f"  corroboration: {source} served different text")
        elif status == get_abstract.PROBE_TRANSPORT:
            saw_transport = True

    if saw_mismatch:
        return MISMATCH, None
    if saw_transport:
        return TRANSPORT_FAILED, None
    return SOURCE_EMPTY, None


def _probe_candidate(
    source: str,
    ga,
    ctx: dict,
    *,
    doi: Optional[str],
    title: str,
    author: Optional[str],
    year: Optional[int],
    s2_api_key: Optional[str],
    openalex_email: Optional[str],
    core_api_key: Optional[str],
    debug: bool,
) -> tuple[str, Optional[str]]:
    """(status, text) for one candidate source; never raises.

    PROBE_EMPTY without any request when the source has no usable
    identifier for this identity -- and, for CORE, when no API key is
    configured: resolve_abstract skips keyless CORE rather than burn
    futile unauthenticated attempts, and a corroboration
    sweep runs over a whole bibliography, so it must not reintroduce them.
    Consequence to know: a claimed-`core` abstract cannot be corroborated
    in a keyless workspace, which is fail-CLOSED (no attestation), not
    fail-open.

    Any exception escaping a probe is a non-answer, i.e. PROBE_TRANSPORT:
    corroboration runs inside the evidence barrier, where a crash would
    take down a whole bib's stamping run.
    """
    try:
        if source == 's2':
            # No s2_id surface: a bib entry carries no Semantic Scholar id.
            if not doi:
                return ga.PROBE_EMPTY, None
            return ga.probe_s2(
                api_key=s2_api_key, limiter=ctx['s2_limiter'],
                backoff=ctx['s2_backoff'], debug=debug, doi=doi)
        if source == 'openalex':
            if not doi:
                return ga.PROBE_EMPTY, None
            return ga.probe_openalex(
                doi=doi, email=openalex_email, limiter=ctx['openalex_limiter'],
                backoff=ctx['other_backoff'], debug=debug)
        if source == 'core':
            if not core_api_key or not (doi or title):
                return ga.PROBE_EMPTY, None
            return ga.probe_core(
                doi=doi, title=title or None, author=author, year=year,
                api_key=core_api_key, limiter=ctx['core_limiter'],
                backoff=ctx['other_backoff'], debug=debug)
        if source == 'ndpr':
            if not title:
                return ga.PROBE_EMPTY, None
            # resolve_ndpr_abstract propagates transport errors
            # (RuntimeError from the sitemap or review fetch), so an NDPR
            # outage escapes to this function's own except and reads as
            # PROBE_TRANSPORT -- distinguishable from "no such review",
            # which stays PROBE_EMPTY.
            text, _ = resolve_ndpr_abstract(title=title, author=author, debug=debug)
            return (ga.PROBE_OK, text) if text else (ga.PROBE_EMPTY, None)
    except Exception as e:
        log_progress(f"  corroboration probe {source} failed: {e}")
        return ga.PROBE_TRANSPORT, None
    return ga.PROBE_EMPTY, None


# =============================================================================
# BibTeX Modification
# =============================================================================

def add_field_to_entry(entry_text: str, field_name: str, field_value: str) -> str:
    """Add or update a field in a BibTeX entry.

    Values are inserted as-is inside braces. BibTeX brace-delimited values
    don't need escaping — braces inside the value are only problematic if
    unbalanced, which API-sourced content won't have. Escaping would corrupt
    LaTeX markup (e.g. \\textit{...}) in abstracts.
    """
    # An existing field is located by the shared scanner (bib_fields): braced
    # or quoted (pybtex's writer emits quoted values on round-trip), nested to
    # any depth, in any position -- including `@article{k,field={x},` with no
    # whitespace before the name, which the old `(\s+)<field>\s*=` locator
    # missed, so the add path inserted a SECOND field pybtex rejects. A
    # two-level-nested existing abstract once fell through the same way,
    # leaving a stale and a new `abstract =` side by side. Every occurrence
    # is replaced (not just the first) -- pinned by
    # tests/test_enrich_bibliography.py::test_add_field_replace_all_occurrences_pinned,
    # which documents that callers rely on entry_text being a SINGLE entry.
    # Rewritten last-to-first so earlier spans stay valid; string slicing,
    # never a regex template, because abstracts carry LaTeX backslashes.
    existing = [f for f in bib_fields.iter_fields(entry_text)
                if f.name.lower() == field_name.lower()]
    if existing:
        for f in reversed(existing):
            entry_text = (entry_text[:f.name_start]
                          + f'{field_name} = {{{field_value}}}'
                          + entry_text[f.value_end:])
        return entry_text
    else:
        # Add new field immediately after the entry's opening line (@type{key,).
        # The opening line is never inside a field value, so a multi-line value
        # (e.g. a wrapped abstract) can no longer swallow the next insertion.
        lines = entry_text.split('\n')
        opening_idx = None
        for i, line in enumerate(lines):
            if re.match(r'\s*@\w+\s*\{', line):
                opening_idx = i
                break

        if opening_idx is None:
            # No recognizable opening line: fall back to before the closing brace.
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == '}':
                    lines.insert(i, f'  {field_name} = {{{field_value}}},')
                    break
            return '\n'.join(lines)

        # Derive indentation from the first existing field line, if any.
        indent = '  '
        for j in range(opening_idx + 1, len(lines)):
            body = lines[j].strip()
            if body and not body.startswith('}'):
                m = re.match(r'^(\s*)', lines[j])
                if m and m.group(1):
                    indent = m.group(1)
                break

        # The opening line should end with a comma ("@type{key,"); ensure it.
        stripped = lines[opening_idx].rstrip()
        if not stripped.endswith(','):
            lines[opening_idx] = stripped + ','
        else:
            lines[opening_idx] = stripped

        lines.insert(opening_idx + 1, f'{indent}{field_name} = {{{field_value}}},')
        return '\n'.join(lines)


def _keywords_field(entry_text: str):
    """The keywords field's span, located by the shared scanner -- braced or
    quoted, nested to any depth -- or None. A private regex here once had a
    braced alternative of `[^{}]*` (no nesting), and when it missed,
    add_keyword_to_entry fell through to add_field_to_entry, which REPLACES a
    field wholesale: `{on {K}alon, High}` became `{INCOMPLETE}`, every topic
    tag and the importance level gone, in an entry pybtex accepts -- silent
    data loss no gate could catch. Both editors, and the NDPR pass's
    keywords checks, now read the same span the parsers read."""
    return next((f for f in bib_fields.iter_fields(entry_text)
                 if f.name.lower() == "keywords"), None)


def _replace_keywords_value(entry_text: str, field, new_value: str) -> str:
    return (entry_text[:field.value_start] + "{" + new_value + "}"
            + entry_text[field.value_end:])


def remove_keyword_from_entry(entry_text: str, keyword: str) -> str:
    """Remove a keyword from the keywords field, editing the value in place;
    the whole field goes when its last token does."""
    field = _keywords_field(entry_text)
    if field is None:
        return entry_text
    keywords = [k.strip() for k in field.value.split(',')]
    keywords = [k for k in keywords if k and k != keyword]
    if keywords:
        return _replace_keywords_value(entry_text, field, ', '.join(keywords))
    return bib_fields.remove_field(entry_text, field)


def _is_ndpr_candidate(entry_text: str) -> bool:
    """Keywords carry INCOMPLETE (any case, as the regex this replaced had
    re.IGNORECASE) and a High or Medium importance token. Both delimiter
    forms, any nesting: the value comes from the shared scanner. One
    deliberate change from the regex: a brace group before INCOMPLETE
    (`{on {K}alon, High, INCOMPLETE}`) used to hide it, so that book was
    skipped; it is a candidate now."""
    field = _keywords_field(entry_text)
    if field is None:
        return False
    tokens = [t.strip() for t in field.value.split(',')]
    return ('incomplete' in field.value.casefold()
            and any(t in ('High', 'Medium') for t in tokens))


def add_keyword_to_entry(entry_text: str, keyword: str) -> str:
    """Add a keyword to the keywords field, appending inside the existing
    value and preserving every other token; delegates to add_field_to_entry
    (which replaces a field wholesale) only when no keywords field exists."""
    field = _keywords_field(entry_text)
    if field is None:
        return add_field_to_entry(entry_text, 'keywords', keyword)
    if keyword in field.value:
        return entry_text
    new_value = f'{field.value}, {keyword}' if field.value.strip() else keyword
    return _replace_keywords_value(entry_text, field, new_value)


def enrich_entry(
    entry: dict,
    s2_api_key: Optional[str],
    openalex_email: Optional[str],
    core_api_key: Optional[str],
    debug: bool = False,
    ledger_writes: Optional[dict] = None
) -> tuple[str, bool, Optional[str]]:
    """
    Enrich a single BibTeX entry with abstract if missing.

    Returns:
        Tuple of (enriched_entry_text, was_enriched, abstract_source)

    If `ledger_writes` is given, records {key: {abstract_source,
    abstract_sha256}} for this entry when an abstract is written -- the
    enrichment-ledger attestation the evidence barrier later consumes.
    """
    entry_text = entry['raw']

    # Skip if already has abstract
    if has_abstract(entry):
        return entry_text, False, None

    # Skip comments
    if entry['entry_type'] == 'comment':
        return entry_text, False, None

    log_progress(f"Resolving abstract for: {entry['key']}")

    abstract, source = resolve_abstract_for_entry(
        entry, s2_api_key, openalex_email, core_api_key, debug
    )

    if abstract:
        # Add abstract and source fields
        entry_text = add_field_to_entry(entry_text, 'abstract', abstract)
        entry_text = add_field_to_entry(entry_text, 'abstract_source', source)
        if ledger_writes is not None:
            ledger_writes[entry['key']] = {
                "abstract_source": source,
                "abstract_sha256": abstract_hash(abstract),
            }
        log_progress(f"  Added abstract from {source} ({len(abstract)} chars)")
        return entry_text, True, source
    else:
        # Mark as INCOMPLETE
        entry_text = add_keyword_to_entry(entry_text, 'INCOMPLETE')
        entry_text = add_keyword_to_entry(entry_text, 'no-abstract')
        log_progress(f"  No abstract found, marked INCOMPLETE")
        return entry_text, False, None


def attest_prefilled_entry(
    entry: dict,
    s2_api_key: Optional[str],
    openalex_email: Optional[str],
    core_api_key: Optional[str],
    debug: bool = False,
    ledger_writes: Optional[dict] = None,
) -> tuple[str, bool]:
    """Attest an entry whose abstract was written by the researcher.

    The enrichment skip path made such abstracts structurally
    unattestable (2026-07-25 A/B root cause 1: mcallister2011patterns).
    Fetches the abstract from the APIs; if the fetched text hash-matches
    the pre-filled text (whitespace/backslash-insensitive), records the
    ledger attestation and normalizes abstract_source to the canonical
    source. Any miss is a no-op: fail-closed, unattested stays unattested.

    Returns (entry_text, attested).
    """
    entry_text = entry['raw']
    existing = entry['fields'].get('abstract', '')
    log_progress(f"Attesting pre-filled abstract for: {entry['key']}")
    try:
        fetched, source = resolve_abstract_for_entry(
            entry, s2_api_key, openalex_email, core_api_key, debug)
    except Exception as e:
        log_progress(f"  Attestation fetch failed ({e}) -- left unattested")
        return entry_text, False
    if not fetched or not source or (
            abstract_hash(fetched) != abstract_hash(existing)):
        log_progress("  Pre-filled abstract matches no API text -- left unattested")
        return entry_text, False
    entry_text = add_field_to_entry(entry_text, 'abstract_source', source)
    if ledger_writes is not None:
        ledger_writes[entry['key']] = {
            "abstract_source": source,
            "abstract_sha256": abstract_hash(existing),
        }
    log_progress(f"  Pre-filled abstract attested via {source}")
    return entry_text, True


# =============================================================================
# Main Processing
# =============================================================================

def _ascii_safe(s: str) -> str:
    """backslashreplace fold for diagnostics: pybtex messages, and citation
    keys themselves, can carry accented source text, and this output may be
    piped through Windows cp1252 (CLAUDE.md non-ASCII output rule)."""
    return s.encode('ascii', 'backslashreplace').decode('ascii')


def _name_invalid_entries(raw_entries: list) -> list:
    """(citation_key, 'ExceptionClass: message') for every entry text that
    fails a standalone pybtex parse. Diagnostic-only: called on the
    validation-failure path so the operator can see WHICH record broke
    the file, not just pybtex's whole-file line number (the production
    ledger drop was undiagnosable from 'premature end of file').
    Non-entry chunks (@comment/@string/@preamble) are skipped -- parsed
    standalone they would be falsely named."""
    from pybtex.database import parse_string
    named = []
    for raw in raw_entries:
        m = re.match(r'@(\w+)\{([^,\s}]*)', raw.lstrip())
        if not m or m.group(1).lower() in ('comment', 'string', 'preamble'):
            continue
        key = m.group(2).strip()
        try:
            parse_string(raw, bib_format='bibtex')
        except Exception as e:
            # _ascii_safe: see its docstring for why (non-ASCII output rule).
            diag = _ascii_safe(f"{type(e).__name__}: {e}")
            named.append((key, diag))
    return named


def enrich_bibliography(
    input_path: Path,
    output_path: Optional[Path],
    s2_api_key: Optional[str],
    openalex_email: Optional[str],
    core_api_key: Optional[str],
    debug: bool = False
) -> dict:
    """
    Enrich all entries in a BibTeX file.

    Returns:
        Stats dict with keys: total, already_had_abstract, enriched,
        marked_incomplete, incomplete_keys, skipped, sources. If pybtex
        validation fails, the original file is left unchanged and
        stats['validation_failed'] is set to True. If a non-empty input
        parses to ZERO entries, the run returns early with
        stats['parse_failed'] = True, having written neither the bib nor
        the ledger. Both failure markers are advisory in the same way:
        main() reports and exits 0 either way, so a caller that cares has
        to read the stats (or the stderr warning).
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    content = input_path.read_text(encoding='utf-8')
    entries = parse_bibtex_entries(content)

    log_progress(f"Processing {len(entries)} entries from {input_path.name}")

    stats = {
        'total': len(entries),
        'already_had_abstract': 0,
        'enriched': 0,
        'marked_incomplete': 0,
        'incomplete_keys': [],
        'skipped': 0,
        'prefilled_attested': 0,
        'prefilled_unverified': 0,
        'sources': {'s2': 0, 'openalex': 0, 'core': 0, 'ndpr': 0}
    }

    # Drop-direction backstop, BEFORE any work. A zero-entry parse of a
    # NON-EMPTY file means the splitter recognized nothing -- and the joined
    # output would then be the empty string, which pybtex validates happily,
    # so os.replace would install an empty bib over the original and destroy
    # it. Refuse loudly and leave the file alone (an actually-empty input is
    # a legitimate no-op and keeps the normal write path).
    if not entries and content.strip():
        log_progress("WARNING: parsed zero entries from non-empty input -- "
                     "refusing to overwrite " + input_path.name)
        stats['parse_failed'] = True
        return stats

    enriched_entries = []
    # citation key -> {abstract_source, abstract_sha256} for abstracts this
    # run wrote; merged with any
    # prior ledger by _update_enrichment_ledger at the end of this function.
    ledger_writes: dict = {}
    prior_ledger = _load_prior_ledger(output_path or input_path)

    for entry in entries:
        # Skip comments
        if entry['entry_type'] == 'comment':
            enriched_entries.append(entry['raw'])
            stats['skipped'] += 1
            continue

        # Entry already has an abstract. If the prior ledger already
        # attests exactly this text and source, it needs no re-check --
        # re-running enrichment must not re-fetch attested entries.
        # Otherwise (researcher-transcribed, or text drifted) try to
        # attest it in place instead of skipping -- a correct pre-filled
        # abstract was otherwise structurally unattestable (A/B root
        # cause 1). Fail-closed: on any miss the entry is untouched.
        if has_abstract(entry):
            prior = prior_ledger.get(entry['key']) or {}
            cur_source = (entry['fields'].get('abstract_source') or '').strip().lower()
            if (prior.get('abstract_sha256') == abstract_hash(entry['fields']['abstract'])
                    and cur_source
                    and cur_source == (prior.get('abstract_source') or '').strip().lower()):
                enriched_entries.append(entry['raw'])
                stats['already_had_abstract'] += 1
                stats['prefilled_attested'] += 1
                continue
            new_text, attested = attest_prefilled_entry(
                entry, s2_api_key, openalex_email, core_api_key, debug,
                ledger_writes=ledger_writes)
            enriched_entries.append(new_text)
            stats['already_had_abstract'] += 1
            stats['prefilled_attested' if attested
                  else 'prefilled_unverified'] += 1
            continue

        # Try to enrich
        enriched_text, was_enriched, source = enrich_entry(
            entry, s2_api_key, openalex_email, core_api_key, debug,
            ledger_writes=ledger_writes
        )
        enriched_entries.append(enriched_text)

        if was_enriched and source:
            stats['enriched'] += 1
            stats['sources'][source] = stats['sources'].get(source, 0) + 1
        else:
            stats['marked_incomplete'] += 1
            stats['incomplete_keys'].append(entry['key'])

    # --- NDPR enrichment pass for books without abstracts ---
    # Only attempt NDPR for @book entries that:
    # 1. Still lack an abstract after the main enrichment pass
    # 2. Have High or Medium importance (as noted in keywords)
    book_entries_without_abstract = [
        (i, e) for i, e in enumerate(entries)
        if e['entry_type'] == 'book'
        and not has_abstract(e)
        and _is_ndpr_candidate(enriched_entries[i])
    ]

    if book_entries_without_abstract:
        log_progress(f"Trying NDPR for {len(book_entries_without_abstract)} book(s) without abstracts...")
        for idx, entry in book_entries_without_abstract:
            title = entry['fields'].get('title', '')
            author = get_author_last_name(entry)
            try:
                abstract, source = resolve_ndpr_abstract(title, author, debug)
            except Exception as e:
                # Best-effort enrichment: an NDPR outage must not kill the
                # pass. The corroboration probe deliberately has no such
                # blanket -- there the same exception must read as a
                # transport non-answer, not a no-match.
                log_progress(f"  NDPR error for '{title}': {e}")
                continue
            if abstract:
                enriched_entries[idx] = add_field_to_entry(enriched_entries[idx], 'abstract', abstract)
                enriched_entries[idx] = add_field_to_entry(enriched_entries[idx], 'abstract_source', 'ndpr')
                enriched_entries[idx] = remove_keyword_from_entry(enriched_entries[idx], 'INCOMPLETE')
                enriched_entries[idx] = remove_keyword_from_entry(enriched_entries[idx], 'no-abstract')
                ledger_writes[entry['key']] = {
                    "abstract_source": "ndpr",
                    "abstract_sha256": abstract_hash(abstract),
                }
                # Stats: enriched/marked_incomplete are cumulative across all passes
                stats['enriched'] += 1
                stats['marked_incomplete'] -= 1
                if entry['key'] in stats['incomplete_keys']:
                    stats['incomplete_keys'].remove(entry['key'])
                stats['sources']['ndpr'] += 1
                log_progress(f"  Added NDPR abstract for: {entry['key']}")

    # Write output atomically
    if output_path is None:
        output_path = input_path  # Overwrite in place

    output_content = '\n\n'.join(entry.strip() for entry in enriched_entries)
    tmp_path = output_path.with_suffix('.bib.tmp')
    tmp_path.write_text(output_content + '\n', encoding='utf-8')

    # Validate the enriched output (defense-in-depth: catch errors at the source)
    validation_ok = True
    try:
        from pybtex.database import parse_file
    except ImportError:
        pass  # pybtex not available, skip validation
    else:
        try:
            parse_file(str(tmp_path), bib_format='bibtex')
        except Exception as e:
            validation_ok = False
            log_progress("WARNING: Enriched file has BibTeX syntax errors: "
                         + _ascii_safe(str(e)))
            offenders = _name_invalid_entries(enriched_entries)
            for key, diag in offenders:
                # The KEY needs the same backslashreplace treatment the diag
                # already got: non-ASCII citation keys exist in the corpus,
                # and this line may be piped through Windows cp1252.
                log_progress(f"WARNING:   offending entry "
                             f"'{_ascii_safe(key)}': {diag}")
            if not offenders:
                # Say so explicitly rather than leaving the operator to read
                # silence: every entry parses standalone, so the fault is
                # file-level (duplicate keys, or a join artifact between
                # entries), not attributable to any one record.
                log_progress("WARNING:   no single entry reproduces the "
                             "failure -- it is file-level (e.g. duplicate "
                             "keys, or a join artifact between entries)")
            # Set BOTH failure markers here so they cannot drift apart if
            # the later else-branch is ever refactored.
            stats['validation_failed'] = True
            stats['validation_failed_keys'] = [k for k, _ in offenders]

    if validation_ok:
        try:
            os.replace(str(tmp_path), str(output_path))
        except OSError:
            # Clean up temp file on failure
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
        log_progress(f"Wrote enriched bibliography to {output_path.name}")
    else:
        stats['validation_failed'] = True
        try:
            tmp_path.unlink()
        except OSError:
            pass
        log_progress("WARNING: Validation failed -- original file unchanged")

    # Enrichment ledger: written on every parse-successful run, symmetric
    # with the cleaning ledger (metadata_cleaner.py) -- an empty entries
    # dict is valid (obscure domains legitimately enrich nothing; a missing
    # ledger would spuriously demote everything under the evidence barrier).
    # Skipped only when the bib write itself was aborted by validation.
    if not stats.get('validation_failed'):
        current_keys = {e['key'] for e in entries if e['entry_type'] != 'comment'}
        try:
            _update_enrichment_ledger(output_path, ledger_writes, current_keys)
        except OSError as e:
            stats.setdefault('warnings', []).append(f"Could not write enrichment ledger: {e}")

    log_progress(f"Stats: {stats['enriched']} enriched, {stats['marked_incomplete']} incomplete, {stats['already_had_abstract']} already had abstract")

    return stats


def _load_prior_ledger(output_path: Path) -> dict:
    """The existing enrichment ledger's entries dict ({} if absent or
    malformed). Used to skip API calls for entries a prior run already
    attested -- re-running enrichment must stay cheap.

    Non-dict values are dropped, not passed through: a malformed record
    must degrade to "not attested" (an API re-check), never crash the
    run. NOTE the trust model: this file is agent-writable and is the
    authority for the zero-fetch fast path HERE. The evidence barrier no
    longer shares that trust for the abstract tier -- a ledger record only
    makes an entry a candidate there, and `corroborate_abstract`
    has to see a live fetch serve the same text before the tier is granted.
    """
    final = (output_path.parent / "intermediate_files" / "json"
             / f"enrichment_ledger-{output_path.stem}.json")
    if not final.exists():
        return {}
    try:
        payload = json.loads(final.read_text(encoding='utf-8'))
        entries = payload.get('entries', {}) if isinstance(payload, dict) else {}
        if not isinstance(entries, dict):
            return {}
        return {k: v for k, v in entries.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        return {}


def _update_enrichment_ledger(output_path: Path, ledger_writes: dict, current_keys: set) -> None:
    """Atomically merge-write the enrichment ledger (tmp + os.replace) --
    the per-entry abstract-source/hash attestation the evidence barrier
    later consumes. Existing
    entries for keys still present in the bib are kept; keys no longer
    present are pruned; new writes from this run win per key."""
    ledger_dir = output_path.parent / "intermediate_files" / "json"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    final = ledger_dir / f"enrichment_ledger-{output_path.stem}.json"

    old_entries: dict = {}
    if final.exists():
        try:
            payload = json.loads(final.read_text(encoding='utf-8'))
            candidate = payload.get('entries', {}) if isinstance(payload, dict) else {}
            old_entries = candidate if isinstance(candidate, dict) else {}
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
            old_entries = {}

    entries = {k: v for k, v in old_entries.items() if k in current_keys}
    entries.update(ledger_writes)

    payload = {
        "schema_version": 1,
        "bib_file": output_path.name,
        "entries": entries,
    }
    tmp = final.with_name(final.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    os.replace(str(tmp), str(final))


def summary_lines(stats: dict) -> list:
    """The lines main() prints after 'Enrichment complete:'. The researcher
    prose reads these instead of grepping the bib, so the INCOMPLETE keys
    are named here whenever any entry was marked."""
    lines = [
        f"  Total entries: {stats['total']}",
        f"  Already had abstract: {stats['already_had_abstract']}",
        f"  Enriched: {stats['enriched']}",
        f"  Marked INCOMPLETE: {stats['marked_incomplete']}",
    ]
    if stats.get('incomplete_keys'):
        lines.append(f"  INCOMPLETE entries: {', '.join(stats['incomplete_keys'])}")
    if stats['enriched'] > 0:
        lines.append(f"  Sources: {stats['sources']}")
    return lines


def main():
    load_dotenv(find_dotenv(usecwd=True), override=True)  # must run before argparse defaults read os.environ
    parser = argparse.ArgumentParser(
        description="Enrich BibTeX bibliography with abstracts"
    )
    parser.add_argument(
        "input",
        help="Input BibTeX file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: overwrite input)"
    )
    parser.add_argument(
        "--s2-api-key",
        default=os.environ.get("S2_API_KEY", ""),
        help="Semantic Scholar API key"
    )
    parser.add_argument(
        "--openalex-email",
        default=os.environ.get("OPENALEX_EMAIL", ""),
        help="Email for OpenAlex polite pool"
    )
    parser.add_argument(
        "--core-api-key",
        default=os.environ.get("CORE_API_KEY", ""),
        help="CORE API key (optional)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information"
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None

    try:
        stats = enrich_bibliography(
            input_path,
            output_path,
            args.s2_api_key,
            args.openalex_email,
            args.core_api_key,
            args.debug
        )

        # Print summary
        print(f"\nEnrichment complete:")
        for line in summary_lines(stats):
            print(line)

        sys.exit(0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
