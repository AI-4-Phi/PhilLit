---
id: PL-3
title: One owner each for the env-var and hooks-wiring docs
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
labels: []
dependencies: []
references:
  - .env.example
  - skills/philosophy-research/scripts/check_setup.py
  - docs/permissions-guide.md
type: docs
project: Consistency
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** A fact kept in several files drifts. The CORE key's description already has, and the hooks wiring needed correcting in two consecutive doc passes.

1. **Environment variables.** `.env.example`, `check_setup.py`, `skills/setup/SKILL.md` and `skills/philosophy-research/SKILL.md` all describe the keys, and CORE has already drifted. `check_setup.py` says the key "improves rate limits" and `.env.example` says it "improves CORE full-text discovery", but without it `search_core.py` and the CORE abstract fallback skip entirely. Make `.env.example` and `check_setup.py` the owners, and cut philosophy-research's copy to a pointer. Open: whether `skills/setup/SKILL.md`, the first-run text a user reads, keeps its list or points too.
2. **Hooks wiring.** It is listed in CLAUDE.md, `docs/ARCHITECTURE.md` and `docs/permissions-guide.md`. Make the permissions-guide table the wiring owner, and cut the others to file names and purpose.
<!-- SECTION:DESCRIPTION:END -->
