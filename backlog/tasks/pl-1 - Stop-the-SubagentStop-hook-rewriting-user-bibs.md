---
id: PL-1
title: Stop the SubagentStop hook rewriting user bibs
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-09-25 19:24'
labels:
  - hooks
dependencies: []
references:
  - hooks/subagent_stop_bib.sh
type: bug
project: Safety
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** PhilLit must never rewrite a user's own files. Today this hook can rewrite a bibliography the user keeps in the workspace root.

The SubagentStop hook cleans every workspace-root `.bib`. Phase 6's stray sweep moves only `literature-domain-*.bib`, but `hooks/subagent_stop_bib.sh` still collects every `"$CLAUDE_PROJECT_DIR"/*.bib` as a researcher stray, validates it and runs `metadata_cleaner.py` on it. Scope the root glob to the names researchers write (`literature-domain-*.bib`).

The same file carries PL-8 (visible SubagentStop gate failures). If that ruling is in by then, ship both together.
<!-- SECTION:DESCRIPTION:END -->
