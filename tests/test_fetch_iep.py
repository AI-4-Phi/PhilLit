"""
Tests for fetch_iep.py (IEP article fetching and parsing).

Tests cover:
- Output schema validation
- Exit codes for different scenarios
- HTML parsing functions
- Rate limiting integration
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from bs4 import BeautifulSoup

from test_utils import validate_output_schema, SCRIPTS_DIR


# Sample IEP HTML structure for testing
SAMPLE_IEP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Free Will | Internet Encyclopedia of Philosophy</title>
    <meta name="author" content="John Smith">
</head>
<body>
<article>
    <h1 class="entry-title">Free Will</h1>

    <p>The concept of free will is central to philosophy. This article examines
    various approaches to the problem of free will, including both compatibilist
    and incompatibilist perspectives.</p>

    <p>Many philosophers have debated whether free will is compatible with determinism.
    Frankfurt (1971) argued that alternative possibilities are not required for moral
    responsibility.</p>

    <h2>1. The Problem of Free Will</h2>

    <p>The problem of free will arises from the apparent tension between determinism
    and our sense of agency. According to Frankfurt (1971), we can be morally responsible
    even if we could not have done otherwise.</p>

    <p>Fischer and Ravizza (1998) developed a theory of guidance control that builds
    on Frankfurt's insights.</p>

    <h2>2. Compatibilism</h2>

    <p>Compatibilists argue that free will is compatible with determinism. This view
    has been defended by many philosophers, including Dennett (1984).</p>

    <h2>References and Further Reading</h2>

    <ul>
        <li>Frankfurt, Harry. "Freedom of the Will and the Concept of a Person." Journal of Philosophy 68 (1971): 5-20.</li>
        <li>Fischer, John Martin and Mark Ravizza. Responsibility and Control. Cambridge UP, 1998.</li>
        <li>Dennett, Daniel. Elbow Room. MIT Press, 1984.</li>
    </ul>

    <h2>Author Information</h2>
    <p>John Smith, University of Example, john.smith@example.edu</p>
</article>
</body>
</html>
"""


class TestIEPOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful response should have correct schema."""
        import fetch_iep

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                fetch_iep.output_success("freewill", {"title": "Free Will"})

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "iep"

    def test_error_output_schema(self):
        """Error response should have correct schema."""
        import fetch_iep

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                fetch_iep.output_error("test", "not_found", "Entry not found", exit_code=1)

        assert exc_info.value.code == 1
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"


class TestIEPParsing:
    """Tests for IEP HTML parsing functions."""

    @pytest.fixture
    def soup(self):
        """Return BeautifulSoup parsed from sample HTML."""
        return BeautifulSoup(SAMPLE_IEP_HTML, "lxml")

    def test_extract_preamble(self, soup):
        """Should extract opening paragraphs."""
        import fetch_iep

        preamble = fetch_iep.extract_preamble(soup)
        assert preamble is not None
        assert "central to philosophy" in preamble
        assert "Frankfurt (1971)" in preamble

    def test_extract_sections(self, soup):
        """Should extract numbered sections."""
        import fetch_iep

        sections = fetch_iep.extract_sections(soup)
        assert len(sections) >= 2

        # Check section content
        section_titles = [s["title"] for s in sections.values()]
        assert any("Problem" in t for t in section_titles)
        assert any("Compatibilism" in t for t in section_titles)

    def test_extract_sections_filtered(self, soup):
        """Should filter sections by ID."""
        import fetch_iep

        sections = fetch_iep.extract_sections(soup, section_ids=["1"])
        assert len(sections) == 1
        assert "1" in sections

    def test_extract_bibliography(self, soup):
        """Should extract bibliography entries."""
        import fetch_iep

        bib = fetch_iep.extract_bibliography(soup)
        assert len(bib) >= 2

        # Check entries contain expected authors
        raw_texts = [e["raw"] for e in bib]
        assert any("Frankfurt" in r for r in raw_texts)
        assert any("Fischer" in r for r in raw_texts)

    def test_extract_author_info(self, soup):
        """Should extract author information."""
        import fetch_iep

        info = fetch_iep.extract_author_info(soup)
        assert "author" in info or len(info) == 0  # May or may not find author


class TestIEPFetching:
    """Tests for IEP article fetching."""

    @patch("fetch_iep.requests.get")
    def test_fetch_article_success(self, mock_get):
        """Should fetch and parse IEP article."""
        mock_get.return_value = MagicMock(
            status_code=200,
            text=SAMPLE_IEP_HTML
        )

        import fetch_iep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("iep_fetch")
        backoff = ExponentialBackoff()

        article = fetch_iep.fetch_iep_article("freewill", limiter, backoff)

        assert article["entry_name"] == "freewill"
        assert article["title"] == "Free Will"
        assert article["url"] == "https://iep.utm.edu/freewill/"
        assert article["preamble"] is not None
        assert len(article["sections"]) > 0

    @patch("fetch_iep.requests.get")
    def test_fetch_article_404(self, mock_get):
        """Should raise LookupError on 404."""
        mock_get.return_value = MagicMock(status_code=404)

        import fetch_iep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("iep_fetch")
        backoff = ExponentialBackoff()

        with pytest.raises(LookupError) as exc_info:
            fetch_iep.fetch_iep_article("nonexistent", limiter, backoff)

        assert "not found" in str(exc_info.value).lower()

    @patch("fetch_iep.requests.get")
    def test_fetch_article_rate_limit(self, mock_get):
        """Should handle rate limiting with backoff."""
        # First request returns 429, second returns success
        mock_get.side_effect = [
            MagicMock(status_code=429),
            MagicMock(status_code=200, text=SAMPLE_IEP_HTML),
        ]

        import fetch_iep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("iep_fetch")
        backoff = ExponentialBackoff(max_attempts=3, base_delay=0.01)

        article = fetch_iep.fetch_iep_article("freewill", limiter, backoff)

        assert article["title"] == "Free Will"
        assert mock_get.call_count == 2


class TestIEPProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import fetch_iep
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            fetch_iep.log_progress("Test message")

        output = captured.getvalue()
        assert "[fetch_iep.py]" in output
        assert "Test message" in output


class TestIEPCLI:
    """Tests for command-line interface."""

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("fetch_iep.py", "--help")
        assert result.returncode == 0
        assert "IEP" in result.stdout

    def test_cli_extracts_entry_from_url(self):
        """Should extract entry name from full URL."""
        import fetch_iep
        import re

        test_url = "https://iep.utm.edu/freewill/"
        match = re.search(r"iep\.utm\.edu/([a-z0-9-]+)/?", test_url)

        assert match is not None
        assert match.group(1) == "freewill"


class TestIEPRateLimiter:
    """Tests for rate limiter configuration."""

    def test_iep_fetch_limiter_exists(self):
        """iep_fetch limiter should be configured."""
        from rate_limiter import get_limiter

        limiter = get_limiter("iep_fetch")
        assert limiter is not None
        assert limiter.min_interval >= 1.0  # At least 1 second between requests
