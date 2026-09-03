# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Researcher prose residuals after the turn-waste rewrite** — one headless
validation run (8 domains, Sonnet, topic "specification gaming and reward
hacking in AI systems", prose at `c5f430b`) against the same-topic baseline:
first-call probes 6/6 → 0/8, standalone non-empty slug heredocs 3 → 0, Stage 4
fired 2/6 → 7/8 with one silent skip, follow-up rounds split across calls 2/20
→ 3/15, prescribed post-enrichment bib greps 0 → 1. Three bars missed narrowly;
the run predates the Stage 4 partial-failure case and the executable
valid-empty slug call added by review. Re-measure with a second run on the same
topic (`docs/known-issues/researcher-turn-measurement-2026-09-03/validation_report.py`)
before spending prose on the residuals.
