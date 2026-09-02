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
