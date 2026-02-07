"""Tests for metadata_cleaner.py - Metadata provenance cleaning hook.

Tests the SubagentStop hook that removes unverifiable BibTeX metadata fields
(hallucinated data) while preserving valid fields and identity information.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add hooks directory to path
HOOKS_DIR = Path(__file__).parent.parent / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from metadata_cleaner import (
    normalize_pages,
    normalize_journal,
    normalize_doi,
    build_metadata_index,
    clean_bibtex,
    clean_entry,
    is_field_verifiable,
    find_api_entry_by_doi,
    should_downgrade_to_misc,
    CLEANABLE_FIELDS,
    EXEMPT_FIELDS,
    IDENTITY_FIELDS,
    CORRECTABLE_FIELDS,
    REQUIRED_FIELDS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def s2_nature_json():
    """S2 API output with Nature journal."""
    return {
        "status": "success",
        "source": "semantic_scholar",
        "query": "Moral Machine experiment",
        "results": [
            {
                "paperId": "abc123",
                "title": "The Moral Machine experiment",
                "authors": [{"name": "E. Awad", "authorId": "12345"}],
                "year": 2018,
                "doi": "10.1038/s41586-018-0637-6",
                "venue": "Nature",
                "journal": {
                    "name": "Nature",
                    "pages": None,
                    "volume": None
                },
                "publicationTypes": ["JournalArticle"]
            }
        ],
        "count": 1,
        "errors": []
    }


@pytest.fixture
def crossref_with_issue_json():
    """CrossRef API output with issue number."""
    return {
        "status": "success",
        "source": "crossref",
        "query": {"doi": "10.1177/1470594X14542566"},
        "results": [
            {
                "verified": True,
                "doi": "10.1177/1470594x14542566",
                "title": "Climate change, intergenerational equity and the social discount rate",
                "authors": [{"family": "Caney", "given": "Simon"}],
                "year": 2014,
                "container_title": "Politics, Philosophy & Economics",
                "volume": "13",
                "issue": "4",
                "page": "320-342",
                "publisher": "SAGE Publications",
                "type": "journal-article",
            }
        ],
        "count": 1,
        "errors": []
    }


@pytest.fixture
def bibtex_with_hallucinated_number():
    """BibTeX entry with hallucinated issue number."""
    return """@article{awad2018moral,
  author = {Awad, Edmond and others},
  title = {The Moral Machine experiment},
  journal = {Nature},
  year = {2018},
  number = {7729},
  doi = {10.1038/s41586-018-0637-6}
}"""


@pytest.fixture
def bibtex_fully_hallucinated():
    """BibTeX entry where all bibliographic metadata is hallucinated."""
    return """@article{bonnefon2016social,
  author = {Bonnefon, Jean-François and Shariff, Azim and Rahwan, Iyad},
  title = {The social dilemma of autonomous vehicles},
  journal = {Science},
  year = {2016},
  volume = {352},
  number = {6293},
  pages = {1573--1576},
  doi = {10.1126/science.aaf2654},
  note = {Foundational paper on AV ethics}
}"""


@pytest.fixture
def bibtex_valid_with_crossref():
    """BibTeX entry that matches CrossRef data."""
    return """@article{caney2014climate,
  author = {Caney, Simon},
  title = {Climate change, intergenerational equity and the social discount rate},
  journal = {Politics, Philosophy & Economics},
  year = {2014},
  volume = {13},
  number = {4},
  pages = {320--342},
  doi = {10.1177/1470594X14542566},
  note = {Key paper on climate ethics.}
}"""


@pytest.fixture
def bibtex_multiple_entries():
    """BibTeX with multiple entries - one valid, one hallucinated."""
    return """@article{validentry,
  author = {Test Author},
  title = {A Valid Entry},
  journal = {Nature},
  year = {2018}
}

@article{hallucinatedentry,
  author = {Another Author},
  title = {Paper with fake metadata},
  journal = {Science},
  year = {2016},
  volume = {352},
  number = {6293},
  note = {This note should be preserved}
}"""


# =============================================================================
# Tests for Field Configuration
# =============================================================================

class TestFieldConfiguration:
    """Tests for field classification constants."""

    def test_cleanable_fields_defined(self):
        """Should have cleanable fields defined."""
        assert 'journal' in CLEANABLE_FIELDS
        assert 'booktitle' in CLEANABLE_FIELDS
        assert 'volume' in CLEANABLE_FIELDS
        assert 'number' in CLEANABLE_FIELDS
        assert 'pages' in CLEANABLE_FIELDS
        assert 'publisher' in CLEANABLE_FIELDS
        assert 'doi' in CLEANABLE_FIELDS

    def test_exempt_fields_defined(self):
        """Should have exempt fields that are never removed."""
        assert 'note' in EXEMPT_FIELDS
        assert 'keywords' in EXEMPT_FIELDS
        assert 'abstract' in EXEMPT_FIELDS
        assert 'url' in EXEMPT_FIELDS

    def test_identity_fields_defined(self):
        """Should have identity fields that are never removed."""
        assert 'author' in IDENTITY_FIELDS
        assert 'title' in IDENTITY_FIELDS

    def test_correctable_fields_defined(self):
        """Should have correctable fields that can be updated from API."""
        assert 'year' in CORRECTABLE_FIELDS

    def test_required_fields_defined(self):
        """Should have required fields mapping for entry type downgrade."""
        assert 'article' in REQUIRED_FIELDS
        assert 'journal' in REQUIRED_FIELDS['article']
        assert 'incollection' in REQUIRED_FIELDS
        assert 'booktitle' in REQUIRED_FIELDS['incollection']

    def test_no_overlap_between_categories(self):
        """Field categories should not overlap."""
        assert len(CLEANABLE_FIELDS & EXEMPT_FIELDS) == 0
        assert len(CLEANABLE_FIELDS & IDENTITY_FIELDS) == 0
        assert len(EXEMPT_FIELDS & IDENTITY_FIELDS) == 0


# =============================================================================
# Tests for is_field_verifiable
# =============================================================================

class TestIsFieldVerifiable:
    """Tests for field verification against index."""

    def test_journal_verifiable(self, tmp_path, s2_nature_json):
        """Should verify journal name against index."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        index = build_metadata_index(json_dir)

        assert is_field_verifiable('journal', 'Nature', index) is True
        assert is_field_verifiable('journal', 'Science', index) is False

    def test_number_verifiable_with_crossref(self, tmp_path, crossref_with_issue_json):
        """Should verify issue number from CrossRef data."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_caney.json").write_text(
            json.dumps(crossref_with_issue_json), encoding='utf-8'
        )

        index = build_metadata_index(json_dir)

        assert is_field_verifiable('number', '4', index) is True
        assert is_field_verifiable('number', '999', index) is False

    def test_number_not_verifiable_without_crossref(self, tmp_path, s2_nature_json):
        """Should not verify issue number when only S2 data available."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        index = build_metadata_index(json_dir)

        # S2 doesn't provide issue numbers
        assert is_field_verifiable('number', '7729', index) is False
        assert is_field_verifiable('number', '1', index) is False


# =============================================================================
# Tests for clean_bibtex
# =============================================================================

class TestCleanBibtex:
    """Tests for the main cleaning function."""

    def test_removes_hallucinated_number(self, tmp_path, s2_nature_json, bibtex_with_hallucinated_number):
        """Should remove hallucinated issue number while preserving valid fields."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1
        assert result["total_fields_removed"] == 1
        assert "awad2018moral" in result["cleaned_entries"]
        assert "number=7729" in result["cleaned_entries"]["awad2018moral"]

        # Verify the file was modified - number field removed as field, but
        # mentioned in the METADATA_CLEANED tag in keywords
        cleaned_content = bib_file.read_text()
        # number = {7729} should not exist as a field (but may be in keywords tag)
        assert "number = " not in cleaned_content.lower().replace('"', '').replace('{', '').replace('}', '')
        assert "journal" in cleaned_content.lower()  # Should still have journal

    def test_removes_all_hallucinated_fields(self, tmp_path, s2_nature_json, bibtex_fully_hallucinated):
        """Should remove all hallucinated fields from an entry."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_fully_hallucinated, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1
        # Should remove: journal, volume, number, pages, doi (5 fields)
        assert result["total_fields_removed"] == 5

        # Verify identity fields preserved
        cleaned_content = bib_file.read_text()
        assert "author" in cleaned_content.lower()
        assert "title" in cleaned_content.lower()
        assert "year" in cleaned_content.lower()
        # Verify exempt fields preserved
        assert "note" in cleaned_content.lower()

    def test_preserves_valid_entry(self, tmp_path, crossref_with_issue_json, bibtex_valid_with_crossref):
        """Should not modify entry that matches API data."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_caney.json").write_text(
            json.dumps(crossref_with_issue_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_valid_with_crossref, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["entries_cleaned"] == 0
        assert result["total_fields_removed"] == 0

    def test_cleans_only_hallucinated_entry(self, tmp_path, s2_nature_json, bibtex_multiple_entries):
        """Should clean only the entry with hallucinated data."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_multiple_entries, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["entries_total"] == 2
        assert result["entries_cleaned"] == 1
        assert "hallucinatedentry" in result["cleaned_entries"]
        assert "validentry" not in result["cleaned_entries"]

    def test_preserves_note_field(self, tmp_path, s2_nature_json, bibtex_fully_hallucinated):
        """Should preserve note field even when other fields are removed."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_fully_hallucinated, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        cleaned_content = bib_file.read_text()
        assert "note" in cleaned_content.lower()
        assert "Foundational paper" in cleaned_content

    def test_creates_backup(self, tmp_path, s2_nature_json, bibtex_with_hallucinated_number):
        """Should create backup file when requested."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')
        original_content = bib_file.read_text()

        result = clean_bibtex(bib_file, json_dir, create_backup=True)

        assert result["success"] is True
        backup_file = bib_file.with_suffix('.bib.bak')
        assert backup_file.exists()
        assert backup_file.read_text() == original_content

    def test_no_backup_when_no_changes(self, tmp_path, crossref_with_issue_json, bibtex_valid_with_crossref):
        """Should not create backup when no changes made."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_caney.json").write_text(
            json.dumps(crossref_with_issue_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_valid_with_crossref, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=True)

        assert result["success"] is True
        assert result["total_fields_removed"] == 0
        backup_file = bib_file.with_suffix('.bib.bak')
        assert not backup_file.exists()

    def test_handles_missing_json_dir(self, tmp_path, bibtex_with_hallucinated_number):
        """Should handle missing JSON directory gracefully."""
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        json_dir = tmp_path / "nonexistent"

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert len(result["warnings"]) > 0
        assert "not found" in result["warnings"][0].lower()

    def test_handles_empty_json_dir(self, tmp_path, bibtex_with_hallucinated_number):
        """Should handle empty JSON directory gracefully."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert len(result["warnings"]) > 0

    def test_handles_missing_bib_file(self, tmp_path):
        """Should fail gracefully for missing BibTeX file."""
        bib_file = tmp_path / "nonexistent.bib"
        json_dir = tmp_path / "json"
        json_dir.mkdir()

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is False
        assert len(result["errors"]) > 0


# =============================================================================
# Tests for Normalization (inherited from validator but needed for cleaner)
# =============================================================================

class TestNormalization:
    """Tests for normalization functions used in cleaning."""

    def test_pages_normalization(self):
        """Should normalize various page formats."""
        assert normalize_pages("163 - 188") == "163-188"
        assert normalize_pages("163--188") == "163-188"
        assert normalize_pages("163-188") == "163-188"

    def test_journal_normalization(self):
        """Should normalize journal names."""
        assert normalize_journal("The Journal of Philosophy") == "journal of philosophy"
        assert normalize_journal("Nature") == "nature"

    def test_doi_normalization(self):
        """Should normalize DOI formats."""
        assert normalize_doi("https://doi.org/10.1038/s41586-018-0637-6") == "10.1038/s41586-018-0637-6"
        assert normalize_doi("10.1038/s41586-018-0637-6") == "10.1038/s41586-018-0637-6"


# =============================================================================
# Tests for CLI
# =============================================================================

class TestCLI:
    """Tests for command-line interface."""

    def test_missing_args(self):
        """Should exit with code 2 when missing arguments."""
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "metadata_cleaner.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Usage:" in result.stdout

    def test_successful_cleaning_exit_0(self, tmp_path, s2_nature_json, bibtex_with_hallucinated_number):
        """Should exit with code 0 after successful cleaning."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "metadata_cleaner.py"),
             str(bib_file), str(json_dir), "--no-backup"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["total_fields_removed"] == 1

    def test_json_output_format(self, tmp_path, s2_nature_json, bibtex_with_hallucinated_number):
        """Should output valid JSON with expected fields."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "metadata_cleaner.py"),
             str(bib_file), str(json_dir)],
            capture_output=True,
            text=True,
        )

        output = json.loads(result.stdout)
        assert "success" in output
        assert "cleaned_entries" in output
        assert "total_fields_removed" in output
        assert "entries_cleaned" in output
        assert "entries_total" in output
        assert "errors" in output
        assert "warnings" in output


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests simulating real-world scenarios."""

    def test_real_world_hallucination_pattern(self, tmp_path):
        """Test the Gardiner hallucination pattern from the investigation.

        API returns: journal="Environmental Values", year=2011
        LLM writes: booktitle="Climate Ethics: Essential Readings", year=2010
        """
        # S2 API output
        s2_json = {
            "status": "success",
            "source": "semantic_scholar",
            "results": [
                {
                    "paperId": "abc",
                    "title": "Some Early Ethics of Geoengineering",
                    "year": 2011,
                    "journal": {"name": "Environmental Values", "pages": "163 - 188", "volume": "20"},
                }
            ]
        }

        # Hallucinated BibTeX (cites anthology version instead of journal)
        hallucinated_bib = """@incollection{gardiner2011early,
  author = {Gardiner, Stephen},
  title = {Some Early Ethics of Geoengineering},
  booktitle = {Climate Ethics: Essential Readings},
  publisher = {Oxford University Press},
  year = {2010},
  pages = {163--175},
  note = {Examines moral hazard.}
}"""

        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_gardiner.json").write_text(json.dumps(s2_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(hallucinated_bib, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1

        # Should remove: booktitle, publisher, pages (hallucinated)
        # Note: year=2010 doesn't match year=2011 in API, but year is an identity field
        cleaned_entries = result["cleaned_entries"]["gardiner2011early"]
        assert any("booktitle" in field for field in cleaned_entries)
        assert any("publisher" in field for field in cleaned_entries)

        # Verify identity fields preserved
        cleaned_content = bib_file.read_text()
        assert "author" in cleaned_content.lower()
        assert "title" in cleaned_content.lower()
        assert "note" in cleaned_content.lower()

    def test_mixed_valid_and_hallucinated(self, tmp_path):
        """Test file with both valid and hallucinated entries."""
        # API data for both papers
        api_json = {
            "status": "success",
            "source": "semantic_scholar",
            "results": [
                {
                    "paperId": "1",
                    "title": "Valid Paper",
                    "year": 2020,
                    "journal": {"name": "Ethics Journal", "volume": "10", "pages": "1-20"},
                },
                {
                    "paperId": "2",
                    "title": "Another Paper",
                    "year": 2021,
                    "journal": {"name": "Philosophy Review"},
                }
            ]
        }

        bib_content = """@article{valid,
  author = {Author One},
  title = {Valid Paper},
  journal = {Ethics Journal},
  year = {2020},
  volume = {10},
  pages = {1--20}
}

@article{hallucinated,
  author = {Author Two},
  title = {Another Paper},
  journal = {Philosophy Review},
  year = {2021},
  volume = {99},
  number = {5},
  pages = {100--200}
}"""

        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_papers.json").write_text(json.dumps(api_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bib_content, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["entries_total"] == 2
        assert result["entries_cleaned"] == 1  # Only hallucinated entry cleaned
        assert "valid" not in result["cleaned_entries"]
        assert "hallucinated" in result["cleaned_entries"]


# =============================================================================
# Tests for Cleaned Entry Tagging (Issue #1)
# =============================================================================

class TestCleanedEntryTagging:
    """Tests for METADATA_CLEANED keyword tagging."""

    def test_cleaned_entry_has_keywords_tag(self, tmp_path, s2_nature_json, bibtex_with_hallucinated_number):
        """Should add METADATA_CLEANED tag to keywords field after cleaning."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1

        # Verify the keywords field contains the tag
        # Note: pybtex escapes underscores, so check for both variants
        cleaned_content = bib_file.read_text()
        assert "METADATA_CLEANED" in cleaned_content or "METADATA\\_CLEANED" in cleaned_content
        assert "number" in cleaned_content  # The field name should be in the tag

    def test_tag_appended_to_existing_keywords(self, tmp_path, s2_nature_json):
        """Should append tag to existing keywords field."""
        bibtex = """@article{test2018,
  author = {Test Author},
  title = {Test Title},
  journal = {Nature},
  year = {2018},
  number = {999},
  keywords = {ethics, AI}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        cleaned_content = bib_file.read_text()
        # Should preserve original keywords and add tag
        assert "ethics" in cleaned_content or "AI" in cleaned_content
        # Note: pybtex escapes underscores, so check for both variants
        assert "METADATA_CLEANED" in cleaned_content or "METADATA\\_CLEANED" in cleaned_content


# =============================================================================
# Tests for Year Correction (Issue #2)
# =============================================================================

class TestYearCorrection:
    """Tests for DOI-based year correction."""

    def test_year_corrected_from_api(self, tmp_path):
        """Entry with DOI should have year corrected when API has different year."""
        api_json = {
            "status": "success",
            "source": "crossref",
            "results": [
                {
                    "doi": "10.1234/test.2020",
                    "title": "Test Paper",
                    "year": 2020,
                    "container_title": "Test Journal"
                }
            ]
        }

        bibtex = """@article{test2019wrong,
  author = {Test Author},
  title = {Test Paper},
  journal = {Test Journal},
  year = {2019},
  doi = {10.1234/test.2020}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "crossref.json").write_text(json.dumps(api_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["years_corrected"] == 1

        cleaned_content = bib_file.read_text()
        assert "2020" in cleaned_content
        # Note: pybtex escapes special chars, so check for core pattern
        assert "year:2019->2020" in cleaned_content or "year:2019-\\textgreater{}2020" in cleaned_content

    def test_year_unchanged_when_no_doi(self, tmp_path):
        """Entry without DOI should not have year changed."""
        api_json = {
            "status": "success",
            "source": "crossref",
            "results": [
                {
                    "doi": "10.1234/other",
                    "title": "Other Paper",
                    "year": 2020,
                    "container_title": "Test Journal"
                }
            ]
        }

        bibtex = """@article{nodoi,
  author = {Test Author},
  title = {Test Paper},
  journal = {Test Journal},
  year = {2019}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "crossref.json").write_text(json.dumps(api_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["years_corrected"] == 0
        cleaned_content = bib_file.read_text()
        assert "2019" in cleaned_content

    def test_year_unchanged_when_api_matches(self, tmp_path):
        """Entry with DOI should not change when API year matches."""
        api_json = {
            "status": "success",
            "source": "crossref",
            "results": [
                {
                    "doi": "10.1234/test.2020",
                    "title": "Test Paper",
                    "year": 2020,
                    "container_title": "Test Journal"
                }
            ]
        }

        bibtex = """@article{correct,
  author = {Test Author},
  title = {Test Paper},
  journal = {Test Journal},
  year = {2020},
  doi = {10.1234/test.2020}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "crossref.json").write_text(json.dumps(api_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["years_corrected"] == 0


# =============================================================================
# Tests for Entry Type Downgrade (Issue #3)
# =============================================================================

class TestEntryTypeDowngrade:
    """Tests for downgrading entry types to @misc."""

    def test_article_downgraded_to_misc(self, tmp_path, s2_nature_json):
        """@article without journal should be downgraded to @misc."""
        # This BibTeX has a hallucinated journal (Science, not in API)
        bibtex = """@article{hallucinated,
  author = {Test Author},
  title = {Test Paper},
  journal = {Science},
  year = {2020}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["types_downgraded"] == 1

        cleaned_content = bib_file.read_text()
        assert "@misc{" in cleaned_content.lower()
        # Note: pybtex escapes special chars
        assert "type:@article" in cleaned_content and "misc" in cleaned_content

    def test_inproceedings_downgraded_to_misc(self, tmp_path, s2_nature_json):
        """@inproceedings without booktitle should be downgraded to @misc."""
        bibtex = """@inproceedings{confpaper,
  author = {Test Author},
  title = {Test Paper},
  booktitle = {Fake Conference},
  year = {2020}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["types_downgraded"] == 1

        cleaned_content = bib_file.read_text()
        assert "@misc{" in cleaned_content.lower()

    def test_article_with_journal_not_downgraded(self, tmp_path, s2_nature_json):
        """@article with valid journal should stay @article."""
        bibtex = """@article{valid,
  author = {Test Author},
  title = {Test Paper},
  journal = {Nature},
  year = {2020}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["success"] is True
        assert result["types_downgraded"] == 0

        cleaned_content = bib_file.read_text()
        assert "@article{" in cleaned_content.lower()

    def test_misc_not_downgraded(self, tmp_path, s2_nature_json):
        """@misc entries should not be downgraded further."""
        bibtex = """@misc{already_misc,
  author = {Test Author},
  title = {Test Paper},
  year = {2020},
  volume = {999}
}"""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, create_backup=False)

        assert result["types_downgraded"] == 0


# =============================================================================
# Tests for Helper Functions
# =============================================================================

class TestHelperFunctions:
    """Tests for new helper functions."""

    def test_find_api_entry_by_doi(self, tmp_path, crossref_with_issue_json):
        """Should find API entry by DOI."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "crossref.json").write_text(
            json.dumps(crossref_with_issue_json), encoding='utf-8'
        )

        index = build_metadata_index(json_dir)

        # Should find with exact DOI
        entry = find_api_entry_by_doi("10.1177/1470594X14542566", index)
        assert entry is not None
        assert entry["year"] == 2014

        # Should not find non-existent DOI
        entry = find_api_entry_by_doi("10.9999/fake", index)
        assert entry is None

        # Should handle None
        entry = find_api_entry_by_doi(None, index)
        assert entry is None

    def test_should_downgrade_to_misc(self):
        """Test entry type downgrade logic."""
        from pybtex.database import Entry

        # Article without journal should downgrade
        article_no_journal = Entry('article')
        article_no_journal.fields['author'] = 'Test'
        article_no_journal.fields['title'] = 'Test'
        assert should_downgrade_to_misc(article_no_journal) is True

        # Article with journal should not downgrade
        article_with_journal = Entry('article')
        article_with_journal.fields['author'] = 'Test'
        article_with_journal.fields['title'] = 'Test'
        article_with_journal.fields['journal'] = 'Nature'
        assert should_downgrade_to_misc(article_with_journal) is False

        # Misc should not downgrade (not in REQUIRED_FIELDS)
        misc_entry = Entry('misc')
        misc_entry.fields['author'] = 'Test'
        assert should_downgrade_to_misc(misc_entry) is False
