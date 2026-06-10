# Deferred Claude Code Opportunities

**Date**: 2026-06-10
**Status**: Deferred — revisit later. None of these are implemented; decisions are out of scope for now.
**Origin**: Audit of PhilLit's Claude Code feature usage against current Claude Code capabilities (docs verified 2026-06-10: hooks.md, sub-agents.md, sandboxing.md, plugins.md at code.claude.com/docs).

This document records improvement opportunities identified in the audit that were deliberately **not** acted on. Protocol-level hook fixes from the same audit were handled separately (see git history of `.claude/hooks/`).

---

## 1. Package PhilLit as a Claude Code plugin (major, strategic)

### Current state

PhilLit is distributed as "clone this repo and open Claude Code in it." Update notification is hand-rolled: `.claude/hooks/check-updates.sh` (~130 lines) detects the canonical remote, auto-adds `upstream` for forks, caches fetch results, and builds escaped JSON for `systemMessage`/`additionalContext`.

### What plugins now offer

Claude Code plugins bundle **skills + agents + hooks + MCP servers + settings** in one installable unit:

- Install via marketplace (`/plugin install`) or git repo; `--plugin-dir` for development.
- **Auto-update**: if the plugin tracks a git branch, users get updates automatically; with a `version` field in `plugin.json`, updates ship on version bumps. This replaces `check-updates.sh` entirely.
- Plugin hooks and settings apply automatically when the plugin is enabled.
- Namespacing: skills become `phillit:literature-review`, etc.
- Since v2.1.157, plugins in `.claude/skills/` load automatically ("skills-directory plugins"), and `claude plugin init` scaffolds a manifest.

The official docs' criteria for converting to a plugin — share with a community, version control and easy updates, same skills/agents across multiple projects — describe PhilLit's distribution model exactly. Users could run literature reviews in **any** project directory instead of working inside a clone of this repo.

### Why it's deferred (real migration costs)

- **Repo-rooted assumptions**: Python scripts, the `uv`-managed `.venv`, `.env` API keys, `reviews/` output, and `tests/` all assume the project root is the PhilLit repo. A plugin runs from `${CLAUDE_PLUGIN_ROOT}`, which is not the user's working directory.
- **SessionStart hook rework**: `setup-environment.sh` would need to create/activate a venv keyed to the plugin dir (or `~/.venvs/phillit`), not `$(pwd)/.venv`. `$PYTHON` propagation via `CLAUDE_ENV_FILE` still works, but every hardcoded `"$CLAUDE_PROJECT_DIR"/.venv/...` path in `settings.json` hooks changes.
- **Where do reviews go?** Today `reviews/` lives in the repo (gitignored). As a plugin, output would land in whatever project the user has open — arguably better, but conventions (`.active-review` pointer, scoped `Write(reviews/**)` permission) need rethinking.
- **`.env` / API key location**: per-user config (e.g., `~/.phillit/.env`) instead of repo-root `.env`; `GETTING_STARTED.md` and `check_setup.py` change accordingly.
- **Testing/CI**: `pytest tests/` and the dev workflow assume the repo layout; the dev loop (this repo) and the distribution artifact (plugin) would diverge.

### Suggested path when revisited

1. Prototype with `--plugin-dir` pointing at a restructured copy (manifest + `skills/` + `agents/` + `hooks/hooks.json`).
2. Solve venv + `.env` location first; everything else is mechanical.
3. Keep this repo as the dev source of truth; publish the plugin from it (marketplace or git). Delete `check-updates.sh` once plugin updates work.

---

## 2. Bash sandboxing as the safety layer (medium, platform-constrained)

**Also deferred** (was recommended for a separate decision alongside the plugin question).

Today, autopilot safety with the global `Bash` allow rests on three deny rules (`sudo`, `dd`, `mkfs`) and two ask rules (`rm`, `rmdir`). Native sandboxing enforces OS-level guarantees instead:

- `sandbox.enabled: true` in settings; filesystem writes confined to project + tmp (`sandbox.filesystem.allowWrite`/`denyWrite`/`denyRead`).
- Network isolation via `sandbox.network.allowedDomains` — PhilLit could pre-allow exactly its academic API hosts (api.semanticscholar.org, api.openalex.org, api.crossref.org, api.core.ac.uk, export.arxiv.org, plato.stanford.edu, iep.utm.edu, philpapers.org, ndpr.nd.edu, api.search.brave.com, …).
- `autoAllowBashIfSandboxed` (default true) keeps the no-prompt autopilot experience.

**Blocker**: no native Windows support (macOS, Linux, WSL2 only), and PhilLit explicitly supports native Windows. Sandboxing must therefore be additive, with `failIfUnavailable: false`, and behavior on a native-Windows machine with `sandbox.enabled: true` must be tested before shipping. Until then, the deny/ask layer stays.

---

## 3. Smaller opportunities

### 3.1 `memory` field on agents (persistent cross-session learning)

Agent frontmatter now supports `memory: user | project | local`, giving the agent a persistent directory across sessions. `domain-literature-researcher` with `memory: project` could accumulate exactly the operational knowledge currently logged manually in `docs/known-issues/` — PhilPapers rate-limit behavior, SEP slugs that 404/hang, NDPR enrichment patterns — instead of relearning per review. Risk: memory quality is uncurated; agents may persist wrong conclusions. Worth a small experiment on one agent.

### 3.2 Prompt-based hooks (`"type": "prompt"`) for annotation quality

Hooks can now be LLM-judged instead of `"type": "command"`. Scripts validate BibTeX *syntax*; nothing mechanically enforces the *annotation quality* rules in `domain-literature-researcher.md` (no superlatives, no generic phrases, substantive CORE ARGUMENT/RELEVANCE/POSITION notes). A prompt-type SubagentStop hook could judge the researcher's `last_assistant_message` (now provided in SubagentStop input) or sampled `.bib` note fields. Cost: every researcher completion incurs an LLM evaluation; failure modes need a loop guard (`stop_hook_active`).

### 3.3 `effort` frontmatter on agents

Agents support `effort: low | medium | high | xhigh | max` (model-dependent). Could tune cost/quality per phase — e.g., higher effort for `synthesis-planner` (one invocation, high leverage) and default for parallel domain researchers. Needs benchmarking against review quality; arbitrary without evals.

### 3.4 `disallowedTools` on agents

Deny-style tool scoping now exists alongside allowlists. Current allowlists are fine; this is only relevant if an agent ever needs "everything except X."

### 3.5 `PermissionDenied` hook with `retry: true`

When a tool call is denied (e.g., by the `.bib` PreToolUse validator), a PermissionDenied hook can return `retry: true` to tell the model it may retry the denied call. Pairs with the deny-reason fix: deny with explanation + explicit retry signal = tighter self-correction loop. Marginal once the deny reason itself is delivered correctly.

### 3.6 `FileChanged` hook to reload `.env` mid-session

A FileChanged hook watching `.env` has `CLAUDE_ENV_FILE` access and can re-export API keys when the user edits `.env` mid-session — closing the edge case that currently justifies per-script `load_dotenv(override=True)` fallbacks (which would stay for manual script runs regardless). Small win; touches a documented defense-in-depth design, so do it deliberately.

### 3.7 PreToolUse `updatedInput` (auto-fix instead of deny)

PreToolUse hooks can now rewrite tool input (`hookSpecificOutput.updatedInput`, combined with `permissionDecision: "allow"` or `"ask"`). `validate_bib_write.py` could *repair* trivial BibTeX issues (unescaped `&`, duplicate fields) in the Write content instead of bouncing the write back to the agent. Trade-off: silent mutation of agent output vs. agent self-correction; current deny-with-reason approach keeps provenance cleaner.

### 3.8 SessionStart `sessionTitle`

SessionStart hooks can set a session title. When resuming an active review (`reviews/.active-review` exists), the hook could set e.g. `Lit review: epistemic-autonomy-ai`. Cosmetic.

---

## Revisit triggers

- **Plugin**: when distribution friction (collaborators cloning/forking, update-check maintenance) outweighs migration cost, or when reviews need to live in users' own project directories.
- **Sandboxing**: when Windows support lands, or if the deny/ask layer proves insufficient in practice.
- **Memory / prompt hooks / effort**: when iterating on review quality with evals in place.
