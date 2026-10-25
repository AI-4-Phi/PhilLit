---
id: PL-30
title: Order title-route candidates by year agreement and exact title
status: Done
assignee: []
created_date: '2026-10-25 14:13'
updated_date: '2026-10-25 16:32'
labels: []
dependencies: []
type: feature
project: Accuracy
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** the service files a title-route copy in a repository every later review shares, so precision there weighs more than locally. Three outside reviews of the service port suggested ordering, not refusing: try a matched record whose publication year agrees with the identity's (±1) and whose main title matches exactly before a year-mismatched title extension. No recall is lost (a stricter match lost 6 of 50 right hits in the PL-27 measurement). Scope: TITLE_SELECT requests publication_year; matched carries the record's year and the two signals so an operator can read them from the sidecar; fs.order sorts title-route locations by (year agrees, exact title) before the rule-15 rank. Service picks it up at the next pin.
<!-- SECTION:DESCRIPTION:END -->
