# PhilLit Roadmap

Open engineering work, in rough priority order. Detailed problem write-ups
live in `docs/known-issues/` (one file per issue; each carries a Status
line); forward-looking design sketches live in `docs/ideas/`. This file
exists so open work has a single place to be listed — it was created
2026-07-24 alongside the bib-pipeline item below.

## 1. Evidence-tier citability — replace the INCOMPLETE exclusion (BUILT + A/B'd HERE, unmerged; dual-repo)

> **Status 2026-07-28 — read this before starting anything.** The build is
> DONE on branch **`worktree-evidence-tier`** (worktree at
> `.claude/worktrees/evidence-tier`, tip `f9e3fda`, 23 commits ahead of
> `main`, unmerged and unpushed). All 11 plan tasks executed; **unit suite
> 1069 green**. The free Sonnet two-arm A/B has run ("What are data?"), and
> Johannes adjudicated **three of the four rubric items** on 2026-07-28.
> Provisional outcome cell: **"Works. Proceed."**
>
> **Two things gate the merge, both open:**
> **(b) writer-guidance follow-ups** — the A/B doc forward-references a
> section that was never written. Raw material: 7 violation sentences across
> 8 of 27 recovered low-tier entries, the CONTEXT in-prose attribution rule
> followed only 1 of 4 times, and a "strip or fence unattested abstract text
> at sanitize time" candidate. **Johannes's call: pre-merge prompt edits, or
> deferred?** This one goes first — it gates the downstream port.
> **(c) blind holistic coherence comparison** — rubric item 3, the last open
> pre-registered gate item. Arms archived at
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
so it needs its own evidence), and the dormant `metadata_validator.py` still
carries the identical defect. Details: phillit-service `HANDOVER.md`,
2026-08-02.

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
one. `metadata_validator.py` gets G's full shape-tolerance too.

Dry-run over all 42 corpora (43 bibs, 4073 entries, writes stubbed):
matched 3179->3109, fields removed 1313->1292, **years corrected 36->36**,
breaker trips 11->11, conflict warnings 140->140, zero errors. So 70 entries
newly abstain, only 19 of which were receiving any cleaning - and no
legitimate year correction was lost. Only (c) has measured harm behind it; the
DOI guard had **zero** real-world incidence and the year work is boundary
hardening (no PhilLit producer emits a float year). Residual, documented not
fixed: two scoped records agreeing on year but differing on
journal/volume/pages are still first-wins.

**I — `entry_scoped` authority is keyed on a FILENAME substring: OPEN, needs
a decision.** Flagged by both kimi-k3 and gpt-5.6-sol reviewing the 2026-08-02
branch. `entry_scoped = "verify_" in filename.lower() and api_source ==
"crossref"` has two failure modes: a genuine per-DOI CrossRef lookup saved as
`crossref_*.json` silently loses correction authority (observed in the local
corpora), and a *broad* CrossRef search saved as `verify_*.json` grants
authority to every record in it — which can recreate the year corruption the
gate exists to prevent. Recommended fix needs a `verify_paper.py` change:
record the lookup mode + requested DOI in the payload and grant authority on
content, keeping the filename rule as a legacy fallback. Cheap interim that
kills the false-authority half alone: additionally require the envelope to
hold exactly one result. The service now at least records refusals
(`years_declined` + warning) so the residual is countable; mirroring that here
is the smaller first step. Full write-up:
`~/Downloads/phillit-review-findings-for-sister-repo-2026-08-02.md`.

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

## Backlog pointers

Other open items are tracked in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open (e.g.
`ndpr-enrichment-underused.md`, `recent-publication-indexing.md`,
`philpapers-rate-limiting.md`).
