#!/usr/bin/env python3
"""Set up a PhilLit review workspace in the current directory.

Creates the .phillit/ marker, scaffolds .env from the plugin's .env.example for any
API keys not already set in the environment (skipped entirely when the environment
has them all), and safely merges PhilLit's permission rules into
./.claude/settings.json (parse, merge, dedupe, back up, write atomically; fail
closed on malformed existing JSON).
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Keys scripts read from .env. Keys already set in the shell environment are left
# there: their values are never copied into .env (the file may sit in a synced or
# committed folder, and — every script calls load_dotenv(find_dotenv(usecwd=True),
# override=True) — a copied value would shadow later key rotations). Their `KEY=`
# lines become comments instead, because an active empty line would override the
# real shell value with "".
ENV_KEYS = ("S2_API_KEY", "CROSSREF_MAILTO", "OPENALEX_EMAIL", "BRAVE_API_KEY", "CORE_API_KEY")

# File permission checks match Edit(path) rules only — Edit rules cover all
# file-editing tools (Write, Edit, NotebookEdit). A Write(path) rule is never
# consulted and triggers a startup warning (verified in Claude Code 2.1.210).
PHILLIT_RULES = {
    "defaultMode": "default",
    "deny": ["Bash(sudo *)", "Bash(dd *)", "Bash(mkfs *)"],
    "allow": [
        "Read", "Grep", "Glob", "WebSearch", "WebFetch", "Bash",
        "Edit(reviews/**)",
        "Skill(phillit:literature-review)", "Skill(phillit:philosophy-research)",
    ],
    "ask": ["Bash(rm *)", "Bash(rmdir *)"],
}

# Rules earlier PhilLit versions shipped that must be removed on re-setup.
# Only PhilLit's own rules go here — user-authored rules are never touched.
OBSOLETE_RULES = {
    "allow": ["Write(reviews/**)"],
}


def _union(existing, new):
    """Existing items first (order preserved), then new items not already present."""
    if existing is None:
        existing = []
    elif isinstance(existing, str):
        # A hand-edited rule list may be a bare string; list() would explode
        # it into single characters.
        existing = [existing]
    out = list(existing)
    for item in new:
        if item not in out:
            out.append(item)
    return out


def merge_permissions(existing: dict, rules: dict) -> dict:
    """Merge `rules` into an existing permissions dict without clobbering user values."""
    merged = dict(existing)
    for key in ("allow", "deny", "ask"):
        union = _union(existing.get(key, []), rules.get(key, []))
        merged[key] = [r for r in union if r not in OBSOLETE_RULES.get(key, [])]
    # Only set defaultMode if the user has not chosen one.
    if "defaultMode" not in merged and "defaultMode" in rules:
        merged["defaultMode"] = rules["defaultMode"]
    return merged


def scaffold_env(example: Path, env_path: Path) -> list[str]:
    """Write .env from .env.example for keys still missing from the environment.

    Keys already set in the environment keep working from there: their `KEY=`
    lines become comments (an active empty line would override the real value
    with ""), and their values are never copied into the file.
    Returns the names of the environment-provided keys.
    """
    inherited = []
    out_lines = []
    for line in example.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped and not stripped.startswith("#") else None
        if key in ENV_KEYS and os.environ.get(key):
            out_lines.append(f"# {key} is read from your environment; set it here only if that changes.")
            inherited.append(key)
        else:
            out_lines.append(line)
    env_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return inherited


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def apply(workspace: Path, plugin_root: Path, dry_run: bool) -> int:
    workspace = Path(workspace)
    plugin_root = Path(plugin_root)
    settings_path = workspace / ".claude" / "settings.json"

    # Read + validate existing settings FIRST so we can fail closed before any writes.
    existing_settings = {}
    if settings_path.exists():
        try:
            existing_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"ERROR: {settings_path} is not valid JSON ({e}). Aborting; nothing changed.",
                  file=sys.stderr)
            return 2
    if not isinstance(existing_settings, dict) or not isinstance(
        existing_settings.get("permissions", {}), dict
    ):
        print(f"ERROR: {settings_path} does not hold a JSON object with an object-valued "
              f'"permissions" key. Aborting; nothing changed.', file=sys.stderr)
        return 2

    merged_perms = merge_permissions(existing_settings.get("permissions", {}), PHILLIT_RULES)
    new_settings = dict(existing_settings)
    new_settings["permissions"] = merged_perms

    inherited = [k for k in ENV_KEYS if os.environ.get(k)]
    missing = [k for k in ENV_KEYS if not os.environ.get(k)]

    if dry_run:
        print("DRY RUN - would create .phillit/, scaffold .env, and write:")
        print(json.dumps(new_settings, indent=2))
        if not missing:
            print("All API keys already set in the environment; would skip .env.")
        elif inherited:
            print(f"Would read from your environment (not copied into .env): {', '.join(inherited)}")
        return 0

    # 1. marker
    (workspace / ".phillit").mkdir(parents=True, exist_ok=True)

    # 2. .env scaffold — only for keys the environment does not already provide,
    # and never overwriting a user's existing .env
    env_path = workspace / ".env"
    example = plugin_root / ".env.example"
    if not env_path.exists() and example.exists():
        if missing:
            inherited = scaffold_env(example, env_path)
            if inherited:
                print(f"Read from your environment (not copied into .env): {', '.join(inherited)}")
        else:
            print("All API keys already set in the environment; skipped creating .env.")

    # 3. settings merge (back up an existing file, then atomic write). Idempotent:
    # when nothing would change, neither rewrite the file nor make a backup — so a
    # re-run never backs up PhilLit's own merged output as if it were pristine.
    # Keep the first backup: a re-run must not overwrite the pristine pre-PhilLit
    # settings with the already-merged file.
    if not settings_path.exists() or new_settings != existing_settings:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = settings_path.with_suffix(".json.bak")
        if settings_path.exists() and not backup_path.exists():
            shutil.copyfile(settings_path, backup_path)
        _atomic_write_json(settings_path, new_settings)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return apply(Path(args.workspace).resolve(), Path(args.plugin_root).resolve(), args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
