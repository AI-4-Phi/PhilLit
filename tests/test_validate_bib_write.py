"""Tests for validate_bib_write.py - BibTeX validation hook.

Pins the Claude Code hook protocol contract:
- PreToolUse(Write): deny via hookSpecificOutput.permissionDecision +
  permissionDecisionReason (exit 0); allow via plain {}.
- PostToolUse(Edit): block via top-level {"decision": "block", "reason"} (exit 0).
The hook must never crash and never exit non-zero on malformed input.
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parent.parent / ".claude" / "hooks" / "validate_bib_write.py"

VALID_BIB = """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971},
  note = {CORE ARGUMENT: Identifies persons with second-order volitions.}
}
"""

# Missing required field `journal` for @article -> check_required_fields error
INVALID_BIB = """@article{wolf1990freedom,
  author = {Wolf, Susan},
  title = {Freedom Within Reason},
  year = {1990}
}
"""


def run_hook(stdin_text: str) -> tuple[dict, int]:
    """Run the hook with stdin text; return (parsed stdout JSON, exit code)."""
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.stdout.strip(), f"hook produced no stdout; stderr: {proc.stderr}"
    return json.loads(proc.stdout), proc.returncode


def write_payload(file_path: str, content: str) -> str:
    return json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )


class TestPreToolUseWrite:
    def test_valid_bib_allows_with_empty_object(self):
        out, code = run_hook(write_payload("reviews/x/literature-domain-1.bib", VALID_BIB))
        assert out == {}
        assert code == 0

    def test_invalid_bib_denies_with_reason(self):
        out, code = run_hook(write_payload("reviews/x/literature-domain-1.bib", INVALID_BIB))
        assert code == 0
        hso = out["hookSpecificOutput"]
        assert hso["hookEventName"] == "PreToolUse"
        assert hso["permissionDecision"] == "deny"
        assert "journal" in hso["permissionDecisionReason"]
        # The old, non-protocol field must be gone
        assert "denyReason" not in hso

    def test_non_bib_file_allows(self):
        out, code = run_hook(write_payload("reviews/x/notes.md", "# not bibtex"))
        assert out == {}
        assert code == 0

    def test_empty_content_allows(self):
        out, code = run_hook(write_payload("reviews/x/literature-domain-1.bib", ""))
        assert out == {}
        assert code == 0

    def test_non_write_tool_allows(self):
        payload = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
        )
        out, code = run_hook(payload)
        assert out == {}
        assert code == 0

    def test_malformed_stdin_allows(self):
        out, code = run_hook("this is not json")
        assert out == {}
        assert code == 0

    def test_non_string_file_path_allows(self):
        payload = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": 123, "content": "x"},
            }
        )
        out, code = run_hook(payload)
        assert out == {}
        assert code == 0

    def test_non_string_content_allows(self):
        payload = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "reviews/x/d1.bib", "content": 123},
            }
        )
        out, code = run_hook(payload)
        assert out == {}
        assert code == 0
