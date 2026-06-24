---
name: setup
description: One-time PhilLit workspace setup — checks uv and jq, scaffolds .env and the .phillit marker, and merges the permission rules into this directory's settings so literature reviews run without per-command prompts. Use when a user first runs PhilLit in a directory, or when reviews prompt repeatedly for Bash.
---

# PhilLit workspace setup

Run this once in the directory where the user will create reviews.

1. **Check uv and jq.** Run `command -v uv` and `command -v jq`. If either is absent,
   tell the user to install it (uv: https://docs.astral.sh/uv/getting-started/installation/ ;
   jq: `brew install jq` / `apt install jq` / `choco install jq`) and stop — `jq` is
   required by the BibTeX-validation hook and is otherwise a silent clean-install failure.
2. **Preview the changes.** Run:
   `bash "$PHILLIT_ROOT/bin/phillit-run" skills/setup/scripts/setup_workspace.py --plugin-root "$PHILLIT_ROOT" --dry-run`
   Show the user the planned `.claude/settings.json` and explain the trust boundary:
   this grants Claude broad `Bash` (plus scoped Write/Edit and deny/ask rules) **in this
   directory**, creates `.phillit/`, and scaffolds `.env`. Nothing is pushed anywhere.
3. **Apply, with consent.** On approval, run the same command without `--dry-run`.
4. **Fill in keys.** Tell the user to edit `.env` (S2_API_KEY, CROSSREF_MAILTO,
   OPENALEX_EMAIL, BRAVE_API_KEY, CORE_API_KEY).
5. **Verify.** Run
   `bash "$PHILLIT_ROOT/bin/phillit-run" skills/philosophy-research/scripts/check_setup.py`
   and report the result.
