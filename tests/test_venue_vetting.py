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

    def test_missing_h_index_counts_as_zero(self):
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
