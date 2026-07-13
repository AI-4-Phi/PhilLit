"""Pins the workspace-.env loading contract.

Review finding (2026-07-13): installed plugins never loaded the workspace .env.
Bare load_dotenv() resolves via find_dotenv(), which walks up from the SCRIPT's
directory — in an installed plugin that is the plugin cache, never the user's
workspace. Every bundled script must therefore call
load_dotenv(find_dotenv(usecwd=True), override=True), which walks up from the
cwd (the workspace; bin/phillit-run does not chdir).
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _bundled_python_files():
    return [
        p
        for d in ("skills", "hooks")
        for p in sorted((REPO_ROOT / d).rglob("*.py"))
    ]


def test_all_load_dotenv_calls_use_usecwd():
    offenders = []
    for path in _bundled_python_files():
        for i, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if "load_dotenv(" not in stripped or stripped.startswith("#"):
                continue
            if "find_dotenv(usecwd=True)" not in stripped:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{i}: {stripped}")
    assert not offenders, (
        "load_dotenv without find_dotenv(usecwd=True) never finds the workspace "
        ".env in installed-plugin runs:\n" + "\n".join(offenders)
    )


def test_usecwd_idiom_loads_workspace_env_from_foreign_script_dir(tmp_path):
    # Reproduce the installed-plugin geometry: the script file lives OUTSIDE
    # the workspace (like the plugin cache); cwd is the workspace with the .env.
    cache = tmp_path / "plugincache"
    cache.mkdir()
    script = cache / "probe.py"
    script.write_text(
        "import os\n"
        "from dotenv import find_dotenv, load_dotenv\n"
        "load_dotenv(find_dotenv(usecwd=True), override=True)\n"
        "print(os.environ.get('PHILLIT_DOTENV_SENTINEL', 'MISSING'))\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".env").write_text(
        "PHILLIT_DOTENV_SENTINEL=from-workspace\n", encoding="utf-8"
    )

    # override=True: the .env value must beat the shell environment.
    env = {**os.environ, "PHILLIT_DOTENV_SENTINEL": "from-shell"}
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "from-workspace"
