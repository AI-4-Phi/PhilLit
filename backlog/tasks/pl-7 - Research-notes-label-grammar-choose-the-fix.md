---
id: PL-7
title: 'Research-notes label grammar: choose the fix'
status: Needs Johannes
assignee: []
created_date: '2026-09-25 19:18'
labels:
  - notes
dependencies: []
references:
  - skills/literature-review/scripts/research_notes.py
  - skills/literature-review/scripts/split_delivery.py
  - agents/domain-literature-researcher.md
type: decision
project: Delivery
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The research notes are one of the three delivered files. Real researcher blocks drift from the label grammar, and the split then withholds the whole file.

**Evidence:**
- **Block drift.** In a live Sonnet review on 2026-09-24 (topic: specification gaming and reward hacking), `split_delivery.py` withheld `research-notes-<id>.md`. Three of the eight researcher blocks (domains 4, 6 and 7) left out the `====` rule that closes the block header. So `research_notes.parse_block` read everything down to the final rule as header, and valid IN labels (`DOMAIN_OVERVIEW`, `KEY_POSITIONS`, ...) failed as unknown. Two blocks also used labels outside the grammar (`GREY_LITERATURE`, `INCOMPLETE`). The track-record and annotated bibs were written.
- **Shapes no list can admit.** Domain 6 of the tagged real run uses headings with no colon after `====` rules (INSTRUMENT COMPARISON TABLE, FAULT LINES (...)); no growth of the label list can admit those. FOR/AGAINST/CONTROL sit inside an OUT section in one block and could sit inside KEY_POSITIONS in another, which an IN/OUT list cannot express.

Reproduce from that run's `intermediate_files/literature-<id>-merged.bib`, always on a COPY, because the split rewrites its input. A local reproducer is saved in `docs/known-issues/research-notes-split-2026-09-24/`.

**Decision needed:** `research_notes.py` marks the label grammar "DECIDED, do not reopen", so the fix is Johannes's call. The options:
1. harden the researcher prose that asks for the closing rule;
2. make the parser end the header at the first IN label;
3. grow the label sets. This cannot cover the colon-less headings or the section-dependent sub-labels.

This ruling gates PL-6 (research-notes label rules for researchers) and its test run.
<!-- SECTION:DESCRIPTION:END -->
