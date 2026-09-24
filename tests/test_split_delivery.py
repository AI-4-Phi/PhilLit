"""split_delivery: the three Phase 6 deliverables. The binding decisions
this exercises live in split_delivery.py's module docstring."""
import sys
from pathlib import Path

import pytest
from pybtex.database import parse_string

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(SCRIPTS))
import fault_lines as fl  # noqa: E402
import split_delivery as sd  # noqa: E402

DEFS = {"FL1.1": "One principle or three?", "FL1.4": "Continuity or rupture with the classical tradition?"}

ENTRY = """@article{waldron2020separation,
  same_work_group = {waldron2013separation, waldron2020separation},
  abstract_source = {s2},
  abstract = {The rationale of the separation of powers.},
  author = {Waldron, Jeremy},
  title = {Separation of powers in thought and practice?},
  journal = {Revista de Direito Administrativo},
  year = {2020},
  year_suffix = {a},
  url = {https://example.org/w},
  urldate = {2026-09-10},
  venue_status = {low-visibility},
  iep_context = {An IEP passage.},
  doi = {10.12660/rda.v279.2020.82914},
  note = {
  CORE ARGUMENT: the thesis on which FL1.1 turns.

  POSITION: disaggregation; see FL1.1, FL1.4.
  },
  keywords = {separation-of-powers, XCONST, FLOW, High-modernism, FL1.1, FL1.4, AI-RELEVANT, NO-DOI, INCOMPLETE, High, EVIDENCE-ABSTRACT, METADATA\\_CLEANED: journal}
}
"""


def _entries(text):
    return parse_string(text, "bibtex").entries


def test_annotated_keywords_keep_topics_and_drop_every_verdict():
    kw = ("separation-of-powers, XCONST, FLOW, High-modernism, FL1.1, AI-RELEVANT, "
          "ROUTING-DISPUTE, NO-DOI, Medium, INCOMPLETE, no-abstract, EVIDENCE-NONE, "
          "METADATA\\_CLEANED: journal")
    assert sd.annotated_keywords(kw) == "separation-of-powers, XCONST, FLOW, High-modernism"


def test_track_keywords_keep_verdicts_and_drop_only_phase3_tokens():
    kw = "a-topic, FL1.1, AI-RELEVANT, INCOMPLETE, no-abstract, High, EVIDENCE-NONE, METADATA\\_CLEANED: journal"
    assert sd.track_keywords(kw) == "a-topic, FL1.1, AI-RELEVANT, High, EVIDENCE-NONE, METADATA\\_CLEANED: journal"


def test_track_record_drops_notes_and_keeps_every_verdict():
    out = sd.track_record_entry(ENTRY)
    e = _entries(out)["waldron2020separation"].fields
    assert "note" not in e and "CORE ARGUMENT" not in out
    for kept in ("same_work_group", "abstract_source", "year_suffix", "venue_status",
                 "urldate", "iep_context"):
        assert kept in e
    kw = e["keywords"]
    for token in ("FL1.1", "AI-RELEVANT", "EVIDENCE-ABSTRACT", "METADATA\\_CLEANED: journal"):
        assert token in kw
    assert ", High," in kw and "INCOMPLETE" not in kw


def test_annotated_substitutes_notes_strips_verdicts_and_the_eight_engine_fields():
    out = sd.annotated_entry(ENTRY, DEFS)
    e = _entries(out)["waldron2020separation"].fields
    assert "the “one principle or three?” fault line turns" in e["note"]
    assert not fl.tags_in(out)
    assert e["keywords"] == "separation-of-powers, XCONST, FLOW, High-modernism"
    for gone in ("same_work_group", "abstract_source", "year_suffix", "venue_status", "urldate"):
        assert gone not in e
    assert e["iep_context"] == "An IEP passage."          # not one of the eight (decided)
    assert e["url"] == "https://example.org/w" and e["abstract"].startswith("The rationale")


def test_a_quoted_note_is_substituted_and_re_emitted_braced():
    entry = '@book{k1,\n  title = {T},\n  year = {2020},\n  note = "POSITION: see FL1.1.",\n}\n'
    out = sd.annotated_entry(entry, DEFS)
    assert 'note = {POSITION: see the “one principle or three?” fault line.}' in out
    assert "k1" in _entries(out)


def test_a_keywords_field_that_empties_is_removed():
    entry = "@book{k1,\n  title = {T},\n  year = {2020},\n  keywords = {FL1.1, High, EVIDENCE-EXISTENCE}\n}\n"
    out = sd.annotated_entry(entry, DEFS)
    assert "keywords" not in out and "k1" in _entries(out)
    only_phase3 = "@book{k2,\n  title = {T},\n  year = {2020},\n  keywords = {INCOMPLETE}\n}\n"
    assert "keywords" not in sd.track_record_entry(only_phase3)


def test_undefined_tags_in_note_and_keywords_are_all_named():
    entry = "@book{k1,\n  title = {T},\n  year = {2020},\n  note = {see FL7.7},\n  keywords = {x, FL8.8}\n}\n"
    with pytest.raises(fl.UndefinedFaultLine) as exc:
        sd.annotated_entry(entry, DEFS)
    assert exc.value.tags == ["FL7.7", "FL8.8"]


def test_an_entry_without_notes_or_keywords_passes_through():
    entry = "@book{k1,\n  title = {T},\n  year = {2020}\n}\n"
    assert sd.track_record_entry(entry) == entry
    assert sd.annotated_entry(entry, DEFS) == entry


import json
import subprocess

RULE = "=" * 68
COMMENT = f"""@comment{{
{RULE}
DOMAIN: 1 -- Anatomy
SEARCH_DATE: 2026-09-10
{RULE}

DOMAIN_OVERVIEW:
The move is DISAGGREGATION.

SYNTHESIS_GUIDANCE:
Do not present FL1.1 as settled.
{RULE}
}}
"""
OTHER_COMMENT = "@comment{jabref-meta: databaseType:bibtex;}\n"
OVERFLOW = "@comment{\nKEY_POSITIONS:\n- more analysis\n}\n"
STRING = "@string{rda = {Revista de Direito Administrativo}}\n"
PLAN = "- **FL1.1 — One principle or three?** Waldron.\n- **FL1.4 — Continuity or rupture with the classical tradition?** x.\n"


def _review(tmp_path, bib_text, plan_text=PLAN):
    bib = tmp_path / "literature-sop.bib"
    bib.write_text(bib_text, encoding="utf-8")
    plan = tmp_path / "lit-review-plan.md"
    plan.write_text(plan_text, encoding="utf-8")
    return bib, plan


def _cli(bib, plan=None):
    cmd = [sys.executable, str(SCRIPTS / "split_delivery.py"), str(bib)]
    if plan is not None:
        cmd += ["--plan", str(plan)]
    return subprocess.run(cmd, capture_output=True, cwd=bib.parent)


def _out(r):
    return r.stdout.decode("ascii")          # raises if any byte is not ASCII


def _summary(r):
    return json.loads(_out(r).strip().splitlines()[-1])


def test_the_split_writes_three_files_by_purpose(tmp_path):
    bib, plan = _review(tmp_path, STRING + "\n" + COMMENT + "\n" + OTHER_COMMENT + "\n" + ENTRY)
    r = _cli(bib, plan)
    assert r.returncode == 0, r.stdout + r.stderr
    s = _summary(r)
    assert s["entries"] == 1 and s["domains"] == 1 and s["errors"] == []
    assert s["written"] == ["literature-sop.bib", "literature-sop-annotated.bib",
                            "research-notes-sop.md"]

    track = bib.read_text(encoding="utf-8")
    annotated = (tmp_path / "literature-sop-annotated.bib").read_text(encoding="utf-8")
    notes = (tmp_path / "research-notes-sop.md").read_text(encoding="utf-8")

    for text in (track, annotated):
        assert "@comment" not in text.lower()          # no comment of any kind
        assert "@string{rda" in text                   # macros stay
        assert "waldron2020separation" in parse_string(text, "bibtex").entries
    assert "EVIDENCE-ABSTRACT" in track and "EVIDENCE-" not in annotated
    assert "CORE ARGUMENT" not in track and "CORE ARGUMENT" in annotated
    assert "## 1 -- Anatomy" in notes
    assert "Do not present the “one principle or three?” fault line as settled." in notes


def test_a_dropped_comment_that_held_analysis_is_noticed(tmp_path):
    bib, plan = _review(tmp_path, COMMENT + "\n" + OVERFLOW + "\n" + ENTRY)
    r = _cli(bib, plan)
    assert r.returncode == 0
    assert "SPLIT-NOTICE:" in _out(r) and "KEY_POSITIONS" not in bib.read_text(encoding="utf-8")


def test_an_unknown_label_writes_the_bibs_but_not_the_notes(tmp_path):
    bad = COMMENT.replace("SYNTHESIS_GUIDANCE:", "SCOPE NOTE:").replace("FL1.1", "FL9.9")
    bib, plan = _review(tmp_path, bad + "\n" + ENTRY)
    stale = tmp_path / "research-notes-sop.md"
    stale.write_text("an older run's notes", encoding="utf-8")
    r = _cli(bib, plan)
    assert r.returncode == 2
    out = _out(r)
    assert "SPLIT-ERROR:" in out and "SCOPE NOTE" in out
    assert "FL9.9" in out                       # every offender named in one run
    assert _summary(r)["written"] == ["literature-sop.bib", "literature-sop-annotated.bib"]
    assert not stale.exists()                   # no stale file beside fresh ones
    assert ("the research blocks are kept in "
            "intermediate_files/literature-sop-merged.bib") in out


def test_an_undefined_tag_withholds_only_the_annotated_bib(tmp_path):
    bib, plan = _review(tmp_path, ENTRY.replace("FL1.4", "FL9.9"))
    r = _cli(bib, plan)
    assert r.returncode == 2 and "FL9.9" in _out(r)
    assert not (tmp_path / "literature-sop-annotated.bib").exists()
    assert "CORE ARGUMENT" not in bib.read_text(encoding="utf-8")   # track record written
    assert (tmp_path / "research-notes-sop.md").exists()


def test_a_track_record_that_would_not_parse_is_not_written(tmp_path):
    broken = ENTRY.replace("  doi =", "  doi = {x},\n  doi =")      # duplicate field
    bib, plan = _review(tmp_path, broken)
    before = bib.read_text(encoding="utf-8")
    r = _cli(bib, plan)
    assert r.returncode == 2 and "does not parse" in _out(r)
    assert bib.read_text(encoding="utf-8") == before
    assert not (tmp_path / "literature-sop-annotated.bib").exists()


def test_re_running_on_a_split_bib_is_refused(tmp_path):
    bib, plan = _review(tmp_path, COMMENT + "\n" + ENTRY)
    assert _cli(bib, plan).returncode == 0
    annotated = (tmp_path / "literature-sop-annotated.bib").read_text(encoding="utf-8")
    r = _cli(bib, plan)
    assert r.returncode == 2 and "re-run step 3" in _out(r)
    assert (tmp_path / "literature-sop-annotated.bib").read_text(encoding="utf-8") == annotated


def test_a_bib_with_no_notes_and_no_siblings_still_splits(tmp_path):
    bib, plan = _review(tmp_path, "@book{k1,\n  title = {T},\n  year = {2020}\n}\n")
    r = _cli(bib, plan)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "No per-domain research notes" in (tmp_path / "research-notes-sop.md").read_text(encoding="utf-8")


def test_a_moved_plan_is_found_in_intermediate_files(tmp_path):
    bib, plan = _review(tmp_path, ENTRY)
    (tmp_path / "intermediate_files").mkdir()
    plan.rename(tmp_path / "intermediate_files" / plan.name)
    r = _cli(bib, plan)                          # the old top-level path
    assert r.returncode == 0, r.stdout + r.stderr
    annotated = (tmp_path / "literature-sop-annotated.bib").read_text(encoding="utf-8")
    assert ("the “continuity or rupture with the classical tradition?” fault line"
            in annotated)                        # the moved plan's FL1.4 definition was used


def test_a_named_plan_that_does_not_exist_is_an_error(tmp_path):
    bib, _ = _review(tmp_path, ENTRY)
    r = _cli(bib, tmp_path / "missing-plan.md")
    assert r.returncode == 1 and "SPLIT-ERROR:" in _out(r)
    assert not (tmp_path / "literature-sop-annotated.bib").exists()


def test_a_non_utf8_input_is_a_clean_error(tmp_path):
    bib = tmp_path / "literature-sop.bib"
    bib.write_bytes("@book{k1,\n  title = {Müller},\n}\n".encode("cp1252"))
    r = _cli(bib)
    assert r.returncode == 1 and "SPLIT-ERROR:" in _out(r)


def test_error_lines_stay_ascii_for_a_non_ascii_label(tmp_path):
    bad = COMMENT.replace("SYNTHESIS_GUIDANCE:", f"{RULE}\nÉTUDE ANNEXE\n")
    bib, plan = _review(tmp_path, bad + "\n" + ENTRY)
    r = _cli(bib, plan)
    assert r.returncode == 2
    assert "\\xc9TUDE" in _out(r)              # escaped, and _out() proves all-ASCII


def test_a_run_that_withholds_both_siblings_still_blocks_a_note_less_rerun(tmp_path):
    bib, plan = _review(tmp_path, COMMENT + "\n" + ENTRY)
    original = bib.read_text(encoding="utf-8")
    r = _cli(bib)                                # no --plan: every FLn.n is undefined
    assert r.returncode == 2
    out = _out(r)
    assert out.count("SPLIT-ERROR:") >= 2        # both siblings withheld

    backup = tmp_path / "intermediate_files" / "literature-sop-merged.bib"
    assert backup.exists() and backup.read_text(encoding="utf-8") == original

    r2 = _cli(bib, plan)                         # now with the right plan
    assert r2.returncode == 2
    out2 = _out(r2)
    assert "re-run step 3" in out2 and backup.name in out2
    assert not (tmp_path / "literature-sop-annotated.bib").exists()
    assert not (tmp_path / "research-notes-sop.md").exists()


def test_a_stray_non_entry_chunk_passes_through_uncounted(tmp_path):
    bib, plan = _review(tmp_path, "% header\n" + ENTRY)
    r = _cli(bib, plan)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _summary(r)["entries"] == 1


import os
import re

SKILL = (ROOT / "skills" / "literature-review" / "SKILL.md").read_text(encoding="utf-8")


def test_phase_6_runs_the_split_not_the_sanitizer():
    assert "split_delivery.py" in SKILL and "sanitize_bib.py" not in SKILL


PHASE_6 = SKILL[SKILL.index("## Phase 6:"):]


FENCE = "`" * 3      # built, not written, so this file can sit in a Markdown code block


def _step_bash(anchor):
    """The first bash code block after `anchor` in Phase 6, for review `p`."""
    tail = PHASE_6[PHASE_6.index(anchor):]
    block = re.search(FENCE + r"bash\n(.*?)" + FENCE, tail, re.S)
    return block.group(1).replace("[project-name]", "p")


def test_step_7_as_written_writes_the_three_files(tmp_path):
    """Runs step 7's command exactly as SKILL.md writes it, from a workspace
    root, so a wrong path or flag fails here and not in a user's review."""
    rd = tmp_path / "reviews" / "p"
    rd.mkdir(parents=True)
    (rd / "literature-p.bib").write_text(COMMENT + "\n" + ENTRY, encoding="utf-8")
    (rd / "lit-review-plan.md").write_text(PLAN, encoding="utf-8")
    env = {**os.environ, "PHILLIT_ROOT": str(ROOT)}
    r = subprocess.run(["bash", "-c", _step_bash("Split the delivery into its three files")],
                       cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for name in ("literature-p.bib", "literature-p-annotated.bib", "research-notes-p.md"):
        assert (rd / name).exists(), name


def test_the_safety_net_keeps_the_three_deliverables(tmp_path):
    """Runs the sweep exactly as SKILL.md writes it: a keep-list typo, or an
    earlier command that moves the notes file, fails here."""
    script = _step_bash("Safety net")
    rd = tmp_path / "reviews" / "p"
    (rd / "intermediate_files").mkdir(parents=True)
    keep = ["literature-review-p.md", "literature-p.bib", "literature-p-annotated.bib",
            "research-notes-p.md"]
    for name in keep + ["stray.txt"]:
        (rd / name).write_text("x", encoding="utf-8")
    subprocess.run(["bash", "-c", script], cwd=tmp_path, check=True)
    for name in keep:
        assert (rd / name).exists(), name
    assert (rd / "intermediate_files" / "stray.txt").exists()
