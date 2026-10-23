#!/usr/bin/env python3
"""
Search Internet Encyclopedia of Philosophy via a site-scoped web search.

Default provider is Brave (BRAVE_API_KEY required). The optional keyless
youcom provider (PHILLIT_SEARCH_PROVIDER=youcom or --provider youcom)
searches via You.com's MCP endpoint and needs no API key.

Usage:
    python search_iep.py "free will"
    python search_iep.py "compatibilism determinism" --limit 10
    python search_iep.py "free will" --provider youcom

Exit Codes: 0=success, 1=not found, 2=config error, 3=API error
"""

import argparse
import os
import sys

from dotenv import find_dotenv, load_dotenv

try:
    from .output import (
        output_success as _output_success,
        output_partial as _output_partial,
        output_error as _output_error,
        log_progress as _log_progress,
        set_output_path,
        add_output_arg,
    )
    from .brave_search import brave_site_search, IEP_CONFIG
    from .youcom_search import youcom_site_search
    from .rate_limiter import ExponentialBackoff, get_limiter
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from output import (
        output_success as _output_success,
        output_partial as _output_partial,
        output_error as _output_error,
        log_progress as _log_progress,
        set_output_path,
        add_output_arg,
    )
    from brave_search import brave_site_search, IEP_CONFIG
    from youcom_search import youcom_site_search
    from rate_limiter import ExponentialBackoff, get_limiter

SOURCE = "iep_via_brave"
SOURCE_YOUCOM = "iep_via_youcom"


# Local wrappers to maintain backward-compatible function signatures
def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    _log_progress("search_iep.py", message)


def output_success(query: str, results: list, source: str = SOURCE) -> None:
    """Output successful search results."""
    _output_success(source, query, results)


def output_partial(query: str, results: list, errors: list, warning: str, source: str = SOURCE) -> None:
    """Output partial results with errors."""
    _output_partial(source, query, results, errors, warning)


def output_error(query: str, error_type: str, message: str, exit_code: int = 2, source: str = SOURCE) -> None:
    """Output error result."""
    _output_error(source, query, error_type, message, exit_code)


def main():
    load_dotenv(find_dotenv(usecwd=True), override=True)  # must run before argparse defaults read os.environ
    parser = argparse.ArgumentParser(description="Search IEP via a site-scoped web search")
    parser.add_argument("query", help="Search terms")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20, max: 200)")
    parser.add_argument("--all-pages", action="store_true", help="Fetch all available pages (Brave only)")
    parser.add_argument(
        "--provider",
        choices=("brave", "youcom"),
        default=(os.environ.get("PHILLIT_SEARCH_PROVIDER", "brave").strip().lower() or "brave"),
        help="Site search provider: brave (default, needs BRAVE_API_KEY) or youcom (keyless; YDC_API_KEY optional)",
    )
    parser.add_argument("--api-key", default="", help="API key (brave: BRAVE_API_KEY, required; youcom: YDC_API_KEY, optional)")
    parser.add_argument("--debug", action="store_true")

    add_output_arg(parser)
    args = parser.parse_args()
    set_output_path(args.output)

    if not args.api_key:
        args.api_key = os.environ.get("BRAVE_API_KEY" if args.provider == "brave" else "YDC_API_KEY", "")

    source = SOURCE if args.provider == "brave" else SOURCE_YOUCOM
    limiter = get_limiter("brave" if args.provider == "brave" else "youcom")
    backoff = ExponentialBackoff(max_attempts=5)

    if args.provider == "brave":
        if not args.api_key:
            output_error(args.query, "config_error", "BRAVE_API_KEY not set", 2)
    elif args.all_pages:
        # The You.com endpoint serves one request per search; nothing to page.
        log_progress("You.com does not paginate; fetching up to the limit in one request")

    try:
        if args.provider == "brave":
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
        else:
            results, errors = youcom_site_search(
                query=args.query,
                limit=args.limit,
                config=IEP_CONFIG,
                limiter=limiter,
                backoff=backoff,
                api_key=args.api_key or None,
                log_fn=log_progress,
                debug=args.debug,
            )

        if not results and not errors:
            output_error(args.query, "not_found", "No IEP entries found", 1, source=source)

        if errors:
            output_partial(args.query, results, errors, f"Found {len(results)} entries with errors", source=source)
        else:
            output_success(args.query, results, source=source)

    except ValueError as e:
        output_error(args.query, "config_error", str(e), 2, source=source)
    except RuntimeError as e:
        output_error(args.query, "api_error", str(e), 3, source=source)


if __name__ == "__main__":
    main()
