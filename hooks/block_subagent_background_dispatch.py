#!/usr/bin/env python3
"""PreToolUse hook: block background dispatch of PhilLit review subagents.

The literature-review workflow requires its subagents to run in the
FOREGROUND (batched, results returned inline).  As of Claude Code v2.1.198
the dispatch tool (renamed Task -> Agent) defaults to background, so a stray
``run_in_background: true`` on an Agent dispatch silently orphans a review
agent -- it keeps running after the orchestrator moves on and nobody reads
its BibTeX output.  This hook denies such a dispatch at the orchestrator.

Mirror-image of block_background_bash.py: that gate blocks background Bash
*inside* subagents (agent_id present); this one blocks background Agent
dispatch *at the orchestrator* (agent_id ABSENT).  Scope is limited to the
four PhilLit review agents, so unrelated background dispatches in a PhilLit
workspace are untouched.

Field names verified empirically against Claude Code 2.1.215:
  tool_name == "Agent"; tool_input = {subagent_type, run_in_background,
  prompt, description}; agent_id absent at orchestrator level.

Reads the hook JSON from stdin (Claude Code hook protocol).
Exits 0 with hookSpecificOutput JSON on stdout.
"""

import json
import sys

# The four review subagents that must run in the foreground (see SKILL.md).
PHILLIT_AGENTS = frozenset(
    {
        "literature-review-planner",
        "domain-literature-researcher",
        "synthesis-planner",
        "synthesis-writer",
    }
)


def _bare_agent(subagent_type: str) -> str:
    """Strip any plugin namespace, e.g. 'phillit:synthesis-writer' -> 'synthesis-writer'."""
    return subagent_type.rsplit(":", 1)[-1] if subagent_type else ""


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        # Can't parse input -- allow by default.
        json.dump({}, sys.stdout)
        return

    tool_input_data = hook_input.get("tool_input", {})
    at_orchestrator = "agent_id" not in hook_input
    is_background = tool_input_data.get("run_in_background") is True
    agent = _bare_agent(tool_input_data.get("subagent_type", ""))

    if at_orchestrator and is_background and agent in PHILLIT_AGENTS:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"PhilLit review agents must run in the foreground. Re-dispatch "
                        f"'{agent}' with run_in_background: false. Parallelism comes from "
                        "issuing several foreground dispatch calls in one message, not from "
                        "backgrounding -- a backgrounded review agent is orphaned and its "
                        "output is never read."
                    ),
                }
            },
            sys.stdout,
        )
    else:
        json.dump({}, sys.stdout)


if __name__ == "__main__":
    main()
