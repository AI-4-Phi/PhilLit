#!/usr/bin/env python3
"""Deduplicate BibTeX entries by citation key and DOI, keeping highest importance.

Also handles:
- Preferring entries with abstract over entries without
- Preserving abstract_source field
- Removing INCOMPLETE flag when merged entry has abstract
"""

import re
import sys
from pathlib import Path

IMPORTANCE_ORDER = {'High': 3, 'Medium': 2, 'Low': 1}


def check_intra_entry_duplicates(content: str) -> list[str]:
    """Warn about duplicate field names within BibTeX entries.

    Lightweight safety-net check for Phase 6 aggregation. Does not crash or
    fix — just prints warnings so operators notice if upstream validation
    was bypassed.

    Uses brace-depth tracking to avoid false positives from multi-line field
    values that happen to contain 'word = text' patterns.

    Returns list of warning strings (empty if clean).
    """
    warnings = []
    lines = content.split('\n')

    current_key = None
    fields_seen: dict[str, int] = {}
    brace_depth = 0
    in_comment = False

    for line_num, line in enumerate(lines, 1):
        entry_match = re.match(r'@(\w+)\{', line, re.IGNORECASE)
        if entry_match and brace_depth == 0:
            entry_type = entry_match.group(1).lower()
            if entry_type == 'comment':
                in_comment = True
                brace_depth += line.count('{') - line.count('}')
                continue
            rest = line[entry_match.end():]
            key_match = re.match(r'([^,]+),', rest)
            if key_match:
                current_key = key_match.group(1).strip()
                fields_seen = {}
                brace_depth = line.count('{') - line.count('}')
            continue

        if in_comment:
            brace_depth += line.count('{') - line.count('}')
            if brace_depth <= 0:
                in_comment = False
                brace_depth = 0
            continue

        if current_key is None:
            continue

        if brace_depth == 1:
            field_match = re.match(r'\s*(\w+)\s*=\s*', line)
            if field_match:
                field_name = field_match.group(1).lower()
                if field_name in fields_seen:
                    msg = (
                        f"  [WARN] '{current_key}': duplicate field '{field_name}' "
                        f"(lines {fields_seen[field_name]} and {line_num})"
                    )
                    warnings.append(msg)
                    print(msg)
                else:
                    fields_seen[field_name] = line_num

        brace_depth += line.count('{') - line.count('}')

        if brace_depth <= 0:
            current_key = None
            fields_seen = {}
            brace_depth = 0

    return warnings


def parse_importance(entry: str) -> str:
    """Extract importance level from keywords field."""
    for level in ['High', 'Medium', 'Low']:
        if level in entry:
            return level
    return 'Low'


def upgrade_importance(entry: str, new_importance: str) -> str:
    """Replace importance level in keywords field."""
    for level in ['High', 'Medium', 'Low']:
        if level in entry:
            return entry.replace(level, new_importance, 1)
    return entry


def extract_doi(entry: str) -> str | None:
    """Extract and normalize DOI from a BibTeX entry."""
    match = re.search(r'doi\s*=\s*\{([^}]+)\}', entry, re.IGNORECASE)
    if not match:
        return None
    doi = match.group(1).strip().lower()
    # Strip URL prefixes
    for prefix in ['https://doi.org/', 'http://doi.org/', 'https://dx.doi.org/', 'http://dx.doi.org/']:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def has_abstract(entry: str) -> bool:
    """Check if entry has a non-empty abstract field."""
    match = re.search(r'abstract\s*=\s*\{([^}]+)\}', entry, re.IGNORECASE)
    if match:
        abstract_content = match.group(1).strip()
        return len(abstract_content) > 10  # Filter out trivial abstracts
    return False


def has_incomplete_flag(entry: str) -> bool:
    """Check if entry has INCOMPLETE in keywords."""
    return 'INCOMPLETE' in entry


def remove_incomplete_flag(entry: str) -> str:
    """Remove INCOMPLETE and no-abstract flags from keywords."""
    entry = re.sub(r',?\s*INCOMPLETE\s*,?', ',', entry)
    entry = re.sub(r',?\s*no-abstract\s*,?', ',', entry)
    # Clean up resulting comma issues
    entry = re.sub(r',\s*,', ',', entry)
    entry = re.sub(r',\s*\}', '}', entry)
    entry = re.sub(r'\{\s*,', '{', entry)
    return entry


def merge_entries(entry1: str, entry2: str) -> tuple[str, str, int]:
    """
    Merge duplicate entries, preferring one with abstract and higher importance.

    Priority:
    1. Entry with abstract (if only one has it)
    2. Entry with higher importance (if both have or lack abstract)

    Returns:
        Tuple of (merged_entry, merge_reason, winner) where winner is 1 or 2.
    """
    has_abstract_1 = has_abstract(entry1)
    has_abstract_2 = has_abstract(entry2)
    importance_1 = parse_importance(entry1)
    importance_2 = parse_importance(entry2)

    reason = ""
    winner = 1

    if has_abstract_2 and not has_abstract_1:
        base = entry2
        winner = 2
        reason = "preferred entry with abstract"
        if IMPORTANCE_ORDER.get(importance_1, 0) > IMPORTANCE_ORDER.get(importance_2, 0):
            base = upgrade_importance(base, importance_1)
            reason += f", upgraded to {importance_1}"
    elif has_abstract_1 and not has_abstract_2:
        base = entry1
        winner = 1
        reason = "kept entry with abstract"
        if IMPORTANCE_ORDER.get(importance_2, 0) > IMPORTANCE_ORDER.get(importance_1, 0):
            base = upgrade_importance(base, importance_2)
            reason += f", upgraded to {importance_2}"
    else:
        # Both have abstract or neither has it — use importance
        if IMPORTANCE_ORDER.get(importance_2, 0) > IMPORTANCE_ORDER.get(importance_1, 0):
            base = entry2
            winner = 2
            reason = f"upgraded importance to {importance_2}"
        else:
            base = entry1
            winner = 1
            reason = f"kept existing ({importance_1})"

    # Remove INCOMPLETE flag if merged entry has abstract
    if has_abstract(base) and has_incomplete_flag(base):
        base = remove_incomplete_flag(base)
        reason += ", removed INCOMPLETE flag"

    return base, reason, winner


def deduplicate_bib(input_files: list[Path], output_file: Path) -> list[str]:
    """
    Deduplicate BibTeX entries across files.

    When merging duplicates:
    - Prefers entry with abstract over entry without
    - Upgrades importance to highest among duplicates
    - Removes INCOMPLETE flag if merged entry has abstract
    - Second pass catches same paper with different keys via DOI

    Returns list of duplicate keys that were removed.
    """
    seen: dict[str, str] = {}  # key -> entry_text
    comments: list[str] = []
    duplicates: list[str] = []

    for bib_file in input_files:
        content = bib_file.read_text(encoding='utf-8')

        # Safety-net: warn about duplicate fields within entries
        check_intra_entry_duplicates(content)

        # Split into entries (handles @comment, @article, @book, etc.)
        entries = re.split(r'\n(?=@)', content)

        for entry in entries:
            if not entry.strip():
                continue

            # Extract citation key
            match = re.match(r'@(\w+)\{([^,]+),', entry)
            if not match:
                if entry.strip().startswith('@comment'):
                    comments.append(entry)
                continue

            entry_type = match.group(1).lower()
            key = match.group(2).strip()

            if entry_type == 'comment':
                comments.append(entry)
                continue

            if key in seen:
                duplicates.append(key)
                merged, reason, _winner = merge_entries(seen[key], entry)
                seen[key] = merged
                print(f"  [DEDUPE] Duplicate '{key}' - {reason}")
            else:
                seen[key] = entry

    # Second pass: DOI-based deduplication (catches same paper with different keys)
    seen_dois: dict[str, str] = {}  # normalized_doi -> key
    doi_dupes: list[str] = []
    for key, entry in list(seen.items()):
        doi = extract_doi(entry)
        if doi is None:
            continue
        if doi in seen_dois:
            existing_key = seen_dois[doi]
            existing_entry = seen[existing_key]
            merged, reason, winner = merge_entries(existing_entry, entry)
            if winner == 2:
                # New entry won — replace
                print(f"  [DEDUPE-DOI] '{key}' and '{existing_key}' share DOI {doi} - keeping '{key}' ({reason})")
                del seen[existing_key]
                seen[key] = merged
                seen_dois[doi] = key
                doi_dupes.append(existing_key)
            else:
                # Existing entry won
                print(f"  [DEDUPE-DOI] '{key}' and '{existing_key}' share DOI {doi} - keeping '{existing_key}' ({reason})")
                seen[existing_key] = merged
                del seen[key]
                doi_dupes.append(key)
        else:
            seen_dois[doi] = key

    duplicates.extend(doi_dupes)

    # Write output
    with output_file.open('w', encoding='utf-8') as f:
        for comment in comments:
            f.write(comment.rstrip())
            f.write('\n\n')

        for key, entry in seen.items():
            f.write(entry.rstrip())
            f.write('\n\n')

    return duplicates


def main():
    if len(sys.argv) < 3:
        print("Usage: dedupe_bib.py output.bib input1.bib [input2.bib ...]")
        sys.exit(1)

    output = Path(sys.argv[1])
    inputs = [Path(f) for f in sys.argv[2:]]

    # Validate input files exist
    for f in inputs:
        if not f.exists():
            print(f"Error: Input file not found: {f}")
            sys.exit(1)

    duplicates = deduplicate_bib(inputs, output)

    if duplicates:
        print(f"\n  Removed {len(duplicates)} duplicate entries")
    else:
        print("\n  No duplicates found")


if __name__ == '__main__':
    main()
