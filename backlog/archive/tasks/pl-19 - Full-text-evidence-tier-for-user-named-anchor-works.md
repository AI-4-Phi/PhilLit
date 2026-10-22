---
id: PL-19
title: Full-text evidence tier for user-named anchor works
status: In Progress
assignee: []
created_date: '2026-10-15 13:49'
updated_date: '2026-10-22 07:39'
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

No current tier can carry full text, and prompt wording cannot fix it (the writers correctly refuse a notes file). Every design question is ruled; the rulings and their measurements are in `docs/ideas/fulltext-evidence-tier.md`. The spec (local, `docs/superpowers/specs/2026-10-22-fulltext-evidence-tier-design.md`) passed three outside reviews.

**Now:** the build on branch `fulltext-tier`, then the implementation review, live runs and a release. The service's part (uploads, the licensed-only flag) goes to phillit-service at the next pin.
<!-- SECTION:DESCRIPTION:END -->
