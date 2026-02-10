"""
Tests for get_abstract.py (multi-source abstract resolution).

Tests cover:
- Output schema validation
- Fallback chain behavior (S2 -> OpenAlex -> CORE)
- Source attribution
- Not found handling
"""

import json
from unittest.mock import patch, MagicMock

import pytest


# =============================================================================
# Output Tests
# =============================================================================

class TestGetAbstractOutput:
    """Tests for output format."""

    def test_success_output_format(self):
        """Success output should have correct fields."""
        import get_abstract

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_abstract.output_result(
                    "success",
                    {"doi": "10.1234/test"},
                    "This is the abstract",
                    "openalex"
                )

        assert exc_info.value.code == 0
        assert output["status"] == "success"
        assert output["abstract"] == "This is the abstract"
        assert output["abstract_source"] == "openalex"
        assert output["query"]["doi"] == "10.1234/test"

    def test_not_found_output_format(self):
        """Not found output should have null abstract."""
        import get_abstract

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_abstract.output_result("not_found", {"doi": "10.1234/test"})

        assert exc_info.value.code == 0
        assert output["status"] == "not_found"
        assert output["abstract"] is None
        assert output["abstract_source"] is None

    def test_error_output_format(self):
        """Error output should have error field."""
        import get_abstract

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_abstract.output_error(
                    {"doi": "10.1234/test"},
                    "api_error",
                    "Something went wrong",
                    exit_code=3
                )

        assert exc_info.value.code == 3
        assert output["status"] == "error"
        assert output["error"]["type"] == "api_error"


# =============================================================================
# OpenAlex Abstract Reconstruction
# =============================================================================

class TestOpenAlexAbstractReconstruction:
    """Tests for OpenAlex inverted index reconstruction."""

    def test_reconstruct_simple(self):
        """Should reconstruct simple abstract."""
        import get_abstract

        inverted = {
            "This": [0],
            "is": [1],
            "a": [2],
            "test": [3],
        }

        result = get_abstract.reconstruct_abstract(inverted)
        assert result == "This is a test"

    def test_reconstruct_with_repeated_words(self):
        """Should handle words appearing multiple times."""
        import get_abstract

        inverted = {
            "the": [0, 4],
            "cat": [1],
            "and": [2],
            "dog": [3, 5],
        }

        result = get_abstract.reconstruct_abstract(inverted)
        assert result == "the cat and dog the dog"

    def test_reconstruct_empty(self):
        """Should return None for empty inverted index."""
        import get_abstract

        assert get_abstract.reconstruct_abstract(None) is None
        assert get_abstract.reconstruct_abstract({}) is None


# =============================================================================
# Individual Source Tests
# =============================================================================

class TestS2Source:
    """Tests for Semantic Scholar abstract retrieval."""

    @patch("requests.get")
    def test_get_abstract_from_s2_success(self, mock_get):
        """Should return abstract from S2."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract": "This is the S2 abstract."}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            "abc123", None, limiter, backoff
        )

        assert result == "This is the S2 abstract."

    @patch("requests.get")
    def test_get_abstract_from_s2_no_abstract(self, mock_get):
        """Should return None if paper has no abstract."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract": None}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            "abc123", None, limiter, backoff
        )

        assert result is None

    @patch("requests.get")
    def test_get_abstract_from_s2_404(self, mock_get):
        """Should return None on 404."""
        mock_get.return_value = MagicMock(status_code=404)

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            "nonexistent", None, limiter, backoff
        )

        assert result is None


class TestOpenAlexSource:
    """Tests for OpenAlex abstract retrieval."""

    @patch("requests.get")
    def test_get_abstract_from_openalex_success(self, mock_get):
        """Should reconstruct and return abstract from OpenAlex."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "abstract_inverted_index": {
                    "This": [0],
                    "is": [1],
                    "the": [2],
                    "OpenAlex": [3],
                    "abstract": [4],
                }
            }
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("openalex")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_openalex(
            "10.1234/test", None, limiter, backoff
        )

        assert result == "This is the OpenAlex abstract"

    @patch("requests.get")
    def test_get_abstract_from_openalex_strips_doi_prefix(self, mock_get):
        """Should handle DOI with https://doi.org/ prefix."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract_inverted_index": {"Test": [0]}}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("openalex")
        backoff = ExponentialBackoff(max_attempts=2)

        get_abstract.get_abstract_from_openalex(
            "https://doi.org/10.1234/test", None, limiter, backoff
        )

        # Verify the URL was constructed correctly
        call_url = mock_get.call_args[0][0]
        assert "doi:10.1234/test" in call_url


class TestCoreSource:
    """Tests for CORE abstract retrieval."""

    @patch("requests.get")
    def test_get_abstract_from_core_by_doi(self, mock_get):
        """Should find abstract by DOI."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "abstract": "This is the CORE abstract which is long enough to pass the filter."
                }]
            }
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_core(
            doi="10.1234/test",
            limiter=limiter,
            backoff=backoff
        )

        assert "CORE abstract" in result

    @patch("requests.get")
    def test_get_abstract_from_core_by_title(self, mock_get):
        """Should find abstract by title and author."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "title": "Freedom of the Will and the Concept of a Person",
                    "abstract": "This paper examines the relationship between freedom and personhood in significant detail."
                }]
            }
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_core(
            title="Freedom of the Will",
            author="Frankfurt",
            limiter=limiter,
            backoff=backoff
        )

        assert result is not None
        assert "freedom" in result.lower()


# =============================================================================
# Fallback Chain Tests
# =============================================================================

class TestFallbackChain:
    """Tests for fallback chain behavior."""

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_s2_checked_first_when_id_provided(
        self, mock_s2, mock_openalex, mock_core
    ):
        """S2 should be checked first when S2 ID is provided."""
        mock_s2.return_value = "S2 abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract == "S2 abstract"
        assert source == "s2"
        mock_s2.assert_called_once()
        mock_openalex.assert_not_called()
        mock_core.assert_not_called()

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_openalex_fallback_when_s2_fails(
        self, mock_s2, mock_openalex, mock_core
    ):
        """OpenAlex should be tried when S2 returns None."""
        mock_s2.return_value = None
        mock_openalex.return_value = "OpenAlex abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract == "OpenAlex abstract"
        assert source == "openalex"
        mock_s2.assert_called_once()
        mock_openalex.assert_called_once()
        mock_core.assert_not_called()

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_core_fallback_when_openalex_fails(
        self, mock_s2, mock_openalex, mock_core
    ):
        """CORE should be tried when OpenAlex returns None."""
        mock_s2.return_value = None
        mock_openalex.return_value = None
        mock_core.return_value = "CORE abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract == "CORE abstract"
        assert source == "core"

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_returns_none_when_all_fail(
        self, mock_s2, mock_openalex, mock_core
    ):
        """Should return (None, None) when all sources fail."""
        mock_s2.return_value = None
        mock_openalex.return_value = None
        mock_core.return_value = None

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract is None
        assert source is None

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    def test_skips_s2_when_no_id(self, mock_openalex, mock_core):
        """Should skip S2 when no S2 ID provided."""
        mock_openalex.return_value = "OpenAlex abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            doi="10.1234/test"
        )

        assert abstract == "OpenAlex abstract"
        assert source == "openalex"

    @patch("get_abstract.get_abstract_from_core")
    def test_title_only_uses_core(self, mock_core):
        """Should use CORE when only title provided."""
        mock_core.return_value = "CORE abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            title="Freedom of the Will",
            author="Frankfurt"
        )

        assert abstract == "CORE abstract"
        assert source == "core"


# =============================================================================
# CLI Tests
# =============================================================================

class TestCLI:
    """Tests for command-line interface."""

    def test_cli_requires_identifier(self, run_skill_script):
        """Should fail when no identifier provided."""
        result = run_skill_script("get_abstract.py")
        assert result.returncode == 2

        output = result.json
        assert output["status"] == "error"
        assert "Must provide" in output["error"]["message"]

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("get_abstract.py", "--help")
        assert result.returncode == 0
        assert "abstract" in result.stdout.lower()


# =============================================================================
# Progress Output Tests
# =============================================================================

class TestProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import get_abstract
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            get_abstract.log_progress("Test message")

        output = captured.getvalue()
        assert "[get_abstract.py]" in output
        assert "Test message" in output
