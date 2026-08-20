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
from stamp_evidence import abstract_hash


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

        # Extract fields
        fields = {}

        # Match field = {value} OR field = "value" -- pybtex's Writer emits
        # quoted values on round-trip (CLAUDE.md), and the cleaner
        # round-trips domain bibs, so a brace-only pattern made every
        # cleaned field invisible (production 42b02936: the whole domain
        # "had no identifiers" and enriched nothing). [^"]* is safe against
        # the pinned pybtex Writer: it brace-wraps any value containing a
        # double quote (verified empirically), and quotes numerics, so
        # neither truncation nor bare values arise from round-tripped
        # files. Braced alternative keeps its one-level nesting tolerance;
        # add_field_to_entry's depth-counting editor is the write-side
        # owner and is unchanged.
        field_pattern = r'(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|"([^"]*)")'
        for match in re.finditer(field_pattern, raw, re.DOTALL):
            field_name = match.group(1).lower()
            field_value = (match.group(2) if match.group(2) is not None
                           else match.group(3)).strip()
            fields[field_name] = field_value

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


def get_author_last_name(entry: dict) -> Optional[str]:
    """Extract first author's last name from entry."""
    author = entry['fields'].get('author', '')
    if not author:
        return None
    # Handle "Last, First" or "First Last" formats
    # BibTeX typically uses "Last, First and Last2, First2"
    first_author = author.split(' and ')[0].strip()
    if ',' in first_author:
        return first_author.split(',')[0].strip()
    else:
        parts = first_author.split()
        return parts[-1] if parts else None


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

    Returns:
        Tuple of (summary_text, "ndpr") or (None, None)
    """
    import search_ndpr
    import fetch_ndpr

    try:
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

    except Exception as e:
        log_progress(f"  NDPR error for '{title}': {e}")
        return None, None


# =============================================================================
# BibTeX Modification
# =============================================================================

def _field_value_end(entry_text: str, value_start: int):
    """Index just past the closing delimiter of a field value that begins
    at value_start, or None if it can't be bounded there (no recognizable
    delimiter, or an unbalanced brace-delimited value).

    Brace-delimited values are bounded by explicit depth counting, not a
    regex character class -- a class like `(?:[^{}]|\\{[^{}]*\\})*` only
    tolerates ONE level of interior nesting; deepening it just moves the
    wall further out, it never removes it (review finding 1, Task 4: a
    two-level-nested existing abstract like
    `{We show {\\it Kant's {a priori}} fails.}` silently failed to match,
    falling through to the insert branch below and leaving BOTH the stale
    and the newly inserted field in the entry -- a duplicate `abstract =`
    that pybtex rejects, invisible to `stamp_evidence.parse_entry_fields`'
    own one-level-tolerant regex, which is why the stamp went out wrong
    too). Depth counting handles nesting at any depth because it isn't
    matching a fixed shape -- it just tracks a counter.
    """
    if value_start >= len(entry_text):
        return None
    delim = entry_text[value_start]
    if delim == '{':
        depth = 0
        for i in range(value_start, len(entry_text)):
            c = entry_text[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
        return None  # unbalanced -- can't safely bound this occurrence
    if delim == '"':
        end = entry_text.find('"', value_start + 1)
        return None if end == -1 else end + 1
    return None


def add_field_to_entry(entry_text: str, field_name: str, field_value: str) -> str:
    """Add or update a field in a BibTeX entry.

    Values are inserted as-is inside braces. BibTeX brace-delimited values
    don't need escaping — braces inside the value are only problematic if
    unbalanced, which API-sourced content won't have. Escaping would corrupt
    LaTeX markup (e.g. \\textit{...}) in abstracts.
    """
    # Check if field already exists -- brace- OR quote-delimited (pybtex's
    # writer emits quoted values on round-trip; researchers hand-write both
    # forms). Brace-delimited values are located by depth-counting
    # (_field_value_end), not a shallow-nesting regex, so an existing value
    # nested at ANY depth is found and replaced whole rather than silently
    # missed. Every occurrence of the field is replaced (not just the
    # first) -- pinned by
    # tests/test_enrich_bibliography.py::test_add_field_replace_all_occurrences_pinned,
    # which documents that callers rely on entry_text being a SINGLE entry.
    head_pattern = re.compile(rf'(\s+){re.escape(field_name)}\s*=\s*', re.IGNORECASE)
    pieces = []
    pos = 0
    replaced_any = False
    while True:
        m = head_pattern.search(entry_text, pos)
        if not m:
            break
        value_end = _field_value_end(entry_text, m.end())
        if value_end is None:
            break  # can't safely bound this occurrence -- stop; fall through
        pieces.append(entry_text[pos:m.start(1)])
        pieces.append(m.group(1))
        # Function replacement, NOT a template string: abstracts carry
        # LaTeX backslashes, and a template would interpret \1, \g<...>.
        pieces.append(f'{field_name} = {{{field_value}}}')
        pos = value_end
        replaced_any = True
    if replaced_any:
        pieces.append(entry_text[pos:])
        return ''.join(pieces)
    else:
        # Add new field immediately after the entry's opening line (@type{key,).
        # The opening line is never inside a field value, so a multi-line value
        # (e.g. a wrapped abstract) can no longer swallow the next insertion
        # (item 13 D2).
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


# Quote-aware keywords-field matcher: brace-delimited value in group(1),
# quote-delimited value in group(2) (never both). Brace-only matching here
# previously let a quote-delimited `keywords = "..."` field fall through to
# add_field_to_entry, which REPLACES a field wholesale on a hit -- silently
# destroying every existing token (topic tags + importance level) and
# leaving only the newly added/removed keyword (reviewer-reproduced). Both
# add_keyword_to_entry and remove_keyword_from_entry must find the field in
# EITHER delimiter style and edit its value in place; only add_keyword_to_entry
# delegates to add_field_to_entry, and only when no keywords field exists at
# all.
_KEYWORDS_FIELD_RE = re.compile(
    r'keywords\s*=\s*(?:\{([^{}]*)\}|"([^"]*)")',
    re.IGNORECASE
)


def remove_keyword_from_entry(entry_text: str, keyword: str) -> str:
    """Remove a keyword from the keywords field (brace- or quote-delimited;
    see _KEYWORDS_FIELD_RE)."""
    match = _KEYWORDS_FIELD_RE.search(entry_text)

    if not match:
        return entry_text

    existing = match.group(1) if match.group(1) is not None else match.group(2)
    # Split, filter, rejoin
    keywords = [k.strip() for k in existing.split(',')]
    keywords = [k for k in keywords if k and k != keyword]

    if keywords:
        new_keywords = ', '.join(keywords)
        return (
            entry_text[:match.start()]
            + f'keywords = {{{new_keywords}}}'
            + entry_text[match.end():]
        )
    else:
        # Remove the entire keywords field if empty
        return re.sub(
            r'\n\s*keywords\s*=\s*(?:\{[^{}]*\}|"[^"]*"),?',
            '',
            entry_text,
            flags=re.IGNORECASE
        )


def add_keyword_to_entry(entry_text: str, keyword: str) -> str:
    """Add a keyword to the keywords field (brace- or quote-delimited;
    see _KEYWORDS_FIELD_RE). Appends inside the existing value, preserving
    every other token; only delegates to add_field_to_entry (which
    replaces a field wholesale) when no keywords field exists at all."""
    match = _KEYWORDS_FIELD_RE.search(entry_text)

    if match:
        existing = match.group(1) if match.group(1) is not None else match.group(2)
        if keyword not in existing:
            new_keywords = f'{existing}, {keyword}' if existing.strip() else keyword
            return (
                entry_text[:match.start()]
                + f'keywords = {{{new_keywords}}}'
                + entry_text[match.end():]
            )
        return entry_text
    else:
        # Add keywords field
        return add_field_to_entry(entry_text, 'keywords', keyword)


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
            # backslashreplace: pybtex messages can embed accented source
            # text, and this diagnostic may be piped through Windows
            # cp1252 (CLAUDE.md non-ASCII output rule).
            diag = f"{type(e).__name__}: {e}".encode(
                'ascii', 'backslashreplace').decode('ascii')
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
        marked_incomplete, skipped, sources. If pybtex validation fails,
        the original file is left unchanged and stats['validation_failed']
        is set to True.
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
        'skipped': 0,
        'prefilled_attested': 0,
        'prefilled_unverified': 0,
        'sources': {'s2': 0, 'openalex': 0, 'core': 0, 'ndpr': 0}
    }

    enriched_entries = []
    # citation key -> {abstract_source, abstract_sha256} for abstracts this
    # run wrote (shared-contract "Enrichment ledger" schema); merged with any
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

    # --- NDPR enrichment pass for books without abstracts ---
    # Only attempt NDPR for @book entries that:
    # 1. Still lack an abstract after the main enrichment pass
    # 2. Have High or Medium importance (as noted in keywords)
    # Both delimiter forms: on a round-tripped bib these were brace-only
    # and the NDPR pass went blind. Value extraction reuses the
    # module-level _KEYWORDS_FIELD_RE (defined above; do not duplicate it)
    # -- same group semantics, group(1)=braced value, group(2)=quoted value.
    _incomplete_kw_re = re.compile(
        r'keywords\s*=\s*(?:\{[^}]*INCOMPLETE|"[^"]*INCOMPLETE)', re.IGNORECASE)

    def _has_high_or_medium_importance(entry_text: str) -> bool:
        m = _KEYWORDS_FIELD_RE.search(entry_text)
        if not m:
            return False
        value = m.group(1) if m.group(1) is not None else m.group(2)
        tokens = [t.strip() for t in value.split(',')]
        return any(t in ('High', 'Medium') for t in tokens)

    book_entries_without_abstract = [
        (i, e) for i, e in enumerate(entries)
        if e['entry_type'] == 'book'
        and not has_abstract(e)
        and _incomplete_kw_re.search(enriched_entries[i])
        and _has_high_or_medium_importance(enriched_entries[i])
    ]

    if book_entries_without_abstract:
        log_progress(f"Trying NDPR for {len(book_entries_without_abstract)} book(s) without abstracts...")
        for idx, entry in book_entries_without_abstract:
            title = entry['fields'].get('title', '')
            author = get_author_last_name(entry)
            abstract, source = resolve_ndpr_abstract(title, author, debug)
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
            log_progress(f"WARNING: Enriched file has BibTeX syntax errors: {e}")
            offenders = _name_invalid_entries(enriched_entries)
            for key, diag in offenders:
                log_progress(f"WARNING:   offending entry '{key}': {diag}")
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
        log_progress(f"WARNING: Validation failed — original file unchanged")

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
    attestation authority for the zero-fetch fast path, the same trust
    boundary the evidence barrier already places on it.
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
    later consumes (shared-contract 'Enrichment ledger' schema). Existing
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
        print(f"  Total entries: {stats['total']}")
        print(f"  Already had abstract: {stats['already_had_abstract']}")
        print(f"  Enriched: {stats['enriched']}")
        print(f"  Marked INCOMPLETE: {stats['marked_incomplete']}")
        if stats['enriched'] > 0:
            print(f"  Sources: {stats['sources']}")

        sys.exit(0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
