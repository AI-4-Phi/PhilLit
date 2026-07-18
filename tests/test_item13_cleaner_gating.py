"""A4: entry-scoped gating, @article no-demote guard, circuit breaker."""
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import metadata_cleaner as mc  # noqa: E402
from pybtex.database import parse_file, parse_string  # noqa: E402


def _crossref_json(results):
    import json
    return json.dumps({"source": "crossref", "results": results})


def _index_from_results(tmp_path, results):
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "c.json").write_text(_crossref_json(results), encoding="utf-8")
    return mc.build_metadata_index(jdir)


def _entry(bibtext, key="k"):
    return parse_string(bibtext, "bibtex").entries[key]


def test_unmatched_entry_left_untouched(tmp_path):
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "c.json").write_text(_crossref_json([
        {"doi": "10.1/aaa", "title": "Some Paper", "container_title": "Real Journal",
         "volume": "1", "page": "1-2", "year": 2020}
    ]), encoding="utf-8")
    bib = tmp_path / "d.bib"
    # entry has NO doi and a title that matches nothing -> unmatched -> untouched
    bib.write_text(
        '@article{k, author="X, Y", title="Totally Unrelated", '
        'journal="Bogus Journal", year="1999"}\n', encoding="utf-8")
    before = bib.read_text(encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    assert res["unmatched_entries"] == 1
    assert res["matched_entries"] == 0
    assert bib.read_text(encoding="utf-8") == before  # not rewritten
    assert "Bogus Journal" in bib.read_text(encoding="utf-8")


def test_matched_entry_keeps_verified_strips_hallucinated(tmp_path):
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "verify_k.json").write_text(_crossref_json([
        {"doi": "10.1/aaa", "title": "Some Paper", "container_title": "Real Journal",
         "volume": "12", "issue": "", "page": "5-9", "year": 2020}
    ]), encoding="utf-8")
    bib = tmp_path / "d.bib"
    bib.write_text(
        '@article{k, author="X, Y", title="Some Paper", journal="Real Journal", '
        'year="2020", volume="12", number="99", pages="5--9", doi="10.1/aaa"}\n',
        encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    assert res["matched_entries"] == 1
    out = bib.read_text(encoding="utf-8")
    assert "Real Journal" in out and "10.1/aaa" in out and "5--9" in out  # kept
    # ADV-A3: assert on PARSED fields — the cleaner writes "METADATA_CLEANED:
    # number" into keywords, so a raw substring check would false-fail.
    fields = {c.lower() for c in parse_file(str(bib), bib_format="bibtex").entries["k"].fields}
    assert "number" not in fields                                        # hallucinated, stripped
    assert "@article" in out                                            # journal survived, no demote


def test_article_no_demote_when_matched_doi_retained(tmp_path):
    # journal is hallucinated (removed) but a matched DOI survives -> stay @article
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "verify_k.json").write_text(_crossref_json([
        {"doi": "10.1/bbb", "title": "Gap Paper", "container_title": "Right Journal",
         "volume": "34", "page": "1057-1084", "year": 2021}
    ]), encoding="utf-8")
    bib = tmp_path / "d.bib"
    bib.write_text(
        '@article{s, author="Santoni, F", title="Gap Paper", '
        'journal="Wrong Journal", year="2021", volume="34", '
        'pages="1057--1084", doi="10.1/bbb"}\n', encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    out = bib.read_text(encoding="utf-8")
    assert "Wrong Journal" not in out          # hallucinated journal stripped
    assert "10.1/bbb" in out                    # DOI kept
    assert "@article" in out                    # NOT demoted (A4.2 @article guard)
    assert "@misc" not in out


def test_circuit_breaker_writes_nothing(tmp_path):
    jdir = tmp_path / "json"; jdir.mkdir()
    results = [{"doi": f"10.1/{i}", "title": f"P{i}", "container_title": "J",
                "year": 2020} for i in range(6)]
    (jdir / "c.json").write_text(_crossref_json(results), encoding="utf-8")
    entries = "".join(
        f'@article{{k{i}, author="A, B", title="P{i}", journal="J", '
        f'year="2020", number="99", doi="10.1/{i}"}}\n' for i in range(6))
    bib = tmp_path / "d.bib"
    bib.write_text(entries, encoding="utf-8")
    before = bib.read_text(encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    assert res["breaker_tripped"] is True
    assert res["total_fields_removed"] == 0
    assert bib.read_text(encoding="utf-8") == before   # wrote NOTHING
    assert any("breaker" in w.lower() for w in res["warnings"])
    # B2: the aborted plan is recorded by field name even though applied_* == 0.
    assert res["planned_fields_removed_by_name"].get("number") == 6
    assert res["applied_entries_cleaned"] == 0


def test_breaker_not_tripped_below_min_entries(tmp_path):
    jdir = tmp_path / "json"; jdir.mkdir()
    results = [{"doi": f"10.1/{i}", "title": f"P{i}", "container_title": "J",
                "year": 2020} for i in range(3)]
    (jdir / "c.json").write_text(_crossref_json(results), encoding="utf-8")
    entries = "".join(
        f'@article{{k{i}, author="A, B", title="P{i}", journal="J", '
        f'year="2020", number="99", doi="10.1/{i}"}}\n' for i in range(3))
    bib = tmp_path / "d.bib"
    bib.write_text(entries, encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    assert res["breaker_tripped"] is False
    assert res["total_fields_removed"] == 3   # each lost its bogus number
    # ADV-A3: parse the fields — "number" survives as a keywords marker token.
    out = parse_file(str(bib), bib_format="bibtex")
    for i in range(3):
        assert "number" not in {c.lower() for c in out.entries[f"k{i}"].fields}


def test_find_api_entry_matches_by_title_year(tmp_path):
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "c.json").write_text(_crossref_json([
        {"doi": "10.1/zzz", "title": "The Same Paper!", "container_title": "J",
         "year": 2019}
    ]), encoding="utf-8")
    index = mc.build_metadata_index(jdir)
    from pybtex.database import parse_string
    e = parse_string('@article{k, author="A, B", title="the same paper", year="2019"}\n',
                     "bibtex").entries["k"]
    api = mc.find_api_entry_for_bib_entry(e, index)
    assert api is not None and api["doi"] == "10.1/zzz"


# --- B3: Unicode-aware title normalization + strict title+year fallback ---

def test_normalize_title_folds_accents_keeps_non_latin_nonempty():
    assert mc._normalize_title("café") == mc._normalize_title("cafe")   # accents folded
    assert mc._normalize_title("Λόγος").strip() != ""                    # Greek must not vanish


def test_normalize_title_distinguishes_stroke_letters():
    # ASCII folding drops Đ/Ł entirely (both -> "bar"); Unicode-aware keeps them.
    assert mc._normalize_title("Đ Bar") != mc._normalize_title("Ł Bar")


def test_title_year_no_match_when_api_year_missing(tmp_path):
    idx = _index_from_results(tmp_path, [
        {"doi": "10.1/z", "title": "Same Title", "container_title": "J"}])  # NO year
    e = _entry('@article{k, author="A,B", title="Same Title", year="2019"}\n')
    assert mc.find_api_entry_for_bib_entry(e, idx) is None


def test_title_year_no_match_when_bib_year_missing(tmp_path):
    idx = _index_from_results(tmp_path, [
        {"doi": "10.1/z", "title": "Same Title", "container_title": "J", "year": 2019}])
    e = _entry('@article{k, author="A,B", title="Same Title"}\n')  # NO year
    assert mc.find_api_entry_for_bib_entry(e, idx) is None


def test_title_year_no_match_when_years_differ(tmp_path):
    idx = _index_from_results(tmp_path, [
        {"doi": "10.1/z", "title": "Same Title", "container_title": "J", "year": 2019}])
    e = _entry('@article{k, author="A,B", title="Same Title", year="2020"}\n')
    assert mc.find_api_entry_for_bib_entry(e, idx) is None


def test_title_match_no_collision_across_stroke_letters(tmp_path):
    # ASCII folding would collide "Đ Bar"/"Ł Bar" (both -> "bar"); Unicode won't.
    idx = _index_from_results(tmp_path, [
        {"doi": "10.1/z", "title": "Ł Bar", "container_title": "J", "year": 2020}])
    assert mc.find_api_entry_for_bib_entry(
        _entry('@article{k, author="A,B", title="Đ Bar", year="2020"}\n'), idx) is None
    # sanity: the SAME stroke letter DOES match (title+year fallback)
    api = mc.find_api_entry_for_bib_entry(
        _entry('@article{k, author="A,B", title="Ł Bar", year="2020"}\n'), idx)
    assert api is not None and api["doi"] == "10.1/z"


def test_greek_title_matches_same_greek_title(tmp_path):
    idx = _index_from_results(tmp_path, [
        {"doi": "10.1/g", "title": "Λόγος καὶ Ἀλήθεια", "container_title": "J",
         "year": 2018}])
    api = mc.find_api_entry_for_bib_entry(
        _entry('@article{k, author="A,B", title="Λόγος καὶ Ἀλήθεια", year="2018"}\n'), idx)
    assert api is not None and api["doi"] == "10.1/g"


# --- SF11: circuit-breaker boundary table + container-type demotion ---

@pytest.mark.parametrize("n_strip,total,expect_trip", [
    (6, 20, False),   # exactly 30% (>=5) -> NOT > 30% -> no trip
    (4, 10, False),   # > 30% but only 4 stripped -> below min -> no trip
    (5, 10, True),    # >=5 AND > 30% -> TRIP
    (5, 17, False),   # >=5 but 5/17 == 29.4% (not > 30%) -> no trip
])
def test_breaker_boundaries(tmp_path, n_strip, total, expect_trip):
    jdir = tmp_path / "json"; jdir.mkdir()
    # every entry matches its API record by DOI; exactly n_strip carry a
    # hallucinated `number` (absent from the API record) so exactly n_strip
    # entries would be stripped.
    results = [{"doi": f"10.1/{i}", "title": f"P{i}", "container_title": "J",
                "volume": "1", "year": 2020} for i in range(total)]
    (jdir / "c.json").write_text(_crossref_json(results), encoding="utf-8")
    entries = []
    for i in range(total):
        extra = ' number="99",' if i < n_strip else ''
        entries.append(
            f'@article{{k{i}, author="A, B", title="P{i}", journal="J", '
            f'year="2020", volume="1",{extra} doi="10.1/{i}"}}\n')
    bib = tmp_path / "d.bib"
    bib.write_text("".join(entries), encoding="utf-8")
    before = bib.read_text(encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    assert res["breaker_tripped"] is expect_trip
    if expect_trip:
        assert res["total_fields_removed"] == 0
        assert bib.read_text(encoding="utf-8") == before           # wrote NOTHING
        assert res["planned_fields_removed_by_name"].get("number") == n_strip
        assert res["applied_entries_cleaned"] == 0
    else:
        assert res["total_fields_removed"] == n_strip


def test_incollection_demotes_even_with_matched_doi(tmp_path):
    # A DOI-bearing @incollection that loses booktitle STILL demotes — the
    # no-demote guard is @article-only (SF11 container negative).
    jdir = tmp_path / "json"; jdir.mkdir()
    (jdir / "c.json").write_text(_crossref_json([
        {"doi": "10.1/inc", "title": "Chapter X", "container_title": "Real Anthology",
         "year": 2020}]), encoding="utf-8")
    bib = tmp_path / "d.bib"
    bib.write_text(
        '@incollection{c, author="A, B", title="Chapter X", '
        'booktitle="Bogus Anthology", year="2020", doi="10.1/inc"}\n', encoding="utf-8")
    res = mc.clean_bibtex(bib, [jdir])
    out = bib.read_text(encoding="utf-8")
    assert "Bogus Anthology" not in out          # hallucinated booktitle stripped
    assert "10.1/inc" in out                      # DOI kept (identity preserved)
    assert "@misc" in out                         # DEMOTED — guard is @article-only
    assert res["types_downgraded"] == 1
