#!/bin/bash
# PhilReview Beta Testing Launcher
#
# This script sources your .env file before starting Claude Code,
# ensuring telemetry and credentials are properly configured.
#
# Usage: ./start-claude.sh

set -e

# Change to script directory so .env lookup works regardless of where user invokes this
cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
  echo "Error: .env file not found in $(pwd)"
  echo ""
  echo "Please copy your personalized .env file (provided by the research team)"
  echo "to this directory before running PhilReview."
  exit 1
fi

# Load .env safely (parse KEY=VALUE only, don't execute arbitrary commands)
# This mirrors the safe parsing in setup-environment.sh and submit_results.py
load_dotenv() {
  local env_file="$1"
  [ -f "$env_file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    # Match KEY=VALUE pattern only
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local value="${BASH_REMATCH[2]}"

      # Strip surrounding quotes (single or double)
      if [[ "$value" =~ ^\"(.*)\"$ ]] || [[ "$value" =~ ^\'(.*)\'$ ]]; then
        value="${BASH_REMATCH[1]}"
      fi

      export "$key=$value"
    fi
  done < "$env_file"
}

load_dotenv ".env"

# Run claude (the global command)
exec claude "$@"
