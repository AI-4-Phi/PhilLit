# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Re-vendor the engine in phillit-service at this repo's HEAD.** Its
`tools/revendor.py` carries `7ea0021` (the researcher's Stage 1/4/5 prose) and
`165eafc` (the `first_author_prose_surname` owner, the `bib_fields` `%` clause)
downstream; both are engine files, so nothing arrives there until the pin
moves. Run it from a session launched in that repo. Two known trips: its
scope-guard test
`test_a_braced_corporate_author_containing_and_is_a_KNOWN_DIVERGENCE` still
carries the divergence brace-aware author splitting removed upstream, and the
five findings this queue held were filed FROM that mirror — re-reading them
there after the pin should now find them fixed.

**Measure how often a delivered bib writes an author field of either shape
the prose surname rule loses.** `first_author_prose_surname`'s docstring names
two, both pre-dating it, both handing the prose consumers a search string real
Chicago prose does not contain: a comma-less name (`author = {Jane Doe}` gives
`Jane Doe`, so `Doe 2020` is not found) and a braced name with an internal
comma (`{Doe, Jane}` gives the brace-unbalanced `{Doe`). Neither raises --
`check_evidence.find_cites` returns no positions and `resolve_context`'s SEP
match finds no candidate line -- so the cost is false "uncited" telemetry on two
recall-floor checkers, never a block. What is unknown is the RATE, per shape: a
census over the delivered corpus (`docs/known-issues/` has the shape of one).
Note the obvious fix does not cover both: switching to the identity rule fixes
the comma-less name and NOT the braced one, since prose writes neither
`{Doe, Jane}` nor `{Doe`. Do not change either blind.

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
