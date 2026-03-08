"""
Cross-script tests for output schema compliance.

Verifies that all search scripts follow the standard JSON output schema.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


# List of all search scripts and their expected source names
SEARCH_SCRIPTS = [
    ("s2_search", "semantic_scholar"),
    ("search_openalex", "openalex"),
    ("search_philpapers", "philpapers_via_brave"),
    ("search_sep", "sep_via_brave"),
    ("search_arxiv", "arxiv"),
    ("verify_paper", "crossref"),
    ("s2_citations", "semantic_scholar"),
    ("s2_recommend", "semantic_scholar"),
    ("s2_batch", "semantic_scholar"),
]


class TestOutputSchemaCompliance:
    """Tests that all scripts produce valid output schemas."""

    @pytest.mark.parametrize("module_name,expected_source", SEARCH_SCRIPTS)
    def test_success_output_has_required_fields(self, module_name, expected_source):
        """Success output should have all required fields."""
        module = __import__(module_name)

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit):
                # Different scripts have different function signatures
                if hasattr(module, "output_success"):
                    if module_name == "verify_paper":
                        module.output_success({"doi": "test"}, {"verified": True})
                    else:
                        module.output_success("test query", [{"title": "Test"}])

        assert output is not None, f"{module_name}: no output captured"
        errors = validate_output_schema(output, "success")
        assert errors == [], f"{module_name}: {errors}"
        assert output["source"] == expected_source

    @pytest.mark.parametrize("module_name,expected_source", SEARCH_SCRIPTS)
    def test_error_output_has_required_fields(self, module_name, expected_source):
        """Error output should have all required fields."""
        module = __import__(module_name)

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit):
                if hasattr(module, "output_error"):
                    if module_name == "verify_paper":
                        module.output_error({"doi": "test"}, "api_error", "Test error")
                    else:
                        module.output_error("test query", "api_error", "Test error")

        assert output is not None, f"{module_name}: no output captured"
        errors = validate_output_schema(output, "error")
        assert errors == [], f"{module_name}: {errors}"


class TestExitCodeConsistency:
    """Tests that all scripts use consistent exit codes."""

    EXIT_CODE_MAPPING = {
        "success": 0,
        "not_found": 1,
        "config_error": 2,
        "api_error": 3,
        "rate_limit": 3,
    }

    @pytest.mark.parametrize("module_name,_", SEARCH_SCRIPTS)
    def test_exit_code_0_for_success(self, module_name, _):
        """All scripts should exit with 0 on success."""
        module = __import__(module_name)

        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                if hasattr(module, "output_success"):
                    if module_name == "verify_paper":
                        module.output_success({"doi": "test"}, {"verified": True})
                    else:
                        module.output_success("test", [])

        if hasattr(module, "output_success"):
            assert exc_info.value.code == 0, f"{module_name} should exit with 0"

    @pytest.mark.parametrize("module_name,_", SEARCH_SCRIPTS)
    def test_exit_code_consistency(self, module_name, _):
        """All scripts should use consistent exit codes for error types."""
        module = __import__(module_name)

        for error_type, expected_code in self.EXIT_CODE_MAPPING.items():
            if error_type == "success":
                continue

            # Not all scripts have output_error with the same signature
            if not hasattr(module, "output_error"):
                continue

            with patch("builtins.print"):
                with pytest.raises(SystemExit) as exc_info:
                    if module_name == "verify_paper":
                        module.output_error(
                            {"test": True},
                            error_type,
                            "Test error",
                            exit_code=expected_code
                        )
                    else:
                        module.output_error(
                            "test",
                            error_type,
                            "Test error",
                            exit_code=expected_code
                        )

                assert exc_info.value.code == expected_code, \
                    f"{module_name}: {error_type} should exit with {expected_code}"


class TestResultsCountConsistency:
    """Tests that results count matches actual results length."""

    @pytest.mark.parametrize("module_name,_", SEARCH_SCRIPTS)
    def test_count_matches_results_length(self, module_name, _):
        """count field should always match len(results)."""
        module = __import__(module_name)

        test_results = [{"title": "Paper 1"}, {"title": "Paper 2"}, {"title": "Paper 3"}]

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit):
                if hasattr(module, "output_success"):
                    if module_name == "verify_paper":
                        module.output_success({"doi": "test"}, test_results[0])
                    else:
                        module.output_success("test", test_results)

        assert output is not None, f"{module_name}: no output captured"
        if "results" in output and "count" in output:
            assert output["count"] == len(output["results"]), \
                f"{module_name}: count ({output['count']}) != len(results) ({len(output['results'])})"


class TestErrorFieldStructure:
    """Tests that error fields follow the expected structure."""

    @pytest.mark.parametrize("module_name,_", SEARCH_SCRIPTS)
    def test_error_field_structure(self, module_name, _):
        """Error entries should have type, message, and recoverable fields."""
        module = __import__(module_name)

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit):
                if hasattr(module, "output_error"):
                    if module_name == "verify_paper":
                        module.output_error({"doi": "test"}, "api_error", "Test error")
                    else:
                        module.output_error("test", "api_error", "Test error")

        assert output is not None, f"{module_name}: no output captured"
        if output.get("errors"):
            for error in output["errors"]:
                assert "type" in error, f"{module_name}: error missing 'type'"
                assert "message" in error, f"{module_name}: error missing 'message'"
                assert "recoverable" in error, f"{module_name}: error missing 'recoverable'"


class TestProgressOutputLocation:
    """Tests that progress output goes to stderr, not stdout."""

    @pytest.mark.parametrize("module_name,_", SEARCH_SCRIPTS)
    def test_log_progress_uses_stderr(self, module_name, _):
        """log_progress should write to stderr."""
        module = __import__(module_name)

        if not hasattr(module, "log_progress"):
            pytest.skip(f"{module_name} doesn't have log_progress")

        import io

        captured_stderr = io.StringIO()
        captured_stdout = io.StringIO()

        with patch("sys.stderr", captured_stderr):
            with patch("sys.stdout", captured_stdout):
                module.log_progress("Test message")

        # Should be in stderr
        assert "Test message" in captured_stderr.getvalue()
        # Should NOT be in stdout
        assert "Test message" not in captured_stdout.getvalue()

    @pytest.mark.parametrize("module_name,_", SEARCH_SCRIPTS)
    def test_log_progress_includes_script_name(self, module_name, _):
        """log_progress should include script name for identification."""
        module = __import__(module_name)

        if not hasattr(module, "log_progress"):
            pytest.skip(f"{module_name} doesn't have log_progress")

        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            module.log_progress("Test message")

        output = captured.getvalue()
        # Should include script name in brackets
        assert f"[{module_name}.py]" in output or f"[{module_name}]" in output
