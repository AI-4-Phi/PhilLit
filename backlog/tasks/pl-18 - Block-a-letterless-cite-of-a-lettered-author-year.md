---
id: PL-18
title: Block a letterless cite of a lettered author-year
status: To Do
assignee: []
created_date: '2026-10-06 14:49'
labels: []
dependencies: []
references:
  - skills/literature-review/scripts/lint_md.py
  - skills/literature-review/scripts/generate_bibliography.py
type: guard
project: Accuracy
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** A cite without its Chicago letter is ambiguous when the author has two works that year, and the reader cannot tell which one carries the claim. Nothing blocks it: the bibliography step reports an ambiguous author-year match, and lint passes.

**Evidence:** headless run 2026-10-06 (moral luck and the control principle, scratchpad `run-ws4`). The barrier gave `khoury2018criminal` the letter a and `khoury2018objects` the letter b, and the References list both as 2018a and 2018b. The prose cites "Khoury (2018) argues that a 'natural penal lottery' account ..." (the 2018a work) with no letter. `check_evidence.py` then matched the EXISTENCE-tier 2018b entry and raised a false `reporting-verb` line.

**Scope:** make a letterless cite of a lettered author-year a lint failure (or a SPLIT/assembly error the orchestrator must fix before delivery), naming the candidates. Check `generate_bibliography.py`'s existing ambiguity report first: it may already hold the data.
<!-- SECTION:DESCRIPTION:END -->
