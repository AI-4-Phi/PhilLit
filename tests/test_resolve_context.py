"""Tests for resolve_context.py -- SEP/IEP matching and passage extraction."""
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from resolve_context import (
    load_slug_files, first_author_surname, title_score, match_entry_to_article,
)


def _article(bib_lines, sections=None, preamble=""):
    return {
        "entry_name": "test-entry",
        "title": "Test Entry",
        "preamble": preamble,
        "sections": sections or {},
        "bibliography": [{"raw": line, "parsed": None, "confidence": "low"} for line in bib_lines],
    }


class TestSlugManifest:
    def test_valid_empty_vs_missing_vs_malformed(self, tmp_path):
        ok = tmp_path / "encyclopedia_entries-domain-1.json"
        ok.write_text('{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
        bad = tmp_path / "encyclopedia_entries-domain-2.json"
        bad.write_text("not json", encoding="utf-8")
        missing = tmp_path / "encyclopedia_entries-domain-3.json"
        states, union = load_slug_files([ok, bad, missing])
        assert states[str(ok)] == "valid-empty"
        assert states[str(bad)] == "malformed"
        assert states[str(missing)] == "missing"
        assert union == {"sep": set(), "iep": set()}

    def test_union_across_domains(self, tmp_path):
        a = tmp_path / "e1.json"
        a.write_text('{"sep_entries": ["freewill"], "iep_entries": []}', encoding="utf-8")
        b = tmp_path / "e2.json"
        b.write_text('{"sep_entries": ["compatibilism", "freewill"], "iep_entries": ["kuhn"]}', encoding="utf-8")
        states, union = load_slug_files([a, b])
        assert union["sep"] == {"freewill", "compatibilism"}
        assert union["iep"] == {"kuhn"}
        assert states[str(a)] == "present"


class TestSurnameAndTitle:
    def test_first_author_surname(self):
        assert first_author_surname("Kuhn, Thomas S. and Popper, Karl") == "Kuhn"

    def test_title_score_full_overlap(self):
        assert title_score(
            "The Structure of Scientific Revolutions",
            "Kuhn, T., 1962, The Structure of Scientific Revolutions, Chicago.",
        ) == 1.0

    def test_title_score_subtitle_edition_still_matches(self):
        s = title_score(
            "The Structure of Scientific Revolutions",
            "Kuhn, T., 1962, The Structure of Scientific Revolutions: 50th Anniversary Edition.",
        )
        assert s >= 0.5

    def test_generic_title_needs_two_overlapping_tokens(self):
        # single shared trivial token must not pass TITLE_MIN_OVERLAP
        assert title_score("Freedom", "Frankfurt, H., 1971, Freedom of the Will.") == 0.0


class TestMatchEntry:
    KUHN = {"author": "Kuhn, Thomas S.", "year": "1962",
            "title": "The Structure of Scientific Revolutions"}

    def test_unique_match(self):
        art = _article([
            "Kuhn, T., 1962, The Structure of Scientific Revolutions, University of Chicago Press.",
            "Popper, K., 1959, The Logic of Scientific Discovery, Hutchinson.",
        ])
        m = match_entry_to_article(self.KUHN, art)
        assert m and not m.get("ambiguous")
        assert "Structure" in m["line"]

    def test_no_candidate_returns_none(self):
        art = _article(["Popper, K., 1959, The Logic of Scientific Discovery."])
        assert match_entry_to_article(self.KUHN, art) is None

    def test_same_surname_same_year_different_work_no_title_overlap(self):
        # collision matrix: candidate line exists but title cannot corroborate
        art = _article(["Kuhn, T., 1962, The Function of Dogma in Scientific Research."])
        assert match_entry_to_article(self.KUHN, art) is None

    def test_two_indistinguishable_candidates_ambiguous(self):
        # both candidate lines contain ALL of the bib title's tokens, so both
        # pass the threshold and the matcher MUST return the ambiguous sentinel
        art = _article([
            "Lewis, D., 1979a, Counterfactual Dependence and Time's Arrow, reprint.",
            "Lewis, D., 1979b, More on Counterfactual Dependence and Time's Arrow.",
        ])
        fields = {"author": "Lewis, David", "year": "1979",
                  "title": "Counterfactual Dependence and Time's Arrow"}
        m = match_entry_to_article(fields, art)
        assert m is not None
        assert m.get("ambiguous") is True

    def test_surname_substring_does_not_match(self):
        # word boundary: 'Mill' must not match 'Miller'; year must not match
        # inside a page range
        art = _article(["Miller, M., 1859, On Liberty and Other Essays, pp. 1859-1900."])
        fields = {"author": "Mill, John Stuart", "year": "1859",
                  "title": "On Liberty"}
        assert match_entry_to_article(fields, art) is None

    def test_translated_title_conservatively_misses(self):
        art = _article(["Husserl, E., 1913, Ideen zu einer reinen Phaenomenologie."])
        fields = {"author": "Husserl, Edmund", "year": "1913",
                  "title": "Ideas Pertaining to a Pure Phenomenology"}
        assert match_entry_to_article(fields, art) is None

    def test_suffix_captured(self):
        art = _article(["Lewis, D., 1979a, Counterfactual Dependence and Time's Arrow."])
        fields = {"author": "Lewis, David", "year": "1979",
                  "title": "Counterfactual Dependence and Time's Arrow"}
        m = match_entry_to_article(fields, art)
        assert m["suffix"] == "a"
