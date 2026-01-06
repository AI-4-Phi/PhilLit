# Ideas and Tasks

Developer notes for things to try, features to implement, and things to test.

Last updated: Jan 6, 2026

## Pending

- [ ] Cleanup: can move `test_files/` somewhere into `tests/`?
- [ ] Have Claude check all the python scripts in philosophy-research/scripts
- [ ] Consider reintegrating editor and novelty assessor agents


## Done

- [x] Check that the hooks refers to absolute path to scripts with `$CLAUDE_PROJECT_DIR` variable as in `"command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-style.sh"`
- [x] Reconcile duplicate entries across different domain .bib files. Combined final .bib file often has duplicate entries. Not necessarily with identical keys.
- [x] Reduce use of conventions.md - simple instructions in agent definition instead (370 → 121 lines)
- [x] Consider domain-literature-researcher with Haiku ––– DONE. Decided against it. Stay with Sonnet. Not worth the risk.
- [x] Add instruction to stop agents from going rogue (e.g. if lit review agent decides to take over whole review?)
- [x] Remove use of `cat` in last phase of literature-review skill - inconsistent with agent role (should use Read, Write, and Edit tools)
- [x] Use SubagentStop hook to validate bib files written by the `domain-literature-researcher` agent. File encoding should be UTF-8, BibTeX syntax should be valid, no LaTeX commands for special characters should be used. See `conventions.md`
- [x] Manually review all agents and files - some are very verbose (e.g. ARCHITECTURE.md)
  - [x] ARCHITECTURE.md
  - [x] domain-literature-researcher.md
  - [x] literature-review-planner.md
  - [x] synthesis-planner.md
  - [x] synthesis-writer.md
  - [x] literature-review/SKILL.md
  - [x] philosophy-research/SKILL.md
- [x] Some reviews don't mention any literature. Synthesize maybe but not specific callouts.
- [x] Fix resumability via [resumable subagents](https://code.claude.com/docs/en/sub-agents#resumable-subagents) - not needed, current solution more robust
- [x] Work in reviews/ subfolder by default - added to CLAUDE.md
- [x] Replace WebSearch (high usage costs) with Skill - done: `.claude/skills/philosophy-research/`
- [x] Cleanup README - rewrote README.md, deleted .claude/agents/README.md, created GETTING_STARTED.md
- [x] Ensure lit researcher takes better notes (reminded to do that, need to check next time)
- [x] Add YAML front matter to final synthesis (helps with pandoc workflow)
- [x] Cleanup files at end of review - keep only validated bib and literature-review-final.md
  - synthesis-outline.md
  - synthesis-section-N.md
  - lit-review-plan.md
  - task-progress.md
  - unverified-sources.bib
- [x] Check permissions changes in Claude Code - suspicion: new version default is no permissions
- [x] Fix orchestrator forgetting last steps: aggregating bib files, moving intermediate files, adding YAML frontmatter (tried to address with manual edits)
- [x] Update documentation to reflect intermediate_files/ move
- [x] Improve agent namespace
- [x] adjust model: parameter to inherit
- [x] Try to parallelize agents again
- [X] Explain how users store API keys? Should offer an .env file (and read from in StartSession hook script)?


## Deferred
- [ ] Agent idea: based on .bib file, download PDFs of sources in final report, add path to PDFs in bib files (check first: does this allow for Zotero import?) (NO NEED: Zotero has this function: "Find Full Text".)
- [ ] Need a hook for auto compacting. What can we do to save progress when we run out of context? (Check first if this is really needed. We already have a resume logic)
- [ ] Do final review assembly with a hook and script? Sometimes it takes very long for Claude to do the final step (note: can't do, there is no Stop hook for skills)
- [ ] Use Stop or SubagentStop hook to concatenate bib files? (Same reason for why can't do as above: no Stop hook for skills)
- [ ] Unexpected behavior Writing Phase: `All 9 synthesis-writer agents completed. The agents drafted sections but couldn't write files due to permission restrictions. Now I'll create the sections directory and write all files, then assemble the final review.`
- [ ] Augment agents with skills for reading/writing .bib files or handling text files
  - https://claude-plugins.dev/skills/@K-Dense-AI/claude-scientific-skills/citation-management
  - https://github.com/cadrianmae/claude-marketplace/tree/main/plugins/pandoc
- [ ] When done: convert literature-review-final.md to DOCX
- [ ] Remove task-progress.md updating - orchestrator now uses improved Claude-internal tool, tends to forget to update task-progress.md; earlier conversations can be resumed with /resume


- [ ] Check Anthropic docs for agent refactoring - some agents seem extensive (harder to steer, context expensive); could some be skills?

---

## Johannes' Debug Prompt

```
Now, help me debug. Check the whole literature reivew process in this session. What obstactles did Claude encounter (errors, lack of permissions, confusions and ambiguities)? Is there anything that could have gone better? 

Take your time evaluating the whole workflow progress. Keep a list of things that didn't work right or that could be improved.

Let me know if you require clarification or direction. If you are unsure or would prefer further information or access to other potentially relevant documents, ask the user. 
```
