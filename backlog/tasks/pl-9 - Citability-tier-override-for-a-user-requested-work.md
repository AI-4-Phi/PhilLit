---
id: PL-9
title: 'Citability: tier override for a user-requested work'
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-10-06 07:15'
labels:
  - agents
  - test-run
dependencies: []
references:
  - agents/synthesis-planner.md
  - agents/synthesis-writer.md
  - docs/conventions.md
  - skills/literature-review/SKILL.md
type: feature
project: Accuracy
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The planner's role spec and the orchestrator's instructions both govern what may be cited, and nothing says which one wins. The model is left to guess, and a guess about citability is an accuracy risk.

The synthesis-planner's role spec can override the orchestrator on citability. `agents/synthesis-planner.md` declares the `EVIDENCE-*` keyword "the single authority on citability". The orchestrator's Phase 4 instructions are not documented as yielding to it, and the precedence is written down nowhere. Reported from the 2026-09-10 run. The same "single authority" wording also sits in `docs/conventions.md` (tier section) and `agents/synthesis-writer.md` (tier table), so the fix covers all three.

**Ruling:** the orchestrator's dispatch prompt can override the `EVIDENCE-*` tier, but only to relay an explicit user request for a named work. The orchestrator never overrides on its own judgement. The dispatch prompt names the work and its tier. The planner and writer then may characterize it, and the prose must disclose that this run could not verify the characterization against a source.

The fix: one rule in SKILL.md Phase 4 and Phase 5 (when to override, how to name the work), and the same exception added to the three "single authority" phrases (`agents/synthesis-planner.md`, `agents/synthesis-writer.md`, `docs/conventions.md`), with the disclosure rule in the writer's tier section. Check whether `check_evidence.py` flags such a citation, and make it accept a relayed override.
<!-- SECTION:DESCRIPTION:END -->
