# Windows: `comm` Command May Not Be Available in Git Bash

**Discovered**: 2026-02-15, during investigation of env propagation fix
**Severity**: Medium (if missing, `CLAUDE_ENV_FILE` propagation silently fails)
**Status**: Open
**Platform**: Windows (Git Bash)

## Summary

The `setup-environment.sh` hook uses `comm -13` to diff environment snapshots and write new variables to `$CLAUDE_ENV_FILE`. The `comm` command is part of GNU coreutils, but Git for Windows ships a subset of coreutils. If `comm` is not included in the user's Git Bash installation, the entire environment propagation mechanism fails silently under `set -e`.

## Root Cause

In `.claude/hooks/setup-environment.sh` (line 94):

```bash
comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
```

- Full MSYS2 installations include `comm` via the `coreutils` package
- Git for Windows bundles a slimmed-down MSYS2 runtime — `comm` may or may not be present depending on the Git for Windows version and installation options
- Under `set -e` (line 5 of the script), a missing `comm` causes the script to exit with a non-zero status, and no environment variables are written to `CLAUDE_ENV_FILE`
- The script has no guard or fallback for this case

## Impact

If `comm` is missing:

- No environment variables (venv PATH, VIRTUAL_ENV, .env API keys, `$PYTHON`) are propagated to the session
- The SessionStart hook exits with an error
- Bare `python` may not resolve to the venv python
- API keys may not be available in Bash tool calls (though Python-level `load_dotenv()` still works as a fallback)

## Suggested Fix

Add a guard that checks for `comm` availability and falls back to an alternative approach:

```bash
# Option A: Check for comm and warn
if ! command -v comm &> /dev/null; then
  echo "Warning: 'comm' not found. Environment variables may not propagate to subagents." >&2
  echo "Install MSYS2 coreutils or use a full Git for Windows installation." >&2
  # Fallback: write all current exports to CLAUDE_ENV_FILE (includes pre-existing vars, but functional)
  export -p >> "$CLAUDE_ENV_FILE"
else
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi
```

```bash
# Option B: Use diff instead (more widely available)
diff <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") | grep "^> " | sed 's/^> //' >> "$CLAUDE_ENV_FILE"
```

Option B uses `diff` which is more likely to be available but produces slightly different output format. Option A is simpler but the fallback writes all exports (including pre-existing ones), which is redundant but not harmful.

## How to Verify

On a Windows Git Bash installation:
```bash
command -v comm && echo "comm available" || echo "comm NOT available"
```

## Related

- Git for Windows ships MSYS2 runtime: [git-for-windows/git](https://github.com/git-for-windows/git)
- MSYS2 coreutils package: includes `comm`, `sort`, `cut`, `head`, etc.
