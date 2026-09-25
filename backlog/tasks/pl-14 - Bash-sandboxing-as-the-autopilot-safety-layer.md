---
id: PL-14
title: Bash sandboxing as the autopilot safety layer
status: Later
assignee: []
created_date: '2026-09-25 19:18'
labels: []
dependencies: []
references:
  - docs/ideas/claude-code-deferred-opportunities.md
type: feature
project: Safety
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** With Bash allowed broadly, autopilot safety rests on three deny rules (`sudo`, `dd`, `mkfs`) and two ask rules (`rm`, `rmdir`). Claude Code's native sandbox would enforce limits at the OS level instead: file writes confined to the project and tmp, and network limited to PhilLit's academic API hosts.

The design is in `docs/ideas/claude-code-deferred-opportunities.md`, section 1. Claude Code has no native Windows sandbox, and PhilLit supports native Windows. So the sandbox must be additive (`failIfUnavailable: false`) and tested on native Windows before it ships.

**What brings it forward:** Windows support for the sandbox landing, or the deny/ask layer proving insufficient in practice.
<!-- SECTION:DESCRIPTION:END -->
