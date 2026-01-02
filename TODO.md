# Ideas and Tasks

Developer notes for things to try, features to implement, and things to test.

Last updated: Jan 1, 2026

## Pending

- [ ] Reduce use of conventions.md - simple instructions in agent definition instead (potential for confusion too great)
- [ ] Improve agent namespace
- [ ] Remove use of `cat` in last phase of literature-review skill - inconsistent with agent role (should use Read, Write, and Edit tools)
- [ ] Fix orchestrator forgetting last steps: aggregating bib files, moving intermediate files, adding YAML frontmatter (tried to address with manual edits)
- [ ] Update documentation to reflect intermediate_files/ move
- [ ] Try to parallelize agents again
- [ ] Manually review all agents and files - some are very verbose (e.g. ARCHITECTURE.md)
- [ ] Consider reintegrating editor and novelty assessor agents
- [ ] Remove task-progress.md updating - orchestrator now uses improved Claude-internal tool, tends to forget to update task-progress.md; earlier conversations can be resumed with /resume
- [ ] Agent idea: based on .bib file, download PDFs of sources in final report, add path to PDFs in bib files (check first: does this allow for Zotero import?)

## Done

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

## Deferred

- [ ] Augment agents with skills for reading/writing .bib files or handling text files
  - https://claude-plugins.dev/skills/@K-Dense-AI/claude-scientific-skills/citation-management
  - https://github.com/cadrianmae/claude-marketplace/tree/main/plugins/pandoc
- [ ] When done: convert literature-review-final.md to DOCX


- [ ] Check Anthropic docs for agent refactoring - some agents seem extensive (harder to steer, context expensive); could some be skills?
