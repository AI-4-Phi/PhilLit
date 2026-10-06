"""Enrichment tries the next abstract source when one is unusable.

The usability screen (abstract_usability.unusable_reason) used to run only
at the barrier, after the one source enrichment had kept. A work whose first
source served a stub lost EVIDENCE-ABSTRACT although a later source held a
usable abstract.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "skills" / "philosophy-research" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "literature-review" / "scripts"))
import get_abstract  # noqa: E402
import enrich_bibliography as eb  # noqa: E402
import stamp_evidence as se  # noqa: E402

STUB = "Freedom of the Will and the Concept of a Person. Frankfurt. Journal of Philosophy."
GOOD = ("Frankfurt argues that persons are distinguished by second-order volitions: "
        "they want certain desires to move them to act. Freedom of the will is the "
        "conformity of the will to those volitions, which explains why a willing "
        "addict differs from an unwilling one and why moral responsibility does not "
        "require the ability to have done otherwise.")
ENTRY = """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {Journal of Philosophy},
  year = {1971},
  doi = {10.2307/2024717},
  keywords = {free-will, High}
}"""


def _sources(monkeypatch, s2, openalex, core=None):
    monkeypatch.setattr(get_abstract, "get_abstract_from_s2", lambda **k: s2)
    monkeypatch.setattr(get_abstract, "get_abstract_from_openalex", lambda *a, **k: openalex)
    monkeypatch.setattr(get_abstract, "get_abstract_from_core", lambda **k: core)


def _usable(text):
    return eb.unusable_reason(text, eb.parse_bibtex_entries(ENTRY)[0]["fields"]) is None


def test_the_stub_and_the_good_text_are_what_the_screen_says():
    assert not _usable(STUB) and _usable(GOOD)


def test_an_unusable_source_falls_through_to_the_next(monkeypatch):
    _sources(monkeypatch, STUB, GOOD)
    assert get_abstract.resolve_abstract(doi="10.2307/2024717", accept=_usable) == (GOOD, "openalex")


def test_without_accept_the_first_source_wins_as_before(monkeypatch):
    _sources(monkeypatch, STUB, GOOD)
    assert get_abstract.resolve_abstract(doi="10.2307/2024717") == (STUB, "s2")


def test_when_every_source_is_unusable_the_first_is_kept(monkeypatch):
    _sources(monkeypatch, STUB, STUB + " Again.", core=None)
    assert get_abstract.resolve_abstract(doi="10.2307/2024717", accept=_usable) == (STUB, "s2")


def test_enrichment_keeps_the_usable_source_and_attests_it(monkeypatch):
    _sources(monkeypatch, STUB, GOOD)
    writes = {}
    text, enriched, source = eb.enrich_entry(eb.parse_bibtex_entries(ENTRY)[0],
                                             None, None, None, ledger_writes=writes)
    assert enriched and source == "openalex" and "second-order volitions" in text
    assert writes["frankfurt1971freedom"] == {"abstract_source": "openalex",
                                              "abstract_sha256": se.abstract_hash(GOOD)}


def test_a_prefilled_unusable_abstract_is_replaced_by_a_usable_source(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, GOOD)
    bib = tmp_path / "literature-domain-1.bib"
    bib.write_text(ENTRY.replace("doi = {10.2307/2024717},",
                                 "doi = {10.2307/2024717},\n  abstract = {" + STUB + "},"),
                   encoding="utf-8")
    stats = eb.enrich_bibliography(bib, None, None, None, None)
    out = bib.read_text(encoding="utf-8")
    assert "second-order volitions" in out and "abstract_source = {openalex}" in out
    ledger = json.loads((tmp_path / "intermediate_files" / "json" /
                         "enrichment_ledger-literature-domain-1.json").read_text(encoding="utf-8"))
    assert ledger["entries"]["frankfurt1971freedom"]["abstract_sha256"] == se.abstract_hash(GOOD)
    assert stats["unusable_replaced"] == 1


def test_a_book_whose_sources_are_all_unusable_tries_ndpr(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, None)
    monkeypatch.setattr(eb, "resolve_ndpr_abstract", lambda title, author=None, debug=False: (GOOD, "ndpr"))
    bib = tmp_path / "literature-domain-1.bib"
    bib.write_text(ENTRY.replace("@article", "@book").replace("journal =", "publisher ="),
                   encoding="utf-8")
    eb.enrich_bibliography(bib, None, None, None, None)
    out = bib.read_text(encoding="utf-8")
    assert "second-order volitions" in out and "abstract_source = {ndpr}" in out
    assert out.count("abstract =") == 1


def _book(tmp_path, extra=""):
    bib = tmp_path / "literature-domain-1.bib"
    bib.write_text(ENTRY.replace("@article", "@book").replace("journal =", "publisher =")
                   .replace("doi = {10.2307/2024717},", "doi = {10.2307/2024717}," + extra),
                   encoding="utf-8")
    return bib


def test_a_prefilled_book_stub_with_no_usable_api_text_tries_ndpr(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, None)
    monkeypatch.setattr(eb, "resolve_ndpr_abstract", lambda title, author=None, debug=False: (GOOD, "ndpr"))
    bib = _book(tmp_path, "\n  abstract = {" + STUB + "},")
    stats = eb.enrich_bibliography(bib, None, None, None, None)
    out = bib.read_text(encoding="utf-8")
    assert "second-order volitions" in out and "abstract_source = {ndpr}" in out
    assert out.count("abstract =") == 1 and stats["sources"]["ndpr"] == 1


def test_a_replacement_drops_the_incomplete_keywords_and_counts_the_final_source(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, GOOD)
    bib = tmp_path / "literature-domain-1.bib"
    bib.write_text(ENTRY.replace("doi = {10.2307/2024717},",
                                 "doi = {10.2307/2024717},\n  abstract = {" + STUB + "},")
                   .replace("{free-will, High}", "{free-will, High, INCOMPLETE, no-abstract}"),
                   encoding="utf-8")
    stats = eb.enrich_bibliography(bib, None, None, None, None)
    out = bib.read_text(encoding="utf-8")
    fields = eb.parse_bibtex_entries(out)[0]["fields"]
    assert "INCOMPLETE" not in fields["keywords"] and "no-abstract" not in fields["keywords"]
    assert out.count("abstract =") == 1 and out.count("abstract_source =") == 1
    assert stats["sources"]["openalex"] == 1


def test_ndpr_replacing_an_api_stub_moves_the_source_count(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, None)
    monkeypatch.setattr(eb, "resolve_ndpr_abstract", lambda title, author=None, debug=False: (GOOD, "ndpr"))
    stats = eb.enrich_bibliography(_book(tmp_path), None, None, None, None)
    assert stats["sources"]["s2"] == 0 and stats["sources"]["ndpr"] == 1


def test_a_low_importance_book_stub_does_not_try_ndpr(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, None)
    calls = []   # the NDPR pass swallows exceptions, so record calls instead
    monkeypatch.setattr(eb, "resolve_ndpr_abstract",
                        lambda *a, **k: calls.append(a) or (GOOD, "ndpr"))
    bib = _book(tmp_path)
    bib.write_text(bib.read_text(encoding="utf-8").replace("High", "Low"), encoding="utf-8")
    eb.enrich_bibliography(bib, None, None, None, None)
    assert calls == []


def test_an_unusable_ndpr_text_keeps_the_api_text(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, None)
    monkeypatch.setattr(eb, "resolve_ndpr_abstract",
                        lambda title, author=None, debug=False: (STUB + " Reviewed.", "ndpr"))
    bib = _book(tmp_path)
    eb.enrich_bibliography(bib, None, None, None, None)
    out = bib.read_text(encoding="utf-8")
    assert "abstract_source = {s2}" in out and out.count("abstract =") == 1


def test_an_ndpr_rescue_of_a_prefilled_stub_drops_the_incomplete_keywords(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, None)
    monkeypatch.setattr(eb, "resolve_ndpr_abstract", lambda title, author=None, debug=False: (GOOD, "ndpr"))
    bib = _book(tmp_path, "\n  abstract = {" + STUB + "},")
    bib.write_text(bib.read_text(encoding="utf-8").replace("{free-will, High}",
                                                           "{free-will, High, INCOMPLETE, no-abstract}"),
                   encoding="utf-8")
    eb.enrich_bibliography(bib, None, None, None, None)
    kw = eb.parse_bibtex_entries(bib.read_text(encoding="utf-8"))[0]["fields"]["keywords"]
    assert "INCOMPLETE" not in kw and "no-abstract" not in kw


def test_a_usable_prefilled_abstract_triggers_no_search(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(eb, "resolve_abstract_for_entry", lambda *a, **k: calls.append(1) or (None, None))
    bib = tmp_path / "literature-domain-1.bib"
    bib.write_text(ENTRY.replace("doi = {10.2307/2024717},",
                                 "doi = {10.2307/2024717},\n  abstract = {" + GOOD + "},"), encoding="utf-8")
    eb.enrich_bibliography(bib, None, None, None, None)
    assert len(calls) == 1      # the ordinary attestation fetch only, no usability retry


def test_a_second_run_over_an_unrescuable_stub_changes_nothing(monkeypatch, tmp_path):
    _sources(monkeypatch, STUB, None)
    bib = tmp_path / "literature-domain-1.bib"
    bib.write_text(ENTRY, encoding="utf-8")
    eb.enrich_bibliography(bib, None, None, None, None)
    first = bib.read_text(encoding="utf-8")
    ledger = tmp_path / "intermediate_files" / "json" / "enrichment_ledger-literature-domain-1.json"
    first_ledger = ledger.read_text(encoding="utf-8")
    eb.enrich_bibliography(bib, None, None, None, None)
    assert bib.read_text(encoding="utf-8") == first
    assert json.loads(ledger.read_text(encoding="utf-8"))["entries"] == json.loads(first_ledger)["entries"]
