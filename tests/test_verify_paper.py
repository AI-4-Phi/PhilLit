"""
Tests for verify_paper.py (CrossRef DOI verification).

Tests cover:
- Output schema validation
- Exit codes for different scenarios
- DOI normalization
- Author name extraction
- Verification by DOI vs. metadata search
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


class TestVerifyPaperOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful verification should have correct schema."""
        import verify_paper

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_success(
                    {"doi": "10.1234/test"},
                    {"verified": True, "doi": "10.1234/test", "title": "Test"}
                )

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "crossref"

    def test_not_found_output_schema(self):
        """Not found response should have correct schema."""
        import verify_paper

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_not_found(
                    {"title": "Unknown Paper"},
                    "Paper not found"
                )

        assert exc_info.value.code == 1
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"
        assert output["errors"][0]["type"] == "not_found"


class TestVerifyPaperExitCodes:
    """Tests for correct exit codes."""

    def test_exit_code_0_on_success(self):
        """Should exit with 0 on successful verification."""
        import verify_paper

        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_success(
                    {"doi": "test"},
                    {"verified": True}
                )

        assert exc_info.value.code == 0

    def test_exit_code_1_on_not_found(self):
        """Should exit with 1 when paper not found."""
        import verify_paper

        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_not_found({"title": "Test"}, "Not found")

        assert exc_info.value.code == 1

    def test_exit_code_2_on_config_error(self):
        """Should exit with 2 on configuration error."""
        import verify_paper

        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_error({"title": "Test"}, "config_error", "Bad config")

        assert exc_info.value.code == 2


class TestDOINormalization:
    """Tests for DOI normalization."""

    def test_normalize_plain_doi(self):
        """Should return plain DOI unchanged."""
        import verify_paper

        assert verify_paper.normalize_doi("10.2307/2024717") == "10.2307/2024717"

    def test_normalize_https_prefix(self):
        """Should strip https://doi.org/ prefix."""
        import verify_paper

        result = verify_paper.normalize_doi("https://doi.org/10.2307/2024717")
        assert result == "10.2307/2024717"

    def test_normalize_http_prefix(self):
        """Should strip http://doi.org/ prefix."""
        import verify_paper

        result = verify_paper.normalize_doi("http://doi.org/10.2307/2024717")
        assert result == "10.2307/2024717"

    def test_normalize_doi_prefix(self):
        """Should strip doi: prefix."""
        import verify_paper

        result = verify_paper.normalize_doi("doi:10.2307/2024717")
        assert result == "10.2307/2024717"

    def test_normalize_whitespace(self):
        """Should strip whitespace."""
        import verify_paper

        result = verify_paper.normalize_doi("  10.2307/2024717  ")
        assert result == "10.2307/2024717"


class TestAuthorNameExtraction:
    """Tests for author name extraction from CrossRef format."""

    def test_extract_basic_names(self):
        """Should extract family and given names."""
        import verify_paper

        authors = [
            {"given": "Harry", "family": "Frankfurt"},
            {"given": "Susan", "family": "Wolf"},
        ]

        result = verify_paper.extract_author_names(authors)
        assert result == ["Frankfurt, Harry", "Wolf, Susan"]

    def test_extract_family_only(self):
        """Should handle authors with only family name."""
        import verify_paper

        authors = [{"family": "Aristotle"}]
        result = verify_paper.extract_author_names(authors)
        assert result == ["Aristotle"]

    def test_extract_organization(self):
        """Should handle organization names."""
        import verify_paper

        authors = [{"name": "World Health Organization"}]
        result = verify_paper.extract_author_names(authors)
        assert result == ["World Health Organization"]

    def test_extract_empty_list(self):
        """Should handle empty author list."""
        import verify_paper

        result = verify_paper.extract_author_names([])
        assert result == []


class TestFormatResult:
    """Tests for result formatting."""

    def test_format_result_basic(self, mock_crossref_response):
        """format_result should extract basic fields."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["verified"] is True
        assert result["doi"] == "10.2307/2024717"
        assert result["title"] == "Freedom of the Will and the Concept of a Person"
        assert result["year"] == 1971
        assert result["method"] == "doi_lookup"

    def test_format_result_suggested_bibtex_type_article(self, mock_crossref_response):
        """format_result should map journal-article to @article."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "article"

    def test_format_result_suggested_bibtex_type_book_chapter(self):
        """format_result should map book-chapter to @incollection."""
        import verify_paper

        item = {
            "DOI": "10.1093/oso/9780190859213.003.0007",
            "title": ["The Value of Ideal Theory"],
            "author": [{"given": "Matthew S.", "family": "Adams"}],
            "published": {"date-parts": [[2020]]},
            "container-title": ["John Rawls"],
            "publisher": "Oxford University Press",
            "type": "book-chapter",
            "page": "73-86",
        }
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "incollection"
        assert result["container_title"] == "John Rawls"

    def test_format_result_editors_for_edited_book(self):
        """format_result should extract editors for edited books."""
        import verify_paper

        item = {
            "DOI": "10.1093/oso/9780190859213.001.0001",
            "title": ["John Rawls"],
            "author": [],
            "editor": [{"given": "Jon", "family": "Mandle"}, {"given": "Sarah", "family": "Roberts-Cady"}],
            "published": {"date-parts": [[2020]]},
            "publisher": "Oxford University Press",
            "type": "edited-book",
        }
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "book"
        assert result["authors"] == []
        assert len(result["editors"]) == 2
        assert result["editors"][0]["family"] == "Mandle"
        assert result["editors"][1]["family"] == "Roberts-Cady"

    def test_format_result_editors_empty_when_absent(self, mock_crossref_response):
        """format_result should return empty editors list for regular articles."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["editors"] == []

    def test_format_result_suggested_bibtex_type_unknown(self):
        """format_result should fall back to @misc for unknown CrossRef types."""
        import verify_paper

        item = {
            "DOI": "10.1234/unknown",
            "title": ["Some Work"],
            "author": [],
            "type": "peer-review",
        }
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "misc"

    def test_format_result_with_score(self, mock_crossref_response):
        """format_result should include score when provided."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "bibliographic_search", score=85.5)

        assert result["score"] == 85.5


class TestVerifyByDOI:
    """Tests for DOI verification."""

    @patch("requests.get")
    def test_verify_by_doi_success(self, mock_get, mock_crossref_response):
        """Should verify paper by DOI."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_crossref_response
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        result = verify_paper.verify_by_doi(
            "10.2307/2024717",
            limiter=limiter,
            backoff=backoff,
            mailto="test@example.com",
        )

        assert result["verified"] is True
        assert result["doi"] == "10.2307/2024717"

    @patch("requests.get")
    def test_verify_by_doi_not_found(self, mock_get):
        """Should raise LookupError for non-existent DOI."""
        mock_get.return_value = MagicMock(status_code=404)

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        with pytest.raises(LookupError) as exc_info:
            verify_paper.verify_by_doi(
                "10.9999/nonexistent",
                limiter=limiter,
                backoff=backoff,
                mailto="test@example.com",
            )

        assert "not found" in str(exc_info.value).lower()


class TestSearchByMetadata:
    """Tests for metadata-based search."""

    @patch("requests.get")
    def test_search_by_title_and_author(self, mock_get):
        """Should find paper by title and author."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.2307/2024717",
                            "title": ["Freedom of the Will and the Concept of a Person"],
                            "author": [{"given": "Harry", "family": "Frankfurt"}],
                            "published": {"date-parts": [[1971]]},
                            "score": 95.0,
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        result = verify_paper.search_by_metadata(
            title="Freedom of the Will",
            author="Frankfurt",
            year=1971,
            limiter=limiter,
            backoff=backoff,
            mailto="test@example.com",
        )

        assert result["verified"] is True
        assert result["doi"] == "10.2307/2024717"

    @patch("requests.get")
    def test_search_returns_editors(self, mock_get):
        """Should populate editors from CrossRef search results."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1093/oso/9780190859213.001.0001",
                            "title": ["John Rawls"],
                            "author": [],
                            "editor": [
                                {"given": "Jon", "family": "Mandle"},
                                {"given": "Sarah", "family": "Roberts-Cady"},
                            ],
                            "published": {"date-parts": [[2020]]},
                            "publisher": "Oxford University Press",
                            "type": "edited-book",
                            "score": 95.0,
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        result = verify_paper.search_by_metadata(
            title="John Rawls",
            author=None,
            year=2020,
            limiter=limiter,
            backoff=backoff,
            mailto="test@example.com",
        )

        assert len(result["editors"]) == 2
        assert result["editors"][0]["family"] == "Mandle"
        assert result["editors"][1]["family"] == "Roberts-Cady"

    @patch("requests.get")
    def test_search_rejects_low_score(self, mock_get):
        """Should reject matches with low confidence score."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1234/wrong",
                            "title": ["Something Completely Different"],
                            "author": [{"given": "John", "family": "Doe"}],
                            "score": 15.0,  # Low score
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        with pytest.raises(LookupError) as exc_info:
            verify_paper.search_by_metadata(
                title="Freedom of the Will",
                author="Frankfurt",
                year=None,
                limiter=limiter,
                backoff=backoff,
                mailto="test@example.com",
            )

        assert "score" in str(exc_info.value).lower()


class TestVerifyPaperCLI:
    """Tests for command-line interface."""

    def test_cli_requires_doi_or_title(self, run_skill_script):
        """Should fail when neither --doi nor --title provided."""
        result = run_skill_script("verify_paper.py")
        assert result.returncode == 2

        output = result.json
        assert output["status"] == "error"
        assert "Must provide" in output["errors"][0]["message"]

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("verify_paper.py", "--help")
        assert result.returncode == 0
        assert "CrossRef" in result.stdout


class TestVerifyPaperProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import verify_paper
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            verify_paper.log_progress("Test message")

        output = captured.getvalue()
        assert "[verify_paper.py]" in output
        assert "Test message" in output
