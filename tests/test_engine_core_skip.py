"""Optional CORE is skipped/non-fatal when no key is configured."""

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
    # pass through an `if a in api_results` skip.
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


# --- check_setup OpenAlex probe: key transport + keyed reporting -------------

def test_openalex_probe_sends_key_as_bearer_header(monkeypatch):
    from unittest.mock import MagicMock, patch
    monkeypatch.setenv("OPENALEX_API_KEY", "sekret")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    mock_response = MagicMock(status_code=200, headers={}, text="")
    # check_api_connectivity does `import requests` inside its body, so
    # patching the module attribute globally is the working form (same
    # idiom the other test files use for the scripts' plain `import requests`).
    with patch("requests.get", return_value=mock_response) as mock_get:
        results = check_setup.check_api_connectivity()
    openalex_calls = [c for c in mock_get.call_args_list
                      if "api.openalex.org" in c.args[0]]
    assert openalex_calls, "no request to api.openalex.org was made"
    assert openalex_calls[0].kwargs["headers"] == {"Authorization": "Bearer sekret"}
    assert "api_key" not in openalex_calls[0].kwargs["params"]
    assert "sekret" not in openalex_calls[0].args[0]
    assert results["openalex"]["api_key"] is True


def _openalex_message(monkeypatch, *, key, flag):
    from unittest.mock import MagicMock, patch
    if key is None:
        monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENALEX_API_KEY", key)
    if flag is None:
        monkeypatch.delenv("PHILLIT_VET_VENUES", raising=False)
    else:
        monkeypatch.setenv("PHILLIT_VET_VENUES", flag)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    mock_response = MagicMock(status_code=200, headers={}, text="")
    with patch("requests.get", return_value=mock_response):
        return check_setup.check_api_connectivity()["openalex"]["message"]


def test_vetting_conflict_notes_in_openalex_message(monkeypatch):
    # on + no key: the round-1 latency gap -- config-time feedback.
    msg = _openalex_message(monkeypatch, key=None, flag="1")
    assert "PHILLIT_VET_VENUES" in msg and "OPENALEX_API_KEY" in msg
    # unrecognized value: flagged regardless of the key.
    msg = _openalex_message(monkeypatch, key="sekret", flag="flase")
    assert "unrecognized" in msg
    # off + key: the SUPPORTED configuration -- no note, no noise.
    msg = _openalex_message(monkeypatch, key="sekret", flag="0")
    assert "PHILLIT_VET_VENUES" not in msg


def test_vetting_note_agrees_with_the_flag_parser(monkeypatch):
    """Drift pin for the token tuples check_setup duplicates from
    venue_vetting._vetting_mode: for every token the parser knows, the note
    behavior must match the parser's classification."""
    monkeypatch.syspath_prepend(str(Path(__file__).parent.parent
                           / "skills" / "literature-review" / "scripts"))
    import venue_vetting as vv
    assert check_setup._VET_ON_TOKENS == vv._ON_TOKENS
    assert check_setup._VET_OFF_TOKENS == vv._OFF_TOKENS
    for token in ("1", "true", "yes", "on"):
        for spelling in (token, token.upper(), f"  {token}  "):
            monkeypatch.setenv("PHILLIT_VET_VENUES", spelling)
            assert vv._vetting_mode() == "on"
            msg = _openalex_message(monkeypatch, key=None, flag=spelling)
            assert "OPENALEX_API_KEY" in msg, spelling
    for token in ("0", "false", "no", "off"):
        for spelling in (token, token.upper(), f"  {token}  "):
            monkeypatch.setenv("PHILLIT_VET_VENUES", spelling)
            assert vv._vetting_mode() == "off"
            msg = _openalex_message(monkeypatch, key="sekret", flag=spelling)
            assert "PHILLIT_VET_VENUES" not in msg, spelling


def test_openalex_probe_reports_unusable_key(monkeypatch):
    msg = _openalex_message(monkeypatch, key="se\tkret", flag=None)
    assert "outside printable ASCII" in msg
    assert "se\tkret" not in msg
