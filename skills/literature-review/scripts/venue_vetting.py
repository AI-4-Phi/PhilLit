"""Item 3 D: flag entries published in venues OpenAlex barely records.

The rule (validated 2026-08-05 against 9 predatory-shape candidates found by a
free name scan of all 928 corpus venues, and 48 legitimate philosophy venues
chosen to stress it -- open-access, non-Anglophone, area-specialist, new):

    flag iff the venue RESOLVES in OpenAlex
            AND is_core is false
            AND is_in_doaj is false
            AND h_index < 15,

evaluated over the HIGHEST-h same-named source. Result: 4/9 candidates
flagged, 0/48 false positives. The FP-free plateau runs from T=14 (where the
4-candidate floor starts) to T=19; T=15 sits at the CONSERVATIVE end of that
plateau, one step in from the floor, not at its midpoint.

Three properties are load-bearing and must not be "simplified" away:

- `is_core` ALONE is prohibited: it misfires on 7 of the 120 most-frequent
  corpus venues, every one legitimate (Journal of Moral Philosophy, Political
  Theory, Phronesis, Kantian Review, ...).
- DOAJ is useless as a NEGATIVE signal (Mind, Nous and Philosophical Review
  are all `is_in_doaj: false`) but sound as a POSITIVE rescue -- it is what
  saves Norsk Filosofisk Tidsskrift at h=11.
- Unresolved is never flagged. Absence of evidence is not evidence, and a
  false discredit costs more than a miss.

Nothing here raises. A missing OPENALEX_API_KEY or an empty name list
produces no flags at all (status "skipped" or a no-op "complete" pass,
respectively). A pass that hits a transport error, exhausts its OpenAlex
budget, or trips one of the two bounds (MAX_CONSECUTIVE_ERRORS,
PASS_DEADLINE_SECONDS) KEEPS every verdict it did resolve and reports itself
as "partial" rather than discarding them -- an independently resolved
verdict from earlier in the pass is still evidence-backed even though the
pass as a whole did not finish.

Two documented limits:

- Venue names are matched by normalized full name only. Abbreviations and
  BibTeX macros (`J. Philos.`, `journal = jphil`) do not resolve and are
  simply never flagged. PhilLit's own producers always write braced full
  venue names (docs/conventions.md), so this bites only on hand-imported
  bibliographies.
- The name fold strips non-ASCII letters. It is applied symmetrically to
  both sides of the comparison, so accented names still match; a wholly
  non-Latin name folds to empty and is skipped, which is fail-open.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "philosophy-research" / "scripts")
)

from search_cache import cache_key, get_cache, put_cache  # noqa: E402

import requests  # noqa: E402
from rate_limiter import (  # noqa: E402
    get_limiter,
    openalex_budget_exhausted,
    openalex_params,
)

VENUE_STATUS_FIELD = "venue_status"
STATUS_LOW_VISIBILITY = "low-visibility"

H_INDEX_THRESHOLD = 15
# Venue standing moves on a scale of years, and a name lookup costs 10 OpenAlex
# credits, so the cache is deliberately long-lived (measured: a review touches
# ~40-80 distinct journals).
CACHE_TTL_SECONDS = 180 * 24 * 3600
# Bounds the spend of a single run: 80 lookups = 800 of a keyed 10,000/day.
# Overflow is REPORTED, never silent.
MAX_LOOKUPS_PER_RUN = 80
# 80 cold names at a 30s timeout is 40 minutes inside the workflow's slowest
# step -- both bounds stop a pass early rather than let it run that long.
MAX_CONSECUTIVE_ERRORS = 3
PASS_DEADLINE_SECONDS = 120.0
# A stale CLEAR verdict costs a miss (tolerable); a stale FLAG keeps
# discrediting a venue that has since joined DOAJ, gone core, or grown past
# the threshold -- so flagged records get a much shorter TTL than clear ones.
FLAGGED_CACHE_TTL_SECONDS = 45 * 24 * 3600
RECORD_SCHEMA_VERSION = 1


def normalize_venue_name(name) -> str:
    """Fold a venue name to its comparison key.

    Same normalization on both sides of the match (bib field and OpenAlex
    display_name / alternate_titles), so `Politics, Philosophy & Economics`
    and `Politics Philosophy and Economics` are one venue.
    """
    s = (name or "").lower().replace("&", "and")
    s = re.sub(r"^(the)\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _h_of(hit: dict) -> int:
    return ((hit or {}).get("summary_stats") or {}).get("h_index") or 0


def select_best_hit(hits: list[dict]) -> dict | None:
    """The highest-h source among same-named ones (two `Phronesis` exist)."""
    if not hits:
        return None
    return max(hits, key=_h_of)


def record_from_hits(hits: list[dict]) -> dict:
    """The cacheable EVIDENCE record -- never a verdict.

    Caching the facts rather than the boolean means a future threshold change
    costs no OpenAlex credits.
    """
    best = select_best_hit(hits)
    if best is None:
        return {"schema_version": RECORD_SCHEMA_VERSION, "resolved": False,
                "fetched_at": time.time()}
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "resolved": True,
        "matched_name": best.get("display_name"),
        # Stored RAW throughout: None means "OpenAlex reports no value",
        # which is not the same fact as False/0 and must not be flagged (see
        # is_flagged). A missing/null/wrong-typed field must never read as
        # affirmative evidence for the rule.
        "h_index": (best.get("summary_stats") or {}).get("h_index"),
        "is_core": best.get("is_core"),
        "is_in_doaj": best.get("is_in_doaj"),
        "works_count": best.get("works_count"),
        "fetched_at": time.time(),
    }


def is_flagged(record: dict | None, threshold: int = H_INDEX_THRESHOLD) -> bool:
    """The three-signal rule. Anything unknown or malformed reads as NOT
    flagged -- never raises, whatever shape `record` is.

    A resolved source with NO h-index is not flagged: every venue in the
    validation set had one, so a missing value is unmeasured rather than low,
    and this rule's whole design point is that a false discredit costs more
    than a miss. `is_core`/`is_in_doaj` must be the exact boolean `False` (a
    missing key, `None`, or a truthy-but-wrong-typed value like the string
    `"false"` all read as "unknown", not "no") and `h_index` must be a real
    int, not a bool (Python's `isinstance(True, int)` is True) and not a
    numeric string.
    """
    if not isinstance(record, dict) or not record.get("resolved"):
        return False
    h_index = record.get("h_index")
    return (
        record.get("is_core") is False
        and record.get("is_in_doaj") is False
        and isinstance(h_index, int)
        and not isinstance(h_index, bool)
        and h_index < threshold
    )


def _cache_key_for(name: str) -> str:
    return cache_key(source="venue", name=normalize_venue_name(name))


def _is_bool_or_none(value) -> bool:
    return value is None or isinstance(value, bool)


def _is_int_or_none(value) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool))


def _valid_record_shape(record) -> bool:
    """Validate the cached record's SHAPE, not just its schema_version.

    A record that survived a schema-version match but has a malformed field
    (a string h_index, a stringly-typed is_core, ...) must still read as a
    cache miss -- schema_version alone does not guarantee the field types
    is_flagged() depends on.
    """
    if not isinstance(record, dict):
        return False
    if record.get("schema_version") != RECORD_SCHEMA_VERSION:
        return False
    resolved = record.get("resolved")
    if not isinstance(resolved, bool):
        return False
    if resolved:
        if not _is_int_or_none(record.get("h_index")):
            return False
        if not _is_bool_or_none(record.get("is_core")):
            return False
        if not _is_bool_or_none(record.get("is_in_doaj")):
            return False
    return True


def _flagged_record_expired(record: dict) -> bool:
    """Asymmetric TTL for a FLAGGED record: checked against the record's own
    `fetched_at`, not the cache file's mtime. A missing/malformed fetched_at
    is treated as expired -- fail toward re-checking, never toward keeping a
    stale discredit.
    """
    fetched_at = record.get("fetched_at")
    if not isinstance(fetched_at, (int, float)) or isinstance(fetched_at, bool):
        return True
    return (time.time() - fetched_at) > FLAGGED_CACHE_TTL_SECONDS


def cache_get(name: str) -> dict | None:
    record = get_cache(_cache_key_for(name), ttl=CACHE_TTL_SECONDS)
    if not _valid_record_shape(record):
        return None  # missing/malformed shape -- re-look-up rather than misread
    if is_flagged(record) and _flagged_record_expired(record):
        return None  # a stale FLAG is re-checked; a stale CLEAR is not
    return record


def cache_put(name: str, record: dict) -> None:
    put_cache(_cache_key_for(name), record)


OPENALEX_SOURCES_URL = "https://api.openalex.org/sources"
REQUEST_TIMEOUT = 30


def lookup_venue(name: str, params: dict) -> tuple[dict | None, str]:
    """One OpenAlex `sources` query. Returns (record|None, outcome).

    outcome: "ok" (record is authoritative, resolved or not),
             "budget_exhausted" (caller must stop -- Retry-After is the
             seconds to midnight UTC, so retrying burns the rest of the day),
             "error" (transport/HTTP; caller treats the venue as unknown).

    ONE attempt, deliberately: this is a plumbing pass whose failure mode is
    "no flag", so a backoff loop would buy nothing and cost the barrier time.
    """
    try:
        get_limiter("openalex").wait()
        response = requests.get(
            OPENALEX_SOURCES_URL,
            params={**params, "filter": f"display_name.search:{name}", "per_page": 200},
            timeout=REQUEST_TIMEOUT,
        )
        if openalex_budget_exhausted(response):
            return None, "budget_exhausted"
        if response.status_code != 200:
            return None, "error"
        target = normalize_venue_name(name)
        hits = []
        for source in (response.json().get("results") or []):
            names = [source.get("display_name") or ""] + list(
                source.get("alternate_titles") or [])
            # `display_name.search` is a FUZZY filter -- a search for "Ratio"
            # returns "Ratio Juris" too. Only exact normalized matches count.
            if any(normalize_venue_name(n) == target for n in names):
                hits.append(source)
        return record_from_hits(hits), "ok"
    except Exception:
        return None, "error"


def vet_venues(names) -> dict:
    """Resolve every distinct venue name and apply the rule. Never raises.

    Gated on OPENALEX_API_KEY: vetting runs AFTER Phase 3's searches, so
    spending the unauthenticated $0.10/day budget here would starve the next
    review's searches. A free key raises the budget to $1/day.

    Queries OpenAlex with the RAW venue name (per normalized key, the first
    raw spelling seen after sorting the raw inputs, so the choice is
    deterministic) -- the validated measurement queried raw names, and
    stripping punctuation before the query changes what OpenAlex's fuzzy
    search ranks. The cache key and the exact-match target stay normalized
    regardless of which raw spelling was queried.
    """
    result = {"status": "complete", "reason": None, "looked_up": 0,
              "cache_hits": 0, "skipped_cap": 0, "flagged": [],
              "evidence": {}, "verdicts": {}, "lookup_errors": 0,
              "errors": [], "capped": [], "unresolved": 0, "resolved": 0}
    raw_by_key: dict[str, str] = {}
    for raw in sorted(n for n in (names or []) if isinstance(n, str) and n.strip()):
        key = normalize_venue_name(raw)
        if key:
            raw_by_key.setdefault(key, raw)
    distinct = sorted(raw_by_key)
    if not distinct:
        return result

    params = openalex_params(os.environ.get("OPENALEX_EMAIL", ""))
    if "api_key" not in params:
        result["status"] = "skipped"
        result["reason"] = ("no OPENALEX_API_KEY -- venue vetting needs the free key "
                            "so it does not spend the unauthenticated search budget")
        return result

    deadline = time.monotonic() + PASS_DEADLINE_SECONDS
    consecutive_errors = 0

    for venue in distinct:
        record = cache_get(venue)
        if record is not None:
            result["cache_hits"] += 1
        else:
            # Cache hits do not count against the cap or the deadline -- only
            # a real network lookup does.
            if result["looked_up"] >= MAX_LOOKUPS_PER_RUN:
                result["skipped_cap"] += 1
                result["capped"].append(venue)
                if result["reason"] is None:
                    result["reason"] = f"lookup cap ({MAX_LOOKUPS_PER_RUN}) reached"
                continue
            if time.monotonic() >= deadline:
                result["skipped_cap"] += 1
                result["capped"].append(venue)
                if result["reason"] is None:
                    result["reason"] = (
                        f"pass deadline ({PASS_DEADLINE_SECONDS}s) exceeded "
                        f"after {result['looked_up']} lookups")
                continue
            record, outcome = lookup_venue(raw_by_key[venue], params)
            result["looked_up"] += 1  # a real request was made, win or lose
            if outcome == "budget_exhausted":
                result["status"] = "budget_exhausted"
                result["reason"] = "OpenAlex daily budget exhausted mid-pass"
                break
            if outcome != "ok" or record is None:
                result["lookup_errors"] += 1
                result["errors"].append(venue)
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    result["status"] = "partial"
                    result["reason"] = (
                        f"stopped after {MAX_CONSECUTIVE_ERRORS} consecutive lookup errors")
                    break
                continue  # unknown venue -- no verdict, no flag
            consecutive_errors = 0  # a successful lookup resets the streak
            cache_put(venue, record)
        flagged = is_flagged(record)
        result["verdicts"][venue] = flagged
        if record.get("resolved"):
            result["resolved"] += 1
        else:
            result["unresolved"] += 1
        if flagged:
            result["flagged"].append(venue)
            result["evidence"][venue] = record
    result["flagged"].sort()
    if result["status"] == "complete" and (result["lookup_errors"] or result["skipped_cap"]):
        result["status"] = "partial"
    return result
