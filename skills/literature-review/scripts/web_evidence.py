"""Web-source evidence: URL extraction, capture validation, existence checks.

Pure logic behind the barrier's EVIDENCE-WEB gate, kept out of
evidence_barrier.py for the same reason venue_vetting.py and year_suffix.py
are: the barrier orchestrates, the module decides. Nothing here writes files
or fails a run -- every failure path returns a verdict the caller reports.

Import-time cost is stdlib only; the two network functions import `requests`
inside their own bodies, so the barrier can import this unconditionally.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Matches a URL wherever it sits in a field: bare, \url{}-wrapped, or after
# prose. Stops at whitespace, a closing brace, or a quote.
_URL_RE = re.compile(r"https?://[^\s{}\"]+")

# Trailing characters that are sentence punctuation, never part of the URL.
_TRAILING = ".,;:!?)]}'\""

# LaTeX escapes that appear inside URLs in real bibs.
_LATEX_UNESCAPE = {r"\_": "_", r"\&": "&", r"\%": "%", r"\#": "#", r"\$": "$"}

# Two-part public suffixes that appear in, or plausibly near, the measured
# in-scope population. NOT a public-suffix list -- just enough that the
# same-domain test does not equate two unrelated sites. Without this,
# `alice.github.io` and `bob.github.io` share a "registered domain", so a
# redirect from one GitHub Pages site to a DIFFERENT user's is read as
# same-domain and corroborates directly -- which is exactly the squatter
# scenario the check exists to catch, and github is one of the 15 in-scope
# hosts the spec measured. Same story for `a.example.co.uk` vs
# `b.other.co.uk`. External review, 2026-08-11.
_TWO_PART_SUFFIXES = frozenset({
    "github.io", "gitlab.io", "blogspot.com", "wordpress.com", "substack.com",
    "webflow.io", "netlify.app", "vercel.app", "co.uk", "org.uk", "ac.uk",
    "gov.uk", "com.au", "edu.au", "co.nz", "co.jp", "co.za", "com.br",
})


def _unescape_latex(text: str) -> str:
    for esc, plain in _LATEX_UNESCAPE.items():
        text = text.replace(esc, plain)
    return text


def extract_url(fields: dict) -> str | None:
    """The entry's web URL, or None. `url` wins over `howpublished`."""
    for name in ("url", "howpublished"):
        raw = (fields.get(name) or "").strip()
        if not raw:
            continue
        m = _URL_RE.search(_unescape_latex(raw))
        if m:
            return m.group(0).rstrip(_TRAILING)
    return None


def normalize_url(url: str) -> str:
    """Comparison form: lowercase scheme/host, drop the default port and a
    trailing slash. Path case and query are PRESERVED -- they are
    case-sensitive on most servers, so folding them would equate URLs that
    serve different documents."""
    parts = urlsplit((url or "").strip())
    host = parts.hostname or ""
    try:
        port = parts.port
    except ValueError:
        # An out-of-range or non-numeric port. `_URL_RE` can capture one out of
        # a bib field, and a raise here would escape check_capture and take the
        # whole web pass down with it. Comparison form only, so dropping the
        # bad port is the right degradation.
        port = None
    if port and not (
        (parts.scheme == "https" and port == 443)
        or (parts.scheme == "http" and port == 80)
    ):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


def registered_domain(url: str) -> str:
    """The registrable part of the host: normally the last two labels, but
    three when the last two are a known two-part suffix (see above)."""
    host = (urlsplit(url or "").hostname or "").lower()
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in _TWO_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])
