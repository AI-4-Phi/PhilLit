"""Tests for hooks/block_subagent_background_dispatch.py — the PreToolUse gate
that forces PhilLit review subagents into the foreground at the orchestrator.

The gate REWRITES the call (updatedInput, run_in_background: false, no
permissionDecision) when all of these hold:
  - the call is at the orchestrator (no ``agent_id`` in the payload) on the
    Agent or Task tool,
  - ``tool_input.subagent_type`` names one of the four review agents, bare
    or as ``phillit:<name>``,
  - ``tool_input.run_in_background`` is not already ``False`` (absent is the
    case that orphaned 61 dispatches on Claude Code 2.1.307), and
  - CLAUDE_CODE_DISABLE_BACKGROUND_TASKS is unset (then the tool lists no
    flag and every dispatch is inline already).
Everything else passes through ({}); unreadable input fails open with a
systemMessage.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).parent.parent / "hooks" / "block_subagent_background_dispatch.py"

PHILLIT_AGENTS = [
    "literature-review-planner",
    "domain-literature-researcher",
    "synthesis-planner",
    "synthesis-writer",
]

_ABSENT = object()


def _run(payload, env_extra=None):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    env = {k: v for k, v in os.environ.items()
           if k != "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"}
    env.update(env_extra or {})
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin, capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _dispatch(subagent_type, run_in_background=_ABSENT, agent_id=None, tool_name="Agent"):
    tool_input = {"subagent_type": subagent_type, "description": "d", "prompt": "p"}
    if run_in_background is not _ABSENT:
        tool_input["run_in_background"] = run_in_background
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    if agent_id is not None:
        payload["agent_id"] = agent_id
    return payload


def _rewritten(out):
    return out.get("hookSpecificOutput", {}).get("updatedInput")


@pytest.mark.parametrize("agent", PHILLIT_AGENTS)
@pytest.mark.parametrize("flag", [_ABSENT, True])
def test_forces_each_review_agent_to_the_foreground(agent, flag):
    out = _run(_dispatch(agent, flag))
    assert _rewritten(out) == {"subagent_type": agent, "description": "d",
                               "prompt": "p", "run_in_background": False}
    # A rewrite, not a permission decision: the user's rules still apply.
    assert "permissionDecision" not in out["hookSpecificOutput"]
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_keeps_every_other_field_of_the_call():
    payload = _dispatch("phillit:synthesis-writer")
    payload["tool_input"].update({"model": "sonnet", "isolation": "worktree"})
    new = _rewritten(_run(payload))
    assert new == {**payload["tool_input"], "run_in_background": False}


def test_tolerates_plugin_namespace_prefix():
    assert _rewritten(_run(_dispatch("phillit:domain-literature-researcher")))


def test_covers_the_task_spelling_of_the_dispatch_tool():
    assert _rewritten(_run(_dispatch("synthesis-writer", tool_name="Task")))


def test_leaves_other_tools_alone():
    assert _run(_dispatch("synthesis-writer", tool_name="Bash")) == {}


@pytest.mark.parametrize("name", ["other:synthesis-writer", "a:phillit:synthesis-writer",
                                  "phillit:general-purpose"])
def test_leaves_same_named_agents_of_other_plugins_alone(name):
    assert _run(_dispatch(name)) == {}


def test_overriding_an_explicit_true_says_so():
    out = _run(_dispatch("synthesis-writer", True))
    assert _rewritten(out)["run_in_background"] is False
    assert "synthesis-writer" in out["systemMessage"]
    assert "systemMessage" not in _run(_dispatch("synthesis-writer"))


def test_a_payload_without_tool_input_passes_through():
    assert _run({"tool_name": "Agent"}) == {}


def test_leaves_an_explicit_foreground_dispatch_alone():
    assert _run(_dispatch("domain-literature-researcher", False)) == {}


def test_leaves_non_phillit_agents_alone():
    assert _run(_dispatch("general-purpose")) == {}
    assert _run(_dispatch("general-purpose", True)) == {}


def test_leaves_calls_inside_a_subagent_alone():
    assert _run(_dispatch("domain-literature-researcher", agent_id="abc123")) == {}


@pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "on"])
def test_no_op_when_background_tasks_are_disabled(value):
    out = _run(_dispatch("synthesis-writer"),
               {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": value})
    assert out == {}


def test_a_falsy_disable_value_still_rewrites():
    out = _run(_dispatch("synthesis-writer"),
               {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "0"})
    assert _rewritten(out)


@pytest.mark.parametrize("stdin", ["not json at all", "", "[1, 2]",
                                   '{"tool_input": "x"}'])
def test_unreadable_input_fails_open_and_says_so(stdin):
    out = _run(stdin)
    assert "hookSpecificOutput" not in out
    assert "not forced to the foreground" in out["systemMessage"]
