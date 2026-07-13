---
name: setup
description: One-time PhilLit workspace setup — checks uv and jq, scaffolds .env (pre-filling keys already set in the environment), and merges the permission rules into this directory's settings so literature reviews run without per-command prompts. Use when a user first runs PhilLit in a directory, or when reviews prompt repeatedly for Bash.
---

# PhilLit workspace setup

Run this once in the directory where the user will create reviews.

**Communication style**: keep every user-facing message to a sentence or two of plain,
non-technical language. Do everything you can on the user's behalf; ask only for what
only they can provide.

1. **Open with what this is.** Before running anything, tell the user in 1–2 sentences,
   e.g.: "Let's set up PhilLit in this folder — a one-time step. I'll create the
   configuration for you; I'll only need your email address and one free API key."
2. **Check uv and jq.** Run `command -v uv` and `command -v jq`. If either is absent,
   give a one-line install instruction (uv: https://docs.astral.sh/uv/getting-started/installation/ ;
   jq: `brew install jq` / `apt install jq` / `choco install jq`) and stop — `jq` is
   required by the BibTeX-validation hook and is otherwise a silent clean-install failure.
3. **Preview and ask consent.** Run:
   `bash "$PHILLIT_ROOT/bin/phillit-run" skills/setup/scripts/setup_workspace.py --plugin-root "$PHILLIT_ROOT" --dry-run`
   Then summarize what will happen in 2–3 short bullets — do not dump the settings JSON
   (show it only if the user asks for details):
   - Creates a `.phillit` folder marker and a `.env` file for API keys
   - Lets Claude run PhilLit's research tools **in this folder** without asking permission
     each time; deleting files and system-level commands still require approval
   - Nothing is sent or published anywhere
   Ask whether to proceed.
4. **Apply.** On approval, run the same command without `--dry-run`. The script pre-fills
   `.env` with any keys already set in the user's environment and prints which ones; if it
   found some, tell the user (e.g. "Your Brave key was already set up — I reused it.").
5. **Collect the rest.** Ask only for what is still missing, and be explicit about
   required vs. optional. Edit `.env` yourself with the answers — don't make the user
   open a file.
   - **Required:**
     - `CROSSREF_MAILTO` — just the user's email address; ask for it and fill
       `OPENALEX_EMAIL` with the same address
     - `BRAVE_API_KEY` — the one thing the user must obtain themselves: a free key from
       https://brave.com/search/api/
   - **Optional (skipping is fine):** `S2_API_KEY` (https://www.semanticscholar.org/product/api)
     and `CORE_API_KEY` (https://core.ac.uk/services/api) improve search coverage and speed.
6. **Verify.** Run
   `bash "$PHILLIT_ROOT/bin/phillit-run" skills/philosophy-research/scripts/check_setup.py`
   and report in one line: "Setup complete — ask me for a literature review whenever you're
   ready", or exactly what is still missing and how to fix it.

If Claude still prompts for every command (or PhilLit runs non-interactively), make sure the workspace trust dialog has been accepted — Claude Code ignores `allow` rules in `.claude/settings.json` in untrusted directories.
