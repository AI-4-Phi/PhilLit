"""Tests for subagent_stop_bib.sh - SubagentStop BibTeX validation hook.

Pins the Claude Code hook protocol contract:
- ALL decisions are stdout JSON with exit code 0 (JSON is ignored on exit 2).
- Block: {"decision": "block", "reason": <syntax errors>}.
- Cleaning summary: hookSpecificOutput.additionalContext (allow path).
- Backward-compat: validates only when agent_type == domain-literature-researcher
  (settings.json scopes via matcher, but older Claude Code ignores matchers).

The script runs against a temporary CLAUDE_PROJECT_DIR containing copies of
bib_validator.py / metadata_cleaner.py, with $PYTHON overriding venv resolution.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "hooks" / "subagent_stop_bib.sh"
HOOK_DEPS = ["bib_validator.py", "metadata_cleaner.py"]

BASH = shutil.which("bash")
JQ = shutil.which("jq")

pytestmark = pytest.mark.skipif(
    BASH is None or JQ is None, reason="requires bash and jq"
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
    """Temporary CLAUDE_PROJECT_DIR with hook deps and an active review."""
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    for dep in HOOK_DEPS:
        shutil.copy(REPO_ROOT / "hooks" / dep, hooks_dir / dep)

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
        "PYTHON": sys.executable,
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


class TestGuards:
    def test_stop_hook_active_allows(self, project):
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
