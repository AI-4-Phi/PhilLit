#!/usr/bin/env python3
"""Validate .bib content for Write (PreToolUse) and Edit (PostToolUse) calls.

Reads JSON from stdin (Claude Code hook protocol) and dispatches on
hook_event_name + tool_name:

- PreToolUse + Write on a .bib file: validates tool_input.content BEFORE it
  reaches disk. On failure returns hookSpecificOutput with
  permissionDecision "deny" and permissionDecisionReason so the agent can
  fix and retry in the same turn.
- PostToolUse + Edit on a .bib file: validates the file ON DISK (post-edit
  content). On failure returns {"decision": "block", "reason": ...} so the
  errors are fed back to the model.

Anything else returns {} (allow / no opinion). Always exits 0 — decisions
are carried in stdout JSON, never in the exit code.

Only fires for .bib files — zero overhead for other writes/edits.
"""

import json
import sys
import tempfile
from pathlib import Path

# Import validation functions from bib_validator (same directory)
HOOKS_DIR = Path(__file__).parent
sys.path.insert(0, str(HOOKS_DIR))

from bib_validator import (
    check_bibtex_syntax,
    check_duplicate_fields,
    check_duplicate_keys,
    check_latex_escapes,
    check_required_fields,
)


def allow() -> None:
    print(json.dumps({}))


def validate_content(content: str, file_path: str) -> list[str]:
    """Run all bib_validator checks against a content string."""
    errors = []
    errors.extend(check_duplicate_fields(content))
    errors.extend(check_duplicate_keys(content))
    errors.extend(check_latex_escapes(file_path, content))

    # Syntax + required-fields checks need a file on disk
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".bib", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        syntax_errors = check_bibtex_syntax(tmp_path)
        errors.extend(syntax_errors)
        if not syntax_errors:
            errors.extend(check_required_fields(tmp_path))
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    return errors


def handle_write(tool_input: dict) -> None:
    """PreToolUse(Write): validate content before it reaches disk."""
    content = tool_input.get("content", "")
    if not content:
        allow()
        return

    errors = validate_content(content, tool_input.get("file_path", ""))
    if errors:
        reason = "BibTeX validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )
        return
    allow()


def handle_edit(tool_input: dict) -> None:
    """PostToolUse(Edit): validate the post-edit file on disk."""
    file_path = tool_input.get("file_path", "")
    path = Path(file_path)
    if not path.is_file():
        allow()
        return

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        allow()
        return

    errors = validate_content(content, file_path)
    if errors:
        reason = (
            "BibTeX validation failed after Edit of "
            + file_path
            + ":\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return
    allow()


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        allow()
        return

    event = hook_input.get("hook_event_name", "")
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if not tool_input.get("file_path", "").endswith(".bib"):
        allow()
        return

    if event == "PreToolUse" and tool_name == "Write":
        handle_write(tool_input)
    elif event == "PostToolUse" and tool_name == "Edit":
        handle_edit(tool_input)
    else:
        allow()


if __name__ == "__main__":
    main()
