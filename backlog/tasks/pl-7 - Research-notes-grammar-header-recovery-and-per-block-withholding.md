---
id: PL-7
title: 'Research-notes grammar: header recovery and per-block withholding'
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-10-06 07:13'
labels:
  - notes
  - test-run
dependencies: []
references:
  - skills/literature-review/scripts/research_notes.py
  - skills/literature-review/scripts/split_delivery.py
  - agents/domain-literature-researcher.md
type: feature
project: Delivery
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The research notes are one of the three files the delivery split writes. Real researcher blocks drift from the label grammar, and the split then withholds the whole file.

**Evidence:**
- **Block drift.** In a live Sonnet review on 2026-09-24 (topic: specification gaming and reward hacking), `split_delivery.py` withheld `research-notes-<id>.md`. Three of the eight researcher blocks (domains 4, 6 and 7) left out the `====` rule that closes the block header. So `research_notes.parse_block` read everything down to the final rule as header, and valid IN labels (`DOMAIN_OVERVIEW`, `KEY_POSITIONS`, ...) failed as unknown. Two blocks also used labels outside the grammar (`GREY_LITERATURE`, `INCOMPLETE`). The track-record and annotated bibs were written.
- **Shapes no list can admit.** In an earlier real run, domain 6 uses headings with no colon after `====` rules (INSTRUMENT COMPARISON TABLE, FAULT LINES (...)); no growth of the label list can admit those. FOR/AGAINST/CONTROL sit inside an OUT section in one block and could sit inside KEY_POSITIONS in another, which an IN/OUT list cannot express.

Reproduce the block drift from the 2026-09-24 run's `intermediate_files/literature-<id>-merged.bib`, always on a COPY, because the split rewrites its input. A reproducer is saved locally (untracked) in `docs/known-issues/research-notes-split-2026-09-24/`.

**Ruling:**
1. **Malformed headers: both.** The researcher prompt makes the closing `====` rule a REQUIRED item with an example. The parser ends the header at the first IN label, since an IN label is never legal in a header. This replaces the docstring sentence "an IN label there is unknown, not a section".
2. **Structures outside the grammar: forbid, and withhold per block.** The grammar stays strict and the label sets do not grow. The researcher prompt also forbids colon-less headings and section-dependent sub-labels (FOR/AGAINST/CONTROL). An `UnknownLabel` withholds only the offending domain's block: the notes file is still delivered, and that domain's place carries a visible line naming every unknown label and pointing to the annotated bibliography.

Update the DECIDED docstring in `research_notes.py` to the new rule. Validate with the 2026-09-24 reproducer (on a copy) and one headless run.
<!-- SECTION:DESCRIPTION:END -->
