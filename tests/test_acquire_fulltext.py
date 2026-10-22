"""acquire_fulltext.py: source order, consent, the service policy, Zotero's
file:// handoff, the PDF-folder index, the store's collision and validity
rules, the download limits and the --gaps deadline.
HTTP is mocked throughout: every request goes through `_http_get`.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import subprocess
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

import acquire_fulltext as af  # noqa: E402
import fulltext as ft  # noqa: E402
from pdf_fixtures import make_pdf  # noqa: E402

FILLER = "This sentence is ordinary body text that pads the page to a realistic length."
DOI = "10.1234/jphil.2019.42"
TITLE = "Justified Harm and the Ethics of Defensive Action"
SURNAME = "Gardner"
YEAR = "2019"
ZBASE = af.ZOTERO_BASE
# What POSIX url2pathname does (it decodes percent-escapes), passed explicitly
# so the path tests hold on Windows too.
POSIX_URL2PATHNAME = unquote


def work_pdf(title=TITLE, author="John Gardner", doi=DOI, marker=""):
    first = [title, author] + ([f"https://doi.org/{doi}"] if doi else []) + [FILLER] * 4
    if marker:
        first.append(marker)
    return make_pdf([first, [FILLER] * 5])


def other_pdf():
    return work_pdf(title="A Completely Different Paper About Moral Luck", author="Jane Other",
                    doi="10.9999/other.1")


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None, payload=None, chunks=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self._payload = payload
        self._chunks = chunks
        self.closed = False
        self.text = body.decode("latin-1") if isinstance(body, bytes) else str(body)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def iter_content(self, chunk_size=65536):
        if self._chunks is not None:
            yield from self._chunks
            return
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


class FakeHTTP:
    """Routes by exact URL (params ignored, recorded)."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def add(self, url, response):
        self.routes[url] = response

    def __call__(self, url, *, headers=None, params=None, timeout=30.0, stream=False, trust_env=True):
        self.calls.append({"url": url, "headers": headers or {}, "params": params,
                           "trust_env": trust_env})
        r = self.routes.get(url)
        if r is None:
            return FakeResponse(404)
        return r(url, params) if callable(r) else r

    def urls(self):
        return [c["url"] for c in self.calls]


class NoLimiter:
    def wait(self):
        return 0.0

    def record(self):
        pass


class NoSleepBackoff(af.ExponentialBackoff):
    def wait(self, attempt, retry_after=None):
        return attempt < self.max_attempts - 1


@pytest.fixture
def http(monkeypatch, tmp_path):
    # Isolate: the cwd decides which .env load_dotenv finds, and
    # load_dotenv(override=True) writes into os.environ behind monkeypatch.
    saved = dict(os.environ)
    for k in list(os.environ):
        if k.startswith("PHILLIT_") or k in ("S2_API_KEY", "OPENALEX_API_KEY", "OPENALEX_EMAIL"):
            del os.environ[k]
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    monkeypatch.setattr(af, "PDF_INDEX_DIR", tmp_path / "pdf-index")
    monkeypatch.setattr(af, "get_limiter", lambda *a, **k: NoLimiter())
    monkeypatch.setattr(af, "ExponentialBackoff", NoSleepBackoff)
    fake = FakeHTTP()
    monkeypatch.setattr(af, "_http_get", fake)
    yield fake
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def workdir(tmp_path):
    wd = tmp_path / "wd"
    wd.mkdir()
    return wd


def write_env(text):
    Path(".env").write_text(text, encoding="utf-8")


def run(capsys, *argv):
    code = af.main([str(a) for a in argv])
    out = capsys.readouterr().out
    return code, out


def run_json(capsys, *argv):
    code, out = run(capsys, *argv)
    return code, json.loads(out)


def zotero_item(key, doi=DOI, title=TITLE, last=SURNAME, date="2019"):
    return {"key": key, "data": {"itemType": "journalArticle", "DOI": doi, "title": title,
                                 "creators": [{"creatorType": "author", "lastName": last,
                                               "firstName": "J"}],
                                 "date": date}, "meta": {}}


def setup_zotero(http, tmp_path, pdfs, items=None):
    """One parent item with one PDF attachment per entry of `pdfs`."""
    items = items if items is not None else [{"key": "NOTE1", "data": {"itemType": "note"}},
                                             zotero_item("PARENT")]
    http.add(f"{ZBASE}/items", FakeResponse(payload=items))
    children = []
    for n, data in enumerate(pdfs):
        att = f"ATT{n}"
        d = tmp_path / "zotero storage" / att
        d.mkdir(parents=True)
        p = d / "My Paper.pdf"
        p.write_bytes(data)
        children.append({"key": att, "data": {"itemType": "attachment", "contentType": "application/pdf"}})
        http.add(f"{ZBASE}/items/{att}/file",
                 FakeResponse(302, headers={"Location": p.as_uri()}))
    http.add(f"{ZBASE}/items/PARENT/children", FakeResponse(payload=children))


def oa_payload(urls_licences, best=None):
    locs = [{"pdf_url": u, "license": lic} for u, lic in urls_licences]
    return {"best_oa_location": best, "locations": locs}


OA_URL = f"{af.OPENALEX_BASE}/works/doi:{DOI}"
S2_URL = f"{af.S2_BASE_URL}/paper/DOI:{DOI}"


# ---------------------------------------------------------------------------
# Usage and crash contract
# ---------------------------------------------------------------------------

class TestCli:
    def test_runs_by_path_in_a_fresh_process(self, tmp_path):
        """The module's own sys.path inserts, not this file's, must find its
        imports (the wrapper runs it by path); and the exit contract holds in
        a real process."""
        env = {**os.environ, "PYTHONPATH": ""}
        script = str(SCRIPTS / "acquire_fulltext.py")
        r = subprocess.run([sys.executable, script, "--help"], cwd=tmp_path,
                           capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        r = subprocess.run([sys.executable, script, str(tmp_path), "--title", "x"], cwd=tmp_path,
                           capture_output=True, text=True, env=env)
        assert r.returncode == 2 and r.stdout == ""

    def test_usage_error_exits_2(self, http, workdir, capsys):
        with pytest.raises(SystemExit) as e:
            af.main([str(workdir), "--title", "x"])
        assert e.value.code == 2

    def test_gaps_needs_domains(self, http, workdir):
        with pytest.raises(SystemExit) as e:
            af.main([str(workdir), "--gaps"])
        assert e.value.code == 2

    def test_bad_doi_is_usage_error(self, http, workdir):
        with pytest.raises(SystemExit) as e:
            af.main([str(workdir), "--doi", "not-a-doi"])
        assert e.value.code == 2

    def test_crash_exits_1_with_one_json_object(self, http, workdir, capsys, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("kaput")
        monkeypatch.setattr(af, "acquire_one", boom)
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert code == 1
        assert data == {"error": "RuntimeError: kaput"}

    def test_not_found_is_exit_0(self, http, workdir, capsys):
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert code == 0
        assert data["status"] == "not_found"
        assert [t["source"] for t in data["tried"]] == ["zotero", "folder", "openalex", "s2"]


# ---------------------------------------------------------------------------
# Consent and the service policy
# ---------------------------------------------------------------------------

class TestConsent:
    def test_no_env_keys_no_zotero_or_folder_touch(self, http, workdir, capsys, tmp_path, monkeypatch):
        reads = []
        monkeypatch.setattr(af, "_index_read_file", lambda p: reads.append(p) or {})
        code, data = run_json(capsys, workdir, "--doi", DOI, "--title", TITLE,
                              "--author", SURNAME, "--year", YEAR)
        assert not any("localhost" in u for u in http.urls())
        assert reads == [] and not (tmp_path / "pdf-index").exists()
        outcomes = {t["source"]: t["outcome"] for t in data["tried"]}
        assert outcomes["zotero"] == "disabled" and outcomes["folder"] == "disabled"

    @pytest.mark.parametrize("token", ["on", "1", "TRUE", "yes"])
    def test_zotero_on_tokens(self, http, workdir, capsys, tmp_path, token):
        write_env(f"PHILLIT_ZOTERO={token}\n")
        setup_zotero(http, tmp_path, [work_pdf()])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired" and data["source"] == "zotero"
        # Zotero is reached proxy-free, like check_setup's probe.
        assert all(c["trust_env"] is False for c in http.calls if "localhost" in c["url"])

    def test_licensed_only_from_process_env_wins_over_env_file(self, http, workdir, capsys, tmp_path):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        write_env("PHILLIT_FULLTEXT_LICENSED_ONLY=0\nPHILLIT_ZOTERO=on\n"
                  f"PHILLIT_PDF_DIR={tmp_path}\n")
        setup_zotero(http, tmp_path, [work_pdf()])
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://pub.example/a.pdf", "publisher-specific")])))
        http.add("https://pub.example/a.pdf", FakeResponse(body=work_pdf()))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        outcomes = {t["source"]: t for t in data["tried"]}
        assert outcomes["zotero"]["outcome"] == "disabled"
        assert outcomes["zotero"]["detail"] == ["licensed_only"]
        assert outcomes["folder"]["outcome"] == "disabled"
        assert outcomes["openalex"]["outcome"] == "unlicensed"
        assert not any("localhost" in u or "pub.example" in u for u in http.urls())
        assert data["status"] == "not_found"

    def test_licensed_only_accepts_cc_and_records_licence(self, http, workdir, capsys):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://pub.example/a.pdf", None),
                                                          ("https://repo.example/b.pdf", "cc-by")])))
        http.add("https://repo.example/b.pdf", FakeResponse(body=work_pdf()))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired" and data["source"] == "openalex"
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.license == "cc-by" and rec.source_ref == "https://repo.example/b.pdf"
        assert "https://pub.example/a.pdf" not in http.urls()

    def test_s2_uppercase_licence_counts_as_cc(self, http, workdir, capsys):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        http.add(S2_URL, FakeResponse(payload={"openAccessPdf": {"url": "https://s2.example/p.pdf",
                                                                 "status": "HYBRID", "license": "CCBY"}}))
        http.add("https://s2.example/p.pdf", FakeResponse(body=work_pdf()))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired" and data["source"] == "s2"

    def test_env_file_cannot_switch_licensed_only_on_either(self, http, workdir, capsys):
        write_env("PHILLIT_FULLTEXT_LICENSED_ONLY=1\n")
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://pub.example/a.pdf", None)])))
        http.add("https://pub.example/a.pdf", FakeResponse(body=work_pdf()))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired"

    def test_pdf_route_works_under_licensed_only(self, http, workdir, capsys, tmp_path):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        p = tmp_path / "upload.pdf"
        p.write_bytes(work_pdf())
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", p)
        assert data["status"] == "acquired" and data["source"] == "user"


# ---------------------------------------------------------------------------
# Source order
# ---------------------------------------------------------------------------

class TestSourceOrder:
    def _all_sources(self, http, tmp_path):
        folder = tmp_path / "pdfs"
        folder.mkdir()
        (folder / "Gardner 2019 Justified Harm.pdf").write_bytes(work_pdf(marker="folder copy"))
        write_env(f'PHILLIT_ZOTERO=on\nPHILLIT_PDF_DIR="{folder}"\n')
        setup_zotero(http, tmp_path, [work_pdf(marker="zotero copy")])
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://oa.example/a.pdf", "cc-by")])))
        http.add("https://oa.example/a.pdf", FakeResponse(body=work_pdf(marker="oa copy")))
        http.add(S2_URL, FakeResponse(payload={"openAccessPdf": {"url": "https://s2.example/p.pdf"}}))
        http.add("https://s2.example/p.pdf", FakeResponse(body=work_pdf(marker="s2 copy")))
        return folder

    def test_zotero_first_and_nothing_after(self, http, workdir, capsys, tmp_path):
        self._all_sources(http, tmp_path)
        code, data = run_json(capsys, workdir, "--doi", DOI, "--title", TITLE,
                              "--author", SURNAME, "--year", YEAR)
        assert data["source"] == "zotero"
        assert [t["source"] for t in data["tried"]] == ["zotero"]
        assert not any("example" in u for u in http.urls())

    def test_doi_alone_uses_the_zotero_items_title_when_the_pdf_lacks_its_doi(
            self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [work_pdf(doi=None)])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired" and data["source"] == "zotero"
        sidecar = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert not sidecar.identity.get("title")   # the caller's identity is stored

    def test_folder_before_open_access(self, http, workdir, capsys, tmp_path):
        self._all_sources(http, tmp_path)
        http.add(f"{ZBASE}/items", FakeResponse(payload=[]))
        code, data = run_json(capsys, workdir, "--doi", DOI, "--title", TITLE,
                              "--author", SURNAME, "--year", YEAR)
        assert data["source"] == "folder"
        assert [(t["source"], t["outcome"]) for t in data["tried"]] == [
            ("zotero", "not_found"), ("folder", "acquired")]
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        # File name only: the sidecar travels with the delivered review.
        assert rec.source_ref == "folder:Gardner 2019 Justified Harm.pdf"

    def test_openalex_before_s2(self, http, workdir, capsys, tmp_path):
        self._all_sources(http, tmp_path)
        write_env("")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["source"] == "openalex"
        assert S2_URL not in http.urls()

    def test_s2_when_openalex_has_nothing(self, http, workdir, capsys, tmp_path):
        self._all_sources(http, tmp_path)
        write_env("")
        http.add(OA_URL, FakeResponse(404))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["source"] == "s2"
        assert ("openalex", "not_found") in [(t["source"], t["outcome"]) for t in data["tried"]]

    def test_oa_best_location_first_and_deduped(self, http, workdir, capsys):
        best = {"pdf_url": "https://best.example/x.pdf", "license": "cc-by"}
        http.add(OA_URL, FakeResponse(payload=oa_payload(
            [("https://best.example/x.pdf", "cc-by"), ("https://other.example/y.pdf", "cc-by")], best=best)))
        http.add("https://best.example/x.pdf", FakeResponse(body=b"<html>landing page</html>"))
        http.add("https://other.example/y.pdf", FakeResponse(body=work_pdf()))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["source"] == "openalex"
        assert http.urls().count("https://best.example/x.pdf") == 1
        assert http.urls().index("https://best.example/x.pdf") < http.urls().index("https://other.example/y.pdf")

    def test_no_api_key_reaches_a_pdf_host(self, http, workdir, capsys):
        write_env("OPENALEX_API_KEY=abcdef123\nS2_API_KEY=s2secret\n")
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://oa.example/a.pdf", None)])))
        http.add("https://oa.example/a.pdf", FakeResponse(body=other_pdf()))
        http.add(S2_URL, FakeResponse(payload={"openAccessPdf": {"url": "https://s2.example/p.pdf"}}))
        http.add("https://s2.example/p.pdf", FakeResponse(body=work_pdf()))
        run_json(capsys, workdir, "--doi", DOI)
        for c in http.calls:
            if "example" in c["url"]:
                assert "Authorization" not in c["headers"] and "x-api-key" not in c["headers"]
        meta = {c["url"]: c["headers"] for c in http.calls}
        assert meta[OA_URL].get("Authorization") == "Bearer abcdef123"
        assert meta[S2_URL].get("x-api-key") == "s2secret"

    def test_oa_sources_need_a_doi(self, http, workdir, capsys):
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        outcomes = {t["source"]: t["outcome"] for t in data["tried"]}
        assert outcomes["openalex"] == "no_doi" and outcomes["s2"] == "no_doi"
        assert http.calls == []


# ---------------------------------------------------------------------------
# --pdf
# ---------------------------------------------------------------------------

class TestUserPdf:
    def test_wrong_work_is_rejected(self, http, workdir, capsys, tmp_path):
        p = tmp_path / "wrong.pdf"
        p.write_bytes(other_pdf())
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", p)
        assert code == 0 and data["status"] == "rejected"
        assert data["tried"][0]["source"] == "user"
        assert data["tried"][0]["detail"][0].startswith("identity_failed:")
        assert not (workdir / ft.STORE_REL).exists()
        assert http.calls == []   # --pdf replaces the source search

    def test_right_work_no_doi(self, http, workdir, capsys, tmp_path):
        p = tmp_path / "right.pdf"
        p.write_bytes(work_pdf(doi=None))
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME,
                              "--year", YEAR, "--pdf", p)
        assert data["status"] == "acquired" and data["source"] == "user"
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.identity == {"doi": None, "title": TITLE, "surname": SURNAME, "year": YEAR}
        assert rec.source_ref == "user:right.pdf"
        assert rec.pdf_sha256 == hashlib.sha256(p.read_bytes()).hexdigest()

    def test_missing_file_is_not_found(self, http, workdir, capsys, tmp_path):
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", tmp_path / "nope.pdf")
        assert data["status"] == "not_found"
        assert data["tried"] == [{"source": "user", "outcome": "not_found", "detail": ["missing"]}]

    def test_unextractable_pdf_is_rejected(self, http, workdir, capsys, tmp_path):
        p = tmp_path / "enc.pdf"
        p.write_bytes(make_pdf([[TITLE, FILLER, FILLER, FILLER]], encrypt=True))
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", p)
        assert data["status"] == "rejected"
        assert data["tried"][0]["detail"] == ["extract_failed:encrypted"]


# ---------------------------------------------------------------------------
# Zotero
# ---------------------------------------------------------------------------

class TestZotero:
    def test_file_url_with_spaces(self):
        path, why = af.zotero_file_path("file:///Users/j%20h/Zotero/storage/AB/My%20Paper.pdf",
                                        url2pathname=POSIX_URL2PATHNAME)
        assert (path, why) == ("/Users/j h/Zotero/storage/AB/My Paper.pdf", "ok")

    def test_percent_in_a_file_name_is_decoded_once(self):
        path, _ = af.zotero_file_path("file:///tmp/100%2541.pdf", url2pathname=POSIX_URL2PATHNAME)
        assert path == "/tmp/100%41.pdf"

    def test_windows_drive_form(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import nturl2path
        path, why = af.zotero_file_path("file:///C:/Users/J%20H/Zotero/storage/AB/My%20Paper.pdf",
                                        url2pathname=nturl2path.url2pathname)
        assert (path, why) == ("C:\\Users\\J H\\Zotero\\storage\\AB\\My Paper.pdf", "ok")

    def test_localhost_host_accepted(self):
        assert af.zotero_file_path("file://localhost/tmp/a.pdf",
                                   url2pathname=POSIX_URL2PATHNAME) == ("/tmp/a.pdf", "ok")

    @pytest.mark.parametrize("loc", [
        "file:////server/share/p.pdf",          # empty host, path //server
        "file://///server/share/p.pdf",
        "file:///%5C%5Cserver/share/p.pdf",     # escaped backslashes
        "file:////%5Cserver/share/p.pdf",
    ])
    def test_share_with_empty_host_refused(self, loc):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import nturl2path
        assert af.zotero_file_path(loc, url2pathname=POSIX_URL2PATHNAME) == (None, "unc_host")
        assert af.zotero_file_path(loc, url2pathname=nturl2path.url2pathname) == (None, "unc_host")
        assert af.zotero_file_path(loc) == (None, "unc_host")   # this platform's own

    def test_share_after_url2pathname_refused(self):
        # A converter that turns an innocent-looking path into a share.
        assert af.zotero_file_path("file:///x/a.pdf",
                                   url2pathname=lambda p: "\\\\server\\x\\a.pdf") == (None, "unc_host")

    @pytest.mark.parametrize("loc,why", [
        ("file://fileserver/share/a.pdf", "unc_host"),
        ("http://localhost:23119/a.pdf", "not_file_url"),
        ("", "not_file_url"),
    ])
    def test_refused_locations(self, loc, why):
        assert af.zotero_file_path(loc) == (None, why)

    def test_unc_attachment_is_skipped_and_reported(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [work_pdf()])
        http.add(f"{ZBASE}/items/ATT0/file", FakeResponse(302, headers={"Location": "file://server/s/a.pdf"}))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        z = data["tried"][0]
        assert z == {"source": "zotero", "outcome": "not_found", "detail": ["ATT0:unc_host"]}

    def test_unavailable_when_zotero_does_not_answer(self, http, workdir, capsys, monkeypatch):
        import requests
        write_env("PHILLIT_ZOTERO=on\n")
        inner = af._http_get

        def refuse(url, **kw):
            if "localhost" in url:
                raise requests.ConnectionError("refused")
            return inner(url, **kw)
        monkeypatch.setattr(af, "_http_get", refuse)
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0]["outcome"] == "unavailable"

    def test_multiple_attachments_first_wins(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        first, second = work_pdf(marker="first copy"), work_pdf(marker="second copy")
        setup_zotero(http, tmp_path, [first, second])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired"
        assert data["tried"][0]["detail"] == ["multiple_candidates:2"]
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.pdf_sha256 == hashlib.sha256(first).hexdigest()
        assert rec.source_ref == "zotero:PARENT/ATT0"

    def test_failing_attachment_then_passing_one(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        good = work_pdf()
        setup_zotero(http, tmp_path, [other_pdf(), good])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.pdf_sha256 == hashlib.sha256(good).hexdigest()
        assert data["tried"][0]["detail"][0].startswith("ATT0:identity_failed")

    def test_all_attachments_fail_is_rejected(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [other_pdf()])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "rejected"
        assert data["tried"][0]["outcome"] == "rejected"

    def test_metadata_mismatch_reads_no_attachment(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [work_pdf()], items=[zotero_item("PARENT", doi="10.5555/else")])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0]["outcome"] == "not_found"
        assert not any(u.endswith("/file") or u.endswith("/children") for u in http.urls())

    def test_no_doi_item_matched_by_title_surname_year(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [work_pdf(doi=None)],
                     items=[zotero_item("PARENT", doi="", date="March 2019")])
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        assert data["status"] == "acquired" and data["source"] == "zotero"
        assert http.calls[0]["params"]["q"] == ft.title_phrase_cut(TITLE)

    def test_wrong_year_item_is_not_matched(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [work_pdf(doi=None)],
                     items=[zotero_item("PARENT", doi="", date="2011")])
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        assert data["tried"][0]["outcome"] == "not_found"


# ---------------------------------------------------------------------------
# PDF folder and its index
# ---------------------------------------------------------------------------

class TestFolder:
    def _folder(self, tmp_path, files):
        folder = tmp_path / "pdfs"
        folder.mkdir(exist_ok=True)
        for name, data in files.items():
            (folder / name).write_bytes(data)
        write_env(f"PHILLIT_PDF_DIR='{folder}'\n")
        return folder

    def test_index_found_by_doi_whatever_the_file_name(self, http, workdir, capsys, tmp_path):
        self._folder(tmp_path, {"scan0001.pdf": work_pdf(), "zzz.pdf": other_pdf()})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["source"] == "folder"
        idx_files = list((tmp_path / "pdf-index").glob("*.json"))
        assert len(idx_files) == 1
        index = json.loads(idx_files[0].read_text(encoding="utf-8"))
        assert DOI in index["files"]["scan0001.pdf"]["dois"]

    def test_index_key_is_the_normalized_folder_path(self, tmp_path):
        folder = tmp_path / "pdfs"
        a = af.index_path(folder)
        b = af.index_path(Path(str(folder) + "/sub/.."))
        assert a == b and len(a.stem) == 16

    def test_index_reused_and_changed_file_reread(self, http, workdir, capsys, tmp_path, monkeypatch):
        folder = self._folder(tmp_path, {"a.pdf": other_pdf(), "b.pdf": other_pdf()})
        reads = []
        real = af._index_read_file
        monkeypatch.setattr(af, "_index_read_file", lambda p: reads.append(Path(p).name) or real(p))
        run_json(capsys, workdir, "--doi", DOI)
        assert sorted(reads) == ["a.pdf", "b.pdf"]
        reads.clear()
        run_json(capsys, workdir, "--doi", DOI)
        assert reads == []   # reused
        (folder / "b.pdf").write_bytes(work_pdf())   # size and mtime change
        st = os.stat(folder / "b.pdf")
        os.utime(folder / "b.pdf", (st.st_atime, st.st_mtime + 10))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert reads == ["b.pdf"]
        assert data["source"] == "folder"

    def test_unindexed_file_still_matches_by_name(self, http, workdir, capsys, tmp_path, monkeypatch):
        self._folder(tmp_path, {"Gardner2019-justified.pdf": work_pdf(doi=None)})
        monkeypatch.setattr(af, "INDEX_BUDGET_SINGLE", 0)   # no time to index anything
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        assert data["source"] == "folder"
        folder_try = data["tried"][1]
        assert any(d.startswith("index_incomplete") for d in folder_try["detail"])

    def test_found_by_page_head_title(self, http, workdir, capsys, tmp_path):
        self._folder(tmp_path, {"x.pdf": work_pdf(doi=None)})
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        assert data["source"] == "folder"

    def test_twenty_first_candidate_reported(self, http, workdir, capsys, tmp_path, monkeypatch):
        files = {f"Gardner {n:02d}.pdf": other_pdf() for n in range(21)}
        self._folder(tmp_path, files)
        checked = []
        real = af.check_pdf
        monkeypatch.setattr(af, "check_pdf", lambda d, i: checked.append(1) or real(d, i))
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        folder_try = data["tried"][1]
        assert folder_try["outcome"] == "rejected"
        assert "candidate_limit:21" in folder_try["detail"]
        assert len(checked) == 20

    def test_symlinks_skipped(self, http, workdir, capsys, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "Gardner.pdf").write_bytes(work_pdf())
        folder = self._folder(tmp_path, {})
        try:
            os.symlink(outside / "Gardner.pdf", folder / "Gardner.pdf")
            os.symlink(outside, folder / "linkdir")
        except OSError:
            pytest.skip("symlinks need privileges here")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][1]["outcome"] == "not_found"

    def test_walk_limit(self, http, workdir, capsys, tmp_path, monkeypatch):
        self._folder(tmp_path, {"a.pdf": other_pdf(), "b.pdf": other_pdf(), "c.pdf": work_pdf()})
        monkeypatch.setattr(af, "MAX_WALK_FILES", 2)
        code, data = run_json(capsys, workdir, "--doi", DOI)
        folder_try = data["tried"][1]
        assert "walk_limit" in folder_try["detail"] and folder_try["outcome"] == "not_found"

    def test_unreadable_subtree_reported_and_cache_kept(self, http, workdir, capsys, tmp_path):
        if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
            pytest.skip("chmod 000 does not block listing here")
        folder = self._folder(tmp_path, {"top.pdf": other_pdf()})
        sub = folder / "sub"
        sub.mkdir()
        (sub / "scan.pdf").write_bytes(work_pdf())
        run_json(capsys, workdir, "--doi", DOI)   # indexes sub/scan.pdf
        idx_file = next((tmp_path / "pdf-index").glob("*.json"))
        assert "sub/scan.pdf" in json.loads(idx_file.read_text(encoding="utf-8"))["files"]
        sub.chmod(0)
        try:
            code, data = run_json(capsys, workdir, "--title", "Other", "--author", "Nobody",
                                  "--year", YEAR)
            folder_try = data["tried"][1]
            assert "walk_error:1" in folder_try["detail"]
            index = json.loads(idx_file.read_text(encoding="utf-8"))
            assert "sub/scan.pdf" in index["files"]   # kept, not dropped
        finally:
            sub.chmod(0o755)

    def test_missing_folder_is_unavailable(self, http, workdir, capsys, tmp_path):
        write_env(f"PHILLIT_PDF_DIR={tmp_path / 'nowhere'}\n")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][1] == {"source": "folder", "outcome": "unavailable",
                                    "detail": ["folder_missing"]}


# ---------------------------------------------------------------------------
# Store: existing records, collisions, path budget
# ---------------------------------------------------------------------------

class TestStore:
    def _pdf(self, tmp_path, data=None):
        p = tmp_path / "in.pdf"
        p.write_bytes(data or work_pdf())
        return p

    def test_exists_ends_the_call(self, http, workdir, capsys, tmp_path):
        p = self._pdf(tmp_path)
        run_json(capsys, workdir, "--doi", DOI, "--pdf", p)
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "exists" and data["source"] == "user"
        assert http.calls == []

    def test_invalid_record_replaced(self, http, workdir, capsys, tmp_path):
        p = self._pdf(tmp_path)
        code, first = run_json(capsys, workdir, "--doi", DOI, "--pdf", p)
        store = workdir / ft.STORE_REL
        (store / f"{first['slug']}.pdf").write_bytes(b"%PDF-tampered")
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", p)
        assert data["status"] == "acquired"
        assert data["tried"][0] == {"source": "store", "outcome": "invalid_replaced:pdf_hash_mismatch"}
        assert isinstance(ft.validate_record(store, data["slug"]), ft.Record)

    def test_unreadable_sidecar_replaced(self, http, workdir, capsys, tmp_path):
        ident = af.make_identity(DOI)
        slug = ft.slug_for(ident)
        store = workdir / ft.STORE_REL
        store.mkdir(parents=True)
        (store / f"{slug}.json").write_text("{not json", encoding="utf-8")
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", self._pdf(tmp_path))
        assert data["tried"][0]["outcome"] == "invalid_replaced:sidecar_unreadable"

    def test_invalid_record_kept_when_nothing_found(self, http, workdir, capsys):
        ident = af.make_identity(DOI)
        slug = ft.slug_for(ident)
        store = workdir / ft.STORE_REL
        store.mkdir(parents=True)
        (store / f"{slug}.pdf").write_bytes(b"%PDF-orphan")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "not_found"
        assert data["tried"][0] == {"source": "store", "outcome": "invalid_kept:sidecar_unreadable"}

    def test_slug_collision_refused_and_nothing_overwritten(self, http, workdir, capsys, tmp_path):
        ident = af.make_identity(DOI)
        slug = ft.slug_for(ident)
        store = workdir / ft.STORE_REL
        store.mkdir(parents=True)
        foreign = {"schema": 1, "slug": slug,
                   "identity": {"doi": "10.1234/someone.else", "title": None, "surname": None, "year": None},
                   "source": "user", "source_ref": None, "license": None,
                   "pdf_sha256": "0" * 64, "acquired_at": "x"}
        (store / f"{slug}.json").write_text(json.dumps(foreign), encoding="utf-8")
        (store / f"{slug}.pdf").write_bytes(b"%PDF-theirs")
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", self._pdf(tmp_path))
        assert code == 0 and data["status"] == "refused"
        assert data["tried"][0]["outcome"] == "slug_collision"
        assert (store / f"{slug}.pdf").read_bytes() == b"%PDF-theirs"
        assert json.loads((store / f"{slug}.json").read_text(encoding="utf-8")) == foreign

    def test_path_too_long_refused(self, http, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(af.ft, "path_budget_ok", lambda wd: False)
        wd = tmp_path / "wd"
        wd.mkdir()
        code, data = run_json(capsys, wd, "--doi", DOI)
        assert data["status"] == "refused"
        assert data["tried"] == [{"source": "store", "outcome": "path_too_long"}]

    def test_sidecar_fields(self, http, workdir, capsys, tmp_path):
        code, data = run_json(capsys, workdir, "--doi", "https://doi.org/10.1234/JPHIL.2019.42",
                              "--pdf", self._pdf(tmp_path))
        side = json.loads((workdir / ft.STORE_REL / f"{data['slug']}.json").read_text(encoding="utf-8"))
        assert set(side) == {"schema", "slug", "identity", "source", "source_ref", "license",
                             "pdf_sha256", "acquired_at"}
        assert side["identity"] == {"doi": DOI, "title": None, "surname": None, "year": None}
        assert not list((workdir / ft.STORE_REL).glob("*.txt"))
        assert not list((workdir / ft.STORE_REL).glob("*.tmp"))


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

class TestDownload:
    def test_redirect_to_a_non_http_scheme_refused(self, http):
        http.add("https://a.example/x", FakeResponse(302, headers={"Location": "file:///etc/passwd"}))
        assert af.download_pdf("https://a.example/x", af.Deadline(None)) == (None, "bad_scheme")
        assert http.urls() == ["https://a.example/x"]

    def test_relative_redirect_followed(self, http):
        http.add("https://a.example/x", FakeResponse(302, headers={"Location": "/y.pdf"}))
        http.add("https://a.example/y.pdf", FakeResponse(body=b"%PDF-1.4 body"))
        assert af.download_pdf("https://a.example/x", af.Deadline(None)) == (b"%PDF-1.4 body", "ok")

    def test_too_many_redirects(self, http):
        for n in range(7):
            http.add(f"https://a.example/{n}", FakeResponse(302, headers={"Location": f"/{n + 1}"}))
        assert af.download_pdf("https://a.example/0", af.Deadline(None)) == (None, "too_many_redirects")
        assert len(http.calls) == af.MAX_REDIRECTS + 1

    def test_streaming_cap(self, http, monkeypatch):
        monkeypatch.setattr(af, "MAX_DOWNLOAD_BYTES", 100)
        resp = FakeResponse(chunks=[b"%PDF-" + b"x" * 59, b"y" * 64, b"z" * 64])
        http.add("https://a.example/big", resp)
        assert af.download_pdf("https://a.example/big", af.Deadline(None)) == (None, "too_large")
        assert resp.closed

    def test_declared_length_over_cap(self, http, monkeypatch):
        monkeypatch.setattr(af, "MAX_DOWNLOAD_BYTES", 100)
        http.add("https://a.example/big", FakeResponse(body=b"%PDF-", headers={"Content-Length": "1000"}))
        assert af.download_pdf("https://a.example/big", af.Deadline(None)) == (None, "too_large")

    def test_body_must_start_pdf(self, http):
        http.add("https://a.example/page", FakeResponse(body=b"<!doctype html><html>"))
        assert af.download_pdf("https://a.example/page", af.Deadline(None)) == (None, "not_pdf")

    def test_http_error_status(self, http):
        http.add("https://a.example/gone", FakeResponse(403))
        assert af.download_pdf("https://a.example/gone", af.Deadline(None)) == (None, "http_403")

    def test_non_http_start_refused(self, http):
        assert af.download_pdf("ftp://a.example/x.pdf", af.Deadline(None)) == (None, "bad_scheme")
        assert http.calls == []

    def test_wall_clock_timeout(self, http, monkeypatch):
        now = [0.0]
        monkeypatch.setattr(af, "_clock", lambda: now[0])

        def slow_chunks():
            yield b"%PDF-"
            now[0] += 31
            yield b"more"
        http.add("https://a.example/slow", FakeResponse(chunks=slow_chunks()))
        assert af.download_pdf("https://a.example/slow", af.Deadline(None)) == (None, "timeout")


# ---------------------------------------------------------------------------
# --gaps
# ---------------------------------------------------------------------------

def bib_entry(key, doi=None, abstract=None, title=TITLE, author="Gardner, John", year=YEAR):
    lines = [f"@article{{{key},", f"  title = {{{title}}},", f"  author = {{{author}}},",
             f"  year = {{{year}}},"]
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    if abstract:
        lines.append(f"  abstract = {{{abstract}}},")
    lines.append("}")
    return "\n".join(lines) + "\n"


class TestGaps:
    def test_candidates_selection(self, http, workdir):
        (workdir / "literature-domain-1.bib").write_text(
            "@comment{ignore me}\n"
            + bib_entry("hasabs", doi="10.1/a", abstract="Some abstract.")
            + bib_entry("doionly", doi="10.1/b")
            + bib_entry("nodoi", title="Another Title Entirely"), encoding="utf-8")
        cands, domains = af.gap_candidates(workdir, 2, title_route=False)
        assert [k for _, k, _ in cands] == ["doionly"]
        assert domains == {"1": "present", "2": "missing"}
        cands, _ = af.gap_candidates(workdir, 1, title_route=True)
        assert [k for _, k, _ in cands] == ["doionly", "nodoi"]

    def test_stored_identity_is_raw(self, http, workdir):
        (workdir / "literature-domain-1.bib").write_text(
            bib_entry("raw", title="{M}oral {L}uck in {K}ant", author="van Fraassen, Bas and Doe, J."),
            encoding="utf-8")
        cands, _ = af.gap_candidates(workdir, 1, title_route=True)
        assert cands[0][2] == {"doi": None, "title": "{M}oral {L}uck in {K}ant",
                               "surname": "van Fraassen", "year": YEAR}

    def test_deadline_and_not_attempted(self, http, workdir, capsys, monkeypatch):
        now = [0.0]
        monkeypatch.setattr(af, "_clock", lambda: now[0])
        (workdir / "literature-domain-1.bib").write_text(
            "".join(bib_entry(f"k{n}", doi=f"10.1/w{n}") for n in range(4)), encoding="utf-8")

        def slow_openalex(identity, settings, deadline):
            now[0] += 200
            return af.SourceResult("openalex", "not_found")
        monkeypatch.setitem(af._SOURCES, "openalex", slow_openalex)
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        assert code == 0
        assert len(out.strip().splitlines()) == 1
        summary = json.loads(out)
        assert summary["counts"] == {"not_found": 3, "not_attempted": 1}
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        outcomes = [(e["key"], e["outcome"]) for e in report["entries"]]
        assert outcomes == [("k0", "not_found"), ("k1", "not_found"), ("k2", "not_found"),
                            ("k3", "not_attempted")]
        # The source the deadline cut inside an entry is reported as such.
        k2 = report["entries"][2]["tried"]
        assert {"source": "s2", "outcome": "deadline"} in k2

    def test_entry_crash_named_in_summary_and_report(self, http, workdir, capsys, monkeypatch):
        (workdir / "literature-domain-1.bib").write_text(
            bib_entry("ok", doi="10.1/fine") + bib_entry("bad", doi="10.1/boom"), encoding="utf-8")
        real = af.acquire_one

        def flaky(wd, ident, settings, deadline, pdf_path=None):
            if ident["doi"] == "10.1/boom":
                raise RuntimeError("kaput")
            return real(wd, ident, settings, deadline, pdf_path)
        monkeypatch.setattr(af, "acquire_one", flaky)
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        assert code == 0
        summary = json.loads(out)
        expected = [{"entry": "1/bad", "reason": "error:RuntimeError: kaput"}]
        assert summary["status"] == "done_with_errors" and summary["errors"] == expected
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert report["status"] == "done_with_errors" and report["errors"] == expected

    def test_duplicate_of_a_crashed_entry_names_the_real_reason(self, http, workdir, capsys, monkeypatch):
        for i in (1, 2):
            (workdir / f"literature-domain-{i}.bib").write_text(bib_entry(f"g{i}", doi=DOI),
                                                                encoding="utf-8")

        def boom(*a, **k):
            raise RuntimeError("kaput")
        monkeypatch.setattr(af, "acquire_one", boom)
        code, out = run(capsys, workdir, "--gaps", "--domains", "2")
        assert json.loads(out)["errors"] == [
            {"entry": "1/g1", "reason": "error:RuntimeError: kaput"},
            {"entry": "2/g2", "reason": "error:RuntimeError: kaput"}]

    def test_folder_warnings_reach_the_summary_once(self, http, workdir, capsys, tmp_path, monkeypatch):
        folder = tmp_path / "pdfs"
        folder.mkdir()
        for n in range(3):
            (folder / f"f{n}.pdf").write_bytes(other_pdf())
        write_env(f"PHILLIT_PDF_DIR={folder}\n")
        monkeypatch.setattr(af, "MAX_WALK_FILES", 2)
        (workdir / "literature-domain-1.bib").write_text(
            bib_entry("a", doi="10.1/a") + bib_entry("b", doi="10.1/b"), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        expected = ["folder: walk_limit (stopped at 2 files)"]
        assert json.loads(out)["warnings"] == expected
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert report["warnings"] == expected

    def test_clean_pass_says_done(self, http, workdir, capsys):
        (workdir / "literature-domain-1.bib").write_text(bib_entry("ok", doi="10.1/fine"), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        summary = json.loads(out)
        assert summary["status"] == "done" and summary["errors"] == [] and summary["warnings"] == []

    def test_same_work_in_two_domains_acquired_once(self, http, workdir, capsys):
        for i in (1, 2):
            (workdir / f"literature-domain-{i}.bib").write_text(bib_entry(f"g{i}", doi=DOI),
                                                                encoding="utf-8")
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://oa.example/a.pdf", "cc-by")])))
        http.add("https://oa.example/a.pdf", FakeResponse(body=work_pdf()))
        code, out = run(capsys, workdir, "--gaps", "--domains", "2")
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert [e["outcome"] for e in report["entries"]] == ["acquired", "acquired"]
        assert report["entries"][1]["tried"] == [{"source": "store", "outcome": "same_work_as:1/g1"}]
        assert http.urls().count(OA_URL) == 1
        assert not list((workdir / ft.STORE_REL).glob("*.txt"))

    def test_gaps_never_touches_a_bib(self, http, workdir, capsys):
        bib = workdir / "literature-domain-1.bib"
        bib.write_text(bib_entry("g", doi=DOI), encoding="utf-8")
        before = bib.read_bytes()
        run(capsys, workdir, "--gaps", "--domains", "1")
        assert bib.read_bytes() == before
