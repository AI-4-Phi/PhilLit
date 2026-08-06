# OpenAlex began metering the API — PhilLit runs unauthenticated on the $0.10/day tier

**Observed**: 2026-08-05, while measuring venue signals for ROADMAP item 3 D.
**Severity**: Medium. Does not fail a run, but a heavy day silently starves
Phase 3 searches, and the failure surfaces as five pointless backoff attempts
per call rather than as "the budget is gone."
**Status**: Open. The one-line remedy (support a free API key) is not built.

## What happened

A per-venue measurement loop (~200 `sources?search=` calls) exhausted the
whole daily allowance. The 429 body is explicit:

```
HTTP/2 429
retry-after: 81471
x-ratelimit-limit: 1000
x-ratelimit-limit-usd: 0.1
x-ratelimit-credits-required: 10
x-ratelimit-cost-required-usd: 0.001
{"error":"Rate limit exceeded","message":"Insufficient budget. This request
 costs $0.001 but you only have $0 remaining. Resets at midnight UTC. ..."}
```

So the model is a **daily spend budget**, not a requests-per-second limit:
1,000 credits = $0.10/day unauthenticated, and a full-text search costs 10
credits. That is ~**100 search calls per day** for an unauthenticated client.
`retry-after` is ~22.6 hours — the budget resets at midnight UTC, not after a
backoff.

## The tiers (OpenAlex `developers.openalex.org/guides/authentication`)

| | no key (what PhilLit does today) | free API key |
|---|---|---|
| daily budget | **$0.10/day** | **$1/day** |
| single-entity retrieval (e.g. `works/doi:…`) | metered | **unlimited** |
| list + filter queries | ~1,000/day | **10,000/day** |
| full-text search | ~100/day | **1,000/day** |

The key is created at `openalex.org/settings/api` (account required, ~30 s)
and passed as the query parameter `api_key=…`.

## PhilLit's exposure — measured, not inferred

- **Abstract resolution is safe.** `get_abstract.py:198` resolves via
  `https://api.openalex.org/works/doi:<doi>` — a single-entity lookup, which
  is *unlimited* with a key and the cheap class without one. This is the path
  behind 846 of the 2,121 abstracts in the local corpora.
- **Phase 3 search is the exposed path.** `search_openalex.py:278` sets
  `params["search"] = query` — the 10-credit class. Counting saved
  `openalex_*.json` envelopes across the 42 corpora that have them: **median
  16 search calls per review, max 36** (754 total). Unauthenticated that is
  only ~3–6 reviews per day before Phase 3 loses OpenAlex entirely; with a
  free key it is ~30–60.
- **A dev measurement and a live run share one budget.** This session's
  measurement left OpenAlex unusable for the rest of the UTC day — worth
  knowing before scheduling item 3 F's live run.

## Defect: the 429 handler cannot tell "slow down" from "budget gone"

`search_openalex.py:224` and `:346` treat any 429 as transient and hand it to
`ExponentialBackoff` (5 attempts). Neither reads `Retry-After` nor the
`Insufficient budget` body, so budget exhaustion costs five escalating sleeps
per call and then fails — 16–36 times per review — and the user is told
"Rate limited, backing off", which is wrong and unactionable.

Cheap fix, alongside key support: treat a 429 whose `Retry-After` exceeds the
remaining backoff budget (or whose body says `Insufficient budget`) as
terminal for the run, fail fast once, and say so — *"OpenAlex daily budget
exhausted, resets at midnight UTC; set OPENALEX_API_KEY for 10× headroom."*

## Remedy (not built)

1. Add `OPENALEX_API_KEY` support to the OpenAlex scripts (`api_key=` query
   param, alongside the existing `mailto`), `.env.example`, and
   `check_setup.py` — optional, so an unkeyed install keeps working.
2. Fail fast and legibly on budget exhaustion (above).
3. Note in the setup skill that the key is free and worth 10×.

This blocks item 3 D (per-venue lookups need the filter/search budget) and
degrades item 3 F's live run.
