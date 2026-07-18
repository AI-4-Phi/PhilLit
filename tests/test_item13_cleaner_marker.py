"""A6: METADATA_CLEANED markers are replaced (deduped), matching escaped forms."""
import re
import sys
from pathlib import Path

from pybtex.database import parse_file

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
FIXTURES = Path(__file__).parent / "fixtures" / "item13"
sys.path.insert(0, str(HOOKS_DIR))

import metadata_cleaner as mc  # noqa: E402

# matches the in-memory marker in any escape state (0/1/2+ backslashes)
_COUNT_RE = re.compile(r"METADATA\\*_CLEANED")


def test_marker_replaced_not_appended_on_double_marker(tmp_path):
    # robbins fixture carries TWO concatenated markers (double + single escaped)
    data = parse_file(str(FIXTURES / "robbins2023many.bib"), bib_format="bibtex")
    entry = data.entries["robbins2023many"]
    assert len(_COUNT_RE.findall(entry.fields["keywords"])) == 2  # precondition
    plan = {"removed_field_names": ["volume"], "removed_fields": ["volume=4"],
            "year_corrected": None, "type_downgraded": None}
    mc._apply_cleaned_marker(entry, plan)
    kw = entry.fields["keywords"]
    assert len(_COUNT_RE.findall(kw)) == 1                 # deduped to ONE
    assert kw.startswith("meaningful-human-control, conceptual-analysis, critique, High")
    assert "METADATA_CLEANED: volume" in kw                # the fresh one
    # the stale marker contents are gone
    assert "number, pages" not in kw and ": doi" not in kw


def test_marker_fresh_when_no_prior(tmp_path):
    from pybtex.database import parse_string
    e = parse_string('@article{k, author="A,B", title="T", keywords="alpha, beta"}\n',
                     "bibtex").entries["k"]
    plan = {"removed_field_names": ["doi"], "removed_fields": ["doi=x"],
            "year_corrected": None, "type_downgraded": None}
    mc._apply_cleaned_marker(e, plan)
    assert e.fields["keywords"] == "alpha, beta, METADATA_CLEANED: doi"


def test_marker_created_when_no_keywords():
    from pybtex.database import parse_string
    e = parse_string('@article{k, author="A,B", title="T"}\n', "bibtex").entries["k"]
    plan = {"removed_field_names": ["journal"], "removed_fields": ["journal=x"],
            "year_corrected": None, "type_downgraded": None}
    mc._apply_cleaned_marker(e, plan)
    assert e.fields["keywords"] == "METADATA_CLEANED: journal"
