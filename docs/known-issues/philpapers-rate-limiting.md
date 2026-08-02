# PhilPapers Rate Limiting During High-Volume Literature Reviews

**Observed**: 2026-02-12, during "Algorithmic Fairness (2023-Present)" literature review
**Severity**: Low (degrades gracefully to other sources; no data loss)
**Status**: Open, **re-scoped 2026-08-02** — the original root-cause section
was wrong at filing, and Option C already exists. `search_philpapers.py` has
gone through the **Brave Search API** (`philpapers_via_brave`, SERP-filtered
to `philpapers.org/rec/`) since `8a2efe6` (2026-01-07, five weeks before the
observation); philpapers.org is never contacted directly, so PhilPapers
cannot be throttling us. The errors were **Brave API quota/429 behaviour**
under 7 parallel agents sharing one key. The script also already carries
`ExponentialBackoff(max_attempts=5)` plus the shared `brave` rate limiter —
Option C is done. What genuinely remains open: whether the shared Brave
quota needs sizing/serializing across parallel researchers (Options A/B/E),
or whether Option D (accept) stands. The recommendation (D now, C if worse)
has effectively been followed.

## Summary

During Phase 3 (domain research), multiple `domain-literature-researcher` agents querying PhilPapers in parallel encountered rate limiting errors. PhilPapers returned HTTP errors or timeouts when processing multiple concurrent search queries, particularly affecting domains 1, 3, and 7. The agents handled the failures gracefully by reporting "Source issues: PhilPapers rate limiting" and relying on alternative sources (Semantic Scholar, OpenAlex, CORE, arXiv) for comprehensive coverage.

## Observed Behavior

### Literature Review: Algorithmic Fairness (2023-Present)

**7 parallel domain researchers** launched simultaneously, each making multiple PhilPapers queries:

- **Domain 1** (Fairness Definitions): 2 PhilPapers queries returned errors
- **Domain 3** (Trade-offs): PhilPapers searches returned no results
- **Domain 7** (Interdisciplinary): PhilPapers searches returned errors

**Impact on review quality**: None. All three domains collected 16-18 papers each from alternative sources. The final review cited 90 papers with comprehensive coverage across all domains.

**Total queries**: ~15-25 PhilPapers queries across 7 agents within a ~5-minute window

## Why This Happens

**(Corrected 2026-08-02 — the original version of this section blamed
PhilPapers throttling/scraping; that was wrong at filing, see Status.)**

The searches run through the Brave Search API: `search_philpapers.py` calls
`brave_site_search(..., PHILPAPERS_CONFIG)`, where `PHILPAPERS_CONFIG`
(`brave_search.py`) is a SERP filter (`site_domain`, `url_path_filter="/rec/"`,
id regex) — the only network call is to the Brave endpoint, gated on
`BRAVE_API_KEY`. Seven parallel researchers share that one key, so a burst of
~15-25 queries in a 5-minute window can hit Brave's per-key rate/quota
limits, which surface to the agents as search errors. PhilPapers itself is
never contacted.

## Current Mitigation

Domain researchers already handle PhilPapers failures gracefully:
- Report the issue in their completion summary ("Source issues: PhilPapers...")
- Continue with other sources (S2, OpenAlex, CORE, arXiv, SEP, IEP)
- PhilPapers is treated as supplementary rather than primary for most technical/recent literature

This mitigation is **working as designed** — no review has failed due to PhilPapers rate limiting.

## Options to Address

### Option A: Sequential PhilPapers queries with delays

Modify the orchestrator (Phase 3 workflow) to stagger domain researcher launches by 5-10 seconds, reducing concurrent PhilPapers load. This would add minimal latency (~1 minute for 7 domains) while potentially avoiding rate limits.

### Option B: PhilPapers query pooling

Have the orchestrator pre-run all PhilPapers queries sequentially during Phase 2 (planning), then pass cached results to domain researchers during Phase 3. This separates PhilPapers access from the parallel research phase.

### Option C: Exponential backoff retry in `search_philpapers.py` — DONE

Implemented: `ExponentialBackoff(max_attempts=5)` in `search_philpapers.py`,
plus the shared `get_limiter("brave")` rate limiter. Individual agents
self-throttle without orchestration changes.

### Option D: Accept current behavior

PhilPapers failures are rare, non-critical, and already handled gracefully. The current approach (fail gracefully + report issue) may be sufficient given that:
- Alternative sources provide comprehensive coverage
- PhilPapers is most valuable for philosophical literature, less so for technical CS papers
- The issue is self-limiting (after rate limit triggers, queries naturally space out)

### Option E: Dedicated PhilPapers query agent

Create a specialized agent that serves as the sole PhilPapers accessor for a review, accepting query requests from domain researchers and serializing them. This centralizes rate limit handling but adds architectural complexity.

## Recommendation

**Option D** (accept current behavior) is reasonable for the near term. PhilPapers failures:
- Are infrequent (only 3 of 7 domains affected)
- Degrade gracefully (alternative sources compensate)
- Are self-documenting (agents report the issue explicitly)

If PhilPapers failures become more frequent or affect review quality, **Option C** (retry with backoff) is the lowest-effort improvement. **Option A** (stagger launches) is also low-cost if we want to reduce the likelihood of triggering rate limits in the first place.

**Option B** or **Option E** would be appropriate only if PhilPapers becomes a critical source that cannot be substituted by S2/OpenAlex/CORE.
