#!/usr/bin/env python3
"""
Verify paper existence and retrieve/validate DOI via CrossRef.

This script verifies that a paper exists and retrieves its metadata.
It can look up papers by DOI directly or search by title/author.

Usage:
    # Verify by DOI (fastest, most reliable)
    python verify_paper.py --doi "10.2307/2024717"

    # Search by title and author
    python verify_paper.py --title "Freedom of the Will and the Concept of a Person" --author "Frankfurt"

    # Search with year filter
    python verify_paper.py --title "Freedom of the Will" --author "Frankfurt" --year 1971

    # Verify DOI matches expected metadata
    python verify_paper.py --doi "10.2307/2024717" --title "Freedom of the Will" --verify-metadata

Output:
    JSON object with verification results following the standard output schema.

Exit Codes:
    0: Success (paper found and verified)
    1: Paper not found
    2: Configuration error (missing env var, invalid args)
    3: API error (network, rate limit after retries)
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


def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    print(f"[verify_paper.py] {message}", file=sys.stderr, flush=True)


# Standard output helpers
def output_success(query: dict, result: dict) -> None:
    """Output successful verification result."""
    print(json.dumps({
        "status": "success",
        "source": "crossref",
        "query": query,
        "results": [result],
        "count": 1,
        "errors": []
    }, indent=2))
    sys.exit(0)


def output_not_found(query: dict, message: str) -> None:
    """Output when paper is not found."""
    print(json.dumps({
        "status": "error",
        "source": "crossref",
        "query": query,
        "results": [],
        "count": 0,
        "errors": [{"type": "not_found", "message": message, "recoverable": False}]
    }, indent=2))
    sys.exit(1)


def output_error(query: dict, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    print(json.dumps({
        "status": "error",
        "source": "crossref",
        "query": query,
        "results": [],
        "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": error_type == "rate_limit"}]
    }, indent=2))
    sys.exit(exit_code)


def normalize_doi(doi: str) -> str:
    """Normalize DOI by removing common prefixes."""
    doi = doi.strip()
    prefixes = ["https://doi.org/", "http://doi.org/", "doi:", "DOI:"]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def extract_author_names(authors: list[dict]) -> list[str]:
    """Extract author names from CrossRef author format."""
    names = []
    for author in authors:
        if "family" in author:
            if "given" in author:
                names.append(f"{author['family']}, {author['given']}")
            else:
                names.append(author["family"])
        elif "name" in author:  # Organization name
            names.append(author["name"])
    return names


# CrossRef type → BibTeX entry type mapping
CROSSREF_TO_BIBTEX_TYPE = {
    "journal-article": "article",
    "book-chapter": "incollection",
    "book-section": "incollection",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "proceedings-article": "inproceedings",
    "dissertation": "phdthesis",
    "posted-content": "misc",       # preprints
    "report": "techreport",
    "reference-entry": "misc",
}


def format_result(item: dict, method: str, score: Optional[float] = None) -> dict:
    """Format CrossRef result into standard output format."""
    # Extract DOI
    doi = item.get("DOI", "")

    # Extract title (CrossRef returns list)
    titles = item.get("title", [])
    title = titles[0] if titles else ""

    # Extract authors and editors
    authors = extract_author_names(item.get("author", []))
    editors = extract_author_names(item.get("editor", []))

    # Extract year from various date fields
    year = None
    for date_field in ["published", "published-print", "published-online", "created"]:
        if date_field in item and "date-parts" in item[date_field]:
            parts = item[date_field]["date-parts"]
            if parts and parts[0] and parts[0][0]:
                year = parts[0][0]
                break

    # Extract container title (journal/book)
    container = item.get("container-title", [])
    container_title = container[0] if container else ""

    # Extract volume, issue, pages
    volume = item.get("volume", "")
    issue = item.get("issue", "")
    page = item.get("page", "")  # CrossRef format: "5-20" or "5"

    result = {
        "verified": True,
        "doi": doi,
        "title": title,
        "authors": [{"family": a.split(", ")[0], "given": a.split(", ")[1] if ", " in a else ""} for a in authors],
        "editors": [{"family": e.split(", ")[0], "given": e.split(", ")[1] if ", " in e else ""} for e in editors],
        "year": year,
        "container_title": container_title,
        "volume": volume,
        "issue": issue,
        "page": page,
        "publisher": item.get("publisher", ""),
        "type": item.get("type", ""),
        "suggested_bibtex_type": CROSSREF_TO_BIBTEX_TYPE.get(item.get("type", ""), "misc"),
        "method": method,
        "url": f"https://doi.org/{doi}" if doi else None,
    }

    if score is not None:
        result["score"] = score

    return result


def verify_by_doi(doi: str, limiter, backoff: ExponentialBackoff, mailto: str, debug: bool = False) -> dict:
    """
    Verify paper by direct DOI lookup.

    Returns:
        Paper metadata dict on success, raises exception on failure
    """
    log_progress(f"Connecting to CrossRef API...")
    log_progress(f"Verifying DOI: {doi}")

    url = f"https://api.crossref.org/works/{doi}"
    params = {}
    if mailto:
        params["mailto"] = mailto

    for attempt in range(backoff.max_attempts):
        limiter.wait()

        if debug:
            print(f"DEBUG: GET {url}", file=sys.stderr)

        try:
            response = requests.get(url, params=params, timeout=30)
            limiter.record()

            if debug:
                print(f"DEBUG: Response status: {response.status_code}", file=sys.stderr)

            if response.status_code == 200:
                data = response.json()
                result = format_result(data.get("message", {}), "doi_lookup")
                log_progress(f"DOI verified: {result.get('title', '')[:50]}...")
                return result

            elif response.status_code == 404:
                raise LookupError(f"DOI {doi} not found in CrossRef")

            elif response.status_code == 429:
                log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded after max retries")
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue

            else:
                raise RuntimeError(f"CrossRef API error: {response.status_code}")

        except requests.exceptions.RequestException as e:
            log_progress(f"Network error: {str(e)[:100]}, retrying (attempt {attempt+1}/{backoff.max_attempts})...")
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Max retries exceeded")


def search_by_metadata(
    title: str,
    author: Optional[str],
    year: Optional[int],
    limiter,
    backoff: ExponentialBackoff,
    mailto: str,
    debug: bool = False
) -> dict:
    """
    Search for paper by title, author, and year.

    Returns:
        Paper metadata dict on success, raises LookupError if not found
    """
    # Build search description
    search_desc = f"title='{title[:50]}...'"
    if author:
        search_desc += f" author={author}"
    if year:
        search_desc += f" year={year}"

    log_progress(f"Connecting to CrossRef API...")
    log_progress(f"Searching CrossRef: {search_desc}")

    url = "https://api.crossref.org/works"

    params = {
        "query.bibliographic": title,
        "rows": 5,
        "sort": "score",
        "order": "desc",
        "select": "DOI,title,author,editor,published,container-title,volume,issue,page,publisher,type,score",
    }

    if author:
        params["query.author"] = author

    if year:
        params["filter"] = f"from-pub-date:{year-1},until-pub-date:{year+1}"

    if mailto:
        params["mailto"] = mailto

    for attempt in range(backoff.max_attempts):
        limiter.wait()

        if debug:
            print(f"DEBUG: GET {url} with params: {params}", file=sys.stderr)

        try:
            response = requests.get(url, params=params, timeout=30)
            limiter.record()

            if debug:
                print(f"DEBUG: Response status: {response.status_code}", file=sys.stderr)

            if response.status_code == 200:
                data = response.json()
                items = data.get("message", {}).get("items", [])

                if not items:
                    raise LookupError("No matching papers found")

                # Check top result
                top = items[0]
                score = top.get("score", 0)

                if debug:
                    print(f"DEBUG: Top result score: {score}", file=sys.stderr)
                    print(f"DEBUG: Top result title: {top.get('title', [''])[0]}", file=sys.stderr)

                # Use score threshold for matching
                # CrossRef scores vary widely; lower threshold with author/year verification
                # A score of 30+ with matching author is usually reliable
                min_score = 30 if author else 50
                if score < min_score:
                    raise LookupError(f"Best match score ({score:.1f}) below threshold ({min_score})")

                # Verify author if provided
                if author:
                    result_authors = [a.get("family", "").lower() for a in top.get("author", [])]
                    author_lower = author.lower()
                    if not any(author_lower in a for a in result_authors):
                        # Check if any author name contains our search term
                        all_author_text = " ".join(
                            f"{a.get('given', '')} {a.get('family', '')}".lower()
                            for a in top.get("author", [])
                        )
                        if author_lower not in all_author_text:
                            raise LookupError(f"Author '{author}' not found in result authors")

                # Verify year if provided
                if year:
                    result_year = None
                    for date_field in ["published", "published-print", "published-online"]:
                        if date_field in top and "date-parts" in top[date_field]:
                            parts = top[date_field]["date-parts"]
                            if parts and parts[0] and parts[0][0]:
                                result_year = parts[0][0]
                                break

                    if result_year and abs(result_year - year) > 1:
                        raise LookupError(f"Year mismatch: expected {year}, got {result_year}")

                result = format_result(top, "bibliographic_search", score)
                log_progress(f"Paper found: {result.get('title', '')[:50]}... (score: {score:.1f})")
                return result

            elif response.status_code == 429:
                log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded after max retries")
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue

            else:
                raise RuntimeError(f"CrossRef API error: {response.status_code}")

        except requests.exceptions.RequestException as e:
            log_progress(f"Network error: {str(e)[:100]}, retrying (attempt {attempt+1}/{backoff.max_attempts})...")
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Max retries exceeded")


def main():
    parser = argparse.ArgumentParser(
        description="Verify paper existence and metadata via CrossRef"
    )
    parser.add_argument(
        "--doi",
        help="DOI to verify directly"
    )
    parser.add_argument(
        "--title",
        help="Paper title to search for"
    )
    parser.add_argument(
        "--author",
        help="Author family name (improves matching)"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Publication year (filters results +/-1 year)"
    )
    parser.add_argument(
        "--verify-metadata",
        action="store_true",
        help="When using --doi, also verify title/author match"
    )
    parser.add_argument(
        "--mailto",
        default=os.environ.get("CROSSREF_MAILTO", ""),
        help="Email for CrossRef polite pool (default: CROSSREF_MAILTO env var)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information"
    )

    args = parser.parse_args()

    # Build query dict for output
    query = {}
    if args.doi:
        query["doi"] = args.doi
    if args.title:
        query["title"] = args.title
    if args.author:
        query["author"] = args.author
    if args.year:
        query["year"] = args.year

    # Validate arguments
    if not args.doi and not args.title:
        output_error(query, "config_error", "Must provide either --doi or --title", exit_code=2)

    if not args.mailto:
        if args.debug:
            print("DEBUG: CROSSREF_MAILTO not set, using public pool", file=sys.stderr)

    # Initialize rate limiter and backoff
    limiter = get_limiter("crossref")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        if args.doi:
            # Direct DOI lookup
            doi = normalize_doi(args.doi)
            result = verify_by_doi(doi, limiter, backoff, args.mailto, args.debug)

            # Optionally verify metadata matches
            if args.verify_metadata and args.title:
                result_title = result.get("title", "").lower()
                search_title = args.title.lower()
                # Check for significant word overlap
                search_words = set(w for w in search_title.split() if len(w) > 3)
                result_words = set(w for w in result_title.split() if len(w) > 3)
                overlap = len(search_words & result_words) / max(len(search_words), 1)
                if overlap < 0.5:
                    output_not_found(query, f"DOI found but title mismatch (overlap: {overlap:.0%})")

            output_success(query, result)

        else:
            # Search by metadata
            result = search_by_metadata(
                args.title,
                args.author,
                args.year,
                limiter,
                backoff,
                args.mailto,
                args.debug
            )
            output_success(query, result)

    except LookupError as e:
        output_not_found(query, str(e))

    except RuntimeError as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            output_error(query, "rate_limit", error_msg, exit_code=3)
        else:
            output_error(query, "api_error", error_msg, exit_code=3)


if __name__ == "__main__":
    main()
