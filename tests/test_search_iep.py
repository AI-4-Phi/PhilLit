"""
Tests for search_iep.py (IEP search via Brave API).

Tests cover:
- Output schema validation
- Exit codes for different scenarios
- IEP-specific configuration
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


class TestIEPOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful response should have correct schema."""
        import search_iep

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                search_iep.output_success("test query", [{"title": "Test"}])

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "iep_via_brave"

    def test_error_output_schema(self):
        """Error response should have correct schema."""
        import search_iep

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                search_iep.output_error("test", "api_error", "Test error", exit_code=3)

        assert exc_info.value.code == 3
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"


class TestIEPConfig:
    """Tests for IEP-specific configuration."""

    def test_iep_config_exists(self):
        """IEP_CONFIG should be properly defined."""
        from brave_search import IEP_CONFIG

        assert IEP_CONFIG.source_name == "iep_via_brave"
        assert IEP_CONFIG.site_domain == "iep.utm.edu"
        assert IEP_CONFIG.id_field_name == "entry_name"

    def test_iep_config_url_pattern(self):
        """IEP URL pattern should match IEP entry URLs."""
        import re
        from brave_search import IEP_CONFIG

        test_urls = [
            ("https://iep.utm.edu/freewill/", "freewill"),
            ("https://iep.utm.edu/compatibilism/", "compatibilism"),
            ("https://iep.utm.edu/moral-resp/", "moral-resp"),
        ]

        for url, expected_id in test_urls:
            match = re.search(IEP_CONFIG.id_pattern, url)
            assert match is not None, f"Pattern should match {url}"
            assert match.group(1) == expected_id


class TestIEPProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import search_iep
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            search_iep.log_progress("Test message")

        output = captured.getvalue()
        assert "[search_iep.py]" in output
        assert "Test message" in output


class TestIEPCLI:
    """Tests for command-line interface."""

    def test_cli_requires_api_key(self, run_skill_script):
        """Should fail when BRAVE_API_KEY not set."""
        # Run without API key env var
        result = run_skill_script("search_iep.py", "free will", env={"BRAVE_API_KEY": ""})

        assert result.returncode == 2
        output = result.json
        assert output["status"] == "error"
        assert "BRAVE_API_KEY" in output["errors"][0]["message"]

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("search_iep.py", "--help")
        assert result.returncode == 0
        assert "IEP" in result.stdout


class TestIEPBraveSearch:
    """Tests for IEP search via Brave API."""

    @patch("brave_search.requests.get")
    def test_search_returns_results(self, mock_get):
        """Should return formatted results from Brave API."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "web": {
                    "results": [
                        {
                            "url": "https://iep.utm.edu/freewill/",
                            "title": "Free Will | Internet Encyclopedia of Philosophy",
                            "description": "An overview of free will...",
                        },
                        {
                            "url": "https://iep.utm.edu/compatibilism/",
                            "title": "Compatibilism | Internet Encyclopedia of Philosophy",
                            "description": "Discussion of compatibilism...",
                        },
                    ]
                }
            }
        )

        from brave_search import brave_site_search, IEP_CONFIG
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("brave")
        backoff = ExponentialBackoff()

        results, errors = brave_site_search(
            query="free will",
            limit=10,
            api_key="test_key",
            config=IEP_CONFIG,
            limiter=limiter,
            backoff=backoff,
        )

        assert len(results) == 2
        assert results[0]["entry_name"] == "freewill"
        assert results[1]["entry_name"] == "compatibilism"
        assert "Free Will" in results[0]["title"]

    @patch("brave_search.requests.get")
    def test_search_extracts_entry_name(self, mock_get):
        """Should correctly extract entry name from IEP URL."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "web": {
                    "results": [
                        {
                            "url": "https://iep.utm.edu/moral-resp/",
                            "title": "Moral Responsibility | IEP",
                            "description": "Test",
                        },
                    ]
                }
            }
        )

        from brave_search import brave_site_search, IEP_CONFIG
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("brave")
        backoff = ExponentialBackoff()

        results, errors = brave_site_search(
            query="moral responsibility",
            limit=10,
            api_key="test_key",
            config=IEP_CONFIG,
            limiter=limiter,
            backoff=backoff,
        )

        assert len(results) == 1
        assert results[0]["entry_name"] == "moral-resp"
