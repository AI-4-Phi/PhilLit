#!/usr/bin/env python3
"""
Unified You.com site search for philosophy resources.

This module is the keyless counterpart to brave_search.py: You.com's MCP
endpoint (https://api.you.com/mcp?profile=free) serves web search without an
API key, so selecting the youcom provider (PHILLIT_SEARCH_PROVIDER=youcom or
--provider youcom) needs zero setup. Set YDC_API_KEY to use the
authenticated endpoint (https://api.you.com/mcp) for higher limits instead.

youcom_site_search() mirrors brave_site_search(): the same site-scoped
BraveSearchConfig, the same (results, errors) contract, and the same result
dict shape, so callers need no provider-specific handling. Differences:
- No offset pagination -- one JSON-RPC tools/call per search, with the count
  capped at what the endpoint serves per call (YOUCOM_COUNT_CAP).
- No freshness filter -- the endpoint's you-search schema takes no freshness
  argument.
- The endpoint is stateless (verified: no initialize handshake, no session
  id), so each call is a single self-contained POST.

Response transport is SSE (text/event-stream); the JSON-RPC reply for our id
is the one data: line that carries it -- notifications/progress messages
interleave and are skipped by matching on id.
"""

import json
import sys
from typing import Optional

import requests

try:
    from .rate_limiter import ExponentialBackoff, user_agent
    from .brave_search import BraveSearchConfig, extract_id
except ImportError:
    from rate_limiter import ExponentialBackoff, user_agent
    from brave_search import BraveSearchConfig, extract_id

YOUCOM_MCP_URL = "https://api.you.com/mcp"
YOUCOM_MCP_FREE_URL = YOUCOM_MCP_URL + "?profile=free"
YOUCOM_COUNT_CAP = 20  # endpoint serves at most ~20 web results per call
SNIPPET_MAX = 280  # You.com highlights are long; keep snippets Brave-sized


def _parse_jsonrpc_result(body: str, msg_id: int) -> dict:
    """Extract the JSON-RPC result object for msg_id from an MCP response.

    The endpoint answers with an SSE stream of data: lines, some of them
    notifications; the reply is the message whose id matches. Robust to a
    plain-JSON body (no data: prefix) in case a deployment ever answers
    without the event-stream wrapper.

    Raises:
        RuntimeError: If no id-matching reply is present, or the reply is a
            JSON-RPC error object.
    """
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            message = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if message.get("id") == msg_id:
            if "error" in message:
                detail = message["error"].get("message", "unknown error")
                raise RuntimeError(f"You.com MCP error: {detail}")
            return message.get("result", {})
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        message = None
    if isinstance(message, dict) and message.get("id") == msg_id:
        if "error" in message:
            detail = message["error"].get("message", "unknown error")
            raise RuntimeError(f"You.com MCP error: {detail}")
        return message.get("result", {})
    raise RuntimeError("You.com MCP response contained no result")


def _snippet(text: str, max_chars: int = SNIPPET_MAX) -> str:
    """Collapse whitespace and truncate a highlight to snippet size."""
    text = " ".join(str(text).split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]  # cut at a word boundary
    return cut.rstrip(" .,;:") + "..."


def format_youcom_result(item: dict, config: BraveSearchConfig) -> dict:
    """Format a You.com web result into the brave_search output format.

    You.com descriptions are often empty for encyclopedia entries; the
    contents.highlights carry the same material, so the first highlight
    becomes the snippet when the description is missing and the rest become
    extra_snippets (mirroring Brave's extra_snippets field).
    """
    url = item.get("url", "")
    resource_id = extract_id(url, config)

    highlights = (item.get("contents") or {}).get("highlights") or []
    description = (item.get("description") or "").strip()
    if description:
        snippet = _snippet(description)
        extra_snippets = [_snippet(h) for h in highlights[:3]]
    elif highlights:
        snippet = _snippet(highlights[0])
        extra_snippets = [_snippet(h) for h in highlights[1:4]]
    else:
        snippet, extra_snippets = "", []

    # You.com renders site suffixes parenthesized ("Compatibilism (Stanford
    # Encyclopedia of Philosophy)") where Brave uses " - Stanford
    # Encyclopedia of Philosophy"; strip both spellings of the configured
    # suffix so titles stay provider-comparable.
    title = item.get("title", "")
    for suffix in (config.title_suffix, " (" + config.title_suffix.lstrip(" -|") + ")"):
        title = title.replace(suffix, "")

    result = {
        "title": title.strip(),
        "url": url,
        config.id_field_name: resource_id,
        "snippet": snippet,
        "page_age": item.get("page_age"),
    }
    if extra_snippets:
        result["extra_snippets"] = extra_snippets

    return result


def youcom_site_search(
    query: str,
    limit: int,
    config: BraveSearchConfig,
    limiter,
    backoff: ExponentialBackoff,
    api_key: Optional[str] = None,
    log_fn: Optional[callable] = None,
    debug: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Search a site via the You.com MCP endpoint with rate limiting and retries.

    Keyless by default (free profile); pass api_key (YDC_API_KEY) to use the
    authenticated endpoint.

    Args:
        query: Search terms
        limit: Maximum number of results
        config: Site-specific configuration
        limiter: Rate limiter instance
        backoff: Exponential backoff instance
        api_key: Optional You.com API key; None uses the keyless free profile
        log_fn: Optional logging function (message -> None)
        debug: Enable debug output

    Returns:
        Tuple of (results list, errors list)
    """

    def log(msg: str) -> None:
        if log_fn:
            log_fn(msg)

    url = YOUCOM_MCP_URL if api_key else YOUCOM_MCP_FREE_URL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": user_agent(),
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    count = min(limit, YOUCOM_COUNT_CAP)
    if limit > YOUCOM_COUNT_CAP:
        log(f"You.com serves at most {YOUCOM_COUNT_CAP} results per call; requesting {count}")
    log(f"Connecting to You.com for {config.source_name} search...")
    log(f"Searching {config.site_domain}: '{query}', limit={count}")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "you-search",
            "arguments": {"query": f"site:{config.site_domain} {query}", "count": count},
        },
    }

    all_results = []
    errors = []

    for attempt in range(backoff.max_attempts):
        limiter.wait()

        if debug:
            print(f"DEBUG: POST {url}", file=sys.stderr)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            limiter.record()

            if response.status_code == 200:
                result = _parse_jsonrpc_result(response.text, msg_id=1)

                if result.get("isError"):
                    err_text = next(
                        (c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"),
                        "",
                    )
                    raise RuntimeError(f"You.com you-search tool error: {err_text[:200]}")

                text = next(
                    (c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"),
                    "",
                )
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    raise RuntimeError("You.com returned an unparseable search response")

                web_results = (data.get("results") or {}).get("web") or []
                for item in web_results:
                    # Only include URLs matching the path filter, mirroring
                    # brave_site_search (e.g. PhilPapers /rec/ over /archive/)
                    if config.url_path_filter in item.get("url", "") and len(all_results) < limit:
                        formatted = format_youcom_result(item, config)
                        if formatted.get(config.id_field_name) is not None:
                            all_results.append(formatted)
                        elif debug:
                            log(f"Dropped result (no {config.id_field_name}): {item.get('url', '')}")

                log(f"Search complete: {len(all_results)} entries found")
                return all_results, errors

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
                    errors.append({"type": "server_error", "message": f"You.com server error: {response.status_code}", "recoverable": True})
                    return all_results, errors
                log(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue

            elif response.status_code == 401:
                raise ValueError("Invalid YDC_API_KEY")

            else:
                raise RuntimeError(f"You.com MCP error: {response.status_code}")

        except requests.exceptions.RequestException as e:
            log(f"Network error: {str(e)[:100]}, retrying (attempt {attempt + 1}/{backoff.max_attempts})...")
            if attempt < backoff.max_attempts - 1:
                backoff.wait(attempt)
                log(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            log(f"Max retries reached after network errors, returning {len(all_results)} partial results")
            errors.append({"type": "network_error", "message": str(e), "recoverable": True})
            return all_results, errors

    return all_results, errors
