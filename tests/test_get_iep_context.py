"""
Tests for get_iep_context.py (IEP citation context extraction).

Tests cover:
- Output schema validation
- Progress output
- CLI interface
"""

import json
from unittest.mock import patch

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


class TestOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful response should have correct schema."""
        import get_iep_context

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        query = {"entry": "freewill", "author": "Frankfurt", "year": "1971"}

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_iep_context.output_success(query, [{"citation_count": 5}])

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "iep_context"

    def test_error_output_schema(self):
        """Error response should have correct schema."""
        import get_iep_context

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        query = {"entry": "freewill", "author": "Frankfurt", "year": "1971"}

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_iep_context.output_error(query, "not_found", "Entry not found", exit_code=1)

        assert exc_info.value.code == 1
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"


class TestProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import get_iep_context
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            get_iep_context.log_progress("Test message")

        output = captured.getvalue()
        assert "[get_iep_context.py]" in output
        assert "Test message" in output


class TestCLI:
    """Tests for command-line interface."""

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("get_iep_context.py", "--help")
        assert result.returncode == 0
        assert "IEP" in result.stdout

    def test_cli_requires_author(self, run_skill_script):
        """Should require --author argument."""
        result = run_skill_script("get_iep_context.py", "freewill", "--year", "1971")
        assert result.returncode == 2
