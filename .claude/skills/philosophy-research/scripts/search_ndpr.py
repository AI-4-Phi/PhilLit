#!/usr/bin/env python3
"""
Search Notre Dame Philosophical Reviews (NDPR) for book reviews.

Uses NDPR's sitemap to find review URLs, then matches by normalized title similarity.
NDPR publishes scholarly book reviews that typically open with summary paragraphs —
useful as abstract substitutes for books missing abstracts from standard APIs.

Usage:
    python search_ndpr.py --title "Being and Time" --author "Heidegger"
    python search_ndpr.py --title "Reasons and Persons"

Exit Codes: 0=success (match or not_found), 2=config error, 3=network error
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output import log_progress as _log_progress, output_success, output_error
from rate_limiter import ExponentialBackoff, get_limiter

SCRIPT_NAME = "search_ndpr.py"
SITEMAP_URL = "https://ndpr.nd.edu/sitemap.xml"

# Module-level sitemap cache for batch use within a single process
_sitemap_cache: Optional[list[str]] = None


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
    """Convert normalized title to a set of meaningful tokens (len >= 3)."""
    return {t for t in title.split() if len(t) >= 3}


def score_match(normalized_title: str, slug: str, author: Optional[str] = None) -> float:
    """Score how well a sitemap slug matches a normalized book title.

    Returns a score between 0.0 and 1.0. Higher is better.
    Single-token titles (e.g., "On Liberty" → {"liberty"}) require author
    confirmation in the slug to avoid false positives.
    """
    # Convert slug to space-separated form for comparison
    slug_text = slug.replace("-", " ")

    title_tokens = title_to_tokens(normalized_title)
    slug_tokens = title_to_tokens(slug_text)

    if not title_tokens or not slug_tokens:
        return 0.0

    # Token overlap (Jaccard-like but weighted toward title coverage)
    overlap = title_tokens & slug_tokens
    if not overlap:
        return 0.0

    # Coverage: what fraction of the title's tokens appear in the slug
    title_coverage = len(overlap) / len(title_tokens)

    # Author bonus: if author's last name appears in slug
    author_bonus = 0.0
    if author:
        author_lower = author.lower()
        if author_lower in slug_text:
            author_bonus = 0.15

    # Single-token titles (e.g., "On Liberty" → {"liberty"}) are too ambiguous
    # for token coverage alone. Only allow if author confirms the match.
    if len(title_tokens) < 2:
        if not (author and author_bonus > 0):
            return 0.0
        # With author confirmed in slug, cap the score to require high threshold
        return min(title_coverage * 0.5 + author_bonus, 1.0)

    score = min(title_coverage + author_bonus, 1.0)
    return score


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
                headers={"User-Agent": "Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/AI-4-Phi/PhilLit)"},
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


def search_ndpr(
    title: str,
    author: Optional[str] = None,
    limiter=None,
    backoff: Optional[ExponentialBackoff] = None,
    debug: bool = False,
) -> Optional[dict]:
    """Search NDPR sitemap for a review matching the given book title.

    Args:
        title: Book title to search for
        author: Optional author last name for better matching
        limiter: Rate limiter instance (created if None)
        backoff: Backoff instance (created if None)
        debug: Enable debug output

    Returns:
        Dict with 'url', 'slug', 'score' if match found, else None
    """
    if limiter is None:
        limiter = get_limiter("ndpr")
    if backoff is None:
        backoff = ExponentialBackoff(max_attempts=3)

    urls = fetch_sitemap(limiter, backoff)
    if not urls:
        return None

    normalized = normalize_title(title)
    if debug:
        print(f"DEBUG: Normalized title: '{normalized}'", file=sys.stderr)

    best_score = 0.0
    best_url = None
    best_slug = None

    for url in urls:
        slug = slug_from_url(url)
        if not slug:
            continue
        score = score_match(normalized, slug, author)
        if score > best_score:
            best_score = score
            best_url = url
            best_slug = slug

    if debug:
        print(f"DEBUG: Best match: {best_slug} (score={best_score:.3f})", file=sys.stderr)

    # Threshold for accepting a match
    if best_score >= 0.6:
        return {"url": best_url, "slug": best_slug, "score": best_score}

    return None


def clear_sitemap_cache() -> None:
    """Clear the module-level sitemap cache (useful for testing)."""
    global _sitemap_cache
    _sitemap_cache = None


def main():
    parser = argparse.ArgumentParser(description="Search NDPR for book reviews")
    parser.add_argument("--title", required=True, help="Book title to search for")
    parser.add_argument("--author", help="Author last name (improves matching)")
    parser.add_argument("--debug", action="store_true", help="Print debug info")

    args = parser.parse_args()

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
