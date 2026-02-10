"""
Tests for search_core.py (CORE API search).

Tests cover:
- Output schema validation
- Exit codes for different scenarios
- Work formatting
- DOI lookup
- Title + author search
- Rate limiting
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


# =============================================================================
# Mock Response Fixture
# =============================================================================

@pytest.fixture
def mock_core_response():
    """Sample CORE API response."""
    return {
        "totalHits": 2,
        "results": [
            {
                "id": 12345678,
                "doi": "10.2307/2024717",
                "title": "Freedom of the Will and the Concept of a Person",
                "authors": [{"name": "Harry G. Frankfurt"}],
                "yearPublished": 1971,
                "abstract": "This paper examines the relationship between freedom of the will and the concept of a person.",
                "publisher": "Philosophy Documentation Center",
                "journals": [{"title": "The Journal of Philosophy"}],
                "downloadUrl": "https://core.ac.uk/download/12345678.pdf",
                "language": {"code": "en"},
                "documentType": "research",
            },
            {
                "id": 87654321,
                "doi": "10.1093/mind/xyz123",
                "title": "Compatibilism and Moral Responsibility",
                "authors": [{"name": "Susan Wolf"}],
                "yearPublished": 1990,
                "abstract": "An exploration of compatibilist accounts of moral responsibility.",
                "publisher": "Oxford University Press",
                "journals": [{"title": "Mind"}],
                "downloadUrl": None,
                "language": "en",
                "documentType": "research",
            },
        ],
    }


@pytest.fixture
def mock_core_empty_response():
    """Empty CORE API response."""
    return {
        "totalHits": 0,
        "results": [],
    }


# =============================================================================
# Output Schema Tests
# =============================================================================

class TestCoreOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful response should have correct schema."""
        import search_core

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                search_core.output_success("test query", [{"title": "Test"}])

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "core"

    def test_error_output_schema(self):
        """Error response should have correct schema."""
        import search_core

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                search_core.output_error("test", "api_error", "Test error", exit_code=3)

        assert exc_info.value.code == 3
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"

    def test_partial_output_schema(self):
        """Partial response should have correct schema."""
        import search_core

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                search_core.output_partial(
                    "test",
                    [{"title": "Result"}],
                    [{"type": "rate_limit", "message": "Limited", "recoverable": True}],
                    "Partial results"
                )

        assert exc_info.value.code == 0
        assert output["status"] == "partial"
        assert len(output["errors"]) == 1


# =============================================================================
# Format Work Tests
# =============================================================================

class TestCoreFormatWork:
    """Tests for work formatting."""

    def test_format_work_basic(self, mock_core_response):
        """format_work should extract basic fields."""
        import search_core

        work = mock_core_response["results"][0]
        formatted = search_core.format_work(work)

        assert formatted["core_id"] == "12345678"
        assert formatted["doi"] == "10.2307/2024717"
        assert formatted["title"] == "Freedom of the Will and the Concept of a Person"
        assert formatted["year"] == 1971
        assert formatted["abstract"] is not None
        assert "freedom" in formatted["abstract"].lower()

    def test_format_work_extracts_authors(self, mock_core_response):
        """format_work should extract author information."""
        import search_core

        work = mock_core_response["results"][0]
        formatted = search_core.format_work(work)

        assert len(formatted["authors"]) == 1
        assert formatted["authors"][0]["name"] == "Harry G. Frankfurt"

    def test_format_work_handles_missing_doi(self):
        """format_work should handle missing DOI."""
        import search_core

        work = {
            "id": 999,
            "title": "No DOI Paper",
            "yearPublished": 2024,
        }

        formatted = search_core.format_work(work)
        assert formatted["doi"] is None

    def test_format_work_strips_doi_prefix(self):
        """format_work should strip https://doi.org/ prefix."""
        import search_core

        work = {
            "id": 123,
            "doi": "https://doi.org/10.1234/test",
            "title": "Test",
        }

        formatted = search_core.format_work(work)
        assert formatted["doi"] == "10.1234/test"

    def test_format_work_handles_string_language(self, mock_core_response):
        """format_work should handle language as string."""
        import search_core

        work = mock_core_response["results"][1]  # Has language as string
        formatted = search_core.format_work(work)

        assert formatted["language"] == "en"

    def test_format_work_handles_dict_language(self, mock_core_response):
        """format_work should handle language as dict."""
        import search_core

        work = mock_core_response["results"][0]  # Has language as dict
        formatted = search_core.format_work(work)

        assert formatted["language"] == "en"


# =============================================================================
# Integration Tests
# =============================================================================

class TestCoreIntegration:
    """Integration tests using mocked HTTP responses."""

    @patch("requests.get")
    def test_search_core_success(self, mock_get, mock_core_response):
        """search_core should return formatted results."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_core_response
        )

        import search_core
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff()

        results, errors = search_core.search_core(
            query="free will",
            limit=10,
            year=None,
            api_key=None,
            limiter=limiter,
            backoff=backoff,
        )

        assert len(results) == 2
        assert results[0]["title"] == "Freedom of the Will and the Concept of a Person"
        assert len(errors) == 0

    @patch("requests.get")
    def test_search_core_empty(self, mock_get, mock_core_empty_response):
        """search_core should handle empty results."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_core_empty_response
        )

        import search_core
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff()

        results, errors = search_core.search_core(
            query="nonexistent topic xyz",
            limit=10,
            year=None,
            api_key=None,
            limiter=limiter,
            backoff=backoff,
        )

        assert len(results) == 0
        assert len(errors) == 0

    @patch("requests.get")
    def test_search_by_doi(self, mock_get, mock_core_response):
        """Should lookup work by DOI."""
        # Return single result for DOI search
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "totalHits": 1,
                "results": [mock_core_response["results"][0]]
            }
        )

        import search_core
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff()

        result = search_core.search_by_doi(
            "10.2307/2024717",
            api_key=None,
            limiter=limiter,
            backoff=backoff,
        )

        assert result is not None
        assert result["doi"] == "10.2307/2024717"

    @patch("requests.get")
    def test_search_by_doi_not_found(self, mock_get, mock_core_empty_response):
        """Should return None when DOI not found."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_core_empty_response
        )

        import search_core
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff()

        result = search_core.search_by_doi(
            "10.9999/nonexistent",
            api_key=None,
            limiter=limiter,
            backoff=backoff,
        )

        assert result is None

    @patch("requests.get")
    def test_search_by_title_author(self, mock_get, mock_core_response):
        """Should search by title and author."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "totalHits": 1,
                "results": [mock_core_response["results"][0]]
            }
        )

        import search_core
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff()

        results = search_core.search_by_title_author(
            title="Freedom of the Will",
            author="Frankfurt",
            year=1971,
            api_key=None,
            limiter=limiter,
            backoff=backoff,
        )

        assert len(results) >= 1

    @patch("requests.get")
    def test_handles_rate_limit(self, mock_get):
        """Should handle 429 rate limit responses."""
        call_count = 0

        def mock_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return MagicMock(status_code=429)
            return MagicMock(
                status_code=200,
                json=lambda: {"totalHits": 0, "results": []}
            )

        mock_get.side_effect = mock_response

        import search_core
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff(max_attempts=5, base_delay=0.01)  # Fast backoff for test

        results, errors = search_core.search_core(
            query="test",
            limit=10,
            year=None,
            api_key=None,
            limiter=limiter,
            backoff=backoff,
        )

        # Should have retried and eventually succeeded
        assert call_count >= 3


# =============================================================================
# CLI Tests
# =============================================================================

class TestCoreCLI:
    """Tests for command-line interface."""

    def test_cli_requires_query_or_options(self, run_skill_script):
        """Should fail when neither query nor --doi/--title provided."""
        result = run_skill_script("search_core.py")
        assert result.returncode == 2

        output = result.json
        assert output["status"] == "error"
        assert "Must provide" in output["errors"][0]["message"]

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("search_core.py", "--help")
        assert result.returncode == 0
        assert "CORE" in result.stdout


# =============================================================================
# Progress Output Tests
# =============================================================================

class TestCoreProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import search_core
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            search_core.log_progress("Test message")

        output = captured.getvalue()
        assert "[search_core.py]" in output
        assert "Test message" in output
