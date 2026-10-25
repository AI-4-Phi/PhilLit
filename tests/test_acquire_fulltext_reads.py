"""acquire_fulltext's body reads against a real local socket.

The fakes in test_acquire_fulltext.py hand over whole chunks, which hid
that `iter_content` returns only once 64 KiB are in: a body trickling in
below the socket timeout was bounded by nothing. These tests serve real
HTTP over loopback, so a read that waits on the network shows its real
duration.
"""

import gzip
import json
import socket
import subprocess
import sys
import threading
import time
import zlib
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "literature-review" / "scripts"))
import acquire_fulltext as af  # noqa: E402

GAP = 0.1         # seconds between trickled pieces
DEADLINE = 0.5    # the read's deadline in the trickle tests
SLACK = 0.5       # what a bounded read may take past it (one GAP plus scheduling)


class Server:
    """Serves one HTTP response on loopback: `head` header lines, then the
    `pieces` of the body with `gap` seconds between them. Records the
    request it received."""

    def __init__(self, pieces, headers=(), gap=0.0, length=None, chunked=False):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.url = f"http://127.0.0.1:{self.sock.getsockname()[1]}/w.pdf"
        self.request = b""
        body_len = sum(len(p) for p in pieces) if length is None else length
        head = [b"HTTP/1.1 200 OK", b"Connection: close", *headers]
        head.append(b"Transfer-Encoding: chunked" if chunked else b"Content-Length: %d" % body_len)
        self._head = b"\r\n".join(head) + b"\r\n\r\n"
        self._pieces, self._gap, self._chunked = pieces, gap, chunked
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        conn, _ = self.sock.accept()
        try:
            self.request = conn.recv(65536)
            conn.sendall(self._head)
            for piece in self._pieces:
                if self._stop.is_set():
                    break
                conn.sendall(b"%x\r\n%s\r\n" % (len(piece), piece) if self._chunked else piece)
                self._stop.wait(self._gap)
            if self._chunked and not self._stop.is_set():
                conn.sendall(b"0\r\n\r\n")
        except OSError:
            pass
        finally:
            conn.close()
            self.sock.close()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=5)


@pytest.fixture
def serve():
    servers = []

    def make(*args, **kwargs):
        servers.append(Server(*args, **kwargs))
        return servers[-1]
    yield make
    for s in servers:
        s.close()


def get(url):
    return af._http_get(url, timeout=5, stream=True)


def timed_read(resp, cap=1 << 20, deadline=None, head=b""):
    t0 = time.monotonic()
    try:
        return af._read_capped(resp, cap, deadline, head=head), time.monotonic() - t0
    finally:
        resp.close()


def gz_header():
    return gzip.compress(b"")[:10]


EMPTY_STORED_BLOCK = b"\x00\x00\x00\xff\xff"   # deflate: a non-final stored block of 0 bytes


class TestDeadline:
    def test_a_plain_trickle_ends_at_the_deadline(self, serve):
        srv = serve([b"x" * 10] * 300, gap=GAP)   # 30 s at full length
        (body, why), took = timed_read(get(srv.url), deadline=af.Deadline(DEADLINE))
        assert (body, why) == (None, "timeout")
        assert took < DEADLINE + SLACK

    def test_a_gzip_trickle_ends_at_the_deadline(self, serve):
        data = gzip.compress(bytes(range(256)) * 400)
        srv = serve([data[i:i + 10] for i in range(0, len(data), 10)], headers=[b"Content-Encoding: gzip"],
                    gap=GAP)
        (body, why), took = timed_read(get(srv.url), deadline=af.Deadline(DEADLINE))
        assert (body, why) == (None, "timeout")
        assert took < DEADLINE + SLACK

    def test_a_gzip_stream_that_never_yields_output_ends_at_the_deadline(self, serve):
        """urllib3's decoding read1 keeps reading while decoded output is
        empty, so this stream would hold it for 30 s."""
        srv = serve([gz_header()] + [EMPTY_STORED_BLOCK] * 300, headers=[b"Content-Encoding: gzip"], gap=GAP)
        (body, why), took = timed_read(get(srv.url), deadline=af.Deadline(DEADLINE))
        assert (body, why) == (None, "timeout")
        assert took < DEADLINE + SLACK

    def test_a_trickling_pdf_download_ends_within_its_deadline(self, serve):
        srv = serve([b"%PDF-1.4\n"] + [b"x" * 10] * 300, gap=GAP)
        t0 = time.monotonic()
        assert af.download_pdf(srv.url, af.Deadline(DEADLINE)) == (None, "timeout")
        assert time.monotonic() - t0 < DEADLINE + SLACK


class TestDecoding:
    BODY = b'{"results": [' + b'"abc", ' * 5000 + b'"z"]}'

    def test_only_gzip_and_deflate_are_asked_for(self, serve):
        srv = serve([b"{}"])
        timed_read(get(srv.url))
        assert b"accept-encoding: gzip, deflate\r\n" in srv.request.lower()

    @pytest.mark.parametrize("encoding, encode", [
        (b"gzip", gzip.compress),
        (b"x-gzip", gzip.compress),
        (b"deflate", zlib.compress),
        (b"deflate", lambda b: zlib.compress(b)[2:-4]),   # raw deflate, as servers often send it
        (b"identity", lambda b: b),
    ])
    def test_an_encoded_body_is_decoded(self, serve, encoding, encode):
        data = encode(self.BODY)
        srv = serve([data[:100], data[100:]], headers=[b"Content-Encoding: " + encoding])
        (body, why), _ = timed_read(get(srv.url))
        assert (body, why) == (self.BODY, "ok")

    def test_every_gzip_member_is_decoded(self, serve):
        data = gzip.compress(self.BODY[:500]) + gzip.compress(self.BODY[500:])
        srv = serve([data], headers=[b"Content-Encoding: gzip"])
        (body, why), _ = timed_read(get(srv.url))
        assert (body, why) == (self.BODY, "ok")

    def test_bytes_after_a_gzip_member_that_do_not_decode_end_the_body(self, serve):
        """As urllib3 decodes: trailing padding after a complete member."""
        srv = serve([gzip.compress(self.BODY) + b"\0" * 16], headers=[b"Content-Encoding: gzip"])
        (body, why), _ = timed_read(get(srv.url))
        assert (body, why) == (self.BODY, "ok")

    def test_the_cap_counts_every_gzip_member(self, serve):
        data = gzip.compress(b"a" * 600) + gzip.compress(b"b" * 600)
        srv = serve([data], headers=[b"Content-Encoding: gzip"])
        (body, why), _ = timed_read(get(srv.url), cap=1000)
        assert (body, why) == (None, "too_large")

    def test_a_chunked_body_is_read_whole(self, serve):
        srv = serve([self.BODY[:7], self.BODY[7:]], chunked=True)
        (body, why), _ = timed_read(get(srv.url))
        assert (body, why) == (self.BODY, "ok")

    def test_an_encoding_it_did_not_ask_for_is_refused(self, serve):
        srv = serve([b"\x8b\x00"], headers=[b"Content-Encoding: br"])
        (body, why), _ = timed_read(get(srv.url))
        assert (body, why) == (None, "bad_encoding")

    def test_a_gzip_bomb_is_too_large(self, serve):
        data = gzip.compress(b"\0" * (8 << 20))   # about 8 KB on the wire
        srv = serve([data], headers=[b"Content-Encoding: gzip"])
        (body, why), _ = timed_read(get(srv.url), cap=1 << 20)
        assert (body, why) == (None, "too_large")

    def test_a_truncated_gzip_stream_is_bad_encoding(self, serve):
        data = gzip.compress(self.BODY)[:-20]
        srv = serve([data], headers=[b"Content-Encoding: gzip"])
        (body, why), _ = timed_read(get(srv.url))
        assert (body, why) == (None, "bad_encoding")

    def test_a_gzip_encoded_pdf_downloads_decoded(self, serve):
        pdf = b"%PDF-1.4\n" + b"x" * 5000 + b"\n%%EOF\n"
        srv = serve([gzip.compress(pdf)], headers=[b"Content-Encoding: gzip"])
        assert af.download_pdf(srv.url, af.Deadline(10)) == (pdf, "ok")


class TestRefusals:
    def test_a_plain_non_pdf_is_refused_without_waiting_for_the_rest(self, serve):
        srv = serve([b"<html>", b"x" * 10], gap=5.0)
        t0 = time.monotonic()
        assert af.download_pdf(srv.url, af.Deadline(10)) == (None, "not_pdf")
        assert time.monotonic() - t0 < 2.0

    def test_a_gzip_non_pdf_is_refused_after_decoding(self, serve):
        srv = serve([gzip.compress(b"<html>" + b"x" * 100)], headers=[b"Content-Encoding: gzip"])
        assert af.download_pdf(srv.url, af.Deadline(10)) == (None, "not_pdf")

    def test_a_body_cut_short_raises_the_requests_error(self, serve):
        """A urllib3 error becomes the requests exception `iter_content`
        raised, so `_api_get` still retries it and `download_pdf` still
        names it."""
        srv = serve([b"{" * 10], length=1000)
        resp = get(srv.url)
        with pytest.raises(requests.exceptions.ChunkedEncodingError):
            timed_read(resp)

    def test_a_download_cut_short_is_a_network_reason(self, serve):
        srv = serve([b"%PDF-1.4\n"], length=1000)
        assert af.download_pdf(srv.url, af.Deadline(10)) == (None, "network:ChunkedEncodingError")


class TestWatchdog:
    """The backstop for what no deadline reaches (a slow status line, DNS,
    a proxy): it prints one JSON error line and ends the process."""

    def test_it_prints_one_error_line_and_exits_1(self, monkeypatch, capsys):
        fired = threading.Event()
        codes = []
        monkeypatch.setattr(af, "_exit", lambda code: (codes.append(code), fired.set()))
        af._Watchdog(0.05).start()
        assert fired.wait(5)
        assert codes == [1]
        out = capsys.readouterr().out.splitlines()
        assert len(out) == 1 and json.loads(out[0])["error"].startswith("hard_limit: stopped after 0.05 s")

    def test_finish_before_the_limit_stops_it(self, monkeypatch, capsys):
        codes = []
        monkeypatch.setattr(af, "_exit", codes.append)
        dog = af._Watchdog(0.1).start()
        dog.finish()
        time.sleep(0.3)
        assert codes == [] and capsys.readouterr().out == ""

    def test_a_blocked_download_ends_with_the_error_line(self, tmp_path):
        """End to end, in a real process: a status line that never ends
        holds `_http_get` past every deadline; the watchdog ends the run."""
        srv_sock = socket.socket()
        srv_sock.bind(("127.0.0.1", 0))
        srv_sock.listen(1)
        url = f"http://127.0.0.1:{srv_sock.getsockname()[1]}/w.pdf"
        stop = threading.Event()

        def trickle_status():
            conn, _ = srv_sock.accept()
            conn.recv(65536)
            while not stop.is_set():
                try:
                    conn.sendall(b"H")
                except OSError:
                    break
                stop.wait(0.05)
            conn.close()
        threading.Thread(target=trickle_status, daemon=True).start()
        script = (
            "import sys; sys.path.insert(0, sys.argv[1]); import acquire_fulltext as af\n"
            "af._Watchdog(1.0).start()\n"
            "af.download_pdf(sys.argv[2], af.Deadline(0.2))\n")
        scripts = Path(af.__file__).resolve().parent
        t0 = time.monotonic()
        proc = subprocess.run([sys.executable, "-c", script, str(scripts), url], capture_output=True,
                              text=True, timeout=60)
        stop.set()
        srv_sock.close()
        assert proc.returncode == 1
        assert proc.stdout.splitlines()[-1].startswith('{"error": "hard_limit: stopped after 1 s')
        assert time.monotonic() - t0 < 30
