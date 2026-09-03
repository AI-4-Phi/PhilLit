"""The four scripts that import bib_identity across `hooks/` must do so
when executed directly (as the wrapper does), not only inside one pytest
process where an earlier import can satisfy them from sys.modules."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"


@pytest.mark.parametrize("script,expr,expected", [
    ("resolve_context.py", "m.first_author_surname('{A and B} and C, D')", "{A and B}"),
    ("check_evidence.py", "m.rc_surname('{A and B} and C, D')", "{A and B}"),
    ("year_suffix.py", "m.first_surname_raw({'author': '{A and B} and C, D'})", "{A and B}"),
])
def test_script_imports_bib_identity_when_loaded_by_path(tmp_path, script, expr, expected):
    code = (
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('m', {str(SCRIPTS / script)!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        f"print({expr})"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True,
                       text=True, env={**os.environ, "PYTHONPATH": ""})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == expected


def test_enrich_imports_bib_identity_when_loaded_by_path(tmp_path):
    code = (
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('m', {str(SCRIPTS / 'enrich_bibliography.py')!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "print(m.get_author_last_name({'fields': {'author': '{A and B} and C, D'}}))"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True,
                       text=True, env={**os.environ, "PYTHONPATH": ""})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "A and B"
