# Permissions Configuration Guide

This document explains the permission structure in `.claude/settings.json`.

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
  // Core read-only exploration tools
  "Read",            // Read any file
  "Grep",            // Search file contents
  "Glob",            // Find files by pattern

  // Web research for literature reviews
  "WebSearch",       // Search the web
  "WebFetch",        // Fetch web content

  // Safe bash commands
  "Bash(ls *)",      // List directory contents
  "Bash(mkdir *)",   // Create directories (for review structure)
  "Bash(python *)",  // Run Python scripts (for literature search)
  "Bash(python3 *)", // Run Python 3 explicitly
  "Bash(.venv/bin/python *)",     // Unix venv Python
  "Bash(.venv/Scripts/python *)", // Windows venv Python
  "Bash(source *)",  // Activate Python virtual environment
  "Bash(echo *)",    // Output text (for debugging)
  "Bash(cat *)",     // Concatenate files (for assembly)
  "Bash(pytest *)",  // Run tests

  // Literature review workflow
  "Write(reviews/**)",  // Create files in reviews/ and subdirectories
  "Edit(reviews/**)",   // Edit files in reviews/ and subdirectories
  "Skill(literature-review)",      // Main orchestration skill
  "Skill(philosophy-research)",    // Academic search skill

  // Workflow automation commands
  "Bash(REVIEW_DIR=*)",   // Set review directory variable
  "Bash(mv *)",            // Move/rename files
  "Bash(find *)",          // Find files
  "Bash(for *)",           // Shell loops
  "Bash(if *)",            // Conditionals
  "Bash(pandoc *)",        // Document conversion
  "Bash(wc *)",            // Word count
  "Bash(rm -f reviews/*)", // Phase 6 cleanup of review intermediates
  "Bash(command *)"        // Check command availability
]
```

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
2. **Allow** rules are checked next (auto-approve without prompt)
3. **Ask** rules are checked last (require user approval)

Example: `Write(reviews/file.md)` matches `allow` rule, so it's auto-approved. `Bash(rm foo.txt)` matches `ask` rule, so it requires approval. `Bash(sudo apt install)` matches `deny` rule, so it's blocked entirely.

## Bash Pattern Limitations

**Important**: Bash patterns use prefix matching with ` *` wildcard suffix.

Current patterns like `Bash(python *)` can potentially be bypassed:
- Variables: `$PYTHON script.py` (does not match `python *`)
- Command chaining: `python script.py && malicious`

**Mitigation**: The `ask` mode for Write/Edit operations outside `reviews/` provides a secondary security layer.

## Security Principles

1. **Principle of least privilege**: Only grant permissions needed for the workflow
2. **Defense in depth**: Multiple security layers (deny rules, scoped writes, ask mode for deletion)
3. **Explicit over implicit**: `defaultMode` and `deny` rules make security stance clear
4. **Safe defaults**: Read-only operations allowed, destructive operations require approval or are blocked

## Hook Configuration

Beyond permissions, `settings.json` configures hooks that run automatically:

| Hook | Trigger | Script | Purpose |
|------|---------|--------|---------|
| SessionStart | Session begins | `setup-environment.sh` | Activate venv |
| PreToolUse (Write) | Before any Write tool call | `validate_bib_write.py` | Validate BibTeX syntax before writing `.bib` files |
| SubagentStop | After subagent finishes | `subagent_stop_bib.sh` | Validate BibTeX output from domain researchers |

## Agent-Specific Configuration

Agents specify `model` and `tools` in their frontmatter (see `.claude/agents/`):

| Agent | Model | Tools |
|-------|-------|-------|
| `domain-literature-researcher` | `sonnet` | Bash, Glob, Grep, Read, Write, WebFetch, WebSearch |
| `synthesis-planner` | `inherit` | Glob, Grep, Read, Write |
| `synthesis-writer` | `sonnet` | Glob, Grep, Read, Write |
| `literature-review-planner` | `inherit` | Read, Write |

Agents inherit the project-level `allow`/`deny`/`ask` rules from `settings.json`. They can optionally set their own `permissionMode` in their frontmatter to override the project-level default (e.g., `permissionMode: acceptEdits`).
