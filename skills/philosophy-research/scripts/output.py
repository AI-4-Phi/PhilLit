#!/usr/bin/env python3
"""
Shared output functions for philosophy-research scripts.

All scripts use the same JSON output schema:
{
    "status": "success|partial|error",
    "source": "script_source_name",
    "query": "original_query",
    "results": [...],
    "count": N,
    "errors": [{"type": "...", "message": "...", "recoverable": bool}]
}

This module consolidates the output functions to ensure consistency
and reduce duplication across all search scripts.
"""

import argparse
import json
import os
import sys
import tempfile
from typing import Any, NoReturn, Optional


# item 13 A1, generalized: each script can own its output file so a
# researcher's shell redirection (`> f.json 2>&1`) can no longer merge stderr
# progress logs into the JSON. Set by the script's main() from --output;
# None (the default) keeps the upstream stdout-only behavior.
_OUTPUT_PATH: Optional[str] = None


def set_output_path(path: Optional[str]) -> None:
    """Configure the --output target. Call once from main() after parsing args.
    None keeps stdout-only output (upstream default)."""
    global _OUTPUT_PATH
    _OUTPUT_PATH = path


def add_output_arg(parser: argparse.ArgumentParser) -> None:
    """Add the standard `--output PATH` argument. When set, the script writes
    its JSON to PATH atomically (in addition to stdout), so callers never need
    to redirect -- and a stray `2>&1` can no longer corrupt the JSON file."""
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Write JSON output to PATH (atomic write, in addition to stdout). "
             "Use this instead of shell redirection; never pipe stderr (2>&1) "
             "into a .json file -- stderr carries progress logs, not data.",
    )


def _write_output_file(payload: dict, path: str, script_name: str) -> bool:
    """Atomically write payload as pretty JSON to path (tmp + os.replace,
    encoding='utf-8'). Creates parent dirs. Returns True on success, False on
    any failure (the caller then warns and exits 4)."""
    try:
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except Exception as e:
        print(f"[{script_name}] Failed to write --output file {path}: {e}",
              file=sys.stderr, flush=True)
        return False


def _emit(output: dict, exit_code: int) -> NoReturn:
    """Print output JSON to stdout (always, upstream-compatible) and, if
    --output was configured, also write it atomically. A failed --output write
    is a hard error: the JSON is still on stdout, but the exit code becomes 4
    so the researcher retries with a good path."""
    print(json.dumps(output, indent=2))
    if _OUTPUT_PATH is not None and not _write_output_file(
        output, _OUTPUT_PATH, output.get("source", "search")
    ):
        sys.exit(4)
    sys.exit(exit_code)


# Public alias for scripts that build their output dict inline (rather than via
# output_success/partial/error) and want the same stdout + atomic-file behavior.
emit = _emit


def log_progress(script_name: str, message: str) -> None:
    """
    Emit progress to stderr (visible to user, doesn't break JSON output).

    Args:
        script_name: Name of the script (e.g., "s2_search.py")
        message: Progress message to emit
    """
    print(f"[{script_name}] {message}", file=sys.stderr, flush=True)


def output_success(
    source: str,
    query: Any,
    results: list,
    **extra_fields
) -> NoReturn:
    """
    Output successful search results and exit with code 0.

    Args:
        source: Source identifier (e.g., "semantic_scholar", "openalex")
        query: Original query (string or dict depending on script)
        results: List of result dictionaries
        **extra_fields: Additional fields to include (e.g., not_found=[])
    """
    output = {
        "status": "success",
        "source": source,
        "query": query,
        "results": results,
        "count": len(results),
        "errors": [],
        **extra_fields
    }
    _emit(output, 0)


def output_partial(
    source: str,
    query: Any,
    results: list,
    errors: list,
    warning: str,
    **extra_fields
) -> NoReturn:
    """
    Output partial results with errors and exit with code 0.

    Used when some results were retrieved but errors occurred
    (e.g., pagination failed partway through).

    Args:
        source: Source identifier
        query: Original query
        results: List of results retrieved before error
        errors: List of error dictionaries
        warning: Warning message explaining partial results
        **extra_fields: Additional fields to include
    """
    output = {
        "status": "partial",
        "source": source,
        "query": query,
        "results": results,
        "count": len(results),
        "errors": errors,
        "warning": warning,
        **extra_fields
    }
    _emit(output, 0)


def output_error(
    source: str,
    query: Any,
    error_type: str,
    message: str,
    exit_code: int = 2
) -> NoReturn:
    """
    Output error result and exit with specified code.

    Args:
        source: Source identifier
        query: Original query
        error_type: Error type (e.g., "not_found", "config_error", "api_error", "rate_limit")
        message: Error message
        exit_code: Exit code (default 2 for config errors, use 1 for not_found, 3 for API)
    """
    output = {
        "status": "error",
        "source": source,
        "query": query,
        "results": [],
        "count": 0,
        "errors": [make_error(error_type, message)]
    }
    _emit(output, exit_code)


def make_error(error_type: str, message: str, recoverable: bool | None = None) -> dict:
    """
    Create a properly structured error dictionary.

    Args:
        error_type: Error type identifier
        message: Error message
        recoverable: Whether error is recoverable (defaults based on error_type)

    Returns:
        Error dictionary with type, message, and recoverable fields
    """
    if recoverable is None:
        recoverable = error_type == "rate_limit"
    return {
        "type": error_type,
        "message": message,
        "recoverable": recoverable
    }
