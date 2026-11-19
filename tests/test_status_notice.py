"""PL-39: the barrier's CrossRef publication-status lookup (`status_notice`).

Fixtures under tests/fixtures/crossref_status/ are real CrossRef payloads
recorded 2026-11-19 (only the bulky `reference` lists dropped):

- fwd.json: `filter=doi:...` for Gerlich 2025 (correction), Sterelny 2010
  (none), a SAGE retraction, a Springer self-retraction, the Gerlich notice
  itself, an Elsevier expression of concern and a Cochrane withdrawal;
- rev.json: `filter=updates:...` for the same originals;
- fwd_preprint.json: one Research Square posted-content preprint;
- facet.json: `facet=update-type:*` over every update record -- the token
  set CrossRef actually emits, which pins the mapping.

No test touches the network: `_http_get` is replaced by a fake transport.
"""
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "hooks"))

import bib_identity  # noqa: E402
import status_notice as sn  # noqa: E402
import venue_vetting as vv  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "crossref_status"


def _load(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def _items(name):
    return _load(name)["message"]["items"]


def _record(doi, name="fwd"):
    return next(i for i in _items(name) if i["DOI"].lower() == doi.lower())


GERLICH = {"author": "Gerlich, Michael",
           "title": "{AI} Tools in Society: Impacts on Cognitive Offloading and "
                    "the Future of Critical Thinking",
           "journal": "Societies", "doi": "10.3390/soc15010006", "year": "2025"}
STERELNY = {"author": "Sterelny, Kim", "title": "Minds: Extended or Scaffolded?",
            "journal": "Phenomenology and the Cognitive Sciences",
            "doi": "10.1007/s11097-010-9174-y", "year": "2010"}
WANG = {"author": "Wang, Yuan and Zhang, Li",
        "title": "Downregulation of long noncoding {RNA} {LINC01419} inhibits cell "
                 "migration, invasion, and tumor growth and promotes autophagy "
                 "\\emph{via} inactivation of the {PI3K/Akt1/mTOR} pathway in "
                 "gastric cancer",
        "doi": "10.1177/1758835919874651", "year": "2019"}


class _NoWait:
    def wait(self, max_seconds=None):
        return 0.0

    def record(self):
        pass


@pytest.fixture(autouse=True)
def _no_limiter(monkeypatch):
    monkeypatch.setattr(sn, "get_limiter", lambda *a, **k: _NoWait())
    # conftest switches the pass off for the session; these tests run it
    # against a fake transport.
    monkeypatch.delenv("PHILLIT_STATUS_NOTICE", raising=False)


class FakeCrossRef:
    """Answers forward and reverse filters from the recorded payloads,
    optionally shuffled, and records every request."""

    def __init__(self, records=None, notices=None, shuffle=False, fail=None):
        # The notices' own records too: the pass reads each notice (R1).
        self.records = (records if records is not None
                        else _items("fwd") + _items("fwd_preprint") + _items("rev"))
        self.notices = notices if notices is not None else _items("rev")
        self.shuffle = shuffle
        self.fail = fail or (lambda kind, dois: None)
        self.calls = []

    def __call__(self, params):
        clauses = params["filter"].split(",")
        kind = clauses[0].split(":", 1)[0]
        dois = [c.split(":", 1)[1] for c in clauses]
        self.calls.append((kind, dois))
        failed = self.fail(kind, dois)
        if failed is not None:
            return failed
        want = {d.lower() for d in dois}
        if kind == "doi":
            items = [r for r in self.records if r["DOI"].lower() in want]
        else:
            items = [n for n in self.notices
                     if any((u.get("DOI") or "").lower() in want
                            for u in n.get("update-to") or [])]
        items = [dict(i) for i in items]
        if self.shuffle:
            random.Random(7).shuffle(items)
        return 200, {"status": "ok",
                     "message": {"total-results": len(items), "items": items}}


def _run(monkeypatch, entries, fake=None, deadline=None):
    fake = fake or FakeCrossRef()
    monkeypatch.setattr(sn, "_http_get", fake)
    if deadline is None:
        deadline = sn.time.monotonic() + 1000
    values, report = sn.lookup_status(entries, deadline)
    return values, report, fake


def _e(fields, none=False, etype=None):
    entry = {"fields": fields, "evidence_none": none}
    if etype is not None:
        entry["entry_type"] = etype
    return entry


# ---------------------------------------------------------------------------
# Token pins against what CrossRef emits
# ---------------------------------------------------------------------------

def test_every_mapped_type_token_is_one_crossref_emits():
    emitted = set(_load("facet")["message"]["facets"]["update-type"]["values"])
    assert set(sn.TYPE_CATEGORY) <= emitted
    assert set(sn.TYPE_CATEGORY) == {
        "retraction", "partial_retraction", "withdrawal",
        "expression_of_concern", "correction", "erratum", "corrigendum"}


def test_case_and_hyphen_variants_map_to_the_seven():
    """CrossRef emits `Retraction`, `Erratum`, `Corrigendum` and
    `expression-of-concern` too (facet fixture): same meaning, same item."""
    emitted = set(_load("facet")["message"]["facets"]["update-type"]["values"])
    for tok, cat in (("Retraction", "retraction"), ("Erratum", "correction"),
                     ("Corrigendum", "correction"),
                     ("expression-of-concern", "expression_of_concern"),
                     (" Partial-Retraction ", "partial_retraction")):
        assert sn.category_of(tok) == cat
    assert {"Retraction", "Erratum", "Corrigendum", "expression-of-concern"} <= emitted
    assert sn.category_of("new_version") is None
    assert sn.category_of("retration") is None


def test_erratum_and_corrigendum_map_to_correction():
    assert sn.TYPE_CATEGORY["erratum"] == "correction"
    assert sn.TYPE_CATEGORY["corrigendum"] == "correction"


def test_doi_shape_is_bib_identitys():
    import fulltext
    assert sn.DOI_SHAPE is bib_identity.DOI_SHAPE
    assert fulltext.DOI_SHAPE is bib_identity.DOI_SHAPE


def test_request_timeout_is_venue_vettings():
    assert sn.REQUEST_TIMEOUT == vv.REQUEST_TIMEOUT


# ---------------------------------------------------------------------------
# Real-payload end to end
# ---------------------------------------------------------------------------

def test_gerlich_correction_stamped_from_real_payload(monkeypatch):
    values, report, _ = _run(monkeypatch, {"d1:gerlich": _e(GERLICH)})
    assert values == {"d1:gerlich": "correction 10.3390/soc15090252"}
    assert report["entries"]["d1:gerlich"] == "stamped"
    assert report["status"] == "complete"
    assert report["sources"] == {"publisher": 1}


def test_entry_with_no_update_is_checked_none(monkeypatch):
    values, report, _ = _run(monkeypatch, {"d1:sterelny": _e(STERELNY)})
    assert values == {}
    assert report["entries"]["d1:sterelny"] == "checked_none"


def test_retracted_title_prefix_does_not_break_identity(monkeypatch):
    """CrossRef retitles the article itself `RETRACTED: ...`; the bib keeps
    the original title. Measured 2026-11-19 on 10.1177/1758835919874651."""
    assert _record("10.1177/1758835919874651")["title"][0].startswith("RETRACTED:")
    values, report, _ = _run(monkeypatch, {"d1:wang": _e(WANG)})
    assert values == {"d1:wang": "retraction 10.1177/17588359211061903"}


def test_springer_in_place_retraction_is_stamped_with_the_articles_own_doi(monkeypatch):
    """Springer retracts in place: `updated-by` names the article's own DOI
    (recorded fixture 10.1007/s11277-021-09072-0, sources retraction-watch
    and publisher). That is real CrossRef practice for retractions, so the
    item is stamped with the entry's own DOI as the notice."""
    she = {"author": "She, Xu",
           "title": "Deep Reinforcement Learning-Based Smart Manufacturing",
           "doi": "10.1007/s11277-021-09072-0", "year": "2021"}
    rec = _record("10.1007/s11277-021-09072-0")
    she["title"] = sn.decode_crossref_title(rec["title"][0])[len("RETRACTED ARTICLE: "):]
    values, report, _ = _run(monkeypatch, {"d1:she": _e(she)})
    assert values == {"d1:she": "retraction 10.1007/s11277-021-09072-0"}
    assert report["entries"]["d1:she"] == "stamped"
    assert report["malformed"] == 0
    assert report["sources"] == {"publisher": 1, "retraction-watch": 1}


@pytest.mark.parametrize("token,item", [
    ("retraction", "retraction 10.1007/s11097-010-9174-y"),
    ("partial_retraction", "partial_retraction 10.1007/s11097-010-9174-y"),
    ("withdrawal", "withdrawal 10.1007/s11097-010-9174-y"),
])
def test_in_place_retractions_and_withdrawals_are_accepted(monkeypatch, token, item):
    """Both partial_retraction records CrossRef holds are self-referential
    (measured 2026-11-19, e.g. 10.29328/journal.jcmhs.1001023)."""
    fake = _with_updates([{"DOI": "10.1007/S11097-010-9174-Y", "type": token,
                           "source": "publisher"}])
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {"s": item}
    assert report["malformed"] == 0


@pytest.mark.parametrize("token", ["correction", "erratum", "corrigendum",
                                   "expression_of_concern"])
def test_self_referential_correction_or_concern_stays_malformed(monkeypatch, token):
    """A correction or expression of concern that names the article itself
    is not a notice."""
    fake = _with_updates([{"DOI": "10.1007/s11097-010-9174-y", "type": token,
                           "source": "publisher"}])
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {}
    assert report["malformed"] == 1
    assert report["entries"]["s"] == "unresolved"
    assert report["status"] == "partial" and "could not map" in report["reason"]


def test_self_referential_reverse_hit_for_a_retraction_is_accepted(monkeypatch):
    """The reverse query returns the in-place record itself (its update-to
    names its own DOI): the same item, deduplicated."""
    rec = dict(_record("10.1007/s11097-010-9174-y"))
    rec["update-to"] = [{"DOI": "10.1007/s11097-010-9174-y", "type": "retraction"}]

    def answer(params):
        return 200, {"message": {"total-results": 1, "items": [rec]}}
    values, _r, _ = _run(monkeypatch, {"s": _e(STERELNY)}, answer)
    assert values == {"s": "retraction 10.1007/s11097-010-9174-y"}


def test_expression_of_concern_and_withdrawal(monkeypatch):
    bazhin = {"author": "Bazhin, A. V. and Savchenko, M. S.",
              "title": sn.decode_crossref_title(
                  _record("10.1016/j.lungcan.2003.10.006")["title"][0]),
              "doi": "10.1016/j.lungcan.2003.10.006"}
    njei = {"author": "Njei, Bubu and Kumar, Ashish",
            "title": sn.decode_crossref_title(
                _record("10.1002/14651858.cd009522")["title"][0]),
            "doi": "10.1002/14651858.CD009522"}
    values, _r, _ = _run(monkeypatch, {"a": _e(bazhin), "b": _e(njei)})
    assert values["a"] == "expression_of_concern 10.1016/j.lungcan.2026.109332"
    assert values["b"] == "withdrawal 10.1002/14651858.cd009522.pub2"


def test_preprint_from_posted_content_subtype(monkeypatch):
    rec = _items("fwd_preprint")[0]
    assert rec["type"] == "posted-content" and rec["subtype"] == "preprint"
    fields = {"author": "Chiowchanwisawakit, P.",
              "title": sn.decode_crossref_title(rec["title"][0]),
              "doi": rec["DOI"]}
    values, _r, _ = _run(monkeypatch, {"p": _e(fields)})
    assert values == {"p": "preprint"}


def test_note_or_arxiv_fields_never_stamp_preprint(monkeypatch):
    fields = dict(STERELNY, note="This is a preprint; a correction was published.",
                  eprint="2101.00001", archiveprefix="arXiv")
    values, _r, _ = _run(monkeypatch, {"s": _e(fields)})
    assert values == {}


def test_posted_content_without_preprint_subtype_is_not_preprint(monkeypatch):
    rec = dict(_items("fwd_preprint")[0])
    rec.pop("subtype")
    fields = {"author": "Chiowchanwisawakit, P.",
              "title": sn.decode_crossref_title(rec["title"][0]), "doi": rec["DOI"]}
    values, _r, _ = _run(monkeypatch, {"p": _e(fields)},
                         FakeCrossRef(records=[rec], notices=[]))
    assert values == {}


def test_entry_doi_that_is_itself_a_notice_stamps_nothing(monkeypatch):
    """The Gerlich correction notice cited as an entry: its record has
    `update-to`; it gets no item from that."""
    rec = _record("10.3390/soc15090252")
    fields = {"author": "Gerlich, Michael",
              "title": sn.decode_crossref_title(rec["title"][0]),
              "doi": "10.3390/soc15090252"}
    values, report, _ = _run(monkeypatch, {"n": _e(fields)})
    assert values == {}
    assert report["entries"]["n"] == "checked_none"


# ---------------------------------------------------------------------------
# Mapping and batching
# ---------------------------------------------------------------------------

def test_mapping_by_doi_with_shuffled_partial_uppercase_response(monkeypatch):
    up = dict(GERLICH, doi="https://doi.org/10.3390/SOC15010006")
    missing = {"author": "Nobody, A.", "title": "A Work CrossRef Does Not Know",
               "doi": "10.9999/not-there"}
    values, report, _ = _run(monkeypatch,
                             {"g": _e(up), "s": _e(STERELNY), "m": _e(missing)},
                             FakeCrossRef(shuffle=True))
    assert values == {"g": "correction 10.3390/soc15090252"}
    assert report["entries"] == {"g": "stamped", "s": "checked_none", "m": "not_found"}
    assert report["not_found"] == 1


def test_returned_item_for_an_unrequested_doi_is_ignored(monkeypatch):
    stray = dict(_record("10.3390/soc15010006"), DOI="10.5555/other")
    fake = FakeCrossRef(records=[stray, _record("10.1007/s11097-010-9174-y")], notices=[])
    fake_call = fake.__call__

    def answer(params):
        status, body = fake_call(params)
        if params["filter"].startswith("doi:"):
            body["message"]["items"].append(stray)
            body["message"]["total-results"] += 1
        return status, body
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, answer)
    assert values == {}
    assert report["entries"]["s"] == "checked_none"


def test_reverse_hit_counts_only_when_update_to_names_the_requested_doi(monkeypatch):
    rec = dict(_record("10.1007/s11097-010-9174-y"))
    other = {"DOI": "10.1000/notice-other", "type": "journal-article",
             "update-to": [{"DOI": "10.1000/somebody-else", "type": "retraction"}]}
    named = {"DOI": "10.1000/notice-named", "type": "journal-article",
             "update-to": [{"DOI": "10.1007/S11097-010-9174-Y", "type": "erratum",
                            "source": "publisher"}]}

    def answer(params):
        if params["filter"].startswith("doi:"):
            want = params["filter"].lower()
            items = [r for r in (rec, named) if r["DOI"].lower() in want]
            return 200, {"message": {"total-results": len(items), "items": items}}
        return 200, {"message": {"total-results": 2, "items": [other, named]}}
    values, _r, _ = _run(monkeypatch, {"s": _e(STERELNY)}, answer)
    assert values == {"s": "correction 10.1000/notice-named"}


def test_reverse_hit_with_unmapped_type_is_counted_not_stamped(monkeypatch):
    rec = dict(_record("10.1007/s11097-010-9174-y"))
    nv = {"DOI": "10.1000/new-version", "update-to": [
        {"DOI": "10.1007/s11097-010-9174-y", "type": "removal"}]}

    def answer(params):
        items = [rec] if params["filter"].startswith("doi:") else [nv]
        return 200, {"message": {"total-results": 1, "items": items}}
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, answer)
    assert values == {}
    assert report["unmapped_types"] == {"removal": 1}
    assert report["entries"]["s"] == "unresolved"
    assert report["status"] == "partial" and report["reason"]


def test_161_dois_make_three_forward_requests(monkeypatch):
    """Z3: chunks of 80; the 400/414 split already handles a long URL."""
    entries = {f"k{n}": _e({"author": "Doe, J.", "title": f"Work {n}",
                            "doi": f"10.1000/w{n}"}) for n in range(161)}
    _v, report, fake = _run(monkeypatch, entries, FakeCrossRef(records=[], notices=[]))
    fwd = [c for c in fake.calls if c[0] == "doi"]
    assert [len(d) for _k, d in fwd] == [80, 80, 1]
    assert len([c for c in fake.calls if c[0] == "updates"]) == 3
    assert report["not_found"] == 161


def test_duplicate_dois_sent_once(monkeypatch):
    entries = {"a": _e(GERLICH), "b": _e(dict(GERLICH, doi="doi:10.3390/SOC15010006"))}
    values, _r, fake = _run(monkeypatch, entries)
    assert fake.calls[0] == ("doi", ["10.3390/soc15010006"])
    assert values == {"a": "correction 10.3390/soc15090252",
                      "b": "correction 10.3390/soc15090252"}


@pytest.mark.parametrize("doi,state", [
    ("", "not_requested:no-doi"),
    ("forthcoming", "not_requested:invalid-doi"),
    ("10.1000/a,b", "not_requested:invalid-doi"),
    ("10.1000/a b", "not_requested:invalid-doi"),
    ("10.48550/arXiv.2101.00001", "not_requested:arxiv"),
])
def test_dois_that_are_never_sent(monkeypatch, doi, state):
    fields = dict(STERELNY, doi=doi)
    if not doi:
        fields.pop("doi")
    values, report, fake = _run(monkeypatch, {"x": _e(fields)})
    assert fake.calls == []
    assert report["entries"]["x"] == state
    assert values == {}
    if state.endswith("arxiv"):
        assert report["arxiv_skipped"] == 1


def test_evidence_none_entry_is_not_looked_up(monkeypatch):
    values, report, fake = _run(monkeypatch, {"g": _e(GERLICH, none=True)})
    assert fake.calls == []
    assert report["entries"]["g"] == "not_requested:evidence-none"


def test_400_splits_the_chunk_and_isolates_the_bad_doi(monkeypatch):
    bad = "10.1000/rejected"

    def fail(kind, dois):
        if bad in dois:
            return 400, {"status": "failed"}
        return None
    entries = {"g": _e(GERLICH), "s": _e(STERELNY),
               "b": _e({"author": "Doe, J.", "title": "Bad", "doi": bad})}
    values, report, fake = _run(monkeypatch, entries, FakeCrossRef(fail=fail))
    assert values == {"g": "correction 10.3390/soc15090252"}
    assert report["entries"]["b"] == "error"
    assert report["entries"]["s"] == "checked_none"
    assert report["status"] == "partial" and report["reason"]


def test_414_also_splits(monkeypatch):
    def fail(kind, dois):
        return (414, None) if len(dois) > 1 else None
    entries = {"g": _e(GERLICH), "s": _e(STERELNY)}
    values, report, _ = _run(monkeypatch, entries, FakeCrossRef(fail=fail))
    assert values == {"g": "correction 10.3390/soc15090252"}
    assert report["status"] == "complete"


def test_truncated_response_is_never_checked_none(monkeypatch):
    def answer(params):
        return 200, {"message": {"total-results": 5, "items": []}}
    _v, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, answer)
    assert report["entries"]["s"] == "error"
    assert report["status"] == "partial"


# ---------------------------------------------------------------------------
# Update items
# ---------------------------------------------------------------------------

def _with_updates(updates, base="10.1007/s11097-010-9174-y"):
    rec = dict(_record(base))
    rec["updated-by"] = updates
    # A plain record for each notice, so the notice check (R1) reads it.
    notices = [{"DOI": u["DOI"], "type": "journal-article", "title": ["Notice"]}
               for u in updates if isinstance(u.get("DOI"), str) and u["DOI"].strip()]
    return FakeCrossRef(records=[rec] + notices, notices=[])


@pytest.mark.parametrize("token,item", [
    ("retraction", "retraction 10.1000/n1"),
    ("partial_retraction", "partial_retraction 10.1000/n1"),
    ("withdrawal", "withdrawal 10.1000/n1"),
    ("expression_of_concern", "expression_of_concern 10.1000/n1"),
    ("correction", "correction 10.1000/n1"),
    ("erratum", "correction 10.1000/n1"),
    ("corrigendum", "correction 10.1000/n1"),
])
def test_each_mapped_type(monkeypatch, token, item):
    fake = _with_updates([{"DOI": "10.1000/N1", "type": token, "source": "publisher"}])
    values, _r, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {"s": item}


def test_items_sorted_deduped_and_joined(monkeypatch):
    fake = _with_updates([
        {"DOI": "10.1000/b", "type": "correction", "source": "publisher"},
        {"DOI": "10.1000/r", "type": "retraction", "source": "retraction-watch"},
        {"DOI": "10.1000/r", "type": "retraction", "source": "publisher"},
        {"DOI": "10.1000/a", "type": "erratum", "source": "publisher"},
    ])
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {"s": "retraction 10.1000/r; correction 10.1000/a; correction 10.1000/b"}
    assert report["sources"] == {"publisher": 3, "retraction-watch": 1}


def test_unmapped_and_malformed_items_counted_not_stamped(monkeypatch):
    fake = _with_updates([
        {"DOI": "10.1000/nv", "type": "removal", "source": "publisher"},
        {"DOI": "10.1000/cap", "type": "Retraction", "source": "publisher"},
        {"DOI": "10.1000/semi;colon", "type": "retraction", "source": "publisher"},
        {"DOI": "10.1000/white space", "type": "retraction", "source": "publisher"},
        {"DOI": "10.1007/S11097-010-9174-Y", "type": "correction", "source": "publisher"},
        {"DOI": "", "type": "correction", "source": "publisher"},
        {"type": "correction"},
    ])
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {"s": "retraction 10.1000/cap"}
    assert report["unmapped_types"] == {"removal": 1}
    assert report["malformed"] == 5
    assert report["entries"]["s"] == "stamped"
    assert report["unresolved"] == 1
    assert report["status"] == "partial" and "could not map" in report["reason"]


def test_an_unmappable_relation_alone_is_unresolved_not_checked_none(monkeypatch):
    fake = _with_updates([{"DOI": "10.1000/nv", "type": "removal", "source": "publisher"}])
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {}
    assert report["entries"]["s"] == "unresolved"
    assert report["status"] == "partial" and "could not map" in report["reason"]


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def _gerlich_with(**kw):
    rec = dict(_record("10.3390/soc15010006"))
    rec.update(kw)
    return rec


def _identity(fields, rec):
    return sn.identity_matches(fields, rec)


def test_identity_latex_accents_vs_unicode():
    rec = _gerlich_with(author=[{"family": "Gödel", "given": "K."}],
                        title=["Über formal unentscheidbare Sätze"])
    fields = {"author": "G{\\\"o}del, Kurt",
              "title": "{\\\"U}ber formal unentscheidbare S{\\\"a}tze"}
    assert _identity(fields, rec)


def test_identity_escaped_ampersand_vs_entity():
    rec = _gerlich_with(author=[{"family": "Smith"}], title=["Law &amp; Society"])
    assert _identity({"author": "Smith, J.", "title": "Law \\& Society"}, rec)


def test_identity_double_encoded_entity_and_markup():
    rec = _gerlich_with(author=[{"family": "Smith"}],
                        title=["The <i>Republic</i> &amp;amp; its Readers"])
    assert _identity({"author": "Smith, J.", "title": "The Republic & its Readers"}, rec)


def test_identity_subtitle_variant_both_ways():
    rec = _gerlich_with(title=["AI Tools in Society"],
                        subtitle=["Impacts on Cognitive Offloading and the Future of Critical Thinking"])
    assert _identity(GERLICH, rec)
    short = dict(GERLICH, title="AI Tools in Society")
    assert _identity(short, _record("10.3390/soc15010006"))


def test_identity_conflicting_subtitles_mismatch():
    rec = _gerlich_with(author=[{"family": "Smith"}], title=["Knowing: Freedom"])
    assert not _identity({"author": "Smith, J.", "title": "Knowing: Causation"}, rec)


def test_identity_translated_title_mismatch():
    rec = _gerlich_with(author=[{"family": "Gerlich"}],
                        title=["KI-Werkzeuge in der Gesellschaft"])
    assert not _identity(GERLICH, rec)


def test_identity_editor_only_book_mismatch():
    rec = _gerlich_with(title=[GERLICH["title"].replace("{AI}", "AI")])
    rec.pop("author")
    rec["editor"] = [{"family": "Gerlich", "given": "Michael"}]
    assert not _identity({"editor": "Gerlich, Michael", "title": GERLICH["title"]}, rec)


def test_identity_book_vs_chapter_mismatch():
    rec = _gerlich_with(type="book-chapter", title=["Cognitive Offloading"])
    assert not _identity(GERLICH, rec)


def test_identity_wrong_surname_mismatch():
    assert not _identity(dict(GERLICH, author="Smith, Michael"),
                         _record("10.3390/soc15010006"))


def test_identity_particle_surname():
    rec = _gerlich_with(author=[{"family": "Linden", "given": "Sander van der",
                                 "sequence": "first"}])
    assert _identity(dict(GERLICH, author="van der Linden, Sander"), rec)


def test_identity_mismatch_stamps_nothing_reverse_hits_included(monkeypatch):
    wrong = dict(GERLICH, author="Smith, A.", title="An Entirely Different Paper")
    values, report, _ = _run(monkeypatch, {"w": _e(wrong)})
    assert values == {}
    assert report["entries"]["w"] == "identity_mismatch"
    assert report["identity_mismatch"] == 1


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

def test_deadline_before_first_request_strands_every_entry(monkeypatch):
    values, report, fake = _run(monkeypatch, {"g": _e(GERLICH)},
                                deadline=sn.time.monotonic() - 1)
    assert fake.calls == []
    assert values == {}
    assert report["entries"]["g"] == "deadline"
    assert report["deadline"] == 1
    assert report["status"] == "partial" and "deadline" in report["reason"]


def test_deadline_rechecked_after_the_limiter_wait(monkeypatch):
    """The wait itself can carry the pass past the deadline: no request is
    sent then."""
    clock = {"t": 0.0}
    monkeypatch.setattr(sn.time, "monotonic", lambda: clock["t"])

    class SlowLimiter(_NoWait):
        def wait(self, max_seconds=None):
            clock["t"] += 50.0
            return 50.0
    monkeypatch.setattr(sn, "get_limiter", lambda *a, **k: SlowLimiter())
    values, report, fake = _run(monkeypatch, {"g": _e(GERLICH)}, deadline=30.0)
    assert fake.calls == []
    assert report["entries"]["g"] == "deadline"


def test_consecutive_error_breaker(monkeypatch):
    entries = {f"k{n}": _e({"author": "Doe, J.", "title": f"W {n}",
                            "doi": f"10.1000/w{n}"}) for n in range(200)}
    fake = FakeCrossRef(records=[], notices=[], fail=lambda k, d: (503, None))
    _v, report, fake = _run(monkeypatch, entries, fake)
    assert len(fake.calls) == sn.MAX_CONSECUTIVE_ERRORS
    assert set(report["entries"].values()) == {"error"}
    assert report["status"] == "partial"
    assert "consecutive" in report["reason"]


def test_transport_exception_is_an_error_not_a_crash(monkeypatch):
    def boom(params):
        raise ConnectionError("down")
    _v, report, _ = _run(monkeypatch, {"g": _e(GERLICH)}, boom)
    assert report["entries"]["g"] == "error"
    assert report["status"] == "partial" and report["reason"]


def test_never_raises_on_bad_input(monkeypatch):
    values, report, _ = _run(monkeypatch, {"g": None})
    assert values == {}
    assert report["status"] == "partial" and report["reason"]


def test_reverse_failure_keeps_forward_items_but_reports_partial(monkeypatch):
    fake = FakeCrossRef(fail=lambda k, d: (503, None) if k == "updates" else None)
    values, report, _ = _run(monkeypatch, {"g": _e(GERLICH), "s": _e(STERELNY)}, fake)
    assert values == {"g": "correction 10.3390/soc15090252"}
    assert report["entries"]["s"] == "error"
    assert report["status"] == "partial"


def test_a_failed_reverse_query_is_partial_even_when_everything_stamped(monkeypatch):
    """Measured live 2026-11-19: one transient failure on the reverse query.
    The forward items still stamp, but the pass must say what went unchecked."""
    fake = FakeCrossRef(fail=lambda k, d: (503, None) if k == "updates" else None)
    values, report, _ = _run(monkeypatch, {"g": _e(GERLICH)}, fake)
    assert values == {"g": "correction 10.3390/soc15090252"}
    assert report["entries"] == {"g": "stamped"}
    assert report["reverse_unchecked"] == 1
    assert report["status"] == "partial" and "reverse" in report["reason"]


def test_request_params_carry_polite_pool_and_no_select(monkeypatch):
    monkeypatch.setenv("CROSSREF_MAILTO", "ops@example.org")
    seen = []

    def answer(params):
        seen.append(params)
        return 200, {"message": {"total-results": 0, "items": []}}
    _run(monkeypatch, {"s": _e(STERELNY)}, answer)
    assert all(p.get("mailto") == "ops@example.org" for p in seen)
    assert all("select" not in p for p in seen)


# ---------------------------------------------------------------------------
# Value grammar
# ---------------------------------------------------------------------------

def test_categories_parses_the_field():
    assert sn.categories("retraction 10.1/a; correction 10.1/b; preprint") == {
        "retraction", "correction", "preprint"}
    assert sn.categories("") == set()
    assert sn.categories(None) == set()


def test_notice_dois_by_category():
    assert sn.parse_items("partial_retraction 10.1/a; preprint") == [
        ("partial_retraction", "10.1/a"), ("preprint", None)]


def test_report_has_every_documented_key(monkeypatch):
    _v, report, _ = _run(monkeypatch, {})
    for key in ("status", "reason", "looked_up", "stamped", "not_found",
                "identity_mismatch", "arxiv_skipped", "errors", "deadline",
                "unmapped_types", "sources", "malformed", "splice_failed",
                "entries"):
        assert key in report
    assert report["status"] == "complete"


@pytest.mark.parametrize("value", ["off", "0", "false", "NO"])
def test_switched_off_is_skipped_with_reason(monkeypatch, value):
    monkeypatch.setenv("PHILLIT_STATUS_NOTICE", value)
    values, report, fake = _run(monkeypatch, {"g": _e(GERLICH)})
    assert fake.calls == [] and values == {}
    assert report["status"] == "skipped"
    assert "PHILLIT_STATUS_NOTICE" in report["reason"]
    assert report["entries"] == {}


def test_unrecognized_switch_value_is_skipped_with_reason(monkeypatch):
    monkeypatch.setenv("PHILLIT_STATUS_NOTICE", "flase")
    _v, report, fake = _run(monkeypatch, {"g": _e(GERLICH)})
    assert fake.calls == []
    assert report["status"] == "skipped" and "unrecognized" in report["reason"]


@pytest.mark.parametrize("value", ["on", "1", "  "])
def test_switched_on_or_blank_runs(monkeypatch, value):
    monkeypatch.setenv("PHILLIT_STATUS_NOTICE", value)
    values, _r, _ = _run(monkeypatch, {"g": _e(GERLICH)})
    assert values == {"g": "correction 10.3390/soc15090252"}


# ---------------------------------------------------------------------------
# Review round 2
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bib_author,cr_family", [
    ("Lopez, Ana", "Garcia Lopez"),
    ("Garcia Lopez, Ana", "Lopez"),
    ("Sterelny, Kim", "Brown Sterelny"),
])
def test_surname_last_token_is_not_enough(bib_author, cr_family):
    """P1: a shared last word is two different surnames."""
    rec = _gerlich_with(author=[{"family": cr_family, "sequence": "first"}])
    assert not _identity(dict(GERLICH, author=bib_author), rec)


@pytest.mark.parametrize("bib_author,cr_family", [
    ("van der Linden, Sander", "Linden"),
    ("van der Linden, Sander", "van der Linden"),
    ("Linden, Sander van der", "van der Linden"),
    ("de Beauvoir, Simone", "Beauvoir"),
    ("von Wright, Georg Henrik", "Von Wright"),
])
def test_leading_particles_are_removed_before_the_exact_compare(bib_author, cr_family):
    rec = _gerlich_with(author=[{"family": cr_family, "sequence": "first"}])
    assert _identity(dict(GERLICH, author=bib_author), rec)


def test_particle_is_only_removed_from_the_front():
    rec = _gerlich_with(author=[{"family": "Lopez", "sequence": "first"}])
    assert not _identity(dict(GERLICH, author="{Lopez de la Garza}, Ana"), rec)


@pytest.mark.parametrize("etype,cr_type,ok", [
    ("book", "book-chapter", False),
    ("book", "journal-article", False),
    ("article", "book", False),
    ("incollection", "book", False),
    ("incollection", "monograph", False),
    ("book", "book", True),
    ("incollection", "book-chapter", True),
    ("article", "journal-article", True),
    ("misc", "posted-content", True),
])
def test_entry_type_must_be_compatible(monkeypatch, etype, cr_type, ok):
    """P2: same author and title, only the type differs."""
    rec = dict(_record("10.3390/soc15010006"), type=cr_type)
    fake = FakeCrossRef(records=[rec, _record("10.3390/soc15090252")], notices=[])
    values, report, _ = _run(monkeypatch, {"g": _e(GERLICH, etype=etype)}, fake)
    assert report["entries"]["g"] == ("stamped" if ok else "identity_mismatch")
    assert bool(values) is ok


def test_markup_inside_a_word_is_removed_without_a_space():
    """P13: `<i>Bio</i>logy` is one word; tags between words keep them apart."""
    assert sn.decode_crossref_title("The <i>Bio</i>logy of Mind") == "The Biology of Mind"
    assert sn.decode_crossref_title("Kant<br/>Hegel") == "Kant Hegel"
    assert sn.decode_crossref_title("Mind <i>and</i> World") == "Mind and World"


def test_limiter_wait_that_would_cross_the_deadline_is_not_taken(monkeypatch):
    """P6: the wait is bounded by the time left; a wait past it is refused,
    nothing is sent, and the entry is `deadline`."""
    asked = []

    class Busy(_NoWait):
        def wait(self, max_seconds=None):
            asked.append(max_seconds)
            return None   # the next slot is past max_seconds
    monkeypatch.setattr(sn, "get_limiter", lambda *a, **k: Busy())
    values, report, fake = _run(monkeypatch, {"g": _e(GERLICH)},
                                deadline=sn.time.monotonic() + 5)
    assert fake.calls == []
    assert asked and 0 < asked[0] <= 5
    assert report["entries"]["g"] == "deadline"
    assert report["status"] == "partial"


def test_failed_reverse_on_a_not_found_entry_is_partial(monkeypatch):
    """P11: forward answers with nothing, reverse fails: the pass says so."""
    missing = {"author": "Nobody, A.", "title": "Unknown", "doi": "10.9999/none"}
    fake = FakeCrossRef(records=[], notices=[],
                        fail=lambda k, d: (503, None) if k == "updates" else None)
    _v, report, _ = _run(monkeypatch, {"m": _e(missing)}, fake)
    assert report["entries"]["m"] == "not_found"
    assert report["status"] == "partial" and "reverse" in report["reason"]


def test_failed_reverse_on_an_identity_mismatch_is_partial(monkeypatch):
    wrong = dict(GERLICH, author="Smith, A.", title="Another Paper")
    fake = FakeCrossRef(fail=lambda k, d: (503, None) if k == "updates" else None)
    _v, report, _ = _run(monkeypatch, {"w": _e(wrong)}, fake)
    assert report["entries"]["w"] == "identity_mismatch"
    assert report["status"] == "partial" and "reverse" in report["reason"]


def test_late_promotion_is_counted_but_keeps_the_pass_complete():
    """Z4: a late promotion is expected barrier behaviour, not a failure."""
    report = sn.empty_report()
    report["entries"]["x"] = "not_checked:late-promotion"
    sn.settle(report)
    assert report["status"] == "complete" and report["reason"] is None
    assert report["late_promotion"] == 1


def test_list_queries_use_crossrefs_list_rate(monkeypatch):
    """Measured live 2026-11-19: the reverse query right after the forward
    one drew HTTP 429 at the shared 0.05 s CrossRef interval. /works filter
    queries are list queries, which CrossRef's public pool allows about once
    a second."""
    import rate_limiter
    assert rate_limiter.get_limiter("crossref_list").min_interval >= 1.0
    names = []
    monkeypatch.setattr(sn, "get_limiter", lambda name, *a, **k: (names.append(name), _NoWait())[1])
    _run(monkeypatch, {"s": _e(STERELNY)}, FakeCrossRef(records=[], notices=[]))
    assert names == ["crossref_list"]


def _answers(*replies):
    calls = []

    def answer(params):
        calls.append(params["filter"].split(":", 1)[0])
        reply = replies[min(len(calls), len(replies)) - 1]
        return reply if reply is not None else (200, {"message": {"total-results": 0, "items": []}})
    return answer, calls


def test_a_429_is_retried_once_after_its_retry_after(monkeypatch):
    slept = []
    monkeypatch.setattr(sn.time, "sleep", lambda s: slept.append(s))
    answer, calls = _answers((429, None, {"Retry-After": "2"}), None, None)
    monkeypatch.setattr(sn, "_http_get", answer)
    values, report = sn.lookup_status({"s": _e(STERELNY)}, sn.time.monotonic() + 100)
    assert calls == ["doi", "doi", "updates"]
    assert slept == [2.0]
    assert report["entries"]["s"] == "not_found"


def test_a_second_429_is_an_error(monkeypatch):
    monkeypatch.setattr(sn.time, "sleep", lambda s: None)
    answer, calls = _answers((429, None, {}), (429, None, {}), None)
    monkeypatch.setattr(sn, "_http_get", answer)
    _v, report = sn.lookup_status({"s": _e(STERELNY)}, sn.time.monotonic() + 100)
    assert calls[:2] == ["doi", "doi"]
    assert report["entries"]["s"] == "error"
    assert report["status"] == "partial"


def test_a_retry_after_past_the_deadline_is_not_waited_for(monkeypatch):
    slept = []
    monkeypatch.setattr(sn.time, "sleep", lambda s: slept.append(s))
    answer, calls = _answers((429, None, {"Retry-After": "60"}), None)
    monkeypatch.setattr(sn, "_http_get", answer)
    _v, report = sn.lookup_status({"s": _e(STERELNY)}, sn.time.monotonic() + 5)
    assert slept == [] and calls == ["doi"]
    assert report["entries"]["s"] == "deadline"


def test_known_non_status_tokens_are_pinned_against_the_facet():
    """Every pinned non-status token is one CrossRef emits (after the fold),
    and none is a status category."""
    emitted = {sn.fold_token(t) for t in
               _load("facet")["message"]["facets"]["update-type"]["values"]}
    assert sn.KNOWN_NON_STATUS <= emitted
    assert not sn.KNOWN_NON_STATUS & set(sn.TYPE_CATEGORY)
    assert sn.KNOWN_NON_STATUS == {
        "new_version", "new_edition", "addendum", "clarification", "comment",
        "correspondence", "book_review", "point_counterpoint", "print"}


@pytest.mark.parametrize("token", ["new_version", "New-Edition", "addendum", "clarification"])
def test_a_non_status_relation_is_ignored_not_unresolved(monkeypatch, token):
    fake = _with_updates([{"DOI": "10.1000/nv", "type": token, "source": "publisher"}])
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {}
    assert report["entries"]["s"] == "checked_none"
    assert report["ignored_types"] == {sn.fold_token(token): 1}
    assert report["unmapped_types"] == {} and report["unresolved"] == 0
    assert report["status"] == "complete" and report["reason"] is None


@pytest.mark.parametrize("token", ["removal", "err", "publisher-note", "unknown", "retration"])
def test_a_token_in_neither_set_is_unresolved(monkeypatch, token):
    fake = _with_updates([{"DOI": "10.1000/x", "type": token, "source": "publisher"}])
    _v, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert report["entries"]["s"] == "unresolved"
    assert report["ignored_types"] == {}
    assert report["status"] == "partial" and "could not map" in report["reason"]


def test_ignored_relation_beside_a_stamp_keeps_the_pass_complete(monkeypatch):
    fake = _with_updates([
        {"DOI": "10.1000/r", "type": "retraction", "source": "publisher"},
        {"DOI": "10.1000/nv", "type": "new_version", "source": "publisher"}])
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {"s": "retraction 10.1000/r"}
    assert report["status"] == "complete"


def test_empty_title_or_no_author_is_unverifiable(monkeypatch):
    """Z5: a record that cannot be compared is not a mismatch."""
    for rec in (dict(_record("10.3390/soc15010006"), title=[]),
                {k: v for k, v in _record("10.3390/soc15010006").items() if k != "author"}):
        values, report, _ = _run(monkeypatch, {"g": _e(GERLICH)},
                                 FakeCrossRef(records=[rec], notices=_items("rev")))
        assert values == {}
        assert report["entries"]["g"] == "identity_unverifiable"
        assert report["identity_unverifiable"] == 1 and report["identity_mismatch"] == 0


def test_single_doi_400s_trip_the_breaker(monkeypatch):
    """Z11: a DOI that alone still draws 400 counts toward the breaker."""
    entries = {f"k{n}": _e({"author": "Doe, J.", "title": f"W {n}",
                            "doi": f"10.1000/w{n}"}) for n in range(8)}
    fake = FakeCrossRef(records=[], notices=[], fail=lambda k, d: (400, None))
    _v, report, fake = _run(monkeypatch, entries, fake)
    singles = [c for c in fake.calls if len(c[1]) == 1]
    assert len(singles) == sn.MAX_CONSECUTIVE_ERRORS
    assert set(report["entries"].values()) == {"error"}
    assert "consecutive" in report["reason"]


def test_value_grammar_lives_in_a_leaf_module():
    """Z9: one owner with no network import; status_notice aliases it."""
    import subprocess
    import status_items
    assert sn.parse_items is status_items.parse_items
    assert sn.categories is status_items.categories
    assert sn.format_items is status_items.format_items
    assert sn.CATEGORY_ORDER is status_items.CATEGORY_ORDER
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); import status_items; "
         "print(sorted(m for m in ('requests', 'venue_vetting', 'rate_limiter', "
         "'evidence_barrier') if m in sys.modules))", str(SCRIPTS)],
        capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr


# ---------------------------------------------------------------------------
# Validation run 2026-11-19 (cognitive-autonomy-ai)
# ---------------------------------------------------------------------------

COSTELLO = {"author": "Costello, Thomas H. and Pennycook, Gordon and Rand, David G.",
            "title": "Durably reducing conspiracy beliefs through dialogues with {AI}",
            "doi": "10.1126/science.adq1814", "year": "2024"}


def test_a_rescinded_notice_is_dropped(monkeypatch):
    """R1: Science rescinded its expression of concern (the notice's own
    record is titled "RESCINDED: Editorial Expression of Concern"). The
    correction stays: its notice record is a plain correction."""
    recs = _items("fwd_costello") + [{"DOI": "10.1126/science.aem1178",
                                      "type": "journal-article",
                                      "title": ["Erratum for the Research Article"]}]
    values, report, _ = _run(monkeypatch, {"c": _e(COSTELLO)},
                             FakeCrossRef(records=recs, notices=[]))
    assert values == {"c": "correction 10.1126/science.aem1178"}
    assert report["notice_rescinded"] == 1


def test_an_entry_whose_only_notice_is_rescinded_says_so(monkeypatch):
    rec = dict(_record("10.1126/science.adq1814", "fwd_costello"))
    rec["updated-by"] = [u for u in rec["updated-by"] if u["type"] == "expression_of_concern"]
    notice = _record("10.1126/science.aej2383", "fwd_costello")
    values, report, _ = _run(monkeypatch, {"c": _e(COSTELLO)},
                             FakeCrossRef(records=[rec, notice], notices=[]))
    assert values == {}
    assert report["entries"]["c"] == "notice_rescinded"
    assert report["status"] == "complete"


def test_a_notice_retracted_by_an_update_is_dropped(monkeypatch):
    notice = {"DOI": "10.1000/n1", "type": "journal-article", "title": ["Correction"],
              "updated-by": [{"DOI": "10.1000/n2", "type": "Removal"}]}
    fake = _with_updates([{"DOI": "10.1000/n1", "type": "correction", "source": "publisher"}])
    fake.records = [r for r in fake.records if r["DOI"] != "10.1000/n1"] + [notice]
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)}, fake)
    assert values == {} and report["notice_rescinded"] == 1


def test_a_notice_whose_record_cannot_be_read_is_dropped(monkeypatch):
    """R1, fail closed: no notice record, no item; the pass is partial."""
    rec = dict(_record("10.1007/s11097-010-9174-y"))
    rec["updated-by"] = [{"DOI": "10.1000/unreadable", "type": "retraction",
                          "source": "publisher"}]
    values, report, _ = _run(monkeypatch, {"s": _e(STERELNY)},
                             FakeCrossRef(records=[rec], notices=[]))
    assert values == {}
    assert report["entries"]["s"] == "notice_unverified"
    assert report["notice_unverified"] == 1
    assert report["status"] == "partial" and "notice" in report["reason"]


def test_in_place_notices_are_not_requeried(monkeypatch):
    she = {"author": "She, Xu", "doi": "10.1007/s11277-021-09072-0",
           "title": "Deep Reinforcement Learning-Based Smart Manufacturing Plants "
                    "with a Novel Digital Twin Training Model"}
    values, _r, fake = _run(monkeypatch, {"s": _e(she)})
    assert values == {"s": "retraction 10.1007/s11277-021-09072-0"}
    assert [c for c in fake.calls if c[0] == "doi"] == [("doi", ["10.1007/s11277-021-09072-0"])]


@pytest.mark.parametrize("fields", [
    {"author": "Doe, J.", "title": "T", "doi": "10.48550/arXiv.2101.00001"},
    {"author": "Doe, J.", "title": "T", "archiveprefix": "arXiv", "eprint": "2101.00001"},
    {"author": "Doe, J.", "title": "T", "howpublished": "arXiv preprint"},
    {"author": "Doe, J.", "title": "T", "howpublished": "arXiv:2603.02960 (preprint)"},
])
def test_arxiv_preprint_stamped_without_a_request(monkeypatch, fields):
    """R2."""
    values, report, fake = _run(monkeypatch, {"x": _e(fields, etype="misc")})
    assert values == {"x": "preprint"} and fake.calls == []
    assert report["entries"]["x"] == "stamped" and report["preprint_arxiv"] == 1


def test_a_journal_article_with_an_eprint_is_not_a_preprint(monkeypatch):
    fields = {"author": "Doe, J.", "title": "T", "journal": "Mind",
              "archiveprefix": "arXiv", "eprint": "2101.00001",
              "doi": "10.48550/arXiv.2101.00001"}
    values, report, _ = _run(monkeypatch, {"x": _e(fields)})
    assert values == {} and report["entries"]["x"] == "not_requested:arxiv"


def test_arxiv_rule_needs_a_real_tier(monkeypatch):
    fields = {"author": "Doe, J.", "title": "T", "howpublished": "arXiv preprint"}
    values, report, _ = _run(monkeypatch, {"x": _e(fields, none=True)})
    assert values == {} and report["entries"]["x"] == "not_requested:evidence-none"


def test_a_trailing_footnote_number_on_the_crossref_title_matches(monkeypatch):
    """R3: 10.4324/9781003004431-10 is titled "... echo chambers 1"."""
    moller = {"author": "M{\\\"o}ller, Judith", "doi": "10.4324/9781003004431-10",
              "title": "Filter bubbles and digital echo chambers"}
    rec = _record("10.4324/9781003004431-10", "fwd_recall")
    assert sn.decode_crossref_title(rec["title"][0]).endswith(" 1")
    assert _identity(moller, rec)
    assert sn.identity_check(moller, rec, "incollection") == "match"


def test_the_trailing_number_rule_is_narrow(monkeypatch):
    rec = _gerlich_with(author=[{"family": "Smith"}], title=["Essays 2"])
    assert not _identity({"author": "Smith, J.", "title": "Essays 1"}, rec)
    rec = _gerlich_with(author=[{"family": "Smith"}], title=["Essays 123"])
    assert not _identity({"author": "Smith, J.", "title": "Essays"}, rec)
    rec = _gerlich_with(author=[{"family": "Smith"}], title=["Essays 1 2"])
    assert not _identity({"author": "Smith, J.", "title": "Essays 1"}, rec)


def test_an_edited_book_matches_on_its_editors(monkeypatch):
    """R4: CrossRef records 10.1093/acprof:oso/9780199338207.001.0001 by its
    editors only; the bib @book lists them as author."""
    coons = {"author": "Coons, Christian and Weber, Michael", "title": "Manipulation",
             "doi": "10.1093/acprof:oso/9780199338207.001.0001"}
    rec = _record("10.1093/acprof:oso/9780199338207.001.0001", "fwd_recall")
    assert not rec.get("author") and rec["editor"]
    assert sn.identity_check(coons, rec, "book") == "match"
    assert sn.identity_check(dict(coons, author="Smith, A."), rec, "book") == "mismatch"
    assert sn.identity_check({"editor": "Coons, Christian", "title": "Manipulation"},
                             rec, "incollection") == "mismatch"   # type conflict
    assert sn.identity_check({"editor": "Coons, Christian", "title": "Manipulation"},
                             rec, None) == "match"
    assert sn.identity_check(coons, rec, "article") == "mismatch"


def test_no_authors_and_no_editors_stays_unverifiable():
    rec = {k: v for k, v in _record("10.1093/acprof:oso/9780199338207.001.0001",
                                    "fwd_recall").items() if k != "editor"}
    assert sn.identity_check({"author": "Coons, C.", "title": "Manipulation"},
                             rec, "book") == "unverifiable"

