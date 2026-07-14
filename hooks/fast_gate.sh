#!/usr/bin/env bash
# Cheap shell pre-filter in front of the per-call uv-backed gates (PreToolUse/
# PostToolUse). These hooks fire on EVERY matched tool call in a session, so
# they must not pay uv startup (or a cold venv build, which can exceed the 60 s
# hook timeout) for calls that cannot concern them.
#
# Usage (hooks.json): fast_gate.sh <needle> <root-relative-script>
# Exits 0 (allow) without starting uv unless BOTH hold:
#   - the cwd is a PhilLit workspace (.phillit marker), and
#   - the hook's stdin JSON contains <needle> literally. The needle is an
#     over-approximation: a miss can never need blocking (a .bib file_path must
#     contain ".bib"; the background gate only blocks run_in_background=true),
#     while a spurious hit just means the Python gate decides properly.
# On a hit, pipes the captured stdin into the gate via bin/phillit-run and
# propagates its exit status, so hooks.json's `|| echo` fail-open fallback
# still fires on uv failure (gate-failure policy: plumbing fails open + loud).

if [ ! -d "${CLAUDE_PROJECT_DIR:-$PWD}/.phillit" ]; then
  exit 0
fi

if [ "$#" -ne 2 ]; then
  # Mis-wired hooks.json (pinned by tests). Fail open but never silent.
  echo '{"systemMessage": "PhilLit: fast_gate.sh called with wrong arguments - the gate was skipped."}'
  exit 0
fi

NEEDLE="$1"
SCRIPT="$2"
INPUT="$(cat)"

case "$INPUT" in
  *"$NEEDLE"*)
    HOOKS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
    printf '%s' "$INPUT" | bash "$HOOKS_DIR/../bin/phillit-run" "$SCRIPT"
    ;;
esac
