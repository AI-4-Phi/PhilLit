"""PL-39: the evidence barrier's `status_notice` field -- derivation, the
shared metadata window with venue vetting, the strip, and the splice."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT / "tests"))

import evidence_barrier as eb  # noqa: E402
import status_notice as sn  # noqa: E402
import venue_vetting as vv  # noqa: E402
from test_evidence_barrier import _cleaning, _domain, _enrichment, _report  # noqa: E402
from test_status_notice import FakeCrossRef, _NoWait  # noqa: E402

GERLICH_BIB = """@article{gerlich2025ai,
  author = {Gerlich, Michael},
  title = {{AI} Tools in Society: Impacts on Cognitive Offloading and the Future of Critical Thinking},
  journal = {Societies},
  doi = {10.3390/soc15010006},
  year = {2025}
}"""

STERELNY_BIB = """@article{sterelny2010minds,
  author = {Sterelny, Kim},
  title = {Minds: Extended or Scaffolded?},
  journal = {Phenomenology and the Cognitive Sciences},
  doi = {10.1007/s11097-010-9174-y},
  year = {2010}
}"""

VERIFIED = {
    "gerlich2025ai": {"api_matched": True, "verified_identifier": "doi",
                      "verified_identifier_value": "10.3390/soc15010006",
                      "entry_type": "article"},
    "sterelny2010minds": {"api_matched": True, "verified_identifier": "doi",
                          "verified_identifier_value": "10.1007/s11097-010-9174-y",
                          "entry_type": "article"},
}


@pytest.fixture
def crossref(monkeypatch):
    """The status pass switched on against the recorded payloads."""
    monkeypatch.delenv("PHILLIT_STATUS_NOTICE", raising=False)
    monkeypatch.setattr(sn, "get_limiter", lambda *a, **k: _NoWait())
    fake = FakeCrossRef()
    monkeypatch.setattr(sn, "_http_get", fake)
    return fake


def _review(tmp_path, bib, entries=VERIFIED):
    rd = tmp_path / "review"
    _domain(rd, 1, bib, cleaning=_cleaning(1, entries), enrichment=_enrichment(1))
    return rd


def _bib(rd):
    return (rd / "literature-domain-1.bib").read_text(encoding="utf-8")


def _chunk(text, key):
    return next(c for c in text.split("\n@") if key in c.split("\n", 1)[0])


def test_status_notice_is_a_derived_field():
    assert "status_notice" in eb._DERIVED_FIELDS
    assert len(eb._DERIVED_FIELDS) == 7


def test_verified_entry_is_stamped_and_reported(tmp_path, crossref, capsys):
    rd = _review(tmp_path, GERLICH_BIB + "\n\n" + STERELNY_BIB)
    assert eb.execute(rd, 1) == 0
    text = _bib(rd)
    assert "status_notice = {correction 10.3390/soc15090252}" in _chunk(text, "gerlich2025ai")
    assert "status_notice" not in _chunk(text, "sterelny2010minds")
    rep = _report(rd)["status_notice"]
    assert rep["status"] == "complete" and rep["reason"] is None
    assert rep["stamped"] == {"correction": 1}
    assert rep["entries"] == {"literature-domain-1.bib:gerlich2025ai": "stamped",
                              "literature-domain-1.bib:sterelny2010minds": "checked_none"}
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert printed["status_notice"]["status"] == "complete"
    assert printed["status_notice"]["stamped"] == {"correction": 1}


def test_evidence_none_entry_is_not_looked_up(tmp_path, crossref):
    rd = _review(tmp_path, GERLICH_BIB, entries={})
    assert eb.execute(rd, 1) == 0
    assert "status_notice" not in _bib(rd)
    assert crossref.calls == []
    assert _report(rd)["status_notice"]["entries"] == {
        "literature-domain-1.bib:gerlich2025ai": "not_requested:evidence-none"}


def test_stamp_does_not_change_tiers(tmp_path, crossref, monkeypatch):
    tiers = {}
    for label, switch in (("on", None), ("off", "off")):
        if switch:
            monkeypatch.setenv("PHILLIT_STATUS_NOTICE", switch)
        rd = tmp_path / label
        _domain(rd, 1, GERLICH_BIB, cleaning=_cleaning(1, VERIFIED),
                enrichment=_enrichment(1))
        assert eb.execute(rd, 1) == 0
        tiers[label] = _report(rd)["stamps"]
    assert tiers["on"] == tiers["off"]
    assert tiers["on"]["literature-domain-1.bib"]["gerlich2025ai"] == "EVIDENCE-EXISTENCE"


@pytest.mark.parametrize("forged", [
    "  status_notice = {retraction 10.1000/fake},\n",
    '  status_notice = "retraction 10.1000/fake",\n',
    "  status_notice={{retraction} 10.1000/fake},\n",
    "  status_notice = 2024,\n",
])
def test_hand_written_field_never_survives(tmp_path, crossref, forged):
    bib = STERELNY_BIB.replace("  year = {2010}\n", forged + "  year = {2010}\n")
    rd = _review(tmp_path, bib)
    assert eb.execute(rd, 1) == 0
    text = _bib(rd)
    assert "10.1000/fake" not in text
    assert "status_notice" not in text


def test_compact_header_line_field_is_stripped(tmp_path, crossref):
    bib = STERELNY_BIB.replace("@article{sterelny2010minds,",
                               "@article{sterelny2010minds,status_notice={retraction 10.1000/fake},")
    rd = _review(tmp_path, bib)
    assert eb.execute(rd, 1) == 0
    assert "status_notice" not in _bib(rd)


def test_literal_text_inside_an_abstract_is_not_a_field(tmp_path, crossref):
    """The strip removes fields only: the words in an abstract stay, and the
    run does not mistake them for a surviving field."""
    bib = STERELNY_BIB.replace(
        "  year = {2010}\n",
        "  abstract = {A note: status_notice = {retraction 10.1000/x} is only text.},\n"
        "  year = {2010}\n")
    rd = _review(tmp_path, bib)
    assert eb.execute(rd, 1) == 0
    text = _bib(rd)
    assert "status_notice = {retraction 10.1000/x} is only text." in text
    fields = eb.se.parse_entry_fields(_chunk(text, "sterelny2010minds"))
    assert "status_notice" not in fields


def test_a_surviving_field_after_the_strip_fails_the_run(tmp_path, crossref, monkeypatch):
    """The barrier asserts the strip worked: a status_notice it did not
    derive must never reach a writer."""
    bib = STERELNY_BIB.replace("  year = {2010}\n",
                               "  status_notice = {retraction 10.1000/fake},\n  year = {2010}\n")
    rd = _review(tmp_path, bib)
    monkeypatch.setattr(eb, "_strip_derived_fields", lambda text: text)
    assert eb.execute(rd, 1) == 1
    assert _report(rd)["status"] == "failed"
    assert "10.1000/fake" in _bib(rd)   # nothing was written


def test_stale_field_removed_when_the_pass_is_off(tmp_path, monkeypatch):
    monkeypatch.setenv("PHILLIT_STATUS_NOTICE", "off")
    bib = GERLICH_BIB.replace("  year = {2025}\n",
                              "  status_notice = {correction 10.3390/soc15090252},\n"
                              "  year = {2025}\n")
    rd = _review(tmp_path, bib)
    assert eb.execute(rd, 1) == 0
    assert "status_notice" not in _bib(rd)
    rep = _report(rd)["status_notice"]
    assert rep["status"] == "skipped" and "PHILLIT_STATUS_NOTICE" in rep["reason"]


def test_a_swallowed_splice_is_reported(tmp_path, crossref, monkeypatch):
    real = eb._stamp_optional_field
    monkeypatch.setattr(
        eb, "_stamp_optional_field",
        lambda text, field, value: text if field == "status_notice" else real(text, field, value))
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    assert "status_notice" not in _bib(rd)
    rep = _report(rd)["status_notice"]
    assert rep["entries"]["literature-domain-1.bib:gerlich2025ai"] == "splice_failed"
    assert rep["splice_failed"] == 1 and rep["stamped"] == {}
    assert rep["status"] == "partial" and "splice" in rep["reason"]


def test_a_crashing_pass_never_fails_the_barrier(tmp_path, crossref, monkeypatch):
    def boom(entries, deadline):
        raise RuntimeError("crossref exploded")
    monkeypatch.setattr(eb.sn, "lookup_status", boom)
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    assert "status_notice" not in _bib(rd)
    rep = _report(rd)["status_notice"]
    assert rep["status"] == "partial" and "RuntimeError" in rep["reason"]


def test_status_and_venue_share_one_absolute_deadline(tmp_path, crossref, monkeypatch):
    order = []

    def status(entries, deadline):
        order.append(("status", deadline))
        return {}, sn.empty_report()

    def vet(names, deadline=None):
        order.append(("venue", deadline))
        return {"status": "complete", "reason": None, "verdicts": {}, "flagged": []}
    monkeypatch.setattr(eb.sn, "lookup_status", status)
    monkeypatch.setattr(eb.vv, "vet_venues", vet)
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    assert [o[0] for o in order] == ["status", "venue"]
    assert order[0][1] == order[1][1] is not None


def test_a_slow_status_pass_shrinks_venue_vettings_share(tmp_path, crossref, monkeypatch):
    """The status pass runs first; if it uses up the window, venue vetting
    sends nothing and reports the deadline."""
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
    monkeypatch.setattr(vv, "get_limiter", lambda *a, **k: _NoWait())
    calls = []
    monkeypatch.setattr(vv.requests, "get", lambda *a, **k: calls.append(1))
    real_lookup = eb.sn.lookup_status

    def slow(entries, deadline):
        clock["t"] = deadline + 1.0
        return real_lookup(entries, deadline)
    clock = {"t": 0.0}
    real_monotonic = vv.time.monotonic
    monkeypatch.setattr(eb.sn, "lookup_status", slow)
    monkeypatch.setattr(vv.time, "monotonic", lambda: real_monotonic() + clock["t"])
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    assert calls == []
    rep = _report(rd)
    assert "deadline" in rep["venue_vetting"]["reason"]
    assert rep["status_notice"]["entries"]["literature-domain-1.bib:gerlich2025ai"] == "deadline"
    assert rep["status_notice"]["status"] == "partial"


def test_metadata_window_stays_inside_the_pinned_budget():
    """One window for both passes: the PL-31 sum is unchanged, and the
    status pass uses venue vetting's request timeout."""
    after = (eb.CORROBORATION_RUN_CEILING_SECONDS + vv.PASS_DEADLINE_SECONDS
             + vv.REQUEST_TIMEOUT + eb.FULLTEXT_PASS_SECONDS)
    assert after <= eb.FULLTEXT_RUN_CEILING_SECONDS < 600
    assert sn.REQUEST_TIMEOUT == vv.REQUEST_TIMEOUT


def test_the_barrier_passes_the_entry_type(tmp_path, crossref, monkeypatch):
    """P2: the lookup can only check type compatibility if it gets the type."""
    seen = {}
    real = eb.sn.lookup_status

    def spy(entries, deadline):
        seen.update(entries)
        return real(entries, deadline)
    monkeypatch.setattr(eb.sn, "lookup_status", spy)
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    assert seen["literature-domain-1.bib:gerlich2025ai"]["entry_type"] == "article"


def test_late_promotion_is_not_checked_and_partial(tmp_path, crossref, monkeypatch):
    """P7: an entry NONE at the metadata phase but promoted later is never
    looked up; the report says so instead of calling it evidence-none."""
    real = eb.se.compute_tier
    calls = {"n": 0}

    def provisional_none(etype, fields, att):
        calls["n"] += 1
        return eb.se.TIER_NONE if calls["n"] == 1 else real(etype, fields, att)
    monkeypatch.setattr(eb.se, "compute_tier", provisional_none)
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    rep = _report(rd)
    assert rep["stamps"]["literature-domain-1.bib"]["gerlich2025ai"] == "EVIDENCE-EXISTENCE"
    state = rep["status_notice"]["entries"]["literature-domain-1.bib:gerlich2025ai"]
    assert state == "not_checked:late-promotion"
    assert rep["status_notice"]["status"] == "complete"     # Z4
    assert rep["status_notice"]["late_promotion"] == 1
    assert "status_notice" not in _bib(rd)


def test_printed_summary_carries_the_diagnostic_counts(tmp_path, crossref, capsys):
    """P12: the operator line shows what the report holds, and only the
    entries that need a look."""
    arxiv = STERELNY_BIB.replace("sterelny2010minds", "arx2021x").replace(
        "10.1007/s11097-010-9174-y", "10.48550/arXiv.2101.00001")
    rd = _review(tmp_path, GERLICH_BIB + "\n\n" + STERELNY_BIB + "\n\n" + arxiv,
                 entries=dict(VERIFIED, arx2021x={
                     "api_matched": True, "verified_identifier": "doi",
                     "verified_identifier_value": "10.48550/arxiv.2101.00001",
                     "entry_type": "article"}))
    assert eb.execute(rd, 1) == 0
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["status_notice"]
    for key in ("unmapped_types", "ignored_types", "sources", "arxiv_skipped", "reverse_unchecked",
                "unresolved", "late_promotion", "notice_rescinded", "notice_unverified",
                "preprint_arxiv"):
        assert key in printed
    assert printed["sources"] == {"publisher": 1}
    assert printed["arxiv_skipped"] == 1
    assert printed["entries"] == {"literature-domain-1.bib:arx2021x": "not_requested:arxiv"}


def test_late_promotion_shows_in_the_printed_entries(tmp_path, crossref, monkeypatch, capsys):
    real = eb.se.compute_tier
    calls = {"n": 0}

    def provisional_none(etype, fields, att):
        calls["n"] += 1
        return eb.se.TIER_NONE if calls["n"] == 1 else real(etype, fields, att)
    monkeypatch.setattr(eb.se, "compute_tier", provisional_none)
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["status_notice"]
    assert printed["entries"] == {
        "literature-domain-1.bib:gerlich2025ai": "not_checked:late-promotion"}


def test_a_stamp_on_an_entry_demoted_to_none_is_dropped(tmp_path, crossref, monkeypatch, capsys):
    """Z8: looked up at a real tier, NONE at the final tier: no field, and
    the state says so."""
    real = eb.se.compute_tier
    calls = {"n": 0}

    def demote_later(etype, fields, att):
        calls["n"] += 1
        return real(etype, fields, att) if calls["n"] == 1 else eb.se.TIER_NONE
    monkeypatch.setattr(eb.se, "compute_tier", demote_later)
    rd = _review(tmp_path, GERLICH_BIB)
    assert eb.execute(rd, 1) == 0
    assert "status_notice" not in _bib(rd)
    rep = _report(rd)["status_notice"]
    assert rep["entries"]["literature-domain-1.bib:gerlich2025ai"] == "dropped:demoted"
    assert rep["stamped"] == {}
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["status_notice"]
    assert printed["entries"] == {"literature-domain-1.bib:gerlich2025ai": "dropped:demoted"}
