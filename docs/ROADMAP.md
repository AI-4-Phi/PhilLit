# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**`parse_entry_fields` drops any field nested two braces deep** — and it
partially defeats the `same_work_group` stamping shipped at `8fc09af`.
`_FIELD_RE`'s value alternation admits a brace group containing no braces, so
the standard LaTeX accent form (`Mendon{\c{c}}a`, `Garc{\'{i}}a-Ferrero`, and
`\textit{{T}he {P}rivatized {S}tate}` in titles) fails to match and the field
is dropped — absent, not mangled, not flagged. One level parses fine, so the
affected population is entries whose authors have accented names, not a random
slice. Two consumers degrade together, both fed from the same dict:
`_same_work_groups` produces no key and therefore no stamp, so the synthesis
writer never learns the reprint pair is one work; and the Chicago a/b pass
reaches `fallback_key` with an empty surname axis, which is the failure
`_first_surname_raw`'s own docstring was written to prevent. `compute_tier`
shares the parser but reads other fields and is not implicated on current
evidence. Measured over `reviews/` at this pin: **33 of 8,894 entries (0.37%),
22 author / 11 title, every one in the same direction**. Census, script and the
two traps that produced two earlier wrong figures:
`docs/known-issues/field-parse-divergence-measurement-2026-09-02/`. Candidate
fix is a brace-depth-aware scan, or handing the entry to pybtex and stopping
maintaining a second parser — the second would also close the sibling gap where
`_first_surname_raw` pre-splits the author field on a naive `" and "` (0 of
8,975 today, so it matters only as a reason to do this once). Found by the
service while reviewing this pin; it is pinned there as a scope guard, so a fix
here is reported rather than absorbed.

**Dynamic-workflow orchestration for Phases 3–5** — unstarted, and two gates
stand before implementation: whether the service's run path can reach a
workspace `.claude/workflows/` at all (it vendors this skill, and the mirror
rule is unconditional), and a re-run of the hook gate test, whose evidence is
from a Claude Code two dozen versions back. Design, status and both gates:
`docs/ideas/dynamic-workflow-refactor.md`, which owns them.
