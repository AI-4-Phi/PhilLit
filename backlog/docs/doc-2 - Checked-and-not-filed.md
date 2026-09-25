---
id: doc-2
title: Checked and not filed
type: other
created_date: '2026-09-25 19:18'
updated_date: '2026-09-25 19:18'
---
Not a queue — a register, so these are not re-found. Each was a live candidate
that did not survive reading the file it concerns.

- A lock protocol between the cleaner and the barrier. Both write the same
  workspace, and a concurrent writer could in principle swap a cleaning ledger
  between the barrier accepting it and re-pointing it. Not filed: the
  workspace is single-writer by design - the cleaner runs from one
  SubagentStop hook, the barrier once at the Phase 3-4 boundary - and a real
  fix needs a lock both participate in, which is a larger change than the
  exposure warrants. The cheap half is already done: the re-point binds the
  text the barrier AUTHORED, so the bib cannot be swapped under it. Revisit if
  the service ever runs domains concurrently.
- Normalizing BOM or NFC/NFD before hashing. It is noise here: every writer in
  the pipeline is Python, `utf-8` neither emits a BOM nor normalizes, and an
  external tool that changes either HAS edited the file - invalidating the
  ledger is the conservative, correct answer. Folding them would deliberately
  make some real edits invisible.
- Forcing pybtex's writer encoding to prevent a predicted Windows outage: a
  cp1252 write of a diacritic bib would make the read-back raise, null the
  hash and refuse every ledger. It cannot happen - `write_bibtex` renders
  through an in-memory `StringIO` and does its own `os.fdopen(fd, "w",
  encoding="utf-8")`, so pybtex never reaches the filesystem. Verified by
  mutation: switching that one encoding to cp1252 does fail the round-trip
  test, which is why the test exists.
- `write_bibtex` hardening beyond the descriptor write: logging a failed
  cleanup unlink, treating the `exists()`/`stat()` mode copy as a race, and
  `os.fchmod`. The cleaner runs as the single writer of a per-review
  workspace; a stale `.tmp` after a failed write is visible in the directory
  and the failure itself reaches the agent as the cleaner's `Rewrite failed`
  error; `os.fchmod` is Unix-only and Windows must work.
- A machine-readable `year-conflicts.json` from `dedupe_bib`, gating
  `generate_bibliography` until acknowledged. Seen once; dedupe's `year
  conflict` stderr line now sits at the cause and names both copies, both
  source bibs and the survivor. A gate would add a flag and a file for that
  one case. Revisit if a run ships a wrong-year survivor despite the line -
  `lint_md`'s late citation failure is the symptom that would show it, not a
  second guard. The line's source attribution was also checked:
  `merge_entries` picks one whole entry and copies only `year_suffix`, so
  origin follows the winner, and a three-copy chain whose year-less middle
  copy wins prints no line rather than a wrong one.

- The budget's `Stage 5.5 enrichment | 1 (2 if you added entries after it)`
  does NOT contradict "the bib file is FROZEN after enrichment" — FROZEN's own
  bullet sanctions "adding a missed entry" by surgical `Edit`. It reads as a
  contradiction, which is a readability datum rather than a defect, and worth
  knowing given the audience is a model.
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

- `skills/philosophy-research/SKILL.md`'s "Do NOT use WebFetch for ... Paper
  abstracts: use `s2_search.py` or `s2_batch.py`" does not conflict with
  `enrich_bibliography.py` being the sole author of `abstract` fields: it is
  a WebFetch prohibition for reading abstracts during selection, and the
  researcher's own "never write `abstract` yourself" rule governs the bib.
- `lint_md.py --help` prints pymarkdown's help rather than its own. Harmless:
  the script is only ever invoked by Phase 6 with fixed arguments.
- CLAUDE.md's Permissions section repeats facts from
  `docs/permissions-guide.md` (evaluation order, Edit covering Write). It is
  kept: CLAUDE.md states them as the imperatives a developer session must
  obey, the guide as explanation.
