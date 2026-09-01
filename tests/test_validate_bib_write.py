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

HOOK = Path(__file__).parent.parent / "hooks" / "validate_bib_write.py"

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
        # Non-domain-numbered filename: this test is about content
        # validation, not the slug gate (TestSlugFileGate below), and the
        # relative "reviews/x" path here does not exist on disk, so a
        # domain-bib filename would trip the new creation-time slug check.
        out, code = run_hook(write_payload("reviews/x/literature.bib", VALID_BIB))
        assert out == {}
        assert code == 0

    def test_invalid_bib_denies_with_reason(self):
        out, code = run_hook(write_payload("reviews/x/literature.bib", INVALID_BIB))
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
        # Non-domain-numbered filename: this test is about content
        # validation (empty content -> no content errors), not the slug
        # gate (TestSlugFileGate below) -- see test_valid_bib_allows above.
        out, code = run_hook(write_payload("reviews/x/literature.bib", ""))
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


def edit_payload(file_path: str) -> str:
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": "x",
                "new_string": "y",
            },
        }
    )


class TestPostToolUseEdit:
    def test_edit_valid_bib_file_allows(self, tmp_path):
        bib = tmp_path / "literature-domain-1.bib"
        bib.write_text(VALID_BIB, encoding="utf-8")
        out, code = run_hook(edit_payload(str(bib)))
        assert out == {}
        assert code == 0

    def test_edit_invalid_bib_file_blocks_with_reason(self, tmp_path):
        bib = tmp_path / "literature-domain-1.bib"
        bib.write_text(INVALID_BIB, encoding="utf-8")
        out, code = run_hook(edit_payload(str(bib)))
        assert code == 0
        assert out["decision"] == "block"
        assert "journal" in out["reason"]

    def test_edit_missing_file_allows(self, tmp_path):
        out, code = run_hook(edit_payload(str(tmp_path / "nope.bib")))
        assert out == {}
        assert code == 0

    def test_edit_non_bib_file_allows(self, tmp_path):
        md = tmp_path / "notes.md"
        md.write_text("# notes", encoding="utf-8")
        out, code = run_hook(edit_payload(str(md)))
        assert out == {}
        assert code == 0


class TestSlugFileGate:
    """Pins the Stage-1 encyclopedia-slug-file write gate: the Write that
    CREATES a domain bib is denied while its paired
    encyclopedia_entries-domain-<stem>.json is missing or malformed."""

    DEFAULT_CONTENT = (
        "@misc{k2020a,\n  author = {A, B},\n  title = {T},\n"
        "  year = {2020},\n  note = {n},\n}\n"
    )

    def test_domain_bib_without_slug_file_is_denied(self, tmp_path):
        review = tmp_path / "reviews" / "topic"
        review.mkdir(parents=True)
        bib = review / "literature-domain-1.bib"
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        assert code == 0
        hso = out["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        reason = hso["permissionDecisionReason"]
        assert "encyclopedia_entries-domain-1.json" in reason
        assert "sep_entries" in reason  # tells the agent the exact shape

    def test_domain_bib_with_slug_file_is_allowed(self, tmp_path):
        review = tmp_path / "reviews" / "topic"
        slug_dir = review / "intermediate_files" / "json"
        slug_dir.mkdir(parents=True)
        (slug_dir / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8"
        )
        bib = review / "literature-domain-1.bib"
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        assert out == {}
        assert code == 0

    def test_non_domain_bib_is_not_slug_checked(self, tmp_path):
        review = tmp_path / "reviews" / "topic"
        review.mkdir(parents=True)
        out, code = run_hook(
            write_payload(str(review / "literature.bib"), self.DEFAULT_CONTENT)
        )
        assert out == {}
        assert code == 0

    def test_domain_bib_outside_reviews_is_not_slug_checked(self, tmp_path):
        # A stray root bib is its own defect with its own handling
        # (SubagentStop validation); the slug gate must not compound it.
        bib = tmp_path / "literature-domain-1.bib"
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        assert out == {}
        assert code == 0

    def test_named_domain_stem_maps_to_named_slug_file(self, tmp_path):
        review = tmp_path / "reviews" / "topic"
        review.mkdir(parents=True)
        bib = review / "literature-domain-compatibilism.bib"
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "encyclopedia_entries-domain-compatibilism.json" in reason

    def test_slug_error_and_content_errors_are_combined(self, tmp_path):
        review = tmp_path / "reviews" / "topic"
        review.mkdir(parents=True)
        bib = review / "literature-domain-1.bib"
        out, code = run_hook(write_payload(str(bib), "@article{broken,\n"))
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "encyclopedia_entries-domain-1.json" in reason
        # The name promises COMBINATION: the content error must appear too.
        assert "broken" in reason or "syntax" in reason.lower()

    def test_existing_bib_rewrite_without_slug_file_is_allowed(self, tmp_path):
        # Legacy reviews predate the slug-file convention; a fix-up Write
        # over an EXISTING non-empty domain bib must not be held hostage
        # to a research phase that finished long ago. The gate scopes to
        # creation only.
        review = tmp_path / "reviews" / "topic"
        review.mkdir(parents=True)
        bib = review / "literature-domain-1.bib"
        bib.write_text(self.DEFAULT_CONTENT, encoding="utf-8")
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        assert out == {}
        assert code == 0

    def test_empty_placeholder_does_not_bypass_slug_gate(self, tmp_path):
        # A zero-byte file (touch, a crashed earlier run) is not an
        # existing bib -- the creation gate still applies.
        review = tmp_path / "reviews" / "topic"
        review.mkdir(parents=True)
        bib = review / "literature-domain-1.bib"
        bib.write_text("", encoding="utf-8")
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        out_json = out
        assert out_json["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_malformed_slug_file_is_denied(self, tmp_path):
        # Existence is not enough: garbage bytes written under deny
        # pressure must not pass (worse than absent - silently malformed).
        review = tmp_path / "reviews" / "topic"
        slug_dir = review / "intermediate_files" / "json"
        slug_dir.mkdir(parents=True)
        (slug_dir / "encyclopedia_entries-domain-1.json").write_text(
            "not json", encoding="utf-8"
        )
        bib = review / "literature-domain-1.bib"
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "malformed" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_wrong_key_shape_slug_file_is_denied(self, tmp_path):
        review = tmp_path / "reviews" / "topic"
        slug_dir = review / "intermediate_files" / "json"
        slug_dir.mkdir(parents=True)
        (slug_dir / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": "not-a-list"}', encoding="utf-8"
        )
        bib = review / "literature-domain-1.bib"
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_degenerate_stem_is_not_slug_checked(self, tmp_path):
        # "literature-domain-.bib" has an empty stem; the (.+) regex does
        # not match, so only ordinary content validation applies.
        review = tmp_path / "reviews" / "topic"
        review.mkdir(parents=True)
        bib = review / "literature-domain-.bib"
        out, code = run_hook(write_payload(str(bib), self.DEFAULT_CONTENT))
        assert out == {}
        assert code == 0
