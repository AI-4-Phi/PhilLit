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
- `.claude-plugin/` — Plugin manifest (`plugin.json`).
- `bin/phillit-run` — Self-locating wrapper that runs every bundled Python script in the plugin's locked `uv` project environment (see "Hooks and Python").
- `skills/literature-review/` — Main orchestration skill for the 6-phase workflow. `scripts/` contains the Phase 3-to-4 evidence barrier (`evidence_barrier.py`, helpers `resolve_context.py`, `stamp_evidence.py`, `venue_vetting.py` — the OpenAlex venue check behind the barrier's `venue_status` flag — `year_suffix.py`, the pure Chicago a/b assigner behind its `year_suffix` field, and `web_evidence.py` — URL extraction, capture validation and existence checks behind the `EVIDENCE-WEB` fetch gate, whose `urldate`/`archiveurl` the barrier also owns, and which also owns the excluded-host policy (SEP + mirrors, IEP, NDPR, PhilPapers — never earn EVIDENCE-WEB)). Since v0.5.0 the barrier also owns `EVIDENCE-ABSTRACT` attestation: the enrichment ledger is candidacy only, and the tier requires a live per-source re-fetch whose text hash-matches the bib's (`enrich_bibliography.corroborate_abstract`; budgeted, fail-closed, bucketed in the report). Phase 6 tools: `assemble_review.py`, `normalize_headings.py`, `dedupe_bib.py`, `enrich_bibliography.py`, `generate_bibliography.py`, `lint_md.py`, `check_evidence.py`, `sanitize_bib.py`.
- `skills/philosophy-research/` — API search scripts for academic sources (Semantic Scholar, OpenAlex, CORE, arXiv, SEP, IEP, PhilPapers, NDPR), abstract resolution, encyclopedia context extraction, and citation verification (CrossRef). Includes Brave web search fallback and caching, and `fetch_web.py` — the research-time fetch-and-capture tool (HTML and PDF, `--stdin` fallback) whose capture files the evidence barrier gates `EVIDENCE-WEB` on, and which refuses the excluded encyclopedia hosts (SEP + mirrors, IEP, NDPR, PhilPapers) before any request. `output.dumps()` in `output.py` is the one owner of the `ensure_ascii` decision for console output, including the Windows stdout guard behind it — never hand-pick `ensure_ascii` at a call site.
- `skills/setup/` — The `/phillit:setup` skill: scaffolds a workspace (`.phillit/` marker, `.env`) and safely merges permission rules into the workspace's `.claude/settings.json`.
- `agents/` — Specialized subagent definitions invoked by the literature-review skill.
- `hooks/` — Hook scripts: `fast_gate.sh` (shell pre-filter for per-call gates), `bib_validator.py`, `validate_bib_write.py`, `metadata_cleaner.py`, `block_background_bash.py` (guards Bash-tool background calls inside subagents), `block_subagent_background_dispatch.py` (guards Agent/Task background dispatch at the orchestrator — the four PhilLit review agents must run foreground), `block_ledger_write.py` (denies **native file-tool** writes to the `enrichment_ledger-*.json` / `cleaning_ledger-*.json` attestation ledgers — the designated writers write them from inside Python, so the supported pipeline is unaffected; it is **not** a security boundary, since broadly-allowed `Bash` bypasses it entirely, and it does deny a *developer* hand-editing a ledger — use the owning script or `git checkout`), `subagent_stop_bib.sh`, and the thin `setup-environment.sh` SessionStart bootstrap. Also here but **not a hook**: `bib_identity.py`, the one owner of bibliography identity, comparison keys, and name folds (`normalize_doi`, `title_key`, `normalize_pages`, `normalize_journal`, `venue_key`, `year_key`, `fallback_key`, `ascii_variants`, `translit_fold`) — note `venue_key` is a deliberately looser VERIFICATION key for venue names (it folds conference citation forms onto the series name) and must never be used for dedup identity, which is `normalize_journal`'s job — it lives in `hooks/` because that is the directory other components already import from, and it is deliberately absent from `hooks.json`. Sites keep their historic names as **aliases to the shared objects**, so tests assert `is` identity; never re-add a local copy.
- `hooks/hooks.json` — Plugin hook definitions (single source of truth): SessionStart bootstrap; marker-gated PreToolUse/PostToolUse/SubagentStop.
- `docs/` — Project documentation: `ROADMAP.md` (open work, priority-ordered), shared specs (`ARCHITECTURE.md`, `conventions.md`, `permissions-guide.md`), `known-issues/`, and `ideas/` (design ideas and deferred plans).
- `tests/` — pytest tests for API scripts and hooks.

# Typical Usage: Literature Review

When asked to perform a new literature review:
1. Invoke the `/phillit:literature-review` skill to begin the 6-phase workflow
2. The skill creates a new directory in `reviews/` with an informative short name (e.g., `reviews/epistemic-autonomy-ai/`)
3. The skill coordinates specialized subagents via the Task tool to complete all phases

# Workflow Architecture

The `/phillit:literature-review` skill runs in the main conversation and coordinates the 6-phase workflow (verify environment → plan domains → parallel domain research → synthesis outline → parallel section writing → assemble/lint), dispatching the four subagents in `agents/` via the Task tool (`literature-review-planner`, `domain-literature-researcher`, `synthesis-planner`, `synthesis-writer` — subagents cannot spawn other subagents). The phase-by-phase procedure lives in `skills/literature-review/SKILL.md`; design patterns and rationale in `docs/ARCHITECTURE.md`.

# Development

For agent architecture and design patterns, see `docs/ARCHITECTURE.md`.

## Sister repo: phillit-service

The downstream service (`~/github-repos/phillit-service`) vendors this repo's
skills/agents/hooks under `engine/.claude/` (near-identical files; this repo's
plugin layout has no `.claude/` prefix).

**Every fix or improvement made here must be implemented or mirrored in
phillit-service, mutatis mutandis** (Johannes, 2026-07-28) — code, docs,
and roadmap items alike. Amended 2026-08-08: the mirror is **scripted** —
the service's `tools/revendor.py` re-vendors the whole engine region at a
pinned upstream commit (first run 2026-08-08 at `08a3b3e`; its roadmap item
26 owns reruns). Fixes land here and arrive there at the next pin — never
hand-mirror engine files piecemeal, and phillit-service work stays in
sessions launched from that repo. Docs and roadmap items still adapt rather
than copy (cross-numbering: PhilLit item 3, the bibliography-pipeline
integrity fixes, ↔ service item 23, its intake of them). Mirroring holds in
both directions; a fix that lands in the service comes back here (e.g. the
frontmatter-title ADOPT change).

**Engine/prompt fixes that need test runs are built and validated HERE
first** — reviews here run under Claude Code (free), while the service bills
every run through the Agent SDK — then ported. Open cross-repo work is
listed in `docs/ROADMAP.md`.

Gotcha: the service tracks its roadmap as **`docs/roadmap.md` (lowercase)**.
On macOS's case-insensitive filesystem, editing `docs/ROADMAP.md` there
writes the right file but `git add docs/ROADMAP.md` stages *nothing* — the
change silently misses the commit. Use the lowercase path, and check
`git show --stat` after committing.

## Cross-Platform

PhilLit must work in Claude Code Cloud, Linux, macOS, and Windows. On Windows, Claude Code uses Git Bash to run hooks and Bash tool calls. Use forward-slash paths everywhere. Python is never invoked directly — the `bin/phillit-run` wrapper runs it through `uv`, which resolves the correct interpreter per platform, so there is no `.venv/bin` vs `.venv/Scripts` branching to maintain.

## Git Worktrees

`git worktree add` (and `EnterWorktree`) only checks out tracked files. `docs/superpowers/` (plans, specs) and the local-only files under `docs/known-issues/` are untracked, so a fresh worktree won't have them — copy them over manually before running a plan-driven workflow (e.g. subagent-driven-development) that needs to read a plan file from inside the worktree.

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

**Post-mortem forensics for headless runs:** every `claude -p` run leaves
full transcripts under `~/.claude-work/projects/<encoded-cwd>/` —
`<session-id>.jsonl` (main agent) plus `<session-id>/subagents/agent-*.jsonl`
with `.meta.json` sidecars naming each subagent's domain. Tool_use blocks
carry complete Write/Edit inputs, so you can reconstruct exactly who wrote
what into a bib and when. Gotcha: transcript timestamps are UTC; workspace
file mtimes are local.

## Headless review runs (free end-to-end test runs)

Scaffold a scratch workspace, then drive a full review headless:

```bash
bash <checkout>/bin/phillit-run skills/setup/scripts/setup_workspace.py --plugin-root <checkout> --workspace .
env -u ANTHROPIC_API_KEY claude --plugin-dir <checkout> --model sonnet \
  --permission-mode bypassPermissions -p "/phillit:literature-review <topic> -- Full Autopilot: run all 6 phases without asking anything."
```

- `env -u ANTHROPIC_API_KEY` is load-bearing: if set, it silently outranks subscription auth and bills the API.
- Bake "Full Autopilot, no questions" into the prompt — any AskUserQuestion ends a `-p` run mid-workflow.
- Headless runs share the account's 5-hour usage window with the session driving them.

## Releasing

Bump `version` in `.claude-plugin/plugin.json` for every user-facing release — installed plugins are pinned to that version string, and `/plugin update` (and marketplace auto-update, off by default for third-party marketplaces) only fires when it changes. There is no CHANGELOG and there are no git tags — the `Plugin: bump version to X` commits are the release history (one exception: the 0.2.8 bump rode in on `88ccc50`, a `Hooks:` commit).

Installs go through the external `ai4phi` marketplace ([AI-4-Phi/plugins](https://github.com/AI-4-Phi/plugins)) since 2026-07-22; this repo is the plugin source only. The legacy in-repo `.claude-plugin/marketplace.json` was removed; installs that registered this repo directly no longer receive updates, and the README migration note tells them how to switch. Do not reintroduce a `marketplace.json` here — and never declare `version` in a marketplace entry: `plugin.json` silently wins, so a duplicate is a stale-value trap.

## Commit Messages

Convention: `<Area>: short description` (e.g. `Hooks: ...`, `Docs: ...`, `Deps: ...`, `Philosophy-research: ...`, `Plugin: ...`) — capitalized component name matching what's touched, colon, lowercase imperative description.

## Principles

- **Keep the repository lean** — Do not keep files only for reference if the functionality is already documented elsewhere (e.g., in `pyproject.toml`). Remove deprecated files rather than marking them as such.
- **Single source of truth** — Dependencies in `pyproject.toml`, agent definitions in `agents/`, skill definitions in `skills/`, hooks in `hooks/hooks.json`. Avoid duplicating information across files.
- **Simple and concise** — Prefer simple solutions. Keep agent/skill instructions brief and effective. Avoid verbosity.
- **Verify assumptions empirically** — Test bash patterns and environment behavior in actual subagent context before codifying. Don't assume documentation is accurate.
- **Cross-platform** — Implementations must work in Claude Code Cloud, Linux, macOS, and Windows. Use forward slashes in paths. Python runs through the `bin/phillit-run` wrapper (uv), so there are no platform-specific interpreter paths to maintain.
- **Python file I/O** — Always pass `encoding='utf-8'` to `open()`, `read_text()`, and `write_text()`. Windows defaults to `cp1252`, causing cross-platform failures. Avoid non-ASCII characters (e.g., `→`) in output that may be piped through subprocesses (Windows `cp1252` can't encode them).
- **pybtex Writer emits quoted fields** (`field = "value"`) on round-trip, not just braced — any regex over `.bib` text must match both forms (pattern: `stamp_evidence.py::_FIELD_RE`).

## Permissions

- **Evaluation order**: deny → ask → allow. First matching rule wins. An `ask` rule overrides a matching `allow` rule.
- **A plugin cannot ship permissions.** `/phillit:setup` merges PhilLit's rules into the user's workspace `.claude/settings.json` (parse / merge / dedupe / back up / atomic write). The canonical rule set lives in `skills/setup/scripts/setup_workspace.py` (`PHILLIT_RULES`).
- **Bash is allowed broadly** (not enumerated). Enumerating prefix patterns (e.g., `Bash(python *)`) is fragile — subagents construct multi-line scripts with variable prefixes that no finite pattern set can match. Safety comes from deny rules (`sudo`, `dd`, `mkfs`), ask rules (`rm`, `rmdir`), and a scoped `Edit(reviews/**)` rule. Edit rules cover all file-editing tools (Write, Edit, NotebookEdit); `Write(path)` rules are never consulted and trigger a startup warning — never add one.
- **Do not revert to enumerated Bash patterns.** This was attempted 4 times (Jan–Feb 2026) and failed each time. See `docs/known-issues/background-bash-tasks.md` and `docs/permissions-guide.md` for details.

## Hooks and Python

**All bundled Python runs through the wrapper — never bare `python`, never `$PYTHON`.**

- **The wrapper** (`bin/phillit-run`): `bash "<root>/bin/phillit-run" <root-relative-script> [args]` execs `uv run --locked --no-dev --project <root>` against the single `pyproject.toml`/`uv.lock`, in a per-install venv keyed to the root path (`~/.venvs/phillit-plugin-<cksum>`). It self-locates the root (works from any cwd) and self-resolves uv: `$PHILLIT_UV` if set, else PATH, else the fallback dirs in `$PHILLIT_BREW_DIRS`. Self-resolution is load-bearing: hook processes never see `CLAUDE_ENV_FILE` exports, so the wrapper cannot rely on the bootstrap's bridging.
- **Path references**: skill/agent prose uses `$PHILLIT_ROOT` (`bash "$PHILLIT_ROOT/bin/phillit-run" skills/…`); `hooks/hooks.json` uses `${CLAUDE_PLUGIN_ROOT}` (only hooks receive it).
- **The SessionStart bootstrap** (`hooks/setup-environment.sh`) is thin: it bridges `PHILLIT_ROOT`, `PHILLIT_UV` (and `PHILLIT_ACTIVE` inside a workspace) into `$CLAUDE_ENV_FILE` for later Bash tool calls and subagents. No venv build, no `.env` load, no package checks — it must stay cheap because plugin hooks fire in *every* session.
- **`.env` loading**: every CLI script that reads configuration from the environment (API keys, `PHILLIT_FETCH_USER_AGENT`) calls `load_dotenv(find_dotenv(usecwd=True), override=True)` in `main()`, before `argparse.ArgumentParser()` (argparse defaults read `os.environ` at definition time); pure-stdin/file tools don't need it. `usecwd=True` is load-bearing: it searches upward from the *workspace* (cwd). The bare default walks up from the script's own directory — in an installed plugin that is the plugin cache, and the workspace `.env` silently never loads. `.env` values take priority over the shell environment. Library modules must never read env at IMPORT time — main() hasn't loaded `.env` yet when imports run; resolve per call instead (pattern: `rate_limiter.user_agent()`). The usecwd idiom is pinned by `tests/test_dotenv_loading.py`.
- **All hooks live in `hooks/hooks.json`**, never in agent frontmatter (plugin subagents ignore frontmatter hooks) — single source of truth, plugin-compatible.
- **Gate-failure policy**: a gate's failure direction follows what the gate is *for*, not which event it fires on, and is never silent. *Accuracy gates* fail **closed** — SubagentStop BibTeX validation (a crashed/empty validator is a block with an explicit "crashed" reason, never a silent allow) and `block_ledger_write.py` (an unreadable payload is denied with a "could not evaluate" reason, since nothing in the supported pipeline writes a ledger through a file tool). *Plumbing gates* fail **open**: a broken uv/venv must never brick the workspace — hook commands carry an `|| echo '{"systemMessage": …}'` fallback so the failure surfaces to the user without blocking. Note the two mechanisms are independent: `|| echo` only fires on a **nonzero exit** (a uv/process failure), so a gate that exits 0 with an "allow" decision after failing to parse its input is failing open *silently* — which the policy forbids, and which the item-3-C review caught in a first draft.
- **Marker gating + fast path**: intrusive hooks no-op outside a workspace. PreToolUse/PostToolUse route through `hooks/fast_gate.sh`, which checks the `.phillit` marker AND a cheap stdin-needle match (`.bib` / `run_in_background` / `_ledger-`, matched **case-insensitively** via `nocasematch` — macOS and Windows filesystems are case-insensitive, so a case-sensitive needle would let `LITERATURE.BIB` skip validation entirely) before uv ever starts — per-call gates must not pay uv startup (or a cold venv build, which can exceed the 60 s hook timeout) for calls that cannot concern them. The needle is a safe over-approximation: a miss can never need blocking; a spurious hit just hands the decision to the Python gate. `subagent_stop_bib.sh` checks `"$CLAUDE_PROJECT_DIR/.phillit"` directly (it has no matcher and fires for every SubagentStop, so it must self-scope).
- **Shell hooks + `jq`**: when parsing a script's JSON output, capture **stdout only** (`2>/dev/null` — the wrapper's `uv` writes warnings/build progress to stderr, which would corrupt the JSON), and guard against non-JSON output with `if ! VAR=$(… | jq … 2>/dev/null); then …` to avoid silent `set -e` deaths. Note `jq` exits **0 on empty input**, so an empty capture slips through that guard — check for empty output explicitly first and treat it as a crash.
- **SubagentStop protocol**: all decisions are stdout JSON with exit 0 (JSON is ignored on exit 2).

## Adding Python Dependencies

When adding a new Python package import:

1. **`pyproject.toml`** — add the package to `dependencies`.
2. **`uv.lock`** — regenerate with `uv lock`.
3. **`skills/philosophy-research/scripts/check_setup.py`** — add to `required_packages` only if the package is specific to the philosophy-research skill.

The wrapper's `uv run --locked` installs the full locked dependency set, so there is no separate per-package check in the bootstrap to update.
