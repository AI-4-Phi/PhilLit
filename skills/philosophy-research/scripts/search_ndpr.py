#!/usr/bin/env python3
"""
Search Notre Dame Philosophical Reviews (NDPR) for book reviews.

Uses NDPR's sitemap to find review URLs, then matches by normalized title similarity.
A slug match is only a candidate: a later book whose slug holds every title word
scores as high as the book itself. `review_matches` decides identity from the
fetched page's bibliographic header; check it before using a review's text.
NDPR publishes scholarly book reviews that typically open with summary paragraphs —
useful as abstract substitutes for books missing abstracts from standard APIs.

Usage:
    python search_ndpr.py --title "Being and Time" --author "Heidegger"
    python search_ndpr.py --title "Reasons and Persons"

Exit Codes: 0=success (match or not_found), 2=config error, 3=network error
"""

import argparse

from dotenv import find_dotenv, load_dotenv
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# hooks/ for bib_identity (single source of truth for title and name folds)
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "hooks"))
from bib_identity import ascii_variants, title_key  # noqa: E402
from output import log_progress as _log_progress, output_success, output_error, set_output_path, add_output_arg
from rate_limiter import ExponentialBackoff, get_limiter, user_agent

SCRIPT_NAME = "search_ndpr.py"
SITEMAP_URL = "https://ndpr.nd.edu/sitemap.xml"

# Module-level sitemap cache for batch use within a single process
_sitemap_cache: Optional[list[str]] = None

# Accepted candidates the resolver may fetch, best first. Each costs one
# review fetch at 1 req/s, and the barrier's corroboration pass is budgeted.
MAX_CANDIDATES = 3

# Pure function words: dropped from title/slug tokens so coincidental overlap
# on "and"/"the"/"for" can't inflate the match score. Content-
# bearing short words philosophy titles use (why, what, not, how, new) stay.
STOPWORDS = frozenset({
    "and", "the", "for", "with", "from", "that", "this", "its",
    "are", "was", "has", "have", "but", "all", "can", "one",
    "two", "own", "out", "who",
})


def log_progress(message: str) -> None:
    _log_progress(SCRIPT_NAME, message)


def normalize_title(title: str) -> str:
    """Normalize a book title to a comparable slug form.

    Strips subtitles (after colon), lowercases, removes non-alphanumeric,
    and collapses whitespace.
    """
    # Strip subtitle (after first colon)
    title = title.split(":")[0].strip()
    # Lowercase
    title = title.lower()
    # Remove non-alphanumeric (keep spaces)
    title = re.sub(r"[^a-z0-9\s]", "", title)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def slug_from_url(url: str) -> str:
    """Extract the slug portion from an NDPR review URL.

    Example: https://ndpr.nd.edu/reviews/being-and-time/ -> being-and-time
    """
    # Extract path after /reviews/
    match = re.search(r"/reviews/([^/]+)/?", url)
    if match:
        return match.group(1)
    return ""


def title_to_tokens(title: str) -> set[str]:
    """Meaningful tokens: len >= 3, excluding pure function words (STOPWORDS)."""
    return {t for t in title.split() if len(t) >= 3 and t not in STOPWORDS}


def score_match(
    normalized_title: str, slug: str, author: Optional[str] = None
) -> tuple[float, bool]:
    """Score how well a sitemap slug matches a normalized book title.

    Returns (score, author_confirmed). Score is 0.0-1.0 (one-directional title
    coverage + author bonus). author_confirmed is True when the author surname
    substring appears in the slug. Single-token titles require author
    confirmation (else (0.0, False)).
    """
    slug_text = slug.replace("-", " ")

    title_tokens = title_to_tokens(normalized_title)
    slug_tokens = title_to_tokens(slug_text)

    if not title_tokens or not slug_tokens:
        return 0.0, False

    overlap = title_tokens & slug_tokens
    if not overlap:
        return 0.0, False

    # Coverage: fraction of the title's tokens present in the slug.
    title_coverage = len(overlap) / len(title_tokens)

    author_bonus = 0.0
    author_confirmed = False
    if author and author.lower() in slug_text:
        author_bonus = 0.15
        author_confirmed = True

    # Single-token titles are too ambiguous for coverage alone.
    if len(title_tokens) < 2:
        if not author_confirmed:
            return 0.0, False
        return min(title_coverage * 0.5 + author_bonus, 1.0), author_confirmed

    score = min(title_coverage + author_bonus, 1.0)
    return score, author_confirmed


def fetch_sitemap(limiter, backoff: ExponentialBackoff) -> list[str]:
    """Fetch NDPR sitemap and extract all review URLs.

    Returns cached result if already fetched in this process.
    """
    global _sitemap_cache
    if _sitemap_cache is not None:
        return _sitemap_cache

    log_progress("Fetching NDPR sitemap...")

    for attempt in range(backoff.max_attempts):
        limiter.wait()
        try:
            response = requests.get(
                SITEMAP_URL,
                timeout=30,
                headers={"User-Agent": user_agent()},
            )
            limiter.record()

            if response.status_code == 429:
                log_progress(f"Rate limited, backing off (attempt {attempt + 1})...")
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded after max retries")
                continue
            elif response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code} fetching sitemap")

            # Parse XML sitemap
            root = ET.fromstring(response.text)
            # Handle XML namespace
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = []
            for url_elem in root.findall(".//sm:url/sm:loc", ns):
                url = url_elem.text
                if url and "/reviews/" in url:
                    urls.append(url)

            # Fallback: try without namespace (some sitemaps don't use it)
            if not urls:
                for url_elem in root.iter():
                    if url_elem.tag.endswith("loc") and url_elem.text:
                        url = url_elem.text
                        if "/reviews/" in url:
                            urls.append(url)

            if not urls:
                # Warn: could indicate sitemapindex format or site restructuring
                root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
                log_progress(
                    f"WARNING: Sitemap parsed but 0 review URLs found "
                    f"(root element: <{root_tag}>). "
                    f"NDPR may have switched to sitemapindex format."
                )
            else:
                log_progress(f"Found {len(urls)} review URLs in sitemap")
            # Only cache non-empty results to allow retry on transient failures
            if urls:
                _sitemap_cache = urls
            return urls

        except requests.exceptions.RequestException as e:
            log_progress(f"Network error: {str(e)[:100]}, retrying...")
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            raise RuntimeError(f"Network error fetching sitemap: {e}")

    raise RuntimeError("Max retries exceeded fetching sitemap")


def _slug_extra(full_title: str, slug: str) -> int:
    """Slug tokens the FULL title (subtitle kept) lacks: the tiebreak among
    equal scores. Coverage is one-directional, so a later book whose slug
    holds every title word scores 1.0 as well; the right slug has the fewest
    words of its own."""
    full = title_to_tokens(re.sub(r"[^a-z0-9\s]", " ", full_title.lower()))
    return len(title_to_tokens(slug.replace("-", " ")) - full)


def search_ndpr_candidates(
    title: str,
    author: Optional[str] = None,
    limiter=None,
    backoff: Optional[ExponentialBackoff] = None,
    debug: bool = False,
    limit: int = MAX_CANDIDATES,
) -> list[dict]:
    """Every sitemap review that passes the acceptance threshold, best first:
    score, then fewest extra slug words, then sitemap order. At most `limit`.

    A candidate is a slug match only. Whether the review is OF this book is
    `review_matches` on the fetched page's header.

    Returns:
        List of dicts with 'url', 'slug', 'score'
    """
    if limiter is None:
        limiter = get_limiter("ndpr")
    if backoff is None:
        backoff = ExponentialBackoff(max_attempts=3)

    urls = fetch_sitemap(limiter, backoff)
    if not urls:
        return []

    normalized = normalize_title(title)
    if debug:
        print(f"DEBUG: Normalized title: '{normalized}'", file=sys.stderr)

    ranked = []
    for order, url in enumerate(urls):
        slug = slug_from_url(url)
        if not slug:
            continue
        score, confirmed = score_match(normalized, slug, author)
        # Tiered acceptance: 0.75 outright, or 0.6 when the author is
        # confirmed in the slug. The stopword-inflated Wallace/Adam-Smith
        # pair (0.667, no author) rejects; descriptive-slug matches pass.
        if score >= 0.75 or (confirmed and score >= 0.6):
            ranked.append((-score, _slug_extra(title, slug), order,
                           {"url": url, "slug": slug, "score": score}))
    ranked.sort(key=lambda r: r[:3])
    found = [r[3] for r in ranked[:limit]]

    if debug:
        print(f"DEBUG: Candidates: {[c['slug'] for c in found]}", file=sys.stderr)
    return found


def search_ndpr(
    title: str,
    author: Optional[str] = None,
    limiter=None,
    backoff: Optional[ExponentialBackoff] = None,
    debug: bool = False,
) -> Optional[dict]:
    """The best `search_ndpr_candidates` match, or None.

    Returns:
        Dict with 'url', 'slug', 'score' if match found, else None
    """
    found = search_ndpr_candidates(title, author, limiter, backoff, debug, limit=1)
    return found[0] if found else None


def _main_title_tokens(title: str) -> set[str]:
    """Content words of a title before its first colon."""
    return title_to_tokens(title_key(title.split(":")[0]))


def _name_words(text: str) -> set[str]:
    """Word-bounded ASCII folds of a name or a name list."""
    return {" " + " ".join(re.sub(r"[^a-z0-9]", " ", v).split()) + " "
            for v in ascii_variants(text, contract=False)}


def review_matches(books: list[dict], title: str, surname: Optional[str]) -> bool:
    """Is this NDPR review OF the book? `books` is the page's bibliographic
    header (`fetch_ndpr.extract_review_content`), one dict per reviewed book.

    One header book must carry the surname as a whole word in its authors
    AND the same main-title content words (before the first colon, function
    words dropped) as `title`. Plain text in: decode BibTeX first. The year
    is not compared: NDPR reviews an edition, and 3 of the 6 right matches
    in the measured sample were dated one year off the bib."""
    if not surname or not title:
        return False
    want = _main_title_tokens(title)
    needles = {n for n in _name_words(surname) if n.strip()}
    if not want or not needles:
        return False
    for book in books:
        if _main_title_tokens(book.get("title") or "") != want:
            continue
        hay = _name_words(book.get("authors") or "")
        if any(n in h for n in needles for h in hay):
            return True
    return False


def clear_sitemap_cache() -> None:
    """Clear the module-level sitemap cache (useful for testing)."""
    global _sitemap_cache
    _sitemap_cache = None


def main():
    load_dotenv(find_dotenv(usecwd=True), override=True)  # before argparse defaults read os.environ
    parser = argparse.ArgumentParser(description="Search NDPR for book reviews")
    parser.add_argument("--title", required=True, help="Book title to search for")
    parser.add_argument("--author", help="Author last name (improves matching)")
    parser.add_argument("--debug", action="store_true", help="Print debug info")

    add_output_arg(parser)
    args = parser.parse_args()
    set_output_path(args.output)

    limiter = get_limiter("ndpr")
    backoff = ExponentialBackoff(max_attempts=3)

    try:
        result = search_ndpr(args.title, args.author, limiter, backoff, args.debug)

        if result:
            output_success(
                source="ndpr",
                query={"title": args.title, "author": args.author},
                results=[result],
            )
        else:
            output_success(
                source="ndpr",
                query={"title": args.title, "author": args.author},
                results=[],
                not_found=True,
            )

    except RuntimeError as e:
        output_error("ndpr", {"title": args.title, "author": args.author}, "network_error", str(e), 3)
    except Exception as e:
        output_error("ndpr", {"title": args.title, "author": args.author}, "parse_error", str(e), 3)


if __name__ == "__main__":
    main()
