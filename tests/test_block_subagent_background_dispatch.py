"""Tests for hooks/block_subagent_background_dispatch.py — the PreToolUse gate
that blocks background dispatch of PhilLit review subagents at the orchestrator.

The gate must DENY only when all three hold:
  - the call is at the orchestrator (no ``agent_id`` in the payload),
  - ``tool_input.run_in_background`` is exactly ``True``, and
  - ``tool_input.subagent_type`` (namespace-stripped) is one of the four
    review agents.
Everything else — foreground dispatch, omitted flag, non-PhilLit agents,
calls made inside a subagent, unparseable input — is allowed through ({}).
"""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "block_subagent_background_dispatch.py"

PHILLIT_AGENTS = [
    "literature-review-planner",
    "domain-literature-researcher",
    "synthesis-planner",
    "synthesis-writer",
]


def _run(payload):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _is_deny(out):
    return out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def _dispatch(subagent_type, run_in_background=True, agent_id=None):
    payload = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": subagent_type,
            "run_in_background": run_in_background,
            "description": "d",
            "prompt": "p",
        },
    }
    if agent_id is not None:
        payload["agent_id"] = agent_id
    return payload


def test_blocks_background_dispatch_of_each_review_agent():
    for agent in PHILLIT_AGENTS:
        out = _run(_dispatch(agent))
        assert _is_deny(out), f"{agent} background dispatch should be denied"
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert agent in reason
        assert "run_in_background: false" in reason


def test_tolerates_plugin_namespace_prefix():
    out = _run(_dispatch("phillit:domain-literature-researcher"))
    assert _is_deny(out)


def test_allows_foreground_dispatch():
    out = _run(_dispatch("domain-literature-researcher", run_in_background=False))
    assert out == {}


def test_allows_when_run_in_background_omitted():
    # Field absent entirely -> not our concern (the wording fix mandates an
    # explicit false; the fast_gate needle also misses when it is absent).
    payload = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "synthesis-writer", "prompt": "p"},
    }
    assert _run(payload) == {}


def test_allows_background_dispatch_of_non_phillit_agent():
    out = _run(_dispatch("general-purpose"))
    assert out == {}


def test_allows_when_called_inside_a_subagent():
    # agent_id present => not the orchestrator; scope is orchestrator-only,
    # mirroring block_background_bash.py's inverse (subagent-only) scope.
    out = _run(_dispatch("domain-literature-researcher", agent_id="abc123"))
    assert out == {}


def test_allows_unparseable_stdin():
    assert _run("not json at all") == {}


def test_allows_empty_stdin():
    assert _run("") == {}
