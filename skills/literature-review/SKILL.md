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

Once `workdir.py init` has created the review (Phase 1, step 7), create the tracker at `[workdir]/task-progress.md`, where `[workdir]` is the absolute `workdir` path `init` printed. The first setup steps of Phase 1 (environment check, resume detection, mode choice) run untracked because the review does not exist yet. The tracker template:

```markdown
# Literature Review Progress Tracker

**Research Topic**: [topic]
**Started**: [timestamp]
**Last Updated**: [timestamp]

## Progress Status

- [ ] Phase 1: Verify environment and determine execution mode; acquire anchor texts (step 8)
- [ ] Phase 2: Structure literature review domains
- [ ] Phase 3: Research [N] domains in parallel; acquire gap texts; run the evidence barrier
- [ ] Phase 4: Outline synthesis review across domains
- [ ] Phase 5: Write review for each section in parallel
- [ ] Phase 6: Assemble, check quotations, deliver and publish the review (tick before step 11)

## Completed Tasks

[timestamp] Phase 2: Created `lit-review-plan.md` ([N] domains)

## Current Task

[Current phase and task]

## Next Steps

[Numbered list of next actions]
```

**Update `task-progress.md` after EVERY completed phase in the workflow.** Phase 6 is the one exception: tick it BEFORE step 11 (`publish`), and never write the tracker, or anything else, into `[workdir]` after publish: the folder is gone (local mode) or is the delivered review (in place).

## Workflow Architecture

Strictly follow this workflow consisting of six distinct phases:

1. Verify environment and determine execution mode
2. Structure literature review domains (Agent tool: `literature-review-planner` agent)
3. Research domains in parallel (Agent tool: `domain-literature-researcher` agents)
4. Outline synthesis review across domains (Agent tool: `synthesis-planner` agent)
5. Write review for each section in parallel (Agent tool: `synthesis-writer` agent)
6. Assemble, deliver and publish the review

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

**A completion you did not receive is not a completion.** A completion is an inline tool result, or a `<task-notification>` that the harness delivers as a separate message. Never write notification text, an agent's result, source counts or "Source issues" lines yourself. Never treat your own text as an agent's report. Before you state that an agent or phase is complete, `ls -l` its expected output files, and quote their names and modification times in that statement. A missing file means the agent has not completed.

Do NOT read agent definition files before invoking them. Agent definitions are for the system, not for you to read.

**Do NOT use `cd`** in any Bash call across all phases. Always use `[workdir]` (an absolute path) or paths relative to the workspace root — a `cd` changes the working directory for later commands too, which is how stray directories and misplaced files happen.

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

5. Check for an active review and determine the resume point:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/workdir.py status
   ```

   It prints one JSON object. From here on, `[workdir]` means the `workdir` value that `status`, `activate`, `init` or `demote` printed (an absolute path, used verbatim), and `[project-name]` means the `name` value.
   - `"committed": true` → a publish was interrupted after the review's files were copied. Run only Phase 6 step 11's command (`workdir.py publish`), and update nothing first, not even the tracker. Never re-run any other Phase 6 step. Then report the outcome by the `state` it prints: `published` is a delivered review, `abandoned` a review set aside.
   - `"missing": true` → **STOP.** The pointer names `reviews/[project-name]/`, but that folder does not exist here: it was deleted, or sync has not delivered it yet. Tell the user; never start the review again under this pointer. Once the folder is back, run step 5 again. To give up on it instead, run `workdir.py publish --abandon`, which only clears the pointer.
   - `"delivered": true` → the pointer names a review that was already delivered (an interrupted "completed review" guard, step 7). Run `workdir.py publish --abandon` (it only clears the pointer; the delivered review is not touched), then run step 5 again and continue from its answer.
   - `"elsewhere": true` → **STOP.** Tell the user that this review's working files are not on this machine: it was last worked on `[host]`, where it can be resumed, or its files were removed. If `[host]` is this machine: when the printed `workdir_exists` is `true`, the workspace was probably moved, renamed or opened by another path spelling (letter case counts), its files are at the printed `workdir`, and reopening the workspace by its original path resumes it; when it is `false`, the files were removed. The user can resume on the machine that holds the files, or delete `reviews/.active-review` themselves — warn them that the pointer is one synced file, so deleting it also detaches the review on the other machine (there it stays listed as abandoned, and `workdir.py activate <name>` re-attaches it). Never treat it as a fresh review.
   - `"unproven": true` → **STOP.** Tell the user that the review's folder exists at the printed `workdir` but its ownership cannot be proven, and give the printed `error` verbatim. To detach the review, the user deletes `reviews/.active-review` by hand. The folder itself is then theirs to move or delete: depending on why ownership failed, `status` may list it as abandoned or stranded, or not at all.
   - `"interrupted_demote": true` → run `workdir.py demote` (it finishes moving the fresh review into the workspace), then write the tracker as step 7 describes, run step 8 (anchor texts), and continue at Phase 2.
   - `"active": true` with a `workdir` and none of the flags above → apply the resume logic below in `[workdir]`.
   - `"active": false` → no review is active. If `abandoned` lists entries, offer to resume one — `workdir.py activate <name>`, which prints the same fields as an active `status` — or to start fresh (step 6). If `activate` refuses, report it verbatim. When it says the copy is not complete yet (still syncing), tell the user to try again once sync has finished; otherwise stop. In Full Autopilot, start fresh. Mention any `stranded` entries once, with their `path` and `note`.
   - An `error`, any nonzero exit, or output that is not one JSON object → report it verbatim to the user and stop.

   **Resume logic** (check files in `[workdir]`, in order):

   ```
   1. If literature-review-[project-name].md exists -> Phase 6 was interrupted:
      resume Phase 6 as its "Resuming Phase 6" note says

   2. If synthesis-section-*.md files exist:
      - Count existing section files
      - Check synthesis-outline.md for total sections expected
      - If all sections exist -> Resume at Phase 6 (assembly)
      - If some sections missing -> Resume Phase 5 for missing sections only

   3. If synthesis-outline.md exists -> Resume at Phase 5

   4. If literature-domain-*.bib files exist:
      - Count existing domain files
      - Check lit-review-plan.md for total domains expected
      - If all domains exist -> if [workdir]/intermediate_files/json/evidence_report.json
        is missing, or its `status` is neither `complete` nor `degraded`, run Phase 3
        steps 5 and 6 (gap texts, then the evidence barrier) first; then resume at Phase 4
      - If some domains missing -> Resume Phase 3 for missing domains only

   5. If lit-review-plan.md exists -> Resume at Phase 3

   6. If task-progress.md exists but no other files -> run Phase 1 step 8
      (anchor texts; works already stored print `exists`), then resume at Phase 2

   7. Otherwise ([workdir] exists but holds no review files: init ran,
      nothing else did) -> skip step 7's init, create
      [workdir]/task-progress.md as step 7 describes (including its write
      check), run step 8 (anchor texts), and continue at Phase 2
   ```

   Output: "Resuming from Phase [N]: [phase name]..."

   **CRITICAL**: When resuming Phase 3 or Phase 5 with partial completion, only invoke agents for MISSING files. Do not re-run completed work.

6. Offer user choice of execution mode:
   - **Full Autopilot**: Execute all phases automatically without pausing for feedback between phases. With `/phillit:setup` having merged PhilLit's permission rules into this directory's `.claude/settings.json`, no approval prompts should appear.
   - **Human-in-the-Loop**: Phase-by-phase with feedback

7. Create the review:
   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/workdir.py init [project-short-name]
   ```
   Use a short, descriptive name (e.g., `epistemic-autonomy-ai`, `mechanistic-interp`): letters, digits, `.`, `_` and `-`, at most 64 characters. This name is `[project-name]` in every later step.

   It prints `mode`, `workdir` (the absolute working directory, `[workdir]` from now on) and `destination` (`reviews/[project-short-name]/`, where the finished review will appear). Output: "Working in [workdir]; the finished review will appear in reviews/[project-short-name]/". If it prints a `reason`, the review runs in the workspace folder itself: tell the user the reason once.

   **Guard — name taken**: If `init` refuses and prints a `suggested_name`, a review (finished or not) already occupies the name. Human-in-the-Loop: ask the user to accept the suggestion or give another name. Full Autopilot: take the suggestion. Then run `init` again.

   **Guard — completed review**: If `init` printed `"existing_review": true`, a completed review occupies `reviews/[project-short-name]/`, and a delivered review is never changed. Run `workdir.py publish --abandon` (here it only clears the pointer), then choose a new name as in "name taken" and run `init` again.

   **Guard — concurrent review**: If `init` refuses because a review is already active, it names that review under `active`. Ask the user whether to resume it (go back to step 5) or abandon it with `workdir.py publish --abandon` — its files then appear in `reviews/` and can be resumed later — and then run `init` again. **PRECONDITION for `publish --abandon`**: nothing the active review started is still running — no dispatched agent without its completion, no evidence barrier or other command in the background. `publish` copies a tree that nothing else may be writing; if you cannot account for every agent and command, resume the review instead.

   **Any other refusal**, nonzero exit or non-JSON output from `init` or `demote`: report it verbatim to the user and stop.

   Then create the progress tracker with the **Write** tool (the Write tool only, never a Bash redirect: `demote` accepts only a folder that holds nothing but `init`'s metadata) at `[workdir]/task-progress.md` (template under "Critical: Task List Management"). **Write check**: if `init` printed `"mode": "local"` and that Write is denied, run
   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/workdir.py demote
   ```
   It moves the fresh review into the workspace and prints a new `workdir` and a `reason`. Tell the user the reason once, and write the tracker again at the new `[workdir]/task-progress.md`. If the review already runs in place (`"mode": "inplace"`) and the Write is denied, `demote` cannot help: stop and tell the user that file writes in `reviews/` are not permitted here, and that `/phillit:setup` merges the rule that allows them.

   **CRITICAL**: All subsequent file operations happen in `[workdir]`. Pass it to ALL subagents as ``Working directory: `[workdir]` ``, with the path in backticks.

8. **Acquire anchor texts (REQUIRED when the request names works)**: an anchor work is one the user's request asks to include, naming it by its full title or by author and year — exactly the Phase 4 tier-override test, exclusions included: a work the request only mentions ("against Kaufman 2011") or names by topic or author alone is not an anchor. If the request names none, skip this step. For each anchor work:
   - Resolve it to its DOI, its full title, its first author's FULL surname as published, particles included (`van Fraassen`, never `Fraassen`), and its year, with CrossRef first:
     ```bash
     bash "$PHILLIT_ROOT/bin/phillit-run" skills/philosophy-research/scripts/verify_paper.py --title "[title]" --author "[surname]"
     ```
     If CrossRef finds nothing, try `s2_search.py` or `search_openalex.py` the same way. Without a DOI, the title, surname and year must all be known; a work you cannot resolve that far gets no acquisition, and the final summary names it.
   - Run, passing everything you resolved:
     ```bash
     bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/acquire_fulltext.py "[workdir]" --doi "[DOI]" --title "[full title]" --author "[surname]" --year [year]
     ```
     When the DOI is known, still pass `--title`, `--author` and `--year`, never `--doi` alone: a PDF that does not print its DOI is matched by title and surname instead. Without a DOI, leave out `--doi`.
   - It prints one JSON object. By its `status`:
     - `acquired` or `exists`: the work's PDF is stored at `[workdir]/intermediate_files/fulltext/[slug].pdf` (`slug` is printed).
     - `not_found` (no source had a PDF) or `rejected` (a PDF was found, but it is another work or has no readable text): Human-in-the-Loop: ask the user for the path of a PDF of the work, then run the same command again with `--pdf "[path]"` added; the file goes through the same identity check, and a second `rejected` means it is not this work — tell the user. Full Autopilot: record the gap for the final summary.
     - `refused` (`tried` names `slug_collision` or `path_too_long`): report it to the user; do not retry.
   - Exit 1, or output that is not one JSON object: report it verbatim and continue without full texts. They are an upgrade; the review does not depend on them.

   In the final summary, name every anchor work left without a PDF and why (`not_found`, `rejected`, `refused` or a failure), and every anchor work whose stored PDF the barrier could not bind to its bib entry (it is listed under `unbound_records` in the barrier report's `fulltext` section, with its title, surname and year; the usual cause is a year the metadata cleaner changed). A stored PDF licenses nothing by itself: only the Phase 3 evidence barrier, after checking the PDF against the work's bib entry, stamps `EVIDENCE-FULLTEXT` and writes the text file the writers read (`[slug].txt`, which does not exist before the barrier runs).

---

## Phase 2: Structure Literature Review Domains

1. Receive and review research idea from user. If you require further information, clarification or direction, ask the user. 
2. Use the Agent tool to invoke `literature-review-planner` agent with research idea:
   - subagent_type: "phillit:literature-review-planner"
   - prompt: Include full research idea, requirements, AND working directory path
   - Example prompt: "Research idea: [idea]. Working directory: `[workdir]`. Write output to `[workdir]/lit-review-plan.md`"
   - If Phase 1 step 8 stored PDFs, add their paths: "Anchor PDFs, for scoping only: [workdir]/intermediate_files/fulltext/[slug].pdf, ...". They help the planner choose domains and search terms; they license no claim about the works.
   - Never prescribe a citation year, citekey or year letter to any agent. The metadata cleaner sets `year` to the CrossRef issue year wherever the entry's own CrossRef record licenses it (an online-first article published online in 2017 in a 2019 issue is cited as 2019; see `$PHILLIT_ROOT/docs/conventions.md`), and the barrier assigns letters.
3. Wait for `literature-review-planner` agent to structure the literature review into domains
4. Read `[workdir]/lit-review-plan.md` (generated by agent)
5. Get user feedback on plan, iterate if needed using the Agent tool to invoke `literature-review-planner` agent again. In Human-in-the-Loop mode, give the user the full path `[workdir]/lit-review-plan.md` when asking for feedback.
6. **Update task-progress.md**

Never advance to a next step in this phase before completing the current step.

---

## Phase 3: Research Literature in Domains

1. Identify and enumerate N domains (typically 3-8) listed in `[workdir]/lit-review-plan.md`
2. **Launch all N domain researchers in parallel** using a single message with multiple Agent tool calls:
   - subagent_type: "phillit:domain-literature-researcher"
   - prompt: Include domain focus, key questions, research idea, working directory, AND output filename
   - Example prompt for domain 1: "Domain: [name]. Focus: [focus]. Key questions: [questions]. Research idea: [idea]. Working directory: `[workdir]`. Write output to: `[workdir]/literature-domain-1.bib`"
   - description: "Domain [N]: [domain name]"
   - **CRITICAL**: Include ALL Agent tool calls in a single message to enable parallel execution
   - **CRITICAL — foreground, never background**: never set `run_in_background: true`; pass `false` where the tool lists the parameter (see Agent Tool Usage).
3. Wait until every one of the N agents has completed — inline results, or one completion notification per agent (see Agent Tool Usage; an immediate "launched" return is not completion). Expected outputs: `[workdir]/literature-domain-1.bib` through `literature-domain-N.bib`. **Update task-progress.md after all domains complete**
4. **Collect source issues**: Note any "Source issues:" reported by domain researchers for the final summary. If a researcher's last message has no `Source issues:` line, read the `NOTABLE_GAPS` part of the `@comment` header in its `literature-domain-N.bib` instead, and quote its failure lines for that domain
5. **Acquire gap texts (REQUIRED, after all researchers complete, before the barrier)**: run

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/acquire_fulltext.py "[workdir]" --gaps --domains N
   ```

   Run it exactly as shown, in the foreground (never set `run_in_background`) with the maximum Bash timeout (600000 ms); its pass stops itself after about seven minutes. It looks for a PDF of every domain-bib entry that has no `abstract`: in the user's Zotero library and PDF folder (only where the user consented to it), then open access. It never edits a bib. It prints one line, `{"status": "done", "candidates": ..., "counts": {...}, "report": ...}`: give the counts once in the final summary. When `status` is `done_with_errors`, the line also has an `errors` list: name each entry and its reason in the final summary. Name every item of its `warnings` list too (for example, folders of the user's that could not be read). Exit 1, or output that is not that one JSON line: report it verbatim to the user and go on to the barrier without gap texts.

6. **Evidence barrier (REQUIRED, after all researchers complete and step 5)**: run

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/evidence_barrier.py "[workdir]" --domains N
   ```

   Run it exactly as shown: never pipe it through `tail`, `head` or anything else, since a pipe hides its exit code. **CRITICAL — foreground, never background**: run this command in the foreground (never set `run_in_background`) with the maximum Bash timeout (600000 ms) — rate-limited encyclopedia fetches can take 10+ minutes on a cold cache. A backgrounded barrier can be orphaned when the session ends, leaving every entry unstamped (all `EVIDENCE-NONE`). If the tool still moves the command to the background at its timeout ceiling, WAIT for its completion notification — do not start Phase 4 until `intermediate_files/json/evidence_report.json` exists with status `complete` or `degraded`.

   The barrier validates every domain's outputs, mechanically acquires SEP/IEP citation context for entries lacking attested content evidence, checks every stored PDF against its entry and renders its text, writes `intermediate_files/json/evidence_report.json`, and stamps every entry with an `EVIDENCE-*` citability tier. **If it exits nonzero, do NOT proceed to Phase 4** — report the failure to the user, with the summary's `error` line verbatim, and stop. If the summary reports `"status": "degraded"`, continue, and quote its `degraded_by` lines (the causes) in the final summary.

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
   with no DOI; claimed `ndpr` with no title or no author or editor surname). `unusable` needs no action:
   the source does serve that abstract (the fetch corroborated it), but it
   is a stub, a keyword list, a publisher page, an opening extract or word
   salad (the report gives each entry's `reason`), so it cannot support the
   tier. The entry keeps a lower tier, as any untiered entry does.

   The summary's `fulltext` key reports the full-text pass: `stamped`
   entries earned `EVIDENCE-FULLTEXT`; `rejected` counts, by reason, stored
   PDFs or entries that did not (the report's `fulltext` object names
   them); `deadline` counts PDFs the pass did not reach (a rerun of the
   barrier reaches them); `unbound_records` counts stored PDFs that matched
   no entry. Mention it once in the final summary when anything was
   rejected, cut by the deadline or unbound, and when `status` is `error`:
   then no entry earned the tier this run, and the review continues.

Never advance to Phase 4 before all domain researchers have completed AND the evidence barrier has exited zero.

---

## Phase 4: Outline Synthesis Review Across Domains

1. Use the Agent tool to invoke `synthesis-planner` agent:
   - subagent_type: "phillit:synthesis-planner"
   - prompt: Include research idea, working directory, list of BibTeX files, original plan path, and — only if the user stated one in their request — the target length
   - **Tier overrides — user request only.** An override lets the planner and writers include a work its `EVIDENCE-*` tier would bar. Write one ONLY for a work the user's request asked to include in the review, naming it by its full title or by author and year. Never on your own judgement: not for an important work, not after an API failure. A work the request only mentions ("building on Lewis (1986)", "against Kaufman 2011"), or names by topic or author alone ("something on Frankfurt cases", "Smith's work"), gets no override.
     - The full title (ignoring case and punctuation) or the author and year must match exactly one work in the BibTeX files: one entry, one `same_work_group`, or entries in different domain files that share one DOI (one work under several citekeys). A partial title is no match. No match or several works: no override, and the final summary says the named work could not be identified.
     - Within a `same_work_group`, take the highest-tier member. If it is `EVIDENCE-FULLTEXT`, `EVIDENCE-ABSTRACT`, `EVIDENCE-CONTEXT` or `EVIDENCE-WEB`, no override is needed.
     - Otherwise (`EVIDENCE-EXISTENCE`, `EVIDENCE-NONE`, or no tier token), the work gets a line: `Tier override (user request): <citekey> (<tier, or "no tier">)`, where `<citekey>` lists every key of the work, separated by `, ` (one work in several domain files carries several keys), followed only when the request describes the work by `; user's description: "<the request's words about the work, copied verbatim on one line, with any double quote changed to a single one>"`.
     - Every time this step runs, rewrite `[workdir]/tier-overrides.md` with exactly this request's lines, one per work — an empty file when there are none, so no earlier request's line survives. Add every line to this prompt.
     - **A named work below `EVIDENCE-ABSTRACT` is an accuracy risk to flag, not to work around.** When a work the request names (identified as above) has no member at `EVIDENCE-FULLTEXT`, `EVIDENCE-ABSTRACT`, `EVIDENCE-CONTEXT` or `EVIDENCE-WEB`, the review cannot say what it argues beyond the user's description or its title. Human-in-the-Loop: tell the user before dispatching the planner, name the work, and ask whether to continue. Full Autopilot: continue. Either way, open the final summary with one line per such work: the review did not verify what it argues, so any conclusion that depends on it needs the user's check against the text.
     - An override never licenses quotation: decline a request to quote in the final summary. In the final summary, name every override line with the user's words, and say whether the assembled review cites the work (search it for the citation); a work it does not cite is reported as not included, whether or not a `CHECK` line flags it.
   - Example prompt: "Research idea: [idea]. Target length: [user's stated length, or omit this sentence]. Working directory: `[workdir]`. BibTeX files: literature-domain-1.bib through literature-domain-N.bib. Plan: lit-review-plan.md. Write output to: `[workdir]/synthesis-outline.md`"
   - description: "Plan synthesis structure"
2. Planner reads BibTeX files and creates tight outline
3. Wait for the planner to complete — its inline result, or its completion notification (see Agent Tool Usage). Expected output: `[workdir]/synthesis-outline.md` (an 800-1500 word outline)
4. **Update task-progress.md**

Never advance to a next step in this phase before completing the current step.

---

## Phase 5: Write Review Sections in Parallel

1. Read synthesis outline `[workdir]/synthesis-outline.md` to identify sections
2. For each section: identify relevant BibTeX .bib files from the outline
3. **Launch all N synthesis writers in parallel** using a single message with multiple Agent tool calls:
   - subagent_type: "phillit:synthesis-writer"
   - prompt: Include working directory, section heading (exactly as it appears in the outline),
     outline path, and relevant BibTeX files — plus every line of `[workdir]/tier-overrides.md`, if it exists, unchanged, to every writer, with the BibTeX files that hold any of each override's keys (read the file, also on a resume: the lines live only there)
   - **Nothing else licenses content.** Never give writers a notes file, a list of "verified facts", or your own reading of a work, even of a full text you have read: a writer may say about a work only what its tier licenses (or its override line). A full text licenses content only through the entry's `EVIDENCE-FULLTEXT` tier, which the barrier stamps, and the writer reads that text itself. Put such material in the final summary for the user instead.
   - **CRITICAL**: Use the outline's own section headings verbatim (e.g., "## Introduction",
     "## Section 1: The Charge"). Do NOT renumber sections linearly (1, 2, 3...) if the outline
     uses different numbering. Writers follow the outline's numbering, so mismatches cause them
     to write the wrong section or produce inconsistent headings. Output filenames should be
     numbered sequentially (synthesis-section-1.md through synthesis-section-N.md) for correct
     assembly order.
   - Example prompt: "Working directory: `[workdir]`. Write the section headed
     '## Introduction' from the outline. Outline: synthesis-outline.md. Relevant BibTeX files:
     literature-domain-1.bib, literature-domain-3.bib. Write output to:
     `[workdir]/synthesis-section-1.md`"
   - description: "Write section [N]: [section name]"
   - **CRITICAL**: Include ALL Agent tool calls in a single message to enable parallel execution
   - **CRITICAL — foreground, never background**: never set `run_in_background: true`; pass `false` where the tool lists the parameter (see Agent Tool Usage).
4. Wait until every one of the N writers has completed — inline results, or one completion notification per agent (see Agent Tool Usage; an immediate "launched" return is not completion). Expected outputs: `[workdir]/synthesis-section-1.md` through `synthesis-section-N.md`. Collect every writer's `Unsupported, cut:` and `Narrowed:` lines (their REQUIRED source check; skip a bare "none") and quote them in the final summary. A completion message without its `Source check:` line, or one reporting 0 claims checked for a section that cites works, means the check did not run: re-dispatch that writer once. If the second message fails the same way, keep the section and name it in the final summary as not source-checked. **Update task-progress.md after all sections complete**

Never advance to Phase 6 before all synthesis writers have completed.

---

## Phase 6: Assemble, Deliver and Publish the Review

**Working directory**: `[workdir]`

**Expected outputs of this phase** (final) — one purpose each:
- `literature-review-[project-name].md` — the complete review, with YAML frontmatter
- `literature-review-[project-name].docx` — the review as a Word document, only if pandoc is installed
- `literature-review-[project-name].pdf` — the review as a PDF, only if pandoc and `lualatex` are installed
- `literature-[project-name].bib` — the TRACK RECORD, for accountability and reproducibility: every work with every verdict the agents reached on it — evidence tier, relevance rating, fault-line tags, cleaning and workflow markers, and the engine-derived fields. No reading notes, no `@comment` blocks.
- `literature-[project-name]-annotated.bib` — the REFERENCE-MANAGER IMPORT (Zotero, BibDesk, ...): the same works with standard fields, topical keywords, and the researchers' reading notes with fault-line tags spelled out. No verdict tokens and none of the nine engine-derived fields. Zotero imports the notes as notes and the keywords as tags.
- `research-notes-[project-name].md` — the per-domain analysis the researchers recorded (overview, key positions, gaps, synthesis guidance, relevance), for reading.

**Resuming Phase 6** (Phase 1 found the final review file). First: if `[workdir]/intermediate_files/.phillit-revision` exists, the review is a revision, and it resumes as "Revising a Delivered Review" says, not by the rules below. Otherwise exactly one test decides where:
- If `[workdir]/intermediate_files/lit-review-plan.md` exists, step 8 had started, so steps 1-7 had finished. Run steps 5 and 6 again (both only read; step 6's `CHECK` lines belong in the final summary, and its quotation gate must pass as step 6 says), then steps 8, 9, 10 and 11. Step 8's moves skip whatever is already moved.
- Otherwise run Phase 6 again from step 1. Every step before step 8 rebuilds its output from the sections and domain bibs, which are all still in `[workdir]`, so a repeat is safe. It redoes the fixes made at steps 3 and 5, because the year-conflict lines and the lint report them again. It also covers a crash in the middle of any step, including step 1.

A resume that starts at step 8 cannot reproduce the split's `SPLIT-*` lines, dedupe's `[FULLTEXT-LOST]` lines or the researchers' source issues, since they lived in the interrupted conversation. Say in the final summary that those lines were lost, rather than implying there were none.

1. Assemble final review with YAML frontmatter:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/assemble_review.py \
     "[workdir]/literature-review-[project-name].md" \
     --title "[Research Topic]" \
     "[workdir]"/synthesis-section-*.md
   ```

   Then use **Read** to verify section ordering and transitions.

2. **Normalize section headings**:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/normalize_headings.py \
     "[workdir]/literature-review-[project-name].md"
   ```

   The script enforces consistent numbering: `## Section N: Title` for body sections,
   `### N.M Title` for subsections. Introduction and Conclusion remain unnumbered.
   If the script reports errors, investigate before proceeding.
   Then use **Read** to verify the heading structure looks correct.

3. Aggregate and deduplicate all domain BibTeX files:

   Run the deduplication script over every `literature-domain-*.bib` file (the command's glob picks them all up) to create `literature-[project-name].bib`:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/dedupe_bib.py \
     "[workdir]/literature-[project-name].bib" \
     --evidence-report "[workdir]/intermediate_files/json/evidence_report.json" \
     "[workdir]"/literature-domain-*.bib
   ```

   The script will:
   - Keep the first occurrence of each citation key
   - Prefer entries with abstracts over entries without (abstract-aware merging)
   - Upgrade importance level if a later domain assigned higher importance
   - Re-stamp each merged entry's `EVIDENCE-*` tier attestation-aware from the evidence report
   - Deduplicate by DOI (catches same paper with different keys)
   - Log which duplicates were removed to console
   - Print a `year conflict` line (stderr) when two copies of one work disagree on the year. The merge still happens and the survivor is chosen by abstract and importance, not by year — so before step 4, check the survivor's year against the prose (and CrossRef) and fix the wrong one in the merged bib. A survivor whose year the prose does not cite fails step 5 as an unresolved citation.
   - Print a `[KEY-REMAP] <removed> -> <survivor>` line for each citekey merged away. When a line maps a key of a `tier-overrides.md` line to a survivor that line does not list, add the survivor to that line (`, <survivor>`) before step 6, so step 6 tags its `CHECK` lines. In the final summary, name each override's work by its surviving key.
   - Print a `[FULLTEXT-LOST] <key>: <reason>` line (stdout) for each entry whose `EVIDENCE-FULLTEXT` did not survive the merge: the merged entry is another work's identity, or its text changed after the barrier. The entry keeps a lower tier. Quote every such line verbatim in the final summary.
   - Leave `same_work_group` pairs alone, by design: the barrier's grouping is advisory (a reprint carries its own DOI). The planner already cites one key per group, and step 4 prints a `[SAME-WORK]` line if the prose cites two.

4. Generate bibliography and append to final review:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/generate_bibliography.py \
     "[workdir]/literature-review-[project-name].md" \
     "[workdir]/literature-[project-name].bib"
   ```

   The script will:
   - Match cited works by surname+year proximity in the review text
   - Format references in Chicago Author-Date style from BibTeX metadata only
   - Deduplicate entries with the same DOI
   - Append (or replace) a `## References` section at the end of the review

   Any later re-run of this step (after a prose fix, also after step 7) uses `literature-[project-name].bib` or `intermediate_files/literature-[project-name]-merged.bib`, never `literature-[project-name]-annotated.bib`: the annotated bib lacks the `year_suffix` field, so the References would lose their year letters. The script refuses the annotated bib.

5. Lint the final markdown file:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/lint_md.py \
     "[workdir]/literature-review-[project-name].md"
   ```

   Fix any reported issues before proceeding. A `workflow language in review prose` warning means a sentence may talk about the workflow (the orchestrator, the request, the outline, tiers, notes) instead of the literature. Read the sentence: one that is about the literature and only shares a word ("the orchestrator of the plot, on Aristotle's account") stays as it is. Otherwise rewrite it for the reader, keeping any disclosure in a reader-facing form ("this review did not verify that account"). The References section is now in scope for linting — verify no false positives from italicized journal names, DOI URLs, or other bibliography formatting.

   The linter also verifies every in-text author-year citation resolves to a
   References entry (ERROR + nonzero exit otherwise, printed as
   `ERROR citation: ...`). This channel carries two distinct cases with two
   distinct remedies, plus a third for a missing letter — read which one fired before touching anything:

   - **Does not resolve to any References entry**: the References generator
     dropped a cited work — fix the body/bib author spelling divergence (or
     the bib entry) and re-run step 4; never delete the citation to silence
     the check. This applies to primary and legal sources too (statutes,
     regulations, treaties, reports): they are cited like any other work, so
     they need a bib entry — the sanctioned remedy for an unresolved
     "(GDPR 2016)" is adding the @misc entry, not removing the citation.
   - **Letterless year** ("gives 2018 without its letter, but References lists 2018a, 2018b"): the author has several works that year. Add the letter of the work the claim is about, judged from the sentence and the entries' titles; never drop the citation to silence the check.
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

6. **Evidence checks: the telemetry checker, then the quotation gate (REQUIRED)**. First the telemetry checker: run

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/check_evidence.py "[workdir]/literature-review-[project-name].md" "[workdir]/literature-[project-name].bib" --overrides "[workdir]/tier-overrides.md"
   ```

   (After step 8 the overrides file is at `[workdir]/intermediate_files/tier-overrides.md`.) Include every `CHECK` line **verbatim** in the final summary (they are telemetry, not blockers). A work cited under a tier override may raise a `CHECK` line, which then ends in `[user-requested override]`: keep it, and say beside it that the user asked for the work — never summarize, count, or gloss them: a live run's summary once reported four findings as "two minor notes", which hid a do-not-cite violation from the user.

   **Quotation gate (REQUIRED, right after the telemetry checker)**: run

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/check_quotes.py "[workdir]/literature-review-[project-name].md" "[workdir]/literature-[project-name].bib" --workdir "[workdir]" --evidence-report "[workdir]/intermediate_files/json/evidence_report.json"
   ```

   It checks every quotation attributed to a work with a full text (an entry with a `fulltext_file` field or the `EVIDENCE-FULLTEXT` tier) against that text, and ends with one `QUOTES-SUMMARY:` line. Exit 1 means `FAIL` lines; read every line whatever the exit code, since `FIX` and `WARN` lines come with exit 0. Fix the review and run the gate again until its output has no `FAIL` and no `FIX` line. The `WARN` lines are advisory: act on them as below. Act on every line you mean to act on, then rerun once.
   - `FAIL verbatim`, `FAIL bracket`, `FAIL ellipsis`: the quoted words are not in the work's text, or are in a form the gate refuses. Correct the quotation against the text the entry's `fulltext_file` names (find the passage with Grep), or cut it.
   - `FAIL licence-lost`: the work no longer has a verified full text (the line says why). Cut the quotation, and check the sentences around it against what the work's tier now licenses.
   - `FIX page`: drop the page locator or correct it to the page the text gives; never cut the quotation for it. A roman-numeral or otherwise unrecognized locator: drop it.
   - `FAIL unclosed-quote`: close the quotation mark where the quotation ends, or remove it; then the gate checks the quotation.
   - `WARN uncited-fulltext`: the quoted words are also in the full text of the work the line names (several works when it names several), at the place it gives. Decide which work, if any, the words quote. If a named work, cite only that work, then rerun as below, so the gate checks the quotation's page and the caps. If a work the line does not name (a named work may itself quote it), cite that work instead. If none (the review's own question or phrase, a match by chance), leave the line. If the same line comes back after you cited, the citation is not in the quotation's sentence or the next one in its paragraph: move it there.
   - `WARN uncited`: decide whether the words quote a work. If they do, add its citation (and run the gate again if that work has a full text). If they are a question, a scare quote or the review's own phrase, leave them.
   - `WARN cap`: shorten the quotation where you can. It does not block.

   After a fix that adds, removes or changes a citation, run steps 4 and 5 and the telemetry checker again, and then the gate if you rerun it; do this even when the gate is not rerun, since the final summary takes the `CHECK` lines of the telemetry checker's last run. Exit 2, or output with no `QUOTES-SUMMARY:` line, is a crash: stop Phase 6 (no split, no clean-up, no publish) and report the output verbatim to the user. In the final summary, give the last run's `QUOTES-SUMMARY` line and any `WARN uncited-fulltext` and `WARN cap` lines it still prints.

7. **Split the delivery into its three files**:

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/split_delivery.py \
     "[workdir]/literature-[project-name].bib" \
     --plan "[workdir]/lit-review-plan.md"
   ```

   It rewrites `literature-[project-name].bib` as the track record and writes `literature-[project-name]-annotated.bib` and `research-notes-[project-name].md` beside it. A `SPLIT-ERROR:` line (exit 2) names a file that was NOT written and why — a fault-line tag the plan does not define, or a bib that does not parse; the files it does not name were written. A `SPLIT-NOTICE:` line names analysis that was left out of a written file: a domain whose research notes were withheld (an unrecognised label or unlabelled text in its block; the notes file says so in that domain's place), or a comment block that was dropped although it held analysis. Do not edit files to get past these: report every line **verbatim** in the final summary and deliver the review with what was written.

   If it exits 1 (a bad input or `--plan` path, or a read/write failure), nothing was written: `literature-[project-name].bib` is still the merged bib — report the line verbatim and fix the path before re-running.

   The one exception is a `SPLIT-ERROR` saying the bib is **already split**: this step ran before on this bib, and nothing was written this time. The merged bib it replaced is saved at `[workdir]/intermediate_files/literature-[project-name]-merged.bib`: copy it back over `literature-[project-name].bib` (or re-run step 3, dedupe), then run this step again. If step 8 has already run, the domain bibs and the plan are in `intermediate_files/`: point step 3's input glob at `"[workdir]"/intermediate_files/literature-domain-*.bib` and `--plan` at `[workdir]/intermediate_files/lit-review-plan.md`.

8. Clean up intermediate files (use absolute paths to avoid cwd issues):

   Move JSON API response files to `intermediate_files/json/` for archival (allows debugging while keeping review directory clean):
   ```bash
   mkdir -p "[workdir]/intermediate_files/json"
   find "[workdir]" -maxdepth 1 -name "*.json" -exec mv {} "[workdir]/intermediate_files/json/" \;
   ```
   (`find`, not a bare `mv …/*.json` glob: under zsh an unmatched glob aborts the command before any redirection applies, so `2>/dev/null || true` cannot silence its `no matches found` error.)

   Move stray API-result files from project root (agents sometimes omit the `$REVIEW_DIR/` prefix).
   Use targeted prefixes — never bare `*.json`, which could swallow unrelated files:
   ```bash
   find . -maxdepth 1 \( -name "philpapers_*.json" -o -name "pp_*.json" -o -name "s2_*.json" -o -name "openalex_*.json" -o -name "stage3_*.json" -o -name "arxiv_*.json" -o -name "core_*.json" -o -name "sep_*.json" -o -name "iep_*.json" -o -name "cites_*.json" -o -name "recommendations_*.json" -o -name "verify_*.json" -o -name "encyclopedia_entries-*.json" \) -exec mv {} "[workdir]/intermediate_files/json/" \;
   find . -maxdepth 1 -name "literature-domain-*.bib" -exec mv {} "[workdir]/intermediate_files/" \;
   ```

   Move remaining intermediate files; every move skips what is already moved, so a resumed Phase 6 can run this step again. `lit-review-plan.md` moves FIRST, because its move is the resume test above:
   ```bash
   for f in lit-review-plan.md task-progress.md synthesis-outline.md; do
     if [ -f "[workdir]/$f" ]; then mv "[workdir]/$f" "[workdir]/intermediate_files/"; fi
   done
   find "[workdir]" -maxdepth 1 \( -name 'synthesis-section-*.md' -o -name 'literature-domain-*.bib' \) -exec mv {} "[workdir]/intermediate_files/" \;
   ```

   Safety net — move any remaining non-final files to `intermediate_files/`:
   ```bash
   for f in "[workdir]"/*; do
     case "$(basename "$f")" in
       literature-review-*.md|literature-review-*.docx|literature-*.bib|research-notes-*.md|intermediate_files) ;;
       *) mv "$f" "[workdir]/intermediate_files/" 2>/dev/null || true ;;
     esac
   done
   ```

   Stray directories — agents sometimes create directories at the project root by mistake. Remove any empty directories that match the review topic:
   ```bash
   find . -maxdepth 1 -type d -empty -not -name '.*' -not -name 'reviews' -not -name 'tests' -not -name 'docs' -exec rmdir {} \;
   ```

   **Note:** Never `cd` here either — see the rule under Agent Tool Usage above.

**After publish** (final state, in `reviews/[project-name]/`):
```
reviews/[project-name]/
├── literature-review-[project-name].md    # Final review (markdown)
├── literature-review-[project-name].docx  # Final review (if pandoc available)
├── literature-review-[project-name].pdf   # Final review (if pandoc and lualatex available)
├── literature-[project-name].bib          # Track record: every agent verdict
├── literature-[project-name]-annotated.bib # Reference-manager import: notes + topical keywords
├── research-notes-[project-name].md       # Per-domain research notes
└── intermediate_files/           # Workflow artifacts
    ├── literature-[project-name]-merged.bib # The merged bib as dedupe wrote it, saved by the split
    ├── json/                     # JSON files archived here
    │   ├── s2_<domain>_results.json … verify_<domain>_<citekey>.json
    │   ├── cleaning_ledger-*.json, enrichment_ledger-*.json
    │   ├── fulltext_acquisition.json
    │   └── evidence_report.json
    ├── fulltext/                 # Full texts: <slug>.pdf, its .json record, the barrier's .txt
    ├── .phillit-review.json      # Ownership marker (local mode): review id and state
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

10. **Optional: Convert to DOCX and PDF** (if pandoc is installed; the PDF also needs `lualatex`):
   ```bash
   if command -v pandoc &> /dev/null; then
     pandoc "[workdir]/literature-review-[project-name].md" \
       --from markdown \
       --to docx \
       --output "[workdir]/literature-review-[project-name].docx" \
       --citeproc \
       --bibliography="[workdir]/literature-[project-name].bib" \
       && echo "Converted to DOCX: literature-review-[project-name].docx"
     if command -v lualatex &> /dev/null; then
       pandoc "[workdir]/literature-review-[project-name].md" \
         --from markdown \
         --pdf-engine=lualatex \
         -V geometry:margin=1in -V fontsize=11pt \
         --output "[workdir]/literature-review-[project-name].pdf" \
         && echo "Converted to PDF: literature-review-[project-name].pdf"
     else
       echo "lualatex not installed, skipping PDF conversion"
     fi
   else
     echo "Pandoc not installed, skipping DOCX and PDF conversion"
   fi
   ```

   A failed PDF build (for example a missing LaTeX package) is not a failed review: mention it in the final summary and continue.

   **Important:** Use the full `[workdir]` paths (not bare filenames). Do NOT use `&&/||` chaining for this check, as Pandoc errors would trigger the wrong fallback message.

11. **Publish the review** into `reviews/[project-name]/`. **PRECONDITION**: every agent this review dispatched has completed, and no command the review started is still running — `publish` copies a tree that nothing else may be writing. Make your last update to `task-progress.md` (now in `[workdir]/intermediate_files/`) BEFORE this step: after `publish`, `[workdir]` no longer exists, and a write there would recreate a stray folder outside the workspace. Never write into `[workdir]` after `publish`.

   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/workdir.py publish
   ```

   It copies the review into `reviews/[project-name]/` once, verifies the copy, clears the active-review pointer and deletes the local working copy. In in-place mode it only archives the pointer as `intermediate_files/.completed-review`. A `leftover` in its output names a local folder it could not delete: mention it; it is collected later. An `unproven` entry names a local folder whose ownership could not be proven: mention it verbatim; the review itself was delivered. If it refuses with "no active review", first check whether `reviews/[project-name]/intermediate_files/.completed-review` exists: if it does, the earlier publish had already finished and the workflow is complete. Otherwise run `workdir.py activate [project-name]`, then `publish` again; if `activate` answers that `reviews/[project-name]/` is a delivered review, the workflow is complete too. If it refuses because the copy does not match (`changed_during_copy`, `mismatched`, `extra`), something was still writing: wait until nothing is, then run `publish` again, and if it refuses the same way twice, report it verbatim and stop. If it refuses because `reviews/[project-name]/` belongs to another review, report the refusal verbatim (it names the way out) and stop. Any other refusal from `publish` or `activate`, nonzero exit or non-JSON output: report it verbatim and stop — never copy, move or delete review files by hand.

   Only now is the workflow complete. The same precondition applies to `publish --abandon` (Phase 1, step 7).

---

## Revising a Delivered Review

A delivered review is never changed. When the user wants one revised (new evidence, a correction, a change of emphasis), make a new review from it:

1. **PRECONDITION**: no review is active (Phase 1 step 5's `status` says `"active": false`). Otherwise finish or abandon the active one first (Phase 1 step 7, concurrent review).
2. Run
   ```bash
   bash "$PHILLIT_ROOT/bin/phillit-run" skills/literature-review/scripts/workdir.py revise [delivered-name]
   ```
   (add `--as [new-name]` for a name of the user's choosing; by default it takes `[delivered-name]-r2`, `-r3`, ...). It prints what `init` prints plus `revised_from`. From here on, `[workdir]` and `[project-name]` are the new review's. It copies the delivered review into `[workdir]`, renaming the four deliverables and the merged bib to the new name (everything else in `intermediate_files/` keeps its name; never rename files by hand), and writes `intermediate_files/.phillit-revision`, which marks the review as a revision. `reviews/[delivered-name]/` stays as it was. A refusal, nonzero exit or non-JSON output: report it verbatim and stop. If it prints `carried`, those top-level files of the old review were moved into `intermediate_files/carried-from-[delivered-name]/`.
3. Add a line to `[workdir]/intermediate_files/task-progress.md`: `Revision of [delivered-name]: [what changes and why]`.
4. Edit `[workdir]/literature-review-[project-name].md`. A revision changes prose only, under the writers' rules: every claim about a work stays within what its tier (or its override line) licenses, and no workflow language enters the prose. It cannot add works to the bibliography; for that, run a new review.
5. Run Phase 6 steps 4 (against `[workdir]/literature-[project-name].bib`, the track record), 5, 6 (with `--overrides "[workdir]/intermediate_files/tier-overrides.md"`, and its REQUIRED quotation gate), 10 and 11. Do not run steps 1-3, 7 or 8: the bib is already merged and split, and the files are already in place.
6. In the final summary, name the delivered review it revises and what changed.

To resume an interrupted revision (`intermediate_files/.phillit-revision` exists), read the tracker's `Revision of` line for what to change. If it is missing, the revision was interrupted before step 3: ask the user what to revise (Full Autopilot: stop and say so). Then continue from step 4.

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
| **Review created** | `Working in [workdir]; the finished review will appear in reviews/[project-name]/` |
| **Environment FAIL** | `Environment verification failed. [details]` |
| **Anchor texts** | `Anchor texts: [N] of [M] named works stored` |
| **Phase transition** | `Phase 2/6: Structuring literature review into domains` |
| **Phase transition** | `Phase 3/6: Researching literature in [N] domains (parallel)` |
| **Phase transition** | `Phase 4/6: Outlining synthesis review across domains` |
| **Phase transition** | `Phase 5/6: Writing [N] review sections (parallel)` |
| **Phase transition** | `Phase 6/6: Assembling, delivering and publishing the review` |
| **Agent launch (parallel)** | `Launching [N] domain researchers in parallel...` |
| **Agent completion** | `Domain [N] complete: literature-domain-[N].bib ([number of sources included] sources)` |
| **Gap texts** | `Gap texts: [counts from the summary line]` |
| **Phase completion** | `Phase [N] complete: [summary]` |
| **Assembly** | `Assembling final review with YAML frontmatter...` |
| **BibTeX aggregation** | `Aggregating BibTeX files -> literature-[project-name].bib` |
| **Quotation gate** | `Quotation gate: [N] FAIL, [M] FIX, [K] WARN uncited-fulltext; fixing and rerunning` or `Quotation gate passed` |
| **Delivery split** | `Split delivery: track record, annotated bib, research notes` |
| **Cleanup** | `Moving intermediate files -> intermediate_files/` |
| **DOCX conversion** | `Converted to DOCX: literature-review-[project-name].docx` |
| **PDF conversion** | `Converted to PDF: literature-review-[project-name].pdf` |
| **Publish** | `Published to reviews/[project-name]/` |
| **Workflow complete** | `Literature review complete: reviews/[project-name]/literature-review-[project-name].md ([wordcount])` |
| **Source issues (if any)** | `⚠️ Source issues: [aggregated list from domain researchers]` |

---

## Success Metrics

- Focused, rigorous, insight-driven review — at the length the user asked for; otherwise sized to the literature found, with 4,000–10,000 words as soft guidance
- Resumable (task-progress.md enables continuity)
- Valid BibTeX files
- Delivered into `reviews/[project-name]/` by `workdir.py publish`; nothing of the review is left in the local work folder
