---
id: PL-2
title: Correct the permissions guide's agent-mode column
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
labels: []
dependencies: []
references:
  - docs/permissions-guide.md
type: docs
project: Consistency
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The guide tells a developer that plugin agents run in `acceptEdits`. In the plugin they run in the session's mode, so anyone reasoning from the table about what an agent may write gets it wrong.

`docs/permissions-guide.md`'s agent table lists `acceptEdits` for all four agents, taken from their `permissionMode` frontmatter. Claude Code's sub-agents docs say plugin subagents ignore `permissionMode` (and `hooks` and `mcpServers`). So in the plugin the mode is the session's, and edits pass on the `Edit` rules that setup merges (`Edit(reviews/**)`, `Edit(~/.local/state/phillit/reviews/**)`).

Keep the frontmatter: phillit-service vendors the files as project agents under `engine/.claude/agents/`, where it IS honoured. Correct the column to say where it applies.
<!-- SECTION:DESCRIPTION:END -->
