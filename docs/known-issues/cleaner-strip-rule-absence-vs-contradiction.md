# The cleaner strips true detail fields on absent evidence; the breaker contains it on a quarter of bibs

**Status:** FIXED 2026-08-25, shipped in plugin v0.5.0 — `5bc1421` (the
`venue_key` `&`↔`and` fold), `7344008` (the barrier accepts cleaning-ledger
schema_version 2), `2519b62`/`3515c30`/`b667c1f` (the three-way strip
policy, agent-prose alignment, and the pages/publisher comparison
hardening); gate results below. The shipped ledger telemetry: per-entry
`unverified_fields` and `venue_stripped_no_evidence` keys, schema_version
2. Transferred from phillit-service the same morning (its
`cleaner-circuit-breaker-trip-rate.md`; its retired roadmap item 23), where
it was filed as a circuit-breaker trip-rate problem — the measurements
below reframed it: the breaker is the containment, not the defect. Design
reviewed 2026-08-25 by gpt-5.6-sol, kimi-k3 and glm-5.3 (two rounds;
approve-with-changes, all changes folded in).

## Measurements (2026-08-25, current engine)

`hooks/metadata_cleaner.py` at PhilLit HEAD (v0.4.9) is byte-identical to
the service's vendored copy at pin `5495839` (v0.4.8), so these numbers
describe both repos. Dry-run over the 46-review local corpus via the
service's committed gate tool `tools/cleaner_corpus_dryrun.py` (writes
stubbed and asserted, corpus digest verified unchanged):

| | 2026-08-02 | 2026-08-25 |
|---|---|---|
| bibs with a usable index | 319 | 321 |
| breaker tripped | 86 (27%) | **81 (25.2%)** |
| field removals withheld by the breaker | 1,479 | 1,338 |
| field removals performed elsewhere | 1,180 | 1,243 |

**Three-way classification of every planned strip** against the entry's own
matched record (313 bibs the classifier could process; the 8 skipped
contributed zero strips — totals reconcile exactly with the dry-run's
1,338 + 1,243 = 2,581):

| field | CONTRADICT | NO-EVIDENCE |
|---|---|---|
| pages | 105 | 859 |
| number | 20 | 698 |
| publisher | 18 | 298 |
| volume | 13 | 145 |
| journal | 174 | 51 |
| booktitle | 73 | 47 |
| doi | 65 | 15 |

**80% of all planned strips are absence-driven**, concentrated in the
detail fields search-API records rarely carry.

**Truth anchor** (sampled, selection-limited: tripped stratum from the 5
most-affected reviews, untripped control n=12, DOI-bearing entries only —
directional evidence, not corpus rates): 36 strips hand-checked against
CrossRef. A clear majority of absence-driven detail strips were TRUE values
(issue numbers, page ranges, `publisher = Oxford University Press` on
*Supersizing the Mind*; a resolving book DOI). The adjudicated
truth-by-state join that shaped the fix:

- **fruh2019climate, pamuk2020risk** — fabricated pages+issue on real
  papers: NO-EVIDENCE (their matched records carry no pages/issue). Only
  absence-stripping can catch them; see the accepted residual below.
  Today's breaker also keeps them (their bib trips).
- **farina2021extended** — fabricated `booktitle` (the chapter's DOI
  resolves to a different book): NO-EVIDENCE, but booktitle is venue-class
  and still strips.
- **mhlambi2023decolonizing** — wrong pages: CONTRADICT from a DOI-matched
  record; still strips.
- **bogen1988saving** — TRUE pages `303--352`: CONTRADICT via CrossRef's
  own first-page truncation (`303`). Pages contradiction must tolerate a
  differing TAIL against a truncated record value (bounded to exactly that
  shape below — an equal first page across two full ranges still
  contradicts).
- **grant2009typology** — TRUE journal: CONTRADICT via a normalizer gap —
  `normalize_journal` decodes `\&`/`&amp;` but nothing folds `&` against
  the word `and` (`Health Information & Libraries Journal` vs
  `... and ...`). Fix: a word-boundary token fold in `venue_key` (the
  deliberately loose VERIFICATION key — never in dedup identity).
- **jamieson2014reason** — TRUE, resolving DOI: CONTRADICT via a
  wrong-artifact match (a title+year match to a Choice-review record of
  the same book, whose DOI legitimately differs). Contradictions from
  title+year-matched broad records are not identity-verified evidence.

## Diagnosis

`plan_entry_cleaning` keeps a cleanable field iff it matches the entry's
own matched API record (`_field_matches_api` — two-valued, so
absent-from-record and contradicted-by-record both read False) or the raw
value appears anywhere in the index (`is_field_verifiable` — coincidence
corroboration for short values like `number = 6`, powerless for page
ranges). Search-API records rarely carry pages/issue/publisher, so on
matched, correct entries those fields are stripped for lack of evidence.
On small domain bibs the planned mass strip trips the breaker (>=5
strip-planned entries and >30%), which withholds ALL cleaning — including
genuine hallucination removals and year corrections. On the ~75% of bibs
below threshold the same rule runs unguarded. Both readings of the service
file's old §3 were right at once: the brake is correct, and the thing it
contains is the strip rule's conflation of "no evidence" with
"contradicted".

## Fix design (item 14)

Three-valued comparison against the entry's own matched record
(MATCH / CONTRADICT / NO-EVIDENCE):

- **Detail fields** (`pages`, `number`, `volume`, `publisher`): strip only
  on CONTRADICT **from an identity-verified record** — entry-scoped, or
  matched by DOI; a title+year-matched broad record can never strip (the
  jamieson wrong-artifact hazard generalized: a review/whole-book record
  carries its own pages). Comparison hardening so CONTRADICT means
  contradiction: pages contradict on a differing first page (and a
  punctuation-only record value like `" - "` — S2's empty-pages shape — is
  no-evidence, never a contradiction); publisher and number/volume compare
  exact after normalization, with publisher tolerating word-prefix
  containment either way (`Springer` / `Springer International Publishing`
  match; a bare generic token like `Press` inside `Oxford University
  Press` does not). **Both tolerances were bounded by the external review
  of 2026-08-25**, which found each over-matching: the first-page tolerance
  now applies only when a side IS a bare first page, so two full ranges
  sharing a first page (`100--999` vs `100--101`) contradict; and a prefix
  must stop at a word boundary or be multi-token, so `O` no longer verifies
  `Oxford University Press` (which had also bought EVIDENCE-EXISTENCE on
  the identifier "o"). The global-bucket coincidence
  check is REMOVED from these fields' decision entirely (today it can keep
  a contradicted value via an unrelated paper's matching issue number).
- **Venue fields** (`journal`, `booktitle`): policy unchanged (absence
  still strips — claim-bearing; the observed ICLR-class exploit; farina's
  fabricated booktitle stays caught), plus the word-boundary `&`↔`and`
  token fold in `venue_key` with a corpus check for false merges AND false
  splits. Broader venue-comparison hardening (abbreviations, article
  prefixes) is a recorded follow-up, not built: one measured case existed
  and the fold fixes it; unmeasured folds are against `venue_key`'s
  measured-bounds doctrine.
- **`doi`**: strip only on CONTRADICT from an entry-scoped record.
  Documented residual: a fabricated DOI on a never-verified entry survives
  cleaning. Live resolution inside the cleaner was considered and rejected
  (the cleaner is an offline SubagentStop hook by design; the
  architecture's CrossRef surface is the researcher's entry-scoped verify
  records).
- **Telemetry** (ledger-only; owner-facing measurement, NOT a control —
  the ledger is agent-writable, so nothing downstream may gate on it):
  kept no-evidence detail fields recorded per entry as
  `unverified_fields`; venue fields stripped on NO-EVIDENCE recorded as
  `venue_stripped_no_evidence`. Requires the cleaning-ledger
  `schema_version` 1→2 bump, landed in cleaner AND barrier together (the
  recorded 2026-08-18 decision). Read-compatibility: the barrier accepts
  {1, 2}; a v1 ledger reads as "no telemetry keys"; other values still
  hard-reject.
- **Year path untouched** — year has its own validated two-licence +
  direction-bound machinery (Option C; the wrong-years audit closed it).
- **Breaker unchanged.** Projected trips under the new policy: 81 → ~2 of
  313 (mass-contradiction bibs — the systemic-failure case the breaker
  exists for). Do not tune the constants.

**Accepted residual (reviewed, named):** fabricated detail values with
no-evidence records — the fruh/pamuk class — are KEPT. Accuracy-first
favors this: the alternative deletes ~2,000 absence-driven strips the
truth anchor says are majority-true, and today's breaker ships the
fruh/pamuk values anyway. Shrink paths recorded: (1) periodic CrossRef
spot-check of the ledger's `unverified_fields` population (the 2026-08-25
checker script is the pattern); (2) measuring and raising entry-scoped
verify coverage, which converts NO-EVIDENCE into MATCH/CONTRADICT
structurally.

## Gates — RAN 2026-08-25, post-change (branch `item14-15-engine-fixes`)

1. **Corpus dry-run before/after** (writes stubbed, corpus digest verified
   unchanged both runs): breaker trips **81 → 2** (0.6%; the two are
   genuine mass-strip bibs, the systemic case the breaker exists for);
   removals withheld 1,338 → 12; removals performed 1,243 → 515;
   planned-strip entries 1,929 → 498; applied demotions 262 → 231. Year
   path provably untouched (`years_corrected` 0→0, `years_declined`
   364→364); matching identical (matched/unmatched counts unchanged).
   Every delta class is the policy.
2. **Venue-cell CrossRef spot-check** (15 post-change venue strips from
   formerly-tripped bibs: 10 absence-cell + 5 contradiction; 12
   CrossRef-adjudicable): ~9 destroy TRUE venue data — conference and
   handbook containers the index never carried, plus two checker
   normalization artifacts re-adjudicated by hand — while 3 catch genuine
   chapter-DOI/container mismatches (a bib naming a different book than
   its DOI resolves to), the exploit class the venue policy exists to
   strip. The venue policy stands as reviewed; this measurement is the
   motivation record for the venue follow-up below.
3. Full suite green at every task gate (1,969 at the cleaner-policy
   completion); mutation-proof tests per field class, the
   identity-verified guard, and the schema bump (14 mutations run across
   the rounds, all killed or proven-unkillable-and-documented).

## Residuals recorded at the gate (all deliberate, none silent)

- **Venue-hardening follow-up (strengthened by gate 2):** venue-absence
  strips are majority-true-data where the index lacks conference/handbook
  containers; candidate remedies to MEASURE first — citation-form folds
  beyond `&`↔`and` (`Proceedings of the Nth X` vs `YYYY Nth X (ACRO)`),
  and index venue coverage (S2 conference records often carry no
  container).
- Letter-prefixed page ranges (`S1--S9`) against a truncated record
  (`S1`) still read as a contradiction — the first-page tolerance is
  digit-run-based. Bogen-shaped, rarer; unmeasured.
- `entry_scoped` includes single-result title-lookup verify records, so
  the identity-verified guard is not strictly same-work in that corner
  (pre-existing class — the year gate keys on `entry_scoped` the same
  way).
- On a breaker trip the ledger telemetry records the PLAN under
  applied-sounding key names (`breaker_tripped: true` sits in the same
  payload).
