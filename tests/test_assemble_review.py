"""Tests for assemble_review.py - Literature review assembly script."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts" / "assemble_review.py"

# Add script directory to path for unit tests
sys.path.insert(0, str(SCRIPT_PATH.parent))
from assemble_review import natural_sort_key, strip_section_frontmatter, assemble_review


class TestNaturalSortKey:
    """Tests for natural sorting of section files."""

    def test_numeric_sorting(self):
        """Section-2 should sort before section-10."""
        paths = [
            Path("section-10.md"),
            Path("section-2.md"),
            Path("section-1.md"),
        ]
        sorted_paths = sorted(paths, key=natural_sort_key)
        assert [p.name for p in sorted_paths] == [
            "section-1.md",
            "section-2.md",
            "section-10.md",
        ]

    def test_prefix_sorting(self):
        """Handles synthesis-section prefix."""
        paths = [
            Path("synthesis-section-3.md"),
            Path("synthesis-section-1.md"),
            Path("synthesis-section-2.md"),
        ]
        sorted_paths = sorted(paths, key=natural_sort_key)
        assert [p.name for p in sorted_paths] == [
            "synthesis-section-1.md",
            "synthesis-section-2.md",
            "synthesis-section-3.md",
        ]


class TestStripSectionFrontmatter:
    """Tests for removing YAML frontmatter from sections."""

    def test_no_frontmatter(self):
        """Content without frontmatter is unchanged."""
        content = "## Section\n\nParagraph."
        assert strip_section_frontmatter(content) == content

    def test_with_frontmatter(self):
        """Frontmatter is stripped."""
        content = '---\ntitle: "Section"\n---\n\n## Section\n\nParagraph.'
        result = strip_section_frontmatter(content)
        assert result == "## Section\n\nParagraph."

    def test_frontmatter_only_at_start(self):
        """Only strips frontmatter at document start."""
        content = "Some text\n---\nnot frontmatter\n---\nmore text"
        assert strip_section_frontmatter(content) == content

    def test_frontmatter_with_dashes_in_content(self):
        """Frontmatter containing --- in YAML values is handled correctly."""
        # The --- inside the YAML value should not be treated as closing delimiter
        content = '---\ntitle: "Section"\nnote: "Use --- for dividers"\n---\n\n## Content'
        result = strip_section_frontmatter(content)
        assert result == "## Content"

    def test_malformed_frontmatter_no_close(self):
        """Frontmatter without closing delimiter is left unchanged."""
        content = '---\ntitle: "Section"\nNo closing delimiter here\n## Content'
        assert strip_section_frontmatter(content) == content

    def test_frontmatter_requires_newline_after_opening(self):
        """Opening --- must be followed by newline."""
        content = '---title: "Section"\n---\nContent'
        assert strip_section_frontmatter(content) == content


class TestAssembleReview:
    """Tests for the main assembly function."""

    def test_basic_assembly(self, tmp_path):
        """Assembles sections with frontmatter."""
        # Create section files
        (tmp_path / "section-1.md").write_text("## Introduction\n\nFirst section.")
        (tmp_path / "section-2.md").write_text("## Methods\n\nSecond section.")

        output = tmp_path / "output.md"
        stats = assemble_review(
            output_file=output,
            section_files=[tmp_path / "section-1.md", tmp_path / "section-2.md"],
            title="Test Review",
            review_date="2026-01-10"
        )

        content = output.read_text()

        # Check frontmatter (yaml.safe_dump format)
        assert content.startswith('---\n')
        assert 'title: Test Review\n' in content
        assert 'date: ' in content
        assert '2026-01-10' in content
        assert '\n---\n' in content

        # Check sections are present
        assert "## Introduction" in content
        assert "## Methods" in content

        # Check stats
        assert len(stats['sections']) == 2
        assert stats['total_bytes'] > 0

    def test_natural_sorting(self, tmp_path):
        """Sections are sorted numerically."""
        (tmp_path / "section-10.md").write_text("## Ten")
        (tmp_path / "section-2.md").write_text("## Two")
        (tmp_path / "section-1.md").write_text("## One")

        output = tmp_path / "output.md"
        assemble_review(
            output_file=output,
            section_files=[
                tmp_path / "section-10.md",
                tmp_path / "section-2.md",
                tmp_path / "section-1.md",
            ],
            title="Test",
        )

        content = output.read_text()
        # Sections should appear in order: 1, 2, 10
        pos_one = content.find("## One")
        pos_two = content.find("## Two")
        pos_ten = content.find("## Ten")
        assert pos_one < pos_two < pos_ten

    def test_empty_section_warning(self, tmp_path):
        """Empty sections produce warnings."""
        (tmp_path / "section-1.md").write_text("## Content")
        (tmp_path / "section-2.md").write_text("   \n\n  ")  # Whitespace only

        output = tmp_path / "output.md"
        stats = assemble_review(
            output_file=output,
            section_files=[tmp_path / "section-1.md", tmp_path / "section-2.md"],
            title="Test",
        )

        assert len(stats['warnings']) == 1
        assert "Empty section" in stats['warnings'][0]
        assert len(stats['sections']) == 1  # Only non-empty section counted

    def test_strips_section_frontmatter(self, tmp_path):
        """Frontmatter in individual sections is removed."""
        (tmp_path / "section-1.md").write_text('---\ntitle: "Old"\n---\n\n## Real Content')

        output = tmp_path / "output.md"
        assemble_review(
            output_file=output,
            section_files=[tmp_path / "section-1.md"],
            title="New Title",
        )

        content = output.read_text()
        # Should have new frontmatter, not old
        assert 'title: New Title\n' in content
        assert 'title: "Old"' not in content
        assert "## Real Content" in content

    def test_missing_section_raises(self, tmp_path):
        """Missing section files raise FileNotFoundError."""
        (tmp_path / "section-1.md").write_text("## Exists")

        output = tmp_path / "output.md"
        with pytest.raises(FileNotFoundError, match="Section file not found"):
            assemble_review(
                output_file=output,
                section_files=[tmp_path / "section-1.md", tmp_path / "nonexistent.md"],
                title="Test",
            )

    def test_title_with_special_yaml_chars(self, tmp_path):
        """Titles with YAML special characters are properly escaped."""
        (tmp_path / "section-1.md").write_text("## Content")

        output = tmp_path / "output.md"
        # Title with colons, quotes, and newline-like content
        assemble_review(
            output_file=output,
            section_files=[tmp_path / "section-1.md"],
            title='Philosophy: "What is Truth?" - A Review',
        )

        content = output.read_text()
        # Verify valid YAML can be parsed
        import yaml
        # Extract frontmatter
        assert content.startswith('---\n')
        end = content.find('\n---\n', 4)
        frontmatter_str = content[4:end]
        parsed = yaml.safe_load(frontmatter_str)
        assert parsed['title'] == 'Philosophy: "What is Truth?" - A Review'

    def test_single_blank_line_between_sections(self, tmp_path):
        """Sections are separated by exactly one blank line (MD022 compliance)."""
        (tmp_path / "section-1.md").write_text("## One\n\nContent one.")
        (tmp_path / "section-2.md").write_text("## Two\n\nContent two.")

        output = tmp_path / "output.md"
        assemble_review(
            output_file=output,
            section_files=[tmp_path / "section-1.md", tmp_path / "section-2.md"],
            title="Test",
        )

        content = output.read_text()
        # Should not have double blank lines (which would fail MD022)
        assert "\n\n\n" not in content

    def test_no_sections_raises(self, tmp_path):
        """Raises error when no sections provided."""
        output = tmp_path / "output.md"
        with pytest.raises(ValueError, match="No section files"):
            assemble_review(output_file=output, section_files=[], title="Test")

    def test_utf8_preserved(self, tmp_path):
        """UTF-8 characters are preserved."""
        (tmp_path / "section-1.md").write_text("## Über Philosophie\n\nCafé résumé.", encoding='utf-8')

        output = tmp_path / "output.md"
        assemble_review(
            output_file=output,
            section_files=[tmp_path / "section-1.md"],
            title="Test",
        )

        content = output.read_text(encoding='utf-8')
        assert "Über Philosophie" in content
        assert "Café résumé" in content


class TestCLI:
    """Tests for command-line interface."""

    def test_missing_args(self):
        """Should exit with error when args missing."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_missing_title(self, tmp_path):
        """Should exit with error when --title missing."""
        section = tmp_path / "section-1.md"
        section.write_text("## Test")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(tmp_path / "out.md"), str(section)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "title" in result.stderr.lower()

    def test_file_not_found(self, tmp_path):
        """Should exit with error for missing section file."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH),
             str(tmp_path / "out.md"),
             "--title", "Test",
             str(tmp_path / "nonexistent.md")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_success_output(self, tmp_path):
        """Successful run reports summary."""
        section = tmp_path / "section-1.md"
        section.write_text("## Introduction\n\nContent here.")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH),
             str(tmp_path / "out.md"),
             "--title", "Test Review",
             str(section)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Assembled 1 section" in result.stdout
        assert "section-1.md" in result.stdout
        assert "bytes" in result.stdout

    def test_date_flag(self, tmp_path):
        """--date flag sets the date in frontmatter."""
        section = tmp_path / "section-1.md"
        section.write_text("## Content")
        output = tmp_path / "out.md"

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH),
             str(output),
             "--title", "Test",
             "--date", "2025-06-15",
             str(section)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        content = output.read_text()
        assert "2025-06-15" in content


class TestBuildFrontmatter:
    """The ADOPTed service builder (its 098a57f) plus the --title/--date
    validation decided 2026-08-08 - landed as ONE change so the service
    receives a validated builder at its next re-vendor pin.

    Grammar parity is the constraint (the service consumer's
    validate_title): title invalid when longer than 160 after NFC+trim or
    containing Cc/Cf/Zl/Zp; invalid values are DROPPED with a bounded
    warning, never sanitized - a producer that strips could emit a title
    the consumer's grammar would never have accepted from the original
    input. --date must be exact YYYY-MM-DD. The serialized block must stay
    within the consumer's 50-line/2 KB caps."""

    def test_no_subfield_output_identical_to_historical(self):
        from assemble_review import build_frontmatter
        block = build_frontmatter("Epistemic Autonomy and AI", "2026-08-09")
        assert block == (
            "---\n"
            "title: Epistemic Autonomy and AI\n"
            "date: '2026-08-09'\n"
            "---"
        )

    def test_valid_subfield_emitted(self):
        import yaml
        from assemble_review import build_frontmatter
        block = build_frontmatter("T", "2026-08-09",
                                  subfield="Political Philosophy")
        parsed = yaml.safe_load(block.strip("-\n").replace("---", ""))
        assert parsed["subfield"] == "Political Philosophy"

    def test_invalid_subfield_dropped_with_bounded_warning(self, capsys):
        from assemble_review import build_frontmatter
        bad = "not;a;subfield" + ("x" * 10_000)
        block = build_frontmatter("T", "2026-08-09", subfield=bad)
        assert "subfield" not in block
        err = capsys.readouterr().err
        assert "subfield" in err
        # Bounded: the 10,000-char value must not be echoed into logs.
        assert len(err) < 300

    def test_overlong_title_dropped_not_truncated(self, capsys):
        from assemble_review import build_frontmatter
        long_title = "t" * 10_000
        block = build_frontmatter(long_title, "2026-08-09")
        assert "title" not in block
        assert "ttt" not in block  # not sanitized INTO the block either
        err = capsys.readouterr().err
        assert "title" in err
        assert "10000" in err     # the length is loggable...
        assert "ttt" not in err   # ...the text is not

    def test_title_at_the_160_boundary_kept(self):
        from assemble_review import build_frontmatter
        block = build_frontmatter("t" * 160, "2026-08-09")
        assert "title" in block

    def test_title_with_format_control_chars_dropped(self, capsys):
        """Cf covers the bidi override; Cc covers newline/tab (multiline)."""
        from assemble_review import build_frontmatter
        for bad in ("evil ‮ title", "two\nlines"):
            block = build_frontmatter(bad, "2026-08-09")
            assert "title" not in block, bad

    def test_title_nfc_normalized_and_trimmed(self):
        from assemble_review import build_frontmatter
        block = build_frontmatter("  Café Ethics  ", "2026-08-09")
        assert "Café Ethics" in block
        assert "  Caf" not in block

    def test_invalid_date_dropped_with_warning(self, capsys):
        from assemble_review import build_frontmatter
        for bad in ("August 9, 2026", "2026-8-9", "2026-13-45"):
            block = build_frontmatter("T", bad)
            assert "date" not in block, bad
        err = capsys.readouterr().err
        assert "date" in err

    def test_maximal_valid_inputs_stay_within_consumer_caps(self):
        from assemble_review import build_frontmatter
        block = build_frontmatter("t" * 160, "2026-08-09",
                                  subfield="s" * 59 + "x")
        assert len(block.encode("utf-8")) <= 2048
        assert block.count("\n") + 1 <= 50

    def test_assemble_review_passes_subfield_through(self, tmp_path):
        import yaml
        from assemble_review import assemble_review
        section = tmp_path / "section-1.md"
        section.write_text("## One\n\nBody.\n", encoding="utf-8")
        out = tmp_path / "review.md"
        assemble_review(out, [section], "T", review_date="2026-08-09",
                        subfield="Ethics")
        text = out.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text.split("---")[1])
        assert parsed == {"title": "T", "date": "2026-08-09",
                          "subfield": "Ethics"}
