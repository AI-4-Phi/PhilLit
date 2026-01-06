---
name: literature-review
description: Coordinate comprehensive literature reviews for research proposals. Manages 6-phase workflow including domain decomposition, literature search, and synthesis. Use when user requests a state-of-the-art review or literature review for philosophy research.
allowed-tools: Bash, Read, Write, Grep, Glob, Edit, TodoWrite
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

**Shared conventions**: See `conventions.md` for BibTeX format, UTF-8 encoding, citation style, and file assembly specifications.

## Task Tool Usage

Invoke subagents using the Task tool with these parameters:
- `subagent_type`: The agent name (e.g., "literature-review-planner")
- `prompt`: The instructions for the agent
- `description`: Short description (3-5 words)

**Example:**
```
Tool: Task
Parameters:
  subagent_type: "literature-review-planner"
  prompt: "Research idea: [idea]. Working directory: reviews/[project-name]/. Write output to reviews/[project-name]/lit-review-plan.md"
  description: "Plan literature domains"
```

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

5. Check for existing `task-progress.md` and determine resume point:

   **If `task-progress.md` does NOT exist**: Create new `task-progress.md` and proceed to step 6.

   **If `task-progress.md` EXISTS**: Resume from interruption using this logic:

   ```
   Resume Logic (check in order):

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

   6. Otherwise -> Resume at Phase 2
   ```

   Output: "Resuming from Phase [N]: [phase name]..."

   **CRITICAL**: When resuming Phase 3 or Phase 5 with partial completion, only invoke agents for MISSING files. Do not re-run completed work.

6. Offer user choice of execution mode:
   - **Full Autopilot**: Execute all phases automatically
   - **Human-in-the-Loop**: Phase-by-phase with feedback

7. Create working directory for this review:
   ```bash
   mkdir -p reviews/[project-short-name]
   ```
   Use a short, descriptive name (e.g., `epistemic-autonomy-ai`, `mechanistic-interp`).

   **CRITICAL**: All subsequent file operations happen in `reviews/[project-short-name]/`. Pass this path to ALL subagents.

---

## Phase 2: Structure Literature Review Domains

1. Receive research idea from user
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
- `literature-all.bib` — aggregated bibliography

1. Assemble final review and add YAML frontmatter:
   ```bash
   cd reviews/[project-name]

   # Create YAML frontmatter
   cat > literature-review-final.md << 'EOF'
   ---
   title: "[Research Topic]"
   date: [YYYY-MM-DD]
   ---

   EOF

   # Append all sections
   for f in synthesis-section-*.md; do cat "$f"; echo; echo; done >> literature-review-final.md
   ```

2. Aggregate all domain BibTeX files into single file:
   ```bash
   for f in literature-domain-*.bib; do echo; cat "$f"; done > literature-all.bib
   ```

3. Clean up intermediate files:
   ```bash
   mkdir -p intermediate_files
   mv task-progress.md lit-review-plan.md synthesis-outline.md intermediate_files/
   mv synthesis-section-*.md literature-domain-*.bib intermediate_files/
   ```

**After cleanup** (final state):
```
reviews/[project-name]/
├── literature-review-final.md    # Final review (pandoc-ready)
├── literature-all.bib            # Aggregated bibliography
└── intermediate_files/           # Workflow artifacts
    ├── task-progress.md
    ├── lit-review-plan.md
    ├── synthesis-outline.md
    ├── synthesis-section-1.md
    ├── synthesis-section-N.md
    ├── literature-domain-1.bib
    ├── literature-domain-N.bib
    └── [other intermediate files, if they exist]
```

4. **Report source issues**: If any domain researchers reported source issues (API errors, partial results), output a summary:
   ```
   ⚠️ Source issues during literature search:
   - Domain [name]: [source]: [issue]
   ```
   If no issues: omit this message.

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
| **Workflow complete** | `Literature review complete: literature-review-final.md ([wordcount])` |
| **Source issues (if any)** | `⚠️ Source issues: [aggregated list from domain researchers]` |

---

## Success Metrics

- Focused, rigorous, insight-driven review (3000-8000 words)
- Clear gap analysis (specific, actionable)
- Resumable (task-progress.md enables continuity)
- Valid BibTeX files
