#!/usr/bin/env python3
"""
Traverse citations and references for a paper in Semantic Scholar.

Usage:
    # Get papers this paper cites (references/backward)
    python s2_citations.py "DOI:10.2307/2024717" --references

    # Get papers that cite this paper (citations/forward)
    python s2_citations.py "CorpusId:12345" --citations

    # Get both directions
    python s2_citations.py "DOI:10.2307/2024717" --both

    # Filter to influential citations only
    python s2_citations.py "DOI:10.2307/2024717" --both --influential-only

Paper ID formats:
    - DOI:10.xxx/xxx
    - CorpusId:12345
    - ARXIV:2301.00001
    - URL:https://arxiv.org/abs/...
    - Raw Semantic Scholar paper ID (40-char hex)

Output:
    JSON object with paper info and citation lists.

Exit Codes:
    0: Success
    1: Paper not found
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
    from .s2_formatters import (
        format_paper as _format_paper,
        format_citation,
        S2_BASE_URL,
        S2_PAPER_FIELDS,
        S2_CITATION_FIELDS,
    )
    from .rate_limiter import ExponentialBackoff, get_limiter
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from output import (
        output_success as _output_success,
        output_partial as _output_partial,
        output_error as _output_error,
        log_progress as _log_progress,
    )
    from s2_formatters import (
        format_paper as _format_paper,
        format_citation,
        S2_BASE_URL,
        S2_PAPER_FIELDS,
        S2_CITATION_FIELDS,
    )
    from rate_limiter import ExponentialBackoff, get_limiter

SOURCE = "semantic_scholar"


# Local wrappers to maintain backward-compatible function signatures
def log_progress(message: str) -> None:
    """Log progress message to stderr."""
    _log_progress("s2_citations.py", message)


def format_paper(paper: dict) -> dict:
    """Format S2 paper response (without extended fields for citations)."""
    return _format_paper(paper, include_extended=False)


def output_success(paper_id: str, result: dict) -> None:
    """Output successful citation traversal results."""
    _output_success(SOURCE, paper_id, [result])


def output_partial(paper_id: str, result: dict, errors: list, warning: str) -> None:
    """Output partial results with errors."""
    _output_partial(SOURCE, paper_id, [result], errors, warning)


def output_error(paper_id: str, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    _output_error(SOURCE, paper_id, error_type, message, exit_code)


def get_paper_details(
    paper_id: str,
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> dict:
    """Get basic paper details."""
    log_progress(f"Connecting to Semantic Scholar API...")
    url = f"{S2_BASE_URL}/paper/{paper_id}"
    params = {"fields": S2_PAPER_FIELDS}

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    for attempt in range(backoff.max_attempts):
        limiter.wait()

        if debug:
            print(f"DEBUG: GET {url}", file=sys.stderr)

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            limiter.record()

            if response.status_code == 200:
                result = format_paper(response.json())
                log_progress(f"Found paper: {result.get('title', '')[:50]}...")
                return result
            elif response.status_code == 404:
                raise LookupError(f"Paper not found: {paper_id}")
            elif response.status_code == 429:
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded")
                continue
            else:
                raise RuntimeError(f"S2 API error: {response.status_code}")

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Max retries exceeded")


def get_citations(
    paper_id: str,
    direction: str,  # "citations" or "references"
    limit: int,
    influential_only: bool,
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> tuple[list[dict], list[dict]]:
    """
    Get citations or references for a paper.

    Returns:
        Tuple of (results, errors)
    """
    direction_label = "citing papers" if direction == "citations" else "references"
    log_progress(f"Fetching {direction_label}...")
    url = f"{S2_BASE_URL}/paper/{paper_id}/{direction}"
    params = {
        "fields": S2_CITATION_FIELDS,
        "limit": min(limit, 1000),
    }

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

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

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("data", [])

                    if not items:
                        return all_results, errors

                    for item in items:
                        if len(all_results) >= limit:
                            break

                        formatted = format_citation(item, direction)

                        # Filter by influential if requested
                        if influential_only and not formatted.get("isInfluential"):
                            continue

                        all_results.append(formatted)

                    # Check if there are more results
                    if len(items) < params["limit"]:
                        log_progress(f"Retrieved {len(all_results)} {direction_label}")
                        return all_results, errors

                    offset += len(items)
                    log_progress(f"Retrieved {len(all_results)} {direction_label}, fetching more...")
                    break  # Success, move to next page

                elif response.status_code == 404:
                    raise LookupError(f"Paper not found: {paper_id}")

                elif response.status_code == 429:
                    if not backoff.wait(attempt):
                        errors.append({
                            "type": "rate_limit",
                            "message": f"Rate limit exceeded fetching {direction} at offset {offset}",
                            "recoverable": True
                        })
                        return all_results, errors
                    continue

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
                return all_results, errors

    return all_results, errors


def main():
    parser = argparse.ArgumentParser(
        description="Traverse citations and references for a paper"
    )
    parser.add_argument(
        "paper_id",
        help="Paper identifier (DOI:, CorpusId:, ARXIV:, URL:, or raw paper ID)"
    )
    parser.add_argument(
        "--references",
        action="store_true",
        help="Get papers this paper cites (backward traversal)"
    )
    parser.add_argument(
        "--citations",
        action="store_true",
        help="Get papers that cite this paper (forward traversal)"
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Get both references and citations"
    )
    parser.add_argument(
        "--influential-only",
        action="store_true",
        help="Only include influential citations/references"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum results per direction (default: 100, max: 1000)"
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

    args = parser.parse_args()

    # Validate arguments
    if not (args.references or args.citations or args.both):
        output_error(
            args.paper_id,
            "config_error",
            "Must specify --references, --citations, or --both",
            exit_code=2
        )

    if args.limit > 1000:
        output_error(
            args.paper_id,
            "config_error",
            f"Limit {args.limit} exceeds maximum 1000",
            exit_code=2
        )

    fetch_references = args.references or args.both
    fetch_citations = args.citations or args.both

    # Initialize rate limiter and backoff
    limiter = get_limiter("semantic_scholar")
    backoff = ExponentialBackoff(max_attempts=5)

    all_errors = []

    try:
        # Get paper details first
        paper = get_paper_details(
            args.paper_id,
            args.api_key,
            limiter,
            backoff,
            args.debug
        )

        result = {
            "paper": paper,
            "references": [],
            "citations": [],
            "references_count": 0,
            "citations_count": 0,
        }

        # Get references if requested
        if fetch_references:
            refs, ref_errors = get_citations(
                args.paper_id,
                "references",
                args.limit,
                args.influential_only,
                args.api_key,
                limiter,
                backoff,
                args.debug
            )
            result["references"] = refs
            result["references_count"] = len(refs)
            all_errors.extend(ref_errors)

        # Get citations if requested
        if fetch_citations:
            cites, cite_errors = get_citations(
                args.paper_id,
                "citations",
                args.limit,
                args.influential_only,
                args.api_key,
                limiter,
                backoff,
                args.debug
            )
            result["citations"] = cites
            result["citations_count"] = len(cites)
            all_errors.extend(cite_errors)

        # Output results
        if all_errors:
            warning = f"Completed with {len(all_errors)} error(s). Some results may be incomplete."
            output_partial(args.paper_id, result, all_errors, warning)
        else:
            output_success(args.paper_id, result)

    except LookupError as e:
        output_error(args.paper_id, "not_found", str(e), exit_code=1)

    except RuntimeError as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            output_error(args.paper_id, "rate_limit", error_msg, exit_code=3)
        else:
            output_error(args.paper_id, "api_error", error_msg, exit_code=3)


if __name__ == "__main__":
    main()
