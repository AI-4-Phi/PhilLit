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
import fulltext_channel as fc  # noqa: E402
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


def write_repo_record(repo_dir, pdf_bytes, identity, *, source, source_ref, license):
    """A repository record (the store's format, plus the rendered text) for
    `identity`; returns its stem."""
    repo_dir = Path(repo_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)
    stem = ft.slug_for(identity)
    (repo_dir / f"{stem}.pdf").write_bytes(pdf_bytes)
    (repo_dir / f"{stem}.txt").write_text(ft.render_text(ft.extract_pages(pdf_bytes), None),
                                          encoding="utf-8")
    side = {"schema": 1, "slug": stem, "identity": identity, "source": source,
            "source_ref": source_ref, "license": license,
            "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "acquired_at": "2026-10-22T00:00:00+00:00"}
    (repo_dir / f"{stem}.json").write_text(json.dumps(side), encoding="utf-8")
    return stem


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
        assert [t["source"] for t in data["tried"]] == ["repository", "zotero", "folder", "openalex", "s2",
                                                       "service"]
        assert data["tried"][-1] == {"source": "service", "outcome": "disabled"}


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

    @pytest.mark.parametrize("lic,policy,ok", [
        ("cc-by", None, True), (None, None, True), ("publisher-specific", None, True),
        ("cc-by", "cc", True), ("CCBY", "cc", True), ("oa:author", "cc", False), (None, "cc", False),
        ("cc-by-nc", "open", True), ("oa:publisher_free", "open", True), ("OA:cc", "open", True),
        ("upload", "open", True), ("Upload ", "open", True), (None, "open", False),
        ("publisher-specific", "open", False), ("", "open", False), (3, "open", False),
    ])
    def test_licence_rule(self, lic, policy, ok):
        assert af._licensed(lic, policy) is ok

    def test_policy_open_from_process_env_admits_oa_locations(self, http, workdir, capsys):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        os.environ["PHILLIT_FULLTEXT_POLICY"] = "open"
        write_env("PHILLIT_FULLTEXT_POLICY=\n")   # .env cannot switch it off
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://pub.example/a.pdf", "oa:publisher_free")])))
        http.add("https://pub.example/a.pdf", FakeResponse(body=work_pdf()))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired"
        assert {t["source"]: t["outcome"] for t in data["tried"]}["zotero"] == "disabled"

    def test_policy_open_in_env_file_is_ignored(self, http, workdir, capsys):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        write_env("PHILLIT_FULLTEXT_POLICY=open\n")
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://pub.example/a.pdf", "oa:author")])))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert {t["source"]: t["outcome"] for t in data["tried"]}["openalex"] == "unlicensed"

    def test_policy_open_alone_keeps_zotero_and_folder(self, http, workdir, capsys, tmp_path):
        os.environ["PHILLIT_FULLTEXT_POLICY"] = "open"
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [work_pdf()])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["source"] == "zotero"

    def test_gaps_report_names_the_policy(self, http, workdir, capsys):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        (workdir / "literature-domain-1.bib").write_text(bib_entry("g", doi=DOI), encoding="utf-8")
        run(capsys, workdir, "--gaps", "--domains", "1")
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert report["policy"] == "cc" and report["licensed_only"] is True


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
        assert [t["source"] for t in data["tried"]] == ["repository", "zotero"]
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
            ("repository", "disabled"), ("zotero", "not_found"), ("folder", "acquired")]
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
        z = data["tried"][1]
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
        assert data["tried"][1]["outcome"] == "unavailable"

    def test_multiple_attachments_first_wins(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        first, second = work_pdf(marker="first copy"), work_pdf(marker="second copy")
        setup_zotero(http, tmp_path, [first, second])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired"
        assert data["tried"][1]["detail"] == ["multiple_candidates:2"]
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
        assert data["tried"][1]["detail"][0].startswith("ATT0:identity_failed")

    def test_all_attachments_fail_is_rejected(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [other_pdf()])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "rejected"
        assert data["tried"][1]["outcome"] == "rejected"

    def test_metadata_mismatch_reads_no_attachment(self, http, workdir, capsys, tmp_path):
        write_env("PHILLIT_ZOTERO=on\n")
        setup_zotero(http, tmp_path, [work_pdf()], items=[zotero_item("PARENT", doi="10.5555/else")])
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][1]["outcome"] == "not_found"
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
        assert data["tried"][1]["outcome"] == "not_found"


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
        folder_try = data["tried"][2]
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
        folder_try = data["tried"][2]
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
        assert data["tried"][2]["outcome"] == "not_found"

    def test_walk_limit(self, http, workdir, capsys, tmp_path, monkeypatch):
        self._folder(tmp_path, {"a.pdf": other_pdf(), "b.pdf": other_pdf(), "c.pdf": work_pdf()})
        monkeypatch.setattr(af, "MAX_WALK_FILES", 2)
        code, data = run_json(capsys, workdir, "--doi", DOI)
        folder_try = data["tried"][2]
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
            folder_try = data["tried"][2]
            assert "walk_error:1" in folder_try["detail"]
            index = json.loads(idx_file.read_text(encoding="utf-8"))
            assert "sub/scan.pdf" in index["files"]   # kept, not dropped
        finally:
            sub.chmod(0o755)

    def test_missing_folder_is_unavailable(self, http, workdir, capsys, tmp_path):
        write_env(f"PHILLIT_PDF_DIR={tmp_path / 'nowhere'}\n")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][2] == {"source": "folder", "outcome": "unavailable",
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
        real = af.begin

        def flaky(wd, ident, settings, deadline, pdf_path=None):
            if ident["doi"] == "10.1/boom":
                raise RuntimeError("kaput")
            return real(wd, ident, settings, deadline, pdf_path)
        monkeypatch.setattr(af, "begin", flaky)
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
        monkeypatch.setattr(af, "begin", boom)
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

    # The service channel in a gap pass: one request for every open entry.

    def test_gaps_sends_one_request_for_every_open_entry(self, http, workdir, capsys, tmp_path, service):
        dois = ["10.1/w0", "10.1/w1", "10.1/w2"]
        repo = tmp_path / "records"
        write_repo_record(repo, work_pdf(doi=dois[0]), af.make_identity(dois[0]), source="user",
                          source_ref="u.pdf", license="upload")
        write_env(f"PHILLIT_FULLTEXT_REQUEST_DIR={service.request_dir}\n"
                  f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        service.answer({d: {"status": "found", "pdf": work_pdf(doi=d)} for d in dois})
        (workdir / "literature-domain-1.bib").write_text(
            "".join(bib_entry(f"k{n}", doi=d) for n, d in enumerate(dois)), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        assert code == 0
        [req] = _request_files(service)
        request = json.loads(req.read_text(encoding="utf-8"))
        assert request["mode"] == "gaps"
        assert [i["key"] for i in request["identities"]] == [f"doi:{d}" for d in dois[1:]]
        assert (service.request_dir / (request["request_id"] + fc.CLOSED_SUFFIX)).exists()
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert report["counts"] == {"acquired": 3}
        assert [e["source"] for e in report["entries"]] == ["repository", "openalex", "openalex"]
        assert list(report["sources"].items()) == [("zotero", "off"), ("folder", "off"),
                                                   ("repository", "on"), ("service", "on")]
        assert http.calls == []

    def test_more_than_fifty_identities_split_into_requests(self, http, workdir, capsys, service):
        dois = [f"10.1/w{n}" for n in range(60)]
        service.answer({d: {"status": "none"} for d in dois})
        (workdir / "literature-domain-1.bib").write_text(
            "".join(bib_entry(f"k{n}", doi=d) for n, d in enumerate(dois)), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        assert json.loads(out)["counts"] == {"not_found": 60}
        requests = [json.loads(p.read_text(encoding="utf-8")) for p in _request_files(service)]
        assert sorted(len(r["identities"]) for r in requests) == [10, 50]
        for r in requests:
            assert (service.request_dir / (r["request_id"] + fc.CLOSED_SUFFIX)).exists()
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert all(_service_tried(e) == {"source": "service", "outcome": "not_found"}
                   for e in report["entries"])

    def test_duplicate_row_copies_the_first_rows_final_outcome(self, http, workdir, capsys, service):
        for i in (1, 2):
            (workdir / f"literature-domain-{i}.bib").write_text(bib_entry(f"g{i}", doi=DOI),
                                                                encoding="utf-8")
        service.answer({DOI: {"status": "found", "pdf": work_pdf()}})
        code, out = run(capsys, workdir, "--gaps", "--domains", "2")
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        first, dup = report["entries"]
        assert (first["outcome"], first["source"]) == ("acquired", "openalex")
        assert (dup["outcome"], dup["source"]) == ("acquired", "openalex")
        assert dup["tried"] == [{"source": "store", "outcome": "same_work_as:1/g1"}]
        [req] = _request_files(service)
        assert [i["key"] for i in json.loads(req.read_text(encoding="utf-8"))["identities"]] == [f"doi:{DOI}"]

    def test_deadline_before_the_request_marks_service_deadline(self, http, workdir, capsys, service,
                                                                 monkeypatch):
        """Both entries are tried locally, and the pass then lies inside the
        wait margin: no request is written."""
        def slow_repository(identity, settings, deadline):
            service.clock[0] += (af.GAPS_DEADLINE - af.SERVICE_WAIT_MARGIN) / 2 + 1
            return af.SourceResult("repository", "not_found")
        monkeypatch.setitem(af._SOURCES, "repository", slow_repository)
        dois = ["10.1/w0", "10.1/w1"]
        service.answer({d: {"status": "found", "pdf": work_pdf(doi=d)} for d in dois})
        (workdir / "literature-domain-1.bib").write_text(
            "".join(bib_entry(f"k{n}", doi=d) for n, d in enumerate(dois)), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert [e["outcome"] for e in report["entries"]] == ["not_found", "not_found"]
        assert all(_service_tried(e) == {"source": "service", "outcome": "deadline"}
                   for e in report["entries"])
        assert _request_files(service) == []
        assert af.GAPS_DEADLINE - af.SERVICE_WAIT_MARGIN < service.clock[0] < af.GAPS_DEADLINE

    def test_finish_crash_is_an_error_row(self, http, workdir, capsys, service, monkeypatch):
        real = af.finish

        def flaky(attempt, svc):
            if attempt.identity["doi"] == "10.1/boom":
                raise RuntimeError("kaput")
            return real(attempt, svc)
        monkeypatch.setattr(af, "finish", flaky)
        service.answer({"10.1/fine": {"status": "found", "pdf": work_pdf(doi="10.1/fine")}})
        (workdir / "literature-domain-1.bib").write_text(
            bib_entry("ok", doi="10.1/fine") + bib_entry("bad", doi="10.1/boom"), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        assert code == 0
        assert json.loads(out)["errors"] == [{"entry": "1/bad", "reason": "error:RuntimeError: kaput"}]
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        ok, bad = report["entries"]
        assert (ok["outcome"], ok["source"]) == ("acquired", "openalex")
        assert bad["outcome"] == "error"
        assert bad["tried"] == [{"source": "pipeline", "outcome": "error:RuntimeError: kaput"}]

    def test_service_crash_is_an_error_row_and_local_hits_stand(self, http, workdir, capsys, tmp_path,
                                                                 service, monkeypatch):
        repo = tmp_path / "records"
        write_repo_record(repo, work_pdf(doi="10.1/w0"), af.make_identity("10.1/w0"), source="user",
                          source_ref="u.pdf", license="upload")
        write_env(f"PHILLIT_FULLTEXT_REQUEST_DIR={service.request_dir}\n"
                  f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")

        def boom(*a, **k):
            raise RuntimeError("kaput")
        monkeypatch.setattr(af, "service_fetch", boom)
        (workdir / "literature-domain-1.bib").write_text(
            bib_entry("k0", doi="10.1/w0") + bib_entry("k1", doi="10.1/w1"), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        assert code == 0
        assert json.loads(out)["errors"] == [{"entry": "1/k1", "reason": "error:RuntimeError: kaput"}]
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        hit, crashed = report["entries"]
        assert (hit["outcome"], hit["source"]) == ("acquired", "repository")
        assert crashed["outcome"] == "error"

    def test_oversize_request_is_unavailable_and_never_written(self, http, workdir, capsys, service,
                                                               monkeypatch):
        monkeypatch.setattr(fc, "MAX_REQUEST_BYTES", 100)
        dois = ["10.1/w0", "10.1/w1"]
        service.answer({d: {"status": "found", "pdf": work_pdf(doi=d)} for d in dois})
        (workdir / "literature-domain-1.bib").write_text(
            "".join(bib_entry(f"k{n}", doi=d) for n, d in enumerate(dois)), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        assert json.loads(out)["counts"] == {"not_found": 2}
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert all(_service_tried(e) == {"source": "service", "outcome": "unavailable",
                                         "detail": ["request_write_failed:request_too_large"]}
                   for e in report["entries"])
        assert _request_files(service) == []


# ---------------------------------------------------------------------------
# The repository source
# ---------------------------------------------------------------------------

OA_REF = {"url": "https://oa.example/a.pdf", "kind": "cc", "service": True}


def _full_args():
    return ("--doi", DOI, "--title", TITLE, "--author", SURNAME, "--year", YEAR)


class TestRepository:
    def test_repository_hit_is_first_and_rewrites_identity(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        write_repo_record(repo, work_pdf(), af.make_identity(DOI), source="openalex",
                          source_ref=OA_REF, license="cc-by")
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\nPHILLIT_ZOTERO=on\n")
        code, data = run_json(capsys, workdir, *_full_args())
        assert data["status"] == "acquired" and data["source"] == "repository"
        assert [t["source"] for t in data["tried"]] == ["repository"]
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.identity == {"doi": DOI, "title": TITLE, "surname": SURNAME, "year": YEAR}
        assert rec.source_ref == {"stem": data["slug"], "source": "openalex", "source_ref": OA_REF}
        assert rec.license == "cc-by" and http.calls == []
        assert not (workdir / ft.STORE_REL / f"{data['slug']}.txt").exists()   # never copied

    def test_repository_unset_is_disabled(self, http, workdir, capsys):
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "disabled"}

    def test_missing_repository_dir_is_unavailable(self, http, workdir, capsys, tmp_path):
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={tmp_path / 'nowhere'}\n")
        http.add(OA_URL, FakeResponse(payload=oa_payload([("https://oa.example/a.pdf", "cc-by")])))
        http.add("https://oa.example/a.pdf", FakeResponse(body=work_pdf()))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "unavailable",
                                    "detail": ["repository_missing"]}
        assert data["status"] == "acquired" and data["source"] == "openalex"

    def test_absent_stem_is_not_found(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        repo.mkdir()
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "not_found"}

    def test_invalid_repository_record_is_not_found_with_reason(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        ident = af.make_identity(DOI)
        stem = write_repo_record(repo, work_pdf(), ident, source="user", source_ref="u.pdf",
                                 license="upload")
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        (repo / f"{stem}.json").write_text("{not json", encoding="utf-8")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "not_found",
                                    "detail": ["invalid:sidecar_unreadable"]}
        write_repo_record(repo, work_pdf(), ident, source="user", source_ref="u.pdf", license="upload")
        (repo / f"{stem}.pdf").write_bytes(work_pdf(marker="tampered"))
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "not_found",
                                    "detail": ["invalid:pdf_hash_mismatch"]}

    def test_repository_record_of_another_work_is_rejected(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        write_repo_record(repo, other_pdf(), af.make_identity(DOI), source="user",
                          source_ref="u.pdf", license="upload")
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        first = data["tried"][0]
        assert first["source"] == "repository" and first["outcome"] == "rejected"
        assert first["detail"][0].startswith("identity_failed:")
        assert data["status"] != "acquired" or data["source"] != "repository"

    def test_repository_licence_backstop(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        write_repo_record(repo, work_pdf(), af.make_identity(DOI), source="openalex",
                          source_ref=OA_REF, license="oa:author")
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "unlicensed",
                                    "detail": ["licence 'oa:author' not admitted by policy"]}
        os.environ["PHILLIT_FULLTEXT_POLICY"] = "open"
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired" and data["source"] == "repository"
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.license == "oa:author"

    def test_repository_shares_the_service_validation_tail(self, http, workdir, capsys, tmp_path,
                                                           monkeypatch):
        """Licence before the read; a valid record that cannot be read is
        unavailable; a repository record is never removed."""
        repo = tmp_path / "records"
        stem = write_repo_record(repo, work_pdf(), af.make_identity(DOI), source="openalex",
                                 source_ref=OA_REF, license="oa:author")
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        monkeypatch.setattr(af, "LOCAL_MAX_BYTES", 10)
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "unlicensed",
                                    "detail": ["licence 'oa:author' not admitted by policy"]}
        del os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"]
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["tried"][0] == {"source": "repository", "outcome": "unavailable",
                                    "detail": ["too_large"]}
        assert sorted(p.name for p in repo.iterdir()) == [f"{stem}.json", f"{stem}.pdf", f"{stem}.txt"]

    def test_repository_without_policy_admits_any_licence(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        write_repo_record(repo, work_pdf(), af.make_identity(DOI), source="openalex",
                          source_ref=OA_REF, license="oa:author")
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired" and data["source"] == "repository"

    def test_no_doi_identity_found_in_repository(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        ident = af.make_identity(None, TITLE, SURNAME, YEAR)
        write_repo_record(repo, work_pdf(doi=None), ident, source="user", source_ref="u.pdf",
                          license="upload")
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        assert data["status"] == "acquired" and data["source"] == "repository"
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.identity == ident

    def test_gaps_no_doi_entries_are_tried_when_a_repository_is_set(self, http, workdir, capsys, tmp_path):
        repo = tmp_path / "records"
        repo.mkdir()
        write_env(f"PHILLIT_FULLTEXT_REPOSITORY_DIR={repo}\n")
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        (workdir / "literature-domain-1.bib").write_text(bib_entry("nodoi"), encoding="utf-8")
        code, out = run(capsys, workdir, "--gaps", "--domains", "1")
        report = json.loads((workdir / af.REPORT_REL).read_text(encoding="utf-8"))
        assert [e["key"] for e in report["entries"]] == ["nodoi"]
        assert report["entries"][0]["tried"][0]["source"] == "repository"
        assert report["sources"]["repository"] == "on"


# ---------------------------------------------------------------------------
# The service source
# ---------------------------------------------------------------------------

SERVICE_REF = {"url": "https://oa.example/a.pdf", "kind": "oa_repository", "service": True}


class FakeWorker:
    """The service worker over a fake clock: `sleep` (patched in as
    `af._sleep`) advances the clock and answers every new request at once,
    copying a record for each `found` that registers a `pdf`."""

    def __init__(self, request_dir, store, clock):
        self.request_dir = Path(request_dir)
        self.store = Path(store)
        self.clock = clock
        self.outcomes = {}
        self.answered = set()

    def answer(self, outcomes_by_doi):
        self.outcomes.update(outcomes_by_doi)

    def sleep(self, seconds):
        self.clock[0] += seconds
        self.tick()

    def tick(self):
        if not self.outcomes:
            return
        for path in sorted(self.request_dir.glob("*" + fc.REQUEST_SUFFIX)):
            request = json.loads(path.read_text(encoding="utf-8"))
            rid = request["request_id"]
            if rid in self.answered:
                continue
            out = {}
            for ident in request["identities"]:
                spec = self.outcomes.get(ident["doi"], {"status": "none"})
                identity = {k: ident[k] for k in ("doi", "title", "surname", "year")}
                stem = spec.get("stem")
                if spec["status"] == "found" and spec.get("pdf") is not None:
                    written = write_repo_record(self.store, spec["pdf"], identity,
                                                source=spec.get("source", "openalex"),
                                                source_ref=spec.get("source_ref", SERVICE_REF),
                                                license=spec.get("license", "cc-by"))
                    stem = stem or written
                out[ident["key"]] = {"status": spec["status"],
                                     "stem": stem or (ft.slug_for(identity) if spec["status"] == "found" else None),
                                     "detail": spec.get("detail")}
            ft.write_text_atomic(self.request_dir / (rid + fc.RESPONSE_SUFFIX),
                                 json.dumps({"schema": 1, "request_id": rid, "complete": True,
                                             "outcomes": out}))
            self.answered.add(rid)


@pytest.fixture
def service(http, workdir, monkeypatch, tmp_path):
    """REQUEST_DIR set in `.env` (created, as the worker does), a fake clock
    and a FakeWorker wired in."""
    now = [0.0]
    monkeypatch.setattr(af, "_clock", lambda: now[0])
    request_dir = tmp_path / "requests"
    request_dir.mkdir()
    worker = FakeWorker(request_dir, workdir / ft.STORE_REL, now)
    monkeypatch.setattr(af, "_sleep", worker.sleep)
    write_env(f"PHILLIT_FULLTEXT_REQUEST_DIR={request_dir}\n")
    return worker


def _service_tried(data):
    return next(t for t in data["tried"] if t["source"] == "service")


def _request_files(worker):
    return sorted(worker.request_dir.glob("*" + fc.REQUEST_SUFFIX)) if worker.request_dir.exists() else []


class TestService:
    def test_service_replaces_open_access_and_validates_the_copy(self, http, workdir, capsys, service):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        os.environ["PHILLIT_FULLTEXT_POLICY"] = "open"
        service.answer({DOI: {"status": "found", "pdf": work_pdf(), "source": "openalex",
                              "source_ref": SERVICE_REF, "license": "oa:oa_repository"}})
        code, data = run_json(capsys, workdir, *_full_args())
        assert code == 0
        assert data["status"] == "acquired" and data["source"] == "openalex"
        assert data["tried"] == [
            {"source": "repository", "outcome": "disabled"},
            {"source": "zotero", "outcome": "disabled", "detail": ["licensed_only"]},
            {"source": "folder", "outcome": "disabled", "detail": ["licensed_only"]},
            {"source": "openalex", "outcome": "disabled", "detail": ["service"]},
            {"source": "s2", "outcome": "disabled", "detail": ["service"]},
            {"source": "service", "outcome": "acquired"}]
        assert http.calls == []
        [req] = _request_files(service)
        rid = req.name[:-len(fc.REQUEST_SUFFIX)]
        assert (service.request_dir / (rid + fc.CLOSED_SUFFIX)).exists()
        assert json.loads(req.read_text(encoding="utf-8")) == {
            "schema": 1, "request_id": rid, "mode": "single",
            "identities": [{"key": f"doi:{DOI}", "doi": DOI, "title": TITLE,
                            "surname": SURNAME, "year": YEAR}]}
        rec = ft.validate_record(workdir / ft.STORE_REL, data["slug"])
        assert rec.identity == {"doi": DOI, "title": TITLE, "surname": SURNAME, "year": YEAR}
        assert (rec.source, rec.source_ref, rec.license) == ("openalex", SERVICE_REF, "oa:oa_repository")

    def test_service_never_sends_a_url_or_a_no_doi_identity(self, http, workdir, capsys, service):
        service.answer({DOI: {"status": "found", "pdf": work_pdf()}})
        code, data = run_json(capsys, workdir, "--title", TITLE, "--author", SURNAME, "--year", YEAR)
        assert _service_tried(data) == {"source": "service", "outcome": "no_doi"}
        outcomes = {t["source"]: t for t in data["tried"]}
        assert outcomes["openalex"] == {"source": "openalex", "outcome": "disabled", "detail": ["service"]}
        assert data["status"] == "not_found"
        assert _request_files(service) == [] and http.calls == []

    @pytest.mark.parametrize("status, detail, outcome, details", [
        ("none", None, "not_found", []),
        ("none", "no_doi", "no_doi", []),
        ("unlicensed", None, "unlicensed", []),
        ("failed", "identity_rejected", "rejected", ["identity_rejected"]),
        ("failed", "timeout", "not_found", ["timeout"]),
        ("failed", "budget", "unavailable", ["budget"]),
    ])
    def test_none_and_failed_outcomes_map(self, http, workdir, capsys, service, status, detail,
                                          outcome, details):
        service.answer({DOI: {"status": status, "detail": detail}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        expected = {"source": "service", "outcome": outcome}
        if details:
            expected["detail"] = details
        assert _service_tried(data) == expected
        assert data["status"] == ("rejected" if outcome == "rejected" else "not_found")

    def test_deadline_when_the_worker_never_answers(self, http, workdir, capsys, service):
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert code == 0
        assert _service_tried(data) == {"source": "service", "outcome": "deadline"}
        assert data["status"] == "not_found"
        [req] = _request_files(service)
        rid = req.name[:-len(fc.REQUEST_SUFFIX)]
        assert (service.request_dir / (rid + fc.CLOSED_SUFFIX)).exists()
        assert (af.SINGLE_DEADLINE - af.SERVICE_WAIT_MARGIN <= service.clock[0]
                < af.SINGLE_DEADLINE - af.SERVICE_WAIT_MARGIN + fc.POLL_SECONDS)

    @pytest.mark.parametrize("copy, reason", [("none", "sidecar_unreadable"),
                                              ("sidecar_only", "pdf_missing")])
    def test_found_without_a_copy_is_unavailable(self, http, workdir, capsys, service, monkeypatch,
                                                 copy, reason):
        if copy == "none":
            service.answer({DOI: {"status": "found"}})
        else:
            service.answer({DOI: {"status": "found", "pdf": work_pdf()}})

            def sleep(seconds):   # the worker died between the PDF and the sidecar
                service.sleep(seconds)
                for p in (workdir / ft.STORE_REL).glob("*.pdf"):
                    p.unlink()
            monkeypatch.setattr(af, "_sleep", sleep)
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert _service_tried(data) == {"source": "service", "outcome": "unavailable",
                                        "detail": [f"copy_invalid:{reason}"]}
        assert data["status"] == "not_found"

    def test_unlicensed_copy_is_removed_by_the_backstop(self, http, workdir, capsys, service):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        service.answer({DOI: {"status": "found", "pdf": work_pdf(), "license": "oa:author"}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert _service_tried(data) == {"source": "service", "outcome": "unlicensed",
                                        "detail": ["licence 'oa:author' not admitted by policy"]}
        assert data["status"] == "not_found"
        assert list((workdir / ft.STORE_REL).iterdir()) == []

    def test_backstop_runs_before_the_copy_is_read(self, http, workdir, capsys, service, monkeypatch):
        """An unlicensed copy is removed even when it could not be read."""
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        monkeypatch.setattr(af, "LOCAL_MAX_BYTES", 10)
        service.answer({DOI: {"status": "found", "pdf": work_pdf(), "license": "oa:author"}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert _service_tried(data) == {"source": "service", "outcome": "unlicensed",
                                        "detail": ["licence 'oa:author' not admitted by policy"]}
        assert list((workdir / ft.STORE_REL).iterdir()) == []

    def test_unreadable_valid_copy_is_removed(self, http, workdir, capsys, service, monkeypatch):
        monkeypatch.setattr(af, "LOCAL_MAX_BYTES", 10)
        service.answer({DOI: {"status": "found", "pdf": work_pdf()}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert _service_tried(data) == {"source": "service", "outcome": "unavailable",
                                        "detail": ["too_large", "removed_copy"]}
        assert data["status"] == "not_found"
        assert list((workdir / ft.STORE_REL).iterdir()) == []

    def test_copy_of_another_work_is_rejected_and_removed(self, http, workdir, capsys, service):
        service.answer({DOI: {"status": "found", "pdf": other_pdf()}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        tried = _service_tried(data)
        assert tried["outcome"] == "rejected" and tried["detail"][0].startswith("identity_failed:")
        assert data["status"] == "rejected"
        assert list((workdir / ft.STORE_REL).iterdir()) == []

    @pytest.mark.parametrize("pdf, status, outcome, details", [
        (work_pdf(), "acquired", "acquired", ["stem_mismatch"]),
        (None, "not_found", "unavailable", ["stem_mismatch", "copy_invalid:sidecar_unreadable"]),
    ])
    def test_stem_mismatch_is_a_detail_not_a_gate(self, http, workdir, capsys, service, pdf, status,
                                                  outcome, details):
        """The record at OUR slug is checked whatever stem the response names."""
        service.answer({DOI: {"status": "found", "stem": "doi-10.9999_x-000000000000", "pdf": pdf}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert _service_tried(data) == {"source": "service", "outcome": outcome, "detail": details}
        assert data["status"] == status

    def test_stem_mismatch_copy_still_meets_the_backstop(self, http, workdir, capsys, service):
        os.environ["PHILLIT_FULLTEXT_LICENSED_ONLY"] = "1"
        service.answer({DOI: {"status": "found", "stem": "doi-10.9999_x-000000000000",
                              "pdf": work_pdf(), "license": "oa:author"}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert _service_tried(data) == {"source": "service", "outcome": "unlicensed",
                                        "detail": ["stem_mismatch",
                                                   "licence 'oa:author' not admitted by policy"]}
        assert list((workdir / ft.STORE_REL).iterdir()) == []

    def test_field_too_long_is_unavailable_and_never_sent(self, http, workdir, capsys, service):
        code, data = run_json(capsys, workdir, "--doi", DOI, "--title", "x" * 501,
                              "--author", SURNAME, "--year", YEAR)
        assert _service_tried(data) == {"source": "service", "outcome": "unavailable",
                                        "detail": ["field_too_long"]}
        assert _request_files(service) == []

    def test_closed_write_failure_is_a_detail_and_the_outcome_stands(self, http, workdir, capsys,
                                                                       service, monkeypatch):
        def refuse(*a, **k):
            raise OSError("read-only")
        monkeypatch.setattr(af.fc, "write_closed", refuse)
        service.answer({DOI: {"status": "found", "pdf": work_pdf()}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert _service_tried(data) == {"source": "service", "outcome": "acquired",
                                        "detail": ["closed_write_failed:OSError"]}
        assert data["status"] == "acquired" and data["source"] == "openalex"

    def test_unwritable_request_dir_is_unavailable_not_a_crash(self, http, workdir, capsys, tmp_path):
        blocker = tmp_path / "a-file"
        blocker.write_text("", encoding="utf-8")
        write_env(f"PHILLIT_FULLTEXT_REQUEST_DIR={blocker}\n")
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert code == 0
        tried = _service_tried(data)
        assert tried["outcome"] == "unavailable" and len(tried["detail"]) == 1
        assert tried["detail"][0].startswith("request_write_failed:")
        assert data["status"] == "not_found"

    def test_local_sources_before_the_service(self, http, workdir, capsys, tmp_path, service):
        setup_zotero(http, tmp_path, [work_pdf()])
        write_env(f"PHILLIT_FULLTEXT_REQUEST_DIR={service.request_dir}\nPHILLIT_ZOTERO=on\n")
        service.answer({DOI: {"status": "found", "pdf": work_pdf()}})
        code, data = run_json(capsys, workdir, "--doi", DOI)
        assert data["status"] == "acquired" and data["source"] == "zotero"
        assert [t["source"] for t in data["tried"]] == ["repository", "zotero"]
        assert _request_files(service) == []

    def test_user_pdf_skips_the_service(self, http, workdir, capsys, tmp_path, service):
        p = tmp_path / "mine.pdf"
        p.write_bytes(work_pdf())
        service.answer({DOI: {"status": "found", "pdf": work_pdf()}})
        code, data = run_json(capsys, workdir, "--doi", DOI, "--pdf", p)
        assert data["status"] == "acquired" and data["source"] == "user"
        assert data["tried"] == [{"source": "user", "outcome": "acquired"}]
        assert _request_files(service) == []
