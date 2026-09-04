"""Tests for hooks/cleaning_marker.py - the METADATA_CLEANED marker grammar.

The grammar lives in its own leaf module because bib_validator must read
markers (to exempt an @article the cleaner deliberately left without a
journal) and bib_identity already imports bib_validator - so the cleaner,
which imports bib_identity, can never be imported from there.
"""

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
SCRIPT_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

import cleaning_marker  # noqa: E402
from cleaning_marker import (  # noqa: E402
    has_marker,
    marker_removed_fields,
    marker_type_changed,
)


class TestMarkerRemovedFields:
    """Field names the marker records as REMOVED, in every spelling pybtex
    can round-trip the underscore into."""

    @pytest.mark.parametrize("keywords,expected", [
        # Plain (in-memory) spelling
        ("High, METADATA_CLEANED: journal", {"journal"}),
        # pybtex Writer escapes '_' on the first round-trip ...
        (r"High, METADATA\_CLEANED: journal", {"journal"}),
        # ... and again on the second
        (r"High, METADATA\\_CLEANED: journal", {"journal"}),
        # Change tokens carry ':' and are not removals, either side of the name
        ("METADATA_CLEANED: journal, year:2007->2019", {"journal"}),
        ("METADATA_CLEANED: year:2007->2019, journal", {"journal"}),
        # Several names
        ("METADATA_CLEANED: booktitle, pages", {"booktitle", "pages"}),
    ])
    def test_names(self, keywords, expected):
        assert marker_removed_fields(keywords) == frozenset(expected)

    @pytest.mark.parametrize("keywords", ["", None, "High, INCOMPLETE, ai-ethics"])
    def test_no_marker_is_empty(self, keywords):
        assert marker_removed_fields(keywords) == frozenset()


class TestMarkerTypeChanged:
    """A `type:` change token means the cleaner DEMOTED the entry."""

    def test_true_for_type_token(self):
        assert marker_type_changed(
            "METADATA_CLEANED: journal, type:@article->@misc") is True

    def test_false_for_other_change_tokens(self):
        assert marker_type_changed(
            "METADATA_CLEANED: journal, year:2007->2019") is False

    def test_false_without_a_marker(self):
        assert marker_type_changed("High, INCOMPLETE") is False


class TestHasMarker:
    @pytest.mark.parametrize("keywords", [
        "High, METADATA_CLEANED: journal",
        r"High, METADATA\_CLEANED: journal",
        r"High, METADATA\\_CLEANED: journal",
    ])
    def test_true_for_every_spelling(self, keywords):
        assert has_marker(keywords) is True

    @pytest.mark.parametrize("keywords", ["", None, "High, INCOMPLETE, ai-ethics"])
    def test_false_without_a_marker(self, keywords):
        assert has_marker(keywords) is False

    def test_colonless_metadata_cleaned_is_not_a_marker(self):
        """The colon is part of the grammar: without a change list there is
        nothing to read back, and marker_removed_fields already returns
        nothing here. Pinned because the two substring heuristics has_marker
        replaced (dedupe_bib, generate_bibliography) DID accept this shape -
        see TestColonlessMarkerTakesTheCreateBranch."""
        assert has_marker("High, METADATA_CLEANED, ai-ethics") is False
        assert marker_removed_fields("High, METADATA_CLEANED, ai-ethics") \
            == frozenset()


class TestColonlessMarkerTakesTheCreateBranch:
    """Behaviour change from adopting has_marker: a bare `METADATA_CLEANED`
    with no colon (real - tests/test_engine_generate_bib.py carries one) used
    to satisfy both consumers' substring tests, so they appended bare names
    to the keywords tail and produced a marker marker_removed_fields could
    not read back. Both now CREATE a well-formed marker instead.

    The tighter grammar is intentional: a marker the parser cannot read is
    not a marker. The two parametrized cases beyond the colonless one are
    shapes the OLD substring heuristics also wrongly accepted: dedupe_bib's
    old check was `"METADATA" in current and "_CLEANED" in current` (accepts
    a stray space before the colon, since it never looks past "_CLEANED");
    generate_bibliography's old check was just `"_CLEANED" in kw` (accepts
    ANY `..._CLEANED:` prefix, not only `METADATA_CLEANED:`). has_marker
    refuses both."""

    @pytest.mark.parametrize("keywords", [
        "High, METADATA_CLEANED, ai-ethics",
        "High, FOO_CLEANED: x, ai-ethics",
        "High, METADATA_CLEANED : pages, ai-ethics",
    ])
    def test_dedupe_bib_creates_a_readable_marker(self, keywords):
        from dedupe_bib import _extract_keywords_value, _fold_removals_into_marker
        entry = ('@article{k,\n  author = {A, B},\n  title = {T},\n'
                 '  year = {2020},\n  keywords = {%s}\n}' % keywords)
        out = _fold_removals_into_marker(entry, {"pages"})
        assert marker_removed_fields(_extract_keywords_value(out)) == \
            frozenset({"pages"})

    @pytest.mark.parametrize("keywords", [
        "High, METADATA_CLEANED, ai-ethics",
        "High, FOO_CLEANED: x, ai-ethics",
        "High, METADATA_CLEANED : pages, ai-ethics",
    ])
    def test_generate_bibliography_creates_a_readable_marker(self, keywords):
        from pybtex.database import parse_string
        from generate_bibliography import _apply_cleaner_verdicts
        db = parse_string(
            '@article{w, author = {A, B}, title = {T}, year = {2020},\n'
            '  pages = {1--9}, keywords = {%s}}\n'
            '@article{l, author = {A, B}, title = {T}, year = {2020},\n'
            '  keywords = {METADATA_CLEANED: pages}}' % keywords, "bibtex")
        winner, loser = db.entries["w"], db.entries["l"]
        _apply_cleaner_verdicts(winner, loser)
        assert "pages" not in winner.fields
        assert marker_removed_fields(winner.fields["keywords"]) == \
            frozenset({"pages"})


class TestSharedOwnerIdentity:
    """Every consumer binds the SHARED object, never a local copy - a
    re-implementation is exactly how the marker grammar drifted apart
    across four sites before it had an owner."""

    def test_metadata_cleaner_reexports_the_owner(self):
        import metadata_cleaner
        assert (metadata_cleaner.marker_removed_fields
                is cleaning_marker.marker_removed_fields)
        assert metadata_cleaner.MARKER_STRIP_RE is cleaning_marker.MARKER_STRIP_RE
        assert metadata_cleaner.MARKER_BODY_RE is cleaning_marker.MARKER_BODY_RE

    def test_bib_validator_binds_the_owner(self):
        # Same idiom as tests/test_bib_validator.py: hooks/ is already on
        # sys.path (this module's own HOOKS_DIR insert, above), then a plain
        # import.
        import bib_validator
        assert (bib_validator.marker_removed_fields
                is cleaning_marker.marker_removed_fields)
        assert (bib_validator.marker_type_changed
                is cleaning_marker.marker_type_changed)

    def test_dedupe_bib_binds_the_owner(self):
        import dedupe_bib
        assert (dedupe_bib.marker_removed_fields
                is cleaning_marker.marker_removed_fields)
        assert dedupe_bib.has_marker is cleaning_marker.has_marker

    def test_generate_bibliography_binds_the_owner(self):
        import generate_bibliography
        assert (generate_bibliography.marker_removed_fields
                is cleaning_marker.marker_removed_fields)
        assert generate_bibliography.has_marker is cleaning_marker.has_marker
