"""Item 13 A7: generate_bibliography dedup (title axis + winner policy +
union-into-survivor + DOI-group bridge guard) and the dangling-'In.' guard."""

import re
import sys
from pathlib import Path

from pybtex.database import parse_string

SCRIPT_DIR = Path(__file__).parent.parent / "skills/literature-review/scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import generate_bibliography as mod  # noqa: E402


def test_fallback_key_and_substantive_count():
    bib = (
        "@article{doe2020a,\n"
        "  author = {Doe, Jane},\n"
        "  title = {A Study of Minds},\n"
        "  year = {2020},\n"
        "  journal = {J Phil},\n"
        "  doi = {10.1/x},\n"
        "}\n"
        "@misc{bare2020,\n"
        "  author = {Roe, Sam},\n"
        "  title = {Untitled},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    key = mod._fallback_key(db.entries["doe2020a"])
    assert key == ("a study of minds", "2020", "doe")
    # missing year -> no fallback key
    assert mod._fallback_key(db.entries["bare2020"]) is None
    assert mod._substantive_field_count(db.entries["doe2020a"]) == 2  # journal + doi


def test_no_doi_duplicate_is_deduped_richer_wins():
    bib = (
        "@article{amoroso2017a,\n"
        "  author = {Amoroso, Daniele and Tamburrini, Guglielmo},\n"
        "  title = {The Case Against Autonomy in Weapons Systems},\n"
        "  year = {2017},\n"
        "  journal = {Global Jurist},\n"
        "}\n"
        "@article{amoroso2017b,\n"
        "  author = {Amoroso, Daniele and Tamburrini, Guglielmo},\n"
        "  title = {The Case Against Autonomy in Weapons Systems},\n"
        "  year = {2017},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    review = "As Amoroso 2017 argue, autonomy in weapons is problematic."
    cited = dict(mod.find_cited_entries(review, db))
    assert len(cited) == 1
    assert "amoroso2017a" in cited  # journal-bearing entry has more substantive fields


def test_differing_dois_same_work_not_merged():
    bib = (
        "@article{smith2020pre,\n"
        "  author = {Smith, John},\n"
        "  title = {A Study of Minds},\n"
        "  year = {2020},\n"
        "  doi = {10.1/preprint},\n"
        "}\n"
        "@article{smith2020pub,\n"
        "  author = {Smith, John},\n"
        "  title = {A Study of Minds},\n"
        "  year = {2020},\n"
        "  doi = {10.1/published},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    review = "Smith 2020 discusses minds."
    cited = dict(mod.find_cited_entries(review, db))
    assert len(cited) == 2  # distinct DOIs => never auto-merged


def test_survivor_unions_loser_only_journal_and_doi():
    # Winner (king2019a) has more substantive fields overall (volume+number+
    # pages = 3); the loser (king2019b) carries a journal + doi (2) the winner
    # lacks. The winner survives AND UNIONs in the loser-only journal + doi
    # (spec v2.1 / ADV-A0).
    bib = (
        "@article{king2019a,\n"
        "  author = {King, Ada},\n"
        "  title = {Machines and Minds},\n"
        "  year = {2019},\n"
        "  volume = {12},\n"
        "  number = {3},\n"
        "  pages = {1--20},\n"
        "}\n"
        "@article{king2019b,\n"
        "  author = {King, Ada},\n"
        "  title = {Machines and Minds},\n"
        "  year = {2019},\n"
        "  journal = {Mind and Machine},\n"
        "  doi = {10.1/mm},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    review = "King 2019 explores machines and minds."
    cited = dict(mod.find_cited_entries(review, db))
    assert len(cited) == 1
    (key, entry), = cited.items()
    assert key == "king2019a"  # 3 substantive fields > 2
    assert mod._get_field(entry, "journal") == "Mind and Machine"      # unioned from loser
    assert mod._normalize_doi(mod._get_field(entry, "doi")) == "10.1/mm"  # unioned from loser


def test_doi_bridge_three_entries_not_over_merged():
    # A(doi=X, title=T), B(no doi, title=T), C(doi=Y, title=T). A+B may merge
    # (B has no DOI), but the resulting AB group (dois={X}) must NOT bridge to C
    # (dois={Y}) through the shared title — distinct DOI sets. Final: 2 entries
    # (GPT-B4). DOI identity is per GROUP, not per current winner.
    bib = (
        "@article{a_pre,\n"
        "  author = {Vale, Uma},\n"
        "  title = {Bridging Work},\n"
        "  year = {2023},\n"
        "  doi = {10.1/x},\n"
        "  journal = {Journal One},\n"
        "}\n"
        "@article{b_mid,\n"
        "  author = {Vale, Uma},\n"
        "  title = {Bridging Work},\n"
        "  year = {2023},\n"
        "}\n"
        "@article{c_pub,\n"
        "  author = {Vale, Uma},\n"
        "  title = {Bridging Work},\n"
        "  year = {2023},\n"
        "  doi = {10.1/y},\n"
        "  journal = {Journal Two},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    review = "Vale 2023 develops the idea."
    cited = dict(mod.find_cited_entries(review, db))
    assert len(cited) == 2  # AB merged; C stays distinct (DOI sets differ)
    dois = sorted(
        mod._normalize_doi(mod._get_field(e, "doi")) for e in cited.values()
    )
    assert dois == ["10.1/x", "10.1/y"]


def test_equal_counts_lexicographic_tie_break():
    # Equal substantive counts (each has exactly one journal). The
    # lexicographically-smaller citation key wins the tie (GPT-SF14c).
    bib = (
        "@article{zeta2021,\n"
        "  author = {Nolan, Ben},\n"
        "  title = {A Shared Title},\n"
        "  year = {2021},\n"
        "  journal = {Journal Z},\n"
        "}\n"
        "@article{alpha2021,\n"
        "  author = {Nolan, Ben},\n"
        "  title = {A Shared Title},\n"
        "  year = {2021},\n"
        "  journal = {Journal A},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    review = "Nolan 2021 is discussed."
    cited = dict(mod.find_cited_entries(review, db))
    assert len(cited) == 1
    assert "alpha2021" in cited  # lexicographically-first key wins the tie


def test_marker_note_keyword_noise_does_not_count():
    # The noisy entry has keywords (with a METADATA_CLEANED marker) + a note but
    # ZERO substantive fields; the plain entry has one substantive field (a
    # journal). Substantive count = 1 vs 0, so the plain entry wins — marker /
    # keyword / note text is NOT substantive (GPT-SF14c).
    bib = (
        "@article{noisy2022,\n"
        "  author = {West, Cara},\n"
        "  title = {Contested Ground},\n"
        "  year = {2022},\n"
        "  keywords = {High, METADATA_CLEANED, ai-ethics},\n"
        "  note = {Cleaned by metadata_cleaner; verify venue},\n"
        "}\n"
        "@article{plain2022,\n"
        "  author = {West, Cara},\n"
        "  title = {Contested Ground},\n"
        "  year = {2022},\n"
        "  journal = {Ethics Review},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    review = "West 2022 stakes out a position."
    cited = dict(mod.find_cited_entries(review, db))
    assert len(cited) == 1
    assert "plain2022" in cited  # one substantive field beats keyword/note noise
    assert mod._substantive_field_count(db.entries["noisy2022"]) == 0


def test_incollection_without_container_has_no_dangling_in():
    bib = (
        "@incollection{doe2019chapter,\n"
        "  author = {Doe, Jane},\n"
        "  title = {On Something},\n"
        "  year = {2019},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    out = mod.format_entry(db.entries["doe2019chapter"], "doe2019chapter")
    assert "In." not in out
    assert " In " not in out
    assert out.startswith("Doe, Jane. 2019.")


def test_inproceedings_without_booktitle_has_no_dangling_in():
    bib = (
        "@inproceedings{roe2018talk,\n"
        "  author = {Roe, Sam},\n"
        "  title = {A Talk},\n"
        "  year = {2018},\n"
        "}"
    )
    db = parse_string(bib, "bibtex")
    out = mod.format_entry(db.entries["roe2018talk"], "roe2018talk")
    assert "In." not in out
    assert re.search(r"\bIn\b", out) is None
