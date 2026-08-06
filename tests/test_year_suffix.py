"""Item 3 F: Chicago a/b letter assignment over work identity."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import year_suffix as ys


def e(eid, author, year, title, doi="", editor=""):
    return {"id": eid, "author": author, "editor": editor, "year": year,
            "title": title, "doi": doi}


class TestAuthorSignature:
    def test_surname_and_initial(self):
        assert ys.author_signature("Menary, Richard") == (("menary", "r"),)

    def test_initial_only_form_matches_full_first_name(self):
        assert ys.author_signature("Menary, R.") == ys.author_signature("Menary, Richard")

    def test_two_authors_are_two_slots(self):
        sig = ys.author_signature("Menary, Richard and Wu, Jing")
        assert sig == (("menary", "r"), ("wu", "j"))

    def test_different_people_same_surname_differ(self):
        # The two Johnsons: item 3 E's case, which F must NOT letter.
        assert ys.author_signature("Johnson, Gabbrielle") != \
            ys.author_signature("Johnson, Rebecca")

    def test_diacritics_folded(self):
        assert ys.author_signature("Milliere, Raphael") == \
            ys.author_signature("Millière, Raphaël")

    def test_editor_used_when_no_author(self):
        assert ys.author_signature("", editor="Menary, Richard") == (("menary", "r"),)

    def test_empty_is_empty(self):
        assert ys.author_signature("") == ()


class TestAssignSuffixes:
    def test_two_works_same_author_year_get_letters(self):
        res = ys.assign_suffixes([
            e("k1", "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/a"),
            e("k2", "Menary, Richard", "2010", "The Extended Mind", doi="10.1/b"),
        ])
        # Ordered alphabetically by title (Chicago 15.18), so "Cognitive" is 'a'.
        assert res["suffixes"] == {"k1": "a", "k2": "b"}

    def test_single_work_gets_no_letter(self):
        res = ys.assign_suffixes([e("k1", "Menary, Richard", "2010", "Only One")])
        assert res["suffixes"] == {}

    def test_same_work_in_two_domains_gets_one_letter(self):
        # The defect this design exists to prevent: identical DOI, different
        # citation keys in different domain bibs.
        res = ys.assign_suffixes([
            e(("d1", "menary2010a"), "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/a"),
            e(("d3", "menaryCog"), "Menary, Richard", "2010", "Cognitive integration", doi="10.1/a"),
            e(("d1", "menary2010b"), "Menary, Richard", "2010", "The Extended Mind", doi="10.1/b"),
        ])
        assert res["suffixes"][("d1", "menary2010a")] == "a"
        assert res["suffixes"][("d3", "menaryCog")] == "a"      # same work, same letter
        assert res["suffixes"][("d1", "menary2010b")] == "b"

    def test_title_identity_collapses_when_doi_absent(self):
        res = ys.assign_suffixes([
            e("k1", "Menary, Richard", "2010", "Cognitive Integration"),
            e("k2", "Menary, Richard", "2010", "Cognitive integration!"),
            e("k3", "Menary, Richard", "2010", "The Extended Mind"),
        ])
        assert res["suffixes"]["k1"] == res["suffixes"]["k2"] == "a"
        assert res["suffixes"]["k3"] == "b"

    def test_different_people_same_surname_not_lettered(self):
        res = ys.assign_suffixes([
            e("k1", "Johnson, Gabbrielle", "2024", "Are Algorithms Value-Free"),
            e("k2", "Johnson, Rebecca", "2024", "Automating Judgement"),
        ])
        assert res["suffixes"] == {}

    def test_different_years_not_lettered(self):
        res = ys.assign_suffixes([
            e("k1", "Menary, Richard", "2010", "A"),
            e("k2", "Menary, Richard", "2013", "B"),
        ])
        assert res["suffixes"] == {}

    def test_different_coauthor_lists_not_lettered(self):
        # "Muldoon and Wu 2023" vs "Muldoon et al. 2023" is item 3 E's case:
        # the citation form already disambiguates, so no letters.
        res = ys.assign_suffixes([
            e("k1", "Muldoon, Ryan and Wu, Jing", "2023", "A"),
            e("k2", "Muldoon, Ryan and Qi, Li and Ng, Ann", "2023", "B"),
        ])
        assert res["suffixes"] == {}

    def test_assignment_is_deterministic_under_input_order(self):
        args = [e("k2", "Menary, Richard", "2010", "The Extended Mind", doi="10.1/b"),
                e("k1", "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/a")]
        assert ys.assign_suffixes(args)["suffixes"] == \
            ys.assign_suffixes(list(reversed(args)))["suffixes"]

    def test_ties_on_title_break_on_id(self):
        res = ys.assign_suffixes([
            e("kb", "Menary, Richard", "2010", "Same Title", doi="10.1/b"),
            e("ka", "Menary, Richard", "2010", "Same Title", doi="10.1/a"),
        ])
        assert res["suffixes"] == {"ka": "a", "kb": "b"}

    def test_missing_year_or_author_is_skipped(self):
        res = ys.assign_suffixes([
            e("k1", "", "2010", "A"), e("k2", "", "2010", "B"),
            e("k3", "Menary, Richard", "", "C"), e("k4", "Menary, Richard", "", "D"),
            e("k5", "Menary, Richard", "n.d.", "E"), e("k6", "Menary, Richard", "n.d.", "F"),
        ])
        assert res["suffixes"] == {}

    def test_more_than_26_works_letters_NOBODY_and_is_reported(self):
        # Never partially letter a group: a mix of lettered and unlettered
        # members lets a suffixed citation select one and drop the rest.
        entries = [e(f"k{i}", "Prolific, Pat", "2020", f"Title {i:02d}", doi=f"10.1/{i}")
                   for i in range(30)]
        res = ys.assign_suffixes(entries)
        assert res["suffixes"] == {}
        assert res["overflow"] == [{"authors": "Prolific, Pat", "year": "2020", "works": 30}]
        assert res["groups"] == []

    def test_exactly_26_works_are_all_lettered(self):
        entries = [e(f"k{i}", "Prolific, Pat", "2020", f"Title {i:02d}", doi=f"10.1/{i}")
                   for i in range(26)]
        res = ys.assign_suffixes(entries)
        assert set(res["suffixes"].values()) == set(ys.LETTERS)
        assert res["overflow"] == []

    def test_conflicting_dois_are_not_merged(self):
        # dedupe refuses to merge two groups whose non-empty DOI sets differ;
        # if this pass merged them, both copies would take one letter and the
        # References would show two entries labelled 2010a.
        res = ys.assign_suffixes([
            e("k1", "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/one"),
            e("k2", "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/two"),
        ])
        assert sorted(res["suffixes"].values()) == ["a", "b"]

    def test_one_missing_doi_still_collapses_on_the_title_axis(self):
        res = ys.assign_suffixes([
            e("k1", "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/one"),
            e("k2", "Menary, Richard", "2010", "Cognitive Integration"),
            e("k3", "Menary, Richard", "2010", "The Extended Mind", doi="10.1/three"),
        ])
        assert res["suffixes"]["k1"] == res["suffixes"]["k2"]
        assert res["suffixes"]["k3"] != res["suffixes"]["k1"]

    def test_copies_disagreeing_on_author_get_no_letter_and_are_reported(self):
        res = ys.assign_suffixes([
            e("k1", "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/a"),
            e("k2", "Menary, Richard and Smith, Jane", "2010", "Cognitive Integration",
              doi="10.1/a"),
            e("k3", "Menary, Richard", "2010", "The Extended Mind", doi="10.1/b"),
        ])
        assert res["suffixes"] == {}      # the surviving work is now alone
        assert len(res["conflicts"]) == 1

    def test_telemetry_counts_works_and_entries_separately(self):
        res = ys.assign_suffixes([
            e(("d1", "a"), "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/a"),
            e(("d2", "a"), "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/a"),
            e(("d3", "a"), "Menary, Richard", "2010", "Cognitive Integration", doi="10.1/a"),
            e(("d1", "b"), "Menary, Richard", "2010", "The Extended Mind", doi="10.1/b"),
        ])
        assert res["assigned_entries"] == 4
        assert res["assigned_works"] == 2

    def test_group_summary_reported(self):
        res = ys.assign_suffixes([
            e("k1", "Menary, Richard", "2010", "A", doi="10.1/a"),
            e("k2", "Menary, Richard", "2010", "B", doi="10.1/b"),
        ])
        assert res["groups"] == [{"authors": "Menary, Richard", "year": "2010", "works": 2}]
