#!/usr/bin/env python3
"""
Fetch and parse SEP article content via BeautifulSoup.

Usage:
    python fetch_sep.py freewill
    python fetch_sep.py https://plato.stanford.edu/entries/freewill/
    python fetch_sep.py freewill --sections "preamble,1,2,bibliography"
    python fetch_sep.py freewill --bibliography-only
    python fetch_sep.py freewill --related-only

Exit Codes: 0=success, 1=not found, 2=config error, 3=network error
"""

import argparse

from dotenv import find_dotenv, load_dotenv
import re
import sys
import os
from typing import Optional

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rate_limiter import ExponentialBackoff, get_limiter, user_agent
from search_cache import cache_key, get_cache, put_cache
from output import emit, set_output_path, add_output_arg

SEP_BASE = "https://plato.stanford.edu/entries"


def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    print(f"[fetch_sep.py] {message}", file=sys.stderr, flush=True)


def output_success(entry: str, result: dict) -> None:
    emit({
        "status": "success", "source": "sep", "query": entry,
        "results": [result], "count": 1, "errors": []
    }, 0)


def output_error(entry: str, error_type: str, message: str, exit_code: int = 2) -> None:
    emit({
        "status": "error", "source": "sep", "query": entry,
        "results": [], "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": False}]
    }, exit_code)


# A year field in its own comma-separated position: "1971" or "forthcoming".
_YEAR_FIELD_RE = re.compile(r'^(?:\d{4}|forthcoming)$', re.IGNORECASE)
# Partial form: the entry opens "Surname, 1971" and nothing more is required.
_PARTIAL_RE = re.compile(r'^([^,]+),\s*(\d{4})')
_EDITOR_RE = re.compile(r'\(eds?\.?\)', re.IGNORECASE)


def _find_year_field(fields: list[str]) -> Optional[int]:
    """Index of the field to read as the entry's year, or None.

    The FIRST field that is exactly a year, skipping any whose successor is
    also year-like. Two rules meet here:

    * First, not last. The old regex's greedy author group effectively took
      the *last* viable year; taking the first is better on entries that
      carry a later reprint/translation/edition year, which is the common
      multi-year shape.
    * Except when the next field is itself a year, because then the first
      year is the one that would be read as the title. On
      "Smith, J., 1999, 2001, Title, Publisher." taking 1999 yields
      title="2001" -- a fabricated-looking title emitted at "high"
      confidence. (resolve_context._title_texts now scores the raw line
      too, so a bad parse no longer costs a CONTEXT match -- but it is
      still a wrong datum.) Skipping to 2001 reproduces the old greedy
      outcome on exactly the inputs where the old outcome was the right one.

    Index-safe: a year in the last field has no successor and is treated as
    followed by nothing (the caller rejects it on position anyway).
    """
    for i, field in enumerate(fields):
        if not _YEAR_FIELD_RE.match(field):
            continue
        following = fields[i + 1] if i + 1 < len(fields) else ''
        if _YEAR_FIELD_RE.match(following):
            continue
        return i
    return None

# A single bibliography line longer than this is not a reference we can parse
# and is not worth the attempt. This bound exists so no future parser change
# can be handed an unbounded string. Over the local SEP cache
# on 2026-08-06 -- 6,731 entries across the 41 articles past reviews had
# fetched -- lengths ran: median 129, p95 244, p99 319, max 915, nothing above
# 1,000. That is a sample of what this project asks SEP for, not of SEP, so the
# cap sits about 2x above the longest line observed rather than at it. Over-cap
# lines are not discarded: extract_bibliography still keeps `raw` with
# `parsed: None`, which is exactly the IEP path.
_MAX_ENTRY_CHARS = 2000


def parse_bibliography_entry(raw_text: str) -> tuple[Optional[dict], str]:
    """Parse SEP bibliography entry. Returns (parsed_dict, confidence).

    Splits on commas in ordinary Python rather than matching a
    comma-structured regex. The previous implementation used

        ^([^,]+(?:,\\s*[^,]+)*),\\s*(\\d{4}|forthcoming),...

    whose repeated comma-field group contains overlapping repetitions: after
    each comma both `\\s*` and `[^,]+` can consume the separator space, so
    every ", " admits two equivalent ways to match the same text. (It is NOT
    that the inner `[^,]+` absorbs what the outer one could -- the outer
    repeated unit begins with a comma, which `[^,]+` cannot consume.) When the
    required `,\\s*(\\d{4}|forthcoming),` never matches -- an entry with no year
    in that position -- the engine explores those equivalent allocations in
    combination across fields. Measured on the shipped pattern, a year-less
    author list cost 0.0009 s at 10 commas and 3.5 s at 22: about 2x per comma,
    4x per two, i.e. minutes at 30 and days at 40. One such entry in SEP's
    "Virtue Epistemology" bibliography hung a real review's evidence barrier
    for 72 minutes at 100% CPU (2026-08-06 live run).

    The split-based form below is linear in the length of the line. It still
    runs regexes -- `_YEAR_FIELD_RE`, `_PARTIAL_RE`, `_EDITOR_RE`, the skip
    patterns -- but each is anchored or bounded and none contains nested
    ambiguous repetition, so none can backtrack combinatorially.
    """
    raw_text = raw_text.strip()
    if not raw_text:
        return None, "unparseable"
    if len(raw_text) > _MAX_ENTRY_CHARS:
        return None, "unparseable"

    # Skip non-reference entries
    skip_patterns = [r'^See the entry', r'^For more on', r'^Also see', r'^\[.*\]$']
    for pattern in skip_patterns:
        if re.match(pattern, raw_text, re.IGNORECASE):
            return None, "unparseable"

    # Common SEP format: Author, Year, Title, Publisher.
    # Find the FIRST comma-delimited field that is exactly a year; everything
    # before it is the author list, everything after is title + publisher.
    fields = [f.strip() for f in raw_text.split(',')]
    year_at = _find_year_field(fields)
    # A year at position 0 leaves no author, and fewer than two fields after
    # the year leaves no title/publisher pair -- neither is the standard form.
    if year_at is not None and 0 < year_at < len(fields) - 2 and raw_text.endswith('.'):
        authors_str = ', '.join(fields[:year_at])
        year = fields[year_at]
        # Title is the next field; publisher is everything after it, with the
        # entry's trailing period removed (the old regex's `(.+)\.$`).
        title = fields[year_at + 1].strip('\'"')
        publisher = ', '.join(fields[year_at + 2:]).rstrip('.').strip()
        if not title:
            # "Author, 1999, , Publisher." -- an empty title field is not a
            # standard-form parse. Emitting it at "high" confidence would
            # advertise a title the entry does not have; fall through instead.
            # NOT a restoration of old behaviour: checked against the old
            # regex, whose `["\']?(.+?)["\']?` matched the separator SPACE and
            # returned title=" " at "high". Both reviews assumed it fell
            # through here; it did not. This is a deliberate improvement.
            return _partial_or_unparseable(raw_text)
        parsed = {
            "authors": [a.strip() for a in re.split(r'\s+and\s+', authors_str)],
            "year": year,
            "title": title,
            "publisher": publisher,
        }
        if _EDITOR_RE.search(authors_str):
            parsed["is_edited"] = True
        return parsed, "high"

    return _partial_or_unparseable(raw_text)


def _partial_or_unparseable(raw_text: str) -> tuple[Optional[dict], str]:
    """Partial extraction. Safe as written: one bounded group, no nesting."""
    match = _PARTIAL_RE.match(raw_text)
    if match:
        return {"authors": [match.group(1).strip()], "year": match.group(2), "title": raw_text}, "low"

    return None, "unparseable"


def extract_preamble(soup: BeautifulSoup) -> Optional[str]:
    """Extract preamble/abstract text."""
    preamble = soup.find("div", id="preamble")
    if preamble:
        return preamble.get_text(separator=" ", strip=True)
    return None


def extract_toc(soup: BeautifulSoup) -> list[dict]:
    """Extract table of contents."""
    toc = soup.find("div", id="toc")
    if not toc:
        return []

    items = []
    for link in toc.find_all("a"):
        href = link.get("href", "")
        if href.startswith("#"):
            text = link.get_text(strip=True)
            # Extract section number
            match = re.match(r'^(\d+(?:\.\d+)*)', text)
            if match:
                items.append({
                    "id": match.group(1),
                    "title": text[len(match.group(1)):].strip(". "),
                    "level": text.count(".") + 1
                })
    return items


def extract_sections(soup: BeautifulSoup, section_ids: Optional[list] = None) -> dict:
    """Extract section content."""
    sections = {}
    main_text = soup.find("div", id="main-text")
    if not main_text:
        return sections

    current_section = None
    current_content = []

    for elem in main_text.children:
        if elem.name in ["h2", "h3", "h4"]:
            # Save previous section
            if current_section:
                sections[current_section["id"]] = {
                    "id": current_section["id"],
                    "title": current_section["title"],
                    "content": " ".join(current_content).strip()
                }
                current_content = []

            # Start new section
            text = elem.get_text(strip=True)
            match = re.match(r'^(\d+(?:\.\d+)*)\.\s*(.+)', text)
            if match:
                sec_id = match.group(1)
                if section_ids is None or sec_id in section_ids:
                    current_section = {"id": sec_id, "title": match.group(2)}
                else:
                    current_section = None
            else:
                current_section = None

        elif current_section and elem.name == "p":
            current_content.append(elem.get_text(separator=" ", strip=True))

    # Save last section
    if current_section and current_content:
        sections[current_section["id"]] = {
            "id": current_section["id"],
            "title": current_section["title"],
            "content": " ".join(current_content).strip()
        }

    return sections


def extract_bibliography(soup: BeautifulSoup) -> list[dict]:
    """Extract bibliography with parsing."""
    bib_section = soup.find("div", id="bibliography")
    if not bib_section:
        return []

    entries = []
    for li in bib_section.find_all("li"):
        raw = li.get_text(separator=" ", strip=True)
        parsed, confidence = parse_bibliography_entry(raw)
        entries.append({"raw": raw, "parsed": parsed, "confidence": confidence})

    return entries


def extract_related_entries(soup: BeautifulSoup) -> list[dict]:
    """Extract related entries."""
    related = soup.find("div", id="related-entries")
    if not related:
        return []

    entries = []
    for link in related.find_all("a"):
        href = link.get("href", "")
        if "/entries/" in href:
            entry_name = href.split("/entries/")[-1].strip("/")
            entries.append({
                "title": link.get_text(strip=True),
                "entry_name": entry_name,
                "url": f"{SEP_BASE}/{entry_name}/"
            })
    return entries


def extract_metadata(soup: BeautifulSoup) -> dict:
    """Extract article metadata."""
    meta = {}

    # Try to get author from aueditable span
    author_elem = soup.find("meta", {"name": "author"})
    if author_elem:
        meta["author"] = author_elem.get("content")

    # Publication dates
    for dt_id, key in [("publication-date", "first_published"), ("modified-date", "last_updated")]:
        elem = soup.find(id=dt_id)
        if elem:
            meta[key] = elem.get_text(strip=True)

    return meta


def fetch_sep_article(entry_name: str, limiter, backoff: ExponentialBackoff, debug: bool = False) -> dict:
    """Fetch and parse SEP article with retry logic and caching."""
    # Check cache first (SEP articles change rarely, 7-day TTL is safe)
    key = cache_key(source="sep_fetch", entry=entry_name)
    cached = get_cache(key)
    if cached:
        log_progress(f"Using cached SEP article: {entry_name}")
        return cached

    url = f"{SEP_BASE}/{entry_name}/"

    log_progress(f"Connecting to Stanford Encyclopedia of Philosophy...")
    log_progress(f"Fetching SEP article: {entry_name}")

    for attempt in range(backoff.max_attempts):
        limiter.wait()
        if debug:
            print(f"DEBUG: GET {url}", file=sys.stderr)

        try:
            response = requests.get(url, timeout=30, headers={"User-Agent": user_agent()})
            limiter.record()

            if response.status_code == 404:
                raise LookupError(f"SEP entry not found: {entry_name}")
            elif response.status_code == 429:
                log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded after max retries")
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            elif response.status_code != 200:
                raise RuntimeError(f"HTTP error: {response.status_code}")

            log_progress(f"Parsing article content...")

            soup = BeautifulSoup(response.text, "lxml")

            # Get title
            title_elem = soup.find("h1")
            title = title_elem.get_text(strip=True) if title_elem else entry_name

            log_progress(f"Article fetched: {title}")

            result = {
                "url": url,
                "entry_name": entry_name,
                "title": title,
                "metadata": extract_metadata(soup),
                "preamble": extract_preamble(soup),
                "toc": extract_toc(soup),
                "sections": extract_sections(soup),
                "bibliography": extract_bibliography(soup),
                "related_entries": extract_related_entries(soup),
            }

            put_cache(key, result)
            return result

        except requests.exceptions.RequestException as e:
            log_progress(f"Network error: {str(e)[:100]}, retrying (attempt {attempt+1}/{backoff.max_attempts})...")
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Max retries exceeded")


def main():
    load_dotenv(find_dotenv(usecwd=True), override=True)  # before argparse defaults read os.environ
    parser = argparse.ArgumentParser(description="Fetch SEP article content")
    parser.add_argument("entry", help="Entry name or full URL")
    parser.add_argument("--sections", help="Comma-separated sections to extract (e.g., 'preamble,1,2,bibliography')")
    parser.add_argument("--bibliography-only", action="store_true")
    parser.add_argument("--related-only", action="store_true")
    parser.add_argument("--debug", action="store_true")

    add_output_arg(parser)
    args = parser.parse_args()
    set_output_path(args.output)

    # Extract entry name from URL if needed
    entry_name = args.entry
    if "plato.stanford.edu" in entry_name:
        match = re.search(r"/entries/([^/]+)/?", entry_name)
        if match:
            entry_name = match.group(1)
        else:
            output_error(args.entry, "config_error", "Could not extract entry name from URL")

    limiter = get_limiter("sep_fetch")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        article = fetch_sep_article(entry_name, limiter, backoff, args.debug)

        # Filter output based on options
        if args.bibliography_only:
            result = {
                "url": article["url"],
                "entry_name": article["entry_name"],
                "bibliography": article["bibliography"]
            }
        elif args.related_only:
            result = {
                "url": article["url"],
                "entry_name": article["entry_name"],
                "related_entries": article["related_entries"]
            }
        elif args.sections:
            requested = [s.strip() for s in args.sections.split(",")]
            result = {
                "url": article["url"],
                "entry_name": article["entry_name"],
                "title": article["title"],
            }
            if "preamble" in requested:
                result["preamble"] = article["preamble"]
            if "bibliography" in requested:
                result["bibliography"] = article["bibliography"]
            if "related" in requested:
                result["related_entries"] = article["related_entries"]

            # Extract numbered sections
            section_nums = [s for s in requested if re.match(r'^\d', s)]
            if section_nums:
                result["sections"] = {k: v for k, v in article["sections"].items() if k in section_nums}
        else:
            result = article

        output_success(entry_name, result)

    except LookupError as e:
        output_error(entry_name, "not_found", str(e), 1)
    except requests.exceptions.RequestException as e:
        output_error(entry_name, "network_error", str(e), 3)
    except Exception as e:
        output_error(entry_name, "parse_error", str(e), 3)


if __name__ == "__main__":
    main()
