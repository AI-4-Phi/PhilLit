---
id: PL-17
title: Writers characterize an abstract-tier work beyond its abstract
status: Needs Johannes
assignee: []
created_date: '2026-10-06 10:13'
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

**Decision needed:** how to close it.
1. Prompt only: a REQUIRED check in the writer's procedure that every content claim about an ABSTRACT-tier work is in its abstract.
2. A mechanical flag in `check_evidence.py`: a sentence that cites an ABSTRACT-tier work and carries content words found in its note but not in its abstract (telemetry, like the other CHECK lines).
3. Both.
4. Accept as a residual and say so in the writer's spec.
<!-- SECTION:DESCRIPTION:END -->
