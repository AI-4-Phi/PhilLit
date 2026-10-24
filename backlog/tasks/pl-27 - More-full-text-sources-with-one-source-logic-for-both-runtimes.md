---
id: PL-27
title: 'More full-text sources, with one source logic for both runtimes'
status: Needs Johannes
assignee: []
created_date: '2026-10-24 20:22'
updated_date: '2026-10-24 21:10'
labels: []
dependencies: []
type: feature
project: Accuracy
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** EVIDENCE-FULLTEXT reaches few gap entries, and no OA source tries a work without a DOI. Requested by Johannes through phillit-service (2026-10-24).

Measured on 240 works, every accepted PDF audited by hand: findings, the proposed one-owner shape (a pure engine module the service imports) and the open decisions are in docs/ideas/fulltext-sources.md. Scripts and data: docs/known-issues/fulltext-sources-measurement-2026-10-24/ (local).

Constraint from phillit-service: the source logic has one owner, a pure function in the engine's full-text code that the service imports; the service adds only the HTTP calls under its budgets and SSRF guard.

**Decision needed:** (1) the OpenAlex title route for no-DOI works, and whether the channel carries no-DOI identities (service lifts B2) or the engine resolves a DOI by title; (2) Brave web search: drop, suggest-only, or automatic with an extra screen; (3) whether to ask PhilPapers for harvester or API access to PhilArchive.
<!-- SECTION:DESCRIPTION:END -->
