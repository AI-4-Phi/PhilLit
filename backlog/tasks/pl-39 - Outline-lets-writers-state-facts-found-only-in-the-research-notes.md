---
id: PL-39
title: Outline lets writers state facts found only in the research notes
status: Done
assignee: []
created_date: '2026-11-17T11:20:00Z'
updated_date: '2026-11-19T15:51:00Z'
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

**Ruling (Johannes, 2026-11-17):** option (b). Bibliographic status facts (a published correction, an erratum, a retraction, preprint status) may enter the prose, but only for this class of facts and only with a source.

**Ruling (Johannes, 2026-11-19, mechanism):** the evidence barrier verifies these facts, not the researcher. A status fact found only in a researcher's note stays unlicensed.

**What was built:**
- The evidence barrier stamps a barrier-owned `status_notice = {<item>; ...}` field (`skills/literature-review/scripts/status_notice.py`). For every entry with a DOI that is not at EVIDENCE-NONE, it runs two batched CrossRef queries: forward (`filter=doi:`, the record's own `updated-by`, type and subtype) and reverse (`filter=updates:`, notices whose `update-to` names the DOI). Items: `retraction`, `partial_retraction`, `withdrawal`, `expression_of_concern` and `correction` (CrossRef correction, erratum, corrigendum), each with the notice DOI, plus `preprint` for a posted-content preprint. A retraction or withdrawal issued in place carries the article's own DOI. A first-author and title identity check comes before any stamp.
- The stamp licenses that a notice exists, never its substance. Absence means no status fact is licensed in this run. The report's `status_notice` object gives a state per entry. The pass shares venue vetting's 120 s metadata window and is switched off with `PHILLIT_STATUS_NOTICE=0`. The barrier strips and re-derives the field on every run. Dedupe keeps the survivor's own field.
- The synthesis writer has a REQUIRED rule. It may state a status only when the entry's `status_notice` has that item, and only in fixed wording with the link on first mention. It never says what a notice changed, and never takes a status from a note. The planner never plans a retracted or withdrawn work as support.
- Phase 6 telemetry (`check_evidence.py`): `CHECK status-claim` names cited works whose `status_notice` lacks the category of a status word in the sentence. `CHECK retracted-cited` lists every sentence citing a retracted or withdrawn work, so the orchestrator can confirm each one discloses the status.
<!-- SECTION:DESCRIPTION:END -->
