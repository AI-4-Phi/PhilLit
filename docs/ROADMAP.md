# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

- **Split bibliography delivery into a clean primary and an annotated
  sibling** - the delivered `literature-<project>.bib` ships the researchers'
  `note` fields, their `FLn.n` fault-line tags and `High`/`Medium`/`Low`
  triage in `keywords`, `abstract_source`, and the per-domain `@comment`
  search logs. `sanitize_bib.py` strips only `EVIDENCE-*` tokens from
  `keywords`, by its own docstring, so all of that reaches a file the user
  imports into Zotero. Owner decision (Johannes, 2026-09-15): the reading
  notes are worth delivering, the engine's tags are not. Ship two files - a
  clean import-ready `literature-<project>.bib` and a
  `literature-<project>-annotated.bib` carrying the notes.
  Constraints any implementation must respect:
  - Researchers emit BOTH `note = {...}` and `note = "..."`. In the
    2026-09-10 run the split was 115 braced / 16 quoted, and a brace-only
    strip left those 16 behind. Locate and remove fields with
    `bib_fields.iter_fields` / `remove_field`, never a new regex.
  - `FLn.n` tags appear in note PROSE, not only in `keywords`: 111 of 131
    notes carried one, over 130 sentences. They are grammatically EMBEDDED,
    not appended - "the thesis on which FL1.1 turns", "the direct statement
    of FL6.2" - so deleting the token breaks the sentence; only 9 of the 130
    are bare lists that would cut cleanly.
    DECIDED (Johannes, 2026-09-15): SUBSTITUTE, do not delete. Each `FLn.n`
    is replaced by the short question the review plan defines it as
    (`intermediate_files/lit-review-plan.md`, e.g. FL1.1 -> `the "one
    principle or three?" fault line`). All 31 tags in the 2026-09-10 run were
    defined there. This is pure string substitution with no model in the
    loop, so no researcher claim can be paraphrased away, and the note
    becomes readable to someone who never saw the plan. It must FAIL LOUDLY
    on a tag the plan does not define rather than leave a bare token - the
    plan is per-review and an undefined tag means the two have drifted.
    Weighed and rejected: leaving the tags (a reader meets an undefined token
    130 times), an LLM rewrite of the 130 sentences (130 unverifiable edits
    to evaluative claims), and dropping whole sentences (guts RELEVANCE).
  - WHICH SECTIONS SURVIVE - DECIDED (Johannes, 2026-09-15): ALL FOUR.
    `CORE ARGUMENT` (131, 68 KB), `RELEVANCE` (131, 60 KB), `POSITION` (131,
    14.8 KB - a one-line classification of where the work sits in the debate)
    and the provenance blocks (14, 2.8 KB - why a record is missing a journal
    or took its year from a secondary source). The provenance blocks keep
    their three INCONSISTENT labels (`METADATA NOTE`, `NOTE ON METADATA`,
    `BIBLIOGRAPHIC NOTE`): unifying them under one reader-facing heading was
    offered and declined, so a normalizer must not "tidy" them. 12 of the 14
    name an engine tool or API in their prose, and that is accepted - the
    information is the point.
  - THE `keywords` FIELD - DECIDED (Johannes, 2026-09-15): keep the topical
    keywords (261 distinct, 508 occurrences); strip the `FLn.n` tags (145),
    the `High`/`Medium`/`Low` ratings (131 - and 95 of them are `High`, so
    the field barely discriminates) and the workflow markers `AI-RELEVANT`
    (7), `ROUTING-DISPUTE` (1) and `NO-DOI` (2).
    STRIP THE MARKERS BY NAME, NEVER BY SHAPE. The markers are ALL-CAPS, but
    so are real dataset and method names the measurement literature uses as
    keywords - `XCONST`, `POLCON`, `DPI`, `CHECKS`, `CCP`, `IRT`, `UDS`,
    `QCA` all appear and all must survive. A `[A-Z][A-Z0-9-]{2,}` rule would
    delete content. Any new marker must be added to the named list.
  - THE `@comment` BLOCKS - DECIDED (Johannes, 2026-09-15): they leave the
    bibliography entirely. The seven blocks are 124 KB of per-domain research
    notes - prose documents that are not BibTeX entries at all - and they go
    to a THIRD deliverable, `research-notes-<project>.md`, alongside the
    review. Neither .bib keeps them. Telemetry is omitted from the new file.
    So the delivery is three files, not two: clean `.bib`, `-annotated.bib`,
    and `research-notes-<project>.md`.
    Note `dedupe_bib` currently CARRIES these blocks forward by design
    (`bib_comments.is_verbatim_block`), so this changes what Phase 6 does
    with them, not just what sanitize strips - and the carry logic must keep
    working for any OTHER `@comment` a bib holds.
    WHICH LABELS REACH THE NOTES FILE - DECIDED (Johannes, 2026-09-15). It is
    a LABEL list, never a sentence-level edit; sentence-level cleaning of
    `NOTABLE_GAPS` was offered and declined, so run-mechanics prose inside a
    kept section stays.
    IN:  `DOMAIN_OVERVIEW`, `KEY_POSITIONS`, `NOTABLE_GAPS`,
         `SYNTHESIS_GUIDANCE`, `RELEVANCE_TO_PROJECT` (94.9 KB of 124).
         `NOTABLE_GAPS` keeps its "Stage 4: 45 candidates inspected" lines -
         what was searched for and not found is itself a finding.
         `SYNTHESIS_GUIDANCE` keeps its imperative voice ("Do not present
         FL1.1 as...") - the analysis is worth more than the register.
    OUT: `DOMAIN`, `SEARCH_DATE`, `PAPERS_FOUND`, `SEARCH_SOURCES`,
         `RETRIEVAL_FAILURES`, `FAULT_LINES_POPULATED`, `ABSTRACTS`,
         `ROUTING NOTES`, and the `====` rules.
    An UNRECOGNISED label must fail loudly rather than be guessed either way
    - the 2026-09-10 run also carried one-off labels (`SCOPE NOTE`,
    `ADJUDICATION ATTEMPT`, `NOTE ON ATTRIBUTION`, `COUNT NOTE`, `AGAINST`,
    `CONTROL`, `ROUTING`), so the list is not closed and a silent default
    would either leak telemetry or drop analysis.
  - SKILL.md's Phase 6 safety-net glob (`literature-*.bib`) already keeps a
    `-annotated` sibling at the top level. That becomes intentional under
    this spec; do not "fix" it back.
  - The spec touches SKILL.md's deliverable list and tree diagram, the
    Phase 6 sweep, and `sanitize_bib.py`'s recorded keep-decision. All of it
    is vendored downstream, so it is a design item, not a one-liner.

- **The barrier blesses its own output wholesale, not just its stamps** -
  after writing a stamped bib the barrier re-points the cleaning ledger's
  `bib_sha256` to that text, on the ground that stamping cannot change which
  entries matched an API record. Nothing ENFORCES that. A bug in the stamping
  renderer that altered a key, title, year or author - or dropped an entry -
  would be bound as valid on the spot, and the next run would trust it. The
  guard is an invariant: the output must equal the input under a canonical
  projection that strips the barrier-owned fields (`keywords`
  `EVIDENCE-*`/`year_suffix`/`web_span`/`venue_status`/`same_work_group`/
  `urldate`/`archiveurl`). Raised in the 0.5.26 round-2 review; no incident.
  Note the same projection, used as the BINDING itself, would remove the need
  to re-point at all - see `docs/ideas/` before building the narrow version.

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
  document wins and say so in the one that loses.

The deploy of 0.5.25 (phillit-service engine at `da48b2c`, re-vendor #23) is
the service's item, run from that repo.

## Checked and deliberately NOT filed

Not a queue — a register, so these are not re-found. Each was a live candidate
that did not survive reading the file it concerns.

- A lock protocol between the cleaner and the barrier (round-2 review,
  2026-09-15). Both write the same workspace, and a concurrent writer could
  in principle swap a cleaning ledger between the barrier accepting it and
  re-pointing it. Not filed: the workspace is single-writer by design - the
  cleaner runs from one SubagentStop hook, the barrier once at the Phase 3-4
  boundary - and a real fix needs a lock both participate in, which is a
  larger change than the exposure warrants. The cheap half is already done:
  the re-point binds the text the barrier AUTHORED, so the bib cannot be
  swapped under it. Revisit if the service ever runs domains concurrently.
- Normalizing BOM or NFC/NFD before hashing (round-2 review, 2026-09-15).
  Both reviewers agreed it is noise here and one argued against it
  outright: every writer in the pipeline is Python, `utf-8` neither emits a
  BOM nor normalizes, and an external tool that changes either HAS edited
  the file - invalidating the ledger is the conservative, correct answer.
  Folding them would deliberately make some real edits invisible.
- Forcing pybtex's writer encoding (round-1 and round-2 reviews). Two
  reviewers predicted a Windows outage: a cp1252 write of a diacritic bib
  would make the read-back raise, null the hash and refuse every ledger. It
  cannot happen - `write_bibtex` renders through an in-memory `StringIO` and
  does its own `os.fdopen(fd, "w", encoding="utf-8")`, so pybtex never
  reaches the filesystem. Verified by mutation: switching that one encoding
  to cp1252 does fail the round-trip test, which is why the test exists.
- `write_bibtex` hardening beyond the descriptor write (the service's 0.5.19
  pin review, 2026-09-10): logging a failed cleanup unlink, treating the
  `exists()`/`stat()` mode copy as a race, and `os.fchmod`. The cleaner runs
  as the single writer of a per-review workspace; a stale `.tmp` after a
  failed write is visible in the directory and the failure itself reaches the
  agent as the cleaner's `Rewrite failed` error; `os.fchmod` is Unix-only and
  Windows must work.
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
