"""
Tests for fetch_ndpr.py (NDPR review page fetching and summary extraction).

Tests cover:
- Paragraph extraction heuristics
- Metadata extraction (reviewer, date)
- Fetching with mocked HTTP responses
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "philosophy-research" / "scripts"))

import fetch_ndpr


# =============================================================================
# Sample HTML Fixtures
# =============================================================================

SAMPLE_REVIEW_HTML = """
<html>
<head>
<meta name="author" content="Jane Smith">
<meta property="article:published_time" content="2023-06-15T00:00:00Z">
</head>
<body>
<article>
<div class="entry-content">
<p>This is a very short metadata line.</p>
<p>In this ambitious and carefully argued book, the author develops a novel framework for understanding moral responsibility in the context of emerging technologies. Drawing on both analytic philosophy and phenomenological traditions, the work represents a significant contribution to applied ethics.</p>
<p>The book is organized into three main parts. The first part establishes the theoretical foundations, examining how traditional accounts of moral responsibility fail to adequately address cases involving artificial agents and automated decision-making systems.</p>
<p>The second part develops the author's positive proposal, which centers on what they call 'distributed responsibility.' This concept allows for meaningful attributions of moral responsibility even in cases where no single agent has full control over the outcome.</p>
<p>The third part applies this framework to specific cases, including autonomous vehicles, algorithmic hiring, and medical AI systems. Each case study demonstrates how the distributed responsibility framework handles cases that stymie traditional approaches.</p>
<p>However, there are some concerns with the framework as presented. The notion of distributed responsibility, while innovative, raises questions about whether it dilutes responsibility to the point of meaninglessness.</p>
<p>Furthermore, the author does not adequately address the epistemic dimensions of responsibility in these contexts.</p>
</div>
</article>
</body>
</html>
"""

SAMPLE_REVIEW_HTML_SHORT = """
<html>
<head></head>
<body>
<article>
<div class="entry-content">
<p>This book examines the nature of consciousness from a philosophical perspective. The author argues that phenomenal consciousness cannot be reduced to functional or physical properties, developing a sophisticated argument that builds on the zombie thought experiment.</p>
<p>The central thesis of the book is that there is an explanatory gap between physical processes and conscious experience that cannot be bridged by any amount of empirical research alone.</p>
<p>My main concern with this argument is that it relies too heavily on conceivability intuitions that may not be reliable guides to metaphysical possibility.</p>
</div>
</article>
</body>
</html>
"""

SAMPLE_REVIEW_HTML_NO_CONTENT = """
<html>
<head></head>
<body>
<div class="sidebar">Some sidebar content</div>
</body>
</html>
"""


# =============================================================================
# Content Extraction Tests
# =============================================================================

class TestExtractReviewContent:
    """Tests for HTML content extraction."""

    def test_extracts_summary_paragraphs(self):
        result = fetch_ndpr.extract_review_content(SAMPLE_REVIEW_HTML)

        # All 6 substantive paragraphs extracted (MAX_PARAGRAPHS=8 cap not hit)
        assert result["paragraph_count"] == 6
        assert "ambitious and carefully argued" in result["summary_text"]
        assert "distributed responsibility" in result["summary_text"]
        # Evaluative paragraphs now included (no detection/cutoff)
        assert "However, there are some concerns" in result["summary_text"]

    def test_extracts_metadata(self):
        result = fetch_ndpr.extract_review_content(SAMPLE_REVIEW_HTML)

        assert result["reviewer"] == "Jane Smith"
        assert result["review_date"] == "2023-06-15"

    def test_extracts_all_short_review(self):
        """Short review: all substantive paragraphs extracted."""
        result = fetch_ndpr.extract_review_content(SAMPLE_REVIEW_HTML_SHORT)

        # All 3 substantive paragraphs extracted (well under MAX_PARAGRAPHS cap)
        assert result["paragraph_count"] == 3

    def test_no_content_div(self):
        result = fetch_ndpr.extract_review_content(SAMPLE_REVIEW_HTML_NO_CONTENT)

        assert result["summary_text"] == ""
        assert result["paragraph_count"] == 0

    def test_returns_paragraphs_list(self):
        result = fetch_ndpr.extract_review_content(SAMPLE_REVIEW_HTML)

        assert isinstance(result["paragraphs"], list)
        assert len(result["paragraphs"]) == result["paragraph_count"]

    def test_skips_short_paragraphs(self):
        """Short paragraphs (< 50 chars) should be filtered out."""
        result = fetch_ndpr.extract_review_content(SAMPLE_REVIEW_HTML)

        # "This is a very short metadata line." is < 50 chars
        for p in result["paragraphs"]:
            assert len(p) >= 50


# =============================================================================
# Fetch Tests (Mocked)
# =============================================================================

class TestFetchNdprReview:
    """Tests for the full fetch function with mocked HTTP."""

    @patch("fetch_ndpr.requests.get")
    def test_fetches_and_extracts(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_REVIEW_HTML
        mock_get.return_value = mock_response

        result = fetch_ndpr.fetch_ndpr_review("https://ndpr.nd.edu/reviews/test-book/")

        assert result["review_url"] == "https://ndpr.nd.edu/reviews/test-book/"
        assert result["paragraph_count"] == 6
        assert result["reviewer"] == "Jane Smith"

    @patch("fetch_ndpr.requests.get")
    def test_handles_404(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        with pytest.raises(LookupError, match="not found"):
            fetch_ndpr.fetch_ndpr_review("https://ndpr.nd.edu/reviews/nonexistent/")

    @patch("fetch_ndpr.requests.get")
    def test_handles_network_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Connection refused")

        with pytest.raises(RuntimeError, match="Network error"):
            fetch_ndpr.fetch_ndpr_review("https://ndpr.nd.edu/reviews/test/")
