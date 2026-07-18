"""A3: union of JSON dirs, salvage of log-polluted verify JSON, surfaced skips."""
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
FIXTURES = Path(__file__).parent / "fixtures" / "item13"
sys.path.insert(0, str(HOOKS_DIR))

import metadata_cleaner as mc  # noqa: E402


def test_salvage_recovers_real_polluted_object():
    txt = (FIXTURES / "verify_amorosotamburrini2017.json").read_text(encoding="utf-8")
    obj = mc._salvage_json(txt)
    assert obj is not None and obj["results"][0]["doi"] == "10.1515/gj-2017-0012"


def test_salvage_survives_brace_in_prefix():
    txt = (FIXTURES / "verify_brace_in_prefix.json").read_text(encoding="utf-8")
    obj = mc._salvage_json(txt)
    assert obj is not None and obj["results"][0]["container_title"] == "Global Jurist"


def test_salvage_rejects_truncated():
    txt = (FIXTURES / "verify_truncated.json").read_text(encoding="utf-8")
    assert mc._salvage_json(txt) is None


def test_salvage_skips_fragment_without_results_key():
    txt = (FIXTURES / "verify_fragment_before_object.json").read_text(encoding="utf-8")
    obj = mc._salvage_json(txt)
    assert obj is not None and obj["results"][0]["doi"] == "10.1000/xyz"


def test_build_index_salvages_and_records(tmp_path):
    jdir = tmp_path / "json"
    jdir.mkdir()
    (jdir / "verify_a.json").write_text(
        (FIXTURES / "verify_amorosotamburrini2017.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (jdir / "verify_trunc.json").write_text(
        (FIXTURES / "verify_truncated.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    index = mc.build_metadata_index(jdir)
    assert "verify_a.json" in index.salvaged_files
    assert "verify_trunc.json" in index.skipped_files
    assert mc.normalize_doi("10.1515/gj-2017-0012") in index.dois


def test_build_index_union(tmp_path):
    d1 = tmp_path / "root"; d1.mkdir()
    d2 = tmp_path / "json"; d2.mkdir()
    (d1 / "s2.json").write_text(
        '{"source":"s2","results":[{"journal":{"name":"Journal A"},"year":2020}]}',
        encoding="utf-8")
    (d2 / "verify.json").write_text(
        (FIXTURES / "verify_amorosotamburrini2017.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    index = mc.build_metadata_index([d1, d2])
    assert mc.normalize_journal("Journal A") in index.journals          # from d1
    assert mc.normalize_journal("Global Jurist") in index.journals      # from salvaged d2


def test_clean_bibtex_surfaces_skips_and_salvage(tmp_path):
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "verify_a.json").write_text(
        (FIXTURES / "verify_amorosotamburrini2017.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    (jdir / "verify_trunc.json").write_text(
        (FIXTURES / "verify_truncated.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    bib = tmp_path / "d.bib"
    bib.write_text('@article{k, author="A, B", title="T", journal="J", year="2020"}\n',
                   encoding="utf-8")
    # list form
    res = mc.clean_bibtex(bib, [jdir])
    assert res["salvaged_files"] == ["verify_a.json"]
    assert res["skipped_files"] == ["verify_trunc.json"]
    assert any("Salvaged" in w for w in res["warnings"])
    assert any("Skipped" in w for w in res["warnings"])
    # single-Path back-compat form still works
    res2 = mc.clean_bibtex(bib, jdir)
    assert res2["success"] is True


def test_clean_bibtex_no_json_dirs_counts_entries_unmatched(tmp_path):
    # B1: with NO json dirs, still PARSE + count — never a silent no-op.
    bib = tmp_path / "d.bib"
    bib.write_text(
        '@article{a, author="A, B", title="T1", journal="J", year="2020"}\n'
        '@article{b, author="C, D", title="T2", journal="K", year="2021"}\n',
        encoding="utf-8",
    )
    before = bib.read_text(encoding="utf-8")
    res = mc.clean_bibtex(bib, [])
    assert res["entries_total"] == 2
    assert res["unmatched_entries"] == 2
    assert res["matched_entries"] == 0
    assert res["total_fields_removed"] == 0
    assert bib.read_text(encoding="utf-8") == before  # no mutation, no marker
    assert "METADATA" not in bib.read_text(encoding="utf-8")


def test_clean_bibtex_all_unparseable_counts_entries_unmatched(tmp_path):
    # B1: a dir whose only JSON is unsalvageable -> empty index -> still count.
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "verify_trunc.json").write_text(
        (FIXTURES / "verify_truncated.json").read_text(encoding="utf-8"), encoding="utf-8")
    bib = tmp_path / "d.bib"
    bib.write_text('@article{a, author="A, B", title="T1", journal="J", year="2020"}\n',
                   encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    assert res["entries_total"] == 1
    assert res["unmatched_entries"] == 1
    assert res["matched_entries"] == 0
    assert "verify_trunc.json" in res["skipped_files"]


def test_clean_bibtex_zero_results_counts_entries_unmatched(tmp_path):
    # B1: a parseable JSON that legitimately holds zero results -> count.
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "s2.json").write_text('{"source": "s2", "results": []}', encoding="utf-8")
    bib = tmp_path / "d.bib"
    bib.write_text('@article{a, author="A, B", title="T1", journal="J", year="2020"}\n',
                   encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    assert res["entries_total"] == 1
    assert res["unmatched_entries"] == 1
    assert res["matched_entries"] == 0
