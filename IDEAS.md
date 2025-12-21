## Some ideas, big and small, of how to improve

Date: Dec 19, 2025. By Johannes
Updated: Dec 21, 2025.

- ensure that lit researcher takes better notes (Johannes already reminded him to do that, need to check how it goes next time)
- Augment agents with skill. E.g. Skill for reading and writing .bib files? Or for handling text files (reading, writing, merging)
    - https://claude-plugins.dev/skills/@K-Dense-AI/claude-scientific-skills/citation-management
    - https://github.com/cadrianmae/claude-marketplace/tree/main/plugins/pandoc
- Add YAML front matter to final synthesis (helps with workflow, e.g. pandoc)
- When done
    - convert literature-review-final.md to DOCX
    - Cleanup files: remove temporary files at the end of review. Keep only validated bib file and literature-review-final.md
        - synthesis-outline.md
        - synthesis-section-N.md
        - lit-review-plan.md
        - task-progress.md
        - unverified-sources.bib
- Check permissions changes in Claude Code 
    - Suspicion: with new version default is no permissions. Change readme, add permissions option in agents YAML block
- Check Anthropic docs to understand how to refactor agents, some of them seem very extensive (harder to steer, context expensive)
    - Could some agents be skills
- feature: download PDFs of sources that make it to the final report, add them to bib files? (could be a different agent)

## DONE / DEFERRED
- fix resumability: the way to do it is described [here](https://code.claude.com/docs/en/sub-agents#resumable-subagents) <-- not needed, current solution more robust
- work in a reviews/ subfolder by default <-- added to CLAUDE.md
- WebSearch has extremely high usage costs. Replace with Skill → **DONE**: `.claude/skills/philosophy-research/`
- cleanup Readme, do we need another readme in .agents → **DONE**: Rewrote README.md, deleted .claude/agents/README.md, created GETTING_STARTED.md