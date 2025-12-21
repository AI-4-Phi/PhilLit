#!/usr/bin/env python3
"""
Search PhilPapers via Brave API.

Usage:
    python search_philpapers.py "epistemic injustice"
    python search_philpapers.py "virtue epistemology" --limit 40
    python search_philpapers.py "phenomenal consciousness" --recent

Exit Codes: 0=success, 1=not found, 2=config error, 3=API error
"""

import argparse
import json
import os
import re
import sys
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rate_limiter import ExponentialBackoff, get_limiter

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


def output_success(query: str, results: list) -> None:
    print(json.dumps({
        "status": "success", "source": "philpapers_via_brave", "query": query,
        "results": results, "count": len(results), "errors": []
    }, indent=2))
    sys.exit(0)


def output_partial(query: str, results: list, errors: list, warning: str) -> None:
    print(json.dumps({
        "status": "partial", "source": "philpapers_via_brave", "query": query,
        "results": results, "count": len(results), "errors": errors, "warning": warning
    }, indent=2))
    sys.exit(0)


def output_error(query: str, error_type: str, message: str, exit_code: int = 2) -> None:
    print(json.dumps({
        "status": "error", "source": "philpapers_via_brave", "query": query,
        "results": [], "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": error_type == "rate_limit"}]
    }, indent=2))
    sys.exit(exit_code)


def extract_philpapers_id(url: str) -> Optional[str]:
    """Extract PhilPapers record ID from URL."""
    match = re.search(r"philpapers\.org/rec/([A-Z0-9]+)", url)
    return match.group(1) if match else None


def format_result(item: dict) -> dict:
    url = item.get("url", "")
    pp_id = extract_philpapers_id(url)

    result = {
        "title": item.get("title", "").replace(" - PhilPapers", "").strip(),
        "url": url,
        "philpapers_id": pp_id,
        "snippet": item.get("description", ""),
        "page_age": item.get("page_age"),
    }

    # Extract author if available
    article = item.get("article", {})
    if article.get("author"):
        result["author"] = article["author"]

    if item.get("extra_snippets"):
        result["extra_snippets"] = item["extra_snippets"]

    return result


def search_philpapers(
    query: str,
    limit: int,
    api_key: str,
    recent: bool,
    all_pages: bool,
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> tuple[list[dict], list[dict]]:
    """Search PhilPapers via Brave API."""
    params = {
        "q": f"site:philpapers.org {query}",
        "count": 20,
        "text_decorations": "false",
        "result_filter": "web",
        "extra_snippets": "true",
    }
    if recent:
        params["freshness"] = "py"  # Past year

    headers = {"X-Subscription-Token": api_key}

    all_results = []
    errors = []
    max_offset = 9 if all_pages else 0

    for offset in range(0, max_offset + 1):
        if len(all_results) >= limit:
            break

        params["offset"] = offset

        for attempt in range(backoff.max_attempts):
            limiter.wait()

            if debug:
                print(f"DEBUG: GET {BRAVE_URL} offset={offset}", file=sys.stderr)

            try:
                response = requests.get(BRAVE_URL, params=params, headers=headers, timeout=30)
                limiter.record()

                if response.status_code == 200:
                    data = response.json()
                    web_results = data.get("web", {}).get("results", [])

                    if not web_results:
                        return all_results, errors

                    for item in web_results:
                        # Only include actual PhilPapers records
                        if "/rec/" in item.get("url", ""):
                            if len(all_results) < limit:
                                all_results.append(format_result(item))

                    break

                elif response.status_code == 429:
                    if not backoff.wait(attempt):
                        errors.append({"type": "rate_limit", "message": "Rate limit exceeded", "recoverable": True})
                        return all_results, errors
                    continue

                elif response.status_code == 401:
                    raise ValueError("Invalid BRAVE_API_KEY")

                else:
                    raise RuntimeError(f"Brave API error: {response.status_code}")

            except requests.exceptions.RequestException as e:
                if attempt < backoff.max_attempts - 1:
                    backoff.wait(attempt)
                    continue
                errors.append({"type": "network_error", "message": str(e), "recoverable": True})
                return all_results, errors

        if not all_pages:
            break

    return all_results, errors


def main():
    parser = argparse.ArgumentParser(description="Search PhilPapers via Brave API")
    parser.add_argument("query", help="Search terms")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--recent", action="store_true", help="Filter to past year")
    parser.add_argument("--all-pages", action="store_true", help="Fetch all available pages")
    parser.add_argument("--api-key", default=os.environ.get("BRAVE_API_KEY", ""))
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if not args.api_key:
        output_error(args.query, "config_error", "BRAVE_API_KEY not set", 2)

    limiter = get_limiter("brave")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        results, errors = search_philpapers(
            args.query, args.limit, args.api_key,
            args.recent, args.all_pages, limiter, backoff, args.debug
        )

        if not results and not errors:
            output_error(args.query, "not_found", "No PhilPapers entries found", 1)

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
