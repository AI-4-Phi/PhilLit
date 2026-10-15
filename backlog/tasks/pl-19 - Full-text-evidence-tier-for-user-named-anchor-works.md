---
id: PL-19
title: Full-text evidence tier for user-named anchor works
status: Needs Johannes
assignee: []
created_date: '2026-10-15 13:49'
labels:
  - barrier
  - agents
dependencies: []
type: feature
project: Accuracy
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** a review whose question turns on one named paper can get it wrong, because no tier lets a writer use that paper's full text. In the 2026-10-14 justified-harm run, Gardner (2019) sat at EVIDENCE-EXISTENCE and the review misread its central distinction; Johansson and Risberg (2018) was CC BY and read in full, but at EVIDENCE-ABSTRACT the writers cut its main arguments.

No current tier can carry full text, and prompt wording cannot fix it (the writers correctly refuse a notes file). The sketch, the evidence and ten open questions are in `docs/ideas/fulltext-evidence-tier.md`: a barrier-stamped EVIDENCE-FULLTEXT tier backed by a DOI-keyed text file with page markers, an acquire script (OA or user-supplied PDF), and an "acquire anchor texts" step in Phase 1.

A barrier change: a spec and a two-model review come before any code.

**Decision needed:** the ten questions in the sketch, one at a time, starting with "new tier or widen EVIDENCE-WEB".
<!-- SECTION:DESCRIPTION:END -->
