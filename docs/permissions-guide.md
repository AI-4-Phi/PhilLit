# Permissions Configuration Guide

This document explains PhilLit's permission rules — merged into your workspace's `.claude/settings.json` by `/phillit:setup` (canonical set: `PHILLIT_RULES` in `skills/setup/scripts/setup_workspace.py`) — and the hooks defined in `hooks/hooks.json`.

## Permission Structure

### Default Mode
```json
"defaultMode": "default"
```
Prompts for approval on first use of each tool per session. Standard security mode.

### Deny Rules (Highest Priority)
```json
"deny": [
  "Bash(sudo *)",    // Prevent privilege escalation
  "Bash(dd *)",      // Prevent disk operations
  "Bash(mkfs *)",    // Prevent filesystem formatting
  "Edit(**/enrichment_ledger-*.json)",   // Evidence-tier attestation ledgers
  "Edit(**/cleaning_ledger-*.json)"      // (see below)
]
```
Blocks destructive operations and hand-written evidence attestations. These cannot be approved even if requested.

**Why the ledgers are denied.** An enrichment-ledger record grants an entry
`EVIDENCE-ABSTRACT` and a cleaning-ledger record attests `EVIDENCE-EXISTENCE`,
so a hand-written record buys a citability tier that no fetch ever
corroborated (ROADMAP item 3 C). Both files are written *from inside Python*
by the scripts that own them, so the supported pipeline is unaffected — but
note this also blocks **you** from hand-editing a ledger while debugging;
re-run the owning script or `git checkout` it. The allow rule `Edit(reviews/**)`
below positively permits the ledger path, so this only works because deny is
evaluated before allow. The rule is belt-and-braces: the mechanism that covers
workspaces which have not re-run `/phillit:setup` is the plugin-shipped
`hooks/block_ledger_write.py` gate.

**What this is not.** Neither the rule nor the gate is a security boundary.
`Bash` is allowed broadly by design, so a `cat >`, heredoc or `python -c`
write reaches the ledger without passing any PreToolUse gate — a complete
bypass for anything deliberate. What these controls buy is protection against
accidental edits and tool-default behaviour, i.e. incidence reduction. The
glob syntax itself is also **unverified against a live Claude Code permission
matcher** (`--dry-run` only proves the strings were serialized); the hook, not
the rule, is what this relies on. The real closure — barrier-side live
corroboration, which makes the ledger a cache rather than an authority — is
tracked as `phillit-service` item 23.

### Allow Rules (Auto-Approved)
```json
"allow": [
  "Read",            // Read any file
  "Grep",            // Search file contents
  "Glob",            // Find files by pattern
  "WebSearch",       // Search the web
  "WebFetch",        // Fetch web content
  "Bash",            // All Bash commands (see safety layers below)
  "Edit(reviews/**)",   // Create and edit files in reviews/ and subdirectories
  "Skill(phillit:literature-review)",   // Main orchestration skill
  "Skill(phillit:philosophy-research)"  // Academic search skill
]
```

**Why `Edit(reviews/**)` and no `Write(reviews/**)`?** Claude Code matches file permission checks against `Edit(path)` rules only — an `Edit` rule covers all file-editing tools (Write, Edit, NotebookEdit). A `Write(path)` rule is never consulted and triggers a startup warning in every session (verified in Claude Code 2.1.210). Earlier PhilLit versions shipped `Write(reviews/**)` alongside; `/phillit:setup` now removes it on re-run (`OBSOLETE_RULES` in `setup_workspace.py`).

**Why `Bash` (all commands)?** Domain researcher subagents construct multi-line scripts with variable prefixes (setting variables, then invoking the `bin/phillit-run` wrapper) that no finite set of prefix patterns can enumerate, causing persistent permission prompts. (Note: current Claude Code splits compound commands — `&&`, `;`, pipes, newlines — and matches each subcommand against rules independently, and wildcards may appear at any position. That makes patterns more capable than when this design was chosen, but enumerating every command shape agents generate remains fragile — this design decision stands; see CLAUDE.md "Do not revert to enumerated Bash patterns".) Using bare `Bash` allows all commands, but the `deny` and `ask` rules still provide safety (see evaluation order below).

### Ask Rules (Require Approval)
```json
"ask": [
  "Bash(rm *)",      // File deletion requires approval
  "Bash(rmdir *)"    // Directory deletion requires approval
]
```
Destructive file operations require user approval rather than being blocked entirely.

## Permission Evaluation Order

1. **Deny** rules are checked first (block completely)
2. **Ask** rules are checked next (require user approval)
3. **Allow** rules are checked last (auto-approve without prompt)

The first matching rule wins. So `Bash(sudo *)` in `deny` blocks sudo even though `Bash` is in `allow`. And `Bash(rm *)` in `ask` still prompts even though `Bash` is in `allow`.

## Security Layers

With `Bash` in the allow list, safety comes from four layers:

1. **Deny rules**: `sudo`, `dd`, `mkfs` are blocked unconditionally, as are file-tool writes to the evidence-tier ledgers
2. **Ask rules**: `rm`, `rmdir` still require approval
3. **Scoped writes**: file-editing tools are only auto-approved in `reviews/` (via `Edit(reviews/**)`)
4. **Hook gates**: the PreToolUse/PostToolUse gates in the table below, which ship with the plugin and so apply even where no permission rules were merged — `.bib` validation and ledger write-protection

Note what none of these reach: `Bash` is deliberately unenumerated, so anything a shell command does is outside all four layers. That is a considered trade (see "Why `Bash`" above), not an oversight, and it is why the ledger controls are described as incidence reduction rather than as a boundary.

## Hook Configuration

Beyond permissions, `hooks/hooks.json` configures hooks that run automatically (the intrusive ones no-op outside a `.phillit/` workspace):

| Hook | Trigger | Script | Purpose |
|------|---------|--------|---------|
| SessionStart (all events) | Session begins, resumes, clears, compacts | `setup-environment.sh` | Thin bootstrap: bridge `$PHILLIT_ROOT`/`$PHILLIT_UV` into `$CLAUDE_ENV_FILE` |
| PreToolUse (`Write`) | Before any Write tool call | `validate_bib_write.py` (via `fast_gate.sh`, needle `.bib`, then `phillit-run`) | Validate BibTeX before writing `.bib` files (deny with reasons) |
| PreToolUse (`Bash`) | Before any Bash tool call | `block_background_bash.py` (via `fast_gate.sh`, needle `run_in_background`, then `phillit-run`) | Block `run_in_background` in subagents |
| PreToolUse (`Agent`) | Before any Agent dispatch | `block_subagent_background_dispatch.py` (via `fast_gate.sh`, needle `run_in_background`, then `phillit-run`) | Block backgrounded dispatch of the four review agents (they must run foreground) |
| PreToolUse (`Task`) | Before any Task dispatch | `block_subagent_background_dispatch.py` (same wiring) | Same guard for the Task-tool spelling of dispatch |
| PreToolUse (`Write`) | Before any Write tool call | `block_ledger_write.py` (via `fast_gate.sh`, needle `_ledger-`, then `phillit-run`) | Refuse tool-writes to `enrichment_ledger-*.json` / `cleaning_ledger-*.json` — the evidence-tier attestation authority |
| PreToolUse (`Edit`) | Before any Edit tool call | `block_ledger_write.py` (same wiring) | Same guard for the Edit-tool spelling; blocking needs PreToolUse, so this cannot live in the PostToolUse `Edit` row below |
| PostToolUse (`Edit`) | After any Edit tool call | `validate_bib_write.py` (via `fast_gate.sh`, needle `.bib`, then `phillit-run`) | Validate `.bib` files after edits (block with reasons) |
| SubagentStop (no matcher) | After any subagent finishes | `subagent_stop_bib.sh` | Validate BibTeX, clean metadata. Self-scopes via `.phillit` + `agent_type`, and additionally requires `jq` (absent → emits a `systemMessage` and SKIPS validation for the run), `stop_hook_active` false, and a valid `reviews/.active-review` pointer to an existing directory |

## Agent-Specific Configuration

Agents specify `model` and `tools` in their frontmatter (see `agents/`):

| Agent | Model | Tools | Permission Mode |
|-------|-------|-------|-----------------|
| `domain-literature-researcher` | `sonnet` | Bash, Edit, Glob, Grep, Read, Write, WebFetch, WebSearch | `acceptEdits` |
| `synthesis-planner` | `inherit` | Glob, Grep, Read, Write | `acceptEdits` |
| `synthesis-writer` | `sonnet` | Glob, Grep, Read, Write | `acceptEdits` |
| `literature-review-planner` | `sonnet` | Read, Write | `acceptEdits` |

Agents inherit the project-level `allow`/`deny`/`ask` rules from the workspace settings. The `Bash` allow rule is inherited by all subagents, so the `domain-literature-researcher` can run multi-line Bash scripts without prompts. The `deny` and `ask` rules are also inherited, maintaining safety.
