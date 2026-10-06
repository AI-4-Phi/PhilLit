---
id: PL-16
title: Barrier summary names why it degraded
status: Done
assignee: []
created_date: '2026-10-06 09:50'
updated_date: '2026-10-06 09:52'
labels:
  - barrier
dependencies: []
references:
  - skills/literature-review/scripts/evidence_barrier.py
type: guard
project: Accuracy
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The barrier's printed summary says `degraded` without the cause, so an operator, or the orchestrator writing the final summary, cannot tell a harmless failed encyclopedia fetch from a missing ledger. In the 2026-10-06 headless run (moral luck) the orchestrator reported "I did not find out why"; the cause was one failed SEP article (`sep:adam-smith`).

**Scope:** `run_barrier` records each degrade cause in `report["degraded_by"]` (domain state, slug file, failed encyclopedia articles), and the printed summary carries it whenever the status is `degraded`.
<!-- SECTION:DESCRIPTION:END -->
