"""Item 2: fetch_web.py — the research-time fetch-and-capture tool.

No network: the HTML/PDF extraction and record-building functions are called
directly, and `fetch` is exercised through a stubbed session.
"""
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "philosophy-research" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_web as fw


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------

def test_html_extraction_pulls_title_and_drops_script_and_style():
    html = ("<html><head><title>The Basic AI Drives</title>"
            "<style>body{color:red}</style></head>"
            "<body><script>var x=1</script><p>Real body text here.</p></body></html>")
    title, text = fw.extract_html(html)
    assert title == "The Basic AI Drives"
    assert "Real body text here." in text
    assert "var x=1" not in text and "color:red" not in text


def test_html_extraction_falls_back_to_h1_when_title_is_absent():
    title, _ = fw.extract_html("<html><body><h1>Fallback Heading</h1><p>x</p></body></html>")
    assert title == "Fallback Heading"


# ---------------------------------------------------------------------------
# capture writing
# ---------------------------------------------------------------------------

def test_write_capture_creates_the_file(tmp_path):
    rec = {"url": "https://a.example/x", "text": "hello", "provenance": "script"}
    assert fw.write_capture(tmp_path, "key2024a", rec) == "written"
    got = json.loads((tmp_path / "key2024a.json").read_text(encoding="utf-8"))
    assert got["text"] == "hello"


def test_a_failure_record_never_clobbers_an_existing_good_capture(tmp_path):
    """A re-run during an outage must not flip a citable entry back to
    EVIDENCE-NONE on the next barrier pass."""
    fw.write_capture(tmp_path, "k", {"url": "u", "text": "good text",
                                     "provenance": "script"})
    assert fw.write_capture(tmp_path, "k", {"url": "u", "error": "timeout"}) == "kept_existing"
    got = json.loads((tmp_path / "k.json").read_text(encoding="utf-8"))
    assert got["text"] == "good text" and "error" not in got


def test_a_successful_refetch_does_overwrite(tmp_path):
    fw.write_capture(tmp_path, "k", {"url": "u", "text": "old", "provenance": "script"})
    assert fw.write_capture(tmp_path, "k", {"url": "u", "text": "new",
                                            "provenance": "script"}) == "written"
    got = json.loads((tmp_path / "k.json").read_text(encoding="utf-8"))
    assert got["text"] == "new"


def test_a_failure_record_is_written_when_nothing_exists_yet(tmp_path):
    assert fw.write_capture(tmp_path, "k", {"url": "u", "error": "timeout"}) == "written"
    assert json.loads((tmp_path / "k.json").read_text(encoding="utf-8"))["error"] == "timeout"


def test_capture_json_is_written_without_ascii_escapes(tmp_path):
    fw.write_capture(tmp_path, "k", {"url": "u", "text": "Oñati Socio-legal",
                                     "provenance": "script"})
    raw = (tmp_path / "k.json").read_text(encoding="utf-8")
    assert "\\u" not in raw and "Oñati" in raw


# ---------------------------------------------------------------------------
# record building: size cap, PDF taxonomy, --stdin
# ---------------------------------------------------------------------------

def test_oversized_body_becomes_an_error_record_not_a_truncated_capture():
    rec = fw.build_record_from_response(
        url="https://a.example/x", final_url="https://a.example/x", status=200,
        content_type="text/html", body=b"x" * (fw.MAX_BYTES + 1))
    assert rec["error"].startswith("response-too-large") and not rec.get("text")


def test_pdf_with_no_extractable_text_becomes_an_error_record(monkeypatch):
    monkeypatch.setattr(fw, "extract_pdf", lambda data: ("", ""))
    rec = fw.build_record_from_response(
        url="https://a.example/x.pdf", final_url="https://a.example/x.pdf", status=200,
        content_type="application/pdf", body=b"%PDF-1.4 scanned")
    assert rec["error"] == "pdf-no-text"


def test_pdf_mojibake_below_the_printable_floor_becomes_an_error_record(monkeypatch):
    monkeypatch.setattr(fw, "extract_pdf", lambda data: ("t", "\x00\x01\x02\x03 ok"))
    rec = fw.build_record_from_response(
        url="https://a.example/x.pdf", final_url="https://a.example/x.pdf", status=200,
        content_type="application/pdf", body=b"%PDF-1.4")
    assert rec["error"] == "pdf-unreadable-text"


def test_a_pdf_is_detected_by_magic_bytes_without_a_content_type(monkeypatch):
    monkeypatch.setattr(fw, "extract_pdf", lambda data: ("T", "real pdf text"))
    rec = fw.build_record_from_response(
        url="https://a.example/x", final_url="https://a.example/x", status=200,
        content_type="", body=b"%PDF-1.7 stuff")
    assert rec["text"] == "real pdf text"


def test_stdin_capture_records_agent_provenance_and_null_status():
    rec = fw.build_stdin_record("https://a.example/x", "pasted page text")
    assert rec["provenance"] == "agent" and rec["http_status"] is None
    assert rec["text"] == "pasted page text"


def test_an_unsupported_scheme_is_refused_before_any_request():
    rec = fw.fetch("file:///etc/passwd")
    assert rec["error"] == "unsupported-scheme"


def test_a_declared_content_length_over_the_cap_short_circuits(monkeypatch):
    class Resp:
        status_code = 200
        url = "https://a.example/big"
        headers = {"Content-Length": str(fw.MAX_BYTES + 1), "Content-Type": "text/html"}
        def iter_content(self, chunk_size=0):      # pragma: no cover
            raise AssertionError("body must not be read")
        def close(self):
            pass

    class Session:
        max_redirects = 5
        def get(self, *a, **k):
            return Resp()

    monkeypatch.setattr(fw.requests, "Session", lambda: Session())
    rec = fw.fetch("https://a.example/big")
    assert rec["error"].startswith("response-too-large")


def test_a_lying_content_length_is_still_capped_while_streaming(monkeypatch):
    class Resp:
        status_code = 200
        url = "https://a.example/big"
        headers = {"Content-Type": "text/html"}     # no Content-Length at all
        def iter_content(self, chunk_size=0):
            yield b"x" * (fw.MAX_BYTES + 1)
        def close(self):
            pass

    class Session:
        max_redirects = 5
        def get(self, *a, **k):
            return Resp()

    monkeypatch.setattr(fw.requests, "Session", lambda: Session())
    rec = fw.fetch("https://a.example/big")
    assert rec["error"].startswith("response-too-large")


def test_stdin_read_is_capped_like_the_network_path(monkeypatch, tmp_path):
    """The network path enforces MAX_BYTES twice; --stdin used to read
    unbounded (2026-08-16 review finding). Oversize input becomes the same
    error-record taxonomy, never a capture."""
    import io
    monkeypatch.setattr(fw, "MAX_BYTES", 100)
    monkeypatch.setattr(sys, "stdin", io.StringIO("x" * 200))
    monkeypatch.setattr(sys, "argv", [
        "fetch_web.py", "--stdin", "--url", "https://a.example/x",
        "--citekey", "k", "--review-dir", str(tmp_path)])
    assert fw.main() == 0
    rec = json.loads((tmp_path / "intermediate_files" / "web_captures"
                      / "k.json").read_text(encoding="utf-8"))
    assert rec["error"].startswith("response-too-large:")
    assert not rec.get("text")
    assert rec["provenance"] == "agent"
