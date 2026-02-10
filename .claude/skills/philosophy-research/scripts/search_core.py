#!/usr/bin/env python3
"""
Search CORE API for papers with abstracts.

CORE aggregates 431M+ research outputs from repositories worldwide,
with 46M+ full texts. Excellent for finding open access versions and abstracts.

Usage:
    # Basic search
    python search_core.py "epistemic injustice"

    # Search by DOI
    python search_core.py --doi "10.1111/nous.12191"

    # Search by title and author
    python search_core.py --title "Freedom of the Will" --author "Frankfurt"

    # With year filter
    python search_core.py "moral responsibility" --year 2020-2024 --limit 20

Output:
    JSON object with search results following the standard output schema.

Exit Codes:
    0: Success
    1: No results found
    2: Configuration error
    3: API error

Rate Limits (free tier, no API key):
    - /search/{query}: 5 requests per 10 seconds
    - /search (batch): 1 request per 10 seconds
"""

import argparse
import json
import os
import sys
from typing import Optional
from urllib.parse import quote

import requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import ExponentialBackoff, get_limiter

# CORE API configuration
CORE_BASE_URL = "https://api.core.ac.uk/v3"
SOURCE = "core"


def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    print(f"[search_core.py] {message}", file=sys.stderr, flush=True)


def output_success(query: str, results: list) -> None:
    """Output successful search results."""
    print(json.dumps({
        "status": "success",
        "source": SOURCE,
        "query": query,
        "results": results,
        "count": len(results),
        "errors": []
    }, indent=2))
    sys.exit(0)


def output_partial(query: str, results: list, errors: list, warning: str) -> None:
    """Output partial results with errors."""
    print(json.dumps({
        "status": "partial",
        "source": SOURCE,
        "query": query,
        "results": results,
        "count": len(results),
        "errors": errors,
        "warning": warning
    }, indent=2))
    sys.exit(0)


def output_error(query: str, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    print(json.dumps({
        "status": "error",
        "source": SOURCE,
        "query": query,
        "results": [],
        "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": error_type == "rate_limit"}]
    }, indent=2))
    sys.exit(exit_code)


def format_work(work: dict) -> dict:
    """Format CORE work response into standard output format."""
    # Extract authors
    authors = []
    for author in work.get("authors", []) or []:
        if isinstance(author, dict):
            name = author.get("name", "")
        else:
            name = str(author)
        if name:
            authors.append({"name": name})

    # Extract DOI (may be in identifiers or as direct field)
    doi = None
    if work.get("doi"):
        doi = work["doi"]
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]

    # Extract year from publishedDate or year field
    year = work.get("yearPublished")
    if not year and work.get("publishedDate"):
        try:
            year = int(work["publishedDate"][:4])
        except (ValueError, TypeError):
            pass

    return {
        "core_id": str(work.get("id", "")),
        "doi": doi,
        "title": work.get("title"),
        "authors": authors,
        "year": year,
        "abstract": work.get("abstract"),
        "publisher": work.get("publisher"),
        "journal": work.get("journals", [{}])[0].get("title") if work.get("journals") else None,
        "download_url": work.get("downloadUrl"),
        "source_url": work.get("sourceFulltextUrls", [None])[0] if work.get("sourceFulltextUrls") else None,
        "language": work.get("language", {}).get("code") if isinstance(work.get("language"), dict) else work.get("language"),
        "document_type": work.get("documentType"),
    }


def search_core(
    query: str,
    limit: int,
    year: Optional[str],
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> tuple[list[dict], list[dict]]:
    """
    Search CORE for papers.

    Returns:
        Tuple of (results, errors)
    """
    search_desc = f"'{query}'"
    if year:
        search_desc += f" (year={year})"

    log_progress(f"Searching CORE: {search_desc}, limit={limit}")

    # Use single query endpoint (5 req/10 sec)
    url = f"{CORE_BASE_URL}/search/works"

    params = {
        "q": query,
        "limit": min(limit, 100),  # API max per request
    }

    # Add year filter if specified
    if year:
        if "-" in year:
            start, end = year.split("-")
            params["q"] = f"{query} AND yearPublished>={start} AND yearPublished<={end}"
        else:
            params["q"] = f"{query} AND yearPublished:{year}"

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    all_results = []
    errors = []
    offset = 0

    while len(all_results) < limit:
        params["offset"] = offset

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
                    works = data.get("results", [])

                    if not works:
                        log_progress(f"Search complete: {len(all_results)} papers found")
                        return all_results, errors

                    for work in works:
                        if len(all_results) >= limit:
                            break
                        formatted = format_work(work)
                        # Only include if has abstract (our main use case)
                        all_results.append(formatted)

                    total = data.get("totalHits", 0)
                    log_progress(f"Retrieved {len(all_results)}/{min(limit, total)} papers...")

                    if len(works) < params["limit"] or len(all_results) >= limit:
                        log_progress(f"Search complete: {len(all_results)} papers found")
                        return all_results, errors

                    offset += len(works)
                    break  # Success, move to next page

                elif response.status_code == 429:
                    log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                    if not backoff.wait(attempt):
                        log_progress(f"Max retries reached, returning {len(all_results)} partial results")
                        errors.append({
                            "type": "rate_limit",
                            "message": "Rate limit exceeded during pagination",
                            "recoverable": True
                        })
                        return all_results, errors
                    log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                    continue

                elif response.status_code == 400:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("message", "Bad request")
                    raise ValueError(f"Invalid query: {error_msg}")

                elif response.status_code == 401:
                    raise ValueError("Invalid or missing API key")

                else:
                    raise RuntimeError(f"CORE API error: {response.status_code}")

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
                return all_results, errors

    log_progress(f"Search complete: {len(all_results)} papers found")
    return all_results, errors


def search_by_doi(
    doi: str,
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> Optional[dict]:
    """Search CORE for a specific DOI."""
    log_progress(f"Looking up DOI: {doi}")

    # Clean DOI
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]

    # Search by DOI
    query = f'doi:"{doi}"'
    results, _ = search_core(query, 1, None, api_key, limiter, backoff, debug)

    if results:
        return results[0]
    return None


def search_by_title_author(
    title: str,
    author: Optional[str],
    year: Optional[int],
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> list[dict]:
    """Search CORE by title and optionally author/year."""
    log_progress(f"Searching by title: '{title}'" + (f", author: '{author}'" if author else ""))

    # Build query
    query_parts = [f'title:"{title}"']
    if author:
        query_parts.append(f'authors:"{author}"')

    query = " AND ".join(query_parts)

    year_str = str(year) if year else None
    results, _ = search_core(query, 10, year_str, api_key, limiter, backoff, debug)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Search CORE API for papers with abstracts"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query string"
    )
    parser.add_argument(
        "--doi",
        help="Direct lookup by DOI"
    )
    parser.add_argument(
        "--title",
        help="Search by title (can combine with --author)"
    )
    parser.add_argument(
        "--author",
        help="Author name filter (use with --title or query)"
    )
    parser.add_argument(
        "--year",
        help="Year filter: YYYY or YYYY-YYYY range"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results (default: 20)"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CORE_API_KEY", ""),
        help="CORE API key (default: CORE_API_KEY env var, optional)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.query and not args.doi and not args.title:
        output_error(
            "",
            "config_error",
            "Must provide query, --doi, or --title",
            exit_code=2
        )

    # Initialize rate limiter and backoff
    limiter = get_limiter("core")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        # DOI lookup
        if args.doi:
            result = search_by_doi(args.doi, args.api_key, limiter, backoff, args.debug)
            if result:
                output_success(args.doi, [result])
            else:
                output_error(args.doi, "not_found", f"No paper found with DOI: {args.doi}", exit_code=1)

        # Title + author search
        elif args.title:
            year = None
            if args.year and "-" not in args.year:
                year = int(args.year)
            results = search_by_title_author(
                args.title, args.author, year,
                args.api_key, limiter, backoff, args.debug
            )
            if results:
                output_success(f"title:{args.title}", results)
            else:
                output_error(
                    f"title:{args.title}",
                    "not_found",
                    f"No papers found matching title: {args.title}",
                    exit_code=1
                )

        # General search
        else:
            query = args.query
            if args.author:
                query = f'{query} AND authors:"{args.author}"'

            results, errors = search_core(
                query,
                args.limit,
                args.year,
                args.api_key,
                limiter,
                backoff,
                args.debug
            )

            if not results and not errors:
                output_error(args.query, "not_found", "No papers found matching query", exit_code=1)

            if errors:
                warning = f"Completed with {len(errors)} error(s). Found {len(results)} papers."
                output_partial(args.query, results, errors, warning)
            else:
                output_success(args.query, results)

    except ValueError as e:
        output_error(args.query or args.doi or args.title, "config_error", str(e), exit_code=2)

    except RuntimeError as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            output_error(args.query or "", "rate_limit", error_msg, exit_code=3)
        else:
            output_error(args.query or "", "api_error", error_msg, exit_code=3)


if __name__ == "__main__":
    main()
