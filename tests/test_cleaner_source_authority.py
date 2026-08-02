"""Tests for source-authority handling in metadata_cleaner.py.

Fix for docs/known-issues/metadata-cleaner-year-corruption.md: broad
keyword-search dumps (s2_*, openalex_*, ...) must never overwrite a
field value; only entry-scoped CrossRef verification files (verify_*)
carry correction authority. Same-DOI year disagreements across pooled
sources are surfaced as warnings.
"""

import json
import re
import sys
from pathlib import Path

import pytest

# Add hooks directory to path
HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from metadata_cleaner import (
    build_metadata_index,
    clean_bibtex,
    find_api_entry_by_doi,
    find_doi_year_conflicts,
    _year_key,
)



def assert_no_cleaned_marker(content: str) -> None:
    """Assert the cleaner wrote no METADATA_CLEANED marker.

    NOT `assert "METADATA_CLEANED" not in content`: pybtex escapes the
    underscore on write (`METADATA\\_CLEANED`, and `METADATA\\\\_CLEANED` on a
    second round-trip), so the plain-string form never appears and that
    assertion can never fail. Match the same backslash-tolerant shape the
    module's own _MARKER_RE uses.
    """
    assert not re.search(r"METADATA\\*_CLEANED", content), content


SPARROW_DOI = "10.1111/j.1468-5930.2007.00346.x"

# Broad Semantic Scholar topic-search dump: returns the Sparrow paper as a
# side-hit with S2's wrong year (2019). Filename s2_* sorts BEFORE verify_*.
S2_DUMP = {
    "status": "success",
    "source": "semantic_scholar",
    "results": [
        {
            "title": "Killer Robots",
            "year": 2019,
            "doi": SPARROW_DOI,
            "journal": {"name": "Journal of Applied Philosophy"},
        }
    ],
}

# Entry-scoped CrossRef verification (verify_paper.py --doi output shape):
# the authoritative record, correct year.
VERIFY_RESULT = {
    "status": "success",
    "source": "crossref",
    "results": [
        {
            "title": "Killer Robots",
            "container_title": "Journal of Applied Philosophy",
            "year": 2007,
            "doi": SPARROW_DOI,
            "volume": "24",
            "issue": "1",
            "page": "62-77",
            "publisher": "Wiley",
        }
    ],
}

SPARROW_BIB_CORRECT = """@article{sparrow2007,
  author = {Sparrow, Robert},
  title = {Killer Robots},
  journal = {Journal of Applied Philosophy},
  year = {2007},
  doi = {10.1111/j.1468-5930.2007.00346.x}
}"""


def make_json_dir(tmp_path, files):
    """Write {filename: payload} dicts into tmp_path/json and return the dir."""
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    for name, payload in files.items():
        (json_dir / name).write_text(json.dumps(payload), encoding="utf-8")
    return json_dir


class TestSourceTagging:
    def test_entries_tagged_with_source_file_and_scope(self, tmp_path):
        """Every pooled entry records its source filename; verify_* files are
        entry-scoped, broad search dumps are not."""
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })

        index = build_metadata_index(json_dir)

        by_file = {e["source_file"]: e for e in index.entries}
        assert by_file["s2_roff.json"]["entry_scoped"] is False
        assert by_file["verify_3_sparrow2007.json"]["entry_scoped"] is True

    def test_verify_detection_is_case_insensitive_substring(self, tmp_path):
        """Domain-prefixed and oddly-cased verify filenames still count as
        entry-scoped (same rule detect_api_source already uses)."""
        json_dir = make_json_dir(tmp_path, {
            "domain-1_VERIFY_bainbridge1983.json": VERIFY_RESULT,
        })

        index = build_metadata_index(json_dir)

        assert index.entries[0]["entry_scoped"] is True


class TestDoiLookupPriority:
    def test_verify_record_outranks_earlier_broad_dump(self, tmp_path):
        """s2_roff.json sorts alphabetically before verify_*.json, so pool
        order alone would return the wrong (2019) record. The entry-scoped
        verify record must win regardless of filename sort."""
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)

        api_entry = find_api_entry_by_doi(SPARROW_DOI, index)

        assert api_entry["source_file"] == "verify_3_sparrow2007.json"
        assert api_entry["year"] == 2007

    def test_broad_dump_still_matches_when_no_verify_file(self, tmp_path):
        """Without a verify file, first-match behavior is unchanged (broad
        dumps still gate cleaning; they just lose correction authority in
        plan_entry_cleaning, Task 3)."""
        json_dir = make_json_dir(tmp_path, {"s2_roff.json": S2_DUMP})
        index = build_metadata_index(json_dir)

        api_entry = find_api_entry_by_doi(SPARROW_DOI, index)

        assert api_entry is not None
        assert api_entry["source_file"] == "s2_roff.json"

    def test_two_verify_files_first_in_pool_order_wins(self, tmp_path):
        """Tie-break pin: when two entry-scoped verify files carry the same
        DOI, the alphabetically-earlier one wins (pool order among equal
        rank). Task 4's conflict warning makes any disagreement visible."""
        other_verify = json.loads(json.dumps(VERIFY_RESULT))
        other_verify["results"][0]["year"] = 2008
        json_dir = make_json_dir(tmp_path, {
            "verify_1_sparrow2007.json": other_verify,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)

        api_entry = find_api_entry_by_doi(SPARROW_DOI, index)

        assert api_entry["source_file"] == "verify_1_sparrow2007.json"
        assert api_entry["year"] == 2008


# Sparse entry-scoped record: a verify_paper.py --doi lookup that resolved
# only partial metadata (year missing). Must NOT authorize a correction,
# and must NOT let the broad dump's wrong year through either (gate #3
# requires api_entry.get("year") truthy on the SELECTED record).
VERIFY_RESULT_NO_YEAR = {
    "status": "success",
    "source": "crossref",
    "results": [
        {
            "title": "Killer Robots",
            "container_title": "Journal of Applied Philosophy",
            "year": None,
            "doi": SPARROW_DOI,
            "volume": "24",
            "issue": "1",
            "page": "62-77",
            "publisher": "Wiley",
        }
    ],
}

SPARROW_BIB_WRONG_YEAR = """@article{sparrow2007,
  author = {Sparrow, Robert},
  title = {Killer Robots},
  journal = {Journal of Applied Philosophy},
  year = {1999},
  doi = {10.1111/j.1468-5930.2007.00346.x}
}"""


class TestYearCorrectionAuthority:
    def test_regression_correct_year_not_overwritten_by_broad_dump(self, tmp_path):
        """The observed corruption (Sparrow 2007 -> 2019): bib year is correct
        and CrossRef-verified; an s2 dump with the same DOI and a wrong year
        sorts first. The year must stay 2007 with no METADATA_CLEANED marker."""
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")

        result = clean_bibtex(bib_file, json_dir)

        assert result["success"] is True
        assert result["years_corrected"] == 0
        content = bib_file.read_text(encoding="utf-8")
        assert "2007" in content
        assert_no_cleaned_marker(content)

    def test_wrong_bib_year_corrected_from_verify_not_broad_dump(self, tmp_path):
        """When the bib year is genuinely wrong, correction still fires - and
        takes the verify file's value (2007), not the s2 dump's (2019)."""
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(SPARROW_BIB_WRONG_YEAR, encoding="utf-8")

        result = clean_bibtex(bib_file, json_dir)

        assert result["years_corrected"] == 1
        content = bib_file.read_text(encoding="utf-8")
        assert "2007" in content
        assert "year:1999" in content  # marker records the old value

    def test_no_correction_when_only_broad_dump_has_doi(self, tmp_path):
        """Option C conservatism: with no entry-scoped record at all, a
        year mismatch against a broad dump is NOT corrected - the dump was
        never queried for this entry and may be wrong (both confirmed
        instances were). The bib's original year survives."""
        json_dir = make_json_dir(tmp_path, {"s2_roff.json": S2_DUMP})
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")

        result = clean_bibtex(bib_file, json_dir)

        assert result["years_corrected"] == 0
        content = bib_file.read_text(encoding="utf-8")
        assert "2007" in content

    def test_no_correction_when_verify_record_has_no_year(self, tmp_path):
        """Sparse verify record (lacks year - e.g. a --doi lookup that only
        resolved partial metadata) must not authorize an overwrite. Gates
        #2 (lookup priority) and #3 (entry_scoped gate) interact here: #2
        selects this yearless verify record over the broad dump (it is
        entry-scoped), and #3 then blocks correction because the selected
        record's year is falsy - the broad dump's wrong year is never
        consulted because it was never selected."""
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT_NO_YEAR,
        })
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")

        result = clean_bibtex(bib_file, json_dir)

        assert result["years_corrected"] == 0
        content = bib_file.read_text(encoding="utf-8")
        assert "2007" in content
        assert_no_cleaned_marker(content)


class TestConflictVisibility:
    def test_conflicting_years_produce_warning(self, tmp_path):
        """Option D: a same-DOI year disagreement across pooled sources is
        logged in the cleaning report, naming values and files - even when
        the resolution leaves the bib untouched."""
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")

        result = clean_bibtex(bib_file, json_dir)

        conflict_warnings = [w for w in result["warnings"] if "disagree" in w]
        assert len(conflict_warnings) == 1
        w = conflict_warnings[0]
        assert "sparrow2007" in w
        assert "2007" in w and "2019" in w
        assert "verify_3_sparrow2007.json" in w and "s2_roff.json" in w

    def test_no_warning_when_sources_agree(self, tmp_path):
        """A single source (or agreeing sources) produces no conflict noise."""
        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")

        result = clean_bibtex(bib_file, json_dir)

        assert not [w for w in result["warnings"] if "disagree" in w]

    def test_helper_returns_empty_without_conflict(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {"s2_roff.json": S2_DUMP})
        index = build_metadata_index(json_dir)
        assert find_doi_year_conflicts(SPARROW_DOI, index) == {}
        assert find_doi_year_conflicts("", index) == {}

    def test_helper_maps_years_to_source_files(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)

        conflicts = find_doi_year_conflicts(SPARROW_DOI, index)

        assert conflicts == {
            "2007": ["verify_3_sparrow2007.json"],
            "2019": ["s2_roff.json"],
        }


def test_assert_no_cleaned_marker_actually_catches_a_written_marker(tmp_path):
    """Guard the guard: pin that the escaped form pybtex really writes DOES
    trip the helper, so the two assertions above cannot go vacuous again."""
    json_dir = make_json_dir(tmp_path, {"s2_roff.json": S2_DUMP})
    bib_file = tmp_path / "test.bib"
    # `number` is absent from every pooled record -> removed -> marker written.
    bib_file.write_text(
        "@article{sparrow2007,\n"
        "  author = {Sparrow, Robert},\n"
        "  title = {Killer Robots},\n"
        "  journal = {Journal of Applied Philosophy},\n"
        "  year = {2007},\n"
        "  number = {1},\n"
        f"  doi = {{{SPARROW_DOI}}}\n"
        "}", encoding="utf-8")

    result = clean_bibtex(bib_file, json_dir)
    assert result["total_fields_removed"] >= 1

    content = bib_file.read_text(encoding="utf-8")
    assert "METADATA_CLEANED" not in content       # the OLD, vacuous assertion still "passes"
    with pytest.raises(AssertionError):            # ...while the real one fails, as it must
        assert_no_cleaned_marker(content)


class TestTypeDowngradeDoiGuard:
    """K1: `_plan_type_downgrade` compared DOIs without a non-empty guard, so
    two MALFORMED dois (both normalizing to "") read as a verified match and
    suppressed the demotion of an @article that had just lost its `journal`."""

    def _case(self, tmp_path, bib_doi, api_doi):
        json_dir = make_json_dir(tmp_path, {"s2.json": {
            "source": "semantic_scholar",
            "results": [{"title": "A Paper", "year": 2020, "doi": api_doi,
                         "journal": {"name": "Real Journal"}}]}})
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(
            "@article{k, author = {A, B}, title = {A Paper}, year = {2020}, "
            "journal = {Fake Journal}, doi = {%s}}" % bib_doi, encoding="utf-8")
        result = clean_bibtex(bib_file, json_dir)
        return result, bib_file.read_text(encoding="utf-8").lower()

    def test_malformed_dois_do_not_count_as_verified(self, tmp_path):
        from metadata_cleaner import normalize_doi
        assert normalize_doi("doi:") == normalize_doi("https://doi.org/") == ""
        result, text = self._case(tmp_path, "doi:", "https://doi.org/")
        assert result["types_downgraded"] == 1
        assert "@misc" in text

    def test_differing_real_dois_still_demote(self, tmp_path):
        result, text = self._case(tmp_path, "10.1/real", "10.2/other")
        assert result["types_downgraded"] == 1
        assert "@misc" in text

    def test_matching_real_doi_still_blocks_the_demotion(self, tmp_path):
        result, text = self._case(tmp_path, "10.1/same", "10.1/same")
        assert result["types_downgraded"] == 0
        assert "@article" in text


MALFORMED_DOI_DUMP = {
    "status": "success",
    "source": "semantic_scholar",
    "results": [
        {
            "title": "An Entirely Different Paper",
            "year": 1999,
            "doi": "https://doi.org/",
            "journal": {"name": "Some Other Journal"},
        }
    ],
}


class TestEmptyNormalizedDoiGuard:
    """The two index SCANS still compared normalized DOIs without the
    non-empty guard that _field_matches_api has always carried (and that
    _plan_type_downgrade gained in 7f6d38f)."""

    def test_malformed_doi_does_not_match_another_malformed_doi(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {"s2_other.json": MALFORMED_DOI_DUMP})
        index = build_metadata_index(json_dir)

        assert find_api_entry_by_doi("doi:", index) is None

    def test_malformed_doi_reports_no_year_conflict(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "s2_other.json": MALFORMED_DOI_DUMP,
            "s2_more.json": {
                "status": "success",
                "source": "semantic_scholar",
                "results": [
                    {"title": "Third Paper", "year": 2001, "doi": "doi:"}
                ],
            },
        })
        index = build_metadata_index(json_dir)

        assert find_doi_year_conflicts("https://doi.org/", index) == {}

    def test_real_doi_lookup_still_works(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {"verify_3_sparrow2007.json": VERIFY_RESULT})
        index = build_metadata_index(json_dir)

        assert find_api_entry_by_doi(SPARROW_DOI, index)["year"] == 2007


class TestYearKey:
    """Canonicalization must be EXACT: the correction path writes this value
    into the .bib, so the helper must never return a number it was not given."""

    @pytest.mark.parametrize("value,expected", [
        (2007, "2007"),
        (2007.0, "2007"),
        ("2007", "2007"),
        ("  2007  ", "2007"),
        ("2007.0", "2007"),
        ("2007.00", "2007"),
        ("0002007", "2007"),
        ("+2007", "2007"),
        ("-2007", "-2007"),
        ("2007.5", "2007.5"),        # non-integral: do NOT collapse to 2007
        ("2.007e3", "2.007e3"),      # exponent notation is out of scope by design
        ("1e999", "1e999"),
        ("n.d.", "n.d."),
        ("forthcoming", "forthcoming"),
        ("MMVII", "MMVII"),
        ("2,007", "2,007"),
        ("", ""),
        (None, "None"),
        (True, "True"),              # a bool must not become "1"
    ])
    def test_canonical_forms(self, value, expected):
        assert _year_key(value) == expected

    @pytest.mark.parametrize("value", [
        9007199254740993,            # > 2**53: float() would return ...992
        12345678901234567890,
        10 ** 400,                   # float() would overflow
    ])
    def test_large_integers_are_exact(self, value):
        assert _year_key(value) == str(value)

    def test_near_integral_float_string_is_not_collapsed(self):
        """A float round-trip rounds this to 2007.0 and collapses it."""
        assert _year_key("2007.0000000000001") == "2007.0000000000001"

    def test_equivalences_and_distinctions(self):
        assert _year_key(2007) == _year_key(2007.0) == _year_key("0002007") == "2007"
        assert _year_key("2007") != _year_key("2007.5")


class TestYearNormalizationAcrossComparisons:
    def test_int_and_float_years_are_not_a_conflict(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "s2_int.json": {
                "status": "success", "source": "semantic_scholar",
                "results": [
                    {"title": "Killer Robots", "year": 2007, "doi": SPARROW_DOI}
                ],
            },
            "s2_float.json": {
                "status": "success", "source": "semantic_scholar",
                "results": [
                    {"title": "Killer Robots", "year": 2007.0, "doi": SPARROW_DOI}
                ],
            },
        })
        index = build_metadata_index(json_dir)

        assert find_doi_year_conflicts(SPARROW_DOI, index) == {}

    def test_genuine_disagreement_is_still_a_conflict(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)

        assert set(find_doi_year_conflicts(SPARROW_DOI, index)) == {"2007", "2019"}

    def test_non_numeric_year_still_conflicts_as_itself(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "s2_nd.json": {
                "status": "success", "source": "semantic_scholar",
                "results": [
                    {"title": "Killer Robots", "year": "n.d.", "doi": SPARROW_DOI}
                ],
            },
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)

        assert set(find_doi_year_conflicts(SPARROW_DOI, index)) == {"n.d.", "2007"}

    def test_float_api_year_does_not_plan_a_phantom_correction(self, tmp_path):
        """A phantom CORRECTION is worse than a phantom conflict: it rewrites
        the .bib. An entry-scoped record carrying 2007.0 against a bib year of
        2007 must plan nothing."""
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {"verify_3_sparrow2007.json": VERIFY_RESULT})
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]
        api_entry = {
            "year": 2007.0, "entry_scoped": True, "doi": SPARROW_DOI,
            "title": "Killer Robots",
            "container_title": "Journal of Applied Philosophy",
            "source_file": "verify_3_sparrow2007.json",
        }

        plan = plan_entry_cleaning(entry, index, api_entry)

        assert plan["year_corrected"] is None

    def test_title_year_fallback_tolerates_float_api_year(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "s2_nodoi.json": {
                "status": "success", "source": "semantic_scholar",
                "results": [{"title": "Killer Robots", "year": 2007.0}],
            },
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(
            "@article{s2007,\n"
            "  author = {Sparrow, Robert},\n"
            "  title = {Killer Robots},\n"
            "  year = {2007}\n"
            "}", "bibtex").entries["s2007"]

        assert find_api_entry_for_bib_entry(entry, index) is not None


SPARROW_BIB_WITH_BAD_YEAR = """@article{sparrow2007,
  author = {Sparrow, Robert},
  title = {Killer Robots},
  journal = {Journal of Applied Philosophy},
  year = {2019},
  doi = {10.1111/j.1468-5930.2007.00346.x}
}"""

S2_DUMP_CONFLICTING = {
    "status": "success",
    "source": "semantic_scholar",
    "results": [
        {
            "title": "Killer Robots", "year": 2019, "doi": SPARROW_DOI,
            "journal": {"name": "Wrong Journal Name"},
        }
    ],
}

S2_DUMP_OTHER_YEAR = {
    "status": "success",
    "source": "semantic_scholar",
    "results": [
        {
            "title": "Killer Robots", "year": 2015, "doi": SPARROW_DOI,
            "journal": {"name": "Another Wrong Journal"},
        }
    ],
}


class TestConflictedDoiAbstention:
    def test_conflicted_doi_without_authority_returns_no_match(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        assert find_api_entry_for_bib_entry(entry, index) is None

    def test_conflicted_doi_is_not_rescued_by_title_year_fallback(self, tmp_path):
        """Abstention must be TERMINAL. With the bib year already equal to the
        bad value, a fall-through would let the weaker signal confirm the
        wrong record - the circular confirmation this exists to prevent."""
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(
            SPARROW_BIB_WITH_BAD_YEAR, "bibtex").entries["sparrow2007"]

        assert find_api_entry_for_bib_entry(entry, index) is None

    def test_entry_scoped_record_still_resolves_a_conflict(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "s2_roff.json": S2_DUMP,
            "verify_3_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        api = find_api_entry_for_bib_entry(entry, index)

        assert api is not None
        assert api["source_file"] == "verify_3_sparrow2007.json"
        assert api["year"] == 2007

    def test_agreeing_sources_still_match(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {"s2_a.json": S2_DUMP_CONFLICTING})
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        assert find_api_entry_for_bib_entry(entry, index) is not None

    def test_conflicted_doi_does_not_strip_a_correct_field(self, tmp_path):
        """The measured harm: today the entry counts as MATCHED, so it is
        cleaned against the untrusted record and its correct journal is
        REMOVED."""
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")
        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })

        result = clean_bibtex(bib, json_dir)

        text = bib.read_text(encoding="utf-8")
        assert "Journal of Applied Philosophy" in text
        assert_no_cleaned_marker(text)
        assert result["unmatched_entries"] == 1
        assert result["matched_entries"] == 0

    def test_conflict_warning_survives_abstention(self, tmp_path):
        """Abstaining must not hide the disagreement that caused it."""
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")
        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })

        result = clean_bibtex(bib, json_dir)

        assert any("disagree on year" in w for w in result["warnings"])


VERIFY_RESULT_DISAGREEING = {
    "status": "success",
    "source": "crossref",
    "results": [
        {
            "title": "Killer Robots",
            "container_title": "Journal of Applied Philosophy",
            "year": 2011,
            "doi": SPARROW_DOI,
        }
    ],
}


class TestDualEntryScopedDisagreement:
    def test_two_disagreeing_verify_records_abstain(self, tmp_path):
        """Filename order must not decide which CrossRef snapshot may rewrite
        the bib year. CrossRef records are mutable across runs."""
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
            "verify_9_sparrow2007.json": VERIFY_RESULT_DISAGREEING,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        assert find_api_entry_for_bib_entry(entry, index) is None

    def test_two_agreeing_verify_records_still_resolve(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
            "verify_9_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        assert find_api_entry_for_bib_entry(entry, index) is not None

    def test_yearless_scoped_record_does_not_shadow_a_year_bearing_one(self, tmp_path):
        """A partial verify_* snapshot sorting first must not suppress the
        correction a complete one would authorize."""
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_1_sparrow2007.json": {
                "status": "success", "source": "crossref",
                "results": [{"title": "Killer Robots", "doi": SPARROW_DOI}],
            },
            "verify_9_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        api = find_api_entry_for_bib_entry(entry, index)

        assert api is not None
        assert api["year"] == 2007

    def test_disagreeing_scoped_records_do_not_rewrite_the_year(self, tmp_path):
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")
        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
            "verify_9_sparrow2007.json": VERIFY_RESULT_DISAGREEING,
        })

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 0
        assert "2007" in bib.read_text(encoding="utf-8")
        assert any("disagree on year" in w for w in result["warnings"])
