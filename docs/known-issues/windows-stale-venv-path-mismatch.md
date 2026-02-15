# Windows: Stale Venv Detection Path Format Mismatch

**Discovered**: 2026-02-15, during investigation of env propagation fix
**Severity**: Low (causes unnecessary venv recreation, no data loss)
**Status**: Fixed
**Platform**: Windows (Git Bash)

## Summary

The stale venv detection in `setup-environment.sh` compares the expected venv path (from `$(pwd)`) with the actual path (from the activate script). On Windows Git Bash, these use incompatible path formats, so the comparison always fails, causing the venv to be deleted and recreated on every session start.

## Root Cause

In `.claude/hooks/setup-environment.sh` (lines 53-69):

```bash
EXPECTED_VENV_PATH="$(pwd)/.venv"
# ...
VENV_PATH=$(grep "^VIRTUAL_ENV=" .venv/Scripts/activate 2>/dev/null | head -1 | cut -d"'" -f2)
if [ -n "$VENV_PATH" ] && [ "$VENV_PATH" != "$EXPECTED_VENV_PATH" ]; then
  echo "Detected stale venv (was at: $VENV_PATH). Recreating..."
  rm -rf .venv
fi
```

- `$(pwd)` in Git Bash returns a POSIX path: `/c/Users/Name/project/.venv`
- The activate script (on Python ≤3.12) contains a Windows path: `C:\Users\Name\project\.venv`
- These never match, so the venv is flagged as "stale" and deleted every session

On Python 3.13.1+, the activate script was fixed to use `cygpath` for conversion (CPython PR #125399), but the path format extracted by `grep`/`cut` may still differ from `$(pwd)` output.

## Impact

- `uv sync` runs unnecessarily on every session start (adds a few seconds)
- No data loss or functional impact — the venv is correctly recreated
- Only affects Windows Git Bash users

## Suggested Fix

Normalize both paths before comparing. Options:

1. Use `cygpath` (available in Git Bash) to convert both to the same format:
   ```bash
   EXPECTED_VENV_PATH="$(cygpath -u "$(pwd)/.venv" 2>/dev/null || echo "$(pwd)/.venv")"
   VENV_PATH=$(grep "^VIRTUAL_ENV=" .venv/Scripts/activate 2>/dev/null | head -1 | cut -d"'" -f2)
   VENV_PATH="$(cygpath -u "$VENV_PATH" 2>/dev/null || echo "$VENV_PATH")"
   ```

2. Or compare only the basename/relative portion of the path, ignoring drive letter format differences.

## Related

- CPython issue [#82764](https://github.com/python/cpython/issues/82764): activate script incorrect for Git Bash
- CPython PR [#125399](https://github.com/python/cpython/pull/125399): Fix path conversion for Git Bash (merged Oct 2024, Python 3.13.1+)
