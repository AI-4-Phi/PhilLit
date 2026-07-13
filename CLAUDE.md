**PhilLit** is a multi-agent system to (a) author academic literature reviews for philosophy research, and (b) improve these agents. It is packaged as a distributable Claude Code plugin.

> **This `CLAUDE.md` is for plugin developers working in this repository.** It does **not** load when PhilLit runs as an installed plugin from a user's own directory — runtime guidance lives in the skills (`skills/*/SKILL.md`) and agents (`agents/*.md`).

# Mode

**Production mode** (default): When the user asks for a literature review, invoke the `/phillit:literature-review` skill to begin the 6-phase workflow. Skills and agents register only when the plugin is loaded — a bare dev clone registers none of them. To run a review against your checkout, launch `claude --plugin-dir /path/to/PhilLit` from a scratch directory (see CONTRIBUTING.md, Getting Started).

**Development mode**: Only if user explicitly asks to develop, improve, or test agents/skills. Work on definitions in `agents/` and `skills/`.

# Objectives

**Priority order for literature reviews** (and agent development):

1. **Accurate** — Only cite verified papers; never fabricate references
2. **Comprehensive** — Cover all major positions and key debates
3. **Rigorous and concise** — Analytical depth, tight prose; balanced presentation of positions
4. **Reproducible** — Structured workflow, standard BibTeX output, Chicago author-date citations

**NOT priorities**:
- ❌ Speed — Quality over fast completion
- ❌ Context efficiency — Use full context as needed; don't optimize for token savings

# File Structure

- `reviews/` — All existing and new literature reviews. Each review has its own subdirectory with an informative short name. Gitignored (local only), except the three example reviews linked from the README.
- `.claude-plugin/` — Plugin manifest (`plugin.json`) and single-plugin marketplace (`marketplace.json`).
- `bin/phillit-run` — Self-locating wrapper that runs every bundled Python script in the plugin's locked `uv` project environment (see "Hooks and Python").
- `skills/literature-review/` — Main orchestration skill for the 6-phase workflow. `scripts/` contains Phase 6 tools: `assemble_review.py`, `normalize_headings.py`, `dedupe_bib.py`, `enrich_bibliography.py`, `generate_bibliography.py`, `lint_md.py`.
- `skills/philosophy-research/` — API search scripts for academic sources (Semantic Scholar, OpenAlex, CORE, arXiv, SEP, IEP, PhilPapers, NDPR), abstract resolution, encyclopedia context extraction, and citation verification (CrossRef). Includes Brave web search fallback and caching.
- `skills/setup/` — The `/phillit:setup` skill: scaffolds a workspace (`.phillit/` marker, `.env`) and safely merges permission rules into the workspace's `.claude/settings.json`.
- `agents/` — Specialized subagent definitions invoked by the literature-review skill.
- `hooks/` — Hook scripts: `bib_validator.py`, `validate_bib_write.py`, `metadata_validator.py`, `metadata_cleaner.py`, `block_background_bash.py`, `subagent_stop_bib.sh`, and the thin `setup-environment.sh` SessionStart bootstrap.
- `hooks/hooks.json` — Plugin hook definitions (single source of truth): SessionStart bootstrap; marker-gated PreToolUse/PostToolUse/SubagentStop.
- `docs/` — Project documentation: shared specs (`ARCHITECTURE.md`, `conventions.md`, `permissions-guide.md`) and `known-issues/`.
- `.claude/settings.json` — Dev-clone permissions only (no hooks block; the plugin's hooks live in `hooks/hooks.json`). A convenience for working in this repo, not shipped behavior.
- `.claude/settings.local.json` — Local settings overrides (gitignored).
- `tests/` — pytest tests for API scripts and hooks.

# Typical Usage: Literature Review

When asked to perform a new literature review:
1. Invoke the `/literature-review` skill to begin the 6-phase workflow
2. The skill creates a new directory in `reviews/` with an informative short name (e.g., `reviews/epistemic-autonomy-ai/`)
3. The skill coordinates specialized subagents via the Task tool to complete all phases

# Workflow Architecture

**`/literature-review` skill** — Main entry point. Runs in main conversation with Task tool access. Coordinates the 6-phase workflow:
- Phase 1: Verify environment and determine execution mode
- Phase 2: Task tool invokes `literature-review-planner` — Decomposes topic into domains
- Phase 3: Task tool invokes `domain-literature-researcher` ×N (parallel) — Uses `philosophy-research` skill for API searches; outputs BibTeX files
- Phase 4: Task tool invokes `synthesis-planner` — Reads BibTeX files; designs outline emphasizing debates and positions
- Phase 5: Task tool invokes `synthesis-writer` ×N (parallel) — Writes sections using relevant BibTeX subsets
- Phase 6: Assemble final review, deduplicate BibTeX, generate bibliography, lint, clean up, optional DOCX

**Specialized subagents** (invoked via Task tool, cannot spawn other subagents):
- `literature-review-planner` — Decomposes topic into domains and search strategies
- `domain-literature-researcher` — Searches academic sources, produces BibTeX with rich annotations
- `synthesis-planner` — Designs tight outline from collected literature
- `synthesis-writer` — Writes individual sections of the review

# Development

For agent architecture and design patterns, see `docs/ARCHITECTURE.md`.

## Cross-Platform

PhilLit must work in Claude Code Cloud, Linux, macOS, and Windows. On Windows, Claude Code uses Git Bash to run hooks and Bash tool calls. Use forward-slash paths everywhere. Python is never invoked directly — the `bin/phillit-run` wrapper runs it through `uv`, which resolves the correct interpreter per platform, so there is no `.venv/bin` vs `.venv/Scripts` branching to maintain.

## Setup

**Plugin users** run `/phillit:setup` once in their working directory; the first script call builds a per-install venv at `~/.venvs/phillit-plugin-<cksum>` via `uv run --locked`.

**Developers** working in this repo:

```bash
uv sync          # create the dev venv and install all dependencies (including dev)
```

Check API setup with:

```bash
bash bin/phillit-run skills/philosophy-research/scripts/check_setup.py
```

API keys are required for literature searches (see `.env.example`).

## Testing

Run tests with: `uv run --locked pytest`

## Releasing

Bump `version` in `.claude-plugin/plugin.json` for every user-facing release — installed plugins are pinned to that version string, and `/plugin update` (and marketplace auto-update, off by default for third-party marketplaces) only fires when it changes. Do not declare `version` in `marketplace.json` as well: `plugin.json` silently wins, so a duplicate is a stale-value trap.

## Principles

- **Keep the repository lean** — Do not keep files only for reference if the functionality is already documented elsewhere (e.g., in `pyproject.toml`). Remove deprecated files rather than marking them as such.
- **Single source of truth** — Dependencies in `pyproject.toml`, agent definitions in `agents/`, skill definitions in `skills/`, hooks in `hooks/hooks.json`. Avoid duplicating information across files.
- **Simple and concise** — Prefer simple solutions. Keep agent/skill instructions brief and effective. Avoid verbosity.
- **Verify assumptions empirically** — Test bash patterns and environment behavior in actual subagent context before codifying. Don't assume documentation is accurate.
- **Cross-platform** — Implementations must work in Claude Code Cloud, Linux, macOS, and Windows. Use forward slashes in paths. Python runs through the `bin/phillit-run` wrapper (uv), so there are no platform-specific interpreter paths to maintain.
- **Python file I/O** — Always pass `encoding='utf-8'` to `open()`, `read_text()`, and `write_text()`. Windows defaults to `cp1252`, causing cross-platform failures. Avoid non-ASCII characters (e.g., `→`) in output that may be piped through subprocesses (Windows `cp1252` can't encode them).

## Permissions

- **Evaluation order**: deny → ask → allow. First matching rule wins. An `ask` rule overrides a matching `allow` rule.
- **A plugin cannot ship permissions.** `/phillit:setup` merges PhilLit's rules into the user's workspace `.claude/settings.json` (parse / merge / dedupe / back up / atomic write). The canonical rule set lives in `skills/setup/scripts/setup_workspace.py` (`PHILLIT_RULES`).
- **Bash is allowed broadly** (not enumerated). Enumerating prefix patterns (e.g., `Bash(python *)`) is fragile — subagents construct multi-line scripts with variable prefixes that no finite pattern set can match. Safety comes from deny rules (`sudo`, `dd`, `mkfs`), ask rules (`rm`, `rmdir`), and scoped `Write`/`Edit` (only `reviews/`).
- **Do not revert to enumerated Bash patterns.** This was attempted 4 times (Jan–Feb 2026) and failed each time. See `docs/known-issues/background-bash-tasks.md` and `docs/permissions-guide.md` for details.

## Hooks and Python

**All bundled Python runs through the wrapper — never bare `python`, never `$PYTHON`.**

- **The wrapper** (`bin/phillit-run`): `bash "<root>/bin/phillit-run" <root-relative-script> [args]` execs `uv run --locked --no-dev --project <root>` against the single `pyproject.toml`/`uv.lock`, in a per-install venv keyed to the root path (`~/.venvs/phillit-plugin-<cksum>`). It self-locates the root (works from any cwd) and self-resolves uv: `$PHILLIT_UV` if set, else PATH, else the fallback dirs in `$PHILLIT_BREW_DIRS`. Self-resolution is load-bearing: hook processes never see `CLAUDE_ENV_FILE` exports, so the wrapper cannot rely on the bootstrap's bridging. `--if-active <script>` makes it a no-op unless the cwd is a PhilLit workspace (`.phillit/` marker) — used by intrusive hooks.
- **Path references**: skill/agent prose uses `$PHILLIT_ROOT` (`bash "$PHILLIT_ROOT/bin/phillit-run" skills/…`); `hooks/hooks.json` uses `${CLAUDE_PLUGIN_ROOT}` (only hooks receive it).
- **The SessionStart bootstrap** (`hooks/setup-environment.sh`) is thin: it bridges `PHILLIT_ROOT`, `PHILLIT_UV` (and `PHILLIT_ACTIVE` inside a workspace) into `$CLAUDE_ENV_FILE` for later Bash tool calls and subagents. No venv build, no `.env` load, no package checks — it must stay cheap because plugin hooks fire in *every* session.
- **`.env` loading**: each Python script calls `load_dotenv(find_dotenv(usecwd=True), override=True)` in `main()`, before `argparse.ArgumentParser()` (argparse defaults read `os.environ` at definition time). `usecwd=True` is load-bearing: it searches upward from the *workspace* (cwd). The bare default walks up from the script's own directory — in an installed plugin that is the plugin cache, and the workspace `.env` silently never loads. `.env` values take priority over the shell environment. Pinned by `tests/test_dotenv_loading.py`.
- **All hooks live in `hooks/hooks.json`**, never in agent frontmatter (plugin subagents ignore frontmatter hooks) — single source of truth, plugin-compatible.
- **Gate-failure policy**: a gate's failure direction is a per-gate design decision, and never silent. *Accuracy gates* (SubagentStop BibTeX validation) fail **closed**: a crashed/empty validator is a block with an explicit "crashed" reason, never a silent allow. *Plumbing gates* (PreToolUse/PostToolUse helpers) fail **open**: a broken uv/venv must never brick the workspace — hook commands carry an `|| echo '{"systemMessage": …}'` fallback so the failure surfaces to the user without blocking.
- **Marker gating**: intrusive hooks no-op outside a workspace. PreToolUse/PostToolUse use `phillit-run --if-active`; `subagent_stop_bib.sh` checks `"$CLAUDE_PROJECT_DIR/.phillit"` directly (it has no matcher and fires for every SubagentStop, so it must self-scope).
- **Shell hooks + `jq`**: when parsing a script's JSON output, capture **stdout only** (`2>/dev/null` — the wrapper's `uv` writes warnings/build progress to stderr, which would corrupt the JSON), and guard against non-JSON output with `if ! VAR=$(… | jq … 2>/dev/null); then …` to avoid silent `set -e` deaths. Note `jq` exits **0 on empty input**, so an empty capture slips through that guard — check for empty output explicitly first and treat it as a crash.
- **SubagentStop protocol**: all decisions are stdout JSON with exit 0 (JSON is ignored on exit 2).

## Adding Python Dependencies

When adding a new Python package import:

1. **`pyproject.toml`** — add the package to `dependencies`.
2. **`uv.lock`** — regenerate with `uv lock`.
3. **`skills/philosophy-research/scripts/check_setup.py`** — add to `required_packages` only if the package is specific to the philosophy-research skill.

The wrapper's `uv run --locked` installs the full locked dependency set, so there is no separate per-package check in the bootstrap to update.
