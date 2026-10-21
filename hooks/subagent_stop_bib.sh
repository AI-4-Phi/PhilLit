#!/bin/bash
# BibTeX validation and cleaning hook for SubagentStop.
# Fires for ALL SubagentStop events (hooks.json registers it with no matcher)
# and self-scopes: it no-ops unless the cwd is a PhilLit workspace (.phillit
# marker), the agent_type contains domain-literature-researcher, and
# workdir.py resolves an active review. When the researcher exits, for the
# bibs THIS researcher owns (researcher_bibs.py; every bib, visibly, when
# that cannot be told):
#   1. Validates BibTeX syntax — blocks on errors (agent must fix them)
#   2. Cleans hallucinated metadata fields and corrects years — never a
#      decision, but its report is sent on the FIRST pass only (below)
#
# Protocol: ALL decisions are stdout JSON with exit code 0.
#   Block: {"decision": "block", "reason": "<errors>"}
#   Allow: {} - omit `decision`. For this event Claude Code documents only
#     "block", and it rejects "allow" as invalid hook output.
#   Allow + cleaning summary: {"hookSpecificOutput": {"hookEventName":
#     "SubagentStop", "additionalContext": "<summary>"}}
#     This is NOT a passive note: Claude Code treats a SubagentStop
#     additionalContext like a block and continues the subagent's turn
#     (capped by CLAUDE_CODE_STOP_HOOK_BLOCK_CAP, default 8). Sent on every
#     pass, it kept each researcher answering the same report until the cap.
#     So it is sent once, on the first pass (stop_hook_active=false).
# Never exit 2: Claude Code ignores stdout JSON on exit 2, so the reason
# would be lost and the agent would see only stderr.
# Resumed pass (stop_hook_active=true): validation + cleaning still run (the
# cleaning ledger must reflect the FINAL pass), but a block is never emitted
# again — unresolved errors surface as a systemMessage instead — and the
# cleaning report is not sent again: the pass allows with {}, or with a
# systemMessage when the cleaner itself failed (never silent, and a
# systemMessage does not continue the turn). Accepted cost: a warning that
# first appears on a resumed pass (say, after the researcher edited its bib
# in reply to the report) is not sent either; the barrier's report is the
# backstop. Do not "fix" this by re-sending: that restores the turn loop.

set -e

# Any command that kills the script under set -e would exit nonzero with no
# JSON, and Claude Code treats that as an allow: a SILENT fail-open. The trap
# turns it into a decision. Fixed text only (no jq: it may be the failure).
# It blocks only on a first pass that is KNOWN to be one; on a resumed pass,
# or before stdin is parsed, it allows visibly, so a crash cannot loop.
# Never interpolate a variable into its printf: only $LINENO (a number) is
# safe there; a quote in a path would break the JSON. Functions do not
# inherit the trap (no set -E: the trap would then fire inside $(...) and
# print into the captured value), so each function's jq carries its own
# || fallback. SIGKILL and a bash that cannot start stay uncatchable.
STOP_HOOK_ACTIVE=""
on_error() {
    local msg="subagent_stop_bib.sh failed at line $1 - BibTeX validation and cleaning did not complete for this researcher."
    if [[ "$STOP_HOOK_ACTIVE" == "false" ]]; then
        printf '{"decision": "block", "reason": "%s"}\n' "$msg"
    else
        printf '{"systemMessage": "PhilLit: %s"}\n' "$msg"
    fi
    exit 0
}
trap 'on_error $LINENO' ERR

allow() {
    echo '{}'
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
# A native jq.exe under Git Bash ends its output in CRLF and $(...) strips
# only the LF: a bare "true\r" would defeat the loop guard. Strip the one
# trailing CR from every scalar compared below.
STOP_HOOK_ACTIVE=${STOP_HOOK_ACTIVE%$'\r'}
[[ "$STOP_HOOK_ACTIVE" == "true" ]] || STOP_HOOK_ACTIVE="false"   # one reading for the trap and the main path

# Self-scoping guard: this hook has no matcher, so it fires for every
# SubagentStop. Validate only when agent_type contains
# domain-literature-researcher (substring tolerates plugin namespacing, e.g.
# phillit:domain-literature-researcher); empty/missing agent_type also allows.
AGENT_TYPE=$(echo "$SUBAGENT_CONTEXT" | jq -r '.agent_type // empty')
AGENT_TYPE=${AGENT_TYPE%$'\r'}
if [[ "$AGENT_TYPE" != *"domain-literature-researcher"* ]]; then
    allow
fi

# Resolve the review's working directory through workdir.py, the one owner of
# the pointer: a local review works OUTSIDE the workspace
# (~/.local/state/phillit/reviews/...), so the pointer is no longer a path to
# paste. It runs FROM the workspace (a subshell cd), so its .env - which may
# set PHILLIT_WORKDIR - is the one that loads. Capture stdout only (uv writes
# build progress to stderr). The output must be exactly one JSON object,
# either {"workdir": <non-empty string>} or {"error": <string>}. Anything
# else - a nonzero exit, empty or non-JSON output, another shape - is a
# resolver CRASH and fails CLOSED like a validator crash: this is an
# accuracy gate. A resolver {error} (no pointer, files on another machine)
# allows with a visible systemMessage (below). workdir.py exits 1 for a
# configuration error (a bad PHILLIT_WORKDIR, or the inplace pin meeting a
# local review), so a config typo blocks loudly instead of skipping
# validation.
RESOLVE_WS="${CLAUDE_PROJECT_DIR:-$PWD}"
RESOLVE_STDERR=$(mktemp)
RESOLVE_STATUS=0
RESOLVED=$(cd "$RESOLVE_WS" && bash "$CLAUDE_PLUGIN_ROOT/bin/phillit-run" \
    skills/literature-review/scripts/workdir.py --workspace "$RESOLVE_WS" resolve \
    2>"$RESOLVE_STDERR") || RESOLVE_STATUS=$?
RESOLVE_SHAPE='length == 1 and (.[0] | type == "object" and (
    (keys == ["workdir"] and (.workdir | type == "string" and length > 0))
    or (keys == ["error"] and (.error | type == "string"))))'
if [[ $RESOLVE_STATUS -ne 0 ]] || [[ -z "$RESOLVED" ]] || \
   ! echo "$RESOLVED" | jq -se "$RESOLVE_SHAPE" >/dev/null 2>&1; then
    RESOLVE_ERR_TAIL=$(tail -c 400 "$RESOLVE_STDERR" 2>/dev/null || true)
    rm -f "$RESOLVE_STDERR"
    RESOLVE_OUT_TAIL=$(echo "$RESOLVED" | tail -c 400)
    RESOLVE_MSG="workdir.py resolve failed (exit $RESOLVE_STATUS, or its output was not one JSON object of the expected shape): could not resolve the review directory, so BibTeX validation did not run. ${RESOLVE_OUT_TAIL} ${RESOLVE_ERR_TAIL}"
    if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
        jq -cn --arg msg "PhilLit: $RESOLVE_MSG" '{"systemMessage": $msg}'
        exit 0
    fi
    jq -cn --arg reason "$RESOLVE_MSG" '{"decision": "block", "reason": $reason}'
    exit 0
fi
rm -f "$RESOLVE_STDERR"

# A review-state error (no pointer, files elsewhere or missing) allows the
# stop: the researcher cannot repair it, so a block would only cost a turn
# and end in the same state. But never silently - stderr on exit 0 is never
# shown, so the skip rides a user-visible systemMessage (gate-failure
# policy). The barrier reports the missing cleaning ledger as degraded.
skipped() {
    jq -cn --arg msg "PhilLit: $1 - BibTeX validation and metadata cleaning were SKIPPED for this researcher." \
        '{"systemMessage": $msg}' \
        || printf '{"systemMessage": "PhilLit: BibTeX validation and metadata cleaning were SKIPPED for this researcher (the report could not be rendered)."}\n'
    exit 0
}

# A native jq.exe under Git Bash emits CRLF, and $(...) strips only the LF.
REVIEW_DIR=$(echo "$RESOLVED" | jq -r '.workdir // empty')
REVIEW_DIR=${REVIEW_DIR%$'\r'}
if [[ -z "$REVIEW_DIR" ]]; then
    RESOLVE_ERROR=$(echo "$RESOLVED" | jq -r '.error')
    skipped "no active review directory (${RESOLVE_ERROR%$'\r'})"
fi

if [[ ! -d "$REVIEW_DIR" ]]; then
    skipped "the review directory $REVIEW_DIR does not exist"
fi

# Collect .bib files from the review directory AND the researchers' strays in
# the project root: domain bibs written without the review-directory prefix.
# The root glob takes literature-domain-*.bib alone: that prefix is PhilLit's
# namespace (researchers write it, and Phase 6's stray sweep moves every root
# file that has it). Any other root .bib is outside it, so it is treated as
# the user's own file: the cleaner rewrites what it processes.
# Uses globs instead of find+process substitution for Windows/Git Bash compatibility
shopt -s nullglob
BIB_FILES=()
for f in "$REVIEW_DIR"/*.bib; do
    [[ -f "$f" ]] && BIB_FILES+=("$f")
done
for f in "$RESOLVE_WS"/literature-domain-*.bib; do
    [[ -f "$f" ]] && BIB_FILES+=("$f")
done
shopt -u nullglob

# Every decision after scoping goes out through here, so the scoping notes
# (SCOPE_NOTE: the owner could not be told; MISSING_NOTE: the owner's
# assigned bib is not on disk) reach the user as a systemMessage beside it,
# on a resumed pass too: a systemMessage does not continue the turn. If the
# merge fails, the decision itself still goes out (a block must never be
# lost), and a bare allow carries a fixed note instead.
emit() {
    local out="$1" notes=""
    [[ -n "$SCOPE_NOTE" ]] && notes="PhilLit: $SCOPE_NOTE"
    [[ -n "$MISSING_NOTE" ]] && notes="${notes:+$notes
}PhilLit: $MISSING_NOTE"
    if [[ -n "$notes" ]]; then
        out=$(printf '%s\n' "$1" | jq -c --arg n "$notes" \
            'if .systemMessage then .systemMessage += "\n" + $n else . + {systemMessage: $n} end' 2>/dev/null) \
            || out=""
        if [[ -z "$out" ]]; then
            out="$1"
            [[ "$out" == "{}" ]] && out='{"systemMessage": "PhilLit: this researcher'"'"'s bib could not be scoped or found; see the hook for details."}'
        fi
    fi
    printf '%s\n' "$out"
    exit 0
}

# Scope to the stopping researcher's own files. Researchers run in parallel,
# so cleaning every bib here rewrote files siblings were still writing and
# reported their corrections to the wrong researcher. researcher_bibs.py
# names this researcher's files from its transcript (its docstring has the
# rule). When it names none or fails, fall back to every bib - the behaviour
# before scoping, so nothing goes unvalidated - and say so: to the user
# (SCOPE_NOTE) and to the researcher (SCOPE_CAVEAT, on its block reason or
# report, so it does not take a sibling's errors for its own). This is
# plumbing, so it fails open, never silently. Accepted cost: a bib is
# cleaned against the JSON present at ITS researcher's stop, so a sibling's
# CrossRef record written later no longer reaches it; the sweep that once did
# that is the same sweep that rewrote files mid-write.
SCOPE_NOTE=""
SCOPE_CAVEAT=""
MISSING_NOTE=""
OWNED_STATUS=0
OWNED_STDERR=$(mktemp)
OWNED=$(printf '%s\n' "$SUBAGENT_CONTEXT" | bash "$CLAUDE_PLUGIN_ROOT/bin/phillit-run" \
    hooks/researcher_bibs.py 2>"$OWNED_STDERR") || OWNED_STATUS=$?
OWNED_ERR_TAIL=$(tail -c 300 "$OWNED_STDERR" 2>/dev/null || true)
rm -f "$OWNED_STDERR"
# One answer: an object whose "bibs" is a nonempty array of plain basenames
# (and "assigned", if present, the same); anything else is no answer.
OWNED_SHAPE='length == 1 and (.[0] | type) == "object"
    and (.[0].bibs | type) == "array" and (.[0].bibs | length) > 0
    and ((.[0].assigned // []) | type) == "array"
    and all((.[0].bibs + (.[0].assigned // []))[];
            type == "string" and length > 0 and (test("[\n\r/\\\\]") | not))'
OWNED_NAMES=""
ASSIGNED_NAMES=""
if [[ $OWNED_STATUS -eq 0 ]] && \
   OWNED_NAMES=$(printf '%s\n' "$OWNED" | jq -ser "if $OWNED_SHAPE then .[0].bibs[] else error(\"shape\") end" 2>/dev/null); then
    ASSIGNED_NAMES=$(printf '%s\n' "$OWNED" | jq -sr '.[0].assigned // [] | .[]' 2>/dev/null || true)
else
    OWNED_NAMES=""
fi
if [[ -n "$OWNED_NAMES" ]]; then
    SCOPED=()
    shopt -s nocasematch    # case-insensitive filesystems (macOS, Windows)
    for f in ${BIB_FILES[@]+"${BIB_FILES[@]}"}; do
        base=$(basename "$f")
        while IFS= read -r name; do
            name=${name%$'\r'}
            if [[ "$base" == "$name" ]]; then
                SCOPED+=("$f")
                break
            fi
        done <<< "$OWNED_NAMES"
    done
    # An assigned bib that matched no swept file was never validated here:
    # the researcher stopped without writing it, or wrote it where the sweep
    # does not look. Say so, even when another owned file was processed.
    MISSING=""
    while IFS= read -r name; do
        name=${name%$'\r'}
        [[ -z "$name" ]] && continue
        found=""
        for f in ${SCOPED[@]+"${SCOPED[@]}"}; do
            [[ "$(basename "$f")" == "$name" ]] && found=1 && break
        done
        [[ -z "$found" ]] && MISSING="${MISSING:+$MISSING, }$name"
    done <<< "$ASSIGNED_NAMES"
    shopt -u nocasematch
    BIB_FILES=(${SCOPED[@]+"${SCOPED[@]}"})
    if [[ -n "$MISSING" ]]; then
        MISSING_NOTE="this researcher's bib ($MISSING) was not found in the review folder or the workspace root, so it was not validated or cleaned here. The evidence barrier reports the domain."
    fi
else
    OWNED_REASON=$(printf '%s\n' "$OWNED" | jq -r '.reason // empty' 2>/dev/null || true)
    OWNED_REASON=${OWNED_REASON%$'\r'}
    if [[ -z "$OWNED_REASON" ]]; then
        if [[ $OWNED_STATUS -eq 0 ]]; then
            OWNED_REASON="researcher_bibs.py exited 0 but did not give one {\"bibs\": [...]} answer"
        else
            OWNED_REASON="researcher_bibs.py failed (exit $OWNED_STATUS): $OWNED_ERR_TAIL"
        fi
    fi
    if [[ ${#BIB_FILES[@]} -eq 0 ]]; then
        SCOPE_NOTE="could not tell which bib this researcher owns ($OWNED_REASON), and no domain bib was found, so nothing was validated."
    else
        SCOPE_NOTE="could not tell which bib this researcher owns ($OWNED_REASON), so every domain bib was validated and cleaned, including any a parallel researcher is still writing."
        SCOPE_CAVEAT="NOTE: PhilLit could not tell which bib file is yours, so what follows covers every domain bib in the review. Fix only errors in your own file; another researcher may still be writing the others."
    fi
fi

# No .bib files found — nothing to validate (any note above goes out).
if [[ ${#BIB_FILES[@]} -eq 0 ]]; then
    emit '{}'
fi

# Track syntax errors (these block) and cleaning summaries (informational).
# CLEANING_FAILURES repeats the cleaner-failure lines of CLEANING_SUMMARY:
# the one part a resumed pass still reports.
SYNTAX_ERRORS=""
CLEANING_SUMMARY=""
CLEANING_FAILURES=""

for bib_file in "${BIB_FILES[@]}"; do
    # Step 1: BibTeX syntax validation (blocks on errors). Capture stdout only —
    # the wrapper's uv writes warnings/build progress to stderr (e.g. a cold venv
    # on first run), which would otherwise corrupt the JSON parsed below. Keep
    # stderr in a temp file so a crash can be reported with its cause.
    STDERR_LOG=$(mktemp)
    VALIDATOR_STATUS=0
    RESULT=$(bash "$CLAUDE_PLUGIN_ROOT/bin/phillit-run" hooks/bib_validator.py "$bib_file" 2>"$STDERR_LOG") || VALIDATOR_STATUS=$?
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
    # Fail closed on any shape but an object with a boolean `valid`: a
    # missing or non-boolean field once read as valid, a silent pass.
    if ! VALID=$(echo "$RESULT" | jq -r 'if type == "object" and (.valid | type) == "boolean" then .valid | tostring else error("no boolean valid") end' 2>/dev/null); then
        echo "WARNING: bib_validator.py output was not an object with a boolean valid: $RESULT" >&2
        SYNTAX_ERRORS="${SYNTAX_ERRORS}bib_validator.py crashed for $bib_file: $RESULT
"
        continue
    fi
    VALID=${VALID%$'\r'}
    # Exactly one true or false: whitespace-only output parses to NO value
    # (jq exits 0, VALID empty) and two objects give "false<LF>false", and
    # either would otherwise read as valid. Exit status cannot replace this:
    # the validator exits 1 for invalid BibTeX AND for an uncaught exception.
    if [[ "$VALID" != "true" && "$VALID" != "false" ]]; then
        SYNTAX_ERRORS="${SYNTAX_ERRORS}bib_validator.py crashed for $bib_file (output was not exactly one true or false valid): $RESULT
"
        continue
    fi

    # A valid file exits 0. "valid": true with a nonzero exit means the
    # process failed after printing, so it is a crash, not a pass.
    if [[ "$VALID" == "true" && "$VALIDATOR_STATUS" -ne 0 ]]; then
        SYNTAX_ERRORS="${SYNTAX_ERRORS}bib_validator.py exited $VALIDATOR_STATUS for $bib_file after reporting it valid (treated as a crash): $RESULT
"
        continue
    fi

    if [[ "$VALID" == "false" ]]; then
        ERRORS=$(echo "$RESULT" | jq -r '.errors[]' 2>/dev/null || echo "$RESULT")
        SYNTAX_ERRORS="${SYNTAX_ERRORS}${ERRORS}
"
    fi

    # Step 2: Metadata provenance cleaning (removes hallucinated fields, does NOT block)
    # Pass the UNION of JSON dirs (same dir as .bib AND
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
            CLEAN_FAILURE="
metadata_cleaner.py FAILED for $(basename "$bib_file") (exit $CLEAN_STATUS) - metadata was NOT verified:
${CLEAN_REPORTED}${CLEAN_ERR_TAIL}
"
            CLEANING_SUMMARY="${CLEANING_SUMMARY}${CLEAN_FAILURE}"
            CLEANING_FAILURES="${CLEANING_FAILURES}${CLEAN_FAILURE}"
            continue
        fi
        rm -f "$CLEAN_STDERR_LOG"

        FIELDS_REMOVED=$(echo "$CLEAN_RESULT" | jq -r '.total_fields_removed // 0' 2>/dev/null || echo "0")
        ENTRIES_CLEANED=$(echo "$CLEAN_RESULT" | jq -r '.entries_cleaned // 0' 2>/dev/null || echo "0")
        FIELDS_REMOVED=${FIELDS_REMOVED%$'\r'}
        ENTRIES_CLEANED=${ENTRIES_CLEANED%$'\r'}

        if [[ "$FIELDS_REMOVED" =~ ^[0-9]+$ ]] && [[ "$FIELDS_REMOVED" -gt 0 ]]; then
            CLEANED_ENTRIES=$(echo "$CLEAN_RESULT" | jq -r '.cleaned_entries | to_entries[] | "  - \(.key): \(.value | join(", "))"' 2>/dev/null || true)
            CLEANING_SUMMARY="${CLEANING_SUMMARY}
Cleaned $(basename "$bib_file"): Removed $FIELDS_REMOVED unverifiable field(s) from $ENTRIES_CLEANED entry(ies):
$CLEANED_ENTRIES
"
        fi

        # A year rewrite is reported on its own, removals or not: the
        # METADATA_CLEANED marker records it in the bib, but without this
        # line the researcher never learns its year changed.
        YEAR_CORRECTIONS=$(echo "$CLEAN_RESULT" | jq -r '.applied_year_corrections[]? | "  - \(.key): \(.old) -> \(.new) (\(.source_file), \(.year_basis // "basis not recorded"))"' 2>/dev/null || true)
        if [[ -n "$YEAR_CORRECTIONS" ]]; then
            CLEANING_SUMMARY="${CLEANING_SUMMARY}
Corrected year(s) in $(basename "$bib_file") from the entry's own CrossRef record:
$YEAR_CORRECTIONS
"
        fi

        # Never-silent policy: surface cleaner warnings — salvage/
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
        RESUMED_OUT=$(jq -cn --arg msg "PhilLit: BibTeX errors remain after the researcher's resumed pass (not re-blocking to avoid a stop-hook loop): $SYNTAX_ERRORS$CLEANING_FAILURES" \
            '{"systemMessage": $msg}')
        emit "$RESUMED_OUT"
    fi
    # First pass: the block is the one continuation this stop gets, and the
    # resumed pass sends no cleaning report, so the report rides in the block
    # reason - otherwise a year correction made on this pass is never shown.
    BLOCK_REASON="$SYNTAX_ERRORS"
    if [[ -n "$CLEANING_SUMMARY" ]]; then
        BLOCK_REASON="${SYNTAX_ERRORS}
METADATA CLEANING REPORT:${CLEANING_SUMMARY}"
    fi
    BLOCK_REASON="${SCOPE_CAVEAT:+$SCOPE_CAVEAT

}$BLOCK_REASON"
    # An assignment, so a failed jq reaches the ERR trap (a block) instead
    # of handing emit an empty decision, a silent allow.
    BLOCK_OUT=$(jq -cn --arg reason "$BLOCK_REASON" '{"decision": "block", "reason": $reason}')
    emit "$BLOCK_OUT"
fi

# Resumed pass: the report went out on the first pass, and sending it again
# would continue the turn again. Only a cleaner failure is reported, to the
# user, as a systemMessage (gate-failure policy: never silent).
if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
    if [[ -n "$CLEANING_FAILURES" ]]; then
        RESUMED_OUT=$(jq -cn --arg msg "PhilLit: metadata cleaning failed on the researcher's resumed pass:$CLEANING_FAILURES" \
            '{"systemMessage": $msg}') \
            || RESUMED_OUT='{"systemMessage": "PhilLit: metadata cleaning failed on a resumed pass, and its report could not be rendered."}'
        emit "$RESUMED_OUT"
    fi
    emit '{}'
fi

# First pass: send the cleaning summary to the model as additionalContext.
# This continues the subagent's turn (see the header), which is why it is
# sent on the first pass only.
if [[ -n "$CLEANING_SUMMARY" ]]; then
    # A failed rendering must not reach the ERR trap: cleaning never blocks.
    CTX_OUT=$(jq -cn --arg ctx "${SCOPE_CAVEAT:+$SCOPE_CAVEAT

}METADATA CLEANING REPORT:$CLEANING_SUMMARY" \
        '{"hookSpecificOutput": {"hookEventName": "SubagentStop", "additionalContext": $ctx}}') \
        || CTX_OUT='{"systemMessage": "PhilLit: metadata cleaning ran, but its report could not be rendered."}'
    emit "$CTX_OUT"
fi

emit '{}'
