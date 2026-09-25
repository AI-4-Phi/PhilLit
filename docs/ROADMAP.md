# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data (see
`CLAUDE.md`). Shipped work is deleted from this file rather than marked done
— the git log is the history. A decision that is still binding belongs in
`CLAUDE.md` or the module that owns it, never here; an accepted residual
belongs in the function it describes, so that a recurrence is recognized
where it would be read.

## Queue

- **The barrier blesses its own output wholesale, not just its stamps** -
  after writing a stamped bib the barrier re-points the cleaning ledger's
  `bib_sha256` to that text, on the ground that stamping cannot change which
  entries matched an API record. Nothing ENFORCES that. A bug in the stamping
  renderer that altered a key, title, year or author - or dropped an entry -
  would be bound as valid on the spot, and the next run would trust it. The
  guard is an invariant: the output must equal the input under a canonical
  projection that strips the barrier-owned fields (`keywords`
  `EVIDENCE-*`/`year_suffix`/`web_span`/`venue_status`/`same_work_group`/
  `urldate`/`archiveurl`). No incident.
  Note the same projection, used as the BINDING itself, would remove the need
  to re-point at all - weigh that against the narrow guard before building
  either.

- **`EVIDENCE-ABSTRACT` attests sameness, not usability** - the barrier's
  per-source re-fetch hash-matches the bib's abstract against the live
  source, which proves the text was not invented. It cannot see that the
  text is useless. The 2026-09-10 run granted the tier to five unusable
  abstracts - one truncated, one a bare JEL keyword string, two
  bibliographic stubs, one garbled OCR - while `abstract_corroboration`
  reported 127/127 with zero mismatches. A citable tier resting on an
  unreadable abstract is an accuracy defect, which is objective #1.
  Reproduce from the 2026-09-10 artifacts before designing anything; a
  usability screen is a second, separate test from the corroboration hash.

- **The synthesis-planner's role spec overrides the orchestrator on
  citability** - `agents/synthesis-planner.md` declares the `EVIDENCE-*`
  keyword "the single authority on citability"; the orchestrator's Phase 4
  instructions are not documented as yielding to it, and the precedence is
  written down nowhere. Reported from the 2026-09-10 run. Decide which
  document wins and say so in the one that loses. The same "single
  authority" wording also sits in `docs/conventions.md` (tier section) and
  `agents/synthesis-writer.md` (tier table); the fix covers all three.

- **The SubagentStop gate fails open silently when the review cannot be
  resolved** - `hooks/subagent_stop_bib.sh` allows the stop with only a
  stderr WARNING when `workdir.py resolve` answers `{error}`: no pointer, a
  malformed pointer, an in-place pointer to a missing folder, a local review
  whose files are elsewhere or missing, or one whose ownership cannot be
  proven. stderr on exit 0 is never shown, so validation and cleaning are
  skipped silently for that researcher. The barrier later reports the
  missing cleaning ledger as `degraded`, so it is not invisible downstream,
  but the gate-failure policy in CLAUDE.md forbids a silent open on an
  accuracy gate. Configuration errors already fail closed (`ConfigError`,
  exit 1). Decide between a `systemMessage` and a block for the review
  states.

- **Phase 6 moves every root-level `.bib` into the review** - SKILL.md's
  stray-file step runs `find . -maxdepth 1 -name "*.bib" -exec mv`, which
  also takes a user's own bibliography from the workspace root, against
  README's "writes review output only to `./reviews/`". Scope it to the
  names researchers write (`literature-domain-*.bib`, `literature-*.bib`).

- **The permissions guide claims a permission mode plugin agents never
  get** - `docs/permissions-guide.md`'s agent table lists `acceptEdits` for
  all four agents, from their `permissionMode` frontmatter. Claude Code's
  sub-agents docs: plugin subagents ignore `permissionMode` (and `hooks`,
  `mcpServers`). So in the plugin the mode is the session's, and edits pass
  on setup's `Edit(reviews/**)` rule. Keep the frontmatter - phillit-service
  vendors the files as project agents under `engine/.claude/agents/`, where
  it IS honoured - and correct the column to say where it applies.

- **Three doc inventories each have more than one owner** - they drift
  between passes. (1) Environment variables: `.env.example`,
  `check_setup.py`, `skills/setup/SKILL.md` and
  `skills/philosophy-research/SKILL.md` all describe the keys, and CORE has
  already drifted - `check_setup.py` says the key "improves rate limits" and
  `.env.example` "improves CORE full-text discovery", but without it
  `search_core.py` and the CORE abstract fallback skip entirely. Make
  `.env.example` + `check_setup.py` the owners and cut philosophy-research's
  copy to a pointer. (2) The hooks wiring is listed in CLAUDE.md,
  `docs/ARCHITECTURE.md` and `docs/permissions-guide.md`, and needed
  correcting in two consecutive doc passes; make the permissions-guide table
  the wiring owner and cut the others to file names and purpose.

- **Resume after Phase 6 step 1 skips the delivery split** - resume rule 1
  (SKILL.md, Resume) treats the workflow as complete once
  `literature-review-*.md` exists, which step 1 writes, so an interruption
  in steps 2-8 resumes as complete and step 7 never runs; the user gets the
  merged bib alone. The saved
  `intermediate_files/literature-<project>-merged.bib` could serve as the
  completion marker.

- **Researchers are not told the research-notes label rules** -
  `agents/domain-literature-researcher.md` (BibTeX File Structure) never
  says an improvised `LABEL:` line withholds the notes file; the one tagged
  real run withheld it on 20 improvised labels. A one-line instruction
  (extra analysis goes inside an existing section; no new `LABEL:` lines)
  needs a test run.

- **The label grammar cannot admit colon-less headings or
  section-dependent sub-labels** - owner decision needed: domain 6 of the
  real run uses headings after `====` rules with no colon (INSTRUMENT
  COMPARISON TABLE, FAULT LINES (...)), which no list growth can admit;
  FOR/AGAINST/CONTROL sit inside an OUT section in one block and could sit
  inside KEY_POSITIONS in another, which an IN/OUT list cannot express.

- **phillit-service: adopt the off-sync working directory at the next pin** -
  PhilLit 0.5.30 moves review work to `~/.local/state/phillit/reviews/` and
  publishes into `reviews/<name>/` at the end. The service must set
  `PHILLIT_WORKDIR=inplace` in its worker environment (and never write
  another value into a workspace `.env`), and its byte-exact
  `_substitute_review_prose` rewrites will fail loudly at re-vendor on the
  reworded researcher and SKILL sentences, including the new
  `existing_review` guard: map `[workdir]` to `reviews/<id>`. In-place
  `init` accepts the `reviews/<id>/` the service pre-creates.

phillit-service is deployed at 0.5.25 (engine at `da48b2c`) and owes a
re-vendor of 0.5.29: 0.5.26's ledger content binding, 0.5.27's prompt fixes
(current-year search bounds, the synthesis writer's note rule), 0.5.28's
review-length rule and enrichment-ledger constant, and 0.5.29's three-file
delivery. It runs from that repo, and its roadmap does not queue it yet.
Tell the operator that the binding FLOOR reports `degraded` for a review
whose researchers ran before the pin and whose barrier runs after, until a
researcher re-runs - fail-closed and intended, but not obvious in production.
The re-vendor script syncs the engine tree and its deletions, but three of
the service's OWN files are not vendored and need a manual follow-up pass:
its public share list (`pages/routes.py`) will publish the track record -
which now carries every verdict token - by the plain `.bib` suffix, while
`research-notes-*.md` will not surface there at all; its `hooks.py`
validation glob will pick up both bibs; and `docs/engine-provenance.md`
still names `sanitize_bib.py`, which this repo deleted.

## Checked and deliberately NOT filed

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
