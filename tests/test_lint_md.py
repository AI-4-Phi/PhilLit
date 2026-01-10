"""Tests for lint_md.py - Markdown linting script."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "literature-review" / "scripts" / "lint_md.py"


class TestLintMarkdown:
    """Tests for markdown linting."""

    def test_valid_markdown(self, tmp_path):
        """Valid markdown should pass."""
        md_file = tmp_path / "valid.md"
        md_file.write_text("# Heading\n\nParagraph text.\n\n## Subheading\n\nMore text.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_missing_blank_line_around_heading(self, tmp_path):
        """Missing blank line around heading should fail MD022."""
        md_file = tmp_path / "invalid.md"
        md_file.write_text("# Heading\nNo blank line after heading.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "MD022" in result.stdout

    def test_heading_level_skip(self, tmp_path):
        """Skipping heading levels should fail MD001."""
        md_file = tmp_path / "skip.md"
        md_file.write_text("# Heading 1\n\n### Heading 3\n\nSkipped level 2.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "MD001" in result.stdout

    def test_explanation_included(self, tmp_path):
        """Error output should include explanation."""
        md_file = tmp_path / "invalid.md"
        md_file.write_text("# Heading\nNo blank line after heading.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert "Fix:" in result.stdout

    def test_missing_args(self):
        """Should exit with error when args missing."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stderr

    def test_file_not_found(self, tmp_path):
        """Should exit with error for missing file."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(tmp_path / "nonexistent.md")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_line_length_not_enforced(self, tmp_path):
        """Line length (MD013) should not be enforced."""
        md_file = tmp_path / "long.md"
        long_line = "x" * 200  # 200 chars, well over 80
        md_file.write_text(f"# Heading\n\n{long_line}\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        # Should pass since MD013 is disabled
        assert result.returncode == 0
        assert "MD013" not in result.stdout

    def test_multiple_errors_multiple_explanations(self, tmp_path):
        """Multiple errors should show multiple explanations."""
        md_file = tmp_path / "multi.md"
        # MD022 (missing blank after heading) + MD001 (skipped heading level)
        md_file.write_text("# Heading\nNo blank line.\n### Skipped level 2\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        # Should have at least 2 "Fix:" explanations
        assert result.stdout.count("Fix:") >= 2
        assert "MD022" in result.stdout
        assert "MD001" in result.stdout

    def test_yaml_frontmatter_not_misinterpreted(self, tmp_path):
        """YAML frontmatter should not be misinterpreted as setext heading."""
        md_file = tmp_path / "frontmatter.md"
        # This pattern was causing false positives: pymarkdown saw the ---
        # followed by title: as a setext-style heading
        md_file.write_text(
            '---\ntitle: "Test Document"\ndate: 2026-01-09\n---\n\n'
            "## Introduction\n\nSome text.\n\n## Methods\n\nMore text.\n"
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        # Should pass - no false positives about heading style inconsistency
        assert result.returncode == 0
        assert "MD003" not in result.stdout  # No heading style errors
        assert "MD022" not in result.stdout  # No blank line errors from frontmatter
