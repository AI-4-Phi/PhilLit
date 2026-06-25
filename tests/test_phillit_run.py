import os
import subprocess
from pathlib import Path

WRAPPER = Path(__file__).parent.parent / "bin" / "phillit-run"


def _fake_uv(tmp_path):
    """A stub `uv` that prints how it was called instead of running anything."""
    d = tmp_path / "fakebin"
    d.mkdir()
    fake = d / "uv"
    fake.write_text(
        '#!/usr/bin/env bash\n'
        'echo "UVPE=$UV_PROJECT_ENVIRONMENT"\n'
        'echo "ARGS=$*"\n',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def test_wrapper_builds_locked_project_command(tmp_path):
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    (root / "skills").mkdir()
    (root / "bin" / "phillit-run").write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "skills" / "x.py").write_text("print('hi')", encoding="utf-8")
    fake = _fake_uv(tmp_path)

    result = subprocess.run(
        ["bash", str(root / "bin" / "phillit-run"), "skills/x.py", "hello", "world"],
        capture_output=True, text=True,
        cwd=str(tmp_path),  # foreign cwd
        env={**os.environ, "PHILLIT_UV": str(fake), "HOME": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    args_line = next(l for l in result.stdout.splitlines() if l.startswith("ARGS="))
    uvpe_line = next(l for l in result.stdout.splitlines() if l.startswith("UVPE="))
    # Assert the CONTRACT, not the literal root (macOS /var vs /private/var symlink skew):
    # locked+project flags, script path = <project>/skills/x.py, trailing args preserved.
    assert args_line.startswith("ARGS=run --locked --no-dev --project")
    assert args_line.endswith("/skills/x.py hello world")
    tail = args_line[len("ARGS=run --locked --no-dev --project "):].split(" ")
    project = tail[0]
    assert tail[1] == f"{project}/skills/x.py"
    # HOME is used verbatim by the wrapper, so this prefix is stable.
    assert uvpe_line.startswith(f"UVPE={tmp_path}/.venvs/phillit-plugin-")


def test_if_active_noops_without_marker(tmp_path):
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    (root / "hooks").mkdir()
    (root / "bin" / "phillit-run").write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "hooks" / "h.py").write_text("print('ran')", encoding="utf-8")
    _fake_uv(tmp_path)
    proj = tmp_path / "someproject"
    proj.mkdir()

    result = subprocess.run(
        ["bash", str(root / "bin" / "phillit-run"), "--if-active", "hooks/h.py"],
        capture_output=True, text=True,
        env={**os.environ, "PHILLIT_UV": str(tmp_path / "fakebin" / "uv"), "HOME": str(tmp_path),
             "CLAUDE_PROJECT_DIR": str(proj)},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""  # no uv invocation


def test_if_active_runs_with_marker(tmp_path):
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    (root / "hooks").mkdir()
    (root / "bin" / "phillit-run").write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "hooks" / "h.py").write_text("print('ran')", encoding="utf-8")
    _fake_uv(tmp_path)
    proj = tmp_path / "workspace"
    (proj / ".phillit").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(root / "bin" / "phillit-run"), "--if-active", "hooks/h.py"],
        capture_output=True, text=True,
        env={**os.environ, "PHILLIT_UV": str(tmp_path / "fakebin" / "uv"), "HOME": str(tmp_path),
             "CLAUDE_PROJECT_DIR": str(proj)},
    )
    assert result.returncode == 0
    assert "ARGS=run --locked --no-dev --project" in result.stdout


def test_wrapper_forwards_stdin_to_script(tmp_path):
    # The hook chain depends on PreToolUse/PostToolUse JSON reaching the Python hook
    # through the wrapper. Stub uv with one that drops the `run --locked --project <ROOT>`
    # prefix and execs the script, verifying the wrapper preserves stdin (fd 0).
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    (root / "skills").mkdir()
    (root / "bin" / "phillit-run").write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "skills" / "cat.py").write_text(
        "import sys; sys.stdout.write('GOT:' + sys.stdin.read())", encoding="utf-8")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "uv").write_text(
        "#!/usr/bin/env bash\nshift 5  # drop: run --locked --no-dev --project <ROOT>\nexec python3 \"$@\"\n",
        encoding="utf-8")
    (fakebin / "uv").chmod(0o755)

    result = subprocess.run(
        ["bash", str(root / "bin" / "phillit-run"), "skills/cat.py"],
        input="PING", capture_output=True, text=True,
        env={**os.environ, "PHILLIT_UV": str(fakebin / "uv"), "HOME": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    assert "GOT:PING" in result.stdout
