# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Dynamic-workflow orchestration for Phases 3–5** — unstarted, and two gates
stand before implementation: whether the service's run path can reach a
workspace `.claude/workflows/` at all (it vendors this skill, and the mirror
rule is unconditional), and a re-run of the hook gate test, whose evidence is
from a Claude Code two dozen versions back. Design, status and both gates:
`docs/ideas/dynamic-workflow-refactor.md`, which owns them.

**The reprint citation form `(Author Year1/Year2)` causes both `same_work_group`
members to be double-listed in delivered References** — found verifying the
v0.5.7 reprint-dedup fix (`docs/known-issues/reprint-dedup-measurement-2026-09-01/`,
2026-09-01). `agents/synthesis-writer.md` instructs writers to cite a reprint
group once, using this form (e.g. `(Reiman 1984/2017)`), and `docs/conventions.md`
now documents it. But `generate_bibliography.find_cited_entries`'s matcher
(`_collect_matches`, `_resolve_collisions`) groups match candidates by
`(surname, EXACT year)`, so the two years in `Year1/Year2` land in separate
singleton groups — each always kept, with no collision resolution between them —
and both bib entries end up in the delivered `.bib`'s References, exactly the
"one work cited as two positions" symptom the fix was built to eliminate.
`warn_same_work_cited` (the `[SAME-WORK]` advisory) does fire but is print-only
to stderr and never blocks or merges. Reproduced directly against
`find_cited_entries` with a synthetic `same_work_group` pair and a
`(Surname Year1/Year2)`-only prose citation. Candidate fixes: special-case the
`Year1/Year2` form in the matcher to resolve to one entry, or escalate
`warn_same_work_cited` to something stronger than a stderr print when both
group members are independently matched as cited.
