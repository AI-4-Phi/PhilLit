# Venue-Name Recall for Subtitled Journals

**Surfaced**: 2026-08-07, sub-item F (Chicago a/b disambiguation) live-run
rider 5
**Severity**: Low — silent no-op in venue vetting; misses only, never a
false flag
**Status**: MEASURED 2026-08-19 — true failure fraction settled below;
decision (fix / accept / drop) is the owner's, pending. Recommendation:
accept and record.

## Problem

`venue_vetting` resolves a bare venue name but not the subtitled form a bib
may carry: "Res Publica" resolves, "Res Publica: A Journal of Moral, Legal
and Social Philosophy" does not (controlled test 2026-08-07, 0 errors either
way — the once-suspected `filter=` injection risk from `:`/`|` is unfounded
and closed). Consequence: vetting never evaluates such entries. Direction is
benign — the rule flags only venues that RESOLVE, so this yields false
negatives, never false low-visibility flags.

## Measurement (2026-08-19)

Method: every distinct raw `journal` value from `@article` entries across
`reviews/**/*.bib` that carries a colon, resolved through the PRODUCTION
path (`venue_vetting.lookup_venue`, its cache included, keyed). Full form
first; on failure, the bare prefix before the colon. All 5 full-form
failures were then re-confirmed with FRESH lookups bypassing the cache — no
verdict rests on a stale cached miss. Script + raw results:
`docs/known-issues/venue-recall-measurement-2026-08-19/` (local-only).
Spend: ~740 credits of the keyed 10,000/day.

Population: **928 distinct journal names** (the corpus has grown since the
2026-08-05 count of 880), of which **55 carry a colon** (5.9%; 147 entries).
All 55 measured, 0 lookup errors:

| Class | Names | Entries | Meaning |
|---|---|---|---|
| Full form resolves | 28 | 95 | colon is part of the real venue name — no failure |
| **Subtitle failure** | **5** | **10** | full fails, bare prefix resolves — the true recall loss |
| Neither resolves | 22 | 42 | not attributable to the subtitle (see below) |

**True failure fraction: 5/55 colon-carrying names (9.1%) = 5/928 of all
distinct journal names (0.54%), 10 entries corpus-wide.** The alarming
upper bound (5.5% of journals carry a colon) dissolves: over half the
colon-carrying names either resolve fine with their subtitle (28) or would
not be rescued by any subtitle handling (22 — thirteen `arXiv preprint
arXiv:NNNN.NNNNN` pseudo-journals, ACL proceedings, edited-volume titles
misfiled as `journal`, and one LaTeX-escaped `Techn\'{e}` that is the
already-documented LaTeX-accent recall gap in `venue_vetting.py`'s
docstring).

The five subtitle failures, with what the prefix resolves to:

| Bib venue (entries) | Prefix resolves as | h | Flagged if rescued? |
|---|---|---|---|
| ASDIWAL: Revue genevoise d'anthropologie... (2) | ASDIWAL Revue genevoise... | 6 | **yes** |
| Human Architecture: Journal of the Sociology of Self-Knowledge (2) | Human architecture | 19 | no |
| Polis: The Journal for Ancient Greek Political Thought (2) | POLIS | 8 | **yes** |
| Psychological Monographs: General and Applied (2) | The Psychological Monographs | 99 | no |
| differences: A Journal of Feminist Cultural Studies (2) | differences | 63 | no |

## Harm analysis

Recall only matters if a rescued venue would then be FLAGGED — a venue that
resolves high-h/core/DOAJ is vetted-and-cleared, and the pipeline's behavior
is identical to never vetting it. Of the 5 rescued: **2 would be flagged
(4 entries corpus-wide)**. That is the entire measured harm.

And both of those 2 carry a wrong-venue risk: prefix matching resolves
"POLIS" and "Human architecture" to *some* same-prefix source, not
provably the subtitled journal the bib names — the same false-merge trap
the conference-venue provenance measurement quantified at ~8x cost
(56 real folds lost per 7 saved). A prefix-fallback fix could therefore
mis-attribute a venue record, and a wrong flag costs more than a miss by
this module's own design rule ("a false discredit costs more than a miss").

## Recommendation

Accept and record. The measured benefit of any fix is at most 2 venues / 4
entries in a 928-venue corpus, the failure direction is benign by design,
and the only available fix shape (prefix fallback) reintroduces a measured
false-merge risk in the harm-dominant direction. Decision is the owner's.
