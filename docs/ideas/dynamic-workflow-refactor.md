# Dynamic-Workflow Refactor of the Literature-Review Orchestration

**Date**: 2026-07-22
**Status**: Unblocked — the Step 1 gate test was executed 2026-07-22 and **PASSED on all six checks** (see "Step 1 results" below). Implementation (roadmap steps 2–6) not started.
**Origin**: Feasibility investigation of refactoring `skills/literature-review/` onto Claude Code's dynamic-workflow feature (docs verified 2026-07-22: workflows.md, plugins.md, plugins-reference.md at code.claude.com/docs).

## Summary

The Phase 3 → 4 → 5 pipeline (parallel domain researchers → synthesis planner → parallel section writers) maps exactly onto the Workflow tool's primitives, and a workflow script would replace the two most prose-fragile guarantees in `SKILL.md` — "include ALL Task tool calls in a single message" and "never advance before all agents complete" — with deterministic `parallel()`/barrier semantics.

Plugins cannot ship workflows, but `/phillit:setup` can install one: copying a workflow file from the plugin into the workspace's `.claude/workflows/` is the same move as the existing permissions merge (a plugin cannot ship permissions either; setup merges them into `.claude/settings.json`).

**The gating unknown is resolved**: plugin hooks — including the fail-closed SubagentStop BibTeX validator with its full block → re-prompt → fix loop — fire for workflow-spawned subagents exactly as for Task-tool subagents (empirically verified 2026-07-22, Claude Code 2.1.218; see "Step 1 results" below). The refactor is unblocked.

## Verified facts (docs, 2026-07-22)

- **Availability**: Workflow tool requires Claude Code ≥ 2.1.154, all paid plans; Pro users must enable it via `/config` ("Dynamic workflows" row). Multi-directory project workflow resolution is ≥ 2.1.178. *Decision: we assume users run a current version; no Task-tool fallback path will be maintained.*
- **Plugins cannot ship workflows**: plugin components are skills, agents, hooks, MCP/LSP servers, monitors, settings. No `workflows/` plugin directory, no `workflows` field in `plugin.json`.
- **Named workflows are plain files**: an ESM JavaScript script in `.claude/workflows/` (project) or `~/.claude/workflows/` (user), identified by its `meta.name` field — dropping the file in the directory *is* the registration; there is no other mechanism. Docs do not state the required file extension (test in Step 1; `.js` is the safe guess).
- **Precedence**: project-level `.claude/workflows/` beats `~/.claude/workflows/` on name collision; nested project dirs resolve closest-to-cwd first. Installing into the workspace scopes correctly. `meta.name` has no plugin namespacing — prefix it (`phillit-…`).
- **Invocation**: users run `/<meta.name>`; the model can also call the Workflow tool with `{name: …}` plus a structured `args` value (arrays/objects arrive as real values, readable as the `args` global in the script).
- **No mid-run user input** (confirmed verbatim in docs): only permission prompts can pause a run; per-stage sign-off requires one workflow per stage. *Decision: acceptable — the workflow covers only the non-interactive middle of the review; Human-in-the-Loop mode is not a constraint we optimize for.*
- **Execution mode**: the docs say workflow subagents always run in `acceptEdits` mode and inherit the session's tool allowlist. *Step 1 verified*: PhilLit's scoped `Write`/`Edit` rules bind as expected — and hook payloads actually report `permission_mode: "default"`, contradicting the docs' `acceptEdits` claim (at least headless, 2.1.218).
- **Custom agent types**: the Workflow tool's `agent()` accepts an `agentType` option resolved from the same registry as the Task tool. *Step 1 verified*: `agentType: "phillit:domain-literature-researcher"` resolves, and hook payloads carry exactly that string.

## Proposed architecture

The skill remains the entry point and keeps everything interactive or bash-shaped; the workflow takes the deterministic agent pipeline.

| Piece | Where | Why |
|---|---|---|
| Phase 1 (env check, resume detection, guards) | skill (main loop) | interactive prompts; bash via `phillit-run` |
| Phase 2 (planner + user feedback loop) | skill (main loop) | requires mid-run user input |
| Phases 3–5 (researchers ×N → planner → writers ×N) | **workflow script** | the fan-out/barrier pipeline; `parallel()` makes the parallelism and waiting deterministic |
| Phase 6 (assembly scripts, cleanup, DOCX) | skill (main loop) | workflow scripts cannot run bash — only spawn agents; spawning agents to run `dedupe_bib.py` etc. wastes tokens |

Workflow shape: `parallel(domains.map(researcher))` → barrier (justified: synthesis-planner reads **all** domain `.bib` files) → `agent(synthesis-planner)` → `parallel(sections.map(writer))`. Inputs (topic, review dir, domain list) pass via `args`; outputs stay file-based (`literature-domain-N.bib`, `synthesis-section-N.md`), so `task-progress.md` cross-conversation resume keeps working unchanged.

Delivery: the script lives in the plugin repo (single source of truth); `setup_workspace.py` copies it to `<workspace>/.claude/workflows/phillit-lit-review.js` alongside the existing marker/env/permissions steps. `apply()` already receives `plugin_root` and `workspace` and writes atomically into `.claude/` — this is a few lines in an established code path.

## Known costs and risks

- **Staleness / drift**: the installed workflow is a snapshot; `/plugin update` does not touch it. Setup must overwrite on re-run (same backup discipline as the settings merge), and a version stamp inside the installed file should be compared against the plugin's copy (by the skill at Phase 1, or the check-updates hook) to prompt a setup re-run. This is a second copy of orchestration logic — a real single-source-of-truth cost.
- **Guard bypass**: `block_subagent_background_dispatch.py` matches Agent/Task calls; a Workflow call sails past it. The foreground-only rationale (orchestrator proceeding before agents finish — PR #38) is solved *by* the workflow's own `await`, but the guard's coverage story should be re-examined in this design.
- **UX change**: foreground Task dispatch streams researcher status inline; a workflow shows progress via the `/workflows` tree instead.

## Roadmap

1. **Empirical gate test (first step — decisive) — DONE 2026-07-22, PASSED (all six checks; results below)**. A minimal test — no full researcher run, no API keys, a few thousand tokens — settles whether plugin hooks fire for workflow-spawned agents. Full protocol in "Step 1 protocol" below. It checks:
   - (a) the SubagentStop BibTeX validator fires on the workflow-spawned agent;
   - (b) the PreToolUse/PostToolUse `.bib` gates fire on its Write/Edit calls;
   - (c) scoped `Write`/`Edit` and deny rules bind under `acceptEdits`;
   - (d) `agentType: "phillit:domain-literature-researcher"` resolves;
   - (e) file naming/extension conventions in `.claude/workflows/` (name from `meta.name` vs filename);
   - (f) `CLAUDE_ENV_FILE` bridging (`PHILLIT_ROOT` etc.) reaches workflow subagents.
   If (a) or (b) fails, record the result here, mark this plan dead, and stop.
2. Author the production workflow script (Phases 3–5) in the plugin repo; namespaced `meta.name`, version stamp, `args` contract.
3. Extend `setup_workspace.py` to install/refresh the workflow file (atomic write, backup, overwrite-on-rerun), and add a `Workflow` allow rule to `PHILLIT_RULES` (Step 1 showed running a saved workflow otherwise hits a "Review dynamic workflow before running" approval gate).
4. Refactor `SKILL.md`: Phases 3–5 delegate to the workflow (Workflow tool `{name, args}`); keep file-based outputs and `task-progress.md` resume; update Status Updates section for the `/workflows` progress model.
5. Add the version-stamp freshness check (Phase 1 or check-updates hook).
6. Update `docs/ARCHITECTURE.md` ("Orchestration: Skill-Based Design" becomes hybrid skill + workflow), bump `plugin.json`, release.

## Step 1 protocol: minimal hook-firing test

**Why minimal suffices.** Every PhilLit hook keys on mechanical conditions, never on agent behavior: the Write/Edit gates fire on the literal needle `.bib` in the tool-call JSON plus the `.phillit/` marker; the background-Bash gate detects subagent context solely via `"agent_id" in hook_input`; the SubagentStop validator self-scopes on the *string* `agent_type` containing `domain-literature-researcher`, the `reviews/.active-review` pointer, and `.bib` files *on disk*. None of that requires real searches — a throwaway agent with a scripted prompt exercises everything. Real API keys, `.env` setup, and researcher behavior contribute nothing to the question.

**Two design principles:**

- **Test by blocking, not by passing.** Use deliberately *invalid* BibTeX: a firing hook produces a visible denial/block with a reason; a clean pass is indistinguishable from a hook that never ran. The invalid-`.bib` SubagentStop block also reveals what `{"decision": "block"}` does to a workflow-spawned agent (re-prompt as with Task agents, or nothing).
- **Sentinel logger.** Temporarily add logging hooks (below) that append each event's raw stdin JSON to a file. This distinguishes "hook never fired" from "hook fired but self-scoped out" — critical because the `agent_type` string that workflow agents report in SubagentStop payloads is itself unknown and might not contain `domain-literature-researcher` even when `agentType` is passed. Without the logger those two outcomes look identical.

### Setup (fresh session, reproducible)

Prerequisites: Claude Code ≥ 2.1.154 (on Pro: enable "Dynamic workflows" in `/config`); a PhilLit dev checkout.

1. **Sentinel logger** — in the *dev checkout's* `hooks/hooks.json`, add one extra logging hook per event (alongside the existing entries; temporary, never commit). A logger that writes nothing to stdout makes no decision, so it cannot perturb the behavior under test:

   ```json
   { "type": "command", "command": "sh -c 'printf \"[SubagentStop] \" >> \"${CLAUDE_PROJECT_DIR}/hook-events.log\"; cat >> \"${CLAUDE_PROJECT_DIR}/hook-events.log\"; printf \"\\n\" >> \"${CLAUDE_PROJECT_DIR}/hook-events.log\"'" }
   ```

   Add matcher-less copies (with the prefix adjusted) under `PreToolUse`, `PostToolUse`, and `SubagentStop`.

2. **Scratch workspace** (never run this inside the PhilLit repo):

   ```bash
   mkdir phillit-wf-test && cd phillit-wf-test
   claude --plugin-dir /path/to/PhilLit
   ```

   In the session: run `/phillit:setup` (needed for real permission rules — item (c) tests the scoped `Write`/`Edit` rules that setup merges into `.claude/settings.json`). API keys can be dummies; no script that needs them will run.

3. **Pre-plant workspace state** (from a shell, so no hooks interfere):

   ```bash
   mkdir -p reviews/hook-test .claude/workflows
   echo "reviews/hook-test" > reviews/.active-review
   printf '@article{broken, title = {Unclosed\n' > reviews/hook-test/planted.bib
   ```

   The planted invalid `.bib` is what the SubagentStop validator must catch — the agent itself may never get an invalid file past the Write gate (if that gate fires, which is the point).

4. **Save the workflow** as `.claude/workflows/phillit-hook-test.js` (if `/phillit-hook-test` doesn't register, try `.mjs` — the extension convention is item (e)):

   ```javascript
   export const meta = {
     name: 'phillit-hook-test',
     description: 'Plumbing test: do plugin hooks fire for workflow-spawned agents?',
   }

   // Tier 1: generic agent — Write/Edit gates (b), permission binding (c), env bridging (f)
   const generic = await agent(`Plumbing test — follow these steps literally, do not improvise, do not retry denials:
   1. Write exactly this content to reviews/hook-test/gate-probe.bib :
      @article{broken2, title = {Unclosed
   2. If step 1 succeeded, use the Edit tool on that file: replace "Unclosed" with "StillUnclosed".
   3. Run the Bash command: echo bg-probe — with run_in_background set to true.
   4. Write the text "outside" to ./outside-probe.txt (project root, NOT under reviews/).
   5. Run the Bash command: echo "PHILLIT_ROOT=$PHILLIT_ROOT"
   Report per step: allowed or denied, plus any denial reason VERBATIM, plus step 5's output.`)

   // Tier 2: plugin agent — agentType resolution (d), SubagentStop validator (a)
   const researcher = await agent(`PLUMBING TEST — do not run any literature searches or API scripts.
   Reply with the single word "ready" and stop.
   If you are then re-prompted with BibTeX validation errors, quote them verbatim, overwrite
   reviews/hook-test/planted.bib with this valid entry, and stop again:
   @article{ok2020, author = {Author, Test}, title = {Probe}, journal = {J}, year = {2020}}`,
     { agentType: 'phillit:domain-literature-researcher' })

   return { generic, researcher }
   ```

5. **Run it**: ask the session to run `/phillit-hook-test` (or call the Workflow tool with `{name: 'phillit-hook-test'}` — programmatic `{name}` invocation is one of the things to confirm).

### Reading the results

| Item | PASS looks like | FAIL / diagnosis |
|---|---|---|
| (e) registration | `/phillit-hook-test` resolves and runs | try `.mjs`; note whether filename or `meta.name` governs |
| (b) Write gate | tier-1 step 1 denied with a BibTeX validation reason | write succeeds and garbage lands on disk → check log: no `[PreToolUse]` line = never fired; line present = fired but mis-decided |
| (b) Edit gate | step 2 unreachable (write denied) or post-edit validation feedback appears | `[PostToolUse]` line absent from log |
| Bash gate | step 3 denied ("background Bash… subagents") | allowed → check logged payload for missing `agent_id` (workflow agents may not carry it) |
| (c) permissions | step 4 denied or prompts (a prompt pauses the run — itself informative) | silent write outside `reviews/` under `acceptEdits` |
| (f) env bridging | step 5 prints a real path | empty `PHILLIT_ROOT` → real researchers would need env passed another way (e.g. via prompt/`args`) |
| (d) resolution | tier-2 agent spawns (no unknown-agentType error) | error → try unprefixed name; record what resolves |
| (a) SubagentStop | tier-2 stop is blocked citing `planted.bib` errors; agent fixes and re-stops (the `stop_hook_active` guard allows the second stop) | clean stop → check log: no `[SubagentStop]` line = event doesn't fire for workflow agents (**plan dead**); line present = inspect its `agent_type` — if it lacks `domain-literature-researcher`, the hook fired but self-scoped out (fixable: adjust the scoping substring) |

Note the generic tier-1 agent's stop also lands in the log — a `[SubagentStop]` entry there already proves the event fires; its payload shows the baseline `agent_type` for untyped workflow agents.

### Cleanup

Revert the sentinel-logger entries in `hooks/hooks.json` (they must never ship) and delete the scratch workspace. Record the outcome — pass or fail, with the logged `agent_type` strings — in this document.

## Step 1 results (2026-07-22): PASS on all six checks

Executed per the protocol on Claude Code **2.1.218**, fully isolated and headless: the plugin checkout was *copied* to a scratch directory (sentinel loggers added only to the copy — the repo was never touched), the workspace scaffolded via `setup_workspace.py`, and the test session run with `claude -p … --plugin-dir <copy> --model sonnet --strict-mcp-config` under a fresh scratch `CLAUDE_CONFIG_DIR` authenticated via `ANTHROPIC_API_KEY`. Sentinel log: 11 PreToolUse, 8 PostToolUse, 3 SubagentStop events.

| Check | Result | Evidence |
|---|---|---|
| (a) SubagentStop validator | **PASS** | Researcher's first stop **blocked** citing `planted.bib`'s syntax error; the agent quoted the errors verbatim, wrote the valid entry, and its second stop was allowed (`stop_hook_active: true` loop guard, as designed). The block → re-prompt → fix loop is identical to Task-agent behavior. |
| (b) Write/Edit `.bib` gates | **PASS** | PreToolUse denied the invalid-BibTeX Write with `bib_validator.py`'s message verbatim ("premature end of file"). PostToolUse events fire for workflow agents (8 logged); the Edit-specific gate was unreachable (the invalid file never got created — anticipated by the matrix) but shares the same `fast_gate.sh` plumbing. |
| Bash background gate | **PASS** | `run_in_background: true` denied with `block_background_bash.py`'s exact message — which also proves workflow subagents **carry `agent_id`** in hook payloads. |
| (c) permission binding | **PASS** | Write to `./outside-probe.txt` (outside `reviews/`) was not granted; writes under `reviews/` passed permissions (then hit the validator). Note: `Edit(reviews/**)` covers the whole Write/Edit tool family in Claude Code's permission model. **Docs discrepancy**: SubagentStop payloads report `permission_mode: "default"`, not the documented `acceptEdits`. |
| (d) plugin agentType | **PASS** | `agentType: "phillit:domain-literature-researcher"` resolved; hook payloads carry exactly that string, so `subagent_stop_bib.sh`'s substring scoping matches unchanged. Untyped workflow agents report `agent_type: "workflow-subagent"`. |
| (e) registration | **PASS** | A `.js` file in `.claude/workflows/` registered under its `meta.name`; programmatic `Workflow({name: 'phillit-hook-test'})` invocation worked. |
| (f) env bridging | **PASS** | `PHILLIT_ROOT` resolved to the plugin root inside a workflow subagent's Bash call — the SessionStart `CLAUDE_ENV_FILE` bridge reaches workflow agents. |

**Additional findings** (feed into roadmap steps 2–3):

- **A `Workflow` allow rule is required.** The first run was denied with `Review dynamic workflow before running`; adding `"Workflow"` to the workspace's `permissions.allow` cleared it. `PHILLIT_RULES` in `setup_workspace.py` must add this rule for the autopilot experience (roadmap step 3).
- **Headless gotcha (test-rig only)**: an untrusted workspace silently ignores all `.claude/settings.json` allow rules in `claude -p` (stderr warning only). Remedy: pre-seed `projects[<workspace>].hasTrustDialogAccepted: true` in the (scratch) config dir's `.claude.json`. Interactive users accept the trust dialog instead, so this does not affect production.
- **Minor quirk**: the saved workflow is also visible to workflow *subagents* as an invokable skill; the untyped tier-1 agent briefly tried to invoke it before proceeding. Harmless here; production agent prompts should not reference the workflow by name.
- The isolated-copy approach (sentinel loggers in a scratch copy of the plugin, scratch `CLAUDE_CONFIG_DIR`) is strictly better than the protocol's original "edit the dev checkout, revert later" — nothing in the real checkout or live config is ever modified.
