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
`tools/revendor.py` carries the researcher's Stage 1/4/5 prose, the
`first_author_prose_surname` owner and the `bib_fields` `%` clause downstream;
all are engine files, so nothing arrives there until the pin moves. Run it from
a session launched in that repo. Three things to expect:

- Its scope-guard test
  `test_a_braced_corporate_author_containing_and_is_a_KNOWN_DIVERGENCE` still
  carries the divergence brace-aware author splitting removed upstream.
- The five findings this queue held were filed FROM that mirror — re-reading
  them there after the pin should now find them fixed.
- **The pins do NOT travel, and there are now ~25 of them.**
  `revendor.py`'s `EXCLUDE_PREFIX` contains `tests/`, so every test this work
  added stays here while every fix it guards goes downstream. Read them off
  `git log d532abd..HEAD -- tests/` rather than from a list here, which would
  rot: they sit in `test_agent_definitions.py` (Stage 4's inventory and
  complement pins, Stage 1's three status values, the whole-file `$JSON_DIR`
  scan), `test_bib_identity.py` (the surname divergence classes, the
  protected-group and single-token boundaries, the three fallback branches),
  `test_bib_fields.py` (the 21 `%` placements, the three accepted-text
  differences) and `test_evidence_barrier.py` (the call-order spy plus its
  own anti-vacuity guard). The service has parallel files for each
  (`test_engine_bib_identity.py`, `test_engine_bib_fields.py`,
  `test_engine_check_evidence.py`, `test_engine_resolve_context.py`,
  `test_engine_dispatch_prose.py`, `test_engine_evidence_barrier.py`) — the
  equivalents have to be written into them there, or the mirror carries the
  fixes with none of the guards that keep them fixed.

**Census the two surname rules' DISAGREEMENT over every delivered author
field.** Do not census a textual shape — run
`first_author_prose_surname(author)` against `first_author_surname(author)`
over each `author` field in the delivered corpus and classify the
disagreements. That measures the exposure directly and picks up any shape,
including every class the owner's docstring names as an example and any it
does not. Enumerating the shapes is exactly what failed twice here, which is
why this is specified as a comparison and not as a count. Both are pre-existing and neither raises — `check_evidence.find_cites`
returns no positions and `resolve_context`'s SEP match finds no candidate line
— so the cost is false "uncited" telemetry on two recall-floor checkers, never
a block. Measure the identity rule's behaviour on the same corpus too, not just
the disagreement rate: the census has to be able to decide the switch, and the
switch is not a clean fix — it repairs the comma-less shape and NOT the braced
one, since Chicago prose writes neither `{Doe, Jane}` nor `{Doe`. Do not change
either consumer blind. Reopen sooner if `find_cites` output ever feeds
something read as a coverage VERDICT rather than a floor.

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
