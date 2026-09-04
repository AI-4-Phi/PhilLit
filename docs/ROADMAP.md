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
