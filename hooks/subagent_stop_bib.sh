#!/bin/bash
# BibTeX validation and cleaning hook for SubagentStop.
# Fires for ALL SubagentStop events (hooks.json registers it with no matcher)
# and self-scopes: it no-ops unless the cwd is a PhilLit workspace (.phillit
# marker), the agent_type contains domain-literature-researcher, and an
# .active-review pointer exists. When the researcher exits:
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
# Resumed pass (stop_hook_active=true): validation + cleaning still run (the
# cleaning ledger must reflect the FINAL pass), but a block is never emitted
# again — unresolved errors surface as a systemMessage instead.

set -e

allow() {
    echo '{"decision": "allow"}'
    exit 0
}

# Plugin hooks fire in every session; no-op outside a PhilLit workspace.
if [ ! -d "${CLAUDE_PROJECT_DIR:-$PWD}/.phillit" ]; then
    allow
fi

# Require jq for JSON parsing. Without it we cannot parse stdin (not even to
# scope by agent_type), so we allow — but LOUDLY: a stderr line on exit 0 is
# never surfaced by Claude Code, so carry the warning as a user-visible
# systemMessage instead (gate-failure policy: no gate failure is ever silent).
if ! command -v jq &> /dev/null; then
    echo '{"systemMessage": "PhilLit: jq is not installed - BibTeX validation was SKIPPED for this researcher. Install jq: brew install jq (macOS), apt install jq (Linux), choco install jq (Windows)."}'
    exit 0
fi

# Parse subagent context from stdin (Claude Code passes JSON via stdin)
SUBAGENT_CONTEXT=$(cat)

# Guard: on a re-invocation after a previous block (stop_hook_active), never
# emit another block (loop prevention) — but validation and cleaning STILL run,
# so the resumed (fixed) bib gets its final cleaning pass and the cleaning
# ledger reflects the final state. An early allow here would skip the cleaner
# on every resumed pass, leaving a stale ledger from the blocked pass — the
# evidence barrier assumes cleaning (and its ledger) precede it.
STOP_HOOK_ACTIVE=$(echo "$SUBAGENT_CONTEXT" | jq -r '.stop_hook_active // false')

# Self-scoping guard: this hook has no matcher, so it fires for every
# SubagentStop. Validate only when agent_type contains
# domain-literature-researcher (substring tolerates plugin namespacing, e.g.
# phillit:domain-literature-researcher); empty/missing agent_type also allows.
AGENT_TYPE=$(echo "$SUBAGENT_CONTEXT" | jq -r '.agent_type // empty')
if [[ "$AGENT_TYPE" != *"domain-literature-researcher"* ]]; then
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
    # Step 1: BibTeX syntax validation (blocks on errors). Capture stdout only —
    # the wrapper's uv writes warnings/build progress to stderr (e.g. a cold venv
    # on first run), which would otherwise corrupt the JSON parsed below. Keep
    # stderr in a temp file so a crash can be reported with its cause.
    STDERR_LOG=$(mktemp)
    RESULT=$(bash "$CLAUDE_PLUGIN_ROOT/bin/phillit-run" hooks/bib_validator.py "$bib_file" 2>"$STDERR_LOG" || true)
    if [[ -z "$RESULT" ]]; then
        # Fail CLOSED (gate-failure policy): empty output means the validator or
        # uv crashed before emitting JSON. jq exits 0 on empty input, so without
        # this check the crash would silently count as valid.
        ERR_TAIL=$(tail -c 400 "$STDERR_LOG" 2>/dev/null || true)
        rm -f "$STDERR_LOG"
        SYNTAX_ERRORS="${SYNTAX_ERRORS}bib_validator.py produced no output for $bib_file (uv or the validator crashed): ${ERR_TAIL}
"
        continue
    fi
    rm -f "$STDERR_LOG"
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
    # Item-13 A3: pass the UNION of JSON dirs (same dir as .bib AND
    # $REVIEW_DIR/intermediate_files/json) so directory shadowing no longer
    # starves the verification index. metadata_cleaner.py accepts one-or-more.
    # (The old $CLAUDE_PROJECT_DIR third fallback is dropped: a processed .bib
    # only ever sits at $REVIEW_DIR root or project root, so its own dir is
    # already indexed as (a).)
    BIB_DIR=$(dirname "$bib_file")
    JSON_DIRS=()

    shopt -s nullglob
    json_matches=("$BIB_DIR"/*.json)
    [[ ${#json_matches[@]} -gt 0 ]] && JSON_DIRS+=("$BIB_DIR")
    json_matches=("$REVIEW_DIR/intermediate_files/json"/*.json)
    if [[ -d "$REVIEW_DIR/intermediate_files/json" ]] && [[ ${#json_matches[@]} -gt 0 ]]; then
        JSON_DIRS+=("$REVIEW_DIR/intermediate_files/json")
    fi
    shopt -u nullglob

    if [[ ${#JSON_DIRS[@]} -gt 0 ]]; then
        # Capture stdout only, for the same reason step 1 does: uv writes
        # warnings/build progress to stderr on a cold venv, and merging that
        # into the JSON would make every first run look like a crash.
        CLEAN_STDERR_LOG=$(mktemp)
        CLEAN_STATUS=0
        CLEAN_RESULT=$(bash "$CLAUDE_PLUGIN_ROOT/bin/phillit-run" hooks/metadata_cleaner.py "$bib_file" "${JSON_DIRS[@]}" 2>"$CLEAN_STDERR_LOG") || CLEAN_STATUS=$?

        # Never-silent policy (the guard step 1 applies to bib_validator).
        # Three distinct failure shapes must all be caught, or a crash is
        # byte-identical to a clean run:
        #   1. non-JSON stdout (a bare traceback)
        #   2. empty stdout (`jq -r '.x // 0'` exits 0 on empty input)
        #   3. VALID JSON reporting failure -- metadata_cleaner.main() now
        #      emits {"success": false, "errors": [...]} and exits 2 on an
        #      unexpected exception, which passes a plain `jq -e .` and then
        #      reads as "0 fields removed". Checking only well-formedness
        #      would let the cleaner's own crash contract slip through.
        # So: require a zero exit AND an object whose .success is true.
        # Cleaning does not block, so this warns and moves on.
        if [[ $CLEAN_STATUS -ne 0 ]] || \
           ! echo "$CLEAN_RESULT" | jq -e 'type == "object" and .success == true' >/dev/null 2>&1; then
            CLEAN_ERR_TAIL=$(tail -c 400 "$CLEAN_STDERR_LOG" 2>/dev/null || true)
            rm -f "$CLEAN_STDERR_LOG"
            # Prefer the structured .errors[] when the payload parsed at all.
            CLEAN_REPORTED=$(echo "$CLEAN_RESULT" | jq -r '.errors[]?' 2>/dev/null || true)
            # Cap the raw fallback the same way CLEAN_ERR_TAIL is capped: a
            # library that dumps a huge repr to stdout must not push megabytes
            # into the hook's JSON output.
            [[ -z "$CLEAN_REPORTED" ]] && CLEAN_REPORTED=$(echo "$CLEAN_RESULT" | tail -c 1000)
            echo "WARNING: metadata_cleaner.py failed (exit $CLEAN_STATUS) for $bib_file: ${CLEAN_REPORTED}${CLEAN_ERR_TAIL}" >&2
            CLEANING_SUMMARY="${CLEANING_SUMMARY}
metadata_cleaner.py FAILED for $(basename "$bib_file") (exit $CLEAN_STATUS) - metadata was NOT verified:
${CLEAN_REPORTED}${CLEAN_ERR_TAIL}
"
            continue
        fi
        rm -f "$CLEAN_STDERR_LOG"

        FIELDS_REMOVED=$(echo "$CLEAN_RESULT" | jq -r '.total_fields_removed // 0' 2>/dev/null || echo "0")
        ENTRIES_CLEANED=$(echo "$CLEAN_RESULT" | jq -r '.entries_cleaned // 0' 2>/dev/null || echo "0")

        if [[ "$FIELDS_REMOVED" =~ ^[0-9]+$ ]] && [[ "$FIELDS_REMOVED" -gt 0 ]]; then
            CLEANED_ENTRIES=$(echo "$CLEAN_RESULT" | jq -r '.cleaned_entries | to_entries[] | "  - \(.key): \(.value | join(", "))"' 2>/dev/null || true)
            CLEANING_SUMMARY="${CLEANING_SUMMARY}
Cleaned $(basename "$bib_file"): Removed $FIELDS_REMOVED unverifiable field(s) from $ENTRIES_CLEANED entry(ies):
$CLEANED_ENTRIES
"
        fi

        # Item-13 A3 (never-silent policy): surface cleaner warnings — salvage/
        # skip notices and, after W3, a circuit-breaker trip — to the model.
        # Without this a tripped breaker is byte-identical to a clean run (the
        # original incident's silence). Reuses the additionalContext emission.
        CLEAN_WARNINGS=$(echo "$CLEAN_RESULT" | jq -r '.warnings[]?' 2>/dev/null || true)
        if [[ -n "$CLEAN_WARNINGS" ]]; then
            CLEANING_SUMMARY="${CLEANING_SUMMARY}
Cleaner warnings for $(basename "$bib_file"):
$CLEAN_WARNINGS
"
        fi
    fi
done

# Block only on syntax errors (not on metadata cleaning).
# Exit 0: the decision is carried in the JSON, not the exit code.
if [[ -n "$SYNTAX_ERRORS" ]]; then
    if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
        # Resumed pass: never re-block (infinite-loop prevention), but never
        # silent either (gate-failure policy) — surface the unresolved errors
        # to the user as a systemMessage.
        jq -cn --arg msg "PhilLit: BibTeX errors remain after the researcher's resumed pass (not re-blocking to avoid a stop-hook loop): $SYNTAX_ERRORS" \
            '{"systemMessage": $msg}'
        exit 0
    fi
    jq -cn --arg reason "$SYNTAX_ERRORS" '{"decision": "block", "reason": $reason}'
    exit 0
fi

# Surface cleaning summary to the model as non-error feedback (v2.1.163+;
# harmlessly ignored by older Claude Code versions).
if [[ -n "$CLEANING_SUMMARY" ]]; then
    jq -cn --arg ctx "METADATA CLEANING REPORT:$CLEANING_SUMMARY" \
        '{"hookSpecificOutput": {"hookEventName": "SubagentStop", "additionalContext": $ctx}}'
    exit 0
fi

allow
