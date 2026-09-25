---
id: PL-9
title: 'Citability: decide which document wins'
status: Needs Johannes
assignee: []
created_date: '2026-09-25 19:18'
labels:
  - agents
dependencies: []
references:
  - agents/synthesis-planner.md
  - agents/synthesis-writer.md
  - docs/conventions.md
  - skills/literature-review/SKILL.md
type: docs
project: Accuracy
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The planner's role spec and the orchestrator's instructions both govern what may be cited, and nothing says which one wins. The model is left to guess, and a guess about citability is an accuracy risk.

The synthesis-planner's role spec overrides the orchestrator on citability. `agents/synthesis-planner.md` declares the `EVIDENCE-*` keyword "the single authority on citability". The orchestrator's Phase 4 instructions are not documented as yielding to it, and the precedence is written down nowhere. Reported from the 2026-09-10 run. The same "single authority" wording also sits in `docs/conventions.md` (tier section) and `agents/synthesis-writer.md` (tier table), so the fix covers all three.

**Decision needed:** which document wins? Then say so in the one that loses.
<!-- SECTION:DESCRIPTION:END -->
