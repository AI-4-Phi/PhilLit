"""Tests for check_evidence.py (Phase 6 telemetry) and sanitize_bib.py
(delivered-bib sanitizer)."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
CHECKER = SCRIPTS_DIR / "check_evidence.py"
SANITIZER = SCRIPTS_DIR / "sanitize_bib.py"

sys.path.insert(0, str(SCRIPTS_DIR))
import check_evidence  # noqa: E402

BIB = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  year = {1962},
  keywords = {ps, High, EVIDENCE-EXISTENCE}
}

@misc{blog2024,
  author = {Blogger, Bea},
  title = {A Post},
  year = {2024},
  keywords = {EVIDENCE-NONE}
}

@article{ok2020,
  author = {Fine, Frank},
  title = {Good Paper},
  year = {2020},
  keywords = {EVIDENCE-ABSTRACT}
}

@article{ghost2019,
  author = {Ghost, Gia},
  title = {Unstamped},
  year = {2019},
  keywords = {tag}
}"""

BIB_NO_AUTHOR = BIB + """

@article{noauthor2021,
  title = {No Author Here},
  year = {2021},
  keywords = {EVIDENCE-NONE}
}"""

BIB_LI = """@article{li2020lit,
  author = {Li, Wei},
  title = {A Paper},
  year = {2020},
  keywords = {tag}
}"""


def _run(tmp_path, md_text, bib_text=BIB):
    (tmp_path / "r.md").write_text(md_text, encoding="utf-8")
    (tmp_path / "b.bib").write_text(bib_text, encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECKER),
                           str(tmp_path / "r.md"), str(tmp_path / "b.bib")],
                          capture_output=True, text=True)


def test_reporting_verb_on_existence_flagged(tmp_path):
    r = _run(tmp_path, "Kuhn (1962) argues that paradigms shift.")
    assert "CHECK reporting-verb: kuhn1962structure" in r.stdout
    assert r.returncode == 0  # telemetry, not enforcement


def test_existence_coverage_claim_not_flagged(tmp_path):
    r = _run(tmp_path, "This has been studied historically (Kuhn 1962).")
    assert "reporting-verb" not in r.stdout


def test_none_cited_flagged(tmp_path):
    r = _run(tmp_path, "As noted online (Blogger 2024).")
    assert "CHECK none-cited: blog2024" in r.stdout


def test_abstract_tier_with_verb_ok(tmp_path):
    r = _run(tmp_path, "Fine (2020) argues convincingly.")
    assert "reporting-verb" not in r.stdout


def test_unstamped_cited_flagged(tmp_path):
    r = _run(tmp_path, "See Ghost (2019).")
    assert "CHECK unstamped-cited: ghost2019" in r.stdout


@pytest.mark.parametrize("verb_phrase", [
    # The four verbs whose absence caused real misses in the evidence-tier
    # A/B spot check (2026-07-28) -- regression guard for the widened list.
    "presses an anti-realist reading",
    "occupies a more qualified position",
    "developed a formal measure of informativeness",
    "identify what they call the creator's advantage",
    # Attribution verbs named as absent during the same adjudication.
    "contends that paradigms shift",
    "claims that paradigms shift",
    "maintains that paradigms shift",
    "traces the term's early modern history",
])
def test_widened_reporting_verbs_flagged(tmp_path, verb_phrase):
    r = _run(tmp_path, f"Kuhn (1962) {verb_phrase}.")
    assert "CHECK reporting-verb: kuhn1962structure" in r.stdout


def test_bare_plural_verb_form_flagged(tmp_path):
    # Multi-author citations take a plural subject; the pre-2026-07-28 list
    # carried only -s/-ed forms, so these were invisible.
    r = _run(tmp_path, "Kuhn and Smith (1962) argue that paradigms shift.")
    assert "CHECK reporting-verb: kuhn1962structure" in r.stdout


@pytest.mark.parametrize("sentence", [
    # Noun senses deliberately excluded from the verb list -- see the
    # _ATTRIBUTION_VERBS docstring. These must stay quiet.
    "The objects of inquiry were physical (Kuhn 1962).",
    "The challenges of the era were many (Kuhn 1962).",
    "This is a well-established view (Kuhn 1962).",
    "That assumption is widely held (Kuhn 1962).",
])
def test_noun_homograph_not_flagged(tmp_path, sentence):
    r = _run(tmp_path, sentence)
    assert "reporting-verb" not in r.stdout


def test_known_false_positive_documented(tmp_path):
    # verb belongs to a different clause in the same sentence -- accepted FP
    r = _run(tmp_path, "While Smith argues X, the field grew (Kuhn 1962).")
    assert "CHECK reporting-verb: kuhn1962structure" in r.stdout  # documented limitation


def test_summary_line_present(tmp_path):
    r = _run(tmp_path, "Kuhn (1962) argues that paradigms shift.")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert lines[-1].startswith("CHECK-SUMMARY: ")


def test_year_digit_run_across_window_boundary_not_flagged(tmp_path):
    """Regression: a digit run like "91962" must not be read as a bare 1962
    just because a pre-sliced 60-char window happens to cut off the leading
    "9". The window here is built so the OLD (buggy) implementation's slice
    boundary lands exactly at the "1" of "1962" -- one past the "9" -- making
    the sliced text look like a bare, unguarded year. The FIX must search
    the year regex over the full text first, so the leading "9" always
    disqualifies this run as a real 1962 occurrence.
    """
    prefix = "x" * 10
    digit_run = "91962"
    year_start_in_run = 1  # index of "1" within "91962" (right after the "9")
    year_pos = len(prefix) + year_start_in_run
    surname_start = year_pos + 60  # old code's window start lands on year_pos
    pad_len = surname_start - (len(prefix) + len(digit_run))
    assert pad_len >= 1
    md_text = prefix + digit_run + (" " * pad_len) + "Kuhn wrote a lot."
    r = _run(tmp_path, md_text)
    assert "kuhn1962structure" not in r.stdout


def test_no_author_entry_skipped(tmp_path):
    r = _run(tmp_path, "Some prose mentioning nobody in particular.",
             bib_text=BIB_NO_AUTHOR)
    assert r.returncode == 0
    assert "noauthor2021" not in r.stdout


def test_surname_does_not_match_inside_word(tmp_path):
    r = _run(tmp_path, "The literature (2020) on this topic is thin.",
             bib_text=BIB_LI)
    assert "li2020lit" not in r.stdout


def test_find_cites_honours_the_entry_suffix():
    md = "Menary (2010a) argues X. Menary (2010b) argues Y."
    a = check_evidence.find_cites(md, "Menary", "2010", suffix="a")
    b = check_evidence.find_cites(md, "Menary", "2010", suffix="b")
    assert len(a) == 1 and len(b) == 1 and a != b


def test_find_cites_without_suffix_is_unchanged():
    """The 3-arg call and the explicit `suffix=""` call must agree on every
    input, i.e. an empty suffix really does route to the historic arm and
    never into the year-anchored one. The old length-1 assertion pinned only
    the arity and passed with the suffix work reverted."""
    fixtures = [
        "Menary (2010) argues X.",
        "Menary (2010a) argues X. Menary (2010b) argues Y.",
        "Menary (2010a; 2010b) both argue X.",
        "In the 2010s, Menary (2010a) argues X.",
        "This is contested (Menary 2010a; Menary 2010b).",
        "Nothing about Menary here at all.",
    ]
    for md in fixtures:
        assert (check_evidence.find_cites(md, "Menary", "2010")
                == check_evidence.find_cites(md, "Menary", "2010", "")), md


# Item 3 F review, F1: the first suffix implementation anchored the pairing
# on the SURNAME, which under-reported genuinely-cited lettered works on the
# exact prose forms the feature creates. Each test below FAILS on that
# implementation; positions are derived from the fixture, never hard-coded,
# and asserted exactly - a truthiness or length-only assertion lets the
# surname-anchored behaviour back in silently.

def test_find_cites_credits_both_letters_in_a_compact_parenthetical():
    # One surname occurrence serves two letters. Surname-anchored pairing
    # gave 'b' [] here, reporting a cited work as uncited.
    for md in ("Menary (2010a; 2010b) both argue X.",
               "Menary (2010a, 2010b) both argue X."):
        pos = md.index("Menary")
        assert check_evidence.find_cites(md, "Menary", "2010", "a") == [pos], md
        assert check_evidence.find_cites(md, "Menary", "2010", "b") == [pos], md


def test_find_cites_pairs_a_repeated_surname_with_the_following_year():
    # "Surname YEAR" prose: the year that belongs to a surname FOLLOWS it.
    # Surname-anchored pairing tied on distance and resolved backwards,
    # giving 'a' both occurrences and 'b' none.
    md = "This is contested (Menary 2010a; Menary 2010b)."
    first = md.index("Menary")
    second = md.index("Menary", first + 1)
    assert check_evidence.find_cites(md, "Menary", "2010", "a") == [first]
    assert check_evidence.find_cites(md, "Menary", "2010", "b") == [second]


def test_find_cites_ignores_a_nearby_decade_mention():
    # "2010s" is not a qualifying mention of 2010 for ANY letter. Under
    # surname-anchored pairing it still entered the nearest-mention contest,
    # won it, and suppressed the real "(2010a)" cite next to it.
    md = "In the 2010s, Menary (2010a) argues X."
    pos = md.index("Menary")
    assert check_evidence.find_cites(md, "Menary", "2010", "a") == [pos]
    assert check_evidence.find_cites(md, "Menary", "2010", "b") == []
    # ...and the decade alone must not manufacture a cite either.
    decade_only = "In the 2010s, Menary said little."
    assert check_evidence.find_cites(decade_only, "Menary", "2010", "a") == []


def test_find_cites_reads_an_uppercase_prose_letter_as_that_letter():
    """Item 3 F second opinion: "2010B" used to fall THROUGH the
    case-sensitive `b` alternative and satisfy the lowercase-only bare-year
    lookahead instead -- so an uppercase letter was read as a BARE citation
    and credited every lettered entry for that year, the 'a' entry included.
    The 'b' row pins that an uppercase letter resolves to its own entry; the
    'a' row pins that it no longer resolves to every OTHER lettered entry.
    Both rows are carried by re.IGNORECASE alone -- the widened `[0-9A-Za-z]`
    class is redundant under that flag (measured) and is spelled out only so
    the bare-year half stops depending on it."""
    md = "Menary (2010B) argues X."
    pos = md.index("Menary")
    assert check_evidence.find_cites(md, "Menary", "2010", "b") == [pos]
    assert check_evidence.find_cites(md, "Menary", "2010", "a") == []
    # An UNLETTERED entry keeps the historic reading: the no-suffix arm is
    # untouched by this fix, and "2010B" is still a mention of 2010 there.
    assert check_evidence.find_cites(md, "Menary", "2010") == [pos]
    # The lowercase control behaves identically, which is the point: the
    # renderer lowercases what it emits, so case must not carry meaning.
    lower = "Menary (2010b) argues X."
    assert (check_evidence.find_cites(lower, "Menary", "2010", "b")
            == check_evidence.find_cites(md, "Menary", "2010", "b"))
    # An uppercase ENTRY suffix reaching find_cites directly resolves too
    # (main() lowercases before calling, but the function is public).
    assert check_evidence.find_cites(lower, "Menary", "2010", "B") == [pos]


BIB_LETTERED = """@book{menary2010cognitive,
  author = {Menary, Richard},
  title = {Cognitive Integration},
  year = {2010},
  year_suffix = {a},
  keywords = {High, EVIDENCE-NONE}
}

@book{menary2010extended,
  author = {Menary, Richard},
  title = {The Extended Mind},
  year = {2010},
  year_suffix = {b},
  keywords = {High, EVIDENCE-NONE}
}"""


def test_bare_year_citation_flags_both_lettered_entries(tmp_path):
    # Item 3 F: a bare "Menary (2010)" is what generate_bibliography
    # deliberately treats as ambiguous-keep-all - the checker must not read
    # a bare cite as citing NEITHER lettered work (false telemetry).
    r = _run(tmp_path, "Menary (2010) is influential.", bib_text=BIB_LETTERED)
    assert "CHECK none-cited: menary2010cognitive" in r.stdout
    assert "CHECK none-cited: menary2010extended" in r.stdout


def test_lettered_citation_flags_only_its_own_entry(tmp_path):
    r = _run(tmp_path, "Menary (2010a) is influential.", bib_text=BIB_LETTERED)
    assert "CHECK none-cited: menary2010cognitive" in r.stdout
    assert "CHECK none-cited: menary2010extended" not in r.stdout


def test_uppercase_lettered_citation_flags_only_its_own_entry(tmp_path):
    # The whole-script consequence of the regex fix: before it, "2010B" read
    # as a bare cite and reported BOTH lettered works as none-cited.
    r = _run(tmp_path, "Menary (2010B) is influential.", bib_text=BIB_LETTERED)
    assert "CHECK none-cited: menary2010extended" in r.stdout
    assert "CHECK none-cited: menary2010cognitive" not in r.stdout


def test_sanitizer_strips_all_tokens(tmp_path):
    bib = tmp_path / "b.bib"
    bib.write_text(BIB, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SANITIZER), str(bib)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    content = bib.read_text(encoding="utf-8")
    assert "EVIDENCE-" not in content        # the delivered-artifact invariant
    assert "ps, High" in content             # other keywords intact


def test_the_web_tier_is_not_low_trust():
    """EVIDENCE-WEB licenses characterization, so it must NOT join the
    low-trust set: check_evidence's verb heuristics police what a writer may
    claim, and WEB entries are citable."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import check_evidence as ce
    import stamp_evidence as se
    assert se.TIER_WEB not in ce._LOW_TRUST_TIERS
    assert se.TIER_EXISTENCE in ce._LOW_TRUST_TIERS
