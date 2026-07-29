"""Tests for resolve_context.py -- SEP/IEP matching and passage extraction."""
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from resolve_context import (
    load_slug_files, first_author_surname, title_score, match_entry_to_article,
    extract_passage, format_context_value, strip_context_fields, acquire_context,
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

    def test_repeated_author_dash_line_matches(self):
        # SEP's repeated-author convention: the second-and-later works of an
        # author carry no surname. Regression for the Leonelli 2016 gate miss
        # in the 2026-07-25 A/B run -- zero candidates -> EXISTENCE, not CONTEXT.
        art = _article([
            "Leonelli, S., 2015, What Counts as Scientific Data?, Philosophy of Science.",
            "–––, 2016, Data-Centric Biology: A Philosophical Study, Chicago.",
        ])
        fields = {"author": "Leonelli, Sabina", "year": "2016",
                  "title": "Data-Centric Biology: A Philosophical Study"}
        m = match_entry_to_article(fields, art)
        assert m and not m.get("ambiguous")
        assert "Data-Centric Biology" in m["line"]

    def test_dash_line_inherits_nearest_explicit_author_only(self):
        # The carried author must be the immediately preceding explicit line,
        # not any earlier one: a neighbouring dash line of a DIFFERENT author
        # in the same year must not become a candidate (that neighbour is what
        # kept the real Leonelli match unambiguous).
        art = _article([
            "Leonelli, S., 2015, What Counts as Scientific Data?, Philosophy of Science.",
            "–––, 2016, Data-Centric Biology: A Philosophical Study, Chicago.",
            "Woodward, J., 2011, Data and Phenomena, Synthese.",
            "–––, 2016, Data-Centric Biology Reconsidered, Synthese.",
        ])
        fields = {"author": "Leonelli, Sabina", "year": "2016",
                  "title": "Data-Centric Biology: A Philosophical Study"}
        m = match_entry_to_article(fields, art)
        # Woodward's 2016 dash line inherits Woodward, so only one candidate
        # survives despite the near-identical title.
        assert m and not m.get("ambiguous")
        assert "Chicago" in m["line"]

    def test_dash_carries_author_prefix_not_previous_title(self):
        # Only the author segment may be carried. If the whole previous line
        # were inherited, its TITLE tokens would manufacture a surname hit.
        art = _article([
            "Smith, A., 1990, A Study of Leonelli's Method, Journal of Things.",
            "–––, 2016, Data-Centric Biology: A Philosophical Study, Chicago.",
        ])
        fields = {"author": "Leonelli, Sabina", "year": "2016",
                  "title": "Data-Centric Biology: A Philosophical Study"}
        assert match_entry_to_article(fields, art) is None

    def test_leading_dash_line_without_preceding_explicit_author(self):
        # A dash line before any explicit line has nothing to inherit; it must
        # not match and must not raise.
        art = _article([
            "–––, 2016, Data-Centric Biology: A Philosophical Study, Chicago.",
        ])
        fields = {"author": "Leonelli, Sabina", "year": "2016",
                  "title": "Data-Centric Biology: A Philosophical Study"}
        assert match_entry_to_article(fields, art) is None

    def test_hyphen_bullet_line_is_not_a_repeated_author_line(self):
        # A single leading hyphen is list punctuation, not the repeat rule.
        art = _article([
            "Smith, A., 1990, Some Other Work, Journal of Things.",
            "- 2016, Data-Centric Biology: A Philosophical Study, Chicago.",
        ])
        fields = {"author": "Leonelli, Sabina", "year": "2016",
                  "title": "Data-Centric Biology: A Philosophical Study"}
        assert match_entry_to_article(fields, art) is None

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


# Real fetch_sep.py/fetch_iep.py sections are keyed by id with
# {"id", "title", "content"} -- find_citations reads section["content"].
KUHN_SECTIONS = {
    "2": {"id": "2", "title": "Paradigms", "content":
          "In his landmark study, Kuhn (1962) argues that normal science "
          "proceeds under a paradigm until anomalies accumulate. This view "
          "reshaped philosophy of science."},
}
LEWIS_SECTIONS = {
    "3": {"id": "3", "title": "Time", "content":
          "Lewis (1979a) proposes an asymmetry of counterfactual dependence. "
          "Later, Lewis (1979b) turns to de se attitudes."},
}


class TestExtractPassage:
    def test_basic_extraction(self):
        art = _article([], sections=KUHN_SECTIONS)
        p = extract_passage(art, "Kuhn", "1962", suffix="", n_candidates=1)
        assert p and "normal science" in p["passage"]
        assert p["section"] == "2"

    def test_bibliography_hit_no_body_passage_returns_none(self):
        art = _article(["Kuhn, T., 1962, The Structure of Scientific Revolutions."])
        assert extract_passage(art, "Kuhn", "1962", suffix="", n_candidates=1) is None

    def test_suffix_attribution(self):
        art = _article([], sections=LEWIS_SECTIONS)
        p = extract_passage(art, "Lewis", "1979", suffix="a", n_candidates=2)
        assert p and "asymmetry" in p["passage"]
        pb = extract_passage(art, "Lewis", "1979", suffix="b", n_candidates=2)
        assert pb and "de se" in pb["passage"]

    def test_bare_year_with_multiple_candidates_not_attributable(self):
        art = _article([], sections=LEWIS_SECTIONS)
        assert extract_passage(art, "Lewis", "1979", suffix="", n_candidates=2) is None

    def test_two_mentions_first_in_document_order(self):
        sections = {"1": {"id": "1", "title": "A", "content": "Kuhn (1962) argues first-thing."},
                    "5": {"id": "5", "title": "B", "content": "Kuhn (1962) also argues later-thing."}}
        art = _article([], sections=sections)
        p = extract_passage(art, "Kuhn", "1962", suffix="", n_candidates=1)
        assert "first-thing" in p["passage"]


class TestContextFieldWrite:
    def test_format_context_value_strips_braces(self):
        v = format_context_value("freewill", 'He {argues}  that "X".')
        assert v == 'Cited in \'freewill\' entry: "He argues that "X"."'

    def test_strip_context_fields_removes_fabricated(self):
        entry = ('@book{k,\n  author = {A},\n'
                 '  sep_context = {FORGED CLAIM},\n'
                 '  iep_context = {ALSO FORGED},\n  year = {1962}\n}')
        out = strip_context_fields(entry)
        assert "FORGED" not in out and "sep_context" not in out
        assert "author = {A}" in out

    def test_strip_context_fields_removes_quoted_form(self):
        entry = ('@book{k,\n  author = {A},\n'
                 '  sep_context = "QUOTED FORGERY",\n  year = {1962}\n}')
        out = strip_context_fields(entry)
        assert "QUOTED FORGERY" not in out and "sep_context" not in out


class TestAcquireContext:
    def test_matched_entry_gets_sep_context(self):
        art = _article(
            ["Kuhn, T., 1962, The Structure of Scientific Revolutions, Chicago."],
            sections=KUHN_SECTIONS)
        articles = {"sep:test-entry": art}
        entries = {"kuhn1962structure": {
            "entry_type": "book",
            "fields": {"author": "Kuhn, Thomas S.", "year": "1962",
                       "title": "The Structure of Scientific Revolutions"}}}
        res = acquire_context(entries, articles)
        r = res["kuhn1962structure"]
        assert r["outcome"] == "matched"
        assert r["field"] == "sep_context"
        assert "normal science" in r["value"]

    def test_unmatched_entry(self):
        articles = {"sep:test-entry": _article(["Someone else, 2001, Other."])}
        entries = {"ghost1999": {"entry_type": "book",
                   "fields": {"author": "Ghost, G.", "year": "1999", "title": "Nothing"}}}
        assert acquire_context(entries, articles)["ghost1999"]["outcome"] == "unmatched"

    LEWIS_ENTRY = {"lewis1979counterfactual": {
        "entry_type": "article",
        "fields": {"author": "Lewis, David", "year": "1979",
                   "title": "Counterfactual Dependence and Time's Arrow"}}}
    # both lines contain all of the bib title's tokens -> ambiguous sentinel
    AMBIG_LINES = [
        "Lewis, D., 1979a, Counterfactual Dependence and Time's Arrow, reprint.",
        "Lewis, D., 1979b, More on Counterfactual Dependence and Time's Arrow.",
    ]

    def test_only_article_ambiguous_yields_ambiguous_skipped(self):
        articles = {"sep:test-entry": _article(self.AMBIG_LINES)}
        res = acquire_context(dict(self.LEWIS_ENTRY), articles)
        assert res["lewis1979counterfactual"] == {"outcome": "ambiguous-skipped"}

    def test_ambiguous_article_does_not_block_later_clean_match(self):
        # "iep:..." sorts before "sep:...", so the ambiguous article is tried
        # first; the later clean article must still win with a matched outcome
        ambiguous_art = _article(self.AMBIG_LINES)
        clean_art = _article(
            ["Lewis, D., 1979a, Counterfactual Dependence and Time's Arrow."],
            sections=LEWIS_SECTIONS)
        articles = {"iep:lewis-ambig": ambiguous_art,
                    "sep:counterfactuals": clean_art}
        res = acquire_context(dict(self.LEWIS_ENTRY), articles)
        r = res["lewis1979counterfactual"]
        assert r["outcome"] == "matched"
        assert r["slug"] == "counterfactuals"
        assert r["field"] == "sep_context"
        assert "asymmetry" in r["value"]


class TestFetchOnce:
    def test_each_slug_fetched_exactly_once(self, monkeypatch):
        # union across domains is a set; the same slug in three domain files
        # triggers one fetch (spec: fetch once, match many)
        import fetch_sep  # importable via resolve_context's sys.path insert
        calls = []
        # real signature: fetch_sep_article(entry_name, limiter, backoff, debug=False)
        monkeypatch.setattr(fetch_sep, "fetch_sep_article",
                            lambda slug, *a, **k: calls.append(slug) or _article([]))
        from resolve_context import fetch_articles
        articles, failed = fetch_articles({"sep": {"freewill"}, "iep": set()})
        assert calls == ["freewill"]
        assert "sep:freewill" in articles and failed == []

    def test_fetch_failure_recorded_not_raised(self, monkeypatch):
        import fetch_sep

        def boom(slug, *a, **k):
            raise LookupError("404")

        monkeypatch.setattr(fetch_sep, "fetch_sep_article", boom)
        from resolve_context import fetch_articles
        articles, failed = fetch_articles({"sep": {"gone"}, "iep": set()})
        assert failed == ["sep:gone"] and articles == {}
