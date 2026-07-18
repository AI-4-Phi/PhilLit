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
