"""Item 13 A7: dedupe_bib third pass (title-axis) - pybtex-robust fallback key,
union-into-survivor, and DOI-group bridge guard."""

import sys
from pathlib import Path

from pybtex.database import parse_string

sys.path.insert(0, str(Path(__file__).parent.parent / "skills/literature-review/scripts"))

from dedupe_bib import dedupe_by_title_key, _fallback_key


def test_dedupe_by_title_key_merges_same_work_abstract_wins():
    # Same (title, year, first-author surname); no shared DOI; one has an
    # abstract. merge_entries() selects the abstract-bearing entry as winner,
    # then the survivor UNIONs in the loser's substantive fields (spec v2.1) -
    # here the loser-only journal.
    seen = {
        "doe2020a": (
            "@article{doe2020a,\n"
            "  author = {Doe, Jane},\n"
            "  title = {A Study of Minds},\n"
            "  year = {2020},\n"
            "  journal = {J Phil},\n"
            "}"
        ),
        "doe2020b": (
            "@article{doe2020b,\n"
            "  author = {Doe, Jane},\n"
            "  title = {A Study of Minds},\n"
            "  year = {2020},\n"
            "  abstract = {A sufficiently long abstract to count as present.},\n"
            "}"
        ),
    }
    removed = dedupe_by_title_key(seen)
    assert len(seen) == 1
    assert removed == ["doe2020a"]           # bare (no-abstract) entry dropped
    survivor = next(iter(seen.values()))
    assert "abstract" in survivor            # abstract-bearing winner survives
    assert "J Phil" in survivor              # loser-only journal unioned in (spec v2.1)


def test_dedupe_by_title_key_unions_loser_journal_and_doi():
    # The winner is chosen by merge_entries() for its abstract; it lacks
    # journal+doi. The loser carries journal+doi. After the pass the survivor
    # (abstract entry) UNIONs in the loser-only journal + doi (spec v2.1 /
    # ADV-A0). This is the "survivor retains a journal+DOI only the LOSER had"
    # assertion.
    seen = {
        "rich_meta": (
            "@article{rich_meta,\n"
            "  author = {Doe, Jane},\n"
            "  title = {A Study of Minds},\n"
            "  year = {2020},\n"
            "  journal = {Journal of Mind},\n"
            "  doi = {10.5/mind},\n"
            "}"
        ),
        "has_abstract": (
            "@article{has_abstract,\n"
            "  author = {Doe, Jane},\n"
            "  title = {A Study of Minds},\n"
            "  year = {2020},\n"
            "  abstract = {A sufficiently long abstract to count as present.},\n"
            "}"
        ),
    }
    removed = dedupe_by_title_key(seen)
    assert len(seen) == 1
    assert removed == ["rich_meta"]          # abstract entry wins
    survivor = seen["has_abstract"]
    assert "abstract" in survivor
    parsed = parse_string(survivor, "bibtex").entries["has_abstract"]
    assert parsed.fields["journal"] == "Journal of Mind"   # unioned from loser
    assert parsed.fields["doi"].lower() == "10.5/mind"      # unioned from loser


def test_dedupe_by_title_key_keeps_differing_dois():
    seen = {
        "smith2020pre": (
            "@article{smith2020pre,\n"
            "  author = {Smith, John},\n"
            "  title = {Minds},\n"
            "  year = {2020},\n"
            "  doi = {10.1/pre},\n"
            "}"
        ),
        "smith2020pub": (
            "@article{smith2020pub,\n"
            "  author = {Smith, John},\n"
            "  title = {Minds},\n"
            "  year = {2020},\n"
            "  doi = {10.1/pub},\n"
            "}"
        ),
    }
    removed = dedupe_by_title_key(seen)
    assert removed == []
    assert len(seen) == 2


def test_dedupe_by_title_key_doi_bridge_not_over_merged():
    # A(doi=X, title=T), B(no doi, title=T), C(doi=Y, title=T). A+B may merge
    # (B has no DOI); the resulting AB group (dois={X}) must NOT bridge to C
    # (dois={Y}) via the shared title. Final output: 2 entries.
    seen = {
        "a_pre": (
            "@article{a_pre,\n"
            "  author = {Vale, Uma},\n"
            "  title = {Bridging Work},\n"
            "  year = {2023},\n"
            "  doi = {10.1/x},\n"
            "}"
        ),
        "b_mid": (
            "@article{b_mid,\n"
            "  author = {Vale, Uma},\n"
            "  title = {Bridging Work},\n"
            "  year = {2023},\n"
            "}"
        ),
        "c_pub": (
            "@article{c_pub,\n"
            "  author = {Vale, Uma},\n"
            "  title = {Bridging Work},\n"
            "  year = {2023},\n"
            "  doi = {10.1/y},\n"
            "}"
        ),
    }
    removed = dedupe_by_title_key(seen)
    assert len(seen) == 2
    assert "b_mid" in removed          # folded into the A group (no DOI of its own)
    assert "c_pub" not in removed      # distinct DOI => never bridged
    assert "a_pre" in seen and "c_pub" in seen


def test_dedupe_by_title_key_ignores_entries_without_key():
    # No year => no fallback key => never title-deduped, even if titles match.
    seen = {
        "a": "@misc{a,\n  author = {Doe, Jane},\n  title = {Same},\n}",
        "b": "@misc{b,\n  author = {Doe, Jane},\n  title = {Same},\n}",
    }
    removed = dedupe_by_title_key(seen)
    assert removed == []
    assert len(seen) == 2


def test_fallback_key_handles_quoted_and_nested_brace_values():
    # Quoted values (title/author/year = "...") and a nested-brace title
    # ({The {AI} Problem}) must all parse - the regex extractors in this
    # file cannot, so _fallback_key parses with pybtex.
    quoted = (
        '@article{q,\n'
        '  author = "Doe, Jane",\n'
        '  title = "A Study of Minds",\n'
        '  year = "2020",\n'
        '}'
    )
    nested = (
        "@article{n,\n"
        "  author = {Doe, Jane},\n"
        "  title = {The {AI} Problem},\n"
        "  year = {2020},\n"
        "}"
    )
    assert _fallback_key(quoted) == ("a study of minds", "2020", "doe")
    assert _fallback_key(nested) == ("the ai problem", "2020", "doe")


def test_fallback_key_none_when_title_missing():
    e = "@article{x,\n  author = {Doe, Jane},\n  year = {2020},\n}"
    assert _fallback_key(e) is None


def test_fallback_key_none_when_year_missing():
    e = "@article{x,\n  author = {Doe, Jane},\n  title = {Minds},\n}"
    assert _fallback_key(e) is None


def test_fallback_key_none_when_author_missing():
    e = "@article{x,\n  title = {Minds},\n  year = {2020},\n}"
    assert _fallback_key(e) is None
