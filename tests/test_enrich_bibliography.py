"""
Tests for enrich_bibliography.py (bibliography enrichment orchestrator).

Tests cover:
- BibTeX parsing
- Abstract field detection
- Entry modification
- INCOMPLETE flag handling
- Batch processing
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "literature-review" / "scripts"))


# =============================================================================
# Sample BibTeX Data
# =============================================================================

SAMPLE_ENTRY_NO_ABSTRACT = """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971},
  doi = {10.2307/2024717},
  keywords = {free-will, compatibilism, High},
}"""

SAMPLE_ENTRY_WITH_ABSTRACT = """@article{wolf1990freedom,
  author = {Wolf, Susan},
  title = {Freedom Within Reason},
  journal = {Philosophy and Phenomenological Research},
  year = {1990},
  doi = {10.2307/2107766},
  abstract = {This paper argues that freedom requires the ability to act in accordance with reason.},
  keywords = {free-will, reason, Medium},
}"""

SAMPLE_ENTRY_INCOMPLETE = """@article{test2020paper,
  author = {Test, Author},
  title = {A Test Paper},
  year = {2020},
  keywords = {testing, INCOMPLETE, no-abstract},
}"""

SAMPLE_COMMENT = """@comment{
  DOMAIN: Testing Domain
  NOTABLE_GAPS: None identified
}"""


# =============================================================================
# Parsing Tests
# =============================================================================

class TestBibTeXParsing:
    """Tests for BibTeX parsing functionality."""

    def test_parse_basic_entry(self):
        """Should parse basic BibTeX entry."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)

        assert len(entries) == 1
        assert entries[0]['entry_type'] == 'article'
        assert entries[0]['key'] == 'frankfurt1971freedom'
        assert entries[0]['fields']['author'] == 'Frankfurt, Harry G.'
        assert entries[0]['fields']['year'] == '1971'

    def test_parse_entry_with_abstract(self):
        """Should parse entry with abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_WITH_ABSTRACT)

        assert len(entries) == 1
        assert 'abstract' in entries[0]['fields']
        assert 'reason' in entries[0]['fields']['abstract']

    def test_parse_multiple_entries(self):
        """Should parse multiple entries."""
        import enrich_bibliography

        content = f"{SAMPLE_ENTRY_NO_ABSTRACT}\n\n{SAMPLE_ENTRY_WITH_ABSTRACT}"
        entries = enrich_bibliography.parse_bibtex_entries(content)

        assert len(entries) == 2

    def test_parse_comment_entry(self):
        """Should parse @comment entries."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_COMMENT)

        assert len(entries) == 1
        assert entries[0]['entry_type'] == 'comment'


class TestFieldDetection:
    """Tests for field detection helpers."""

    def test_has_abstract_true(self):
        """Should detect existing abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_WITH_ABSTRACT)
        assert enrich_bibliography.has_abstract(entries[0]) is True

    def test_has_abstract_false(self):
        """Should detect missing abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        assert enrich_bibliography.has_abstract(entries[0]) is False

    def test_is_incomplete_true(self):
        """Should detect INCOMPLETE flag."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_INCOMPLETE)
        assert enrich_bibliography.is_incomplete(entries[0]) is True

    def test_is_incomplete_false(self):
        """Should detect missing INCOMPLETE flag."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        assert enrich_bibliography.is_incomplete(entries[0]) is False

    def test_get_doi(self):
        """Should extract DOI from entry."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        doi = enrich_bibliography.get_doi(entries[0])
        assert doi == "10.2307/2024717"

    def test_get_author_last_name(self):
        """Should extract author last name."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        last_name = enrich_bibliography.get_author_last_name(entries[0])
        assert last_name == "Frankfurt"

    def test_get_year(self):
        """Should extract year from entry."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        year = enrich_bibliography.get_year(entries[0])
        assert year == 1971


# =============================================================================
# Entry Modification Tests
# =============================================================================

class TestEntryModification:
    """Tests for BibTeX entry modification."""

    def test_add_field_to_entry(self):
        """Should add new field to entry."""
        import enrich_bibliography

        result = enrich_bibliography.add_field_to_entry(
            SAMPLE_ENTRY_NO_ABSTRACT,
            'abstract',
            'This is a test abstract.'
        )

        assert 'abstract = {This is a test abstract.}' in result

    def test_add_keyword_to_entry_new(self):
        """Should add keyword to entry without keywords."""
        import enrich_bibliography

        entry_no_keywords = """@article{test,
  author = {Test},
  title = {Test},
  year = {2020},
}"""

        result = enrich_bibliography.add_keyword_to_entry(
            entry_no_keywords,
            'INCOMPLETE'
        )

        assert 'keywords = {INCOMPLETE}' in result

    def test_add_keyword_to_entry_existing(self):
        """Should append keyword to existing keywords."""
        import enrich_bibliography

        result = enrich_bibliography.add_keyword_to_entry(
            SAMPLE_ENTRY_NO_ABSTRACT,
            'INCOMPLETE'
        )

        assert 'INCOMPLETE' in result
        # Original keywords should still be there
        assert 'free-will' in result

    def test_add_keyword_already_present(self):
        """Should not duplicate existing keyword."""
        import enrich_bibliography

        result = enrich_bibliography.add_keyword_to_entry(
            SAMPLE_ENTRY_INCOMPLETE,
            'INCOMPLETE'
        )

        # Should only have one INCOMPLETE
        assert result.count('INCOMPLETE') == 1


# =============================================================================
# Enrichment Tests
# =============================================================================

class TestEnrichment:
    """Tests for entry enrichment logic."""

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_entry_success(self, mock_resolve):
        """Should add abstract when found."""
        mock_resolve.return_value = ("This is the resolved abstract.", "openalex")

        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        enriched_text, was_enriched, source = enrich_bibliography.enrich_entry(
            entries[0], None, None, None
        )

        assert was_enriched is True
        assert source == "openalex"
        assert 'abstract = {' in enriched_text
        assert 'abstract_source = {openalex}' in enriched_text

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_entry_not_found(self, mock_resolve):
        """Should mark INCOMPLETE when abstract not found."""
        mock_resolve.return_value = (None, None)

        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        enriched_text, was_enriched, source = enrich_bibliography.enrich_entry(
            entries[0], None, None, None
        )

        assert was_enriched is False
        assert source is None
        assert 'INCOMPLETE' in enriched_text
        assert 'no-abstract' in enriched_text

    def test_enrich_entry_skips_existing_abstract(self):
        """Should skip entries that already have abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_WITH_ABSTRACT)
        enriched_text, was_enriched, source = enrich_bibliography.enrich_entry(
            entries[0], None, None, None
        )

        assert was_enriched is False
        # Original abstract should be preserved
        assert 'accordance with reason' in enriched_text


# =============================================================================
# Batch Processing Tests
# =============================================================================

class TestBatchProcessing:
    """Tests for batch bibliography enrichment."""

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_mixed(self, mock_resolve):
        """Should handle mixed entries correctly."""
        # Return abstract for first call, None for subsequent
        mock_resolve.side_effect = [
            ("Found abstract", "core"),
            (None, None),
        ]

        import enrich_bibliography

        # Create temp input file
        content = f"{SAMPLE_ENTRY_NO_ABSTRACT}\n\n{SAMPLE_ENTRY_INCOMPLETE}"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(content)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            stats = enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            assert stats['total'] == 2
            assert stats['enriched'] == 1
            assert stats['marked_incomplete'] == 1

            # Check output file
            output_content = output_path.read_text()
            assert 'Found abstract' in output_content
            assert 'abstract_source = {core}' in output_content

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_preserves_comments(self, mock_resolve):
        """Should preserve @comment entries."""
        mock_resolve.return_value = ("Abstract", "s2")

        import enrich_bibliography

        content = f"{SAMPLE_COMMENT}\n\n{SAMPLE_ENTRY_NO_ABSTRACT}"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(content)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            stats = enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            assert stats['skipped'] == 1  # Comment was skipped

            output_content = output_path.read_text()
            assert 'DOMAIN: Testing Domain' in output_content

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()

    def test_enrich_bibliography_file_not_found(self):
        """Should raise error for missing input file."""
        import enrich_bibliography

        with pytest.raises(FileNotFoundError):
            enrich_bibliography.enrich_bibliography(
                Path("/nonexistent/file.bib"), None, None, None, None
            )

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_inplace(self, mock_resolve):
        """Should overwrite input when no output specified."""
        mock_resolve.return_value = ("Inplace abstract", "openalex")

        import enrich_bibliography

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(SAMPLE_ENTRY_NO_ABSTRACT)
            input_path = Path(f.name)

        try:
            enrich_bibliography.enrich_bibliography(
                input_path, None, None, None, None  # No output path = inplace
            )

            output_content = input_path.read_text()
            assert 'Inplace abstract' in output_content

        finally:
            input_path.unlink()


# =============================================================================
# Stats Tests
# =============================================================================

class TestStats:
    """Tests for statistics tracking."""

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_stats_tracks_sources(self, mock_resolve):
        """Should track abstract sources in stats."""
        # Mix of sources
        mock_resolve.side_effect = [
            ("Abstract 1", "s2"),
            ("Abstract 2", "openalex"),
            ("Abstract 3", "core"),
        ]

        import enrich_bibliography

        # Three entries without abstract
        entry = """@article{test%d,
  author = {Test},
  title = {Test %d},
  year = {2020},
  doi = {10.1234/test%d},
}"""
        content = "\n\n".join(entry % (i, i, i) for i in range(3))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(content)
            input_path = Path(f.name)

        try:
            stats = enrich_bibliography.enrich_bibliography(
                input_path, None, None, None, None
            )

            assert stats['enriched'] == 3
            assert stats['sources']['s2'] == 1
            assert stats['sources']['openalex'] == 1
            assert stats['sources']['core'] == 1

        finally:
            input_path.unlink()
