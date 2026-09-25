---
id: PL-4
title: Windows length check in suggest_name
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
labels:
  - workdir
dependencies: []
references:
  - skills/literature-review/scripts/workdir.py
type: bug
project: Platform
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** On Windows, a deep workspace can make `init` refuse the very name `suggest_name` offered. In Full Autopilot the orchestrator takes the suggestion, so the review cannot start.

`workdir.py`'s `suggest_name` checks `name_problem` and whether the name exists, but not `length_problem`. On a deep workspace it can therefore suggest a name that `init` then refuses as too long.

This needs no Windows machine: `length_problem` takes `windows=True`, so the fix and its test run on macOS. The rest of the Windows check is PL-12 (verify the local work folder on Windows).
<!-- SECTION:DESCRIPTION:END -->
