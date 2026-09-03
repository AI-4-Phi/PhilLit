# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Follow-up search rounds still split across Bash calls** — the one bar the
researcher-prose rewrite did not move. Two headless runs on the same topic
("specification gaming and reward hacking in AI systems", Sonnet): 3 of 15 and
4 of 21 follow-up rounds ran as more than one call, against a baseline of 2 of
20, while every other measured bar cleared (first-call probes 6/6 → 0/7, Stage 4
fired 2/6 → 7/7, standalone slug heredocs 3 → 0, prescribed bib greps → 0). The
"one follow-up call per round" rule is therefore inert; the lever is small
(about one call per domain, since most rounds are single queries). Decide
whether to drop the rule as noise or find a mechanism that is not prose.
Measure with `docs/known-issues/researcher-turn-measurement-2026-09-03/validation_report.py`.
