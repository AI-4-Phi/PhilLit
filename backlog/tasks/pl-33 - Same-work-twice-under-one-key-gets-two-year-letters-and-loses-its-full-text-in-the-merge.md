---
id: PL-33
title: >-
  Same work twice under one key gets two year letters and loses its full text in
  the merge
status: In Progress
assignee: []
created_date: '2026-11-17T11:20:00Z'
updated_date: '2026-11-19T10:53:00Z'
labels:
  - barrier
dependencies: []
type: bug
project: Accuracy
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** in the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), Rubel, Castro and Pham's *Algorithms and Autonomy* (2021) entered two domains under the same key `rubel2021algorithms`. Domain 4 had it with DOI 10.1017/9781108895057 and the short title. Domain 6 had it without a DOI, with the subtitle, and with a stored full text (EVIDENCE-FULLTEXT). The barrier reported `same_work` groups 0 and gave the copies different year letters (`a` in domain 4, `b` in domain 6). `dedupe_bib.py` then printed `[SUFFIX] conflict: 'rubel2021algorithms' and 'rubel2021algorithms' carry 'a' and 'b' - keeping 'a'`. It kept the DOI copy, copied the full-text file from the other copy, and printed `[FULLTEXT-LOST] rubel2021algorithms: identity changed in the merge (DOI, title, author or year)`.

**Effect:** one work is lettered as two, and a verified full text is discarded. The review did not cite the work, so no harm was visible this time.

**Scope:** the barrier's same-work grouping and year-letter pass should treat one key with the same authors and year, whose titles differ only by a subtitle, as one work. The merge should then keep the full-text tier when the surviving copy is the same work.
<!-- SECTION:DESCRIPTION:END -->
