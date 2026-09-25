---
id: PL-13
title: Dynamic-workflow orchestration
status: Later
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-09-25 19:24'
labels: []
dependencies: []
references:
  - docs/ideas/dynamic-workflow-refactor.md
type: feature
project: Delivery
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The parallel middle of a review rests on prose rules a model can break: "include ALL Task tool calls in a single message" and "never advance before all agents complete". A model that advances early drops domains or sections. A Workflow script would make both guarantees deterministic.

The design, its verified facts and its gates are in `docs/ideas/dynamic-workflow-refactor.md`.

**What brings it forward:** the design doc's "Gates before step 2". The first gate answered no: phillit-service cannot deliver a workspace workflow file, so the step-3 redesign comes before the headless run for gate 2.
<!-- SECTION:DESCRIPTION:END -->
