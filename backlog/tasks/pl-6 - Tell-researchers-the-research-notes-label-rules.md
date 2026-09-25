---
id: PL-6
title: Tell researchers the research-notes label rules
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-09-25 19:18'
labels:
  - agents
  - notes
  - test-run
dependencies: []
references:
  - agents/domain-literature-researcher.md
  - skills/literature-review/scripts/research_notes.py
type: docs
project: Delivery
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** One improvised label makes `split_delivery.py` withhold the whole research-notes file. The user then loses the researchers' analysis, one of the three files the delivery split writes.

`agents/domain-literature-researcher.md` (BibTeX File Structure) never says that an improvised `LABEL:` line withholds the notes file. The one tagged real run withheld it on 20 improvised labels. The fix is a one-line instruction: extra analysis goes inside an existing section, and there are no new `LABEL:` lines.

PL-7 (the research-notes label-grammar ruling) may change what counts as an existing section; if it lands first, word the instruction to match. Needs a headless test run; share it with PL-5 (the abstract usability screen).
<!-- SECTION:DESCRIPTION:END -->
