import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "hooks" / "setup-environment.sh"


def _run(tmp_path, *, active: bool, with_uv: bool):
    proj = tmp_path / "proj"
    proj.mkdir()
    if active:
        (proj / ".phillit").mkdir()
    env_file = tmp_path / "envfile.sh"
    env_file.write_text("", encoding="utf-8")
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()

    env = {
        "HOME": str(tmp_path),
        "CLAUDE_ENV_FILE": str(env_file),
        "CLAUDE_PROJECT_DIR": str(proj),
        "CLAUDE_PLUGIN_ROOT": str(plugin_root),
        "PHILLIT_BREW_DIRS": "",  # disable homebrew fallback for the no-uv case
    }
    if with_uv:
        fakebin = tmp_path / "fakebin"
        fakebin.mkdir()
        (fakebin / "uv").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        (fakebin / "uv").chmod(0o755)
        env["PATH"] = f"{fakebin}:{os.environ['PATH']}"
    else:
        env["PATH"] = "/usr/bin:/bin"

    r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)
    return r, env_file.read_text(encoding="utf-8")


def test_bridges_root_and_uv_when_active(tmp_path):
    r, written = _run(tmp_path, active=True, with_uv=True)
    assert r.returncode == 0, r.stderr
    assert "export PHILLIT_ROOT=" in written
    assert "export PHILLIT_UV=" in written
    assert "export PHILLIT_ACTIVE=1" in written


def test_no_active_flag_outside_workspace(tmp_path):
    r, written = _run(tmp_path, active=False, with_uv=True)
    assert r.returncode == 0
    assert "export PHILLIT_ROOT=" in written      # harmless bridge still set
    assert "PHILLIT_ACTIVE" not in written


def test_root_bridged_even_without_uv_outside_workspace(tmp_path):
    # PHILLIT_ROOT must bridge regardless of uv (so /phillit:setup can locate the wrapper),
    # but PHILLIT_UV must not, and unrelated projects get no nag on stderr.
    r, written = _run(tmp_path, active=False, with_uv=False)
    assert r.returncode == 0
    assert "export PHILLIT_ROOT=" in written
    assert "PHILLIT_UV" not in written
    assert "uv" not in r.stderr.lower()


def test_missing_uv_warns_inside_workspace_but_still_bridges_root(tmp_path):
    r, written = _run(tmp_path, active=True, with_uv=False)
    assert r.returncode == 0
    assert "export PHILLIT_ROOT=" in written       # setup can still locate the wrapper
    assert "uv" in r.stderr.lower()
