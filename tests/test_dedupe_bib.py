"""Tests for dedupe_bib.py - BibTeX deduplication script."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

SCRIPT_PATH = SCRIPT_DIR / "dedupe_bib.py"

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

    def test_quote_delimited_doi(self):
        entry = '@article{simpsonmuller2016justwar,\n  doi = "10.1093/pq/pqv075"\n}'
        assert extract_doi(entry) == '10.1093/pq/pqv075'

    def test_brace_delimited_doi_still_works(self):
        entry = '@article{simpsonMuller2015justwar,\n  doi = {10.1093/pq/pqv075}\n}'
        assert extract_doi(entry) == '10.1093/pq/pqv075'

    def test_quote_delimited_doi_with_url_prefix(self):
        entry = '@article{test,\n  doi = "https://doi.org/10.x/y"\n}'
        assert extract_doi(entry) == '10.x/y'


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

    def test_mixed_delimiter_same_doi_different_years(self, tmp_path):
        """Same DOI, different citekeys AND different years, one quote-delimited
        and one brace-delimited: must still collapse to a single entry."""
        bib1 = tmp_path / "test1.bib"
        bib1.write_text(
            '@article{simpsonmuller2016justwar,\n'
            '  title = {Just War and Guerrilla War},\n'
            '  year = {2016},\n'
            '  doi = "10.1093/pq/pqv075",\n'
            '  keywords = {war, Medium}\n'
            '}'
        )
        bib2 = tmp_path / "test2.bib"
        bib2.write_text(
            '@article{simpsonMuller2015justwar,\n'
            '  title = {Just War and Guerrilla War},\n'
            '  year = {2015},\n'
            '  doi = {10.1093/pq/pqv075},\n'
            '  keywords = {war, High}\n'
            '}'
        )
        output = tmp_path / "output.bib"
        duplicates = deduplicate_bib([bib1, bib2], output)
        content = output.read_text()
        assert content.count('10.1093/pq/pqv075') == 1
        assert len([d for d in duplicates
                    if 'simpsonmuller2016justwar' in d or 'simpsonMuller2015justwar' in d]) == 1

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

    def test_no_evidence_report_warns_on_stderr(self, tmp_path):
        bib1 = tmp_path / "test1.bib"
        bib1.write_text('@article{test2020,\n  title = {Test},\n  keywords = {High}\n}')
        output = tmp_path / "output.bib"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(output), str(bib1)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "no --evidence-report" in result.stderr

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


# =============================================================================
# Tests for _SUBSTANTIVE_FIELDS (context fields; sync with generate_bibliography)
# =============================================================================

class TestSubstantiveFieldsIncludeContext:
    def test_context_fields_present(self):
        from dedupe_bib import _SUBSTANTIVE_FIELDS
        assert "sep_context" in _SUBSTANTIVE_FIELDS
        assert "iep_context" in _SUBSTANTIVE_FIELDS

    def test_generate_bibliography_copy_in_sync(self):
        import dedupe_bib
        import generate_bibliography
        assert set(dedupe_bib._SUBSTANTIVE_FIELDS) == set(generate_bibliography._SUBSTANTIVE_FIELDS)


# =============================================================================
# Tests for attestation-aware re-stamp (--evidence-report)
# =============================================================================

class TestEvidenceRestamp:
    """CLI-level: two input bibs with title-pass duplicates + a report file,
    run with --evidence-report, assert on the merged file's tier token."""

    def _run_cli(self, tmp_path, bib_a, bib_b, atts_a, atts_b):
        (tmp_path / "a.bib").write_text(bib_a, encoding="utf-8")
        (tmp_path / "b.bib").write_text(bib_b, encoding="utf-8")
        report = tmp_path / "evidence_report.json"
        report.write_text(json.dumps(
            {"schema_version": 1,
             "attestations": {"a.bib": atts_a, "b.bib": atts_b}}), encoding="utf-8")
        out = tmp_path / "merged.bib"
        r = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(out),
             str(tmp_path / "a.bib"), str(tmp_path / "b.bib"),
             "--evidence-report", str(report)],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return out.read_text(encoding="utf-8")

    NO_ATT = {"abstract_attested": False, "abstract_source": None,
              "abstract_sha256": None, "context_written": False,
              "context_field": None, "context_sha256": None,
              "api_matched": False, "verified_identifier": None,
              "verified_identifier_value": None, "breaker_tripped": False}

    def test_context_survives_merge_and_tier_via_loser_attestation(self, tmp_path):
        # A's key carries sep_context + a value-bound context attestation;
        # B's duplicate (different key, same title/year/author) wins on
        # abstract. Union pulls sep_context across; the re-stamp re-verifies
        # A's context hash against the merged value -> CONTEXT... but only if
        # B's unattested abstract does not win ABSTRACT (it must not).
        import stamp_evidence
        ctx_value = "Cited in 'tk' entry: \"Normal science.\""
        a = ('@book{kuhn1962structure,\n  author = {Kuhn, Thomas S.},\n'
             '  title = {The Structure of Scientific Revolutions},\n'
             '  year = {1962},\n'
             '  sep_context = {' + ctx_value + '},\n'
             '  keywords = {ps, High, EVIDENCE-CONTEXT}\n}')
        b = ('@book{kuhn1962,\n  author = {Kuhn, Thomas S.},\n'
             '  title = {The Structure of Scientific Revolutions},\n'
             '  year = {1962},\n  abstract = {A researcher-written abstract.},\n'
             '  abstract_source = {s2},\n'
             '  keywords = {ps, High, EVIDENCE-NONE}\n}')
        att_a = dict(self.NO_ATT, context_written=True,
                     context_field="sep_context",
                     context_sha256=stamp_evidence.abstract_hash(ctx_value))
        merged = self._run_cli(tmp_path, a, b,
                               {"kuhn1962structure": att_a},
                               {"kuhn1962": dict(self.NO_ATT)})
        assert "sep_context" in merged
        assert "EVIDENCE-CONTEXT" in merged
        assert "EVIDENCE-ABSTRACT" not in merged  # forged abstract not laundered
        assert "EVIDENCE-NONE" not in merged

    def test_abstract_laundering_blocked(self, tmp_path):
        # A had a genuinely attested abstract (hash of A's text); B's
        # fabricated abstract wins the merge. A's attestation must NOT
        # authorize B's text: hashes differ -> not ABSTRACT.
        import stamp_evidence
        a = ('@article{smith2020,\n  author = {Smith, Sam},\n'
             '  title = {A Real Study},\n  year = {2020},\n'
             '  keywords = {EVIDENCE-ABSTRACT}\n}')
        b = ('@article{smith2020dup,\n  author = {Smith, Sam},\n'
             '  title = {A Real Study},\n  year = {2020},\n'
             '  abstract = {FABRICATED CLAIMS.},\n  abstract_source = {s2},\n'
             '  keywords = {EVIDENCE-NONE}\n}')
        att_a = dict(self.NO_ATT, abstract_attested=True, abstract_source="s2",
                     abstract_sha256=stamp_evidence.abstract_hash("The genuine abstract text."))
        merged = self._run_cli(tmp_path, a, b, {"smith2020": att_a},
                               {"smith2020dup": dict(self.NO_ATT)})
        assert "EVIDENCE-ABSTRACT" not in merged

    def test_context_laundering_blocked(self, tmp_path):
        # Same-field context laundering: the survivor (B, wins on abstract)
        # carries a FABRICATED sep_context; the loser's (A's) attestation
        # binds sep_context to a DIFFERENT genuine value. A's context_written
        # boolean must NOT authorize B's value: hash mismatch -> not CONTEXT
        # (and B's unattested abstract -> not ABSTRACT) -> NONE.
        import stamp_evidence
        genuine = "Cited in 'real' entry."
        a = ('@book{ctx2018,\n  author = {Ctx, Cal},\n'
             '  title = {A Context Study},\n  year = {2018},\n'
             '  sep_context = {' + genuine + '},\n'
             '  keywords = {High, EVIDENCE-CONTEXT}\n}')
        b = ('@book{ctx2018dup,\n  author = {Ctx, Cal},\n'
             '  title = {A Context Study},\n  year = {2018},\n'
             '  abstract = {An abstract long enough to win the merge.},\n'
             '  sep_context = {FABRICATED CONTEXT CLAIM.},\n'
             '  keywords = {High, EVIDENCE-NONE}\n}')
        att_a = dict(self.NO_ATT, context_written=True,
                     context_field="sep_context",
                     context_sha256=stamp_evidence.abstract_hash(genuine))
        merged = self._run_cli(tmp_path, a, b, {"ctx2018": att_a},
                               {"ctx2018dup": dict(self.NO_ATT)})
        assert "FABRICATED CONTEXT CLAIM" in merged  # B's value won the merge
        assert "EVIDENCE-CONTEXT" not in merged  # A's boolean not laundered
        assert "EVIDENCE-ABSTRACT" not in merged  # B's abstract unattested
        assert "EVIDENCE-NONE" in merged

    def test_resurrected_identifier_on_no_match_entry_stays_none(self, tmp_path):
        # glm-5.2's dedup-resurrection path: loser's doi is unioned into the
        # survivor, but neither key was api-matched -> still NONE.
        a = ('@article{phantom2001data,\n  author = {Phantom, Pia},\n'
             '  title = {A Phantom Data Study},\n  year = {2001},\n'
             '  keywords = {EVIDENCE-NONE}\n}')
        b = ('@article{phantom2001dup,\n  author = {Phantom, Pia},\n'
             '  title = {A Phantom Data Study},\n  year = {2001},\n'
             '  doi = {10.9999/fabricated},\n  keywords = {EVIDENCE-NONE}\n}')
        merged = self._run_cli(tmp_path, a, b,
                               {"phantom2001data": dict(self.NO_ATT)},
                               {"phantom2001dup": dict(self.NO_ATT)})
        assert "EVIDENCE-NONE" in merged
        assert "EVIDENCE-EXISTENCE" not in merged

    def test_merge_takes_highest_tier_across_contributing_keys(self, tmp_path):
        # survivor key unattested; loser key api-matched with verified doi
        # VALUE equal to the merged entry's doi -> EXISTENCE via loser's
        # value-bound attestation
        a = ('@article{real2020,\n  author = {Real, Rae},\n'
             '  title = {A Genuine Empirical Study},\n  year = {2020},\n'
             '  keywords = {EVIDENCE-NONE}\n}')
        b = ('@article{real2020dup,\n  author = {Real, Rae},\n'
             '  title = {A Genuine Empirical Study},\n  year = {2020},\n'
             '  doi = {10.1000/real},\n  keywords = {EVIDENCE-EXISTENCE}\n}')
        att_b = dict(self.NO_ATT, api_matched=True, verified_identifier="doi",
                     verified_identifier_value="10.1000/real")
        merged = self._run_cli(tmp_path, a, b, {"real2020": dict(self.NO_ATT)},
                               {"real2020dup": att_b})
        assert "EVIDENCE-EXISTENCE" in merged

    def test_doi_laundering_blocked(self, tmp_path):
        # loser's attestation verified DOI X; the merged entry ends up with a
        # DIFFERENT doi Y (from the survivor) -> value binding demotes.
        a = ('@article{swap2020,\n  author = {Swap, Sue},\n'
             '  title = {A Study of Swaps},\n  year = {2020},\n'
             '  doi = {10.9999/other},\n  keywords = {EVIDENCE-NONE}\n}')
        b = ('@article{swap2020dup,\n  author = {Swap, Sue},\n'
             '  title = {A Study of Swaps},\n  year = {2020},\n'
             '  keywords = {EVIDENCE-NONE}\n}')
        att_b = dict(self.NO_ATT, api_matched=True, verified_identifier="doi",
                     verified_identifier_value="10.1000/verified")
        merged = self._run_cli(tmp_path, a, b, {"swap2020": dict(self.NO_ATT)},
                               {"swap2020dup": att_b})
        assert "EVIDENCE-EXISTENCE" not in merged

    def test_transitive_merge_chain_carries_attestation(self, tmp_path):
        # chain across two passes: x2 DOI-merges with x1, then x3 title-merges
        # in, contributing sep_context + its value-bound context attestation.
        # The survivor must still reach CONTEXT (transitive merged_from).
        import stamp_evidence
        ctx_value = "Cited in 'chain' entry: \"Described here.\""
        a = ('@article{x1,\n  author = {Chain, Cara},\n'
             '  title = {A Chained Study},\n  year = {2019},\n'
             '  doi = {10.1000/chain},\n  keywords = {EVIDENCE-NONE}\n}')
        b = ('@article{x2,\n  author = {Chain, Cara},\n'
             '  title = {A Chained Study},\n  year = {2019},\n'
             '  doi = {10.1000/chain},\n  keywords = {EVIDENCE-NONE}\n}\n\n'
             '@article{x3,\n  author = {Chain, Cara},\n'
             '  title = {A Chained Study},\n  year = {2019},\n'
             '  sep_context = {' + ctx_value + '},\n'
             '  keywords = {EVIDENCE-CONTEXT}\n}')
        att_x3 = dict(self.NO_ATT, context_written=True,
                      context_field="sep_context",
                      context_sha256=stamp_evidence.abstract_hash(ctx_value))
        merged = self._run_cli(tmp_path, a, b, {"x1": dict(self.NO_ATT)},
                               {"x2": dict(self.NO_ATT), "x3": att_x3})
        assert merged.count("@article") == 1
        assert "EVIDENCE-CONTEXT" in merged


class TestRestampMergedUnreadableReport:
    """Finding 2: an unreadable/corrupt --evidence-report must not silently
    demote every entry to EVIDENCE-NONE -- restamp_merged's except branch
    must warn on stderr so the operator notices."""

    def test_corrupt_report_warns_on_stderr(self, tmp_path):
        bib = tmp_path / "a.bib"
        bib.write_text(
            '@article{smith2020,\n  author = {Smith, Sam},\n'
            '  title = {A Study},\n  year = {2020},\n'
            '  keywords = {EVIDENCE-NONE}\n}', encoding="utf-8")
        report = tmp_path / "evidence_report.json"
        report.write_text("{ not valid json", encoding="utf-8")
        out = tmp_path / "merged.bib"
        r = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(out), str(bib),
             "--evidence-report", str(report)],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "warning: evidence report unreadable" in r.stderr
        assert str(report) in r.stderr


# =============================================================================
# ROADMAP item 4: identity keys come from the one owner (hooks/bib_identity.py)
# =============================================================================

class TestDiacriticInsensitiveTitleDedup:
    """dedupe_bib was the only copy applying no Unicode normalization, so
    accented/unaccented pairs survived dedup in 5/32 delivered reviews."""

    def _entry(self, key: str, author: str) -> str:
        return (
            f"@article{{{key},\n"
            f"  author = {{{author}}},\n"
            "  title = {Moral Status and the Mind},\n"
            "  year = {2020},\n"
            "  journal = {J Phil},\n"
            "}"
        )

    def test_accented_and_unaccented_first_author_are_one_work(self):
        from dedupe_bib import dedupe_by_title_key
        seen = {
            "milliere2020": self._entry("milliere2020", "Millière, Raphaël"),
            "milliere2020a": self._entry("milliere2020a", "Milliere, Raphael"),
        }
        removed = dedupe_by_title_key(seen)
        assert len(seen) == 1, f"expected one survivor, got {sorted(seen)}"
        assert len(removed) == 1

    def test_normalize_title_is_the_shared_owner(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
        import bib_identity
        import dedupe_bib
        assert dedupe_bib._normalize_title is bib_identity.title_key

    def test_non_latin_title_still_yields_a_key(self):
        import dedupe_bib
        entry = (
            "@article{pap2021,\n"
            "  author = {Παπαδόπουλος, Γ.},\n"
            "  title = {Η ηθική της τεχνολογίας},\n"
            "  year = {2021},\n"
            "}"
        )
        assert dedupe_bib._fallback_key(entry) is not None


class TestExtractDoiUsesSharedNormalization:
    """ROADMAP item 4, sixth site: extract_doi carried its own prefix list,
    missing `doi:` and bare `doi.org/`, so those entries keyed differently
    here than in metadata_cleaner / generate_bibliography / stamp_evidence."""

    def test_doi_colon_prefix_is_stripped(self):
        from dedupe_bib import extract_doi
        entry = "@article{a,\n  doi = {doi:10.1000/x},\n}"
        assert extract_doi(entry) == "10.1000/x"

    def test_bare_doi_org_prefix_is_stripped(self):
        from dedupe_bib import extract_doi
        entry = "@article{a,\n  doi = {doi.org/10.1000/x},\n}"
        assert extract_doi(entry) == "10.1000/x"

    def test_url_prefixes_and_case_still_normalize(self):
        from dedupe_bib import extract_doi
        assert extract_doi("@article{a,\n  doi = {https://dx.doi.org/10.1000/X},\n}") == "10.1000/x"

    def test_missing_doi_field_still_returns_none(self):
        from dedupe_bib import extract_doi
        assert extract_doi("@article{a,\n  title = {No DOI Here},\n}") is None

    def test_normalize_doi_is_the_shared_owner(self):
        # extract_doi delegates through the module global, so a future
        # shadowing redefinition would silently restore the sixth-site drift.
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
        import bib_identity
        import dedupe_bib
        assert dedupe_bib.normalize_doi is bib_identity.normalize_doi


QUOTED_ENTRY = '''@article{q,
    author = "B, A",
    title = "T",
    year = "2020",
    abstract = "A perfectly substantial abstract of adequate length.",
    keywords = "High, INCOMPLETE, no-abstract, METADATA\\_CLEANED: pages"
}'''


class TestQuotedFormExtractors:
    """pybtex Writer emits quoted fields; the extractors must read them
    (ROADMAP item 3 A prerequisite - cleaned bibs are quoted-form)."""

    def test_extract_keywords_value_quoted(self):
        from dedupe_bib import _extract_keywords_value
        assert "High" in _extract_keywords_value(QUOTED_ENTRY)

    def test_parse_importance_quoted(self):
        from dedupe_bib import parse_importance
        assert parse_importance(QUOTED_ENTRY) == "High"

    def test_has_abstract_quoted(self):
        from dedupe_bib import has_abstract
        assert has_abstract(QUOTED_ENTRY) is True

    def test_has_incomplete_flag_quoted(self):
        from dedupe_bib import has_incomplete_flag
        assert has_incomplete_flag(QUOTED_ENTRY) is True

    def test_remove_incomplete_flag_quoted(self):
        from dedupe_bib import remove_incomplete_flag, has_incomplete_flag
        out = remove_incomplete_flag(QUOTED_ENTRY)
        assert not has_incomplete_flag(out)
        assert "no-abstract" not in out
        # the rest of the keywords value survives
        assert "High" in out and "METADATA" in out

    def test_upgrade_importance_quoted(self):
        from dedupe_bib import upgrade_importance, parse_importance
        low = QUOTED_ENTRY.replace("High", "Low")
        assert parse_importance(upgrade_importance(low, "High")) == "High"

    def test_braced_form_still_works(self):
        from dedupe_bib import parse_importance, has_abstract
        braced = ('@article{b, author = {A B}, title = {T}, year = {2020},\n'
                  '  abstract = {A perfectly substantial abstract of adequate '
                  'length.},\n  keywords = {Medium}}')
        assert parse_importance(braced) == "Medium"
        assert has_abstract(braced) is True


CLEANED_COPY = '''@inproceedings{iclr_d3,
    author = "Doe, Jane",
    title = "Impossible Publication",
    year = "2024",
    keywords = "Medium, METADATA\\_CLEANED: booktitle"
}'''

UNCLEANED_COPY = '''@inproceedings{iclr_d1,
    author = {Doe, Jane},
    title = {Impossible Publication},
    year = {2024},
    booktitle = {International Conference on Learning Representations},
    abstract = {A substantial abstract that makes this copy win the merge.},
    keywords = {Medium}
}'''


class TestCleanerVerdictPropagation:
    """Item 3 A: a field one domain's evidence flagged unverifiable must not
    ship via an unchecked duplicate."""

    def test_uncleaned_winner_loses_flagged_field(self):
        # The uncleaned copy wins (it has the abstract) - but booktitle,
        # flagged by the cleaned loser, must be stripped from the merge.
        from dedupe_bib import merge_entries
        merged, _reason, winner = merge_entries(CLEANED_COPY, UNCLEANED_COPY)
        assert winner == 2
        assert "International Conference" not in merged
        assert "abstract" in merged.lower()  # winner's own fields survive

    def test_merged_marker_records_propagated_removal(self):
        from dedupe_bib import merge_entries, _extract_keywords_value
        from metadata_cleaner import marker_removed_fields
        merged, _r, _w = merge_entries(CLEANED_COPY, UNCLEANED_COPY)
        assert "booktitle" in marker_removed_fields(
            _extract_keywords_value(merged))

    def test_union_never_reinserts_flagged_field(self):
        # Cleaned copy WINS (give it the abstract); union from the uncleaned
        # loser must not re-insert booktitle.
        from dedupe_bib import merge_entries, _union_substantive_fields_text
        cleaned_with_abs = CLEANED_COPY.replace(
            '"Medium, METADATA\\_CLEANED: booktitle"',
            '"Medium, METADATA\\_CLEANED: booktitle",\n'
            '    abstract = "A substantial abstract that makes this copy win."')
        merged, _r, winner = merge_entries(UNCLEANED_COPY.replace(
            "    abstract = {A substantial abstract that makes this copy "
            "win the merge.},\n", ""), cleaned_with_abs)
        assert winner == 2
        out = _union_substantive_fields_text(merged, UNCLEANED_COPY)
        assert "International Conference" not in out

    def test_unflagged_fields_still_union(self):
        from dedupe_bib import _union_substantive_fields_text
        winner = CLEANED_COPY  # lacks doi; marker flags only booktitle
        loser = UNCLEANED_COPY.replace(
            "booktitle = {International Conference on Learning Representations},",
            "doi = {10.1000/xyz},")
        out = _union_substantive_fields_text(winner, loser)
        assert "10.1000/xyz" in out

    def test_no_marker_no_behavior_change(self):
        from dedupe_bib import merge_entries
        plain1 = UNCLEANED_COPY
        plain2 = UNCLEANED_COPY.replace("iclr_d1", "iclr_d2")
        merged, _r, _w = merge_entries(plain1, plain2)
        assert "International Conference" in merged

    def test_end_to_end_through_deduplicate_bib(self, tmp_path):
        # Same-key merge across two files: the shipped bib must not carry
        # the flagged booktitle.
        from dedupe_bib import deduplicate_bib
        f1 = tmp_path / "d1.bib"
        f2 = tmp_path / "d3.bib"
        f1.write_text(UNCLEANED_COPY.replace("iclr_d1", "shared"),
                      encoding="utf-8")
        f2.write_text(CLEANED_COPY.replace("iclr_d3", "shared"),
                      encoding="utf-8")
        out = tmp_path / "merged.bib"
        deduplicate_bib([f1, f2], out)
        text = out.read_text(encoding="utf-8")
        assert "International Conference" not in text

    def test_doi_pass_with_flagged_loser(self, tmp_path):
        # Pass 2 (shared DOI, different keys): strip must fire there too
        # (review Q2 coverage note).
        from dedupe_bib import deduplicate_bib
        f1 = tmp_path / "d1.bib"
        f2 = tmp_path / "d3.bib"
        f1.write_text(UNCLEANED_COPY.replace(
            "year = {2024},", "year = {2024},\n    doi = {10.1000/same},"),
            encoding="utf-8")
        f2.write_text(CLEANED_COPY.replace(
            'year = "2024",', 'year = "2024",\n    doi = "10.1000/same",'),
            encoding="utf-8")
        out = tmp_path / "merged.bib"
        deduplicate_bib([f1, f2], out)
        assert "International Conference" not in out.read_text(encoding="utf-8")

    def test_two_hop_transitive_verdict(self):
        # A (cleaned) loses to B; the folded marker on the merged entry must
        # then strip C's copy of the field in a SECOND merge - the scenario
        # that justifies marker folding (review Q2).
        from dedupe_bib import merge_entries
        merged_ab, _r, _w = merge_entries(CLEANED_COPY, UNCLEANED_COPY)
        third = UNCLEANED_COPY.replace("iclr_d1", "iclr_d6")
        merged_abc, _r2, winner = merge_entries(third, merged_ab)
        assert "International Conference" not in merged_abc

    def test_unparseable_entry_ships_loudly_with_honest_marker(self, capsys):
        # Strip failure (unbalanced brace): field ships with a stderr
        # warning, and the marker/reason must NOT claim removal (review 5a).
        # With the surgical scanner (review findings 1/2 fix) this fixture's
        # unmatched inner brace deterministically fails the depth scan every
        # run - the branch below is always taken now, not merely possible.
        from dedupe_bib import merge_entries, _extract_keywords_value
        from metadata_cleaner import marker_removed_fields
        broken = UNCLEANED_COPY.replace(
            "booktitle = {International Conference on Learning Representations},",
            "booktitle = {International {Conference on Learning Representations},")
        merged, reason, _w = merge_entries(CLEANED_COPY, broken)
        err = capsys.readouterr().err
        if "International" in merged:  # strip genuinely failed
            assert "UNVETTED" in err
            assert "dropped cleaner-flagged" not in reason
            assert "booktitle" not in marker_removed_fields(
                _extract_keywords_value(merged)) or \
                "booktitle" in marker_removed_fields(
                    _extract_keywords_value(CLEANED_COPY))

    def test_truncated_value_ships_loudly_with_honest_marker(self, capsys):
        # Winner's OWN booktitle value has an unclosed brace (malformed/
        # truncated entry) while the loser independently flags booktitle via
        # its cleaner marker. The scanner's depth count never returns to 0,
        # so the strip must fail honestly rather than let a regex-miss
        # masquerade as a successful removal (review finding 2) - and the
        # failed scan must not have eaten neighboring fields.
        from dedupe_bib import merge_entries, _extract_keywords_value
        from metadata_cleaner import marker_removed_fields
        truncated = UNCLEANED_COPY.replace(
            "booktitle = {International Conference on Learning Representations},",
            "booktitle = {International {Conference on Learning Representations,")
        merged, reason, winner = merge_entries(CLEANED_COPY, truncated)
        assert winner == 2  # truncated copy still wins (it has the abstract)
        err = capsys.readouterr().err
        assert "UNVETTED" in err
        assert "dropped cleaner-flagged booktitle" not in reason
        assert "booktitle" not in marker_removed_fields(
            _extract_keywords_value(merged))
        # neighboring fields survive untouched - the scan did not swallow them
        assert "abstract = {A substantial abstract" in merged
        assert "Medium" in merged

    def test_two_hop_field_absent_on_winner_still_folds_and_blocks(self):
        # The winner need not even HAVE the flagged field for the fold to
        # happen: _remove_fields_text treats "absent" as a no-op, not a
        # failure, so `applied` still includes it. That is load-bearing for
        # two-hop transitivity - a LATER merge against a third copy that DOES
        # carry the field must still be blocked by the folded marker.
        from dedupe_bib import (
            merge_entries, _union_substantive_fields_text,
            _extract_keywords_value)
        from metadata_cleaner import marker_removed_fields
        winner_no_booktitle = UNCLEANED_COPY.replace(
            "    booktitle = {International Conference on Learning "
            "Representations},\n", "")
        merged, _r, winner = merge_entries(CLEANED_COPY, winner_no_booktitle)
        assert winner == 2
        assert "booktitle" in marker_removed_fields(
            _extract_keywords_value(merged))
        third_with_booktitle = UNCLEANED_COPY.replace("iclr_d1", "iclr_d9")
        out = _union_substantive_fields_text(merged, third_with_booktitle)
        assert "International Conference" not in out

    def test_surgical_strip_preserves_corporate_author_and_custom_fields(self):
        # Surgical scanner removal (no pybtex round-trip) must not
        # reinterpret or rewrite any field outside the one being removed -
        # review finding 1: the old pybtex round-trip re-emitted a
        # single-braced corporate author as a person name
        # (author = {National Research Council} -> author = "Council,
        # National Research").
        from dedupe_bib import _remove_fields_text
        entry = ('@techreport{nrc, author = {National Research Council},\n'
                 '  title = {R}, year = {2020}, pages = {1--3},\n'
                 '  sep_context = {S}, iep_context = {I},\n'
                 '  abstract_source = {crossref}, note = {N}}')
        out, failed = _remove_fields_text(entry, {"pages"})
        assert failed == set()
        # byte-identical single-braced corporate author - no reinterpretation
        assert "author = {National Research Council}" in out
        assert "pages" not in out.lower().replace("abstract_source", "")
        for f in ("sep_context", "iep_context", "abstract_source", "note"):
            assert f in out
        # every other field's own delimiter form is untouched by the removal
        assert "title = {R}" in out
        assert "year = {2020}" in out
        assert "sep_context = {S}" in out

    def test_post_condition_guard_reverts_when_spurious_brace_swallows_neighbor(self):
        # Ledger T3: a dedicated pin for the PRE-EXISTING over-greedy-scan
        # post-condition guard (`known_others`), which no prior test actually
        # exercised. A spurious closing brace inside `pages`'s own value
        # rebalances depth early, so the brace-depth scan for `pages` treats
        # the whole `journal = {Mind}}` field as part of pages's value and
        # eats it - a KNOWN OTHER field's assignment (`journal`) vanishes.
        # The guard must revert the whole removal.
        from dedupe_bib import _remove_fields_text
        entry = ('@article{x,\n'
                  '  author = {A},\n'
                  '  title = {T},\n'
                  '  year = {2020},\n'
                  '  pages = {1--10,\n'
                  '  journal = {Mind}},\n'
                  '  volume = {5},\n'
                  '  keywords = {Medium}\n'
                  '}')
        out, failed = _remove_fields_text(entry, {"pages"})
        assert failed == {"pages"}
        assert out.strip() == entry.strip()
        assert "journal = {Mind}" in out  # neighbor survived the revert

    def test_c1_fake_match_before_real_field_does_not_mangle(self, capsys):
        # C1: a field-name-shaped substring inside ANOTHER field's value
        # (here, "pages = 12" inside the abstract) sits EARLIER in the
        # entry text than the real `pages` field, so the naive scan's
        # first-match search would grab the fake one first - stripping into
        # the abstract while the real pages field survives untouched and the
        # marker would lie about what was removed. The fix must report
        # `pages` failed (loud + honest) and leave the whole entry
        # byte-unchanged rather than shipping a mangled abstract.
        from dedupe_bib import merge_entries, _extract_keywords_value
        from metadata_cleaner import marker_removed_fields
        loser = CLEANED_COPY.replace("booktitle", "pages")
        winner = UNCLEANED_COPY.replace(
            "booktitle = {International Conference on Learning Representations},\n"
            "    abstract = {A substantial abstract that makes this copy win the merge.},",
            "abstract = {We discuss pages = 12, and more.},\n"
            "    pages = {1--10},")
        merged, reason, w = merge_entries(loser, winner)
        assert w == 2
        err = capsys.readouterr().err
        assert "UNVETTED" in err
        assert "dropped cleaner-flagged pages" not in reason
        assert "pages" not in marker_removed_fields(_extract_keywords_value(merged))
        assert merged.strip() == winner.strip()  # unmangled, byte-unchanged
        assert "We discuss pages = 12, and more." in merged  # abstract intact
        assert "pages = {1--10}" in merged  # real field intact

    def test_c1_no_comma_variant_eats_closing_brace(self, capsys):
        # C1, "no-comma" flavor: the fake `pages = 12` mention has no comma
        # before its containing field's (abstract's) own closing brace, so
        # the unquoted/unbraced value scan would run past that brace looking
        # for the next comma - eating through it and writing an unparseable
        # entry, in the pre-fix code. The real pages field (after the
        # abstract) must still be found post-removal, so the fix reports
        # `pages` failed and reverts to the untouched entry.
        from dedupe_bib import merge_entries, _extract_keywords_value
        from metadata_cleaner import marker_removed_fields
        loser = CLEANED_COPY.replace("booktitle", "pages")
        winner = UNCLEANED_COPY.replace(
            "booktitle = {International Conference on Learning Representations},\n"
            "    abstract = {A substantial abstract that makes this copy win the merge.},",
            "abstract = {We discuss pages = 12 without comment},\n"
            "    pages = {1--10},")
        merged, reason, w = merge_entries(loser, winner)
        assert w == 2
        err = capsys.readouterr().err
        assert "UNVETTED" in err
        assert "dropped cleaner-flagged pages" not in reason
        assert "pages" not in marker_removed_fields(_extract_keywords_value(merged))
        assert merged.strip() == winner.strip()  # entry text unchanged

    def test_c1_real_field_first_fake_later_reports_failed(self, capsys):
        # C1, accepted behavior change: the REAL pages field now sits FIRST
        # in the entry text (so the naive scan's first match IS the real
        # assignment), with the fake "pages = 12" mention in the abstract
        # AFTER it. The strip of the real field is textually clean, but the
        # fake occurrence still remains findable afterward - ambiguous, so
        # the specified policy is loud-and-honest: report `pages` failed
        # rather than silently accept a removal next to an unflagged
        # look-alike. Do not "improve" this into a success; it is the
        # deliberately conservative accepted trade-off (review-verified).
        from dedupe_bib import merge_entries, _extract_keywords_value
        from metadata_cleaner import marker_removed_fields
        loser = CLEANED_COPY.replace("booktitle", "pages")
        winner = UNCLEANED_COPY.replace(
            "booktitle = {International Conference on Learning Representations},\n"
            "    abstract = {A substantial abstract that makes this copy win the merge.},",
            "pages = {1--10},\n"
            "    abstract = {We discuss pages = 12, and more.},")
        merged, reason, w = merge_entries(loser, winner)
        assert w == 2
        err = capsys.readouterr().err
        assert "UNVETTED" in err
        assert "dropped cleaner-flagged pages" not in reason
        assert "pages" not in marker_removed_fields(_extract_keywords_value(merged))
        assert merged.strip() == winner.strip()  # unchanged, not half-stripped

    def test_fold_removals_idempotent(self):
        from dedupe_bib import _fold_removals_into_marker
        once = _fold_removals_into_marker(UNCLEANED_COPY, {"booktitle"})
        twice = _fold_removals_into_marker(once, {"booktitle"})
        assert once == twice

    def test_restamp_integration_on_flagged_merge(self, tmp_path):
        # Round-tripped (quoted-form, folded-marker) entries must still flow
        # through restamp_merged without error and carry a tier token
        # (review 5c).
        import json
        from dedupe_bib import deduplicate_bib
        f1 = tmp_path / "d1.bib"
        f2 = tmp_path / "d3.bib"
        f1.write_text(UNCLEANED_COPY.replace("iclr_d1", "shared"),
                      encoding="utf-8")
        f2.write_text(CLEANED_COPY.replace("iclr_d3", "shared"),
                      encoding="utf-8")
        report = tmp_path / "evidence_report.json"
        report.write_text(json.dumps({"attestations": {}}), encoding="utf-8")
        out = tmp_path / "merged.bib"
        deduplicate_bib([f1, f2], out, evidence_report=report)
        text = out.read_text(encoding="utf-8")
        assert "International Conference" not in text
        assert "EVIDENCE-" in text  # tier token stamped, no crash


class TestVenueStatusField:
    """Item 3 D: venue_status must be known to the field scanner, but must
    be unioned apart from the journal identity it was computed against."""

    def test_venue_status_is_a_known_field(self):
        from dedupe_bib import _KNOWN_FIELDS
        assert "venue_status" in _KNOWN_FIELDS

    def test_venue_status_is_not_substantive(self):
        # A derived venue verdict must never be unioned independently of the
        # journal identity it was computed against: _union_substantive_fields
        # copies any listed field the winner lacks, with no coupling between
        # fields, so a winner with a different journal could inherit the
        # loser's verdict.
        from dedupe_bib import _SUBSTANTIVE_FIELDS
        import generate_bibliography
        assert "venue_status" not in _SUBSTANTIVE_FIELDS
        assert "venue_status" not in generate_bibliography._SUBSTANTIVE_FIELDS

    def test_flagged_winner_keeps_its_field_and_flagged_loser_does_not_donate(self, tmp_path):
        """Real duplicates -- same DOI, different keys -- so this exercises
        real winner selection through deduplicate_bib's DOI-based pass, not
        just field co-existence. It does NOT exercise the loser-field
        union: that pass never calls _union_substantive_fields_text (only
        dedupe_by_title_key's title-key pass does), so the merged output
        here is simply the winner's own text -- the loser's venue_status
        was never going to travel regardless of what _SUBSTANTIVE_FIELDS
        contains."""
        winner = """@article{smith2020rich,
  author = {Smith, Anna},
  title = {Data and Things},
  journal = {Synthese},
  doi = {10.1000/xyz123},
  year = {2020},
  abstract = {A real abstract, which is what makes this copy the winner.},
  keywords = {data, High}
}"""
        loser = """@article{smith2020thin,
  author = {Smith, Anna},
  title = {Data and Things},
  journal = {Advanced International Journal for Research},
  venue_status = {low-visibility},
  doi = {10.1000/xyz123},
  year = {2020},
  keywords = {data, Medium}
}"""
        a = tmp_path / "literature-domain-1.bib"
        b = tmp_path / "literature-domain-2.bib"
        a.write_text(winner, encoding="utf-8")
        b.write_text(loser, encoding="utf-8")
        out = tmp_path / "literature-all.bib"
        r = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(out), str(a), str(b)],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        merged = out.read_text(encoding="utf-8")
        from pybtex.database import parse_string
        entries = parse_string(merged, "bibtex").entries
        assert len(entries) == 1                      # they really did merge
        surviving = list(entries.values())[0]
        # The loser's verdict must NOT travel to a winner whose journal is a
        # different venue entirely.
        assert "venue_status" not in surviving.fields
        assert surviving.fields.get("journal") == "Synthese"
        assert "A real abstract" in surviving.fields.get("abstract", "")

    def test_entry_with_venue_status_survives_dedup(self, tmp_path):
        """Contract pin, not a merge test: these two entries share no DOI
        and no title-key, so no merge happens at all -- both survive as
        separate entries. Confirms only that a bare venue_status field
        tolerates parsing/splitting/writing across the whole
        deduplicate_bib pipeline when nothing merges it; it does not reach
        merge_entries or _remove_fields_text."""
        flagged = """@article{okoro2021ai,
  author = {Okoro, Ada},
  title = {Agency and Machines},
  journal = {Advanced International Journal for Research},
  venue_status = {low-visibility},
  doi = {10.1000/aim1},
  year = {2021},
  keywords = {agency, High}
}"""
        other = """@article{smith2020data,
  author = {Smith, Anna},
  title = {Data and Things},
  journal = {Synthese},
  doi = {10.1000/xyz123},
  year = {2020},
  keywords = {data, Medium}
}"""
        a = tmp_path / "literature-domain-1.bib"
        b = tmp_path / "literature-domain-2.bib"
        a.write_text(flagged, encoding="utf-8")
        b.write_text(other, encoding="utf-8")
        out = tmp_path / "literature-all.bib"
        r = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(out), str(a), str(b)],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        merged = out.read_text(encoding="utf-8")
        assert "venue_status = {low-visibility}" in merged
        for expected in ("Agency and Machines", "10.1000/aim1",
                         "Advanced International Journal for Research",
                         "Data and Things"):
            assert expected in merged
        from pybtex.database import parse_string
        assert len(parse_string(merged, "bibtex").entries) == 2

    def test_flagged_field_strip_leaves_venue_status_and_neighbors_intact(self):
        """The one path _KNOWN_FIELDS actually feeds: _remove_fields_text's
        over-greedy post-condition guard, reached only when merge_entries
        strips a loser's METADATA_CLEANED-flagged field from a winner that
        also carries venue_status. Reuses the item 3 A CLEANED_COPY (loser,
        flags booktitle) / UNCLEANED_COPY (winner, has the field and the
        abstract) fixtures with venue_status added to the winner, right
        next to the field being stripped.

        This is a well-formed-input pin, not fault injection: the removal
        scan finds booktitle's true closing brace here, so venue_status
        survives regardless of whether it is registered in _KNOWN_FIELDS --
        confirmed by temporarily reverting the _KNOWN_FIELDS addition and
        re-running this exact test (still green; see task-4-report.md fix
        wave for the command and output). What this test does verify: the
        guard's known_others enumeration -- which now includes
        venue_status -- runs against real merge_entries output without
        raising or corrupting the field, and the surrounding fields
        (abstract) survive the strip untouched. A test that would actually
        DISCRIMINATE on _KNOWN_FIELDS membership needs a malformed-brace
        fixture that makes the booktitle scan over-reach into
        venue_status, along the lines of
        test_post_condition_guard_reverts_when_spurious_brace_swallows_
        neighbor in TestCleanerVerdictPropagation.
        """
        from dedupe_bib import merge_entries
        winner_with_venue = UNCLEANED_COPY.replace(
            "booktitle = {International Conference on Learning Representations},",
            "booktitle = {International Conference on Learning Representations},\n"
            "    venue_status = {low-visibility},")
        merged, _reason, winner = merge_entries(CLEANED_COPY, winner_with_venue)
        assert winner == 2
        assert "International Conference" not in merged  # flagged field stripped
        assert "venue_status = {low-visibility}" in merged  # neighbor untouched
        assert "abstract" in merged.lower()  # another neighbor untouched


class TestYearSuffixField:
    """Item 3 F: unlike venue_status (item 3 D), whose job is already done
    once the writers have read the domain bibs, losing year_suffix in a
    merge breaks a rendered References that prose already cites by letter
    (e.g. "2010a") - so this field needs a REAL merge policy, not
    venue_status's "drop it, nothing depends on it" treatment."""

    def test_year_suffix_is_a_known_field(self):
        from dedupe_bib import _KNOWN_FIELDS, _SUBSTANTIVE_FIELDS
        assert "year_suffix" in _KNOWN_FIELDS
        assert "year_suffix" not in _SUBSTANTIVE_FIELDS

    _WINNER = """@article{smith2020rich,
  author = {Smith, Anna},
  title = {Data and Things},
  journal = {Synthese},
  doi = {10.1000/xyz123},
  year = {2020},
  abstract = {A real abstract, which is what makes this copy the winner.},
  keywords = {data, High}
}"""

    _LOSER = """@article{smith2020thin,
  author = {Smith, Anna},
  title = {Data and Things},
  doi = {10.1000/xyz123},
  year = {2020},
  keywords = {data, Medium}
}"""

    def _run_dedupe(self, tmp_path, winner_text, loser_text, evidence_report=False):
        """Real duplicates (same DOI, different citation keys) through
        deduplicate_bib's DOI-based pass, mirroring
        TestVenueStatusField.test_flagged_winner_keeps_its_field_and_
        flagged_loser_does_not_donate."""
        a = tmp_path / "literature-domain-1.bib"
        b = tmp_path / "literature-domain-2.bib"
        a.write_text(winner_text, encoding="utf-8")
        b.write_text(loser_text, encoding="utf-8")
        out = tmp_path / "literature-all.bib"
        args = [sys.executable, str(SCRIPT_PATH), str(out), str(a), str(b)]
        if evidence_report:
            report = tmp_path / "evidence_report.json"
            report.write_text(json.dumps({"attestations": {}}), encoding="utf-8")
            args += ["--evidence-report", str(report)]
        r = subprocess.run(args, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r, out.read_text(encoding="utf-8")

    def _sole_entry(self, merged_text):
        from pybtex.database import parse_string
        entries = parse_string(merged_text, "bibtex").entries
        assert len(entries) == 1  # they really did merge
        return list(entries.values())[0]

    def test_unanimous_suffix_survives_merge(self, tmp_path):
        # Regression pin only: this case CANNOT be made to fail with the
        # policy reverted, because "winner and loser agree" is a genuine
        # no-op - the winner's own field already survives in `base`. The
        # discrimination for the no-op branches lives in
        # test_lettered_winner_keeps_its_letter_against_a_bare_loser below.
        winner = self._WINNER.replace(
            "keywords = {data, High}",
            "year_suffix = {a},\n  keywords = {data, High}")
        loser = self._LOSER.replace(
            "keywords = {data, Medium}",
            "year_suffix = {a},\n  keywords = {data, Medium}")
        _r, merged = self._run_dedupe(tmp_path, winner, loser)
        surviving = self._sole_entry(merged)
        assert surviving.fields.get("year_suffix") == "a"

    def test_missing_winner_suffix_is_copied_from_agreeing_loser(self, tmp_path):
        loser = self._LOSER.replace(
            "keywords = {data, Medium}",
            "year_suffix = {b},\n  keywords = {data, Medium}")
        _r, merged = self._run_dedupe(tmp_path, self._WINNER, loser)
        surviving = self._sole_entry(merged)
        assert surviving.fields.get("year_suffix") == "b"

    def test_conflicting_suffixes_warn_and_change_nothing(self, tmp_path):
        # Exercised WITH --evidence-report so restamp_merged's re-stamp pass
        # (which touches every surviving entry's text) is in the path too.
        winner = self._WINNER.replace(
            "keywords = {data, High}",
            "year_suffix = {a},\n  keywords = {data, High}")
        loser = self._LOSER.replace(
            "keywords = {data, Medium}",
            "year_suffix = {b},\n  keywords = {data, Medium}")
        r, merged = self._run_dedupe(tmp_path, winner, loser, evidence_report=True)
        assert "[SUFFIX] conflict" in r.stderr
        assert "smith2020rich" in r.stderr and "smith2020thin" in r.stderr
        assert "'a'" in r.stderr and "'b'" in r.stderr
        surviving = self._sole_entry(merged)
        assert surviving.fields.get("year_suffix") == "a"  # winner's, unpicked-not-guessed

    def test_lettered_winner_keeps_its_letter_against_a_bare_loser(self, tmp_path):
        """Third policy branch (winner lettered, loser bare), untested until
        the item-3-F review. Both halves discriminate: the letter must
        survive the merge (a future _apply_cleaner_verdicts or
        _union_substantive_fields change that stripped the field would fail
        the first), and a one-sided letter must NOT read as a disagreement
        (an over-eager conflict branch would fail the second)."""
        winner = self._WINNER.replace(
            "keywords = {data, High}",
            "year_suffix = {c},\n  keywords = {data, High}")
        r, merged = self._run_dedupe(tmp_path, winner, self._LOSER,
                                     evidence_report=True)
        surviving = self._sole_entry(merged)
        assert surviving.fields.get("year_suffix") == "c"
        assert "[SUFFIX]" not in r.stderr


def test_both_derived_fields_are_known_and_neither_is_substantive():
    """Items 3 D and F share the _KNOWN_FIELDS literal and the barrier's
    insertion point, and each already has its own single-field pin above
    (TestVenueStatusField / TestYearSuffixField). This asserts them JOINTLY,
    so an edit that rewrites the shared literal and keeps only one of the two
    fails here rather than passing one class and quietly gutting the other.
    """
    from dedupe_bib import _KNOWN_FIELDS, _SUBSTANTIVE_FIELDS
    import generate_bibliography
    assert {"venue_status", "year_suffix"} <= _KNOWN_FIELDS
    assert not {"venue_status", "year_suffix"} & set(_SUBSTANTIVE_FIELDS)
    assert not {"venue_status", "year_suffix"} & set(
        generate_bibliography._SUBSTANTIVE_FIELDS)
