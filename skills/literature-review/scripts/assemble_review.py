#!/usr/bin/env python3
"""Assemble literature review sections into a single markdown file with YAML frontmatter."""

import re
import sys
from datetime import date
from pathlib import Path

import yaml


def natural_sort_key(path: Path) -> tuple[str | int, ...]:
    """Sort key for natural ordering (section-2 before section-10)."""
    # Extract numbers from filename and convert to int for proper sorting
    parts = re.split(r'(\d+)', path.name)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def strip_section_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from section content if present.

    Frontmatter must start with '---\\n' and end with '\\n---\\n' or '\\n---' at EOF.
    """
    if not content.startswith('---\n'):
        return content

    # Find closing delimiter: \n--- followed by newline or end of string
    match = re.search(r'\n---\n|\n---$', content[4:])
    if match:
        # Skip frontmatter and the closing delimiter
        end_pos = 4 + match.end()
        return content[end_pos:].lstrip('\n')

    return content


def assemble_review(
    output_file: Path,
    section_files: list[Path],
    title: str,
    review_date: str | None = None
) -> dict:
    """
    Assemble sections into a single review file with YAML frontmatter.

    Returns dict with assembly statistics.
    """
    if not section_files:
        raise ValueError("No section files provided")

    # Sort sections naturally (section-2 before section-10)
    sorted_files = sorted(section_files, key=natural_sort_key)

    # Use provided date or today
    if review_date is None:
        review_date = date.today().isoformat()

    # Build output content
    parts = []

    # YAML frontmatter (using yaml.safe_dump to handle special characters)
    frontmatter = yaml.safe_dump(
        {'title': title, 'date': review_date},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip('\n')
    parts.append('---')
    parts.append(frontmatter)
    parts.append('---')
    parts.append('')  # Blank line after frontmatter

    stats = {
        'sections': [],
        'total_bytes': 0,
        'warnings': []
    }

    for section_file in sorted_files:
        if not section_file.exists():
            raise FileNotFoundError(f"Section file not found: {section_file}")

        content = section_file.read_text(encoding='utf-8')

        # Strip any frontmatter from individual sections
        content = strip_section_frontmatter(content)

        # Check for empty sections
        if not content.strip():
            stats['warnings'].append(f"Empty section: {section_file.name}")
            continue

        section_bytes = len(content.encode('utf-8'))
        stats['sections'].append({
            'name': section_file.name,
            'bytes': section_bytes
        })
        stats['total_bytes'] += section_bytes

        # Add section content with trailing newline normalization
        # Use single blank line between sections (MD022 requires exactly 1)
        parts.append(content.rstrip())
        parts.append('')  # Single blank line between sections

    # Remove trailing blank lines (keep just one at end)
    while parts and parts[-1] == '':
        parts.pop()
    parts.append('')  # Single trailing newline

    # Write output
    output_content = '\n'.join(parts)
    output_file.write_text(output_content, encoding='utf-8')

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Assemble literature review sections into a single file'
    )
    parser.add_argument('output', type=Path, help='Output file path')
    parser.add_argument('--title', required=True, help='Review title for YAML frontmatter')
    parser.add_argument('--date', help='Review date (YYYY-MM-DD), defaults to today')
    parser.add_argument('sections', nargs='+', type=Path, help='Section files to assemble')

    args = parser.parse_args()

    # Validate section files exist
    missing = [f for f in args.sections if not f.exists()]
    if missing:
        print(f"Error: Section files not found: {', '.join(str(f) for f in missing)}", file=sys.stderr)
        sys.exit(1)

    try:
        stats = assemble_review(
            output_file=args.output,
            section_files=args.sections,
            title=args.title,
            review_date=args.date
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Report summary
    print(f"Assembled {len(stats['sections'])} sections into {args.output.name}")
    for section in stats['sections']:
        print(f"  - {section['name']} ({section['bytes']:,} bytes)")
    print(f"Total: {stats['total_bytes']:,} bytes")

    if stats['warnings']:
        print("\nWarnings:")
        for warning in stats['warnings']:
            print(f"  - {warning}")


if __name__ == '__main__':
    main()
