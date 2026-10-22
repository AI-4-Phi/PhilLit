---
id: PL-23
title: NDPR abstracts glue words at italic boundaries
status: Done
assignee: []
created_date: '2026-10-22 14:26'
updated_date: '2026-10-22 14:44'
labels: []
dependencies: []
type: bug
project: Accuracy
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** NDPR review text becomes a book's abstract and ships in the annotated bib. `fetch_ndpr.extract_review_content` reads each paragraph with `get_text(strip=True)`, which strips every text node and joins them with no space, so an italic title loses the spaces around it: "In <em>Mind in Life</em> Evan Thompson" becomes "InMind in LifeEvan Thompson" (live, 2026-10-22: 3 glued words in that review's 8 paragraphs).

**Scope:** join text nodes with a space and collapse whitespace (`get_text(" ", strip=True)` then a single-space fold), with a fixture test.

**Constraint:** the abstract hash changes for every NDPR text that had inline markup, so a resumed review's existing NDPR claims probe as MISMATCH and lose EVIDENCE-ABSTRACT for that run (no barrier failure). Ship it in the same release as another NDPR change, or accept that one-run demotion.

**Brings it forward:** the next NDPR change, or a user report of glued words in an annotated bib.
<!-- SECTION:DESCRIPTION:END -->
