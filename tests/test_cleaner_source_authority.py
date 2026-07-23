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
