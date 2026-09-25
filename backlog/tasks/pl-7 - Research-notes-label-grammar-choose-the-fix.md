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
**Why:** The research notes are one of the three files the delivery split writes. Real researcher blocks drift from the label grammar, and the split then withholds the whole file.

**Evidence:**
- **Block drift.** In a live Sonnet review on 2026-09-24 (topic: specification gaming and reward hacking), `split_delivery.py` withheld `research-notes-<id>.md`. Three of the eight researcher blocks (domains 4, 6 and 7) left out the `====` rule that closes the block header. So `research_notes.parse_block` read everything down to the final rule as header, and valid IN labels (`DOMAIN_OVERVIEW`, `KEY_POSITIONS`, ...) failed as unknown. Two blocks also used labels outside the grammar (`GREY_LITERATURE`, `INCOMPLETE`). The track-record and annotated bibs were written.
- **Shapes no list can admit.** In an earlier real run, domain 6 uses headings with no colon after `====` rules (INSTRUMENT COMPARISON TABLE, FAULT LINES (...)); no growth of the label list can admit those. FOR/AGAINST/CONTROL sit inside an OUT section in one block and could sit inside KEY_POSITIONS in another, which an IN/OUT list cannot express.

Reproduce the block drift from the 2026-09-24 run's `intermediate_files/literature-<id>-merged.bib`, always on a COPY, because the split rewrites its input. A reproducer is saved locally (untracked) in `docs/known-issues/research-notes-split-2026-09-24/`.

**Decision needed:** `research_notes.py` marks the label grammar "DECIDED, do not reopen", so the fix is Johannes's call. It is two questions:
1. **Malformed headers.** How does a block whose header lacks the closing `====` rule recover? Harden the researcher prose that asks for the rule, make the parser end the header at the first IN label, or both.
2. **Structures outside the grammar** (improvised labels, colon-less headings, section-dependent sub-labels). Accept them by growing the label sets, which cannot cover the last two; forbid them in the researcher prompt (PL-6, research-notes label rules, covers improvised labels; colon-less headings would need a further line); or represent them another way.
<!-- SECTION:DESCRIPTION:END -->
