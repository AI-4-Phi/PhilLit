#!/usr/bin/env python3
"""
Minimal markdown linter for Claude Code.
Checks markdown files against specific pymarkdownlnt rules.
"""
import re
import subprocess
import sys
from pathlib import Path

# Rule explanations for helpful error messages
RULE_EXPLANATIONS = {
    "MD001": "Heading levels should increment by one (don't skip from # to ###)",
    "MD003": "Heading style should be consistent (use ATX style: # Heading)",
    "MD004": "Unordered list style should be consistent (use - for bullets)",
    "MD005": "List items should have consistent indentation",
    "MD007": "Unordered list indentation should be consistent (2 spaces per level)",
    "MD018": "ATX headings need a space after the hash (# Heading, not #Heading)",
    "MD019": "ATX headings should have only one space after hash",
    "MD020": "Closed ATX headings need space inside (# Heading #)",
    "MD021": "Closed ATX headings should have only one space inside",
    "MD022": "Headings need blank lines above and below",
    "MD023": "Headings must start at the beginning of the line",
    "MD028": "Blockquotes should not have blank lines inside",
    "MD029": "Ordered list prefixes should be consistent",
    "MD031": "Fenced code blocks need blank lines above and below",
    "MD032": "Lists need blank lines above and below",
    "MD037": "Emphasis markers should not have spaces inside (*text*, not * text *)",
    "MD056": "Table rows should have consistent column count",
    "MD058": "Tables need blank lines above and below",
}

# Extensions to enable (front-matter handles YAML frontmatter in literature reviews)
ENABLED_EXTENSIONS = ["front-matter"]

# Rules enabled by default in pymarkdownlnt that we want to disable
# (not relevant for literature reviews - e.g., line length, trailing spaces)
DISABLED_RULES = [
    "MD009",  # No trailing spaces
    "MD010",  # No hard tabs
    "MD011",  # No reversed links
    "MD012",  # No multiple blanks
    "MD013",  # Line length
    "MD014",  # Commands show output
    "MD024",  # No duplicate heading
    "MD025",  # Single title/h1
    "MD026",  # No trailing punctuation in heading
    "MD027",  # Multiple spaces after blockquote
    "MD030",  # Spaces after list markers
    "MD033",  # No inline HTML
    "MD034",  # No bare URLs
    "MD035",  # Horizontal rule style
    "MD036",  # No emphasis as heading
    "MD038",  # Spaces inside code span
    "MD039",  # Spaces inside link text
    "MD040",  # Fenced code language
    "MD041",  # First line heading
    "MD042",  # No empty links
    "MD043",  # Required heading structure
    "MD044",  # Proper names capitalization
    "MD045",  # Images should have alt text
    "MD046",  # Code block style
    "MD047",  # Files should end with newline
    "MD048",  # Code fence style
]


def lint_markdown(filepath: str) -> int:
    """Lint a markdown file and output errors with explanations."""
    disabled_str = ",".join(DISABLED_RULES)
    extensions_str = ",".join(ENABLED_EXTENSIONS)

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pymarkdown",
                "--enable-extensions", extensions_str,
                "--disable-rules", disabled_str,
                "scan", filepath
            ],
            capture_output=True,
            text=True,
        )

        # Process output to add explanations
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                print(line)
                # Extract rule code from pymarkdown output format: "file:line:col: MDXXX: message"
                match = re.search(r': (MD\d{3}):', line)
                if match:
                    code = match.group(1)
                    if code in RULE_EXPLANATIONS:
                        print(f"  -> Fix: {RULE_EXPLANATIONS[code]}")

        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        return result.returncode

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# --- Prose-quality heuristics (roadmap item 13, B5) -------------------------
# WARN-level advisory checks surfaced at Phase 6. They NEVER affect the exit
# code: false positives cost nothing, so the patterns stay simple and err
# toward noticing rather than silence.

# Annotation phrases that leak into citation parentheses (item 13 §4.2): a
# citation parenthesis carrying any of these is an improvised process note
# that loses its margin-apparatus anchor at render.
_ANNOTATION_PHRASES = (
    "non-peer-reviewed",
    "working paper",
    "classic text",
    "cited via",
    # "primary policy source" observed verbatim in the 2026-07-17 production
    # artifact ("(Article 36 2013; a non-peer-reviewed primary policy source)")
    # — an evidence-grounded phrase, not an invention.
    "primary policy source",
)

# A parenthesis and its (non-nested) contents.
_PAREN_RE = re.compile(r"\(([^()]*)\)")

# In-prose "Section 3" / "Section 3.3" cross-reference tokens. Display-time
# renumbering makes these off-by-one; cross-reference by title instead.
_INPROSE_SECTION_RE = re.compile(r"\bSection\s+\d+(?:\.\d+)?\b")

# An H2 heading ending in a parenthesized Title-Case meta-label, e.g.
# "## Section 1: Foo (Core Analytical Section)". Requires >=2 Title-Case
# words so "(2020-2025)" and single ordinary words do not match.
_H2_META_LABEL_RE = re.compile(
    r"^\s*##\s+.*\(([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+)\)\s*$"
)


def check_prose_quality(text: str) -> list[str]:
    """Return WARN-level advisories about prose-quality issues (item 13 §4.2).

    Heuristic, WARN-only — the caller must never let these affect the exit
    code. Detects: (1) citation parentheses carrying process annotations,
    (2) in-prose "Section N(.M)" cross-references, (3) H2 headings ending in a
    parenthesized Title-Case meta-label. Fenced code blocks and heading lines
    are exempt from the prose checks.
    """
    warnings: list[str] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if stripped.startswith("#"):
            m = _H2_META_LABEL_RE.match(line)
            if m:
                warnings.append(
                    f"line {lineno}: H2 heading ends in a parenthesized "
                    f"meta-label '({m.group(1)})' - section titles should be "
                    f"reader-facing (WARN)"
                )
            # Headings are exempt from the prose checks below.
            continue

        for content in _PAREN_RE.findall(line):
            low = content.lower()
            for phrase in _ANNOTATION_PHRASES:
                if phrase in low:
                    warnings.append(
                        f"line {lineno}: citation parenthesis contains the "
                        f"annotation '{phrase}' - put source qualifiers in "
                        f"prose, outside the parenthesis (WARN)"
                    )
                    break

        for m in _INPROSE_SECTION_RE.finditer(line):
            warnings.append(
                f"line {lineno}: in-prose cross-reference '{m.group(0)}' - "
                f"cross-reference sections by title, not number (display "
                f"renumbering makes numbers off-by-one) (WARN)"
            )
    return warnings


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: python lint_md.py <markdown_file>", file=sys.stderr)
        return 1

    filepath = args[0]
    rc = lint_markdown(filepath)

    # Prose-quality advisories (item 13 §4.2): WARN-only — printed for the
    # orchestrator to see at Phase 6, never affecting the exit code.
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except OSError:
        text = ""
    for warning in check_prose_quality(text):
        print(f"WARN prose-quality: {warning}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
