---
id: PL-42
title: Writers skip the per-claim support lines of the source check
status: Done
assignee: []
created_date: '2026-11-19T15:35:00Z'
updated_date: '2026-11-19T17:16:00Z'
labels:
  - agents
  - test-run
dependencies: []
type: bug
project: Accuracy
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** in the 2026-11-19 validation run (cognitive-autonomy-ai, PhilLit 0.5.49 + PL-39, 8 domains, 9 sections), the writers of sections 2, 3, 5, 6 and 7 reported claim counts but no per-claim support lines, and the section 4 writer's first source check was unrecorded (the orchestrator re-ran it; the second run listed 62 claims). The Source Check (REQUIRED) in agents/synthesis-writer.md asks for one line per claim in the reply. Without the lines, nothing shows that each claim about a work sits in its licensed text.

**Scope:** find why Sonnet writers drop the lines (transcripts: ~/.claude-work/projects/<encoded ws path>/<session>/subagents/, the run workspace ~/phillit-runs/pl39-validation/ws). Options: a documented failure exit, a completion-message example that shows the lines, or an orchestrator check in SKILL.md Phase 5 that re-dispatches a writer whose reply lacks them. Validate in a headless run.
<!-- SECTION:DESCRIPTION:END -->
