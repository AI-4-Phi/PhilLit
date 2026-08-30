# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Dynamic-workflow orchestration for Phases 3–5** — unstarted, unblocked.
Design and status: `docs/ideas/dynamic-workflow-refactor.md`, which owns them.

**Two findings from the service's `ce38441` re-vendor reviews** (two external
models over the full intake diff; every claim below re-verified against this
tree before filing — two of the reviewers' larger claims did NOT survive
verification and are recorded at the end so nobody re-chases them):

- **`lint_md` has no collision backstop, and the contraction's residual (b)
  is silent exactly there.** `ascii_variants`' accepted-residual note leans on
  `generate_bibliography._resolve_collisions` (keep-all + `[COLLISION]`
  stderr), but lint's `_fold_variants` IS `ascii_variants` with no equivalent
  machinery: body "Gust (2020)" against a References line "Guest, D. 2020. …"
  now resolves silently (reproduced empirically) where a correct ERROR used
  to fire — the bad direction for a checker. The census behind the ≥4 guard
  measured needle-side flood; the (b) class is prose/line-side digraph
  vocabulary, which is unbounded. Owed: one sentence in the residual note
  naming lint's lack of backstop, and optionally a pin (the service carries
  one downstream: `test_guest_gust_false_resolve_is_the_accepted_residual`).

- **The researcher's chapter wording re-softens on the bail path.**
  "CrossRef's best available container otherwise" implies a quality judgment
  CrossRef does not make; the bail value is CrossRef's FIRST LISTED
  container, which for the motivating fixture was the series. "CrossRef's
  first listed container" is the accurate hedge. One-line prose fix in
  `domain-literature-researcher.md`.

  Minor, mention-only: `volume`/`issue` `0` is dropped at the parser
  (`str(...) if truthy`) before the admission gate ever sees it — probably an
  accepted drop, but nothing says so.

  Verified NON-findings, for the record: (a) the reviewers' worry that the
  parsed-title stress sweep might have been title-only pairs is answered by
  `docs/known-issues/parsed-title-measurement-2026-08-29/` — pass 2 scored
  full raw reference lines from 115 cached articles, so the
  journal/publisher-token overlap class was measured, not missed; (b) the
  claimed `contract_fold("Schulze") == "schulz"` bridge is false — "schulze"
  contains no ae/oe/ue digraph and the Schulze-vs-Schulz lint ERROR still
  fires.
