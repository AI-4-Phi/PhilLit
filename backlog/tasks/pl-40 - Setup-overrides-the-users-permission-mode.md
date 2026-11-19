---
id: PL-40
title: Setup overrides the user's permission mode
status: To Do
assignee: []
created_date: '2026-11-17T13:00:00Z'
labels:
  - test-run
dependencies: []
type: bug
project: Safety
ordinal: 1500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** `/phillit:setup` writes `"defaultMode": "default"` into the workspace's `.claude/settings.json` (`PHILLIT_RULES` in `skills/setup/scripts/setup_workspace.py`). The merge skips this only when that project file already sets a mode. It does not look at the user's own `~/.claude/settings.json`. Project settings take precedence over user settings, so a user whose default is `auto`, as many users' is, silently gets manual mode in every PhilLit workspace. Seen on goldfinch, 2026-11-17: setup at 11:02 wrote the key into `~/Documents/Work/Research/.claude/settings.json`, and the next session started in manual mode although the user-level default was `auto`.

**Ruling (Johannes, 2026-11-17):** setup does not change the permission mode at all. Its purpose is that reviews run without repeated prompts, and the allow, ask and deny rules it merges achieve that in any mode that respects them. The permission mode is the user's choice.

**Scope:**
- Drop `defaultMode` from `PHILLIT_RULES` and from the merge.
- Update `tests/test_setup_workspace.py`, and add a test that a merge never adds `defaultMode`.
- Remove the "Default Mode" part of `docs/permissions-guide.md` and the `defaultMode` line from the manual-settings JSON in `README.md`.
- Decide what setup does with the key it already wrote in existing workspaces. One option: remove `"defaultMode": "default"` when the backup shows that setup added it. Otherwise, say in the setup output how to remove it.
- Check that the merged rules also hold in `auto` mode: no prompts in a review run, and the deny rules for the ledger files still bind.
<!-- SECTION:DESCRIPTION:END -->
