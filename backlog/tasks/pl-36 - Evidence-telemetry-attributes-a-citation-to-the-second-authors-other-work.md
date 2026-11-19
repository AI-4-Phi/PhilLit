---
id: PL-36
title: Evidence telemetry attributes a citation to the second author's other work
status: To Do
assignee: []
created_date: '2026-11-17T11:20:00Z'
labels: []
dependencies: []
type: bug
project: Accuracy
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** in the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), `check_evidence.py` printed two `CHECK reporting-verb` lines for `risko2016cognitiveoffloading` (EVIDENCE-EXISTENCE). Both sentences cite "Dunn and Risko (2016)", which is `dunn2016metacognitiveoffloading` (EVIDENCE-ABSTRACT), not Risko and Gilbert (2016). The matcher appears to accept a surname and year anywhere in the citation, so the second author's own 2016 work matched.

**Effect:** a false accuracy alarm. The skill requires CHECK lines to be reported verbatim and never glossed, so a false line reaches the user as a possible violation.

**Scope:** match citations by first author (with "and X" or "et al." for the rest) the way `generate_bibliography.py` does, so that a work by a second author is not matched.
<!-- SECTION:DESCRIPTION:END -->
