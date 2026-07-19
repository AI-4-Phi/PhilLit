"""Item 13 D3: optional CORE is skipped/non-fatal when no key is configured."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "skills/philosophy-research/scripts"))
import check_setup  # noqa: E402
import get_abstract  # noqa: E402

_SCRIPTS = Path(__file__).parent.parent / "skills" / "philosophy-research" / "scripts"


# --- check_setup._json_status ------------------------------------------------

def test_json_status_optional_core_failure_is_ok():
    env = {
        "BRAVE_API_KEY": {"set": True, "required": True},
        "CROSSREF_MAILTO": {"set": True, "required": True},
    }
    deps = {"requests": {"installed": True}}
    apis = {
        "brave": {"reachable": True},
        "crossref": {"reachable": True},
        "core": {"reachable": None, "skipped_no_key": True},
        "arxiv": {"reachable": False},
    }
    status, optional_failures = check_setup._json_status(env, deps, apis)
    assert status == "ok"
    assert "core" not in optional_failures     # skipped, not a failure
    assert "arxiv" in optional_failures         # optional + unreachable


def test_json_status_required_api_failure_is_error():
    env = {"BRAVE_API_KEY": {"set": True, "required": True}}
    deps = {"requests": {"installed": True}}
    apis = {"brave": {"reachable": False}, "crossref": {"reachable": True}}
    status, _ = check_setup._json_status(env, deps, apis)
    assert status == "error"


def test_json_status_missing_brave_record_is_error():
    # A required API whose record is entirely ABSENT must fail, not silently
    # pass through an `if a in api_results` skip (GPT-SF10).
    env = {"BRAVE_API_KEY": {"set": True, "required": True}}
    deps = {"requests": {"installed": True}}
    apis = {"crossref": {"reachable": True}}   # brave record missing
    status, _ = check_setup._json_status(env, deps, apis)
    assert status == "error"


def test_json_status_missing_crossref_record_is_error():
    env = {"BRAVE_API_KEY": {"set": True, "required": True}}
    deps = {"requests": {"installed": True}}
    apis = {"brave": {"reachable": True}}      # crossref record missing
    status, _ = check_setup._json_status(env, deps, apis)
    assert status == "error"


def test_json_status_empty_api_results_is_error():
    env = {"BRAVE_API_KEY": {"set": True, "required": True}}
    deps = {"requests": {"installed": True}}
    status, _ = check_setup._json_status(env, deps, {})
    assert status == "error"


def test_check_core_connectivity_skipped_without_key(monkeypatch):
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    import requests as _requests
    def _boom(*a, **k):
        raise AssertionError("CORE must not be probed without a key")
    monkeypatch.setattr(_requests, "get", _boom)
    result = check_setup.check_core_connectivity()
    assert result["skipped_no_key"] is True
    assert result["reachable"] is None


# --- get_abstract.resolve_abstract -------------------------------------------

def test_resolve_abstract_skips_core_without_key(monkeypatch):
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    def _boom(*a, **k):
        raise AssertionError("CORE must not be called without a key")
    monkeypatch.setattr(get_abstract, "get_abstract_from_core", _boom)
    assert get_abstract.resolve_abstract(title="A Book", author="Doe") == (None, None)


def test_resolve_abstract_uses_core_with_key(monkeypatch):
    monkeypatch.setenv("CORE_API_KEY", "test-key")
    monkeypatch.setattr(get_abstract, "get_abstract_from_core", lambda **k: "A resolved abstract.")
    abstract, source = get_abstract.resolve_abstract(
        title="A Book", author="Doe", core_api_key="test-key"
    )
    assert (abstract, source) == ("A resolved abstract.", "core")


def test_resolve_abstract_uses_core_when_key_passed_but_env_unset(monkeypatch):
    # The CORE gate must key on the RESOLVED core_api_key param, not the raw
    # environment: an explicit --core-api-key with CORE_API_KEY unset in the
    # environment must still try CORE (mirrors search_core.py's args.api_key gate).
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    monkeypatch.setattr(get_abstract, "get_abstract_from_core", lambda **k: "A resolved abstract.")
    abstract, source = get_abstract.resolve_abstract(
        title="A Book", author="Doe", core_api_key="explicit-key"
    )
    assert (abstract, source) == ("A resolved abstract.", "core")


# --- search_core.py CLI early skip-exit --------------------------------------

def test_search_core_skips_without_key(tmp_path):
    script = _SCRIPTS / "search_core.py"
    env = dict(os.environ)
    env.pop("CORE_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, str(script), "some query"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"status": "skipped", "reason": "no CORE_API_KEY"}
