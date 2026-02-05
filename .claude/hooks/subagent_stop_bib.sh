#!/bin/bash
# BibTeX validation and cleaning hook for SubagentStop
# When domain-literature-researcher agent exits:
# 1. Validates BibTeX syntax (blocks on errors - must be fixed)
# 2. Cleans hallucinated metadata fields (removes unverifiable fields, does not block)
# Returns JSON with decision: "allow" or "block" with reason.

set -e

# Parse subagent context from stdin (Claude Code passes JSON via stdin)
SUBAGENT_CONTEXT=$(cat)

# Extract agent name and working directory
AGENT_NAME=$(echo "$SUBAGENT_CONTEXT" | jq -r '.agent_name // .subagent_type // empty')
WORKING_DIR=$(echo "$SUBAGENT_CONTEXT" | jq -r '.cwd // "."')

# Only process for domain-literature-researcher agent
if [[ "$AGENT_NAME" != "domain-literature-researcher" ]]; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Check if any .bib files exist in working directory
if ! find "$WORKING_DIR" -maxdepth 1 -name "*.bib" -type f -print -quit 2>/dev/null | grep -q .; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Track syntax errors (these block) and cleaning summaries (informational)
SYNTAX_ERRORS=""
CLEANING_SUMMARY=""

# Process .bib files with proper null-delimiter handling for filenames with spaces
while IFS= read -r -d '' bib_file; do
    # Step 1: BibTeX syntax validation (blocks on errors)
    RESULT=$(python "$CLAUDE_PROJECT_DIR/.claude/hooks/bib_validator.py" "$bib_file" 2>&1 || true)
    VALID=$(echo "$RESULT" | jq -r '.valid // "true"')

    if [[ "$VALID" == "false" ]]; then
        ERRORS=$(echo "$RESULT" | jq -r '.errors[]' 2>/dev/null || echo "$RESULT")
        SYNTAX_ERRORS="${SYNTAX_ERRORS}${ERRORS}
"
    fi

    # Step 2: Metadata provenance cleaning (removes hallucinated fields, does NOT block)
    # JSON files are in working directory during subagent execution,
    # moved to intermediate_files/json/ only during Phase 6 assembly
    JSON_DIR="${WORKING_DIR}"
    # Fall back to intermediate_files/json if no JSON files in working directory
    if ! find "$JSON_DIR" -maxdepth 1 -name "*.json" -type f -print -quit 2>/dev/null | grep -q .; then
        JSON_DIR="${WORKING_DIR}/intermediate_files/json"
    fi
    if [[ -d "$JSON_DIR" ]] && find "$JSON_DIR" -maxdepth 1 -name "*.json" -type f -print -quit 2>/dev/null | grep -q .; then
        CLEAN_RESULT=$(python "$CLAUDE_PROJECT_DIR/.claude/hooks/metadata_cleaner.py" "$bib_file" "$JSON_DIR" --backup 2>&1 || true)
        FIELDS_REMOVED=$(echo "$CLEAN_RESULT" | jq -r '.total_fields_removed // 0')
        ENTRIES_CLEANED=$(echo "$CLEAN_RESULT" | jq -r '.entries_cleaned // 0')

        if [[ "$FIELDS_REMOVED" =~ ^[0-9]+$ ]] && [[ "$FIELDS_REMOVED" -gt 0 ]]; then
            # Log what was cleaned (informational, not blocking)
            CLEANED_ENTRIES=$(echo "$CLEAN_RESULT" | jq -r '.cleaned_entries | to_entries[] | "  - \(.key): \(.value | join(", "))"' 2>/dev/null || true)
            CLEANING_SUMMARY="${CLEANING_SUMMARY}
Cleaned $(basename "$bib_file"): Removed $FIELDS_REMOVED unverifiable field(s) from $ENTRIES_CLEANED entry(ies):
$CLEANED_ENTRIES
"
        fi
    fi
done < <(find "$WORKING_DIR" -maxdepth 1 -name "*.bib" -type f -print0 2>/dev/null)

# Block only on syntax errors (not on metadata cleaning)
if [[ -n "$SYNTAX_ERRORS" ]]; then
    REASON=$(printf '%s' "$SYNTAX_ERRORS" | jq -Rs .)
    echo "{\"decision\": \"block\", \"reason\": $REASON}"
    exit 2
fi

# If we cleaned any fields, include summary in allow message (informational)
if [[ -n "$CLEANING_SUMMARY" ]]; then
    # Log to stderr for visibility (Claude Code shows this)
    echo "METADATA CLEANING PERFORMED:$CLEANING_SUMMARY" >&2
fi

echo '{"decision": "allow"}'
exit 0
