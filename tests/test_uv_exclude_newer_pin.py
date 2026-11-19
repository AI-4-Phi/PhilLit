"""The pyproject exclude-newer pin must exist and match the lock (PL-41).

A user-level or environment exclude-newer otherwise changes uv's resolution
options, and `uv run --locked` in bin/phillit-run refuses the lock.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _pin(text: str, table: str):
    m = re.search(rf"^\[{re.escape(table)}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    assert m, f"no [{table}] table"
    v = re.search(r'^exclude-newer\s*=\s*"([^"]+)"', m.group(1), re.M)
    assert v, f"no exclude-newer in [{table}]"
    return v.group(1)


def test_pyproject_pin_matches_lock():
    pin = _pin((ROOT / "pyproject.toml").read_text(encoding="utf-8"), "tool.uv")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", pin), "use a fixed RFC 3339 date, not a span"
    assert _pin((ROOT / "uv.lock").read_text(encoding="utf-8"), "options") == pin


def test_wrapper_drops_environment_exclude_newer(tmp_path):
    # Run the real wrapper against a fake uv that records the env it receives.
    fake = tmp_path / "uv"
    fake.write_text("#!/bin/sh\nenv > \"$PROBE_OUT\"\nprintf '%s\\n' \"$@\" > \"$PROBE_OUT.args\"\n",
                    encoding="utf-8")
    fake.chmod(0o755)
    out = tmp_path / "env.txt"
    env = dict(os.environ, PHILLIT_UV=str(fake), PROBE_OUT=str(out),
               UV_EXCLUDE_NEWER="3 days", UV_EXCLUDE_NEWER_PACKAGE="x=3 days")
    subprocess.run(["bash", str(ROOT / "bin" / "phillit-run"), "x.py"], env=env, check=True)
    seen = out.read_text(encoding="utf-8").splitlines()
    assert not any(line.startswith("UV_EXCLUDE_NEWER") for line in seen)
    assert any(line.startswith("UV_PROJECT_ENVIRONMENT=") for line in seen)
    # The pin rides on the command line, which outranks every config source.
    pin = _pin((ROOT / "pyproject.toml").read_text(encoding="utf-8"), "tool.uv")
    args = Path(str(out) + ".args").read_text(encoding="utf-8").splitlines()
    assert args[:2] == ["run", "--locked"]
    i = args.index("--exclude-newer")
    assert args[i + 1] == pin
    assert args[-1].endswith("x.py") and args.index("--project") < i


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_wrapper_runs_under_a_uv_config_file_cutoff(tmp_path):
    cfg = tmp_path / "uv.toml"
    cfg.write_text('exclude-newer = "7 days"\n', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("UV_")}
    env.pop("PHILLIT_UV", None)
    env["UV_CONFIG_FILE"] = str(cfg)
    r = subprocess.run(["bash", str(ROOT / "bin" / "phillit-run"),
                        "skills/literature-review/scripts/workdir.py", "--help"],
                       env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_lock_stays_valid_under_a_user_level_relative_cutoff(tmp_path):
    # The reported failure: a user uv.toml with exclude-newer = "7 days".
    (tmp_path / "uv").mkdir()
    (tmp_path / "uv" / "uv.toml").write_text('exclude-newer = "7 days"\n', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("UV_")}
    env["XDG_CONFIG_HOME"] = str(tmp_path)
    r = subprocess.run(["uv", "lock", "--check", "--offline", "--project", str(ROOT)],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
