"""Tests for subagent_stop_bib.sh - SubagentStop BibTeX validation hook.

Pins the Claude Code hook protocol contract:
- ALL decisions are stdout JSON with exit code 0 (JSON is ignored on exit 2).
- Block: {"decision": "block", "reason": <syntax errors>}.
- Allow: {} (Claude Code rejects {"decision": "allow"} as invalid hook output).
- Cleaning summary: hookSpecificOutput.additionalContext, first pass only (it
  continues the subagent's turn); a resumed pass reports only a cleaner
  failure, as a systemMessage.
- Self-scopes with NO matcher: validates only inside a .phillit workspace, when
  agent_type contains "domain-literature-researcher", and workdir.py resolves an active review.

The script runs against a temporary CLAUDE_PROJECT_DIR marked with .phillit; the
bib_validator.py / metadata_cleaner.py validators resolve from CLAUDE_PLUGIN_ROOT
(the repo root) through the phillit-run wrapper (uv project env).
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
from ledger_binding import (  # noqa: E402
    BINDING_SCHEMA_VERSION, bib_text_sha256,
)

import pytest
from pybtex.database import parse_file as pybtex_parse_file

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "hooks" / "subagent_stop_bib.sh"
FIXTURES = Path(__file__).parent / "fixtures" / "bib_quality"

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

# Entry with a `number` the entry-scoped CrossRef record below REFUTES ->
# cleaner removes it. Since the strip-rule fix a field merely ABSENT from the
# pool is kept,
# so a "did the cleaner run" detector needs the contradicting record too.
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


# Entry-scoped CrossRef record for the same DOI, naming a DIFFERENT issue.
# An S2 dump can never refute `number` (parse_s2_result reports issue=None
# unconditionally), so the strip needs this record.
VERIFY_AWAD_JSON = {
    "status": "success",
    "source": "crossref",
    "query": {"doi": "10.1038/s41586-018-0637-6"},
    "results": [
        {
            "verified": True,
            "doi": "10.1038/s41586-018-0637-6",
            "title": "The Moral Machine experiment",
            "container_title": "Nature",
            "issue": "1",
            "year": 2018,
            "type": "journal-article",
        }
    ],
    "count": 1,
    "errors": [],
}


# The year-correction case from a real run: the bib's year (2017) is also a
# broad dump's, so the pooled sources disagree; the entry-scoped CrossRef
# record (published-print 2018) settles it, and the cleaner rewrites the year.
WRONG_YEAR_BIB = """@article{awad2018moral,
  author = {Awad, Edmond and Dsouza, Sohan},
  title = {The Moral Machine experiment},
  journal = {Nature},
  year = {2017},
  doi = {10.1038/s41586-018-0637-6}
}
"""

S2_WRONG_YEAR_JSON = {**S2_NATURE_JSON, "results": [
    {**S2_NATURE_JSON["results"][0], "year": 2017}]}

VERIFY_AWAD_PRINT_YEAR_JSON = {**VERIFY_AWAD_JSON, "results": [{
    "verified": True,
    "doi": "10.1038/s41586-018-0637-6",
    "title": "The Moral Machine experiment",
    "container_title": "Nature",
    "year": 2018,
    "year_basis": "published-print",
    "type": "journal-article",
}]}


def seed_year_correction(review: Path) -> Path:
    bib = review / "d1.bib"
    bib.write_text(WRONG_YEAR_BIB, encoding="utf-8")
    (review / "s2_results.json").write_text(
        json.dumps(S2_WRONG_YEAR_JSON), encoding="utf-8")
    (review / "verify_awad.json").write_text(
        json.dumps(VERIFY_AWAD_PRINT_YEAR_JSON), encoding="utf-8")
    return bib


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


def write_transcript(path: Path, prompt: str, written: tuple[str, ...] = ()) -> Path:
    """A subagent transcript in Claude Code's JSONL shape (checked against a
    real researcher's): the dispatch prompt as the first user record, then
    one assistant record per file-tool Write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [{"type": "user", "isSidechain": True,
                "message": {"role": "user", "content": prompt}}]
    for fp in written:
        records.append({"type": "assistant", "isSidechain": True, "message": {
            "role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "Write",
                                              "input": {"file_path": fp, "content": ""}}]}})
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def with_transcript(payload: dict, project_dir: Path) -> dict:
    """Tests about validation and cleaning, not scoping, get a transcript that
    owns every bib under the workspace (and literature-domain-1.bib, a local
    review's), so the hook scopes to exactly the files it used to sweep. A
    payload that names a transcript, or no researcher, is left alone."""
    if ("domain-literature-researcher" not in str(payload.get("agent_type", ""))
            or "agent_transcript_path" in payload or "transcript_path" in payload):
        return payload
    names = {"literature-domain-1.bib"}
    for _root, _dirs, files in os.walk(project_dir):     # never follows symlinks
        names.update(f for f in files if f.endswith(".bib"))
    # The prompt assigns no file, so a test without one gets no "missing" note.
    t = write_transcript(project_dir / ".transcripts" / "agent-auto.jsonl",
                         "Research your domain.", tuple(sorted(names)))
    return {**payload, "agent_transcript_path": str(t)}


def run_hook(payload: dict, project_dir: Path) -> tuple[dict, int, str]:
    payload = with_transcript(payload, project_dir)
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
    assert json.loads(r.stdout) == {}
    assert bib.read_text(encoding="utf-8") == original  # untouched


class TestGuards:
    def test_stop_hook_active_with_no_bibs_allows(self, project):
        # A resumed pass still runs the full flow (validation + cleaning) but
        # with no .bib files present it falls through to a plain allow.
        out, code, _ = run_hook(
            {"agent_type": "domain-literature-researcher", "stop_hook_active": True},
            project,
        )
        assert out == {}
        assert code == 0

    def test_other_agent_type_allows(self, project):
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            INVALID_BIB, encoding="utf-8"
        )
        out, code, _ = run_hook({"agent_type": "synthesis-writer"}, project)
        assert out == {}
        assert code == 0

    def test_missing_agent_type_allows(self, project):
        out, code, _ = run_hook({}, project)
        assert out == {}
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

    def test_no_active_review_allows_visibly(self, project):
        (project / "reviews" / ".active-review").unlink()
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0 and "decision" not in out
        assert "SKIPPED" in out["systemMessage"]


class TestValidation:
    def test_valid_bib_allows(self, project):
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            VALID_BIB, encoding="utf-8"
        )
        out, code, _ = run_hook(RESEARCHER, project)
        assert out == {}
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
        assert out == {}
        assert code == 0

    def test_every_decision_the_hook_prints_is_one_claude_code_accepts(self):
        # Claude Code documents only decision "block" for SubagentStop (omit
        # it to allow); "allow" fails validation on every researcher stop.
        decisions = set(re.findall(r'"decision":\s*"(\w+)"',
                                   SCRIPT.read_text(encoding="utf-8")))
        assert decisions, "the scan found no decision literal at all"
        assert decisions <= {"block"}, decisions


class TestRootStrays:
    """The workspace root is swept for researcher strays only: a domain bib
    written without the review-directory prefix, named in PhilLit's
    literature-domain-*.bib namespace. Any other root .bib is treated as the
    user's own file: the cleaner rewrites what it processes."""

    def test_users_own_root_bibs_are_never_validated_or_rewritten(self, project):
        refs = project / "refs.bib"
        refs.write_text(HALLUCINATED_NUMBER_BIB, encoding="utf-8")
        draft = project / "draft.bib"
        draft.write_text(INVALID_BIB, encoding="utf-8")
        # Evidence beside them that would make the cleaner strip `number`.
        (project / "s2_results.json").write_text(
            json.dumps(S2_NATURE_JSON), encoding="utf-8")
        (project / "verify_awad.json").write_text(
            json.dumps(VERIFY_AWAD_JSON), encoding="utf-8")
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        assert out == {}, "a user's own root .bib was validated or cleaned"
        assert refs.read_text(encoding="utf-8") == HALLUCINATED_NUMBER_BIB
        assert draft.read_text(encoding="utf-8") == INVALID_BIB

    def test_a_researcher_stray_at_the_root_is_still_validated(self, project):
        (project / "literature-domain-3.bib").write_text(
            INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        assert out["decision"] == "block"
        assert "journal" in out["reason"]


class TestGateFailurePolicy:
    """Accuracy gates fail CLOSED and loud (CLAUDE.md gate-failure policy).

    Review finding (2026-07-13): a validator/uv crash yields empty stdout, and
    jq exits 0 on empty input — so the crash silently counted as valid BibTeX.
    """

    def test_validator_crash_blocks_not_allows(self, project):
        # A .bib exists (content is irrelevant — the validator never runs).
        # The stub phillit-run answers `resolve` (so the resolver succeeds)
        # and crashes everything else, so the crash lands on the validator:
        # the hook must block with a "crashed" reason, not allow.
        (project / "reviews" / "test-review" / "d1.bib").write_text(
            VALID_BIB, encoding="utf-8"
        )
        root = project / "stub-plugin"
        (root / "bin").mkdir(parents=True)
        run = root / "bin" / "phillit-run"
        run.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            "  *workdir.py) printf '{\"workdir\": \"%s/reviews/test-review\"}\\n' \"$CLAUDE_PROJECT_DIR\" ;;\n"
            "  *) echo 'uv: simulated venv build failure' >&2; exit 2 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        run.chmod(0o755)
        env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(project),
            "CLAUDE_PLUGIN_ROOT": str(root),
            "PHILLIT_UV": UV,
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
        (review / "verify_awad.json").write_text(
            json.dumps(VERIFY_AWAD_JSON), encoding="utf-8"
        )
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert out["hookSpecificOutput"]["hookEventName"] == "SubagentStop"
        assert "awad2018moral" in ctx

    def test_union_of_json_dirs_passed_to_cleaner(self, project):
        # A field verifiable ONLY via intermediate_files/json must
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
        assert out == {}
        assert bib.read_text(encoding="utf-8") == original  # untouched

    def test_blocked_resume_still_writes_final_pass_ledger(self, project):
        """Pre-merge checklist: a researcher whose SubagentStop
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
        (review / "verify_awad.json").write_text(
            json.dumps(VERIFY_AWAD_JSON), encoding="utf-8"
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
        assert ldata["schema_version"] == BINDING_SCHEMA_VERSION
        assert ldata["bib_file"] == "d1.bib"
        # The resumed pass rewrote the bib, so its ledger must bind to the
        # text that is there NOW -- the blocked pass's hash would not.
        assert ldata["bib_sha256"] == bib_text_sha256(
            (review / "d1.bib").read_text(encoding="utf-8"))
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
        assert "hookSpecificOutput" not in out

    def test_first_pass_reports_the_year_correction_once(self, project):
        """The cleaner's year rewrite is named in the first-pass report (key,
        old -> new, basis), and a disagreement the scoped record SETTLED is
        not reported at all."""
        review = project / "reviews" / "test-review"
        bib = seed_year_correction(review)
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        assert "decision" not in out
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "awad2018moral: 2017 -> 2018" in ctx
        assert "verify_awad.json" in ctx and "published-print" in ctx
        assert "disagree" not in ctx
        assert "Removed" not in ctx          # no field was removed
        assert "year = {2018}" in bib.read_text(encoding="utf-8")

    def test_resumed_pass_sends_no_report_but_still_cleans(self, project):
        """A SubagentStop additionalContext continues the subagent's turn, so
        a report on every pass kept researchers answering the same report
        until Claude Code's stop-hook cap. On a resumed pass the hook allows
        with {} - but the cleaner and its ledger still run (the barrier
        needs a ledger for the final text)."""
        review = project / "reviews" / "test-review"
        bib = seed_year_correction(review)
        out, code, _ = run_hook({**RESEARCHER, "stop_hook_active": True}, project)
        assert code == 0
        assert out == {}
        text = bib.read_text(encoding="utf-8")
        assert "year = {2018}" in text, "resumed pass did not run the cleaner"
        ledger = review / "intermediate_files" / "json" / "cleaning_ledger-d1.json"
        ldata = json.loads(ledger.read_text(encoding="utf-8"))
        assert ldata["bib_sha256"] == bib_text_sha256(text)
        assert "awad2018moral" in ldata["entries"]

    def test_cleaner_warnings_surface_in_additional_context(self, project):
        # Never-silent: a salvage/skip notice from the cleaner must
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

    def test_core_json_does_not_silently_disable_cleaning(self, project):
        # A CORE result file (string-shaped `journal`) crashed the cleaner, and
        # the hook swallowed the traceback: no summary, bib untouched -- byte-
        # identical to a clean run. The refuted `number` must now go.
        review = project / "reviews" / "test-review"
        bib = review / "d1.bib"
        bib.write_text(HALLUCINATED_NUMBER_BIB, encoding="utf-8")
        jdir = review / "intermediate_files" / "json"
        jdir.mkdir(parents=True)
        (jdir / "s2_nature.json").write_text(
            json.dumps(S2_NATURE_JSON), encoding="utf-8")
        (jdir / "verify_awad.json").write_text(
            json.dumps(VERIFY_AWAD_JSON), encoding="utf-8")
        (jdir / "core_moral.json").write_text(json.dumps({
            "status": "success", "source": "core", "query": "moral machine",
            "results": [{"core_id": "1", "doi": "10.1038/s41586-018-0637-6",
                         "title": "The Moral Machine experiment", "year": 2018,
                         "publisher": "Springer", "journal": "Nature"}],
            "count": 1, "errors": [],
        }), encoding="utf-8")
        out, code, _ = run_hook(RESEARCHER, project)
        assert code == 0
        fields = {k.lower() for k in pybtex_parse_file(
            str(bib), bib_format="bibtex").entries["awad2018moral"].fields}
        assert "number" not in fields, (
            "cleaning did not run: a CORE JSON in the dir still disables it")
        assert "Cleaned d1.bib" in out.get(
            "hookSpecificOutput", {}).get("additionalContext", "")


class TestCleanerFailureIsNeverSilent:
    """A crashed cleaner must not read as a clean run (never-silent policy)."""

    def _stub_root(self, tmp_path: Path, cleaner_stdout: str, cleaner_rc: int,
                   validator: str = "echo '{\"valid\": true, \"errors\": []}'") -> Path:
        root = tmp_path / "stub-plugin"
        (root / "bin").mkdir(parents=True)
        run = root / "bin" / "phillit-run"
        run.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            "  *workdir.py) printf '{\"workdir\": \"%s/reviews/test-review\"}\\n' \"$CLAUDE_PROJECT_DIR\" ;;\n"
            "  *researcher_bibs.py) echo '{\"bibs\": [\"d1.bib\"]}' ;;\n"
            f"  *bib_validator.py) {validator} ;;\n"
            f"  *metadata_cleaner.py) {cleaner_stdout}\n"
            f"                        exit {cleaner_rc} ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        run.chmod(0o755)
        return root

    def _run(self, project: Path, root: Path,
             payload: dict = RESEARCHER) -> tuple[dict, int, str]:
        proc = subprocess.run(
            [BASH, str(SCRIPT)], input=json.dumps(payload),
            capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project),
                 "CLAUDE_PLUGIN_ROOT": str(root), "PHILLIT_UV": UV},
        )
        return json.loads(proc.stdout), proc.returncode, proc.stderr

    def _seed(self, project: Path) -> None:
        review = project / "reviews" / "test-review"
        (review / "d1.bib").write_text(VALID_BIB, encoding="utf-8")
        jdir = review / "intermediate_files" / "json"
        jdir.mkdir(parents=True)
        (jdir / "s2.json").write_text(json.dumps(S2_NATURE_JSON), encoding="utf-8")

    _YEAR_FIX = (
        "echo '{\"success\": true, \"total_fields_removed\": 0, "
        "\"entries_cleaned\": 0, \"warnings\": [], \"cleaned_entries\": {}, "
        "\"applied_year_corrections\": [{\"key\": \"k2017\", \"old\": \"2017\", "
        "\"new\": \"2019\", \"source_file\": \"verify_1_k.json\", "
        "\"year_basis\": \"published-print\"}]}'")

    def test_first_pass_block_carries_the_cleaning_report(self, project, tmp_path):
        # The block is this stop's one continuation and the resumed pass
        # sends no report, so a year fix made on the blocked pass must ride
        # in the block reason or it is never shown.
        self._seed(project)
        root = self._stub_root(
            tmp_path, self._YEAR_FIX, 0,
            validator="echo '{\"valid\": false, \"errors\": [\"bad brace\"]}'; exit 1")
        out, code, _ = self._run(project, root)
        assert code == 0 and out.get("decision") == "block"
        assert "bad brace" in out["reason"]
        assert "METADATA CLEANING REPORT" in out["reason"]
        assert "k2017: 2017 -> 2019" in out["reason"]

    def test_resumed_pass_with_syntax_errors_still_names_a_cleaner_failure(
            self, project, tmp_path):
        self._seed(project)
        root = self._stub_root(
            tmp_path, "echo 'boom' >&2", 1,
            validator="echo '{\"valid\": false, \"errors\": [\"bad brace\"]}'; exit 1")
        out, code, _ = self._run(project, root, {**RESEARCHER, "stop_hook_active": True})
        assert code == 0 and "decision" not in out
        assert "bad brace" in out["systemMessage"]
        assert "FAILED for d1.bib" in out["systemMessage"]

    def test_valid_output_with_a_nonzero_exit_fails_closed(self, project, tmp_path):
        self._seed(project)
        root = self._stub_root(
            tmp_path, self._YEAR_FIX, 0,
            validator="echo '{\"valid\": true, \"errors\": []}'; exit 2")
        out, code, _ = self._run(project, root)
        assert code == 0 and out.get("decision") == "block"
        assert "treated as a crash" in out["reason"]

    def test_traceback_is_reported_not_swallowed(self, project, tmp_path):
        self._seed(project)
        root = self._stub_root(
            tmp_path,
            "echo 'Traceback (most recent call last):' >&2; "
            "echo \"AttributeError: 'str' object has no attribute 'get'\" >&2",
            1)
        out, code, stderr = self._run(project, root)
        assert code == 0                              # hook protocol: never exit 2
        assert "metadata_cleaner.py failed" in stderr
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "FAILED for d1.bib" in ctx
        assert "AttributeError" in ctx

    def test_empty_output_is_reported_not_swallowed(self, project, tmp_path):
        # `jq -r '.x // 0'` exits 0 on empty input, so the old code read an
        # empty cleaner result as "0 fields removed".
        self._seed(project)
        root = self._stub_root(tmp_path, "true", 0)
        out, code, stderr = self._run(project, root)
        assert code == 0
        assert "metadata_cleaner.py failed" in stderr
        assert "FAILED for d1.bib" in out.get(
            "hookSpecificOutput", {}).get("additionalContext", "")

    def test_stderr_noise_alongside_valid_json_is_not_a_failure(self, project, tmp_path):
        # uv writes build progress to stderr on a cold venv (see step 1's own
        # comment). Merging that into the result would make every first run
        # look like a crash AND skip cleaning.
        self._seed(project)
        root = self._stub_root(
            tmp_path,
            "echo 'Building phillit-run v0.1 (cold venv)' >&2; "
            "echo '{\"success\": true, \"total_fields_removed\": 0, "
            "\"entries_cleaned\": 0, \"warnings\": [], \"cleaned_entries\": {}}'",
            0)
        out, code, stderr = self._run(project, root)
        assert code == 0
        assert "metadata_cleaner.py failed" not in stderr
        assert out == {}

    def test_valid_json_reporting_failure_is_not_treated_as_success(self, project, tmp_path):
        """The shape metadata_cleaner.main() ACTUALLY emits on an unexpected
        exception: well-formed JSON, success=false, exit 2. A guard that only
        checked JSON validity passed it and then read
        `.total_fields_removed // 0` as "nothing cleaned" -- the crash contract
        and the hook guard defeating each other, restoring the original
        silence -- a defect in the fix itself."""
        self._seed(project)
        root = self._stub_root(
            tmp_path,
            "echo 'Traceback (most recent call last):' >&2; "
            "echo '{\"success\": false, \"errors\": "
            "[\"metadata_cleaner crashed on d1.bib: RuntimeError: boom\"]}'",
            2)
        out, code, stderr = self._run(project, root)
        assert code == 0
        assert "metadata_cleaner.py failed" in stderr
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "FAILED for d1.bib" in ctx
        assert "RuntimeError: boom" in ctx      # the structured .errors[] is surfaced

    def test_failure_on_resumed_pass_is_a_system_message(self, project, tmp_path):
        """A resumed pass sends no additionalContext (it would continue the
        turn again), but a cleaner failure must still not read as a clean
        run: it reaches the user as a systemMessage."""
        self._seed(project)
        root = self._stub_root(
            tmp_path,
            "echo '{\"success\": false, \"errors\": "
            "[\"metadata_cleaner crashed on d1.bib: RuntimeError: boom\"]}'",
            2)
        out, code, _ = self._run(
            project, root, {**RESEARCHER, "stop_hook_active": True})
        assert code == 0
        assert "decision" not in out and "hookSpecificOutput" not in out
        assert "FAILED for d1.bib" in out["systemMessage"]
        assert "RuntimeError: boom" in out["systemMessage"]

    def test_success_on_resumed_pass_allows_silently(self, project, tmp_path):
        """Warnings and removals are first-pass news; a resumed pass with a
        successful cleaner returns {}."""
        self._seed(project)
        root = self._stub_root(
            tmp_path,
            "echo '{\"success\": true, \"total_fields_removed\": 1, "
            "\"entries_cleaned\": 1, \"warnings\": [\"w\"], "
            "\"cleaned_entries\": {\"k\": [\"number\"]}}'",
            0)
        out, code, _ = self._run(
            project, root, {**RESEARCHER, "stop_hook_active": True})
        assert code == 0
        assert out == {}

    def test_non_object_json_is_not_treated_as_success(self, project, tmp_path):
        """`jq -e .` also passes a bare scalar or an unrelated object."""
        self._seed(project)
        root = self._stub_root(tmp_path, "echo '\"just a string\"'", 0)
        out, code, stderr = self._run(project, root)
        assert code == 0
        assert "metadata_cleaner.py failed" in stderr


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as e:  # Windows without Developer Mode or elevation
        pytest.skip(f"symlinks need privileges here: {e}")


def _home_sharing_uv(tmp_path):
    """A fresh HOME for the local work folder whose plugin venvs, uv cache and
    uv-managed Pythons are the REAL ones (symlinked). bin/phillit-run keys its
    venv off $HOME and uv finds its cache and interpreters there, so a bare
    temp HOME would rebuild the environment cold (network) on every test."""
    real = Path.home()
    home = tmp_path / "home"
    (home / ".local").mkdir(parents=True)
    for rel in (".venvs", ".cache", ".local/share"):
        if (real / rel).exists():
            _symlink(home / rel, real / rel)
    return home


def _local_review(tmp_path, monkeypatch_env):
    """A workspace with a LOCAL review, built by the real workdir.py."""
    home = _home_sharing_uv(tmp_path)
    proj = tmp_path / "proj"
    (proj / ".phillit").mkdir(parents=True)
    (proj / ".claude").mkdir()
    (proj / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Edit(~/.local/state/phillit/reviews/**)"]}}),
        encoding="utf-8")
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
           "CLAUDE_CONFIG_DIR": str(home / ".claude")}
    env.pop("PHILLIT_WORKDIR", None)
    r = subprocess.run([sys.executable, str(REPO_ROOT / "skills" / "literature-review" / "scripts" / "workdir.py"),
                        "init", "topic"], cwd=proj, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    monkeypatch_env.update({"HOME": str(home), "USERPROFILE": str(home),
                            "CLAUDE_CONFIG_DIR": str(home / ".claude")})
    return proj, Path(json.loads(r.stdout)["workdir"])


def _run(payload, proj, extra_env, cwd=None):
    payload = with_transcript(payload, proj)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
           "PHILLIT_UV": UV, **extra_env}
    env.pop("PHILLIT_WORKDIR", None)
    proc = subprocess.run([BASH, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=cwd or proj)
    return json.loads(proc.stdout.strip().splitlines()[-1]), proc.returncode, proc.stderr


def test_local_review_bibs_are_validated(tmp_path):
    extra = {}
    proj, workdir = _local_review(tmp_path, extra)
    (workdir / "literature-domain-1.bib").write_text(INVALID_BIB, encoding="utf-8")
    out, code, _ = _run(RESEARCHER, proj, extra)
    assert code == 0
    assert out.get("decision") == "block" and "journal" in out["reason"]


def test_resolver_error_allows_with_a_visible_system_message(tmp_path):
    # A review-state error (here: the local files are missing) allows the stop,
    # since the researcher cannot repair it, but never silently: stderr on
    # exit 0 is never shown, so the skip must ride a systemMessage.
    extra = {}
    proj, workdir = _local_review(tmp_path, extra)
    shutil.rmtree(workdir)
    out, code, _ = _run(RESEARCHER, proj, extra)
    assert code == 0 and "decision" not in out
    msg = out["systemMessage"]
    assert "not on this machine" in msg and "SKIPPED" in msg


def test_resolver_error_on_resumed_pass_is_a_system_message(tmp_path):
    extra = {}
    proj, workdir = _local_review(tmp_path, extra)
    shutil.rmtree(workdir)
    out, code, _ = _run({**RESEARCHER, "stop_hook_active": True}, proj, extra)
    assert code == 0 and "decision" not in out and "SKIPPED" in out["systemMessage"]


def test_resolver_crash_fails_closed(tmp_path):
    extra = {}
    proj, _ = _local_review(tmp_path, extra)
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_text("#!/bin/sh\necho boom >&2\nexit 3\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    extra["PHILLIT_UV"] = str(fake_uv)
    out, code, _ = _run(RESEARCHER, proj, extra)
    assert code == 0
    assert out.get("decision") == "block" and "could not resolve the review directory" in out["reason"]


def test_resolver_crash_on_resumed_pass_is_a_system_message(tmp_path):
    extra = {}
    proj, _ = _local_review(tmp_path, extra)
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    extra["PHILLIT_UV"] = str(fake_uv)
    out, _, _ = _run({**RESEARCHER, "stop_hook_active": True}, proj, extra)
    assert "decision" not in out and "could not resolve" in out["systemMessage"]


@pytest.mark.parametrize("resolver_stdout", [
    "{}",
    '{"workdir": 4}',
    '{"workdir": ""}',
    '{"workdir": "/x", "error": "y"}',
    '[{"workdir": "/x"}]',
    '{"workdir": "/x"}\n{"workdir": "/y"}',
    "",
    "boom",
    '{"error": 5}',
])
def test_malformed_resolver_output_fails_closed(tmp_path, resolver_stdout):
    proj = tmp_path / "proj"
    (proj / ".phillit").mkdir(parents=True)
    root = tmp_path / "stub-plugin"
    (root / "bin").mkdir(parents=True)
    out_file = tmp_path / "resolver-out.txt"
    out_file.write_text(resolver_stdout + "\n", encoding="utf-8")
    run = root / "bin" / "phillit-run"
    run.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$1\" in\n"
        f"  *workdir.py) cat '{out_file}' ;;\n"
        "  *researcher_bibs.py) echo '{\"bibs\": [\"d1.bib\"]}' ;;\n"
        "  *) echo '{\"valid\": true, \"errors\": []}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    run.chmod(0o755)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_PLUGIN_ROOT": str(root),
           "PHILLIT_UV": UV}
    proc = subprocess.run([BASH, str(SCRIPT)], input=json.dumps(RESEARCHER), capture_output=True,
                          text=True, encoding="utf-8", env=env)
    out = json.loads(proc.stdout)
    assert out.get("decision") == "block" and "could not resolve" in out["reason"]


def test_resolver_reads_the_workspace_env(tmp_path):
    # .env sets PHILLIT_WORKDIR=inplace while the review is local: resolve must
    # see that .env (it runs from the workspace) and fail closed on the configuration error.
    extra = {}
    proj, workdir = _local_review(tmp_path, extra)
    (workdir / "literature-domain-1.bib").write_text(INVALID_BIB, encoding="utf-8")
    (proj / ".env").write_text("PHILLIT_WORKDIR=inplace\n", encoding="utf-8")
    out, _, _ = _run(RESEARCHER, proj, extra, cwd=tmp_path)  # the hook's cwd is NOT the workspace
    # The .env pin meets a local review: a configuration error, so the gate
    # blocks loudly instead of skipping validation.
    assert out.get("decision") == "block" and "unset PHILLIT_WORKDIR" in out["reason"]


def test_a_resolved_folder_that_does_not_exist_is_a_system_message(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".phillit").mkdir(parents=True)
    root = tmp_path / "stub-plugin"
    (root / "bin").mkdir(parents=True)
    out_file = tmp_path / "resolver-out.txt"
    missing = (tmp_path / "gone").as_posix()
    out_file.write_text(json.dumps({"workdir": missing}) + "\n", encoding="utf-8")
    run = root / "bin" / "phillit-run"
    run.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$1\" in\n"
        f"  *workdir.py) cat '{out_file}' ;;\n"
        "  *researcher_bibs.py) echo '{\"bibs\": [\"d1.bib\"]}' ;;\n"
        "  *) echo '{\"valid\": true, \"errors\": []}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    run.chmod(0o755)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_PLUGIN_ROOT": str(root),
           "PHILLIT_UV": UV}
    proc = subprocess.run([BASH, str(SCRIPT)], input=json.dumps(RESEARCHER), capture_output=True,
                          text=True, encoding="utf-8", env=env)
    out = json.loads(proc.stdout)
    assert proc.returncode == 0 and "decision" not in out
    assert missing in out["systemMessage"] and "SKIPPED" in out["systemMessage"]


def test_the_stub_resolver_positive_control_allows(tmp_path):
    # The stub harness of the malformed-output test, fed a VALID resolver
    # answer: the hook must get past resolve and validate, so the malformed
    # cases above fail for their shape, not for a broken stub.
    proj = tmp_path / "proj"
    (proj / ".phillit").mkdir(parents=True)
    review = proj / "reviews" / "r"
    review.mkdir(parents=True)
    (review / "d1.bib").write_text(VALID_BIB, encoding="utf-8")
    root = tmp_path / "stub-plugin"
    (root / "bin").mkdir(parents=True)
    out_file = tmp_path / "resolver-out.txt"
    out_file.write_text(json.dumps({"workdir": review.as_posix()}) + "\n", encoding="utf-8")
    run = root / "bin" / "phillit-run"
    run.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$1\" in\n"
        f"  *workdir.py) cat '{out_file}' ;;\n"
        "  *researcher_bibs.py) echo '{\"bibs\": [\"d1.bib\"]}' ;;\n"
        "  *) echo '{\"valid\": true, \"errors\": []}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    run.chmod(0o755)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_PLUGIN_ROOT": str(root),
           "PHILLIT_UV": UV}
    proc = subprocess.run([BASH, str(SCRIPT)], input=json.dumps(RESEARCHER), capture_output=True,
                          text=True, encoding="utf-8", env=env)
    assert json.loads(proc.stdout) == {}


def test_an_invalid_workdir_mode_blocks_instead_of_skipping(tmp_path):
    extra = {}
    proj, workdir = _local_review(tmp_path, extra)
    (workdir / "literature-domain-1.bib").write_text(INVALID_BIB, encoding="utf-8")
    (proj / ".env").write_text("PHILLIT_WORKDIR=lcoal\n", encoding="utf-8")  # a typo
    out, _, _ = _run(RESEARCHER, proj, extra)
    assert out.get("decision") == "block" and "'lcoal'" in out["reason"]


def _crlf_jq(tmp_path: Path) -> dict:
    """PATH with a `jq` that ends every output line in CRLF, as a native
    jq.exe does under Git Bash. pipefail keeps jq's own exit status, which
    the hook's `jq -e` shape checks rely on."""
    shim_dir = tmp_path / "crlf-jq"
    shim_dir.mkdir()
    shim = shim_dir / "jq"
    shim.write_text("#!/usr/bin/env bash\nset -o pipefail\n"
                    f"'{shutil.which('jq')}' \"$@\" | sed 's/$/\\r/'\n", encoding="utf-8")
    shim.chmod(0o755)
    return {"PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"}


def _run_with(payload: dict, project_dir: Path, extra_env: dict, root: Path = REPO_ROOT):
    payload = with_transcript(payload, project_dir)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir),
           "CLAUDE_PLUGIN_ROOT": str(root), "PHILLIT_UV": UV, **extra_env}
    proc = subprocess.run([BASH, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                          text=True, encoding="utf-8", env=env)
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1, proc.stdout     # one decision, never two
    return json.loads(lines[0]), proc.returncode


class TestCrlfJq:
    def test_invalid_bib_still_blocks(self, project, tmp_path):
        (project / "reviews" / "test-review" / "d1.bib").write_text(INVALID_BIB, encoding="utf-8")
        out, code = _run_with(RESEARCHER, project, _crlf_jq(tmp_path))
        assert code == 0 and out.get("decision") == "block"

    def test_resumed_pass_never_reblocks(self, project, tmp_path):
        (project / "reviews" / "test-review" / "d1.bib").write_text(INVALID_BIB, encoding="utf-8")
        out, code = _run_with({**RESEARCHER, "stop_hook_active": True}, project, _crlf_jq(tmp_path))
        assert code == 0 and "decision" not in out and "BibTeX errors remain" in out["systemMessage"]


@pytest.mark.parametrize("validator_stdout", [
    '{"errors": []}', '{"valid": "true"}', '[true]',
    ' ', '\r',                                     # whitespace parses to NO value
    '{"valid": false}\n{"valid": false}',          # two answers, "false<LF>false"
])
def test_validator_output_without_a_boolean_valid_fails_closed(project, tmp_path, validator_stdout):
    (project / "reviews" / "test-review" / "d1.bib").write_text(VALID_BIB, encoding="utf-8")
    out_file = tmp_path / "validator-out.txt"
    out_file.write_text(validator_stdout + "\n", encoding="utf-8")
    root = tmp_path / "stub-plugin"
    (root / "bin").mkdir(parents=True)
    run = root / "bin" / "phillit-run"
    run.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$1\" in\n"
        "  *workdir.py) printf '{\"workdir\": \"%s/reviews/test-review\"}\\n' \"$CLAUDE_PROJECT_DIR\" ;;\n"
        f"  *bib_validator.py) cat '{out_file}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    run.chmod(0o755)
    out, code = _run_with(RESEARCHER, project, {}, root)
    assert code == 0 and out.get("decision") == "block" and "crashed" in out["reason"]


class TestErrTrap:
    """A set -e death would exit nonzero with no JSON: a silent allow. The
    ERR trap turns it into a decision. A failing mktemp is the probe."""

    @staticmethod
    def _failing_mktemp(tmp_path: Path) -> dict:
        shim_dir = tmp_path / "bad-mktemp"
        shim_dir.mkdir()
        shim = shim_dir / "mktemp"
        shim.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        shim.chmod(0o755)
        return {"PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"}

    def test_first_pass_blocks(self, project, tmp_path):
        out, code = _run_with(RESEARCHER, project, self._failing_mktemp(tmp_path))
        assert code == 0 and out.get("decision") == "block" and "failed at line" in out["reason"]

    def test_resumed_pass_allows_visibly(self, project, tmp_path):
        out, code = _run_with({**RESEARCHER, "stop_hook_active": True}, project,
                              self._failing_mktemp(tmp_path))
        assert code == 0 and "decision" not in out and "failed at line" in out["systemMessage"]

    def test_a_failing_report_in_skipped_still_emits_json(self, project, tmp_path):
        # skipped() is a function, so the ERR trap does not cover it: its own
        # || fallback must. The shim fails only jq's output-building calls.
        shim_dir = tmp_path / "bad-jq-cn"
        shim_dir.mkdir()
        shim = shim_dir / "jq"
        shim.write_text("#!/usr/bin/env bash\n[ \"$1\" = -cn ] && exit 1\n"
                        f"exec '{shutil.which('jq')}' \"$@\"\n", encoding="utf-8")
        shim.chmod(0o755)
        (project / "reviews" / ".active-review").unlink()
        out, code = _run_with(RESEARCHER, project,
                              {"PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"})
        assert code == 0 and "decision" not in out and "SKIPPED" in out["systemMessage"]


class TestScopeToTheStoppingResearcher:
    """Researchers run in parallel: one's stop must validate and clean only
    its own bib, never a sibling's that may still be mid-write (the
    2026-10-14 incident: a sibling's year was corrected, and reported, at the wrong
    researcher's stop)."""

    @staticmethod
    def _two_domains(project: Path) -> tuple[Path, Path]:
        review = project / "reviews" / "test-review"
        (review / "s2_results.json").write_text(json.dumps(S2_WRONG_YEAR_JSON), encoding="utf-8")
        (review / "verify_awad.json").write_text(
            json.dumps(VERIFY_AWAD_PRINT_YEAR_JSON), encoding="utf-8")
        mine, sibling = review / "literature-domain-1.bib", review / "literature-domain-2.bib"
        mine.write_text(WRONG_YEAR_BIB, encoding="utf-8")
        sibling.write_text(WRONG_YEAR_BIB, encoding="utf-8")
        return mine, sibling

    @staticmethod
    def _payload(project: Path, prompt: str, written=(), **extra) -> dict:
        t = write_transcript(project / ".transcripts" / "agent-r1.jsonl", prompt, tuple(written))
        return {**RESEARCHER, "agent_transcript_path": str(t), **extra}

    def test_only_the_researchers_own_bib_is_cleaned_and_reported(self, project):
        mine, sibling = self._two_domains(project)
        out, code, _ = run_hook(self._payload(
            project, "Domain: X. Write output to: `/w/literature-domain-1.bib`"), project)
        assert code == 0 and "systemMessage" not in out
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "literature-domain-1.bib" in ctx and "literature-domain-2.bib" not in ctx
        assert "year = {2018}" in mine.read_text(encoding="utf-8")
        assert sibling.read_text(encoding="utf-8") == WRONG_YEAR_BIB    # byte-identical

    def test_a_siblings_half_written_bib_does_not_block_this_researcher(self, project):
        review = project / "reviews" / "test-review"
        (review / "literature-domain-1.bib").write_text(VALID_BIB, encoding="utf-8")
        (review / "literature-domain-2.bib").write_text(INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`"), project)
        assert code == 0 and out == {}

    def test_a_bib_written_with_a_file_tool_is_owned_too(self, project):
        _mine, sibling = self._two_domains(project)
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`",
            written=[str(sibling)]), project)
        assert code == 0
        assert "year = {2018}" in sibling.read_text(encoding="utf-8")

    def test_a_root_stray_of_a_sibling_is_left_alone(self, project):
        (project / "reviews" / "test-review" / "literature-domain-1.bib").write_text(
            VALID_BIB, encoding="utf-8")
        stray = project / "literature-domain-2.bib"
        stray.write_text(INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`"), project)
        assert code == 0 and out == {}
        assert stray.read_text(encoding="utf-8") == INVALID_BIB

    def test_the_researchers_own_root_stray_is_validated(self, project):
        (project / "literature-domain-1.bib").write_text(INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`"), project)
        assert code == 0 and out["decision"] == "block"

    def test_names_match_without_regard_to_case(self, project):
        (project / "reviews" / "test-review" / "literature-domain-1.bib").write_text(
            INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `LITERATURE-DOMAIN-1.BIB`"), project)
        assert code == 0 and out["decision"] == "block"

    def test_an_own_bib_not_written_yet_allows_visibly_and_touches_no_sibling(self, project):
        review = project / "reviews" / "test-review"
        (review / "literature-domain-2.bib").write_text(INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`"), project)
        assert code == 0 and "decision" not in out
        assert "literature-domain-1.bib) was not found" in out["systemMessage"]

    def test_an_assigned_bib_missing_beside_a_written_one_is_reported(self, project):
        mine, sibling = self._two_domains(project)
        mine.unlink()
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`", written=[str(sibling)]), project)
        assert code == 0 and "additionalContext" in out["hookSpecificOutput"]
        assert "(literature-domain-1.bib) was not found" in out["systemMessage"]

    def test_an_output_line_without_the_templates_colon_still_assigns(self, project):
        _mine, sibling = self._two_domains(project)
        out, code, _ = run_hook(self._payload(
            project, "Avoid literature-domain-2.bib.\n"
                     "Write your output to /w/literature-domain-1.bib"), project)
        assert code == 0 and "systemMessage" not in out
        assert sibling.read_text(encoding="utf-8") == WRONG_YEAR_BIB

    def test_the_fallback_tells_the_researcher_too(self, project):
        review = project / "reviews" / "test-review"
        (review / "literature-domain-2.bib").write_text(INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook({**RESEARCHER, "agent_transcript_path": ""}, project)
        assert out["decision"] == "block"
        assert out["reason"].startswith("NOTE: PhilLit could not tell which bib file is yours")

    def test_the_fallback_with_no_bib_at_all_is_not_silent(self, project):
        out, code, _ = run_hook({**RESEARCHER, "agent_transcript_path": "/gone.jsonl"}, project)
        assert code == 0 and "decision" not in out
        assert "no domain bib was found, so nothing was validated" in out["systemMessage"]

    def test_two_owned_bibs_are_both_processed(self, project):
        mine, sibling = self._two_domains(project)
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`", written=[str(sibling)]), project)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "literature-domain-1.bib" in ctx and "literature-domain-2.bib" in ctx

    def test_scoping_survives_a_crlf_jq(self, project, tmp_path):
        mine, sibling = self._two_domains(project)
        out, code = _run_with(self._payload(
            project, "Write output to: `literature-domain-1.bib`"), project, _crlf_jq(tmp_path))
        assert code == 0 and "systemMessage" not in out
        assert "year = {2018}" in mine.read_text(encoding="utf-8")
        assert sibling.read_text(encoding="utf-8") == WRONG_YEAR_BIB

    def test_a_blank_agent_transcript_path_is_derived_from_the_session(self, project):
        mine, sibling = self._two_domains(project)
        session = project / ".transcripts" / "sess.jsonl"
        write_transcript(project / ".transcripts" / "sess" / "subagents" / "agent-abc.jsonl",
                         "Write output to: `literature-domain-1.bib`")
        out, code, _ = run_hook({**RESEARCHER, "agent_transcript_path": "",
                                 "transcript_path": str(session), "agent_id": "abc"}, project)
        assert code == 0 and "systemMessage" not in out
        assert sibling.read_text(encoding="utf-8") == WRONG_YEAR_BIB

    def test_the_resumed_pass_scopes_the_same_way(self, project):
        review = project / "reviews" / "test-review"
        (review / "literature-domain-1.bib").write_text(INVALID_BIB, encoding="utf-8")
        (review / "literature-domain-2.bib").write_text(INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook(self._payload(
            project, "Write output to: `literature-domain-1.bib`", stop_hook_active=True), project)
        assert code == 0 and "decision" not in out
        msg = out["systemMessage"]
        assert "BibTeX errors remain" in msg and "could not tell" not in msg
        assert msg.count("journal") == 1      # domain 1's error only, not domain 2's

    def test_no_transcript_falls_back_to_every_bib_and_says_so(self, project):
        mine, sibling = self._two_domains(project)
        out, code, _ = run_hook({**RESEARCHER, "agent_transcript_path": "/nonexistent/a.jsonl"},
                                project)
        assert code == 0
        assert "could not tell which bib this researcher owns" in out["systemMessage"]
        assert "/nonexistent/a.jsonl" in out["systemMessage"]
        assert "year = {2018}" in sibling.read_text(encoding="utf-8")   # old behaviour
        assert "additionalContext" in out["hookSpecificOutput"]

    def test_the_fallback_note_rides_beside_a_block(self, project):
        (project / "reviews" / "test-review" / "literature-domain-2.bib").write_text(
            INVALID_BIB, encoding="utf-8")
        out, code, _ = run_hook({**RESEARCHER, "agent_transcript_path": ""}, project)
        assert code == 0 and out["decision"] == "block"
        assert "could not tell" in out["systemMessage"]

    def test_the_fallback_note_goes_out_on_a_resumed_pass_too(self, project):
        # A systemMessage does not continue the turn, so a fallback that
        # happens on a resumed pass is never silent either.
        (project / "reviews" / "test-review" / "literature-domain-2.bib").write_text(
            VALID_BIB, encoding="utf-8")
        out, code, _ = run_hook({**RESEARCHER, "agent_transcript_path": "",
                                 "stop_hook_active": True}, project)
        assert code == 0 and "decision" not in out and "hookSpecificOutput" not in out
        assert "could not tell" in out["systemMessage"]

    def test_a_sibling_named_in_the_prompt_is_not_owned(self, project):
        _mine, sibling = self._two_domains(project)
        out, code, _ = run_hook(self._payload(
            project, "Avoid overlap with literature-domain-2.bib.\n"
                     "Write output to: `/w/literature-domain-1.bib`"), project)
        assert code == 0 and "systemMessage" not in out
        assert sibling.read_text(encoding="utf-8") == WRONG_YEAR_BIB

    @pytest.mark.parametrize("helper_stdout", [
        '{"bibs": ["d1.bib"]}\n{"bibs": ["d2.bib"]}',   # two answers
        '{"bibs": [3]}', '{"bibs": ["a/d1.bib"]}', '{"bibs": [""]}', '{"bibs": "d1.bib"}',
    ])
    def test_a_malformed_helper_answer_falls_back_visibly(self, project, tmp_path, helper_stdout):
        review = project / "reviews" / "test-review"
        (review / "d1.bib").write_text(VALID_BIB, encoding="utf-8")
        (review / "d2.bib").write_text(INVALID_BIB, encoding="utf-8")
        out_file = tmp_path / "helper-out.txt"
        out_file.write_text(helper_stdout + "\n", encoding="utf-8")
        root = tmp_path / "stub-plugin"
        (root / "bin").mkdir(parents=True)
        run = root / "bin" / "phillit-run"
        run.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            "  *workdir.py) printf '{\"workdir\": \"%s/reviews/test-review\"}\\n' \"$CLAUDE_PROJECT_DIR\" ;;\n"
            f"  *researcher_bibs.py) cat '{out_file}' ;;\n"
            f"  *) exec bash '{REPO_ROOT}/bin/phillit-run' \"$@\" ;;\n"
            "esac\n", encoding="utf-8")
        run.chmod(0o755)
        out, code = _run_with({**RESEARCHER, "agent_transcript_path": "/x.jsonl"}, project, {}, root)
        assert code == 0 and out["decision"] == "block"          # d2 was validated
        assert "could not tell" in out["systemMessage"]
