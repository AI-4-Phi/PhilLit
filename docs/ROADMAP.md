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

**`_plan_type_downgrade`'s verified-DOI guard and `check_required_fields`
disagree, and the stop hook blocks on the disagreement.** The cleaner has a
downgrade path for an entry that loses a required field (`REQUIRED_FIELDS` in
`metadata_cleaner.py`, "if missing after cleaning, downgrade to @misc") and a
DOCUMENTED exemption from it: "an article that would lose its required
'journal' is NOT demoted when it retains a DOI matching its own API record — a
verified DOI proves the work is identifiable and @article degrades cleanly to
author/year/title." That ruling is deliberate and reads as right. But
`bib_validator.REQUIRED_FIELDS['article']` still contains `journal`, so the
entry the guard deliberately preserved is reported as `missing required field
'journal' for @article` by the validator in the same repo — and
`subagent_stop_bib.sh` accumulates `.errors[]` in FULL into `SYNTAX_ERRORS`
and blocks on it. The cleaner runs in that same hook, AFTER validation, so the
file it leaves blocks the NEXT researcher to stop, and the one after that. One
resumed pass each; `stop_hook_active` caps it at one per subagent, not one per
review.

**Measured, not inferred**: replayed `validate_bib` over all 71 `.bib` files in
the service's delivered production reviews (2026-09-04). Three fail the full
validator; **zero fail any structural check** (encoding, duplicate key,
duplicate field, pybtex). Two of the three are this — `blessenohl2015selfexempting`,
carrying both `METADATA_CLEANED: journal` in its keywords and the DOI
`10.1515/krt-2015-290304` that fires the guard. The third is the same class
from a different check: `konigs2022artificial: 'author' contains LaTeX escape
\"o`, on an entry that parses correctly.

Both halves are live at `191bde5`. The service contained it by narrowing its
own SubagentStop gate to the structural subset and logging the policy findings
instead (`_structural_bib_errors` in `reviews/hooks.py`), which is a service-side
mitigation and not a fix — the disagreement is between two files here. The
shape of the fix is upstream's call: exempting an entry whose `keywords` carry
a `METADATA_CLEANED` marker naming the missing field would be narrow and would
keep the check honest for everything else, but so would dropping the guard and
accepting the `@misc` demotion the docstring argues against.

**Note the service could not have found this before now.** Its ported
SubagentStop hook nested `decision`/`reason` inside `hookSpecificOutput`, where
the CLI reads neither, so the gate had blocked nothing since it was ported.
Fixing that payload is what surfaced the disagreement — this repo's shell hook
never had that bug, so the exposure here is live and unmitigated.

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
