"""
Shared utilities for philosophy-research skill tests.

This module contains helper functions and constants that are imported
directly by test files. pytest fixtures are in conftest.py.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


# =============================================================================
# Paths
# =============================================================================

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "philosophy-research" / "scripts"

# Add scripts directory to path for imports
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# =============================================================================
# Output Schema Validation
# =============================================================================

REQUIRED_SUCCESS_FIELDS = {"status", "source", "query", "results", "count", "errors"}
REQUIRED_ERROR_FIELDS = {"status", "source", "query", "results", "count", "errors"}


def validate_output_schema(output: dict, expected_status: str = "success") -> list[str]:
    """
    Validate that output conforms to the standard schema.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Check required fields
    required = REQUIRED_SUCCESS_FIELDS if expected_status == "success" else REQUIRED_ERROR_FIELDS
    for field in required:
        if field not in output:
            errors.append(f"Missing required field: {field}")

    # Validate field types
    if "status" in output and output["status"] not in ("success", "partial", "error"):
        errors.append(f"Invalid status: {output['status']}")

    if "results" in output and not isinstance(output["results"], list):
        errors.append(f"'results' must be a list, got {type(output['results'])}")

    if "count" in output and not isinstance(output["count"], int):
        errors.append(f"'count' must be an int, got {type(output['count'])}")

    if "errors" in output and not isinstance(output["errors"], list):
        errors.append(f"'errors' must be a list, got {type(output['errors'])}")

    # Validate count matches results
    if "results" in output and "count" in output:
        if output["count"] != len(output["results"]):
            errors.append(f"count ({output['count']}) != len(results) ({len(output['results'])})")

    return errors


# =============================================================================
# Script Execution Helper
# =============================================================================

class ScriptResult:
    """Result of running a skill script."""

    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self._json: Optional[dict] = None

    @property
    def json(self) -> dict:
        """Parse stdout as JSON."""
        if self._json is None:
            self._json = json.loads(self.stdout)
        return self._json

    @property
    def success(self) -> bool:
        """Check if script succeeded (exit code 0)."""
        return self.returncode == 0

    def __repr__(self) -> str:
        return f"ScriptResult(returncode={self.returncode}, stdout_len={len(self.stdout)}, stderr_len={len(self.stderr)})"


def run_script(script_name: str, *args, env: Optional[dict] = None, timeout: int = 30) -> ScriptResult:
    """
    Run a skill script and capture output.

    Args:
        script_name: Name of script (e.g., "s2_search.py")
        *args: Command line arguments
        env: Additional environment variables
        timeout: Timeout in seconds

    Returns:
        ScriptResult with returncode, stdout, stderr
    """
    script_path = SCRIPTS_DIR / script_name

    # Build environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    # Run script
    result = subprocess.run(
        [sys.executable, str(script_path)] + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=run_env,
    )

    return ScriptResult(result.returncode, result.stdout, result.stderr)
