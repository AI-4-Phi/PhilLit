---
id: PL-24
title: Straightened quote marks make a correct abstract fail corroboration
status: Done
assignee: []
created_date: '2026-10-23 08:00'
updated_date: '2026-10-23 09:12'
labels:
  - barrier
dependencies: []
type: bug
project: Accuracy
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** abstract corroboration compares hashes after `stamp_evidence.normalize_abstract_for_hash`, which folds only whitespace and backslashes. A researcher who copies an API abstract into the bib with straightened quote marks ("x" for “x”) gets a MISMATCH, and the correct abstract loses EVIDENCE-ABSTRACT.

Evidence (phillit-service PS-83, run fc7edbffba104b6b, engine 2a5b966, 2026-10-23): `rudyhiller2022capacitarian` (openalex). The bib text and live OpenAlex text are both 952 characters after normalization and differ only in two quote marks. The entry was stamped EVIDENCE-EXISTENCE only, `abstract_attested: false`. The service did not trace the barrier path itself.

Scope: fold typographic punctuation (“ ” ‘ ’ to ASCII; probably en and em dashes too) on both sides of every fetched-versus-bib comparison: `enrich_bibliography.corroborate_abstract` and `attest_prefilled_entry` (the pre-filled path, likely the first gate this entry failed). The barrier heal (`evidence_barrier._heal_abstract`) compares against the ledger hash and writes the fetched text, so check whether it needs the fold too.

Constraint: do not change `normalize_abstract_for_hash` itself. It also makes the ledger `abstract_sha256`, so a change orphans existing ledgers.

Tests: straight quotes in the bib against curly ones fetched corroborates; a one-word difference still mismatches.
<!-- SECTION:DESCRIPTION:END -->
