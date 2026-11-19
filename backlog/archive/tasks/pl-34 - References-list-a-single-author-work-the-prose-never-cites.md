---
id: PL-34
title: References list a single-author work the prose never cites
status: Done
assignee: []
created_date: '2026-11-17T11:20:00Z'
updated_date: '2026-11-19T13:00:00Z'
labels: []
dependencies: []
type: bug
project: Accuracy
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** in the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), the prose cites only "Susser, Roessler, and Nissenbaum (2019)" (`susser2019technology`). `generate_bibliography.py` still listed Susser's single-author 2019 paper (`susser2019invisible`) in the References. It printed `[COLLISION] ambiguous: susser2019invisible, susser2019technology share surname/year and the prose also cites Susser 2019 with no letter, in a form the citation parser cannot resolve - all kept, possible phantom references`. The citation was not letterless: it names all three authors, which only one of the two works has. `lint_md.py` passed the phantom entry, and I removed it by hand.

**Scope:** the collision resolver should use the co-author list of a multi-author citation to pick the work, before falling back to keeping all candidates. When it does keep a possible phantom, a check later in Phase 6 should flag it.
<!-- SECTION:DESCRIPTION:END -->
