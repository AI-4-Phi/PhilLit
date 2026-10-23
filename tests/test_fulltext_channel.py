"""fulltext_channel.py: the file grammar of the service full-text channel."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

import fulltext as ft  # noqa: E402
import fulltext_channel as fc  # noqa: E402

IDENT = {"doi": "10.1234/jphil.2019.42", "title": "On Things", "surname": "Smith", "year": "2019"}


def _payload(i=0):
    return fc.identity_payload({**IDENT, "doi": f"10.1234/x.{i}"})


def _write_response(tmp_path, request_id, obj):
    (tmp_path / (request_id + fc.RESPONSE_SUFFIX)).write_text(
        json.dumps(obj), encoding="utf-8")


def _response(request_id, complete, outcomes=None):
    return {"schema": 1, "request_id": request_id, "complete": complete,
            "outcomes": outcomes or {}}


def test_request_id_shape():
    assert fc.REQUEST_ID_RE.match(fc.new_request_id("gaps"))
    assert fc.new_request_id("x") != fc.new_request_id("x")


def test_identity_payload_carries_the_canonical_key():
    assert fc.identity_payload(IDENT) == {
        "key": ft.canonical_identity(IDENT),
        "doi": "10.1234/jphil.2019.42", "title": "On Things",
        "surname": "Smith", "year": "2019"}
    assert fc.identity_payload(IDENT)["key"] == "doi:10.1234/jphil.2019.42"


def test_identity_payload_keeps_none():
    ident = {"doi": None, "title": "On Things", "surname": "Smith", "year": "2019"}
    payload = fc.identity_payload(ident)
    assert payload["doi"] is None and payload["key"].startswith("t:")


def test_identity_payload_refuses_a_long_field():
    with pytest.raises(ValueError, match="field_too_long"):
        fc.identity_payload({**IDENT, "title": "x" * 501})
    fc.identity_payload({**IDENT, "title": "x" * 500})


def test_write_request_is_atomic_ascii_and_capped(tmp_path):
    d = tmp_path / "nested" / "req"
    payload = fc.identity_payload({**IDENT, "title": "Café 中文"})
    path = fc.write_request(d, "gaps-1", "gaps", [payload])
    assert path == d / ("gaps-1" + fc.REQUEST_SUFFIX)
    assert path.is_file()
    assert not list(d.glob("*.tmp"))
    raw = path.read_bytes()
    raw.decode("ascii")
    assert json.loads(raw) == {"schema": 1, "request_id": "gaps-1", "mode": "gaps",
                               "identities": [payload]}
    with pytest.raises(ValueError):
        fc.write_request(d, "gaps-2", "gaps", [_payload(i) for i in range(51)])
    fc.write_request(d, "gaps-3", "gaps", [_payload(i) for i in range(50)])
    with pytest.raises(ValueError):
        fc.write_request(d, "A", "gaps", [payload])
    assert not (d / "A.request.json").exists()


def test_write_request_refuses_an_oversize_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "MAX_REQUEST_BYTES", 100)
    with pytest.raises(ValueError):
        fc.write_request(tmp_path, "gaps-1", "gaps", [_payload()])
    assert not (tmp_path / "gaps-1.request.json").exists()


def test_read_response_normalizes(tmp_path):
    _write_response(tmp_path, "r1", _response("r1", 1, {
        "a": {"status": "found", "stem": "doi-a-123456789abc", "detail": None},
        "b": {"status": "weird", "stem": "s", "detail": "d"},
        "c": {"status": "none", "stem": 5, "detail": 7},
        "d": "nope",
        "e": {"status": "unlicensed", "detail": "no_licence"},
    }))
    got = fc.read_response(tmp_path, "r1")
    bad = {"status": "failed", "stem": None, "detail": "bad_outcome"}
    assert got == {"complete": True, "outcomes": {
        "a": {"status": "found", "stem": "doi-a-123456789abc", "detail": None},
        "b": bad,
        "c": {"status": "none", "stem": None, "detail": None},
        "d": bad,
        "e": {"status": "unlicensed", "stem": None, "detail": "no_licence"},
    }}


def test_read_response_outcomes_not_a_dict(tmp_path):
    _write_response(tmp_path, "r1", {"schema": 1, "request_id": "r1",
                                     "complete": False, "outcomes": ["x"]})
    assert fc.read_response(tmp_path, "r1") == {"complete": False, "outcomes": {}}


@pytest.mark.parametrize("text", [
    "[]", "{not json", "",
    json.dumps({"schema": 2, "request_id": "r1", "complete": True, "outcomes": {}}),
    json.dumps({"request_id": "r1", "complete": True, "outcomes": {}}),
    json.dumps({"schema": 1, "request_id": "other", "complete": True, "outcomes": {}}),
])
def test_response_with_wrong_id_or_shape_is_absent(tmp_path, text):
    (tmp_path / "r1.response.json").write_text(text, encoding="utf-8")
    assert fc.read_response(tmp_path, "r1") is None


def test_response_absent_or_unreadable(tmp_path):
    assert fc.read_response(tmp_path, "r1") is None
    (tmp_path / "r1.response.json").mkdir()   # a directory: OSError on read
    assert fc.read_response(tmp_path, "r1") is None


def test_response_too_deeply_nested_is_absent(tmp_path):
    (tmp_path / "r1.response.json").write_text("[" * 100000, encoding="utf-8")
    assert fc.read_response(tmp_path, "r1") is None


class FakeTime:
    def __init__(self, on_sleep=None):
        self.now = 0.0
        self.sleeps = []
        self.on_sleep = on_sleep

    def clock(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s
        if self.on_sleep:
            self.on_sleep(len(self.sleeps))


def test_wait_returns_on_complete(tmp_path):
    _write_response(tmp_path, "r1", _response("r1", False))

    def on_sleep(n):
        if n == 2:
            _write_response(tmp_path, "r1", _response(
                "r1", True, {"k": {"status": "found", "stem": "s"}}))

    t = FakeTime(on_sleep)
    got = fc.wait_for_response(tmp_path, "r1", 60, clock=t.clock, sleep=t.sleep)
    assert got["complete"] is True and got["outcomes"]["k"]["status"] == "found"
    assert t.sleeps == [fc.POLL_SECONDS, fc.POLL_SECONDS]
    assert t.now == 2 * fc.POLL_SECONDS


def test_wait_stops_at_the_deadline(tmp_path):
    partial = _response("r1", False, {"k": {"status": "found", "stem": "s"}})
    _write_response(tmp_path, "r1", partial)
    t = FakeTime()
    got = fc.wait_for_response(tmp_path, "r1", 5, clock=t.clock, sleep=t.sleep)
    assert got["complete"] is False and got["outcomes"]["k"]["status"] == "found"
    assert t.sleeps == [2.0, 2.0, 1.0]
    assert sum(t.sleeps) <= 5


def test_wait_with_zero_seconds_reads_once(tmp_path):
    _write_response(tmp_path, "r1", _response("r1", True))
    t = FakeTime()
    got = fc.wait_for_response(tmp_path, "r1", 0, clock=t.clock, sleep=t.sleep)
    assert got["complete"] is True and t.sleeps == []


def test_wait_without_any_response(tmp_path):
    t = FakeTime()
    assert fc.wait_for_response(tmp_path, "r1", 3, clock=t.clock, sleep=t.sleep) == {
        "complete": False, "outcomes": {}}
    assert sum(t.sleeps) <= 3


def test_write_closed(tmp_path):
    fc.write_closed(tmp_path, "gaps-1")
    assert (tmp_path / "gaps-1.closed").is_file()
    assert (tmp_path / "gaps-1.closed").read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("entry,expected", [
    (None, ("deadline", [])),
    ({"status": "found", "stem": "s", "detail": None}, ("acquired", [])),
    ({"status": "found", "stem": "s", "detail": "x"}, ("acquired", [])),
    ({"status": "none", "stem": None, "detail": "no_doi"}, ("no_doi", [])),
    ({"status": "none", "stem": None, "detail": "no_oa_pdf"}, ("not_found", ["no_oa_pdf"])),
    ({"status": "none", "stem": None, "detail": None}, ("not_found", [])),
    ({"status": "unlicensed", "stem": None, "detail": "cc-by-nd"}, ("unlicensed", ["cc-by-nd"])),
    ({"status": "unlicensed", "stem": None, "detail": None}, ("unlicensed", [])),
    ({"status": "failed", "stem": None, "detail": "identity_rejected"},
     ("rejected", ["identity_rejected"])),
    ({"status": "failed", "stem": None, "detail": "timeout"}, ("not_found", ["timeout"])),
    ({"status": "failed", "stem": None, "detail": "too_large"}, ("not_found", ["too_large"])),
    ({"status": "failed", "stem": None, "detail": "not_pdf"}, ("not_found", ["not_pdf"])),
    ({"status": "failed", "stem": None, "detail": "blocked_host"}, ("not_found", ["blocked_host"])),
    ({"status": "failed", "stem": None, "detail": "removed"}, ("not_found", ["removed"])),
    ({"status": "failed", "stem": None, "detail": "bad_outcome"}, ("unavailable", ["bad_outcome"])),
    ({"status": "failed", "stem": None, "detail": None}, ("unavailable", ["failed"])),
])
def test_source_outcome(entry, expected):
    assert fc.source_outcome(entry) == expected
