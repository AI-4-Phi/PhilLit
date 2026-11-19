---
id: PL-32
title: Quotation gate refuses quotes from an article's unnumbered first page
status: To Do
assignee: []
created_date: '2026-11-17T11:20:00Z'
labels: []
dependencies: []
type: bug
project: Accuracy
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** `check_quotes.py` FAILs a correct quotation when it sits on the first page of an article whose first page carries no detected page number. `fulltext._quotable_range` limits matching to the span from the first to the last confirmed page, so a leading `[[sheet 1]]` block is never searched. In the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), Sterelny (2010), "Minds: extended or scaffolded?" (`doi-10.1007_s11097-010-9174-y`), has the abstract and first page under `[[sheet 1]]` and the next page as `[[page 466]]`. Three quotations from the abstract, copied from the stored text (lines 13-15), returned `FAIL verbatim`, including one that sits on a single line. A quotation from page 466 passed.

**Effect:** the gate pushed the orchestrator to drop the quotation marks and keep a near-verbatim paraphrase. That is worse for accuracy than the quotation it refused.

**Scope:** make an article's own unnumbered first page quotable, for example when the sheet directly precedes the first confirmed page and the page map implies its number, either with that inferred locator or with none. Keep excluding repository cover sheets, which the range rule was presumably meant to exclude.
<!-- SECTION:DESCRIPTION:END -->
