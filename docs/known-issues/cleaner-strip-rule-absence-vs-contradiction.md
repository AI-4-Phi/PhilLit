# The cleaner strips true detail fields on absent evidence; the breaker contains it on a quarter of bibs

**Status:** Open. Owned by ROADMAP item 14, the cleaner strip-rule fix.
Transferred from phillit-service 2026-08-25 (its
`cleaner-circuit-breaker-trip-rate.md`; its retired roadmap item 23), where
it was filed as a circuit-breaker trip-rate problem. The measurements below
(2026-08-25) reframe it: the breaker is the containment, not the defect.
Design reviewed 2026-08-25 by gpt-5.6-sol, kimi-k3 and glm-5.3 (two rounds;
approve-with-changes, all changes folded in below).

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
  own first-page truncation (`303`). Pages contradiction must require a
  differing FIRST page.
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
  contradiction: pages contradict only on a differing first page;
  publisher and number/volume compare exact after normalization, with
  publisher tolerating containment either way (`Springer` /
  `Springer International Publishing`). The global-bucket coincidence
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

## Gates

1. `cleaner_corpus_dryrun.py` before/after with every delta explained —
   the 2026-08-25 baseline is captured (session scratchpad; numbers above).
2. CrossRef spot-check of post-change planned strips, INCLUDING the
   venue-absence cell (the one cell the 2026-08-25 truth anchor did not
   sample).
3. Full test suite; mutation-proof tests for the three-way comparator per
   field class, the identity-verified guard, and the schema bump.
