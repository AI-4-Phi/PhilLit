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
import json
import re
import sys
import os
from typing import Optional

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rate_limiter import get_limiter

SEP_BASE = "https://plato.stanford.edu/entries"


def output_success(entry: str, result: dict) -> None:
    print(json.dumps({
        "status": "success", "source": "sep", "query": entry,
        "results": [result], "count": 1, "errors": []
    }, indent=2))
    sys.exit(0)


def output_error(entry: str, error_type: str, message: str, exit_code: int = 2) -> None:
    print(json.dumps({
        "status": "error", "source": "sep", "query": entry,
        "results": [], "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": False}]
    }, indent=2))
    sys.exit(exit_code)


def parse_bibliography_entry(raw_text: str) -> tuple[Optional[dict], str]:
    """Parse SEP bibliography entry. Returns (parsed_dict, confidence)."""
    raw_text = raw_text.strip()
    if not raw_text:
        return None, "unparseable"

    # Skip non-reference entries
    skip_patterns = [r'^See the entry', r'^For more on', r'^Also see', r'^\[.*\]$']
    for pattern in skip_patterns:
        if re.match(pattern, raw_text, re.IGNORECASE):
            return None, "unparseable"

    # Common SEP format: Author, Year, Title, Publisher.
    standard = r'^([^,]+(?:,\s*[^,]+)*),\s*(\d{4}|forthcoming),\s*["\']?(.+?)["\']?,\s*(.+)\.$'
    match = re.match(standard, raw_text)
    if match:
        authors_str, year, title, publisher = match.groups()
        authors = [a.strip() for a in re.split(r'\s+and\s+', authors_str)]
        is_edited = bool(re.search(r'\(eds?\.?\)', authors_str, re.IGNORECASE))
        parsed = {"authors": authors, "year": year, "title": title.strip("'\""), "publisher": publisher.strip()}
        if is_edited:
            parsed["is_edited"] = True
        return parsed, "high"

    # Try partial extraction
    partial = r'^([^,]+),\s*(\d{4})'
    match = re.match(partial, raw_text)
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


def fetch_sep_article(entry_name: str, limiter, debug: bool = False) -> dict:
    """Fetch and parse SEP article."""
    url = f"{SEP_BASE}/{entry_name}/"

    limiter.wait()
    if debug:
        print(f"DEBUG: GET {url}", file=sys.stderr)

    response = requests.get(url, timeout=30, headers={"User-Agent": "PhiloResearchBot/1.0"})
    limiter.record()

    if response.status_code == 404:
        raise LookupError(f"SEP entry not found: {entry_name}")
    elif response.status_code != 200:
        raise RuntimeError(f"HTTP error: {response.status_code}")

    soup = BeautifulSoup(response.text, "lxml")

    # Get title
    title_elem = soup.find("h1")
    title = title_elem.get_text(strip=True) if title_elem else entry_name

    return {
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


def main():
    parser = argparse.ArgumentParser(description="Fetch SEP article content")
    parser.add_argument("entry", help="Entry name or full URL")
    parser.add_argument("--sections", help="Comma-separated sections to extract (e.g., 'preamble,1,2,bibliography')")
    parser.add_argument("--bibliography-only", action="store_true")
    parser.add_argument("--related-only", action="store_true")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    # Extract entry name from URL if needed
    entry_name = args.entry
    if "plato.stanford.edu" in entry_name:
        match = re.search(r"/entries/([^/]+)/?", entry_name)
        if match:
            entry_name = match.group(1)
        else:
            output_error(args.entry, "config_error", "Could not extract entry name from URL")

    limiter = get_limiter("sep_fetch")

    try:
        article = fetch_sep_article(entry_name, limiter, args.debug)

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
