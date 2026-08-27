# OpenAlex began metering the API — PhilLit runs unauthenticated on the $0.10/day tier

**Observed**: 2026-08-05, while measuring venue signals for ROADMAP
item 3 D, venue vetting.
**Severity**: Medium. Does not fail a run, but a heavy day silently starves
Phase 3 searches, and the failure surfaces as five pointless backoff attempts
per call rather than as "the budget is gone."
**Status**: **Key support BUILT 2026-08-05** (same day). PhilLit now sends
the key on every OpenAlex request when `OPENALEX_API_KEY` is set (since
v0.5.3 as an `Authorization: Bearer` header — the key never rides in the
URL), and both the search path and the abstract path stop retrying on
budget exhaustion instead of sleeping through it. An unkeyed install
behaves exactly as before.

**CLOSED 2026-08-07.** Johannes registered a working key and it is in place.
Verified end-to-end through the real code path, not just by presence: the
previously-held key was **unregistered, not stale** (OpenAlex answered 401/403,
"API key not found", under every documented mechanism while the same URL unkeyed
returned 200), and `vet_venues` reported `status: partial` naming exactly that.
With the new key the same call returns `status: complete`, and the live run
of item 3 F, Chicago a/b disambiguation, then completed a full keyed venue
pass — **40 venues looked up, 2 cache hits, 0
unresolved, 0 errors, 0 flagged**. That was the first time keyed venue vetting had
ever run against a registered key; the support was built correct but unexercised.

Two notes worth keeping:

- **A key added to a workspace `.env` reaches a run already in flight.** Every CLI
  script calls `load_dotenv(find_dotenv(usecwd=True), override=True)` in `main()`,
  so `.env` beats the environment the `claude -p` process inherited at launch. No
  restart needed. Updating `~/.api_keys` does **not** reach a running process.
- Timing still matters per phase: on 2026-08-07 the key landed after most Phase 3
  researchers had run, so **6 entries were tagged `INCOMPLETE`** for metadata
  OpenAlex would have supplied, even though venue vetting (Phase 3→4) was keyed.

## If OpenAlex says "Invalid or missing API key"

The key is wrong or stale, not the plumbing: `developers.openalex.org` still
documents the key as a **query parameter** (`api_key=YOUR_KEY`) — that was
exactly what `rate_limiter.openalex_params()` sent at the time (re-checked
2026-08-06). Since v0.5.3 the key travels as an `Authorization: Bearer`
header via `rate_limiter.openalex_headers()` (presence checked by
`openalex_api_key()`); `openalex_params(email)` now owns `mailto` only.
Get a fresh one at `openalex.org/settings/api`.

**Put it in the workspace `.env`**, not a shell profile. `.env` is the path
`load_dotenv(find_dotenv(usecwd=True))` reads, and the only one hooks and
subagents inherit; a value exported only in an interactive-shell profile is
invisible to non-interactive Bash calls.

### 2026-08-06: isolated to the key VALUE, three ways

The key reachable from `~/.api_keys` (22 chars, alphanumeric) is rejected. The
diagnosis is no longer inferential — all four requests below went to
`api.openalex.org/sources?filter=display_name.search:Synthese`:

| request | HTTP |
|---|---|
| no key at all | **200** |
| `&api_key=<key>` (what the code sent then) | 401 |
| `Authorization: Bearer <key>` | 401 |
| `api_key: <key>` header | 401 |

Two conclusions. **The plumbing is not the problem**: the key fails under every
auth mechanism OpenAlex has ever documented, and the same URL without a key
succeeds. **The key is not registered**: the body is
`{"error":"Invalid or missing API key","message":"API key not found"}` — *not
found*, i.e. no such key exists on OpenAlex's side. That is a different failure
from expired, revoked, or over-budget, and no amount of re-checking the local
environment will change it. The only fix is to generate a new key at
`openalex.org/settings/api` and replace the value.

Also checked, to rule out the obvious near-miss: the interactive-shell profile
and `~/.api_keys` hold the **same** value (fingerprints compared without
printing either), and `~/.api_keys` defines it exactly once. There is no second,
working key hiding in the other location.

Trap when probing this by hand on dove: `zsh -ic 'printf "%s" "$VAR"'` captures
**iTerm2 shell-integration escape sequences** along with the value, so the
result looks like a 214-character key. Probe with `${VAR:+x}` and `${#VAR}`
inside the shell and print only the verdict.

Note the unkeyed tier answered **200** at 08:49 EDT 2026-08-06, so the daily
budget had reset and unkeyed OpenAlex was usable again at that moment.

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
and sent by PhilLit as an `Authorization: Bearer` header (v0.5.3+; OpenAlex
accepts both transports and the header takes precedence — verified live
2026-08-27).

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
  knowing before scheduling the live run of item 3 F, Chicago a/b
  disambiguation.

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

1. `rate_limiter.openalex_headers()` is the one owner of OpenAlex auth
   transport: an `Authorization: Bearer` header when `OPENALEX_API_KEY` is
   set (presence checked by `openalex_api_key()`), `{}` otherwise.
   `openalex_params(email)` owns `mailto` only — the key deliberately never
   rides in query params. Used by `search_openalex.py` (both the search and
   single-work paths), `get_abstract.py` (the DOI path) and `check_setup.py`.
   Resolved at **call** time, never import time — the workspace `.env` loads
   in each CLI's `main()`, which runs after the module is imported, so an
   import-time read would silently see no key (same rule as
   `rate_limiter.user_agent()`).
2. Budget exhaustion fails fast and legibly (above).
3. `.env.example` documents the key with the numbers and the 30-second signup
   link; `check_setup.py` reports whether a key is in use (`[API key: $1/day
   budget]` vs a `no API key` nudge) and surfaces exhaustion explicitly rather
   than reporting "unreachable".

The key is **optional by design**: with none set, every request is byte-identical
to before. Set it in the workspace `.env` (preferred — that is what
`load_dotenv(find_dotenv(usecwd=True))` reads) or in the shell environment.

This unblocks item 3 D, venue vetting (per-venue lookups need the
filter/search budget), and the live run of item 3 F, Chicago a/b
disambiguation.
