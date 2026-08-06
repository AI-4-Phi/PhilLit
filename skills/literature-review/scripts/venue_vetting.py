"""Item 3 D: flag entries published in venues OpenAlex barely records.

The rule (validated 2026-08-05 against 9 predatory-shape candidates found by a
free name scan of all 928 corpus venues, and 48 legitimate philosophy venues
chosen to stress it -- open-access, non-Anglophone, area-specialist, new):

    flag iff the venue RESOLVES in OpenAlex
            AND is_core is false
            AND is_in_doaj is false
            AND h_index < 15,

evaluated over the HIGHEST-h same-named source. Result: 4/9 candidates
flagged, 0/48 false positives, and the FP-free plateau runs to T=19 while the
4-candidate floor starts at T=14, so 15 sits mid-plateau.

Three properties are load-bearing and must not be "simplified" away:

- `is_core` ALONE is prohibited: it misfires on 7 of the 120 most-frequent
  corpus venues, every one legitimate (Journal of Moral Philosophy, Political
  Theory, Phronesis, Kantian Review, ...).
- DOAJ is useless as a NEGATIVE signal (Mind, Nous and Philosophical Review
  are all `is_in_doaj: false`) but sound as a POSITIVE rescue -- it is what
  saves Norsk Filosofisk Tidsskrift at h=11.
- Unresolved is never flagged. Absence of evidence is not evidence, and a
  false discredit costs more than a miss.

Everything here fails OPEN: any error, missing key or exhausted budget yields
no flags at all.
"""
from __future__ import annotations

import os
import re
import sys
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
        return {"schema_version": RECORD_SCHEMA_VERSION, "resolved": False}
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "resolved": True,
        "matched_name": best.get("display_name"),
        # Stored RAW: None means "OpenAlex reports no h-index", which is not
        # the same fact as h=0 and must not be flagged (see is_flagged).
        "h_index": (best.get("summary_stats") or {}).get("h_index"),
        "is_core": bool(best.get("is_core")),
        "is_in_doaj": bool(best.get("is_in_doaj")),
        "works_count": best.get("works_count"),
    }


def is_flagged(record: dict | None, threshold: int = H_INDEX_THRESHOLD) -> bool:
    """The three-signal rule. Anything unknown reads as NOT flagged.

    A resolved source with NO h-index is not flagged: every venue in the
    validation set had one, so a missing value is unmeasured rather than low,
    and this rule's whole design point is that a false discredit costs more
    than a miss.
    """
    if not record or not record.get("resolved"):
        return False
    h_index = record.get("h_index")
    if h_index is None:
        return False
    return (
        not record.get("is_core")
        and not record.get("is_in_doaj")
        and h_index < threshold
    )


def _cache_key_for(name: str) -> str:
    return cache_key(source="venue", name=normalize_venue_name(name))


def cache_get(name: str) -> dict | None:
    record = get_cache(_cache_key_for(name), ttl=CACHE_TTL_SECONDS)
    if not isinstance(record, dict):
        return None
    if record.get("schema_version") != RECORD_SCHEMA_VERSION:
        return None  # shape changed -- re-look-up rather than misread
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
            params={**params, "filter": f"display_name.search:{name}", "per_page": 25},
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
    """
    result = {"status": "complete", "reason": None, "looked_up": 0,
              "cache_hits": 0, "skipped_cap": 0, "flagged": [],
              "evidence": {}, "verdicts": {}}
    distinct = sorted({normalize_venue_name(n) for n in (names or []) if normalize_venue_name(n)})
    if not distinct:
        return result

    params = openalex_params(os.environ.get("OPENALEX_EMAIL", ""))
    if "api_key" not in params:
        result["status"] = "skipped"
        result["reason"] = ("no OPENALEX_API_KEY -- venue vetting needs the free key "
                            "so it does not spend the unauthenticated search budget")
        return result

    for venue in distinct:
        record = cache_get(venue)
        if record is not None:
            result["cache_hits"] += 1
        else:
            if result["looked_up"] >= MAX_LOOKUPS_PER_RUN:
                result["skipped_cap"] += 1
                continue
            record, outcome = lookup_venue(venue, params)
            if outcome == "budget_exhausted":
                result["status"] = "budget_exhausted"
                break
            result["looked_up"] += 1
            if outcome != "ok" or record is None:
                continue  # unknown venue -- no verdict, no flag
            cache_put(venue, record)
        flagged = is_flagged(record)
        result["verdicts"][venue] = flagged
        if flagged:
            result["flagged"].append(venue)
            result["evidence"][venue] = record
    result["flagged"].sort()
    return result
