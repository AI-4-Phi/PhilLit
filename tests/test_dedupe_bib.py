"""Tests for dedupe_bib.py - BibTeX deduplication script."""

import subprocess
import sys
from pathlib import Path

import pytest

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent.parent / ".claude" / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dedupe_bib import parse_importance, upgrade_importance, extract_doi, deduplicate_bib, check_intra_entry_duplicates


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_entry_high():
    """BibTeX entry with High importance."""
    return """@article{rawls1971theory,
  author = {Rawls, John},
  title = {A Theory of Justice},
  year = {1971},
  keywords = {contractualism, High}
}"""


@pytest.fixture
def sample_entry_medium():
    """BibTeX entry with Medium importance."""
    return """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  year = {1971},
  keywords = {free-will, Medium}
}"""


@pytest.fixture
def sample_entry_low():
    """BibTeX entry with Low importance."""
    return """@article{test2020paper,
  author = {Test, Author},
  title = {A Test Paper},
  year = {2020},
  keywords = {testing, Low}
}"""


@pytest.fixture
def sample_comment():
    """BibTeX @comment block (domain metadata)."""
    return """@comment{
====================================================================
DOMAIN: Test Domain
SEARCH_DATE: 2024-01-01
PAPERS_FOUND: 5 total (High: 2, Medium: 2, Low: 1)
====================================================================
}"""


@pytest.fixture
def sample_entry_utf8():
    """BibTeX entry with UTF-8 characters in author name."""
    return """@article{muller2020ethics,
  author = {Müller, Hans-Georg and García, María},
  title = {Éthique et Philosophie},
  year = {2020},
  keywords = {ethics, High}
}"""


# =============================================================================
# Tests for parse_importance
# =============================================================================

class TestParseImportance:
    """Tests for parse_importance function."""

    def test_high(self, sample_entry_high):
        """Should extract High importance."""
        assert parse_importance(sample_entry_high) == 'High'

    def test_medium(self, sample_entry_medium):
        """Should extract Medium importance."""
        assert parse_importance(sample_entry_medium) == 'Medium'

    def test_low(self, sample_entry_low):
        """Should extract Low importance."""
        assert parse_importance(sample_entry_low) == 'Low'

    def test_missing_returns_low(self):
        """Should return Low when no importance found."""
        entry = "@article{test,\n  title = {Test},\n  keywords = {topic}\n}"
        assert parse_importance(entry) == 'Low'

    def test_no_keywords_returns_low(self):
        """Should return Low when no keywords field."""
        entry = "@article{test,\n  title = {Test}\n}"
        assert parse_importance(entry) == 'Low'


# =============================================================================
# Tests for upgrade_importance
# =============================================================================

class TestUpgradeImportance:
    """Tests for upgrade_importance function."""

    def test_medium_to_high(self, sample_entry_medium):
        """Should upgrade Medium to High."""
        result = upgrade_importance(sample_entry_medium, 'High')
        assert 'High' in result
        assert 'Medium' not in result

    def test_low_to_high(self, sample_entry_low):
        """Should upgrade Low to High."""
        result = upgrade_importance(sample_entry_low, 'High')
        assert 'High' in result
        assert 'Low' not in result

    def test_low_to_medium(self, sample_entry_low):
        """Should upgrade Low to Medium."""
        result = upgrade_importance(sample_entry_low, 'Medium')
        assert 'Medium' in result
        assert 'Low' not in result

    def test_no_existing_importance(self):
        """Should return entry unchanged if no importance to replace."""
        entry = "@article{test,\n  title = {Test},\n  keywords = {topic}\n}"
        result = upgrade_importance(entry, 'High')
        assert result == entry  # Unchanged


# =============================================================================
# Tests for deduplicate_bib
# =============================================================================

class TestDeduplicateBib:
    """Tests for deduplicate_bib function."""

    def test_no_duplicates(self, tmp_path, sample_entry_high):
        """Single file with no duplicates should preserve all entries."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(sample_entry_high)

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1], output)

        assert duplicates == []
        assert output.exists()
        content = output.read_text()
        assert 'rawls1971theory' in content

    def test_duplicate_removed(self, tmp_path):
        """Duplicate key should be removed, first entry kept."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{same2020key,
  title = {First Version},
  keywords = {High}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{same2020key,
  title = {Second Version},
  keywords = {Medium}
}""")

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)

        assert 'same2020key' in duplicates
        content = output.read_text()
        assert content.count('same2020key') == 1
        assert 'First Version' in content  # First entry kept
        assert 'Second Version' not in content

    def test_importance_upgrade(self, tmp_path):
        """Duplicate with higher importance should upgrade first entry."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{test2020key,
  title = {Test Paper},
  keywords = {topic, Medium}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{test2020key,
  title = {Test Paper},
  keywords = {topic, High}
}""")

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)

        assert 'test2020key' in duplicates
        content = output.read_text()
        assert 'High' in content  # Upgraded
        assert 'Medium' not in content

    def test_importance_not_downgraded(self, tmp_path):
        """Duplicate with lower importance should not downgrade first entry."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{test2020key,
  title = {Test Paper},
  keywords = {topic, High}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{test2020key,
  title = {Test Paper},
  keywords = {topic, Low}
}""")

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)

        assert 'test2020key' in duplicates
        content = output.read_text()
        assert 'High' in content  # Not downgraded
        assert 'Low' not in content

    def test_comments_preserved(self, tmp_path, sample_comment, sample_entry_high):
        """@comment blocks should be preserved."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(sample_comment + "\n\n" + sample_entry_high)

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1], output)

        assert duplicates == []
        content = output.read_text()
        assert 'DOMAIN: Test Domain' in content
        assert 'rawls1971theory' in content

    def test_multiple_comments_preserved(self, tmp_path, sample_comment):
        """@comment blocks from multiple files should all be preserved."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(sample_comment.replace("Test Domain", "Domain 1"))

        bib2 = tmp_path / "test2.bib"
        bib2.write_text(sample_comment.replace("Test Domain", "Domain 2"))

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)

        content = output.read_text()
        assert 'Domain 1' in content
        assert 'Domain 2' in content

    def test_utf8_preserved(self, tmp_path, sample_entry_utf8):
        """UTF-8 characters should be preserved."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(sample_entry_utf8, encoding='utf-8')

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1], output)

        content = output.read_text(encoding='utf-8')
        assert 'Müller' in content
        assert 'García' in content
        assert 'Éthique' in content

    def test_multiple_duplicates(self, tmp_path):
        """Multiple different duplicate keys should all be handled."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{key1,
  title = {First},
  keywords = {High}
}

@article{key2,
  title = {Second},
  keywords = {Medium}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{key1,
  title = {First Dup},
  keywords = {Low}
}

@article{key2,
  title = {Second Dup},
  keywords = {High}
}""")

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)

        assert 'key1' in duplicates
        assert 'key2' in duplicates
        assert len(duplicates) == 2

        content = output.read_text()
        assert content.count('key1') == 1
        assert content.count('key2') == 1

    def test_empty_file_handled(self, tmp_path):
        """Empty bib file should be handled gracefully."""
        bib1 = tmp_path / "empty.bib"
        bib1.write_text("")

        bib2 = tmp_path / "test.bib"
        bib2.write_text("""@article{test,
  title = {Test},
  keywords = {High}
}""")

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)

        assert duplicates == []
        content = output.read_text()
        assert 'test' in content


# =============================================================================
# Tests for CLI (main function)
# =============================================================================

class TestCLI:
    """Tests for command-line interface."""

    def test_missing_args(self):
        """Should exit with error when args missing."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout

    def test_file_not_found(self, tmp_path):
        """Should exit with error for missing input file."""
        output = tmp_path / "output.bib"
        nonexistent = tmp_path / "nonexistent.bib"

        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py"),
             str(output), str(nonexistent)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stdout

    def test_success(self, tmp_path):
        """Should run successfully with valid inputs."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{test2020,
  title = {Test},
  keywords = {High}
}""")

        output = tmp_path / "output.bib"

        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py"),
             str(output), str(bib1)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert output.exists()

    def test_reports_duplicates(self, tmp_path):
        """Should report duplicate count in output."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("@article{dup,\n  keywords = {High}\n}")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("@article{dup,\n  keywords = {Medium}\n}")

        output = tmp_path / "output.bib"

        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py"),
             str(output), str(bib1), str(bib2)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "1 duplicate" in result.stdout or "[DEDUPE]" in result.stdout


# =============================================================================
# Tests for extract_doi
# =============================================================================

class TestExtractDoi:
    """Tests for extract_doi function."""

    def test_bare_doi(self):
        """Should extract a plain DOI."""
        entry = '@article{test,\n  doi = {10.1007/s13347-021-00449-4}\n}'
        assert extract_doi(entry) == '10.1007/s13347-021-00449-4'

    def test_url_prefix_https(self):
        """Should strip https://doi.org/ prefix."""
        entry = '@article{test,\n  doi = {https://doi.org/10.1007/s13347}\n}'
        assert extract_doi(entry) == '10.1007/s13347'

    def test_url_prefix_dx(self):
        """Should strip https://dx.doi.org/ prefix."""
        entry = '@article{test,\n  doi = {https://dx.doi.org/10.1007/s13347}\n}'
        assert extract_doi(entry) == '10.1007/s13347'

    def test_case_insensitive(self):
        """DOI should be lowercased."""
        entry = '@article{test,\n  doi = {10.1007/S13347-021-00449-4}\n}'
        assert extract_doi(entry) == '10.1007/s13347-021-00449-4'

    def test_no_doi_field(self):
        """Should return None when no doi field exists."""
        entry = '@article{test,\n  title = {No DOI here}\n}'
        assert extract_doi(entry) is None

    def test_whitespace_handling(self):
        """Should strip whitespace around DOI value."""
        entry = '@article{test,\n  doi = {  10.1007/s13347  }\n}'
        assert extract_doi(entry) == '10.1007/s13347'

    def test_doi_field_case_insensitive(self):
        """Should match DOI field regardless of case."""
        entry = '@article{test,\n  DOI = {10.1007/s13347}\n}'
        assert extract_doi(entry) == '10.1007/s13347'


# =============================================================================
# Tests for DOI-based deduplication
# =============================================================================

class TestDOIDeduplication:
    """Tests for DOI-based deduplication in deduplicate_bib."""

    def test_same_doi_different_keys(self, tmp_path):
        """Two entries with same DOI but different keys should be deduplicated."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{geisslinger2021autonomous,
  title = {Autonomous Driving Ethics},
  doi = {10.1007/s13347-021-00449-4},
  keywords = {ethics, High}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{geisslinger2021trolley,
  title = {Autonomous Driving Ethics},
  doi = {10.1007/s13347-021-00449-4},
  keywords = {regulation, High}
}""")

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)

        content = output.read_text()
        # Only one entry should survive
        assert content.count('10.1007/s13347-021-00449-4') == 1
        assert 'geisslinger2021' in content
        assert len([d for d in duplicates if 'geisslinger' in d]) == 1

    def test_doi_dedup_keeps_higher_importance(self, tmp_path):
        """DOI dedup should keep the higher-importance entry."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{paper2021a,
  title = {Paper},
  doi = {10.1234/test},
  keywords = {topic, Medium}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{paper2021b,
  title = {Paper},
  doi = {10.1234/test},
  keywords = {topic, High}
}""")

        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)

        content = output.read_text()
        assert 'paper2021b' in content  # High importance wins
        assert 'paper2021a' not in content

    def test_doi_url_prefix_normalized(self, tmp_path):
        """DOIs with URL prefixes should match bare DOIs."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{alpha2021,
  title = {Paper},
  doi = {10.1234/test},
  keywords = {High}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{beta2021,
  title = {Paper},
  doi = {https://doi.org/10.1234/test},
  keywords = {Medium}
}""")

        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)

        content = output.read_text()
        assert content.count('10.1234/test') == 1

    def test_entries_without_doi_not_affected(self, tmp_path):
        """Entries without DOI fields should pass through unaffected."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{nodoi2021a,
  title = {Paper A},
  keywords = {High}
}

@article{nodoi2021b,
  title = {Paper B},
  keywords = {Medium}
}""")

        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1], output)

        content = output.read_text()
        assert 'nodoi2021a' in content
        assert 'nodoi2021b' in content
        assert duplicates == []

    def test_mixed_doi_and_no_doi(self, tmp_path):
        """DOI dedup should not interfere with entries lacking DOIs."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@article{with_doi_a,
  title = {Same Paper},
  doi = {10.1234/test},
  keywords = {High}
}

@article{no_doi,
  title = {Different Paper},
  keywords = {Medium}
}""")

        bib2 = tmp_path / "test2.bib"
        bib2.write_text("""@article{with_doi_b,
  title = {Same Paper},
  doi = {10.1234/test},
  keywords = {Medium}
}""")

        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)

        content = output.read_text()
        assert 'with_doi_a' in content  # Higher importance
        assert 'with_doi_b' not in content  # Deduped
        assert 'no_doi' in content  # Unaffected


# =============================================================================
# Tests for check_intra_entry_duplicates
# =============================================================================

class TestCheckIntraEntryDuplicates:
    """Tests for the intra-entry duplicate field warning check."""

    def test_clean_content(self):
        """Should return no warnings for clean content."""
        content = """@article{clean2020,
  author = {Clean, Author},
  title = {Clean Paper},
  journal = {Good Journal},
  year = {2020}
}"""
        warnings = check_intra_entry_duplicates(content)
        assert warnings == []

    def test_duplicate_note_detected(self):
        """Should warn about duplicate note fields."""
        content = """@misc{test2023,
  author = {Test, Author},
  title = {Test},
  year = {2023},
  note = {arXiv:1234.5678},
  note = {This paper argues something.}
}"""
        warnings = check_intra_entry_duplicates(content)
        assert len(warnings) == 1
        assert "note" in warnings[0]
        assert "test2023" in warnings[0]

    def test_comment_ignored(self):
        """Should not warn about fields in @comment blocks."""
        content = """@comment{
  note = {a},
  note = {b}
}"""
        warnings = check_intra_entry_duplicates(content)
        assert warnings == []

    def test_deduplicate_bib_calls_check(self, tmp_path, capsys):
        """deduplicate_bib should call check_intra_entry_duplicates and print warnings."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("""@misc{dup2023,
  author = {Dup, Author},
  title = {Dup Paper},
  year = {2023},
  note = {arXiv:1234.5678},
  note = {Annotation.}
}""")
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1], output)

        captured = capsys.readouterr()
        assert "WARN" in captured.out
        assert "note" in captured.out
