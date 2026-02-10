#!/bin/bash
# BibTeX validation and cleaning hook for SubagentStop
# When domain-literature-researcher agent exits:
# 1. Validates BibTeX syntax (blocks on errors - must be fixed)
# 2. Cleans hallucinated metadata fields (removes unverifiable fields, does not block)
# Returns JSON with decision: "allow" or "block" with reason.

set -e

# Resolve project Python (cross-platform)
if [[ -x "$CLAUDE_PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$CLAUDE_PROJECT_DIR/.venv/bin/python"
elif [[ -x "$CLAUDE_PROJECT_DIR/.venv/Scripts/python" ]]; then
    PYTHON="$CLAUDE_PROJECT_DIR/.venv/Scripts/python"
else
    echo "WARNING: Project venv not found — skipping BibTeX validation" >&2
    echo '{"decision": "allow"}'
    exit 0
fi

# Require jq for JSON parsing
if ! command -v jq &> /dev/null; then
    echo "WARNING: jq not installed — skipping BibTeX validation. Install with: brew install jq (macOS), apt install jq (Linux), or choco install jq (Windows)" >&2
    echo '{"decision": "allow"}'
    exit 0
fi

# Parse subagent context from stdin (Claude Code passes JSON via stdin)
SUBAGENT_CONTEXT=$(cat)

echo "DEBUG [subagent_stop_bib]: hook invoked" >&2

# Guard: if this is a re-invocation after a previous block, allow to prevent loops
STOP_HOOK_ACTIVE=$(echo "$SUBAGENT_CONTEXT" | jq -r '.stop_hook_active // false')
if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
    echo "DEBUG [subagent_stop_bib]: stop_hook_active=true, allowing to prevent loop" >&2
    echo '{"decision": "allow"}'
    exit 0
fi

# Extract agent type (documented field with fallback for older versions)
AGENT_TYPE=$(echo "$SUBAGENT_CONTEXT" | jq -r '.agent_type // .subagent_type // .agent_name // empty')
echo "DEBUG [subagent_stop_bib]: agent_type=$AGENT_TYPE" >&2

# Only process for domain-literature-researcher agent
if [[ "$AGENT_TYPE" != "domain-literature-researcher" ]]; then
    echo "DEBUG [subagent_stop_bib]: not domain-literature-researcher, allowing" >&2
    echo '{"decision": "allow"}'
    exit 0
fi

# Read .active-review pointer to find review directory
POINTER="$CLAUDE_PROJECT_DIR/reviews/.active-review"
if [[ ! -f "$POINTER" ]]; then
    echo "WARNING: No .active-review pointer found — skipping BibTeX validation" >&2
    echo '{"decision": "allow"}'
    exit 0
fi

POINTER_CONTENT=$(tr -d '\r\n' < "$POINTER")

# Validate pointer content (must start with reviews/)
if [[ ! "$POINTER_CONTENT" =~ ^reviews/ ]]; then
    echo "WARNING: Invalid .active-review pointer content: $POINTER_CONTENT" >&2
    echo '{"decision": "allow"}'
    exit 0
fi

REVIEW_DIR="$CLAUDE_PROJECT_DIR/$POINTER_CONTENT"

# Validate directory exists
if [[ ! -d "$REVIEW_DIR" ]]; then
    echo "WARNING: Review directory $REVIEW_DIR does not exist" >&2
    echo '{"decision": "allow"}'
    exit 0
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
    echo '{"decision": "allow"}'
    exit 0
fi

# Track syntax errors (these block) and cleaning summaries (informational)
SYNTAX_ERRORS=""
CLEANING_SUMMARY=""

for bib_file in "${BIB_FILES[@]}"; do
    # Step 1: BibTeX syntax validation (blocks on errors)
    RESULT=$($PYTHON "$CLAUDE_PROJECT_DIR/.claude/hooks/bib_validator.py" "$bib_file" 2>&1 || true)
    if ! VALID=$(echo "$RESULT" | jq -r '.valid // "true"' 2>/dev/null); then
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
        CLEAN_RESULT=$($PYTHON "$CLAUDE_PROJECT_DIR/.claude/hooks/metadata_cleaner.py" "$bib_file" "$JSON_DIR" --backup 2>&1 || true)
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

# Block only on syntax errors (not on metadata cleaning)
if [[ -n "$SYNTAX_ERRORS" ]]; then
    echo "DEBUG [subagent_stop_bib]: blocking — syntax errors found" >&2
    REASON=$(printf '%s' "$SYNTAX_ERRORS" | jq -Rs .)
    echo "{\"decision\": \"block\", \"reason\": $REASON}"
    exit 2
fi

# If we cleaned any fields, include summary in allow message (informational)
if [[ -n "$CLEANING_SUMMARY" ]]; then
    echo "METADATA CLEANING PERFORMED:$CLEANING_SUMMARY" >&2
fi

echo "DEBUG [subagent_stop_bib]: allowing" >&2
echo '{"decision": "allow"}'
exit 0
