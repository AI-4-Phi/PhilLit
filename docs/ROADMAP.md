# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Census the two surname rules' DISAGREEMENT over every delivered author
field.** Do not census a textual shape — run
`first_author_prose_surname(author)` against `first_author_surname(author)`
over each `author` field in the delivered corpus and classify the
disagreements by RUNNING the code path, never by matching shapes; enumerating
shapes is what failed here repeatedly. Measure the two consumers'
consequences separately, because their costs differ: for
`check_evidence.find_cites` a divergence is a false "uncited" reading on a
recall-floor checker (telemetry); for `resolve_context` it is an evidence-tier
demotion in the DELIVERED bibliography — an unmatched SEP line means the
barrier never sets `context_written`, so `compute_tier` cannot return
`TIER_CONTEXT`, and `strip_context_fields` leaves no other route to the
field. Only `match_entry_to_article`'s `prose_surname` site is exposed;
`acquire_context`'s second site is inert because
`citation_context.normalize_author` re-derives its own token (measured by
mutating each site alone). Measure the identity rule's own failures on the
same corpus too — the switch is not a clean fix, since Chicago prose writes
neither `{Doe, Jane}` nor `{Doe` — so the census can decide it. Do not change
either consumer blind. The tier chain is pinned only in the phillit-service
mirror (`test_TIER_CONTEXT_requires_the_barriers_own_context_written_flag`
and `test_a_matched_context_earns_EVIDENCE_CONTEXT_and_a_miss_DEMOTES`;
`EXCLUDE_PREFIX` carries `tests/`), so write the same two tests here. Reopen
sooner if `find_cites` output ever feeds something read as a coverage VERDICT
rather than a floor.

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
