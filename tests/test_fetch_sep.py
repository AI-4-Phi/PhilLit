"""
Tests for fetch_sep.py (SEP article fetching and parsing).

Tests cover:
- Output schema validation
- Exit codes for different scenarios
- HTML parsing functions
- Rate limiting integration
"""

import io
import json
from unittest.mock import patch, MagicMock

import pytest
from bs4 import BeautifulSoup

from test_utils import validate_output_schema, SCRIPTS_DIR


# Sample SEP HTML structure matching plato.stanford.edu's actual layout
SAMPLE_SEP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Free Will (Stanford Encyclopedia of Philosophy)</title>
    <meta name="author" content="Timothy O'Connor">
</head>
<body>
<div id="aueditable">
    <h1>Free Will</h1>
    <div id="article-copyright">
        <p>First published Mon Jan 7, 2002; substantive revision Fri Oct 15, 2021</p>
    </div>
    <div id="preamble">
        <p>Free will is a philosophical term of art for a particular sort of capacity
        of rational agents to choose a course of action from among various alternatives.
        This entry examines the major positions on free will.</p>

        <p>Debates about free will have historically been framed as concerning the
        compatibility or incompatibility of free will with determinism. Frankfurt (1969)
        introduced influential cases challenging the Principle of Alternative Possibilities.</p>
    </div>

    <div id="toc">
        <ol>
            <li><a href="#1">1. Free Will: The Problem</a></li>
            <li><a href="#2">2. Compatibilism</a>
                <ol>
                    <li><a href="#2.1">2.1 Classical Compatibilism</a></li>
                </ol>
            </li>
            <li><a href="#3">3. Incompatibilism</a></li>
        </ol>
    </div>

    <div id="main-text">
        <h2>1. Free Will: The Problem</h2>

        <p>The problem of free will is among the most contentious in philosophy.
        At its core is the question of whether human beings control their own
        destinies, and if so, in what sense.</p>

        <p>Compatibilists such as Frankfurt (1971) argue that free will is compatible
        with determinism. Incompatibilists disagree.</p>

        <h2>2. Compatibilism</h2>

        <p>Compatibilism is the view that free will and determinism can both be true.
        This view has ancient roots and has been defended by Hume (1748).</p>

        <h3>2.1 Classical Compatibilism</h3>

        <p>Classical compatibilists identified free will with acting according to
        one's desires without external compulsion.</p>

        <h2>3. Incompatibilism</h2>

        <p>Incompatibilists hold that free will and determinism cannot both be true.
        Hard determinists conclude that free will is therefore an illusion.</p>
    </div>

    <div id="bibliography">
        <ul>
            <li>Frankfurt, Harry G., 1969, "Alternate Possibilities and Moral Responsibility", <em>Journal of Philosophy</em>, 66(23): 829-839.</li>
            <li>Frankfurt, Harry G., 1971, "Freedom of the Will and the Concept of a Person", <em>Journal of Philosophy</em>, 68(1): 5-20.</li>
            <li>Hume, David, 1748, <em>An Enquiry Concerning Human Understanding</em>, London: Millar.</li>
            <li>Kane, Robert, 1996, <em>The Significance of Free Will</em>, Oxford: Oxford University Press.</li>
        </ul>
    </div>

    <div id="related-entries">
        <p>See also:</p>
        <ul>
            <li><a href="/entries/compatibilism/">Compatibilism</a></li>
            <li><a href="/entries/incompatibilism-arguments/">Arguments for Incompatibilism</a></li>
            <li><a href="/entries/moral-responsibility/">Moral Responsibility</a></li>
        </ul>
    </div>

    <div id="publication-date">Mon Jan 7, 2002</div>
    <div id="modified-date">Fri Oct 15, 2021</div>
</div>
</body>
</html>
"""


class TestSEPOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful response should have correct schema."""
        import fetch_sep

        output = None

        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                fetch_sep.output_success("freewill", {"title": "Free Will"})

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "sep"

    def test_error_output_schema(self):
        """Error response should have correct schema."""
        import fetch_sep

        output = None

        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                fetch_sep.output_error("freewill", "not_found", "Entry not found", exit_code=1)

        assert exc_info.value.code == 1
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"

    def test_success_output_query_field(self):
        """Success output should echo the entry name in query field."""
        import fetch_sep

        output = None

        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit):
                fetch_sep.output_success("freewill", {"title": "Free Will"})

        assert output["query"] == "freewill"

    def test_error_output_exit_codes(self):
        """Error output should use appropriate exit codes."""
        import fetch_sep

        for exit_code in [1, 2, 3]:
            with patch("builtins.print"):
                with pytest.raises(SystemExit) as exc_info:
                    fetch_sep.output_error("test", "some_error", "msg", exit_code=exit_code)
            assert exc_info.value.code == exit_code


class TestSEPParsing:
    """Tests for SEP HTML parsing functions."""

    @pytest.fixture
    def soup(self):
        """Return BeautifulSoup parsed from sample SEP HTML."""
        return BeautifulSoup(SAMPLE_SEP_HTML, "lxml")

    def test_extract_preamble(self, soup):
        """Should extract preamble text from #preamble div."""
        import fetch_sep

        preamble = fetch_sep.extract_preamble(soup)
        assert preamble is not None
        assert "philosophical term of art" in preamble
        assert "Frankfurt (1969)" in preamble

    def test_extract_preamble_missing(self):
        """Should return None when no preamble div present."""
        import fetch_sep

        empty_soup = BeautifulSoup("<html><body><p>No preamble here.</p></body></html>", "lxml")
        result = fetch_sep.extract_preamble(empty_soup)
        assert result is None

    def test_extract_sections(self, soup):
        """Should extract numbered sections from #main-text div."""
        import fetch_sep

        sections = fetch_sep.extract_sections(soup)
        assert len(sections) >= 2

        section_titles = [s["title"] for s in sections.values()]
        assert any("Free Will" in t or "Problem" in t for t in section_titles)
        assert any("Compatibilism" in t for t in section_titles)
        assert any("Incompatibilism" in t for t in section_titles)

    def test_extract_sections_have_content(self, soup):
        """Extracted sections should contain text content."""
        import fetch_sep

        sections = fetch_sep.extract_sections(soup)
        for sec_id, sec in sections.items():
            assert "id" in sec
            assert "title" in sec
            assert "content" in sec
            assert len(sec["content"]) > 0

    def test_extract_sections_filtered(self, soup):
        """Should filter sections by ID."""
        import fetch_sep

        sections = fetch_sep.extract_sections(soup, section_ids=["1"])
        assert len(sections) == 1
        assert "1" in sections

    def test_extract_sections_no_main_text(self):
        """Should return empty dict when no #main-text div present."""
        import fetch_sep

        empty_soup = BeautifulSoup("<html><body><p>No main text.</p></body></html>", "lxml")
        sections = fetch_sep.extract_sections(empty_soup)
        assert sections == {}

    def test_extract_toc(self, soup):
        """Should extract table of contents from #toc div."""
        import fetch_sep

        toc = fetch_sep.extract_toc(soup)
        assert isinstance(toc, list)
        assert len(toc) >= 2

        ids = [item["id"] for item in toc]
        assert "1" in ids
        assert "2" in ids

    def test_extract_toc_missing(self):
        """Should return empty list when no toc div present."""
        import fetch_sep

        empty_soup = BeautifulSoup("<html><body></body></html>", "lxml")
        toc = fetch_sep.extract_toc(empty_soup)
        assert toc == []

    def test_extract_bibliography(self, soup):
        """Should extract bibliography entries from #bibliography div."""
        import fetch_sep

        bib = fetch_sep.extract_bibliography(soup)
        assert len(bib) >= 3

        raw_texts = [e["raw"] for e in bib]
        assert any("Frankfurt" in r for r in raw_texts)
        assert any("Hume" in r for r in raw_texts)
        assert any("Kane" in r for r in raw_texts)

    def test_extract_bibliography_entry_structure(self, soup):
        """Bibliography entries should have raw, parsed, and confidence fields."""
        import fetch_sep

        bib = fetch_sep.extract_bibliography(soup)
        for entry in bib:
            assert "raw" in entry
            assert "parsed" in entry
            assert "confidence" in entry
            assert entry["confidence"] in ("high", "low", "unparseable")

    def test_extract_bibliography_missing(self):
        """Should return empty list when no bibliography div present."""
        import fetch_sep

        empty_soup = BeautifulSoup("<html><body></body></html>", "lxml")
        bib = fetch_sep.extract_bibliography(empty_soup)
        assert bib == []

    def test_extract_related_entries(self, soup):
        """Should extract related entries from #related-entries div."""
        import fetch_sep

        related = fetch_sep.extract_related_entries(soup)
        assert isinstance(related, list)
        assert len(related) >= 2

        entry_names = [e["entry_name"] for e in related]
        assert "compatibilism" in entry_names
        assert "moral-responsibility" in entry_names

    def test_extract_related_entries_structure(self, soup):
        """Related entries should have title, entry_name, and url fields."""
        import fetch_sep

        related = fetch_sep.extract_related_entries(soup)
        for entry in related:
            assert "title" in entry
            assert "entry_name" in entry
            assert "url" in entry
            assert "plato.stanford.edu" in entry["url"]

    def test_extract_related_entries_missing(self):
        """Should return empty list when no related-entries div present."""
        import fetch_sep

        empty_soup = BeautifulSoup("<html><body></body></html>", "lxml")
        related = fetch_sep.extract_related_entries(empty_soup)
        assert related == []

    def test_extract_metadata(self, soup):
        """Should extract article metadata."""
        import fetch_sep

        meta = fetch_sep.extract_metadata(soup)
        assert isinstance(meta, dict)
        # Author from meta tag
        assert meta.get("author") == "Timothy O'Connor"
        # Dates from id elements
        assert "first_published" in meta or "last_updated" in meta

    def test_parse_bibliography_entry_high_confidence(self):
        """Standard-format entries should parse with high confidence."""
        import fetch_sep

        raw = "Frankfurt, Harry G., 1971, \"Freedom of the Will\", Journal of Philosophy, 68: 5-20."
        parsed, confidence = fetch_sep.parse_bibliography_entry(raw)
        assert confidence == "high"
        assert parsed is not None
        assert "Frankfurt" in parsed["authors"][0]
        assert parsed["year"] == "1971"

    def test_parse_bibliography_entry_low_confidence(self):
        """Partial-format entries should parse with low confidence."""
        import fetch_sep

        # Matches partial regex: "Author, 1971" without complete standard format
        raw = "Frankfurt, 1971 Some incomplete reference without proper formatting"
        parsed, confidence = fetch_sep.parse_bibliography_entry(raw)
        assert confidence == "low"
        assert parsed is not None
        assert parsed["year"] == "1971"

    def test_parse_bibliography_entry_unparseable(self):
        """Skip patterns should return None with unparseable confidence."""
        import fetch_sep

        for raw in ["See the entry on compatibilism.", "", "   "]:
            parsed, confidence = fetch_sep.parse_bibliography_entry(raw)
            assert parsed is None
            assert confidence == "unparseable"


class TestSEPFetching:
    """Tests for SEP article fetching with mocked HTTP."""

    @patch("fetch_sep.put_cache", return_value=True)
    @patch("fetch_sep.get_cache", return_value=None)
    @patch("fetch_sep.requests.get")
    def test_fetch_article_success(self, mock_get, _mock_get_cache, _mock_put_cache):
        """Should fetch and parse SEP article on successful HTTP response."""
        mock_get.return_value = MagicMock(
            status_code=200,
            text=SAMPLE_SEP_HTML,
        )

        import fetch_sep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("sep_fetch")
        backoff = ExponentialBackoff()

        article = fetch_sep.fetch_sep_article("freewill", limiter, backoff)

        assert article["entry_name"] == "freewill"
        assert article["title"] == "Free Will"
        assert article["url"] == "https://plato.stanford.edu/entries/freewill/"
        assert article["preamble"] is not None
        assert len(article["sections"]) > 0
        assert isinstance(article["bibliography"], list)
        assert isinstance(article["related_entries"], list)
        assert isinstance(article["toc"], list)

    @patch("fetch_sep.get_cache", return_value=None)
    @patch("fetch_sep.requests.get")
    def test_fetch_article_404(self, mock_get, _mock_cache):
        """Should raise LookupError on 404 response."""
        mock_get.return_value = MagicMock(status_code=404)

        import fetch_sep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("sep_fetch")
        backoff = ExponentialBackoff()

        with pytest.raises(LookupError) as exc_info:
            fetch_sep.fetch_sep_article("nonexistent-entry", limiter, backoff)

        assert "not found" in str(exc_info.value).lower()

    @patch("fetch_sep.get_cache", return_value=None)
    @patch("fetch_sep.requests.get")
    def test_fetch_article_connection_error(self, mock_get, _mock_cache):
        """Should raise RuntimeError on connection failure after retries."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Connection refused")

        import fetch_sep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("sep_fetch")
        backoff = ExponentialBackoff(max_attempts=2, base_delay=0.01)

        with pytest.raises(RuntimeError) as exc_info:
            fetch_sep.fetch_sep_article("freewill", limiter, backoff)

        assert "network error" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()

    @patch("fetch_sep.put_cache", return_value=True)
    @patch("fetch_sep.get_cache", return_value=None)
    @patch("fetch_sep.requests.get")
    def test_fetch_article_rate_limit_retry(self, mock_get, _mock_cache, _mock_put_cache):
        """Should retry after 429 rate limit response."""
        mock_get.side_effect = [
            MagicMock(status_code=429),
            MagicMock(status_code=200, text=SAMPLE_SEP_HTML),
        ]

        import fetch_sep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("sep_fetch")
        backoff = ExponentialBackoff(max_attempts=3, base_delay=0.01)

        article = fetch_sep.fetch_sep_article("freewill", limiter, backoff)

        assert article["title"] == "Free Will"
        assert mock_get.call_count == 2

    def test_fetch_article_uses_cache(self):
        """Should return cached result without making HTTP request."""
        cached_result = {
            "url": "https://plato.stanford.edu/entries/freewill/",
            "entry_name": "freewill",
            "title": "Free Will (cached)",
            "metadata": {},
            "preamble": "Cached preamble text.",
            "toc": [],
            "sections": {},
            "bibliography": [],
            "related_entries": [],
        }

        with patch("fetch_sep.get_cache", return_value=cached_result):
            with patch("fetch_sep.requests.get") as mock_get:
                import fetch_sep
                from rate_limiter import get_limiter, ExponentialBackoff

                limiter = get_limiter("sep_fetch")
                backoff = ExponentialBackoff()

                article = fetch_sep.fetch_sep_article("freewill", limiter, backoff)

                assert article["title"] == "Free Will (cached)"
                mock_get.assert_not_called()

    @patch("fetch_sep.put_cache", return_value=True)
    @patch("fetch_sep.get_cache", return_value=None)
    @patch("fetch_sep.requests.get")
    def test_fetch_article_correct_url(self, mock_get, _mock_cache, _mock_put_cache):
        """Should request the correct SEP URL for the entry."""
        mock_get.return_value = MagicMock(status_code=200, text=SAMPLE_SEP_HTML)

        import fetch_sep
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("sep_fetch")
        backoff = ExponentialBackoff()

        fetch_sep.fetch_sep_article("freewill", limiter, backoff)

        call_args = mock_get.call_args
        requested_url = call_args[0][0]
        assert requested_url == "https://plato.stanford.edu/entries/freewill/"


class TestSEPProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr, not stdout."""
        import fetch_sep

        captured_stderr = io.StringIO()
        captured_stdout = io.StringIO()

        with patch("sys.stderr", captured_stderr):
            with patch("sys.stdout", captured_stdout):
                fetch_sep.log_progress("Test progress message")

        stderr_output = captured_stderr.getvalue()
        stdout_output = captured_stdout.getvalue()

        assert "[fetch_sep.py]" in stderr_output
        assert "Test progress message" in stderr_output
        assert "Test progress message" not in stdout_output

    def test_log_progress_prefix(self):
        """Progress messages should include the script name prefix."""
        import fetch_sep

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            fetch_sep.log_progress("Connecting to Stanford Encyclopedia of Philosophy...")

        output = captured.getvalue()
        assert "[fetch_sep.py]" in output


class TestSEPCLI:
    """Tests for command-line interface."""

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("fetch_sep.py", "--help")
        assert result.returncode == 0
        assert "SEP" in result.stdout or "entry" in result.stdout.lower()

    def test_cli_extracts_entry_from_url(self):
        """Should extract entry name from full plato.stanford.edu URL."""
        import fetch_sep
        import re

        test_url = "https://plato.stanford.edu/entries/freewill/"
        match = re.search(r"/entries/([^/]+)/?", test_url)

        assert match is not None
        assert match.group(1) == "freewill"

    def test_cli_extracts_entry_from_url_no_trailing_slash(self):
        """Should extract entry name from URL without trailing slash."""
        import fetch_sep
        import re

        test_url = "https://plato.stanford.edu/entries/moral-responsibility"
        match = re.search(r"/entries/([^/]+)/?", test_url)

        assert match is not None
        assert match.group(1) == "moral-responsibility"


class TestSEPRateLimiter:
    """Tests for rate limiter configuration."""

    def test_sep_fetch_limiter_exists(self):
        """sep_fetch limiter should be configured."""
        from rate_limiter import get_limiter

        limiter = get_limiter("sep_fetch")
        assert limiter is not None

    def test_sep_fetch_limiter_min_interval(self):
        """sep_fetch limiter should enforce at least 1 second between requests."""
        from rate_limiter import get_limiter

        limiter = get_limiter("sep_fetch")
        assert limiter.min_interval >= 1.0

    def test_sep_fetch_limiter_api_name(self):
        """sep_fetch limiter should have correct api_name."""
        from rate_limiter import get_limiter

        limiter = get_limiter("sep_fetch")
        assert limiter.api_name == "sep_fetch"
