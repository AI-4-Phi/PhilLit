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
  "Bash(mkfs *)"     // Prevent filesystem formatting
]
```
Explicitly blocks destructive operations for safety. These cannot be approved even if requested.

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

With `Bash` in the allow list, safety comes from three layers:

1. **Deny rules**: `sudo`, `dd`, `mkfs` are blocked unconditionally
2. **Ask rules**: `rm`, `rmdir` still require approval
3. **Scoped writes**: file-editing tools are only auto-approved in `reviews/` (via `Edit(reviews/**)`)

## Hook Configuration

Beyond permissions, `hooks/hooks.json` configures hooks that run automatically (the intrusive ones no-op outside a `.phillit/` workspace):

| Hook | Trigger | Script | Purpose |
|------|---------|--------|---------|
| SessionStart (all events) | Session begins, resumes, clears, compacts | `setup-environment.sh` | Thin bootstrap: bridge `$PHILLIT_ROOT`/`$PHILLIT_UV` into `$CLAUDE_ENV_FILE` |
| PreToolUse (`Write`) | Before any Write tool call | `validate_bib_write.py` (via `fast_gate.sh`, needle `.bib`, then `phillit-run`) | Validate BibTeX before writing `.bib` files (deny with reasons) |
| PreToolUse (`Bash`) | Before any Bash tool call | `block_background_bash.py` (via `fast_gate.sh`, needle `run_in_background`, then `phillit-run`) | Block `run_in_background` in subagents |
| PostToolUse (`Edit`) | After any Edit tool call | `validate_bib_write.py` (via `fast_gate.sh`, needle `.bib`, then `phillit-run`) | Validate `.bib` files after edits (block with reasons) |
| SubagentStop (no matcher) | After any subagent finishes | `subagent_stop_bib.sh` | Self-scopes via `.phillit` + `agent_type`; validate BibTeX, clean metadata |

## Agent-Specific Configuration

Agents specify `model` and `tools` in their frontmatter (see `agents/`):

| Agent | Model | Tools | Permission Mode |
|-------|-------|-------|-----------------|
| `domain-literature-researcher` | `sonnet` | Bash, Glob, Grep, Read, Write, WebFetch, WebSearch | `acceptEdits` |
| `synthesis-planner` | `inherit` | Glob, Grep, Read, Write | `acceptEdits` |
| `synthesis-writer` | `sonnet` | Glob, Grep, Read, Write | `acceptEdits` |
| `literature-review-planner` | `sonnet` | Read, Write | `acceptEdits` |

Agents inherit the project-level `allow`/`deny`/`ask` rules from the workspace settings. The `Bash` allow rule is inherited by all subagents, so the `domain-literature-researcher` can run multi-line Bash scripts without prompts. The `deny` and `ask` rules are also inherited, maintaining safety.
