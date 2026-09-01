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
import re
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

# Pairing rule for the Stage 1 encyclopedia slug file. Prose alone measured
# 2-of-8 researchers non-compliant (service run d474e00d140a4b10), so the
# requirement is enforced here: the Write that CREATES a domain bib is the
# one moment the writer is unambiguously the domain owner. Case-insensitive
# like the .bib suffix check below.
_DOMAIN_BIB_RE = re.compile(r"^literature-domain-(.+)\.bib$", re.IGNORECASE)


def check_slug_file(file_path: str) -> list[str]:
    """Deny-reason list for a domain-bib Write whose paired
    encyclopedia_entries-domain-<stem>.json is missing or malformed. Empty
    when the gate does not apply (not a domain bib, not under reviews/) or
    the slug file exists with the required shape.

    Shape is validated, not just existence: a deny at bib-write time lands
    AFTER discovery is done, which is when dashing off garbage bytes is most
    tempting - requiring parseable JSON with both list keys closes that.
    Empty lists still pass (the sanctioned "looked, found nothing").
    ACCEPTED RESIDUALS: an agent can still fabricate empty lists (the deny
    text forbids it; not mechanically checkable), and the gate covers the
    Write tool only - a bib created via Bash bypasses it (same stance as
    block_ledger_write: a compliance gate, not a security boundary). The
    gate keys on the NAME PATTERN literature-domain-*.bib, so a lookalike
    scratch file (literature-domain-notes.bib) under reviews/ is gated too -
    deliberate (multi-form stems are real), and the deny message makes
    recovery obvious."""
    p = Path(file_path)
    m = _DOMAIN_BIB_RE.match(p.name)
    # "reviews" check is case-sensitive and positional-agnostic by intent:
    # the workflow always creates a lowercase reviews/ directory.
    if not m or "reviews" not in p.parts:
        return []
    try:
        existing_size = p.stat().st_size
    except OSError:
        existing_size = 0
    if existing_size > 0:
        # A NON-EMPTY bib already exists: this is a rewrite, not the
        # creation the gate scopes to (the enforcement moment is the
        # researcher's FIRST real Write, when discovery context is live).
        # Without this, every fix-up Write on a legacy review that
        # predates the slug-file convention is denied for a research
        # phase long finished. An EMPTY file does not count as existing -
        # a zero-byte placeholder (touch, a crashed earlier run) must not
        # become a permanent bypass of the gate.
        return []
    slug = (p.parent / "intermediate_files" / "json"
            / ("encyclopedia_entries-domain-" + m.group(1) + ".json"))
    shape = ('{"sep_entries": [...], "iep_entries": [...]} listing the '
             "slugs of every SEP/IEP entry you discovered - empty lists "
             "ONLY if you truly found none")
    if not slug.is_file():
        return [
            "missing encyclopedia slug file (Stage 1 requirement): first "
            "Write " + slug.as_posix() + " with " + shape
            + ", then retry this Write."
        ]
    try:
        data = json.loads(slug.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None

    def _slug_list(v):
        return (isinstance(v, list)
                and all(isinstance(s, str) and s.strip() for s in v))

    if (not isinstance(data, dict)
            or not _slug_list(data.get("sep_entries"))
            or not _slug_list(data.get("iep_entries"))):
        return [
            "malformed encyclopedia slug file " + slug.as_posix()
            + ": rewrite it as " + shape
            + " (every element a nonempty string), then retry this Write."
        ]
    return []


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
    file_path = tool_input.get("file_path", "")
    errors = check_slug_file(file_path)
    content = tool_input.get("content", "")
    if isinstance(content, str) and content:
        errors.extend(validate_content(content, file_path))
    if errors:
        # "Bib write denied" (not "BibTeX validation failed"): errors here can
        # come from check_slug_file, a Stage 1 compliance gate, not a BibTeX
        # defect - the old header was false for that class of deny.
        reason = "Bib write denied:\n" + "\n".join(f"  - {e}" for e in errors)
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

    file_path = tool_input.get("file_path", "")
    # Case-insensitive suffix: macOS/Windows filesystems are case-insensitive,
    # so "LITERATURE.BIB" is the same file as "literature.bib" and must not
    # skip validation (found alongside the fast_gate needle fix, 2026-08-05).
    if not isinstance(file_path, str) or not file_path.lower().endswith(".bib"):
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
