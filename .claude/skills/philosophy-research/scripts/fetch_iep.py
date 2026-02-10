#!/usr/bin/env python3
"""
Fetch and parse IEP (Internet Encyclopedia of Philosophy) article content.

Usage:
    python fetch_iep.py freewill
    python fetch_iep.py https://iep.utm.edu/freewill/
    python fetch_iep.py freewill --sections "1,2,3"
    python fetch_iep.py freewill --bibliography-only

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
from rate_limiter import ExponentialBackoff, get_limiter

IEP_BASE = "https://iep.utm.edu"


def log_progress(message: str) -> None:
    """Emit progress to stderr (visible to user, doesn't break JSON output)."""
    print(f"[fetch_iep.py] {message}", file=sys.stderr, flush=True)


def output_success(entry: str, result: dict) -> None:
    print(json.dumps({
        "status": "success", "source": "iep", "query": entry,
        "results": [result], "count": 1, "errors": []
    }, indent=2))
    sys.exit(0)


def output_error(entry: str, error_type: str, message: str, exit_code: int = 2) -> None:
    print(json.dumps({
        "status": "error", "source": "iep", "query": entry,
        "results": [], "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": False}]
    }, indent=2))
    sys.exit(exit_code)


def extract_preamble(soup: BeautifulSoup) -> Optional[str]:
    """Extract the opening/abstract text of the article.

    IEP articles typically start with introductory paragraphs before
    the table of contents or first numbered section.
    """
    # Look for article content container
    article = soup.find("article") or soup.find("div", class_="entry-content")
    if not article:
        return None

    # Get paragraphs before first heading
    preamble_parts = []
    for elem in article.children:
        if elem.name in ["h2", "h3", "h4", "ol", "ul"]:
            # Stop at first heading or list (often TOC)
            if elem.name in ["ol", "ul"] and "toc" in str(elem.get("class", [])).lower():
                break
            if elem.name in ["h2", "h3", "h4"]:
                break
        if elem.name == "p":
            text = elem.get_text(separator=" ", strip=True)
            if text:
                preamble_parts.append(text)

    return " ".join(preamble_parts) if preamble_parts else None


def extract_toc(soup: BeautifulSoup) -> list[dict]:
    """Extract table of contents.

    IEP often uses ordered lists or specific TOC classes.
    """
    items = []

    # Try to find a TOC container
    toc = (soup.find("div", class_=re.compile(r"toc", re.I)) or
           soup.find("nav", class_=re.compile(r"toc", re.I)) or
           soup.find("ol", class_=re.compile(r"toc", re.I)))

    if toc:
        for i, link in enumerate(toc.find_all("a"), 1):
            href = link.get("href", "")
            if href.startswith("#"):
                items.append({
                    "id": str(i),
                    "title": link.get_text(strip=True),
                    "level": 1
                })

    return items


def extract_sections(soup: BeautifulSoup, section_ids: Optional[list] = None) -> dict:
    """Extract section content from the article."""
    sections = {}

    # Find article content
    article = soup.find("article") or soup.find("div", class_="entry-content")
    if not article:
        return sections

    current_section = None
    current_content = []
    section_num = 0

    for elem in article.descendants:
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
            section_num += 1
            sec_id = str(section_num)
            title = elem.get_text(strip=True)

            # Check if we want this section
            if section_ids is None or sec_id in section_ids:
                current_section = {"id": sec_id, "title": title}
            else:
                current_section = None

        elif current_section and elem.name == "p":
            # Avoid nested duplicates
            if elem.parent.name not in ["p", "blockquote"]:
                text = elem.get_text(separator=" ", strip=True)
                if text:
                    current_content.append(text)

    # Save last section
    if current_section and current_content:
        sections[current_section["id"]] = {
            "id": current_section["id"],
            "title": current_section["title"],
            "content": " ".join(current_content).strip()
        }

    return sections


def extract_bibliography(soup: BeautifulSoup) -> list[dict]:
    """Extract bibliography/references section.

    IEP typically has a References or Bibliography section near the end.
    """
    entries = []

    # Look for bibliography section by heading
    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = heading.get_text(strip=True).lower()
        if any(kw in text for kw in ["bibliography", "references", "works cited", "further reading"]):
            # Get the next list or paragraphs
            sibling = heading.find_next_sibling()
            while sibling:
                if sibling.name == "ul":
                    for li in sibling.find_all("li", recursive=False):
                        raw = li.get_text(separator=" ", strip=True)
                        if raw:
                            entries.append({"raw": raw, "parsed": None, "confidence": "low"})
                    break
                elif sibling.name == "p":
                    raw = sibling.get_text(separator=" ", strip=True)
                    if raw and len(raw) > 20:  # Filter out short non-reference text
                        entries.append({"raw": raw, "parsed": None, "confidence": "low"})
                elif sibling.name in ["h2", "h3", "h4"]:
                    break  # Next section
                sibling = sibling.find_next_sibling()
            break

    return entries


def extract_author_info(soup: BeautifulSoup) -> dict:
    """Extract author information.

    IEP articles typically have author info at the end.
    """
    info = {}

    # Look for author section
    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = heading.get_text(strip=True).lower()
        if "author" in text:
            sibling = heading.find_next_sibling()
            if sibling and sibling.name == "p":
                author_text = sibling.get_text(strip=True)
                info["author"] = author_text

                # Try to extract email
                email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', author_text)
                if email_match:
                    info["email"] = email_match.group()
            break

    # Try meta tag as fallback
    if "author" not in info:
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta:
            info["author"] = author_meta.get("content")

    return info


def fetch_iep_article(entry_name: str, limiter, backoff: ExponentialBackoff, debug: bool = False) -> dict:
    """Fetch and parse IEP article with retry logic."""
    url = f"{IEP_BASE}/{entry_name}/"

    log_progress(f"Connecting to Internet Encyclopedia of Philosophy...")
    log_progress(f"Fetching IEP article: {entry_name}")

    for attempt in range(backoff.max_attempts):
        limiter.wait()
        if debug:
            print(f"DEBUG: GET {url}", file=sys.stderr)

        try:
            response = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/philreview)"
                }
            )
            limiter.record()

            if response.status_code == 404:
                raise LookupError(f"IEP entry not found: {entry_name}")
            elif response.status_code == 403:
                log_progress(f"Access denied (403), trying with different headers...")
                # Try with different headers (respect rate limiter)
                limiter.wait()
                response = requests.get(
                    url,
                    timeout=30,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                )
                limiter.record()
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP error: {response.status_code} (access denied)")
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

            # Get title - try multiple selectors
            title_elem = (soup.find("h1", class_="entry-title") or
                         soup.find("h1") or
                         soup.find("title"))
            title = title_elem.get_text(strip=True) if title_elem else entry_name
            # Clean up title suffix
            title = re.sub(r'\s*\|\s*Internet Encyclopedia of Philosophy\s*$', '', title)

            log_progress(f"Article fetched: {title}")

            return {
                "url": url,
                "entry_name": entry_name,
                "title": title,
                "metadata": extract_author_info(soup),
                "preamble": extract_preamble(soup),
                "toc": extract_toc(soup),
                "sections": extract_sections(soup),
                "bibliography": extract_bibliography(soup),
            }

        except requests.exceptions.RequestException as e:
            log_progress(f"Network error: {str(e)[:100]}, retrying (attempt {attempt+1}/{backoff.max_attempts})...")
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Max retries exceeded")


def main():
    parser = argparse.ArgumentParser(description="Fetch IEP article content")
    parser.add_argument("entry", help="Entry name or full URL")
    parser.add_argument("--sections", help="Comma-separated section numbers to extract (e.g., '1,2,3')")
    parser.add_argument("--bibliography-only", action="store_true")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    # Extract entry name from URL if needed
    entry_name = args.entry
    if "iep.utm.edu" in entry_name:
        match = re.search(r"iep\.utm\.edu/([a-z0-9-]+)/?", entry_name)
        if match:
            entry_name = match.group(1)
        else:
            output_error(args.entry, "config_error", "Could not extract entry name from URL")

    limiter = get_limiter("iep_fetch")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        article = fetch_iep_article(entry_name, limiter, backoff, args.debug)

        # Filter output based on options
        if args.bibliography_only:
            result = {
                "url": article["url"],
                "entry_name": article["entry_name"],
                "bibliography": article["bibliography"]
            }
        elif args.sections:
            requested = [s.strip() for s in args.sections.split(",")]
            result = {
                "url": article["url"],
                "entry_name": article["entry_name"],
                "title": article["title"],
                "sections": {k: v for k, v in article["sections"].items() if k in requested}
            }
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
