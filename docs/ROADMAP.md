# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

- **Re-vendor phillit-service at the 0.5.19 pin** - the service's item, run
  from that repo. 0.5.19 is the final-design review round of the `@comment`
  grammar: block extent by pybtex's rule (the next `@`, not the braces),
  paren-delimited commands lexed with braces and quotes, a BOM tolerated,
  render crashes routed through the refusal path, and dispatch rule 2/3
  wording.
- **Bind the cleaning ledger to its bib by content** - the evidence barrier
  binds a ledger to its bib by NAME only, so a refused cleaning pass must
  delete the stale ledger, and that unlink can fail (a warning, not a block).
  A `bib_sha256` in the ledger (schema 3; the barrier accepts {1, 2} and must
  learn 3) would make a stale ledger unusable however it survived. Raised in
  the 0.5.18 final-design review; no incident yet.
- **Paren-delimited entries** (`@article(k1, ...)`) - pybtex and
  `bib_comments` accept them; dedupe's and the validator's `@type{` header
  grammar does not, so dedupe drops one with only a stderr warning. Either
  reject the form at validation (the researcher spec only shows braces) or
  support it in both. Zero incidence over 335 local bibs.

The service's deploy of re-vendor #15 (the 0.5.18 pin, service `064e658`) is
the service's item, run from that repo.

## Checked and deliberately NOT filed

Not a queue — a register, so these are not re-found. Each was a live candidate
that did not survive reading the file it concerns.

- A machine-readable `year-conflicts.json` from `dedupe_bib`, gating
  `generate_bibliography` until acknowledged (proposed in review, 2026-09-10).
  Seen once; dedupe's `year conflict` stderr line now sits at the cause and
  names both copies, both source bibs and the survivor. A gate would add a
  flag and a file for that one case. Revisit if a run ships a wrong-year
  survivor despite the line - `lint_md`'s late citation failure is the
  symptom that would show it, not a second guard. The line's source
  attribution was also checked: `merge_entries` picks one whole entry and
  copies only `year_suffix`, so origin follows the winner, and a three-copy
  chain whose year-less middle copy wins prints no line rather than a wrong
  one.

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
- The validator's required-field exemption (the DOI-retaining `@article` the
  cleaner deliberately keeps) emits nothing when it fires, so no hook-side
  incidence counter sees it; the service logs `required-fields exemption
  applied` from its SubagentStop hook. Not mirrored: the exempted entry
  already carries `METADATA_CLEANED: journal` in its keywords and the strip
  is in the cleaning ledger, so the delivered bib IS the incidence record —
  grep the marker, not the hook.
- The budget's `Stage 5 verification | 1 per ~6 DOIs` is keyed on DOIs while
  Stage 5's work is keyed on papers, so the DOI-less fallback's calls are
  uncounted — real, but the table is explicitly approximate ("About ten
  calls") and says what it caps ("ceremony"), so it does not carry the risk of
  a skipped mandated call.
