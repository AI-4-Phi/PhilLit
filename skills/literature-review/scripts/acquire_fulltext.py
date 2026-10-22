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
`--gaps` mode the run report `intermediate_files/json/fulltext_acquisition.json`.
Never a `.txt` (the evidence barrier renders texts) and never a bib. A PDF
here licenses nothing by itself: the barrier re-extracts it, checks its hash
against the sidecar and re-runs the identity check against the ENTRY before
it stamps FULLTEXT. "Is this PDF this work" is `fulltext.identity_ok`, run
here on every candidate from every source, `--pdf` included; slugs, record
validity and the store paths are `fulltext.py`'s too.

SOURCES, in the ruled order, the first passing PDF wins:
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
OpenAlex and Semantic Scholar need a DOI. Several passing PDFs within the
winning source: the first is kept and the rest are reported
(`multiple_candidates`); every candidate of that source is checked, up to
the folder's 20-candidate limit.

CONSENT. Zotero and the folder are the user's own files, so they are never
touched without their workspace `.env` keys, which `/phillit:setup` writes
on consent: `PHILLIT_ZOTERO` (1/true/yes/on) and `PHILLIT_PDF_DIR`. Without
a key, the source reports `disabled` and makes no call and no file read.
Paywalled copies come only from the user's own copies (Zotero, the folder,
`--pdf`) or open access, never a proxy or a shadow library.

SERVICE POLICY. `PHILLIT_FULLTEXT_LICENSED_ONLY` (1/true/yes/on) disables
Zotero and the folder and accepts OA locations only when their licence
starts with `cc` (case-insensitive: S2 reports `CCBY`). It is read from the
PROCESS environment BEFORE `.env` is loaded and `.env` is ignored for it in
both directions: the hosted service sets it for its own process, so a
workspace `.env` cannot switch the filter off. It is a policy default, not
a security boundary: a Bash call can still unset the variable for one run.
Every sidecar records `source`, `source_ref` and `license`, so a run can be
audited afterwards. `--pdf` stays available under the policy (the service
builds uploads on it).

DOWNLOADS. http(s) only, re-checked on every redirect hop (at most 5,
followed by hand); 30 s per download; a 60 MB cap enforced while streaming;
the body must start `%PDF-`; only the User-Agent is sent (no API key ever
reaches a PDF host). Local files (Zotero, folder, `--pdf`): a 200 MB cap.

OUTCOMES. Single-work mode prints one JSON object `{status, slug, source,
tried}`; `status` is `acquired`, `exists` (a valid record for this identity
is already stored), `not_found` (no PDF was obtained), `rejected` (a PDF was
obtained and none passed extraction and the identity check) or `refused`
(`slug_collision`: a sidecar under the stem names another identity, and
nothing is overwritten; `path_too_long`: the store path would exceed the
Windows limit). `tried` lists `{source, outcome[, detail]}` in order;
source outcomes are `disabled`, `unavailable`, `not_found`, `rejected`,
`acquired`, plus `no_doi` and `unlicensed` for the OA sources and
`deadline` for a source the pass deadline cut. An invalid stored record is
reported as `{source: "store", outcome: "invalid_replaced:<reason>"}` when a
new PDF replaced it (`invalid_kept:<reason>` when none was found). Exit 0
for every status; 1 for a crash, with one JSON object `{"error": ...}`; 2
for a usage error.

`--gaps` tries every domain-bib entry with no `abstract` and either a DOI,
or (Zotero or the folder enabled) a title, author and year, within a 420 s
pass deadline (the Bash ceiling is 600 s); entries not reached are
`not_attempted`. It writes the run report and prints a one-line JSON
summary with counts per outcome.

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
    data: bytes
    source: str
    source_ref: object
    license: str | None


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

def _licensed(lic) -> bool:
    return isinstance(lic, str) and lic.strip().lower().startswith("cc")


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
    if settings.licensed_only:
        unlicensed = [u for u, lic in locs if not _licensed(lic)]
        locs = [(u, lic) for u, lic in locs if _licensed(lic)]
        if unlicensed and not locs:
            res.outcome, res.detail = "unlicensed", [f"{len(unlicensed)} location(s) without a cc licence"]
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


SOURCE_ORDER = ("zotero", "folder", "openalex", "s2")
_SOURCES = {"zotero": source_zotero, "folder": source_folder,
            "openalex": source_openalex, "s2": source_s2}


# --------------------------------------------------------------------------
# Settings, store and the single-work pipeline
# --------------------------------------------------------------------------

@dataclass
class Settings:
    licensed_only: bool
    zotero_on: bool
    pdf_dir: Path | None
    index_budget: float
    _index: FolderIndex | None = None

    def folder_index(self) -> FolderIndex:
        if self._index is None:
            self._index = FolderIndex(self.pdf_dir)
        return self._index


def settings_from_env(licensed_only: bool, index_budget: float) -> Settings:
    raw = os.environ.get(PDF_DIR_ENV, "").strip().strip("\"'").strip()
    pdf_dir = Path(os.path.expanduser(raw)).resolve() if raw else None
    return Settings(licensed_only=licensed_only, zotero_on=_on(os.environ.get(ZOTERO_ENV)),
                    pdf_dir=pdf_dir, index_budget=index_budget)


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


def acquire_one(workdir: Path, identity: dict, settings: Settings, deadline: Deadline,
                pdf_path: str | None = None) -> dict:
    """Run the single-work pipeline; returns {status, slug, source, tried}."""
    slug = ft.slug_for(identity)
    canon = ft.canonical_identity(identity)
    out = {"status": None, "slug": slug, "source": None, "tried": []}
    if not ft.path_budget_ok(workdir):
        out.update(status="refused", tried=[{"source": "store", "outcome": "path_too_long"}])
        return out
    store = Path(workdir) / ft.STORE_REL
    state, info = store_state(store, slug, canon)
    if state == "collision":
        out.update(status="refused", tried=[{"source": "store", "outcome": "slug_collision",
                                              "detail": [info]}])
        return out
    if state == "exists":
        out.update(status="exists", source=info.source,
                   tried=[{"source": "store", "outcome": "exists"}])
        return out
    invalid = info if state == "invalid" else None

    results: list[SourceResult] = []
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
        results.append(res)
    else:
        for name in SOURCE_ORDER:
            if deadline.expired():
                results.append(SourceResult(name, "deadline"))
                continue
            res = _SOURCES[name](identity, settings, deadline)
            results.append(res)
            if res.hits:
                break

    winner = next((r for r in results if r.hits), None)
    tried = [r.tried() for r in results]
    if winner is not None:
        write_record(store, slug, identity, winner.hits[0])
        if invalid:
            tried.insert(0, {"source": "store", "outcome": f"invalid_replaced:{invalid}"})
        out.update(status="acquired", source=winner.hits[0].source, tried=tried)
        return out
    if invalid:
        tried.insert(0, {"source": "store", "outcome": f"invalid_kept:{invalid}"})
    status = "rejected" if any(r.outcome == "rejected" for r in results) else "not_found"
    out.update(status=status, tried=tried)
    return out


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
    title_route = not settings.licensed_only and (settings.zotero_on or settings.pdf_dir is not None)
    cands, domains = gap_candidates(workdir, n_domains, title_route)
    entries, by_slug = [], {}
    for domain, key, ident in cands:
        row = {"domain": domain, "key": key}
        try:
            slug = ft.slug_for(ident)
        except ValueError:
            row.update(slug=None, outcome="refused", source=None,
                       tried=[{"source": "store", "outcome": "bad_identity"}])
            entries.append(row)
            continue
        if slug in by_slug:
            first = by_slug[slug]
            row.update(slug=slug, outcome=first["outcome"], source=first["source"],
                       tried=[{"source": "store", "outcome": f"same_work_as:{first['domain']}/{first['key']}"}])
        elif deadline.expired():
            row.update(slug=slug, outcome="not_attempted", source=None, tried=[])
        else:
            try:
                res = acquire_one(workdir, ident, settings, deadline)
                row.update(slug=slug, outcome=res["status"], source=res["source"], tried=res["tried"])
            except Exception as exc:   # one entry's crash never sinks the pass
                row.update(slug=slug, outcome="error", source=None,
                           tried=[{"source": "pipeline", "outcome": f"error:{type(exc).__name__}: {exc}"}])
            if row["outcome"] != "not_attempted":
                by_slug[slug] = row
        entries.append(row)
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
              "sources": {"zotero": "on" if settings.zotero_on and not settings.licensed_only else "off",
                          "folder": "on" if settings.pdf_dir is not None and not settings.licensed_only else "off"},
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
            settings = settings_from_env(licensed_only, INDEX_BUDGET_GAPS)
            report = run_gaps(workdir, args.domains, settings)
            # One line, as the barrier prints its summary (escaped ASCII).
            print(json.dumps({"status": report["status"], "candidates": report["candidates"],
                              "counts": report["counts"], "errors": report["errors"],
                              "warnings": report["warnings"],
                              "report": REPORT_REL}))
            return 0
        settings = settings_from_env(licensed_only, INDEX_BUDGET_SINGLE)
        identity = make_identity(args.doi, args.title, args.author, args.year)
        result = acquire_one(workdir, identity, settings, Deadline(None), pdf_path=args.pdf)
        print(output.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
