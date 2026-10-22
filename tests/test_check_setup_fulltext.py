"""check_setup reports the optional Zotero / PDF-folder settings, informationally."""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "skills/philosophy-research/scripts"))
import check_setup  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("PHILLIT_ZOTERO", raising=False)
    monkeypatch.delenv("PHILLIT_PDF_DIR", raising=False)


def _fake_session(monkeypatch, outcome):
    calls = []

    class S:
        trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kw):
            calls.append((url, kw, self.trust_env))
            if isinstance(outcome, BaseException):
                raise outcome

            class R:
                status_code = outcome

            return R()

    monkeypatch.setattr(requests, "Session", S)
    return calls


def test_nothing_set_is_informational_and_makes_no_request(monkeypatch):
    calls = _fake_session(monkeypatch, 200)
    out = check_setup.check_fulltext_sources()
    assert out["zotero"]["enabled"] is False and out["pdf_folder"]["set"] is False
    assert calls == []


def test_zotero_enabled_and_reachable(monkeypatch):
    monkeypatch.setenv("PHILLIT_ZOTERO", "on")
    calls = _fake_session(monkeypatch, 200)
    out = check_setup.check_fulltext_sources()
    assert out["zotero"]["enabled"] is True and out["zotero"]["reachable"] is True
    url, kw, trust_env = calls[0]
    assert url == check_setup.ZOTERO_PROBE_URL and kw["allow_redirects"] is False and trust_env is False


def test_zotero_enabled_but_unreachable_is_not_a_failure(monkeypatch):
    monkeypatch.setenv("PHILLIT_ZOTERO", "on")
    _fake_session(monkeypatch, requests.ConnectionError("refused"))
    assert check_setup.check_fulltext_sources()["zotero"]["reachable"] is False
    _fake_session(monkeypatch, 403)
    assert check_setup.check_fulltext_sources()["zotero"]["reachable"] is False


def test_zotero_probe_skipped_with_skip_api(monkeypatch):
    monkeypatch.setenv("PHILLIT_ZOTERO", "on")
    calls = _fake_session(monkeypatch, 200)
    out = check_setup.check_fulltext_sources(probe=False)
    assert out["zotero"]["enabled"] is True and out["zotero"]["reachable"] is None
    assert calls == []


def test_pdf_folder_set_and_exists_or_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PHILLIT_PDF_DIR", str(tmp_path))
    out = check_setup.check_fulltext_sources(probe=False)["pdf_folder"]
    assert out["set"] is True and out["exists"] is True
    monkeypatch.setenv("PHILLIT_PDF_DIR", str(tmp_path / "gone"))
    out = check_setup.check_fulltext_sources(probe=False)["pdf_folder"]
    assert out["set"] is True and out["exists"] is False


def test_print_results_shows_info_lines_and_never_fails(capsys):
    full = {"zotero": {"enabled": True, "reachable": False, "message": "Enabled, but Zotero is not answering"},
            "pdf_folder": {"set": True, "exists": False, "message": "Set, but the folder was not found"}}
    env = {"BRAVE_API_KEY": {"set": True, "required": True, "description": "", "preview": None}}
    ok = check_setup.print_results(env, {}, {}, fulltext_results=full)
    out = capsys.readouterr().out
    assert ok is True
    assert "[INFO] Zotero: Enabled, but Zotero is not answering" in out
    assert "[INFO] PDF folder: Set, but the folder was not found" in out
    assert "FAIL" not in out


def test_json_status_ignores_fulltext_sources():
    status, _ = check_setup._json_status(
        {"BRAVE_API_KEY": {"set": True, "required": True}}, {}, {"brave": {"reachable": True}, "crossref": {"reachable": True}})
    assert status == "ok"
