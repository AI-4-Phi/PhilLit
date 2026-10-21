"""Prose-quality WARN backstop for the assembled review.

check_prose_quality is a heuristic, WARN-only detector run at Phase 6. It must
never affect lint_md's exit code. Strings below are the real leaks observed in
the 2026-07-17 production test review.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import lint_md  # noqa: E402


def test_annotated_citation_non_peer_reviewed_warns():
    text = "As the report shows (Human Rights Watch 2012, non-peer-reviewed), the risk is real."
    warnings = lint_md.check_prose_quality(text)
    assert any("non-peer-reviewed" in w for w in warnings)


def test_annotated_citation_classic_text_cited_via_warns():
    text = "This view (Fischer 1982, classic text cited via title and year without quoted abstract) is foundational."
    warnings = lint_md.check_prose_quality(text)
    # Matches "classic text" and/or "cited via"; at least one warning, exactly one per parenthesis.
    assert len([w for w in warnings if "line 1" in w]) == 1
    assert any(("classic text" in w) or ("cited via" in w) for w in warnings)


def test_all_annotation_phrases_flagged():
    for phrase in ("non-peer-reviewed", "working paper", "classic text", "cited via", "primary policy source"):
        text = f"A claim (Smith 2020, {phrase}) appears here."
        assert lint_md.check_prose_quality(text), phrase


def test_in_prose_section_subsection_token_warns():
    text = "As discussed in Section 3.3, the tension recurs."
    warnings = lint_md.check_prose_quality(text)
    assert any("Section 3.3" in w for w in warnings)


def test_in_prose_bare_section_number_warns():
    text = "See Section 3 above for the framing."
    warnings = lint_md.check_prose_quality(text)
    assert any("Section 3" in w for w in warnings)


def test_h2_meta_label_warns():
    text = "## Section 1: Moral Responsibility (Core Analytical Section)"
    warnings = lint_md.check_prose_quality(text)
    assert any("meta-label" in w for w in warnings)


def test_legit_h2_heading_does_not_warn():
    # A numbered heading is not an in-prose "Section N" cross-reference,
    # and has no parenthesized meta-label.
    text = "## Section 3: The Expertise-Democracy Tension"
    assert lint_md.check_prose_quality(text) == []


def test_clean_prose_no_warnings():
    text = (
        "The debate (Sparrow 2007) turns on control. Section headings here "
        "carry no numeric cross-reference, and (Amoroso & Tamburrini 2017) is clean.\n"
    )
    assert lint_md.check_prose_quality(text) == []


def test_section_token_inside_fenced_code_ignored():
    text = "```\nSection 3.3 is a code sample, not prose.\n```\n"
    assert lint_md.check_prose_quality(text) == []


def test_returns_list():
    assert isinstance(lint_md.check_prose_quality(""), list)


def test_main_prints_warnings_without_affecting_exit_code(tmp_path, monkeypatch, capsys):
    md = tmp_path / "review.md"
    md.write_text(
        "Body text (Human Rights Watch 2012, non-peer-reviewed) here.\n",
        encoding="utf-8",
    )
    # Isolate the prose wiring: force the pymarkdown pass to a known clean exit.
    monkeypatch.setattr(lint_md, "lint_markdown", lambda p: 0)
    rc = lint_md.main([str(md)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN prose-quality" in out
    assert "non-peer-reviewed" in out


def test_main_preserves_lint_returncode(tmp_path, monkeypatch):
    md = tmp_path / "review.md"
    md.write_text("Clean prose with no issues.\n", encoding="utf-8")
    monkeypatch.setattr(lint_md, "lint_markdown", lambda p: 3)
    assert lint_md.main([str(md)]) == 3


# --- workflow (process) language in review prose -----------------------------

def test_process_language_phrases_warn():
    for phrase in (
        "orchestrator",
        "writer notes", "writer-notes", "Writer Notes",
        "tier override", "tier-overrides",
        "research brief", "research request",
        "user's description", "user\u2019s description",
        "synthesis outline", "synthesis-outline",
        "could not check that account", "this review could not check",
        "this review could not verify",
        "EVIDENCE-ABSTRACT",
    ):
        text = f"The text mentions the {phrase} in passing."
        warnings = lint_md.check_prose_quality(text)
        assert any(
            "workflow language in review prose: rewrite for the reader" in w
            and phrase in w
            for w in warnings
        ), phrase


def test_process_language_real_leaks_warn():
    for text in (
        "The research request describes Gardner (2019) as a defence; this "
        "review could not check that account.",
        "On the orchestrator's reading of her notes, the view is weaker.",
        "The research brief also lists a third position.",
    ):
        warnings = lint_md.check_prose_quality(text)
        assert any("workflow language" in w for w in warnings), text


def test_sanctioned_reader_facing_hedges_do_not_warn():
    for text in (
        "Smith (2020) is reported to argue that harm is comparative; its "
        "full text was not available for this review.",
        "This review does not cover the legal literature.",
        "The agent could not check whether the door was locked.",
        "Descartes could not verify the work of the senses by the senses alone.",
        "Kant could not check its argument against experience.",
        "The evidence for this claim is mixed.",
        # The writer's sanctioned disclosure forms (agents/synthesis-writer.md):
        "Smith (2020) is taken here to offer a compatibilist reply to "
        "Frankfurt; this review did not verify that account.",
        "On that account, the reply concedes the first premise.",
        "Smith (2020), whose title identifies it as a study of moral luck, "
        "is relevant; this review did not verify its argument.",
        "The work itself could not be verified for this review.",
        "Parfit, as Gardner (2019) reports, accepts the comparative account.",
    ):
        assert lint_md.check_prose_quality(text) == [], text


def test_process_language_is_whole_word_and_skips_code_and_headings():
    assert lint_md.check_prose_quality("The orchestrators of the plan met.") == []
    assert lint_md.check_prose_quality("## The research brief\n") == []
    fenced = "```\nthe orchestrator ran\n```\n"
    assert lint_md.check_prose_quality(fenced) == []


def test_process_language_warn_never_changes_exit_code(tmp_path, capsys):
    md = tmp_path / "r.md"
    md.write_text("# T\n\nThe orchestrator decided.\n", encoding="utf-8")
    sys.argv = ["lint_md.py", str(md)]
    try:
        rc = lint_md.main()
    except SystemExit as e:
        rc = e.code
    out = capsys.readouterr().out
    assert "WARN prose-quality:" in out and "workflow language" in out
    assert not rc
