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


def test_the_tracker_is_never_written_after_publish():
    assert "tick before step 11" in SKILL
    rule = SKILL[SKILL.index("**Update `task-progress.md` after EVERY completed phase"):][:500]
    assert "never write the tracker" in rule and "after publish" in rule


def test_status_active_branch_excludes_the_flags():
    assert "with a `workdir` and none of the flags above" in SKILL


def test_researcher_strips_the_backticks():
    assert "the path between the backticks, without the backticks" in RESEARCHER


def test_resume_never_skips_the_evidence_barrier():
    rules = SKILL[SKILL.index("**Resume logic**"):SKILL.index("Output: \"Resuming from Phase")]
    assert "evidence_report.json" in rules and "evidence barrier" in rules
    # a report that exists but says `failed` must re-run the barrier too
    assert "`complete`" in rules and "`degraded`" in rules


def test_phase6_root_sweep_takes_only_phillit_bibs():
    phase6 = SKILL.split("## Phase 6")[1].split("\n## ")[0]
    step8 = phase6[phase6.index("8. Clean up"):phase6.index("**After publish**")]
    assert '-name "*.bib"' not in step8  # a user's own bibliography stays put
    assert 'find . -maxdepth 1 -name "literature-domain-*.bib" -exec mv' in step8


def test_publish_step_names_the_unproven_entry():
    phase6 = SKILL.split("## Phase 6")[1].split("\n## ")[0]
    step11 = phase6[phase6.index("11. **Publish the review**"):]
    assert "An `unproven` entry names a local folder whose ownership could not be proven" in step11


def test_status_names_every_stuck_state_before_the_active_branch():
    step5 = SKILL[SKILL.index("5. Check for an active review"):SKILL.index("**Resume logic**")]
    active = step5.index("with a `workdir` and none of the flags above")
    for flag in ('"unproven": true', '"interrupted_demote": true'):
        assert -1 < step5.find(flag) < active, flag
    unproven = step5[step5.index('"unproven": true'):].split("\n   - ")[0]
    assert "**STOP.**" in unproven and "`error` verbatim" in unproven
    assert "reviews/.active-review` by hand" in unproven
    demote = step5[step5.index('"interrupted_demote": true'):].split("\n   - ")[0]
    assert "workdir.py demote" in demote and "Phase 2" in demote
    elsewhere = step5[step5.index('"elsewhere": true'):].split("\n   - ")[0]
    assert "`workdir_exists`" in elsewhere


def test_phase1_names_the_way_out_of_an_activate_refusal():
    step5 = SKILL[SKILL.index("5. Check for an active review"):SKILL.index("**Resume logic**")]
    inactive = step5[step5.index('"active": false'):].split("\n   - ")[0]
    assert "If `activate` refuses, report it verbatim." in inactive
    assert "try again once sync has finished; otherwise stop" in inactive


def test_an_unproven_folder_is_never_promised_a_listing():
    step5 = SKILL[SKILL.index("5. Check for an active review"):SKILL.index("**Resume logic**")]
    unproven = step5[step5.index('"unproven": true'):].split("\n   - ")[0]
    assert "listed under `stranded`" not in unproven
    assert unproven.count("deletes `reviews/.active-review` by hand") == 1
    assert "may list it as abandoned or stranded, or not at all" in unproven


def test_publish_step_names_the_foreign_destination_refusal():
    phase6 = SKILL.split("## Phase 6")[1].split("\n## ")[0]
    step11 = phase6[phase6.index("11. **Publish the review**"):]
    assert ("If it refuses because `reviews/[project-name]/` belongs to another review, "
            "report the refusal verbatim (it names the way out) and stop.") in step11


def test_step11_checks_completed_review_before_activate():
    phase6 = SKILL.split("## Phase 6")[1].split("\n## ")[0]
    step11 = phase6[phase6.index("11. **Publish the review**"):]
    completed = step11.index(
        "first check whether `reviews/[project-name]/intermediate_files/.completed-review` exists")
    otherwise = step11.index("Otherwise run `workdir.py activate [project-name]`")
    assert -1 < completed < otherwise
