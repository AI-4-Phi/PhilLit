---
id: PL-1
title: Stop the SubagentStop hook rewriting user bibs
status: Done
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-10-02 12:56'
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

The same fix makes an allow print `{}`. The hook printed `{"decision": "allow"}`, which Claude Code rejects as invalid output: for SubagentStop it documents only `"block"`, and omitting `decision` allows the stop.
<!-- SECTION:DESCRIPTION:END -->
