#!/usr/bin/env python3
"""
Search Internet Encyclopedia of Philosophy via Brave API.

Usage:
    python search_iep.py "free will"
    python search_iep.py "compatibilism determinism" --limit 10

Exit Codes: 0=success, 1=not found, 2=config error, 3=API error
"""

import argparse
import os
import sys

try:
    from .output import (
        output_success as _output_success,
        output_partial as _output_partial,
        output_error as _output_error,
        log_progress as _log_progress,
    )
    from .brave_search import brave_site_search, IEP_CONFIG
    from .rate_limiter import ExponentialBackoff, get_limiter
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from output import (
        output_success as _output_success,
        output_partial as _output_partial,
        output_error as _output_error,
        log_progress as _log_progress,
    )
    from brave_search import brave_site_search, IEP_CONFIG
    from rate_limiter import ExponentialBackoff, get_limiter

SOURCE = "iep_via_brave"


# Local wrappers to maintain backward-compatible function signatures
def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    _log_progress("search_iep.py", message)


def output_success(query: str, results: list) -> None:
    """Output successful search results."""
    _output_success(SOURCE, query, results)


def output_partial(query: str, results: list, errors: list, warning: str) -> None:
    """Output partial results with errors."""
    _output_partial(SOURCE, query, results, errors, warning)


def output_error(query: str, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    _output_error(SOURCE, query, error_type, message, exit_code)


def main():
    parser = argparse.ArgumentParser(description="Search IEP via Brave API")
    parser.add_argument("query", help="Search terms")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20, max: 200)")
    parser.add_argument("--all-pages", action="store_true", help="Fetch all available pages")
    parser.add_argument("--api-key", default=os.environ.get("BRAVE_API_KEY", ""))
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if not args.api_key:
        output_error(args.query, "config_error", "BRAVE_API_KEY not set", 2)

    limiter = get_limiter("brave")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        results, errors = brave_site_search(
            query=args.query,
            limit=args.limit,
            api_key=args.api_key,
            config=IEP_CONFIG,
            limiter=limiter,
            backoff=backoff,
            all_pages=args.all_pages,
            log_fn=log_progress,
            debug=args.debug,
        )

        if not results and not errors:
            output_error(args.query, "not_found", "No IEP entries found", 1)

        if errors:
            output_partial(args.query, results, errors, f"Found {len(results)} entries with errors")
        else:
            output_success(args.query, results)

    except ValueError as e:
        output_error(args.query, "config_error", str(e), 2)
    except RuntimeError as e:
        output_error(args.query, "api_error", str(e), 3)


if __name__ == "__main__":
    main()
