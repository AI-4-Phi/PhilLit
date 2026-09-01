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

**Lint WARN on contraction-only citation resolutions** — undecided, blocked on
a measurement. `lint_md`'s `_fold_variants` is `ascii_variants` bare, so
`ascii_variants`' accepted residual (b) resolves silently there and turns a
correct ERROR into a clean pass (stated in full in that function's docstring —
do not re-litigate the residual itself). The candidate fix is a WARN whenever a
citation resolves ONLY through the contraction axis. **Measure the
false-positive rate first**: the WARN would also fire on every legitimate
Müller/Muller pair, which is the common case, and a checker that cries wolf on
the common case is worse than the silent residual. Harness:
`docs/known-issues/surname-contraction-measurement-2026-08-29/`.

**Booktitle/series duplication on the CrossRef bail path** — undecided, and it
is a policy call rather than a measurement. When `disambiguate_container` bails
it sets `container_title` = element [0] and leaves `series` empty; element [0]
may itself BE the series (a Springer series shipped as a booktitle in
production — the defect the disambiguation was built for). Nothing downstream
notices: no Phase-6 script reads `series` at all, so an entry whose `booktitle`
and `series` carry the same string renders that way unchallenged. Decide
whether the bail path should suppress or flag that case; the bail rule is owned
by `docs/conventions.md`, so the ruling lands there and in
`disambiguate_container`'s docstring.
