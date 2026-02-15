#!/bin/bash
# Literature Review Environment Setup
# Activates uv-managed virtual environment for all bash commands in this session

set -e

# Add homebrew to PATH (for uv installed via homebrew)
if [ -d "/opt/homebrew/bin" ]; then
  export PATH="/opt/homebrew/bin:$PATH"
elif [ -d "/usr/local/bin" ]; then
  export PATH="/usr/local/bin:$PATH"
fi

# Load environment variables from .env file (overrides existing environment)
load_dotenv() {
  local env_file="$1"
  [ -f "$env_file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    # Match KEY=VALUE pattern
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

# Verify CLAUDE_ENV_FILE is available (only present in SessionStart hooks)
if [ -z "$CLAUDE_ENV_FILE" ]; then
  echo "Environment setup failed: CLAUDE_ENV_FILE not available. This hook should only run during SessionStart events." >&2
  exit 2
fi

# Verify uv is installed
if ! command -v uv &> /dev/null; then
  echo "Environment setup failed: uv is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 2
fi

# Detect stale venv (created at a different path) and recreate if necessary
EXPECTED_VENV_PATH="$(pwd)/.venv"
if [ -f ".venv/bin/activate" ]; then
  # Unix: extract VIRTUAL_ENV path from activate script
  VENV_PATH=$(grep "^VIRTUAL_ENV=" .venv/bin/activate 2>/dev/null | head -1 | cut -d"'" -f2)
  if [ -n "$VENV_PATH" ] && [ "$VENV_PATH" != "$EXPECTED_VENV_PATH" ]; then
    echo "Detected stale venv (was at: $VENV_PATH). Recreating..."
    rm -rf .venv
  fi
elif [ -f ".venv/Scripts/activate" ]; then
  # Windows: extract VIRTUAL_ENV path from activate script
  # Normalize both paths with cygpath — $(pwd) returns POSIX paths (/c/Users/...)
  # but the activate script contains Windows paths (C:\Users\...), so they never
  # match without conversion.
  VENV_PATH=$(grep "^VIRTUAL_ENV=" .venv/Scripts/activate 2>/dev/null | head -1 | cut -d"'" -f2)
  VENV_PATH="$(cygpath -u "$VENV_PATH" 2>/dev/null || echo "$VENV_PATH")"
  EXPECTED_VENV_PATH="$(cygpath -u "$EXPECTED_VENV_PATH" 2>/dev/null || echo "$EXPECTED_VENV_PATH")"
  if [ -n "$VENV_PATH" ] && [ "$VENV_PATH" != "$EXPECTED_VENV_PATH" ]; then
    echo "Detected stale venv (was at: $VENV_PATH). Recreating..."
    rm -rf .venv
  fi
fi

# Capture environment state before activation
ENV_BEFORE=$(export -p | sort)

# Load project .env file (after ENV_BEFORE so diff captures these vars for CLAUDE_ENV_FILE)
load_dotenv ".env"

# Sync environment (creates .venv and uv.lock if needed)
if ! uv sync --quiet 2>/dev/null; then
  echo "Environment setup failed: uv sync failed. Check pyproject.toml and try running 'uv sync' manually." >&2
  exit 2
fi

# Activate the virtual environment (cross-platform: Windows uses Scripts/, Unix uses bin/)
if [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
else
  echo "Environment setup failed: .venv activation script not found after uv sync." >&2
  exit 2
fi

# Set cross-platform $PYTHON path (captured by ENV_AFTER diff → CLAUDE_ENV_FILE)
if [ -f ".venv/Scripts/python" ]; then
  export PYTHON=".venv/Scripts/python"
else
  export PYTHON=".venv/bin/python"
fi

# Capture environment state after activation
ENV_AFTER=$(export -p | sort)

# Persist only new/changed environment variables
comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"

# Check critical packages
MISSING_PACKAGES=""
check_package() {
  local pkg_name="$1"
  local import_name="$2"
  if ! python -c "import $import_name" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES $pkg_name"
  fi
}

check_package "beautifulsoup4" "bs4"
check_package "lxml" "lxml"
check_package "arxiv" "arxiv"
check_package "requests" "requests"
check_package "pybtex" "pybtex"
check_package "pymarkdownlnt" "pymarkdown"
check_package "pyyaml" "yaml"
check_package "python-dotenv" "dotenv"

if [ -n "$MISSING_PACKAGES" ]; then
  echo "Environment setup failed: Missing packages:$MISSING_PACKAGES. Run 'uv sync' to install dependencies." >&2
  exit 2
fi

# Check system tools required by hooks
if ! command -v jq &> /dev/null; then
  echo "Warning: jq not installed. SubagentStop hook requires jq for BibTeX validation." >&2
  echo "Install with: brew install jq (macOS), apt install jq (Linux), or choco install jq (Windows)" >&2
fi

# Success: output context for Claude (stdout is added to Claude's context)
echo "Python environment ready: $(python --version 2>&1), venv at .venv/"
exit 0
