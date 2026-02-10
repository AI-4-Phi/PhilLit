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
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Add philosophy-research scripts to path for imports
PHIL_SCRIPTS = Path(__file__).parent.parent.parent / "philosophy-research" / "scripts"
sys.path.insert(0, str(PHIL_SCRIPTS))

from rate_limiter import ExponentialBackoff, get_limiter


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

    # Split into entries
    entry_pattern = r'(@\w+\{[^@]+)'
    raw_entries = re.findall(entry_pattern, content, re.DOTALL)

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

        # Match field = {value} or field = "value" patterns
        # Handle multi-line values in braces
        field_pattern = r'(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}'
        for match in re.finditer(field_pattern, raw, re.DOTALL):
            field_name = match.group(1).lower()
            field_value = match.group(2).strip()
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
    # Check if field already exists
    pattern = rf'(\s+){field_name}\s*=\s*\{{[^}}]*\}}'
    if re.search(pattern, entry_text, re.IGNORECASE):
        # Replace existing field
        return re.sub(
            pattern,
            rf'\1{field_name} = {{{field_value}}}',
            entry_text,
            flags=re.IGNORECASE
        )
    else:
        # Add new field before closing brace
        # Find the last field line and add after it
        lines = entry_text.split('\n')
        for i in range(len(lines) - 1, -1, -1):
            if '=' in lines[i] and not lines[i].strip().startswith('}'):
                # Ensure preceding field line ends with a comma
                stripped = lines[i].rstrip()
                if stripped.endswith('}') and not stripped.endswith('},'):
                    lines[i] = stripped + ','
                # Insert after this line
                indent = '  '  # Default indent
                match = re.match(r'^(\s+)', lines[i])
                if match:
                    indent = match.group(1)
                lines.insert(i + 1, f'{indent}{field_name} = {{{field_value}}},')
                break
        else:
            # No existing fields found, add before closing brace
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == '}':
                    lines.insert(i, f'  {field_name} = {{{field_value}}},')
                    break
        return '\n'.join(lines)


def add_keyword_to_entry(entry_text: str, keyword: str) -> str:
    """Add a keyword to the keywords field."""
    # Check if keywords field exists
    pattern = r'keywords\s*=\s*\{([^}]*)\}'
    match = re.search(pattern, entry_text, re.IGNORECASE)

    if match:
        existing = match.group(1)
        if keyword not in existing:
            new_keywords = f'{existing}, {keyword}' if existing.strip() else keyword
            return re.sub(
                pattern,
                f'keywords = {{{new_keywords}}}',
                entry_text,
                flags=re.IGNORECASE
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
    debug: bool = False
) -> tuple[str, bool, Optional[str]]:
    """
    Enrich a single BibTeX entry with abstract if missing.

    Returns:
        Tuple of (enriched_entry_text, was_enriched, abstract_source)
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
        log_progress(f"  Added abstract from {source} ({len(abstract)} chars)")
        return entry_text, True, source
    else:
        # Mark as INCOMPLETE
        entry_text = add_keyword_to_entry(entry_text, 'INCOMPLETE')
        entry_text = add_keyword_to_entry(entry_text, 'no-abstract')
        log_progress(f"  No abstract found, marked INCOMPLETE")
        return entry_text, False, None


# =============================================================================
# Main Processing
# =============================================================================

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
        Stats dict with counts of processed, enriched, incomplete entries
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
        'sources': {'s2': 0, 'openalex': 0, 'core': 0}
    }

    enriched_entries = []

    for entry in entries:
        # Skip comments
        if entry['entry_type'] == 'comment':
            enriched_entries.append(entry['raw'])
            stats['skipped'] += 1
            continue

        # Check if already has abstract
        if has_abstract(entry):
            enriched_entries.append(entry['raw'])
            stats['already_had_abstract'] += 1
            continue

        # Try to enrich
        enriched_text, was_enriched, source = enrich_entry(
            entry, s2_api_key, openalex_email, core_api_key, debug
        )
        enriched_entries.append(enriched_text)

        if was_enriched and source:
            stats['enriched'] += 1
            stats['sources'][source] = stats['sources'].get(source, 0) + 1
        else:
            stats['marked_incomplete'] += 1

    # Write output
    if output_path is None:
        output_path = input_path  # Overwrite in place

    output_content = '\n\n'.join(entry.strip() for entry in enriched_entries)
    output_path.write_text(output_content + '\n', encoding='utf-8')

    # Validate the enriched output (defense-in-depth: catch errors at the source)
    try:
        from pybtex.database import parse_file
    except ImportError:
        pass  # pybtex not available, skip validation
    else:
        try:
            parse_file(str(output_path), bib_format='bibtex')
        except Exception as e:
            log_progress(f"WARNING: Enriched file has BibTeX syntax errors: {e}")

    log_progress(f"Wrote enriched bibliography to {output_path.name}")
    log_progress(f"Stats: {stats['enriched']} enriched, {stats['marked_incomplete']} incomplete, {stats['already_had_abstract']} already had abstract")

    return stats


def main():
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
