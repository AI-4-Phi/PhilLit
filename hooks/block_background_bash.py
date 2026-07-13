#!/usr/bin/env python3
"""PreToolUse hook: block run_in_background on Bash tool calls in subagents.

Background Bash tasks outlive subagent sessions -- they keep running after
the agent finishes but nobody reads their output.  This hook prevents
domain researchers (and any other subagent) from accidentally spawning
orphaned background processes.

Only blocks in subagent contexts (agent_id present).  Main session Bash
calls with run_in_background are allowed through.

Reads tool input JSON from stdin (Claude Code hook protocol).
Exits 0 with hookSpecificOutput JSON on stdout.
"""

import json
import sys


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        # Can't parse input -- allow by default
        json.dump({}, sys.stdout)
        return

    tool_input_data = hook_input.get("tool_input", {})
    in_subagent = "agent_id" in hook_input

    if in_subagent and tool_input_data.get("run_in_background") is True:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "run_in_background is not allowed on Bash calls in "
                        "subagents. Use bash & with wait instead."
                    ),
                }
            },
            sys.stdout,
        )
    else:
        json.dump({}, sys.stdout)


if __name__ == "__main__":
    main()
