#!/usr/bin/env python3
"""
Semantic Scholar paper search with relevance ranking or bulk retrieval.

Usage:
    # Basic relevance search
    python s2_search.py "free will compatibilism" --limit 20

    # Bulk search (no ranking, up to 1000 results)
    python s2_search.py "moral responsibility" --bulk --year 2020-2024

    # Filtered search
    python s2_search.py "Frankfurt cases" --field Philosophy --min-citations 10

    # With year range
    python s2_search.py "epistemic injustice" --year 2015-2025 --limit 50

Output:
    JSON object with search results following the standard output schema.

Exit Codes:
    0: Success (results found) or partial success
    1: No results found
    2: Configuration error
    3: API error
"""

import argparse
import os
import sys
from typing import Optional

import requests

try:
    from .output import (
        output_success as _output_success,
        output_partial as _output_partial,
        output_error as _output_error,
        log_progress as _log_progress,
    )
    from .s2_formatters import format_paper, S2_BASE_URL, S2_FIELDS
    from .rate_limiter import ExponentialBackoff, get_limiter
    from .search_cache import cache_key, get_cache, put_cache
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from output import (
        output_success as _output_success,
        output_partial as _output_partial,
        output_error as _output_error,
        log_progress as _log_progress,
    )
    from s2_formatters import format_paper, S2_BASE_URL, S2_FIELDS
    from rate_limiter import ExponentialBackoff, get_limiter
    from search_cache import cache_key, get_cache, put_cache

SOURCE = "semantic_scholar"


# Local wrappers to maintain backward-compatible function signatures
def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    _log_progress("s2_search.py", message)


def output_success(query: str, results: list, source: str = SOURCE) -> None:
    """Output successful search results."""
    _output_success(source, query, results)


def output_partial(query: str, results: list, errors: list, warning: str) -> None:
    """Output partial results with errors."""
    _output_partial(SOURCE, query, results, errors, warning)


def output_error(query: str, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    _output_error(SOURCE, query, error_type, message, exit_code)


def relevance_search(
    query: str,
    limit: int,
    year: Optional[str],
    field: Optional[str],
    min_citations: Optional[int],
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> list[dict]:
    """
    Perform relevance-ranked search (default mode).
    Returns up to 100 results per request.
    """
    # Build search description
    search_desc = f"'{query}'"
    if year:
        search_desc += f" (year={year})"
    if field:
        search_desc += f" (field={field})"
    if min_citations:
        search_desc += f" (min_citations={min_citations})"

    log_progress(f"Searching Semantic Scholar: {search_desc}, limit={limit}")

    url = f"{S2_BASE_URL}/paper/search"

    params = {
        "query": query,
        "fields": S2_FIELDS,
        "limit": min(limit, 100),  # API max is 100 for relevance search
    }

    if year:
        params["year"] = year
    if field:
        params["fieldsOfStudy"] = field
    if min_citations:
        params["minCitationCount"] = min_citations

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    all_results = []
    offset = 0
    errors = []

    while len(all_results) < limit:
        params["offset"] = offset
        params["limit"] = min(limit - len(all_results), 100)

        for attempt in range(backoff.max_attempts):
            limiter.wait()

            if debug:
                print(f"DEBUG: GET {url} offset={offset}", file=sys.stderr)

            try:
                response = requests.get(url, params=params, headers=headers, timeout=30)
                limiter.record()

                if debug:
                    print(f"DEBUG: Response status: {response.status_code}", file=sys.stderr)

                if response.status_code == 200:
                    data = response.json()
                    papers = data.get("data", [])

                    if not papers:
                        # No more results
                        log_progress(f"Found {len(all_results)} papers total")
                        return all_results

                    for paper in papers:
                        all_results.append(format_paper(paper))

                    # Check if there are more results
                    total = data.get("total", 0)
                    log_progress(f"Retrieved {len(all_results)}/{min(limit, total)} papers...")

                    if offset + len(papers) >= total or len(papers) < params["limit"]:
                        log_progress(f"Search complete: {len(all_results)} papers found")
                        return all_results

                    offset += len(papers)
                    break  # Success, move to next page

                elif response.status_code == 429:
                    log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                    if not backoff.wait(attempt):
                        log_progress(f"Max retries reached, returning {len(all_results)} partial results")
                        errors.append({
                            "type": "rate_limit",
                            "message": f"Rate limit exceeded at offset {offset}",
                            "recoverable": True
                        })
                        # Return partial results
                        return all_results
                    log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                    continue

                elif response.status_code == 400:
                    error_msg = response.json().get("message", "Bad request")
                    raise ValueError(f"Invalid query: {error_msg}")

                else:
                    raise RuntimeError(f"S2 API error: {response.status_code}")

            except requests.exceptions.RequestException as e:
                log_progress(f"Network error: {str(e)[:100]}, retrying (attempt {attempt+1}/{backoff.max_attempts})...")
                if attempt < backoff.max_attempts - 1:
                    backoff.wait(attempt)
                    log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                    continue
                log_progress(f"Max retries reached after network errors, returning {len(all_results)} partial results")
                errors.append({
                    "type": "network_error",
                    "message": str(e),
                    "recoverable": True
                })
                return all_results

    return all_results


def bulk_search(
    query: str,
    limit: int,
    year: Optional[str],
    field: Optional[str],
    min_citations: Optional[int],
    sort: Optional[str],
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> list[dict]:
    """
    Perform bulk search (no relevance ranking, up to 1000 per request).
    Supports boolean operators in query.
    """
    # Build search description
    search_desc = f"'{query}'"
    if year:
        search_desc += f" (year={year})"
    if field:
        search_desc += f" (field={field})"
    if min_citations:
        search_desc += f" (min_citations={min_citations})"

    log_progress(f"Bulk searching Semantic Scholar: {search_desc}, limit={limit}")

    url = f"{S2_BASE_URL}/paper/search/bulk"

    params = {
        "query": query,
        "fields": S2_FIELDS,
    }

    if year:
        params["year"] = year
    if field:
        params["fieldsOfStudy"] = field
    if min_citations:
        params["minCitationCount"] = min_citations
    if sort:
        params["sort"] = sort

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    all_results = []
    token = None
    errors = []

    while len(all_results) < limit:
        if token:
            params["token"] = token

        for attempt in range(backoff.max_attempts):
            limiter.wait()

            if debug:
                print(f"DEBUG: GET {url} token={token}", file=sys.stderr)

            try:
                response = requests.get(url, params=params, headers=headers, timeout=30)
                limiter.record()

                if debug:
                    print(f"DEBUG: Response status: {response.status_code}", file=sys.stderr)

                if response.status_code == 200:
                    data = response.json()
                    papers = data.get("data", [])

                    for paper in papers:
                        if len(all_results) >= limit:
                            break
                        all_results.append(format_paper(paper))

                    log_progress(f"Retrieved {len(all_results)} papers...")

                    # Check for continuation token
                    token = data.get("token")
                    if not token or len(papers) == 0:
                        log_progress(f"Bulk search complete: {len(all_results)} papers found")
                        return all_results

                    break  # Success, move to next page

                elif response.status_code == 429:
                    log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                    if not backoff.wait(attempt):
                        log_progress(f"Max retries reached, returning {len(all_results)} partial results")
                        errors.append({
                            "type": "rate_limit",
                            "message": "Rate limit exceeded during bulk search",
                            "recoverable": True
                        })
                        return all_results
                    log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                    continue

                elif response.status_code == 400:
                    error_msg = response.json().get("message", "Bad request")
                    raise ValueError(f"Invalid query: {error_msg}")

                else:
                    raise RuntimeError(f"S2 API error: {response.status_code}")

            except requests.exceptions.RequestException as e:
                if attempt < backoff.max_attempts - 1:
                    backoff.wait(attempt)
                    continue
                errors.append({
                    "type": "network_error",
                    "message": str(e),
                    "recoverable": True
                })
                return all_results

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Search Semantic Scholar for papers"
    )
    parser.add_argument(
        "query",
        help="Search query string"
    )
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="Use bulk search (no ranking, up to 1000 results, supports boolean operators)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results (default: 20, max: 100 for relevance, 1000 for bulk)"
    )
    parser.add_argument(
        "--year",
        help="Year filter: YYYY or YYYY-YYYY range"
    )
    parser.add_argument(
        "--field",
        help="Field of study filter (e.g., Philosophy, Computer Science)"
    )
    parser.add_argument(
        "--min-citations",
        type=int,
        help="Minimum citation count filter"
    )
    parser.add_argument(
        "--sort",
        choices=["paperId", "publicationDate", "citationCount"],
        help="Sort order for bulk search"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("S2_API_KEY", ""),
        help="Semantic Scholar API key (default: S2_API_KEY env var)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable result caching"
    )

    args = parser.parse_args()

    # Validate limit
    max_limit = 1000 if args.bulk else 100
    if args.limit > max_limit:
        output_error(
            args.query,
            "config_error",
            f"Limit {args.limit} exceeds maximum {max_limit} for {'bulk' if args.bulk else 'relevance'} search",
            exit_code=2
        )

    if not args.api_key and args.debug:
        print("DEBUG: S2_API_KEY not set, using unauthenticated access", file=sys.stderr)

    # Generate cache key from query parameters
    cache_params = {
        "query": args.query,
        "limit": args.limit,
        "bulk": args.bulk,
    }
    if args.year:
        cache_params["year"] = args.year
    if args.field:
        cache_params["field"] = args.field
    if args.min_citations:
        cache_params["min_citations"] = args.min_citations
    if args.sort:
        cache_params["sort"] = args.sort

    key = cache_key(source="s2", **cache_params)

    # Check cache first (unless --no-cache)
    if not args.no_cache:
        cached = get_cache(key)
        if cached:
            log_progress(f"Using cached results (cache key: {key})")
            output_success(args.query, cached)

    # Initialize rate limiter and backoff
    limiter = get_limiter("semantic_scholar")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        if args.bulk:
            results = bulk_search(
                args.query,
                args.limit,
                args.year,
                args.field,
                args.min_citations,
                args.sort,
                args.api_key,
                limiter,
                backoff,
                args.debug
            )
        else:
            results = relevance_search(
                args.query,
                args.limit,
                args.year,
                args.field,
                args.min_citations,
                args.api_key,
                limiter,
                backoff,
                args.debug
            )

        if not results:
            output_error(args.query, "not_found", "No papers found matching query", exit_code=1)

        # Cache results (unless --no-cache)
        if not args.no_cache:
            if put_cache(key, results):
                log_progress(f"Cached results (cache key: {key})")

        output_success(args.query, results)

    except ValueError as e:
        output_error(args.query, "config_error", str(e), exit_code=2)

    except RuntimeError as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            output_error(args.query, "rate_limit", error_msg, exit_code=3)
        else:
            output_error(args.query, "api_error", error_msg, exit_code=3)


if __name__ == "__main__":
    main()
