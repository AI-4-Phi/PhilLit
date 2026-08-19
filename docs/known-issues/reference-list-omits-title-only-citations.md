# Reference List Omits Sources the Body Cites by Title Only

**Observed**: 2026-08-19, downstream service, production kimi-k3 run
(service review `42b029364b084b6b`)
**Severity**: Medium — a delivered review cites a work the reader cannot
look up; single instance observed so far
**Status**: Open

## Summary

The body text cited `heersmink2016internet` by TITLE — "Heersmink's 'The
Internet, Cognitive Enhancement, and the Values of Cognition' (2016) frames
the upshot in its title" — and the rendered References list omits it. The
reference builder's cited-entry matcher works on author-year shapes, so a
title-only mention is invisible to it. The inverse direction held in the
same run: all 135 in-text author-year tokens resolved to a References
entry (zero orphans), so this is specifically the title-mention shape.

The sentence itself was evidence-disciplined (EVIDENCE-EXISTENCE entry,
existence-level hedging "in its title" — correct); the defect is only that
a genuinely-used source dropped out of References.

## Fix direction

Either the writer convention requires author-year form for every citation
(making title-only mentions non-citations by definition), or
`find_cited_entries` learns title mentions. Related but distinct from
`author-year-collision.md` — same matcher, different failure shape (that
file is about suffix/disambiguation collisions among author-year cites;
this is a citation form the matcher never sees at all). Downstream mirror:
phillit-service `docs/known-issues/writer-cites-entry-absent-from-references.md`.
