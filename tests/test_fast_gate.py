"""Tests for hooks/fast_gate.sh — the cheap shell pre-filter in front of the
per-call uv-backed gates (PreToolUse/PostToolUse).

The gate must:
- no-op (exit 0, no uv) outside a PhilLit workspace,
- no-op (exit 0, no uv) when stdin lacks the needle,
- pipe the captured stdin into the Python gate via phillit-run on a hit,
- propagate the wrapper's exit status so hooks.json's || echo fallback fires,
- fail open but LOUD on mis-wired arguments.
"""
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent


def _plugin_root(tmp_path):
    """Minimal plugin copy: fast_gate.sh + phillit-run + a stub gate script."""
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    (root / "hooks").mkdir()
    for rel in ("hooks/fast_gate.sh", "bin/phillit-run"):
        (root / rel).write_text((REPO / rel).read_text(encoding="utf-8"), encoding="utf-8")
    (root / "hooks" / "h.py").write_text("print('ran')", encoding="utf-8")
    return root


def _fake_uv(tmp_path):
    """A stub `uv` that prints how it was called instead of running anything."""
    d = tmp_path / "fakebin"
    d.mkdir()
    fake = d / "uv"
    fake.write_text(
        '#!/usr/bin/env bash\n'
        'echo "ARGS=$*"\n',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _run(root, args, env_extra, stdin=""):
    return subprocess.run(
        ["bash", str(root / "hooks" / "fast_gate.sh"), *args],
        input=stdin, capture_output=True, text=True,
        env={**os.environ, **env_extra},
    )


def test_noops_without_marker(tmp_path):
    root = _plugin_root(tmp_path)
    proj = tmp_path / "someproject"
    proj.mkdir()
    # Broken uv proves uv is never touched: a hit would fail loudly.
    result = _run(root, [".bib", "hooks/h.py"],
                  {"CLAUDE_PROJECT_DIR": str(proj), "PHILLIT_UV": "/nonexistent/uv",
                   "HOME": str(tmp_path)},
                  stdin='{"tool_input": {"file_path": "x.bib"}}')
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_noops_on_needle_miss(tmp_path):
    root = _plugin_root(tmp_path)
    proj = tmp_path / "workspace"
    (proj / ".phillit").mkdir(parents=True)
    result = _run(root, [".bib", "hooks/h.py"],
                  {"CLAUDE_PROJECT_DIR": str(proj), "PHILLIT_UV": "/nonexistent/uv",
                   "HOME": str(tmp_path)},
                  stdin='{"tool_input": {"file_path": "notes.md", "content": "plain text"}}')
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_invokes_gate_on_needle_hit(tmp_path):
    root = _plugin_root(tmp_path)
    fake = _fake_uv(tmp_path)
    proj = tmp_path / "workspace"
    (proj / ".phillit").mkdir(parents=True)
    result = _run(root, [".bib", "hooks/h.py"],
                  {"CLAUDE_PROJECT_DIR": str(proj), "PHILLIT_UV": str(fake),
                   "HOME": str(tmp_path)},
                  stdin='{"tool_input": {"file_path": "refs.bib"}}')
    assert result.returncode == 0, result.stderr
    assert "ARGS=run --locked --no-dev --project" in result.stdout
    assert result.stdout.rstrip().endswith("/hooks/h.py")


def test_forwards_stdin_to_gate(tmp_path):
    # The Python gates read the hook JSON from stdin; the pre-filter consumes
    # stdin for the needle test, so it must re-pipe the captured input.
    root = _plugin_root(tmp_path)
    (root / "hooks" / "h.py").write_text(
        "import sys; sys.stdout.write('GOT:' + sys.stdin.read())", encoding="utf-8")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "uv").write_text(
        "#!/usr/bin/env bash\nshift 5  # drop: run --locked --no-dev --project <ROOT>\nexec python3 \"$@\"\n",
        encoding="utf-8")
    (fakebin / "uv").chmod(0o755)
    proj = tmp_path / "workspace"
    (proj / ".phillit").mkdir(parents=True)
    payload = '{"tool_input": {"file_path": "refs.bib", "content": "@article{x,"}}'
    result = _run(root, [".bib", "hooks/h.py"],
                  {"CLAUDE_PROJECT_DIR": str(proj), "PHILLIT_UV": str(fakebin / "uv"),
                   "HOME": str(tmp_path)},
                  stdin=payload)
    assert result.returncode == 0, result.stderr
    assert f"GOT:{payload}" in result.stdout


def test_propagates_uv_failure_for_fail_open_fallback(tmp_path):
    # Gate-failure policy: plumbing fails open + loud. The nonzero exit must
    # reach hooks.json so its `|| echo systemMessage` fallback fires.
    root = _plugin_root(tmp_path)
    proj = tmp_path / "workspace"
    (proj / ".phillit").mkdir(parents=True)
    result = _run(root, [".bib", "hooks/h.py"],
                  {"CLAUDE_PROJECT_DIR": str(proj), "PHILLIT_UV": "/nonexistent/uv",
                   "HOME": str(tmp_path)},
                  stdin='{"tool_input": {"file_path": "refs.bib"}}')
    assert result.returncode != 0


def test_wrong_args_fail_open_loud(tmp_path):
    root = _plugin_root(tmp_path)
    proj = tmp_path / "workspace"
    (proj / ".phillit").mkdir(parents=True)
    result = _run(root, [".bib"],  # missing the script argument
                  {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)},
                  stdin='{"tool_input": {"file_path": "refs.bib"}}')
    assert result.returncode == 0
    assert "systemMessage" in result.stdout


def test_fast_gate_is_executable():
    assert os.access(REPO / "hooks" / "fast_gate.sh", os.X_OK)
