#!/usr/bin/env python3
"""Deduplicate BibTeX entries by citation key, keeping highest importance."""

import re
import sys
from pathlib import Path

IMPORTANCE_ORDER = {'High': 3, 'Medium': 2, 'Low': 1}


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


def deduplicate_bib(input_files: list[Path], output_file: Path) -> list[str]:
    """
    Deduplicate BibTeX entries across files.

    Returns list of duplicate keys that were removed.
    """
    seen: dict[str, tuple[str, str]] = {}  # key -> (entry_text, importance_level)
    comments: list[str] = []
    duplicates: list[str] = []

    for bib_file in input_files:
        content = bib_file.read_text(encoding='utf-8')

        # Split into entries (handles @comment, @article, @book, etc.)
        entries = re.split(r'\n(?=@)', content)

        for entry in entries:
            if not entry.strip():
                continue

            # Extract citation key
            match = re.match(r'@(\w+)\{([^,]+),', entry)
            if not match:
                # Keep any non-matching content that starts with @comment
                if entry.strip().startswith('@comment'):
                    comments.append(entry)
                continue

            entry_type = match.group(1).lower()
            key = match.group(2).strip()

            # Always keep @comment entries
            if entry_type == 'comment':
                comments.append(entry)
                continue

            importance = parse_importance(entry)

            if key in seen:
                # Duplicate found
                duplicates.append(key)
                existing_entry, existing_importance = seen[key]

                # Upgrade importance if new one is higher
                if IMPORTANCE_ORDER.get(importance, 0) > IMPORTANCE_ORDER.get(existing_importance, 0):
                    upgraded = upgrade_importance(existing_entry, importance)
                    seen[key] = (upgraded, importance)
                    print(f"  [DEDUPE] Duplicate '{key}' - upgraded importance to {importance}")
                else:
                    print(f"  [DEDUPE] Duplicate '{key}' - kept existing ({existing_importance})")
            else:
                seen[key] = (entry, importance)

    # Write output
    with output_file.open('w', encoding='utf-8') as f:
        # Write comments first (domain metadata headers)
        for comment in comments:
            f.write(comment.rstrip())
            f.write('\n\n')

        # Write entries
        for key, (entry, _) in seen.items():
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
