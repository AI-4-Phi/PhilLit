---
name: literature-review
description: Coordinate comprehensive literature reviews for research proposals. Manages 6-phase workflow including domain decomposition, literature search, and synthesis. Use proactively when user requests a literature review.
allowed-tools: Bash, Read, Write, Grep, Glob, Edit
---

# Literature Review Workflow

## Overview

This skill coordinates the production of a focused, insight-driven, rigorous, and accurate literature review for philosophy research proposals. The skill coordinates specialized subagents using the Task tool to execute a structured 6-phase workflow.

## Critical: Task List Management

**ALWAYS maintain a todo list and a `task-progress.md` file to enable resume across conversations.**

At workflow start, create `task-progress.md` in the working directory:

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

[timestamp] Phase 1: Created `lit-review-plan.md` ([N] domains)

## Current Task

[Current phase and task]

## Next Steps

[Numbered list of next actions]
```

**Update `task-progress.md` after EVERY completed phase in the workflow.**

## Workflow Architecture

Strictly follow this workflow consisting of six distinct phases:

1. Verify environment and determine execution mode
2. Structure literature review domains (Task tool: `literature-review-planner` agent)
3. Research domains in parallel (Task tool: `domain-literature-researcher` agents)
4. Outline synthesis review across domains (Task tool: `synthesis-planner` agent)
5. Write review for each section in parallel (Task tool: `synthesis-writer` agent)
6. Assemble final review files and move intermediate files

Advance only to a subsequent phase after completing the current phase.

**Shared conventions**: See `conventions.md` for BibTeX format, UTF-8 encoding, and citation style.

## Task Tool Usage

Invoke subagents using the Task tool with these parameters:
- `subagent_type`: The agent name (e.g., "literature-review-planner")
- `prompt`: The instructions for the agent (include working directory and output filename)
- `description`: Short description (3-5 words)

**Do NOT use `run_in_background`**. Foreground execution streams status updates to the user. Parallel execution is achieved by including multiple Task calls in a single message.

Do NOT read agent definition files before invoking them. Agent definitions are for the system, not for you to read.

---

## Phase 1: Verify Environment and Determine Execution Mode

This phase validates conditions for subsequent phases to function.

1. Check if file `.claude/CLAUDE.local.md` contains instructions about environment setup. Follow these instructions for environment verification and all phases in the literature review workflow.

2. Run the environment verification check:
   ```bash
   python .claude/skills/philosophy-research/scripts/check_setup.py --json
   ```

3. Parse the JSON output and check the `status` field:
   - If `status` is `"ok"`: Proceed to step 5
   - If `status` is `"error"`: **ABORT IMMEDIATELY** with clear instructions

4. **If environment check fails**, inform the user:
   ```
   Environment verification failed. Cannot proceed with literature review.

   See GETTING_STARTED.md on how to set up the environment.
   ```

**Why this matters**: If the environment isn't configured, the `philosophy-research` skill scripts used by the domain researchers will fail, causing agents to fall back to unstructured web searches, undermining review quality.

5. Check for an active review pointer and determine resume point:

   **Check `reviews/.active-review`** to find the review directory:
   - If `reviews/.active-review` exists → read the path from it (e.g., `reviews/epistemic-autonomy-ai`), use that as the working directory, and check file state below
   - If `reviews/.active-review` does NOT exist → this is a fresh review, proceed to step 6
     (If you suspect an orphaned review from a previous interruption, scan `reviews/*/task-progress.md` to locate it.)

   **Resume logic** (check files in the review directory, in order):

   ```
   1. If literature-review-final.md exists -> Workflow complete, inform user

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
   - **Full Autopilot**: Execute all phases automatically
   - **Human-in-the-Loop**: Phase-by-phase with feedback

7. Create working directory and write the active-review pointer:
   ```bash
   mkdir -p reviews/[project-short-name]
   echo "reviews/[project-short-name]" > reviews/.active-review
   ```
   Use a short, descriptive name (e.g., `epistemic-autonomy-ai`, `mechanistic-interp`).

   **Guard — name collision**: If `reviews/[project-short-name]/literature-review-final.md` already exists, warn the user that a completed review occupies that path. Ask whether to overwrite or choose a different name (e.g., append `-2`).

   **Guard — concurrent review**: If `reviews/.active-review` already exists and points to a *different* directory, warn the user that another review appears to be in progress. Ask whether to abandon the previous review or resume it instead.

   **CRITICAL**: All subsequent file operations happen in `reviews/[project-short-name]/`. Pass this path to ALL subagents.

---

## Phase 2: Structure Literature Review Domains

1. Receive and review research idea from user. If you require further information, clarification or direction, ask the user. 
2. Use Task tool to invoke `literature-review-planner` agent with research idea:
   - subagent_type: "literature-review-planner"
   - prompt: Include full research idea, requirements, AND working directory path
   - Example prompt: "Research idea: [idea]. Working directory: reviews/[project-name]/. Write output to reviews/[project-name]/lit-review-plan.md"
3. Wait for `literature-review-planner` agent to structure the literature review into domains
4. Read `reviews/[project-name]/lit-review-plan.md` (generated by agent)
5. Get user feedback on plan, iterate if needed using Task tool to invoke `literature-review-planner` agent again
6. **Update task-progress.md**

Never advance to a next step in this phase before completing the current step.

---

## Phase 3: Research Literature in Domains

1. Identify and enumerate N domains (typically 3-8) listed in `reviews/[project-name]/lit-review-plan.md`
2. **Launch all N domain researchers in parallel** using a single message with multiple Task tool calls:
   - subagent_type: "domain-literature-researcher"
   - prompt: Include domain focus, key questions, research idea, working directory, AND output filename
   - Example prompt for domain 1: "Domain: [name]. Focus: [focus]. Key questions: [questions]. Research idea: [idea]. Working directory: reviews/[project-name]/. Write output to: reviews/[project-name]/literature-domain-1.bib"
   - description: "Domain [N]: [domain name]"
   - **CRITICAL**: Include ALL Task tool calls in a single message to enable parallel execution
3. Wait for all N agents to finish using TaskOutput (block until complete). Expected outputs: `reviews/[project-name]/literature-domain-1.bib` through `literature-domain-N.bib`. **Update task-progress.md after all domains complete**
4. **Collect source issues**: Note any "Source issues:" reported by domain researchers for the final summary

Never advance to Phase 4 before all domain researchers have completed.

---

## Phase 4: Outline Synthesis Review Across Domains

1. Use Task tool to invoke `synthesis-planner` agent:
   - subagent_type: "synthesis-planner"
   - prompt: Include research idea, working directory, list of BibTeX files, and original plan path
   - Example prompt: "Research idea: [idea]. Working directory: reviews/[project-name]/. BibTeX files: literature-domain-1.bib through literature-domain-N.bib. Plan: lit-review-plan.md. Write output to: reviews/[project-name]/synthesis-outline.md"
   - description: "Plan synthesis structure"
2. Planner reads BibTeX files and creates tight outline
3. Wait for agent to finish using TaskOutput. Expected output: `reviews/[project-name]/synthesis-outline.md` (800-1500 words outline for a 3000-4000 word review)
4. **Update task-progress.md**

Never advance to a next step in this phase before completing the current step.

---

## Phase 5: Write Review Sections in Parallel

1. Read synthesis outline `reviews/[project-name]/synthesis-outline.md` to identify sections
2. For each section: identify relevant BibTeX .bib files from the outline
3. **Launch all N synthesis writers in parallel** using a single message with multiple Task tool calls:
   - subagent_type: "synthesis-writer"
   - prompt: Include working directory, section number, section title, outline path, and relevant BibTeX files
   - Example prompt for section 1: "Working directory: reviews/[project-name]/. Section: 1. Title: [title]. Outline: synthesis-outline.md. Relevant BibTeX files: literature-domain-1.bib, literature-domain-3.bib. Write output to: reviews/[project-name]/synthesis-section-1.md"
   - description: "Write section [N]: [section name]"
   - **CRITICAL**: Include ALL Task tool calls in a single message to enable parallel execution
4. Wait for all N agents to finish using TaskOutput (block until complete). Expected outputs: `reviews/[project-name]/synthesis-section-1.md` through `synthesis-section-N.md`. **Update task-progress.md after all sections complete**

Never advance to Phase 6 before all synthesis writers have completed.

---

## Phase 6: Assemble Final Review Files and Move Intermediate Files

**Working directory**: `reviews/[project-name]/`

**Expected outputs of this phase** (final):
- `literature-review-final.md` — complete review with YAML frontmatter
- `literature-review-final.docx` — DOCX version (if pandoc is installed)
- `literature-all.bib` — aggregated bibliography

1. Assemble final review with YAML frontmatter:

   ```bash
   python .claude/skills/literature-review/scripts/assemble_review.py \
     "reviews/[project-name]/literature-review-final.md" \
     --title "[Research Topic]" \
     reviews/[project-name]/synthesis-section-*.md
   ```

   Then use **Read** to verify section ordering and transitions.

2. Aggregate and deduplicate all domain BibTeX files:

   Use **Glob** to find all `literature-domain-*.bib` files. Run the deduplication script to create `literature-all.bib`:

   ```bash
   python .claude/skills/literature-review/scripts/dedupe_bib.py \
     "reviews/[project-name]/literature-all.bib" \
     reviews/[project-name]/literature-domain-*.bib
   ```

   The script will:
   - Keep the first occurrence of each citation key
   - Prefer entries with abstracts over entries without (abstract-aware merging)
   - Upgrade importance level if a later domain assigned higher importance
   - Remove INCOMPLETE flags when merged entry has an abstract
   - Deduplicate by DOI (catches same paper with different keys)
   - Log which duplicates were removed to console

3. Generate bibliography and append to final review:

   ```bash
   python .claude/skills/literature-review/scripts/generate_bibliography.py \
     "reviews/[project-name]/literature-review-final.md" \
     "reviews/[project-name]/literature-all.bib"
   ```

   The script will:
   - Match cited works by surname+year proximity in the review text
   - Format references in Chicago Author-Date style from BibTeX metadata only
   - Deduplicate entries with the same DOI
   - Append (or replace) a `## References` section at the end of the review

4. Lint the final markdown file:

   ```bash
   python .claude/skills/literature-review/scripts/lint_md.py \
     "reviews/[project-name]/literature-review-final.md"
   ```

   Fix any reported issues before proceeding. The References section is now in scope for linting — verify no false positives from italicized journal names, DOI URLs, or other bibliography formatting.

5. Clean up intermediate files (use absolute paths to avoid cwd issues):

   Move JSON API response files to `intermediate_files/json/` for archival (allows debugging while keeping review directory clean):
   ```bash
   mkdir -p "reviews/[project-name]/intermediate_files/json"
   mv "reviews/[project-name]"/*.json "reviews/[project-name]/intermediate_files/json/" 2>/dev/null || true
   ```

   Move stray API-result files from project root (agents sometimes omit the `$REVIEW_DIR/` prefix).
   Use targeted prefixes — never bare `*.json`, which could swallow unrelated files:
   ```bash
   for prefix in philpapers_ pp_ s2_ openalex_ stage3_ arxiv_; do
       mv ${prefix}*.json "reviews/[project-name]/intermediate_files/json/" 2>/dev/null || true
   done
   mv *.bib "reviews/[project-name]/intermediate_files/" 2>/dev/null || true
   ```

   Move remaining intermediate files and remove the active-review pointer:
   ```bash
   mv "reviews/[project-name]/task-progress.md" "reviews/[project-name]/lit-review-plan.md" "reviews/[project-name]/synthesis-outline.md" "reviews/[project-name]/intermediate_files/"
   mv "reviews/[project-name]/synthesis-section-"*.md "reviews/[project-name]/literature-domain-"*.bib "reviews/[project-name]/intermediate_files/"
   rm -f reviews/.active-review
   ```

   **Note:** Do NOT use `cd` to change directories. Always use paths relative to the repo root or absolute paths to prevent working directory mismatches in subsequent commands.

**After cleanup** (final state):
```
reviews/[project-name]/
├── literature-review-final.md    # Final review (markdown)
├── literature-review-final.docx  # Final review (if pandoc available)
├── literature-all.bib            # Aggregated bibliography
└── intermediate_files/           # Workflow artifacts
    ├── json/                     # JSON files archived here
    │   ├── s2_results.json
    │   ├── openalex_results.json
    │   └── stage3_*.json
    ├── task-progress.md
    ├── lit-review-plan.md
    ├── synthesis-outline.md
    ├── synthesis-section-1.md
    ├── synthesis-section-N.md
    ├── literature-domain-1.bib
    ├── literature-domain-N.bib
    └── [other intermediate files, if they exist]
```

6. **Report source issues**: If any domain researchers reported source issues (API errors, partial results), output a summary:
   ```
   ⚠️ Source issues during literature search:
   - Domain [name]: [source]: [issue]
   ```
   If no issues: omit this message.

7. **Optional: Convert to DOCX** (if pandoc is installed):
   ```bash
   if command -v pandoc &> /dev/null; then
     pandoc "reviews/[project-name]/literature-review-final.md" \
       --from markdown \
       --to docx \
       --output "reviews/[project-name]/literature-review-final.docx" \
       --citeproc \
       --bibliography="reviews/[project-name]/literature-all.bib" \
       && echo "Converted to DOCX: literature-review-final.docx"
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
| **Agent launch (parallel)** | `Launching [N] domain researchers in parallel...` |
| **Agent completion** | `Domain [N] complete: literature-domain-[N].bib ([number of sources included] sources)` |
| **Phase completion** | `Phase [N] complete: [summary]` |
| **Assembly** | `Assembling final review with YAML frontmatter...` |
| **BibTeX aggregation** | `Aggregating BibTeX files -> literature-all.bib` |
| **Cleanup** | `Moving intermediate files -> intermediate_files/` |
| **DOCX conversion** | `Converted to DOCX: literature-review-final.docx` |
| **Workflow complete** | `Literature review complete: literature-review-final.md ([wordcount])` |
| **Source issues (if any)** | `⚠️ Source issues: [aggregated list from domain researchers]` |

---

## Success Metrics

- Focused, rigorous, insight-driven review (3000-8000 words)
- Clear gap analysis (specific, actionable)
- Resumable (task-progress.md enables continuity)
- Valid BibTeX files
