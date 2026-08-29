"""fetch_web.py — the research-time fetch-and-capture tool.

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


def test_a_windows_1252_page_with_a_meta_charset_decodes_correctly():
    """A non-UTF-8 page must not become U+FFFD soup: replacement characters
    look like a valid capture but silently fail the barrier's title anchor
    and span containment for any non-ASCII span. The meta charset is the
    page's own declaration -- the parser must honor it."""
    filler = "He said “philosophy” and café matters greatly. " * 20
    body = ('<html><head><meta charset="windows-1252">'
            "<title>Café Studies</title></head>"
            f"<body><p>{filler}</p></body></html>").encode("windows-1252")
    rec = fw.build_record_from_response(
        "https://a.example/x", "https://a.example/x", 200, "text/html", body)
    assert "error" not in rec
    assert "�" not in rec["text"] and "�" not in rec["title"]
    assert rec["title"] == "Café Studies"
    assert "café matters" in rec["text"]


def test_the_http_header_charset_is_honored_without_a_meta_tag():
    """Pins the bytes-to-bs4 path with the header hint plumbed through.
    Honesty note: bs4's own statistical fallback also decodes this body, so
    this test discriminates the force-decode-as-UTF-8 bug, not the hint
    alone -- the hint is belt-and-braces for bodies where detection
    guesses wrong."""
    filler = "He said “philosophy” and café matters greatly. " * 20
    body = ("<html><head><title>Café Studies</title></head>"
            f"<body><p>{filler}</p></body></html>").encode("windows-1252")
    rec = fw.build_record_from_response(
        "https://a.example/x", "https://a.example/x", 200,
        "text/html; charset=windows-1252", body)
    assert "error" not in rec
    assert "�" not in rec["text"]
    assert "café matters" in rec["text"]


def test_declared_charset_parses_the_legal_header_forms():
    """Quoted values and whitespace around '=' are legal and common; a regex
    draft missed both, silently dropping the header hint (external review,
    2026-08-18)."""
    assert fw._declared_charset('text/html; charset="windows-1252"') == "windows-1252"
    assert fw._declared_charset("text/html; charset = Shift_JIS") == "shift_jis"
    assert fw._declared_charset("text/html; charset=windows-1252") == "windows-1252"
    assert fw._declared_charset("text/html; xcharset=evil") is None
    assert fw._declared_charset("text/html") is None
    assert fw._declared_charset(None) is None


def test_a_garbage_charset_name_degrades_to_sniffing_not_an_error_record():
    filler = "Plain ASCII sentences that decode anywhere at all. " * 10
    body = ("<html><head><title>Plain Page</title></head>"
            f"<body><p>{filler}</p></body></html>").encode("ascii")
    rec = fw.build_record_from_response(
        "https://a.example/x", "https://a.example/x", 200,
        "text/html; charset=totally-bogus-name", body)
    assert "error" not in rec
    assert "Plain ASCII sentences" in rec["text"]


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


# ---------------------------------------------------------------------------
# encyclopedia-host exclusion (owner decision 2026-08-17)
# ---------------------------------------------------------------------------

def test_an_excluded_host_is_refused_before_any_request(monkeypatch, tmp_path, capsys):
    class Boom:
        def __init__(self):
            raise AssertionError("network touched for an excluded host")
    monkeypatch.setattr(fw.requests, "Session", Boom)
    monkeypatch.setattr(sys, "argv", [
        "fetch_web.py", "--url", "https://plato.stanford.edu/entries/agency/",
        "--citekey", "k", "--review-dir", str(tmp_path)])
    assert fw.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error"
    assert out["error"] == "excluded-host:plato.stanford.edu"
    assert out["outcome"] == "refused"
    assert "fetch_sep" in out["hint"]
    assert not (tmp_path / "intermediate_files" / "web_captures" / "k.json").exists()


def test_stdin_cannot_capture_an_excluded_host_either(monkeypatch, tmp_path, capsys):
    """The exclusion is scope, not network courtesy alone: piping page text
    via --stdin must not create a capture for an excluded host."""
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("page text " * 50))
    monkeypatch.setattr(sys, "argv", [
        "fetch_web.py", "--stdin", "--url", "https://philpapers.org/rec/SMIT-1",
        "--citekey", "k", "--review-dir", str(tmp_path)])
    assert fw.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["error"] == "excluded-host:philpapers.org"
    assert not (tmp_path / "intermediate_files" / "web_captures" / "k.json").exists()


def test_a_refusal_never_touches_an_existing_good_capture(monkeypatch, tmp_path, capsys):
    """Network stubbed with the Boom idiom (like
    test_an_excluded_host_is_refused_before_any_request): unstubbed, this
    test false-passes on a network-isolated machine via the never-clobber
    fallback, and a regression that let the exclusion pre-check slip would
    make a live outbound GET in CI (external review, 2026-08-17)."""
    class Boom:
        def __init__(self):
            raise AssertionError("network touched for an excluded host")
    monkeypatch.setattr(fw.requests, "Session", Boom)
    cdir = tmp_path / "intermediate_files" / "web_captures"
    cdir.mkdir(parents=True)
    payload = json.dumps({"url": "https://iep.utm.edu/freewill/", "text": "good",
                          "provenance": "script"})
    (cdir / "k.json").write_text(payload, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "fetch_web.py", "--url", "https://iep.utm.edu/freewill/",
        "--citekey", "k", "--review-dir", str(tmp_path)])
    assert fw.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "refused"
    assert out["error"] == "excluded-host:iep.utm.edu"
    assert (cdir / "k.json").read_text(encoding="utf-8") == payload  # byte-identical


def test_a_redirect_onto_an_excluded_host_refuses_to_write_the_capture(monkeypatch, tmp_path, capsys):
    """The redirect seam (both external reviews, 2026-08-17): an allowed
    --url whose response chain lands on SEP must not become a capture. The
    GET has already happened (accepted, documented residual); the refusal
    keeps the excluded content out of the evidence chain."""
    class Resp:
        url = "https://plato.stanford.edu/entries/agency/"   # final, post-redirect
        status_code = 200
        headers = {"Content-Type": "text/html"}
        def iter_content(self, chunk_size):
            yield b"<html><head><title>Agency</title></head><body>" + b"x" * 500 + b"</body></html>"
        def close(self):
            pass
    class Session:
        max_redirects = 5
        def get(self, *a, **k):
            return Resp()
    monkeypatch.setattr(fw.requests, "Session", lambda: Session())
    monkeypatch.setattr(sys, "argv", [
        "fetch_web.py", "--url", "https://a.example/agency",
        "--citekey", "k", "--review-dir", str(tmp_path)])
    assert fw.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error"
    assert out["error"] == "excluded-host:plato.stanford.edu"
    assert out["outcome"] == "refused"
    assert not (tmp_path / "intermediate_files" / "web_captures" / "k.json").exists()


def test_cli_refusal_resolves_the_cross_skill_import_in_a_clean_process(tmp_path):
    """The sibling-skill sys.path reach must work OUTSIDE pytest's mutated
    import state (external review, 2026-08-17): in-process imports can mask
    a broken path computation because web_evidence is already in
    sys.modules from other test files."""
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "fetch_web.py"),
         "--url", "https://iep.utm.edu/freewill/",
         "--citekey", "k", "--review-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["error"] == "excluded-host:iep.utm.edu"
