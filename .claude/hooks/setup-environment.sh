#!/bin/bash
# Literature Review Environment Setup
# Activates uv-managed virtual environment for all bash commands in this session

set -e

# Add homebrew to PATH (for uv installed via homebrew)
# Check common homebrew locations
if [ -d "/opt/homebrew/bin" ]; then
  export PATH="/opt/homebrew/bin:$PATH"
elif [ -d "/usr/local/bin" ]; then
  export PATH="/usr/local/bin:$PATH"
fi

echo "🔧 Setting up Python environment with uv..." >&2

# Verify CLAUDE_ENV_FILE is available (only present in SessionStart hooks)
if [ -z "$CLAUDE_ENV_FILE" ]; then
  echo "⚠️  Warning: CLAUDE_ENV_FILE not available" >&2
  echo "   This hook should only run during SessionStart events" >&2
  exit 1
fi

# Verify uv is installed
if ! command -v uv &> /dev/null; then
  echo "❌ Error: uv is not installed" >&2
  echo "   Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "   Or visit: https://github.com/astral-sh/uv" >&2
  exit 1
fi

# Capture environment state before activation
ENV_BEFORE=$(export -p | sort)

# Sync environment from lockfile
# This creates .venv if needed and installs all dependencies from uv.lock
echo "  Syncing environment from lockfile..." >&2
uv sync --frozen --quiet

# Activate the virtual environment
source .venv/bin/activate

# Capture environment state after activation
ENV_AFTER=$(export -p | sort)

# Persist only new/changed environment variables
comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"

# Verify activation
echo "✓ Virtual environment activated" >&2
echo "  Python: $(which python)" >&2
echo "  Python version: $(python --version 2>&1)" >&2

# Check critical packages (package_name:import_name)
echo "  Checking dependencies..." >&2
PACKAGES_OK=true

check_package() {
  local pkg_name="$1"
  local import_name="$2"
  if python -c "import $import_name" 2>/dev/null; then
    VERSION=$(python -c "import $import_name; print($import_name.__version__)" 2>/dev/null || echo "unknown")
    echo "    ✓ $pkg_name: $VERSION" >&2
  else
    echo "    ✗ $pkg_name: NOT INSTALLED" >&2
    PACKAGES_OK=false
  fi
}

check_package "beautifulsoup4" "bs4"
check_package "lxml" "lxml"
check_package "pyalex" "pyalex"
check_package "arxiv" "arxiv"
check_package "requests" "requests"

if [ "$PACKAGES_OK" = false ]; then
  echo "" >&2
  echo "⚠️  Warning: Some required packages are missing" >&2
  echo "   Run: uv sync" >&2
  exit 1
fi

echo "✓ Environment setup complete" >&2
exit 0
