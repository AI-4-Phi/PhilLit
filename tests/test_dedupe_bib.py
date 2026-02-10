"""Tests for dedupe_bib.py - BibTeX deduplication script."""

import subprocess
import sys
from pathlib import Path

import pytest

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent.parent / ".claude" / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dedupe_bib import (
    _extract_keywords_value, parse_importance, upgrade_importance,
    extract_doi, deduplicate_bib, check_intra_entry_duplicates,
    has_abstract, has_incomplete_flag, remove_incomplete_flag, merge_entries
)


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
def sample_entry_medium_in_title():
    """BibTeX entry with 'Medium' in title and 'Low' in keywords."""
    return """@article{schaffer2009medium,
  author = {Schaffer, Jonathan},
  title = {Medium-sized Objects and the Problem of Composition},
  year = {2009},
  keywords = {mereology, Low}
}"""


@pytest.fixture
def sample_entry_high_in_abstract():
    """BibTeX entry with 'High' in abstract and 'Medium' in keywords."""
    return """@article{korsgaard2008constitution,
  author = {Korsgaard, Christine M.},
  title = {The Constitution of Agency},
  year = {2008},
  abstract = {This paper develops a High-level account of agency and its relation to moral responsibility.},
  keywords = {agency, Medium}
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
        assert parse_importance(sample_entry_high) == 'High'

    def test_medium(self, sample_entry_medium):
        assert parse_importance(sample_entry_medium) == 'Medium'

    def test_low(self, sample_entry_low):
        assert parse_importance(sample_entry_low) == 'Low'

    def test_missing_returns_low(self):
        entry = "@article{test,\n  title = {Test},\n  keywords = {topic}\n}"
        assert parse_importance(entry) == 'Low'

    def test_no_keywords_returns_low(self):
        entry = "@article{test,\n  title = {Test}\n}"
        assert parse_importance(entry) == 'Low'

    def test_parse_importance_ignores_title(self, sample_entry_medium_in_title):
        """'Medium' in title should NOT be detected; keywords has 'Low'."""
        assert parse_importance(sample_entry_medium_in_title) == 'Low'

    def test_parse_importance_ignores_abstract(self, sample_entry_high_in_abstract):
        """'High' in abstract should NOT be detected; keywords has 'Medium'."""
        assert parse_importance(sample_entry_high_in_abstract) == 'Medium'


# =============================================================================
# Tests for upgrade_importance
# =============================================================================

class TestUpgradeImportance:
    """Tests for upgrade_importance function."""

    def test_medium_to_high(self, sample_entry_medium):
        result = upgrade_importance(sample_entry_medium, 'High')
        assert 'High' in result
        assert 'Medium' not in result

    def test_low_to_high(self, sample_entry_low):
        result = upgrade_importance(sample_entry_low, 'High')
        assert 'High' in result
        assert 'Low' not in result

    def test_low_to_medium(self, sample_entry_low):
        result = upgrade_importance(sample_entry_low, 'Medium')
        assert 'Medium' in result
        assert 'Low' not in result

    def test_no_existing_importance(self):
        entry = "@article{test,\n  title = {Test},\n  keywords = {topic}\n}"
        result = upgrade_importance(entry, 'High')
        assert result == entry

    def test_upgrade_importance_preserves_title(self, sample_entry_medium_in_title):
        """Upgrading Low->High in keywords must NOT touch 'Medium' in title."""
        result = upgrade_importance(sample_entry_medium_in_title, 'High')
        assert 'Medium-sized Objects' in result  # title intact
        assert 'High' in _extract_keywords_value(result)
        assert 'Low' not in _extract_keywords_value(result)


# =============================================================================
# Tests for extract_doi
# =============================================================================

class TestExtractDoi:
    """Tests for extract_doi function."""

    def test_bare_doi(self):
        entry = '@article{test,\n  doi = {10.1007/s13347-021-00449-4}\n}'
        assert extract_doi(entry) == '10.1007/s13347-021-00449-4'

    def test_url_prefix_https(self):
        entry = '@article{test,\n  doi = {https://doi.org/10.1007/s13347}\n}'
        assert extract_doi(entry) == '10.1007/s13347'

    def test_url_prefix_dx(self):
        entry = '@article{test,\n  doi = {https://dx.doi.org/10.1007/s13347}\n}'
        assert extract_doi(entry) == '10.1007/s13347'

    def test_case_insensitive(self):
        entry = '@article{test,\n  doi = {10.1007/S13347-021-00449-4}\n}'
        assert extract_doi(entry) == '10.1007/s13347-021-00449-4'

    def test_no_doi_field(self):
        entry = '@article{test,\n  title = {No DOI here}\n}'
        assert extract_doi(entry) is None

    def test_whitespace_handling(self):
        entry = '@article{test,\n  doi = {  10.1007/s13347  }\n}'
        assert extract_doi(entry) == '10.1007/s13347'

    def test_doi_field_case_insensitive(self):
        entry = '@article{test,\n  DOI = {10.1007/s13347}\n}'
        assert extract_doi(entry) == '10.1007/s13347'


# =============================================================================
# Tests for abstract handling
# =============================================================================

class TestHasAbstract:
    """Tests for has_abstract function."""

    def test_has_abstract_true(self):
        entry = '@article{test,\n  abstract = {This is a substantial abstract with enough content.}\n}'
        assert has_abstract(entry) is True

    def test_has_abstract_false(self):
        entry = '@article{test,\n  keywords = {High}\n}'
        assert has_abstract(entry) is False

    def test_has_abstract_empty(self):
        entry = '@article{test,\n  abstract = {}\n}'
        assert has_abstract(entry) is False

    def test_has_abstract_too_short(self):
        entry = '@article{test,\n  abstract = {Short.}\n}'
        assert has_abstract(entry) is False


class TestHasIncompleteFlag:
    """Tests for has_incomplete_flag function."""

    def test_has_incomplete_true(self):
        entry = '@article{test,\n  keywords = {topic, INCOMPLETE, no-abstract}\n}'
        assert has_incomplete_flag(entry) is True

    def test_has_incomplete_false(self):
        entry = '@article{test,\n  keywords = {topic, High}\n}'
        assert has_incomplete_flag(entry) is False

    def test_has_incomplete_flag_ignores_abstract(self):
        """INCOMPLETE in abstract text should NOT trigger the flag."""
        entry = '@article{test,\n  abstract = {This INCOMPLETE draft discusses moral agency.},\n  keywords = {topic, High}\n}'
        assert has_incomplete_flag(entry) is False


class TestRemoveIncompleteFlag:
    """Tests for remove_incomplete_flag function."""

    def test_removes_incomplete(self):
        entry = '@article{test,\n  keywords = {topic, INCOMPLETE, other}\n}'
        result = remove_incomplete_flag(entry)
        assert "INCOMPLETE" not in result
        assert "topic" in result
        assert "other" in result

    def test_removes_no_abstract(self):
        entry = '@article{test,\n  keywords = {topic, no-abstract, other}\n}'
        result = remove_incomplete_flag(entry)
        assert "no-abstract" not in result

    def test_cleans_up_commas(self):
        entry = '@article{test,\n  keywords = {INCOMPLETE, topic}\n}'
        result = remove_incomplete_flag(entry)
        assert ",," not in result
        assert "{," not in result

    def test_preserves_abstract_with_incomplete_text(self):
        """INCOMPLETE in abstract must not be touched when removing from keywords."""
        entry = '@article{test,\n  abstract = {This INCOMPLETE draft discusses moral agency.},\n  keywords = {topic, INCOMPLETE, no-abstract}\n}'
        result = remove_incomplete_flag(entry)
        assert "INCOMPLETE" not in _extract_keywords_value(result)
        assert "This INCOMPLETE draft discusses moral agency." in result


class TestMergeEntries:
    """Tests for merge_entries function."""

    def test_prefers_entry_with_abstract(self):
        entry_no_abstract = '@article{test,\n  title = {First},\n  keywords = {topic, High}\n}'
        entry_with_abstract = '@article{test,\n  title = {Second},\n  abstract = {This is a substantial abstract with good content.},\n  keywords = {topic, Low}\n}'
        merged, reason, winner = merge_entries(entry_no_abstract, entry_with_abstract)
        assert "Second" in merged
        assert "preferred entry with abstract" in reason
        assert winner == 2

    def test_keeps_entry_with_abstract(self):
        entry_with = '@article{test,\n  title = {First},\n  abstract = {This is a substantial abstract with good content.},\n  keywords = {topic, Medium}\n}'
        entry_without = '@article{test,\n  title = {Second},\n  keywords = {topic, High}\n}'
        merged, reason, winner = merge_entries(entry_with, entry_without)
        assert "First" in merged
        assert "kept entry with abstract" in reason
        assert winner == 1

    def test_upgrades_importance_when_preferring_abstract(self):
        entry_high = '@article{test,\n  title = {No Abstract},\n  keywords = {topic, High}\n}'
        entry_low_abstract = '@article{test,\n  title = {With Abstract},\n  abstract = {This is a substantial abstract with good content.},\n  keywords = {topic, Low}\n}'
        merged, reason, winner = merge_entries(entry_high, entry_low_abstract)
        assert "With Abstract" in merged
        assert "High" in merged
        assert "upgraded to High" in reason
        assert winner == 2

    def test_removes_incomplete_when_has_abstract(self):
        entry1 = '@article{test,\n  abstract = {This is a substantial abstract with good content.},\n  keywords = {topic, INCOMPLETE, no-abstract, High}\n}'
        entry2 = '@article{test,\n  keywords = {topic, Medium}\n}'
        merged, reason, winner = merge_entries(entry1, entry2)
        assert "INCOMPLETE" not in merged
        assert "removed INCOMPLETE flag" in reason
        assert winner == 1

    def test_merge_entries_preserves_title(self):
        """End-to-end: merging entries with 'Medium' in title must not corrupt it."""
        entry1 = '@article{test,\n  title = {Medium-sized Objects and Composition},\n  keywords = {mereology, Low}\n}'
        entry2 = '@article{test,\n  title = {Medium-sized Objects and Composition},\n  abstract = {This is a substantial abstract with good content.},\n  keywords = {mereology, Medium}\n}'
        merged, reason, winner = merge_entries(entry1, entry2)
        assert "Medium-sized Objects" in merged
        assert winner == 2  # has abstract


# =============================================================================
# Tests for deduplicate_bib
# =============================================================================

class TestDeduplicateBib:
    """Tests for deduplicate_bib function."""

    def test_no_duplicates(self, tmp_path, sample_entry_high):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(sample_entry_high)
        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1], output)
        assert duplicates == []
        assert 'rawls1971theory' in output.read_text()

    def test_duplicate_removed(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{same2020key,\n  title = {First Version},\n  keywords = {High}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{same2020key,\n  title = {Second Version},\n  keywords = {Medium}\n}')
        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)
        assert 'same2020key' in duplicates
        content = output.read_text()
        assert content.count('same2020key') == 1
        assert 'First Version' in content

    def test_importance_upgrade(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{test2020key,\n  title = {Test},\n  keywords = {topic, Medium}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{test2020key,\n  title = {Test},\n  keywords = {topic, High}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert 'High' in content
        assert 'Medium' not in content

    def test_importance_not_downgraded(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{test2020key,\n  title = {Test},\n  keywords = {topic, High}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{test2020key,\n  title = {Test},\n  keywords = {topic, Low}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert 'High' in content
        assert 'Low' not in content

    def test_comments_preserved(self, tmp_path, sample_comment, sample_entry_high):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(sample_comment + "\n\n" + sample_entry_high)
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1], output)
        content = output.read_text()
        assert 'DOMAIN: Test Domain' in content
        assert 'rawls1971theory' in content

    def test_utf8_preserved(self, tmp_path, sample_entry_utf8):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(sample_entry_utf8, encoding='utf-8')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1], output)
        content = output.read_text(encoding='utf-8')
        assert 'Müller' in content
        assert 'García' in content

    def test_empty_file_handled(self, tmp_path):
        bib1 = tmp_path / "empty.bib"
        bib1.write_text("")
        bib2 = tmp_path / "test.bib"
        bib2.write_text('@article{test,\n  title = {Test},\n  keywords = {High}\n}')
        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)
        assert duplicates == []

    def test_prefers_abstract_in_dedup(self, tmp_path):
        """Should prefer entry with abstract during deduplication."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{key,\n  title = {No Abstract},\n  keywords = {High}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{key,\n  title = {Abstract Version},\n  abstract = {This is a substantial abstract with good content.},\n  keywords = {Medium}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert "Abstract Version" in content
        assert "No Abstract" not in content
        assert "High" in content  # Should be upgraded

    def test_removes_incomplete_in_dedup(self, tmp_path):
        """Should remove INCOMPLETE flag when merging gives abstract."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{key,\n  title = {Incomplete},\n  keywords = {INCOMPLETE, no-abstract, Medium}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{key,\n  title = {Complete},\n  abstract = {This is a substantial abstract with good content.},\n  keywords = {topic, High}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert "Complete" in content
        assert "INCOMPLETE" not in content

    def test_preserves_abstract_source(self, tmp_path):
        """Should preserve abstract_source field."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{key,\n  title = {Entry},\n  abstract = {This is a substantial abstract with good content.},\n  abstract_source = {openalex},\n  keywords = {High}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1], output)
        content = output.read_text()
        assert "abstract_source = {openalex}" in content


# =============================================================================
# Tests for DOI-based deduplication
# =============================================================================

class TestDOIDeduplication:
    """Tests for DOI-based deduplication in deduplicate_bib."""

    def test_same_doi_different_keys(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{geisslinger2021autonomous,\n  title = {Autonomous Driving Ethics},\n  doi = {10.1007/s13347-021-00449-4},\n  keywords = {ethics, High}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{geisslinger2021trolley,\n  title = {Autonomous Driving Ethics},\n  doi = {10.1007/s13347-021-00449-4},\n  keywords = {regulation, High}\n}')
        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert content.count('10.1007/s13347-021-00449-4') == 1
        assert len([d for d in duplicates if 'geisslinger' in d]) == 1

    def test_doi_dedup_keeps_higher_importance(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{paper2021a,\n  title = {Paper},\n  doi = {10.1234/test},\n  keywords = {topic, Medium}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{paper2021b,\n  title = {Paper},\n  doi = {10.1234/test},\n  keywords = {topic, High}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert 'paper2021b' in content
        assert 'paper2021a' not in content

    def test_doi_url_prefix_normalized(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{alpha2021,\n  title = {Paper},\n  doi = {10.1234/test},\n  keywords = {High}\n}')
        bib2 = tmp_path / "test2.bib"
        bib2.write_text('@article{beta2021,\n  title = {Paper},\n  doi = {https://doi.org/10.1234/test},\n  keywords = {Medium}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert content.count('10.1234/test') == 1

    def test_entries_without_doi_not_affected(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{nodoi2021a,\n  title = {Paper A},\n  keywords = {High}\n}\n\n@article{nodoi2021b,\n  title = {Paper B},\n  keywords = {Medium}\n}')
        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1], output)
        content = output.read_text()
        assert 'nodoi2021a' in content
        assert 'nodoi2021b' in content
        assert duplicates == []


# =============================================================================
# Tests for check_intra_entry_duplicates
# =============================================================================

class TestCheckIntraEntryDuplicates:
    """Tests for the intra-entry duplicate field warning check."""

    def test_clean_content(self):
        content = '@article{clean2020,\n  author = {Clean, Author},\n  title = {Clean Paper},\n  year = {2020}\n}'
        assert check_intra_entry_duplicates(content) == []

    def test_duplicate_note_detected(self):
        content = '@misc{test2023,\n  author = {Test, Author},\n  title = {Test},\n  year = {2023},\n  note = {arXiv:1234.5678},\n  note = {This paper argues something.}\n}'
        warnings = check_intra_entry_duplicates(content)
        assert len(warnings) == 1
        assert "note" in warnings[0]

    def test_comment_ignored(self):
        content = '@comment{\n  note = {a},\n  note = {b}\n}'
        assert check_intra_entry_duplicates(content) == []

    def test_deduplicate_bib_calls_check(self, tmp_path, capsys):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@misc{dup2023,\n  author = {Dup, Author},\n  title = {Dup},\n  year = {2023},\n  note = {arXiv:1234.5678},\n  note = {Annotation.}\n}')
        output = tmp_path / "output.bib"
        deduplicate_bib([bib1], output)
        captured = capsys.readouterr()
        assert "WARN" in captured.out
        assert "note" in captured.out


# =============================================================================
# Tests for CLI (main function)
# =============================================================================

class TestCLI:
    """Tests for command-line interface."""

    def test_missing_args(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py")],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout

    def test_file_not_found(self, tmp_path):
        output = tmp_path / "output.bib"
        nonexistent = tmp_path / "nonexistent.bib"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py"),
             str(output), str(nonexistent)],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stdout

    def test_success(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{test2020,\n  title = {Test},\n  keywords = {High}\n}')
        output = tmp_path / "output.bib"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py"),
             str(output), str(bib1)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert output.exists()

    def test_reports_duplicates(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text("@article{dup,\n  keywords = {High}\n}")
        bib2 = tmp_path / "test2.bib"
        bib2.write_text("@article{dup,\n  keywords = {Medium}\n}")
        output = tmp_path / "output.bib"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "dedupe_bib.py"),
             str(output), str(bib1), str(bib2)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "1 duplicate" in result.stdout or "[DEDUPE]" in result.stdout
