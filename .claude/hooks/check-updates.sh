#!/bin/bash
# Check if AI-4-Phi/PhilLit main branch has updates the user hasn't pulled yet.
# Runs as a SessionStart hook — stdout is injected into Claude's context.
# Fails silently on any error so it never blocks session startup.

CANONICAL_REPO="AI-4-Phi/PhilLit"
CACHE_MAX_AGE=3600  # seconds (1 hour)

# Resolve project directory (hooks receive $CLAUDE_PROJECT_DIR; fall back to cwd)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# User opt-out: skip if .phillit-no-update-check exists in the project root
[ -f "$PROJECT_DIR/.phillit-no-update-check" ] && exit 0

# Check that git is available
command -v git &>/dev/null || exit 0

# Verify we're inside a git repository
git rev-parse --git-dir &>/dev/null || exit 0

# Cache file inside .git/ dir — per-repo, per-clone, no multi-user collisions
CACHE_FILE="$(git rev-parse --git-dir)/phillit-update-cache"

# Cache: skip fetch if last check was less than CACHE_MAX_AGE seconds ago
if [ -f "$CACHE_FILE" ]; then
  NOW=$(date +%s)
  # macOS stat uses -f %m, Linux uses -c %Y
  LAST_CHECK=$(stat -f %m "$CACHE_FILE" 2>/dev/null || stat -c %Y "$CACHE_FILE" 2>/dev/null || echo "0")
  if [ $((NOW - LAST_CHECK)) -lt "$CACHE_MAX_AGE" ]; then
    exit 0
  fi
fi

# Find the remote that points to the canonical repo.
# Direct clones: origin = AI-4-Phi/PhilLit
# Forks: origin = user's fork, upstream = AI-4-Phi/PhilLit (may need to be added)
CANONICAL_REMOTE=""
for remote in $(git remote 2>/dev/null); do
  url=$(git remote get-url "$remote" 2>/dev/null)
  # Anchored match: /AI-4-Phi/PhilLit or :AI-4-Phi/PhilLit, optional .git suffix
  if echo "$url" | grep -qEi "(/|:)${CANONICAL_REPO}(\.git)?$"; then
    CANONICAL_REMOTE="$remote"
    break
  fi
done

# If no remote points to the canonical repo, try to auto-add "upstream".
# Only do this if origin URL contains "PhilLit" (i.e., likely a fork, not an unrelated repo).
if [ -z "$CANONICAL_REMOTE" ]; then
  origin_url=$(git remote get-url origin 2>/dev/null) || exit 0
  if echo "$origin_url" | grep -qEi "(/|:)[^/]+/PhilLit(\.git)?$"; then
    git remote add upstream "https://github.com/$CANONICAL_REPO.git" 2>/dev/null || exit 0
    CANONICAL_REMOTE="upstream"
  else
    exit 0
  fi
fi

# Fetch latest main from the canonical remote (non-blocking on network failure)
git fetch "$CANONICAL_REMOTE" main --quiet 2>/dev/null || exit 0

# Update cache timestamp after successful fetch
touch "$CACHE_FILE" 2>/dev/null

# Compare local main to the canonical remote's main
LOCAL=$(git rev-parse main 2>/dev/null) || exit 0
REMOTE=$(git rev-parse "$CANONICAL_REMOTE/main" 2>/dev/null) || exit 0

[ "$LOCAL" = "$REMOTE" ] && exit 0

BEHIND=$(git rev-list --count "main..$CANONICAL_REMOTE/main" 2>/dev/null || echo "0")
[ "$BEHIND" -eq 0 ] && exit 0

# Check if working tree is clean (unstaged or uncommitted changes)
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  DIRTY_WARNING=" The working tree has uncommitted changes -- stash or commit them first."
else
  DIRTY_WARNING=""
fi

# Build the update command using --ff-only (safe: only succeeds on clean fast-forward)
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [ "$CURRENT_BRANCH" = "main" ]; then
  UPDATE_CMD="git pull --ff-only $CANONICAL_REMOTE main"
else
  UPDATE_CMD="git checkout main && git pull --ff-only $CANONICAL_REMOTE main"
fi

cat <<MSG
UPDATE AVAILABLE: A newer version of PhilLit is available ($BEHIND new commit(s)). Ask the user: 'A newer version of PhilLit is available. Do you want to update?' If they agree, run: $UPDATE_CMD$DIRTY_WARNING If they want to disable update checks, run: touch $PROJECT_DIR/.phillit-no-update-check
MSG

exit 0
