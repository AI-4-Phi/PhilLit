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
# hosts measured for this list. Same story for `a.example.co.uk` vs
# `b.other.co.uk`. External review, 2026-08-11.
_TWO_PART_SUFFIXES = frozenset({
    "github.io", "gitlab.io", "blogspot.com", "wordpress.com", "substack.com",
    "webflow.io", "netlify.app", "vercel.app", "co.uk", "org.uk", "ac.uk",
    "gov.uk", "com.au", "edu.au", "co.nz", "co.jp", "co.za", "com.br",
})


CAPTURE_DIR = "web_captures"
SPAN_DELIM = "||"
MIN_TEXT_CHARS = 200
# Span parameters. The first proposal said "1-2 spans of 8-15 words"; it was a
# proposal, not normative, and these are deliberately looser at both ends -- 8
# words is short enough that a real sentence fragment often misses it, and a
# hard 15 forces researchers to trim mid-clause. MAX_SPANS enforces the "one or
# two" the researcher prose asks for, so prose and check cannot drift.
MIN_SPAN_WORDS = 6      # floor: a 2-word "span" proves nothing
MAX_SPAN_WORDS = 40
MAX_SPANS = 2

# Versioned negative signatures. Incomplete BY DESIGN -- it only has to cover
# the few dominant interstitial providers; the title anchor catches the rest.
BOILERPLATE_SIGNATURES_VERSION = 1
_BOILERPLATE = (
    "just a moment",
    "enable javascript",
    "checking your browser",
    "verify you are human",
    "accept all cookies",
    "attention required! | cloudflare",
)


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


# Encyclopedia-host exclusion (owner decision, 2026-08-17). These hosts never
# earn EVIDENCE-WEB -- out of scope by design, and now mechanical:
#   - SEP (plus its two official mirrors -- same content, same crawl-delay
#     courtesy, so leaving them in scope would leave a one-edit hole) and IEP
#     reach evidence through the store-backed CONTEXT channel, not captures.
#   - NDPR reviews feed @book abstracts through fetch_ndpr.py.
#   - A PhilPapers /rec/ page is an index ABOUT a work; the work itself is
#     the citation, resolved through the abstract/API channel. This repo also
#     never contacts philpapers.org directly anywhere else -- search_philpapers.py
#     goes through the Brave Search API, filtered to philpapers.org/rec/ --
#     and excluding it here keeps that true. philarchive.org, the OA archive on
#     its own domain, stays IN scope on purpose.
# Matching is exact host or dot-subdomain, never bare suffix (see
# excluded_host). Values are the hints fetch_web.py prints on refusal.
EXCLUDED_HOST_HINTS = {
    "plato.stanford.edu": (
        "SEP entries earn evidence through the encyclopedia context channel: "
        "cite the SEP entry itself (search_sep.py / fetch_sep.py), not a web "
        "capture."),
    "plato.sydney.edu.au": (
        "This is a SEP mirror. SEP entries earn evidence through the "
        "encyclopedia context channel: cite the SEP entry itself "
        "(search_sep.py / fetch_sep.py), not a web capture."),
    "seop.illc.uva.nl": (
        "This is a SEP mirror. SEP entries earn evidence through the "
        "encyclopedia context channel: cite the SEP entry itself "
        "(search_sep.py / fetch_sep.py), not a web capture."),
    "iep.utm.edu": (
        "IEP entries earn evidence through the encyclopedia context channel: "
        "cite the IEP entry itself (search_iep.py / fetch_iep.py), not a web "
        "capture."),
    "ndpr.nd.edu": (
        "NDPR reviews feed @book abstracts through fetch_ndpr.py; they are "
        "not web-capture sources."),
    "philpapers.org": (
        "A PhilPapers record page indexes a work: cite the work itself "
        "(resolve it via get_abstract.py / verify_paper.py), never the "
        "record page."),
}


def excluded_host(url: str) -> str | None:
    """The canonical excluded host `url` belongs to, or None.

    Subdomains count (www.iep.utm.edu is iep.utm.edu); look-alike suffixes
    do not (notphilpapers.org is nobody's subdomain), hence the dot in the
    endswith test. A trailing DNS dot is normalized away -- plato.stanford.edu.
    is the same host, and would otherwise match neither arm. Malformed
    netlocs return None rather than raise (urlsplit raises ValueError on bad
    IPv6 brackets): the callers' own bad-URL handling stays in charge.
    The three Unicode DNS label separators -- IDEOGRAPHIC FULL STOP (U+3002),
    FULLWIDTH FULL STOP (U+FF0E), HALFWIDTH IDEOGRAPHIC FULL STOP (U+FF61) --
    are normalized to ASCII "." before matching: IDNA/UTS-46 treats them as
    the same separator, so a host spelled with one of them IS iep.utm.edu
    (e.g.) once resolved, and must not bypass the policy matcher via an
    alternate spelling of the SAME host. Deliberately NOT handled: IDN/punycode
    homographs -- every excluded host is ASCII, and a homograph is a
    DIFFERENT domain (unlike the separator case above, which is the same
    domain under a different spelling).
    """
    try:
        host = (urlsplit(url or "").hostname or "")
    except (TypeError, ValueError):
        return None
    host = host.translate({0x3002: ".", 0xFF0E: ".", 0xFF61: "."})
    host = host.rstrip(".").lower()
    if not host:
        return None
    for key in EXCLUDED_HOST_HINTS:
        if host == key or host.endswith("." + key):
            return key
    return None


def load_capture(review_dir, citekey: str) -> dict | None:
    """The research-time capture for one citekey, or None."""
    path = Path(review_dir) / "intermediate_files" / CAPTURE_DIR / f"{citekey}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _fold(text: str) -> str:
    """Comparison form for containment: NFKC, LaTeX unescaped, whitespace
    collapsed, casefolded. Without this, spans fail on line wrapping and on the
    `\\&` the bib writer emits -- so "verbatim" here means verbatim up to this
    folding, which is what the researcher prose must say too."""
    text = _unescape_latex(unicodedata.normalize("NFKC", text or ""))
    return " ".join(text.split()).casefold()


def split_spans(raw: str) -> list[str]:
    return [s.strip() for s in (raw or "").split(SPAN_DELIM) if s.strip()]


def _title_tokens(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", _fold(text)) if len(t) > 3}


def check_capture(capture: dict | None, entry_url: str, title: str,
                  spans: str) -> tuple[bool, str]:
    """The five rule-(b) checks. Returns (passed, reason).

    Every reason is a distinct diagnosis, deliberately: collapsing any two of
    them hides the answer to a different operational question. `no_capture` vs
    `fetch_error` is "the researcher never ran the tool" vs "the tool ran and
    hit a WAF or an outage" -- failure records are written precisely so those
    stay apart. `thin` vs `title_mismatch` is "too little text" vs
    "captured the wrong page". `span_malformed` vs `span_unverified` is a
    formatting problem vs a note that outran its source, and only the second is
    evidence about the note.
    """
    if not capture:
        return False, "no_capture"
    if capture.get("error"):
        return False, "fetch_error"

    # 1. URL binding -- without it the gate is satisfiable by two unrelated
    #    facts: the entry's URL answers somewhere, and a file named for this
    #    citekey exists. Binding is what makes (a) and (b) about one source.
    want = normalize_url(entry_url)
    if not want:
        # Unreachable from the barrier (it only calls this after extract_url
        # returned non-None), but this is a public interface and an empty
        # `want` would otherwise bind to a capture missing both URL fields.
        return False, "url_mismatch"
    if want not in {normalize_url(capture.get("url") or ""),
                    normalize_url(capture.get("final_url") or "")}:
        return False, "url_mismatch"

    # 2. Status -- everything EXCEPT an explicit agent capture. A scripted
    #    fetch of a WAF challenge page records its 403 and must not pass on
    #    text length. Testing `!= "agent"` rather than `== "script"` so an
    #    unrecognized provenance value fails STRICT.
    if (capture.get("provenance") or "script") != "agent":
        status = capture.get("http_status")
        if not (isinstance(status, int) and 200 <= status < 300):
            return False, "bad_status"

    text = capture.get("text") or ""
    folded = _fold(text)

    # 3. Negative signatures.
    if any(sig in folded for sig in _BOILERPLATE):
        return False, "boilerplate"

    # 4. Substance, then title anchor -- two separate diagnoses. The text-head
    #    fallback is broader than first designed (scoped then to --stdin): a
    #    SCRIPT capture of a page with no <title>/<h1>/PDF-metadata title still
    #    needs an anchor, and refusing it would fail pages that are real.
    if len(text) < MIN_TEXT_CHARS:
        return False, "thin"
    anchor = capture.get("title") or text[:1000]
    wanted = _title_tokens(title)
    if wanted and not (wanted & _title_tokens(anchor)):
        return False, "title_mismatch"

    # 5. Span grounding (owner decision 2026-08-11). EVERY listed span must
    #    appear; one-of-many would reward padding the field.
    listed = split_spans(spans)
    if not listed or len(listed) > MAX_SPANS:
        return False, "span_malformed"
    for span in listed:
        words = _fold(span).split()
        if not (MIN_SPAN_WORDS <= len(words) <= MAX_SPAN_WORDS):
            return False, "span_malformed"
        if " ".join(words) not in folded:
            return False, "span_unverified"

    return True, "ok"


BOT_BLOCK_STATUSES = (403, 429)
EXISTENCE_TIMEOUT = 15
WAYBACK_API = "https://archive.org/wayback/available"


def http_get(url: str) -> dict:
    """Existence probe. GET, not HEAD: hosts routinely 405 a HEAD they would
    answer 200 for, which would read as link rot.

    Reaches rate_limiter across skills the way venue_vetting reaches
    search_cache. Flagged for the service port: it couples this module to a
    sibling skill's directory layout.
    """
    import requests
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                           / "philosophy-research" / "scripts"))
    from rate_limiter import user_agent
    session = requests.Session()
    session.max_redirects = 5
    resp = session.get(url, timeout=EXISTENCE_TIMEOUT, allow_redirects=True,
                       headers={"User-Agent": user_agent()})
    return {"status": resp.status_code, "final_url": resp.url}


def wayback_lookup(url: str) -> str | None:
    """Read-only availability lookup. NEVER Save Page Now (owner decision):
    no outward writes to the archive."""
    import requests
    resp = requests.get(WAYBACK_API, params={"url": url},
                        timeout=EXISTENCE_TIMEOUT)
    snap = ((resp.json() or {}).get("archived_snapshots") or {}).get("closest") or {}
    return snap.get("url") if snap.get("available") else None


def evaluate_existence(url: str, get_fn=None, wayback_fn=None) -> dict:
    """Rule (a): does this source exist?

    Direct corroboration is a 2xx that stayed on the same registered domain,
    or a bot-block on that same domain. Everything else -- connection failure,
    404/410, 5xx, or a cross-domain redirect -- falls through to the archive,
    because link rot is not nonexistence while a fabricated URL is neither
    reachable nor archived. The archive lookup runs either way (delivery wants
    the snapshot URL), and its failure never poisons existence the GET earned.
    """
    # Resolved HERE, not in the signature: a default bound at def time would
    # capture the original function object, so a test monkeypatching the module
    # global would silently hit the real network.
    get_fn = http_get if get_fn is None else get_fn
    wayback_fn = wayback_lookup if wayback_fn is None else wayback_fn

    basis, final_url = "none", None
    try:
        res = get_fn(url) or {}
        status = res.get("status")
        final_url = res.get("final_url") or url
        if isinstance(status, int):
            same_domain = registered_domain(final_url) == registered_domain(url)
            if 200 <= status < 300 and same_domain:
                basis = "direct"
            elif status in BOT_BLOCK_STATUSES and same_domain:
                # same_domain applies to bot_block too. The blanket-WAF
                # residual ("this host exists and blocks bots") is an accepted
                # honesty limit, but a CROSS-domain redirect ending at a WAF'd
                # 403 says only "some OTHER host blocks bots", which
                # corroborates nothing about the cited source.
                basis = "bot_block"
    except Exception:
        final_url = None

    archiveurl = None
    wayback_error = False
    try:
        archiveurl = wayback_fn(url) or None
    except Exception:
        # Failure never poisons existence already earned -- but it IS recorded:
        # the live acceptance run (2026-08-15) delivered no archiveurl on any
        # promoted entry, and a throttled availability API (429) was
        # indistinguishable post hoc from "no snapshot exists". Diagnostic
        # only; basis and archiveurl behave exactly as before.
        archiveurl = None
        wayback_error = True

    if basis == "none" and archiveurl:
        basis = "archive"
    return {"exists": basis != "none", "basis": basis,
            "final_url": final_url, "archiveurl": archiveurl,
            "wayback_error": wayback_error}
