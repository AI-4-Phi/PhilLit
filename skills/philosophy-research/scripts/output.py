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

import json
import sys
from typing import Any, NoReturn


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
    print(json.dumps(output, indent=2))
    sys.exit(0)


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
    print(json.dumps(output, indent=2))
    sys.exit(0)


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
    print(json.dumps(output, indent=2))
    sys.exit(exit_code)


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
