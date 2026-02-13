# Beta Testing Scripts

Internal scripts for PhilReview beta testing infrastructure.

## Scripts

### `check_updates.py`

SessionStart hook that checks for and applies updates from the beta-testing branch.

**Behavior:**
1. Checks if on beta-testing branch (skips if not)
2. Checks for uncommitted changes (skips if any)
3. Fetches from origin
4. If behind: runs `git pull --ff-only`
5. Prints current git short hash (PHILREVIEW_VERSION)
6. If pyproject.toml or uv.lock changed: runs `uv sync`

Note: PHILREVIEW_VERSION is read directly from git by submit_results.py at upload time, as environment variables from hooks don't persist.

### `submit_results.py`

Stop hook that detects completed reviews and uploads data for analysis.

**Behavior:**
1. Checks for `.philreview_complete` marker in any `reviews/*/` directory
2. If no marker: exits silently (normal case)
3. If marker found:
   - Uploads `*.md` and `*.bib` files to B2
   - Uploads metadata.json with review_id, tester_id, version, status
   - Deletes marker after successful upload
   - Prompts for survey feedback

## Files

- `state.json` - Persistent state for survey timing (gitignored)
- `metadata_temp.json` - Temporary file during upload (gitignored)
- `.version` - Current version export (gitignored)

## Environment Variables

See `README-BETA-TESTERS.md` in the project root for the full list of required environment variables.
