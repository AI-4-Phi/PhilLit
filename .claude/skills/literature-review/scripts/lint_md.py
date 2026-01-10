#!/usr/bin/env python3
"""
Minimal markdown linter for Claude Code.
Checks markdown files against specific pymarkdownlnt rules.
"""
import re
import subprocess
import sys

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
                        print(f"  → Fix: {RULE_EXPLANATIONS[code]}")

        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        return result.returncode

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python lint_md.py <markdown_file>", file=sys.stderr)
        sys.exit(1)

    sys.exit(lint_markdown(sys.argv[1]))
