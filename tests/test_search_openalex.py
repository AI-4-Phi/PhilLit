"""
Tests for search_openalex.py (OpenAlex academic search).

Tests cover:
- Output schema validation
- Exit codes for different scenarios
- Work formatting
- Abstract reconstruction from inverted index
- Direct ID/DOI lookups
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


class TestOpenAlexOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful response should have correct schema."""
        import search_openalex

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                search_openalex.output_success("test query", [{"title": "Test"}])

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "openalex"

    def test_error_output_schema(self):
        """Error response should have correct schema."""
        import search_openalex

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                search_openalex.output_error("test", "api_error", "Test error", exit_code=3)

        assert exc_info.value.code == 3
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"


class TestOpenAlexAbstractReconstruction:
    """Tests for abstract reconstruction from inverted index."""

    def test_reconstruct_simple(self):
        """Should reconstruct simple abstract."""
        import search_openalex

        inverted = {
            "This": [0],
            "is": [1],
            "a": [2],
            "test": [3],
        }

        result = search_openalex.reconstruct_abstract(inverted)
        assert result == "This is a test"

    def test_reconstruct_with_repeated_words(self):
        """Should handle words appearing multiple times."""
        import search_openalex

        inverted = {
            "the": [0, 4],
            "cat": [1],
            "and": [2],
            "dog": [3, 5],
        }

        result = search_openalex.reconstruct_abstract(inverted)
        assert result == "the cat and dog the dog"

    def test_reconstruct_empty(self):
        """Should return None for empty inverted index."""
        import search_openalex

        assert search_openalex.reconstruct_abstract(None) is None
        assert search_openalex.reconstruct_abstract({}) is None


class TestOpenAlexFormatWork:
    """Tests for work formatting."""

    def test_format_work_basic(self, mock_openalex_response):
        """format_work should extract basic fields."""
        import search_openalex

        work = mock_openalex_response["results"][0]
        formatted = search_openalex.format_work(work)

        assert formatted["openalex_id"] == "W2741809807"
        assert formatted["doi"] == "10.2307/2024717"
        assert formatted["title"] == "Freedom of the Will and the Concept of a Person"
        assert formatted["publication_year"] == 1971
        assert formatted["cited_by_count"] == 1500

    def test_format_work_extracts_authors(self, mock_openalex_response):
        """format_work should extract author information."""
        import search_openalex

        work = mock_openalex_response["results"][0]
        formatted = search_openalex.format_work(work)

        assert len(formatted["authors"]) == 1
        assert formatted["authors"][0]["name"] == "Harry G. Frankfurt"
        assert "institutions" in formatted["authors"][0]

    def test_format_work_handles_missing_doi(self):
        """format_work should handle missing DOI."""
        import search_openalex

        work = {
            "id": "https://openalex.org/W123",
            "title": "No DOI Paper",
            "publication_year": 2024,
        }

        formatted = search_openalex.format_work(work)
        assert formatted["doi"] is None

    def test_format_work_strips_doi_prefix(self):
        """format_work should strip https://doi.org/ prefix."""
        import search_openalex

        work = {
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/10.1234/test",
            "title": "Test",
        }

        formatted = search_openalex.format_work(work)
        assert formatted["doi"] == "10.1234/test"


class TestOpenAlexIntegration:
    """Integration tests using mocked HTTP responses."""

    @patch("requests.get")
    def test_search_works_success(self, mock_get, mock_openalex_response):
        """search_works should return formatted results."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_openalex_response
        )

        import search_openalex
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("openalex")
        backoff = ExponentialBackoff()

        results, errors = search_openalex.search_works(
            query="free will",
            limit=10,
            year=None,
            cites=None,
            oa_only=False,
            min_citations=None,
            work_type=None,
            email=None,
            limiter=limiter,
            backoff=backoff,
        )

        assert len(results) == 1
        assert results[0]["title"] == "Freedom of the Will and the Concept of a Person"
        assert len(errors) == 0

    @patch("requests.get")
    def test_get_work_by_doi(self, mock_get, mock_openalex_response):
        """Should lookup work by DOI."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_openalex_response["results"][0]
        )

        import search_openalex
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("openalex")
        backoff = ExponentialBackoff()

        result = search_openalex.get_work_by_id(
            "10.2307/2024717",
            email=None,
            limiter=limiter,
            backoff=backoff,
        )

        assert result["doi"] == "10.2307/2024717"

    @patch("requests.get")
    def test_handles_404(self, mock_get):
        """Should raise LookupError on 404."""
        mock_get.return_value = MagicMock(status_code=404)

        import search_openalex
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("openalex")
        backoff = ExponentialBackoff()

        with pytest.raises(LookupError) as exc_info:
            search_openalex.get_work_by_id(
                "nonexistent",
                email=None,
                limiter=limiter,
                backoff=backoff,
            )

        assert "not found" in str(exc_info.value).lower()

    @patch("requests.get")
    def test_get_work_by_id_sends_bearer_header(self, mock_get, mock_openalex_response, monkeypatch):
        monkeypatch.setenv("OPENALEX_API_KEY", "sekret")
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_openalex_response["results"][0]
        )
        import search_openalex
        from rate_limiter import get_limiter, ExponentialBackoff
        search_openalex.get_work_by_id(
            "10.2307/2024717", email=None,
            limiter=get_limiter("openalex"), backoff=ExponentialBackoff())
        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"Authorization": "Bearer sekret"}

    @patch("requests.get")
    def test_search_works_sends_bearer_header(self, mock_get, mock_openalex_response, monkeypatch):
        monkeypatch.setenv("OPENALEX_API_KEY", "sekret")
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_openalex_response
        )
        import search_openalex
        from rate_limiter import get_limiter, ExponentialBackoff
        search_openalex.search_works(
            query="free will", limit=1, year=None, cites=None, oa_only=False,
            min_citations=None, work_type=None, email=None,
            limiter=get_limiter("openalex"), backoff=ExponentialBackoff())
        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"Authorization": "Bearer sekret"}


class TestOpenAlexCLI:
    """Tests for command-line interface."""

    def test_cli_requires_query_or_id(self, run_skill_script):
        """Should fail when neither query nor --doi/--id provided."""
        result = run_skill_script("search_openalex.py")
        assert result.returncode == 2

        output = result.json
        assert output["status"] == "error"
        assert "Must provide" in output["errors"][0]["message"]

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("search_openalex.py", "--help")
        assert result.returncode == 0
        assert "OpenAlex" in result.stdout


class TestOpenAlexProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import search_openalex
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            search_openalex.log_progress("Test message")

        output = captured.getvalue()
        assert "[search_openalex.py]" in output
        assert "Test message" in output
