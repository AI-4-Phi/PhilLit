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
def crossref_awad_other_issue():
    """Entry-scoped CrossRef record for s2_nature_json's DOI that names a
    DIFFERENT issue.

    Needed by every test that wants a `number` strip: since the strip-rule
    fix only a
    CONTRADICTION strips a detail field, and an S2 dump can never supply one
    (parse_s2_result reports issue=None unconditionally). Constructed to
    disagree - the disagreement, not the value, is the point."""
    return {
        "status": "success",
        "source": "crossref",
        "results": [
            {
                "verified": True,
                "doi": "10.1038/s41586-018-0637-6",
                "title": "The Moral Machine experiment",
                "container_title": "Nature",
                "issue": "1",
                "year": 2018,
                "type": "journal-article",
            }
        ],
        "count": 1,
        "errors": [],
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
  journal = {Journal of Fabrications},
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

    def test_removes_contradicted_number(self, tmp_path, s2_nature_json,
                                         crossref_awad_other_issue,
                                         bibtex_with_hallucinated_number):
        """Should remove an issue number the entry's own CrossRef record
        contradicts, while preserving valid fields."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )
        (json_dir / "verify_awad.json").write_text(
            json.dumps(crossref_awad_other_issue), encoding='utf-8'
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

    def test_absent_number_is_kept_end_to_end(self, tmp_path, s2_nature_json,
                                              bibtex_with_hallucinated_number):
        """The strip rule at the level a user sees: with only an S2 dump in
        the pool
        the record says NOTHING about the issue, so `number` survives in the
        written .bib and no marker is written. Before the fix it was
        stripped."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )

        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bibtex_with_hallucinated_number, encoding='utf-8')
        before = bib_file.read_text(encoding='utf-8')

        result = clean_bibtex(bib_file, json_dir)

        assert result["matched_entries"] == 1  # not a vacuous no-match
        assert result["total_fields_removed"] == 0
        assert bib_file.read_text(encoding='utf-8') == before  # not rewritten

    def test_removes_only_the_venue_when_the_record_carries_nothing(
            self, tmp_path, bibtex_fully_hallucinated):
        """A matched entry (by DOI) whose record supplies no bibliographic
        metadata at all loses only its VENUE - journal is claim-bearing, so
        absence still strips it. volume/number/pages are absence-only and
        survive as unverified telemetry (before the strip-rule fix all four
        went).
        The verified DOI is kept, so @article is not demoted."""
        # Matches bonnefon by DOI but carries NONE of the claimed
        # journal/volume/issue/pages.
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
        assert result["total_fields_removed"] == 1

        parsed = pybtex_parse_file(str(bib_file), bib_format='bibtex')
        entry = parsed.entries["bonnefon2016social"]
        fields = {c.lower() for c in entry.fields}
        assert "journal" not in fields
        assert {"volume", "number", "pages"} <= fields  # absence-only -> kept
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
        """Both entries match by title+year; only the one carrying a field its
        API record refutes is cleaned.

        The refuted field is the VENUE: a title+year match is not
        identity-verified, so since the strip-rule fix no detail field of
        either entry
        could be stripped on this evidence (the second entry's volume+number
        are absent from its record and stay)."""
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

    def test_successful_cleaning_exit_0(self, tmp_path, s2_nature_json,
                                       crossref_awad_other_issue,
                                       bibtex_with_hallucinated_number):
        """Should exit with code 0 after successful cleaning."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )
        # Contradicting record: the strip this test detects needs one.
        (json_dir / "verify_awad.json").write_text(
            json.dumps(crossref_awad_other_issue), encoding='utf-8'
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
        the fabricated BOOKTITLE is stripped and the @incollection demotes to
        @misc (container types get no @article no-demote guard).

        `publisher` survives: a title+year match is not identity-verified and
        the record names no publisher at all, so since the strip-rule fix
        that value is
        unverified rather than refuted. The demotion still fires, which is what
        keeps the fabricated container out of the rendered citation.

        `pages` survives too, and is telemetry-flagged: the bib's `163--175`
        and the record's `163 - 188` are two full RANGES that merely start
        together, which is a contradiction rather than CrossRef truncation
        (the true extent is 163-188, so the flag is right). Being a detail
        field on a record that is not identity-verified, a contradiction
        cannot strip it."""
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

        # Should remove the fabricated booktitle; publisher is unverified, kept.
        cleaned_entries = result["cleaned_entries"]["gardiner2011early"]
        assert any("booktitle" in field for field in cleaned_entries)
        assert not any("publisher" in field for field in cleaned_entries)
        ledger = json.loads(
            (tmp_path / "intermediate_files" / "json"
             / "cleaning_ledger-test.json").read_text(encoding="utf-8"))
        assert not any("pages" in field for field in cleaned_entries)
        assert ledger["entries"]["gardiner2011early"]["unverified_fields"] == [
            "publisher", "pages"]

        parsed = pybtex_parse_file(str(bib_file), bib_format='bibtex')
        entry = parsed.entries["gardiner2011early"]
        assert entry.type == "misc"                 # demoted (container type)
        # Identity + exempt fields preserved (author is a pybtex person field).
        fields = {c.lower() for c in entry.fields}
        assert "title" in fields and "note" in fields
        assert entry.persons.get("author")          # author preserved

    def test_mixed_valid_and_hallucinated(self, tmp_path):
        """Test file with both valid and hallucinated entries.

        The hallucinated entry carries a DOI its record confirms, which makes
        that record identity-verified - so its refuted `volume` is stripped.
        Its `number` and `pages` are absent from the record and survive."""
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
                    "doi": "10.2/another",
                    "journal": {"name": "Philosophy Review", "volume": "7"},
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
  pages = {100--200},
  doi = {10.2/another}
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

    def test_cleaned_entry_has_keywords_tag(self, tmp_path, s2_nature_json,
                                            crossref_awad_other_issue,
                                            bibtex_with_hallucinated_number):
        """Should add METADATA_CLEANED tag to keywords field after cleaning."""
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "s2_nature.json").write_text(
            json.dumps(s2_nature_json), encoding='utf-8'
        )
        # Contradicting record: the strip this test detects needs one.
        (json_dir / "verify_awad.json").write_text(
            json.dumps(crossref_awad_other_issue), encoding='utf-8'
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
  journal = {Journal of Fabrications},
  year = {2018},
  keywords = {ethics, AI}
}"""
        # Matches test2018 by title+year; the API record names another journal
        # and nothing else in the pool names this one -> journal stripped -> a
        # marker is written. (A title+year match is not identity-verified, so
        # since the strip-rule fix only the venue can be stripped here.)
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
                    "year_basis": "published-print",
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
                    "year_basis": "published-print",
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
    barrier later consumes.

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
        # 2 since the strip-rule fix added the optional telemetry keys.
        assert ledger["schema_version"] == 2
        assert ledger["bib_file"] == "literature-domain-1.bib"
        assert ledger["breaker_tripped"] is False
        ent = ledger["entries"]["nature2018"]
        assert ent["api_matched"] is True
        assert ent["verified_identifier"] == "doi"
        # value binding: the normalized confirmed DOI itself is recorded
        assert ent["verified_identifier_value"] == normalize_doi(rec["doi"])
        assert ent["entry_type"] == "article"
        # Telemetry keys are OMITTED when empty: this entry's only cleanable
        # field is its matching doi, so a v2 record reads exactly like a v1 one.
        assert "unverified_fields" not in ent
        assert "venue_stripped_no_evidence" not in ent

    def test_telemetry_keys_recorded_when_non_empty(self, tmp_path):
        """Owner-facing telemetry: kept-but-uncorroborated detail
        fields and venue strips made for want of evidence. Present only when
        non-empty (the empty case is pinned in
        test_matched_entry_with_verified_doi), and never a control - nothing
        downstream may gate on either key."""
        api = {"source": "crossref", "results": [
            {"doi": "10.1/t", "title": "Telemetry", "year": 2020}]}
        bib = (
            "@article{tel2020,\n"
            "  author = {T, T.},\n"
            "  title = {Telemetry},\n"
            "  journal = {Ghost Journal of Nothing},\n"
            "  year = {2020},\n"
            "  volume = {5},\n"
            "  pages = {1--9},\n"
            "  doi = {10.1/t}\n"
            "}\n"
        )
        _result, ledger_path = self._run(tmp_path, bib, {"verify_t.json": api})
        ent = json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]["tel2020"]
        assert set(ent["unverified_fields"]) == {"volume", "pages"}
        assert ent["venue_stripped_no_evidence"] == ["journal"]

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
        tests/test_cleaner_gating.py: 6 matched entries would each
        lose a 'number' their own record refutes (6/6 > 30% and >= 5),
        tripping the breaker. The ledger must STILL be written (with the flag
        set) even though clean_bibtex writes nothing to the .bib itself."""
        results = [
            {"doi": f"10.1/{i}", "title": f"P{i}", "container_title": "J",
             "issue": "1", "year": 2020}
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
        record (the kuhn1962structure example shape). The entry
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
        fails open): the failure
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
# --- CORE parsing + per-file isolation ---------------------------------
# `search_core.py` writes `journal` as a STRING; detect_api_source had no
# `core` branch, so core_*.json fell through to parse_s2_result, whose
# journal_info.get("name") raised AttributeError. Nothing caught it, so ONE
# such file killed the index -- and all cleaning -- for the whole review
# (130 of 7087 files across the local corpora; 27 of 42 reviews).

CORE_JSON = {
    "status": "success",
    "source": "core",
    "query": "moral agency",
    "results": [{
        "core_id": "123", "doi": "10.1111/phis.12345",
        "title": "Moral Agency and Machines", "authors": ["A. Author"],
        "year": 2019, "abstract": "x", "publisher": "Wiley",
        "journal": "Philosophical Issues", "download_url": None,
        "source_url": None, "language": "en", "document_type": "research",
    }],
    "count": 1, "errors": [],
}


class TestCoreResults:
    def test_detect_api_source_recognizes_core_by_source_field(self):
        from metadata_cleaner import detect_api_source
        assert detect_api_source({"source": "core"}, "whatever.json") == "core"

    def test_detect_api_source_recognizes_core_by_filename(self):
        from metadata_cleaner import detect_api_source
        assert detect_api_source({}, "core_accountability.json") == "core"

    def test_detect_api_source_tolerates_non_string_source(self):
        from metadata_cleaner import detect_api_source
        assert detect_api_source({"source": None}, "s2_x.json") == "s2"
        assert detect_api_source({"source": ["core"]}, "unknown.json") == "unknown"

    def test_parse_core_result_reads_journal_publisher_doi(self):
        from metadata_cleaner import parse_core_result
        entry = parse_core_result(CORE_JSON, "core_x.json")[0]
        assert entry["title"] == "Moral Agency and Machines"
        assert entry["container_title"] == "Philosophical Issues"
        assert entry["publisher"] == "Wiley"
        assert entry["doi"] == "10.1111/phis.12345"
        assert entry["year"] == 2019

    def test_parse_s2_result_tolerates_string_journal(self):
        from metadata_cleaner import parse_s2_result
        entries = parse_s2_result(
            {"results": [{"title": "T", "journal": "Philosophical Issues"}]}, "x.json")
        assert entries[0]["container_title"] == "Philosophical Issues"

    def test_core_json_feeds_the_index_instead_of_crashing(self, tmp_path):
        from metadata_cleaner import normalize_doi, normalize_journal
        jdir = tmp_path / "json"
        jdir.mkdir()
        (jdir / "core_moral_agency.json").write_text(
            json.dumps(CORE_JSON), encoding="utf-8")
        index = build_metadata_index([jdir])
        assert index.skipped_files == []
        assert normalize_journal("Philosophical Issues") in index.journals
        assert "wiley" in index.publishers
        assert normalize_doi("10.1111/phis.12345") in index.dois


class TestPerFileIsolation:
    def test_a_file_with_the_wrong_results_shape_is_skipped_not_fatal(self, tmp_path):
        from metadata_cleaner import normalize_journal
        jdir = tmp_path / "json"
        jdir.mkdir()
        (jdir / "s2_bad.json").write_text(
            '{"source": "s2", "results": ["not-a-dict"]}', encoding="utf-8")
        (jdir / "s2_good.json").write_text(
            '{"source": "s2", "results": [{"journal": {"name": "Journal A"}}]}',
            encoding="utf-8")
        index = build_metadata_index(jdir)
        assert "s2_bad.json" in index.skipped_files
        assert normalize_journal("Journal A") in index.journals

    def test_json_that_is_not_an_object_is_skipped(self, tmp_path):
        # Real shape: reviews/algorithmic-fairness/.../final_selection.json is
        # a researcher-authored top-level LIST, not an API envelope.
        from metadata_cleaner import normalize_journal
        jdir = tmp_path / "json"
        jdir.mkdir()
        (jdir / "final_selection.json").write_text('[["a"], ["b"]]', encoding="utf-8")
        (jdir / "s2_good.json").write_text(
            '{"source": "s2", "results": [{"journal": {"name": "Journal A"}}]}',
            encoding="utf-8")
        index = build_metadata_index(jdir)
        assert "final_selection.json" in index.skipped_files
        assert normalize_journal("Journal A") in index.journals

    def test_clean_bibtex_survives_and_warns_about_a_poisoned_file(self, tmp_path):
        jdir = tmp_path / "json"
        jdir.mkdir()
        (jdir / "s2_bad.json").write_text(
            '{"source": "s2", "results": ["not-a-dict"]}', encoding="utf-8")
        (jdir / "verify_a.json").write_text(
            '{"source": "crossref", "results": [{"title": "T1", '
            '"container_title": "J", "year": 2020}]}', encoding="utf-8")
        bib = tmp_path / "d.bib"
        bib.write_text('@article{a, author="A, B", title="T1", journal="J", '
                       'year="2020"}\n', encoding="utf-8")
        res = clean_bibtex(bib, [jdir])
        assert res["success"] is True
        assert "s2_bad.json" in res["skipped_files"]
        assert any("s2_bad.json" in w for w in res["warnings"])

    def test_cli_reports_an_unexpected_failure_as_json(self, tmp_path):
        """The CLI's contract with subagent_stop_bib.sh is JSON on stdout: a
        bare traceback makes the hook's `jq` fail, which reads as a clean run."""
        bib = tmp_path / "d.bib"
        bib.write_text('@article{a, author="A, B", title="T"}\n', encoding="utf-8")
        script = HOOKS_DIR / "metadata_cleaner.py"
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys, runpy\n"
             f"sys.path.insert(0, {str(HOOKS_DIR)!r})\n"
             "import metadata_cleaner as mc\n"
             "def boom(*a, **k):\n"
             "    raise RuntimeError('unexpected')\n"
             "mc.clean_bibtex = boom\n"
             f"sys.argv = [{str(script)!r}, {str(bib)!r}, {str(tmp_path)!r}]\n"
             "mc.main()\n"],
            capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == 2
        payload = json.loads(proc.stdout)
        assert payload["success"] is False
        assert any("unexpected" in e for e in payload["errors"])


class TestLoadFailuresOutsideJSONDecodeError:
    """3G made the parser dispatch fail-soft per file, but the LOAD step still
    named only JSONDecodeError. json.loads can raise a plain ValueError
    (integer digit limit) or RecursionError (deep nesting) - neither is a
    JSONDecodeError, so one such file killed the whole index build, which is
    exactly the same failure class one layer up. Found by kimi-k3/gpt-5.6-sol
    reviewing the dormant validator, then reproduced HERE, in the live
    destructive path."""

    def _dir(self, tmp_path, bad_name, bad_text):
        import json as _json
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / bad_name).write_text(bad_text, encoding="utf-8")
        (json_dir / "s2_ok.json").write_text(_json.dumps({
            "source": "semantic_scholar",
            "results": [{"title": "T", "year": 2007}],
        }), encoding="utf-8")
        return json_dir

    def test_oversized_integer_is_skipped_not_fatal(self, tmp_path):
        from metadata_cleaner import build_metadata_index

        json_dir = self._dir(
            tmp_path, "a_huge.json",
            '{"results":[{"year":' + "9" * 5000 + "}]}")

        index = build_metadata_index(json_dir)

        assert "a_huge.json" in index.skipped_files
        assert index.entries          # the good file still indexed

    def test_deeply_nested_json_is_skipped_not_fatal(self, tmp_path):
        from metadata_cleaner import build_metadata_index

        json_dir = self._dir(
            tmp_path, "a_deep.json", "[" * 200000 + "]" * 200000)

        index = build_metadata_index(json_dir)

        assert "a_deep.json" in index.skipped_files
        assert index.entries


# =============================================================================
# Tests for marker_removed_fields
# =============================================================================

class TestMarkerRemovedFields:
    """marker_removed_fields: the public parser for the METADATA_CLEANED
    marker's removed-field names."""

    def test_plain_marker_removals(self):
        from metadata_cleaner import marker_removed_fields
        kw = "High, METADATA_CLEANED: booktitle, pages"
        assert marker_removed_fields(kw) == frozenset({"booktitle", "pages"})

    def test_pybtex_escaped_marker(self):
        from metadata_cleaner import marker_removed_fields
        kw = r"High, METADATA\_CLEANED: journal"
        assert marker_removed_fields(kw) == frozenset({"journal"})

    def test_double_escaped_marker(self):
        from metadata_cleaner import marker_removed_fields
        kw = r"METADATA\\_CLEANED: volume"
        assert marker_removed_fields(kw) == frozenset({"volume"})

    def test_change_tokens_are_not_removals(self):
        from metadata_cleaner import marker_removed_fields
        kw = "METADATA_CLEANED: year:2007->2019, type:@article->@misc, pages"
        assert marker_removed_fields(kw) == frozenset({"pages"})

    def test_no_marker_and_empty(self):
        from metadata_cleaner import marker_removed_fields
        assert marker_removed_fields("High, INCOMPLETE") == frozenset()
        assert marker_removed_fields("") == frozenset()

    def test_names_lowercased(self):
        from metadata_cleaner import marker_removed_fields
        assert marker_removed_fields("METADATA_CLEANED: Booktitle") == \
            frozenset({"booktitle"})

    def test_roundtrip_with_writer_output(self):
        """The parser must read what _apply_cleaned_marker + pybtex Writer
        actually produce."""
        import io
        from pybtex.database import parse_string
        from pybtex.database.output.bibtex import Writer
        from metadata_cleaner import marker_removed_fields
        db = parse_string(
            "@article{k, author={A B}, title={T}, year={2020},"
            " keywords={High, METADATA_CLEANED: booktitle, pages}}", "bibtex")
        out = io.StringIO()
        Writer().write_stream(db, out)
        text = out.getvalue()  # keywords = "High, METADATA\_CLEANED: booktitle, pages"
        import re
        kw = re.search(r'keywords\s*=\s*"([^"]*)"', text).group(1)
        assert marker_removed_fields(kw) == frozenset({"booktitle", "pages"})


# =============================================================================
# Tests for the three-way comparator and the per-field strip policy
# (the cleaner strip-rule fix). Measurements:
# docs/known-issues/cleaner-strip-rule-absence-vs-contradiction.md
# =============================================================================

class TestFieldCompare:
    """_field_compare: MATCH / CONTRADICT / NO-EVIDENCE against the entry's
    OWN matched API record. Absence of a field from the record is NOT a weak
    contradiction - 80% of the pre-fix strips were absence-driven and the
    truth anchor found those values majority-TRUE."""

    def test_venue_match_via_normalize_journal(self):
        assert mc._field_compare(
            "journal", "The Journal of Philosophy",
            {"container_title": "Journal of Philosophy"}) == "match"

    def test_venue_contradicts_when_record_names_another_venue(self):
        assert mc._field_compare(
            "journal", "Mind", {"container_title": "Synthese"}) == "contradict"

    def test_venue_no_evidence_when_record_carries_no_container(self):
        assert mc._field_compare("journal", "Mind", {}) == "no-evidence"
        assert mc._field_compare(
            "booktitle", "Some Volume",
            {"container_title": "   "}) == "no-evidence"

    def test_booktitle_uses_the_same_rule_as_journal(self):
        assert mc._field_compare(
            "booktitle", "Handbook of A",
            {"container_title": "Handbook of A"}) == "match"
        assert mc._field_compare(
            "booktitle", "Handbook of A",
            {"container_title": "Handbook of B"}) == "contradict"
        assert mc._field_compare("booktitle", "Handbook of A", {}) == "no-evidence"

    def test_volume_three_states(self):
        assert mc._field_compare("volume", "13", {"volume": " 13 "}) == "match"
        assert mc._field_compare("volume", "13", {"volume": "14"}) == "contradict"
        assert mc._field_compare("volume", "13", {}) == "no-evidence"

    def test_number_compares_against_the_records_issue(self):
        assert mc._field_compare("number", "4", {"issue": "4"}) == "match"
        assert mc._field_compare("number", "4", {"issue": "5"}) == "contradict"
        assert mc._field_compare("number", "4", {"issue": None}) == "no-evidence"

    def test_pages_exact_range_matches(self):
        assert mc._field_compare(
            "pages", "320--342", {"pages": "320-342"}) == "match"

    def test_pages_first_page_tolerance_is_a_match(self):
        """bogen1988saving: TRUE pages `303--352` against CrossRef's own
        first-page truncation `303`. A differing TAIL is not a contradiction."""
        assert mc._field_compare(
            "pages", "303--352", {"pages": "303"}) == "match"
        assert mc._field_compare(
            "pages", "303", {"pages": "303--352"}) == "match"

    def test_pages_differing_first_page_contradicts(self):
        assert mc._field_compare(
            "pages", "641--658", {"pages": "867-880"}) == "contradict"

    def test_pages_two_full_ranges_sharing_a_first_page_contradict(self):
        """The tolerance exists for CrossRef's first-page TRUNCATION, so it
        applies only when a side actually IS a bare first page. Two full
        ranges that merely start together disagree about the work's extent:
        `100--999` is not `100--101`."""
        assert mc._field_compare(
            "pages", "100--999", {"pages": "100--101"}) == "contradict"
        assert mc._field_compare(
            "pages", "100--101", {"pages": "100-999"}) == "contradict"
        # Equal ranges still match, on the full-string test that runs first.
        assert mc._field_compare(
            "pages", "100--999", {"pages": "100-999"}) == "match"

    def test_pages_no_evidence_when_record_has_none(self):
        assert mc._field_compare("pages", "641--658", {}) == "no-evidence"
        assert mc._field_compare(
            "pages", "641--658", {"pages": ""}) == "no-evidence"

    def test_pages_punctuation_only_record_value_is_no_evidence(self):
        """An API record that emitted a bare separator carries no page
        information however non-empty it looks: OpenAlex/S2 records with
        `pages: " - "` normalize to "-", which used to reach the fall-through
        and CONDEMN a true page range."""
        assert mc._field_compare("pages", "641--658", {"pages": " - "}) == "no-evidence"
        assert mc._field_compare("pages", "641--658", {"pages": "--"}) == "no-evidence"
        # Narrow by design: alphanumeric non-digit forms still contradict.
        assert mc._field_compare(
            "pages", "e12345", {"pages": "e99999"}) == "contradict"
        assert mc._field_compare(
            "pages", "641--658", {"pages": "xii-xv"}) == "contradict"

    def test_pages_without_a_leading_digit_run_fall_back_to_full_equality(self):
        """Roman-numeral and article-id pages have no comparable first page,
        so they compare whole - equal is a match, unequal a contradiction."""
        assert mc._field_compare(
            "pages", "e12345", {"pages": "e12345"}) == "match"
        assert mc._field_compare(
            "pages", "e12345", {"pages": "e99999"}) == "contradict"
        assert mc._field_compare(
            "pages", "xii--xv", {"pages": "1-10"}) == "contradict"

    def test_publisher_prefix_containment_matches_in_either_direction(self):
        # Imprint depth: the prefix ends at a WORD BOUNDARY in the longer name.
        assert mc._field_compare(
            "publisher", "Springer",
            {"publisher": "Springer International Publishing"}) == "match"
        assert mc._field_compare(
            "publisher", "Springer International Publishing",
            {"publisher": "springer"}) == "match"
        # Concatenated-location artifact: the tail is glued on with no
        # separator, so only a PREFIX test rescues it -- and it is licensed
        # by the prefix being MULTI-TOKEN, not by a boundary.
        assert mc._field_compare(
            "publisher", "Oxford University Press",
            {"publisher": "Oxford University PressNew York"}) == "match"

    def test_publisher_prefix_needs_a_boundary_or_a_multi_token_prefix(self):
        """Unbounded prefix containment verified `O` against `Oxford
        University Press`: it kept a one-letter fabricated publisher AND,
        inherited by _verified_identifier, bought EVIDENCE-EXISTENCE on the
        identifier "o". A SINGLE-token prefix that cuts a word in half is a
        contradiction, not a shallower report of the same imprint (external
        review, 2026-08-25)."""
        assert mc._field_compare(
            "publisher", "O",
            {"publisher": "Oxford University Press"}) == "contradict"
        assert mc._field_compare(
            "publisher", "Brill",
            {"publisher": "Brillante Editores"}) == "contradict"

    def test_publisher_containment_is_prefix_only_not_substring(self):
        """A bare imprint word is a SUBSTRING of a real publisher but names no
        publisher, and suffix containment would verify it against any house
        ending the same way. Prefix-only, so these contradict."""
        assert mc._field_compare(
            "publisher", "Press",
            {"publisher": "Oxford University Press"}) == "contradict"
        assert mc._field_compare(
            "publisher", "University Press",
            {"publisher": "Cambridge University Press"}) == "contradict"

    def test_publisher_three_states(self):
        assert mc._field_compare(
            "publisher", "Oxford University Press",
            {"publisher": "oxford university press"}) == "match"
        assert mc._field_compare(
            "publisher", "Oxford University Press",
            {"publisher": "Routledge"}) == "contradict"
        assert mc._field_compare(
            "publisher", "Oxford University Press", {}) == "no-evidence"

    def test_doi_three_states(self):
        assert mc._field_compare(
            "doi", "https://doi.org/10.1/A", {"doi": "10.1/a"}) == "match"
        assert mc._field_compare(
            "doi", "10.1/a", {"doi": "10.2/b"}) == "contradict"
        assert mc._field_compare("doi", "10.1/a", {"doi": ""}) == "no-evidence"

    def test_unknown_field_is_match(self):
        """Mirror of the pre-fix default-keep: a field with no comparison
        rule is never condemned."""
        assert mc._field_compare("school", "Anywhere", {}) == "match"

    def test_publisher_containment_reaches_verified_identifier(self):
        """The containment widening is INHERITED by _verified_identifier, and
        that inheritance has a downstream consequence: stamp_evidence binds
        EVIDENCE-EXISTENCE to a publisher-verified book. Pinned here so a later
        tightening of publisher comparison cannot revert it silently."""
        from pybtex.database import parse_string
        entry = parse_string(
            '@book{k, author="A, B", title="T", year="2020", '
            'publisher="Springer"}', "bibtex").entries["k"]
        assert mc._verified_identifier(
            entry, {"publisher": "Springer International Publishing"}) == (
                "publisher", "springer")

    def test_field_matches_api_is_exactly_the_match_state(self):
        cases = [
            ("pages", "303--352", {"pages": "303"}),
            ("pages", "641--658", {"pages": "867-880"}),
            ("publisher", "Springer", {"publisher": "Springer Nature"}),
            ("number", "4", {"issue": "5"}),
            ("journal", "Mind", {}),
            ("doi", "10.1/a", {"doi": "10.1/A"}),
        ]
        for field_lower, value, api in cases:
            assert mc._field_matches_api(field_lower, value, api) is (
                mc._field_compare(field_lower, value, api) == "match"), (
                    field_lower, value, api)


def _plan_for(tmp_path, bib_text, json_payloads):
    """(plan, entry) for the single entry in `bib_text`, planned against an
    index built from `json_payloads`. Asserts the fixture really MATCHES a
    record - an accidental no-match would make every policy assertion below
    vacuously true."""
    json_dir = tmp_path / "json"
    json_dir.mkdir(exist_ok=True)
    for name, payload in json_payloads.items():
        (json_dir / name).write_text(json.dumps(payload), encoding="utf-8")
    index = build_metadata_index([json_dir])
    bib = tmp_path / "p.bib"
    bib.write_text(bib_text, encoding="utf-8")
    parsed = pybtex_parse_file(str(bib), bib_format="bibtex")
    (_key, entry), = parsed.entries.items()
    api_entry = find_api_entry_for_bib_entry(entry, index)
    assert isinstance(api_entry, dict), "fixture must MATCH an API record"
    return mc.plan_entry_cleaning(entry, index, api_entry), entry


class TestStripPolicy:
    """plan_entry_cleaning's per-field policy: detail fields strip only on a
    CONTRADICTION from an identity-verified record; venue fields keep the
    older policy (absence strips too); doi needs an entry-scoped record."""

    def test_field_classes_partition_the_cleanable_fields(self):
        """Every cleanable field reaches exactly one policy branch - a new
        cleanable field must not silently inherit another class's policy."""
        assert mc.DETAIL_FIELDS | {"journal", "booktitle", "doi"} == CLEANABLE_FIELDS
        assert not mc.DETAIL_FIELDS & {"journal", "booktitle", "doi"}

    def test_fruh_shape_absent_detail_fields_are_kept(self, tmp_path):
        """fruh2019climate / pamuk2020risk shape: a DOI-matched record that
        carries NO volume, issue or pages. Those bib values are absence-only,
        so all three are KEPT (before the fix all three were stripped) and
        recorded as unverified telemetry."""
        api = {"source": "crossref", "results": [
            {"doi": "10.1/fruh", "title": "Climate and Justice", "year": 2019,
             "container_title": "Journal of Applied Philosophy"}]}
        bib = (
            "@article{fruh2019climate,\n"
            "  author = {Fruh, K.},\n"
            "  title = {Climate and Justice},\n"
            "  journal = {Journal of Applied Philosophy},\n"
            "  year = {2019},\n"
            "  volume = {36},\n"
            "  number = {3},\n"
            "  pages = {1--20},\n"
            "  doi = {10.1/fruh}\n"
            "}\n"
        )
        plan, _ = _plan_for(tmp_path, bib, {"verify_fruh.json": api})
        assert plan["removed_field_names"] == []
        assert set(plan["unverified_fields"]) == {"volume", "number", "pages"}
        assert plan["venue_stripped_no_evidence"] == []

    def test_jamieson_shape_broad_record_contradiction_keeps_details(self, tmp_path):
        """jamieson2014reason: a title+year match to a broad dump's record for
        a DIFFERENT artifact about the same book (a Choice review, with its own
        pages and its own DOI). Not identity-verified, so neither a detail
        field nor the doi may be stripped on its say-so."""
        api = {"source": "semantic_scholar", "results": [
            {"title": "Reason in a Dark Time", "year": 2014,
             "doi": "10.5860/choice.99999",
             "journal": {"name": "Choice Reviews Online",
                         "volume": "52", "pages": "52-0999"},
             "publisher": "Association of College and Research Libraries"}]}
        bib = (
            "@book{jamieson2014reason,\n"
            "  author = {Jamieson, Dale},\n"
            "  title = {Reason in a Dark Time},\n"
            "  year = {2014},\n"
            "  publisher = {Oxford University Press},\n"
            "  pages = {1--266},\n"
            "  doi = {10.1093/acprof:oso/9780199337668.001.0001}\n"
            "}\n"
        )
        plan, _ = _plan_for(tmp_path, bib, {"s2_dump.json": api})
        assert plan["removed_field_names"] == []
        assert set(plan["unverified_fields"]) == {"publisher", "pages", "doi"}

    def test_entry_scoped_contradiction_strips_details_and_doi(self, tmp_path):
        """The same contradiction from an entry-scoped record (a targeted
        single-work CrossRef lookup) DOES strip - that is the hallucination
        class the cleaner exists for."""
        api = {"source": "crossref", "results": [
            {"title": "Reason in a Dark Time", "year": 2014,
             "doi": "10.5860/choice.99999",
             "container_title": "Choice Reviews Online",
             "page": "52-0999",
             "publisher": "Association of College and Research Libraries"}]}
        bib = (
            "@book{jamieson2014reason,\n"
            "  author = {Jamieson, Dale},\n"
            "  title = {Reason in a Dark Time},\n"
            "  year = {2014},\n"
            "  publisher = {Oxford University Press},\n"
            "  pages = {1--266},\n"
            "  doi = {10.1093/acprof:oso/9780199337668.001.0001}\n"
            "}\n"
        )
        plan, _ = _plan_for(tmp_path, bib, {"verify_jam.json": api})
        assert set(plan["removed_field_names"]) == {"publisher", "pages", "doi"}
        assert plan["unverified_fields"] == []

    def test_doi_match_makes_a_broad_record_identity_verified(self, tmp_path):
        """A DOI match is identity verification even from a broad dump: the
        record IS this work's metadata, so its contradictions can strip
        (mhlambi2023decolonizing's wrong pages)."""
        api = {"source": "semantic_scholar", "results": [
            {"title": "Wrong Pages", "year": 2020, "doi": "10.1/x",
             "journal": {"name": "Mind", "pages": "867-880"}}]}
        bib = (
            "@article{mhlambi2023decolonizing,\n"
            "  author = {M, S.},\n"
            "  title = {Wrong Pages},\n"
            "  journal = {Mind},\n"
            "  year = {2020},\n"
            "  pages = {641--658},\n"
            "  doi = {10.1/x}\n"
            "}\n"
        )
        plan, _ = _plan_for(tmp_path, bib, {"s2_dump.json": api})
        assert plan["removed_field_names"] == ["pages"]
        assert plan["unverified_fields"] == []

    def test_broad_record_doi_contradiction_is_kept(self, tmp_path):
        """doi keys on entry_scoped, NOT on identity_verified: a broad dump's
        differing DOI is usually its own artifact's, so it can never strip -
        even when the record contradicts on other fields too."""
        api = {"source": "semantic_scholar", "results": [
            {"title": "Reason in a Dark Time", "year": 2014,
             "doi": "10.5860/choice.99999",
             "journal": {"name": "Choice Reviews Online"}}]}
        bib = (
            "@book{jamieson2014reason,\n"
            "  author = {Jamieson, Dale},\n"
            "  title = {Reason in a Dark Time},\n"
            "  year = {2014},\n"
            "  doi = {10.1093/acprof:oso/9780199337668.001.0001}\n"
            "}\n"
        )
        plan, _ = _plan_for(tmp_path, bib, {"s2_dump.json": api})
        assert plan["removed_field_names"] == []
        assert plan["unverified_fields"] == ["doi"]

    def test_global_bucket_no_longer_rescues_a_contradicted_detail_field(self, tmp_path):
        """The coincidence check is REMOVED from the detail fields' decision:
        an unrelated paper's matching issue number used to keep a value the
        entry's own record contradicted."""
        own = {"source": "crossref", "results": [
            {"doi": "10.1/own", "title": "Paper A", "year": 2020,
             "container_title": "Journal A", "issue": "4"}]}
        unrelated = {"source": "crossref", "results": [
            {"doi": "10.1/other", "title": "Paper B", "year": 2001,
             "container_title": "Journal B", "issue": "9"},
            {"doi": "10.1/third", "title": "Paper C", "year": 2002,
             "container_title": "Journal C", "issue": "9"}]}
        bib = (
            "@article{a2020,\n"
            "  author = {A, A.},\n"
            "  title = {Paper A},\n"
            "  journal = {Journal A},\n"
            "  year = {2020},\n"
            "  number = {9},\n"
            "  doi = {10.1/own}\n"
            "}\n"
        )
        plan, _ = _plan_for(
            tmp_path, bib, {"verify_a.json": own, "verify_b.json": unrelated})
        assert "9" in build_metadata_index([tmp_path / "json"]).issues, (
            "fixture must put the contradicted value in the global bucket")
        assert plan["removed_field_names"] == ["number"]

    def test_venue_absence_still_strips_and_is_recorded(self, tmp_path):
        """Venue policy is UNCHANGED: a journal absent from both the entry's
        record and the global bucket still strips (farina2021extended's
        fabricated booktitle stays caught). The strip is recorded as telemetry
        under its own key, never as 'unverified'."""
        api = {"source": "crossref", "results": [
            {"doi": "10.1/v", "title": "No Venue Record", "year": 2020}]}
        bib = (
            "@article{v2020,\n"
            "  author = {V, V.},\n"
            "  title = {No Venue Record},\n"
            "  journal = {Ghost Journal of Nothing},\n"
            "  year = {2020},\n"
            "  doi = {10.1/v}\n"
            "}\n"
        )
        plan, _ = _plan_for(tmp_path, bib, {"verify_v.json": api})
        assert plan["removed_field_names"] == ["journal"]
        assert plan["venue_stripped_no_evidence"] == ["journal"]
        assert plan["unverified_fields"] == []

    def test_venue_global_bucket_rescue_still_works(self, tmp_path):
        """A venue named by ANOTHER indexed file is legitimately sourced, so
        the bucket still keeps it - and a bucket-verified venue is not
        'unverified' telemetry."""
        own = {"source": "crossref", "results": [
            {"doi": "10.1/w", "title": "Bucket Venue", "year": 2020}]}
        elsewhere = {"source": "crossref", "results": [
            {"doi": "10.1/other", "title": "Other", "year": 1999,
             "container_title": "Ghost Journal of Nothing"},
            {"doi": "10.1/third", "title": "Third", "year": 1998,
             "container_title": "Ghost Journal of Nothing"}]}
        bib = (
            "@article{w2020,\n"
            "  author = {W, W.},\n"
            "  title = {Bucket Venue},\n"
            "  journal = {Ghost Journal of Nothing},\n"
            "  year = {2020},\n"
            "  doi = {10.1/w}\n"
            "}\n"
        )
        plan, _ = _plan_for(
            tmp_path, bib, {"verify_w.json": own, "verify_e.json": elsewhere})
        assert plan["removed_field_names"] == []
        assert plan["venue_stripped_no_evidence"] == []
        assert plan["unverified_fields"] == []

    def test_venue_contradiction_strips_without_the_no_evidence_key(self, tmp_path):
        """A contradicted venue strips as before, but only ABSENCE strips are
        recorded under venue_stripped_no_evidence - the key means what it
        says."""
        api = {"source": "crossref", "results": [
            {"doi": "10.1/c", "title": "Wrong Venue", "year": 2020,
             "container_title": "Synthese"}]}
        bib = (
            "@article{c2020,\n"
            "  author = {C, C.},\n"
            "  title = {Wrong Venue},\n"
            "  journal = {Mind},\n"
            "  year = {2020},\n"
            "  doi = {10.1/c}\n"
            "}\n"
        )
        plan, _ = _plan_for(tmp_path, bib, {"verify_c.json": api})
        assert plan["removed_field_names"] == ["journal"]
        assert plan["venue_stripped_no_evidence"] == []
