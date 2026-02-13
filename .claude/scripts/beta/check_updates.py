#!/usr/bin/env python3
"""
SessionStart hook for PhilReview beta testing.

Checks for and applies updates from the beta-testing branch at session start.

Behavior:
1. Check if on beta-testing branch; skip if not
2. Check for uncommitted changes; skip if any
3. Fetch from origin
4. If behind: git pull --ff-only
5. Print current git short hash (PHILREVIEW_VERSION)
6. If pyproject.toml or uv.lock changed: run uv sync

Note: Environment variables set in subprocesses don't persist to the parent.
The version is read directly from git by submit_results.py at upload time.
"""

import os
import subprocess
import sys
from pathlib import Path


def get_script_dir() -> Path:
    """Get directory containing this script."""
    return Path(__file__).resolve().parent


def get_project_root() -> Path:
    """Get project root (3 levels up from .claude/scripts/beta/)."""
    return get_script_dir().parent.parent.parent


def run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.SubprocessError as e:
        return 1, "", str(e)


def get_current_branch(cwd: Path) -> str | None:
    """Get current git branch name."""
    code, stdout, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return stdout if code == 0 else None


def has_uncommitted_changes(cwd: Path) -> bool:
    """Check if there are uncommitted changes."""
    code, stdout, _ = run_git(["status", "--porcelain"], cwd)
    return code == 0 and bool(stdout)


def get_short_hash(cwd: Path) -> str:
    """Get current commit short hash."""
    code, stdout, _ = run_git(["rev-parse", "--short", "HEAD"], cwd)
    return stdout if code == 0 else "unknown"


def fetch_origin(cwd: Path) -> bool:
    """Fetch from origin."""
    code, _, _ = run_git(["fetch", "origin"], cwd)
    return code == 0


def is_behind_origin(branch: str, cwd: Path) -> bool:
    """Check if local branch is behind origin."""
    code, stdout, _ = run_git(
        ["rev-list", "--count", f"HEAD..origin/{branch}"],
        cwd
    )
    if code != 0:
        return False
    try:
        return int(stdout) > 0
    except ValueError:
        return False


def get_changed_files_after_pull(cwd: Path) -> set[str]:
    """Get files that would change after a pull."""
    code, stdout, _ = run_git(["diff", "--name-only", "HEAD", "origin/beta-testing"], cwd)
    if code != 0:
        return set()
    return set(stdout.split("\n")) if stdout else set()


def pull_ff_only(cwd: Path) -> bool:
    """Perform git pull --ff-only."""
    code, stdout, stderr = run_git(["pull", "--ff-only"], cwd)
    if code != 0:
        print(f"Warning: git pull failed: {stderr}", file=sys.stderr)
        return False
    return True


def run_uv_sync(cwd: Path) -> bool:
    """Run uv sync to update dependencies."""
    try:
        result = subprocess.run(
            ["uv", "sync"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            print(f"Warning: uv sync failed: {result.stderr}", file=sys.stderr)
            return False
        return True
    except subprocess.SubprocessError as e:
        print(f"Warning: uv sync error: {e}", file=sys.stderr)
        return False


def export_version(version: str) -> None:
    """Export PHILREVIEW_VERSION environment variable.

    Note: Environment variables set in a subprocess don't persist to the parent.
    The calling hook system needs to handle this. We print for visibility and
    write to a file that can be sourced.
    """
    print(f"PhilReview version: {version}")

    # Write version to a file that the hook system can source
    version_file = get_script_dir() / ".version"
    try:
        version_file.write_text(f"export PHILREVIEW_VERSION={version}\n")
    except OSError:
        pass


def main() -> int:
    """Main entry point."""
    project_root = get_project_root()

    # Check if on beta-testing branch
    branch = get_current_branch(project_root)
    if branch != "beta-testing":
        # Not on beta-testing branch, skip update check
        export_version(get_short_hash(project_root))
        return 0

    # Check for uncommitted changes
    if has_uncommitted_changes(project_root):
        print("Note: Uncommitted changes detected, skipping auto-update")
        export_version(get_short_hash(project_root))
        return 0

    # Fetch from origin
    print("Checking for updates...")
    if not fetch_origin(project_root):
        print("Warning: Could not fetch from origin", file=sys.stderr)
        export_version(get_short_hash(project_root))
        return 0

    # Check if behind
    if not is_behind_origin("beta-testing", project_root):
        print("Already up to date")
        export_version(get_short_hash(project_root))
        return 0

    # Get files that will change
    changed_files = get_changed_files_after_pull(project_root)
    needs_sync = "pyproject.toml" in changed_files or "uv.lock" in changed_files

    # Pull updates
    print("Updating from beta-testing branch...")
    if not pull_ff_only(project_root):
        export_version(get_short_hash(project_root))
        return 1

    print("Update complete")

    # Run uv sync if needed
    if needs_sync:
        print("Dependencies changed, running uv sync...")
        if run_uv_sync(project_root):
            print("Dependencies updated")
        else:
            print("Warning: Dependency update may have failed", file=sys.stderr)

    export_version(get_short_hash(project_root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
