"""Tests for metadata_validator.py - Metadata provenance validation hook.

Tests the SubagentStop hook that validates BibTeX metadata fields
against API JSON output to detect hallucinated bibliographic data.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add hooks directory to path
HOOKS_DIR = Path(__file__).parent.parent / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from metadata_validator import (
    normalize_pages,
    normalize_journal,
    normalize_doi,
    build_metadata_index,
    validate_metadata,
    parse_s2_result,
    parse_openalex_result,
    parse_crossref_result,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def s2_gardiner_json():
    """S2 API output for Gardiner paper - the hallucination example from plan."""
    return {
        "status": "success",
        "source": "semantic_scholar",
        "query": "Gardiner geoengineering moral hazard",
        "results": [
            {
                "paperId": "c91e1586c0b6b273d36a3d978f71bb1137750876",
                "title": "Some Early Ethics of Geoengineering the Climate: A Commentary on the Values of the Royal Society Report",
                "authors": [{"name": "S. Gardiner", "authorId": "34954884"}],
                "year": 2011,
                "doi": "10.3197/096327111X12997574391689",
                "venue": "The Ethics of Nanotechnology, Geoengineering and Clean Energy",
                "journal": {
                    "name": "Environmental Values",
                    "pages": "163 - 188",
                    "volume": "20"
                },
                "publicationTypes": ["JournalArticle"]
            }
        ],
        "count": 1,
        "errors": []
    }


@pytest.fixture
def s2_mitigation_json():
    """S2 API output - Peacock paper without issue number."""
    return {
        "status": "success",
        "source": "semantic_scholar",
        "query": "mitigation deterrence negative emissions",
        "results": [
            {
                "paperId": "b83dc13c49bce42dda2c456536f371f704c50f89",
                "title": "As Much as Possible, as Soon As Possible: Getting Negative About Emissions",
                "authors": [{"name": "K. Peacock", "authorId": "1931373"}],
                "year": 2021,
                "doi": "10.1080/21550085.2021.1904497",
                "venue": "Ethics, Policy & Environment",
                "journal": {
                    "name": "Ethics, Policy & Environment",
                    "pages": "281 - 296",
                    "volume": "25"
                },
                "publicationTypes": None
            }
        ],
        "count": 1,
        "errors": []
    }


@pytest.fixture
def crossref_result_json():
    """CrossRef API output example."""
    return {
        "status": "success",
        "source": "crossref",
        "query": {"doi": "10.2307/2024717"},
        "results": [
            {
                "verified": True,
                "doi": "10.2307/2024717",
                "title": "Freedom of the Will and the Concept of a Person",
                "authors": [{"family": "Frankfurt", "given": "Harry G."}],
                "year": 1971,
                "container_title": "The Journal of Philosophy",
                "volume": "68",
                "issue": "1",
                "page": "5-20",
                "publisher": "Philosophy Documentation Center",
                "type": "journal-article",
                "method": "doi_lookup",
                "url": "https://doi.org/10.2307/2024717"
            }
        ],
        "count": 1,
        "errors": []
    }


@pytest.fixture
def valid_bibtex_content():
    """BibTeX entry that matches the S2 Gardiner JSON."""
    return """@article{gardiner2011early,
  author = {Gardiner, S.},
  title = {Some Early Ethics of Geoengineering the Climate},
  journal = {Environmental Values},
  year = {2011},
  volume = {20},
  pages = {163--188},
  doi = {10.3197/096327111X12997574391689},
  note = {CORE ARGUMENT: Examines moral hazard in geoengineering.}
}"""


@pytest.fixture
def hallucinated_bibtex_content():
    """BibTeX entry with hallucinated metadata - the Gardiner incollection example."""
    return """@incollection{gardiner2011early,
  author = {Gardiner, Stephen},
  title = {Some Early Ethics of Geoengineering the Climate},
  booktitle = {Climate Ethics: Essential Readings},
  editor = {Gardiner, Stephen and Caney, Simon and Jamieson, Dale and Shue, Henry},
  publisher = {Oxford University Press},
  year = {2010},
  pages = {163--175},
  note = {CORE ARGUMENT: Examines moral hazard in geoengineering.}
}"""


@pytest.fixture
def peacock_with_fabricated_issue():
    """BibTeX entry with fabricated issue number (not in API)."""
    return """@article{peacock2021much,
  author = {Peacock, K.},
  title = {As Much as Possible, as Soon As Possible},
  journal = {Ethics, Policy & Environment},
  year = {2021},
  volume = {25},
  number = {3},
  pages = {281--296},
  doi = {10.1080/21550085.2021.1904497},
  note = {Discusses negative emissions.}
}"""


# =============================================================================
# Tests for Normalization Functions
# =============================================================================

class TestNormalizePages:
    """Tests for page range normalization."""

    def test_already_normalized(self):
        """Should pass through already normalized pages."""
        assert normalize_pages("163-188") == "163-188"

    def test_spaces_around_dash(self):
        """Should remove spaces around dashes (S2 format)."""
        assert normalize_pages("163 - 188") == "163-188"

    def test_bibtex_double_dash(self):
        """Should normalize BibTeX double dash."""
        assert normalize_pages("163--188") == "163-188"

    def test_en_dash(self):
        """Should normalize en-dash."""
        assert normalize_pages("163–188") == "163-188"

    def test_em_dash(self):
        """Should normalize em-dash."""
        assert normalize_pages("163—188") == "163-188"

    def test_empty_string(self):
        """Should handle empty string."""
        assert normalize_pages("") == ""

    def test_single_page(self):
        """Should handle single page."""
        assert normalize_pages("42") == "42"


class TestNormalizeJournal:
    """Tests for journal name normalization."""

    def test_lowercase(self):
        """Should lowercase."""
        assert normalize_journal("Environmental Values") == "environmental values"

    def test_strip_the(self):
        """Should strip 'The' prefix."""
        assert normalize_journal("The Journal of Philosophy") == "journal of philosophy"

    def test_normalize_whitespace(self):
        """Should normalize extra whitespace."""
        assert normalize_journal("Ethics,  Policy   & Environment") == "ethics, policy & environment"


class TestNormalizeDoi:
    """Tests for DOI normalization."""

    def test_bare_doi(self):
        """Should pass through bare DOI."""
        assert normalize_doi("10.2307/2024717") == "10.2307/2024717"

    def test_https_prefix(self):
        """Should strip https prefix."""
        assert normalize_doi("https://doi.org/10.2307/2024717") == "10.2307/2024717"

    def test_doi_prefix(self):
        """Should strip doi: prefix."""
        assert normalize_doi("doi:10.2307/2024717") == "10.2307/2024717"


# =============================================================================
# Tests for JSON Parsing
# =============================================================================

class TestParseS2Result:
    """Tests for Semantic Scholar result parsing."""

    def test_parse_gardiner(self, s2_gardiner_json):
        """Should parse S2 result correctly."""
        entries = parse_s2_result(s2_gardiner_json, "s2_gardiner.json")

        assert len(entries) == 1
        entry = entries[0]
        assert entry.title == "Some Early Ethics of Geoengineering the Climate: A Commentary on the Values of the Royal Society Report"
        assert entry.container_title == "Environmental Values"
        assert entry.volume == "20"
        assert entry.pages == "163 - 188"
        assert entry.year == 2011
        assert entry.doi == "10.3197/096327111X12997574391689"
        assert entry.source_api == "s2"


class TestParseCrossrefResult:
    """Tests for CrossRef result parsing."""

    def test_parse_crossref(self, crossref_result_json):
        """Should parse CrossRef result correctly."""
        entries = parse_crossref_result(crossref_result_json, "crossref_frankfurt.json")

        assert len(entries) == 1
        entry = entries[0]
        assert entry.container_title == "The Journal of Philosophy"
        assert entry.volume == "68"
        assert entry.issue == "1"
        assert entry.pages == "5-20"
        assert entry.publisher == "Philosophy Documentation Center"
        assert entry.source_api == "crossref"


# =============================================================================
# Tests for Metadata Validation
# =============================================================================

class TestBuildMetadataIndex:
    """Tests for building the metadata index from JSON files."""

    def test_build_index(self, tmp_path, s2_gardiner_json):
        """Should build index from JSON files."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()

        # Write S2 JSON file
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        index = build_metadata_index(json_dir)

        assert len(index.entries) == 1
        assert "environmental values" in index.journals
        assert "20" in index.volumes
        assert "163-188" in index.pages
        assert "2011" in index.years


class TestValidateMetadata:
    """Tests for the full validation pipeline."""

    def test_valid_entry_passes(self, tmp_path, s2_gardiner_json, valid_bibtex_content):
        """Should pass when BibTeX matches API output."""
        # Set up files
        json_dir = tmp_path / "intermediate_files" / "json"
        json_dir.mkdir(parents=True)
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(valid_bibtex_content, encoding='utf-8')

        result = validate_metadata(bib_file, json_dir)

        assert result["valid"] is True
        assert result["error_count"] == 0
        assert result["verified_count"] == 1

    def test_gardiner_hallucination_detected(self, tmp_path, s2_gardiner_json, hallucinated_bibtex_content):
        """Should detect hallucinated booktitle/publisher in Gardiner entry.

        This is the key test case from the investigation:
        - API returns: journal="Environmental Values", year=2011, pages="163 - 188"
        - BibTeX has: booktitle="Climate Ethics: Essential Readings", publisher="Oxford University Press"
        """
        json_dir = tmp_path / "intermediate_files" / "json"
        json_dir.mkdir(parents=True)
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(hallucinated_bibtex_content, encoding='utf-8')

        result = validate_metadata(bib_file, json_dir)

        assert result["valid"] is False
        assert result["error_count"] == 1

        # Check for specific errors
        error_text = "\n".join(result["errors"])
        assert "booktitle" in error_text.lower()  # Fabricated booktitle
        assert "publisher" in error_text.lower()  # Fabricated publisher
        # Year might also fail since API has 2011, BibTeX has 2010
        assert "2010" in error_text or "year" in error_text.lower()

    def test_peacock_fabricated_issue_detected(self, tmp_path, s2_mitigation_json, peacock_with_fabricated_issue):
        """Should detect fabricated issue number in Peacock entry.

        API returns no 'issue' field, but BibTeX has number={3}.
        """
        json_dir = tmp_path / "intermediate_files" / "json"
        json_dir.mkdir(parents=True)
        (json_dir / "s2_mitigation.json").write_text(
            json.dumps(s2_mitigation_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(peacock_with_fabricated_issue, encoding='utf-8')

        result = validate_metadata(bib_file, json_dir)

        assert result["valid"] is False

        # Check for issue/number error
        error_text = "\n".join(result["errors"])
        assert "number" in error_text.lower()

    def test_pages_normalization_accepts_variations(self, tmp_path, s2_gardiner_json):
        """Should accept BibTeX pages "163--188" when API has "163 - 188"."""
        json_dir = tmp_path / "intermediate_files" / "json"
        json_dir.mkdir(parents=True)
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        # BibTeX with double-dash pages (standard BibTeX format)
        bibtex = """@article{gardiner2011early,
  author = {Gardiner, S.},
  title = {Some Early Ethics of Geoengineering the Climate},
  journal = {Environmental Values},
  year = {2011},
  volume = {20},
  pages = {163--188},
  note = {Test}
}"""

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = validate_metadata(bib_file, json_dir)

        # Pages should pass - "163--188" normalizes to "163-188" which matches "163 - 188"
        error_text = "\n".join(result.get("errors", []))
        assert "pages" not in error_text.lower()

    def test_note_field_exempt(self, tmp_path, s2_gardiner_json):
        """Should not validate 'note' field (LLM-generated content)."""
        json_dir = tmp_path / "intermediate_files" / "json"
        json_dir.mkdir(parents=True)
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        # BibTeX with extensive note field
        bibtex = """@article{gardiner2011early,
  author = {Gardiner, S.},
  title = {Some Early Ethics of Geoengineering the Climate},
  journal = {Environmental Values},
  year = {2011},
  volume = {20},
  pages = {163--188},
  note = {CORE ARGUMENT: This is completely made up content that doesn't exist in the API.

  RELEVANCE: Totally fabricated by the LLM but that's fine for notes.

  POSITION: Notes are exempt from validation.}
}"""

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = validate_metadata(bib_file, json_dir)

        # Should pass - note field is exempt
        assert result["valid"] is True

    def test_crossref_data_validates(self, tmp_path, crossref_result_json):
        """Should validate against CrossRef data."""
        json_dir = tmp_path / "intermediate_files" / "json"
        json_dir.mkdir(parents=True)
        (json_dir / "crossref_frankfurt.json").write_text(
            json.dumps(crossref_result_json), encoding='utf-8'
        )

        # BibTeX matching CrossRef data
        bibtex = """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971},
  volume = {68},
  number = {1},
  pages = {5--20},
  doi = {10.2307/2024717},
  note = {Foundational paper on free will.}
}"""

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex, encoding='utf-8')

        result = validate_metadata(bib_file, json_dir)

        assert result["valid"] is True
        assert result["verified_count"] == 1

    def test_missing_json_dir_warns(self, tmp_path):
        """Should warn but not fail if JSON directory doesn't exist."""
        bib_file = tmp_path / "test.bib"
        bib_file.write_text("@article{test, author={A}, title={B}, journal={C}, year={2020}}", encoding='utf-8')

        json_dir = tmp_path / "nonexistent_json"

        result = validate_metadata(bib_file, json_dir)

        # Should pass with warning, not fail
        assert result["valid"] is True
        assert len(result["warnings"]) > 0
        assert "not found" in result["warnings"][0].lower()

    def test_empty_json_dir_warns(self, tmp_path):
        """Should warn if JSON directory is empty."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()

        bib_file = tmp_path / "test.bib"
        bib_file.write_text("@article{test, author={A}, title={B}, journal={C}, year={2020}}", encoding='utf-8')

        result = validate_metadata(bib_file, json_dir)

        # Should pass with warning
        assert result["valid"] is True
        assert len(result["warnings"]) > 0


# =============================================================================
# Tests for CLI
# =============================================================================

class TestCLI:
    """Tests for command-line interface."""

    def test_missing_args(self):
        """Should exit with code 2 when missing arguments."""
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "metadata_validator.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Usage:" in result.stdout

    def test_valid_file_exit_0(self, tmp_path, s2_gardiner_json, valid_bibtex_content):
        """Should exit with code 0 for valid file."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        bib_file = tmp_path / "valid.bib"
        bib_file.write_text(valid_bibtex_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "metadata_validator.py"),
             str(bib_file), str(json_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert '"valid": true' in result.stdout

    def test_invalid_file_exit_1(self, tmp_path, s2_gardiner_json, hallucinated_bibtex_content):
        """Should exit with code 1 for invalid file."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        bib_file = tmp_path / "invalid.bib"
        bib_file.write_text(hallucinated_bibtex_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "metadata_validator.py"),
             str(bib_file), str(json_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert '"valid": false' in result.stdout

    def test_json_output_format(self, tmp_path, s2_gardiner_json, valid_bibtex_content):
        """Should output valid JSON."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_gardiner.json").write_text(
            json.dumps(s2_gardiner_json), encoding='utf-8'
        )

        bib_file = tmp_path / "valid.bib"
        bib_file.write_text(valid_bibtex_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "metadata_validator.py"),
             str(bib_file), str(json_dir)],
            capture_output=True,
            text=True,
        )

        # Should parse as valid JSON
        output = json.loads(result.stdout)
        assert "valid" in output
        assert "errors" in output
        assert "verified_count" in output
        assert "error_count" in output
