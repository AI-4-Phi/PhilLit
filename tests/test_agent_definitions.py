"""In plugin mode, agents and skills run from the user's workspace: relative
repo paths like `../docs/conventions.md` resolve against the workspace's parent
directory, not the plugin root. Shared-doc references must use $PHILLIT_ROOT
(bridged into the session by the SessionStart bootstrap).

Review finding (2026-07-13): SKILL.md was fixed to the $PHILLIT_ROOT form
during the plugin conversion; the agent files were not.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_no_relative_docs_paths_in_agents_or_skills():
    files = list((REPO_ROOT / "agents").glob("*.md")) + list(
        (REPO_ROOT / "skills").rglob("SKILL.md")
    )
    assert files, "expected agent/skill definitions to exist"
    offenders = []
    for path in files:
        for i, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if "../docs/" in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{i}")
    assert not offenders, (
        "relative ../docs/ paths do not resolve from a plugin workspace "
        "(use $PHILLIT_ROOT/docs/...):\n" + "\n".join(offenders)
    )


def test_researcher_teaches_verify_paper_output_convention():
    """verify_paper.py owns its output file via --output (item 13, A2/D4);
    a researcher piping stdout to a file (or worse, `2>&1`) corrupts the
    JSON with interleaved progress logs. The agent definition must both
    show the --output invocation and explicitly forbid the redirect
    footgun. We only assert positive markers (never `"2>&1" not in text`)
    because the prohibition sentence itself quotes `2>&1`.
    """
    path = REPO_ROOT / "agents" / "domain-literature-researcher.md"
    text = path.read_text(encoding="utf-8")

    assert "verify_paper.py" in text and "--output" in text, (
        "researcher agent must show verify_paper.py invoked with --output"
    )
    assert "never redirect" in text.lower() or "do not redirect" in text.lower(), (
        "researcher agent must explicitly instruct never to redirect "
        "verify_paper.py output (e.g. `> f.json 2>&1`) instead of using --output"
    )


def test_researcher_forbids_post_enrichment_reemission():
    """A/B root cause 2 (2026-07-25): researchers re-emit the whole bib
    after enrichment, silently mutating hash-attested abstracts. The
    guidance must freeze the file, name the Write AND the Bash-workaround
    paths, and give the surgical-Edit alternative."""
    path = REPO_ROOT / "agents" / "domain-literature-researcher.md"
    text = path.read_text(encoding="utf-8")
    assert "FROZEN after enrichment" in text
    assert "Never `Write` the whole bib file again" in text
    assert "Bash file operations" in text
    assert "surgical" in text.lower()


def test_researcher_has_edit_tool_and_guidance():
    """Critical finding from reviewer (2026-08-01): researchers need Edit
    for surgical changes to .bib files after enrichment. The tool must be
    listed in frontmatter and guidance must replace the stale "Edit is NOT
    available" note with new guidance about post-edit validation."""
    path = REPO_ROOT / "agents" / "domain-literature-researcher.md"
    text = path.read_text(encoding="utf-8")

    # Extract frontmatter
    lines = text.split("\n")
    tools_line = None
    for line in lines:
        if line.startswith("tools:"):
            tools_line = line
            break

    assert tools_line is not None, "could not find 'tools:' line in frontmatter"
    assert "Edit" in tools_line, "Edit tool must be in the frontmatter tools list"

    # Verify stale guidance is gone
    assert "The Edit tool is NOT available to you" not in text, (
        "stale guidance asserting Edit is unavailable must be removed"
    )

    # Verify new guidance is present
    assert "Prefer `Edit` for targeted changes" in text or "Edit` to a `.bib`" in text, (
        "new guidance about Edit post-edit validation must be present"
    )


def test_writer_tier_rules_carry_b2_edits():
    """Adjudication 2026-07-28 + decision b2 2026-08-01: CONTEXT
    attribution was followed 1 of 4 times, and EXISTENCE-tier
    over-characterization needed a title-derivable clarifier plus
    calibration examples from the adjudicated run."""
    path = REPO_ROOT / "agents" / "synthesis-writer.md"
    text = path.read_text(encoding="utf-8")
    assert "title-derivable" in text
    assert "every sentence" in text.lower()
    assert "Calibration examples" in text
    assert "Sequoiah-Grayson" in text          # CONTEXT exemplar present
    assert "announces, in its very title" in text  # EXISTENCE exemplar present
    assert "data creators" in text             # negative exemplar present
