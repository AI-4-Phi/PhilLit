#!/usr/bin/env python3
"""
Resolve paper abstracts from multiple sources.

This script attempts to find a paper's actual abstract using a fallback chain:
1. Semantic Scholar (if S2 ID provided)
2. OpenAlex (if DOI provided)
3. CORE API (by DOI or title+author)

Usage:
    # By DOI (tries OpenAlex first, then CORE)
    python get_abstract.py --doi "10.1111/nous.12191"

    # By S2 ID (tries Semantic Scholar first)
    python get_abstract.py --s2-id "abc123def"

    # By title and author (uses CORE)
    python get_abstract.py --title "Freedom of the Will" --author "Frankfurt" --year 1971

Output:
    JSON object with abstract and source attribution:
    {
        "status": "success|not_found",
        "abstract": "...",
        "abstract_source": "s2|openalex|core",
        "query": {"doi": "...", ...}
    }

Exit Codes:
    0: Success (abstract found) or not_found (no abstract available)
    2: Configuration error
    3: API error
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import ExponentialBackoff, get_limiter

SOURCE = "get_abstract"


def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    print(f"[get_abstract.py] {message}", file=sys.stderr, flush=True)


def output_result(status: str, query: dict, abstract: Optional[str] = None,
                  abstract_source: Optional[str] = None) -> None:
    """Output result and exit."""
    result = {
        "status": status,
        "query": query,
        "abstract": abstract,
        "abstract_source": abstract_source,
    }
    print(json.dumps(result, indent=2))
    sys.exit(0)


def output_error(query: dict, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    print(json.dumps({
        "status": "error",
        "query": query,
        "abstract": None,
        "abstract_source": None,
        "error": {"type": error_type, "message": message}
    }, indent=2))
    sys.exit(exit_code)


# =============================================================================
# Source 1: Semantic Scholar
# =============================================================================

def get_abstract_from_s2(
    s2_id: str,
    api_key: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> Optional[str]:
    """Try to get abstract from Semantic Scholar by paper ID."""
    log_progress(f"Trying Semantic Scholar: {s2_id}")

    url = f"https://api.semanticscholar.org/graph/v1/paper/{s2_id}"
    params = {"fields": "abstract"}

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
                data = response.json()
                abstract = data.get("abstract")
                if abstract:
                    log_progress(f"Found abstract from S2 ({len(abstract)} chars)")
                    return abstract
                log_progress("S2: Paper found but no abstract")
                return None

            elif response.status_code == 404:
                log_progress("S2: Paper not found")
                return None

            elif response.status_code == 429:
                if not backoff.wait(attempt):
                    log_progress("S2: Rate limit exceeded, giving up")
                    return None
                continue

            else:
                log_progress(f"S2: API error {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            log_progress(f"S2: Network error: {e}")
            return None

    return None


# =============================================================================
# Source 2: OpenAlex
# =============================================================================

def reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return None

    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words.sort(key=lambda x: x[0])
    return " ".join(word for _, word in words)


def get_abstract_from_openalex(
    doi: str,
    email: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> Optional[str]:
    """Try to get abstract from OpenAlex by DOI."""
    log_progress(f"Trying OpenAlex: {doi}")

    # Clean DOI
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]

    url = f"https://api.openalex.org/works/doi:{doi}"
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
                data = response.json()
                inverted_index = data.get("abstract_inverted_index")
                if inverted_index:
                    abstract = reconstruct_abstract(inverted_index)
                    if abstract:
                        log_progress(f"Found abstract from OpenAlex ({len(abstract)} chars)")
                        return abstract
                log_progress("OpenAlex: Paper found but no abstract")
                return None

            elif response.status_code == 404:
                log_progress("OpenAlex: Paper not found")
                return None

            elif response.status_code == 429:
                if not backoff.wait(attempt):
                    log_progress("OpenAlex: Rate limit exceeded, giving up")
                    return None
                continue

            else:
                log_progress(f"OpenAlex: API error {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            log_progress(f"OpenAlex: Network error: {e}")
            return None

    return None


# =============================================================================
# Source 3: CORE
# =============================================================================

def get_abstract_from_core(
    doi: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[int] = None,
    api_key: Optional[str] = None,
    limiter=None,
    backoff: ExponentialBackoff = None,
    debug: bool = False
) -> Optional[str]:
    """Try to get abstract from CORE by DOI or title+author."""
    if doi:
        log_progress(f"Trying CORE: DOI {doi}")
        # Clean DOI
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        query = f'doi:"{doi}"'
    elif title:
        log_progress(f"Trying CORE: title '{title}'")
        query_parts = [f'title:"{title}"']
        if author:
            query_parts.append(f'authors:"{author}"')
        query = " AND ".join(query_parts)
    else:
        return None

    url = "https://api.core.ac.uk/v3/search/works"
    params = {"q": query, "limit": 5}

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for attempt in range(backoff.max_attempts):
        limiter.wait()

        if debug:
            print(f"DEBUG: GET {url} q={query}", file=sys.stderr)

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            limiter.record()

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                for work in results:
                    abstract = work.get("abstract")
                    if abstract and len(abstract) > 50:  # Filter out very short "abstracts"
                        # If searching by title, verify it's a reasonable match
                        if title:
                            work_title = work.get("title", "").lower()
                            search_title = title.lower()
                            # Basic title matching
                            if search_title[:30] in work_title or work_title[:30] in search_title:
                                log_progress(f"Found abstract from CORE ({len(abstract)} chars)")
                                return abstract
                        else:
                            log_progress(f"Found abstract from CORE ({len(abstract)} chars)")
                            return abstract

                log_progress("CORE: No abstract found")
                return None

            elif response.status_code == 429:
                if not backoff.wait(attempt):
                    log_progress("CORE: Rate limit exceeded, giving up")
                    return None
                continue

            else:
                log_progress(f"CORE: API error {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            log_progress(f"CORE: Network error: {e}")
            return None

    return None


# =============================================================================
# Main Resolution Logic
# =============================================================================

def resolve_abstract(
    doi: Optional[str] = None,
    s2_id: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[int] = None,
    s2_api_key: Optional[str] = None,
    openalex_email: Optional[str] = None,
    core_api_key: Optional[str] = None,
    debug: bool = False
) -> tuple[Optional[str], Optional[str]]:
    """
    Try to resolve abstract from multiple sources.

    Returns:
        Tuple of (abstract, source) where source is "s2", "openalex", or "core"
        Returns (None, None) if no abstract found
    """
    # Get rate limiters
    s2_limiter = get_limiter("semantic_scholar")
    openalex_limiter = get_limiter("openalex")
    core_limiter = get_limiter("core")

    backoff = ExponentialBackoff(max_attempts=3, base_delay=1.0)

    # Source 1: Semantic Scholar (if S2 ID provided)
    if s2_id:
        abstract = get_abstract_from_s2(s2_id, s2_api_key, s2_limiter, backoff, debug)
        if abstract:
            return abstract, "s2"

    # Source 2: OpenAlex (if DOI provided)
    if doi:
        abstract = get_abstract_from_openalex(doi, openalex_email, openalex_limiter, backoff, debug)
        if abstract:
            return abstract, "openalex"

    # Source 3: CORE (by DOI or title+author)
    abstract = get_abstract_from_core(
        doi=doi, title=title, author=author, year=year,
        api_key=core_api_key, limiter=core_limiter, backoff=backoff, debug=debug
    )
    if abstract:
        return abstract, "core"

    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Resolve paper abstract from multiple sources"
    )
    parser.add_argument(
        "--doi",
        help="Paper DOI"
    )
    parser.add_argument(
        "--s2-id",
        help="Semantic Scholar paper ID"
    )
    parser.add_argument(
        "--title",
        help="Paper title (for CORE search)"
    )
    parser.add_argument(
        "--author",
        help="Author name (use with --title)"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Publication year (use with --title)"
    )
    parser.add_argument(
        "--s2-api-key",
        default=os.environ.get("S2_API_KEY", ""),
        help="Semantic Scholar API key"
    )
    parser.add_argument(
        "--openalex-email",
        default=os.environ.get("OPENALEX_EMAIL", ""),
        help="Email for OpenAlex polite pool"
    )
    parser.add_argument(
        "--core-api-key",
        default=os.environ.get("CORE_API_KEY", ""),
        help="CORE API key (optional)"
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
    if args.s2_id:
        query["s2_id"] = args.s2_id
    if args.title:
        query["title"] = args.title
    if args.author:
        query["author"] = args.author
    if args.year:
        query["year"] = args.year

    # Validate: need at least one identifier
    if not args.doi and not args.s2_id and not args.title:
        output_error(
            query,
            "config_error",
            "Must provide --doi, --s2-id, or --title",
            exit_code=2
        )

    try:
        abstract, source = resolve_abstract(
            doi=args.doi,
            s2_id=args.s2_id,
            title=args.title,
            author=args.author,
            year=args.year,
            s2_api_key=args.s2_api_key,
            openalex_email=args.openalex_email,
            core_api_key=args.core_api_key,
            debug=args.debug
        )

        if abstract:
            output_result("success", query, abstract, source)
        else:
            log_progress("No abstract found from any source")
            output_result("not_found", query)

    except Exception as e:
        output_error(query, "api_error", str(e), exit_code=3)


if __name__ == "__main__":
    main()
