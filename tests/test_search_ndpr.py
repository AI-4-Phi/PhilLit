"""
Tests for search_ndpr.py (NDPR sitemap-based book review search).

Tests cover:
- Title normalization
- Slug extraction from URLs
- Title-slug matching/scoring
- Sitemap fetching with mocked responses
- End-to-end search with mocked sitemap
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "philosophy-research" / "scripts"))

import search_ndpr


# =============================================================================
# Title Normalization Tests
# =============================================================================

class TestNormalizeTitle:
    """Tests for title normalization."""

    def test_basic_title(self):
        assert search_ndpr.normalize_title("Being and Time") == "being and time"

    def test_strips_subtitle(self):
        result = search_ndpr.normalize_title("Being and Time: A Revised Edition")
        assert result == "being and time"

    def test_removes_punctuation(self):
        result = search_ndpr.normalize_title("What's It Like?")
        assert result == "whats it like"

    def test_collapses_whitespace(self):
        result = search_ndpr.normalize_title("Being   and    Time")
        assert result == "being and time"

    def test_empty_string(self):
        assert search_ndpr.normalize_title("") == ""


# =============================================================================
# Slug Extraction Tests
# =============================================================================

class TestSlugFromUrl:
    """Tests for URL slug extraction."""

    def test_basic_url(self):
        url = "https://ndpr.nd.edu/reviews/being-and-time/"
        assert search_ndpr.slug_from_url(url) == "being-and-time"

    def test_url_without_trailing_slash(self):
        url = "https://ndpr.nd.edu/reviews/being-and-time"
        assert search_ndpr.slug_from_url(url) == "being-and-time"

    def test_non_review_url(self):
        url = "https://ndpr.nd.edu/about/"
        assert search_ndpr.slug_from_url(url) == ""

    def test_complex_slug(self):
        url = "https://ndpr.nd.edu/reviews/al-ghazali-the-ideal-of-godlikeness/"
        assert search_ndpr.slug_from_url(url) == "al-ghazali-the-ideal-of-godlikeness"


# =============================================================================
# Scoring Tests
# =============================================================================

class TestScoreMatch:
    """Tests for title-slug scoring."""

    def test_exact_match(self):
        score = search_ndpr.score_match("being and time", "being-and-time")
        assert score >= 0.8

    def test_partial_match(self):
        score = search_ndpr.score_match("being and time", "being-and-time-a-revised-translation")
        assert score >= 0.6

    def test_no_match(self):
        score = search_ndpr.score_match("being and time", "critique-of-pure-reason")
        assert score < 0.3

    def test_author_bonus(self):
        # Use a case where base token overlap is moderate so author bonus is visible
        score_without = search_ndpr.score_match("reasons and persons", "reasons-persons-parfit")
        score_with = search_ndpr.score_match("reasons and persons", "reasons-persons-parfit", author="Parfit")
        assert score_with > score_without

    def test_empty_inputs(self):
        assert search_ndpr.score_match("", "some-slug") == 0.0
        assert search_ndpr.score_match("a b", "") == 0.0

    def test_single_token_title_rejected_without_author(self):
        """Single-token titles without author should score 0 to avoid false positives."""
        # "On Liberty" normalizes to "on liberty", but "on" is dropped (len < 3)
        # leaving only {"liberty"} — too ambiguous to match without author
        score = search_ndpr.score_match("liberty", "liberty-equality-fraternity")
        assert score == 0.0

    def test_single_token_title_allowed_with_author(self):
        """Single-token titles can match if author is confirmed in slug."""
        score = search_ndpr.score_match("liberty", "on-liberty-mill", author="Mill")
        assert score > 0.0

    def test_two_token_title_works(self):
        """Two-token titles should still match normally."""
        score = search_ndpr.score_match("after virtue", "after-virtue")
        assert score >= 0.8


# =============================================================================
# Sitemap Fetch Tests (Mocked)
# =============================================================================

MOCK_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://ndpr.nd.edu/reviews/being-and-time/</loc></url>
  <url><loc>https://ndpr.nd.edu/reviews/reasons-and-persons/</loc></url>
  <url><loc>https://ndpr.nd.edu/reviews/critique-of-pure-reason/</loc></url>
  <url><loc>https://ndpr.nd.edu/about/</loc></url>
  <url><loc>https://ndpr.nd.edu/reviews/a-theory-of-justice/</loc></url>
</urlset>"""


class TestFetchSitemap:
    """Tests for sitemap fetching."""

    def setup_method(self):
        """Clear sitemap cache before each test."""
        search_ndpr.clear_sitemap_cache()

    @patch("search_ndpr.requests.get")
    def test_fetch_sitemap_extracts_review_urls(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_SITEMAP_XML
        mock_get.return_value = mock_response

        from rate_limiter import RateLimiter
        limiter = RateLimiter("test_ndpr", 0.0)
        from rate_limiter import ExponentialBackoff
        backoff = ExponentialBackoff(max_attempts=1)

        urls = search_ndpr.fetch_sitemap(limiter, backoff)

        # Should only include /reviews/ URLs, not /about/
        assert len(urls) == 4
        assert all("/reviews/" in url for url in urls)

    @patch("search_ndpr.requests.get")
    def test_fetch_sitemap_empty_returns_empty_list(self, mock_get):
        """Sitemap with no /reviews/ URLs (e.g. sitemapindex) returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://ndpr.nd.edu/sitemap-posts.xml</loc></sitemap>
</sitemapindex>"""
        mock_get.return_value = mock_response

        from rate_limiter import RateLimiter, ExponentialBackoff
        limiter = RateLimiter("test_ndpr", 0.0)
        backoff = ExponentialBackoff(max_attempts=1)

        urls = search_ndpr.fetch_sitemap(limiter, backoff)

        assert urls == []

    @patch("search_ndpr.requests.get")
    def test_fetch_sitemap_caches(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_SITEMAP_XML
        mock_get.return_value = mock_response

        from rate_limiter import RateLimiter, ExponentialBackoff
        limiter = RateLimiter("test_ndpr", 0.0)
        backoff = ExponentialBackoff(max_attempts=1)

        urls1 = search_ndpr.fetch_sitemap(limiter, backoff)
        urls2 = search_ndpr.fetch_sitemap(limiter, backoff)

        # Should only fetch once due to caching
        assert mock_get.call_count == 1
        assert urls1 == urls2


# =============================================================================
# End-to-End Search Tests (Mocked)
# =============================================================================

class TestSearchNdpr:
    """Tests for the full search_ndpr function."""

    def setup_method(self):
        search_ndpr.clear_sitemap_cache()

    @patch("search_ndpr.requests.get")
    def test_finds_matching_review(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_SITEMAP_XML
        mock_get.return_value = mock_response

        result = search_ndpr.search_ndpr("Being and Time")

        assert result is not None
        assert result["slug"] == "being-and-time"
        assert result["score"] >= 0.6
        assert "ndpr.nd.edu/reviews/being-and-time" in result["url"]

    @patch("search_ndpr.requests.get")
    def test_returns_none_for_no_match(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_SITEMAP_XML
        mock_get.return_value = mock_response

        result = search_ndpr.search_ndpr("Phenomenology of Spirit")

        assert result is None

    @patch("search_ndpr.requests.get")
    def test_author_improves_matching(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_SITEMAP_XML
        mock_get.return_value = mock_response

        result = search_ndpr.search_ndpr("Reasons and Persons", author="Parfit")

        assert result is not None
        assert result["slug"] == "reasons-and-persons"
