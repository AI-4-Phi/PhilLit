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
    4: --output file write failed (JSON still printed to stdout)
"""

import argparse
import json
import os
import sys
import tempfile
from typing import Any, Optional

import requests
from dotenv import find_dotenv, load_dotenv

# Add parent directory to path for rate_limiter import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import ExponentialBackoff, get_limiter
# output.dumps is the ONE owner of the ensure_ascii decision (and of the
# Windows stdout guard behind it) -- this script keeps its own emit path, but
# must not keep its own copy of that rule.
import output

# Add hooks directory to path for bib_identity import (single source of truth)
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "hooks"))

from bib_identity import normalize_doi  # noqa: E402,F401 - re-exported for callers


def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    print(f"[verify_paper.py] {message}", file=sys.stderr, flush=True)


# A1 (item 13): the script owns its output file so a researcher's shell
# redirection (`> f.json 2>&1`) can no longer merge stderr logs into the JSON.
# Set by main() from --output; None means stdout-only (upstream default).
_OUTPUT_PATH: Optional[str] = None


def write_output_file(payload: dict, path: str) -> bool:
    """Atomically write payload as pretty JSON to path (tmp + os.replace,
    encoding='utf-8'). Returns True on success, False on any failure (the
    caller then warns and exits 4)."""
    try:
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except Exception as e:
        print(f"[verify_paper.py] Failed to write --output file {path}: {e}",
              file=sys.stderr, flush=True)
        return False


def _emit(payload: dict, exit_code: int) -> None:
    """Print payload JSON to stdout (always, upstream-compatible), and if
    --output was given also write it atomically. A failed --output write is a
    hard error: the JSON is still on stdout, but the exit code becomes 4
    (output write failed) so the researcher retries with a good path."""
    print(output.dumps(payload))
    if _OUTPUT_PATH is not None and not write_output_file(payload, _OUTPUT_PATH):
        sys.exit(4)
    sys.exit(exit_code)


# Standard output helpers
def output_success(query: dict, result: dict) -> None:
    """Output successful verification result."""
    _emit({
        "status": "success",
        "source": "crossref",
        "query": query,
        "results": [result],
        "count": 1,
        "errors": []
    }, 0)


def output_not_found(query: dict, message: str) -> None:
    """Output when paper is not found."""
    _emit({
        "status": "error",
        "source": "crossref",
        "query": query,
        "results": [],
        "count": 0,
        "errors": [{"type": "not_found", "message": message, "recoverable": False}]
    }, 1)


def output_error(query: dict, error_type: str, message: str, exit_code: int = 2) -> None:
    """Output error result."""
    _emit({
        "status": "error",
        "source": "crossref",
        "query": query,
        "results": [],
        "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": error_type == "rate_limit"}]
    }, exit_code)


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
    "book-part": "incollection",
    "book-track": "incollection",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    # Reference works and multi-volume sets are the canonical, reprint-prone
    # class the cleaner's reprint-edition direction bound exists for -
    # falling to "misc" bypassed it.
    "reference-book": "book",
    "book-set": "book",
    "book-series": "book",
    "proceedings-article": "inproceedings",
    "dissertation": "phdthesis",
    "posted-content": "misc",       # preprints
    "report": "techreport",
    "reference-entry": "misc",
}


# Which CrossRef date field to believe, in order. `published-print` FIRST:
# CrossRef defines `published` as the EARLIEST of published-print and
# published-online, so for any online-first work `published` is the online
# date, not the citation year. Trying it first made every online-first article
# report the wrong year - and metadata_cleaner.py then "corrected" correct
# bibliographies to match. Measured over the 43 local corpora: 27 of 42 year
# rewrites replaced a year that exactly matched `published-print` with the
# `published-online` year (e.g. Mind 130(517): print 2021-06, online 2019-12).
# `created` is a registration timestamp, not a publication date; it is a last
# resort and is marked as such so consumers can refuse to act on it.
_YEAR_FIELDS = ["published-print", "published", "published-online", "created"]

# The bibliographic-search path's CrossRef `select` list, derived from
# _YEAR_FIELDS so extract_year's preference order can never desync from what
# is actually requested. The missing published-print request WAS that desync:
# the field was first in _YEAR_FIELDS but never asked for, so every
# search-verified record carried the online-first year. `created` is
# deliberately not requested here - it is a registration timestamp, a
# last-resort the search path has no business acting on.
_SEARCH_SELECT = ",".join(
    ["DOI", "title", "author", "editor", "container-title", "volume",
     "issue", "page", "publisher", "type", "score", "ISBN"]
    + [f for f in _YEAR_FIELDS if f != "created"])


def extract_year(item: dict) -> tuple[Optional[int], Optional[str]]:
    """Publication year of a CrossRef work, plus WHICH date field it came from.

    Returns (year, basis); (None, None) when the item carries no usable date.
    The basis travels with the record so a consumer can tell a version-of-record
    year from a bare registration timestamp instead of guessing.
    """
    for date_field in _YEAR_FIELDS:
        value = item.get(date_field)
        if isinstance(value, dict) and "date-parts" in value:
            parts = value["date-parts"]
            if parts and parts[0] and parts[0][0]:
                return parts[0][0], date_field
    return None, None


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

    # Extract year, and record which CrossRef date field supplied it
    year, year_basis = extract_year(item)

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
        # Provenance of `year`, so a consumer can require positive evidence
        # before OVERWRITING a bibliography's own year. See _YEAR_FIELDS.
        "year_basis": year_basis,
        "container_title": container_title,
        # Volume-vs-series split for multi-valued container-title lives in
        # disambiguate_container; "" until it positively identifies one.
        "series": "",
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


# CrossRef `container-title` is an ARRAY; for a book chapter it commonly
# holds both the series and the volume, in UNDOCUMENTED order -- [0] shipped
# a Springer series as a booktitle in production. The parent volume's own
# CrossRef record, found by ISBN filtered to book-like types, names the
# volume authoritatively; the remaining element is the series.
_MULTI_CONTAINER_TYPES = {"book-chapter", "proceedings-article"}
# `proceedings` is the parent type of a proceedings-article's volume record
# -- without it, that half of the stated scope would silently never
# disambiguate (deepseek review, 2026-08-26).
_BOOK_PARENT_TYPES = ("book", "edited-book", "monograph", "reference-book",
                      "proceedings")


def _norm_container(value: str) -> str:
    """Whitespace-collapsed casefold, the only normalization the parent-title
    match needs -- anything looser risks matching the wrong element."""
    return " ".join((value or "").split()).casefold()


def disambiguate_container(item: dict, result: dict, limiter,
                           mailto: str, debug: bool = False) -> None:
    """Split a multi-valued `container-title` into volume vs series, in place.

    Runs only for CrossRef types where two container titles mean
    series+volume (journal articles rarely carry two and are deliberately
    untouched). ONE extra CrossRef request per multi-container chapter,
    through the same limiter as the verification itself: both normalized
    ISBN forms in a single filter (same-key values are ORed), so print and
    electronic registrations land in one result set that is judged
    together -- sequential per-ISBN lookups could accept a second form's
    answer after the first form contradicted it.

    UNANIMITY gate, not a vote: every returned parent must name exactly one
    and the same container element. A parent naming neither (title drift or
    ISBN reuse), both, or a different element is contradictory exact-ISBN
    evidence and bails; agreeing duplicate registrations pass. A truncated
    page (total-results beyond the rows returned) also bails -- unseen
    records could dissent.

    `series` needs SEPARATE support: the parent record's own
    container-title names its series, and only when it corroborates the one
    remaining element (exactly-2 arrays) is `series` set -- leftover
    position alone proves nothing, so a 3+-element array fixes
    container_title only.

    Every failure path BAILS to the incumbent behavior (container_title =
    element [0], series empty): this is best-effort enrichment, not
    attestation -- doi/title/authors/year never depend on it. `[1]` is
    deliberately NOT the fallback: array order is undocumented, so without
    a parent match there is no authority either way.
    """
    if item.get("type") not in _MULTI_CONTAINER_TYPES:
        return
    # isinstance guards: external JSON can put a null, number or object
    # where a string array is expected, and a crash here would take down
    # the verification itself, violating the bail guarantee.
    containers = [c for c in (item.get("container-title") or [])
                  if isinstance(c, str) and c.strip()]
    if len(containers) < 2:
        return
    # CrossRef's isbn: filter matches its indexed UNHYPHENATED form; the
    # ISBN array on a record is not guaranteed unhyphenated, and a
    # hyphenated value would yield zero hits and a silent bail.
    isbns = ["".join(ch for ch in raw if ch.isdigit() or ch in "Xx")
             for raw in (item.get("ISBN") or []) if isinstance(raw, str)]
    isbns = [i for i in isbns if i][:2]
    if not isbns:
        return
    params = {
        "filter": ",".join([f"isbn:{i}" for i in isbns]
                           + [f"type:{t}" for t in _BOOK_PARENT_TYPES]),
        "rows": 10,
        "select": "title,type,container-title",
    }
    if mailto:
        params["mailto"] = mailto
    try:
        limiter.wait()
        response = requests.get("https://api.crossref.org/works",
                                params=params, timeout=30)
        limiter.record()
        if response.status_code != 200:
            return
        message = response.json().get("message") or {}
        parents = message.get("items") or []
        total = message.get("total-results", len(parents))
        if not parents or (isinstance(total, int) and total > len(parents)):
            return
        norm_containers = {_norm_container(c): c for c in containers}
        volume_keys = set()
        for p in parents:
            titles = {_norm_container(t) for t in (p.get("title") or [])
                      if isinstance(t, str)}
            matches = {k for k in norm_containers if k in titles}
            if len(matches) != 1:
                return
            volume_keys |= matches
        if len(volume_keys) != 1:
            return
        volume = norm_containers[next(iter(volume_keys))]
        result["container_title"] = volume
        remaining = [c for c in containers if c != volume]
        parent_series = {_norm_container(t)
                         for p in parents
                         for t in (p.get("container-title") or [])
                         if isinstance(t, str)}
        if (len(containers) == 2 and len(remaining) == 1
                and _norm_container(remaining[0]) in parent_series):
            result["series"] = remaining[0]
    except Exception as e:
        if debug:
            print(f"DEBUG: container disambiguation failed: {e}",
                  file=sys.stderr)
        return


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
                disambiguate_container(data.get("message", {}), result,
                                       limiter, mailto, debug)
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
        "select": _SEARCH_SELECT,
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

                # Verify year if provided. Accept a match against EITHER the
                # print year or the online-first year: the researcher cites one
                # of the two, and an online-first work can straddle the +/-1
                # window (Episteme 17(2): online 2018, print 2020), which used
                # to reject the correct paper outright.
                if year:
                    candidates = set()
                    for date_field in _YEAR_FIELDS[:-1]:  # not `created`
                        value = top.get(date_field)
                        if isinstance(value, dict) and "date-parts" in value:
                            parts = value["date-parts"]
                            if parts and parts[0] and parts[0][0]:
                                candidates.add(parts[0][0])

                    if candidates and all(abs(c - year) > 1 for c in candidates):
                        raise LookupError(
                            f"Year mismatch: expected {year}, got "
                            f"{'/'.join(str(c) for c in sorted(candidates))}")

                result = format_result(top, "bibliographic_search", score)
                disambiguate_container(top, result, limiter, mailto, debug)
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
    load_dotenv(find_dotenv(usecwd=True), override=True)  # must run before argparse defaults read os.environ
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
    parser.add_argument(
        "--output",
        help="Write the result JSON to this file atomically (stderr logs stay "
             "on stderr). Use this instead of shell redirection.",
    )

    args = parser.parse_args()

    global _OUTPUT_PATH
    _OUTPUT_PATH = args.output

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
