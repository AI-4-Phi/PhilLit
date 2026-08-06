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

## 2026-08-06: the key in the environment is being REJECTED — needs replacing

While reviewing item 3 D's build, a subagent probing the live API got
`{"error":"Invalid or missing API key"}` for the `OPENALEX_API_KEY` reachable
from the interactive shell profile, and a plain 429 unkeyed. Almost certainly
the key that was rotated out on the night of 2026-08-05 (it had leaked into a
session transcript); the profile still holds the old value.

Two things this is **not**:

- It is not a mechanism bug. `developers.openalex.org` still documents the key
  as a **query parameter** (`api_key=YOUR_KEY`), which is exactly what
  `rate_limiter.openalex_params()` sends. Re-checked 2026-08-06.
- It is not a code change. Nothing to fix here — a fresh key from
  `openalex.org/settings/api` needs to reach the process.

**Where to put the new key: the workspace `.env`.** That is the path
`load_dotenv(find_dotenv(usecwd=True))` reads, and the only one hooks and
subagents inherit; a value that lives only in an interactive-shell profile is
invisible to non-interactive Bash calls.

Provenance note: the rejection was observed by a review subagent, not
re-verified in the controller session (reading `.env` and the shell profile is
blocked there, correctly — they hold credentials). Confirm with one keyed
request before scheduling item 3 F's live run.

One unresolved discrepancy, recorded rather than acted on: the current
`developers.openalex.org/llms.txt` summary states the unkeyed budget as
**$0.01/day**, while the `x-ratelimit-limit-usd: 0.1` header quoted below says
$0.10/day. The header is the stronger evidence and the table below keeps it;
if unkeyed calls start failing ten times sooner than expected, this is why.

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

## Does a user need a key? No — measured 2026-08-05

**One review costs roughly 210-430 credits of the unkeyed 1,000/day**, so
**2-4 reviews a day run fine with no key**. Breakdown: 16-36 searches at 10
credits (160-360) plus ~50-70 single-work DOI lookups at 1 credit. A key is
therefore for heavy days only — including *development* days, which is how
this was found. The key stays **optional**, `.env.example` says so plainly,
and `check_setup.py` reports its absence neutrally rather than nagging; only
actual exhaustion carries a call to action.

**Value asymmetry worth knowing before anyone proposes dropping OpenAlex.**
Measured across the 42 corpora with saved envelopes:

| use | class | contribution |
|---|---|---|
| abstract resolution (`works/doi:`) | 1 credit, unmetered with a key | **1,711 abstracts (45%** of all resolved). It is tried only *after* S2 misses, so these are papers that would otherwise have **no abstract at all** — and under the evidence tier that means dropping from `EVIDENCE-ABSTRACT` to CONTEXT/EXISTENCE, which restricts what the writer may say. |
| search (`search_openalex.py`) | 10 credits | **175 cited works, 5.8%** of the 3,005 DOI-bearing works in delivered bibliographies were reachable only via OpenAlex search (~4 per review). Its envelopes carry 16,320 DOIs of which 15,297 no other engine surfaced, so the recall is broad but mostly not *used*. |

So the load-bearing use is the cheap one and the metered use buys ~4 extra
cited works per review. Caveat on that 5.8%: "OpenAlex-only" means no other
engine's *saved envelope* carried the DOI — another engine might have found it
under a different query — so it measures what did come only from there, not
what could only ever come from there. If credit pressure ever needs relieving,
gating the search half (e.g. run it only when S2 returns thin results) cuts
~75% of the spend; but 5.8% of cited works is real coverage and
"Comprehensive" is priority 2 in this project, so that is not a cost-only call.

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
