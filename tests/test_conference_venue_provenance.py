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
        """The volume guard, not the proceedings gate, has to do the work here.

        A name that reads as proceedings opens the aggressive strips, so the
        trailing number is only saved by the volume-word check inside them.
        """
        five = venue_key("Proceedings of the Aristotelian Society Volume 5")
        eight = venue_key("Proceedings of the Aristotelian Society Volume 8")
        assert five != eight
        assert five == "aristotelian society volume 5"

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


class TestClearnerAcceptsExpandedVenue:

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
