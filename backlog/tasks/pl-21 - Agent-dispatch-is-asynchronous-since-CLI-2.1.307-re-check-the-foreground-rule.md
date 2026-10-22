---
id: PL-21
title: 'Agent dispatch is asynchronous since CLI 2.1.307: re-check the foreground rule'
status: To Do
assignee: []
created_date: '2026-10-22 10:28'
labels:
  - hooks
  - test-run
dependencies: []
type: verify
project: Platform
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** in a headless run on Claude Code 2.1.307 (2026-10-22), every Agent dispatch returned "Async agent launched" with no `run_in_background` flag, the planner included. The orchestrator ended its turn while the researchers ran, and `-p` stopped them 10 minutes later (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` now in CLAUDE.md's headless recipe fixes runs). `block_subagent_background_dispatch.py` and SKILL.md still say the four review agents must run in the foreground; the hook only sees `run_in_background`, so it cannot enforce that any more.

**Check:** whether an interactive session dispatches the same way; whether anything relied on foreground dispatch (the hook's rationale, SKILL.md wording, the researchers' 10-minute Bash budget); then either rewrite the rule and the hook's docstring to the new behaviour, or retire the hook. phillit-service is not affected at its pin (bundled CLI 2.1.233); its worker sets `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` and measured inline dispatch in every acceptance run, so test that variable first as the fix for headless runs and plugin users.
<!-- SECTION:DESCRIPTION:END -->
