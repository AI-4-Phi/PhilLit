#!/usr/bin/env python3
"""PreToolUse hook: force PhilLit review subagents into the foreground.

The literature-review workflow wants its four review agents to run in the
FOREGROUND: several dispatch calls in one message run in parallel, each
returns its agent's result inline, and the orchestrator cannot advance
before they finish. Where the dispatch tool (Agent, formerly Task) lists
`run_in_background`, an OMITTED flag means background: on Claude Code
2.1.307 the orchestrator omitted it on all 61 review-agent dispatches of
three headless runs (2026-10-22), each returned "Async agent launched",
and `-p` stopped the researchers mid-run. A deny on an explicit `true`,
which this hook used to be, never saw those calls.

So the hook REWRITES the call instead of denying it: it sets
`run_in_background: false` (absent or true alike) through `updatedInput`,
without a permissionDecision, so the user's permission rules still apply
and the call costs no extra turn. Measured on 2.1.307 and 2.1.309: the
rewritten call returns the agent's result inline, and two rewritten calls
in one message still run in parallel. A foreground agent stays foreground
unless `CLAUDE_AUTO_BACKGROUND_TASKS` is set, which moves it to the
background after 120 s (read off the 2.1.309 binary).

All of that holds for headless (`-p`) runs. An INTERACTIVE 2.1.309 session
runs every agent in the background whatever the flag says: there the rewrite
lands (measured: a rewritten description appeared on the launched task) and
the result still comes back `async_launched`. That is harmless, since an
interactive session stays open for the completion notifications, but it is
why SKILL.md's notification rules stay load-bearing.

No-op when `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` is set (phillit-service's
worker sets it): the tool then lists no such flag and every dispatch is
already inline. 2.1.309 tolerates the injected key on a flagless tool, but
an older CLI might reject it. Untested residual: a flagless CLI without
that variable (2.1.267 measured no flag on 2026-09-10) gets the key too.

Scope: the four review agents (any plugin namespace) at the orchestrator
(`agent_id` absent; subagents cannot dispatch). Disabling background tasks
workspace-wide is NOT the plugin's fix: with it, a Bash command is never
moved to the background, so a barrier that outlasts the 10-minute Bash
ceiling would be killed.

Reads the hook JSON from stdin (Claude Code hook protocol). Exits 0 with
JSON on stdout: `{}` to leave the call alone.
"""

import json
import os
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


def _background_tasks_disabled() -> bool:
    return (os.environ.get("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS") or "").strip().lower() in (
        "1", "true", "yes", "on")


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
        tool_input = dict(hook_input.get("tool_input") or {})
    except (json.JSONDecodeError, EOFError, AttributeError, TypeError, ValueError):
        # Plumbing gate: fail open, but never silently.
        json.dump({"systemMessage": "PhilLit: foreground-dispatch gate could not read "
                   "its input - the dispatch was not forced to the foreground."}, sys.stdout)
        return

    at_orchestrator = "agent_id" not in hook_input
    agent = _bare_agent(str(tool_input.get("subagent_type") or ""))
    if (at_orchestrator and agent in PHILLIT_AGENTS
            and tool_input.get("run_in_background") is not False
            and not _background_tasks_disabled()):
        tool_input["run_in_background"] = False
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "updatedInput": tool_input}}, sys.stdout)
    else:
        json.dump({}, sys.stdout)


if __name__ == "__main__":
    main()
