---
id: PL-35
title: References show a year letter whose sibling was dropped
status: Done
assignee: []
created_date: '2026-11-17T11:20:00Z'
labels: []
dependencies: []
type: bug
project: Accuracy
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** in the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), the barrier lettered Matheson's 2024 works across the whole bibliography: `matheson2024philosophy` got `a`, and `matheson2024why` got `b`. The review cites only "Why Think for Yourself?". `generate_bibliography.py` dropped the uncited `a` entry (`[COLLISION] dropped matheson2024philosophy`). The delivered review cites "Matheson (2024b)" and lists "Matheson, Jonathan. 2024b." with no 2024a. Lint passes. A reader sees a lone 2024b.

**Scope:** letter only works the review cites, or re-letter after the References generator has fixed the cited set, and update the in-text citations to match. Related: the archived PL-18, "Block a letterless cite of a lettered author-year".

**Resolution (detection only, by Johannes's ruling):** `generate_bibliography.py` prints a `[LETTER]` line for each such group and leaves prose, bib and References unchanged; SKILL.md step 4 has the line quoted verbatim in the final summary. The letter is not rewritten because a stateless rewrite in step 4 is undone by the next step-4 run (see `warn_lone_letters`' docstring).
<!-- SECTION:DESCRIPTION:END -->
