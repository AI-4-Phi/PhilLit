#!/usr/bin/env python3
"""Acquire a work's PDF into the full-text store (EVIDENCE-FULLTEXT).

Usage:
  acquire_fulltext.py <workdir> --doi D [--title T --author A --year Y]
  acquire_fulltext.py <workdir> --title T --author A --year Y
  acquire_fulltext.py <workdir> (--doi D | --title T --author A --year Y) --pdf PATH
  acquire_fulltext.py <workdir> --pdf PATH --gap-entry DOMAIN/KEY
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
3. Open access, one step: OpenAlex, then Semantic Scholar, are asked (the
   requests and parsing are `fulltext_sources`'), the locations the policy
   refuses are dropped (`_licensed` on the raw licence value), and the rest
   are tried in rule-15 order (`fulltext_sources.order`: a publisher copy
   before a self-archived one), stopping at the first that passes. Each API
   keeps its own `tried` row (`openalex`, `s2`), computed from its own
   lookup and locations; a URL both report feeds both rows, and the winning
   location's API is the hit's `source`. A work without a DOI gets the
   OpenAlex title route (title and first-author surname, the matched
   record's locations; its `source_ref` is `{url, matched}`), only with a
   usable `OPENALEX_API_KEY` (a title search costs credits an unkeyed run
   shares with the researchers' searches); Semantic Scholar needs a DOI.
4. The service channel (`PHILLIT_FULLTEXT_REQUEST_DIR`; it replaces 3,
   whose rows then report `disabled` with detail `service`). One request file per
   batch of at most `fulltext_channel.MAX_PER_REQUEST` identities, never
   a URL; a no-DOI identity is sent too (a worker without the title route
   answers `none`, detail `no_doi`), and a request too large is written as
   two halves, down to one identity (`request_too_large` for that one); the grammar is
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
   A second window: a copy the engine could not remove, unchecked or refused
   (`remove_failed`), stays for the barrier, which binds it without a
   licence re-check.
   A service-copied record found on a later acquisition run (`exists`) is
   re-checked against the policy then (a refused one is removed:
   `unlicensed_removed`).
Several passing PDFs within the winning local source (Zotero, the
folder): the first is kept and the rest are reported
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
4); a location, not a policy, it is read after `.env` loads like
`PHILLIT_PDF_DIR`. The worker creates that directory
(`intermediate_files/fulltext_requests/`) before the review starts; the
engine never does, and a missing directory means no worker
(`request_dir_missing`).

DOWNLOADS. http(s) only, re-checked on every redirect hop (at most 5,
followed by hand); a 30 s deadline per download; a 60 MB cap enforced
while streaming; the body must start `%PDF-`; only the User-Agent is sent
(no API key ever reaches a PDF host). Local files (Zotero, folder,
`--pdf`): a 200 MB cap. A metadata answer (OpenAlex, Semantic Scholar,
Brave) is read streaming within `MAX_API_BYTES` (5 MB); a larger one is
`unavailable`, detail `too_large` (for Brave, the failed call
`too_large`). Every body is read per receive (`_read_capped`) with its
deadline checked whenever bytes arrive: bytes received after the end
make a download `timeout`, an OpenAlex or Semantic Scholar row
`deadline` (for Brave, the failed call `timeout`). Each socket operation
waits at most the request's timeout, the time left when it started
(at most 30 s), so a body read ends within its deadline plus that
timeout, however slowly the body trickles in. What the deadline does not
reach (a status line, headers or chunk framing that trickle in, DNS, a
proxy, the local Zotero calls, PDF text extraction) is bounded by the
watchdog (HARD LIMIT). Only gzip and deflate are asked for
and decoded, within the same caps (`bad_encoding` for any other or a
corrupt stream). A malformed `Content-Length` (not 1-20 ASCII digits) is
ignored, and the streaming cap still applies.

SUGGESTIONS. A work the sources and the service left `not_found` or
`rejected` (or, in `--gaps`, `not_attempted`) gets one Brave web search when
`BRAVE_API_KEY` is set, under every policy (`suggest`; the query and the
filtering are `fulltext_sources.brave_request`/`brave_parse`, which may
decline an identity without a 2-word main title or a surname: not asked).
Its up to 3 links are for the user to check and hand over (`--pdf`):
nothing is ever downloaded or stored from a suggestion, and the Brave key
goes to Brave only. Each call is one HTTP attempt (a 429 or 5xx is a failed
call, never retried); its budget is a `Deadline` started after the fetch
work, so it never takes time from a fetch; the limiter wait and the
call's timeout are clamped to it, and the body read checks it per
received chunk (no call starts with less than `SUGGESTION_MIN_SECONDS`
left after the limiter's spacing). Residual: the limiter's real wait can
exceed its spacing when other processes queue on it (it caps a queue at
10 spacings, 15 s).
Timing of `--gaps`: about 420 s of fetch work, then at most 60 s of
suggestions, which stop starting reads `GAPS_SUGGESTION_END` (530 s) into
the pass; a body read ends within one socket timeout of its deadline
(see DOWNLOADS).

HARD LIMIT. Whatever blocks, the process ends `HARD_LIMIT_SECONDS` (570 s)
after it starts, below the 600 s Bash ceiling: it prints one line
`{"error": "hard_limit: ..."}` and exits 1 (`_Watchdog`). PDFs already
stored are kept; a `--gaps` run writes no report.

OUTCOMES. Single-work mode prints one JSON object `{status, slug, source,
tried}`, within a 420 s deadline (`SINGLE_DEADLINE`, the Bash ceiling is
600 s), plus, for a `not_found` or `rejected` work when Brave is asked
(never with `--pdf`), `suggestions: [{url, host, title}]` (empty when Brave
found none) or `suggestions_error: <reason>` for a failed call, within
another `SINGLE_SUGGESTION_SECONDS` (20 s); `status` is `acquired`,
`exists` (a valid record for this identity is already stored),
`not_found` (no PDF was obtained), `rejected` (a PDF was obtained and
none passed extraction and the identity check) or
`refused` (`slug_collision`: a sidecar under the stem names another
identity, and nothing is overwritten; `path_too_long`: the store path
would exceed the Windows limit; `unlicensed_remove_failed:<error>`: a
stored service copy the policy refuses could not be removed, and no
source runs). `tried` lists `{source, outcome[, detail]}` in order;
source outcomes are `disabled`, `unavailable`, `not_found`, `rejected`,
`acquired`, plus `no_doi` for the OA sources and the service (OpenAlex's
detail: `no_key` without an OpenAlex key, `short_title` when the title's
cut phrase has fewer than 2 words (a missing title included),
`no_surname`), `unlicensed` for the OA
sources, the repository and the service, and `deadline` for a source the
deadline cut.
Service details: `no_outcome` (a complete response without this key),
`stem_mismatch` (added to the outcome of checking the record at this
slug), `copied_after_response:<outcome>` (a copy found at this slug
although the answer was not `found`), `copy_invalid:<reason>`
(the copy fails `validate_record`; it is left for the barrier to
withhold), `removed_copy` (a valid copy that could not be read),
`error:<exception>` (this slug's check crashed; its copy is removed,
`remove_failed:<error>` when that fails), `pdf_changed_during_check` (the
bytes read do not hash to the sidecar's `pdf_sha256`; the copy is removed),
`unchecked_copy_removed` (the
deadline passed before this slug's check, and its copy was removed),
`field_too_long`, `request_dir_missing`, `request_write_failed:<error>`,
`closed_write_failed:<error>`, and the worker's own detail token. An
invalid stored record is reported as `{source: "store", outcome:
"invalid_replaced:<reason>"}` when a new PDF replaced it
(`invalid_kept:<reason>` when none was found and a file is still at the
slug, `invalid_removed:<reason>` when none is left: a service copy that
overwrote it was removed); a stored service copy the
policy refuses as `{source: "store", outcome: "unlicensed_removed"}`. Exit
0 for every status; 1 for a crash or the hard limit, with one JSON object
`{"error": ...}`; 2 for a usage error.

`--gaps` tries every domain-bib entry with no `abstract` and either a DOI,
or (the repository, Zotero, the folder, the service channel, an OpenAlex
key or a Brave key enabled) a title, author and year, within a 420 s pass
deadline (the Bash ceiling is 600 s): store and repository (and Zotero and
the folder where enabled; OpenAlex and Semantic Scholar while the service
channel is off) per entry, each entry decided or
found there stored at once, then one service request for the entries still
open, then a wait bounded by the pass deadline. Entries not reached are
`not_attempted`; an entry whose work an earlier entry already tried is
`same_work_as` that entry and takes its final outcome. Each report entry
carries the stored identity (`doi`, `title`, `surname`, `year`, raw).
Then, with a Brave key, every `not_found`, `rejected` or `not_attempted`
entry gets `suggestions` (see SUGGESTIONS), once per work: a `same_work_as`
row never does, so only the first row carries them. They have their own
budget after the fetch work: at most `MAX_SUGGESTION_QUERIES` (40) HTTP
attempts within `SUGGESTION_SECONDS` (60), ending by
`GAPS_SUGGESTION_END` (see SUGGESTIONS). An entry the cap or
the time does not reach, or whose call failed, carries no `suggestions`
field; both are counted in one `warnings` line, `suggestions: N not asked
(cap or time), M failed`, when either is non-zero. It writes the run
report and prints a one-line JSON summary with counts per outcome and
`suggested`, the number of entries with a non-empty `suggestions` list.

`--gap-entry DOMAIN/KEY` (with `--pdf`; no `--doi/--title/--author/--year`,
`--gaps` or `--domains`) hands a PDF over for a gap entry under exactly that
entry's identity: it is read from the run report's row (retyping raw bib
values breaks LaTeX: `M{\\"u}ller` loses its backslash in double quotes, `$`
expands), and the entry is re-read from the current domain bib, whose
identity (`entry_identity_for_gaps`, the one builder `--gaps` uses, blind to
which sources are on now) must equal the report's. Exit 2 naming the cause
(`GapEntryError`) for a missing report, no row or several, a missing bib
entry, a changed identity, or a `same_work_as` row (recognised by its
`tried`; it shares the first row's slug, which does not prove the barrier
binds its own raw values: hand the PDF over for the first row).

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
import threading
import time
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
import urllib3
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
import fulltext_sources as fs  # noqa: E402
from stamp_evidence import entry_header, parse_entry_fields, split_entries  # noqa: E402
from venue_vetting import _ON_TOKENS  # noqa: E402 - the shared on-token set

sys.path.remove(_here)
_research = str(Path(__file__).resolve().parent.parent.parent / "philosophy-research" / "scripts")
sys.path.insert(0, _research)
from rate_limiter import (  # noqa: E402
    ExponentialBackoff,
    get_limiter,
    openalex_api_key,
    openalex_budget_exhausted,
    openalex_headers,
    openalex_params,
    parse_retry_after,
    user_agent,
)
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

DOWNLOAD_TIMEOUT = 30
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024
MAX_REDIRECTS = 5
LOCAL_MAX_BYTES = ft.MAX_PDF_BYTES   # 200 MB
API_TIMEOUT = 30
MAX_API_BYTES = 5 * 1024 * 1024   # a metadata answer, read streaming
# The Content-Encodings `_read_capped` decodes, as zlib wbits (None: as
# sent). `_http_get` asks for exactly these, so an installed brotli or
# zstd never adds one it cannot read.
_ENCODINGS = {"": None, "identity": None, "gzip": 16 + zlib.MAX_WBITS, "x-gzip": 16 + zlib.MAX_WBITS,
              "deflate": zlib.MAX_WBITS}
ACCEPT_ENCODING = "gzip, deflate"
BUDGET_BODY_BYTES = 64 * 1024   # an OpenAlex 429 body, read for its budget marker

GAPS_DEADLINE = 420
SINGLE_DEADLINE = 420
SERVICE_WAIT_MARGIN = 20   # seconds of the deadline kept for validating arrivals
ARRIVAL_CHECK_SECONDS = 1.0   # and this much more per identity sent
MAX_SUGGESTION_QUERIES = 40   # Brave calls per gap pass, after the fetch deadline
SUGGESTION_SECONDS = 60        # their own budget in a gap pass (about 420 + 60 s in all; see SUGGESTIONS)
# and no call starts reading past this many seconds into the pass, so the
# pass normally ends well before HARD_LIMIT_SECONDS.
GAPS_SUGGESTION_END = 530
SINGLE_SUGGESTION_SECONDS = 20  # and in single-work mode (one call)
SUGGESTION_MIN_SECONDS = 1.0   # no call starts with less than this left
HARD_LIMIT_SECONDS = 570   # the process ends by this, whatever blocks (the Bash ceiling is 600 s)
SUGGEST_STATUSES = ("not_found", "rejected", "not_attempted")   # the outcomes that get links
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


class _Watchdog:
    """The backstop under every deadline: HARD_LIMIT_SECONDS after it
    starts, it prints one JSON line `{"error": "hard_limit: ..."}` and ends
    the process with exit 1, whatever the main thread is blocked in (a
    slow status line or chunk framing, DNS, a proxy, Zotero, PDF text
    extraction). Records already stored stay: each is written atomically
    as its entry finishes, and the barrier withholds an invalid one. The
    main thread calls `finish` before it prints its own result, so exactly
    one of the two lines is printed."""

    def __init__(self, seconds: float):
        self._seconds = seconds
        self._lock = threading.Lock()
        self._done = False
        self._timer = threading.Timer(seconds, self._fire)
        self._timer.daemon = True

    def start(self) -> "_Watchdog":
        self._timer.start()
        return self

    def _fire(self) -> None:
        with self._lock:   # held until the process ends: `finish` never returns
            if self._done:
                return
            self._done = True
            sys.stdout.write(json.dumps({"error": f"hard_limit: stopped after {self._seconds:g} s; "
                                                  "PDFs stored before then are kept"}) + "\n")
            sys.stdout.flush()
            _exit(1)

    def finish(self) -> None:
        with self._lock:
            self._done = True
            self._timer.cancel()


_exit = os._exit   # tests monkeypatch this


def _on(value: str | None) -> bool:
    return (value or "").strip().lower() in _ON_TOKENS


def _doi_ok(doi: str) -> bool:
    return doi.startswith("10.") and "/" in doi


# --------------------------------------------------------------------------
# HTTP seam: every request goes through here (tests patch it)
# --------------------------------------------------------------------------

def _http_get(url, *, headers=None, params=None, timeout=30.0, stream=False, trust_env=True):
    """One GET, never following redirects, asking only for the encodings
    `_read_capped` decodes."""
    session = requests.Session()
    session.trust_env = trust_env
    return session.get(url, headers={"Accept-Encoding": ACCEPT_ENCODING, **(headers or {})},
                       params=params, timeout=timeout,
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
        return _read_capped(resp, MAX_DOWNLOAD_BYTES, dl, head=b"%PDF-")
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
    the licence backstop, the read, the hash of the bytes read against the
    sidecar's (a mismatch is `unavailable`, `pdf_changed_during_check`), then
    `check_pdf` against THIS run's identity. Returns (hit, "acquired", []) or (None, outcome, detail). With
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
    if hashlib.sha256(data).hexdigest() != rec.pdf_sha256:
        return refuse("unavailable", ["pdf_changed_during_check"])
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


def _declared_length(resp) -> int | None:
    """The response's Content-Length as an int, or None when it is missing
    or malformed (not 1-20 ASCII digits): a malformed header is ignored and
    the streaming cap still applies. `isdigit` alone admits `²`, which
    `int` refuses."""
    declared = resp.headers.get("Content-Length")
    if not isinstance(declared, str):
        return None
    declared = declared.strip()
    if not (declared.isascii() and declared.isdecimal() and len(declared) <= 20):
        return None
    try:
        return int(declared)
    except ValueError:
        return None


def _decode_body(raw: bytes, wbits: int, cap: int) -> tuple[bytes | None, str]:
    """`raw` decoded within `cap` bytes: (None, "too_large") past it,
    (None, "bad_encoding") for a corrupt or truncated stream. As urllib3
    decodes: gzip may hold several members, all decoded, and bytes after a
    complete member that do not decode end the body; `deflate` is
    zlib-wrapped by the standard and raw in practice: both are read."""
    gzip_bits = 16 + zlib.MAX_WBITS
    for bits in (wbits, -zlib.MAX_WBITS) if wbits == zlib.MAX_WBITS else (wbits,):
        out, rest = b"", raw
        try:
            while True:
                d = zlib.decompressobj(bits)
                try:
                    out += d.decompress(rest, cap + 1 - len(out))
                except zlib.error:
                    if out and bits == gzip_bits:   # trailing bytes after a member
                        break
                    raise
                if len(out) > cap or d.unconsumed_tail:
                    return None, "too_large"
                if not d.eof:
                    return None, "bad_encoding"
                rest = d.unused_data
                if not rest or bits != gzip_bits:
                    break
        except zlib.error:
            continue
        return out, "ok"
    return None, "bad_encoding"


def _read_capped(resp, cap: int, deadline: Deadline | None = None,
                 head: bytes = b"") -> tuple[bytes | None, str]:
    """A streamed body of at most `cap` bytes, decoded, or (None, reason):
    `too_large` (a declared Content-Length over the cap is refused before
    reading; the cap applies to the bytes received and again to the
    decoded body), `bad_encoding` (a Content-Encoding outside
    `_ENCODINGS`, or a stream that does not decode), `not_pdf` (`head`
    given and the body does not start with it; checked as soon as enough
    plain bytes are in, else after decoding) and, with a `deadline`,
    `timeout` for bytes received after its end.

    The body is read with `raw.read1`, which returns per receive, so the
    deadline is checked whenever bytes arrive and a read ends within the
    deadline plus one socket timeout (the request's `timeout`). Not
    `iter_content`: it returns only once 64 KiB are in, so a body trickling
    in below the socket timeout was bounded by nothing; and not urllib3's
    decoding `read1`, which keeps reading while a compressed stream yields
    no output. Hence the raw bytes, decoded here. A urllib3 error is raised
    as the requests exception `iter_content` would raise, so callers keep
    one exception family."""
    declared = _declared_length(resp)
    if declared is not None and declared > cap:
        return None, "too_large"
    encoding = str(resp.headers.get("Content-Encoding") or "").strip().lower()
    if encoding not in _ENCODINGS:
        return None, "bad_encoding"
    wbits = _ENCODINGS[encoding]
    chunks, total, head_ok = [], 0, not head
    while True:
        try:
            chunk = resp.raw.read1(65536, decode_content=False)
        except urllib3.exceptions.ProtocolError as exc:
            raise requests.exceptions.ChunkedEncodingError(exc) from exc
        except urllib3.exceptions.ReadTimeoutError as exc:
            raise requests.exceptions.ConnectionError(exc) from exc
        except urllib3.exceptions.SSLError as exc:
            raise requests.exceptions.SSLError(exc) from exc
        except urllib3.exceptions.HTTPError as exc:
            raise requests.exceptions.ConnectionError(exc) from exc
        if not chunk:
            break
        if deadline is not None and deadline.left() < 0:   # arrived after the end
            return None, "timeout"
        total += len(chunk)
        if total > cap:
            return None, "too_large"
        chunks.append(chunk)
        if not head_ok and wbits is None and total >= len(head):
            if not b"".join(chunks).startswith(head):
                return None, "not_pdf"
            head_ok = True
    body = b"".join(chunks)
    if wbits is not None:
        body, why = _decode_body(body, wbits, cap)
        if body is None:
            return None, why
    if not body.startswith(head):
        return None, "not_pdf"
    return body, "ok"


def _api_get(url, *, headers, params, limiter, deadline: Deadline, openalex: bool):
    """(json | None, reason): a metadata call with a short retry on 429/5xx.
    The answer is read streaming within MAX_API_BYTES (`too_large` past it,
    never retried) with `deadline` checked per received chunk (a chunk
    received after its end gives `deadline`, never retried), then decoded: the caller contract of
    `fulltext_sources`' parse functions, which take decoded JSON."""
    backoff = ExponentialBackoff(max_attempts=3, max_delay=10.0)
    for attempt in range(backoff.max_attempts):
        if deadline.expired():
            return None, "deadline"
        limiter.wait()
        if deadline.expired():   # the limiter's wait used it up
            return None, "deadline"
        r = None
        try:
            r = _http_get(url, headers=headers, params=params, timeout=deadline.clamp(API_TIMEOUT),
                          stream=True)
            if r.status_code == 200:
                body, why = _read_capped(r, MAX_API_BYTES, deadline)
                if body is None:
                    return None, "deadline" if why == "timeout" else why
                try:
                    return json.loads(body), "ok"
                except (ValueError, RecursionError):
                    return None, "bad_json"
            if r.status_code == 404:
                return None, "not_found"
            if r.status_code == 429 and openalex:
                # The budget marker is in a short body: read a capped one
                # (an oversize body reads as none, leaving Retry-After).
                text, why = _read_capped(r, BUDGET_BODY_BYTES, deadline)
                if why == "timeout":
                    return None, "deadline"
                if openalex_budget_exhausted(r, text=(text or b"").decode("utf-8", "replace")):
                    return None, "budget_exhausted"
            if (r.status_code == 429 or r.status_code >= 500) and backoff.wait(
                    attempt, retry_after=parse_retry_after(r.headers.get("Retry-After"))):
                continue
            return None, f"http_{r.status_code}"
        except requests.RequestException as exc:
            if attempt < backoff.max_attempts - 1 and backoff.wait(attempt):
                continue
            return None, f"network:{type(exc).__name__}"
        finally:
            if r is not None:
                try:
                    r.close()
                except Exception:
                    pass
    return None, "retries_exhausted"


def _brave_on() -> bool:
    """Whether a Brave Search key is set, read now (after `.env` loads):
    non-empty once stripped."""
    return bool(os.environ.get("BRAVE_API_KEY", "").strip())


def suggest(identity: dict, deadline: Deadline) -> tuple[list[dict] | None, str | None]:
    """Candidate PDF links from one Brave web search, for the user to check
    and hand over; nothing is downloaded from them. (None, None): not asked
    (no BRAVE_API_KEY, read now, or `fs.brave_request` declines the
    identity), and no HTTP call. (None, "deadline"): skipped, too little of
    `deadline` left for the limiter's spacing plus SUGGESTION_MIN_SECONDS,
    and no HTTP call. ([{url, host, title}], None): Brave answered (the list
    may be empty). (None, reason): the one HTTP attempt failed (`http_<n>`,
    `network:<error>`, `timeout`, `too_large`, `bad_json`, `error:<error>`);
    a 429 or 5xx is never retried. The limiter wait and the call's timeout
    are both clamped to `deadline`; the body read checks it per received
    chunk."""
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    req = fs.brave_request(identity) if key else None
    if req is None:
        return None, None
    r = None
    try:
        limiter = get_limiter("brave")
        # The limiter sleeps by itself and says nothing in advance: wait
        # only when its spacing still leaves a call's minimum.
        if deadline.left() < getattr(limiter, "min_interval", 0.0) + SUGGESTION_MIN_SECONDS:
            return None, "deadline"
        limiter.wait()
        if deadline.left() < SUGGESTION_MIN_SECONDS:
            return None, "deadline"
        headers = {"X-Subscription-Token": key, "Accept": "application/json",
                   "User-Agent": user_agent()}
        r = _http_get(req.url, headers=headers, params=dict(req.params),
                      timeout=deadline.clamp(API_TIMEOUT), stream=True)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        body, why = _read_capped(r, MAX_API_BYTES, deadline)
        if body is None:
            return None, why
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            return None, "bad_json"
        return [{"url": s.url, "host": s.host, "title": s.title}
                for s in fs.brave_parse(identity, payload)], None
    except requests.RequestException as exc:
        # The class name only: a requests message embeds the URL.
        return None, f"network:{type(exc).__name__}"
    except Exception as exc:   # a suggestion never sinks the run
        return None, f"error:{type(exc).__name__}"
    finally:
        if r is not None:
            try:
                r.close()
            except Exception:
                pass


def _title_route_on() -> bool:
    """Whether the OpenAlex title route may run: a usable OPENALEX_API_KEY,
    read now (after `.env` loads). A title search costs credits an unkeyed
    run shares with the researchers' own searches, as `venue_vetting`
    decides; a key with unprintable characters reads as unset
    (`openalex_api_key`), so it never runs unkeyed."""
    return bool(openalex_api_key())


def _send(req: fs.Request, deadline: Deadline):
    """Send a `fulltext_sources` request with its API's credentials: the
    OpenAlex key as a header plus the polite-pool mailto, or S2's
    `x-api-key` when set. (json | None, reason)."""
    if req.api == "openalex":
        return _api_get(req.url, headers={**openalex_headers(), "User-Agent": user_agent()},
                        params={**req.params, **openalex_params(os.environ.get("OPENALEX_EMAIL", ""))},
                        limiter=get_limiter("openalex"), deadline=deadline, openalex=True)
    key = os.environ.get("S2_API_KEY", "").strip()
    headers = {"User-Agent": user_agent()}
    if key:
        headers["x-api-key"] = key
    return _api_get(req.url, headers=headers, params=dict(req.params),
                    limiter=get_limiter("semantic_scholar", authenticated=bool(key)),
                    deadline=deadline, openalex=False)


def openalex_locations(identity: dict, deadline: Deadline) -> tuple[list | None, str, list[str]]:
    """(locations | None, reason, detail) from OpenAlex: the DOI route, or
    for a work without a DOI the title route (only with a key). None with
    `no_doi` when neither can run (detail `no_key`, `short_title` or
    `no_surname`)."""
    req = fs.openalex_doi_request(identity)
    parse = fs.openalex_doi_parse
    if req is None:
        if not _title_route_on():
            return None, "no_doi", ["no_key"]
        req = fs.openalex_title_request(identity)
        parse = fs.openalex_title_parse
        if req is None:
            return None, "no_doi", ["no_surname" if fs.key_phrase(identity) else "short_title"]
    data, why = _send(req, deadline)
    return (None, why, []) if data is None else (parse(identity, data), "ok", [])


def s2_locations(identity: dict, deadline: Deadline) -> tuple[list | None, str, list[str]]:
    req = fs.s2_doi_request(identity)
    if req is None:
        return None, "no_doi", []
    data, why = _send(req, deadline)
    return (None, why, []) if data is None else (fs.s2_parse(identity, data), "ok", [])


OA_APIS = ("openalex", "s2")


def source_open_access(identity: dict, settings: "Settings", deadline: Deadline) -> list[SourceResult]:
    """The open-access step: ask OpenAlex, then S2, drop the locations the
    policy refuses (`_licensed` on the raw value), put the rest in rule-15
    order (`fs.order`: a publisher copy before a self-archived one) and try
    them until one passes `check_pdf`. One row per API, from its own lookup
    and its own locations: `acquired` (its location passed), else
    `rejected` (one was downloaded and failed), else `unlicensed` (it had
    locations, all refused), else `not_found`; or its lookup's `no_doi`,
    `unavailable` or `deadline`. A URL both APIs report is each API's
    location: its outcome feeds both rows. Only the winning location's API
    row carries the hit, and that API is the hit's `source`."""
    if settings.request_dir is not None:
        return [SourceResult(api, "disabled", ["service"]) for api in OA_APIS]
    rows = {api: SourceResult(api, "not_found") for api in OA_APIS}
    admitted, apis_by_url, mine = [], {}, {api: [] for api in OA_APIS}
    for api, locate in (("openalex", openalex_locations), ("s2", s2_locations)):
        res = rows[api]
        locs, why, detail = locate(identity, deadline)
        if locs is None:
            if why != "not_found":
                res.outcome, res.detail = {"no_doi": ("no_doi", detail), "deadline": ("deadline", [])}.get(
                    why, ("unavailable", [why]))
            continue
        admit = [loc for loc in locs if _licensed(loc.license, settings.policy)]
        if locs and not admit:
            res.outcome, res.detail = "unlicensed", [f"{len(locs)} location(s) not admitted by policy"]
        for loc in admit:
            apis_by_url.setdefault(loc.url, set()).add(api)
            if loc.url not in mine[api]:
                mine[api].append(loc.url)
        admitted += admit
    tried: set[str] = set()
    checked: set[str] = set()   # URLs downloaded and checked (failed or passed)
    winner = None
    for loc in fs.order(admitted):
        if deadline.expired():
            for api in OA_APIS:
                if any(u not in tried for u in mine[api]):
                    rows[api].detail.append("deadline")
            break
        tried.add(loc.url)
        data, why = download_pdf(loc.url, deadline)
        if data is not None:
            checked.add(loc.url)
            ok, why = check_pdf(data, identity)
            if ok:
                winner = (loc, data)
                break
        for api in apis_by_url[loc.url]:
            rows[api].detail.append(f"{loc.url}:{why}")
    for api in OA_APIS:
        res = rows[api]
        if res.outcome != "not_found" or not mine[api]:
            continue
        if winner is not None and api in apis_by_url[winner[0].url]:
            res.outcome = "acquired"
        elif any(u in checked for u in mine[api]):
            res.outcome = "rejected"
    if winner is not None:
        loc, data = winner
        ref = loc.url if loc.matched is None else {"url": loc.url, "matched": loc.matched}
        rows[loc.source].hits.append(Hit(data, loc.source, ref, loc.license))
    return [rows[api] for api in OA_APIS]


SOURCE_ORDER = ("repository", "zotero", "folder", "open_access", "service")
LOCAL_SOURCES = SOURCE_ORDER[:-1]   # the ones _SOURCES maps, tried per work
# Each returns one SourceResult, or a list of them (the open-access step:
# one row per API); `open_access` is an internal name, never a `tried` row.
_SOURCES = {"repository": source_repository, "zotero": source_zotero, "folder": source_folder,
            "open_access": source_open_access}
_STEP_ROWS = {"open_access": OA_APIS}


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
            attempt.results.extend(SourceResult(row, "deadline") for row in _STEP_ROWS.get(name, (name,)))
            continue
        res = _SOURCES[name](identity, settings, deadline)
        rows = res if isinstance(res, list) else [res]
        attempt.results.extend(rows)
        if any(r.hits for r in rows):
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


def _write_split(request_dir: Path, mode: str, chunk: list, out: dict) -> list[tuple[str, list]]:
    """Write `chunk` as one request, or, when the file would exceed
    `fc.MAX_REQUEST_BYTES`, as two halves, recursing down to one identity.
    Returns [(request_id, part)] for each request written; a part whose
    write fails is `unavailable` in `out` (`request_write_failed:<reason>`,
    so a single identity still too large is `request_too_large`)."""
    request_id = fc.new_request_id(mode)
    try:
        fc.write_request(request_dir, request_id, mode, [c[3] for c in chunk])
    except (OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(exc, ValueError) else "") or type(exc).__name__
        if reason == "request_too_large" and len(chunk) > 1:
            half = len(chunk) // 2
            return (_write_split(request_dir, mode, chunk[:half], out)
                    + _write_split(request_dir, mode, chunk[half:], out))
        for slug, *_ in chunk:
            out[slug] = SourceResult("service", "unavailable", [f"request_write_failed:{reason}"])
        return []
    return [(request_id, chunk)]


def service_fetch(store: Path, pending: list[tuple[str, dict, str | None]], settings: Settings,
                  deadline: Deadline, mode: str) -> dict[str, SourceResult]:
    """Ask the service channel for `pending` [(slug, identity, invalid)]
    (`invalid`: the reason `begin` found the stored record invalid, or
    None); returns a `service` SourceResult for every slug. Every identity
    `fc.identity_payload` accepts is sent (a no-DOI one too; a worker
    without the title route answers it `none/no_doi`), in requests of at
    most `fc.MAX_PER_REQUEST` that split in half while too large, and only
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
            for request_id, part in _write_split(settings.request_dir, mode, chunk, out):
                written.append((request_id, part))
                n_sent += len(part)
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
        left = any((attempt.store / f"{attempt.slug}{suffix}").exists()
                   for suffix in (".json", ".pdf"))
        note = "invalid_kept" if left else "invalid_removed"
        tried.insert(0, {"source": "store", "outcome": f"{note}:{attempt.invalid}"})
    out["status"] = "rejected" if any(r.outcome == "rejected" for r in results) else "not_found"
    return out


def acquire_one(workdir: Path, identity: dict, settings: Settings, deadline: Deadline,
                pdf_path: str | None = None) -> dict:
    """Run the single-work pipeline; returns {status, slug, source, tried},
    plus `suggestions` or `suggestions_error` when the sources left the work
    `not_found` or `rejected` and Brave was asked (never for `--pdf`: a
    hand-over ends the suggestion loop). The suggestion budget starts after
    the fetch work, so it never takes time from a fetch."""
    attempt = begin(workdir, identity, settings, deadline, pdf_path)
    service = None
    if attempt.open and pdf_path is None:
        service = service_fetch(attempt.store, [(attempt.slug, identity, attempt.invalid)], settings,
                                deadline, "single")[attempt.slug]
    out = finish(attempt, service)
    if pdf_path is None and out["status"] in SUGGEST_STATUSES:
        found, why = suggest(identity, Deadline(SINGLE_SUGGESTION_SECONDS))
        if found is not None:
            out["suggestions"] = found
        elif why is not None:
            out["suggestions_error"] = why
    return out


# --------------------------------------------------------------------------
# --gaps
# --------------------------------------------------------------------------

def entry_identity_for_gaps(fields: dict) -> dict | None:
    """The stored identity of one bib entry's parsed fields, as `--gaps` and
    `--gap-entry` build it: the normalised DOI when it is usable, the RAW
    title, `first_author_surname(author, editor)` and the raw year (the
    barrier binds no-DOI records on raw values). None when the entry has no
    usable DOI and no complete title/author/year. Which sources are enabled
    is not its concern: admission is `gap_candidates`' decision, so a handover
    reconstructs the identity the same way whatever the settings now are."""
    doi = normalize_doi(fields.get("doi") or "")
    doi = doi if _doi_ok(doi) else ""
    title = fields.get("title") or ""
    surname = first_author_surname(fields.get("author") or "", fields.get("editor") or "")
    year = fields.get("year") or ""
    if doi or (title.strip() and surname.strip() and year.strip()):
        return make_identity(doi, title, surname, year)
    return None


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
            ident = entry_identity_for_gaps(fields)
            if ident and (ident["doi"] or title_route):
                out.append((i, header[1], ident))
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


def _suggest_gaps(entries: list[dict], seconds: float) -> list[str]:
    """The suggestion post-pass, after the fetch work: every row left
    `not_found`, `rejected` or `not_attempted` gets a Brave search, once per
    work (a `same_work_as` row, or a later row of a slug already asked, is
    skipped, so only the first row carries the links), within its own
    budget: at most MAX_SUGGESTION_QUERIES HTTP attempts in `seconds`
    (SUGGESTION_SECONDS, less when the fetch work ran long). A row the
    module declines (`fs.brave_request` None) is neither asked nor counted.
    Rows the cap or the time does not reach, and failed calls, carry no
    `suggestions` field; the warning line counts them (none when both are
    0). A row whose handling crashes counts as failed, so one bad row
    neither sinks the counts nor stops the rows after it."""
    budget = Deadline(max(0.0, seconds))
    asked, calls, not_asked, failed = set(), 0, 0, 0
    for row in entries:
        try:
            if (row.get("outcome") not in SUGGEST_STATUSES or row.get("slug") is None
                    or row["slug"] in asked
                    or any(str(t.get("outcome", "")).startswith("same_work_as:") for t in row["tried"])):
                continue
            identity = {k: row.get(k) for k in ("doi", "title", "surname", "year")}
            if fs.brave_request(identity) is None:
                continue
            asked.add(row["slug"])
            if calls >= MAX_SUGGESTION_QUERIES:
                not_asked += 1
                continue
            found, why = suggest(identity, budget)
            if found is None and why in (None, "deadline"):   # `suggest` skipped it for time
                not_asked += 1
                continue
            calls += 1
            if found is None:
                failed += 1
            else:
                row["suggestions"] = found
        except Exception:
            failed += 1
    if not (not_asked or failed):
        return []
    return [f"suggestions: {not_asked} not asked (cap or time), {failed} failed"]


def run_gaps(workdir: Path, n_domains: int, settings: Settings) -> dict:
    started = _clock()
    deadline = Deadline(GAPS_DEADLINE)
    title_route = (settings.repository_dir is not None
                   or (not settings.licensed_only and (settings.zotero_on or settings.pdf_dir is not None))
                   or _title_route_on() or settings.request_dir is not None or _brave_on())
    cands, domains = gap_candidates(workdir, n_domains, title_route)

    def crashed(row, exc):   # one entry's crash never sinks the pass
        row.update(outcome="error", source=None,
                   tried=[{"source": "pipeline", "outcome": f"error:{type(exc).__name__}: {exc}"}])

    entries, by_slug, attempts, duplicates = [], {}, [], []
    for domain, key, ident in cands:
        row = {"domain": domain, "key": key, **ident}   # the raw stored identity
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
    suggestions_started = _clock()
    try:   # a suggestion never sinks the pass
        seconds = min(SUGGESTION_SECONDS, GAPS_SUGGESTION_END - (suggestions_started - started))
        suggestion_warnings = _suggest_gaps(entries, seconds) if _brave_on() else []
    except Exception as exc:
        suggestion_warnings = [f"suggestions: error:{type(exc).__name__}"]
    suggestion_seconds = round(_clock() - suggestions_started, 1)
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
    warnings = _folder_warnings(settings) + suggestion_warnings
    report = {"schema": 1, "status": "done_with_errors" if errors else "done",
              "generated_at": _now_iso(), "deadline_seconds": GAPS_DEADLINE,
              "elapsed_seconds": round(_clock() - started, 1),
              "suggestion_seconds": suggestion_seconds,
              "licensed_only": settings.licensed_only,
              "policy": settings.policy,
              "sources": {"zotero": "on" if settings.zotero_on and not settings.licensed_only else "off",
                          "folder": "on" if settings.pdf_dir is not None and not settings.licensed_only else "off",
                          "repository": "on" if settings.repository_dir is not None else "off",
                          "service": "on" if settings.request_dir is not None else "off"},
              "domains": domains, "candidates": len(entries), "counts": counts,
              "suggested": sum(1 for e in entries if e.get("suggestions")),
              "errors": errors, "warnings": warnings, "entries": entries}
    path = workdir / REPORT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    ft.write_text_atomic(path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


class GapEntryError(Exception):
    """`--gap-entry` cannot name one entry's identity; the message says why."""


def identity_from_report(workdir: Path, spec: str) -> dict:
    """The identity of the gap entry `spec` (`DOMAIN/KEY`), from the run
    report, proven against the entry's current bib text. Raises
    `GapEntryError`. Retyping raw bib values on a command line breaks LaTeX,
    so the report's raw values are the identity, and the bib is re-read only
    to prove they still describe the entry (a bib edited after the pass is
    refused). A `same_work_as` row is refused: it shares the first row's slug,
    which does not prove the barrier binds THIS row's raw values."""
    domain, sep, key = spec.partition("/")
    domain = domain.strip()
    # ASCII digits only, and short: `isdigit` admits `²`, which `int` refuses,
    # and `int` refuses a string of more than 4,300 digits.
    if (not sep or not key or not (domain.isascii() and domain.isdecimal())
            or len(domain) > 6):
        raise GapEntryError(f"--gap-entry wants DOMAIN/KEY (e.g. 1/gardner2019), got: {spec}")
    rerun = "run the gap pass again (--gaps --domains N)"
    try:
        report = json.loads(ft.read_text(workdir / REPORT_REL))
        entries = report["entries"]
    except FileNotFoundError:
        raise GapEntryError(f"no gap-pass report at {REPORT_REL}: {rerun}") from None
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        raise GapEntryError(f"the gap-pass report is unreadable ({type(exc).__name__}): {rerun}") from None
    if not (isinstance(entries, list)
            and all(isinstance(e, dict) and isinstance(e.get("tried"), list) for e in entries)):
        raise GapEntryError(f"the gap-pass report is malformed (entries): {rerun}")
    domain = str(int(domain))
    rows = [e for e in entries if str(e.get("domain")) == domain and e.get("key") == key]
    if not rows:
        raise GapEntryError(f"the gap-pass report has no entry {domain}/{key}: {rerun} if the entry is new")
    if len(rows) > 1:
        raise GapEntryError(f"the gap-pass report has {len(rows)} rows for {domain}/{key}: "
                            f"{rerun} after making the keys unique")
    row = rows[0]
    marker = next((str(t.get("outcome")) for t in row["tried"] if isinstance(t, dict)
                   and str(t.get("outcome") or "").startswith("same_work_as:")), None)
    if marker is not None:
        raise GapEntryError(f"{domain}/{key} is the same work as an earlier entry "
                            f"({marker}): hand the PDF over for that entry")
    if not row.get("slug"):
        raise GapEntryError(f"{domain}/{key} has no usable identity (outcome {row.get('outcome')}): "
                            "nothing to store it under")
    reported = {f: row.get(f) for f in ("doi", "title", "surname", "year")}
    bib = workdir / f"literature-domain-{domain}.bib"
    try:
        text = ft.read_text(bib)
    except (OSError, ValueError) as exc:
        raise GapEntryError(f"cannot read {bib.name} ({type(exc).__name__}): {rerun}") from None
    chunks = [c for c in split_entries(text)
              if not is_verbatim_block(c) and (entry_header(c) or (None, None))[1] == key]
    if len(chunks) != 1:
        raise GapEntryError(f"{bib.name} has {len(chunks)} entries with key {key}, not one: {rerun}")
    current = entry_identity_for_gaps(parse_entry_fields(chunks[0]))
    if current != reported:
        raise GapEntryError(f"{domain}/{key} changed in {bib.name} since the gap pass: {rerun}")
    return reported


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
    ap.add_argument("--gap-entry", metavar="DOMAIN/KEY",
                    help="With --pdf: store the PDF under the identity the gap-pass report holds "
                         "for that entry (instead of --doi/--title/--author/--year)")
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
    gap_identity = None
    if args.gap_entry is not None:
        if args.gaps or args.domains is not None:
            ap.error("--gap-entry cannot go with --gaps or --domains")
        if args.doi or args.title or args.author or args.year:
            ap.error("--gap-entry takes its identity from the gap-pass report, "
                     "not --doi/--title/--author/--year")
        if not args.pdf:
            ap.error("--gap-entry needs --pdf PATH")
        try:
            gap_identity = identity_from_report(workdir, args.gap_entry)
        except GapEntryError as exc:
            ap.error(str(exc))
    elif args.gaps:
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
    watchdog = _Watchdog(HARD_LIMIT_SECONDS).start()
    try:
        if args.gaps:
            settings = settings_from_env(licensed_only, policy, INDEX_BUDGET_GAPS)
            report = run_gaps(workdir, args.domains, settings)
            watchdog.finish()
            # One line, as the barrier prints its summary (escaped ASCII).
            print(json.dumps({"status": report["status"], "candidates": report["candidates"],
                              "counts": report["counts"], "suggested": report["suggested"],
                              "errors": report["errors"],
                              "warnings": report["warnings"],
                              "report": REPORT_REL}))
            return 0
        settings = settings_from_env(licensed_only, policy, INDEX_BUDGET_SINGLE)
        identity = gap_identity or make_identity(args.doi, args.title, args.author, args.year)
        result = acquire_one(workdir, identity, settings, Deadline(SINGLE_DEADLINE),
                             pdf_path=args.pdf)
        watchdog.finish()
        print(output.dumps(result))
        return 0
    except Exception as exc:
        watchdog.finish()
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 1
    finally:
        watchdog.finish()


if __name__ == "__main__":
    sys.exit(main())
