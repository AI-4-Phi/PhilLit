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
2026-09-01). `agents/synthesis-writer.md` no longer recommends this form (it
now instructs writers to note the original date in prose instead), and
`docs/conventions.md` no longer documents it. But `skills/literature-review/scripts/lint_md.py`'s
citation grammar still accepts `(Author Year1/Year2)` (`_YEAR` allows an
optional `/YEAR` group), so a writer can still produce the form spontaneously
and the double-listing bug fires when they do. `generate_bibliography.find_cited_entries`'s matcher
(`_collect_matches`, `_resolve_collisions`) groups match candidates by
`(surname, EXACT year)`, so the two years in `Year1/Year2` land in separate
singleton groups — each always kept, with no collision resolution between them —
and both bib entries end up in the delivered `.bib`'s References, exactly the
"one work cited as two positions" symptom the fix was built to eliminate.
`warn_same_work_cited` (the `[SAME-WORK]` advisory) does fire but is print-only
to stderr and never blocks or merges. Reproduced directly against
`find_cited_entries` with a synthetic `same_work_group` pair and a
`(Surname Year1/Year2)`-only prose citation. The form is no longer recommended
anywhere, so support or reject it properly: either special-case the
`Year1/Year2` form in the matcher to resolve to one entry, or have
`lint_md.py`'s grammar reject the form outright and escalate
`warn_same_work_cited` to something stronger than a stderr print when both
group members are independently matched as cited.

Escalating `warn_same_work_cited` is not a free move: the advisory sees only
the cited-entry list, not any citation's own text, so it cannot distinguish
the double-listing bug from the SANCTIONED case of a writer legitimately
citing both editions as two separate citations ("(Reiman 1984)" and
"(Reiman 2017)" each on their own) — and would fire on both. `lint_md.py`
still sees each citation's own text, including the `Year1/Year2` token when
present, so it is the right place to escalate.

Detection now ships: `check_citations`'s STRADDLE check ERRORs (printed as
`ERROR citation: ...`) when a `Year1/Year2` citation's two years resolve to
two DIFFERENT References entries, and stays silent when the bib holds only a
single edition or one References line already carries both years. What
remains open is the RENDERING half: `generate_bibliography.find_cited_entries`
still has no single-entry rendering for a proper reprint citation — its
matcher (`_collect_matches`, `_resolve_collisions`) groups by `(surname,
EXACT year)`, so there is no code path that collapses a genuine reprint pair
into one rendered citation. Either build that single-entry rendering, or
decide never to support the form and rely on lint's ERROR plus the "cite one
year, prose the other" convention already in `agents/synthesis-writer.md`
and `docs/conventions.md`. Any further grammar change should stay scoped to
`lint_md`'s `_YEAR`/STRADDLE logic; do not tighten
`bib_identity.same_work_year`, whose acceptance of a bib YEAR FIELD like
"1984/2017" is a defensive parse of real-world data (a malformed/reprint
year field), not an endorsement of the citation form.
