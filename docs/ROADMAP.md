# PhilLit Roadmap

Open engineering work, in rough priority order. Detailed problem write-ups
live in `docs/known-issues/` (one file per issue; each carries a Status
line); forward-looking design sketches live in `docs/ideas/`. This file
exists so open work has a single place to be listed — it was created
2026-07-24 alongside the bib-pipeline item below.

## 1. Evidence-tier citability — replace the INCOMPLETE exclusion (BUILT + A/B'd HERE, unmerged; dual-repo)

> **Status 2026-08-02 (post-merge; supersedes all earlier figures) — read
> this before starting anything.** The build is DONE on branch
> **`worktree-evidence-tier`** (worktree at `.claude/worktrees/evidence-tier`,
> tip **`9842f2d`** = catch-up merge of `main` + Option C, unmerged into
> `main` and unpushed). All 11 plan tasks executed; **unit suite 1192 green**
> (2026-08-02, post-merge). The free Sonnet two-arm A/B has run ("What are
> data?"), and Johannes adjudicated **three of the four rubric items** on
> 2026-07-28. Provisional outcome cell: **"Works. Proceed."**
>
> **DIVERGENCE RESOLVED 2026-08-02 — catch-up merge landed on the branch.**
> `main` (fa6cde4, the 3G-3K cleaner hardening) was merged into the branch as
> `ee5f12c` using the resolution verified on the `merge-trial` throwaway
> (warning stays hoisted above the match check — 3J(c) preserved; the
> branch's ledger writes re-inserted additively). **Option C ("attest
> existence, decline the year"; Johannes's decision, write-up §9) is
> implemented on top as `9842f2d`**: `find_api_entry_for_bib_entry` returns a
> falsy `CleaningAbstention` on its two abstention paths, and the ledger
> records `api_matched: True` + the normalized DOI + an additive
> `cleaning_abstained` reason, while cleaning behaviour is byte-identical to
> no-match. Acceptance measured over all 319 local bibs: **cleaner metrics
> identical to `main`** (matched 6611, planned fields removed 2668, breaker
> trips 86, years corrected 0, 0 crashes), ledger diff = **106 abstention
> flips and nothing else** (all `pooled_year_conflict`), EXISTENCE gate
> **+56 regained, 0 lost** (incl. every §9-named work), corpora untouched.
> Suite: **1192 green**. Analysis + resolution record:
> `docs/known-issues/evidence-tier-branch-divergence.md`.
>
> **`hooks/metadata_cleaner.py` remains frozen on `main`** until the branch
> lands: a main-side cleaner edit would re-open the divergence. Cleaner work
> goes on the branch (which now carries main's hardening) or waits.
> Sister-repo instructions for the port (the service has no evidence-tier
> layer yet, so Option C is a condition on its pending port item 20):
> `~/Downloads/phillit-abstention-attestation-decision-2026-08-02.md`.
>
> **One thing gates the merge:**
> **(b) writer-guidance follow-ups — CLOSED, PASSED 2026-08-02.** The b2
> prompt edits (built 2026-08-01) were validated with a live headless Sonnet
> run on the branch ("Scientific representation and models in science",
> workspace `~/phillit-ab/gateb-validation-20260802`, kept): CONTEXT
> in-prose attribution **11 of 11 sentences** (pre-edit baseline: 1 of 4);
> violation sentences **2/28** low-tier entries (baseline: 7/27), both mild;
> 4 exemplary title-derivable EXISTENCE uses. Option C live-validated in the
> same run (3 abstentions attested, refusal visible, none demoted). Full
> adjudication: A/B results doc, "Gate (b) validation run" section. The
> sanitize-time stripping candidate is **CLOSED — REJECTED** (Johannes,
> 2026-08-02: it would have suppressed 7 correct abstracts; self-heal +
> prefilled attestation + anti-re-emission guidance address the real
> mechanism). Side finding: the run hand-confirmed item 3E live — the
> orchestrator removed 6 phantom References entries from the surname+year
> matcher unprompted.
> **(c) blind holistic coherence comparison — the last open gate** — rubric
> item 3. Arms archived at
> `~/phillit-ab/archives/{control,treatment}-*-20260725.tar.gz`.
>
> **DO NOT REMOVE THE `evidence-tier` WORKTREE.** `docs/superpowers/` is
> gitignored here, so the A/B results + adjudication record exist ONLY inside
> that worktree, at
> `docs/superpowers/plans/2026-07-25-evidence-tier-ab-results.md`. Johannes
> decided on 2026-07-28 to leave them untracked (sole developer, one machine,
> daily backups) — that decision is made, don't re-raise it.
>
> **Two post-A/B fixes on the branch must survive the downstream port** — a
> merge conflict resolved against the old 11-verb regex silently reverts the
> first: `6ee2566` (widened `check_evidence._VERB_RE`; violation-sentence
> recall 2/7 → 6/7, precision 33% → 47%) and `f9e3fda` (SEP `–––`
> repeated-author resolution in `resolve_context`, which had cost Leonelli
> 2016 its CONTEXT tier). Sister-repo status: `phillit-service`
> `docs/roadmap.md` item 20 + its `HANDOVER.md` top entry.

The agreed next build (Johannes, 2026-07-24). The `INCOMPLETE` exclusion is
unfollowable and fails in both directions — Claude cites excluded canon
anyway (zero discipline), weaker downstream models obey and produce false
claims of absence. Replace it with a script-stamped evidence tier
(`EVIDENCE-ABSTRACT` / `-CONTEXT` / `-EXISTENCE` / `-NONE`) plus a mechanical
encyclopedia-context acquisition pass (`resolve_context.py`).

- **Write-up (start here):** `docs/known-issues/incomplete-exclusion-unfollowable.md`
  — both failure modes with evidence, the tier design, this repo's own
  path/line map, and seven implementation catches.
- **Full spec:** sibling repo,
  `phillit-service/docs/superpowers/specs/2026-07-24-evidence-tier-citability-design.md`
  (v5.1, dual-repo — carries the path/line maps for both trees; four
  adversarial reviews committed alongside).
- **The fix lands in BOTH repos at the same time; BUILD HERE FIRST** — runs
  here are free under Claude Code, the service bills every run through the
  Agent SDK. Then port to the service's vendored `engine/.claude/`. The free
  Sonnet control run here also settles an external reviewer's blocking
  objection to the downstream spec.
- Supersedes the INCOMPLETE-keyed parts of item 3's Issue C (the no-marker
  case); as of spec v5, `abstract_source` is enrichment-ledger attested,
  narrowing C's residual to a forged-*ledger* attack — full provenance
  re-verification stays with item 3 (service roadmap item 23).

## 2. Web-source evidence — citability for `@misc`/url-only entries (dual-repo, spec-first)

Descoped from the evidence-tier spec in v5.1 (Johannes, 2026-07-24): under
item 1's design, every abstract-less web source (blog posts, org reports,
working papers not on arXiv) stamps `EVIDENCE-NONE` and is uncitable —
measured at **~3–17 entries per AI-adjacent review, near zero for classic
topics** (arXiv preprints get API abstracts via normal enrichment and are
unaffected). The barrier report from item 1 counts affected entries per
run, so this item starts from data.

- A first mechanism (`verify_web.py` fetch-and-match) was cut from the spec
  after one round: no alternatives evaluation, A/B contamination, and naive
  fetching fails on the legitimate targets (JS-rendered pages, PDFs,
  bot-blocking hosts). Full autopsy: the spec's Cut section.
- **Spec-first** — brainstorm alternatives (researcher-side page capture,
  Wayback snapshot pinning, archive-fallback fetch, title-in-page match,
  existence-only citability, PDF extraction), decide the earned tier and
  licensed claims, then external review, like item 1.
- **Dual-repo, same path as item 1**: spec lives in the sister repo
  (`phillit-service/docs/superpowers/specs/`), build and validate HERE
  first (free runs), then port. Service roadmap tracks the mirror as
  item 24. Sequence after item 1 ships.

## 3. Bibliography-pipeline integrity fixes

**G — metadata cleaning was dead on 64% of real reviews: FIXED 2026-08-02**
(`aca9d33`; mirrored to phillit-service `8ed7cba`). CORE writes `journal` as
a string, `detect_api_source` had no `core` branch, and the S2 fallback
parser raised AttributeError with nothing catching it — so one `core_*.json`
killed the whole index (**27 of 42 local corpora**), while
`subagent_stop_bib.sh` `jq`-swallowed the traceback into "0 fields removed",
byte-identical to a clean run. Fix: per-file isolation in
`build_metadata_index`, JSON-not-traceback from `main()`, a non-JSON guard in
the hook, a real `parse_core_result`, and a string-tolerant
`parse_s2_result`. Gated on a dry-run over all 42 corpora (writes stubbed):
the 113 bibs that already worked are unchanged, the 206 newly-activated ones
strip *less* (20.7% vs 29.7%). Two things left open on purpose: `unknown`
sources still fall through to `parse_s2_result` (479 non-paper files inject
928 bare-title entries — narrowing it would shrink the index and strip MORE,
so it needs its own evidence). The second — the dormant `metadata_validator.py`
carrying the identical defect — is **CLOSED 2026-08-02**: the module was
deleted rather than fixed twice (it was wired into no hook, and its duplicated
parser/index layer is what let the dormant copy be hardened past the live one).
Details: phillit-service `HANDOVER.md`, 2026-08-02.

**H — malformed-DOI false verification (K1): FIXED 2026-08-02** (`7f6d38f`;
service `59536cd`). `_plan_type_downgrade` compared DOIs with a bare
`normalize_doi(a) == normalize_doi(b)`; `doi:`, `https://doi.org/` and `"  "`
all normalize to `""`, so two malformed DOIs read as a verified match and
suppressed the `@misc` demotion of an article that had just lost its
`journal`. Now routed through `_field_matches_api` and its `bool(nv)` guard.
The same commit replaces two vacuous `assert "METADATA_CLEANED" not in
content` assertions (pybtex escapes the underscore, so they could never fail)
with a backslash-tolerant helper plus a control test that pins the vacuity.

**J - cleaner DOI/year comparison hardening: FIXED 2026-08-02.** The residual
comparison defects after G/H, all one pattern: comparing a *derived* value
without asking whether it is meaningful. (a) `find_api_entry_by_doi` and
`find_doi_year_conflicts` now reject an empty normalized DOI - the two scan
sites H did not cover. (b) `_year_key` canonicalizes years across conflict
detection, the title+year fallback AND the year correction that writes to the
.bib - by exact string grammar, NOT `float()`. **This supersedes the advice in
H**: a float round-trip turns `9007199254740993` into `...992` and collapses
`"2007.0000000000001"`, so the version phillit-service ships must be replaced,
not copied (report:
`~/Downloads/phillit-service-cleaner-findings-2026-08-02.md`). (c) A
conflicted DOI with no entry-scoped record now abstains terminally - no
title+year fall-through, or the bib's own bad year confirms the wrong source -
and the conflict warning moved above the match check so abstention is never
silent. (d) Two entry-scoped records disagreeing on a non-empty canonical year
also abstain, and a yearless scoped record no longer shadows a year-bearing
one **that is at least as complete** - the winner governs verification of
every field, so trading completeness for a year would delete metadata the
first record verified. `metadata_validator.py` got G's full shape-tolerance too
(`9aa473d`) — work since discarded with the module itself, which was deleted
2026-08-02 as dead code.

Dry-run over all 42 corpora (43 bibs, 4073 entries, writes stubbed):
matched 3179->3109, fields removed 1313->1292, **years corrected 36->36**,
breaker trips 11->11, zero errors. So 70 entries newly abstain, only 19 of
which were receiving any cleaning - and no legitimate year correction was
lost. Warning SETS (not just counts) are identical old vs new: 0 added, 0
removed, 0 retext. All 70 abstentions are (c); Task 1 and the scoped-conflict
path account for none. (An earlier figure of 24 was the same phenomenon
measured over only the 15 corpora that parsed before G fixed the index
crash.) Only (c) has measured harm behind it; the
DOI guard had **zero** real-world incidence and the year work is boundary
hardening (no PhilLit producer emits a float year). Residual, documented not
fixed: two scoped records agreeing on year but differing on
journal/volume/pages are still first-wins.

**I — `entry_scoped` authority was keyed on a FILENAME substring: FIXED
2026-08-02.** Flagged by both kimi-k3 and gpt-5.6-sol reviewing the 2026-08-02
branch. `entry_scoped = "verify_" in filename.lower() and api_source ==
"crossref"` was wrong in both directions; authority now follows the envelope's
content — `api_source == "crossref"` **and exactly one result**, i.e. a
targeted single-work lookup. Measured over the 45 local corpora (7109 JSON
files): **262 files gain** authority (genuine per-DOI CrossRef lookups saved as
`crossref_*.json`, `<author>_<year>.json`; previously "trusted to acquit but
not to convict"), and the **181 that lose the tag all carry `results: []`** —
they contribute zero records, which is why no legacy filename fallback is
needed. The `api_source` conjunct is retained and load-bearing: the 11
multi-result `verify_*.json` files here are Semantic Scholar dumps. The
external review recommended two further conjuncts (lookup mode `doi`, and
requested DOI == record DOI); both were **deliberately not adopted** —
`verify_paper.py --title` is still a targeted single-work query (227 such files
here), and once a record's DOI matches the bib entry's, the record is
CrossRef's own metadata for that DOI. Only 2 of 981 requested-vs-returned DOIs
differ locally, both benign aliases. Dry-run over all 43 bibs: matched
3109→3130, planned fields removed 1292→1293, breaker trips 11→11, zero errors.
Refusals are now countable (`years_declined` + warning, mirrored from the
service) and a starved index sets `index_starved` (review finding E). Full
write-up: `~/Downloads/phillit-review-findings-for-sister-repo-2026-08-02.md`.

**K — the CrossRef year was the ONLINE-FIRST year, so 64% of "corrections"
corrupted a correct bibliography: FIXED 2026-08-02.** Found while measuring I.
`verify_paper.py:format_result` read date fields in the order `published`,
`published-print`, `published-online`, `created` — and CrossRef defines
`published` as the **earliest** of print and online. Every online-first work
therefore reported its pre-issue year, and the cleaner rewrote the bib to
match. Ground-truthed against the CrossRef API for all 42 year rewrites the
local corpora produce: **27 replaced a year that exactly equals
`published-print` with the `published-online` year** (Mind 130(517): print
2021-06, online 2019-12 → the correct 2021 became 2019; likewise Episteme
17(2), Sci Eng Ethics 23(3), Synthese 197(7), …). This is the same corruption
as the original known issue, from a different direction: G–J fixed *whose*
evidence may correct a year, and nothing had asked whether the year itself was
the citation year. Two-part fix: (a) the producer prefers `published-print` and
records `year_basis` — which CrossRef field the year came from; (b) the cleaner
requires *positive* provenance before overwriting a populated year
(`_year_is_overwritable`), so the legacy records already on disk — where good
and bad years are indistinguishable — decline instead, countably. The same
online-first bug made the title-search `±1` year filter reject correct papers
(a 2020 citation year vs a 2018 online date); it now accepts either date.
Re-verified against CrossRef, the fixed producer turns **27 of the 42 rewrites
into no-ops and leaves 15 corrections, all to the print year — zero
corruptions**. On the legacy corpora the gate yields 0 corrections and 154
recorded declines (up from 109), all surfaced to the model through the hook's
existing `.warnings[]` pass-through. (`metadata_validator.py` needed no mirror —
it was read-only with no year-overwrite path — and is moot since its deletion
2026-08-02.)

> **⚠ SUPERSEDED BY ITEM J — do not act on the paragraph below.** It says to
> copy the service's `float()` + `is_integer()` `_year_key`. That version has
> a third defect of its own: binary float cannot represent large integers, so
> it returns a value nobody supplied (`9007199254740993` → `...992`,
> `"2007.0000000000001"` → `"2007"`) — and the year correction WRITES its
> output into the .bib. J replaced it with an exact string grammar in both
> repos (service `edaef51`). Kept below only for the reasoning about the
> ORIGINAL `str(int(float(value)))`, which is still correct.

**IF THE PORT PLAN'S TASK 2 PROCEEDS, carry the CORRECTED `_year_key`** — not
the version the service shipped before 2026-08-02. The original
`str(int(float(value)))` collapses genuinely different values (`"2007.9"` →
`"2007"`) and lets `OverflowError` escape (it is not a `ValueError` subclass,
and `float("1e999")` is `inf`). The service's current version canonicalizes
only integral values and catches it — copy that one, and apply it at all four
year-comparison sites, not just the two conflict-detection ones. Note the
service also now gates its year overwrite on `entry_scoped`, ported FROM
here, but keeps its stronger conflict abstention: where this repo lets a
verify record win a same-DOI year conflict, the service abstains entirely.
That divergence is deliberate and documented in both docstrings.

Six related gaps. A–D were surfaced 2026-07-24 by the downstream
`phillit-service` model-experiment audit and written up in
`docs/known-issues/bib-pipeline-integrity-gaps.md`; E–F were added later
(see below).

- **A — cleaner-unaware dedup** (`dedupe_bib.py`): cross-domain duplicate
  merging can resurrect a field the metadata cleaner stripped as
  unverifiable. Deterministic; affects plugin runs today.
- **B — silent References omission** (`generate_bibliography.py`): a
  body/bib author-spelling divergence beyond NFKD normalization silently
  drops a cited work from the rendered References; no
  every-citation-resolves post-check exists (natural home: `lint_md.py`).
  Deterministic; affects plugin runs today.
- **C — unenforced abstract provenance**: an invented `abstract` field with
  no `abstract_source` marker passes every gate and evades the
  INCOMPLETE-keyed cite-cautiously rule. Structural; the observed exploit
  was under a non-Anthropic orchestrator, but nothing model-specific closes
  the gap. *Partly superseded by item 1*: the tier design closes the
  no-marker case (top tier requires `abstract_source`); the forged-marker
  residual remains and is revisited with the item-1 spec.
- **D — no venue-quality vetting**: predatory-venue papers pass DOI
  verification; flag-and-caveat heuristics (DOAJ lookup, `VENUE_UNVETTED`
  keyword + writer rule) would turn observed good model behavior into a
  pipeline guarantee.

Two further sub-items, added 2026-07-28 from a side finding during
evidence-tier A/B adjudication, then measured across all 32 delivered
reviews. Write-up:
`docs/known-issues/author-year-collision.md` (evidence tables, the three
failure modes, and why the fix cannot live in Phase 6).

The pipeline identifies a work in prose by *first-author surname within 60
characters of a 4-digit year* — `find_cited_entries` and
`check_evidence.find_cites`, both on `_MATCH_WINDOW = 60`. Nothing
distinguishes two works sharing that pair, and no stage assigns Chicago
`2019a`/`2019b` suffixes. Two defects are visible in delivered output:

Collisions come in two kinds, and they need *different* mechanisms — E
handles those the prose can already distinguish, F those it cannot. Both
close a phantom-reference hole for their own class. Measurements: 21/32
reviews contain at least one collision group; in **7 groups** the prose
carries strictly fewer distinct citation forms than the group has entries,
so a listed work is confirmed uncited.

- **E — matcher collisions / phantom references**
  (`generate_bibliography.py`): every entry sharing `(first-author surname,
  year)` matches whenever any one of them is cited, so uncited works get
  rendered into References *even when the prose was unambiguous*. Scope:
  collisions where the works have **different authors**. Two sub-shapes,
  both needing a fix:
  - *Different author lists* — `Muldoon et al. 2023` vs. `Muldoon and Wu
    2023`; also Moore 2020, Li 2022, Wang 2023, Adams 2010. Fix: require a
    discriminating token (second-author surname, or `et al.`) in the window
    before matching.
  - *Different people, same surname, both solo* — Gabbrielle vs. Rebecca
    **Johnson** 2024; no author-list token can separate these. Chicago's own
    rule is first initials (`G. Johnson 2024` / `R. Johnson 2024`), which
    means E also needs an initial-aware match and a writer-facing note.

  Where the prose form stays ambiguous, warn rather than guess.
  Self-contained in `generate_bibliography.py`, no agent-prompt change, no
  live run — natural companion to B's every-citation-resolves check in
  `lint_md.py`.
- **F — no Chicago a/b disambiguation**: scope is collisions where the
  works have the **same author**, which E cannot touch — nothing in the
  citation distinguishes them, so suffixes are the only fix. Flagship case:
  `extended-mind-cognitive-offloading` cites `Menary (2006, 2010, 2013)`
  while References lists **three** distinct solo-author Menary 2010 works
  (two chapters + the edited volume) — unresolvable for a reader, and two
  of the three are phantoms. Separately, 8/32 reviews contain prose cites
  like `Wiens (2015a; 2015b)` while **zero** reference lists carry a
  lettered entry, so the citation resolves to nothing (the mirror image of
  B). Writers are already trying to disambiguate; the renderer never emits
  suffixes. The information is lost at write time, so suffixes must be
  assigned on the merged bib *before* Phase 5, into a dedicated field —
  **not** `year`, whose `\d{4}` guards in `check_evidence.py` and
  `stamp_evidence.py` would reject `2019a`. Touches `conventions.md` and
  `agents/synthesis-writer.md`, so it needs a live headless run to confirm
  writer compliance before the port.

Suggested order: A+B first (small, testable, deterministic), then E (same
shape, and it pairs with B), then C (mechanical validator rule), then D
(heuristics + prompt rules). F last — it is the only one of the six that
needs a live run, and that run should not be entangled with the
evidence-tier A/B experiment.

Related out-of-scope find (2026-07-28, recorded in the same write-up): 5/32
reviews carry near-identical *undeduped* entries surviving on diacritic
variance (`Milliere`/`Millière`) and arXiv-vs-journal pairs. Overlaps A but
is a distinct failure; not folded into A's scope.
Cross-repo: fixes land here or in the service's vendored engine and are
cherry-picked to the other side — same path as the metadata-cleaner year
fix (plugin 0.2.6 ↔ service `7369880`). The service tracks the mirror item
as roadmap item 23.

## 4. One owner for bibliography identity and matching (refactor; cause of several measured symptoms)

**Opened 2026-08-02**, after `metadata_validator.py` was deleted for being a
dormant copy that absorbed hardening meant for the live path (item 3 G). That
was the terminal case of a pattern that is still live elsewhere: **no module
owns "is this the same work / is this value trustworthy", so every script
re-implements it.** Measured, not inferred — three live copies of title
normalization, all disagreeing:

| input | `metadata_cleaner` | `dedupe_bib` | `generate_bibliography` |
|---|---|---|---|
| `Millière` | `milliere` | `milli re` | `milliere` |
| `Davidović` | `davidovic` | `davidovi` | `davidovic` |
| `Łącki on agency` | `łacki on agency` | `cki on agency` | `acki on agency` |
| `Η ηθική της τεχνολογίας` | `η ηθικη τησ τεχνολογιασ` | `''` | `''` |

**This explains two already-measured symptoms whose cause was recorded as
unknown:**

- The `Milliere`/`Millière` undeduped pairs in **5/32 reviews** (item 3's
  out-of-scope find, above). `dedupe_bib._normalize_title` is the only one of
  the three that applies no Unicode normalization at all — a bare
  `re.sub(r"[^a-z0-9]+", " ", s.lower())`, so any non-ASCII letter becomes a
  space. The other two match these pairs correctly.
- A **new mode inside Issue B** (`bib-pipeline-integrity-gaps.md`): a title or
  first-author surname in a wholly non-Latin script ASCII-folds to `''`, and
  `generate_bibliography.py:417` (`if not norm_surname: continue`) then skips
  the entry, so a cited work is **deterministically absent** from the rendered
  References. Issue B's recorded fix directions (transliteration-aware
  normalization, fuzzy near-miss fallback) **do not cover this** — there is
  nothing to be near when the key is empty. The `lint_md.py` post-check does
  cover it, which breaks the tie between B's two fix directions.

The `metadata_cleaner` versions are the hardened ones (item-13 B3 fixed exactly
this ASCII-fold bug there and the fix was never propagated — its docstring
still documents the defect the other two carry). Scope: one module owning
`normalize_doi`, title normalization, `normalize_pages`, `normalize_journal`,
`_year_key`, and fallback-key construction; four import sites
(`metadata_cleaner`, `dedupe_bib`, `generate_bibliography`, `verify_paper`).

**No new infrastructure needed** — cross-directory sharing already exists and
is already used: `generate_bibliography.py:19-24` imports `LATEX_ESCAPES` from
`hooks/bib_validator.py` with the comment *"single source of truth"*. The
project shares constants and duplicates judgments. One plan document
(2026-07-24) explicitly sanctions the duplication — *"duplicating avoids a
cross-module import for a trivial function"* — so this is policy to reverse,
not an accident to patch.

**Sequence AFTER the item-1 merge.** It touches `dedupe_bib.py`, which carries
+180 lines on `worktree-evidence-tier` and currently auto-merges cleanly;
refactoring first manufactures a conflict where there is none. See
`docs/known-issues/evidence-tier-branch-divergence.md`.

## Backlog pointers

Other open items are tracked in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open (e.g.
`ndpr-enrichment-underused.md`, `recent-publication-indexing.md`,
`philpapers-rate-limiting.md`).
