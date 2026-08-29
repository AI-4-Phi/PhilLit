"""Conference papers keep their venue, pages and entry type.

A bibliography names a conference in its expanded citation form ("Proceedings
of the 34th International Conference on Machine Learning (ICML 2017)") while the
APIs report the canonical series name ("International Conference on Machine
Learning"). Comparing those with `normalize_journal` alone reported a mismatch,
so the cleaner deleted `booktitle` — the required field for @inproceedings — and
demoted the entry to @misc, losing the venue from the reference.

Measured over the 46 delivered corpora before the fix: 43 entries were demoted,
30 of them @inproceedings, and `booktitle` was the single most-removed field.

The other half is provenance: OpenAlex results carried no volume/issue/pages at
all, so a correct page range had to be confirmed by some other source or be
deleted.
"""

import json
import sys
from pathlib import Path

import pytest
from pybtex.database import parse_string

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
SCRIPTS_DIR = (Path(__file__).parent.parent / "skills" / "philosophy-research"
               / "scripts")
sys.path.insert(0, str(SCRIPTS_DIR))

from bib_identity import venue_key, normalize_journal  # noqa: E402
from metadata_cleaner import (  # noqa: E402
    build_metadata_index,
    clean_bibtex,
    is_field_verifiable,
    parse_openalex_result,
    _field_matches_api,
)


# =============================================================================
# venue_key: the folds it must make
# =============================================================================

class TestVenueKeyFolds:
    """Citation forms of the SAME venue must produce one key."""

    @pytest.mark.parametrize("bib_form,api_form", [
        # The six forms reconstructable from the delivered corpus.
        ("Proceedings of the 34th International Conference on Machine Learning"
         " (ICML 2017)", "International Conference on Machine Learning"),
        ("Advances in Neural Information Processing Systems 30 (NeurIPS 2017)",
         "Neural Information Processing Systems"),
        ("Advances in Neural Information Processing Systems 32 (NeurIPS 2019)",
         "Neural Information Processing Systems"),
        ("Advances in Neural Information Processing Systems 34 (NeurIPS 2021)",
         "Neural Information Processing Systems"),
        ("Proceedings of the Twenty-Ninth AAAI Conference on Artificial"
         " Intelligence (AAAI 2015)", "AAAI Conference on Artificial Intelligence"),
        # Other forms observed across the corpus.
        ("Proceedings of the 2025 ACM Conference on Fairness, Accountability,"
         " and Transparency",
         "2022 ACM Conference on Fairness, Accountability, and Transparency"),
        ("2023 IEEE Intelligent Vehicles Symposium (IV)",
         "IEEE Intelligent Vehicles Symposium"),
        # Disambiguating parentheticals on plain journals.
        ("ACM Computing Surveys (CSUR)", "ACM Computing Surveys"),
        ("Criminology (Beverly Hills)", "Criminology"),
        ("arXiv (Cornell University)", "arXiv"),
    ])
    def test_same_venue_folds_to_one_key(self, bib_form, api_form):
        assert venue_key(bib_form) == venue_key(api_form) != ""

    def test_fold_is_strictly_looser_than_normalize_journal(self):
        """The point of the key: these differ under the identity normalizer."""
        bib = "Proceedings of the 34th International Conference on Machine Learning"
        api = "International Conference on Machine Learning"
        assert normalize_journal(bib) != normalize_journal(api)
        assert venue_key(bib) == venue_key(api)


class TestVenueKeyBounds:
    """Distinct venues must NOT fold together. Each case was observed while
    measuring the corpus; each previously merged under a rejected design."""

    @pytest.mark.parametrize("left,right", [
        # Two different Elsevier journals. Ungating the "Advances in" strip
        # merged them.
        ("Advances in Applied Energy", "Applied Energy"),
        # Different books in one series. A blanket trailing-number strip
        # merged them.
        ("Oxford Studies in Political Philosophy Volume 5",
         "Oxford Studies in Political Philosophy Volume 8"),
        ("Oxford Studies in Agency and Responsibility Volume 5",
         "Oxford Studies in Agency and Responsibility Volume 7"),
        # An ordinal that is part of the name, not decoration. Stripping it
        # hyphen-joined produced the nonsense key "-century life".
        ("Eighteenth-Century Life", "Nineteenth-Century Life"),
        # Plain distinct journals must never touch.
        ("Australasian Journal of Philosophy", "Journal of Philosophy"),
        ("Ethics", "Environmental Ethics"),
    ])
    def test_distinct_venues_stay_distinct(self, left, right):
        assert venue_key(left) != venue_key(right)

    def test_ordinal_in_name_survives_intact(self):
        """Regression: the key must not begin with the hyphen left behind."""
        key = venue_key("Eighteenth-Century Life")
        assert key == "eighteenth-century life"

    def test_volume_number_survives(self):
        assert venue_key("Oxford Studies in Political Philosophy Volume 5") == \
            "oxford studies in political philosophy volume 5"

    def test_volume_number_survives_inside_a_proceedings_name(self):
        """Different volumes of one proceedings series stay different keys."""
        five = venue_key("Proceedings of the Aristotelian Society Volume 5")
        eight = venue_key("Proceedings of the Aristotelian Society Volume 8")
        assert five != eight
        # "Proceedings of the" is this venue's actual name, not decoration:
        # nothing after it names a series, so the prefix is kept.
        assert five == "proceedings of the aristotelian society volume 5"

    def test_volume_numbered_book_series_never_opens_the_strips(self):
        """A volume number must not be mistaken for a conference series number.

        "Advances in Experimental Social Psychology Volume 45" is a book series.
        If its trailing number counted as proceedings evidence, the gate would
        open and "Advances in" would be stripped, folding the series onto a bare
        "Experimental Social Psychology" — the same false merge that "Advances in
        Applied Energy" produces.
        """
        assert venue_key("Advances in Experimental Social Psychology Volume 45") \
            == "advances in experimental social psychology volume 45"
        assert venue_key("Advances in Experimental Social Psychology Volume 45") \
            != venue_key("Experimental Social Psychology Volume 45")

    def test_hyphen_joined_ordinal_survives_inside_a_conference_name(self):
        """The whole-token ordinal rule, not the proceedings gate, does this one.

        "Conference" opens the aggressive strips, so only the requirement that an
        ordinal be a whole token keeps "Eighteenth-Century" intact.
        """
        assert venue_key("Eighteenth-Century Studies Conference") == \
            "eighteenth-century studies conference"
        # ...while a genuinely detached ordinal is still decoration.
        assert venue_key("Twenty-Ninth AAAI Conference on Artificial Intelligence") == \
            "aaai conference on artificial intelligence"

    def test_empty_and_none_are_empty(self):
        assert venue_key("") == ""
        assert venue_key(None) == ""


class TestNoTokenIsItsOwnLicence:
    """The first draft had three false-merge classes, all with one cause: a
    token was allowed to license its own removal. Each case below fails against that first draft."""

    @pytest.mark.parametrize("left,right", [
        # A bare trailing number opened the strips, which then deleted it --
        # so a journal name with a volume glued on folded onto the bare name of
        # a DIFFERENT journal.
        ("Advances in Applied Energy 12", "Applied Energy 34"),
        ("Advances in Applied Energy 12", "Applied Energy"),
        ("Advances in Experimental Social Psychology 45",
         "Experimental Social Psychology"),
        # "congress" occurs inside an institution name, so a conference word
        # anywhere was enough to strip a real volume number.
        ("Library of Congress Quarterly 7", "Library of Congress Quarterly"),
        # A fabricated "Proceedings of the ..." wrapper around a real journal
        # verified against that journal. This is a plausible invention shape:
        # the model knows the work is proceedings-like and wraps a journal it
        # has seen.
        ("Proceedings of the Journal of Philosophy", "Journal of Philosophy"),
        ("Proceedings of the Mind", "Mind"),
        ("Proceedings of the Ethics", "Ethics"),
    ])
    def test_distinct_venues_stay_distinct(self, left, right):
        assert venue_key(left) != venue_key(right)

    def test_real_proceedings_named_venue_keeps_its_prefix(self):
        """The flip side: when nothing after "Proceedings of" names a series,
        the phrase is the venue's own name and must survive."""
        assert venue_key("Proceedings of the Aristotelian Society") == \
            "proceedings of the aristotelian society"

    def test_prefix_still_folds_when_a_series_follows_it(self):
        """...but it IS decoration when what follows is itself named a series."""
        assert venue_key("Proceedings of the International Joint Conference on"
                         " Artificial Intelligence") == \
            venue_key("International Joint Conference on Artificial Intelligence")

    def test_known_series_without_a_conference_word_still_folds(self):
        """NeurIPS carries no conference word, so only the known-series list
        distinguishes it from "Advances in <journal> <volume>"."""
        assert venue_key("Advances in Neural Information Processing Systems 30") \
            == venue_key("Neural Information Processing Systems")
        # ...and the lookalike shape must NOT fold.
        assert venue_key("Advances in Applied Energy 30") != venue_key("Applied Energy")


# =============================================================================
# The cleaner honours the fold
# =============================================================================

def _s2_conference_json(title, venue, pages, doi=None):
    return {
        "status": "ok", "source": "semantic_scholar", "query": "q", "count": 1,
        "results": [{
            "paperId": "p1", "title": title, "year": 2017,
            "venue": venue, "journal": {"pages": pages} if pages else None,
            "doi": doi, "authors": [{"name": "A. Author"}],
        }],
    }


class TestCleanerAcceptsExpandedVenue:

    def test_index_verifies_expanded_conference_name(self, tmp_path):
        jd = tmp_path / "json"
        jd.mkdir()
        (jd / "s2_guo.json").write_text(json.dumps(_s2_conference_json(
            "On Calibration of Modern Neural Networks",
            "International Conference on Machine Learning", "1321-1330")),
            encoding="utf-8")
        index = build_metadata_index(jd)

        assert is_field_verifiable(
            'booktitle',
            "Proceedings of the 34th International Conference on Machine"
            " Learning (ICML 2017)", index) is True
        # An unrelated venue is still refused.
        assert is_field_verifiable(
            'booktitle', "Proceedings of the Aristotelian Society", index) is False

    def test_own_record_match_accepts_expanded_form(self):
        api_entry = {"container_title": "Neural Information Processing Systems"}
        assert _field_matches_api(
            'booktitle',
            "Advances in Neural Information Processing Systems 30 (NeurIPS 2017)",
            api_entry) is True
        assert _field_matches_api(
            'booktitle', "Advances in Applied Energy",
            {"container_title": "Applied Energy"}) is False

    def test_inproceedings_keeps_booktitle_and_type(self, tmp_path):
        """End to end: the entry that used to arrive as a bare @misc."""
        jd = tmp_path / "json"
        jd.mkdir()
        (jd / "s2_guo.json").write_text(json.dumps(_s2_conference_json(
            "On Calibration of Modern Neural Networks",
            "International Conference on Machine Learning", "1321-1330")),
            encoding="utf-8")

        bib = tmp_path / "lit.bib"
        bib.write_text(
            "@inproceedings{guo2017calibration,\n"
            "  author = {Guo, Chuan and Pleiss, Geoff},\n"
            "  title = {On Calibration of Modern Neural Networks},\n"
            "  booktitle = {Proceedings of the 34th International Conference on"
            " Machine Learning (ICML 2017)},\n"
            "  pages = {1321--1330},\n"
            "  year = {2017}\n}\n", encoding="utf-8")

        clean_bibtex(bib, [jd])

        out = parse_string(bib.read_text(encoding="utf-8"), "bibtex")
        entry = out.entries["guo2017calibration"]
        assert entry.type.lower() == "inproceedings", "must not be demoted to @misc"
        assert entry.fields.get("booktitle"), "venue must survive"
        assert entry.fields.get("pages")

    def test_fabricated_venue_is_still_removed(self, tmp_path):
        """The fold must not blunt the cleaner: an invented venue still goes."""
        jd = tmp_path / "json"
        jd.mkdir()
        (jd / "s2_guo.json").write_text(json.dumps(_s2_conference_json(
            "On Calibration of Modern Neural Networks",
            "International Conference on Machine Learning", "1321-1330")),
            encoding="utf-8")

        bib = tmp_path / "lit.bib"
        bib.write_text(
            "@inproceedings{guo2017calibration,\n"
            "  author = {Guo, Chuan},\n"
            "  title = {On Calibration of Modern Neural Networks},\n"
            "  booktitle = {Proceedings of the Aristotelian Society},\n"
            "  year = {2017}\n}\n", encoding="utf-8")

        clean_bibtex(bib, [jd])

        out = parse_string(bib.read_text(encoding="utf-8"), "bibtex")
        entry = out.entries["guo2017calibration"]
        assert not entry.fields.get("booktitle"), "invented venue must be removed"


# =============================================================================
# OpenAlex as provenance for volume / issue / pages
# =============================================================================

class TestOpenAlexBiblioReadThrough:

    def _oa(self, biblio, publisher=None):
        return {"results": [{
            "title": "T", "publication_year": 2020, "doi": "10.1/x",
            "source": {"name": "Mind", "publisher": publisher},
            "biblio": biblio,
        }]}

    def test_volume_issue_pages_are_read_through(self):
        rec = parse_openalex_result(self._oa(
            {"volume": "129", "issue": "514",
             "first_page": "405", "last_page": "432"}), "oa.json")[0]
        assert rec["volume"] == "129"
        assert rec["issue"] == "514"
        assert rec["pages"] == "405-432"

    def test_single_page_is_not_rendered_as_a_range(self):
        rec = parse_openalex_result(
            self._oa({"first_page": "7", "last_page": "7"}), "oa.json")[0]
        assert rec["pages"] == "7"

    def test_first_page_only(self):
        rec = parse_openalex_result(
            self._oa({"first_page": "7"}), "oa.json")[0]
        assert rec["pages"] == "7"

    def test_publisher_is_read_through(self):
        rec = parse_openalex_result(
            self._oa({}, publisher="Oxford University Press"), "oa.json")[0]
        assert rec["publisher"] == "Oxford University Press"

    def test_absent_biblio_is_the_old_behaviour(self):
        """Result files written before the producer emitted `biblio`."""
        rec = parse_openalex_result(
            {"results": [{"title": "T", "source": {"name": "Mind"}}]}, "oa.json")[0]
        assert rec["volume"] is None
        assert rec["issue"] is None
        assert rec["pages"] is None

    def test_non_dict_biblio_does_not_crash(self):
        rec = parse_openalex_result(
            {"results": [{"title": "T", "biblio": "junk",
                          "source": {"name": "Mind"}}]}, "oa.json")[0]
        assert rec["pages"] is None

    def test_openalex_pages_verify_a_bibliography(self, tmp_path):
        """The point of the read-through: a correct page range now survives."""
        jd = tmp_path / "json"
        jd.mkdir()
        (jd / "openalex_x.json").write_text(json.dumps({
            "status": "ok", "source": "openalex", "count": 1,
            "results": [{
                "title": "A Paper", "publication_year": 2020, "doi": "10.1/x",
                "source": {"name": "Mind", "publisher": "OUP"},
                "biblio": {"volume": "129", "issue": "514",
                           "first_page": "405", "last_page": "432"},
            }]}), encoding="utf-8")
        index = build_metadata_index(jd)

        assert is_field_verifiable('pages', '405--432', index) is True
        assert is_field_verifiable('volume', '129', index) is True
        assert is_field_verifiable('publisher', 'OUP', index) is True
        assert is_field_verifiable('pages', '999--1000', index) is False


class TestOpenAlexProducerEmitsBiblio:
    """The consumer above can only read what search_openalex.py writes."""

    def test_format_work_emits_biblio_and_publisher(self):
        from search_openalex import format_work
        out = format_work({
            "id": "https://openalex.org/W1", "title": "T",
            "publication_year": 2020,
            "primary_location": {"source": {
                "display_name": "Mind", "type": "journal", "issn": ["0026-4423"],
                "host_organization_name": "Oxford University Press"}},
            "biblio": {"volume": "129", "issue": "514",
                       "first_page": "405", "last_page": "432"},
        })
        assert out["biblio"] == {"volume": "129", "issue": "514",
                                 "first_page": "405", "last_page": "432"}
        assert out["source"]["publisher"] == "Oxford University Press"

    def test_absent_biblio_emits_none(self):
        from search_openalex import format_work
        out = format_work({"id": "https://openalex.org/W1", "title": "T",
                           "publication_year": 2020})
        assert out["biblio"] is None

    def test_producer_output_round_trips_into_the_cleaner(self):
        """Producer and consumer must agree on the shape, not just each on its own."""
        from search_openalex import format_work
        work = format_work({
            "id": "https://openalex.org/W1", "title": "T",
            "publication_year": 2020,
            "primary_location": {"source": {
                "display_name": "Mind",
                "host_organization_name": "Oxford University Press"}},
            "biblio": {"volume": "129", "first_page": "405", "last_page": "432"},
        })
        rec = parse_openalex_result({"results": [work]}, "oa.json")[0]
        assert rec["pages"] == "405-432"
        assert rec["volume"] == "129"
        assert rec["publisher"] == "Oxford University Press"
        assert rec["container_title"] == "Mind"


class TestRemainingGuards:
    """Guards whose mutants survived the first pass — each now pinned."""

    def test_volume_number_survives_after_a_prefix_was_stripped(self):
        """Once a prefix is removed the string is a known series instance, which
        licenses removing a trailing number. A VOLUME number must still be
        exempt: it identifies the book rather than the instance."""
        key = venue_key("Proceedings of the 5th International Conference on"
                        " Ethics Volume 2")
        assert key.endswith("volume 2"), key
        assert key != venue_key("Proceedings of the 5th International Conference"
                                " on Ethics Volume 3")

    def test_unhyphenated_ordinal_in_a_name_is_not_stripped(self):
        """Without the hyphen, "Eighteenth Century Life" would lose its head
        if a leading ordinal were stripped unlicensed.
        Nothing here names a conference, so no ordinal strip may fire."""
        assert venue_key("Eighteenth Century Life") == "eighteenth century life"
        assert venue_key("Eighteenth Century Life") != venue_key("Century Life")

    def test_lone_last_page_is_not_a_page_value(self):
        """OpenAlex emits last_page-only records where an article number was
        mis-parsed, and treating it as a page would let a
        bibliography verify a page the source never attested."""
        rec = parse_openalex_result(
            {"results": [{"title": "T", "source": {"name": "Mind"},
                          "biblio": {"last_page": "432"}}]}, "oa.json")[0]
        assert rec["pages"] is None
        # first_page alone remains a real single-page citation.
        rec2 = parse_openalex_result(
            {"results": [{"title": "T", "source": {"name": "Mind"},
                          "biblio": {"first_page": "7"}}]}, "oa.json")[0]
        assert rec2["pages"] == "7"


class TestConferenceWordInsideAProperNoun:
    """Every fabrication case above picks a journal with NO conference word in
    its name, so none of them exercise
    the path where `_CONF_WORD` matches a proper-noun component. These pin that
    path — one side as a fixed defect, one side as a measured, accepted bound."""

    def test_ordinal_does_not_license_removing_a_volume_number(self):
        """FIXED. A conference word anywhere licenses the ordinal strip, but the
        ordinal must not then license the trailing-number strip — otherwise
        "congress" inside an institution name deletes a real volume number."""
        assert venue_key("7th Library of Congress Quarterly 7") != \
            venue_key("Library of Congress Quarterly")

    @pytest.mark.parametrize("fabricated,real", [
        ("Proceedings of the Library of Congress Quarterly",
         "Library of Congress Quarterly"),
        ("Proceedings of the Congress & the Presidency", "Congress & the Presidency"),
        ("Proceedings of the History Workshop Journal", "History Workshop Journal"),
    ])
    def test_proceedings_wrapper_is_accepted_over_a_conference_worded_journal(
            self, fabricated, real):
        """ACCEPTED BOUND 4, pinned so it stays a known bound rather than a blind
        spot. These SHOULD ideally differ, and they do not.

        The fix — requiring the conference word to head the phrase — was measured
        against the corpus and rejected: it strips 56 genuine conference series of
        their fold while protecting only 7 of the 9 journals of this shape it
        targets, causing about eight times more `booktitle` deletion than it
        prevents. If this assertion ever starts failing, someone has changed that
        trade; re-measure first, with
        the folds-lost-against-journals-protected trade over the venue corpus.
        """
        assert venue_key(fabricated) == venue_key(real)

    def test_the_bound_does_not_extend_to_journals_without_a_conference_word(self):
        """The far more common shape stays protected."""
        for fabricated, real in [("Proceedings of the Journal of Philosophy",
                                  "Journal of Philosophy"),
                                 ("Proceedings of the Mind", "Mind")]:
            assert venue_key(fabricated) != venue_key(real)
