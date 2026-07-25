"""Tests for metadata_cleaner.py - Metadata provenance cleaning hook.

Tests the SubagentStop hook that removes unverifiable BibTeX metadata fields
(hallucinated data) while preserving valid fields and identity information.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pybtex.database import parse_file as pybtex_parse_file

# Add hooks directory to path
HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import metadata_cleaner as mc  # noqa: E402 - module handle for monkeypatching internals

from metadata_cleaner import (
    normalize_pages,
    normalize_journal,
    normalize_doi,
    build_metadata_index,
    clean_bibtex,
    is_field_verifiable,
    find_api_entry_by_doi,
    find_api_entry_for_bib_entry,
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

    def test_domain_prefixed_verify_file_is_indexed(self, tmp_path, crossref_with_issue_json):
        """Fix 2a: researchers namespace verify files as verify_<domain>_<citekey>.json
        to avoid cross-agent collisions. The cleaner must still index them — it globs
        *.json and detects CrossRef records by the 'verify_' substring, so a
        domain-prefixed name is recognized exactly like the bare form."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_3_caney.json").write_text(
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

        result = clean_bibtex(bib_file, json_dir, 
)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1
        assert result["total_fields_removed"] == 1
        assert "awad2018moral" in result["cleaned_entries"]
        assert "number=7729" in result["cleaned_entries"]["awad2018moral"]

        # Verify the file was modified - number field removed as field, but
        # mentioned in the METADATA_CLEANED tag in keywords
        parsed = pybtex_parse_file(str(bib_file), bib_format='bibtex')
        entry = parsed.entries["awad2018moral"]
        assert 'number' not in entry.fields
        assert 'journal' in entry.fields  # Should still have journal

    def test_removes_all_hallucinated_fields(self, tmp_path, bibtex_fully_hallucinated):
        """A matched entry (by DOI) whose bibliographic fields are hallucinated
        loses the unconfirmable ones but keeps its verified DOI (entry-scoped:
        the DOI proves identity, so @article is not demoted)."""
        # Matches bonnefon by DOI but carries NONE of the claimed
        # journal/volume/issue/pages, so those bib values are unconfirmable.
        api_json = {
            "source": "crossref",
            "results": [
                {"doi": "10.1126/science.aaf2654",
                 "title": "The social dilemma of autonomous vehicles",
                 "year": 2016}
            ],
        }
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_bonnefon.json").write_text(
            json.dumps(api_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_fully_hallucinated, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1
        # journal, volume, number, pages unconfirmable -> removed (4).
        # doi MATCHES the API record -> kept (the verified identity).
        assert result["total_fields_removed"] == 4

        parsed = pybtex_parse_file(str(bib_file), bib_format='bibtex')
        entry = parsed.entries["bonnefon2016social"]
        fields = {c.lower() for c in entry.fields}
        assert not ({"journal", "volume", "number", "pages"} & fields)
        assert "doi" in fields            # verified DOI kept
        assert "note" in fields           # exempt field preserved
        assert entry.type == "article"    # matched DOI -> @article guard, no demote

    def test_preserves_valid_entry(self, tmp_path, crossref_with_issue_json, bibtex_valid_with_crossref):
        """Should not modify entry that matches API data."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_caney.json").write_text(
            json.dumps(crossref_with_issue_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_valid_with_crossref, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, 
)

        assert result["success"] is True
        assert result["entries_cleaned"] == 0
        assert result["total_fields_removed"] == 0

    def test_cleans_only_hallucinated_entry(self, tmp_path, bibtex_multiple_entries):
        """Both entries match by title+year; only the one carrying a field
        absent from its API record is cleaned."""
        # Both match by title+year; the first's journal checks out, the second's
        # volume+number are absent from its API record (hallucinated).
        api_json = {
            "source": "semantic_scholar",
            "results": [
                {"title": "A Valid Entry", "year": 2018,
                 "journal": {"name": "Nature"}},
                {"title": "Paper with fake metadata", "year": 2016,
                 "journal": {"name": "Science"}},
            ],
        }
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_papers.json").write_text(json.dumps(api_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_multiple_entries, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["entries_total"] == 2
        assert result["matched_entries"] == 2
        assert result["entries_cleaned"] == 1
        assert "hallucinatedentry" in result["cleaned_entries"]
        assert "validentry" not in result["cleaned_entries"]

    def test_preserves_note_field(self, tmp_path, bibtex_fully_hallucinated):
        """Should preserve the exempt note field even while other fields are
        removed from a matched entry."""
        api_json = {
            "source": "crossref",
            "results": [
                {"doi": "10.1126/science.aaf2654",
                 "title": "The social dilemma of autonomous vehicles",
                 "year": 2016}
            ],
        }
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_bonnefon.json").write_text(
            json.dumps(api_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_fully_hallucinated, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["entries_cleaned"] == 1  # fields WERE removed...
        cleaned_content = bib_file.read_text()
        assert "note" in cleaned_content.lower()      # ...but note survived
        assert "Foundational paper" in cleaned_content

    def test_handles_missing_json_dir(self, tmp_path, bibtex_with_hallucinated_number):
        """Should handle missing JSON directory gracefully."""
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        json_dir = tmp_path / "nonexistent"

        result = clean_bibtex(bib_file, json_dir, 
)

        assert result["success"] is True
        assert len(result["warnings"]) > 0
        assert "no json directory found" in result["warnings"][0].lower()

    def test_handles_empty_json_dir(self, tmp_path, bibtex_with_hallucinated_number):
        """Should handle empty JSON directory gracefully."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir, 
)

        assert result["success"] is True
        assert len(result["warnings"]) > 0

    def test_handles_missing_bib_file(self, tmp_path):
        """Should fail gracefully for missing BibTeX file."""
        bib_file = tmp_path / "nonexistent.bib"
        json_dir = tmp_path / "json"
        json_dir.mkdir()

        result = clean_bibtex(bib_file, json_dir, 
)

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

    def test_journal_normalization_does_not_collapse_distinct_names(self):
        """Regression: a normal journal name must not normalize to empty."""
        assert normalize_journal("Mind") == "mind"

    def test_journal_normalization_latex_ampersand(self):
        """LaTeX '\\&' and HTML '&amp;' must compare equal to a bare '&'."""
        a = normalize_journal(r"Philosophy \& Technology")
        b = normalize_journal("Philosophy &amp; Technology")
        c = normalize_journal("Philosophy & Technology")
        assert a == b == c

    def test_journal_normalization_double_backslash_ampersand(self):
        """Round-tripped bibs sometimes carry a doubled backslash before '&'."""
        a = normalize_journal(r"Philosophy \\& Technology")
        b = normalize_journal("Philosophy & Technology")
        assert a == b

    def test_journal_normalization_braced_circumflex_accent(self):
        """'No\\^{u}s' (braced accent, as real bibs write it) must equal 'Noûs'."""
        assert normalize_journal(r"No\^{u}s") == normalize_journal("Noûs")

    def test_journal_normalization_ampersand_case_insensitive(self):
        assert normalize_journal(r"AI \& SOCIETY") == normalize_journal("AI &amp; Society")

    def test_journal_normalization_cedilla(self):
        """LaTeX cedilla escape '\\c{c}' must equal the precomposed 'ç'."""
        assert normalize_journal(r"\c{c}") == normalize_journal("ç")

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
             str(bib_file), str(json_dir)],
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
        """Gardiner pattern: the LLM cited the anthology (booktitle/publisher)
        for a paper the API shows as a journal article. Matched by title+year,
        the hallucinated container fields are stripped and the @incollection
        demotes to @misc (container types get no @article no-demote guard)."""
        # S2 API output — the real record is a journal article.
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

        # Hallucinated BibTeX: cites the anthology (booktitle/publisher). Year
        # MATCHES the API (2011) so the entry is identified by title+year.
        hallucinated_bib = """@incollection{gardiner2011early,
  author = {Gardiner, Stephen},
  title = {Some Early Ethics of Geoengineering},
  booktitle = {Climate Ethics: Essential Readings},
  publisher = {Oxford University Press},
  year = {2011},
  pages = {163--175},
  note = {Examines moral hazard.}
}"""

        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_gardiner.json").write_text(json.dumps(s2_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(hallucinated_bib, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["matched_entries"] == 1
        assert result["entries_cleaned"] == 1

        # Should remove the hallucinated container fields booktitle + publisher.
        cleaned_entries = result["cleaned_entries"]["gardiner2011early"]
        assert any("booktitle" in field for field in cleaned_entries)
        assert any("publisher" in field for field in cleaned_entries)

        parsed = pybtex_parse_file(str(bib_file), bib_format='bibtex')
        entry = parsed.entries["gardiner2011early"]
        assert entry.type == "misc"                 # demoted (container type)
        # Identity + exempt fields preserved (author is a pybtex person field).
        fields = {c.lower() for c in entry.fields}
        assert "title" in fields and "note" in fields
        assert entry.persons.get("author")          # author preserved

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

        result = clean_bibtex(bib_file, json_dir, 
)

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

        result = clean_bibtex(bib_file, json_dir, 
)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1

        # Verify the keywords field contains the tag
        # Note: pybtex escapes underscores, so check for both variants
        cleaned_content = bib_file.read_text()
        assert "METADATA_CLEANED" in cleaned_content or "METADATA\\_CLEANED" in cleaned_content
        assert "number" in cleaned_content  # The field name should be in the tag

    def test_tag_appended_to_existing_keywords(self, tmp_path):
        """Should append tag to existing keywords field."""
        bibtex = """@article{test2018,
  author = {Test Author},
  title = {Test Title},
  journal = {Nature},
  year = {2018},
  number = {999},
  keywords = {ethics, AI}
}"""
        # Matches test2018 by title+year; journal Nature checks out, number 999
        # is absent from the API record -> stripped -> a marker is written.
        api_json = {
            "source": "semantic_scholar",
            "results": [
                {"title": "Test Title", "year": 2018, "journal": {"name": "Nature"}}
            ],
        }
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_test.json").write_text(
            json.dumps(api_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["entries_cleaned"] == 1
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
        """Entry with DOI should have year corrected when API has different year.

        The API record must come from an entry-scoped verify_* file - broad
        search dumps no longer carry year-correction authority (see
        tests/test_cleaner_source_authority.py)."""
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
        (json_dir / "verify_test.json").write_text(json.dumps(api_json), encoding='utf-8')

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir,
)

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

        result = clean_bibtex(bib_file, json_dir, 
)

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

        result = clean_bibtex(bib_file, json_dir, 
)

        assert result["years_corrected"] == 0


# =============================================================================
# Tests for Entry Type Downgrade (Issue #3)
# =============================================================================

class TestEntryTypeDowngrade:
    """Tests for downgrading entry types to @misc."""

    def test_article_downgraded_to_misc(self, tmp_path):
        """A matched @article whose journal is hallucinated AND has no verified
        DOI to save it is downgraded to @misc."""
        # This BibTeX has a hallucinated journal (Science; the API says Nature)
        # and no DOI, so the @article no-demote guard does not apply.
        bibtex = """@article{hallucinated,
  author = {Test Author},
  title = {Test Paper},
  journal = {Science},
  year = {2020}
}"""
        api_json = {
            "source": "semantic_scholar",
            "results": [
                {"title": "Test Paper", "year": 2020, "journal": {"name": "Nature"}}
            ],
        }
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_test.json").write_text(
            json.dumps(api_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["types_downgraded"] == 1

        cleaned_content = bib_file.read_text()
        assert "@misc{" in cleaned_content.lower()
        # Note: pybtex escapes special chars
        assert "type:@article" in cleaned_content and "misc" in cleaned_content

    def test_inproceedings_downgraded_to_misc(self, tmp_path):
        """A matched @inproceedings whose booktitle is hallucinated is
        downgraded to @misc (the no-demote guard is @article-only)."""
        bibtex = """@inproceedings{confpaper,
  author = {Test Author},
  title = {Test Paper},
  booktitle = {Fake Conference},
  year = {2020}
}"""
        api_json = {
            "source": "crossref",
            "results": [
                {"title": "Test Paper", "year": 2020,
                 "container_title": "Real Proceedings"}
            ],
        }
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_conf.json").write_text(
            json.dumps(api_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["types_downgraded"] == 1

        cleaned_content = bib_file.read_text()
        assert "@misc{" in cleaned_content.lower()

    def test_article_with_journal_not_downgraded(self, tmp_path):
        """A matched @article whose journal is CONFIRMED stays @article."""
        bibtex = """@article{valid,
  author = {Test Author},
  title = {Test Paper},
  journal = {Nature},
  year = {2020}
}"""
        # Matches by title+year and the journal is confirmed -> journal kept.
        api_json = {
            "source": "semantic_scholar",
            "results": [
                {"title": "Test Paper", "year": 2020, "journal": {"name": "Nature"}}
            ],
        }
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_test.json").write_text(
            json.dumps(api_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["matched_entries"] == 1
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

        result = clean_bibtex(bib_file, json_dir, 
)

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

    def test_find_api_entry_for_bib_entry_by_doi(self, tmp_path, crossref_with_issue_json):
        """Entry-scoped matcher finds THIS entry's own API record by DOI, and
        returns None for an entry with no matching DOI or title+year."""
        from pybtex.database import Entry

        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "crossref.json").write_text(
            json.dumps(crossref_with_issue_json), encoding='utf-8'
        )
        index = build_metadata_index(json_dir)

        matched = Entry('article')
        matched.fields['title'] = 'Something Else Entirely'
        matched.fields['year'] = '1900'
        matched.fields['doi'] = '10.1177/1470594X14542566'  # matches by DOI
        api = find_api_entry_for_bib_entry(matched, index)
        assert api is not None and api["year"] == 2014

        # No DOI and a title/year that match nothing -> None (left untouched).
        unmatched = Entry('article')
        unmatched.fields['title'] = 'Nonexistent Paper'
        unmatched.fields['year'] = '1850'
        assert find_api_entry_for_bib_entry(unmatched, index) is None


# =============================================================================
# Tests for the cleaning ledger (positive-match attestation)
# =============================================================================

class TestCleaningLedger:
    """Tests for the cleaning ledger clean_bibtex writes on every
    parse-successful invocation - the attestation source the evidence
    barrier later consumes (docs/superpowers/sdd .../shared-contract.md).

    Note: clean_bibtex's real signature takes bib_path/json_dirs as Path
    objects (bib_path.exists() is called directly on the argument), not
    strings - unlike the task brief's pseudocode, which passed str(...).
    """

    def _run(self, tmp_path, bib_text, json_payloads, bib_name="literature-domain-1.bib"):
        json_dir = tmp_path / "json"
        json_dir.mkdir(exist_ok=True)
        for name, payload in json_payloads.items():
            (json_dir / name).write_text(json.dumps(payload), encoding="utf-8")
        bib = tmp_path / bib_name
        bib.write_text(bib_text, encoding="utf-8")
        result = clean_bibtex(bib, [json_dir])
        ledger_path = tmp_path / "intermediate_files" / "json" / f"cleaning_ledger-{bib.stem}.json"
        return result, ledger_path

    def test_matched_entry_with_verified_doi(self, tmp_path, s2_nature_json):
        """s2_nature_json (real fixture) carries a DOI; a bib entry with the
        SAME title/doi/year positively matches it, so the ledger records a
        verified 'doi' identifier with its normalized value."""
        rec = s2_nature_json["results"][0]
        bib = (
            "@article{nature2018,\n"
            "  author = {A},\n"
            f"  title = {{{rec['title']}}},\n"
            f"  doi = {{{rec['doi']}}},\n"
            f"  year = {{{rec['year']}}}\n"
            "}\n"
        )
        result, ledger_path = self._run(tmp_path, bib, {"s2_x.json": s2_nature_json})
        assert ledger_path.exists()
        assert result["ledger_path"] == str(ledger_path)
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert ledger["schema_version"] == 1
        assert ledger["bib_file"] == "literature-domain-1.bib"
        assert ledger["breaker_tripped"] is False
        ent = ledger["entries"]["nature2018"]
        assert ent["api_matched"] is True
        assert ent["verified_identifier"] == "doi"
        # value binding: the normalized confirmed DOI itself is recorded
        assert ent["verified_identifier_value"] == normalize_doi(rec["doi"])
        assert ent["entry_type"] == "article"

    def test_unmatched_entry_recorded_no_match(self, tmp_path, s2_nature_json):
        """An entry that matches no API record at all (no DOI, and a
        title/year present in no pooled record) is recorded as unmatched
        with a null identifier - never silently omitted from the ledger."""
        bib = (
            "@book{ghost1999,\n"
            "  author = {Ghost, G.},\n"
            "  title = {Nonexistent},\n"
            "  publisher = {Oxford University Press},\n"
            "  year = {1999}\n"
            "}\n"
        )
        result, ledger_path = self._run(tmp_path, bib, {"s2_x.json": s2_nature_json})
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ent = ledger["entries"]["ghost1999"]
        assert ent["api_matched"] is False
        assert ent["verified_identifier"] is None
        assert ent["verified_identifier_value"] is None
        assert ent["entry_type"] == "book"

    def test_ledger_written_even_when_nothing_cleaned(self, tmp_path, s2_nature_json):
        """The ledger is written on EVERY parse-successful invocation, even
        one where nothing was cleaned (here: the entry doesn't match
        anything in the pool, so clean_bibtex touches nothing)."""
        bib = '@book{clean1,\n  author = {A},\n  title = {T},\n  year = {2000}\n}\n'
        result, ledger_path = self._run(tmp_path, bib, {"s2_x.json": s2_nature_json})
        assert ledger_path.exists()
        assert result["entries_cleaned"] == 0

    def test_ledger_written_on_breaker_trip_with_flag(self, tmp_path):
        """Breaker-trip case, adapted from the existing
        test_circuit_breaker_writes_nothing template in
        tests/test_item13_cleaner_gating.py: 6 matched entries would each
        lose a hallucinated 'number' field (6/6 > 30% and >= 5), tripping
        the breaker. The ledger must STILL be written (with the flag set)
        even though clean_bibtex writes nothing to the .bib itself."""
        results = [
            {"doi": f"10.1/{i}", "title": f"P{i}", "container_title": "J", "year": 2020}
            for i in range(6)
        ]
        api_json = {"source": "crossref", "results": results}
        entries = "".join(
            f'@article{{k{i}, author = {{A, B}}, title = {{P{i}}}, journal = {{J}}, '
            f'year = {{2020}}, number = {{99}}, doi = {{10.1/{i}}}}}\n'
            for i in range(6)
        )
        result, ledger_path = self._run(tmp_path, entries, {"c.json": api_json})
        assert result["breaker_tripped"] is True
        assert ledger_path.exists()
        assert result["ledger_path"] == str(ledger_path)
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert ledger["breaker_tripped"] is True
        assert len(ledger["entries"]) == 6
        for i in range(6):
            ent = ledger["entries"][f"k{i}"]
            assert ent["api_matched"] is True
            assert ent["verified_identifier"] == "doi"
            assert ent["verified_identifier_value"] == f"10.1/{i}"

    def test_matched_book_with_verified_publisher(self, tmp_path, crossref_with_issue_json):
        """A MATCHED @book entry whose publisher is confirmed by its own API
        record (shared-contract kuhn1962structure example shape). The entry
        carries no doi field of its own, so it matches by title+year (only
        CrossRef's parser populates 'publisher'); the ledger must then record
        the 'publisher' branch of _verified_identifier, not 'doi'."""
        rec = crossref_with_issue_json["results"][0]
        bib = (
            "@book{caney2014climate,\n"
            "  author = {Caney, Simon},\n"
            f"  title = {{{rec['title']}}},\n"
            f"  publisher = {{{rec['publisher']}}},\n"
            f"  year = {{{rec['year']}}}\n"
            "}\n"
        )
        result, ledger_path = self._run(
            tmp_path, bib, {"crossref_x.json": crossref_with_issue_json}
        )
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ent = ledger["entries"]["caney2014climate"]
        assert ent["api_matched"] is True
        assert ent["verified_identifier"] == "publisher"
        assert ent["verified_identifier_value"] == rec["publisher"].lower().strip()
        assert ent["entry_type"] == "book"

    def test_ledger_write_failure_is_fail_open(self, tmp_path, s2_nature_json, monkeypatch):
        """A ledger-write OSError must not fail cleaning itself (plumbing gate
        fails open, per the shared-contract gate-failure policy): the failure
        surfaces only as a warning, result['ledger_path'] stays None, and
        cleaning still reports success - the missing ledger then demotes
        downstream, which is the safe direction."""
        def _boom(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(mc, "write_cleaning_ledger", _boom)

        bib = '@book{clean1,\n  author = {A},\n  title = {T},\n  year = {2000}\n}\n'
        result, ledger_path = self._run(tmp_path, bib, {"s2_x.json": s2_nature_json})

        assert result["success"] is True
        assert not ledger_path.exists()
        assert result["ledger_path"] is None
        assert any("ledger" in w.lower() for w in result["warnings"])

    def test_reclean_overwrites_ledger_with_final_pass(self, tmp_path, s2_nature_json):
        """A re-clean run (second SubagentStop on a regenerated .bib) must
        OVERWRITE the ledger to reflect only the final pass - stale entries
        from a prior run must not linger."""
        bib1 = '@book{clean1,\n  author = {A},\n  title = {T},\n  year = {2000}\n}\n'
        _, ledger_path = self._run(tmp_path, bib1, {"s2_x.json": s2_nature_json})
        assert "clean1" in json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]

        bib2 = '@book{clean2,\n  author = {B},\n  title = {U},\n  year = {2001}\n}\n'
        _, ledger_path = self._run(tmp_path, bib2, {"s2_x.json": s2_nature_json})
        entries = json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]
        assert "clean2" in entries and "clean1" not in entries

    def test_ledger_written_when_no_json_dir(self, tmp_path, bibtex_with_hallucinated_number):
        """The 'no JSON directory' short-circuit (_count_entries_as_unmatched)
        still parses the .bib successfully, so it must also emit a ledger -
        every entry recorded unmatched with a null identifier."""
        bib_file = tmp_path / "literature-domain-1.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')
        missing_json_dir = tmp_path / "nonexistent"

        result = clean_bibtex(bib_file, [missing_json_dir])

        ledger_path = tmp_path / "intermediate_files" / "json" / "cleaning_ledger-literature-domain-1.json"
        assert ledger_path.exists()
        assert result["ledger_path"] == str(ledger_path)
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert ledger["breaker_tripped"] is False
        ent = ledger["entries"]["awad2018moral"]
        assert ent["api_matched"] is False
        assert ent["verified_identifier"] is None

    def test_ledger_written_when_no_api_results(self, tmp_path, bibtex_with_hallucinated_number):
        """The 'JSON dir exists but has no parseable API results' short-circuit
        also parses the .bib successfully and must emit a ledger."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        bib_file = tmp_path / "literature-domain-1.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')

        result = clean_bibtex(bib_file, [json_dir])

        ledger_path = tmp_path / "intermediate_files" / "json" / "cleaning_ledger-literature-domain-1.json"
        assert ledger_path.exists()
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ent = ledger["entries"]["awad2018moral"]
        assert ent["api_matched"] is False
