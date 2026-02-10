#!/usr/bin/env python3
"""
Fetch an NDPR review page and extract opening paragraphs.

NDPR book reviews typically open with paragraphs describing the book's content
and arguments. This script extracts the first MAX_PARAGRAPHS substantive
paragraphs for use as abstract substitutes for @book entries.

The extracted text may include some reviewer evaluation alongside description —
NDPR reviews for single-authored books typically transition to sustained
critical evaluation after 8-10 paragraphs, but some interleave evaluation
earlier. This is acceptable: the primary purpose is to provide rich content
about a book that would otherwise have no abstract at all.

Usage:
    python fetch_ndpr.py --url "https://ndpr.nd.edu/reviews/being-and-time/"
    python fetch_ndpr.py --slug "being-and-time"

Exit Codes: 0=success, 1=not found, 2=config error, 3=network error
"""

import argparse
import os
import re
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output import log_progress as _log_progress, output_success, output_error
from rate_limiter import ExponentialBackoff, get_limiter

SCRIPT_NAME = "fetch_ndpr.py"
NDPR_BASE = "https://ndpr.nd.edu/reviews"

# Maximum number of opening paragraphs to extract. Empirical testing across
# 10 random NDPR reviews of single-authored books shows that the descriptive
# portion typically runs 8-17 paragraphs (median ~9, range 787-1654 words at
# 8 paragraphs). 8 paragraphs captures the full descriptive portion for
# shorter reviews and provides a substantial excerpt for longer ones.
MAX_PARAGRAPHS = 8


def log_progress(message: str) -> None:
    _log_progress(SCRIPT_NAME, message)


def extract_review_content(html: str) -> dict:
    """Extract opening paragraphs and metadata from an NDPR review page.

    Extracts up to MAX_PARAGRAPHS substantive paragraphs from the review body.
    Skips short paragraphs (<50 chars) and citation/reference lines.

    Returns dict with:
        - summary_text: Joined opening paragraphs
        - paragraph_count: Number of paragraphs extracted
        - paragraphs: List of individual paragraph texts
        - reviewer: Reviewer name if found
        - review_date: Review date if found
    """
    soup = BeautifulSoup(html, "lxml")

    # Extract reviewer and date from metadata
    reviewer = None
    review_date = None

    # Try meta tags
    author_meta = soup.find("meta", {"name": "author"})
    if author_meta:
        reviewer = author_meta.get("content")

    # Try common NDPR page structure for reviewer
    if not reviewer:
        # Look for reviewer name in byline patterns
        byline = soup.find("p", class_=re.compile(r"byline|author|reviewer", re.I))
        if byline:
            reviewer = byline.get_text(strip=True)

    # Try to find date
    date_meta = soup.find("meta", {"property": "article:published_time"})
    if date_meta:
        review_date = date_meta.get("content", "")[:10]  # YYYY-MM-DD
    if not review_date:
        time_elem = soup.find("time")
        if time_elem:
            review_date = time_elem.get("datetime", time_elem.get_text(strip=True))

    # Extract review body paragraphs
    # NDPR uses various content structures; try common patterns
    content_div = (
        soup.find("div", class_=re.compile(r"entry-content|review-content|post-content|article-content", re.I))
        or soup.find("article")
        or soup.find("div", class_="content")
        or soup.find("main")
    )

    if not content_div:
        return {
            "summary_text": "",
            "paragraph_count": 0,
            "paragraphs": [],
            "reviewer": reviewer,
            "review_date": review_date,
        }

    # Get all <p> tags from the content area
    all_paragraphs = content_div.find_all("p")

    # Filter to substantive paragraphs (skip very short ones, metadata-like lines)
    substantive = []
    for p in all_paragraphs:
        text = p.get_text(strip=True)
        # Skip very short paragraphs (likely metadata, captions, etc.)
        if len(text) < 50:
            continue
        # Skip paragraphs that look like citations or references
        # "[..." always skipped (reference indicators); "(..." only if also ends with ")"
        if text.startswith("[") or (text.startswith("(") and text.endswith(")")):
            continue
        substantive.append(text)

    # Take the first MAX_PARAGRAPHS substantive paragraphs
    summary_paragraphs = substantive[:MAX_PARAGRAPHS]
    summary_text = "\n\n".join(summary_paragraphs)

    return {
        "summary_text": summary_text,
        "paragraph_count": len(summary_paragraphs),
        "paragraphs": summary_paragraphs,
        "reviewer": reviewer,
        "review_date": review_date,
    }


def fetch_ndpr_review(
    url: str,
    limiter=None,
    backoff: Optional[ExponentialBackoff] = None,
    debug: bool = False,
) -> dict:
    """Fetch an NDPR review page and extract opening content.

    Args:
        url: Full URL to the NDPR review page
        limiter: Rate limiter instance (created if None)
        backoff: Backoff instance (created if None)
        debug: Enable debug output

    Returns:
        Dict with summary_text, paragraph_count, review_url, reviewer, review_date
    """
    if limiter is None:
        limiter = get_limiter("ndpr")
    if backoff is None:
        backoff = ExponentialBackoff(max_attempts=3)

    log_progress(f"Fetching NDPR review: {url}")

    for attempt in range(backoff.max_attempts):
        limiter.wait()
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "PhiloResearchBot/1.0"},
            )
            limiter.record()

            if response.status_code == 404:
                raise LookupError(f"NDPR review not found: {url}")
            elif response.status_code == 429:
                log_progress(f"Rate limited, backing off (attempt {attempt + 1})...")
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded after max retries")
                continue
            elif response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}")

            result = extract_review_content(response.text)
            result["review_url"] = url

            if result["summary_text"]:
                log_progress(
                    f"Extracted {result['paragraph_count']} paragraphs "
                    f"({len(result['summary_text'])} chars)"
                )
            else:
                log_progress("No paragraphs extracted")

            return result

        except requests.exceptions.RequestException as e:
            log_progress(f"Network error: {str(e)[:100]}, retrying...")
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Max retries exceeded")


def main():
    parser = argparse.ArgumentParser(description="Fetch NDPR review and extract summary")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Full NDPR review URL")
    group.add_argument("--slug", help="Review slug (e.g., 'being-and-time')")
    parser.add_argument("--debug", action="store_true", help="Print debug info")

    args = parser.parse_args()

    url = args.url if args.url else f"{NDPR_BASE}/{args.slug}/"
    query = args.url or args.slug

    limiter = get_limiter("ndpr")
    backoff = ExponentialBackoff(max_attempts=3)

    try:
        result = fetch_ndpr_review(url, limiter, backoff, args.debug)
        # Remove paragraphs list from CLI output (verbose)
        result.pop("paragraphs", None)
        output_success(source="ndpr", query=query, results=[result])

    except LookupError as e:
        output_error("ndpr", query, "not_found", str(e), 1)
    except RuntimeError as e:
        output_error("ndpr", query, "network_error", str(e), 3)
    except Exception as e:
        output_error("ndpr", query, "parse_error", str(e), 3)


if __name__ == "__main__":
    main()
