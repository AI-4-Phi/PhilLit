---
id: PL-5
title: Keep unusable abstracts out of the evidence tier
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-09-25 19:24'
labels:
  - barrier
  - test-run
dependencies: []
references:
  - skills/literature-review/scripts/evidence_barrier.py
  - skills/literature-review/scripts/enrich_bibliography.py
type: bug
project: Accuracy
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** Accuracy is objective #1. A citable evidence tier that rests on an unreadable abstract lets the writers make claims the evidence cannot support.

`EVIDENCE-ABSTRACT` attests sameness, not usability. The barrier's per-source re-fetch hash-matches the bib's abstract against the live source. That proves the text was not invented; it cannot see that the text is useless. The 2026-09-10 run (topic: separation of powers) granted the tier to five unusable abstracts: one truncated, one a bare JEL keyword string, two bibliographic stubs and one garbled OCR text. Meanwhile `abstract_corroboration` reported 127/127 with zero mismatches.

Reproduce from that run's artifacts before designing anything. A usability screen is a second test, separate from the corroboration hash. Test the screen on a copy of that run's bibs first. A headless run then confirms it end to end; share that run with PL-6 (research-notes label rules).
<!-- SECTION:DESCRIPTION:END -->
