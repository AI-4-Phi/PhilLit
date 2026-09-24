"""fault_lines: the review plan's FLn.n definitions and their substitution."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"))
import fault_lines as fl  # noqa: E402

PLAN = """**Fault Lines** (state each as a proposition; array positions for and against)
- **FL1.1 — One principle or three?** Waldron's disaggregation thesis.
- **FL1.3 — Separation as insulation vs. separation as interaction.** Pure-separation readings.
- **FL4.7 — Is the "new separation of powers" comparative or American?** `[SEED — verify]` Ackerman.
- **FL6.2 — Does XCONST conflate constraint with regime type?** A standing objection.
- **FL3.2 — Veto points: constraint or paralysis?** `[SEED — verify]` Tsebelis, *Veto Players*.
"""


def test_parse_definitions_reads_every_bullet():
    defs = fl.parse_definitions(PLAN)
    assert defs["FL1.1"] == "One principle or three?"
    assert defs["FL1.3"] == "Separation as insulation vs. separation as interaction"
    assert set(defs) == {"FL1.1", "FL1.3", "FL4.7", "FL6.2", "FL3.2"}


def test_phrase_lowercases_a_capitalised_first_word_only():
    assert fl.phrase("One principle or three?") == "the “one principle or three?” fault line"
    # An acronym first word keeps its case.
    assert fl.phrase("XCONST and regime type") == "the “XCONST and regime type” fault line"


def test_phrase_turns_inner_straight_quotes_curly():
    # A straight `"` would end a quote-delimited BibTeX value.
    out = fl.phrase('Is the "new separation of powers" comparative or American?')
    assert '"' not in out
    assert "'‘new separation of powers’'" in out or "'new separation of powers'" in out


def test_phrase_leaves_a_latex_accent_alone():
    assert 'M{\\\"u}ller' in fl.phrase('Does M{\\"u}ller hold?')


def test_substitute_replaces_embedded_and_listed_tags():
    defs = fl.parse_definitions(PLAN)
    text = "the thesis on which FL1.1 turns; see FL1.1, FL1.3."
    out = fl.substitute(text, defs)
    assert "FL1" not in out
    assert out.startswith("the thesis on which the “one principle or three?” fault line turns")


def test_substitute_fails_loudly_on_an_undefined_tag():
    with pytest.raises(fl.UndefinedFaultLine) as exc:
        fl.substitute("FL1.1 and FL9.9 and FL8.1", fl.parse_definitions(PLAN))
    assert exc.value.tags == ["FL8.1", "FL9.9"]


def test_look_alikes_are_not_tags():
    assert fl.tags_in("FLOW, FL-tagged, AFL1.1x, FL1.10") == ["FL1.10"]


def test_no_tags_means_no_op_even_without_definitions():
    assert fl.substitute("no tags here", {}) == "no tags here"
