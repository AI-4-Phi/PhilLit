"""A6: METADATA_CLEANED markers are replaced (deduped), matching escaped forms."""
import re
import sys
from pathlib import Path

from pybtex.database import parse_file

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
FIXTURES = Path(__file__).parent / "fixtures" / "bib_quality"
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
    assert "METADATA_CLEANED: volume" in kw                # the fresh one FIRST
    # The stale marker's names are CARRIED FORWARD rather than erased: their
    # fields are still absent from the entry, so the removal record is still
    # true, and downstream consumers (bib_validator's @article exemption
    # among them) read it. Each name appears exactly once.
    assert mc.marker_removed_fields(kw) == frozenset({"volume", "number", "pages"})
    assert kw.count("number") == 1 and kw.count("pages") == 1


def test_carry_forward_drops_a_readded_field():
    """A prior removal whose field the researcher re-added (and this run
    verified) is NOT carried: the record would be false."""
    from pybtex.database import parse_string
    e = parse_string('@article{k, author="A,B", title="T", volume="4",\n'
                     '  keywords="High, METADATA_CLEANED: volume, pages"}\n',
                     "bibtex").entries["k"]
    plan = {"removed_field_names": ["doi"], "removed_fields": ["doi=x"],
            "year_corrected": None, "type_downgraded": None}
    mc._apply_cleaned_marker(e, plan)
    assert mc.marker_removed_fields(e.fields["keywords"]) == \
        frozenset({"doi", "pages"})


def test_carry_forward_checks_persons_not_just_fields():
    """author/editor live in entry.persons, not entry.fields - pybtex never
    puts them in .fields even when the source .bib spells them as a plain
    field. A marker naming `author` on an entry that HAS an author must not
    carry that name forward: checking entry.fields alone would miss the
    author's real location and re-carry a removal that is no longer true."""
    from pybtex.database import parse_string
    e = parse_string('@article{k, author="A, B", title="T",\n'
                     '  keywords="High, METADATA_CLEANED: author, pages"}\n',
                     "bibtex").entries["k"]
    assert "author" not in e.fields and "author" in e.persons  # precondition
    plan = {"removed_field_names": ["doi"], "removed_fields": ["doi=x"],
            "year_corrected": None, "type_downgraded": None}
    mc._apply_cleaned_marker(e, plan)
    assert mc.marker_removed_fields(e.fields["keywords"]) == \
        frozenset({"doi", "pages"})


def test_readded_field_survives_until_the_next_rewrite():
    """A re-added field is dropped from the marker only WHEN the marker is
    rewritten. A run with no changes of its own hits the early return and
    rewrites nothing, so a stale name for a field the researcher already
    re-added survives until the next rewrite - the validator's documented
    stale-record residual, not a bug in the carry-forward logic itself."""
    from pybtex.database import parse_string
    original = 'High, METADATA_CLEANED: journal'
    e = parse_string(
        '@article{k, author="A,B", title="T", journal="Real Journal",\n'
        '  keywords="%s"}\n' % original, "bibtex").entries["k"]
    plan = {"removed_field_names": [], "removed_fields": [],
            "year_corrected": None, "type_downgraded": None}
    mc._apply_cleaned_marker(e, plan)
    assert e.fields["keywords"] == original
    assert "journal" in mc.marker_removed_fields(e.fields["keywords"])


def test_carry_forward_keeps_a_prior_type_change():
    """The cleaner's own REQUIRED_FIELDS has no 'misc' entry, so a demoted
    entry re-entering the cleaner can never re-derive its own demotion. The
    prior `type:` token is carried verbatim or the record is lost."""
    from pybtex.database import parse_string
    e = parse_string(
        '@misc{k, author="A,B", title="T",\n'
        '  keywords="Medium, METADATA_CLEANED: booktitle, '
        'type:@incollection->@misc"}\n', "bibtex").entries["k"]
    plan = {"removed_field_names": [], "removed_fields": [],
            "year_corrected": ("2019", "2020"), "type_downgraded": None}
    mc._apply_cleaned_marker(e, plan)
    kw = e.fields["keywords"]
    assert "type:@incollection->@misc" in kw
    assert "year:2019->2020" in kw
    assert mc.marker_removed_fields(kw) == frozenset({"booktitle"})


def test_this_runs_type_change_is_not_duplicated():
    """When this run records its own demotion, the prior token is dropped -
    the fresh one supersedes it."""
    from pybtex.database import parse_string
    e = parse_string('@article{k, author="A,B", title="T",\n'
                     '  keywords="METADATA_CLEANED: type:@a->@misc"}\n',
                     "bibtex").entries["k"]
    plan = {"removed_field_names": [], "removed_fields": [],
            "year_corrected": None, "type_downgraded": ("incollection", "misc")}
    mc._apply_cleaned_marker(e, plan)
    kw = e.fields["keywords"]
    assert kw == "METADATA_CLEANED: type:@incollection->@misc"


def test_untouched_entry_keeps_its_marker_verbatim():
    """The early return stands: a run that changed nothing must not rewrite
    (or carry-forward-reorder) a marker it has no business touching."""
    from pybtex.database import parse_string
    original = "High, METADATA_CLEANED: journal, type:@article->@misc"
    e = parse_string('@misc{k, author="A,B", title="T", keywords="%s"}\n'
                     % original, "bibtex").entries["k"]
    plan = {"removed_field_names": [], "removed_fields": [],
            "year_corrected": None, "type_downgraded": None}
    mc._apply_cleaned_marker(e, plan)
    assert e.fields["keywords"] == original


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
