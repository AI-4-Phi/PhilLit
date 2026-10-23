#!/usr/bin/env python3
"""Acquire a work's PDF into the full-text store (EVIDENCE-FULLTEXT).

Usage:
  acquire_fulltext.py <workdir> --doi D [--title T --author A --year Y]
  acquire_fulltext.py <workdir> --title T --author A --year Y
  acquire_fulltext.py <workdir> (--doi D | --title T --author A --year Y) --pdf PATH
  acquire_fulltext.py <workdir> --gaps --domains N

Rulings: `docs/ideas/fulltext-evidence-tier.md` ("Decided").

WHAT IT WRITES. Only `<slug>.pdf` and then its `<slug>.json` acquisition
sidecar in `[workdir]/intermediate_files/fulltext/` (both atomic), and in
`--gaps` mode the run report `intermediate_files/json/fulltext_acquisition.json`;
with the service channel on, also its request and `.closed` files, and it
removes a service copy that the licence backstop, the read or the identity
check refuses, or that the deadline left unchecked. Never a `.txt` (the
evidence barrier renders texts; a service copy's `.txt` is left for it)
and never a bib. A PDF here licenses nothing by itself: the barrier
re-extracts it, checks its hash against the sidecar and re-runs the
identity check against the ENTRY before it stamps FULLTEXT.
"Is this PDF this work" is `fulltext.identity_ok`, run here on every
candidate from every source, `--pdf` included; slugs, record validity and
the store paths are `fulltext.py`'s too.

SOURCES, in the ruled order, the first passing PDF wins:
0. The repository: a flat, read-only directory of records in the store's
   format (`PHILLIT_FULLTEXT_REPOSITORY_DIR`, read after `.env` loads like
   `PHILLIT_PDF_DIR`; normally unset locally), looked up by this identity's
   slug. The record must validate, pass the licence rule and the identity
   check against THIS run's identity. It is never copied: the PDF is stored
   through the normal path with `source` `repository` and the original
   source and ref nested in `source_ref` (`{stem, source, source_ref}`),
   because the barrier binds no-DOI records on this run's own identity.
1. Zotero, through Zotero 7's local API on localhost:23119 (never the
   database file, never an MCP server). The item's metadata must match
   (DOI equal, or title phrase + first-creator surname + year), then each
   `application/pdf` child attachment's `/file` endpoint answers 302 with a
   `file://` Location, which is parsed, never followed as HTTP.
2. The local PDF folder, through a cached index (`PDF_INDEX_DIR`): DOIs on
   pages 1-3 and the folded heads of pages 1-5 per file, refreshed
   incrementally within a time budget. The index is a superset filter; the
   identity check runs on each candidate file.
3. OpenAlex (`best_oa_location`, then the other locations with a `pdf_url`).
4. Semantic Scholar (`openAccessPdf`).
5. The service channel (`PHILLIT_FULLTEXT_REQUEST_DIR`; it replaces 3 and 4,
   which then report `disabled` with detail `service`). One request file per
   batch of at most `fulltext_channel.MAX_PER_REQUEST` DOI identities, never
   a URL and never a no-DOI identity (`no_doi`); the grammar is
   `fulltext_channel`'s. A worker copies each found record into the store
   under this identity's slug and answers; the engine waits on all its
   requests together until `SERVICE_WAIT_MARGIN` seconds plus
   `ARRIVAL_CHECK_SECONDS` per identity sent before the deadline, writes
   `<id>.closed`, and maps a key still unanswered to `deadline`
   (`no_outcome` when the response is complete). It then checks the record
   at THIS identity's slug for every requested key, whatever the response
   says: for `found` whatever stem it names (a differing stem is the
   detail `stem_mismatch`, never a gate), and for any other answer, or
   none, whenever a file is there (a passing copy is a hit noted
   `copied_after_response:<outcome>`). Each copy is validated as a
   download is: `validate_record`, the licence backstop (`_licensed`), the
   read, then `check_pdf` against THIS run's identity; a copy refused by
   the backstop, unreadable or failing the identity check is removed
   (nothing downstream reads licences), and a passing one stays as the
   worker wrote it, with its own source, ref and licence (it is not
   rewritten and its bytes are not held). A slug the deadline reaches
   before its check is `deadline`, and its copy is removed unchecked. A
   copy that lands after the arrival check is bound by the barrier without
   a licence re-check (the barrier checks identity and the hash only). The
   worker stops copying at `.closed` and applies the same policy before it
   fetches, so the window is a copy already in flight at `.closed` with a
   worker licence bug, accepted under the project's scrappy legal posture.
   A service-copied record found on a later acquisition run (`exists`) is
   re-checked against the policy then (a refused one is removed:
   `unlicensed_removed`).
OpenAlex and Semantic Scholar need a DOI. Several passing PDFs within the
winning source: the first is kept and the rest are reported
(`multiple_candidates`); every candidate of that source is checked, up to
the folder's 20-candidate limit.

CONSENT. Zotero and the folder are the user's own files, so they are never
touched without their workspace `.env` keys, which are written only on the
user's consent: `PHILLIT_ZOTERO` (1/true/yes/on) and `PHILLIT_PDF_DIR`. Without
a key, the source reports `disabled` and makes no call and no file read.
Paywalled copies come only from the user's own copies (Zotero, the folder,
`--pdf`) or open access, never a proxy or a shadow library.

SERVICE POLICY. One licence rule, three settings (`_licensed`), compared
case-insensitively after stripping (S2 reports `CCBY`).
`PHILLIT_FULLTEXT_POLICY=open` admits a licence that starts with `cc` or
`oa:`, or equals `upload`; `open` is the only value recognised, and any
other non-empty value falls to the `cc`-only rule (fails closed).
`PHILLIT_FULLTEXT_LICENSED_ONLY` (1/true/yes/on) admits a licence that
starts with `cc` only, and also disables Zotero and the folder (`POLICY`
alone leaves both on). With neither set there is no filter. Both are read
from the PROCESS environment BEFORE `.env` is loaded and `.env` is ignored
for them in both directions: the hosted service sets them for its own
process, so a workspace `.env` cannot switch the filter off. They are a
policy default, not a security boundary: a Bash call can still unset the
variables for one run. Every sidecar records `source`, `source_ref` and
`license`, so a run can be audited afterwards. `--pdf` stays available
under the policy (the service builds uploads on it) and never consults the
service channel. The service sets a third variable,
`PHILLIT_FULLTEXT_REQUEST_DIR`, which turns the service channel on (source
5); a location, not a policy, it is read after `.env` loads like
`PHILLIT_PDF_DIR`. The worker creates that directory
(`intermediate_files/fulltext_requests/`) before the review starts; the
engine never does, and a missing directory means no worker
(`request_dir_missing`).

DOWNLOADS. http(s) only, re-checked on every redirect hop (at most 5,
followed by hand); 30 s per download; a 60 MB cap enforced while streaming;
the body must start `%PDF-`; only the User-Agent is sent (no API key ever
reaches a PDF host). Local files (Zotero, folder, `--pdf`): a 200 MB cap.

OUTCOMES. Single-work mode prints one JSON object `{status, slug, source,
tried}`, within a 420 s deadline (`SINGLE_DEADLINE`, the Bash ceiling is
600 s); `status` is `acquired`, `exists` (a valid record for this identity
is already stored), `not_found` (no PDF was obtained), `rejected` (a PDF
was obtained and none passed extraction and the identity check) or
`refused` (`slug_collision`: a sidecar under the stem names another
identity, and nothing is overwritten; `path_too_long`: the store path
would exceed the Windows limit; `unlicensed_remove_failed:<error>`: a
stored service copy the policy refuses could not be removed, and no
source runs). `tried` lists `{source, outcome[, detail]}` in order;
source outcomes are `disabled`, `unavailable`, `not_found`, `rejected`,
`acquired`, plus `no_doi` for the OA sources and the service,
`unlicensed` for the OA sources, the repository and the service, and
`deadline` for a source the deadline cut.
Service details: `no_outcome` (a complete response without this key),
`stem_mismatch` (added to the outcome of checking the record at this
slug), `copied_after_response:<outcome>` (a copy found at this slug
although the answer was not `found`), `copy_invalid:<reason>`
(the copy fails `validate_record`; it is left for the barrier to
withhold), `removed_copy` (a valid copy that could not be read),
`error:<exception>` (this slug's check crashed; its copy is removed,
`remove_failed:<error>` when that fails), `unchecked_copy_removed` (the
deadline passed before this slug's check, and its copy was removed),
`field_too_long`, `request_dir_missing`, `request_write_failed:<error>`,
`closed_write_failed:<error>`, and the worker's own detail token. An
invalid stored record is reported as `{source: "store", outcome:
"invalid_replaced:<reason>"}` when a new PDF replaced it
(`invalid_kept:<reason>` when none was found); a stored service copy the
policy refuses as `{source: "store", outcome: "unlicensed_removed"}`. Exit
0 for every status; 1 for a crash, with one JSON object `{"error": ...}`;
2 for a usage error.

`--gaps` tries every domain-bib entry with no `abstract` and either a DOI,
or (the repository, Zotero or the folder enabled) a title, author and
year, within a 420 s pass deadline (the Bash ceiling is 600 s): store and
repository (and Zotero and the folder where enabled; OpenAlex and Semantic
Scholar while the service channel is off) per entry, each entry decided or
found there stored at once, then one service request for the entries still
open, then a wait bounded by the pass deadline. Entries not reached are
`not_attempted`; an entry whose work an earlier entry already tried is
`same_work_as` that entry and takes its final outcome. It writes the run
report and prints a one-line JSON summary with counts per outcome.

IDENTITY FORMS (the barrier's binding contract). `--gaps` stores the
entry's RAW title, `bib_identity.first_author_surname(author, editor)` and
the raw year, because the barrier binds no-DOI records by `same_work_key`
on raw values. Single-work mode stores `--title`, `--author` (the first
author's full surname, particles included) and `--year` as given.
`identity_ok` decodes LaTeX itself, so raw values go to it unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
from dotenv import find_dotenv, load_dotenv

# Each insert is removed by value, not pop(0): an imported module may insert
# paths of its own (the convention fulltext.py documents).
_hook_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "hooks")
sys.path.insert(0, _hook_dir)
from bib_comments import is_verbatim_block  # noqa: E402
from bib_identity import first_author_surname, normalize_doi, same_work_year  # noqa: E402

sys.path.remove(_hook_dir)
_here = str(Path(__file__).resolve().parent)
sys.path.insert(0, _here)
import fulltext as ft  # noqa: E402
import fulltext_channel as fc  # noqa: E402
from stamp_evidence import entry_header, parse_entry_fields, split_entries  # noqa: E402
from venue_vetting import _ON_TOKENS  # noqa: E402 - the shared on-token set

sys.path.remove(_here)
_research = str(Path(__file__).resolve().parent.parent.parent / "philosophy-research" / "scripts")
sys.path.insert(0, _research)
from rate_limiter import (  # noqa: E402
    ExponentialBackoff,
    get_limiter,
    openalex_budget_exhausted,
    openalex_headers,
    openalex_params,
    parse_retry_after,
    user_agent,
)
from s2_formatters import S2_BASE_URL  # noqa: E402
import output  # noqa: E402

sys.path.remove(_research)


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

LICENSED_ONLY_ENV = "PHILLIT_FULLTEXT_LICENSED_ONLY"
POLICY_ENV = "PHILLIT_FULLTEXT_POLICY"
REPOSITORY_DIR_ENV = "PHILLIT_FULLTEXT_REPOSITORY_DIR"
REQUEST_DIR_ENV = "PHILLIT_FULLTEXT_REQUEST_DIR"
ZOTERO_ENV = "PHILLIT_ZOTERO"
PDF_DIR_ENV = "PHILLIT_PDF_DIR"

ZOTERO_BASE = "http://localhost:23119/api/users/0"
ZOTERO_TIMEOUT = 10
ZOTERO_SEARCH_LIMIT = 100
OPENALEX_BASE = "https://api.openalex.org"

DOWNLOAD_TIMEOUT = 30
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024
MAX_REDIRECTS = 5
LOCAL_MAX_BYTES = ft.MAX_PDF_BYTES   # 200 MB
API_TIMEOUT = 30

GAPS_DEADLINE = 420
SINGLE_DEADLINE = 420
SERVICE_WAIT_MARGIN = 20   # seconds of the deadline kept for validating arrivals
ARRIVAL_CHECK_SECONDS = 1.0   # and this much more per identity sent
INDEX_BUDGET_GAPS = 60
INDEX_BUDGET_SINGLE = 20
MAX_WALK_FILES = 50_000
MAX_CANDIDATES = 20
INDEX_PAGES = 5
INDEX_DOI_PAGES = 3
INDEX_HEAD_CHARS = 600
INDEX_SCHEMA = 1

# Resolved at call time (tests monkeypatch it): the folder index cache.
PDF_INDEX_DIR = Path.home() / ".cache" / "phillit" / "pdf-index"

REPORT_REL = "intermediate_files/json/fulltext_acquisition.json"

_clock = time.monotonic   # tests monkeypatch this, never sleep
_sleep = time.sleep       # and this, for the service channel's polling


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Deadline:
    """A wall-clock end on `_clock`; None seconds means no end."""

    def __init__(self, seconds: float | None):
        self.end = None if seconds is None else _clock() + seconds

    def left(self) -> float:
        return float("inf") if self.end is None else self.end - _clock()

    def expired(self) -> bool:
        return self.left() <= 0

    def clamp(self, seconds: float) -> float:
        return max(0.0, min(seconds, self.left()))


def _on(value: str | None) -> bool:
    return (value or "").strip().lower() in _ON_TOKENS


def _doi_ok(doi: str) -> bool:
    return doi.startswith("10.") and "/" in doi


# --------------------------------------------------------------------------
# HTTP seam: every request goes through here (tests patch it)
# --------------------------------------------------------------------------

def _http_get(url, *, headers=None, params=None, timeout=30.0, stream=False, trust_env=True):
    """One GET, never following redirects."""
    session = requests.Session()
    session.trust_env = trust_env
    return session.get(url, headers=headers or {}, params=params, timeout=timeout,
                       stream=stream, allow_redirects=False)


def download_pdf(url: str, deadline: Deadline) -> tuple[bytes | None, str]:
    """(bytes, "ok") or (None, reason). http(s) only on every hop; at most
    MAX_REDIRECTS redirects; DOWNLOAD_TIMEOUT overall; MAX_DOWNLOAD_BYTES
    while streaming; the body must start `%PDF-`."""
    dl = Deadline(min(DOWNLOAD_TIMEOUT, deadline.left()))
    headers = {"User-Agent": user_agent(), "Accept": "application/pdf,*/*;q=0.5"}
    resp = None
    try:
        for hop in range(MAX_REDIRECTS + 1):
            if urlparse(url).scheme.lower() not in ("http", "https"):
                return None, "bad_scheme"
            if dl.expired():
                return None, "timeout"
            resp = _http_get(url, headers=headers, timeout=dl.clamp(DOWNLOAD_TIMEOUT), stream=True)
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location")
                resp.close()
                resp = None
                if not loc:
                    return None, "redirect_without_location"
                if hop == MAX_REDIRECTS:
                    return None, "too_many_redirects"
                url = urljoin(url, loc)
                continue
            break
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        declared = resp.headers.get("Content-Length")
        if declared and str(declared).isdigit() and int(declared) > MAX_DOWNLOAD_BYTES:
            return None, "too_large"
        chunks, total, head_ok = [], 0, False
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                return None, "too_large"
            chunks.append(chunk)
            if not head_ok and total >= 5:
                if not b"".join(chunks)[:5] == b"%PDF-":
                    return None, "not_pdf"
                head_ok = True
            if dl.expired():
                return None, "timeout"
        body = b"".join(chunks)
        if not body.startswith(b"%PDF-"):
            return None, "not_pdf"
        return body, "ok"
    except requests.RequestException as exc:
        # The class name only: a requests message embeds the URL.
        return None, f"network:{type(exc).__name__}"
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass


# --------------------------------------------------------------------------
# Candidates
# --------------------------------------------------------------------------

@dataclass
class Hit:
    """A passing candidate. `stored`: a validated service copy, already the
    store's record at the slug; it holds no bytes (`data` is empty) and
    `finish` leaves it as written."""
    data: bytes
    source: str
    source_ref: object
    license: str | None
    stored: bool = False


@dataclass
class SourceResult:
    source: str
    outcome: str
    detail: list = field(default_factory=list)
    hits: list = field(default_factory=list)

    def tried(self) -> dict:
        out = {"source": self.source, "outcome": self.outcome}
        if self.detail:
            out["detail"] = list(self.detail)
        return out


def check_pdf(data: bytes, identity: dict) -> tuple[bool, str]:
    """Extraction plus `fulltext.identity_ok`, the same for every source."""
    try:
        pages = ft.extract_pages(data)
    except ft.FulltextError as exc:
        return False, f"extract_failed:{exc.reason}"
    ok, why = ft.identity_ok(pages, identity)
    return ok, (why if ok else f"identity_failed:{why}")


def _read_local(path: str) -> tuple[bytes | None, str]:
    try:
        st = os.stat(path)
    except OSError:
        return None, "missing"
    if not os.path.isfile(path):
        return None, "not_a_file"
    if st.st_size > LOCAL_MAX_BYTES:
        return None, "too_large"
    try:
        with open(path, "rb") as f:
            return f.read(LOCAL_MAX_BYTES + 1), "ok"
    except OSError:
        return None, "unreadable"


def _finish(result: SourceResult, checked: int, passed: int) -> SourceResult:
    if result.hits:
        result.outcome = "acquired"
        if passed > 1:
            result.detail.append(f"multiple_candidates:{passed}")
    elif checked:
        result.outcome = "rejected"
    else:
        result.outcome = "not_found"
    return result


# --------------------------------------------------------------------------
# Repository
# --------------------------------------------------------------------------

def source_repository(identity: dict, settings: "Settings", deadline: Deadline) -> SourceResult:
    """The record at this identity's slug in the repository. A missing,
    empty (an unmounted mountpoint) or unreadable directory is
    `unavailable`, never a crash and never `not_found`."""
    res = SourceResult("repository", "not_found")
    if settings.repository_dir is None:
        res.outcome = "disabled"
        return res
    stem = ft.slug_for(identity)
    try:
        if not settings.repository_dir.is_dir():
            res.outcome, res.detail = "unavailable", ["repository_missing"]
            return res
        if not settings.repository_has_records():
            res.outcome, res.detail = "unavailable", ["repository_empty"]
            return res
        if not (settings.repository_dir / f"{stem}.json").exists() \
                and not (settings.repository_dir / f"{stem}.pdf").exists():
            return res
    except OSError as exc:
        res.outcome, res.detail = "unavailable", [f"repository_error:{type(exc).__name__}"]
        return res
    rec = ft.validate_record(settings.repository_dir, stem)
    if not isinstance(rec, ft.Record):
        res.detail.append(f"invalid:{rec}")
        return res
    hit, res.outcome, res.detail = _check_stored_record(rec, identity, settings,
                                                        remove_on_refusal=False)
    if hit is not None:
        res.hits.append(Hit(hit.data, "repository",
                            {"stem": stem, "source": rec.source, "source_ref": rec.source_ref},
                            rec.license))
    return res


def _check_stored_record(rec: ft.Record, identity: dict, settings: "Settings", *,
                         remove_on_refusal: bool) -> tuple[Hit | None, str, list[str]]:
    """The validation tail every stored record meets, after `validate_record`:
    the licence backstop, the read, then `check_pdf` against THIS run's
    identity. Returns (hit, "acquired", []) or (None, outcome, detail). With
    `remove_on_refusal` (a service copy) a refused or unreadable record is
    removed, so no record is left for the barrier to bind, and a passing
    one is a `stored` hit that keeps no bytes."""
    def refuse(outcome: str, detail: list[str]):
        if remove_on_refusal:
            _remove_copy(rec.json_path.parent, rec.stem)
        return None, outcome, detail
    if not _licensed(rec.license, settings.policy):
        return refuse("unlicensed", [f"licence {rec.license!r} not admitted by policy"])
    data, why = _read_local(str(rec.pdf_path))
    if data is None:
        return refuse("unavailable", [why, "removed_copy"] if remove_on_refusal else [why])
    ok, why = check_pdf(data, identity)
    if not ok:
        return refuse("rejected", [why])
    if remove_on_refusal:
        del data
        return Hit(b"", rec.source, rec.source_ref, rec.license, stored=True), "acquired", []
    return Hit(data, rec.source, rec.source_ref, rec.license), "acquired", []


# --------------------------------------------------------------------------
# Zotero
# --------------------------------------------------------------------------

class ZoteroUnavailable(Exception):
    pass


def zotero_file_path(location: str, url2pathname=urllib.request.url2pathname) -> tuple[str | None, str]:
    """The local path a Zotero `/file` Location names, or (None, reason).

    `url2pathname` decodes percent-escapes itself (on POSIX and on Windows),
    so the path is NOT unquoted first: a second decode would turn a file
    name holding a literal `%41` into `A`. Swappable so the Windows drive
    form (`nturl2path.url2pathname`) is testable on any platform.

    A share is refused however it is spelled: a host in the URL
    (`file://server/...`), or an empty host with a path that begins `//`
    (`file:////server/...`), in the raw path, in its decoded form
    (`%5C%5Cserver`) or in what `url2pathname` makes of it (`\\\\server`).
    `unquote` here only TESTS; the returned path is decoded once."""
    try:
        p = urlparse(location or "")
    except ValueError:
        return None, "bad_location"
    if p.scheme.lower() != "file":
        return None, "not_file_url"
    if p.netloc not in ("", "localhost"):
        return None, "unc_host"
    if not p.path:
        return None, "bad_location"
    if _unc_like(p.path) or _unc_like(unquote(p.path)):
        return None, "unc_host"
    try:
        path = url2pathname(p.path)
    except Exception:   # newer Pythons raise URLError on a host-like path
        return None, "unc_host"
    if _unc_like(path):
        return None, "unc_host"
    return path, "ok"


def _unc_like(path: str) -> bool:
    """A path naming a network share: it begins with two separators, either
    kind (`//server`, `\\\\server`, `/\\\\server`)."""
    return path.replace("\\", "/").startswith("//")


def _zotero_json(path: str, params: dict | None, deadline: Deadline):
    try:
        r = _http_get(ZOTERO_BASE + path, params=params,
                      timeout=deadline.clamp(ZOTERO_TIMEOUT) or 0.1, trust_env=False)
    except requests.RequestException as exc:
        raise ZoteroUnavailable(f"network:{type(exc).__name__}")
    if r.status_code != 200:
        raise ZoteroUnavailable(f"http_{r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise ZoteroUnavailable("bad_json")


def _item_year(item: dict) -> str:
    parsed = ((item.get("meta") or {}).get("parsedDate") or "")
    m = re.match(r"(\d{4})", str(parsed))
    if not m:
        m = re.search(r"\b(\d{4})\b", str((item.get("data") or {}).get("date") or ""))
    return m.group(1) if m else ""


def _item_surname(data: dict) -> str:
    creators = [c for c in (data.get("creators") or []) if isinstance(c, dict)]
    authors = [c for c in creators if c.get("creatorType") == "author"] or creators
    if not authors:
        return ""
    c = authors[0]
    return c.get("lastName") or c.get("name") or ""


def _surname_eq(a: str, b: str) -> bool:
    fa, fb = ft.fold(a), ft.fold(b)
    if not fa or not fb:
        return False
    return fa == fb or fa.split()[-1] == fb.split()[-1]


def zotero_item_matches(item: dict, identity: dict) -> bool:
    """The metadata gate before any attachment is read: DOI equal, or (when
    the item has no DOI) title phrase + first-creator surname + year."""
    data = item.get("data") or {}
    if data.get("itemType") in ("note", "annotation", "attachment"):
        return False
    doi = normalize_doi(identity.get("doi") or "")
    item_doi = normalize_doi(data.get("DOI") or "")
    if doi and item_doi:
        return doi == item_doi
    title = ft.clean_bibtex_str(identity.get("title") or "")
    surname = ft.clean_bibtex_str(identity.get("surname") or "")
    year = same_work_year(identity.get("year"))
    phrase = ft.title_phrase_cut(title)
    if not (phrase and surname and year):
        return False
    return (ft.fold(data.get("title") or "").startswith(phrase)
            and _surname_eq(_item_surname(data), surname)
            and _item_year(item) == year)


def source_zotero(identity: dict, settings: "Settings", deadline: Deadline) -> SourceResult:
    res = SourceResult("zotero", "not_found")
    if settings.licensed_only:
        res.outcome, res.detail = "disabled", ["licensed_only"]
        return res
    if not settings.zotero_on:
        res.outcome = "disabled"
        return res
    doi = normalize_doi(identity.get("doi") or "")
    title = ft.clean_bibtex_str(identity.get("title") or "")
    queries = [doi] if doi else []
    if title and identity.get("surname") and identity.get("year"):
        queries.append(ft.title_phrase_cut(title))
    checked = passed = 0
    try:
        matched, seen = [], set()
        for q in queries:
            if not q:
                continue
            items = _zotero_json("/items", {"q": q, "qmode": "everything", "itemType": "-attachment",
                                            "limit": ZOTERO_SEARCH_LIMIT}, deadline)
            for item in items if isinstance(items, list) else []:
                key = item.get("key") if isinstance(item, dict) else None
                if key and key not in seen and zotero_item_matches(item, identity):
                    seen.add(key)
                    matched.append((key, item.get("data") or {}))
            if matched:
                break
        for key, idata in matched:
            # A DOI-matched item supplies a title and surname the caller did
            # not give, for the PDF check's title fallback only (a PDF that
            # does not print its DOI). The sidecar keeps the caller's identity;
            # the barrier re-checks against the bib entry.
            check_identity = dict(identity)
            if not check_identity.get("title"):
                check_identity["title"] = idata.get("title") or ""
            if not check_identity.get("surname"):
                check_identity["surname"] = _item_surname(idata)
            children = _zotero_json(f"/items/{quote(key)}/children", None, deadline)
            for child in children if isinstance(children, list) else []:
                cdata = (child or {}).get("data") or {}
                if cdata.get("itemType") != "attachment" or cdata.get("contentType") != "application/pdf":
                    continue
                att = child.get("key")
                if deadline.expired():
                    res.detail.append("deadline")
                    return _finish(res, checked, passed)
                try:
                    r = _http_get(f"{ZOTERO_BASE}/items/{quote(att)}/file",
                                  timeout=deadline.clamp(ZOTERO_TIMEOUT) or 0.1, trust_env=False)
                except requests.RequestException as exc:
                    raise ZoteroUnavailable(f"network:{type(exc).__name__}")
                if r.status_code != 302:
                    res.detail.append(f"{att}:no_file:http_{r.status_code}")
                    continue
                path, why = zotero_file_path(r.headers.get("Location") or "")
                if path is None:
                    res.detail.append(f"{att}:{why}")
                    continue
                data, why = _read_local(path)
                if data is None:
                    res.detail.append(f"{att}:{why}")
                    continue
                checked += 1
                ok, why = check_pdf(data, check_identity)
                if ok:
                    passed += 1
                    if not res.hits:
                        res.hits.append(Hit(data, "zotero", f"zotero:{key}/{att}", None))
                else:
                    res.detail.append(f"{att}:{why}")
    except ZoteroUnavailable as exc:
        if not res.hits:
            res.outcome, res.detail = "unavailable", res.detail + [str(exc)]
            return res
    return _finish(res, checked, passed)


# --------------------------------------------------------------------------
# PDF folder and its index
# --------------------------------------------------------------------------

def index_path(folder: Path) -> Path:
    key = os.path.normcase(os.path.normpath(os.path.abspath(str(folder))))
    return Path(PDF_INDEX_DIR) / (hashlib.sha256(key.encode("utf-8")).hexdigest()[:16] + ".json")


def _index_read_file(path: str) -> dict:
    """DOIs on pages 1-3 and folded heads of pages 1-5. Read with pypdf
    directly, not `fulltext.extract_pages`: that extracts every page (slow on
    a book) and rejects short texts, which an index must not."""
    try:
        if os.path.getsize(path) > LOCAL_MAX_BYTES:
            return {"error": "too_large"}
        from pypdf import PdfReader
        with open(path, "rb") as f:
            reader = PdfReader(f)
            if reader.is_encrypted and not reader.decrypt(""):
                return {"error": "encrypted"}
            pages = [reader.pages[i].extract_text() or ""
                     for i in range(min(INDEX_PAGES, len(reader.pages)))]
    except Exception:
        return {"error": "unreadable"}
    dois = sorted({d.lower().rstrip(".,;)") for d in ft.DOI_RE.findall("\n".join(pages[:INDEX_DOI_PAGES]))})
    return {"dois": dois, "heads": [ft.fold(p)[:INDEX_HEAD_CHARS] for p in pages]}


def _name_words(name: str) -> str:
    """A file name split for surname matching: camel case and letter/digit
    boundaries become spaces (`Smith2019` -> `smith 2019`)."""
    stem = Path(name).stem
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)
    folded = ft.fold(stem)
    return re.sub(r"(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])", " ", folded)


class FolderIndex:
    """The cached, incremental index of one PDF folder (a superset filter)."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.path = index_path(folder)
        self.entries: dict[str, dict] = {}
        self.files: list[str] = []   # every PDF the walk saw, relative posix paths
        self.notes: list[str] = []
        self.unreadable: list[str] = []
        self.refreshed = False

    def _load(self) -> None:
        try:
            data = json.loads(ft.read_text(self.path))
        except (OSError, ValueError):
            return
        if (isinstance(data, dict) and data.get("schema") == INDEX_SCHEMA
                and data.get("folder") == os.path.normcase(os.path.normpath(os.path.abspath(str(self.folder))))
                and isinstance(data.get("files"), dict)):
            self.entries = {k: v for k, v in data["files"].items() if isinstance(v, dict)}

    def _walk(self) -> dict[str, tuple[int, float]]:
        """Every PDF under the folder. A directory that cannot be listed is
        recorded in `self.unreadable` (relative posix paths, "." for the
        folder itself), never skipped silently."""
        found, count = {}, 0
        self.unreadable = []

        def onerror(err: OSError) -> None:
            where = err.filename or str(self.folder)
            self.unreadable.append(Path(os.path.relpath(where, self.folder)).as_posix())
        for root, dirs, names in os.walk(self.folder, followlinks=False, onerror=onerror):
            dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
            for name in sorted(names):
                count += 1
                if count > MAX_WALK_FILES:
                    self.notes.append("walk_limit")
                    return found
                full = os.path.join(root, name)
                if not name.lower().endswith(".pdf") or os.path.islink(full):
                    continue
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                rel = Path(os.path.relpath(full, self.folder)).as_posix()
                found[rel] = (st.st_size, st.st_mtime)
        return found

    def refresh(self, budget: Deadline) -> None:
        if self.refreshed:
            return
        self.refreshed = True
        self._load()
        found = self._walk()
        self.files = sorted(found)
        changed, new = [], []
        for rel, (size, mtime) in found.items():
            e = self.entries.get(rel)
            if e is None:
                new.append(rel)
            elif e.get("size") != size or e.get("mtime") != mtime:
                del self.entries[rel]   # stale: matches by file name until re-read
                changed.append(rel)
        dirty = bool(changed)
        if self.unreadable:
            self.notes.append(f"walk_error:{len(self.unreadable)}")
        for rel in [r for r in self.entries if r not in found]:
            if self._under_unreadable(rel):
                # Not seen because its directory could not be listed: keep the
                # cached entry, and keep the file a candidate (a failed read
                # of it is reported like any other).
                self.files.append(rel)
                continue
            del self.entries[rel]
            dirty = True
        self.files.sort()
        queue = sorted(changed) + sorted(new)
        done = 0
        for rel in queue:
            if budget.expired():
                break
            size, mtime = found[rel]
            entry = _index_read_file(str(self.folder / rel))
            entry.update({"size": size, "mtime": mtime})
            self.entries[rel] = entry
            done += 1
            dirty = True
        if done < len(queue):
            self.notes.append(f"index_incomplete:{len(queue) - done}")
        if dirty:
            self._save()

    def _under_unreadable(self, rel: str) -> bool:
        return any(d == "." or rel.startswith(d + "/") for d in self.unreadable)

    def _save(self) -> None:
        payload = {"schema": INDEX_SCHEMA,
                   "folder": os.path.normcase(os.path.normpath(os.path.abspath(str(self.folder)))),
                   "updated_at": _now_iso(), "files": self.entries}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            ft.write_text_atomic(self.path, json.dumps(payload, ensure_ascii=False))
        except OSError:
            self.notes.append("index_write_failed")

    def candidates(self, identity: dict) -> list[str]:
        """DOI matches, then file-name surname matches, then page-head title
        matches; each group by path; no repeats."""
        doi = normalize_doi(identity.get("doi") or "")
        surname = ft.fold(ft.clean_bibtex_str(identity.get("surname") or ""))
        title = ft.clean_bibtex_str(identity.get("title") or "")
        phrases = {p for p in (ft.title_phrase(title), ft.title_phrase_cut(title)) if p}
        by_doi = sorted(r for r, e in self.entries.items() if doi and doi in (e.get("dois") or []))
        by_name = [r for r in self.files
                   if surname and f" {surname} " in f" {_name_words(Path(r).name)} "]
        by_head = sorted(r for r, e in self.entries.items()
                         if any(p in h for h in (e.get("heads") or []) for p in phrases))
        out, seen, present = [], set(), set(self.files)
        for r in by_doi + by_name + by_head:
            if r not in seen and r in present:
                seen.add(r)
                out.append(r)
        return out


def source_folder(identity: dict, settings: "Settings", deadline: Deadline) -> SourceResult:
    res = SourceResult("folder", "not_found")
    if settings.licensed_only:
        res.outcome, res.detail = "disabled", ["licensed_only"]
        return res
    if settings.pdf_dir is None:
        res.outcome = "disabled"
        return res
    if not settings.pdf_dir.is_dir():
        res.outcome, res.detail = "unavailable", ["folder_missing"]
        return res
    idx = settings.folder_index()
    idx.refresh(Deadline(deadline.clamp(settings.index_budget)))
    res.detail.extend(idx.notes)
    cands = idx.candidates(identity)
    if len(cands) > MAX_CANDIDATES:
        res.detail.append(f"candidate_limit:{len(cands)}")
    checked = passed = 0
    for rel in cands[:MAX_CANDIDATES]:
        if deadline.expired():
            res.detail.append("deadline")
            break
        data, why = _read_local(str(settings.pdf_dir / rel))
        if data is None:
            res.detail.append(f"{rel}:{why}")
            continue
        checked += 1
        ok, why = check_pdf(data, identity)
        if ok:
            passed += 1
            if not res.hits:
                # The file name only: the sidecar is delivered with the review.
                res.hits.append(Hit(data, "folder", f"folder:{Path(rel).name}", None))
        else:
            res.detail.append(f"{rel}:{why}")
    return _finish(res, checked, passed)


# --------------------------------------------------------------------------
# Open access: OpenAlex, Semantic Scholar
# --------------------------------------------------------------------------

def policy_from_env(licensed_only: bool) -> str | None:
    """The licence policy: "open", "cc" or None (no filter), from os.environ
    now. It fails closed: a POLICY value other than `open` is "cc", so a
    misspelt value never removes the filter."""
    raw = os.environ.get(POLICY_ENV, "").strip().lower()
    if raw == "open":
        return "open"
    if raw:
        return "cc"
    return "cc" if licensed_only else None


def _licensed(lic, policy: str | None) -> bool:
    """The one licence rule. No policy admits everything; "cc" admits cc*;
    "open" also admits oa:* and upload."""
    if policy is None:
        return True
    if not isinstance(lic, str):
        return False
    lic = lic.strip().lower()
    if lic.startswith("cc"):
        return True
    return policy == "open" and (lic.startswith("oa:") or lic == "upload")


def _api_get(url, *, headers, params, limiter, deadline: Deadline, openalex: bool):
    """(json | None, reason): a metadata call with a short retry on 429/5xx."""
    backoff = ExponentialBackoff(max_attempts=3, max_delay=10.0)
    for attempt in range(backoff.max_attempts):
        if deadline.expired():
            return None, "deadline"
        limiter.wait()
        try:
            r = _http_get(url, headers=headers, params=params, timeout=deadline.clamp(API_TIMEOUT) or 0.1)
        except requests.RequestException as exc:
            if attempt < backoff.max_attempts - 1 and backoff.wait(attempt):
                continue
            return None, f"network:{type(exc).__name__}"
        if r.status_code == 200:
            try:
                return r.json(), "ok"
            except ValueError:
                return None, "bad_json"
        if r.status_code == 404:
            return None, "not_found"
        if r.status_code == 429 and openalex and openalex_budget_exhausted(r):
            return None, "budget_exhausted"
        if (r.status_code == 429 or r.status_code >= 500) and backoff.wait(
                attempt, retry_after=parse_retry_after(r.headers.get("Retry-After"))):
            continue
        return None, f"http_{r.status_code}"
    return None, "retries_exhausted"


def openalex_locations(doi: str, deadline: Deadline) -> tuple[list | None, str]:
    """[(pdf_url, licence)], best_oa_location first, without repeats."""
    data, why = _api_get(f"{OPENALEX_BASE}/works/doi:{quote(doi, safe='/')}",
                         headers={**openalex_headers(), "User-Agent": user_agent()},
                         params=openalex_params(os.environ.get("OPENALEX_EMAIL", "")),
                         limiter=get_limiter("openalex"), deadline=deadline, openalex=True)
    if data is None:
        return None, why
    locs = [data.get("best_oa_location")] + list(data.get("locations") or [])
    out, seen = [], set()
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        url = loc.get("pdf_url")
        if isinstance(url, str) and url and url not in seen:
            seen.add(url)
            out.append((url, loc.get("license")))
    return out, "ok"


def s2_locations(doi: str, deadline: Deadline) -> tuple[list | None, str]:
    key = os.environ.get("S2_API_KEY", "").strip()
    headers = {"User-Agent": user_agent()}
    if key:
        headers["x-api-key"] = key
    data, why = _api_get(f"{S2_BASE_URL}/paper/DOI:{quote(doi, safe='/')}",
                         headers=headers, params={"fields": "openAccessPdf"},
                         limiter=get_limiter("semantic_scholar", authenticated=bool(key)),
                         deadline=deadline, openalex=False)
    if data is None:
        return None, why
    oa = data.get("openAccessPdf")
    if isinstance(oa, dict) and isinstance(oa.get("url"), str) and oa["url"]:
        return [(oa["url"], oa.get("license"))], "ok"
    return [], "ok"


def _source_oa(name: str, locate, identity: dict, settings: "Settings", deadline: Deadline) -> SourceResult:
    res = SourceResult(name, "not_found")
    if settings.request_dir is not None:
        res.outcome, res.detail = "disabled", ["service"]
        return res
    doi = normalize_doi(identity.get("doi") or "")
    if not doi:
        res.outcome = "no_doi"
        return res
    locs, why = locate(doi, deadline)
    if locs is None:
        if why == "not_found":
            return res
        res.outcome, res.detail = ("deadline", []) if why == "deadline" else ("unavailable", [why])
        return res
    if settings.policy is not None:
        unlicensed = [u for u, lic in locs if not _licensed(lic, settings.policy)]
        locs = [(u, lic) for u, lic in locs if _licensed(lic, settings.policy)]
        if unlicensed and not locs:
            res.outcome, res.detail = "unlicensed", [f"{len(unlicensed)} location(s) not admitted by policy"]
            return res
    checked = passed = 0
    for url, lic in locs:
        if deadline.expired():
            res.detail.append("deadline")
            break
        data, why = download_pdf(url, deadline)
        if data is None:
            res.detail.append(f"{url}:{why}")
            continue
        checked += 1
        ok, why = check_pdf(data, identity)
        if ok:
            passed += 1
            res.hits.append(Hit(data, name, url, lic if isinstance(lic, str) else None))
            break   # OA locations are tried until the first passes
        res.detail.append(f"{url}:{why}")
    return _finish(res, checked, passed)


def source_openalex(identity, settings, deadline):
    return _source_oa("openalex", openalex_locations, identity, settings, deadline)


def source_s2(identity, settings, deadline):
    return _source_oa("s2", s2_locations, identity, settings, deadline)


SOURCE_ORDER = ("repository", "zotero", "folder", "openalex", "s2", "service")
LOCAL_SOURCES = SOURCE_ORDER[:-1]   # the ones _SOURCES maps, tried per work
_SOURCES = {"repository": source_repository, "zotero": source_zotero, "folder": source_folder,
            "openalex": source_openalex, "s2": source_s2}


# --------------------------------------------------------------------------
# Settings, store and the single-work pipeline
# --------------------------------------------------------------------------

@dataclass
class Settings:
    licensed_only: bool
    policy: str | None
    zotero_on: bool
    pdf_dir: Path | None
    index_budget: float
    repository_dir: Path | None = None
    request_dir: Path | None = None
    _index: FolderIndex | None = None
    _repository_has_records: bool | None = None

    def folder_index(self) -> FolderIndex:
        if self._index is None:
            self._index = FolderIndex(self.pdf_dir)
        return self._index

    def repository_has_records(self) -> bool:
        """Whether the repository holds any `*.json` entry, listed once per
        run and stopping at the first. Raises OSError (never cached)."""
        if self._repository_has_records is None:
            with os.scandir(self.repository_dir) as it:
                self._repository_has_records = any(e.name.endswith(".json") for e in it)
        return self._repository_has_records


def settings_from_env(licensed_only: bool, policy: str | None, index_budget: float) -> Settings:
    raw = os.environ.get(PDF_DIR_ENV, "").strip().strip("\"'").strip()
    pdf_dir = Path(os.path.expanduser(raw)).resolve() if raw else None
    raw = os.environ.get(REPOSITORY_DIR_ENV, "").strip().strip("\"'").strip()
    repository_dir = Path(os.path.expanduser(raw)).resolve() if raw else None
    raw = os.environ.get(REQUEST_DIR_ENV, "").strip().strip("\"'").strip()
    request_dir = Path(os.path.expanduser(raw)).resolve() if raw else None
    return Settings(licensed_only=licensed_only, policy=policy, zotero_on=_on(os.environ.get(ZOTERO_ENV)),
                    pdf_dir=pdf_dir, index_budget=index_budget, repository_dir=repository_dir,
                    request_dir=request_dir)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def store_state(store: Path, slug: str, canon: str):
    """("absent"|"collision"|"exists"|"invalid", Record | reason | None).
    Collision is decided on the RAW sidecar first: validate_record folds a
    sidecar naming another identity into `bad_slug`, which must never be
    treated as replaceable."""
    jp, pp = store / f"{slug}.json", store / f"{slug}.pdf"
    if not jp.exists() and not pp.exists():
        return "absent", None
    try:
        data = json.loads(ft.read_text(jp))
        ident = data.get("identity") if isinstance(data, dict) else None
        if isinstance(ident, dict):
            try:
                other = ft.canonical_identity(ident)
            except ValueError:
                other = None
            if other is not None and other != canon:
                return "collision", other
    except (OSError, ValueError):
        pass
    rec = ft.validate_record(store, slug)
    if isinstance(rec, ft.Record):
        return "exists", rec
    return "invalid", rec


def write_record(store: Path, slug: str, identity: dict, hit: Hit) -> None:
    store.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(store / f"{slug}.pdf", hit.data)
    sidecar = {"schema": ft.SCHEMA, "slug": slug, "identity": identity,
               "source": hit.source, "source_ref": hit.source_ref, "license": hit.license,
               "pdf_sha256": hashlib.sha256(hit.data).hexdigest(), "acquired_at": _now_iso()}
    ft.write_text_atomic(store / f"{slug}.json", json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n")
    rec = ft.validate_record(store, slug)
    if not isinstance(rec, ft.Record):
        raise RuntimeError(f"written record {slug} does not validate: {rec}")


def make_identity(doi=None, title=None, surname=None, year=None) -> dict:
    """The stored identity (the sidecar's `identity`)."""
    def clean(v):
        v = (v or "").strip() if isinstance(v, str) else v
        return v or None
    nd = normalize_doi(doi or "")
    return {"doi": nd or None, "title": clean(title), "surname": clean(surname),
            "year": None if year is None or str(year).strip() == "" else str(year).strip()}


@dataclass
class Attempt:
    """One work's pass: what `begin` decided and found, for `finish`. `out`
    is set when the call was decided before any source (refused, exists);
    `store_notes` are store rows `finish` puts first in `tried`."""
    identity: dict
    slug: str
    store: Path
    invalid: str | None
    results: list[SourceResult]
    out: dict | None
    store_notes: list[dict] = field(default_factory=list)

    @property
    def open(self) -> bool:
        """Undecided and without a hit: the service channel is still to ask."""
        return self.out is None and not any(r.hits for r in self.results)


def _refused_service_copy(rec: ft.Record, settings: Settings) -> bool:
    """A stored record the service copied (`source_ref.service` true at the
    top level) whose licence the policy refuses. A repository record nests
    the original ref inside its own, so it is never one."""
    ref = rec.source_ref
    return (isinstance(ref, dict) and ref.get("service") is True
            and not _licensed(rec.license, settings.policy))


def begin(workdir: Path, identity: dict, settings: Settings, deadline: Deadline,
          pdf_path: str | None = None) -> Attempt:
    """The store checks, then `--pdf` or the local sources in order. A
    stored service copy meets the licence rule again (a copy that landed
    after an earlier run's arrival check is checked here, on the next run):
    a refused one is removed and the work tried as absent, or, when the
    removal fails, the call is `refused` (`unlicensed_remove_failed`) and
    no source runs. Its identity is the barrier's check."""
    slug = ft.slug_for(identity)
    canon = ft.canonical_identity(identity)
    store = Path(workdir) / ft.STORE_REL
    attempt = Attempt(identity, slug, store, None, [], None)
    if not ft.path_budget_ok(workdir):
        attempt.out = {"status": "refused", "slug": slug, "source": None,
                       "tried": [{"source": "store", "outcome": "path_too_long"}]}
        return attempt
    state, info = store_state(store, slug, canon)
    if state == "exists" and _refused_service_copy(info, settings):
        try:
            _remove_copy(store, slug)
        except OSError as exc:
            attempt.out = {"status": "refused", "slug": slug, "source": None,
                           "tried": [{"source": "store",
                                      "outcome": f"unlicensed_remove_failed:{type(exc).__name__}"}]}
            return attempt
        attempt.store_notes.append({"source": "store", "outcome": "unlicensed_removed"})
        state, info = "absent", None
    if state == "collision":
        attempt.out = {"status": "refused", "slug": slug, "source": None,
                       "tried": [{"source": "store", "outcome": "slug_collision", "detail": [info]}]}
        return attempt
    if state == "exists":
        attempt.out = {"status": "exists", "slug": slug, "source": info.source,
                       "tried": [{"source": "store", "outcome": "exists"}]}
        return attempt
    attempt.invalid = info if state == "invalid" else None

    if pdf_path is not None:
        res = SourceResult("user", "not_found")
        data, why = _read_local(pdf_path)
        if data is None:
            res.detail.append(why)
        else:
            ok, why = check_pdf(data, identity)
            if ok:
                res.outcome = "acquired"
                res.hits.append(Hit(data, "user", f"user:{Path(pdf_path).name}", None))
            else:
                res.outcome, res.detail = "rejected", [why]
        attempt.results.append(res)
        return attempt
    for name in LOCAL_SOURCES:
        if deadline.expired():
            attempt.results.append(SourceResult(name, "deadline"))
            continue
        res = _SOURCES[name](identity, settings, deadline)
        attempt.results.append(res)
        if res.hits:
            break
    return attempt


def _remove_copy(store: Path, slug: str) -> None:
    """Remove a service copy the licence backstop, the read or the identity
    check refused, sidecar first, so no record is left for the barrier to
    bind."""
    for suffix in (".json", ".txt", ".pdf"):
        (store / f"{slug}{suffix}").unlink(missing_ok=True)


def _service_result(store: Path, slug: str, identity: dict, entry: dict | None,
                    settings: Settings, invalid: str | None = None,
                    complete: bool = False) -> SourceResult:
    """One requested key's arrival check: the record at OUR slug, validated
    as if downloaded here, whatever the response says. For `found`, a
    differing stem is only a detail. For any other answer (or none), a file
    at the slug is a copy that arrived without its answer: it is checked
    the same way, and a passing one is a hit noted
    `copied_after_response:<outcome>`. A record `begin` already knew as
    invalid (`invalid`) is left untouched, so `invalid_kept` keeps its
    meaning. A copy that fails `validate_record` is left (the barrier
    withholds it) with the detail `copy_invalid:<reason>`. `complete`: the
    response was complete, so a missing entry is `no_outcome`."""
    outcome, detail = fc.source_outcome(entry, complete=complete)
    res = SourceResult("service", outcome, detail)
    note = []
    if outcome == "acquired":
        res.outcome = "unavailable"
        if entry.get("stem") != slug:
            res.detail.append("stem_mismatch")
    elif invalid is not None or not ((store / f"{slug}.json").exists()
                                     or (store / f"{slug}.pdf").exists()):
        return res
    else:
        note = [f"copied_after_response:{outcome}"]
    rec = ft.validate_record(store, slug)
    if not isinstance(rec, ft.Record):
        res.detail.append(f"copy_invalid:{rec}")
        return res
    hit, res.outcome, more = _check_stored_record(rec, identity, settings, remove_on_refusal=True)
    res.detail.extend(note + more)
    if hit is not None:
        res.hits.append(hit)
    return res


def _unchecked_result(store: Path, slug: str, entry: dict | None, invalid: str | None,
                      complete: bool) -> SourceResult:
    """A slug the deadline reached before its arrival check: `deadline`. A
    copy the engine could not check must not reach the barrier, so a
    sidecar or PDF at the slug is removed (`unchecked_copy_removed`,
    `remove_failed:<error>` when that fails); the repository still holds
    the work for the next review. A record `begin` knew as invalid is left
    alone under `_service_result`'s rule."""
    res = SourceResult("service", "deadline")
    outcome, _ = fc.source_outcome(entry, complete=complete)
    if outcome != "acquired" and invalid is not None:
        return res
    if not ((store / f"{slug}.json").exists() or (store / f"{slug}.pdf").exists()):
        return res
    res.detail.append("unchecked_copy_removed")
    try:
        _remove_copy(store, slug)
    except OSError as exc:
        res.detail.append(f"remove_failed:{type(exc).__name__}")
    return res


def _wait_bound(deadline: Deadline, n_sent: int) -> float:
    """The seconds the service wait may take: it ends SERVICE_WAIT_MARGIN
    plus ARRIVAL_CHECK_SECONDS per identity sent before the deadline (an
    endless deadline counts as SINGLE_DEADLINE)."""
    left = SINGLE_DEADLINE if deadline.end is None else deadline.left()
    return max(0.0, left - (SERVICE_WAIT_MARGIN + ARRIVAL_CHECK_SECONDS * n_sent))


def _close_requests(request_dir: Path, written: list) -> dict[str, list[str]]:
    """Write `<id>.closed` for every written request; a failed write is the
    detail `closed_write_failed:<error>` of that request's keys."""
    notes = {}
    for request_id, _ in written:
        try:
            fc.write_closed(request_dir, request_id)
        except OSError as exc:
            notes[request_id] = [f"closed_write_failed:{type(exc).__name__}"]
    return notes


def service_fetch(store: Path, pending: list[tuple[str, dict, str | None]], settings: Settings,
                  deadline: Deadline, mode: str) -> dict[str, SourceResult]:
    """Ask the service channel for `pending` [(slug, identity, invalid)]
    (`invalid`: the reason `begin` found the stored record invalid, or
    None); returns a `service` SourceResult for every slug. DOI identities
    only are sent, in requests of at most `fc.MAX_PER_REQUEST`, and only
    when the request directory exists (else `request_dir_missing`: the
    worker creates it, so there is no worker). All are written first, then
    waited on together until `_wait_bound`, then every written request is
    closed (also when the wait raises), then every requested slug's store
    record is checked (`_service_result`), or, once the deadline has
    passed, its copy removed unchecked (`_unchecked_result`). One slug's
    crashing check is that slug's `unavailable` (`error:...`) and its copy
    is removed."""
    if settings.request_dir is None:
        return {slug: SourceResult("service", "disabled") for slug, _, _ in pending}
    out: dict[str, SourceResult] = {}
    sendable = []
    for slug, identity, invalid in pending:
        if not normalize_doi(identity.get("doi") or ""):
            out[slug] = SourceResult("service", "no_doi")
            continue
        try:
            sendable.append((slug, identity, invalid, fc.identity_payload(identity)))
        except ValueError as exc:
            out[slug] = SourceResult("service", "unavailable", [str(exc)])
    try:
        has_worker = settings.request_dir.is_dir()
    except OSError:
        has_worker = False
    if not has_worker:   # the worker creates the directory; the engine never does
        for slug, *_ in sendable:
            out[slug] = SourceResult("service", "unavailable", ["request_dir_missing"])
        return out
    written, n_sent = [], 0
    try:
        for i in range(0, len(sendable), fc.MAX_PER_REQUEST):
            chunk = sendable[i:i + fc.MAX_PER_REQUEST]
            if _wait_bound(deadline, n_sent + len(chunk)) <= 0:
                for slug, *_ in sendable[i:]:
                    out[slug] = SourceResult("service", "deadline")
                break
            request_id = fc.new_request_id(mode)
            try:
                fc.write_request(settings.request_dir, request_id, mode, [c[3] for c in chunk])
            except (OSError, ValueError) as exc:
                reason = (str(exc) if isinstance(exc, ValueError) else "") or type(exc).__name__
                for slug, *_ in chunk:
                    out[slug] = SourceResult("service", "unavailable", [f"request_write_failed:{reason}"])
                continue
            written.append((request_id, chunk))
            n_sent += len(chunk)
        responses = fc.wait_for_responses(settings.request_dir, [rid for rid, _ in written],
                                          _wait_bound(deadline, n_sent), clock=_clock, sleep=_sleep)
    finally:
        closed_notes = _close_requests(settings.request_dir, written)
    for request_id, chunk in written:
        outcomes = responses[request_id]["outcomes"]
        complete = responses[request_id]["complete"]
        for slug, identity, invalid, payload in chunk:
            entry = outcomes.get(payload["key"])
            try:
                if deadline.expired():
                    res = _unchecked_result(store, slug, entry, invalid, complete)
                else:
                    res = _service_result(store, slug, identity, entry, settings, invalid,
                                          complete)
            except Exception as exc:   # one slug's check never sinks the others
                res = SourceResult("service", "unavailable", [f"error:{type(exc).__name__}: {exc}"])
                try:
                    _remove_copy(store, slug)
                except OSError as rexc:
                    res.detail.append(f"remove_failed:{type(rexc).__name__}")
            res.detail.extend(closed_notes.get(request_id, []))
            out[slug] = res
    return out


def finish(attempt: Attempt, service: SourceResult | None) -> dict:
    """Store the winner, if any, and build {status, slug, source, tried}."""
    if attempt.out is not None:
        return attempt.out
    results = list(attempt.results)
    if service is not None and not any(r.hits for r in results):
        results.append(service)
    winner = next((r for r in results if r.hits), None)
    tried = list(attempt.store_notes) + [r.tried() for r in results]
    out = {"status": None, "slug": attempt.slug, "source": None, "tried": tried}
    if winner is not None:
        # A stored service copy is the validated record (hash matched,
        # licence and identity checked, this run's identity written by the
        # worker); every other hit is written here.
        if not winner.hits[0].stored:
            write_record(attempt.store, attempt.slug, attempt.identity, winner.hits[0])
        if attempt.invalid:
            tried.insert(0, {"source": "store", "outcome": f"invalid_replaced:{attempt.invalid}"})
        out.update(status="acquired", source=winner.hits[0].source)
        return out
    if attempt.invalid:
        tried.insert(0, {"source": "store", "outcome": f"invalid_kept:{attempt.invalid}"})
    out["status"] = "rejected" if any(r.outcome == "rejected" for r in results) else "not_found"
    return out


def acquire_one(workdir: Path, identity: dict, settings: Settings, deadline: Deadline,
                pdf_path: str | None = None) -> dict:
    """Run the single-work pipeline; returns {status, slug, source, tried}."""
    attempt = begin(workdir, identity, settings, deadline, pdf_path)
    service = None
    if attempt.open and pdf_path is None:
        service = service_fetch(attempt.store, [(attempt.slug, identity, attempt.invalid)], settings,
                                deadline, "single")[attempt.slug]
    return finish(attempt, service)


# --------------------------------------------------------------------------
# --gaps
# --------------------------------------------------------------------------

def gap_candidates(workdir: Path, n_domains: int, title_route: bool):
    """([(domain, key, stored identity)], {domain: "present"|"missing"|"unreadable"})."""
    out, domains = [], {}
    for i in range(1, n_domains + 1):
        bib = workdir / f"literature-domain-{i}.bib"
        try:
            text = ft.read_text(bib)
        except FileNotFoundError:
            domains[str(i)] = "missing"
            continue
        except (OSError, ValueError):
            domains[str(i)] = "unreadable"
            continue
        domains[str(i)] = "present"
        for chunk in split_entries(text):
            if is_verbatim_block(chunk):
                continue
            header = entry_header(chunk)
            if header is None:
                continue
            fields = parse_entry_fields(chunk)
            if (fields.get("abstract") or "").strip():
                continue
            doi = normalize_doi(fields.get("doi") or "")
            doi = doi if _doi_ok(doi) else ""
            title = fields.get("title") or ""
            surname = first_author_surname(fields.get("author") or "", fields.get("editor") or "")
            year = fields.get("year") or ""
            if doi or (title_route and title.strip() and surname.strip() and year.strip()):
                out.append((i, header[1], make_identity(doi, title, surname, year)))
    return out, domains


_FOLDER_NOTE_TEXT = {
    "walk_error": "directories PhilLit could not read",
    "walk_limit": "stopped at {limit} files",
    "index_incomplete": "files not yet indexed, matched by file name only",
    "index_write_failed": "the index cache could not be saved",
}


def _folder_warnings(settings: Settings) -> list[str]:
    """The folder index's run-level notes, once each, for the summary line:
    an operator reads that line, not each entry's `tried` detail."""
    idx = settings._index
    out = []
    for note in (idx.notes if idx is not None else []):
        text = _FOLDER_NOTE_TEXT.get(note.split(":", 1)[0], "").format(limit=MAX_WALK_FILES)
        line = f"folder: {note}" + (f" ({text})" if text else "")
        if line not in out:
            out.append(line)
    return out


def run_gaps(workdir: Path, n_domains: int, settings: Settings) -> dict:
    started = _clock()
    deadline = Deadline(GAPS_DEADLINE)
    title_route = settings.repository_dir is not None or (
        not settings.licensed_only and (settings.zotero_on or settings.pdf_dir is not None))
    cands, domains = gap_candidates(workdir, n_domains, title_route)

    def crashed(row, exc):   # one entry's crash never sinks the pass
        row.update(outcome="error", source=None,
                   tried=[{"source": "pipeline", "outcome": f"error:{type(exc).__name__}: {exc}"}])

    entries, by_slug, attempts, duplicates = [], {}, [], []
    for domain, key, ident in cands:
        row = {"domain": domain, "key": key}
        try:
            slug = ft.slug_for(ident)
        except ValueError:
            row.update(slug=None, outcome="refused", source=None,
                       tried=[{"source": "store", "outcome": "bad_identity"}])
            entries.append(row)
            continue
        row.update(slug=slug, outcome=None, source=None, tried=[])
        if slug in by_slug:
            first = by_slug[slug]
            row["tried"] = [{"source": "store", "outcome": f"same_work_as:{first['domain']}/{first['key']}"}]
            duplicates.append((row, first))
        elif deadline.expired():
            row["outcome"] = "not_attempted"
        else:
            # A decided entry or a local hit is finished (stored) at once, so
            # its record is on disk before the service wait and its PDF bytes
            # are not held; only open entries wait for the service.
            try:
                attempt = begin(workdir, ident, settings, deadline)
                if attempt.open:
                    attempts.append((row, attempt))
                else:
                    res = finish(attempt, None)
                    row.update(outcome=res["status"], source=res["source"], tried=res["tried"])
            except Exception as exc:
                crashed(row, exc)
            by_slug[slug] = row
        entries.append(row)
    # One service request for every entry the local sources left open.
    pending = [(a.slug, a.identity, a.invalid) for _, a in attempts]
    try:
        service = service_fetch(workdir / ft.STORE_REL, pending, settings, deadline, "gaps")
    except Exception as exc:
        for row, _ in attempts:
            crashed(row, exc)
        attempts, service = [], {}
    for row, attempt in attempts:
        try:
            res = finish(attempt, service.get(attempt.slug))
            row.update(outcome=res["status"], source=res["source"], tried=res["tried"])
        except Exception as exc:
            crashed(row, exc)
    for row, first in duplicates:
        row.update(outcome=first["outcome"], source=first["source"])
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["outcome"]] = counts.get(e["outcome"], 0) + 1
    # An entry that crashed is named in the summary itself, never only
    # counted: the orchestrator reads the summary line, not the report.
    # A duplicate row (same_work_as) names the first row's real reason.
    errors = []
    for e in entries:
        if e["outcome"] != "error":
            continue
        src = by_slug.get(e["slug"], e)
        errors.append({"entry": f"{e['domain']}/{e['key']}",
                       "reason": src["tried"][0]["outcome"] if src["tried"] else "error"})
    warnings = _folder_warnings(settings)
    report = {"schema": 1, "status": "done_with_errors" if errors else "done",
              "generated_at": _now_iso(), "deadline_seconds": GAPS_DEADLINE,
              "elapsed_seconds": round(_clock() - started, 1),
              "licensed_only": settings.licensed_only,
              "policy": settings.policy,
              "sources": {"zotero": "on" if settings.zotero_on and not settings.licensed_only else "off",
                          "folder": "on" if settings.pdf_dir is not None and not settings.licensed_only else "off",
                          "repository": "on" if settings.repository_dir is not None else "off",
                          "service": "on" if settings.request_dir is not None else "off"},
              "domains": domains, "candidates": len(entries), "counts": counts, "errors": errors, "warnings": warnings,
              "entries": entries}
    path = workdir / REPORT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    ft.write_text_atomic(path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Acquire a work's PDF into the full-text store")
    ap.add_argument("workdir", help="The review working directory")
    ap.add_argument("--doi", help="The work's DOI")
    ap.add_argument("--title", help="The work's title")
    ap.add_argument("--author", help="The first author's full surname as a bib holds it, "
                                     "particles included (e.g. 'van Fraassen')")
    ap.add_argument("--year", help="The publication year")
    ap.add_argument("--pdf", help="A PDF the user handed over (replaces the source search)")
    ap.add_argument("--gaps", action="store_true",
                    help="Try every domain-bib entry without an abstract")
    ap.add_argument("--domains", type=int, help="Number of domain bibs (with --gaps)")
    return ap


def main(argv=None) -> int:
    # The service policy is read from the PROCESS environment BEFORE .env is
    # loaded (load_dotenv(override=True) would replace it) and never re-read.
    licensed_only = _on(os.environ.get(LICENSED_ONLY_ENV))
    policy = policy_from_env(licensed_only)
    load_dotenv(find_dotenv(usecwd=True), override=True)
    ap = _parser()
    args = ap.parse_args(argv)
    workdir = Path(args.workdir)
    if not workdir.is_dir():
        ap.error(f"workdir not found: {args.workdir}")
    if args.gaps:
        if args.doi or args.title or args.author or args.year or args.pdf:
            ap.error("--gaps takes no work identity and no --pdf")
        if not args.domains or args.domains < 1:
            ap.error("--gaps needs --domains N (N >= 1)")
    else:
        if args.domains is not None:
            ap.error("--domains goes with --gaps")
        doi = normalize_doi(args.doi or "")
        if args.doi is not None and not _doi_ok(doi):
            ap.error(f"not a DOI: {args.doi}")
        triple = [args.title, args.author, args.year]
        if not doi and not all(v and v.strip() for v in triple):
            ap.error("give --doi, or all of --title, --author and --year")
    try:
        if args.gaps:
            settings = settings_from_env(licensed_only, policy, INDEX_BUDGET_GAPS)
            report = run_gaps(workdir, args.domains, settings)
            # One line, as the barrier prints its summary (escaped ASCII).
            print(json.dumps({"status": report["status"], "candidates": report["candidates"],
                              "counts": report["counts"], "errors": report["errors"],
                              "warnings": report["warnings"],
                              "report": REPORT_REL}))
            return 0
        settings = settings_from_env(licensed_only, policy, INDEX_BUDGET_SINGLE)
        identity = make_identity(args.doi, args.title, args.author, args.year)
        result = acquire_one(workdir, identity, settings, Deadline(SINGLE_DEADLINE),
                             pdf_path=args.pdf)
        print(output.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
