#!/bin/bash
# PhilLit plugin SessionStart bootstrap.
# Plugin hooks fire in EVERY session, so this stays cheap and benign: it bridges a few
# env vars into $CLAUDE_ENV_FILE for later Bash tool calls (main session + subagents).
# No venv build, no .env load, no package checks.
set -e

# Overridable list of fallback dirs to locate uv (Homebrew, uv's own installer).
# No-colon `=` so an explicitly-empty value (PHILLIT_BREW_DIRS="") disables the
# fallback — used by tests. Keep in sync with bin/phillit-run, which self-resolves
# uv with the same list (hook processes never see $CLAUDE_ENV_FILE exports).
: "${PHILLIT_BREW_DIRS=/opt/homebrew/bin /usr/local/bin $HOME/.local/bin}"

# CLAUDE_ENV_FILE is only present during SessionStart; without it we cannot bridge.
[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0

# Is the current directory an activated PhilLit workspace?
ACTIVE=0
if [ -d "${CLAUDE_PROJECT_DIR:-$PWD}/.phillit" ]; then
  ACTIVE=1
fi

# Bridge PHILLIT_ROOT (and ACTIVE) FIRST and unconditionally: /phillit:setup invokes the
# wrapper via "$PHILLIT_ROOT/bin/phillit-run" BEFORE the .phillit marker or uv exist, so
# this must not depend on uv. Harmless in unrelated projects (an unused env var).
{
  printf 'export PHILLIT_ROOT=%q\n' "${CLAUDE_PLUGIN_ROOT:-}"
  if [ "$ACTIVE" -eq 1 ]; then printf 'export PHILLIT_ACTIVE=1\n'; fi
} >> "$CLAUDE_ENV_FILE"

# Resolve uv: PATH first, then the Homebrew fallback dirs.
UV_PATH="$(command -v uv 2>/dev/null || true)"
if [ -z "$UV_PATH" ]; then
  for d in $PHILLIT_BREW_DIRS; do
    if [ -x "$d/uv" ]; then UV_PATH="$d/uv"; break; fi
  done
fi

# Missing uv: warn only inside an active workspace; never nag unrelated projects.
if [ -z "$UV_PATH" ]; then
  if [ "$ACTIVE" -eq 1 ]; then
    echo "PhilLit: 'uv' not found - literature reviews cannot run. Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
  fi
  exit 0
fi

# Bridge the resolved uv path so hooks/scripts find it regardless of a minimal hook PATH.
printf 'export PHILLIT_UV=%q\n' "$UV_PATH" >> "$CLAUDE_ENV_FILE"

if [ "$ACTIVE" -eq 1 ]; then
  echo "PhilLit ready (uv: $UV_PATH)."
fi
exit 0
