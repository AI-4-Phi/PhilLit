"""Item 3 D: the venue-vetting rule, normalization and cache.

Fixtures are the real OpenAlex facts measured 2026-08-05 (the measurement
data itself is local-only and untracked, so the numbers are inlined here).
"""
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import venue_vetting as vv


def hit(name, h, core, doaj, **kw):
    return {"display_name": name, "alternate_titles": kw.get("alt", []),
            "is_core": core, "is_in_doaj": doaj,
            "summary_stats": {"h_index": h}, "works_count": kw.get("works", 100)}


class TestNormalizeVenueName:
    def test_case_and_punctuation_folded(self):
        assert vv.normalize_venue_name("Philosophers' Imprint") == "philosophers imprint"

    def test_ampersand_becomes_and(self):
        assert vv.normalize_venue_name("Politics, Philosophy & Economics") == \
            vv.normalize_venue_name("Politics Philosophy and Economics")

    def test_leading_the_stripped(self):
        assert vv.normalize_venue_name("The Journal of Philosophy") == "journal of philosophy"

    def test_empty_and_none_are_empty(self):
        assert vv.normalize_venue_name("") == ""
        assert vv.normalize_venue_name(None) == ""


class TestSelectBestHit:
    def test_picks_highest_h_index(self):
        # Two real OpenAlex sources are named Phronesis; the small one must
        # not condemn the venue.
        hits = [hit("Phronesis", 3, False, False), hit("Phronesis", 86, False, False)]
        assert vv.select_best_hit(hits)["summary_stats"]["h_index"] == 86

    def test_missing_h_index_still_selectable(self):
        hits = [hit("X", None, False, False)]
        assert vv.select_best_hit(hits) is not None

    def test_empty_hits_is_none(self):
        assert vv.select_best_hit([]) is None


class TestRule:
    """Every case below is a venue measured on 2026-08-05."""

    def test_flags_measured_candidate(self):
        # Advanced International Journal for Research: h=2, non-core, non-DOAJ
        rec = vv.record_from_hits([hit("Advanced International Journal for Research", 2, False, False)])
        assert vv.is_flagged(rec) is True

    def test_doaj_rescues_small_legitimate_venue(self):
        # Norsk Filosofisk Tidsskrift: h=11, non-core, but DOAJ-listed.
        # This is the conjunct measure_d_threshold.py::flagged() omitted.
        rec = vv.record_from_hits([hit("Norsk Filosofisk Tidsskrift", 11, False, True)])
        assert vv.is_flagged(rec) is False

    def test_is_core_rescues_small_legitimate_venue(self):
        # Journal of Practical Ethics: h=7, core, DOAJ.
        rec = vv.record_from_hits([hit("Journal of Practical Ethics", 7, True, True)])
        assert vv.is_flagged(rec) is False

    def test_above_threshold_not_flagged(self):
        # Metascience: h=19, non-core, non-DOAJ -- clear at T=15, the reason
        # the threshold is not 20.
        rec = vv.record_from_hits([hit("Metascience", 19, False, False)])
        assert vv.is_flagged(rec) is False

    def test_unresolved_is_never_flagged(self):
        assert vv.is_flagged(vv.record_from_hits([])) is False
        assert vv.is_flagged(None) is False

    def test_missing_h_index_is_not_flagged(self):
        # No h-index is "unmeasured", not "low" -- fail open.
        rec = vv.record_from_hits([hit("Brand New Journal", None, False, False)])
        assert rec["h_index"] is None
        assert vv.is_flagged(rec) is False

    def test_flag_uses_best_hit_not_first(self):
        hits = [hit("Phronesis", 3, False, False), hit("Phronesis", 86, False, False)]
        assert vv.is_flagged(vv.record_from_hits(hits)) is False

    def test_threshold_is_fifteen(self):
        assert vv.H_INDEX_THRESHOLD == 15
        assert vv.is_flagged(vv.record_from_hits([hit("X", 14, False, False)])) is True
        assert vv.is_flagged(vv.record_from_hits([hit("X", 15, False, False)])) is False

    def test_record_carries_evidence_not_a_boolean(self):
        rec = vv.record_from_hits([hit("Small Journal", 2, False, False)])
        assert rec["resolved"] is True
        assert rec["h_index"] == 2
        assert rec["is_core"] is False
        assert rec["is_in_doaj"] is False
        assert rec["matched_name"] == "Small Journal"
        assert rec["schema_version"] == vv.RECORD_SCHEMA_VERSION
        assert "flagged" not in rec  # the rule is applied at read time


class TestCache:
    def test_roundtrip(self, tmp_path, monkeypatch):
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        rec = vv.record_from_hits([hit("Small Journal", 2, False, False)])
        vv.cache_put("Small Journal", rec)
        assert vv.cache_get("small journal") == rec  # keyed on the normalized name

    def test_miss_returns_none(self, tmp_path, monkeypatch):
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        assert vv.cache_get("Never Looked Up") is None

    def test_schema_mismatch_reads_as_miss(self, tmp_path, monkeypatch):
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        vv.cache_put("Legacy", {"schema_version": 0, "resolved": True})
        assert vv.cache_get("Legacy") is None

    def test_ttl_is_180_days(self):
        assert vv.CACHE_TTL_SECONDS == 180 * 24 * 3600

    def test_ttl_survives_search_cache_default_window(self, tmp_path, monkeypatch):
        # search_cache's own default TTL is 7 days; a venue record older than
        # that but younger than CACHE_TTL_SECONDS must still be a cache hit --
        # proving cache_get actually threads CACHE_TTL_SECONDS through to
        # get_cache rather than falling back to the 7-day default.
        import os
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        rec = vv.record_from_hits([hit("Small Journal", 2, False, False)])
        vv.cache_put("Small Journal", rec)
        cache_file = next(tmp_path.glob("*.pkl"))
        ten_days_ago = time.time() - 10 * 24 * 3600
        os.utime(cache_file, (ten_days_ago, ten_days_ago))
        assert vv.cache_get("small journal") == rec


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {"results": []}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    import search_cache
    monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
    return tmp_path


class TestLookupVenue:
    def test_exact_name_match_only(self, monkeypatch):
        # OpenAlex `display_name.search` is fuzzy: a search for "Ratio" also
        # returns "Ratio Juris". Only exact normalized matches may count.
        payload = {"results": [hit("Ratio Juris", 2, False, False),
                               hit("Ratio", 61, True, False)]}
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload=payload))
        record, outcome = vv.lookup_venue("Ratio", {"api_key": "x"})
        assert outcome == "ok"
        assert record["matched_name"] == "Ratio"
        assert record["h_index"] == 61

    def test_alternate_title_matches(self, monkeypatch):
        payload = {"results": [hit("Nous", 90, True, False, alt=["Nous (Detroit)"])]}
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload=payload))
        record, outcome = vv.lookup_venue("Nous (Detroit)", {"api_key": "x"})
        assert outcome == "ok" and record["resolved"] is True

    def test_no_match_is_unresolved_not_error(self, monkeypatch):
        payload = {"results": [hit("Something Else", 4, False, False)]}
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload=payload))
        record, outcome = vv.lookup_venue("Nonexistent Journal", {"api_key": "x"})
        assert outcome == "ok" and record["resolved"] is False

    def test_budget_exhaustion_reported(self, monkeypatch):
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(
            status_code=429, headers={"Retry-After": "81471"}, text="insufficient budget"))
        record, outcome = vv.lookup_venue("Whatever", {"api_key": "x"})
        assert outcome == "budget_exhausted" and record is None

    def test_http_error_is_error_not_exception(self, monkeypatch):
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(status_code=500))
        record, outcome = vv.lookup_venue("Whatever", {"api_key": "x"})
        assert outcome == "error" and record is None

    def test_network_exception_is_swallowed(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("connection reset")
        monkeypatch.setattr(vv.requests, "get", boom)
        record, outcome = vv.lookup_venue("Whatever", {"api_key": "x"})
        assert outcome == "error" and record is None

    def test_no_retry_on_error(self, monkeypatch):
        calls = []
        def once(*a, **k):
            calls.append(1)
            return FakeResponse(status_code=500)
        monkeypatch.setattr(vv.requests, "get", once)
        vv.lookup_venue("Whatever", {"api_key": "x"})
        assert len(calls) == 1  # one attempt, fail open -- never a backoff loop


class TestVetVenues:
    def test_skips_without_api_key(self, monkeypatch, isolated_cache):
        monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
        called = []
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: called.append(1))
        result = vv.vet_venues(["Some Journal"])
        assert result["status"] == "skipped"
        assert "OPENALEX_API_KEY" in result["reason"]
        assert called == []

    def test_flags_and_reports_evidence(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        payload = {"results": [hit("Small Journal", 2, False, False)]}
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload=payload))
        result = vv.vet_venues(["Small Journal"])
        assert result["status"] == "complete"
        assert result["flagged"] == ["small journal"]
        assert result["verdicts"]["small journal"] is True
        assert result["evidence"]["small journal"]["h_index"] == 2
        assert result["looked_up"] == 1

    def test_clear_venue_carries_no_evidence_blob(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        payload = {"results": [hit("Synthese", 164, True, False)]}
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload=payload))
        result = vv.vet_venues(["Synthese"])
        assert result["flagged"] == []
        assert result["verdicts"]["synthese"] is False
        assert result["evidence"] == {}

    def test_second_call_uses_cache(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        calls = []
        payload = {"results": [hit("Small Journal", 2, False, False)]}
        def counted(*a, **k):
            calls.append(1)
            return FakeResponse(payload=payload)
        monkeypatch.setattr(vv.requests, "get", counted)
        vv.vet_venues(["Small Journal"])
        second = vv.vet_venues(["Small Journal"])
        assert len(calls) == 1
        assert second["cache_hits"] == 1 and second["looked_up"] == 0
        assert second["flagged"] == ["small journal"]

    def test_duplicate_and_empty_names_collapse(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        calls = []
        def counted(*a, **k):
            calls.append(1)
            return FakeResponse(payload={"results": []})
        monkeypatch.setattr(vv.requests, "get", counted)
        result = vv.vet_venues(["Mind", "MIND", "  ", "", None, "The Mind"])
        assert len(calls) == 1  # one distinct normalized name
        assert result["looked_up"] == 1

    def test_budget_exhaustion_stops_the_pass(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        calls = []
        def exhausted(*a, **k):
            calls.append(1)
            return FakeResponse(status_code=429, headers={"Retry-After": "81471"},
                                text="insufficient budget")
        monkeypatch.setattr(vv.requests, "get", exhausted)
        result = vv.vet_venues(["A Journal", "B Journal", "C Journal"])
        assert result["status"] == "budget_exhausted"
        assert len(calls) == 1  # stops on the first exhaustion, does not grind
        assert result["flagged"] == []

    def test_cap_is_enforced_and_reported(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        monkeypatch.setattr(vv, "MAX_LOOKUPS_PER_RUN", 2)
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload={"results": []}))
        result = vv.vet_venues([f"Journal {i}" for i in range(5)])
        assert result["looked_up"] == 2
        assert result["skipped_cap"] == 3  # reported, never silent
