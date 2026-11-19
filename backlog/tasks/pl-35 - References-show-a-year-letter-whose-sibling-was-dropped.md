---
id: PL-35
title: References show a year letter whose sibling was dropped
status: To Do
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
<!-- SECTION:DESCRIPTION:END -->
