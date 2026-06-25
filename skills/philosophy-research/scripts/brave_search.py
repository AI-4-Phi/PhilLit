#!/usr/bin/env python3
"""
Unified Brave site search for philosophy resources.

This module provides a shared implementation for searching philosophy
resources via Brave API. Used by search_sep.py and search_philpapers.py.

The main function brave_site_search() handles:
- Rate limiting and exponential backoff
- Pagination across multiple Brave API pages
- Site-specific result formatting
"""

import re
import sys
from dataclasses import dataclass
from typing import Optional

import requests

try:
    from .rate_limiter import ExponentialBackoff, get_limiter
except ImportError:
    from rate_limiter import ExponentialBackoff, get_limiter

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


@dataclass
class BraveSearchConfig:
    """Configuration for site-specific Brave search."""

    source_name: str  # e.g., "sep_via_brave"
    site_domain: str  # e.g., "plato.stanford.edu"
    url_path_filter: str  # e.g., "/entries/" - only include URLs containing this
    id_pattern: str  # Regex to extract ID from URL
    id_field_name: str  # Field name for the ID (e.g., "entry_name", "philpapers_id")
    title_suffix: str  # Suffix to remove from titles


# Pre-configured search targets
SEP_CONFIG = BraveSearchConfig(
    source_name="sep_via_brave",
    site_domain="plato.stanford.edu",
    url_path_filter="/entries/",
    id_pattern=r"plato\.stanford\.edu/entries/([^/]+)/?",
    id_field_name="entry_name",
    title_suffix=" - Stanford Encyclopedia of Philosophy",
)

PHILPAPERS_CONFIG = BraveSearchConfig(
    source_name="philpapers_via_brave",
    site_domain="philpapers.org",
    url_path_filter="/rec/",
    id_pattern=r"philpapers\.org/rec/([A-Z0-9]+)",
    id_field_name="philpapers_id",
    title_suffix=" - PhilPapers",
)

IEP_CONFIG = BraveSearchConfig(
    source_name="iep_via_brave",
    site_domain="iep.utm.edu",
    url_path_filter="/",
    id_pattern=r"iep\.utm\.edu/([a-z0-9-]+)/?$",
    id_field_name="entry_name",
    title_suffix=" | Internet Encyclopedia of Philosophy",
)


def extract_id(url: str, config: BraveSearchConfig) -> Optional[str]:
    """Extract resource ID from URL using config pattern."""
    match = re.search(config.id_pattern, url)
    return match.group(1) if match else None


def format_result(item: dict, config: BraveSearchConfig) -> dict:
    """Format a Brave search result into standard output format."""
    url = item.get("url", "")
    resource_id = extract_id(url, config)

    result = {
        "title": item.get("title", "").replace(config.title_suffix, "").strip(),
        "url": url,
        config.id_field_name: resource_id,
        "snippet": item.get("description", ""),
        "page_age": item.get("page_age"),
    }

    # Extract author if available
    article = item.get("article", {})
    if article.get("author"):
        result["author"] = article["author"]

    # Extra snippets if available
    if item.get("extra_snippets"):
        result["extra_snippets"] = item["extra_snippets"]

    return result


def brave_site_search(
    query: str,
    limit: int,
    api_key: str,
    config: BraveSearchConfig,
    limiter,
    backoff: ExponentialBackoff,
    all_pages: bool = False,
    freshness: Optional[str] = None,
    log_fn: Optional[callable] = None,
    debug: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Search a site via Brave API with rate limiting and pagination.

    Args:
        query: Search terms
        limit: Maximum number of results
        api_key: Brave API key
        config: Site-specific configuration
        limiter: Rate limiter instance
        backoff: Exponential backoff instance
        all_pages: Whether to fetch all available pages
        freshness: Brave freshness filter (e.g., "py" for past year)
        log_fn: Optional logging function (message -> None)
        debug: Enable debug output

    Returns:
        Tuple of (results list, errors list)
    """

    def log(msg: str) -> None:
        if log_fn:
            log_fn(msg)

    log(f"Connecting to Brave API for {config.source_name} search...")
    log(f"Searching {config.site_domain}: '{query}', limit={limit}")

    params = {
        "q": f"site:{config.site_domain} {query}",
        "count": 20,
        "text_decorations": "false",
        "result_filter": "web",
        "extra_snippets": "true",
    }
    if freshness:
        params["freshness"] = freshness

    headers = {"X-Subscription-Token": api_key}

    all_results = []
    errors = []
    max_offset = 9 if all_pages else 0  # Brave max offset is 9

    for offset in range(0, max_offset + 1):
        if len(all_results) >= limit:
            break

        params["offset"] = offset

        for attempt in range(backoff.max_attempts):
            limiter.wait()

            if debug:
                print(f"DEBUG: GET {BRAVE_URL} offset={offset}", file=sys.stderr)

            try:
                response = requests.get(BRAVE_URL, params=params, headers=headers, timeout=30)
                limiter.record()

                if response.status_code == 200:
                    data = response.json()
                    web_results = data.get("web", {}).get("results", [])

                    if not web_results:
                        log(f"Search complete: {len(all_results)} entries found")
                        return all_results, errors

                    for item in web_results:
                        # Only include URLs matching the path filter
                        if config.url_path_filter in item.get("url", ""):
                            if len(all_results) < limit:
                                formatted = format_result(item, config)
                                if formatted.get(config.id_field_name) is not None:
                                    all_results.append(formatted)
                                elif debug:
                                    log(f"Dropped result (no {config.id_field_name}): {item.get('url', '')}")

                    log(f"Retrieved {len(all_results)} entries...")
                    break

                elif response.status_code == 429:
                    log(f"Rate limited, backing off (attempt {attempt + 1}/{backoff.max_attempts})...")
                    if not backoff.wait(attempt):
                        log(f"Max retries reached, returning {len(all_results)} partial results")
                        errors.append({"type": "rate_limit", "message": "Rate limit exceeded", "recoverable": True})
                        return all_results, errors
                    log(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                    continue

                elif response.status_code >= 500:
                    log(f"Server error {response.status_code}, retrying (attempt {attempt + 1}/{backoff.max_attempts})...")
                    if not backoff.wait(attempt):
                        log(f"Max retries reached after server errors, returning {len(all_results)} partial results")
                        errors.append({"type": "server_error", "message": f"Brave API server error: {response.status_code}", "recoverable": True})
                        return all_results, errors
                    log(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                    continue

                elif response.status_code == 401:
                    raise ValueError("Invalid BRAVE_API_KEY")

                else:
                    raise RuntimeError(f"Brave API error: {response.status_code}")

            except requests.exceptions.RequestException as e:
                log(f"Network error: {str(e)[:100]}, retrying (attempt {attempt + 1}/{backoff.max_attempts})...")
                if attempt < backoff.max_attempts - 1:
                    backoff.wait(attempt)
                    log(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                    continue
                log(f"Max retries reached after network errors, returning {len(all_results)} partial results")
                errors.append({"type": "network_error", "message": str(e), "recoverable": True})
                return all_results, errors

        if not all_pages:
            break

    log(f"Search complete: {len(all_results)} entries found")
    return all_results, errors
