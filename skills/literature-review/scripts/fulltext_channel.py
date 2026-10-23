"""The one owner of the file grammar of the service full-text channel.

When a hosted review needs open-access PDFs, `acquire_fulltext.py` does not
fetch them: it drops a request file into a request directory, a worker
process answers, and the engine reads the answer. The worker side belongs to
PS-79 (phillit-service); this module defines what both sides read and write.
Nothing else in the engine spells a file name or a field of these files.

FILES, all in the request directory, named `<request_id>` plus a suffix:
- `<id>.request.json` (engine writes, once): `{"schema": 1, "request_id",
  "mode", "identities": [{"key", "doi", "title", "surname", "year"}, ...]}`.
  `key` is `fulltext.canonical_identity`; the other four fields are the
  identity as stored (`null` kept). The file is ASCII (`ensure_ascii`).
- `<id>.response.json` (worker writes, rewritten atomically after EACH
  outcome): `{"schema": 1, "request_id", "complete": bool, "outcomes":
  {key: {"status", "stem", "detail"}}}`. A key absent from `outcomes` has no
  answer yet.
- `<id>.closed` (engine writes, empty): the engine has stopped waiting.

WRITE ORDER the worker follows: copy a found work's record into the review's
store FIRST, then rewrite the response naming its `stem`; set `complete` true
only in the rewrite that carries the last outcome. A response may therefore
be read at any moment and never names a stem that is not yet in the store.

GRAMMAR: `request_id` matches `REQUEST_ID_RE` (`<mode>-<16 hex>` from
`new_request_id`); at most `MAX_PER_REQUEST` identities per request, each
string field at most `MAX_FIELD_CHARS`, the request file at most
`MAX_REQUEST_BYTES`. `status` is one of `STATUSES`: `found` (stem names the
stored record), `none` (no open copy; detail `no_doi` when the work has no
DOI), `unlicensed` (a copy exists, its licence refuses reuse), `failed`.
`detail` is a short token or null; for `failed` it is `identity_rejected`,
`timeout`, `too_large`, `not_pdf`, `blocked_host` or `removed`, anything else
reads as unavailable.

DEADLINE: the engine waits a bounded time (`wait_for_response`). A key still
absent from `outcomes` when it stops is reported as `deadline`, and the
engine writes `<id>.closed` so the worker can drop the remaining work.

A reader never trusts a response: an unreadable file, a wrong schema or a
foreign `request_id` is no response, and every outcome is normalized to the
four statuses (`read_response`). Pure apart from the file helpers
(`write_request`, `read_response`, `write_closed`, `wait_for_response`).
"""

import json
import re
import secrets
import sys
import time
from pathlib import Path
from typing import Optional

_here = str(Path(__file__).resolve().parent)
sys.path.insert(0, _here)
from fulltext import canonical_identity, read_text, write_text_atomic  # noqa: E402

sys.path.remove(_here)


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SCHEMA = 1
REQUEST_ID_RE = re.compile(r"^[a-z0-9-]{1,40}$")
MAX_PER_REQUEST = 50
MAX_FIELD_CHARS = 500
MAX_REQUEST_BYTES = 256 * 1024
REQUEST_SUFFIX = ".request.json"
RESPONSE_SUFFIX = ".response.json"
CLOSED_SUFFIX = ".closed"
STATUSES = frozenset({"found", "none", "unlicensed", "failed"})
POLL_SECONDS = 2.0

_NOT_FOUND_FAILURES = frozenset({"timeout", "too_large", "not_pdf", "blocked_host", "removed"})
_BAD_OUTCOME = {"status": "failed", "stem": None, "detail": "bad_outcome"}


# --------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------

def new_request_id(mode: str) -> str:
    return f"{mode}-{secrets.token_hex(8)}"


def identity_payload(identity: dict) -> dict:
    """The request form of one identity. Raises ValueError("field_too_long")
    when a string value exceeds MAX_FIELD_CHARS."""
    payload = {"key": canonical_identity(identity)}
    for name in ("doi", "title", "surname", "year"):
        value = identity.get(name)
        if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
            raise ValueError("field_too_long")
        payload[name] = value
    return payload


def write_request(request_dir: Path, request_id: str, mode: str, payloads: list[dict]) -> Path:
    """Write `<id>.request.json` atomically; returns its path. Raises
    ValueError on a bad id, too many payloads or an oversize file."""
    if not REQUEST_ID_RE.match(request_id):
        raise ValueError("bad_request_id")
    if len(payloads) > MAX_PER_REQUEST:
        raise ValueError("too_many_identities")
    text = json.dumps({"schema": SCHEMA, "request_id": request_id, "mode": mode,
                       "identities": payloads}, ensure_ascii=True)
    if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("request_too_large")
    request_dir = Path(request_dir)
    request_dir.mkdir(parents=True, exist_ok=True)
    path = request_dir / (request_id + REQUEST_SUFFIX)
    write_text_atomic(path, text)
    return path


def write_closed(request_dir: Path, request_id: str) -> None:
    write_text_atomic(Path(request_dir) / (request_id + CLOSED_SUFFIX), "")


# --------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------

def _str_or_none(value) -> Optional[str]:
    return value if isinstance(value, str) else None


def _outcome(raw) -> dict:
    if not isinstance(raw, dict) or raw.get("status") not in STATUSES:
        return dict(_BAD_OUTCOME)
    return {"status": raw["status"], "stem": _str_or_none(raw.get("stem")),
            "detail": _str_or_none(raw.get("detail"))}


def read_response(request_dir: Path, request_id: str) -> Optional[dict]:
    """The normalized response, `{"complete": bool, "outcomes": {key:
    {"status", "stem", "detail"}}}`, or None when the file is absent,
    unreadable, not a JSON object, of another schema or for another id."""
    path = Path(request_dir) / (request_id + RESPONSE_SUFFIX)
    try:
        obj = json.loads(read_text(path))
    except (OSError, ValueError, RecursionError):
        return None
    if (not isinstance(obj, dict) or obj.get("schema") != SCHEMA
            or obj.get("request_id") != request_id):
        return None
    raw = obj.get("outcomes")
    outcomes = {key: _outcome(value) for key, value in raw.items()} if isinstance(raw, dict) else {}
    return {"complete": bool(obj.get("complete")), "outcomes": outcomes}


def wait_for_response(request_dir: Path, request_id: str, seconds: float, *,
                      clock=time.monotonic, sleep=time.sleep) -> dict:
    """Poll `read_response` until it is complete or `seconds` have passed on
    `clock` (always at least one read). Returns the last response read, or an
    empty incomplete one when none was."""
    start = clock()
    last = {"complete": False, "outcomes": {}}
    while True:
        response = read_response(request_dir, request_id)
        if response is not None:
            last = response
            if response["complete"]:
                return last
        left = seconds - (clock() - start)
        if left <= 0:
            return last
        sleep(min(POLL_SECONDS, left))


def source_outcome(entry: Optional[dict]) -> tuple[str, list[str]]:
    """The engine outcome and detail list for one key's response entry
    (None: the worker had not answered when the engine stopped waiting)."""
    if entry is None:
        return "deadline", []
    status = entry.get("status")
    detail = entry.get("detail")
    details = [detail] if detail else []
    if status == "found":
        return "acquired", []
    if status == "none":
        return ("no_doi", []) if detail == "no_doi" else ("not_found", details)
    if status == "unlicensed":
        return "unlicensed", details
    if detail == "identity_rejected":
        return "rejected", ["identity_rejected"]
    if detail in _NOT_FOUND_FAILURES:
        return "not_found", [detail]
    return "unavailable", [detail or "failed"]
