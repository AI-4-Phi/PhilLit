---
id: PL-17
title: Writers characterize an abstract-tier work beyond its abstract
status: In Progress
assignee: []
created_date: '2026-10-06 10:13'
updated_date: '2026-10-06 14:16'
labels:
  - agents
dependencies: []
references:
  - agents/synthesis-writer.md
  - skills/literature-review/scripts/check_evidence.py
type: guard
project: Accuracy
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** A writer characterized an `EVIDENCE-ABSTRACT` work with content its abstract does not hold, taken from the LLM-written `note`. The writer prompt forbids that, and nothing catches it.

**Evidence:** headless run 2026-10-06 (moral luck and the control principle, the PL-9 validation run, files in the session scratchpad `run-ws2/reviews/moral-luck-control-principle/`). Section 2.3 says "Sand (2020) ... quotes Rescher (1995) at length and reports two grounds for the denial" (epistemic or reputational advantage; drunk drivers). `sand2020fleming`'s abstract is about Fleming and penicillin and never mentions Rescher. The run's own report says these claims "rest on bib note fields". `check_evidence.py` flagged the sentence only because it also names the `EVIDENCE-NONE` Rescher entry. The tier override (PL-9) raised the pressure: the writer looked for secondary support for a work it could not verify.

**Ruling: prompt rule.** The writer gets a REQUIRED source check after drafting: every claim about what a work says, including what one work says about another, must be in that work's licensed text, else it is cut or narrowed and named in the completion message (`Unsupported, cut:`), which the orchestrator quotes in the final summary. Validate in a headless run.
<!-- SECTION:DESCRIPTION:END -->
