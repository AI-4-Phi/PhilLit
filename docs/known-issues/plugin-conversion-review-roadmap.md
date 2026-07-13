# Plugin-Conversion Review: Findings and Roadmap

**Origin**: Comprehensive code review of `plugin-conversion` vs `main`, 2026-07-13 (workflow-backed, xhigh effort; 6 finder angles, every candidate independently verified — 15 confirmed root causes, 1 candidate refuted).
**Status**: Merge to `main` is gated on Phases 1–3. Phase 4 may follow the merge.

Theme: the conversion inverted the gate-failure directions — the accuracy-critical BibTeX gate failed *open* (silently) when its tooling crashed, while low-stakes helper hooks failed *closed* (bricking the workspace). The corrective policy is documented in `CLAUDE.md` ("Hooks and Python" → gate-failure policy).

## Findings

| # | Location | Defect | Phase |
|---|----------|--------|-------|
| 1 | all bundled scripts (`load_dotenv`) | Installed plugin never loads the workspace `.env`: bare `load_dotenv()` resolves via `find_dotenv()`, which walks up from the *script's* directory (plugin cache), never the cwd | 1 |
| 2 | `hooks/subagent_stop_bib.sh:102` | Validator/uv crash yields empty stdout; `jq` on empty input exits 0, so the crash silently passes as valid — anti-hallucination gate disabled exactly when the env is broken | 1 |
| 3 | `hooks/hooks.json` (PreToolUse) | uv exit 2 (cold build failure, offline) propagates out of the hook and hard-blocks every Bash/Write in the workspace; the old `\|\| echo '{}'` fallback was dropped | 1 |
| 4 | `hooks/setup-environment.sh:46` / `bin/phillit-run:24` | `PHILLIT_UV` is bridged via `CLAUDE_ENV_FILE`, which reaches Bash tool calls and subagents but **not hook processes** — the wrapper must self-resolve uv | 1 |
| 5 | `agents/*.md` | Agents reference `../docs/conventions.md`, unresolvable from a plugin user's workspace (SKILL.md was fixed to `$PHILLIT_ROOT/…`; agents were not) | 1 |
| 6 | `bin/phillit-run` | Committed mode 100644 (not executable) although Claude Code puts the plugin's `bin/` on PATH | 1 |
| 7 | parity gate method | Gate ran with `--plugin-dir <dev checkout>`: the repo-root `.env` masked finding 1; hook-process env (finding 4) was never exercised | 2 |
| 8 | `skills/setup/SKILL.md:22` | `bash "$PHILLIT_ROOT/bin/phillit-run"` with no guard for unset `PHILLIT_ROOT` (plugin installed mid-session) → cryptic `/bin/phillit-run: No such file` on first run | 3 |
| 9 | `skills/setup/SKILL.md:51` | Trust check keys `.projects[$PWD]`; symlinked cwd (e.g. OneDrive, `/var`→`/private/var`) never matches the canonical path in `.claude.json` → permanent false "untrusted" | 3 |
| 10 | `hooks/subagent_stop_bib.sh:32` | Missing `jq` silently disables SubagentStop validation (stderr + exit 0 is never surfaced) | 1* |
| 11 | `skills/setup/scripts/setup_workspace.py:34` | `_union` does `list(existing)`: a string-valued `allow`/`deny`/`ask` is exploded into single characters and written back | 3 |
| 12 | `skills/setup/scripts/setup_workspace.py:120` | Re-running setup copies the already-merged settings over `settings.json.bak`, destroying the pristine backup | 3 |
| 13 | `README.md:103` | Settings opt-out path self-defeating: manual-merge users still need the `.phillit/` marker but are only told to run the setup that merges anyway (never told the marker is just `mkdir .phillit`) | 3 |
| 14 | `rate_limiter.py:56`, `search_cache.py:30` | World-shared `$TMPDIR` dirs break on multi-user hosts (PermissionError on another user's lock files) | 4 |
| 15 | `hooks/hooks.json` + docs | Trivial per-call gates pay uv startup (and a possible cold venv build > 60 s hook timeout) per invocation; residual doc staleness (CLAUDE.md dev loop, `--no-dev` omission) | 4 |

\* Finding 10 is fixed alongside Phase 1 (same file/policy), though listed by the review in the setup cluster.

## Phases

- **Phase 1 — plugin runtime fixes (merge blockers)**: findings 1–6, 10. Status: **done** (2026-07-13). Regression-pinned by `tests/test_dotenv_loading.py`, `tests/test_agent_definitions.py`, and new tests in `test_phillit_run.py` / `test_subagent_stop_bib.py` / `test_hooks_json.py`; verified empirically from a plugin copy outside the repo (workspace-only `.env` loads; broken uv → SubagentStop blocks with a "crashed" reason while PreToolUse fails open with a `systemMessage`).
- **Phase 2 — harden + re-run the parity gate**: finding 7. Re-test from a plugin copy *outside* the repo, with a workspace `.env` that differs from the shell env, and an explicit hook-process check. Status: **done** (2026-07-13). All eight checks pass — outside-repo `git archive` copy, conflicting workspace/shell env, `env -i` hook-process sims (uv off PATH, broken uv, jq absent), and four headless sessions (bridge + live hooks, stripped PATH, SubagentStop researcher gate, no-marker control). Results table: `plugin-parity-gate.md` → "Phase 2 re-run".
- **Phase 3 — setup robustness**: findings 8, 9, 11, 12, 13. Status: **pending**.
- **Phase 4 — efficiency + doc sweep (post-merge OK)**: findings 14, 15. Consider pure-shell versions of `block_background_bash` / write-time validation to take uv off the per-call hook path. Status: **pending**.

After Phase 3: bump `version` in `.claude-plugin/plugin.json`, merge to `main`.
