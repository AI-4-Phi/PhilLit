---
id: PL-8
title: Stop the SubagentStop gate failing open silently
status: Done
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-10-06 07:35'
labels:
  - hooks
dependencies: []
references:
  - hooks/subagent_stop_bib.sh
  - skills/literature-review/scripts/workdir.py
type: bug
project: Accuracy
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** CLAUDE.md's gate-failure policy forbids an accuracy gate from failing open silently. Today a researcher's bib can skip validation and cleaning with no warning at the gate; the skip surfaces only later, as `degraded` in the barrier report.

The SubagentStop gate fails open silently when the review cannot be resolved. When `workdir.py resolve` answers `{error}`, `hooks/subagent_stop_bib.sh` allows the stop with only a stderr WARNING. That happens with no pointer, a malformed pointer, an in-place pointer to a missing folder, a local review whose files are elsewhere or missing, or one whose ownership cannot be proven. stderr on exit 0 is never shown, so validation and cleaning are skipped silently for that researcher.

The barrier later reports the missing cleaning ledger as `degraded`, so the skip shows up downstream. Configuration errors already fail closed (`ConfigError`, exit 1).

**Ruling:** emit a `systemMessage` that names the cause and says validation and cleaning were skipped, and allow the stop. Do not block: the researcher cannot repair a pointer or a missing folder, so a block costs a wasted turn and ends in the same state. The fix covers both silent allows in `hooks/subagent_stop_bib.sh`: the resolver `{error}` answer and the resolved folder that does not exist. Pin both in the hook tests.

PL-1 (stop the SubagentStop hook rewriting user bibs) shipped in 0.5.33: the root sweep takes `literature-domain-*.bib` only, and an allow prints `{}`.
<!-- SECTION:DESCRIPTION:END -->
