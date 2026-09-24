"""research_notes: per-domain @comment research blocks -> Markdown."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "skills" / "literature-review" / "scripts"))
import fault_lines as fl  # noqa: E402
import research_notes as rn  # noqa: E402

RULE = "=" * 68
DEFS = {"FL1.1": "One principle or three?"}
BODY = f"""
DOMAIN_OVERVIEW:

The move is DISAGGREGATION (waldron2013separation).

KEY_POSITIONS:
- Disaggregation: 3 papers - FL1.1 turns on it.

NOTABLE_GAPS:
Stage 4: 45 candidates inspected.

ABSTRACTS: 17 of 19 entries carry abstracts.
Two are INCOMPLETE.

SYNTHESIS_GUIDANCE:
Do not present FL1.1 as settled.

RELEVANCE_TO_PROJECT: Directly relevant.
{RULE}"""


def block(domain="1 -- Conceptual Anatomy", body=BODY, header_extra="", opener="{", closer="}"):
    return f"""@comment{opener}
{RULE}
DOMAIN: {domain}
SEARCH_DATE: 2026-09-10
PAPERS_FOUND: 19 total (High: 12, Medium: 7, Low: 0) -- 7 book, 2 incollection,
7 article, 3 misc.
SEARCH_SOURCES: SEP, PhilPapers
{header_extra}{RULE}
{body}
{closer}
"""


def test_a_research_block_is_recognised_and_other_blocks_are_not():
    assert rn.is_research_block(block())
    assert rn.is_research_block(block(opener="(", closer=")"))
    assert rn.is_comment_block("@comment{ jabref-meta: databaseType:bibtex; }\n")
    assert not rn.is_research_block("@comment{ jabref-meta: databaseType:bibtex; }\n")
    assert not rn.is_research_block("@string{j = {Mind}}\n")
    assert not rn.is_comment_block("@string{j = {Mind}}\n")
    assert not rn.is_research_block("@article{k1,\n  title = {DOMAIN: x},\n}\n")


def test_parse_keeps_in_sections_in_order_and_drops_header_and_out_sections():
    d = rn.parse_block(block())
    assert d.title == "1 -- Conceptual Anatomy" and d.number == 1
    assert [label for label, _ in d.sections] == [
        "DOMAIN_OVERVIEW", "KEY_POSITIONS", "NOTABLE_GAPS",
        "SYNTHESIS_GUIDANCE", "RELEVANCE_TO_PROJECT"]
    gaps = dict(d.sections)["NOTABLE_GAPS"]
    assert "Stage 4: 45 candidates inspected." in gaps
    assert "ABSTRACTS" not in gaps and "Two are INCOMPLETE" not in gaps   # OUT, inline
    assert dict(d.sections)["RELEVANCE_TO_PROJECT"] == "Directly relevant."  # inline IN
    text = "\n".join(t for _, t in d.sections)
    assert "SEARCH_DATE" not in text and "7 article" not in text


def test_the_parenthesised_comment_form_parses():
    assert rn.parse_block(block(opener="(", closer=")")).title == "1 -- Conceptual Anatomy"


def test_an_inline_unknown_label_fails_loudly():
    body = BODY.replace("- Disaggregation: 3 papers", "AGAINST: Kavanagh 2026.\n- Disaggregation: 3 papers")
    with pytest.raises(rn.UnknownLabel) as exc:
        rn.parse_block(block(body=body))
    assert exc.value.labels == ["AGAINST"]
    assert exc.value.texts == []


def test_an_unknown_label_in_the_header_fails_loudly():
    with pytest.raises(rn.UnknownLabel) as exc:
        rn.parse_block(block(header_extra="COUNT NOTE: the plan expected 10-14.\n"))
    assert exc.value.labels == ["COUNT NOTE"]


def test_every_unknown_label_is_named_in_one_pass():
    body = BODY.replace("NOTABLE_GAPS:", "SCOPE NOTE:\n26 entries.\n\nNOTABLE_GAPS:")
    with pytest.raises(rn.UnknownLabel) as exc:
        rn.parse_block(block(body=body, header_extra="COUNT NOTE: x\n"))
    assert exc.value.labels == ["COUNT NOTE", "SCOPE NOTE"]


def test_a_colonless_heading_after_a_rule_is_named_once():
    body = f"""
DOMAIN_OVERVIEW:
Kept.
{RULE}

FAULT LINES (proposition, positions)

FL6.1 -- TEXT OR BEHAVIOUR? Proposition.
{RULE}"""
    with pytest.raises(rn.UnknownLabel) as exc:
        rn.parse_block(block(body=body))
    assert exc.value.texts == ["FAULT LINES (proposition, positions)"]
    assert exc.value.labels == []


def test_text_before_any_label_fails_loudly():
    with pytest.raises(rn.UnknownLabel) as exc:
        rn.parse_block(block(body="\nSome unlabelled paragraph.\n\nDOMAIN_OVERVIEW:\nKept.\n"))
    assert exc.value.texts == ["Some unlabelled paragraph."]
    assert exc.value.labels == []


def test_text_before_the_first_rule_is_reported_not_discarded():
    chunk = block().replace("@comment{\n", "@comment{\nStray preamble.\n", 1)
    with pytest.raises(rn.UnknownLabel) as exc:
        rn.parse_block(chunk)
    assert exc.value.texts == ["Stray preamble."]
    assert exc.value.labels == []


def test_blank_lines_before_the_first_rule_are_fine():
    chunk = block().replace("@comment{\n", "@comment{\n\n\n", 1)
    assert rn.parse_block(chunk).title == "1 -- Conceptual Anatomy"


def test_has_in_label_spots_overflow_analysis():
    assert rn.has_in_label("@comment{\nKEY_POSITIONS:\n- x\n}\n")
    assert not rn.has_in_label("@comment{ jabref-meta: databaseType:bibtex; }\n")


def test_render_substitutes_tags_and_orders_numbered_domains():
    d10, d2 = rn.parse_block(block("10 -- Late")), rn.parse_block(block("2 -- Early"))
    md = rn.render([d10, d2], DEFS, "separation-of-powers")
    assert md.index("## 2 -- Early") < md.index("## 10 -- Late")
    assert "Do not present the “one principle or three?” fault line as settled." in md
    assert not fl.tags_in(md)
    assert "### Domain overview" in md


def test_unnumbered_domains_keep_their_block_order():
    a, b = rn.parse_block(block("Zeta")), rn.parse_block(block("Alpha"))
    md = rn.render([a, b], DEFS, "p")
    assert md.index("## Zeta") < md.index("## Alpha")


def test_a_tag_in_a_domain_title_is_substituted_or_fails():
    d = rn.parse_block(block("3 -- The FL1.1 debate"))
    assert "## 3 -- The the “one principle or three?” fault line debate" in rn.render([d], DEFS, "p")
    with pytest.raises(fl.UndefinedFaultLine) as exc:
        rn.render([rn.parse_block(block("3 -- The FL5.5 debate"))], DEFS, "p")
    assert exc.value.tags == ["FL5.5"]


def test_render_names_every_undefined_tag():
    with pytest.raises(fl.UndefinedFaultLine) as exc:
        rn.render([rn.parse_block(block())], {}, "p")
    assert exc.value.tags == ["FL1.1"]


def test_render_with_no_domains_says_so():
    assert "No per-domain research notes were recorded." in rn.render([], {}, "p")


def test_every_in_label_renders_a_heading():
    expected = {
        "DOMAIN_OVERVIEW": "Domain overview",
        "KEY_POSITIONS": "Key positions",
        "NOTABLE_GAPS": "Notable gaps",
        "SYNTHESIS_GUIDANCE": "Synthesis guidance",
        "RELEVANCE_TO_PROJECT": "Relevance to project",
    }
    assert set(rn.IN_LABELS) == set(expected)
    for label in rn.IN_LABELS:
        assert rn._heading(label) == expected[label]


def test_render_does_not_raise_when_in_labels_is_extended(monkeypatch):
    monkeypatch.setattr(rn, "IN_LABELS", rn.IN_LABELS + ("EXTRA_SECTION",))
    body = f"""
EXTRA_SECTION:
New content.
{RULE}"""
    d = rn.parse_block(block(body=body))
    md = rn.render([d], DEFS, "p")
    assert "### Extra section" in md
