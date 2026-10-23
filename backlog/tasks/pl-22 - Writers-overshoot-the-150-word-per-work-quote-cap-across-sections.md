---
id: PL-22
title: Writers overshoot the 150-word per-work quote cap across sections
status: Later
assignee: []
created_date: '2026-10-22 10:28'
labels:
  - agents
dependencies: []
type: guard
project: Accuracy
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** the cap is per work across the review, but each writer sees only its own section. In the 2026-10-22 live run, 201 words were quoted from Bradley (2012) against the cap of 150; `check_quotes.py` warned (advisory by ruling) and the orchestrator could not get under it. Options: give each writer a per-section quota for works several sections quote (the outline knows which), or have the orchestrator shorten after the gate. Not an accuracy failure: every quotation was verbatim.

**What brings it forward:** Johannes first reads a few reviews that exceed the cap to judge whether it is a problem at all; until he says so, it stays parked.
<!-- SECTION:DESCRIPTION:END -->
