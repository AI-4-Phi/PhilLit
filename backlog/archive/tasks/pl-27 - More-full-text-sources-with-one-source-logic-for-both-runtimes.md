---
id: PL-27
title: 'More full-text sources, with one source logic for both runtimes'
status: Done
assignee: []
created_date: '2026-10-24 20:22'
updated_date: '2026-10-25 13:21'
labels: []
dependencies: []
type: feature
project: Accuracy
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** EVIDENCE-FULLTEXT reaches few gap entries, and no OA source tried a work without a DOI. Requested by Johannes through phillit-service (2026-10-24).

Built on branch pl-27-fulltext-sources (worktree ../PhilLit-pl27, head 7c2144d): fulltext_sources.py (pure source logic the service imports), the merged OpenAlex+S2 step in rule-15 order, the OpenAlex title route for no-DOI works, no-DOI identities on the channel, Brave suggest-only links, --gap-entry, SKILL.md questions. 4,038 tests pass; replay 51 right / 0 wrong; headless run (reward hacking) acquired 33 no-DOI works by title and stamped 23 EVIDENCE-FULLTEXT. Rulings and findings: docs/ideas/fulltext-sources.md. Follow-ups: PL-28, PL-29.

phillit-service (PS-93) waits for the release SHA; its re-vendor breaks on removed acquire_fulltext names (told).

**Decision needed:** approve merging the branch into main, bumping plugin.json to 0.5.46 and pushing to origin.
<!-- SECTION:DESCRIPTION:END -->
