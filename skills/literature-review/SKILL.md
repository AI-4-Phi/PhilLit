---
name: literature-review
description: Coordinate comprehensive literature reviews on any research topic in philosophy. Manages 6-phase workflow including domain decomposition, literature search, and synthesis. Use proactively when user requests a literature review.
allowed-tools: Bash, Read, Write, Grep, Glob, Edit
---

# Literature Review Workflow

## Overview

This skill coordinates the production of a focused, insight-driven, rigorous, and accurate literature review for philosophy research proposals. The skill coordinates specialized subagents using the Agent tool to execute a structured 6-phase workflow.

## Objectives (priority order)

1. **Accurate** — Only cite verified papers; never fabricate references
2. **Comprehensive** — Cover all major positions and key debates
3. **Rigorous and concise** — Analytical depth, tight prose; balanced presentation of positions
4. **Reproducible** — Structured workflow, standard BibTeX output, Chicago author-date citations

Quality over speed; use full context as needed (do not optimize for token savings).

## Critical: Task List Management

**ALWAYS maintain a todo list and a `task-progress.md` file to enable resume across conversations.**

Once the review directory `reviews/[project-short-name]/` is established (Phase 1, step 7), create the tracker at `reviews/[project-short-name]/task-progress.md`. The first setup steps of Phase 1 (environment check, resume detection, mode choice) run untracked because the review directory does not exist yet. The tracker template:

```markdown
# Literature Review Progress Tracker

**Research Topic**: [topic]
**Started**: [timestamp]
**Last Updated**: [timestamp]

## Progress Status

- [ ] Phase 1: Verify environment and determine execution mode
- [ ] Phase 2: Structure literature review domains
- [ ] Phase 3: Research [N] domains in parallel
- [ ] Phase 4: Outline synthesis review across domains
- [ ] Phase 5: Write review for each section in parallel
- [ ] Phase 6: Assemble final review files and move intermediate files

## Completed Tasks

[timestamp] Phase 2: Created `lit-review-plan.md` ([N] domains)

## Current Task

[Current phase and task]

## Next Steps

[Numbered list of next actions]
```

**Update `task-progress.md` after EVERY completed phase in the workflow.**

## Workflow Architecture

Strictly follow this workflow consisting of six distinct phases:

1. Verify environment and determine execution mode
2. Structure literature review domains (Agent tool: `literature-review-planner` agent)
3. Research domains in parallel (Agent tool: `domain-literature-researcher` agents)
4. Outline synthesis review across domains (Agent tool: `synthesis-planner` agent)
5. Write review for each section in parallel (Agent tool: `synthesis-writer` agent)
6. Assemble final review files and move intermediate files

Advance only to a subsequent phase after completing the current phase.

**Shared conventions**: See `$PHILLIT_ROOT/docs/conventions.md` for BibTeX format, UTF-8 encoding, and citation style.

## Agent Tool Usage

Invoke subagents using the Agent tool with these parameters (older Claude Code spelled this tool `Task`; if that is the only dispatch tool available, it takes the same parameters):
- `subagent_type`: The agent name with the plugin prefix (e.g., "phillit:literature-review-planner")
- `prompt`: The instructions for the agent (include working directory and output filename)
- `description`: Short description (3-5 words)
- `run_in_background`: pass `run_in_background: false` **only if the tool's parameter list includes it**; never add a parameter the tool does not list. Claude Code 2.1.267 exposes no such parameter on `Agent` — every dispatch there returns "Async agent launched" at once, and the result arrives later as a `<task-notification>`.

**How dispatch completes depends on the harness.** On the harnesses observed so far, either every call in a message blocks and returns its result inline (the tool lists `run_in_background`), or every call returns immediately and each agent's result arrives later as a `<task-notification>` (the tool lists no such parameter). In both models the same five rules hold:
- Issue all N calls of a parallel phase in ONE message.
- An immediate "launched" acknowledgement means the dispatch was accepted, not that the agent completed or failed — never re-dispatch an agent merely because its call came back at once.
- Do not start the next step until every dispatched agent has reported completion. If a call returned the agent's result inline, that agent is complete (a return that carries the agent's report or a completion or failure status IS the result; a status that reports failure is that agent's failure: read its output, then re-dispatch it): continue in this same turn — never end your turn to wait for a notification that will not come. Only a call that returned an acknowledgement without the agent's result (such as "Async agent launched", usually with a task id) completes later: its completion is the FIRST `<task-notification>` carrying its `<task-id>` with `<status>completed</status>` (if the acknowledgement carried no task id, match its notification by the output file it names); read the result from that notification or the output file it names. An inline error or an empty return is neither: handle it as that one agent's failure (read what came back, then re-dispatch it), never by waiting. Do not poll for it and do not busy-wait with tool calls — do whatever does not need the results (e.g. update `task-progress.md`), then end your turn only to let those pending notifications arrive. Before advancing, also confirm every expected output file of the phase exists; if one is missing, re-dispatch that one agent, in either model.
- One agent can notify more than once (the harness re-fires when an agent stops again). A later notification with a `<task-id>` you have already collected is a repeat — take no action, and never re-dispatch.
- A notification with any status other than `completed` is a failure to handle, not a repeat: do not advance — read that agent's output, then re-dispatch that one agent only.

Do NOT read agent definition files before invoking them. Agent definitions are for the system, not for you to read.

**Do NOT use `cd`** in any Bash call across all phases. Always use paths relative to the repo root or absolute paths — a `cd` changes the working directory for later commands too, which is how stray directories and misplaced files happen.

---

## Phase 1: Verify Environment and Determine Execution Mode

This phase validates conditions for subsequent phases to function.

**Setup check**: If the current directory has no `.phillit/` marker, PhilLit has not been set up here — offer to run `/phillit:setup` (a quick one-time step) before continuing.

1. Check if file `CLAUDE.local.md` contains instructions about environment setup. Follow these instructions for environment verification and all phases in the literature review workflow.

2. Run the environment verification check:
   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/philosophy-research/scripts/check_setup.py --json
   ```

3. Parse the JSON output and check the `status` field:
   - If `status` is `"ok"`: Proceed to step 5
   - If `status` is `"error"`: **ABORT IMMEDIATELY** with clear instructions

4. **If environment check fails**, inform the user:
   ```
   Environment verification failed. Cannot proceed with literature review.

   Run /phillit:setup in this directory, then make sure uv and jq are installed and your API keys are set (in .env or your environment).
   ```

**Why this matters**: If the environment isn't configured, the `philosophy-research` skill scripts used by the domain researchers will fail, causing agents to fall back to unstructured web searches, undermining review quality.

5. Check for an active review pointer and determine resume point:

   **Check `reviews/.active-review`** to find the review directory:
   - If `reviews/.active-review` exists → read the path from it (e.g., `reviews/epistemic-autonomy-ai`), use that as the working directory, and check file state below
   - If `reviews/.active-review` does NOT exist → this is a fresh review, proceed to step 6
     (If you suspect an orphaned review from a previous interruption, scan `reviews/*/task-progress.md` to locate it.)

   **Resume logic** (check files in the review directory, in order):

   ```
   1. If literature-review-[project-name].md exists -> Workflow complete, inform user

   2. If synthesis-section-*.md files exist:
      - Count existing section files
      - Check synthesis-outline.md for total sections expected
      - If all sections exist -> Resume at Phase 6 (assembly)
      - If some sections missing -> Resume Phase 5 for missing sections only

   3. If synthesis-outline.md exists -> Resume at Phase 5

   4. If literature-domain-*.bib files exist:
      - Count existing domain files
      - Check lit-review-plan.md for total domains expected
      - If all domains exist -> Resume at Phase 4
      - If some domains missing -> Resume Phase 3 for missing domains only

   5. If lit-review-plan.md exists -> Resume at Phase 3

   6. If task-progress.md exists but no other files -> Resume at Phase 2

   7. Otherwise -> Treat as fresh review (proceed to step 6)
   ```

   Output: "Resuming from Phase [N]: [phase name]..."

   **CRITICAL**: When resuming Phase 3 or Phase 5 with partial completion, only invoke agents for MISSING files. Do not re-run completed work.

6. Offer user choice of execution mode:
   - **Full Autopilot**: Execute all phases automatically without pausing for feedback between phases. With `/phillit:setup` having merged PhilLit's permission rules into this directory's `.claude/settings.json`, no approval prompts should appear.
   - **Human-in-the-Loop**: Phase-by-phase with feedback

7. Create working directory and write the active-review pointer:
   ```bash
   mkdir -p reviews/[project-short-name]
   echo "reviews/[project-short-name]" > reviews/.active-review
   ```
   Use a short, descriptive name (e.g., `epistemic-autonomy-ai`, `mechanistic-interp`).

   Then create the progress tracker inside the review directory (see the template in "Critical: Task List Management" above):
   `reviews/[project-short-name]/task-progress.md`

   **Guard — name collision**: If `reviews/[project-short-name]/literature-review-[project-short-name].md` already exists, warn the user that a completed review occupies that path. Ask whether to overwrite or choose a different name (e.g., append `-2`).

   **Guard — concurrent review**: If `reviews/.active-review` already exists and points to a *different* directory, warn the user that another review appears to be in progress. Ask whether to abandon the previous review or resume it instead.

   **CRITICAL**: All subsequent file operations happen in `reviews/[project-short-name]/`. Pass this path to ALL subagents.

---

## Phase 2: Structure Literature Review Domains

1. Receive and review research idea from user. If you require further information, clarification or direction, ask the user. 
2. Use the Agent tool to invoke `literature-review-planner` agent with research idea:
   - subagent_type: "phillit:literature-review-planner"
   - prompt: Include full research idea, requirements, AND working directory path
   - Example prompt: "Research idea: [idea]. Working directory: reviews/[project-name]/. Write output to reviews/[project-name]/lit-review-plan.md"
3. Wait for `literature-review-planner` agent to structure the literature review into domains
4. Read `reviews/[project-name]/lit-review-plan.md` (generated by agent)
5. Get user feedback on plan, iterate if needed using the Agent tool to invoke `literature-review-planner` agent again
6. **Update task-progress.md**

Never advance to a next step in this phase before completing the current step.

---

## Phase 3: Research Literature in Domains

1. Identify and enumerate N domains (typically 3-8) listed in `reviews/[project-name]/lit-review-plan.md`
2. **Launch all N domain researchers in parallel** using a single message with multiple Agent tool calls:
   - subagent_type: "phillit:domain-literature-researcher"
   - prompt: Include domain focus, key questions, research idea, working directory, AND output filename
   - Example prompt for domain 1: "Domain: [name]. Focus: [focus]. Key questions: [questions]. Research idea: [idea]. Working directory: reviews/[project-name]/. Write output to: reviews/[project-name]/literature-domain-1.bib"
   - description: "Domain [N]: [domain name]"
   - **CRITICAL**: Include ALL Agent tool calls in a single message to enable parallel execution
   - **CRITICAL — foreground, never background**: never set `run_in_background: true`; pass `false` where the tool lists the parameter (see Agent Tool Usage).
3. Wait until every one of the N agents has completed — inline results, or one completion notification per agent (see Agent Tool Usage; an immediate "launched" return is not completion). Expected outputs: `reviews/[project-name]/literature-domain-1.bib` through `literature-domain-N.bib`. **Update task-progress.md after all domains complete**
4. **Collect source issues**: Note any "Source issues:" reported by domain researchers for the final summary
5. **Evidence barrier (REQUIRED, after all researchers complete)**: run

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/evidence_barrier.py "reviews/[project-name]" --domains N
   ```

   **CRITICAL — foreground, never background**: run this command in the foreground (never set `run_in_background`) with the maximum Bash timeout (600000 ms) — rate-limited encyclopedia fetches can take 10+ minutes on a cold cache. A backgrounded barrier can be orphaned when the session ends, leaving every entry unstamped (all `EVIDENCE-NONE`). If the tool still moves the command to the background at its timeout ceiling, WAIT for its completion notification — do not start Phase 4 until `intermediate_files/json/evidence_report.json` exists with status `complete` or `degraded`.

   The barrier validates every domain's outputs, mechanically acquires SEP/IEP citation context for entries lacking attested content evidence, writes `intermediate_files/json/evidence_report.json`, and stamps every entry with an `EVIDENCE-*` citability tier. **If it exits nonzero, do NOT proceed to Phase 4** — report the failure to the user and stop. If the summary reports `"status": "degraded"`, continue but include the degraded domains in the final summary.

   The summary's `venue_vetting` key reports the venue check: it
   flags entries whose journal is barely indexed. `"status": "skipped"` means
   the check did not run — the `reason` says why (no `OPENALEX_API_KEY`, or
   `PHILLIT_VET_VENUES` switched it off or holds an unrecognized value);
   mention it once in the final summary so the user knows. `OPENALEX_API_KEY`
   remains optional; obtaining one is free. Any other non-`complete` status
   means the check ran but did not finish, or
   could not run at all — surface that once too, reading why from
   `intermediate_files/json/evidence_report.json`'s `venue_vetting` object
   (the printed summary carries the status but not the explanation): for
   `partial`/`budget_exhausted`/`skipped` it is the `reason` string; for
   `error` it is the `error` string instead (no `reason` key on that path);
   `not-run` means the object is absent from the report entirely, which only
   happens alongside a barrier failure already caught by the nonzero-exit
   rule above.

   The summary's `abstract_corroboration` key reports the abstract check,
   which re-fetches one abstract per candidate entry and is bounded at 180 s
   and 3 consecutive failures — surface it once, for the same reason as the
   venue check above: a non-zero `corroboration_deadline` count means one of those
   two bounds stopped the pass early, so those entries carry a lower tier
   this run and a re-run restores it. But a count that REPEATS across runs
   means the probes themselves are failing rather than the pass merely
   running long — read it alongside the `transport_failed` and `probe_error`
   counts beside it and check credentials and connectivity (a missing or
   invalid `S2_API_KEY`, or an API outage, trips the breaker at the third
   entry on every run). `probe_unavailable` merges two different causes
   instead — a claimed source outside the allowlist, which can never earn
   the tier, and one this environment cannot ask (claimed `core` with no
   `CORE_API_KEY` set — which demotes every claimed-core entry in a keyless
   workspace — or with neither DOI nor title; claimed `s2` or `openalex`
   with no DOI; claimed `ndpr` with no title).

Never advance to Phase 4 before all domain researchers have completed AND the evidence barrier has exited zero.

---

## Phase 4: Outline Synthesis Review Across Domains

1. Use the Agent tool to invoke `synthesis-planner` agent:
   - subagent_type: "phillit:synthesis-planner"
   - prompt: Include research idea, working directory, list of BibTeX files, original plan path, and — only if the user stated one in their request — the target length
   - Example prompt: "Research idea: [idea]. Target length: [user's stated length, or omit this sentence]. Working directory: reviews/[project-name]/. BibTeX files: literature-domain-1.bib through literature-domain-N.bib. Plan: lit-review-plan.md. Write output to: reviews/[project-name]/synthesis-outline.md"
   - description: "Plan synthesis structure"
2. Planner reads BibTeX files and creates tight outline
3. Wait for the planner to complete — its inline result, or its completion notification (see Agent Tool Usage). Expected output: `reviews/[project-name]/synthesis-outline.md` (an 800-1500 word outline)
4. **Update task-progress.md**

Never advance to a next step in this phase before completing the current step.

---

## Phase 5: Write Review Sections in Parallel

1. Read synthesis outline `reviews/[project-name]/synthesis-outline.md` to identify sections
2. For each section: identify relevant BibTeX .bib files from the outline
3. **Launch all N synthesis writers in parallel** using a single message with multiple Agent tool calls:
   - subagent_type: "phillit:synthesis-writer"
   - prompt: Include working directory, section heading (exactly as it appears in the outline),
     outline path, and relevant BibTeX files
   - **CRITICAL**: Use the outline's own section headings verbatim (e.g., "## Introduction",
     "## Section 1: The Charge"). Do NOT renumber sections linearly (1, 2, 3...) if the outline
     uses different numbering. Writers follow the outline's numbering, so mismatches cause them
     to write the wrong section or produce inconsistent headings. Output filenames should be
     numbered sequentially (synthesis-section-1.md through synthesis-section-N.md) for correct
     assembly order.
   - Example prompt: "Working directory: reviews/[project-name]/. Write the section headed
     '## Introduction' from the outline. Outline: synthesis-outline.md. Relevant BibTeX files:
     literature-domain-1.bib, literature-domain-3.bib. Write output to:
     reviews/[project-name]/synthesis-section-1.md"
   - description: "Write section [N]: [section name]"
   - **CRITICAL**: Include ALL Agent tool calls in a single message to enable parallel execution
   - **CRITICAL — foreground, never background**: never set `run_in_background: true`; pass `false` where the tool lists the parameter (see Agent Tool Usage).
4. Wait until every one of the N writers has completed — inline results, or one completion notification per agent (see Agent Tool Usage; an immediate "launched" return is not completion). Expected outputs: `reviews/[project-name]/synthesis-section-1.md` through `synthesis-section-N.md`. **Update task-progress.md after all sections complete**

Never advance to Phase 6 before all synthesis writers have completed.

---

## Phase 6: Assemble Final Review Files and Move Intermediate Files

**Working directory**: `reviews/[project-name]/`

**Expected outputs of this phase** (final) — one purpose each:
- `literature-review-[project-name].md` — the complete review, with YAML frontmatter
- `literature-review-[project-name].docx` — the review as a Word document, only if pandoc is installed
- `literature-[project-name].bib` — the TRACK RECORD, for accountability and reproducibility: every work with every verdict the agents reached on it — evidence tier, relevance rating, fault-line tags, cleaning and workflow markers, and the engine-derived fields. No reading notes, no `@comment` blocks.
- `literature-[project-name]-annotated.bib` — the REFERENCE-MANAGER IMPORT (Zotero, BibDesk, ...): the same works with standard fields, topical keywords, and the researchers' reading notes with fault-line tags spelled out. No verdict tokens and none of the eight engine-derived fields. Zotero imports the notes as notes and the keywords as tags.
- `research-notes-[project-name].md` — the per-domain analysis the researchers recorded (overview, key positions, gaps, synthesis guidance, relevance), for reading.

1. Assemble final review with YAML frontmatter:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/assemble_review.py \
     "reviews/[project-name]/literature-review-[project-name].md" \
     --title "[Research Topic]" \
     reviews/[project-name]/synthesis-section-*.md
   ```

   Then use **Read** to verify section ordering and transitions.

2. **Normalize section headings**:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/normalize_headings.py \
     "reviews/[project-name]/literature-review-[project-name].md"
   ```

   The script enforces consistent numbering: `## Section N: Title` for body sections,
   `### N.M Title` for subsections. Introduction and Conclusion remain unnumbered.
   If the script reports errors, investigate before proceeding.
   Then use **Read** to verify the heading structure looks correct.

3. Aggregate and deduplicate all domain BibTeX files:

   Use **Glob** to find all `literature-domain-*.bib` files. Run the deduplication script to create `literature-[project-name].bib`:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/dedupe_bib.py \
     "reviews/[project-name]/literature-[project-name].bib" \
     --evidence-report "reviews/[project-name]/intermediate_files/json/evidence_report.json" \
     reviews/[project-name]/literature-domain-*.bib
   ```

   The script will:
   - Keep the first occurrence of each citation key
   - Prefer entries with abstracts over entries without (abstract-aware merging)
   - Upgrade importance level if a later domain assigned higher importance
   - Re-stamp each merged entry's `EVIDENCE-*` tier attestation-aware from the evidence report
   - Deduplicate by DOI (catches same paper with different keys)
   - Log which duplicates were removed to console
   - Print a `year conflict` line (stderr) when two copies of one work disagree on the year. The merge still happens and the survivor is chosen by abstract and importance, not by year — so before step 4, check the survivor's year against the prose (and CrossRef) and fix the wrong one in the merged bib. A survivor whose year the prose does not cite fails step 5 as an unresolved citation.
   - Leave `same_work_group` pairs alone, by design: the barrier's grouping is advisory (a reprint carries its own DOI). The planner already cites one key per group, and step 4 prints a `[SAME-WORK]` line if the prose cites two.

4. Generate bibliography and append to final review:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/generate_bibliography.py \
     "reviews/[project-name]/literature-review-[project-name].md" \
     "reviews/[project-name]/literature-[project-name].bib"
   ```

   The script will:
   - Match cited works by surname+year proximity in the review text
   - Format references in Chicago Author-Date style from BibTeX metadata only
   - Deduplicate entries with the same DOI
   - Append (or replace) a `## References` section at the end of the review

5. Lint the final markdown file:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/lint_md.py \
     "reviews/[project-name]/literature-review-[project-name].md"
   ```

   Fix any reported issues before proceeding. The References section is now in scope for linting — verify no false positives from italicized journal names, DOI URLs, or other bibliography formatting.

   The linter also verifies every in-text author-year citation resolves to a
   References entry (ERROR + nonzero exit otherwise, printed as
   `ERROR citation: ...`). This channel carries two distinct cases with two
   distinct remedies — read which one fired before touching anything:

   - **Does not resolve to any References entry**: the References generator
     dropped a cited work — fix the body/bib author spelling divergence (or
     the bib entry) and re-run step 4; never delete the citation to silence
     the check. This applies to primary and legal sources too (statutes,
     regulations, treaties, reports): they are cited like any other work, so
     they need a bib entry — the sanctioned remedy for an unresolved
     "(GDPR 2016)" is adding the @misc entry, not removing the citation.
   - **Reprint-form straddle** ("uses the reprint form but its two years
     resolve to two DIFFERENT References entries"): the bib is correct as
     is — do NOT edit it. The fix is in the PROSE: cite the one year whose
     edition the claim relies on, and give the original date as prose words
     instead of the second year (e.g. "Reiman ([1984] 2017)" becomes
     "Reiman (2017), originally published 1984").

   The check only runs when the file has an exact `## References`
   heading — confirm the lint output does NOT say
   "citation-check: ... skipped" on a finished review; that message means the
   check never ran, not that it passed.

6. **Evidence checker (telemetry)**: run

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/check_evidence.py "reviews/[project-name]/literature-review-[project-name].md" "reviews/[project-name]/literature-[project-name].bib"
   ```

   Include every `CHECK` line **verbatim** in the final summary (they are telemetry, not blockers) — never summarize, count, or gloss them: a live run's summary once reported four findings as "two minor notes", which hid a do-not-cite violation from the user.

7. **Split the delivery into its three files**:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/split_delivery.py \
     "reviews/[project-name]/literature-[project-name].bib" \
     --plan "reviews/[project-name]/lit-review-plan.md"
   ```

   It rewrites `literature-[project-name].bib` as the track record and writes `literature-[project-name]-annotated.bib` and `research-notes-[project-name].md` beside it. A `SPLIT-ERROR:` line (exit 2) names a file that was NOT written and why — an unrecognised label in a domain's research notes, a fault-line tag the plan does not define, or a bib that does not parse; the files it does not name were written. A `SPLIT-NOTICE:` line names a comment block that was dropped although it held analysis. Do not edit files to get past these: report every line **verbatim** in the final summary and deliver the review with what was written.

   If it exits 1 (a bad input or `--plan` path, or a read/write failure), nothing was written: `literature-[project-name].bib` is still the merged bib — report the line verbatim and fix the path before re-running.

   The one exception is a `SPLIT-ERROR` saying the bib is **already split**: this step ran before on this bib, and nothing was written this time. The merged bib it replaced is saved at `reviews/[project-name]/intermediate_files/literature-[project-name]-merged.bib`: copy it back over `literature-[project-name].bib` (or re-run step 3, dedupe), then run this step again. If step 8 has already run, the domain bibs and the plan are in `intermediate_files/`: point step 3's input glob at `reviews/[project-name]/intermediate_files/literature-domain-*.bib` and `--plan` at `reviews/[project-name]/intermediate_files/lit-review-plan.md`.

8. Clean up intermediate files (use absolute paths to avoid cwd issues):

   Move JSON API response files to `intermediate_files/json/` for archival (allows debugging while keeping review directory clean):
   ```bash
   mkdir -p "reviews/[project-name]/intermediate_files/json"
   find "reviews/[project-name]" -maxdepth 1 -name "*.json" -exec mv {} "reviews/[project-name]/intermediate_files/json/" \;
   ```
   (`find`, not a bare `mv …/*.json` glob: under zsh an unmatched glob aborts the command before any redirection applies, so `2>/dev/null || true` cannot silence its `no matches found` error.)

   Move stray API-result files from project root (agents sometimes omit the `$REVIEW_DIR/` prefix).
   Use targeted prefixes — never bare `*.json`, which could swallow unrelated files:
   ```bash
   find . -maxdepth 1 \( -name "philpapers_*.json" -o -name "pp_*.json" -o -name "s2_*.json" -o -name "openalex_*.json" -o -name "stage3_*.json" -o -name "arxiv_*.json" -o -name "core_*.json" -o -name "sep_*.json" -o -name "iep_*.json" -o -name "cites_*.json" -o -name "recommendations_*.json" -o -name "verify_*.json" -o -name "encyclopedia_entries-*.json" \) -exec mv {} "reviews/[project-name]/intermediate_files/json/" \;
   find . -maxdepth 1 -name "*.bib" -exec mv {} "reviews/[project-name]/intermediate_files/" \;
   ```

   Move remaining intermediate files and clear the active-review pointer.
   Archive the pointer with `mv` (not `rm`) — moving it into the completed review's
   `intermediate_files/` clears it from `reviews/` without triggering the `rm` permission prompt:
   ```bash
   mv "reviews/[project-name]/task-progress.md" "reviews/[project-name]/lit-review-plan.md" "reviews/[project-name]/synthesis-outline.md" "reviews/[project-name]/intermediate_files/"
   mv "reviews/[project-name]/synthesis-section-"*.md "reviews/[project-name]/literature-domain-"*.bib "reviews/[project-name]/intermediate_files/"
   mv reviews/.active-review "reviews/[project-name]/intermediate_files/.completed-review" 2>/dev/null || true
   ```

   Safety net — move any remaining non-final files to `intermediate_files/`:
   ```bash
   for f in "reviews/[project-name]"/*; do
     case "$(basename "$f")" in
       literature-review-*.md|literature-review-*.docx|literature-*.bib|research-notes-*.md|intermediate_files) ;;
       *) mv "$f" "reviews/[project-name]/intermediate_files/" 2>/dev/null || true ;;
     esac
   done
   ```

   Stray directories — agents sometimes create directories at the project root by mistake. Remove any empty directories that match the review topic:
   ```bash
   find . -maxdepth 1 -type d -empty -not -name '.*' -not -name 'reviews' -not -name 'tests' -not -name 'docs' -exec rmdir {} \;
   ```

   **Note:** Never `cd` here either — see the rule under Agent Tool Usage above.

**After cleanup** (final state):
```
reviews/[project-name]/
├── literature-review-[project-name].md    # Final review (markdown)
├── literature-review-[project-name].docx  # Final review (if pandoc available)
├── literature-[project-name].bib          # Track record: every agent verdict
├── literature-[project-name]-annotated.bib # Reference-manager import: notes + topical keywords
├── research-notes-[project-name].md       # Per-domain research notes
└── intermediate_files/           # Workflow artifacts
    ├── literature-[project-name]-merged.bib # The merged bib as dedupe wrote it, saved by the split
    ├── json/                     # JSON files archived here
    │   ├── s2_<domain>_results.json … verify_<domain>_<citekey>.json
    │   ├── cleaning_ledger-*.json, enrichment_ledger-*.json
    │   └── evidence_report.json
    ├── task-progress.md
    ├── lit-review-plan.md
    ├── synthesis-outline.md
    ├── synthesis-section-1.md
    ├── synthesis-section-N.md
    ├── literature-domain-1.bib
    ├── literature-domain-N.bib
    └── [other intermediate files, if they exist]
```

9. **Report source issues**: If any domain researchers reported source issues (API errors, partial results), output a summary:
   ```
   ⚠️ Source issues during literature search:
   - Domain [name]: [source]: [issue]
   ```
   If no issues: omit this message.

10. **Optional: Convert to DOCX** (if pandoc is installed):
   ```bash
   if command -v pandoc &> /dev/null; then
     pandoc "reviews/[project-name]/literature-review-[project-name].md" \
       --from markdown \
       --to docx \
       --output "reviews/[project-name]/literature-review-[project-name].docx" \
       --citeproc \
       --bibliography="reviews/[project-name]/literature-[project-name].bib" \
       && echo "Converted to DOCX: literature-review-[project-name].docx"
   else
     echo "Pandoc not installed, skipping DOCX conversion"
   fi
   ```

   **Important:** Use paths relative to repo root (not bare filenames). Do NOT use `&&/||` chaining for this check, as Pandoc errors would trigger the wrong fallback message.

---

## Error Handling

**Too few papers** (<5 per domain): Re-invoke `domain-literature-researcher` agents with broader terms

**Synthesis thin**: Request expansion from `synthesis-planner` agent, or loop back to planning `literature-review-planner` agent

**API failures**: Domain researchers report "Source issues:" in their completion message. Collect these for the final summary. Re-run domains with critical failures if needed.

---

## Quality Standards

- Academic rigor: proper citations, balanced coverage
- Relevance: clear connection to research proposal
- Comprehensiveness: no major positions missed
- **Citation integrity**: ONLY real papers found via skill scripts (structured API searches)
- **Citation format**: (Author Year) in-text, Chicago-style bibliography

---

## Status Updates

Output status updates directly as text (visible to user in real-time):

| Event | Status Format |
|-------|---------------|
| **Workflow start** | `Starting literature review: [topic]` |
| **Environment check** | `Phase 1/6: Verifying environment and determining execution mode...` |
| **Environment OK** | `Environment OK. Proceeding...` |
| **Environment FAIL** | `Environment verification failed. [details]` |
| **Phase transition** | `Phase 2/6: Structuring literature review into domains` |
| **Phase transition** | `Phase 3/6: Researching literature in [N] domains (parallel)` |
| **Phase transition** | `Phase 4/6: Outlining synthesis review across domains` |
| **Phase transition** | `Phase 5/6: Writing [N] review sections (parallel)` |
| **Phase transition** | `Phase 6/6: Assembling final review files` |
| **Agent launch (parallel)** | `Launching [N] domain researchers in parallel...` |
| **Agent completion** | `Domain [N] complete: literature-domain-[N].bib ([number of sources included] sources)` |
| **Phase completion** | `Phase [N] complete: [summary]` |
| **Assembly** | `Assembling final review with YAML frontmatter...` |
| **BibTeX aggregation** | `Aggregating BibTeX files -> literature-[project-name].bib` |
| **Delivery split** | `Split delivery: track record, annotated bib, research notes` |
| **Cleanup** | `Moving intermediate files -> intermediate_files/` |
| **DOCX conversion** | `Converted to DOCX: literature-review-[project-name].docx` |
| **Workflow complete** | `Literature review complete: literature-review-[project-name].md ([wordcount])` |
| **Source issues (if any)** | `⚠️ Source issues: [aggregated list from domain researchers]` |

---

## Success Metrics

- Focused, rigorous, insight-driven review — at the length the user asked for; otherwise sized to the literature found, with 4,000–10,000 words as soft guidance
- Resumable (task-progress.md enables continuity)
- Valid BibTeX files
