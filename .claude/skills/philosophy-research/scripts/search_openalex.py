#!/usr/bin/env python3
"""
Search OpenAlex for broad academic paper discovery and verification.

OpenAlex has 250M+ works, providing excellent coverage for cross-disciplinary research.

Usage:
    # Basic search
    python search_openalex.py "free will compatibilism"

    # With year filter
    python search_openalex.py "moral responsibility" --year 2020-2024 --limit 50

    # Direct DOI lookup
    python search_openalex.py --doi "10.2307/2024717"

    # OpenAlex ID lookup
    python search_openalex.py --id "W2741809807"

    # Find papers citing a work
    python search_openalex.py --cites "W2741809807" --limit 100

    # Open access only
    python search_openalex.py "epistemic injustice" --oa-only --min-citations 10

Output:
    JSON object with search results following the standard output schema.

Exit Codes:
    0: Success
    1: No results found
    2: Configuration error
    3: API error
"""

import argparse
import json
import os
import sys
from typing import Any, Optional

import requests

# Add parent directory to path for rate_limiter import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import ExponentialBackoff, get_limiter

# OpenAlex API configuration
OPENALEX_BASE_URL = "https://api.openalex.org"


def output_success(query: str, results: list) -> None:
    """Output successful search results."""
    print(json.dumps({
        "status": "success",
        "source": "openalex",
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
        "source": "openalex",
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
        "source": "openalex",
        "query": query,
        "results": [],
        "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": error_type == "rate_limit"}]
    }, indent=2))
    sys.exit(exit_code)


def reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return None

    # Build list of (position, word) tuples
    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    # Sort by position and join
    words.sort(key=lambda x: x[0])
    return " ".join(word for _, word in words)


def format_work(work: dict) -> dict:
    """Format OpenAlex work response into standard output format."""
    # Extract DOI
    doi = work.get("doi", "")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[16:]  # Strip prefix

    # Extract authors
    authors = []
    for authorship in work.get("authorships", []) or []:
        author_info = authorship.get("author", {})
        if author_info:
            author = {
                "name": author_info.get("display_name", ""),
                "openalex_id": author_info.get("id", "").replace("https://openalex.org/", ""),
            }
            if authorship.get("author", {}).get("orcid"):
                author["orcid"] = authorship["author"]["orcid"]

            # Get institutions
            institutions = []
            for inst in authorship.get("institutions", []) or []:
                if inst.get("display_name"):
                    institutions.append(inst["display_name"])
            if institutions:
                author["institutions"] = institutions

            authors.append(author)

    # Extract source info
    source = {}
    primary_location = work.get("primary_location", {}) or {}
    source_info = primary_location.get("source", {}) or {}
    if source_info:
        source = {
            "name": source_info.get("display_name"),
            "type": source_info.get("type"),
            "issn": source_info.get("issn"),
        }

    # Extract abstract
    abstract = None
    if work.get("abstract_inverted_index"):
        abstract = reconstruct_abstract(work["abstract_inverted_index"])

    # Extract open access info
    open_access = work.get("open_access", {}) or {}

    # Get OpenAlex ID
    openalex_id = work.get("id", "").replace("https://openalex.org/", "")

    return {
        "openalex_id": openalex_id,
        "doi": doi if doi else None,
        "title": work.get("title") or work.get("display_name"),
        "authors": authors,
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "abstract": abstract,
        "cited_by_count": work.get("cited_by_count"),
        "type": work.get("type"),
        "source": source if source.get("name") else None,
        "open_access": {
            "is_oa": open_access.get("is_oa", False),
            "oa_status": open_access.get("oa_status"),
            "oa_url": open_access.get("oa_url"),
        } if open_access else None,
        "topics": [t.get("display_name") for t in (work.get("topics", []) or [])[:5]],
        "referenced_works_count": len(work.get("referenced_works", []) or []),
        "url": f"https://openalex.org/{openalex_id}" if openalex_id else None,
    }


def get_work_by_id(
    work_id: str,
    email: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> dict:
    """Get a single work by OpenAlex ID or DOI."""
    # Determine if it's a DOI or OpenAlex ID
    if work_id.startswith("10.") or work_id.startswith("doi:"):
        work_id = work_id.replace("doi:", "")
        url = f"{OPENALEX_BASE_URL}/works/doi:{work_id}"
    elif work_id.startswith("W") or work_id.startswith("https://openalex.org/"):
        work_id = work_id.replace("https://openalex.org/", "")
        url = f"{OPENALEX_BASE_URL}/works/{work_id}"
    else:
        # Assume it's a DOI without prefix
        url = f"{OPENALEX_BASE_URL}/works/doi:{work_id}"

    params = {}
    if email:
        params["mailto"] = email

    for attempt in range(backoff.max_attempts):
        limiter.wait()

        if debug:
            print(f"DEBUG: GET {url}", file=sys.stderr)

        try:
            response = requests.get(url, params=params, timeout=30)
            limiter.record()

            if response.status_code == 200:
                return format_work(response.json())
            elif response.status_code == 404:
                raise LookupError(f"Work not found: {work_id}")
            elif response.status_code == 429:
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded")
                continue
            else:
                raise RuntimeError(f"OpenAlex API error: {response.status_code}")

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Max retries exceeded")


def search_works(
    query: str,
    limit: int,
    year: Optional[str],
    cites: Optional[str],
    oa_only: bool,
    min_citations: Optional[int],
    work_type: Optional[str],
    email: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> tuple[list[dict], list[dict]]:
    """
    Search OpenAlex works.

    Returns:
        Tuple of (results, errors)
    """
    url = f"{OPENALEX_BASE_URL}/works"

    params = {
        "per_page": min(limit, 200),  # API max is 200
    }

    if email:
        params["mailto"] = email

    # Build search query
    if query:
        params["search"] = query

    # Build filters
    filters = []
    if year:
        if "-" in year:
            start, end = year.split("-")
            filters.append(f"publication_year:{start}-{end}")
        else:
            filters.append(f"publication_year:{year}")
    if cites:
        cites_id = cites.replace("https://openalex.org/", "")
        filters.append(f"cites:{cites_id}")
    if oa_only:
        filters.append("is_oa:true")
    if min_citations:
        filters.append(f"cited_by_count:>{min_citations}")
    if work_type:
        filters.append(f"type:{work_type}")

    if filters:
        params["filter"] = ",".join(filters)

    all_results = []
    errors = []
    cursor = "*"

    while len(all_results) < limit and cursor:
        params["cursor"] = cursor
        params["per_page"] = min(limit - len(all_results), 200)

        for attempt in range(backoff.max_attempts):
            limiter.wait()

            if debug:
                print(f"DEBUG: GET {url} cursor={cursor[:20]}...", file=sys.stderr)

            try:
                response = requests.get(url, params=params, timeout=30)
                limiter.record()

                if debug:
                    print(f"DEBUG: Response status: {response.status_code}", file=sys.stderr)

                if response.status_code == 200:
                    data = response.json()
                    works = data.get("results", [])

                    if not works:
                        return all_results, errors

                    for work in works:
                        if len(all_results) >= limit:
                            break
                        all_results.append(format_work(work))

                    # Get next cursor
                    meta = data.get("meta", {})
                    cursor = meta.get("next_cursor")
                    if not cursor:
                        return all_results, errors

                    break  # Success, move to next page

                elif response.status_code == 429:
                    if not backoff.wait(attempt):
                        errors.append({
                            "type": "rate_limit",
                            "message": "Rate limit exceeded during pagination",
                            "recoverable": True
                        })
                        return all_results, errors
                    continue

                elif response.status_code == 400:
                    error_msg = response.json().get("message", "Bad request")
                    raise ValueError(f"Invalid query: {error_msg}")

                else:
                    raise RuntimeError(f"OpenAlex API error: {response.status_code}")

            except requests.exceptions.RequestException as e:
                if attempt < backoff.max_attempts - 1:
                    backoff.wait(attempt)
                    continue
                errors.append({
                    "type": "network_error",
                    "message": str(e),
                    "recoverable": True
                })
                return all_results, errors

    return all_results, errors


def main():
    parser = argparse.ArgumentParser(
        description="Search OpenAlex for academic papers"
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
        "--id",
        help="Direct lookup by OpenAlex ID (e.g., W2741809807)"
    )
    parser.add_argument(
        "--cites",
        help="Find papers citing this OpenAlex ID"
    )
    parser.add_argument(
        "--year",
        help="Year filter: YYYY or YYYY-YYYY range"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of results (default: 25, max: 200 per page)"
    )
    parser.add_argument(
        "--oa-only",
        action="store_true",
        help="Only return open access papers"
    )
    parser.add_argument(
        "--min-citations",
        type=int,
        help="Minimum citation count filter"
    )
    parser.add_argument(
        "--type",
        choices=["journal-article", "book", "book-chapter", "proceedings-article", "dataset", "preprint"],
        help="Filter by work type"
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("OPENALEX_EMAIL", ""),
        help="Email for polite pool (default: OPENALEX_EMAIL env var)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.query and not args.doi and not args.id and not args.cites:
        output_error(
            "",
            "config_error",
            "Must provide query, --doi, --id, or --cites",
            exit_code=2
        )

    if not args.email and args.debug:
        print("DEBUG: OPENALEX_EMAIL not set, using public pool", file=sys.stderr)

    # Initialize rate limiter and backoff
    limiter = get_limiter("openalex")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        # Direct lookups
        if args.doi or args.id:
            work_id = args.doi or args.id
            result = get_work_by_id(work_id, args.email, limiter, backoff, args.debug)
            output_success(work_id, [result])

        # Search
        else:
            query_str = args.query or f"cites:{args.cites}"
            results, errors = search_works(
                args.query,
                args.limit,
                args.year,
                args.cites,
                args.oa_only,
                args.min_citations,
                args.type,
                args.email,
                limiter,
                backoff,
                args.debug
            )

            if not results and not errors:
                output_error(query_str, "not_found", "No papers found matching query", exit_code=1)

            if errors:
                warning = f"Completed with {len(errors)} error(s). Found {len(results)} papers."
                output_partial(query_str, results, errors, warning)
            else:
                output_success(query_str, results)

    except LookupError as e:
        output_error(args.doi or args.id or args.query, "not_found", str(e), exit_code=1)

    except ValueError as e:
        output_error(args.query or "", "config_error", str(e), exit_code=2)

    except RuntimeError as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            output_error(args.query or "", "rate_limit", error_msg, exit_code=3)
        else:
            output_error(args.query or "", "api_error", error_msg, exit_code=3)


if __name__ == "__main__":
    main()
