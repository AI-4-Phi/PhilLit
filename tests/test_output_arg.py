"""
Tests for the shared `--output` mechanism in output.py.

Every search/fetch script routes its JSON through output.py's
output_success/output_partial/output_error. Once a script calls
set_output_path(args.output), those helpers write the JSON to the file
atomically (in addition to stdout), so a researcher never needs to redirect
and a stray `2>&1` can no longer corrupt the JSON file.
"""

import argparse
import json
from pathlib import Path

import pytest

import output


@pytest.fixture(autouse=True)
def reset_output_path():
    """The _OUTPUT_PATH global persists across tests -- reset it each time."""
    output.set_output_path(None)
    yield
    output.set_output_path(None)


class TestAddOutputArg:
    def test_adds_output_argument_defaulting_to_none(self):
        parser = argparse.ArgumentParser()
        output.add_output_arg(parser)
        args = parser.parse_args([])
        assert args.output is None

    def test_output_argument_captures_path(self):
        parser = argparse.ArgumentParser()
        output.add_output_arg(parser)
        args = parser.parse_args(["--output", "some/path.json"])
        assert args.output == "some/path.json"


class TestStdoutOnlyByDefault:
    def test_no_output_path_writes_no_file(self, tmp_path, capsys):
        # Default: stdout only, no file created anywhere.
        with pytest.raises(SystemExit) as exc:
            output.output_success("src", "q", [{"title": "T"}])
        assert exc.value.code == 0
        captured = json.loads(capsys.readouterr().out)
        assert captured["status"] == "success"
        assert captured["count"] == 1
        # No stray files in tmp_path
        assert list(tmp_path.iterdir()) == []


class TestFileWrite:
    def test_success_writes_valid_json_file(self, tmp_path, capsys):
        target = tmp_path / "results.json"
        output.set_output_path(str(target))
        with pytest.raises(SystemExit) as exc:
            output.output_success("src", "query", [{"title": "A"}, {"title": "B"}])
        assert exc.value.code == 0
        # File exists and is clean, valid JSON (no log-line pollution)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["status"] == "success"
        assert data["count"] == 2
        # stdout still carries the JSON (upstream-compatible)
        assert json.loads(capsys.readouterr().out)["count"] == 2

    def test_creates_parent_directories(self, tmp_path):
        target = tmp_path / "intermediate_files" / "json" / "s2_results.json"
        output.set_output_path(str(target))
        with pytest.raises(SystemExit):
            output.output_success("src", "query", [])
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8"))["count"] == 0

    def test_write_is_atomic_no_tmp_left(self, tmp_path):
        target = tmp_path / "results.json"
        output.set_output_path(str(target))
        with pytest.raises(SystemExit):
            output.output_success("src", "query", [{"title": "A"}])
        leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert leftovers == []

    def test_error_output_also_writes_file_and_keeps_exit_code(self, tmp_path):
        target = tmp_path / "err.json"
        output.set_output_path(str(target))
        with pytest.raises(SystemExit) as exc:
            output.output_error("src", "q", "api_error", "boom", exit_code=3)
        assert exc.value.code == 3
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["status"] == "error"
        assert data["errors"][0]["type"] == "api_error"

    def test_partial_output_writes_file(self, tmp_path):
        target = tmp_path / "partial.json"
        output.set_output_path(str(target))
        with pytest.raises(SystemExit) as exc:
            output.output_partial("src", "q", [{"title": "A"}], [output.make_error("rate_limit", "slow")], "partial")
        assert exc.value.code == 0
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["status"] == "partial"
        assert data["warning"] == "partial"


class TestWriteFailure:
    def test_failed_write_exits_4(self, tmp_path, capsys):
        # A path whose parent is an existing *file* cannot be created as a dir.
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("x", encoding="utf-8")
        target = blocker / "results.json"
        output.set_output_path(str(target))
        with pytest.raises(SystemExit) as exc:
            output.output_success("src", "query", [{"title": "A"}])
        # JSON still on stdout, but exit code signals the write failure
        assert exc.value.code == 4
        assert json.loads(capsys.readouterr().out)["count"] == 1
