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
  "Bash(rm:*)",      // Prevent file deletion
  "Bash(rmdir:*)",   // Prevent directory deletion
  "Bash(sudo:*)",    // Prevent privilege escalation
  "Bash(dd:*)",      // Prevent disk operations
  "Bash(mkfs:*)"     // Prevent filesystem formatting
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
  // Note: Bash patterns use prefix-only matching (limited bypass protection)
  "Bash(ls:*)",      // List directory contents
  "Bash(mkdir:*)",   // Create directories (for review structure)
  "Bash(python:*)",  // Run Python scripts (for literature search)
  "Bash(source:*)",  // Activate Python virtual environment
  "Bash(echo:*)",    // Output text (for debugging)
  "Bash(cat:*)",     // Concatenate files (for assembly)
  "Bash(pytest:*)",  // Run tests

  // Literature review workflow - unrestricted within reviews/ directory
  "Write(reviews/**)",  // Create files in reviews/ and subdirectories
  "Edit(reviews/**)",   // Edit files in reviews/ and subdirectories

  // Custom skills for literature review workflow
  "Skill(literature-review)",      // Main orchestration skill
  "Skill(philosophy-research)"     // Academic search skill (SEP, PhilPapers, S2, etc.)
]
```

### Ask Rules (Require Approval)
```json
"ask": [
  "Write(*)",        // Ask before writing files outside reviews/
  "Edit(*)"          // Ask before editing files outside reviews/
]
```
File modifications outside `reviews/` require user approval.

## Permission Evaluation Order

1. **Deny** rules are checked first (block completely)
2. **Allow** rules are checked next (auto-approve without prompt)
3. **Ask** rules are checked last (require user approval)

Example: `Write(reviews/file.md)` matches `allow` rule, so it's auto-approved. `Write(.claude/settings.json)` matches `ask` rule, so it requires approval.

## Bash Pattern Limitations

**Important**: Bash patterns only support prefix matching with `:*` wildcard at the end.

Current patterns like `Bash(python:*)` can potentially be bypassed:
- Options before command: `python -c "malicious"`
- Extra spaces: `python  script.py`
- Variables: `$PYTHON script.py`

**Mitigation**: The `ask` mode for Write/Edit operations outside `reviews/` provides a secondary security layer.

## Security Principles

1. **Principle of least privilege**: Only grant permissions needed for the workflow
2. **Defense in depth**: Multiple security layers (deny rules, scoped writes, ask mode)
3. **Explicit over implicit**: `defaultMode` and `deny` rules make security stance clear
4. **Safe defaults**: Read-only operations allowed, destructive operations blocked

## Agent-Specific Permissions

Agents can override the global `defaultMode` with their own `permissionMode`:

- **domain-literature-researcher**: `permissionMode: default` (uses Bash/Web, requires visibility)
- **synthesis-planner**: `permissionMode: acceptEdits` (low-risk writing tasks)
- **synthesis-writer**: `permissionMode: acceptEdits` (low-risk writing tasks)
- **literature-review-planner**: `permissionMode: acceptEdits` (low-risk writing tasks)

See individual agent definitions in `.claude/agents/` for details.
