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
    d.mkdir(parents=True)
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


def test_write_request_never_creates_the_directory(tmp_path):
    """The worker creates the request directory; a missing one is no worker."""
    with pytest.raises(FileNotFoundError):
        fc.write_request(tmp_path / "missing", "gaps-1", "gaps", [_payload()])
    assert not (tmp_path / "missing").exists()


def test_write_request_refuses_an_unknown_mode(tmp_path):
    with pytest.raises(ValueError, match="bad_mode"):
        fc.write_request(tmp_path, "bulk-1", "bulk", [_payload()])
    assert list(tmp_path.iterdir()) == []


def test_write_request_refuses_an_oversize_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "MAX_REQUEST_BYTES", 100)
    with pytest.raises(ValueError):
        fc.write_request(tmp_path, "gaps-1", "gaps", [_payload()])
    assert not (tmp_path / "gaps-1.request.json").exists()


def test_read_response_normalizes(tmp_path):
    _write_response(tmp_path, "r1", _response("r1", True, {
        "a": {"status": "found", "stem": "doi-a-123456789abc", "detail": None},
        "b": {"status": "weird", "stem": "s", "detail": "d"},
        "c": {"status": "none", "stem": 5, "detail": 7},
        "d": "nope",
        "e": {"status": "unlicensed", "detail": "no_licence"},
        "f": {"status": []},
        "g": {"status": {}},
    }))
    got = fc.read_response(tmp_path, "r1")
    bad = {"status": "failed", "stem": None, "detail": "bad_outcome"}
    assert got == {"complete": True, "outcomes": {
        "a": {"status": "found", "stem": "doi-a-123456789abc", "detail": None},
        "b": bad,
        "c": {"status": "none", "stem": None, "detail": None},
        "d": bad,
        "e": {"status": "unlicensed", "stem": None, "detail": "no_licence"},
        "f": bad,
        "g": bad,
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
    json.dumps({"schema": True, "request_id": "r1", "complete": True, "outcomes": {}}),
    json.dumps({"schema": 1.0, "request_id": "r1", "complete": True, "outcomes": {}}),
])
def test_response_with_wrong_id_or_shape_is_absent(tmp_path, text):
    (tmp_path / "r1.response.json").write_text(text, encoding="utf-8")
    assert fc.read_response(tmp_path, "r1") is None


@pytest.mark.parametrize("value", ["false", "true", 1, [1], None])
def test_complete_is_only_the_literal_true(tmp_path, value):
    _write_response(tmp_path, "r1", _response("r1", value))
    assert fc.read_response(tmp_path, "r1") == {"complete": False, "outcomes": {}}


def test_oversize_response_is_absent(tmp_path, monkeypatch):
    _write_response(tmp_path, "r1", _response("r1", True, {"k": {"status": "none"}}))
    monkeypatch.setattr(fc, "MAX_REQUEST_BYTES", 20)
    assert fc.read_response(tmp_path, "r1") is None


def test_oversize_response_is_absent_whatever_stat_says(tmp_path, monkeypatch):
    """The read itself is capped: a file that stat reports small (it grew
    after the stat) and whose JSON prefix parses is still too large."""
    monkeypatch.setattr(fc, "MAX_REQUEST_BYTES", 200)
    text = json.dumps(_response("r1", True, {"k": {"status": "none"}}))
    (tmp_path / "r1.response.json").write_text(text + " " * 300, encoding="utf-8")
    assert len(text) < 200

    class Small:
        st_size = 10
    monkeypatch.setattr(Path, "stat", lambda self, **kw: Small())
    assert fc.read_response(tmp_path, "r1") is None


def test_crlf_response_over_the_byte_cap_is_absent(tmp_path, monkeypatch):
    """Newlines are counted as stored: a CRLF file over the cap is oversize
    although its LF-translated text would fit."""
    lf = json.dumps(_response("r1", True, {"k": {"status": "none"}}), indent=1)
    crlf = lf.replace("\n", "\r\n")
    assert len(crlf) - len(lf) >= 2
    monkeypatch.setattr(fc, "MAX_REQUEST_BYTES", len(lf) + 1)
    (tmp_path / "r1.response.json").write_bytes(crlf.encode("utf-8"))
    assert fc.read_response(tmp_path, "r1") is None


def test_read_response_reads_at_most_one_past_the_cap(tmp_path, monkeypatch):
    _write_response(tmp_path, "r1", _response("r1", True))
    sizes, real_open = [], open

    class Spy:
        def __init__(self, f):
            self.f = f

        def __enter__(self):
            self.f.__enter__()
            return self

        def __exit__(self, *a):
            return self.f.__exit__(*a)

        def read(self, size=-1):
            sizes.append(size)
            return self.f.read(size)
    monkeypatch.setattr(fc, "open", lambda *a, **k: Spy(real_open(*a, **k)), raising=False)
    assert fc.read_response(tmp_path, "r1") is not None
    assert sizes == [fc.MAX_REQUEST_BYTES + 1]


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


def test_wait_for_responses_polls_every_id_each_round(tmp_path, monkeypatch):
    """The second request completes on the first tick and the first never:
    the wait runs to its bound, reading both ids every round, and keeps the
    second's complete response and the first's partial one."""
    partial = _response("r1", False, {"a": {"status": "none"}})
    _write_response(tmp_path, "r1", partial)
    reads = []
    real = fc.read_response

    def spy(request_dir, request_id):
        reads.append(request_id)
        return real(request_dir, request_id)

    def on_sleep(n):
        if n == 1:
            _write_response(tmp_path, "r2", _response(
                "r2", True, {"b": {"status": "found", "stem": "s"}}))

    t = FakeTime(on_sleep)
    monkeypatch.setattr(fc, "read_response", spy)
    got = fc.wait_for_responses(tmp_path, ["r1", "r2"], 5, clock=t.clock, sleep=t.sleep)
    assert got == {"r1": {"complete": False, "outcomes": {"a": {"status": "none", "stem": None,
                                                               "detail": None}}},
                   "r2": {"complete": True, "outcomes": {"b": {"status": "found", "stem": "s",
                                                               "detail": None}}}}
    assert t.sleeps == [2.0, 2.0, 1.0]
    assert reads == ["r1", "r2"] * 4


def test_wait_for_responses_returns_once_all_are_complete(tmp_path):
    for rid in ("r1", "r2"):
        _write_response(tmp_path, rid, _response(rid, True))
    t = FakeTime()
    got = fc.wait_for_responses(tmp_path, ["r1", "r2"], 60, clock=t.clock, sleep=t.sleep)
    assert all(r["complete"] for r in got.values()) and t.sleeps == []


def test_wait_for_responses_without_ids(tmp_path):
    t = FakeTime()
    assert fc.wait_for_responses(tmp_path, [], 60, clock=t.clock, sleep=t.sleep) == {}
    assert t.sleeps == []


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
    ({"status": "failed", "stem": None, "detail": "bad_request"}, ("unavailable", ["bad_request"])),
    ({"status": "failed", "stem": None, "detail": "budget"}, ("unavailable", ["budget"])),
    ({"status": "failed", "stem": None, "detail": "aborted"}, ("unavailable", ["aborted"])),
    ({"status": "failed", "stem": None, "detail": None}, ("unavailable", ["failed"])),
])
def test_source_outcome(entry, expected):
    assert fc.source_outcome(entry) == expected


def test_a_complete_response_without_the_key_is_no_outcome():
    """The worker finished and never answered this key: not a deadline."""
    assert fc.source_outcome(None, complete=True) == ("unavailable", ["no_outcome"])
    assert fc.source_outcome(None, complete=False) == ("deadline", [])
    found = {"status": "found", "stem": "s", "detail": None}
    assert fc.source_outcome(found, complete=True) == ("acquired", [])
