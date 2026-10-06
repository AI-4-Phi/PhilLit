---
id: PL-15
title: 'Enrichment: try the next abstract source when one is unusable'
status: In Progress
assignee: []
created_date: '2026-10-06 07:32'
updated_date: '2026-10-06 08:45'
labels:
  - barrier
dependencies: []
references:
  - skills/literature-review/scripts/enrich_bibliography.py
  - skills/philosophy-research/scripts/get_abstract.py
  - skills/literature-review/scripts/abstract_usability.py
type: feature
project: Accuracy
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** When the first abstract source returns an unusable text (a stub, a keyword list, a publisher page, an opening extract, word salad), the work loses its `EVIDENCE-ABSTRACT` tier, even when a later source holds a good abstract. The 2026-10-02 run refused 12 entries this way at the barrier.

Enrichment takes the first abstract `get_abstract.resolve_abstract` finds. The usability screen (`abstract_usability.unusable_reason`) runs only at the barrier, after corroboration, so nothing tries another source.

**Scope:** enrichment is stubborn. It screens each candidate with `unusable_reason` and, when a text is unusable, moves on to the next source in the probe order (S2, OpenAlex, CORE, NDPR) until one passes or all are spent. A researcher-prefilled abstract that fails the screen also falls through to resolution. The ledger records the source that passed, so the barrier's corroboration re-fetches from that source. The barrier keeps its screen as the final gate.

Measure on the 2026-10-02 separation-of-powers files (on a copy) how many of the 12 refusals a later source rescues.
<!-- SECTION:DESCRIPTION:END -->
