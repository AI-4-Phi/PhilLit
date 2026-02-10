"""
Tests for NDPR enrichment integration in enrich_bibliography.py.

Tests cover:
- NDPR pass targets only @book entries without abstracts
- NDPR pass skips @article entries
- NDPR pass skips books that already have abstracts
- remove_keyword_from_entry helper
- Stats tracking for NDPR source
- Integration test for resolve_ndpr_abstract import chain
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "literature-review" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "philosophy-research" / "scripts"))


# =============================================================================
# Sample BibTeX Data
# =============================================================================

SAMPLE_BOOK_NO_ABSTRACT = """@book{rawls1971theory,
  author = {Rawls, John},
  title = {A Theory of Justice},
  publisher = {Harvard University Press},
  year = {1971},
  keywords = {justice, political-philosophy, High},
}"""

SAMPLE_BOOK_WITH_ABSTRACT = """@book{nozick1974anarchy,
  author = {Nozick, Robert},
  title = {Anarchy, State, and Utopia},
  publisher = {Basic Books},
  year = {1974},
  abstract = {This book argues for a minimal state limited to protection against force and fraud.},
  keywords = {libertarianism, political-philosophy, High},
}"""

SAMPLE_ARTICLE_NO_ABSTRACT = """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971},
  doi = {10.2307/2024717},
  keywords = {free-will, compatibilism, High},
}"""

SAMPLE_BOOK_INCOMPLETE = """@book{parfit1984reasons,
  author = {Parfit, Derek},
  title = {Reasons and Persons},
  publisher = {Oxford University Press},
  year = {1984},
  keywords = {personal-identity, ethics, High, INCOMPLETE, no-abstract},
}"""


# =============================================================================
# remove_keyword_from_entry Tests
# =============================================================================

class TestRemoveKeyword:
    """Tests for remove_keyword_from_entry helper."""

    def test_remove_existing_keyword(self):
        import enrich_bibliography

        result = enrich_bibliography.remove_keyword_from_entry(
            SAMPLE_BOOK_INCOMPLETE,
            'INCOMPLETE'
        )

        assert 'INCOMPLETE' not in result
        assert 'no-abstract' in result
        assert 'personal-identity' in result

    def test_remove_last_keyword_of_type(self):
        import enrich_bibliography

        result = enrich_bibliography.remove_keyword_from_entry(
            SAMPLE_BOOK_INCOMPLETE,
            'no-abstract'
        )

        assert 'no-abstract' not in result
        assert 'INCOMPLETE' in result

    def test_remove_nonexistent_keyword(self):
        import enrich_bibliography

        result = enrich_bibliography.remove_keyword_from_entry(
            SAMPLE_BOOK_NO_ABSTRACT,
            'INCOMPLETE'
        )

        # Should be unchanged
        assert 'justice' in result
        assert 'High' in result

    def test_remove_from_entry_without_keywords(self):
        import enrich_bibliography

        entry = """@book{test2020,
  author = {Test},
  title = {Test},
  year = {2020},
}"""
        result = enrich_bibliography.remove_keyword_from_entry(entry, 'INCOMPLETE')
        assert result == entry


# =============================================================================
# NDPR Enrichment Pass Tests
# =============================================================================

class TestNdprEnrichmentPass:
    """Tests for NDPR enrichment targeting in enrich_bibliography."""

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    @patch("enrich_bibliography.resolve_ndpr_abstract")
    def test_ndpr_targets_only_books_without_abstract(self, mock_ndpr, mock_resolve):
        """NDPR pass should only target @book entries marked INCOMPLETE."""
        # Main loop: no abstract found for anything
        mock_resolve.return_value = (None, None)
        # NDPR: returns abstract for book
        mock_ndpr.return_value = ("Summary of the book from NDPR review.", "ndpr")

        import enrich_bibliography

        content = f"{SAMPLE_BOOK_NO_ABSTRACT}\n\n{SAMPLE_ARTICLE_NO_ABSTRACT}"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(content)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            stats = enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            # NDPR should have been called once (for the book)
            assert mock_ndpr.call_count == 1
            call_args = mock_ndpr.call_args
            assert "Theory of Justice" in call_args[0][0]

            # Book should be enriched, article should be incomplete
            assert stats['sources']['ndpr'] == 1
            assert stats['enriched'] == 1
            assert stats['marked_incomplete'] == 1  # article stays incomplete

            output_content = output_path.read_text()
            assert 'Summary of the book from NDPR review.' in output_content
            assert 'abstract_source = {ndpr}' in output_content

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    @patch("enrich_bibliography.resolve_ndpr_abstract")
    def test_ndpr_skips_books_with_abstract(self, mock_ndpr, mock_resolve):
        """NDPR pass should skip books that already have abstracts."""
        mock_resolve.return_value = (None, None)

        import enrich_bibliography

        # One book with abstract, one without
        content = f"{SAMPLE_BOOK_WITH_ABSTRACT}\n\n{SAMPLE_BOOK_NO_ABSTRACT}"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(content)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            mock_ndpr.return_value = ("NDPR summary", "ndpr")

            stats = enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            # Only the book without abstract should trigger NDPR
            assert mock_ndpr.call_count == 1
            assert stats['already_had_abstract'] == 1

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    @patch("enrich_bibliography.resolve_ndpr_abstract")
    def test_ndpr_removes_incomplete_flag(self, mock_ndpr, mock_resolve):
        """When NDPR succeeds, INCOMPLETE and no-abstract flags should be removed."""
        mock_resolve.return_value = (None, None)
        mock_ndpr.return_value = ("NDPR book summary text here.", "ndpr")

        import enrich_bibliography

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(SAMPLE_BOOK_NO_ABSTRACT)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            stats = enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            output_content = output_path.read_text()
            assert 'INCOMPLETE' not in output_content
            assert 'no-abstract' not in output_content
            assert 'abstract_source = {ndpr}' in output_content

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    @patch("enrich_bibliography.resolve_ndpr_abstract")
    def test_ndpr_failure_leaves_incomplete(self, mock_ndpr, mock_resolve):
        """When NDPR fails, entry should remain INCOMPLETE."""
        mock_resolve.return_value = (None, None)
        mock_ndpr.return_value = (None, None)

        import enrich_bibliography

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(SAMPLE_BOOK_NO_ABSTRACT)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            stats = enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            assert stats['marked_incomplete'] == 1
            assert stats['sources']['ndpr'] == 0

            output_content = output_path.read_text()
            assert 'INCOMPLETE' in output_content

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    @patch("enrich_bibliography.resolve_ndpr_abstract")
    def test_ndpr_not_called_for_articles(self, mock_ndpr, mock_resolve):
        """NDPR should not be called for @article entries."""
        mock_resolve.return_value = (None, None)

        import enrich_bibliography

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(SAMPLE_ARTICLE_NO_ABSTRACT)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            # NDPR should never be called for articles
            assert mock_ndpr.call_count == 0

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_ndpr_stats_in_initial_sources(self, mock_resolve):
        """Stats dict should include 'ndpr' key from the start."""
        mock_resolve.return_value = ("Abstract", "s2")

        import enrich_bibliography

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(SAMPLE_ARTICLE_NO_ABSTRACT)
            input_path = Path(f.name)

        output_path = input_path.with_suffix('.enriched.bib')

        try:
            stats = enrich_bibliography.enrich_bibliography(
                input_path, output_path, None, None, None
            )

            assert 'ndpr' in stats['sources']
            assert stats['sources']['ndpr'] == 0

        finally:
            input_path.unlink()
            if output_path.exists():
                output_path.unlink()


# =============================================================================
# Integration Test — resolve_ndpr_abstract import chain
# =============================================================================

MOCK_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://ndpr.nd.edu/reviews/a-theory-of-justice/</loc></url>
</urlset>"""

MOCK_REVIEW_HTML = """<html><body><article><div class="entry-content">
<p>In this landmark work, Rawls develops a comprehensive theory of justice as fairness, arguing that principles of justice are those that would be chosen by rational agents behind a veil of ignorance.</p>
<p>The book's central argument proceeds through an elaborate thought experiment in which parties in an 'original position' must choose principles to govern the basic structure of society without knowing their particular place in it.</p>
<p>Rawls argues that two principles would emerge from this procedure: first, that each person has an equal right to the most extensive basic liberties compatible with similar liberties for others.</p>
</div></article></body></html>"""


class TestResolveNdprAbstractIntegration:
    """Integration test exercising the real import chain inside resolve_ndpr_abstract."""

    @patch("requests.get")
    def test_resolve_ndpr_abstract_real_imports(self, mock_get):
        """Exercise the actual search_ndpr/fetch_ndpr imports inside resolve_ndpr_abstract."""
        import search_ndpr
        search_ndpr.clear_sitemap_cache()

        # Return different responses based on URL
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "sitemap" in url:
                resp.text = MOCK_SITEMAP_XML
            else:
                resp.text = MOCK_REVIEW_HTML
            return resp

        mock_get.side_effect = side_effect

        import enrich_bibliography
        abstract, source = enrich_bibliography.resolve_ndpr_abstract(
            "A Theory of Justice", "Rawls"
        )

        assert source == "ndpr"
        assert abstract is not None
        assert "veil of ignorance" in abstract

        search_ndpr.clear_sitemap_cache()

    @patch("requests.get")
    def test_resolve_ndpr_abstract_no_match(self, mock_get):
        """Returns (None, None) when no NDPR review matches."""
        import search_ndpr
        search_ndpr.clear_sitemap_cache()

        sitemap_response = MagicMock()
        sitemap_response.status_code = 200
        sitemap_response.text = MOCK_SITEMAP_XML
        mock_get.return_value = sitemap_response

        import enrich_bibliography
        abstract, source = enrich_bibliography.resolve_ndpr_abstract(
            "Phenomenology of Spirit", "Hegel"
        )

        assert abstract is None
        assert source is None

        search_ndpr.clear_sitemap_cache()
