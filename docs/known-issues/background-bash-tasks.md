# Background Bash Tasks Spawned by Domain Researchers

**Observed**: 2026-02-10, during "What are data?" literature review (two separate runs)
**Severity**: Medium (no data loss, but causes sustained 100% CPU and user confusion)
**Status**: Open

## Summary

During Phase 3 (domain research), multiple `domain-literature-researcher` agents launched `fetch_sep.py` calls using `run_in_background: true` on the Bash tool. This violates explicit instructions in both the skill definition and the agent definition. The background tasks completed after the agents had already finished, producing orphaned output and late completion notifications that confused the user.

## Observed Behavior

### Run 1 (completed but orphaned)

- 6 background Bash tasks were spawned, all fetching the same SEP entry (`science-big-data`)
- Each produced ~68–86 KB of raw JSON output (total ~412 KB), none of which was consumed
- 3 of the 6 outputs were byte-identical; the other 3 differed slightly (likely timing-dependent extraction differences)
- Completion notifications arrived after the review workflow had moved on to later phases
- Multiple domain researchers independently fetched the same SEP entry, compounding the redundancy

### Run 2 (hung indefinitely)

- 6 background Bash tasks spawned, again all fetching `science-big-data` from SEP
- All 6 processes hung at ~100% CPU for 25–30 minutes, producing 0 bytes of output (`sep_science-big-data.txt` was empty)
- The SEP entry `science-big-data` likely does not exist or has a different slug, causing `fetch_sep.py` to hang rather than fail gracefully
- Processes had to be manually killed (`kill` via PID); the last one exited with code 143 (SIGTERM)
- The `fetch_sep.py` script lacks a timeout, so a missing or unreachable SEP entry causes indefinite hangs

## Existing Prohibitions (Ignored by Agents)

Two explicit prohibitions already exist:

1. **`SKILL.md`** (line 72):
   > **Do NOT use `run_in_background`**. Foreground execution streams status updates to the user.

2. **`domain-literature-researcher.md`** (line 310):
   > **NEVER use `run_in_background: true` on Bash tool calls.** Background Bash tasks outlive your session — they keep running after you finish but nobody reads their output. Use bash `&` with `wait` instead.

   The agent definition provides a detailed recommended pattern (lines 312–337) for achieving parallelism with bash `&` + `wait` within a single Bash tool call.

Despite the explicit `NEVER` instruction in their own definition, the agents used `run_in_background: true` anyway. This is a model compliance failure.

## Impact

- **Sustained CPU load**: Hung processes consume ~100% CPU each (600% total for 6 processes) until manually killed
- **User confusion**: Multiple late completion notifications after the workflow finished
- **Wasted compute**: Redundant SEP fetches producing unused output
- **No data loss**: Agents had already completed their work; the background outputs were never consumed by any downstream process

## Options to Address

### Option A: Strengthen agent instructions

Reinforce the prohibition with more context about *why* it matters. The current instruction is already explicit (`NEVER`), so this may have limited additional effect. Could try:
- Moving the prohibition higher in the agent definition (closer to the top)
- Adding a concrete negative example showing the broken behavior
- Repeating the prohibition near the SEP/encyclopedia search instructions specifically

### Option B: SubagentStop hook validation

Add a SubagentStop hook (project-level, in `.claude/settings.json`) that inspects domain researcher agent output for evidence of `run_in_background` usage and flags it. This is reactive (catches it after the fact) but would at least surface the violation reliably.

### Option C: Cache SEP fetches across domains

Implement a project-level cache for `fetch_sep.py` results so that even if multiple domain researchers fetch the same entry, only the first one does real work. This doesn't fix the `run_in_background` violation but eliminates the redundancy cost. Note: `fetch_sep.py` may already have caching — check whether the cache is shared across concurrent agent processes.

### Option D: PreToolUse hook to block `run_in_background`

Add a PreToolUse hook on the Bash tool that rejects calls with `run_in_background: true` when invoked from within a subagent context. This would be a hard guardrail rather than relying on model compliance. Requires checking whether PreToolUse hooks fire in Task-spawned subagents (CLAUDE.md notes they may not fire for PreToolUse hooks in agent frontmatter, but project-level hooks in `settings.json` may behave differently).

### Option E: Add timeout to `fetch_sep.py`

Add a request timeout (e.g., 60 seconds) and overall script timeout to `fetch_sep.py` so that missing or unreachable SEP entries fail fast instead of hanging indefinitely. This is independent of the `run_in_background` issue but prevents the worst symptom (sustained 100% CPU zombie processes).

### Option F: Limit SEP queries per review

Have the orchestrator (Phase 3 launcher) specify which SEP entries each domain researcher should fetch, avoiding overlap. This requires the `literature-review-planner` (Phase 2) to identify relevant SEP entries upfront and assign them to domains. Adds planning complexity but eliminates redundant fetches at the source.

## Recommendation

Options are not mutually exclusive. A reasonable combination:
- **Option E** (low effort) — Add timeout to `fetch_sep.py` to prevent zombie processes
- **Option A** (low effort) — Strengthen instructions as a first pass
- **Option D** (medium effort) — Hard guardrail via hook if the model continues to ignore instructions
- **Option C** (medium effort) — Cache as defense-in-depth against redundancy regardless of how tasks are launched
