#!/usr/bin/env python3
"""Set up a PhilLit review workspace in the current directory.

Creates the .phillit/ marker, scaffolds .env from the plugin's .env.example, and
safely merges PhilLit's permission rules into ./.claude/settings.json (parse, merge,
dedupe, back up, write atomically; fail closed on malformed existing JSON).
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PHILLIT_RULES = {
    "defaultMode": "default",
    "deny": ["Bash(sudo *)", "Bash(dd *)", "Bash(mkfs *)"],
    "allow": [
        "Read", "Grep", "Glob", "WebSearch", "WebFetch", "Bash",
        "Write(reviews/**)", "Edit(reviews/**)",
        "Skill(phillit:literature-review)", "Skill(phillit:philosophy-research)",
    ],
    "ask": ["Bash(rm *)", "Bash(rmdir *)"],
}


def _union(existing, new):
    """Existing items first (order preserved), then new items not already present."""
    out = list(existing)
    for item in new:
        if item not in out:
            out.append(item)
    return out


def merge_permissions(existing: dict, rules: dict) -> dict:
    """Merge `rules` into an existing permissions dict without clobbering user values."""
    merged = dict(existing)
    for key in ("allow", "deny", "ask"):
        merged[key] = _union(existing.get(key, []), rules.get(key, []))
    # Only set defaultMode if the user has not chosen one.
    if "defaultMode" not in merged and "defaultMode" in rules:
        merged["defaultMode"] = rules["defaultMode"]
    return merged


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

    merged_perms = merge_permissions(existing_settings.get("permissions", {}), PHILLIT_RULES)
    new_settings = dict(existing_settings)
    new_settings["permissions"] = merged_perms

    if dry_run:
        print("DRY RUN - would create .phillit/, scaffold .env, and write:")
        print(json.dumps(new_settings, indent=2))
        return 0

    # 1. marker
    (workspace / ".phillit").mkdir(parents=True, exist_ok=True)

    # 2. .env scaffold (never overwrite a user's .env)
    env_path = workspace / ".env"
    example = plugin_root / ".env.example"
    if not env_path.exists() and example.exists():
        shutil.copyfile(example, env_path)

    # 3. settings merge (back up an existing file, then atomic write)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.exists():
        shutil.copyfile(settings_path, settings_path.with_suffix(".json.bak"))
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
