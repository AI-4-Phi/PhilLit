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


@pytest.fixture(autouse=True)
def _no_real_rate_limiting(monkeypatch):
    # lookup_venue() calls get_limiter("openalex").wait(), which is a real
    # file-locked, wall-clock rate limiter (0.11s/request). Left unpatched,
    # any test making several sequential lookups sleeps for real time --
    # forbidden by this suite's test discipline. The return value is unused
    # by lookup_venue, so a no-op stand-in is safe everywhere.
    class _NoWaitLimiter:
        def wait(self):
            return 0.0
    monkeypatch.setattr(vv, "get_limiter", lambda *a, **k: _NoWaitLimiter())


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


class TestTriStateSignals:
    """Item 3 D hardening: a missing/null/malformed field must never read as
    affirmative "non-core" / "non-DOAJ" evidence -- only an exact `False`
    (or an exact int h_index) may trigger the rule."""

    def test_missing_is_core_not_flagged(self):
        rec = {"schema_version": vv.RECORD_SCHEMA_VERSION, "resolved": True,
               "is_in_doaj": False, "h_index": 2}
        assert vv.is_flagged(rec) is False

    def test_null_is_in_doaj_not_flagged(self):
        rec = {"schema_version": vv.RECORD_SCHEMA_VERSION, "resolved": True,
               "is_core": False, "is_in_doaj": None, "h_index": 2}
        assert vv.is_flagged(rec) is False

    def test_string_false_for_is_core_not_flagged(self):
        # bool("false") is True -- a truthy-but-wrong-type value must not
        # count as the exact boolean False the rule requires.
        rec = {"schema_version": vv.RECORD_SCHEMA_VERSION, "resolved": True,
               "is_core": "false", "is_in_doaj": False, "h_index": 2}
        assert vv.is_flagged(rec) is False

    def test_string_false_for_is_in_doaj_not_flagged(self):
        rec = {"schema_version": vv.RECORD_SCHEMA_VERSION, "resolved": True,
               "is_core": False, "is_in_doaj": "false", "h_index": 2}
        assert vv.is_flagged(rec) is False

    def test_bool_h_index_not_flagged(self):
        # isinstance(True, int) is True in Python -- must be excluded explicitly.
        rec = {"schema_version": vv.RECORD_SCHEMA_VERSION, "resolved": True,
               "is_core": False, "is_in_doaj": False, "h_index": True}
        assert vv.is_flagged(rec) is False

    def test_non_numeric_h_index_not_flagged(self):
        rec = {"schema_version": vv.RECORD_SCHEMA_VERSION, "resolved": True,
               "is_core": False, "is_in_doaj": False, "h_index": "2"}
        assert vv.is_flagged(rec) is False

    def test_is_flagged_never_raises_on_malformed_record(self):
        for bad in ["a string", 42, ["list"], object()]:
            assert vv.is_flagged(bad) is False

    def test_record_from_hits_stores_raw_booleans(self):
        # A hit missing "is_core" entirely (not via the hit() helper, which
        # always sets a literal bool) must round-trip as None, not False.
        raw_hit = {"display_name": "Sparse Journal",
                   "summary_stats": {"h_index": 2}}
        rec = vv.record_from_hits([raw_hit])
        assert rec["is_core"] is None
        assert rec["is_in_doaj"] is None
        assert vv.is_flagged(rec) is False

    def test_malformed_cached_record_reads_as_miss(self, tmp_path, monkeypatch):
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        # Right schema_version, right top-level shape, but a string h_index --
        # cache_get must validate the record's SHAPE, not just schema_version.
        vv.cache_put("Malformed", {
            "schema_version": vv.RECORD_SCHEMA_VERSION, "resolved": True,
            "matched_name": "Malformed", "h_index": "high",
            "is_core": False, "is_in_doaj": False, "works_count": 1,
            "fetched_at": time.time(),
        })
        assert vv.cache_get("Malformed") is None


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

    def test_flagged_ttl_is_45_days(self):
        assert vv.FLAGGED_CACHE_TTL_SECONDS == 45 * 24 * 3600

    def test_stale_flagged_record_reads_as_miss(self, tmp_path, monkeypatch):
        # A stale CLEAR verdict just costs a miss; a stale FLAG keeps
        # discrediting a venue that may since have joined DOAJ, gone core,
        # or grown past the threshold -- so flagged records get the shorter
        # asymmetric TTL, checked against the record's own fetched_at, not
        # the cache file's mtime.
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        old = time.time() - (46 * 24 * 3600)
        rec = vv.record_from_hits([hit("Small Journal", 2, False, False)])
        rec["fetched_at"] = old
        vv.cache_put("Small Journal", rec)
        assert vv.is_flagged(rec) is True  # sanity: this record IS a flag
        assert vv.cache_get("small journal") is None

    def test_stale_clear_record_still_a_hit(self, tmp_path, monkeypatch):
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        old = time.time() - (46 * 24 * 3600)
        rec = vv.record_from_hits([hit("Synthese", 164, True, False)])  # clear: is_core
        rec["fetched_at"] = old
        vv.cache_put("Synthese", rec)
        assert vv.is_flagged(rec) is False  # sanity: this record is clear
        assert vv.cache_get("synthese") == rec

    def test_flagged_record_with_no_fetched_at_reads_as_miss(self, tmp_path, monkeypatch):
        # No usable fetched_at -> treated as expired for the flagged case:
        # fail toward re-checking, never toward keeping a stale discredit.
        import search_cache
        monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path)
        rec = vv.record_from_hits([hit("Small Journal", 2, False, False)])
        del rec["fetched_at"]
        vv.cache_put("Small Journal", rec)
        assert vv.cache_get("small journal") is None


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

    def test_per_page_is_200(self, monkeypatch):
        captured = {}
        def responder(*a, **k):
            captured.update(k["params"])
            return FakeResponse(payload={"results": []})
        monkeypatch.setattr(vv.requests, "get", responder)
        vv.lookup_venue("Whatever", {"api_key": "x"})
        assert captured["per_page"] == 200


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


class TestRawNameQuery:
    """Item 3 D hardening: query OpenAlex with the RAW name (the validated
    measurement queried raw names, and punctuation-stripping before the
    query changes what OpenAlex's fuzzy search ranks), while the cache key
    and exact-match target stay normalized."""

    def test_queries_with_raw_not_normalized_name(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        captured = {}
        def responder(*a, **k):
            captured["filter"] = k["params"]["filter"]
            return FakeResponse(payload={"results": []})
        monkeypatch.setattr(vv.requests, "get", responder)
        vv.vet_venues(["The Journal, Of Ratio!"])
        assert captured["filter"] == "display_name.search:The Journal, Of Ratio!"

    def test_differently_cased_raw_name_is_cache_hit(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        calls = []
        payload = {"results": [hit("Small Journal", 2, False, False)]}
        def counted(*a, **k):
            calls.append(k["params"]["filter"])
            return FakeResponse(payload=payload)
        monkeypatch.setattr(vv.requests, "get", counted)
        first = vv.vet_venues(["small journal"])
        second = vv.vet_venues(["SMALL JOURNAL"])
        assert len(calls) == 1  # one distinct normalized key -- one network call
        assert calls[0] == "display_name.search:small journal"
        assert first["flagged"] == ["small journal"]
        assert second["cache_hits"] == 1 and second["looked_up"] == 0
        assert second["flagged"] == ["small journal"]

    def test_representative_raw_name_is_first_after_sort(self, monkeypatch, isolated_cache):
        # Both inputs normalize to "small journal"; sorted() over the raw
        # inputs picks "SMALL JOURNAL" (capitals sort before lowercase in
        # ASCII) as the deterministic representative queried.
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        captured = {}
        def responder(*a, **k):
            captured["filter"] = k["params"]["filter"]
            return FakeResponse(payload={"results": []})
        monkeypatch.setattr(vv.requests, "get", responder)
        vv.vet_venues(["small journal", "SMALL JOURNAL"])
        assert captured["filter"] == "display_name.search:SMALL JOURNAL"


class TestHonestStatusAndErrors:
    """Item 3 D hardening: "complete" must mean complete. A pass that errors
    out or hits the lookup cap must say so, and must not silently drop
    verdicts it already resolved."""

    def test_all_errors_status_partial(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(status_code=500))
        result = vv.vet_venues(["A Journal", "B Journal"])
        assert result["status"] == "partial"
        assert result["lookup_errors"] == 2
        assert result["errors"] == ["a journal", "b journal"]
        assert result["flagged"] == []

    def test_one_success_then_error_survives(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        def responder(*a, **k):
            if "aa journal" in k["params"]["filter"].lower():
                return FakeResponse(payload={"results": [hit("AA Journal", 2, False, False)]})
            return FakeResponse(status_code=500)
        monkeypatch.setattr(vv.requests, "get", responder)
        result = vv.vet_venues(["AA Journal", "ZZ Journal"])  # sorted: aa before zz
        assert result["flagged"] == ["aa journal"]
        assert result["status"] == "partial"
        assert result["lookup_errors"] == 1
        assert result["errors"] == ["zz journal"]
        assert result["resolved"] == 1
        assert result["unresolved"] == 0

    def test_budget_exhaustion_increments_looked_up(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        def responder(*a, **k):
            if "aa journal" in k["params"]["filter"].lower():
                return FakeResponse(payload={"results": [hit("AA Journal", 2, False, False)]})
            return FakeResponse(status_code=429, headers={"Retry-After": "81471"},
                                 text="insufficient budget")
        monkeypatch.setattr(vv.requests, "get", responder)
        result = vv.vet_venues(["AA Journal", "ZZ Journal"])
        assert result["flagged"] == ["aa journal"]  # earlier flag survives
        assert result["looked_up"] == 2  # the exhausting call counts too
        assert result["status"] == "budget_exhausted"

    def test_capped_names_reported(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        monkeypatch.setattr(vv, "MAX_LOOKUPS_PER_RUN", 2)
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload={"results": []}))
        result = vv.vet_venues([f"Journal {i}" for i in range(5)])
        assert result["skipped_cap"] == 3
        assert len(result["capped"]) == 3
        assert set(result["capped"]) == {"journal 2", "journal 3", "journal 4"}
        assert result["status"] == "partial"
        assert "cap" in result["reason"]

    def test_unresolved_venue_counted(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload={"results": []}))
        result = vv.vet_venues(["Nonexistent Journal"])
        assert result["resolved"] == 0
        assert result["unresolved"] == 1
        assert result["status"] == "complete"

    def test_all_keys_present_even_on_clean_pass(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload={"results": []}))
        result = vv.vet_venues(["Some Journal"])
        for key in ("lookup_errors", "errors", "capped", "unresolved", "resolved"):
            assert key in result
        assert result["lookup_errors"] == 0
        assert result["errors"] == []
        assert result["capped"] == []

    def test_ok_outcome_with_no_record_never_raises(self, monkeypatch, isolated_cache):
        # Defensive: lookup_venue's contract never pairs "ok" with a None
        # record, but vet_venues must not crash even if a future change to
        # lookup_venue broke that contract -- it must be treated as an
        # unresolved lookup, same as an "error" outcome.
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        monkeypatch.setattr(vv, "lookup_venue", lambda name, params: (None, "ok"))
        result = vv.vet_venues(["Some Journal"])
        assert result["status"] == "partial"
        assert result["lookup_errors"] == 1
        assert result["flagged"] == []


class TestTimeBounds:
    """Item 3 D hardening: 80 cold names at a 30s timeout is 40 minutes
    inside the workflow's slowest step -- bound both the error streak and
    the wall-clock time a pass may spend on network lookups."""

    def test_constants(self):
        assert vv.MAX_CONSECUTIVE_ERRORS == 3
        assert vv.PASS_DEADLINE_SECONDS == 120.0

    def test_three_consecutive_errors_stop_pass(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        calls = []
        def responder(*a, **k):
            calls.append(1)
            return FakeResponse(status_code=500)
        monkeypatch.setattr(vv.requests, "get", responder)
        result = vv.vet_venues(["01 err", "02 err", "03 err", "04 never"])
        assert len(calls) == 3  # stops before the fourth request
        assert result["status"] == "partial"
        assert result["lookup_errors"] == 3

    def test_success_between_errors_resets_counter(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        names = ["01 err", "02 err", "03 ok", "04 err", "05 err", "06 err", "07 never"]
        calls = []
        def responder(*a, **k):
            filt = k["params"]["filter"]
            calls.append(filt)
            if "03 ok" in filt:
                return FakeResponse(payload={"results": [hit("03 ok", 2, False, False)]})
            return FakeResponse(status_code=500)
        monkeypatch.setattr(vv.requests, "get", responder)
        result = vv.vet_venues(names)
        # 01, 02 (errors, streak=2), 03 (success, resets streak), 04, 05, 06
        # (errors, streak reaches 3 again) -- stops before 07.
        assert len(calls) == 6
        assert all("07 never" not in c for c in calls)
        assert result["status"] == "partial"
        assert result["flagged"] == ["03 ok"]  # the earlier success survives

    def test_deadline_stops_further_lookups(self, monkeypatch, isolated_cache):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        calls = []
        monkeypatch.setattr(vv.requests, "get",
                             lambda *a, **k: (calls.append(1), FakeResponse(payload={"results": []}))[1])
        # First call captures the deadline (t=0 -> deadline=120). The next
        # reads (one per venue, before each network lookup) all land past it.
        clock = iter([0.0, 1.0] + [vv.PASS_DEADLINE_SECONDS + 1] * 10)
        monkeypatch.setattr(vv.time, "monotonic", lambda: next(clock))
        result = vv.vet_venues(["Journal A", "Journal B", "Journal C"])
        assert len(calls) == 1  # only the first venue's lookup happened before the deadline
        assert result["capped"] == ["journal b", "journal c"]
        assert result["skipped_cap"] == 2
        assert result["status"] == "partial"
        assert "deadline" in result["reason"]  # distinguishable from a lookup-cap stop

    def test_cache_hits_do_not_count_against_deadline(self, monkeypatch, isolated_cache):
        # Populate the cache for one venue via a real lookup, then re-run
        # with the deadline already blown -- the cache hit must still be
        # served (cache hits do not count toward the deadline check).
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        payload = {"results": [hit("Small Journal", 2, False, False)]}
        monkeypatch.setattr(vv.requests, "get", lambda *a, **k: FakeResponse(payload=payload))
        vv.vet_venues(["Small Journal"])

        calls = []
        monkeypatch.setattr(vv.requests, "get",
                             lambda *a, **k: (calls.append(1), FakeResponse(payload={"results": []}))[1])
        clock = iter([0.0] + [vv.PASS_DEADLINE_SECONDS + 1] * 10)
        monkeypatch.setattr(vv.time, "monotonic", lambda: next(clock))
        result = vv.vet_venues(["Small Journal"])
        assert calls == []  # no network call -- served from cache
        assert result["cache_hits"] == 1
        assert result["flagged"] == ["small journal"]
