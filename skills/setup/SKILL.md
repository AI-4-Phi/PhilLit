---
name: setup
description: One-time PhilLit workspace setup — checks uv and jq, scaffolds .env for any API keys not already set in the environment, optionally connects the user's own Zotero or PDF folder, and merges the permission rules into this directory's settings so literature reviews run without per-command prompts. Use when a user first runs PhilLit in a directory, or when reviews prompt repeatedly for Bash.
---

# PhilLit workspace setup

Run this once in the directory where the user will create reviews.

**Communication style**: keep every user-facing message to a sentence or two of plain,
non-technical language. Do everything you can on the user's behalf; ask only for what
only they can provide.

1. **Open with what this is.** Before running anything, tell the user in 1–2 sentences,
   e.g.: "Let's set up PhilLit in this folder — a one-time step. I'll create the
   configuration for you; I'll only need your email address and one free API key."
2. **Check the environment.** Run
   `[ -x "${PHILLIT_ROOT:-}/bin/phillit-run" ] && echo ok || echo missing`,
   `command -v uv`, and `command -v jq`.
   - If the first check prints `missing`, the plugin's environment isn't loaded in this
     session (`PHILLIT_ROOT` unset, empty, or stale — typically the plugin was installed
     or updated mid-session; the bridge only runs at session start), so every later step
     would fail with a cryptic "No such file or directory". Tell the user: "One quick
     step: please restart Claude Code in this folder, then run /phillit:setup again."
     and stop.
   - If uv or jq is absent, give a one-line install instruction (uv:
     https://docs.astral.sh/uv/getting-started/installation/ ; jq: `brew install jq` /
     `apt install jq` / `choco install jq`) and stop — `jq` is required by the
     BibTeX-validation hook and is otherwise a silent clean-install failure.
3. **Preview and ask consent.** Run:
   `bash "$PHILLIT_ROOT/bin/phillit-run" skills/setup/scripts/setup_workspace.py --plugin-root "$PHILLIT_ROOT" --dry-run`
   Then summarize what will happen in 2–3 short bullets — do not dump the settings JSON
   (show it only if the user asks for details):
   - Creates a `.phillit` folder marker and, for any API keys not already set in the
     environment, a `.env` file to hold them (keys found in the environment are used
     from there — never copied into a file)
   - Lets Claude run PhilLit's research tools **in this folder**, and make file edits in
     `~/.local/state/phillit/reviews/` (the local work folder where reviews run before
     they appear in `reviews/`, keeping hours of rewrites off a synced folder), without
     asking permission each time; deleting files and system-level commands still require
     approval
   - Nothing is sent or published anywhere
   Ask whether to proceed.
4. **Apply.** On approval, run the same command without `--dry-run`. Keys already set in
   the user's environment stay there — the script never copies their values into `.env`;
   it prints which ones it found (and skips creating `.env` when it found them all). If it
   found some, tell the user (e.g. "Your Brave key was already set up — I'm using it from
   your environment.").
5. **Collect the rest.** Ask only for what is still missing, and be explicit about
   required vs. optional. Edit `.env` yourself with the answers (uncomment the key's
   `# KEY=` line and add the value) — don't make the user open a file. Keys the user
   skips stay commented: an active empty `KEY=` line would override that key with ""
   if the user ever exports it in their shell.
   - **Required:**
     - `CROSSREF_MAILTO` — just the user's email address; ask for it and fill
       `OPENALEX_EMAIL` with the same address
     - `BRAVE_API_KEY` — the one thing the user must obtain themselves: a free key from
       https://brave.com/search/api/
   - **Optional (skipping is fine):** `S2_API_KEY` (https://www.semanticscholar.org/product/api)
     and `CORE_API_KEY` (https://core.ac.uk/services/api) improve search coverage and speed.
6. **Optional: your own PDFs.** PhilLit writes more accurately about a paper, and can quote it,
   when it can read your own copy. It never reads Zotero or a folder of yours
   unless you say yes here, and it only uses them for your own reviews on this computer.
   Ask the two questions one at a time; on **no** (or no answer) write nothing to `.env`.
   Write each key the way step 5 writes keys: uncomment the key's `# KEY=` line and add
   the value, or append the line to `.env` if it is not there (create `.env` if step 4
   skipped it).
   - **Zotero.** Ask: "Do you use Zotero? PhilLit can read the PDFs in it — only on this
     computer." On yes, tell the user: "In Zotero 7, open Settings > Advanced and tick
     'Allow other applications on this computer to communicate with Zotero'. Keep Zotero
     open, and tell me when that's done." Then run
     `bash "$PHILLIT_ROOT/bin/phillit-run" skills/setup/scripts/setup_workspace.py --probe-zotero`.
     If it prints `"zotero": "ok"`, set `PHILLIT_ZOTERO=on` and say "Zotero is connected."
     Otherwise say plainly that Zotero isn't answering yet (the `detail` says why),
     offer one retry after they check the setting, and leave `PHILLIT_ZOTERO` unset if
     it still fails — PhilLit just works without it.
   - **A folder of PDFs.** Ask: "Do you keep academic PDFs in a folder PhilLit may read?"
     On yes, ask for the folder's path and run
     `bash "$PHILLIT_ROOT/bin/phillit-run" skills/setup/scripts/setup_workspace.py --check-pdf-dir "<path>"`.
     If `is_dir` is true and `pdf_count` is above 0, set `PHILLIT_PDF_DIR=` to the printed
     `path` in double quotes (forward slashes; the quotes keep a `#` in the path intact) and say how many PDFs it found. If the folder is
     missing or holds no PDFs, say so plainly, ask once for a corrected path, and
     otherwise leave `PHILLIT_PDF_DIR` unset.
7. **Verify.** Run
   `bash "$PHILLIT_ROOT/bin/phillit-run" skills/philosophy-research/scripts/check_setup.py`
   and report in one line: "Setup complete — ask me for a literature review whenever you're
   ready", or exactly what is still missing and how to fix it.
8. **Trust check.** Settings changes reload live, but Claude Code ignores the new `allow`
   rules until the workspace is trusted. Check (prefer the `$PWD` entry; fall back to the
   physical path only when `$PWD` has no entry at all — under a symlinked cwd, e.g.
   OneDrive or `/var` → `/private/var`, `.claude.json` may key either form):
   ```bash
   CFG="${CLAUDE_CONFIG_DIR:+$CLAUDE_CONFIG_DIR/.claude.json}"
   jq -r --arg d "$PWD" --arg p "$(pwd -P)" \
     '((.projects[$d] // .projects[$p] // {}).hasTrustDialogAccepted // false)' \
     "${CFG:-$HOME/.claude.json}"
   ```
   - If `true` (or the check itself fails): say nothing — permissions are already live.
   - If `false`: end the setup with this, prominently, as the final line:
     **"One last step: restart Claude Code in this folder and choose 'Yes, I trust this
     folder' when asked — PhilLit's permissions only take effect after that."**
9. **Updates tip.** Close with one sentence: "PhilLit doesn't update automatically — to
   change that, open `/plugin`, go to Marketplaces, and turn on auto-update for ai4phi
   (or run `/plugin marketplace update ai4phi`, then `/plugin update phillit@ai4phi`,
   whenever you want the latest)."

If Claude still prompts for every command later (or PhilLit runs non-interactively), the workspace trust dialog was likely declined — Claude Code ignores `allow` rules in `.claude/settings.json` in untrusted directories.
