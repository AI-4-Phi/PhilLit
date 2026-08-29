"""A1: verify_paper.py --output owns its file so shell redirection cannot corrupt it."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "skills/philosophy-research/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_paper  # noqa: E402

PAYLOAD = {"status": "success", "source": "crossref", "results": [{"doi": "10.1/x"}], "count": 1}


def test_write_output_file_atomic_success(tmp_path):
    target = tmp_path / "verify_x.json"
    assert verify_paper.write_output_file(PAYLOAD, str(target)) is True
    assert json.loads(target.read_text(encoding="utf-8")) == PAYLOAD
    # no leftover tmp files in the dir
    assert [p.name for p in tmp_path.iterdir()] == ["verify_x.json"]


def test_write_output_file_returns_false_on_bad_path(tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    # parent is a regular file -> makedirs/mkstemp fails
    assert verify_paper.write_output_file(PAYLOAD, str(blocker / "sub" / "v.json")) is False


def test_emit_writes_file_and_exits_zero(tmp_path, monkeypatch, capsys):
    target = tmp_path / "out.json"
    monkeypatch.setattr(verify_paper, "_OUTPUT_PATH", str(target))
    with pytest.raises(SystemExit) as exc:
        verify_paper._emit(PAYLOAD, 0)
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out) == PAYLOAD  # stdout still prints
    assert json.loads(target.read_text(encoding="utf-8")) == PAYLOAD


def test_emit_exits_4_when_output_write_fails(tmp_path, monkeypatch, capsys):
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(verify_paper, "_OUTPUT_PATH", str(blocker / "sub" / "v.json"))
    with pytest.raises(SystemExit) as exc:
        verify_paper._emit(PAYLOAD, 0)
    assert exc.value.code == 4
    out = capsys.readouterr()
    assert json.loads(out.out) == PAYLOAD          # stdout JSON still printed
    assert "Failed to write" in out.err            # stderr warning


def test_emit_no_output_path_is_stdout_only(monkeypatch, capsys):
    monkeypatch.setattr(verify_paper, "_OUTPUT_PATH", None)
    with pytest.raises(SystemExit) as exc:
        verify_paper._emit(PAYLOAD, 1)
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out) == PAYLOAD


@pytest.mark.parametrize("fn,args,expected_status,expected_code", [
    ("output_success", ({"doi": "10.1/x"}, {"verified": True, "doi": "10.1/x"}), "success", 0),
    ("output_not_found", ({"doi": "10.1/x"}, "no match"), "error", 1),
    ("output_error", ({"doi": "10.1/x"}, "api_error", "boom", 3), "error", 3),
])
def test_output_helpers_honor_output(tmp_path, monkeypatch, capsys, fn, args,
                                     expected_status, expected_code):
    """All THREE output paths write --output AND still print to stdout, keeping
    their normal exit codes when the write succeeds."""
    target = tmp_path / "out.json"
    monkeypatch.setattr(verify_paper, "_OUTPUT_PATH", str(target))
    with pytest.raises(SystemExit) as exc:
        getattr(verify_paper, fn)(*args)
    assert exc.value.code == expected_code
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["status"] == expected_status
    assert json.loads(capsys.readouterr().out)["status"] == expected_status  # stdout too


def test_cli_exit_4_overrides_normal_exit_on_unwritable_output(tmp_path):
    """CLI-level: with no --doi/--title the script takes its config-error path
    (normal exit 2); an unwritable --output makes _emit's write fail and exit 4
    OVERRIDES the config-error code. This path touches no network."""
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    bad_output = str(blocker / "sub" / "v.json")  # parent is a file -> write fails
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "verify_paper.py"), "--output", bad_output],
        capture_output=True, text=True,
    )
    assert proc.returncode == 4                          # 4 overrides the normal exit 2
    assert json.loads(proc.stdout)["status"] == "error"  # JSON still printed to stdout
    assert "Failed to write" in proc.stderr
