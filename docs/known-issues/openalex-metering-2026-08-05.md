# OpenAlex began metering the API — PhilLit runs unauthenticated on the $0.10/day tier

**Observed**: 2026-08-05, while measuring venue signals for ROADMAP item 3 D.
**Severity**: Medium. Does not fail a run, but a heavy day silently starves
Phase 3 searches, and the failure surfaces as five pointless backoff attempts
per call rather than as "the budget is gone."
**Status**: **Key support BUILT 2026-08-05** (same day). PhilLit now sends
`api_key` on every OpenAlex request when `OPENALEX_API_KEY` is set, and both
the search path and the abstract path stop retrying on budget exhaustion
instead of sleeping through it. Remaining: nothing in the code — the user
supplies the key (free, `openalex.org/settings/api`). An unkeyed install
behaves exactly as before.

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

## Defect: the 429 handler could not tell "slow down" from "budget gone" — FIXED

`search_openalex.py` and `get_abstract.py` treated every 429 as transient and
handed it to `ExponentialBackoff` (5 attempts). Neither read `Retry-After` nor
the `Insufficient budget` body, so exhaustion cost four escalating sleeps per
call and then failed, while telling the user "Rate limited, backing off" —
wrong and unactionable.

The cost was worse than it looks. `ExponentialBackoff.wait` clamps
`Retry-After` to `max_delay` (60 s), so it does *not* sleep for the 22.6 hours
the header asks — but 4 × 60 s per call × 16–36 search calls is **1–2.4 hours
of pure sleeping per review** before the run gives up on OpenAlex.

`rate_limiter.openalex_budget_exhausted(response)` now distinguishes them: a
429 whose `Retry-After` exceeds 300 s, or whose body carries an
`Insufficient budget` / `Rate limit exceeded` marker, is terminal. The search
path returns a non-recoverable `budget_exhausted` error, the abstract path
skips OpenAlex and moves down the resolver chain, and both name the fix. It
never raises: an unexpected response shape reads as "not exhausted", so the
caller falls back to ordinary backoff.

## Remedy — BUILT 2026-08-05

1. `rate_limiter.openalex_params(email)` is the one owner of OpenAlex query
   auth: `mailto` plus `api_key` when `OPENALEX_API_KEY` is set. Used by
   `search_openalex.py` (both the search and single-work paths),
   `get_abstract.py` (the DOI path) and `check_setup.py`. Resolved at **call**
   time, never import time — the workspace `.env` loads in each CLI's `main()`,
   which runs after the module is imported, so an import-time read would
   silently see no key (same rule as `rate_limiter.user_agent()`).
2. Budget exhaustion fails fast and legibly (above).
3. `.env.example` documents the key with the numbers and the 30-second signup
   link; `check_setup.py` reports whether a key is in use (`[API key: $1/day
   budget]` vs a `no API key` nudge) and surfaces exhaustion explicitly rather
   than reporting "unreachable".

The key is **optional by design**: with none set, every request is byte-identical
to before. Set it in the workspace `.env` (preferred — that is what
`load_dotenv(find_dotenv(usecwd=True))` reads) or in the shell environment.

This unblocks item 3 D (per-venue lookups need the filter/search budget) and
item 3 F's live run.
