---
id: PL-11
title: Confirm the in-place init refusal ruling
status: Needs Johannes
assignee: []
created_date: '2026-09-25 19:18'
labels:
  - workdir
dependencies: []
references:
  - skills/literature-review/scripts/workdir.py
  - skills/literature-review/SKILL.md
type: decision
project: Safety
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** A delivered review is never changed. This ruling decides where that promise is enforced when a review runs in the workspace folder itself (in place).

**What shipped (0.5.30):** when `workdir.py init` falls back to in-place mode on its own (no allow rule for the local folder, or a path the shell cannot quote) and `reviews/<name>/` already holds a finished review, `init` refuses and suggests `<name>-2`. With an explicit `PHILLIT_WORKDIR=inplace`, the service's setting, `init` still accepts the folder and prints `"existing_review": true`. SKILL.md's "Guard — completed review" then has the orchestrator clear the pointer and choose a new name.

Both earlier outcomes stand: the plugin refuses and suggests `-2`, and the service continues in the folder it pre-created. Only the plugin's refusal moved from prose into code.

**Cost if wrong:** a plugin user who sets `PHILLIT_WORKDIR=inplace` explicitly is protected by the prose guard alone. If the session dies between `init` and the guard, the pointer names the delivered review, and a resume could re-run Phase 6 on it.

**Decision needed:** confirm the ruling, or overturn it. Overturning it means refusing for explicit in-place too, and giving the service another way to opt in.
<!-- SECTION:DESCRIPTION:END -->
