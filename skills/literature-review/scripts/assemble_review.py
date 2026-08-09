#!/usr/bin/env python3
"""Assemble literature review sections into a single markdown file with YAML frontmatter."""

import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import yaml

# Grammar parity with the phillit-service consumer (its reviews/title.py
# validate_title and frontmatter.py caps) - parity, not sanitizing: a
# producer that STRIPS could emit a title the consumer's grammar would never
# have accepted from the original input, so invalid values are dropped with
# a bounded warning instead (decided 2026-08-08, ADOPT; constraints in the
# service's known-issues/frontmatter-title-unvalidated-at-producer.md).
_TITLE_MAX_CHARS = 160
_TITLE_FORBIDDEN_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")  # covers multiline+bidi
_SUBFIELD_RE = re.compile(r"[A-Za-z][A-Za-z /&-]{0,59}\Z")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
# The consumer rejects any frontmatter block over 50 lines or 2 KB and - by
# its deliberate never-strip contract - then leaves the raw YAML visible in
# the delivered review body.
_FRONTMATTER_MAX_LINES = 50
_FRONTMATTER_MAX_BYTES = 2048


def _valid_title(title: str) -> str | None:
    """NFC+trimmed title, or None with a BOUNDED warning (drop, never
    sanitize; never echo the text - it can carry 10,000 chars of user topic
    into logs, so the warning names the reason and a length only)."""
    normalized = unicodedata.normalize("NFC", title).strip()
    if not normalized or len(normalized) > _TITLE_MAX_CHARS:
        print(f"Warning: invalid title dropped from frontmatter "
              f"(length {len(normalized)} after NFC+trim; "
              f"1-{_TITLE_MAX_CHARS} required)", file=sys.stderr)
        return None
    if any(unicodedata.category(ch) in _TITLE_FORBIDDEN_CATEGORIES
           for ch in normalized):
        print("Warning: invalid title dropped from frontmatter "
              "(contains a control or format character)", file=sys.stderr)
        return None
    return normalized


def _valid_date(value: str) -> str | None:
    """The exact-shape calendar date, or None with a bounded warning."""
    if _DATE_RE.match(value):
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            pass
    print(f"Warning: invalid date dropped from frontmatter "
          f"(need YYYY-MM-DD, got {len(value)} chars)", file=sys.stderr)
    return None


def build_frontmatter(title: str, date: str, subfield: str | None = None) -> str:
    """Build the ----delimited YAML frontmatter block for the review file.

    Adopted from phillit-service (its 098a57f) with the --title/--date
    validation landed as one change. Every field is validated and an invalid
    value is dropped with a bounded warning, its key omitted; with a valid
    title and date and no subfield the output is byte-identical to the
    historical block. The subfield grammar (letters/spaces/`/`/`&`/`-`,
    starts with a letter, max 60 chars) is the service consumer's.
    """
    fields = {}
    valid_title = _valid_title(title)
    if valid_title is not None:
        fields['title'] = valid_title
    valid_date = _valid_date(date)
    if valid_date is not None:
        fields['date'] = valid_date
    if subfield is not None:
        subfield = subfield.strip()
        if _SUBFIELD_RE.fullmatch(subfield):
            fields['subfield'] = subfield
        else:
            print(f"Warning: invalid subfield dropped from frontmatter "
                  f"({len(subfield)} chars)", file=sys.stderr)

    # yaml.safe_dump handles special characters (quoting, unicode)
    yaml_block = yaml.safe_dump(
        fields,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip('\n')
    block = '\n'.join(['---', yaml_block, '---'])

    # Post-serialization invariant: validated fields cannot exceed the
    # consumer's caps, so a violation here means a NEW key recreated the
    # oversized-block bug - fail loudly rather than deliver raw YAML.
    if (len(block.encode('utf-8')) > _FRONTMATTER_MAX_BYTES
            or block.count('\n') + 1 > _FRONTMATTER_MAX_LINES):
        raise ValueError(
            f"frontmatter block exceeds the consumer caps "
            f"({_FRONTMATTER_MAX_LINES} lines / {_FRONTMATTER_MAX_BYTES} bytes)")
    return block


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
    review_date: str | None = None,
    subfield: str | None = None
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

    # YAML frontmatter
    parts.append(build_frontmatter(title, review_date, subfield))
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
    parser.add_argument('--title', required=True,
                        help='Review title for YAML frontmatter (max 160 chars '
                             'after NFC+trim, no control/format characters; '
                             'invalid values are dropped with a warning)')
    parser.add_argument('--date', help='Review date (exact YYYY-MM-DD, defaults '
                                       'to today; invalid values are dropped)')
    parser.add_argument(
        '--subfield',
        help='Review subfield in Title Case for YAML frontmatter '
             '(letters, spaces, /, &, - only; max 60 chars; invalid values '
             'are dropped)'
    )
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
            review_date=args.date,
            subfield=args.subfield
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
