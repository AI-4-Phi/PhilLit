# PhilLit Roadmap

**Open engineering work only.** Detailed problem write-ups live in
`docs/known-issues/` (one file per issue, each with a Status line); design
sketches in `docs/ideas/`. Shipped work is deleted from this file rather than
marked done — the git log is the history. A decision that is still binding
belongs in `CLAUDE.md` or the owning module, not here.

## Queue

**Service re-vendor.** Run the service's scripted re-vendor (`tools/revendor.py`)
at a pin at or past this repo's tip. Service-session work, never
hand-mirrored — rule in `CLAUDE.md`, "Sister repo: phillit-service".

One thing that run cannot infer: the service filed 19 dangling section
citations across 8 engine files, but only 8 existed here. `source_store.py` is
not in this repo at all, and `fetch_sep`/`fetch_iep`/`fetch_ndpr`/`rate_limiter`
carry no such pointer, so that count was taken from the service tree. The
remaining ~11 sites are the service's own to check — no mirror reaches them.

Nothing else is queued. `docs/ideas/dynamic-workflow-refactor.md` is the only
substantial unstarted item: its feasibility gate passed on all six checks,
implementation never began.

## Recorded residuals — read before filing a new defect

None of these is queued. Each is here so a recurrence is recognized instead of
re-investigated.

- **A keep-all resurrection can put an evidence-excluded entry into delivered
  References.** `_resolve_collisions`' protective keep-all branch carries a
  suffix group's uncited sibling through even when the synthesis outline
  excluded it as EVIDENCE-NONE; the 2026-08-26 run hit this at first assembly
  and its orchestrator removed the entry by hand. Owner decision: recorded,
  not queued. If it recurs, the two directions worth evaluating are
  assembly-time letter re-derivation over the delivered set — assembly can
  renumber prose and References together, which render-time suppression
  cannot — and a report bucket naming every keep-all resurrection, so nobody
  has to find one by hand.
- **Nothing mechanical polices how a WEB-tier source is characterized.**
  `check_evidence.py`'s verb heuristics run only on `_LOW_TRUST_TIERS`, so the
  note-license boundary is held by writer prose alone, against a measured
  1-in-4 note-drift baseline. Extending the verb heuristic as it stands would
  false-positive on legitimate note-licensed cites; whether a feasible check
  exists at all (note-vs-prose containment at Phase 6, say) is open.
- **A compact `venue_status` that survives `_strip_derived_fields` is never
  re-flagged**, and both planner and writer act on it, so the strip asymmetry
  their prose documents is not fully honest. The splice half of this shape is
  fixed — a swallowed or duplicate-producing splice reverts and is reported —
  and this half is not. The strip's three accepted limits, and why widening
  the anchor is the wrong trade, are in `evidence_barrier._strip_derived_fields`.
- **Three web-evidence paths have never been exercised by production data:**
  the `wayback_failed` bucket, the book-year direction bound, and the
  publisher-prefix attestation edge. All three are test-covered, so this is
  not a coverage gap — but do not describe them as validated by a live run.

Anything else still open lives in its own `docs/known-issues/` file — look for
a Status line that still reads Open.
