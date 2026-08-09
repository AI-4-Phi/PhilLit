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
            # verify_paper.py records WHICH CrossRef date field supplied the
            # year; only a version-of-record field licenses an overwrite.
            "year_basis": "published-print",
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

    def test_domain_prefixed_verify_file_is_still_scoped(self, tmp_path):
        """Back-compat pin for the naming the corpora actually use. NOTE this
        no longer tests the filename at all - the file qualifies because it is
        a single-result CrossRef envelope. See
        TestAuthorityIsKeyedOnContentNotFilename for the rule itself."""
        json_dir = make_json_dir(tmp_path, {
            "domain-1_VERIFY_bainbridge1983.json": VERIFY_RESULT,
        })

        index = build_metadata_index(json_dir)

        assert index.entries[0]["entry_scoped"] is True


class TestAuthorityIsKeyedOnContentNotFilename:
    """ROADMAP 3I. `entry_scoped` used to require "verify_" in the filename,
    which was wrong in both directions. Measured over the 45 local corpora:
    262 genuine single-work CrossRef lookups saved under other names lost
    correction authority, and the filename could equally grant it to a broad
    dump. Authority now follows the envelope: CrossRef + exactly one result.
    """

    def test_single_work_crossref_lookup_is_scoped_whatever_its_name(self, tmp_path):
        """D1, observed 262 times locally: a per-DOI CrossRef lookup saved as
        crossref_*.json was "trusted to acquit but not to convict" - its
        journal/volume/pages still protected fields from stripping, but it
        could not correct a wrong year."""
        json_dir = make_json_dir(tmp_path, {
            "crossref_williams_deed.json": VERIFY_RESULT,
        })

        index = build_metadata_index(json_dir)

        assert index.entries[0]["entry_scoped"] is True

    def test_multi_result_crossref_dump_is_not_scoped_even_when_named_verify(self, tmp_path):
        """D2: a BROAD CrossRef search saved as verify_*.json used to mark
        every record in it entry-scoped, letting one erroneous record
        authorize the very year rewrite the gate exists to refuse."""
        broad = json.loads(json.dumps(VERIFY_RESULT))
        broad["results"].append({
            "title": "Some Other Paper", "year": 1999,
            "doi": "10.1111/other", "container_title": "Elsewhere",
        })
        json_dir = make_json_dir(tmp_path, {"verify_search.json": broad})

        index = build_metadata_index(json_dir)

        assert [e["entry_scoped"] for e in index.entries] == [False, False]

    def test_non_crossref_source_is_never_scoped(self, tmp_path):
        """The api_source conjunct is retained and load-bearing: 11 multi-result
        verify_*.json files in the local corpora are Semantic Scholar dumps -
        the source class that caused the original corruption."""
        json_dir = make_json_dir(tmp_path, {"verify_habernal.json": S2_DUMP})

        index = build_metadata_index(json_dir)

        assert index.entries[0]["entry_scoped"] is False

    def test_empty_result_envelope_contributes_no_records(self, tmp_path):
        """The 181 verify_* files that lose the tag are all not_found/error
        envelopes with results: [] - they supply no records, which is why
        dropping the filename rule needs no legacy fallback."""
        json_dir = make_json_dir(tmp_path, {
            "verify_missing.json": {"status": "error", "source": "crossref",
                                    "results": [], "count": 0},
        })

        index = build_metadata_index(json_dir)

        assert index.entries == []


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
            "year": 2007.0, "entry_scoped": True, "year_basis": "published-print",
            "doi": SPARROW_DOI,
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
    def test_conflicted_doi_without_authority_abstains(self, tmp_path):
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        out = find_api_entry_for_bib_entry(entry, index)

        assert isinstance(out, CleaningAbstention)
        assert out.reason == "pooled_year_conflict"

    def test_conflicted_doi_is_not_rescued_by_title_year_fallback(self, tmp_path):
        """Abstention must be TERMINAL. With the bib year already equal to the
        bad value, a fall-through would let the weaker signal confirm the
        wrong record - the circular confirmation this exists to prevent."""
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(
            SPARROW_BIB_WITH_BAD_YEAR, "bibtex").entries["sparrow2007"]

        assert isinstance(
            find_api_entry_for_bib_entry(entry, index), CleaningAbstention)

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

        # A dict, specifically - not merely "not None", which an abstention
        # would also satisfy under the Option C contract.
        assert isinstance(find_api_entry_for_bib_entry(entry, index), dict)

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
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
            "verify_9_sparrow2007.json": VERIFY_RESULT_DISAGREEING,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        out = find_api_entry_for_bib_entry(entry, index)

        assert isinstance(out, CleaningAbstention)
        assert out.reason == "scoped_year_disagreement"

    def test_two_agreeing_verify_records_still_resolve(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
            "verify_9_sparrow2007.json": VERIFY_RESULT,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        assert isinstance(find_api_entry_for_bib_entry(entry, index), dict)

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


class TestAbstentionAttestsExistence:
    """Option C (evidence-tier divergence write-up §9): abstention is a
    year-scoped refusal built on an exact DOI match, so the ledger must
    attest existence (api_matched: True + the normalized DOI, plus an
    additive cleaning_abstained reason) - while cleaning behaviour stays
    identical to no-match: nothing removed, nothing corrected, no marker."""

    def _ledger_entry(self, tmp_path):
        payload = json.loads(
            (tmp_path / "intermediate_files" / "json" / "cleaning_ledger-lit.json")
            .read_text(encoding="utf-8"))
        return payload["entries"]["sparrow2007"]

    def test_pooled_conflict_returns_abstention_marker(self, tmp_path):
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        out = find_api_entry_for_bib_entry(entry, index)

        assert isinstance(out, CleaningAbstention)
        assert out.reason == "pooled_year_conflict"
        assert out.normalized_doi == SPARROW_DOI
        # Falsy on purpose: for cleaning decisions an abstention behaves
        # exactly like no-match; only the ledger records the difference.
        assert not out

    def test_scoped_disagreement_returns_abstention_marker(self, tmp_path):
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
            "verify_9_sparrow2007.json": VERIFY_RESULT_DISAGREEING,
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(SPARROW_BIB_CORRECT, "bibtex").entries["sparrow2007"]

        out = find_api_entry_for_bib_entry(entry, index)

        assert isinstance(out, CleaningAbstention)
        assert out.reason == "scoped_year_disagreement"
        assert out.normalized_doi == SPARROW_DOI

    def test_pooled_conflict_abstention_attests_existence_in_ledger(self, tmp_path):
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")
        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })

        result = clean_bibtex(bib, json_dir)

        ent = self._ledger_entry(tmp_path)
        assert ent["api_matched"] is True
        assert ent["verified_identifier"] == "doi"
        assert ent["verified_identifier_value"] == SPARROW_DOI
        assert ent["cleaning_abstained"] == "pooled_year_conflict"
        # The cleaner's own metrics are UNCHANGED by Option C: an abstained
        # entry still counts as unmatched (metric identity with main).
        assert result["matched_entries"] == 0
        assert result["unmatched_entries"] == 1

    def test_scoped_disagreement_abstention_attests_existence_in_ledger(self, tmp_path):
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")
        json_dir = make_json_dir(tmp_path, {
            "verify_3_sparrow2007.json": VERIFY_RESULT,
            "verify_9_sparrow2007.json": VERIFY_RESULT_DISAGREEING,
        })

        result = clean_bibtex(bib, json_dir)

        ent = self._ledger_entry(tmp_path)
        assert ent["api_matched"] is True
        assert ent["verified_identifier"] == "doi"
        assert ent["verified_identifier_value"] == SPARROW_DOI
        assert ent["cleaning_abstained"] == "scoped_year_disagreement"
        assert result["matched_entries"] == 0
        assert result["unmatched_entries"] == 1

    def test_abstention_still_declines_cleaning(self, tmp_path):
        """Attestation must not re-enable what abstention exists to prevent:
        no field removal, no year rewrite, no marker, and the refusal is
        countable."""
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")
        json_dir = make_json_dir(tmp_path, {
            "s2_a.json": S2_DUMP_CONFLICTING,
            "s2_b.json": S2_DUMP_OTHER_YEAR,
        })

        result = clean_bibtex(bib, json_dir)

        text = bib.read_text(encoding="utf-8")
        assert "Journal of Applied Philosophy" in text
        assert "2007" in text
        assert_no_cleaned_marker(text)
        assert result["years_corrected"] == 0
        assert result["planned_entries_cleaned"] == 0
        assert result["applied_entries_cleaned"] == 0
        assert result["abstained_entries"] == 1

    def test_genuine_no_match_does_not_attest(self, tmp_path):
        """A DOI absent from the index is a real no-match - Option C must not
        leak attestation onto it (§9: never attest the genuine no-match
        paths)."""
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")
        json_dir = make_json_dir(tmp_path, {
            "s2_other.json": {
                "status": "success", "source": "semantic_scholar",
                "results": [{"title": "Something Else Entirely",
                             "year": 1999, "doi": "10.9999/other"}],
            },
        })

        result = clean_bibtex(bib, json_dir)

        ent = self._ledger_entry(tmp_path)
        assert ent["api_matched"] is False
        assert ent["verified_identifier"] is None
        assert ent["verified_identifier_value"] is None
        assert "cleaning_abstained" not in ent
        assert result["abstained_entries"] == 0


class TestYearKeyWriteSafety:
    """Review findings (gpt-5.6-sol, 2026-08-02): a comparison KEY is not
    automatically a value that may be written into the .bib."""

    def test_whitespace_scoped_year_never_erases_a_populated_year(self, tmp_path):
        """`" "` is raw-truthy but canonicalizes to "". Testing raw truthiness
        and then writing the canonical form planned year_corrected
        ("2007" -> "") - it emptied a populated year."""
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        index = build_metadata_index(tmp_path / "nonexistent")
        entry = parse_string(
            "@article{x,author={A, B},title={T},year={2007},doi={10.1/x}}",
            "bibtex").entries["x"]
        api = {"year": " ", "entry_scoped": True, "year_basis": "published-print",
               "doi": "10.1/x", "title": "T"}

        plan = plan_entry_cleaning(entry, index, api)

        assert plan["year_corrected"] is None

    def test_non_numeric_scoped_year_is_never_written(self, tmp_path):
        """"n.d." is a legitimate key for comparison but must not be written
        into the bib as a corrected year."""
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        index = build_metadata_index(tmp_path / "nonexistent")
        entry = parse_string(
            "@article{x,author={A, B},title={T},year={2007},doi={10.1/x}}",
            "bibtex").entries["x"]
        api = {"year": "n.d.", "entry_scoped": True, "year_basis": "published-print",
               "doi": "10.1/x", "title": "T"}

        plan = plan_entry_cleaning(entry, index, api)

        assert plan["year_corrected"] is None

    def test_a_real_year_is_still_corrected(self, tmp_path):
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        index = build_metadata_index(tmp_path / "nonexistent")
        entry = parse_string(
            "@article{x,author={A, B},title={T},year={2019},doi={10.1/x}}",
            "bibtex").entries["x"]
        api = {"year": 2007, "entry_scoped": True, "year_basis": "published-print",
               "doi": "10.1/x", "title": "T"}

        plan = plan_entry_cleaning(entry, index, api)

        assert plan["year_corrected"] == ("2019", "2007")

    @pytest.mark.parametrize("value,expected", [
        ("2007.", "2007."),      # `0+`: a bare trailing dot is NOT an integral year
        (-0.0, "0"),             # signed zero normalizes
        ("-000", "0"),
        ("-2007", "-2007"),
    ])
    def test_grammar_edges(self, value, expected):
        assert _year_key(value) == expected


class TestYearlessScopedRecordCannotSettleAConflict:
    """A scoped record with no usable year supplies no evidence about which
    of two disagreeing broad years is right, so it must not suppress the
    pooled-conflict abstention."""

    def _index(self, tmp_path, scoped_year=None):
        scoped = {"title": "T", "doi": "10.1/y"}
        if scoped_year is not None:
            scoped["year"] = scoped_year
        return build_metadata_index(make_json_dir(tmp_path, {
            "s2_a.json": {"source": "semantic_scholar",
                          "results": [{"title": "T", "year": 2007, "doi": "10.1/y"}]},
            "s2_b.json": {"source": "semantic_scholar",
                          "results": [{"title": "T", "year": 2019, "doi": "10.1/y"}]},
            "verify_1.json": {"source": "crossref", "results": [scoped]},
        }))

    def _entry(self):
        from pybtex.database import parse_string
        return parse_string(
            "@article{y,author={A, B},title={T},year={2007},doi={10.1/y}}",
            "bibtex").entries["y"]

    def test_yearless_scoped_record_falls_through_to_abstention(self, tmp_path):
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry

        out = find_api_entry_for_bib_entry(self._entry(), self._index(tmp_path))

        assert isinstance(out, CleaningAbstention)
        assert out.reason == "pooled_year_conflict"

    def test_whitespace_scoped_year_counts_as_yearless(self, tmp_path):
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry

        assert isinstance(
            find_api_entry_for_bib_entry(
                self._entry(), self._index(tmp_path, scoped_year="  ")),
            CleaningAbstention)

    def test_a_scoped_year_does_settle_the_conflict(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry

        api = find_api_entry_for_bib_entry(
            self._entry(), self._index(tmp_path, scoped_year=2007))

        assert api is not None
        assert api["year"] == 2007


class TestScopedPreferenceDoesNotIncreaseDestruction:
    def test_year_bearing_swap_never_picks_a_less_complete_record(self, tmp_path):
        """The selected record governs verification of EVERY field. Swapping
        to a sparse record just because it carries a year would let the
        cleaner delete journal/volume/pages the first record verified."""
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_1.json": {"source": "crossref", "results": [{
                "title": "T", "doi": "10.1/z",
                "container_title": "Mind", "volume": "120", "page": "1-20",
            }]},
            "verify_9.json": {"source": "crossref", "results": [{
                "title": "T", "doi": "10.1/z", "year": 2011,
            }]},
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(
            "@article{z,author={A, B},title={T},year={2011},"
            "journal={Mind},volume={120},doi={10.1/z}}", "bibtex").entries["z"]

        api = find_api_entry_for_bib_entry(entry, index)

        assert api is not None
        assert api["container_title"] == "Mind"   # kept the complete record


class TestWriteGateMatchesTheGrammar:
    """Review round 3 (gpt-5.6-sol): the write gate used
    `api_year.lstrip("-").isdigit()`, a DIFFERENT language from
    _INTEGRAL_YEAR_RE - it re-admitted exactly what the grammar rejects."""

    @pytest.mark.parametrize("bad_year", [
        "٢٠٠٧",   # Arabic-Indic digits: isdigit() is True
        "²⁰⁰⁷",   # superscript digits: isdigit() is True
        "--2007",                     # lstrip("-") removes BOTH signs
        "-2007",                      # negative: not a publication year
        "1" * 40,                     # absurd magnitude
        "0",                          # year zero is not a publication year
    ])
    def test_ungrammatical_years_are_never_written(self, tmp_path, bad_year):
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        index = build_metadata_index(tmp_path / "nonexistent")
        entry = parse_string(
            "@article{x,author={A, B},title={T},year={2007},doi={10.1/x}}",
            "bibtex").entries["x"]
        api = {"year": bad_year, "entry_scoped": True,
               "year_basis": "published-print", "doi": "10.1/x"}

        assert plan_entry_cleaning(entry, index, api)["year_corrected"] is None

    @pytest.mark.parametrize("good_year", [2007, "2007", 2007.0, "0002007", 1650])
    def test_plausible_years_are_still_written(self, tmp_path, good_year):
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        index = build_metadata_index(tmp_path / "nonexistent")
        entry = parse_string(
            "@article{x,author={A, B},title={T},year={1999},doi={10.1/x}}",
            "bibtex").entries["x"]
        api = {"year": good_year, "entry_scoped": True,
               "year_basis": "published-print", "doi": "10.1/x"}

        plan = plan_entry_cleaning(entry, index, api)

        assert plan["year_corrected"] == ("1999", _year_key(good_year))


class TestNumericZeroIsNotTreatedAsAbsent:
    """`record.get("year") or ""` made numeric 0 yearless while "0" was
    year-bearing - the exact int/str split _year_key exists to erase."""

    def test_scoped_years_zero_and_2007_are_a_disagreement(self, tmp_path):
        from metadata_cleaner import CleaningAbstention, find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_1.json": {"source": "crossref",
                              "results": [{"title": "T", "doi": "10.1/z", "year": 0}]},
            "verify_9.json": {"source": "crossref",
                              "results": [{"title": "T", "doi": "10.1/z", "year": 2007}]},
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(
            "@article{z,author={A, B},title={T},year={2007},doi={10.1/z}}",
            "bibtex").entries["z"]

        out = find_api_entry_for_bib_entry(entry, index)

        assert isinstance(out, CleaningAbstention)
        assert out.reason == "scoped_year_disagreement"

    def test_authority_does_not_depend_on_int_vs_str_encoding(self, tmp_path):
        """A scoped year of 0 and of "0" must behave identically."""
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        def outcome(year_value):
            sub = tmp_path / repr(year_value).replace("'", "s")
            sub.mkdir()
            json_dir = make_json_dir(sub, {
                "s2_a.json": {"source": "semantic_scholar",
                              "results": [{"title": "T", "year": 2007, "doi": "10.1/w"}]},
                "s2_b.json": {"source": "semantic_scholar",
                              "results": [{"title": "T", "year": 2019, "doi": "10.1/w"}]},
                "verify_1.json": {"source": "crossref",
                                  "results": [{"title": "T", "doi": "10.1/w",
                                               "year": year_value}]},
            })
            entry = parse_string(
                "@article{w,author={A, B},title={T},year={2007},doi={10.1/w}}",
                "bibtex").entries["w"]
            r = find_api_entry_for_bib_entry(
                entry, build_metadata_index(json_dir))
            # Discriminate all three contract outcomes (dict / abstention /
            # None), not just None-ness - int 0 and "0" must land on the
            # SAME one.
            return (type(r).__name__, getattr(r, "reason", None))

        assert outcome(0) == outcome("0")


class TestScopedSwapPreservesVerificationPower:
    """Counting fields is not enough: an equally-sized but DISJOINT record
    cannot verify what the first one could, so the swap deleted data."""

    def test_equal_count_disjoint_record_does_not_win(self, tmp_path):
        from metadata_cleaner import find_api_entry_for_bib_entry
        from pybtex.database import parse_string

        json_dir = make_json_dir(tmp_path, {
            "verify_1.json": {"source": "crossref", "results": [{
                "title": "T", "doi": "10.1/q",
                "container_title": "Mind", "volume": "120",
            }]},
            "verify_9.json": {"source": "crossref", "results": [{
                "title": "T", "doi": "10.1/q", "year": 2011,
                "issue": "3", "publisher": "OUP",
            }]},
        })
        index = build_metadata_index(json_dir)
        entry = parse_string(
            "@article{q,author={A, B},title={T},year={2011},"
            "journal={Mind},volume={120},doi={10.1/q}}", "bibtex").entries["q"]

        api = find_api_entry_for_bib_entry(entry, index)

        assert api is not None
        assert api["container_title"] == "Mind"

    def test_whitespace_fields_do_not_count_as_supplied(self, tmp_path):
        from metadata_cleaner import _record_completeness

        assert _record_completeness({"publisher": " ", "issue": " "}) == 0


class TestYearBasisGate:
    """The second licence for a year overwrite: the record must say WHICH
    CrossRef date field its year came from, and it must be a version-of-record
    field.

    verify_paper.py used to read CrossRef's `published` first, which is the
    EARLIEST of published-print and published-online. Over the 43 local
    corpora, 27 of 42 year rewrites therefore replaced a year that exactly
    matched `published-print` with the online-first year (Mind 130(517): print
    2021, online 2019). Those records are still on disk in delivered reviews
    and nothing in them separates the good years from the bad, so a record with
    no `year_basis` may not overwrite - it is refused, and counted.
    """

    BIB = """@article{pinder2019conceptual,
  author = {Pinder, Mark},
  title = {Conceptual Engineering},
  journal = {Mind},
  year = {2021},
  volume = {130},
  number = {517},
  doi = {10.1093/mind/fzz069}
}"""

    def _run(self, tmp_path, record):
        payload = {"status": "success", "source": "crossref", "results": [record]}
        json_dir = make_json_dir(tmp_path, {"verify_pinder.json": payload})
        bib = tmp_path / "lit.bib"
        bib.write_text(self.BIB, encoding="utf-8")
        return clean_bibtex(bib, json_dir), bib

    # Everything except the year matches the bib, so the only thing under test
    # is the year gate - no unrelated field stripping muddies the assertions.
    ONLINE_FIRST = {
        "title": "Conceptual Engineering",
        "container_title": "Mind",
        "volume": "130",
        "issue": "517",
        "year": 2019,
        "doi": "10.1093/mind/fzz069",
    }

    def test_legacy_record_without_a_basis_cannot_overwrite(self, tmp_path):
        result, bib = self._run(tmp_path, self.ONLINE_FIRST)

        assert result["years_corrected"] == 0
        assert "2021" in bib.read_text(encoding="utf-8")
        assert_no_cleaned_marker(bib.read_text(encoding="utf-8"))

    def test_the_refusal_is_countable_and_warned(self, tmp_path):
        result, _ = self._run(tmp_path, self.ONLINE_FIRST)

        assert result["years_declined"] == [
            ["2021", "2019", "verify_pinder.json", "no-version-of-record-date"]]
        assert any("online-first" in w for w in result["warnings"])

    def test_registration_timestamp_cannot_overwrite(self, tmp_path):
        """`created` is when CrossRef was told about the work."""
        record = dict(self.ONLINE_FIRST, year_basis="created")

        result, bib = self._run(tmp_path, record)

        assert result["years_corrected"] == 0
        assert "2021" in bib.read_text(encoding="utf-8")

    def test_print_year_still_corrects(self, tmp_path):
        """The gate must not be vacuous: a properly-provenanced record from the
        fixed producer still fixes a genuinely wrong bib year."""
        record = dict(self.ONLINE_FIRST, year=2021, year_basis="published-print")
        bib_wrong_year = self.BIB.replace("year = {2021}", "year = {2019}")
        payload = {"status": "success", "source": "crossref", "results": [record]}
        json_dir = make_json_dir(tmp_path, {"verify_pinder.json": payload})
        bib = tmp_path / "lit.bib"
        bib.write_text(bib_wrong_year, encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 1
        assert result["years_declined"] == []
        assert "2021" in bib.read_text(encoding="utf-8")

    def test_online_only_journal_still_corrects(self, tmp_path):
        """No print edition: `published` IS the citation year."""
        record = dict(self.ONLINE_FIRST, year=2020, year_basis="published")
        payload = {"status": "success", "source": "crossref", "results": [record]}
        json_dir = make_json_dir(tmp_path, {"verify_pinder.json": payload})
        bib = tmp_path / "lit.bib"
        bib.write_text(self.BIB, encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 1

    def test_unscoped_and_undated_declines_report_different_reasons(self, tmp_path):
        """The two licences fail for different causes and want different fixes
        (re-verify the entry vs. re-run under the fixed producer), so the
        reason travels with the refusal."""
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        index = build_metadata_index(tmp_path / "nonexistent")
        entry = parse_string(
            "@article{x,author={A, B},title={T},year={2021},doi={10.1/x}}",
            "bibtex").entries["x"]

        unscoped = plan_entry_cleaning(entry, index, {
            "year": 2019, "year_basis": "published-print", "doi": "10.1/x",
            "entry_scoped": False, "source_file": "s2_dump.json"})
        undated = plan_entry_cleaning(entry, index, {
            "year": 2019, "doi": "10.1/x",
            "entry_scoped": True, "source_file": "verify_x.json"})

        assert unscoped["year_correction_declined"][3] == "unscoped"
        assert undated["year_correction_declined"][3] == "no-version-of-record-date"

    def test_a_missing_year_is_still_filled(self, tmp_path):
        """The gate protects POPULATED years. An entry with no year at all
        loses nothing, so this path is unchanged."""
        from metadata_cleaner import plan_entry_cleaning
        from pybtex.database import parse_string

        index = build_metadata_index(tmp_path / "nonexistent")
        entry = parse_string(
            "@article{x,author={A, B},title={T},doi={10.1/x}}",
            "bibtex").entries["x"]

        plan = plan_entry_cleaning(entry, index, {
            "year": 2019, "doi": "10.1/x", "entry_scoped": True})

        assert plan["year_corrected"] is None
        assert plan["year_correction_declined"] is None


class TestIndexStarvedFlag:
    """A starved index and a clean bill of health used to be distinguishable
    only by free-text warnings. External review finding E."""

    def test_flag_set_when_no_file_yields_a_record(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "final_selection.json": ["not", "an", "envelope"],
            "verify_missing.json": {"status": "error", "source": "crossref",
                                    "results": []},
        })
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["index_starved"] is True
        assert result["success"] is True
        assert result["entries_total"] == 1
        assert result["unmatched_entries"] == 1

    def test_flag_clear_on_an_ordinary_run(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {"verify_sparrow.json": VERIFY_RESULT})
        bib = tmp_path / "lit.bib"
        bib.write_text(SPARROW_BIB_CORRECT, encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["index_starved"] is False


# --- Item 5 B: the reprint-edition direction bound ------------------------

RAWLS_DOI = "10.2307/j.ctv1pncngc"


def _verify_book_record(year, suggested_bibtex_type="book",
                        crossref_type="monograph"):
    """Entry-scoped CrossRef verify record for a book, verify_paper.py shape.

    The live failure: JSTOR registered this DOI against the 2001 paperback of
    The Law of Peoples (Harvard UP 1999), so CrossRef's published-print is
    genuinely 2001 for the DOI while being the wrong citation year for the
    work - every component behaved as designed and a canonical book was
    misdated, which then manufactured a spurious Chicago a/b collision with
    Justice as Fairness (2001)."""
    return {
        "status": "success",
        "source": "crossref",
        "results": [{
            "title": "The Law of Peoples",
            "year": year,
            "year_basis": "published-print",
            "doi": RAWLS_DOI,
            "publisher": "Harvard University Press",
            "type": crossref_type,
            "suggested_bibtex_type": suggested_bibtex_type,
        }],
    }


def _rawls_bib(year):
    return f"""@book{{rawls1999lawofpeoples,
  author = {{Rawls, John}},
  title = {{The Law of Peoples}},
  publisher = {{Harvard University Press}},
  year = {{{year}}},
  doi = {{{RAWLS_DOI}}}
}}"""


class TestBookYearDirectionBound:
    """A book's year must never be moved LATER by a CrossRef record: a
    reprint edition gets its own DOI whose print year postdates the work's
    real publication year, and a reprint can only move a year forward."""

    def test_reprint_print_year_does_not_move_book_year_later(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "verify_1_rawls1999lop.json": _verify_book_record(2001),
        })
        bib = tmp_path / "test.bib"
        bib.write_text(_rawls_bib(1999), encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 0
        content = bib.read_text(encoding="utf-8")
        assert "1999" in content
        assert_no_cleaned_marker(content)

    def test_book_decline_is_recorded_with_its_own_reason(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "verify_1_rawls1999lop.json": _verify_book_record(2001),
        })
        bib = tmp_path / "test.bib"
        bib.write_text(_rawls_bib(1999), encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert len(result["years_declined"]) == 1
        declined = result["years_declined"][0]
        assert declined[0] == "1999"
        assert declined[1] == "2001"
        assert declined[3] == "book-year-moved-later"
        assert any("book" in w for w in result["warnings"])

    def test_book_year_still_corrects_toward_earlier(self, tmp_path):
        """The bound is a DIRECTION bound, not a book-year freeze: a bib
        wrongly carrying the reprint year is still corrected back to the
        earlier (original-edition) print year."""
        json_dir = make_json_dir(tmp_path, {
            "verify_1_rawls1999lop.json": _verify_book_record(1999),
        })
        bib = tmp_path / "test.bib"
        bib.write_text(_rawls_bib(2001), encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 1
        content = bib.read_text(encoding="utf-8")
        assert re.search(r"year\s*=\s*[{\"]1999", content)
        assert "year:2001" in content  # marker records the old value

    def test_article_record_may_still_move_a_year_later(self, tmp_path):
        """The bound covers only the reprint-capable book class. For
        articles the later print year IS the citation year (the online-first
        class item 3 K, cleaner/year hardening, fixed), so an @article entry
        with an article-typed record must still correct 2011 -> 2012.
        Bookness on EITHER side (record type or bib entry type) triggers the
        bound, so this test keeps both sides article-typed."""
        record = _verify_book_record(2012, suggested_bibtex_type="article",
                                     crossref_type="journal-article")
        json_dir = make_json_dir(tmp_path, {
            "verify_1_wiens.json": record,
        })
        bib = tmp_path / "test.bib"
        bib.write_text(f"""@article{{wiens2011prescribing,
  author = {{Wiens, David}},
  title = {{Prescribing Institutions Without Ideal Theory}},
  journal = {{Journal of Political Philosophy}},
  year = {{2011}},
  doi = {{{RAWLS_DOI}}}
}}""", encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 1
        content = bib.read_text(encoding="utf-8")
        assert re.search(r"year\s*=\s*[{\"]2012", content)

    def test_nonintegral_book_year_fails_closed(self, tmp_path):
        """With a bib year the direction test cannot parse ("n.d."), the
        guard cannot prove the move is not later, so for books it declines
        (counted, never silent) rather than writing - under its own reason,
        since the remediation (fix the malformed year) differs from the
        moved-later case's (check for a reprint DOI)."""
        json_dir = make_json_dir(tmp_path, {
            "verify_1_rawls1999lop.json": _verify_book_record(2001),
        })
        bib = tmp_path / "test.bib"
        bib.write_text(_rawls_bib("n.d."), encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 0
        assert len(result["years_declined"]) == 1
        assert result["years_declined"][0][3] == "book-year-direction-unknown"
        content = bib.read_text(encoding="utf-8")
        assert "n.d." in content


class TestDirectionBoundCoverage:
    """Review findings on item 5 B, the reprint-edition direction bound:
    bookness keyed on suggested_bibtex_type == "book" exactly missed (a) the
    chapter class - a per-chapter DOI of the same reprint edition maps to
    "incollection" and the researcher agent explicitly instructs
    @incollection entries with chapter DOIs, and (b) records written before
    verify_paper.py emitted the field at all (pre-2026-02-09 workspaces),
    where the bib entry's own @book type is the only bookness evidence."""

    def test_chapter_record_of_reprint_does_not_move_year_later(self, tmp_path):
        record = _verify_book_record(2001, suggested_bibtex_type="incollection",
                                     crossref_type="book-chapter")
        json_dir = make_json_dir(tmp_path, {
            "verify_1_rawlschapter.json": record,
        })
        bib = tmp_path / "test.bib"
        bib.write_text(f"""@incollection{{rawls1999chapter,
  author = {{Rawls, John}},
  title = {{Section 58}},
  booktitle = {{The Law of Peoples}},
  year = {{1999}},
  doi = {{{RAWLS_DOI}}}
}}""", encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 0
        assert result["years_declined"][0][3] == "book-year-moved-later"

    def test_book_bib_entry_is_bookness_evidence_when_record_lacks_the_field(
            self, tmp_path):
        """A verify record written before the producer emitted
        suggested_bibtex_type must not reopen the Rawls rewrite when the bib
        entry itself says @book."""
        record = _verify_book_record(2001)
        del record["results"][0]["suggested_bibtex_type"]
        del record["results"][0]["type"]
        json_dir = make_json_dir(tmp_path, {
            "verify_1_rawls1999lop.json": record,
        })
        bib = tmp_path / "test.bib"
        bib.write_text(_rawls_bib(1999), encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 0
        assert result["years_declined"][0][3] == "book-year-moved-later"

    def test_article_bib_entry_with_fieldless_record_still_corrects(self, tmp_path):
        """The entry-type fallback must not over-block: an @article whose
        record lacks the field keeps the pre-bound behavior (year may move
        later - the online-first class)."""
        record = _verify_book_record(2012)
        del record["results"][0]["suggested_bibtex_type"]
        del record["results"][0]["type"]
        json_dir = make_json_dir(tmp_path, {
            "verify_1_wiens.json": record,
        })
        bib = tmp_path / "test.bib"
        bib.write_text(f"""@article{{wiens2011,
  author = {{Wiens, David}},
  title = {{Prescribing Institutions Without Ideal Theory}},
  journal = {{Journal of Political Philosophy}},
  year = {{2011}},
  doi = {{{RAWLS_DOI}}}
}}""", encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 1


class TestDeclineReasonReporting:
    """Review findings: the unparseable-year branch reused the moved-later
    reason (sending the operator hunting reprint DOIs when the remediation
    is fixing a malformed year), and the summary derived one bucket by
    subtraction (a future reason would be silently misreported)."""

    def test_unparseable_book_year_gets_its_own_reason(self, tmp_path):
        json_dir = make_json_dir(tmp_path, {
            "verify_1_rawls1999lop.json": _verify_book_record(2001),
        })
        bib = tmp_path / "test.bib"
        bib.write_text(_rawls_bib("n.d."), encoding="utf-8")

        result = clean_bibtex(bib, json_dir)

        assert result["years_corrected"] == 0
        assert result["years_declined"][0][3] == "book-year-direction-unknown"
        assert any("could not be compared" in w for w in result["warnings"])
        assert not any("moved LATER" in w for w in result["warnings"])
