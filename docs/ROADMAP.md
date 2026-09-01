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

**Make `disambiguate_container`'s reopen threshold measurable** — the
accepted bail-path residual (v0.5.6, `verify_paper.py` docstring) says it
reopens above "roughly 30% of multi-element chapters" bailing, but by the
docstring's own admission neither cache retains the raw `container-title`
array, so the bail rate is uncomputable and the residual has no working
reopen mechanism. Cheap fix: count multi-element arrays and bails in the
existing debug/enrichment output, so the at-risk subset becomes measurable
from a run's artifacts instead of unmeasurable in principle. Raised by the
service's 7911770 pin review (glm-5.3 round, 2026-09-01).
