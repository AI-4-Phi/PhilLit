# Plugin clean-install parity gate (plan Task 10)

Recorded results per assertion. `main` keeps clone-and-run until **every** assertion passes.

**Environment for headless runs (2026-07-13):** macOS (dove), Claude Code CLI 2.1.207, uv 0.8+, dev checkout at `~/github-repos/PhilLit` loaded via `--plugin-dir`, sessions run headless (`claude -p`). Headless runs validate *mechanics*, not the interactive approval UX — permission modes were `acceptEdits` with a scoped `--allowedTools` list, so prompt counts and the trust dialog remain interactive-only assertions.

> **Method caveat (review finding 7) and re-run:** the original Steps 1–5 pointed `--plugin-dir` at the *dev checkout*, so the repo-root `.env` masked the workspace-`.env` loading bug (finding 1) and hook-process env resolution (finding 4) was never exercised. After the Phase 1 fixes, the gate was **re-run 2026-07-13 with a hardened method** — see "Phase 2 re-run" at the end. All assertions pass.

## Status summary

| Step | Assertion | Status |
|------|-----------|--------|
| 1 | Local plugin-dir smoke (naming, `/phillit:setup`, researcher spawns) | **PASS** (headless + interactive, see Step 7) |
| 2 | Hooks no-op outside a workspace | **PASS** (with positive control) |
| 3 | Env bridge reaches subagents | **PASS** |
| 4 | Deterministic content assertions | **PASS** (headless + interactive, see Step 7) |
| 5 | Environment lifecycle | **PASS** |
| 6 | Windows/Git Bash | **DEFERRED** (2026-07-13, user decision — no Windows machine available; revisit on first Windows bug report or hardware access) |
| 7 | Second-machine clean install | **PASS** (2026-07-13, interactive user run) |
| 8 | Record + decide | **Gate passed** (Step 6 explicitly deferred) — proceed with merge to `main` |

## Step 1 — Local plugin-dir smoke ✅ (headless)

- **Naming:** skills register namespaced — `phillit:literature-review`, `phillit:philosophy-research`, `phillit:setup`. Agents likewise: `phillit:domain-literature-researcher`, `phillit:literature-review-planner`, `phillit:synthesis-planner`, `phillit:synthesis-writer` (confirmed by the Task tool's own error listing).
- **Spawn:** bare `domain-literature-researcher` fails (`Agent type not found`); `phillit:domain-literature-researcher` spawns successfully. **Fix applied** (commit `10b9cad`): all five `subagent_type` references in `skills/literature-review/SKILL.md` now carry the `phillit:` prefix. Suite stays 736 green.
- **`/phillit:setup`:** dry-run runs through the wrapper, presents the trust boundary, and (correctly) stops for confirmation. With confirmation given, it created `.phillit/`, scaffolded `.env` (empty values), and wrote `.claude/settings.json` matching `PHILLIT_RULES` exactly — including correctly namespaced `Skill(phillit:…)` allow rules, so the Task 8 naming guess was right, no change needed.
- **Bonus findings:**
  - Claude Code adds the plugin's `bin/` to `PATH` automatically in plugin sessions.
  - **Workspace trust caveat:** in an untrusted directory, `claude -p` *ignores* the workspace `.claude/settings.json` `allow` entries ("Ignoring 10 permissions.allow entries … workspace has not been trusted"). Setup's merged permissions only take effect after the user accepts the trust dialog interactively once. Worth a line in the README/setup skill output.
- **Pending (interactive, user):** approval-flow UX, unexpected skill-invocation prompts, prompt counts.

## Step 2 — Hooks no-op outside a workspace ✅

In a directory with **no** `.phillit/` marker, under `--plugin-dir`:

- Normal `Bash` tool call: ran clean (`block_background_bash` no-op).
- `Write` of a deliberately **malformed** `.bib`: succeeded, content landed byte-for-byte (`validate_bib_write` no-op).
- Spawned a `phillit:domain-literature-researcher` subagent and let it stop: `SubagentStop` fired and did nothing — a pre-placed malformed `stray.bib` had an identical checksum before/after.
- SessionStart: no PhilLit output.

**Positive control:** the *same* malformed `.bib` write **inside** the `.phillit` workspace was blocked with `BibTeX validation failed: … premature end of file` — proving the hooks are live and the marker gate is what differentiates.

## Step 3 — Bridge → subagent ✅

A spawned `phillit:domain-literature-researcher` subagent reported `PHILLIT_ROOT=/…/PhilLit` in its Bash environment and ran `bash "$PHILLIT_ROOT/bin/phillit-run" …` with exit 0. (`PHILLIT_UV` also bridged; `PHILLIT_ACTIVE` correctly absent outside a workspace.)

## Step 4 — Deterministic content assertions ✅ (headless; prompt count pending)

- End-to-end tiny review (1 domain, ≤8 papers, 2 sections) run headless via the `phillit:literature-review` skill: see results below. All script invocations exit 0; no unresolved `$PHILLIT_ROOT`/`.claude/` paths anywhere in `reviews/`; expected intermediate files present; final bibliography parses with pybtex 0.25.1.
- **Pending (interactive, user):** permission-prompt count before vs. after `/phillit:setup`.

### Tiny-review results

Topic: "Moral responsibility gaps in automated decision-making", 1 domain, ≤8 papers, 2 sections, headless.

- Phases 1–3 (first session): environment verified; `phillit:literature-review-planner` produced a 1-domain plan; `phillit:domain-literature-researcher` produced `literature-domain-1.bib` — 8 entries, parses clean with pybtex 0.25.1 (matthias2004responsibility, sparrow2007killer, …). No unresolved `$PHILLIT_ROOT` or `.claude/` paths in any output.
- **Headless-only finding:** the orchestrator ran the researcher as a background task, and `claude -p` terminates still-running background tasks after 600 s ("Background tasks still running after 600s; terminating"), cutting the run off before Phase 4. Interactive sessions are unaffected. Workaround for headless/automation use: set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` (or instruct synchronous subagents). Relevant to any PhilLit-as-a-service automation.
- Phases 4–6 (resumed session, ceiling disabled, subagents synchronous): `phillit:synthesis-planner` ×1 and `phillit:synthesis-writer` ×4 spawned; all six Phase 6 scripts exited 0 (`assemble_review.py`, `normalize_headings.py`, `dedupe_bib.py`, `generate_bibliography.py` ×2, `lint_md.py`). Final review: 3,142 words, 8/8 references matched, lint clean. Final `literature-moral-responsibility-gaps-adm.bib` parses with pybtex (8 entries). Intermediate files archived to `intermediate_files/` as specified.
- **Hooks live during a real review:** `validate_bib_write.py` fired in-workspace and blocked an interim bad bib write (LaTeX-escaped umlaut broke the surname matcher; the orchestrator fixed to unicode and re-ran — first `generate_bibliography.py` pass matched 7/8, second 8/8).
- Minor leftover: `reviews/.active-review` couldn't be removed headless (`rm` is an *ask* rule by design, and headless denies asks) — harmless; interactive runs will prompt and clear it.

## Step 5 — Environment lifecycle ✅

- **Cold build:** after `rm -rf ~/.venvs/phillit-plugin-*`, the wrapper rebuilt the venv from a foreign cwd (26 packages) and `check_setup.py` exited 0, total 7.4 s.
- **Warm run:** ~0.1 s, no rebuild.
- **Lock change under `--locked`:** bumped `version` 0.1.0→0.1.1, regenerated `uv.lock`, wrapper re-ran with exit 0; reverted cleanly and re-ran with exit 0.
- **Maintenance note:** the committed `uv.lock` was written by an older uv (lockfile `revision = 1`); current uv rewrites it to revision 3, churning the whole file on the next `uv lock`. Harmless (`--locked` accepts revision 1), but expect a big one-time diff.
- Note: `phillit` itself is a virtual project (no `build-system`), so the venv holds dependencies only — the re-sync assertion is about lock validation + dependency sync, which is the behavior that matters.

## Step 6 — Windows/Git Bash — DEFERRED

Deferred 2026-07-13 (user decision): no Windows machine available, and macOS coverage is complete. The cross-platform conventions (forward-slash paths, `uv`-resolved interpreters, UTF-8 I/O) are enforced by tests; revisit on first Windows bug report or when a Windows machine is available. Assertion when run: `/plugin install`, `/phillit:setup`, one review end-to-end. Also check then: `$PHILLIT_BREW_DIRS` is expanded unquoted (space-separated list), so a `$HOME` containing spaces (e.g. `/c/Users/John Smith`) word-splits the `~/.local/bin` fallback entry in `bin/phillit-run` and `hooks/setup-environment.sh` — PATH resolution still works, only the fallback breaks (2026-07-13 review, deferred). And: the setup skill's trust check (step 7) keys `.claude.json` by `$PWD`/`pwd -P`, which under Git Bash are POSIX-style (`/c/Users/...`) while Claude Code on Windows likely keys native paths (`C:\Users\...`) — if so, the check always prints `false` and setup ends with a spurious "restart and trust this folder" line (harmless but noisy; 2026-07-13 adversarial review, deferred).

The symlink risk named in the plan is **already eliminated**: `skills/literature-review/conventions.md` (the repo's only tracked symlink) was removed in commit `94a2ed0`; `SKILL.md` now references `$PHILLIT_ROOT/docs/conventions.md` directly. (The agents did NOT — they carried `../docs/conventions.md` paths that don't resolve from a plugin workspace; caught by the 2026-07-13 review and fixed to the `$PHILLIT_ROOT` form, pinned by `tests/test_agent_definitions.py`.)

## Step 7 — Second-machine clean install ✅ (2026-07-13)

Interactive clean install on a second machine that never cloned the repo, via
`/plugin marketplace add https://github.com/AI-4-Phi/PhilLit#plugin-conversion` +
`/plugin install phillit@phillit` (the `#branch` fragment is pre-merge only; plain
`AI-4-Phi/PhilLit` once the plugin is on `main`). A fresh-session review ran end-to-end
with no blocking friction. This interactive run also discharges the interactive
assertions left pending in Steps 1 and 4 (trust dialog, `/phillit:setup` approval UX,
permission prompts).

## Step 8 — Decision

**Gate passed** (2026-07-13): Steps 1–5 and 7 pass; Step 6 (Windows) explicitly deferred by user decision. Proceed: retire `GETTING_STARTED.md` clone-and-run, merge `plugin-conversion` → `main`. Post-merge: second-machine installs that used the `#plugin-conversion` fragment should re-add the marketplace without it.

## Phase 2 re-run — hardened method (2026-07-13, post-Phase-1 fixes)

Addresses review finding 7. Same machine/CLI as above; every check ran against a **plugin copy outside the repo** (`git archive HEAD | tar -x` into a scratch dir — tracked files only, exec bits preserved, no gitignored `.env`), from a scratch **workspace** with a `.phillit/` marker and a `.env` whose values deliberately conflict with the launching shell's env.

| Check | Method | Result |
|-------|--------|--------|
| Workspace `.env` loads and wins over shell env (finding 1) | `check_setup.py --json` via the wrapper; shell exported `CORE_API_KEY=shellBBBB2222`, workspace `.env` had `wsenvAAAA1111` | **PASS** — preview `wsen...1111`; shell-only key stays visible when absent from `.env`; `.env` overrides even an empty-string shell export |
| Hook process self-resolves uv (finding 4) | Exact `hooks.json` commands run via `env -i` — no `CLAUDE_ENV_FILE`/`PHILLIT_UV`, PATH without any uv | **PASS** — PreToolUse denies a malformed `.bib` write, allows a valid one; SubagentStop blocks a malformed bib |
| Gate-failure policy | `PHILLIT_UV=/nonexistent/uv` (broken uv) | **PASS** — SubagentStop fails **closed** (block, "produced no output … crashed" + stderr tail); PreToolUse fails **open** with the loud `systemMessage` fallback |
| jq absent (finding 10) | `PATH=/var/empty` (note: macOS 15+ ships `/usr/bin/jq`, so merely stripping Homebrew from PATH does *not* simulate a jq-less host) | **PASS** — loud `systemMessage` "validation was SKIPPED", exit 0; also pinned by `test_missing_jq_emits_visible_system_message` |
| Real session: bridge + `.env` + live Write hook | Headless `claude -p --plugin-dir <copy>` from the workspace, shell `CORE_API_KEY` conflicting | **PASS** — `PHILLIT_ROOT` = copy path in Bash tool calls; `check_setup.py` reports the workspace `.env` value; malformed `.bib` Write blocked, file absent after session |
| Real session: hook works with uv off PATH | Same, launched with `PATH=$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin` (no Homebrew) | **PASS** — `command -v uv` fails in-session, yet the PreToolUse hook still blocks the malformed write (wrapper fallback-dir resolution inside a real hook process) |
| Real session: SubagentStop researcher gate | Pre-placed malformed `stray.bib` at workspace root, valid bib in review dir, spawned `phillit:domain-literature-researcher` told to just finish | **PASS** — stop blocked; subagent quoted "BibTeX syntax error: … premature end of file"; `stray.bib` checksum unchanged |
| Control: no `.phillit` marker | Same malformed write from a marker-less scratch dir | **PASS** — write lands byte-for-byte (hooks no-op) |

Headless invocation notes for reproducing: pass the prompt on **stdin** (`--allowedTools` is variadic and swallows a trailing positional prompt), and `env -u ANTHROPIC_API_KEY` if the shell exports one (it would silently take auth precedence over the claude.ai login).
