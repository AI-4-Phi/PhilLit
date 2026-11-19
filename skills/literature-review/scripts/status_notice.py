"""Publication-status facts from CrossRef, for the barrier's `status_notice`.

The evidence barrier stamps `status_notice = {<item>; <item>; ...}` on an
entry when CrossRef lists an update relation for the entry's own DOI, or
when that DOI is itself a CrossRef preprint. Items, in this order and
deduplicated:

    retraction <notice-doi>
    partial_retraction <notice-doi>
    withdrawal <notice-doi>
    expression_of_concern <notice-doi>
    correction <notice-doi>     (CrossRef correction, erratum, corrigendum)
    preprint                    (type posted-content, subtype preprint)

The stamp licenses the EXISTENCE of a notice, never its substance. Its
absence means "no status fact is licensed for this entry in this run",
never "no notice exists"; the report's per-entry `entries` map says why.

Type tokens are pinned against CrossRef's own facet over every update
record (measured 2026-11-19, the fixture
tests/fixtures/crossref_status/facet.json): all seven mapped tokens occur.
CrossRef also emits case and hyphen variants of them (`Erratum` 11 records,
`expression-of-concern` 6, `Corrigendum` 5, `Retraction` 3), so a token is
case- and hyphen-folded before the exact match (`category_of`). A relation
whose token still maps to nothing (`new_version`, `addendum`, a misspelling),
or a mapped one with a malformed notice DOI, is never stamped and never read
as "no notice": the entry is `unresolved` (unless other items stamp) and the
pass is partial.

Who is looked up: entries with a DOI of `bib_identity.DOI_SHAPE` whose tier
is not EVIDENCE-NONE. Not sent: arXiv DOIs (`10.48550/`, DataCite, not in
CrossRef) and DOIs carrying a comma or whitespace (a comma splits CrossRef's
filter list and fails the whole batch with HTTP 400, measured).

Per chunk of at most BATCH_SIZE DOIs, two batched queries and no `select`
(CrossRef rejects `subtype` there): forward `filter=doi:A,doi:B` (each
record's type, subtype, title, author and `updated-by`), and reverse
`filter=updates:A,updates:B` (notice records whose `update-to` names a
requested DOI). HTTP 400/414, or a response with fewer items than its
`total-results`, splits the chunk in half; a single DOI that still fails is
`error` for its entries. Requests go through CrossRef's list-query rate
(`get_limiter("crossref_list")`, one a second), and one HTTP 429 is retried
after its Retry-After when that fits the deadline. Results are mapped by
normalized DOI only.

The forward record must match the entry before anything is stamped: a
compatible type (a @book never matches a chapter or article record, nor a
part a book record), the same first-author surname (folded, leading
particles such as "van der" removed, then compared exactly -- "Garcia Lopez"
is not "Lopez") and the same title, or a subtitle variant
(`bib_identity.titles_differ_by_subtitle`). CrossRef titles are decoded
(HTML entities, repeatedly: `&amp;amp;` occurs; markup) and the subtitle
CrossRef often keeps in its own field is tried joined on. A leading
`RETRACTED:` / `RETRACTED ARTICLE:` / `WITHDRAWN:` marker is cut on both
sides: CrossRef renames the retracted article itself that way (measured on
10.1177/1758835919874651 and 10.1007/s11277-021-09072-0), and without the
cut the most important category never matched.

A notice DOI that is not of DOI_SHAPE or holds `;` or whitespace is skipped
and counted `malformed`. A notice DOI equal to the entry's own DOI is
accepted for retraction, partial_retraction and withdrawal, which publishers
issue in place: Springer's retraction of 10.1007/s11277-021-09072-0 names the
article itself, and both `partial_retraction` records CrossRef holds do the
same (measured 2026-11-19). The item then carries the entry's own DOI. For a
correction or expression of concern, self-reference stays `malformed`.

Bounds: the caller's absolute `deadline` (shared with venue vetting) is
checked before the rate-limiter wait and again after it, so at most one
request runs past it (REQUEST_TIMEOUT). MAX_CONSECUTIVE_ERRORS failed
requests stop the pass. No caching: status is re-fetched every run.
PHILLIT_STATUS_NOTICE=off (or 0/false/no; an unrecognized value too) skips
the pass with a reason; the test suite runs with it off.

`lookup_status` never raises.
"""
from __future__ import annotations

import html
import os
import re
import sys
import time
from pathlib import Path

_here = str(Path(__file__).resolve().parent)
sys.path.insert(0, _here)
import venue_vetting as _vv  # noqa: E402  (also puts philosophy-research/scripts on sys.path)
from generate_bibliography import clean_bibtex_str  # noqa: E402

sys.path.remove(_here)
_hook_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "hooks")
sys.path.insert(0, _hook_dir)
from bib_identity import (  # noqa: E402
    DOI_SHAPE, first_author_surname, normalize_doi, title_key,
    titles_differ_by_subtitle)

sys.path.remove(_hook_dir)

import requests  # noqa: E402
from rate_limiter import get_limiter  # noqa: E402

FIELD = "status_notice"
REQUEST_TIMEOUT = _vv.REQUEST_TIMEOUT
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
BATCH_SIZE = 40
ROWS = 1000
MAX_CONSECUTIVE_ERRORS = 3
ARXIV_PREFIX = "10.48550/"

TYPE_CATEGORY = {
    "retraction": "retraction",
    "partial_retraction": "partial_retraction",
    "withdrawal": "withdrawal",
    "expression_of_concern": "expression_of_concern",
    "correction": "correction",
    "erratum": "correction",
    "corrigendum": "correction",
}
PREPRINT = "preprint"


def category_of(token) -> str | None:
    """The category of a CrossRef update type: case and hyphens folded, then
    an exact match to the seven tokens above. CrossRef emits `Retraction`,
    `Erratum`, `Corrigendum` and `expression-of-concern` beside the canonical
    spellings (facet fixture); a misspelling (`retration`) still maps to
    nothing."""
    if not isinstance(token, str):
        return None
    return TYPE_CATEGORY.get(token.strip().lower().replace("-", "_"))


CATEGORY_ORDER = ("retraction", "partial_retraction", "withdrawal",
                  "expression_of_concern", "correction", PREPRINT)
ENTRY_STATES = ("stamped", "checked_none", "not_found", "identity_mismatch",
                "not_requested:no-doi", "not_requested:evidence-none",
                "not_requested:arxiv", "not_requested:invalid-doi",
                "unresolved", "error", "deadline", "splice_failed",
                "not_checked:late-promotion")

_TAG_RE = re.compile(r"<[^>]+>")
# Tags that separate words (a line break, a block) become a space; every
# other tag is removed outright, since `<i>Bio</i>logy` is one word.
_BREAK_TAG_RE = re.compile(r"<\s*(?:br|p|div|/p|/div)\b[^>]*>", re.IGNORECASE)
_RETRACTED_MARK_RE = re.compile(
    r"^\s*(?:retracted(?:\s+article)?|withdrawn)\s*[:.]\s*", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Value grammar
# ---------------------------------------------------------------------------

def parse_items(value) -> list[tuple[str, str | None]]:
    """(category, notice DOI or None) per `; `-separated item, in order."""
    out = []
    for part in (value or "").split(";"):
        words = part.split()
        if not words:
            continue
        out.append((words[0], words[1] if len(words) > 1 else None))
    return out


def categories(value) -> set[str]:
    return {cat for cat, _doi in parse_items(value)}


def format_items(items) -> str:
    rank = {c: n for n, c in enumerate(CATEGORY_ORDER)}
    ordered = sorted(set(items), key=lambda it: (rank[it[0]], it[1] or ""))
    return "; ".join(cat if doi is None else f"{cat} {doi}" for cat, doi in ordered)


# ---------------------------------------------------------------------------
# DOIs and identity
# ---------------------------------------------------------------------------

def request_doi(raw) -> tuple[str | None, str | None]:
    """(normalized DOI to send, None) or (None, not_requested reason)."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "no-doi"
    doi = normalize_doi(raw)
    if doi.startswith(ARXIV_PREFIX):
        return None, "arxiv"
    if not DOI_SHAPE.fullmatch(doi) or "," in doi or re.search(r"\s", doi):
        return None, "invalid-doi"
    return doi, None


# Categories whose notice may be the article itself: publishers retract and
# withdraw IN PLACE (Springer's "RETRACTED ARTICLE" record names its own DOI;
# both partial_retraction records CrossRef holds do too, measured
# 2026-11-19). A correction or expression of concern naming itself is not a
# notice, so self-reference stays malformed there.
SELF_NOTICE_CATEGORIES = frozenset({"retraction", "partial_retraction", "withdrawal"})


def _notice_doi(raw, entry_doi: str, category: str) -> str | None:
    """The notice DOI, normalized, or None when it is malformed."""
    if not isinstance(raw, str):
        return None
    doi = normalize_doi(raw)
    if not DOI_SHAPE.fullmatch(doi) or ";" in doi or re.search(r"\s", raw.strip()):
        return None
    if doi == entry_doi and category not in SELF_NOTICE_CATEGORIES:
        return None
    return doi


def decode_crossref_title(text) -> str:
    """CrossRef title text as plain text: entities unescaped until stable
    (double-encoded `&amp;amp;` occurs), tags removed, whitespace collapsed."""
    s = text if isinstance(text, str) else ""
    for _ in range(4):
        u = html.unescape(s)
        if u == s:
            break
        s = u
    return " ".join(_TAG_RE.sub("", _BREAK_TAG_RE.sub(" ", s)).split())


def _cut_mark(title: str) -> str:
    return _RETRACTED_MARK_RE.sub("", title, count=1)


def _first(value):
    if isinstance(value, list):
        return value[0] if value and isinstance(value[0], str) else ""
    return value if isinstance(value, str) else ""


def _titles_match(bib_title: str, cr_title: str) -> bool:
    a, b = _cut_mark(bib_title), _cut_mark(cr_title)
    ka, kb = title_key(a), title_key(b)
    if not ka or not kb:
        return False
    return ka == kb or titles_differ_by_subtitle(a, b)


# Lowercase name particles, removed from the FRONT of a folded surname only,
# so "van der Linden" and CrossRef's "Linden" compare equal while "Garcia
# Lopez" and "Lopez" never do (a shared last word is two surnames).
_PARTICLES = frozenset({"van", "von", "de", "der", "den", "da", "di", "du",
                        "la", "le", "del", "della", "dos", "das", "ten", "ter",
                        "d", "l", "zu", "vom", "zum", "zur", "op"})


def _surname_key(name: str) -> str:
    words = title_key(clean_bibtex_str(name or "")).split()
    while len(words) > 1 and words[0] in _PARTICLES:
        words = words[1:]
    return " ".join(words)


# P2: a book record never identifies a part of one, nor the reverse.
_CR_WHOLE_BOOK = frozenset({"book", "monograph", "edited-book", "reference-book",
                            "book-set", "book-series", "book-track"})
_CR_PART = frozenset({"book-chapter", "book-section", "book-part", "reference-entry",
                      "journal-article", "proceedings-article"})
_BIB_WHOLE_BOOK = frozenset({"book", "proceedings", "collection", "mvbook"})
_BIB_PART = frozenset({"article", "incollection", "inbook", "inproceedings",
                       "inreference"})


def _types_compatible(entry_type, record: dict) -> bool:
    etype = (entry_type or "").strip().lower()
    cr = (record.get("type") or "").strip().lower()
    if etype in _BIB_WHOLE_BOOK and cr in _CR_PART:
        return False
    if etype in _BIB_PART and cr in _CR_WHOLE_BOOK:
        return False
    return True


def _crossref_first_surname(record: dict) -> str:
    authors = [a for a in (record.get("author") or []) if isinstance(a, dict)]
    if not authors:
        return ""
    first = next((a for a in authors if a.get("sequence") == "first"), authors[0])
    return first.get("family") or first.get("name") or ""


def identity_matches(fields: dict, record: dict, entry_type=None) -> bool:
    """Is the CrossRef forward record this entry? First-author surname
    (bib_identity's rule; authors only, so an editor-only book never
    matches), title equal or a subtitle variant, and a compatible entry type
    when `entry_type` is given. Never raises."""
    try:
        if not _types_compatible(entry_type, record):
            return False
        bib_surname = _surname_key(first_author_surname(fields.get("author") or "", ""))
        cr_surname = _surname_key(_crossref_first_surname(record))
        if not bib_surname or bib_surname != cr_surname:
            return False
        bib_title = clean_bibtex_str(fields.get("title") or "")
        main = decode_crossref_title(_first(record.get("title")))
        candidates = [main]
        sub = decode_crossref_title(_first(record.get("subtitle")))
        if main and sub:
            candidates.append(f"{main}: {sub}")
        return any(_titles_match(bib_title, c) for c in candidates if c)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def _http_get(params: dict):
    """One GET against /works: (status_code, parsed JSON or None, headers).
    Test fakes may return the first two only."""
    response = requests.get(CROSSREF_WORKS_URL, params=params, timeout=REQUEST_TIMEOUT)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body, response.headers


RETRY_AFTER_DEFAULT = 1.0


def _retry_after(headers) -> float:
    try:
        value = float((headers or {}).get("Retry-After"))
    except (TypeError, ValueError):
        return RETRY_AFTER_DEFAULT
    return value if value >= 0 else RETRY_AFTER_DEFAULT


class _Pass:
    def __init__(self, deadline: float):
        self.deadline = deadline
        self.limiter = get_limiter("crossref_list")
        self.mailto = os.environ.get("CROSSREF_MAILTO", "").strip()
        self.consecutive_errors = 0
        self.stop = None   # None, "deadline" or "error"

    def request(self, kind: str, dois: list[str]):
        """("ok", items) | ("split", None) | ("error", None) | ("deadline", None).
        One HTTP 429 is retried after its Retry-After, when that fits before
        the deadline; a second 429 is an error."""
        outcome = self._send(kind, dois)
        if outcome[0] != "throttled":
            return outcome
        delay = outcome[1]
        if time.monotonic() + delay >= self.deadline:
            return "deadline", None
        time.sleep(delay)
        outcome = self._send(kind, dois)
        return ("error", None) if outcome[0] == "throttled" else outcome

    def _send(self, kind: str, dois: list[str]):
        left = self.deadline - time.monotonic()
        if left <= 0:
            return "deadline", None
        # Bounded by the time left: a slot past the deadline is never waited
        # for (the limiter returns None and reserves nothing).
        if self.limiter.wait(max_seconds=left) is None:
            return "deadline", None
        if time.monotonic() >= self.deadline:   # the wait itself can cross it
            return "deadline", None
        params = {"filter": ",".join(f"{kind}:{d}" for d in dois), "rows": ROWS}
        if self.mailto:
            params["mailto"] = self.mailto
        try:
            reply = _http_get(params)
            status, body = reply[0], reply[1]
            headers = reply[2] if len(reply) > 2 else {}
        except Exception:
            return "error", None
        finally:
            try:
                self.limiter.record()
            except Exception:
                pass
        if status == 429:
            return "throttled", _retry_after(headers)
        if status in (400, 414):
            return "split", None
        if status != 200 or not isinstance(body, dict):
            return "error", None
        message = body.get("message")
        items = message.get("items") if isinstance(message, dict) else None
        if not isinstance(items, list):
            return "error", None
        total = message.get("total-results")
        if isinstance(total, int) and total > len(items):
            return "split", None   # truncated: never read as "nothing there"
        return "ok", [i for i in items if isinstance(i, dict)]

    def query(self, kind: str, dois: list[str]):
        """Items for these DOIs, plus {doi: "ok"|"error"|"deadline"}."""
        items, state = [], {}
        queue = [list(dois)]
        while queue:
            chunk = queue.pop(0)
            if self.stop:
                state.update({d: self.stop for d in chunk})
                continue
            outcome, got = self.request(kind, chunk)
            if outcome == "deadline":
                self.stop = "deadline"
                state.update({d: "deadline" for d in chunk})
            elif outcome == "split":
                if len(chunk) > 1:
                    half = len(chunk) // 2
                    queue[0:0] = [chunk[:half], chunk[half:]]
                else:
                    state[chunk[0]] = "error"
            elif outcome == "error":
                state.update({d: "error" for d in chunk})
                self.consecutive_errors += 1
                if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    self.stop = "error"
            else:
                self.consecutive_errors = 0
                items.extend(got)
                state.update({d: "ok" for d in chunk})
        return items, state


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------

_ON_TOKENS = ("1", "true", "yes", "on")
_OFF_TOKENS = ("0", "false", "no", "off")


def _skip_reason() -> str | None:
    """PHILLIT_STATUS_NOTICE, read at call time: unset, blank or an on token
    runs the pass; an off token or an unrecognized value skips it with a
    reason. Skipping licenses no status fact, the safe direction."""
    value = os.environ.get("PHILLIT_STATUS_NOTICE", "").strip().lower()
    if not value or value in _ON_TOKENS:
        return None
    if value in _OFF_TOKENS:
        return "status lookup disabled by PHILLIT_STATUS_NOTICE"
    return ("unrecognized PHILLIT_STATUS_NOTICE value -- expected 1/true/yes/on, "
            "0/false/no/off, or unset; status lookup skipped")


def empty_report() -> dict:
    return {"status": "complete", "reason": None, "stop_reason": None,
            "looked_up": 0, "stamped": {},
            "not_found": 0, "identity_mismatch": 0, "arxiv_skipped": 0,
            "errors": 0, "deadline": 0, "unmapped_types": {}, "sources": {},
            "malformed": 0, "splice_failed": 0, "reverse_unchecked": 0,
            "unresolved": 0, "late_promotion": 0, "entries": {}}


def _bump(d: dict, key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _entry_items(doi: str, record: dict, notices: list, reverse_ok: bool, report: dict):
    """The (category, notice DOI) items for one entry whose forward record
    matched, and how many of its relations could not be resolved (a type
    that maps to no category, or a mapped one with a malformed notice DOI).
    Counts unmapped types, sources and malformed items once per distinct
    relation."""
    items, unmapped, malformed, sourced = set(), set(), set(), set()
    relations = []   # (type token, raw notice doi, source)
    for u in record.get("updated-by") or []:
        if isinstance(u, dict):
            relations.append((u.get("type"), u.get("DOI"), u.get("source")))
    if reverse_ok:
        for n in notices:
            for u in n.get("update-to") or []:
                if isinstance(u, dict) and normalize_doi(u.get("DOI") or "") == doi:
                    relations.append((u.get("type"), n.get("DOI"), u.get("source")))
    for token, raw, source in relations:
        category = category_of(token)
        if category is None:
            unmapped.add((str(token), str(raw)))
            continue
        notice = _notice_doi(raw, doi, category)
        if notice is None:
            malformed.add((category, str(raw)))
            continue
        items.add((category, notice))
        if isinstance(source, str) and source:
            sourced.add((category, notice, source))
    for token, _raw in unmapped:
        _bump(report["unmapped_types"], token)
    report["malformed"] += len(malformed)
    for _c, _n, source in sourced:
        _bump(report["sources"], source)
    if record.get("type") == "posted-content" and record.get("subtype") == "preprint":
        items.add((PREPRINT, None))
    return items, len(unmapped) + len(malformed)


def lookup_status(entries: dict, deadline: float):
    """Look up every eligible entry. `entries` maps a label (the barrier uses
    "<bib>:<key>") to {"fields": parsed fields, "evidence_none": bool,
    "entry_type": BibTeX type (optional; checked against CrossRef's type)}.
    Returns ({label: field value}, report). Never raises: a crash keeps what
    was resolved and reports itself "partial" with the stage in `reason`."""
    report = empty_report()
    values: dict = {}
    skip = _skip_reason()
    if skip:
        report["status"], report["reason"] = "skipped", skip
        return values, report
    stage = "classifying entries"
    try:
        wanted: dict[str, list] = {}
        etypes: dict = {}
        for label, entry in (entries or {}).items():
            fields = (entry or {})["fields"] or {}
            doi, why = request_doi(fields.get("doi"))
            if why != "no-doi" and entry.get("evidence_none"):
                doi, why = None, "evidence-none"
            if doi is None:
                report["entries"][label] = f"not_requested:{why}"
                if why == "arxiv":
                    report["arxiv_skipped"] += 1
                continue
            wanted.setdefault(doi, []).append((label, fields))
            etypes[label] = entry.get("entry_type")

        stage = "querying CrossRef"
        run = _Pass(deadline)
        distinct = sorted(wanted)
        fwd_items, fwd_state, rev_items, rev_state = [], {}, [], {}
        for start in range(0, len(distinct), BATCH_SIZE):
            chunk = distinct[start:start + BATCH_SIZE]
            got, state = run.query("doi", chunk)
            fwd_items += got
            fwd_state.update(state)
            got, state = run.query("updates", chunk)
            rev_items += got
            rev_state.update(state)

        stage = "mapping results"
        records = {}
        for item in fwd_items:
            d = normalize_doi(item.get("DOI") or "") if isinstance(item.get("DOI"), str) else ""
            if d in wanted:
                records.setdefault(d, item)
        report["looked_up"] = sum(1 for d in distinct if fwd_state.get(d) == "ok")
        for doi in distinct:
            fstate, rstate = fwd_state.get(doi, "error"), rev_state.get(doi, "error")
            for label, fields in wanted[doi]:
                if fstate != "ok":
                    report["entries"][label] = fstate
                    continue
                record = records.get(doi)
                if record is None:
                    report["entries"][label] = "not_found"
                    continue
                if not identity_matches(fields, record, etypes.get(label)):
                    report["entries"][label] = "identity_mismatch"
                    continue
                items, unresolved = _entry_items(doi, record, rev_items, rstate == "ok", report)
                if unresolved:
                    report["unresolved"] += 1
                if items:
                    values[label] = format_items(items)
                    report["entries"][label] = "stamped"
                elif rstate != "ok":
                    report["entries"][label] = rstate
                elif unresolved:
                    # Not "checked_none": CrossRef lists a relation this pass
                    # could not read, which may be a status fact.
                    report["entries"][label] = "unresolved"
                else:
                    report["entries"][label] = "checked_none"
        # Every DOI whose forward query answered but whose reverse query did
        # not, whatever its entry state: notices only the reverse query finds
        # were never checked, so the pass is partial even when every entry
        # reads "stamped", "not_found" or "identity_mismatch".
        report["reverse_unchecked"] = sum(
            1 for d in distinct
            if fwd_state.get(d) == "ok" and rev_state.get(d, "error") != "ok")
        if run.stop == "error":
            report["stop_reason"] = (f"stopped after {MAX_CONSECUTIVE_ERRORS} consecutive "
                                     "CrossRef request errors")
    except Exception as exc:
        report["status"] = "partial"
        report["stop_reason"] = f"unexpected error while {stage}: {type(exc).__name__}"
    finally:
        settle(report)
    return values, report


def settle(report: dict) -> None:
    """Recount the entry states and make a non-complete status explain itself."""
    states = list(report["entries"].values())
    report["not_found"] = states.count("not_found")
    report["identity_mismatch"] = states.count("identity_mismatch")
    report["errors"] = states.count("error")
    report["deadline"] = states.count("deadline")
    report["splice_failed"] = states.count("splice_failed")
    report["late_promotion"] = states.count("not_checked:late-promotion")
    causes = []
    if report["errors"]:
        causes.append(f"{report['errors']} entr{'y' if report['errors'] == 1 else 'ies'} "
                      "not checked (CrossRef request error)")
    if report["deadline"]:
        causes.append(f"{report['deadline']} entr{'y' if report['deadline'] == 1 else 'ies'} "
                      "not checked (shared metadata deadline passed)")
    if report.get("reverse_unchecked"):
        causes.append(f"{report['reverse_unchecked']} DOI(s) checked without the "
                      "reverse CrossRef query (request error or deadline)")
    if report.get("unresolved"):
        causes.append(f"{report['unresolved']} entr{'y' if report['unresolved'] == 1 else 'ies'} "
                      "with a CrossRef update relation PhilLit could not map (unmapped "
                      "type or malformed notice DOI; see unmapped_types)")
    if report["late_promotion"]:
        causes.append(f"{report['late_promotion']} entr{'y' if report['late_promotion'] == 1 else 'ies'} "
                      "promoted past EVIDENCE-NONE after the lookup, so never checked")
    if report["splice_failed"]:
        causes.append(f"{report['splice_failed']} stamp(s) did not land (splice failed)")
    parts = [r for r in [report.get("stop_reason"), *causes] if r]
    if parts:
        report["status"] = "partial"
        report["reason"] = "; ".join(parts)
    elif report["status"] != "complete":
        report["reason"] = report["reason"] or "status pass did not finish"
    else:
        report["reason"] = None


def record_stamp(report: dict, label: str, value: str, took: bool) -> None:
    """The barrier's splice outcome for one planned value: count what landed
    by category, or mark the entry splice_failed (status turns partial)."""
    if took:
        for cat in categories(value):
            _bump(report["stamped"], cat)
    else:
        report["entries"][label] = "splice_failed"
    settle(report)
