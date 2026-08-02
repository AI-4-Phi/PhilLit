# NDPR Enrichment Not Used for Seminal Books

**Observed**: 2026-02-10, during "What are data?" literature review (run 2)
**Severity**: Medium (reduces synthesis quality for key works)
**Status**: Resolved in design — **both recommended options shipped.**
Option A landed the day this was filed (`1a97b65` 2026-02-10, gated to
`book` + no-abstract + INCOMPLETE + High/Medium importance in
`enrich_bibliography.py`; narrowed `8424551`, matching improved `6390794`).
Option B is the evidence-tier design (ROADMAP item 1, built on
`worktree-evidence-tier`): `INCOMPLETE` stops meaning "exclude" and is
consumed/stripped by the barrier. The headline numbers below (~38
INCOMPLETE, 3 enriched) describe the pre-fix state; the post-fix enrichment
rate has not been re-measured — that re-measurement is the only thing left
here.

## Summary

Domain researcher agents mark books without abstracts as `INCOMPLETE` and `no-abstract` in BibTeX keywords. The system has an NDPR enrichment capability (`fetch_ndpr.py`) that can extract descriptive paragraphs from Notre Dame Philosophical Reviews as abstract substitutes. However, domain researchers rarely use it for the most important books, relying instead on hand-written `note` field annotations.

## Observed Behavior

Out of ~38 entries marked INCOMPLETE across 7 domain BibTeX files, only 3 received NDPR-sourced abstracts (`abstract_source = {ndpr}`):
- Harding 1993 (domain 7)
- A Sceski/Popper book (domain 2)
- An Ayer/Reichenbach entry (domain 1)

The most important books — which are the ones that would benefit most from NDPR enrichment — were **not** NDPR-enriched:

| Book | Importance | NDPR attempted? | Workaround |
|------|-----------|-----------------|------------|
| Hanson 1958, *Patterns of Discovery* | High | No | Hand-written `note` |
| Kuhn 1962, *Structure of Scientific Revolutions* | High | No | Partial CORE metadata |
| Leonelli 2016, *Data-Centric Biology* | High | No | Hand-written `note` |
| van Fraassen 1980, *The Scientific Image* | High | Unclear (corrupted abstract) | Possibly wrong NDPR abstract |
| Popper 1959, *Logic of Scientific Discovery* | Medium | No | Partial CORE metadata |

## Additional Issue: INCOMPLETE Convention Not Enforced

The synthesis outline explicitly states INCOMPLETE entries should be "excluded from synthesis" and the synthesis-writer agents should not cite them directly. In practice, all five books above were cited extensively in the final review. This is arguably the right outcome (these are essential works), but it means the INCOMPLETE convention is not functioning as designed.

## Root Cause

1. **Agent behavior**: Domain researchers attempt abstract resolution via Semantic Scholar, OpenAlex, and CORE, but do not systematically fall back to NDPR for books. The `fetch_ndpr.py` script exists and works, but agents invoke it inconsistently.
2. **No automated fallback** *(fixed — see Status)*: at filing, nothing fell back to NDPR automatically. The `get_abstract.py` chain (S2 -> OpenAlex -> CORE) still ends at CORE, but the book-scoped NDPR fallback lives one layer up, in `enrich_bibliography.py` (`resolve_ndpr_abstract`), which is the layer that runs in Phase 3/5.5.
3. **INCOMPLETE convention mismatch**: Marking seminal books as INCOMPLETE and instructing synthesis-writers to skip them creates a conflict — these are precisely the works that must appear in any competent review.

## Options to Address

### Option A: Add NDPR to the abstract resolution chain

Extend `get_abstract.py` to attempt `fetch_ndpr.py` as a final fallback when the entry type is `book` and no abstract was found from S2/OpenAlex/CORE. This would automate what agents currently do inconsistently.

### Option B: Revise the INCOMPLETE convention

Change the meaning of INCOMPLETE from "exclude from synthesis" to "cite with caution; rely on secondary literature and `note` annotations rather than the abstract field." This matches actual behavior and avoids penalizing essential works that lack machine-readable abstracts.

### Option C: Pre-populate NDPR abstracts for canonical works

Maintain a curated list of canonical philosophy books with their NDPR review URLs. Domain researchers could check this list before marking entries as INCOMPLETE.

## Recommendation

- **Option B** (low effort) — Align the convention with reality; INCOMPLETE should not mean "exclude"
- **Option A** (medium effort) — Automate NDPR fallback so fewer entries are marked INCOMPLETE in the first place
