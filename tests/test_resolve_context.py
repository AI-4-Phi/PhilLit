"""Tests for resolve_context.py -- SEP/IEP matching and passage extraction."""
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from resolve_context import (
    load_slug_files, first_author_surname, title_score, match_entry_to_article,
    extract_passage, format_context_value, strip_context_fields, acquire_context,
    _title_texts,
)


def _article_from_entries(entries):
    """Like _article() below, but the caller supplies raw+parsed+confidence
    directly instead of forcing parsed=None -- needed to test parsed-title
    scoring."""
    return {
        "entry_name": "test-entry",
        "title": "Test Entry",
        "preamble": "",
        "sections": {},
        "bibliography": entries,
    }


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


class TestParsedTitleMaxScoring:
    """match_entry_to_article scores each candidate as the max of its parsed
    title and its raw line, never one at the other's expense. Both SEP's
    parser and the old regex truncate a title at its first comma, so a
    correct comma-bearing bib title can score zero on the parsed title
    alone; the raw line still carries every token."""

    def test_ayer_regression_comma_truncated_parsed_title_still_matches(self):
        # SEP's parser truncates "Language, Truth and Logic" to a parsed
        # title of "Language" -- overlap 1 < TITLE_MIN_OVERLAP, score 0.0 on
        # parsed alone. Under the old parsed-preferred scoring this candidate
        # never passes; the raw line has all three title tokens.
        art = _article_from_entries([{
            "raw": "Ayer, A.J., 1936, Language, Truth and Logic, London: Gollancz.",
            "parsed": {"authors": ["Ayer, A.J."], "year": "1936",
                       "title": "Language", "publisher": "Truth and Logic, London: Gollancz"},
            "confidence": "high",
        }])
        fields = {"author": "Ayer, A.J.", "year": "1936",
                  "title": "Language, Truth and Logic"}
        m = match_entry_to_article(fields, art)
        assert m is not None and not m.get("ambiguous")

    def test_ambiguity_still_fires_with_parsed_titles(self):
        # Both lines' parsed titles fully overlap the bib title; the
        # ambiguity rule must still fire exactly as it does on raw-only
        # scoring.
        art = _article_from_entries([
            {"raw": "Lewis, D., 1979a, Counterfactual Dependence and Time's Arrow, reprint.",
             "parsed": {"title": "Counterfactual Dependence and Time's Arrow"},
             "confidence": "high"},
            {"raw": "Lewis, D., 1979b, More on Counterfactual Dependence and Time's Arrow.",
             "parsed": {"title": "More on Counterfactual Dependence and Time's Arrow"},
             "confidence": "high"},
        ])
        fields = {"author": "Lewis, David", "year": "1979",
                  "title": "Counterfactual Dependence and Time's Arrow"}
        m = match_entry_to_article(fields, art)
        assert m is not None and m.get("ambiguous") is True

    def test_parsed_none_items_unchanged_raw_fallback(self):
        # parsed: None (IEP's shape, and low-confidence SEP partials) must
        # still score on raw alone, exactly as before the fix.
        art = _article_from_entries([{
            "raw": "Kuhn, T., 1962, The Structure of Scientific Revolutions, Chicago.",
            "parsed": None, "confidence": "low",
        }])
        fields = {"author": "Kuhn, Thomas S.", "year": "1962",
                  "title": "The Structure of Scientific Revolutions"}
        m = match_entry_to_article(fields, art)
        assert m is not None and not m.get("ambiguous")

    def test_junk_line_rejected_when_both_texts_score_low(self):
        art = _article_from_entries([{
            "raw": "Kuhn, T., 1962, Totally Unrelated Topic, Publisher.",
            "parsed": {"title": "Totally Unrelated Topic"}, "confidence": "high",
        }])
        fields = {"author": "Kuhn, Thomas S.", "year": "1962",
                  "title": "The Structure of Scientific Revolutions"}
        assert match_entry_to_article(fields, art) is None

    def test_max_semantics_low_parsed_score_high_raw_score_still_matches(self):
        # parsed title overlaps 2 of 5 bib tokens (0.4, below threshold on
        # its own); the raw line contains all 5 (1.0). A narrower fix (e.g.
        # "prefer parsed, else raw" without ever combining) would lose this
        # case -- pin the max explicitly.
        art = _article_from_entries([{
            "raw": "Zeta, Z., 1999, Alpha Beta Gamma Delta Epsilon, Publisher.",
            "parsed": {"title": "Alpha Beta"}, "confidence": "high",
        }])
        fields = {"author": "Zeta, Z.", "year": "1999",
                  "title": "Alpha Beta Gamma Delta Epsilon"}
        m = match_entry_to_article(fields, art)
        assert m is not None and not m.get("ambiguous")
        assert m["score"] == 1.0

    def test_sibling_residual_accepted_when_own_work_absent(self):
        # ACCEPTED RESIDUAL (measured 2026-08-29, docs/known-issues/
        # parsed-title-measurement-2026-08-29/): a same-author-same-year
        # SIBLING title, comma-truncated by the parser exactly like the Ayer
        # case, can raw-overlap the bib title at >= threshold (0.75 here)
        # when the entry's own work is absent from the article's
        # bibliography. Pinned deliberately -- a future change to this
        # behavior, in EITHER direction, must break this test rather than
        # slip by silently.
        art = _article_from_entries([{
            "raw": "Piccinini, G., 2004, Computation, Explanation, and Mental Contents, Publisher.",
            "parsed": {"title": "Computation"}, "confidence": "high",
        }])
        fields = {"author": "Piccinini, Gualtiero", "year": "2004",
                  "title": "Computation, Explanation, and Mental States"}
        m = match_entry_to_article(fields, art)
        assert m is not None and not m.get("ambiguous")

    def test_both_siblings_present_backstop_is_ambiguous(self):
        # Now load-bearing: when both the entry's own work and its sibling
        # are present, it is the ambiguity rule -- not raw-overlap avoidance
        # -- that bounds the sibling-residual class pinned above.
        art = _article_from_entries([
            {"raw": "Piccinini, G., 2004, Computation, Explanation, and Mental States, Publisher.",
             "parsed": {"title": "Computation"}, "confidence": "high"},
            {"raw": "Piccinini, G., 2004, Computation, Explanation, and Mental Contents, Publisher.",
             "parsed": {"title": "Computation"}, "confidence": "high"},
        ])
        fields = {"author": "Piccinini, Gualtiero", "year": "2004",
                  "title": "Computation, Explanation, and Mental States"}
        m = match_entry_to_article(fields, art)
        assert m is not None and m.get("ambiguous") is True

    def test_loss_to_ambiguous_is_the_accepted_conservative_direction(self):
        # Under the old parsed-only scoring, line B's parsed title
        # ("Something Else Entirely") scores 0 and only line A passes: a
        # single (baseline) match. Under max(), line B's RAW line also
        # scores >= threshold (2 of 4 bib tokens), so both lines pass and
        # the matcher must retreat to AMBIGUOUS rather than guess -- a lost
        # match costs one tier; a wrong one manufactures a sanctioned
        # mischaracterization.
        art = _article_from_entries([
            {"raw": "Wright, C., 2000, Alpha Beta Gamma Delta, Publisher A.",
             "parsed": {"title": "Alpha Beta Gamma Delta"}, "confidence": "high"},
            {"raw": "Wright, C., 2000b, Alpha Beta Unrelated Extra, Publisher B.",
             "parsed": {"title": "Something Else Entirely"}, "confidence": "high"},
        ])
        fields = {"author": "Wright, Crispin", "year": "2000",
                  "title": "Alpha Beta Gamma Delta"}
        m = match_entry_to_article(fields, art)
        assert m is not None and m.get("ambiguous") is True

    def test_title_texts_scores_parsed_when_raw_missing(self):
        # Plumbing symmetry: an item with a parsed title but no raw key must
        # not crash, and the parsed title must still be scored.
        item = {"parsed": {"title": "Data-Centric Biology"}}
        texts = _title_texts(item)
        assert texts == ["Data-Centric Biology"]
        assert title_score("Data-Centric Biology", texts[0]) == 1.0
        # And a fully malformed item still yields a scoreable (zero) text.
        assert _title_texts({"raw": None}) == [""]


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


    def test_strip_context_fields_reaches_nested_bare_and_compact_forms(self):
        """The regex this replaced matched one nesting level, braced or
        quoted, and only a field opening its line; the three shapes below
        each survived it. Located structurally now (bib_fields), so a forged
        context field cannot hide in any delimiter or position."""
        entry = ('@book{k, sep_context = {FORGED {nested {deep}} CLAIM},\n'
                 '  author = {A}, iep_context = bare_macro,\n'
                 '  year = {1962}\n}')
        out = strip_context_fields(entry)
        assert "sep_context" not in out and "iep_context" not in out
        assert "FORGED" not in out and "bare_macro" not in out
        assert "author = {A}" in out and "year = {1962}" in out
        from pybtex.database import parse_string
        parse_string(out, "bibtex")


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
        # triggers one fetch (fetch once, match many)
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

    def test_a_partial_failure_partitions_the_requested_slugs(self, monkeypatch):
        """Every requested slug lands in exactly one of articles/failed.

        No deadline involvement: this is the fetch-error path. A count-only
        assertion would not establish the partition (one id in both lists plus
        one id in neither preserves the total), so assert the sets.
        """
        import fetch_sep
        import resolve_context

        seen = []

        def first_ok_then_boom(slug, limiter, backoff, debug=False):
            seen.append(slug)
            if len(seen) > 1:
                raise RuntimeError("boom")
            return {"entry_name": slug, "bibliography": []}

        monkeypatch.setattr(fetch_sep, "fetch_sep_article", first_ok_then_boom)
        requested = ["aaa", "bbb", "ccc"]
        articles, failed = resolve_context.fetch_articles({"sep": requested})
        expected = {f"sep:{slug}" for slug in requested}
        assert set(articles) | set(failed) == expected
        assert set(articles).isdisjoint(failed)
        assert len(failed) == len(set(failed))


class TestFetchPassDeadline:
    """The acquisition pass admits work against a budget.

    What is pinned here is exactly the guarantee the code gives: once a fetch
    RETURNS, no further fetch is started past the budget. It is not a
    wall-clock bound on the pass and not a watchdog -- a single call that never
    returns is never interrupted, which is why
    test_a_single_fetch_may_overrun_the_budget_entirely is here to record the
    limitation rather than a bound that does not exist.

    Context: a live review's barrier sat at 100% CPU for 72 minutes inside one
    SEP article and nothing here could notice (2026-08-06). This budget would
    NOT
    have stopped that; making the parser linear did. What it does stop is the
    slow-but-progressing pass.
    """

    @staticmethod
    def _fake_clock(monkeypatch, start=0.0):
        """A monotonic() the test drives by hand. fetch_articles does its
        `import time` at call time, so this patches the same module object it
        will look up."""
        import time
        now = [start]
        monkeypatch.setattr(time, "monotonic", lambda: now[0])
        return now

    def test_slugs_past_the_deadline_are_reported_failed_not_dropped(self, monkeypatch):
        import resolve_context

        calls = []

        def slow_fetch(slug, limiter, backoff, debug=False):
            calls.append(slug)
            return {"entry_name": slug, "bibliography": []}

        import fetch_sep
        monkeypatch.setattr(fetch_sep, "fetch_sep_article", slow_fetch)
        # A deadline already in the past: nothing should be fetched, and every
        # slug must surface as failed rather than vanishing from both lists.
        articles, failed = resolve_context.fetch_articles(
            {"sep": ["aaa", "bbb", "ccc"]}, deadline_seconds=-1.0)
        assert calls == [], "no fetch should start past the deadline"
        assert articles == {}
        assert sorted(failed) == ["sep:aaa", "sep:bbb", "sep:ccc"]

    def test_a_generous_deadline_fetches_everything(self, monkeypatch):
        import resolve_context

        import fetch_sep
        monkeypatch.setattr(
            fetch_sep, "fetch_sep_article",
            lambda slug, limiter, backoff, debug=False: {
                "entry_name": slug, "bibliography": []})
        articles, failed = resolve_context.fetch_articles(
            {"sep": ["aaa", "bbb"]}, deadline_seconds=600.0)
        assert sorted(articles) == ["sep:aaa", "sep:bbb"]
        assert failed == []

    def test_a_budget_that_expires_mid_pass_skips_only_the_remainder(
            self, monkeypatch, capsys):
        """The case the already-expired test cannot reach.

        One fetch runs, returns, and has consumed the whole budget. Every
        later slug -- including every iep slug, since sep is always attempted
        first -- must be skipped and reported, not silently dropped.
        """
        import fetch_iep
        import fetch_sep
        import resolve_context

        now = self._fake_clock(monkeypatch)
        attempted = []

        def slow_but_returning(slug, limiter, backoff, debug=False):
            attempted.append(slug)
            now[0] += 150.0  # this one fetch outlasts the whole budget
            return {"entry_name": slug, "bibliography": []}

        monkeypatch.setattr(fetch_sep, "fetch_sep_article", slow_but_returning)
        monkeypatch.setattr(fetch_iep, "fetch_iep_article", slow_but_returning)
        articles, failed = resolve_context.fetch_articles(
            {"sep": ["aaa", "bbb", "ccc"], "iep": ["zzz"]}, deadline_seconds=100.0)

        assert attempted == ["aaa"], "only the pre-budget fetch may start"
        assert sorted(articles) == ["sep:aaa"]
        assert sorted(failed) == ["iep:zzz", "sep:bbb", "sep:ccc"]
        assert "3 slug(s) never attempted" in capsys.readouterr().err

    def test_a_single_fetch_may_overrun_the_budget_entirely(self, monkeypatch):
        """RECORDED LIMITATION, not a bug to be read as one.

        The budget is checked between fetches, so one call that takes ten
        times the budget runs to completion and its result is kept. A call
        that never returns is therefore never interrupted at all -- the pass
        is not bounded in wall-clock time. Any future claim that it is should
        break this test first.
        """
        import fetch_sep
        import resolve_context

        now = self._fake_clock(monkeypatch)

        def very_slow(slug, limiter, backoff, debug=False):
            now[0] += 1000.0
            return {"entry_name": slug, "bibliography": []}

        monkeypatch.setattr(fetch_sep, "fetch_sep_article", very_slow)
        articles, failed = resolve_context.fetch_articles(
            {"sep": ["aaa"]}, deadline_seconds=100.0)
        assert sorted(articles) == ["sep:aaa"], (
            "an overrunning fetch is neither interrupted nor discarded")
        assert failed == []
        assert now[0] == 1000.0  # ten times the budget, uninterrupted

    def test_no_message_when_the_budget_is_never_hit(self, monkeypatch, capsys):
        import fetch_sep
        import resolve_context

        monkeypatch.setattr(
            fetch_sep, "fetch_sep_article",
            lambda slug, limiter, backoff, debug=False: {
                "entry_name": slug, "bibliography": []})
        resolve_context.fetch_articles({"sep": ["aaa"]}, deadline_seconds=600.0)
        assert capsys.readouterr().err == ""


def test_first_author_surname_is_brace_aware_and_keeps_comma_less_names_whole():
    # A braced return never matches prose; parity with the pre-change rule,
    # census 0 of 9,157 such fields -- accepted residual.
    assert first_author_surname("{Smith and Jones Institute} and Doe, Jane") == "{Smith and Jones Institute}"
    assert first_author_surname("Doe, Jane and Smith, John") == "Doe"
    # Parity with the pre-change rule: no comma -> the whole first name.
    assert first_author_surname("Willem van der Deijl and Doe, Jane") == "Willem van der Deijl"
