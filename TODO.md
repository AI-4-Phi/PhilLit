# Ideas and Tasks

Developer notes for things to try, features to implement, and things to test.

Last updated: Jan 6, 2026

## Pending

- [ ] Do final review assembly with a hook and script? Sometimes it takes very long for Claude to do the final step
- [ ] Unexpected behavior Writing Phase: `All 9 synthesis-writer agents completed. The agents drafted sections but couldn't write files due to permission restrictions. Now I'll create the sections directory and write all files, then assemble the final review.`
- [ ] Need a hook for auto compacting. What can we do to save progress when we run out of context?
- [ ] How to stop agents from going rogue (e.g. if lit review agent decides to take over whole review?)
- [ ] Use Stop or SubagentStop hook to concatenate bib files?
- [ ] Use hook to validate syntax of bib files?
- [ ] Check that the hooks refers to absolute path to scripts with `$CLAUDE_PROJECT_DIR` variable as in `"command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-style.sh"`
- [ ] Reduce use of conventions.md - simple instructions in agent definition instead (potential for confusion too great)
- [ ] Remove use of `cat` in last phase of literature-review skill - inconsistent with agent role (should use Read, Write, and Edit tools)
- [ ] Try domain-literature-researcher with Haiku
- [ ] Manually review all agents and files - some are very verbose (e.g. ARCHITECTURE.md)
  - [x] ARCHITECTURE.md
  - [ ] domain-literature-researcher.md
  - [ ] literature-review-planner.md
  - [ ] synthesis-planner.md
  - [ ] synthesis-writer.md
  - [ ] literature-review/SKILL.md
  - [ ] philosophy-research/SKILL.md
- [ ] Have Claude check all the python scripts in philosophy-research/scripts
- [ ] Consider reintegrating editor and novelty assessor agents
- [ ] Agent idea: based on .bib file, download PDFs of sources in final report, add path to PDFs in bib files (check first: does this allow for Zotero import?)

## Done

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
