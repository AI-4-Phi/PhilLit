#!/usr/bin/env python3
"""
Resolve paper abstracts from multiple sources.

This script attempts to find a paper's actual abstract using a fallback chain:
1. Semantic Scholar (by S2 ID, or by DOI via DOI:{doi} endpoint)
2. OpenAlex (if DOI provided)
3. CORE API (by DOI or title+author)

Usage:
    # By DOI (tries S2 first via DOI:{doi}, then OpenAlex, then CORE)
    python get_abstract.py --doi "10.1111/nous.12191"

    # By S2 ID (tries Semantic Scholar first by ID)
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
from dotenv import find_dotenv, load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import (
    ExponentialBackoff,
    get_limiter,
    openalex_budget_exhausted,
    openalex_params,
    parse_retry_after,
)
# Abstracts are the field most likely to carry non-ASCII and the field agents
# most often copy as text -- so this emitter goes through the shared unescaped
# dumper too. output.dumps owns the ensure_ascii decision; see its docstring.
import output

SOURCE = "get_abstract"

# Probe status vocabulary. A source that ANSWERED and has no abstract for
# this identity is PROBE_EMPTY; a source we never got an answer out of is
# PROBE_TRANSPORT. The text-or-None public functions below cannot express
# that difference, which is why corroboration reads the probes instead:
# "no abstract here" is evidence about the work, "the request failed" is
# evidence about the network.
PROBE_OK = "ok"
PROBE_EMPTY = "empty"
PROBE_TRANSPORT = "transport"


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
    print(output.dumps(result))
    sys.exit(0)


def output_error(query: dict, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    print(output.dumps({
        "status": "error",
        "query": query,
        "abstract": None,
        "abstract_source": None,
        "error": {"type": error_type, "message": message}
    }))
    sys.exit(exit_code)


# =============================================================================
# Source 1: Semantic Scholar
# =============================================================================

def get_abstract_from_s2(
    s2_id: Optional[str] = None,
    api_key: Optional[str] = None,
    limiter=None,
    backoff: ExponentialBackoff = None,
    debug: bool = False,
    doi: Optional[str] = None
) -> Optional[str]:
    """Try to get abstract from Semantic Scholar by paper ID or DOI.

    When s2_id is provided, uses it directly. Otherwise falls back to DOI:{doi}.

    The text-or-None view of probe_s2 -- every request, retry and log line
    lives there, so the two can never drift.
    """
    status, abstract = probe_s2(
        s2_id=s2_id, api_key=api_key, limiter=limiter,
        backoff=backoff, debug=debug, doi=doi
    )
    return abstract if status == PROBE_OK else None


def probe_s2(
    s2_id: Optional[str] = None,
    api_key: Optional[str] = None,
    limiter=None,
    backoff: ExponentialBackoff = None,
    debug: bool = False,
    doi: Optional[str] = None
) -> tuple[str, Optional[str]]:
    """Semantic Scholar abstract lookup, reporting WHY there is no text.

    Returns (status, abstract): (PROBE_OK, text) when S2 served an
    abstract; (PROBE_EMPTY, None) when S2 answered and has none for this
    identity (200-without-abstract, 404, or no identifier to ask with);
    (PROBE_TRANSPORT, None) when we never got an answer -- HTTP error,
    timeout, connection failure, exhausted rate-limit retries, or a body
    that is not a JSON object.

    Malformation is classified at RESPONSE-SHAPE level only. A residual
    per-field type error (a JSON object with a field of the wrong type)
    still propagates, exactly as before this function existed;
    enrich_bibliography.corroborate_abstract wraps every probe call and
    classifies such an escape as transport.
    """
    if s2_id:
        identifier = s2_id
    elif doi:
        # Clean DOI prefix
        clean_doi = doi
        if clean_doi.startswith("https://doi.org/"):
            clean_doi = clean_doi[16:]
        elif clean_doi.startswith("http://doi.org/"):
            clean_doi = clean_doi[15:]
        identifier = f"DOI:{clean_doi}"
    else:
        return PROBE_EMPTY, None

    log_progress(f"Trying Semantic Scholar: {identifier}")

    url = f"https://api.semanticscholar.org/graph/v1/paper/{identifier}"
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
                if not isinstance(data, dict):
                    log_progress("S2: malformed response body (not a JSON object)")
                    return PROBE_TRANSPORT, None
                abstract = data.get("abstract")
                if abstract:
                    log_progress(f"Found abstract from S2 ({len(abstract)} chars)")
                    return PROBE_OK, abstract
                log_progress("S2: Paper found but no abstract")
                return PROBE_EMPTY, None

            elif response.status_code == 404:
                log_progress("S2: Paper not found")
                return PROBE_EMPTY, None

            elif response.status_code == 429:
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                if not backoff.wait(attempt, retry_after=retry_after):
                    log_progress("S2: Rate limit exceeded, giving up")
                    return PROBE_TRANSPORT, None
                continue

            else:
                log_progress(f"S2: API error {response.status_code}")
                return PROBE_TRANSPORT, None

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            log_progress(f"S2: Network error: {e}")
            return PROBE_TRANSPORT, None

    return PROBE_TRANSPORT, None


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
    """Try to get abstract from OpenAlex by DOI.

    The text-or-None view of probe_openalex; see it for the status
    vocabulary and for where the request behavior lives.
    """
    status, abstract = probe_openalex(doi, email, limiter, backoff, debug)
    return abstract if status == PROBE_OK else None


def probe_openalex(
    doi: str,
    email: Optional[str],
    limiter,
    backoff: ExponentialBackoff,
    debug: bool = False
) -> tuple[str, Optional[str]]:
    """OpenAlex abstract lookup, reporting WHY there is no text.

    Status vocabulary as in probe_s2. Daily-budget exhaustion is
    PROBE_TRANSPORT, not PROBE_EMPTY: a quota wall is a non-answer about
    the work, and reading it as "OpenAlex has no abstract" would let a
    quota outage look like evidence.
    """
    log_progress(f"Trying OpenAlex: {doi}")

    # Clean DOI
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]

    url = f"https://api.openalex.org/works/doi:{doi}"
    params = openalex_params(email)

    for attempt in range(backoff.max_attempts):
        limiter.wait()

        if debug:
            print(f"DEBUG: GET {url}", file=sys.stderr)

        try:
            response = requests.get(url, params=params, timeout=30)
            limiter.record()

            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, dict):
                    log_progress("OpenAlex: malformed response body (not a JSON object)")
                    return PROBE_TRANSPORT, None
                inverted_index = data.get("abstract_inverted_index")
                if inverted_index:
                    if not isinstance(inverted_index, dict):
                        log_progress("OpenAlex: malformed abstract_inverted_index")
                        return PROBE_TRANSPORT, None
                    abstract = reconstruct_abstract(inverted_index)
                    if abstract:
                        log_progress(f"Found abstract from OpenAlex ({len(abstract)} chars)")
                        return PROBE_OK, abstract
                log_progress("OpenAlex: Paper found but no abstract")
                return PROBE_EMPTY, None

            elif response.status_code == 404:
                log_progress("OpenAlex: Paper not found")
                return PROBE_EMPTY, None

            elif response.status_code == 429:
                if openalex_budget_exhausted(response):
                    # Budget exhaustion resets at midnight UTC, so every retry
                    # is dead time: ExponentialBackoff clamps Retry-After to
                    # max_delay (60 s) but still burns 4 of them per call.
                    log_progress(
                        "OpenAlex: daily budget exhausted (resets midnight UTC); "
                        "set OPENALEX_API_KEY for 10x headroom - skipping OpenAlex"
                    )
                    return PROBE_TRANSPORT, None
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                if not backoff.wait(attempt, retry_after=retry_after):
                    log_progress("OpenAlex: Rate limit exceeded, giving up")
                    return PROBE_TRANSPORT, None
                continue

            else:
                log_progress(f"OpenAlex: API error {response.status_code}")
                return PROBE_TRANSPORT, None

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            log_progress(f"OpenAlex: Network error: {e}")
            return PROBE_TRANSPORT, None

    return PROBE_TRANSPORT, None


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
    """Try to get abstract from CORE by DOI or title+author.

    The text-or-None view of probe_core; see it for the status vocabulary
    and for where the request behavior lives.
    """
    status, abstract = probe_core(
        doi=doi, title=title, author=author, year=year, api_key=api_key,
        limiter=limiter, backoff=backoff, debug=debug
    )
    return abstract if status == PROBE_OK else None


def probe_core(
    doi: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[int] = None,
    api_key: Optional[str] = None,
    limiter=None,
    backoff: ExponentialBackoff = None,
    debug: bool = False
) -> tuple[str, Optional[str]]:
    """CORE abstract lookup, reporting WHY there is no text.

    Status vocabulary as in probe_s2. PROBE_EMPTY covers "searched and
    nothing usable came back" -- including results whose abstract is too
    short or whose title does not match -- because that is CORE answering
    about this identity.
    """
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
        return PROBE_EMPTY, None

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
                if not isinstance(data, dict):
                    log_progress("CORE: malformed response body (not a JSON object)")
                    return PROBE_TRANSPORT, None
                results = data.get("results", [])
                if not isinstance(results, list):
                    log_progress("CORE: malformed results (not a list)")
                    return PROBE_TRANSPORT, None

                for work in results:
                    if not isinstance(work, dict):
                        log_progress("CORE: malformed result entry (not a JSON object)")
                        return PROBE_TRANSPORT, None
                    abstract = work.get("abstract")
                    if abstract and len(abstract) > 50:  # Filter out very short "abstracts"
                        # If searching by title, verify it's a reasonable match
                        if title:
                            work_title = work.get("title", "").lower()
                            search_title = title.lower()
                            # Basic title matching
                            if search_title[:30] in work_title or work_title[:30] in search_title:
                                log_progress(f"Found abstract from CORE ({len(abstract)} chars)")
                                return PROBE_OK, abstract
                        else:
                            log_progress(f"Found abstract from CORE ({len(abstract)} chars)")
                            return PROBE_OK, abstract

                log_progress("CORE: No abstract found")
                return PROBE_EMPTY, None

            elif response.status_code == 429:
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                if not backoff.wait(attempt, retry_after=retry_after):
                    log_progress("CORE: Rate limit exceeded, giving up")
                    return PROBE_TRANSPORT, None
                continue

            else:
                log_progress(f"CORE: API error {response.status_code}")
                return PROBE_TRANSPORT, None

        except requests.exceptions.RequestException as e:
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            log_progress(f"CORE: Network error: {e}")
            return PROBE_TRANSPORT, None

    return PROBE_TRANSPORT, None


# =============================================================================
# Main Resolution Logic
# =============================================================================

def build_source_context(s2_api_key: Optional[str] = None) -> dict:
    """Rate limiters and retry budgets for the three API sources.

    One owner of the tuning: resolve_abstract and
    enrich_bibliography.corroborate_abstract both build their clients
    here, so a change to a limiter or a retry budget cannot land on one
    path and silently miss the other.
    """
    # Fewer retries than main S2 scripts: abstract resolution has fallback sources
    if s2_api_key:
        s2_backoff = ExponentialBackoff(max_attempts=3, base_delay=1.0)
    else:
        s2_backoff = ExponentialBackoff(max_attempts=5, base_delay=2.0)
    return {
        # Auth-aware for S2
        "s2_limiter": get_limiter("semantic_scholar", authenticated=bool(s2_api_key)),
        "openalex_limiter": get_limiter("openalex"),
        "core_limiter": get_limiter("core"),
        "s2_backoff": s2_backoff,
        "other_backoff": ExponentialBackoff(max_attempts=3, base_delay=1.0),
    }


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
    ctx = build_source_context(s2_api_key)
    s2_limiter = ctx["s2_limiter"]
    openalex_limiter = ctx["openalex_limiter"]
    core_limiter = ctx["core_limiter"]
    s2_backoff = ctx["s2_backoff"]
    other_backoff = ctx["other_backoff"]

    # Source 1: Semantic Scholar (by S2 ID or DOI)
    if s2_id or doi:
        abstract = get_abstract_from_s2(
            s2_id=s2_id, api_key=s2_api_key, limiter=s2_limiter,
            backoff=s2_backoff, debug=debug, doi=doi
        )
        if abstract:
            return abstract, "s2"

    # Source 2: OpenAlex (if DOI provided)
    if doi:
        abstract = get_abstract_from_openalex(doi, openalex_email, openalex_limiter, other_backoff, debug)
        if abstract:
            return abstract, "openalex"

    # Source 3: CORE (by DOI or title+author) — only when a CORE key was
    # resolved (from the environment OR an explicit --core-api-key). Without a
    # key the unauthenticated tier only rate-limits, so skip rather than burn
    # futile "Trying CORE" attempts (item 13 D3). Gate on the resolved param,
    # not os.environ, so an explicit key with CORE_API_KEY unset in the
    # environment still works (mirrors search_core.py, which gates on
    # args.api_key).
    if core_api_key:
        abstract = get_abstract_from_core(
            doi=doi, title=title, author=author, year=year,
            api_key=core_api_key, limiter=core_limiter, backoff=other_backoff, debug=debug
        )
        if abstract:
            return abstract, "core"
    elif debug:
        log_progress("Skipping CORE (no CORE_API_KEY configured)")

    return None, None


def main():
    load_dotenv(find_dotenv(usecwd=True), override=True)  # must run before argparse defaults read os.environ
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
