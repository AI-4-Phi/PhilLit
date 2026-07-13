#!/usr/bin/env python3
"""Normalize section and subsection headings in an assembled literature review.

Enforces consistent numbering: ## Section N: Title for body sections,
### N.M Title for subsections. Introduction and Conclusion remain unnumbered.
Em-dashes in heading titles are normalized to colons.

Note: Only ## and ### headings are processed. #### and deeper headings are
passed through unchanged. YAML frontmatter (--- delimited) is skipped.
"""

import dataclasses
import re
import sys
from pathlib import Path

# Patterns for detecting intro/conclusion headings (case-insensitive, matched on stripped title)
INTRO_PATTERNS = {"introduction", "preamble", "overview", "background"}
CONCLUSION_PATTERNS = {"conclusion", "summary", "closing remarks", "final remarks", "concluding remarks"}

# Headings to exclude from processing entirely (left as-is)
EXCLUDED_HEADINGS = {"references", "bibliography"}

# Regex for stripping existing section/subsection prefixes.
# Limited to 1-2 digit numbers to avoid false positives like "Section 230".
RE_SECTION_PREFIX = re.compile(r'^(?:Section\s+\d{1,2}\s*:\s*)(.*)', re.IGNORECASE)
# Note: The optional "Subsection" prefix means bare "N.M" patterns also match.
# This could false-positive on titles starting with decimal numbers (e.g., "3.5 Sigma"),
# but such titles are extremely rare in philosophy literature review headings.
RE_SUBSECTION_PREFIX = re.compile(r'^(?:Subsection\s+)?\d{1,2}\.\d{1,2}\s*:?\s*(.*)', re.IGNORECASE)


@dataclasses.dataclass
class SectionInfo:
    line_index: int
    raw_line: str
    stripped_title: str
    kind: str  # "intro", "conclusion", "body", "excluded"
    section_num: int | None
    subsection_lines: list[int]


def strip_section_prefix(title: str) -> str:
    """Strip 'Section N:' prefix from a heading title.

    Only matches 1-2 digit section numbers to avoid false positives
    like 'Section 230 and Platform Liability'.
    """
    m = RE_SECTION_PREFIX.match(title)
    return m.group(1).strip() if m else title


def strip_subsection_prefix(title: str) -> str:
    """Strip 'Subsection N.M:', 'N.M:', or 'N.M' prefix from a subsection title."""
    m = RE_SUBSECTION_PREFIX.match(title)
    return m.group(1).strip() if m else title


def normalize_em_dashes(title: str) -> str:
    """Replace em-dashes with colons in heading titles."""
    return re.sub(r'\s*\u2014\s*', ': ', title)


def classify_heading(stripped_title: str, position: str) -> str:
    """Classify a heading as intro, conclusion, or body based on title and position.

    Args:
        stripped_title: The heading title with any section prefix already removed.
        position: One of "first", "last", or "middle".
    """
    lower_title = stripped_title.lower().strip()
    if position == "first" and lower_title in INTRO_PATTERNS:
        return "intro"
    if position == "last" and lower_title in CONCLUSION_PATTERNS:
        return "conclusion"
    return "body"


def normalize_headings(content: str) -> tuple[str, list[str]]:
    """Normalize section and subsection headings in a literature review.

    4-pass algorithm:
      Pass 1: Collect all ## headings, strip prefixes, normalize em-dashes, track ### lines.
      Pass 2: Classify non-excluded headings (intro/conclusion/body).
      Pass 3: Assign sequential section numbers to body headings.
      Pass 4: Generate normalized lines and track changes.

    Returns:
        Tuple of (new_content, list_of_change_descriptions).
    """
    lines = content.split('\n')
    changes: list[str] = []

    # Skip YAML frontmatter (--- delimited block at start of file)
    frontmatter_end = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                frontmatter_end = i + 1
                break

    # --- Pass 1: Collect ## headings and their ### subsection lines ---
    sections: list[SectionInfo] = []
    current_section_idx: int | None = None

    for i, line in enumerate(lines):
        if i < frontmatter_end:
            continue
        if line.startswith('## ') and not line.startswith('### '):
            raw_title = line[3:].strip()
            stripped = strip_section_prefix(raw_title)
            stripped = normalize_em_dashes(stripped)

            # Check if this heading is excluded
            if stripped.lower().strip() in EXCLUDED_HEADINGS:
                kind = "excluded"
            else:
                kind = "body"  # Placeholder; classified in Pass 2

            info = SectionInfo(
                line_index=i,
                raw_line=line,
                stripped_title=stripped,
                kind=kind,
                section_num=None,
                subsection_lines=[],
            )
            sections.append(info)
            current_section_idx = len(sections) - 1

        elif line.startswith('### ') and current_section_idx is not None:
            sections[current_section_idx].subsection_lines.append(i)

    # --- Pass 2: Classify non-excluded headings ---
    non_excluded = [s for s in sections if s.kind != "excluded"]

    if len(non_excluded) == 1:
        # Special case: only one heading
        s = non_excluded[0]
        lower = s.stripped_title.lower().strip()
        if lower in INTRO_PATTERNS:
            s.kind = "intro"
        elif lower in CONCLUSION_PATTERNS:
            s.kind = "conclusion"
        else:
            s.kind = "body"
    else:
        for idx, s in enumerate(non_excluded):
            if idx == 0:
                position = "first"
            elif idx == len(non_excluded) - 1:
                position = "last"
            else:
                position = "middle"
            s.kind = classify_heading(s.stripped_title, position)

    # --- Pass 3: Assign sequential section numbers to body headings ---
    body_counter = 0
    for s in sections:
        if s.kind == "body":
            body_counter += 1
            s.section_num = body_counter

    # --- Pass 4: Generate normalized lines ---
    # Build a map of line_index -> new line content
    replacements: dict[int, str] = {}

    for s in sections:
        if s.kind == "excluded":
            continue

        if s.kind in ("intro", "conclusion"):
            new_line = f"## {s.stripped_title}"
            if new_line != s.raw_line:
                replacements[s.line_index] = new_line
                changes.append(f"L{s.line_index + 1}: '{s.raw_line}' -> '{new_line}'")

            # Subsections in intro/conclusion: strip prefix, normalize em-dashes, no number
            for sub_i in s.subsection_lines:
                sub_raw = lines[sub_i]
                sub_title = sub_raw[4:].strip()  # Strip '### '
                sub_title = strip_subsection_prefix(sub_title)
                sub_title = normalize_em_dashes(sub_title)
                new_sub = f"### {sub_title}"
                if new_sub != sub_raw:
                    replacements[sub_i] = new_sub
                    changes.append(f"L{sub_i + 1}: '{sub_raw}' -> '{new_sub}'")

        elif s.kind == "body":
            new_line = f"## Section {s.section_num}: {s.stripped_title}"
            if new_line != s.raw_line:
                replacements[s.line_index] = new_line
                changes.append(f"L{s.line_index + 1}: '{s.raw_line}' -> '{new_line}'")

            # Subsections in body: strip prefix, normalize em-dashes, apply N.M numbering
            sub_counter = 0
            for sub_i in s.subsection_lines:
                sub_counter += 1
                sub_raw = lines[sub_i]
                sub_title = sub_raw[4:].strip()  # Strip '### '
                sub_title = strip_subsection_prefix(sub_title)
                sub_title = normalize_em_dashes(sub_title)
                new_sub = f"### {s.section_num}.{sub_counter} {sub_title}"
                if new_sub != sub_raw:
                    replacements[sub_i] = new_sub
                    changes.append(f"L{sub_i + 1}: '{sub_raw}' -> '{new_sub}'")

    # Apply replacements
    for i, new_line in replacements.items():
        lines[i] = new_line

    new_content = '\n'.join(lines)
    return new_content, changes


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Normalize section/subsection headings in a literature review'
    )
    parser.add_argument('file', type=Path, help='Markdown file to normalize (modified in-place)')

    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    content = args.file.read_text(encoding='utf-8')
    new_content, changes = normalize_headings(content)

    if changes:
        args.file.write_text(new_content, encoding='utf-8')
        print(f"Normalized {len(changes)} heading(s) in {args.file.name}:", file=sys.stderr)
        for change in changes:
            print(f"  {change}", file=sys.stderr)
    else:
        print("No heading changes needed.", file=sys.stderr)


if __name__ == '__main__':
    main()
