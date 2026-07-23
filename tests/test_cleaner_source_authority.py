"""Tests for source-authority handling in metadata_cleaner.py.

Fix for docs/known-issues/metadata-cleaner-year-corruption.md: broad
keyword-search dumps (s2_*, openalex_*, ...) must never overwrite a
field value; only entry-scoped CrossRef verification files (verify_*)
carry correction authority. Same-DOI year disagreements across pooled
sources are surfaced as warnings.
"""

import json
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
)
# NOTE: Task 4 adds `find_doi_year_conflicts` to this import block when the
# helper exists. Do not import it earlier - the file must stay runnable at
# every task boundary.


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
        assert "METADATA_CLEANED" not in content

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
