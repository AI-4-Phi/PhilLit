#!/usr/bin/env python3
"""PreToolUse hook: block tool-writes to the enrichment/cleaning ledgers.

The ledgers are the *attestation authority* for the evidence tier: an
enrichment-ledger record (`abstract_source` + `abstract_sha256`) is what
grants an entry `EVIDENCE-ABSTRACT`, and a cleaning-ledger record is what
attests `EVIDENCE-EXISTENCE`. Both are plain JSON files inside the workspace,
which made them agent-writable -- forge a record next to a fabricated
abstract and enrichment's prior-ledger fast path skips the fetch that would
have refused attestation, so the barrier stamps the fabrication as fully
citable (ROADMAP item 3 C; `enrich_bibliography.py` says as much in
`_load_prior_ledger`'s docstring).

**Scope, stated exactly** (the external review of 2026-08-05 rejected looser
wording, rightly): this denies ledger writes made through Claude Code's
native file-editing tools. It is NOT a security boundary. A deliberate
forger keeps a complete bypass -- `Bash` is allowed broadly by design, so
`cat > ledger.json`, a heredoc or `python -c` writes the file without ever
reaching a PreToolUse gate. Distinguishing `cat ledger.json` from
`cat > ledger.json` needs real shell parsing, which is the
enumerated-Bash-pattern approach this project records as having failed four
times, and an agent deliberate enough to fabricate an abstract, a source
marker and a matching SHA-256 is not stopped by losing its easiest route. The
value here is against accidental edits and tool-default behaviour, plus the
incidence reduction that comes from closing the cheap path. Symlink/hardlink
aliases and check-then-open races are in the same accepted bucket: creating
one needs Bash. Full residual list and the real closure (barrier-side live
corroboration, routed to phillit-service item 23):
`docs/known-issues/bib-pipeline-integrity-gaps.md` Issue C.

Nothing in the supported pipeline is affected: the designated writers
`enrich_bibliography._update_enrichment_ledger` and
`metadata_cleaner.write_cleaning_ledger` both write from inside Python
(tmp + os.replace), which no hook sees, and no skill or agent prompt mentions
a ledger at all (audited 2026-08-05). Two legitimate operations ARE denied,
deliberately: a developer hand-editing a ledger while debugging, and a file
elsewhere that happens to carry a ledger filename. Recovery goes through the
owning script or `git checkout` -- the latter being a sanctioned non-script
writer, which is why this file avoids claiming "the scripts are the only
writers".

Matching is on the BASENAME only, and that is a deliberate trade against the
review's suggestion to require the `intermediate_files/json/` authority path:
a relative `file_path` written from inside that directory carries no such
prefix, so path-anchoring would open a one-word bypass. Over-blocking a
same-named file elsewhere is the cheaper error.

Reads tool input JSON from stdin (Claude Code hook protocol); exits 0 with
hookSpecificOutput JSON on stdout.

Failure direction: this is an *accuracy* gate, so per CLAUDE.md's gate-failure
policy it fails CLOSED and never silently -- unparseable stdin is denied with
a reason saying the gate could not evaluate the call, rather than allowed
without a word (the review caught that an earlier draft advertised "fail open
but loud" while actually failing open *silently*: the hooks.json `|| echo`
fallback only fires on a nonzero exit, i.e. a uv/process failure, never on a
parse failure). A well-formed payload with no usable `file_path` is not a
failure -- it is a non-candidate -- and is allowed; but if the raw stdin still
contains a ledger-shaped filename in that case (a payload-schema change would
look like this), it is denied rather than waved through.
"""

import json
import posixpath
import re
import sys

# The two names evidence_barrier._load_ledger opens:
#   intermediate_files/json/enrichment_ledger-<bibstem>.json
#   intermediate_files/json/cleaning_ledger-<bibstem>.json
_LEDGER_PREFIXES = ("enrichment_ledger-", "cleaning_ledger-")
# Raw-stdin backstop, used only when no file_path could be extracted.
_LEDGER_ANYWHERE_RE = re.compile(
    r"(?:enrichment|cleaning)_ledger-[^\"'\\/\s]*\.json", re.IGNORECASE
)

_REASON = (
    "PhilLit: refusing to write {name} through a file tool. The enrichment and "
    "cleaning ledgers are the evidence-tier attestation authority, and the "
    "supported pipeline writes them only from inside "
    "enrich_bibliography.py / metadata_cleaner.py. To change a ledger, re-run "
    "the script that owns it; to restore one, use git. A hand-written "
    "attestation would grant a citability tier no fetch ever corroborated "
    "(ROADMAP item 3 C)."
)

_UNEVALUABLE_REASON = (
    "PhilLit: refusing this call because the ledger write-protection gate "
    "could not evaluate it (unreadable hook payload). This gate protects the "
    "evidence-tier attestation ledgers, so it fails closed rather than "
    "allowing an unexaminable write. Re-run the call; if this repeats, the "
    "hook payload format has changed and hooks/block_ledger_write.py needs "
    "updating (ROADMAP item 3 C)."
)


def _deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def is_ledger_path(file_path) -> bool:
    """True when file_path's basename is one of the two ledger filenames.

    Tolerates Windows separators (Claude Code reports native paths and Git
    Bash is supported -- CLAUDE.md, Cross-Platform), matches case-insensitively
    because macOS/Windows filesystems do, and strips a trailing separator so it
    cannot be a one-character bypass.
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False
    basename = posixpath.basename(file_path.replace("\\", "/").rstrip("/")).lower()
    return basename.startswith(_LEDGER_PREFIXES) and basename.endswith(".json")


def main() -> None:
    raw = sys.stdin.read()
    try:
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # Accuracy gate: fail CLOSED and never silently. fast_gate.sh only
        # started us because the payload carried the needle, so an
        # unexaminable call here is a candidate we must not wave through.
        _deny(_UNEVALUABLE_REASON)
        return

    tool_input = hook_input.get("tool_input") if isinstance(hook_input, dict) else None
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None

    if file_path is None:
        # No usable file_path: normally a non-candidate payload shape, so
        # allow. But a schema change would look exactly like this, and then a
        # real ledger write would sail through -- so consult the raw text
        # before allowing. A genuine file write always carries a file_path and
        # never reaches this branch, so a document merely *mentioning* a
        # ledger filename is unaffected.
        if _LEDGER_ANYWHERE_RE.search(raw):
            _deny(_UNEVALUABLE_REASON)
        else:
            json.dump({}, sys.stdout)
        return

    if is_ledger_path(file_path):
        _deny(_REASON.format(
            name=posixpath.basename(str(file_path).replace("\\", "/").rstrip("/"))
        ))
    else:
        json.dump({}, sys.stdout)


if __name__ == "__main__":
    main()
