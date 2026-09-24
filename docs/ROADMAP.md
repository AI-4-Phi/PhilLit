# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data (see
`CLAUDE.md`). Shipped work is deleted from this file rather than marked done
— the git log is the history. A decision that is still binding belongs in
`CLAUDE.md` or the module that owns it, never here; an accepted residual
belongs in the function it describes, so that a recurrence is recognized
where it would be read.

## Queue

- **Split the delivery into three files, one per purpose** - the delivered
  `literature-<project>.bib` mixes three audiences: the researchers' `note`
  fields, their `FLn.n` fault-line tags and `High`/`Medium`/`Low` triage in
  `keywords`, the engine's derived fields, and the per-domain `@comment`
  research notes, while `sanitize_bib.py` strips the `EVIDENCE-*` tiers - the
  one verdict an auditor most needs. DECIDED - each file has one purpose, and
  SKILL.md's deliverable list and README must state it:
  - `literature-<project>.bib` - the TRACK RECORD: accountability,
    transparency and reproducibility. It shows the verdict each agent reached
    on each entry: the `EVIDENCE-*` tier, the `High`/`Medium`/`Low` rating,
    the `FLn.n` tags, the workflow markers, the `METADATA_CLEANED` markers
    and all eight engine-derived fields. No `note`, no `@comment`.
  - `literature-<project>-annotated.bib` - the ZOTERO IMPORT. Standard
    fields, topical keywords and the reading notes, `FLn.n` substituted.
    Zotero's BibTeX importer (`BibTeX.js` in zotero/translators) turns `note`
    into a child note and every `keywords` item into a tag, maps `urldate` to
    Accessed, and silently drops fields it has no mapping for - so every
    verdict token must be stripped from this file's `keywords`, or it becomes
    a Zotero tag.
  - `research-notes-<project>.md` - the per-domain analysis from today's
    `@comment` blocks, for a human reader.
  Weighed and rejected: a clean "import-ready" bib for Zotero with the notes
  and engine fields in the annotated one (it discarded the verdicts from
  every file, and put Zotero on the file with no notes).
  Nothing here is still open: the item is ready to build.
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
    DECIDED: SUBSTITUTE, do not delete. Each `FLn.n`
    is replaced by the short question the review plan defines it as
    (`intermediate_files/lit-review-plan.md`, e.g. FL1.1 -> `the "one
    principle or three?" fault line`). All 31 tags in the 2026-09-10 run were
    defined there. The planner emits no fault lines of its own - tags appear
    only when the user's prompt asks for them (no plan or bib in the 45
    reviews under `reviews/` carries one; the 2026-09-10 run, which lives
    outside the repo, is the one tagged run known) - so with no tags the
    substitution is a no-op, and the FAIL LOUDLY path is what a tagged run
    exercises. This is pure string substitution with no model in the loop, so
    no researcher claim can be paraphrased away, and the note becomes
    readable to someone who never saw the plan. It must FAIL LOUDLY
    on a tag the plan does not define rather than leave a bare token - the
    plan is per-review and an undefined tag means the two have drifted.
    Weighed and rejected: leaving the tags (a reader meets an undefined token
    130 times), an LLM rewrite of the 130 sentences (130 unverifiable edits
    to evaluative claims), and dropping whole sentences (guts RELEVANCE).
  - WHICH SECTIONS SURVIVE - DECIDED: ALL FOUR.
    `CORE ARGUMENT` (131, 68 KB), `RELEVANCE` (131, 60 KB), `POSITION` (131,
    14.8 KB - a one-line classification of where the work sits in the debate)
    and the provenance blocks (14, 2.8 KB - why a record is missing a journal
    or took its year from a secondary source). The provenance blocks keep
    their three INCONSISTENT labels (`METADATA NOTE`, `NOTE ON METADATA`,
    `BIBLIOGRAPHIC NOTE`): unifying them under one reader-facing heading was
    offered and declined, so a normalizer must not "tidy" them. 12 of the 14
    name an engine tool or API in their prose, and that is accepted - the
    information is the point.
  - THE `keywords` FIELD in the ANNOTATED (Zotero) bib - DECIDED: keep the
    topical keywords (261 distinct, 508 occurrences); strip the `EVIDENCE-*`
    tier, the `FLn.n` tags (145), the `High`/`Medium`/`Low` ratings (131 -
    and 95 of them are `High`, so the field barely discriminates), the
    `METADATA_CLEANED` marker and the workflow markers `AI-RELEVANT` (7),
    `ROUTING-DISPUTE` (1) and `NO-DOI` (2). The TRACK-RECORD bib keeps all of
    them; `INCOMPLETE`/`no-abstract` leave both, as today.
    STRIP THE MARKERS BY NAME, NEVER BY SHAPE. The markers are ALL-CAPS, but
    so are real dataset and method names the measurement literature uses as
    keywords - `XCONST`, `POLCON`, `DPI`, `CHECKS`, `CCP`, `IRT`, `UDS`,
    `QCA` all appear and all must survive. A `[A-Z][A-Z0-9-]{2,}` rule would
    delete content. Any new marker must be added to the named list.
  - THE `@comment` BLOCKS - DECIDED: they leave the
    bibliography entirely. The seven blocks are 124 KB of per-domain research
    notes - prose documents that are not BibTeX entries at all - and they go
    to a THIRD deliverable, `research-notes-<project>.md`, alongside the
    review. Neither .bib keeps them. Telemetry is omitted from the new file.
    So the delivery is three files, not two.
    Note `dedupe_bib` currently CARRIES these blocks forward by design
    (`bib_comments.is_verbatim_block`), so this changes what Phase 6 does
    with them, not just what sanitize strips - and the carry logic must keep
    working for any OTHER `@comment` a bib holds.
    WHICH LABELS REACH THE NOTES FILE - DECIDED. It is
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
  - THE ENGINE-DERIVED FIELDS - DECIDED, and this IS the "new owner
    decision" `sanitize_bib.py`'s docstring requires before any field
    stripping: `abstract_source` (117), `web_span` (3), `urldate` (3),
    `same_work_group` (3), `venue_status` (2), `sep_context` (1), and
    `year_suffix` and `archiveurl` (engine-derived like the rest, absent from
    that run) - all eight `sanitize_bib.py` names. The TRACK-RECORD bib keeps
    them; the ANNOTATED bib strips them (Zotero would drop them regardless).
  - WRITER-DIRECTED SENTENCES inside a kept section (10 of the 131
    `RELEVANCE` blocks say things like "Cite one or the other, not both, in
    the final review") are NOT removed. Settled by the same-day precedent on
    `NOTABLE_GAPS`: the rule is a LABEL list, never a sentence-level edit.
    Do not re-raise this as a separate cleanup.
  - The split runs where `sanitize_bib` runs today: AFTER
    `generate_bibliography` and `check_evidence`, both of which read
    `year_suffix` for the Chicago a/b labels. Stripping it any earlier breaks
    the review's citations. `sanitize_bib`'s `EVIDENCE-*` strip moves from the
    track-record bib to the annotated one.
  - Give the rewritten `sanitize_bib` a real CLI: today it reads
    `sys.argv[1]` bare, so `--help` (or a wrong path) is a traceback.
  - SKILL.md's Phase 6 safety-net glob (`literature-*.bib`) already keeps a
    `-annotated` sibling at the top level. That becomes intentional under
    this spec; do not "fix" it back.
  - The spec touches SKILL.md's deliverable list and tree diagram, README's
    Highlights and Output Structure (each file's PURPOSE, as above), the
    Phase 6 sweep, and `sanitize_bib.py`'s docstring and behaviour. All of it
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

- **The SubagentStop gate fails open silently on a bad review pointer** -
  `hooks/subagent_stop_bib.sh` allows the stop with only a stderr WARNING
  when `reviews/.active-review` is missing, malformed, or names a missing
  directory, and stderr on exit 0 is never shown. Validation and cleaning
  are then skipped for that researcher. The barrier later reports the
  missing cleaning ledger as `degraded`, so it is not invisible downstream,
  but the gate-failure policy in CLAUDE.md forbids a silent open on an
  accuracy gate. Decide between a `systemMessage` and a block.

- **Phase 6 moves every root-level `.bib` into the review** - SKILL.md's
  stray-file step runs `find . -maxdepth 1 -name "*.bib" -exec mv`, which
  also takes a user's own bibliography from the workspace root, against
  README's "writes review output only to `./reviews/`". Scope it to the
  names researchers write (`literature-domain-*.bib`, `literature-*.bib`).

- **The enrichment ledger's version is a literal, not the shared
  constant** - `enrich_bibliography.py` writes `"schema_version": 1` while
  the barrier accepts `ENRICHMENT_SCHEMA_VERSION` from `ledger_binding.py`.
  Bumping the producer alone would refuse every enrichment ledger, and no
  test ties the two. Import the constant, as the cleaner does.

- **Delivered reviews run about twice the planner's length target** - the
  synthesis planner (and SKILL.md's Phase 4 text) targets 3000-4000 words;
  SKILL.md's Success Metrics say 3000-8000. Measured over the 43 delivered
  reviews under `reviews/` (body only, frontmatter and References excluded):
  min 4,407, p25 5,672, median 7,073, p75 8,164, max 14,247 - not one met
  the planner's range. Decide the intended length, then align the planner's
  total and per-section targets, the Phase 4 line and the success metric.

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

phillit-service is deployed at 0.5.25 (engine at `da48b2c`) and owes a
re-vendor of 0.5.27: 0.5.26's ledger content binding, plus 0.5.27's prompt
fixes (current-year search bounds, the synthesis writer's note rule). It
runs from that repo, and its roadmap does not queue it yet.
Tell the operator that the binding FLOOR reports `degraded` for a review
whose researchers ran before the pin and whose barrier runs after, until a
researcher re-runs - fail-closed and intended, but not obvious in production.

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
