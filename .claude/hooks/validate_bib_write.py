#!/usr/bin/env python3
"""PreToolUse hook: Validate .bib content before Write tool commits to disk.

Reads JSON from stdin (Claude Code PreToolUse protocol), checks if the Write
target is a .bib file, and validates the content using bib_validator checks.
Returns hookSpecificOutput with permissionDecision "deny" on validation failure
so the agent can fix and retry in the same turn.

Only fires for .bib files — zero overhead for other writes.
"""

import json
import sys
import tempfile
from pathlib import Path

# Import validation functions from bib_validator (same directory)
HOOKS_DIR = Path(__file__).parent
sys.path.insert(0, str(HOOKS_DIR))

from bib_validator import (
    check_duplicate_fields,
    check_duplicate_keys,
    check_latex_escapes,
)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        # Not valid JSON — allow (don't block non-Write calls)
        print(json.dumps({"hookSpecificOutput": {}}))
        return

    # Extract tool name and parameters
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only process Write tool calls
    if tool_name != "Write":
        print(json.dumps({"hookSpecificOutput": {}}))
        return

    file_path = tool_input.get("file_path", "")

    # Only process .bib files
    if not file_path.endswith(".bib"):
        print(json.dumps({"hookSpecificOutput": {}}))
        return

    content = tool_input.get("content", "")
    if not content:
        print(json.dumps({"hookSpecificOutput": {}}))
        return

    # Run pre-parse validation checks on the content string
    errors = []
    errors.extend(check_duplicate_fields(content))
    errors.extend(check_duplicate_keys(content))
    errors.extend(check_latex_escapes(file_path, content))

    # Also validate BibTeX syntax by writing to a temp file and parsing
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".bib", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        from bib_validator import check_bibtex_syntax, check_required_fields

        syntax_errors = check_bibtex_syntax(tmp_path)
        errors.extend(syntax_errors)

        if not syntax_errors:
            errors.extend(check_required_fields(tmp_path))
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    if errors:
        reason = "BibTeX validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "denyReason": reason,
                    }
                }
            )
        )
        return

    # Valid — allow the write
    print(json.dumps({"hookSpecificOutput": {}}))


if __name__ == "__main__":
    main()
