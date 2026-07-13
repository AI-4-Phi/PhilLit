# tests/test_hooks_json.py
import json
from pathlib import Path

HOOKS = json.loads(
    (Path(__file__).parent.parent / "hooks" / "hooks.json").read_text(encoding="utf-8")
)["hooks"]


def _commands(event):
    return [h["command"] for entry in HOOKS.get(event, []) for h in entry["hooks"]]


def test_sessionstart_runs_bootstrap_only():
    cmds = _commands("SessionStart")
    assert any("setup-environment.sh" in c for c in cmds)
    assert not any("check-updates" in c for c in cmds)  # removed


def test_intrusive_hooks_are_gated_and_use_wrapper():
    pre = _commands("PreToolUse") + _commands("PostToolUse")
    bib = [c for c in pre if "validate_bib_write.py" in c]
    bash = [c for c in pre if "block_background_bash.py" in c]
    assert bib and bash
    for c in bib + bash:
        assert "--if-active" in c
        assert "phillit-run" in c
        assert "${CLAUDE_PLUGIN_ROOT}" in c


def test_plumbing_hooks_fail_open_with_visible_message():
    # Gate-failure policy (CLAUDE.md): plumbing gates fail OPEN and loud. uv
    # exits 2 when the cold venv build fails (e.g. offline); propagated from a
    # PreToolUse hook, exit 2 hard-blocks the tool call and bricks the
    # workspace. Every wrapper-routed command needs an || echo fallback that
    # surfaces the failure as a systemMessage instead.
    for c in _commands("PreToolUse") + _commands("PostToolUse"):
        if "phillit-run" in c:
            assert "|| echo" in c, f"no fail-open fallback: {c}"
            assert "systemMessage" in c, f"fallback is silent: {c}"


def test_subagentstop_routes_to_bib_hook():
    # No matcher: the hook fires for all SubagentStop events and self-scopes internally
    # (.phillit marker + tolerant agent_type + .active-review). Robust to plugin namespacing.
    entries = HOOKS["SubagentStop"]
    assert "matcher" not in entries[0]
    assert "subagent_stop_bib.sh" in entries[0]["hooks"][0]["command"]
