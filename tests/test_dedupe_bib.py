"""Tests for dedupe_bib.py - BibTeX deduplication script."""

import subprocess
import sys
from pathlib import Path

import pytest

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent.parent / ".claude" / "skills" / "literature-review"
sys.path.insert(0, str(SCRIPT_DIR))

from dedupe_bib import parse_importance, upgrade_importance, deduplicate_bib


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
