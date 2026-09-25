---
id: PL-12
title: Verify the local work folder on Windows
status: Later
assignee: []
created_date: '2026-09-25 19:18'
labels:
  - workdir
dependencies: []
references:
  - skills/literature-review/scripts/workdir.py
  - docs/ARCHITECTURE.md
type: verify
project: Platform
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** PhilLit promises Windows support, but the off-sync working directory was built and tested on macOS only.

On a real Windows machine, check four things:
- Claude Code honours the `~` form of `Edit(~/.local/state/phillit/reviews/**)`.
- `workdir.py`'s name-surrogate test refuses a real junction and accepts a OneDrive Files On-Demand placeholder.
- Read-only attributes never wedge `publish`, `activate` or the pointer.
- The 120-character headroom (`DEEP_FILE_HEADROOM`) covers the longest generated filenames (`intermediate_files/json/verify_<domain>_<citekey>.json`).

The one part that needs no Windows machine is PL-4 (the Windows length check in `suggest_name`).

**What brings it forward:** the first Windows bug report, or a Windows machine to test on (CLAUDE.md, Cross-Platform).
<!-- SECTION:DESCRIPTION:END -->
