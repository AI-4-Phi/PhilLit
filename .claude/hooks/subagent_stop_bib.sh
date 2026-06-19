#!/bin/bash
# BibTeX validation and cleaning hook for SubagentStop.
# Scoped to domain-literature-researcher via the SubagentStop matcher in
# settings.json. When the researcher exits:
#   1. Validates BibTeX syntax — blocks on errors (agent must fix them)
#   2. Cleans hallucinated metadata fields — informational, does not block
#
# Protocol: ALL decisions are stdout JSON with exit code 0.
#   Block: {"decision": "block", "reason": "<errors>"}
#   Allow: {"decision": "allow"}
#   Allow + cleaning summary: {"hookSpecificOutput": {"hookEventName":
#     "SubagentStop", "additionalContext": "<summary>"}}
# Never exit 2: Claude Code ignores stdout JSON on exit 2, so the reason
# would be lost and the agent would see only stderr.

set -e

allow() {
    echo '{"decision": "allow"}'
    exit 0
}

# Resolve project Python. A pre-set $PYTHON (e.g., from tests) wins;
# otherwise fall back to the project venv (cross-platform).
if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
    if [[ -x "$CLAUDE_PROJECT_DIR/.venv/bin/python" ]]; then
        PYTHON="$CLAUDE_PROJECT_DIR/.venv/bin/python"
    elif [[ -x "$CLAUDE_PROJECT_DIR/.venv/Scripts/python" ]]; then
        PYTHON="$CLAUDE_PROJECT_DIR/.venv/Scripts/python"
    else
        echo "WARNING: Project venv not found — skipping BibTeX validation" >&2
        allow
    fi
fi

# Require jq for JSON parsing
if ! command -v jq &> /dev/null; then
    echo "WARNING: jq not installed — skipping BibTeX validation. Install with: brew install jq (macOS), apt install jq (Linux), or choco install jq (Windows)" >&2
    allow
fi

# Parse subagent context from stdin (Claude Code passes JSON via stdin)
SUBAGENT_CONTEXT=$(cat)

# Guard: if this is a re-invocation after a previous block, allow to prevent loops
STOP_HOOK_ACTIVE=$(echo "$SUBAGENT_CONTEXT" | jq -r '.stop_hook_active // false')
if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
    allow
fi

# Backward-compat guard: settings.json scopes this hook to
# domain-literature-researcher via the SubagentStop matcher, but older
# Claude Code versions ignore matchers. Validate only when agent_type
# matches; empty/missing agent_type (very old versions) also allows.
AGENT_TYPE=$(echo "$SUBAGENT_CONTEXT" | jq -r '.agent_type // empty')
if [[ "$AGENT_TYPE" != "domain-literature-researcher" ]]; then
    allow
fi

# Read .active-review pointer to find review directory
POINTER="$CLAUDE_PROJECT_DIR/reviews/.active-review"
if [[ ! -f "$POINTER" ]]; then
    echo "WARNING: No .active-review pointer found — skipping BibTeX validation" >&2
    allow
fi

POINTER_CONTENT=$(tr -d '\r\n' < "$POINTER")

# Validate pointer content (must start with reviews/)
if [[ ! "$POINTER_CONTENT" =~ ^reviews/ ]]; then
    echo "WARNING: Invalid .active-review pointer content: $POINTER_CONTENT" >&2
    allow
fi

REVIEW_DIR="$CLAUDE_PROJECT_DIR/$POINTER_CONTENT"

# Validate directory exists
if [[ ! -d "$REVIEW_DIR" ]]; then
    echo "WARNING: Review directory $REVIEW_DIR does not exist" >&2
    allow
fi

# Collect .bib files from review directory AND project root (strays)
# Uses globs instead of find+process substitution for Windows/Git Bash compatibility
shopt -s nullglob
BIB_FILES=()
for f in "$REVIEW_DIR"/*.bib; do
    [[ -f "$f" ]] && BIB_FILES+=("$f")
done
for f in "$CLAUDE_PROJECT_DIR"/*.bib; do
    [[ -f "$f" ]] && BIB_FILES+=("$f")
done
shopt -u nullglob

# No .bib files found — nothing to validate
if [[ ${#BIB_FILES[@]} -eq 0 ]]; then
    allow
fi

# Track syntax errors (these block) and cleaning summaries (informational)
SYNTAX_ERRORS=""
CLEANING_SUMMARY=""

for bib_file in "${BIB_FILES[@]}"; do
    # Step 1: BibTeX syntax validation (blocks on errors)
    RESULT=$("$PYTHON" "$CLAUDE_PROJECT_DIR/.claude/hooks/bib_validator.py" "$bib_file" 2>&1 || true)
    if ! VALID=$(echo "$RESULT" | jq -r 'if has("valid") then .valid | tostring else "true" end' 2>/dev/null); then
        echo "WARNING: bib_validator.py produced non-JSON output: $RESULT" >&2
        SYNTAX_ERRORS="${SYNTAX_ERRORS}bib_validator.py crashed for $bib_file: $RESULT
"
        continue
    fi

    if [[ "$VALID" == "false" ]]; then
        ERRORS=$(echo "$RESULT" | jq -r '.errors[]' 2>/dev/null || echo "$RESULT")
        SYNTAX_ERRORS="${SYNTAX_ERRORS}${ERRORS}
"
    fi

    # Step 2: Metadata provenance cleaning (removes hallucinated fields, does NOT block)
    # Find JSON files via 3-location fallback:
    #   1. Same directory as .bib file
    #   2. $REVIEW_DIR/intermediate_files/json/
    #   3. Project root
    BIB_DIR=$(dirname "$bib_file")
    JSON_DIR=""

    shopt -s nullglob
    json_matches=("$BIB_DIR"/*.json)
    if [[ ${#json_matches[@]} -gt 0 ]]; then
        JSON_DIR="$BIB_DIR"
    else
        json_matches=("$REVIEW_DIR/intermediate_files/json"/*.json)
        if [[ -d "$REVIEW_DIR/intermediate_files/json" ]] && [[ ${#json_matches[@]} -gt 0 ]]; then
            JSON_DIR="$REVIEW_DIR/intermediate_files/json"
        else
            json_matches=("$CLAUDE_PROJECT_DIR"/*.json)
            if [[ ${#json_matches[@]} -gt 0 ]]; then
                JSON_DIR="$CLAUDE_PROJECT_DIR"
            fi
        fi
    fi
    shopt -u nullglob

    if [[ -n "$JSON_DIR" ]]; then
        CLEAN_RESULT=$("$PYTHON" "$CLAUDE_PROJECT_DIR/.claude/hooks/metadata_cleaner.py" "$bib_file" "$JSON_DIR" 2>&1 || true)
        FIELDS_REMOVED=$(echo "$CLEAN_RESULT" | jq -r '.total_fields_removed // 0' 2>/dev/null || echo "0")
        ENTRIES_CLEANED=$(echo "$CLEAN_RESULT" | jq -r '.entries_cleaned // 0' 2>/dev/null || echo "0")

        if [[ "$FIELDS_REMOVED" =~ ^[0-9]+$ ]] && [[ "$FIELDS_REMOVED" -gt 0 ]]; then
            CLEANED_ENTRIES=$(echo "$CLEAN_RESULT" | jq -r '.cleaned_entries | to_entries[] | "  - \(.key): \(.value | join(", "))"' 2>/dev/null || true)
            CLEANING_SUMMARY="${CLEANING_SUMMARY}
Cleaned $(basename "$bib_file"): Removed $FIELDS_REMOVED unverifiable field(s) from $ENTRIES_CLEANED entry(ies):
$CLEANED_ENTRIES
"
        fi
    fi
done

# Block only on syntax errors (not on metadata cleaning).
# Exit 0: the decision is carried in the JSON, not the exit code.
if [[ -n "$SYNTAX_ERRORS" ]]; then
    jq -cn --arg reason "$SYNTAX_ERRORS" '{"decision": "block", "reason": $reason}'
    exit 0
fi

# Surface cleaning summary to the model as non-error feedback (v2.1.163+;
# harmlessly ignored by older Claude Code versions).
if [[ -n "$CLEANING_SUMMARY" ]]; then
    jq -cn --arg ctx "METADATA CLEANING PERFORMED:$CLEANING_SUMMARY" \
        '{"hookSpecificOutput": {"hookEventName": "SubagentStop", "additionalContext": $ctx}}'
    exit 0
fi

allow
