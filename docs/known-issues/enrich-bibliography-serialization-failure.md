# `enrich_bibliography.py` Serialization Failure Drops a Whole Domain's Enrichment Ledger

**Observed**: 2026-08-19, downstream service, production kimi-k3 run
(service review `42b029364b084b6b`, domain 2)
**Severity**: Medium — one crash costs an entire domain its ABSTRACT-tier
citability; the degrade path held, so no false promotion, but the quality
tax is silent to the reader
**Status**: Open

## Summary

Domain 2's enrichment ledger was never written; the run's own
`task-progress.md` records "domain 2 enrichment ledger missing due to
enrich_bibliography.py serialization failure". Consequence, measured:
domain 2 ended with ZERO EVIDENCE-ABSTRACT entries (every other domain had
7–16); its entries fell to CONTEXT/EXISTENCE and the text cites them with
existence-level hedging. The evidence barrier correctly reported top-level
`status: degraded`, and a full tier recomputation over the artifact
confirmed no entry was falsely promoted — fail-closed/degrade-only
behavior worked as designed. The crash itself is the defect.

## Reproducer

The failing domain's inputs are preserved in the service's kept artifact
set: `REVIEWS_BASE_DIR/42b029364b084b6b/intermediate_files/`
(`literature-domain-2.bib` plus the `json/` source envelopes) on the
production box, and the service session kept a local copy. Reproduce the
serialization failure from those inputs; the exact exception shape was not
captured in the run log (worth making the failure log the exception class
and offending record when it is fixed).

Downstream mirror: phillit-service
`docs/known-issues/enrich-bibliography-serialization-failure.md` (fix
arrives there by port).
