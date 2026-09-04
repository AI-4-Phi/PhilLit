# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Re-vendor phillit-service at the current `main` tip (`2110dc8` or later — not the v0.5.15
bump `bcc80b7`: the commits past it change `docs/conventions.md`, which the mirror vendors,
and `check_evidence.py`), from a session launched in that repo.** Five things that session
must know. (1) `hooks/cleaning_marker.py` is a NEW file
in the vendored engine region; if `tools/revendor.py` enumerates files rather than copying
the tree, the service's `bib_validator` dies at import with `ModuleNotFoundError:
cleaning_marker`. (2) The service's `_structural_bib_errors` narrowing of its SubagentStop
gate was a mitigation for the cleaner/validator disagreement this pin fixes; decide there
whether to keep it. (3) The service's known-issue file
`prose-surname-divergence-demotes-a-tier.md` and its test
`test_acquire_context_END_TO_END_is_gated_by_the_MATCH_site_only` say the passage site is
INERT for the divergence. It is not: `citation_context.normalize_author` keeps a tie, so
on space-spelled prose the passage site misses the same way — the match site gates first
and MASKS it. This repo's `tests/test_resolve_context.py::
TestSurnameRuleGatesContextAcquisition` pins the true facts; the census file above
closes that known issue's "what closes this" clause. (4) The box's SEP mirror (`sum2026`)
lacks `ethics-care` and `wisdom-analytic`, which delivered reviews used; adding them
restores 75 of 146 attempted rows to the census. (5) `check_evidence.rc_surname` is now an
alias of `enrich_bibliography.get_author_last_name` (search text: case-protection braces stripped,
comma-less names to their last token), no longer
of `bib_identity.first_author_prose_surname`; the service's
`tests/test_engine_bib_identity.py::TestProseSurnameIsTheOwner` pins the old binding and
goes red at any pin that includes the switch. The 2026-09-04 census licensed it for that one
consumer (its roadmap already says the census is what must license such a switch);
`resolve_context` is unchanged.

## Checked and deliberately NOT filed

Not a queue — a register, so these are not re-found. Each was a live candidate
that did not survive reading the file it concerns
(`agents/domain-literature-researcher.md`).

- The budget's `Stage 5.5 enrichment | 1 (2 if you added entries after it)`
  does NOT contradict "the bib file is FROZEN after enrichment" — FROZEN's own
  bullet sanctions "adding a missed entry" by surgical `Edit`. Two independent
  reviewers called it a contradiction, which is a readability datum rather than
  a defect, and worth knowing given the audience is a model.
- Stage 4 case 3's `<status from the Stage 3 tail>` is not undefined when a
  source fails: Stage 3's tail names each expected file explicitly, so a
  missing one prints a `grep: … No such file` line. (Stage 1 and Stage 4's
  tails glob, which is the case that IS absent — but neither is quoted by
  case 3.)
- Stage 5.5 does carry a failure path: "a FAILED run — network error, crash —
  does not count: re-run it".
- The budget's `Stage 5 verification | 1 per ~6 DOIs` is keyed on DOIs while
  Stage 5's work is keyed on papers, so the DOI-less fallback's calls are
  uncounted — real, but the table is explicitly approximate ("About ten
  calls") and says what it caps ("ceremony"), so it does not carry the risk of
  a skipped mandated call.
