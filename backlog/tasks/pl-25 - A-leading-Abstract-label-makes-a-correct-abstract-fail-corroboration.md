---
id: PL-25
title: A leading Abstract label makes a correct abstract fail corroboration
status: To Do
assignee: []
created_date: '2026-10-23 10:15'
labels:
  - barrier
dependencies: []
type: bug
project: Accuracy
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** abstract corroboration rejects a correct copy when only one side starts with an "Abstract" / "ABSTRACT" label. Measured 2026-10-23 on 1,799 local bib abstracts against the API JSON they were copied from (`docs/known-issues/abstract-typography-measurement-2026-10-23/measure.py`): after the typography fold, about 40 pairs differ only by that leading label. In 32 the source has it and the researcher dropped it; in 8 the bib has it and the source does not.

Scope: extend `stamp_evidence.abstract_texts_agree` (the fetch-vs-bib comparison only; never `abstract_hash`, which is the ledger hash) to ignore one leading label on either side. Measure the rescue with the script above first.

Constraint: philosophy abstracts can start with the word itself ("Abstract objects are ..."), so strip only a label shape (for example the word followed by a colon, a period, or a case change such as "ABSTRACT The ..."), and test that "Abstract objects are" keeps its first word. A wrong strip only equates two texts that differ by that one word, so it is a false accept of little weight, but it should still not happen.
<!-- SECTION:DESCRIPTION:END -->
