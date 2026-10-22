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

from dotenv import find_dotenv, load_dotenv
import os
import re
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup, NavigableString

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output import log_progress as _log_progress, output_success, output_error, set_output_path, add_output_arg
from rate_limiter import ExponentialBackoff, get_limiter, user_agent

SCRIPT_NAME = "fetch_ndpr.py"
NDPR_BASE = "https://ndpr.nd.edu/reviews"

# Maximum number of opening paragraphs to extract. Empirical testing across
# 10 random NDPR reviews of single-authored books shows that the descriptive
# portion typically runs 8-17 paragraphs (median ~9, range 787-1654 words at
# 8 paragraphs). 8 paragraphs captures the full descriptive portion for
# shorter reviews and provides a substantial excerpt for longer ones.
MAX_PARAGRAPHS = 8

# A bibliographic entry's year: what separates one reviewed book from the next.
_YEAR = re.compile(r"\b(1[5-9]|20)\d\d\b")


def log_progress(message: str) -> None:
    _log_progress(SCRIPT_NAME, message)


def extract_reviewed_books(soup: BeautifulSoup) -> list[dict]:
    """The books a review is OF, from its bibliographic header: the
    `.meta-item__bibliography` paragraphs, "Authors, <em>Title</em>,
    Publisher, Year, ..." (some pages use <i>). An italic run starts a new
    book only when it is the paragraph's first or the text since the
    previous one carries a year, i.e. the previous book's "Publisher, Year"
    tail; the text before it is that book's authors. Otherwise it continues
    the previous title, which covers the CMS splitting a title ("...Gender
    and </em></strong><strong><em>Redress") and a title inside a title, set
    roman ("Kuhn's </em>The Structure of Scientific Revolutions<em>
    Revisited"). So a paragraph naming two books gives two.

    A header with no italics at all (4 of 120 random pages) falls back to
    the `search_authors` / `search_title` meta pair, but only when both
    values occur verbatim in the header's visible text: the meta is blank
    on some pages, and an unchecked value would be a guess. Otherwise no
    book, and the page reads as unverifiable."""
    books = []
    paras = soup.select(".meta-item__bibliography p")
    for para in paras:
        before = []
        run_open = False   # an italic run in THIS paragraph that may continue
        for node in para.descendants:
            if _is_title_tag(node) and not any(_is_title_tag(p) for p in node.parents):
                title = node.get_text(" ", strip=True)
                # Space-joined: a <br> or adjacent <span>s must not glue names.
                between = " ".join(" ".join(before).split())
                if title and run_open and not _YEAR.search(between):
                    books[-1]["title"] = " ".join(
                        (books[-1]["title"] + " " + between + " " + title).split())
                elif title:
                    books.append({"authors": between.strip(" ,."), "title": title})
                    run_open = True
                before = []
            # Exact type: Comment, CData and the like subclass it.
            elif type(node) is NavigableString and not any(_is_title_tag(p) for p in node.parents):
                before.append(str(node))
    if books:
        return books

    def meta(name):
        tag = soup.find("meta", {"name": name})
        return " ".join((tag.get("content") or "").split()) if tag else ""
    header = " ".join(" ".join(p.get_text(" ") for p in paras).split()).casefold()
    authors, title = meta("search_authors"), meta("search_title")
    if authors and title and authors.casefold() in header and title.casefold() in header:
        return [{"authors": authors, "title": title}]
    return []


def _is_title_tag(node) -> bool:
    return getattr(node, "name", None) in ("em", "i")


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
        - books: The reviewed books from the page's bibliographic header,
          [{"authors": ..., "title": ...}], [] when the page has none
    """
    soup = BeautifulSoup(html, "lxml")
    books = extract_reviewed_books(soup)

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
            "books": books,
        }

    # Get all <p> tags from the content area
    all_paragraphs = content_div.find_all("p")

    # Filter to substantive paragraphs (skip very short ones, metadata-like lines)
    substantive = []
    for p in all_paragraphs:
        # The bibliographic header is identity, never summary (the
        # <article> fallback above would otherwise include it).
        if p.find_parent(class_="meta-item__bibliography"):
            continue
        # Collapse the page's own whitespace: get_text(strip=True) stripped
        # every text node, gluing "In <em>Mind in Life</em> Evan" into
        # "InMind in LifeEvan"; a " " separator would split "16<sup>th</sup>".
        text = " ".join(p.get_text().split())
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
        "books": books,
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
        Dict with summary_text, paragraph_count, review_url, reviewer,
        review_date, books (the reviewed books from the page header)
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
                headers={"User-Agent": user_agent()},
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
    load_dotenv(find_dotenv(usecwd=True), override=True)  # before argparse defaults read os.environ
    parser = argparse.ArgumentParser(description="Fetch NDPR review and extract summary")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Full NDPR review URL")
    group.add_argument("--slug", help="Review slug (e.g., 'being-and-time')")
    parser.add_argument("--debug", action="store_true", help="Print debug info")

    add_output_arg(parser)
    args = parser.parse_args()
    set_output_path(args.output)

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
