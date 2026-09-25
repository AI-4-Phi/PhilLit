"""Pins the prose contract of the off-sync working directory: every agent
and SKILL.md path runs through [workdir], the pointer is touched only by
workdir.py, and no Phase 6 step moves the ownership metadata file."""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKILL = (ROOT / "skills" / "literature-review" / "SKILL.md").read_text(encoding="utf-8")
RESEARCHER = (ROOT / "agents" / "domain-literature-researcher.md").read_text(encoding="utf-8")
AGENTS = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "agents").glob("*.md")}


def _code_blocks(text):
    """Shell blocks only: the final-state tree (a plain ``` block) names the
    published reviews/[project-name]/ on purpose."""
    return re.findall(r"```bash\n(.*?)```", text, flags=re.S)


def test_researcher_review_dir_is_the_pasted_workdir():
    assert RESEARCHER.count('REVIEW_DIR="[workdir]"') == 10
    assert "$PWD/reviews" not in RESEARCHER
    assert "outside the working directory" in RESEARCHER


def test_no_agent_example_names_a_reviews_path():
    for name, text in AGENTS.items():
        assert "reviews/project-name" not in text, name


def test_skill_commands_never_hardcode_the_review_folder():
    for block in _code_blocks(SKILL):
        assert "reviews/[project-name]" not in block
        assert "reviews/[project-short-name]" not in block


def test_skill_pointer_is_owned_by_workdir_py():
    for block in _code_blocks(SKILL):
        assert ".active-review" not in block
    for sub in ("status", "init", "activate", "demote", "publish"):
        assert f"workdir.py {sub}" in SKILL, sub
    assert "workdir.py publish --abandon" in SKILL


def test_no_phase6_step_touches_the_metadata_file():
    phase6 = SKILL.split("## Phase 6")[1]
    for block in _code_blocks(phase6):
        assert ".phillit-review" not in block
        assert not re.search(r"\brm\b", block)


def test_publish_is_the_last_phase6_step_after_docx():
    phase6 = SKILL.split("## Phase 6")[1].split("\n## ")[0]
    assert phase6.index("Convert to DOCX") < phase6.index("workdir.py publish")
    assert "PRECONDITION" in phase6


def test_phase6_resume_rule_is_the_one_marker_rule():
    phase6 = SKILL.split("## Phase 6")[1].split("\n## ")[0]
    assert "intermediate_files/lit-review-plan.md" in phase6
    assert "again from step 1" in phase6
    assert "MARKER" not in phase6  # the per-step marker scheme was dropped


def test_phase6_step8_moves_are_idempotent():
    phase6 = SKILL.split("## Phase 6")[1].split("\n## ")[0]
    step8 = phase6[phase6.index("8. Clean up"):phase6.index("**After publish**")]
    for block in _code_blocks(step8):
        # no bare multi-file mv of fixed names or globs: a re-run on a resume
        # must skip what is already moved
        assert not re.search(r'^\s*mv "\[workdir\]/(task-progress|synthesis-section)', block, re.M)


def test_abandon_precondition_is_stated_where_abandon_is_offered():
    phase1 = SKILL.split("## Phase 1")[1].split("\n## ")[0]
    guard = phase1[phase1.index("Guard — concurrent review"):]
    assert "PRECONDITION" in guard.split("\n\n")[0]
