"""Tests for subagent_stop_bib.sh - SubagentStop BibTeX validation hook.

Pins the Claude Code hook protocol contract:
- ALL decisions are stdout JSON with exit code 0 (JSON is ignored on exit 2).
- Block: {"decision": "block", "reason": <syntax errors>}.
- Cleaning summary: hookSpecificOutput.additionalContext (allow path).
- Self-scopes with NO matcher: validates only inside a .phillit workspace, when
  agent_type contains "domain-literature-researcher", and an .active-review exists.

The script runs against a temporary CLAUDE_PROJECT_DIR marked with .phillit; the
bib_validator.py / metadata_cleaner.py validators resolve from CLAUDE_PLUGIN_ROOT
(the repo root) through the phillit-run wrapper (uv project env).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pybtex.database import parse_file as pybtex_parse_file

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "hooks" / "subagent_stop_bib.sh"
FIXTURES = Path(__file__).parent / "fixtures" / "item13"

BASH = shutil.which("bash")
JQ = shutil.which("jq")
UV = shutil.which("uv")

pytestmark = pytest.mark.skipif(
    BASH is None or JQ is None or UV is None, reason="requires bash, jq, and uv"
)

VALID_BIB = """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971}
}
"""

# Missing required field `journal` for @article -> validation error
INVALID_BIB = """@article{wolf1990freedom,
  author = {Wolf, Susan},
  title = {Freedom Within Reason},
  year = {1990}
}
"""

# Entry with a `number` field not present in the API JSON -> cleaner removes it
HALLUCINATED_NUMBER_BIB = """@article{awad2018moral,
  author = {Awad, Edmond and Dsouza, Sohan},
  title = {The Moral Machine experiment},
  journal = {Nature},
  year = {2018},
  number = {7729},
  doi = {10.1038/s41586-018-0637-6}
}
"""

S2_NATURE_JSON = {
    "status": "success",
    "source": "semantic_scholar",
    "query": "Moral Machine experiment",
    "results": [
        {
            "paperId": "abc123",
            "title": "The Moral Machine experiment",
            "authors": [{"name": "E. Awad", "authorId": "12345"}],
            "year": 2018,
            "doi": "10.1038/s41586-018-0637-6",
            "venue": "Nature",
            "journal": {"name": "Nature", "pages": None, "volume": None},
            "publicationTypes": ["JournalArticle"],
        }
    ],
    "count": 1,
    "errors": [],
}


@pytest.fixture
def project(tmp_path):
    """Temporary CLAUDE_PROJECT_DIR: an active PhilLit workspace (.phillit) with an active review."""
    (tmp_path / ".phillit").mkdir()
    review_dir = tmp_path / "reviews" / "test-review"
    review_dir.mkdir(parents=True)
    (tmp_path / "reviews" / ".active-review").write_text(
        "reviews/test-review", encoding="utf-8"
    )
    return tmp_path


def run_hook(payload: dict, project_dir: Path) -> tuple[dict, int, str]:
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
        "PHILLIT_UV": UV,
    }
    proc = subprocess.run(
        [BASH, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert proc.stdout.strip(), f"hook produced no stdout; stderr: {proc.stderr}"
    return json.loads(proc.stdout), proc.returncode, proc.stderr


RESEARCHER = {"agent_type": "domain-literature-researcher", "stop_hook_active": False}


def test_no_marker_allows_and_does_not_touch_bib(tmp_path):
    # Plugin hooks fire for ALL SubagentStop events; without a .phillit marker the
    # hook must no-op AND never mutate .bib files (the BLOCKER this fixes:
    # metadata_cleaner.py rewrites .bib in place).
    proj = tmp_path  # note: NO (proj / ".phillit")
    bib = proj / "refs.bib"
    original = "@article{x, title={X}, hallucinated={y}}\n"
    bib.write_text(original, encoding="utf-8")
    (proj / "reviews").mkdir()
    (proj / "reviews" / ".active-review").write_text("reviews/r", encoding="utf-8")
    (proj / "reviews" / "r").mkdir()
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
        "PHILLIT_UV": UV,
        "CLAUDE_PROJECT_DIR": str(proj),
    }
    r = subprocess.run(
        [BASH, str(SCRIPT)],
        input='{"agent_type":"domain-literature-researcher"}',
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    assert '"decision": "allow"' in r.stdout
    assert bib.read_text(encoding="utf-8") == original  # untouched


class TestGuards:
    def test_stop_hook_active_with_no_bibs_allows(self, project):
        # A resumed pass still runs the full flow (validation + cleaning) but
        # with no .bib files present it falls through to a plain allow.
        out, code, _ = run_hook(
            {"agent_type": "domain-literature-researcher", "stop_hook_active": True},
            project,
        )
        assert out == {"decision": "allow"}
        assert code == 0

    def test_other_agent_type_allows(self, project):
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            INVALID_BIB, encoding="utf-8"
        )
        out, code, _ = run_hook({"agent_type": "synthesis-writer"}, project)
        assert out == {"decision": "allow"}
        assert code == 0

    def test_missing_agent_type_allows(self, project):
        out, code, _ = run_hook({}, project)
        assert out == {"decision": "allow"}
        assert code == 0

    def test_namespaced_agent_type_validates(self, project):
        # Substring match: a plugin-namespaced agent_type must still validate.
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            INVALID_BIB, encoding="utf-8"
        )
        out, code, _ = run_hook(
            {"agent_type": "phillit:domain-literature-researcher"}, project
        )
        assert code == 0
        assert out["decision"] == "block"
        assert "journal" in out["reason"]

    def test_no_active_review_allows(self, project):
        (project / "reviews" / ".active-review").unlink()
        out, code, _ = run_hook(RESEARCHER, project)
        assert out == {"decision": "allow"}
        assert code == 0


class TestValidation:
    def test_valid_bib_allows(self, project):
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            VALID_BIB, encoding="utf-8"
        )
        out, code, _ = run_hook(RESEARCHER, project)
        assert out == {"decision": "allow"}
        assert code == 0

    def test_invalid_bib_blocks_with_reason_and_exit_zero(self, project):
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            INVALID_BIB, encoding="utf-8"
        )
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0, "block must be exit 0 — JSON is ignored on exit 2"
        assert out["decision"] == "block"
        assert "journal" in out["reason"]

    def test_no_bib_files_allows(self, project):
        out, code, _ = run_hook(RESEARCHER, project)
        assert out == {"decision": "allow"}
        assert code == 0


class TestGateFailurePolicy:
    """Accuracy gates fail CLOSED and loud (CLAUDE.md gate-failure policy).

    Review finding (2026-07-13): a validator/uv crash yields empty stdout, and
    jq exits 0 on empty input — so the crash silently counted as valid BibTeX.
    """

    def test_validator_crash_blocks_not_allows(self, project):
        # A .bib exists (content is irrelevant — the validator never runs), and
        # uv is broken: the hook must block with a "crashed" reason, not allow.
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            VALID_BIB, encoding="utf-8"
        )
        broken = project / "brokenbin"
        broken.mkdir()
        fake_uv = broken / "uv"
        fake_uv.write_text(
            "#!/usr/bin/env bash\necho 'uv: simulated venv build failure' >&2\nexit 2\n",
            encoding="utf-8",
        )
        fake_uv.chmod(0o755)
        env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(project),
            "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
            "PHILLIT_UV": str(fake_uv),
        }
        proc = subprocess.run(
            [BASH, str(SCRIPT)],
            input=json.dumps(RESEARCHER),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        assert out["decision"] == "block"
        assert "produced no output" in out["reason"]

    def test_missing_jq_emits_visible_system_message(self, project):
        # Without jq the hook cannot parse stdin (not even to scope the event),
        # so it allows — but the skip must surface as a user-visible
        # systemMessage, never as a silent stderr line on exit 0.
        env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(project),
            "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
            "PATH": "/nonexistent",  # no jq (bash builtins suffice up to the check)
        }
        proc = subprocess.run(
            [BASH, str(SCRIPT)],
            input="{}",
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        assert proc.returncode == 0
        out = json.loads(proc.stdout)
        assert "jq" in out.get("systemMessage", ""), (
            f"expected a user-visible systemMessage about jq, got: {proc.stdout}"
        )


class TestMetadataCleaning:
    def test_cleaning_summary_in_additional_context(self, project):
        review = project / "reviews" / "test-review"
        (review / "d1.bib").write_text(HALLUCINATED_NUMBER_BIB, encoding="utf-8")
        (review / "s2_results.json").write_text(
            json.dumps(S2_NATURE_JSON), encoding="utf-8"
        )
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert out["hookSpecificOutput"]["hookEventName"] == "SubagentStop"
        assert "awad2018moral" in ctx

    def test_union_of_json_dirs_passed_to_cleaner(self, project):
        # Item-13 A3: a field verifiable ONLY via intermediate_files/json must
        # survive — proving the hook passes the UNION of both dirs. The old
        # first-match logic picked the review root alone and would have shadowed
        # (starved) the verify JSON, stripping the field.
        review = project / "reviews" / "test-review"
        bib = review / "d1.bib"
        bib.write_text(
            "@article{awad2018moral,\n"
            "  author = {Awad, Edmond},\n"
            "  title = {The Moral Machine experiment},\n"
            "  journal = {Nature},\n"
            "  year = {2018},\n"
            "  number = {5},\n"
            "  doi = {10.1038/s41586-018-0637-6}\n"
            "}\n",
            encoding="utf-8",
        )
        # An UNRELATED json at the review root so BIB_DIR is non-empty (this is
        # what the old first-match logic would have selected, shadowing below).
        (review / "s2_other.json").write_text(
            json.dumps({"source": "s2", "results": [
                {"title": "Other", "year": 1999, "doi": "10.9/other",
                 "journal": {"name": "Other J"}}]}),
            encoding="utf-8",
        )
        # The MATCHING verify json, carrying issue 5, ONLY under intermediate_files/json.
        jdir = review / "intermediate_files" / "json"
        jdir.mkdir(parents=True)
        (jdir / "verify_awad.json").write_text(
            json.dumps({"source": "crossref", "results": [
                {"container_title": "Nature", "issue": "5", "year": 2018,
                 "doi": "10.1038/s41586-018-0637-6"}]}),
            encoding="utf-8",
        )
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        data = pybtex_parse_file(str(bib), bib_format="bibtex")
        fields = {k.lower() for k in data.entries["awad2018moral"].fields}
        assert "number" in fields, (
            "number=5 (verifiable only via the second dir) was stripped — "
            "the hook did not pass the union of JSON dirs"
        )

    def test_no_json_dirs_skips_cleaner_and_leaves_bib_untouched(self, project):
        # Neither the .bib's own dir nor intermediate_files/json holds JSON, so
        # JSON_DIRS is empty and the cleaner is never invoked — no summary, and
        # (crucially) no field is stripped without evidence.
        review = project / "reviews" / "test-review"
        bib = review / "d1.bib"
        original = HALLUCINATED_NUMBER_BIB
        bib.write_text(original, encoding="utf-8")
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        assert out == {"decision": "allow"}
        assert bib.read_text(encoding="utf-8") == original  # untouched

    def test_blocked_resume_still_writes_final_pass_ledger(self, project):
        """Spec section 8 pre-merge checklist: a researcher whose SubagentStop
        BLOCKED on a BibTeX syntax error and then resumed must still end with a
        cleaned file AND a cleaning ledger reflecting the FINAL pass.

        The old stop_hook_active guard short-circuited to allow BEFORE the
        validator/cleaner loop, so the resumed (fixed) bib was never re-cleaned
        and the ledger stayed stale from the blocked pass — silently breaking
        the evidence barrier's assumption that cleaning precedes it.
        """
        review = project / "reviews" / "test-review"
        bib = review / "d1.bib"
        # API JSON present so the cleaner runs on both passes.
        (review / "s2_results.json").write_text(
            json.dumps(S2_NATURE_JSON), encoding="utf-8"
        )
        # Pass 1: validation error (missing `journal`) -> block. The cleaner
        # still parses this bib fine and seeds a STALE ledger (wolf1990freedom).
        bib.write_text(INVALID_BIB, encoding="utf-8")
        out1, code1, _ = run_hook(RESEARCHER, project)
        assert code1 == 0
        assert out1["decision"] == "block"
        # Pass 2 (resumed): the agent replaced the file with a fixed bib; the
        # hook fires again with stop_hook_active=true. It must not block, and
        # the cleaner must run again so the ledger reflects THIS pass.
        bib.write_text(HALLUCINATED_NUMBER_BIB, encoding="utf-8")
        out2, code2, _ = run_hook(
            {"agent_type": "domain-literature-researcher", "stop_hook_active": True},
            project,
        )
        assert code2 == 0
        assert out2.get("decision") != "block"
        # Cleaning happened on the resumed pass: hallucinated `number` removed.
        data = pybtex_parse_file(str(bib), bib_format="bibtex")
        fields = {k.lower() for k in data.entries["awad2018moral"].fields}
        assert "number" not in fields, "resumed pass did not run the cleaner"
        # Ledger exists and reflects the final pass, not the blocked one.
        ledger = review / "intermediate_files" / "json" / "cleaning_ledger-d1.json"
        assert ledger.exists()
        ldata = json.loads(ledger.read_text(encoding="utf-8"))
        assert ldata["schema_version"] == 1
        assert ldata["bib_file"] == "d1.bib"
        assert "awad2018moral" in ldata["entries"]
        assert "wolf1990freedom" not in ldata["entries"], (
            "ledger is stale from the blocked pass — the resumed pass "
            "skipped the cleaner"
        )

    def test_resumed_pass_never_reblocks_but_surfaces_errors(self, project):
        # Loop prevention: a still-invalid bib on a resumed pass must NOT emit
        # another block — but per the never-silent gate policy the unresolved
        # errors must surface as a user-visible systemMessage.
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            INVALID_BIB, encoding="utf-8"
        )
        out, code, _ = run_hook(
            {"agent_type": "domain-literature-researcher", "stop_hook_active": True},
            project,
        )
        assert code == 0
        assert out.get("decision") != "block", (
            "re-blocking on stop_hook_active=true risks an infinite stop-hook loop"
        )
        assert "journal" in out.get("systemMessage", ""), (
            f"unresolved BibTeX errors must surface in a systemMessage: {out}"
        )

    def test_cleaner_warnings_surface_in_additional_context(self, project):
        # Item-13 A3 (never-silent): a salvage/skip notice from the cleaner must
        # reach the model via additionalContext even when no field is removed.
        review = project / "reviews" / "test-review"
        (review / "d1.bib").write_text(VALID_BIB, encoding="utf-8")
        jdir = review / "intermediate_files" / "json"
        jdir.mkdir(parents=True)
        # A log-polluted but salvageable verify JSON -> cleaner emits "Salvaged N".
        (jdir / "verify_a.json").write_text(
            (FIXTURES / "verify_amorosotamburrini2017.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Salvaged" in ctx or "Cleaner warnings" in ctx, (
            f"cleaner salvage warning did not surface in additionalContext: {out}"
        )
