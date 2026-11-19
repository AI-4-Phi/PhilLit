---
id: PL-39
title: Outline lets writers state facts found only in the research notes
status: To Do
assignee: []
created_date: '2026-11-17T11:20:00Z'
updated_date: '2026-11-17T12:59:00Z'
labels:
  - agents
dependencies: []
type: feature
project: Accuracy
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** the synthesis-writer contract says only a work's tier (or a user override) licenses claims about it. In the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), the synthesis planner's Writer Conventions told writers to flag published correction notices and preprint status. The domain researchers had recorded those facts in their notes, not in any abstract. As a result:
- The writers of the empirical section and the Conclusion stated the correction notices on Bastani et al. (2025) and Gerlich (2025), each saying so in its report.
- The writer of section 1 cut the same Gerlich fact as unlicensed.
- No gate checks facts that come from the notes. The Costello et al. (2024) erratum, also in the notes, was left out.

So the same kind of fact was stated in one section and cut in another, and nothing verified it either way.

**Ruling (Johannes, 2026-11-17):** option (b). Bibliographic status facts that a researcher recorded in a note (a published correction, an erratum, a retraction, preprint status or peer-review status) may enter the prose, but only for this class of facts and only with a source.

**Scope:**
- The domain researcher records the source with the fact, for example the CrossRef `update-to` relation or the URL of the publisher's notice.
- A Phase 6 check confirms each such statement in the prose against that source. A statement it cannot confirm is cut and listed in the final summary.
- The synthesis planner's Writer Conventions and the writer contract both name this class as the one exception to "only the tier licenses content".
- Every other fact found only in the notes stays unlicensed.
<!-- SECTION:DESCRIPTION:END -->
