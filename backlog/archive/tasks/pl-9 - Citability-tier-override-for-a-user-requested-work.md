---
id: PL-9
title: 'Citability: tier override for a user-requested work'
status: Done
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-10-06 10:13'
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

**Ruling:** the orchestrator's dispatch prompt can override the `EVIDENCE-*` tier, but only to relay an explicit user request for a named work. The orchestrator never overrides on its own judgement. The dispatch prompt names the work and its tier. The planner and writer then place it, and characterize it only from the user's own description, attributed to the research request; without one, they say no more than its title identifies; either way the prose discloses what was not verified (content only at `EVIDENCE-EXISTENCE`, identity too at `EVIDENCE-NONE`). Never a quotation, never the LLM-written note (the WEB drop rule it would borrow rests on a fetch attestation a barred entry lacks). A work the request only mentions gets no override.

The fix: one rule in SKILL.md Phase 4 and Phase 5 (when to override, how to name the work), and the same exception added to the three "single authority" phrases (`agents/synthesis-planner.md`, `agents/synthesis-writer.md`, `docs/conventions.md`), with the disclosure rule in the writer's tier section. `check_evidence.py` keeps flagging an overridden work (it is telemetry and reads only the bib), and SKILL.md has the summary say beside the CHECK line that the user asked for the work. Validate in the headless run batched with PL-7: a review whose request names an `EVIDENCE-NONE` work.
<!-- SECTION:DESCRIPTION:END -->
