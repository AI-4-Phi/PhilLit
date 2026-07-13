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
