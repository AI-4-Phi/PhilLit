---
id: PL-41
title: Global uv exclude-newer breaks the locked wrapper
status: Done
assignee: []
created_date: '2026-11-19T09:22:00Z'
updated_date: '2026-11-19T09:25:00Z'
labels: []
dependencies: []
type: bug
project: Delivery
ordinal: 500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** a user-level uv setting `exclude-newer = "7 days"` (a common supply-chain guard) makes every `uv run --locked` in `bin/phillit-run` fail with "The lockfile at uv.lock needs to be updated", because uv adds the user's cutoff to the resolution options and the lock records none. Every PhilLit script and hook then fails. Seen on dove 2026-11-19 with uv 0.13.9.

**Ruling (Johannes, 2026-11-19):** pin a fixed `exclude-newer` date in `pyproject.toml` `[tool.uv]`. Project config outranks user config, so `--locked` passes (probed); the pin also gives every install a supply-chain cutoff. Developers move the date forward to upgrade dependencies.

**Scope:** add the pin, re-lock without version changes, document the bump in CONTRIBUTING.md, and add a test that the pin exists and the lock records it.
<!-- SECTION:DESCRIPTION:END -->
