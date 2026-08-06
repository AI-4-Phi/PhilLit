# PhilLit Roadmap

Open engineering work, in rough priority order. Detailed problem write-ups
live in `docs/known-issues/` (one file per issue; each carries a Status
line); forward-looking design sketches live in `docs/ideas/`. This file
exists so open work has a single place to be listed — it was created
2026-07-24 alongside the bib-pipeline item below.

**Working sequence (Johannes, 2026-08-05):** (1) push `main` with a plugin
version bump — DONE 2026-08-05, released as **v0.3.1** (`318aa2c`); (2) the 27-wrong-years
audit of delivered reviews — measurement DONE 2026-08-05 (finding: 449
delivered entries carry online-first years, see item 3 K; remediation
decision pending); (3) item 3's residuals — **A, B, and E all DONE
2026-08-05** (A's dedup fix, B's post-check + matcher-side transliteration,
E's instance-based collision resolution); **C closed-as-narrowed 2026-08-05**
(ledger write-protection); **D BUILT 2026-08-06** (OpenAlex venue-status
flag on low-visibility journals, plus the researcher/writer/planner prompt
rules) and **CLOSED the same day** — whole-branch review verdict "safe to
consider done", its 3 Important + 4 Minor findings all fixed; and **F BUILT
2026-08-06** — all seven tasks, one Critical found and fixed in review. **F's
live run is the one thing outstanding**, carrying five riders; (3b) **NEW
2026-08-05: OpenAlex began metering the API** —
**key support BUILT the same day** (`OPENALEX_API_KEY`, optional; plus
fail-fast on budget exhaustion, which was costing 1–2.4 h of dead sleeping
per review), see `docs/known-issues/openalex-metering-2026-08-05.md`. F's
live run — including D's writer-compliance rider and D's own live smoke
test — needs a working key in the environment. **Re-diagnosed 2026-08-06: the
key is not stale or over-budget, it is UNREGISTERED.** OpenAlex answers
`{"error":"Invalid or missing API key","message":"API key not found"}` under
every documented auth mechanism (query parameter, `Bearer` header, `api_key`
header) while the same URL unkeyed returns 200, and `~/.api_keys` and the shell
profile hold the same value. A new key from `openalex.org/settings/api` is the
only fix — see the write-up's "2026-08-06" section. Note riders 1-3 and F's own
check need no key at all, so an F-only run is possible while riders 4-5 wait;
(4) ONE
batched phillit-service mirror session — the item-4 `bib_identity` port,
the item-1 evidence-tier port (service item 20), the item-3-E
collision-aware-matching port (Tasks 1-4 plus the final-review fix-wave,
`917850d`..`970b117` — port from `970b117` or later, never `e5e863a` or
`e5cb717` alone: `970b117` fixes a left-anchor gap in
`_CITE_INSTANCE_RE` (C1) and requires bib-record corroboration before a
second-position sighting can drop a group (I1), both of which the
earlier commits in this range still get wrong),
and the deferred `rate_limiter` fix — which **opens with a decision: the
two trees have drifted far enough that the session may conclude they
should be developed separately rather than mirrored**; (5) item 2. Until
that session, mirror debt accumulates deliberately — don't mirror
piecemeal, and don't touch/push phillit-service outside it.

## 1. Evidence-tier citability — replace the INCOMPLETE exclusion (MERGED here, v0.3.0; service port pending — dual-repo)

> **Status 2026-08-02, end of day: MERGED TO `main` (`f89f4de`) and RELEASED
> as plugin v0.3.0.** Both merge gates closed the same day: **(b)** the
> writer-guidance validation run PASSED (fresh headless Sonnet run on the
> branch, "Scientific representation and models in science": CONTEXT
> in-prose attribution **11/11** sentences vs the 1/4 pre-edit baseline;
> violation sentences **2/28** low-tier entries vs 7/27; Option C
> live-validated — 3 abstentions attested, none demoted; run workspace
> `~/phillit-ab/gateb-validation-20260802` kept); **(c)** the blind
> coherence read — Johannes recorded his verdict before the mapping was
> unsealed and PREFERRED the treatment arm "by a clear margin but not
> overwhelmingly" (better structure, focus, and coverage; control ahead
> only on prose style). **Final pre-registered outcome cell: "Works.
> Proceed." — all four rubric items adjudicated.** Full records: the A/B
> results doc (gitignored — see the records note below) and
> `docs/known-issues/evidence-tier-branch-divergence.md` §10 (the earlier
> catch-up merge + Option C acceptance). The `metadata_cleaner.py` freeze
> on `main` is LIFTED — `main` is the single line again.
>
> **The A/B results + adjudication records live in the main checkout's
> gitignored `docs/superpowers/plans/`** (`2026-07-25-evidence-tier-ab-results.md`
> and the implementation/attestation-fix plans). The `evidence-tier` worktree
> and branch were removed 2026-08-02 after the merge landed and every record
> was verified byte-identical in the main checkout. Johannes decided on
> 2026-07-28 to leave the records untracked (sole developer, one machine,
> daily backups) — that decision is made, don't re-raise it.
>
> **What remains of this item: the service port** (service roadmap item 20,
> currently queued behind its item-25 repo audit; batched into the mirror
> session — working sequence above — and contingent on its mirror-vs-fork
> decision). The port-scope list lives
> there and must survive the port: the widened `check_evidence._VERB_RE`,
> the SEP `–––` repeated-author resolution in `resolve_context`, and Option
> C abstention attestation. Sister-repo instructions:
> `docs/known-issues/phillit-abstention-attestation-decision-2026-08-02.md`
> (local-only).

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
  item 24. Sequenced last (working sequence above): after item 3's
  residuals and the batched mirror session — whose mirror-vs-fork decision
  determines whether this item's "dual-repo" framing still holds.

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
`"2007.0000000000001"`, so the version phillit-service originally shipped had
to be replaced, not copied — done, service `edaef51` (report:
`docs/known-issues/phillit-service-cleaner-findings-2026-08-02.md` (local-only)). (c) A
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
write-up: `docs/known-issues/phillit-review-findings-for-sister-repo-2026-08-02.md` (local-only).

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

**Delivered-output audit DONE 2026-08-05** (the sequence's step 7): every
DOI-bearing entry in all 41 delivered bibs ground-truthed against CrossRef.
**449 of 3,456 entries (13%) carry the online-first year** — 417 pin the
version of record via volume/number, 269 surface in the delivered review
text, all 41 reviews are affected including the three tracked README
examples (51 entries). Structurally these are NOT the 27: the cleaner never
applied a year rewrite in this corpus (zero `METADATA_CLEANED` markers — the
27 record-side corruptions never landed, and those delivered years are
correct), so the 449 were **seeded at research/enrichment time from
search-API metadata** (S2/OpenAlex report online-first years). K's fix
covers the producer and the cleaner gate but NOT this seed path, so new
runs still seed online years and self-correct only where an entry-scoped
CrossRef record exists. **Decisions (Johannes, 2026-08-05):** delivered
reviews are NEVER retroactively changed — sole exception the public README
examples, **fixed same day (`ef15dbd`, 54 entries; their Word-exported PDFs
remain stale)**. Search-API data is accepted as veridical, with conflicts
resolved by a *hierarchy of sources*: for years, CrossRef version-of-record
dates trump S2/OpenAlex — which is what the cleaner's authority model
(entry-scoped + `year_basis`) already implements. **Open follow-up (the
year-hierarchy coverage gap):** Phase 3 instructs researchers to
verify_paper every DOI-bearing entry, but coverage is agent-compliance, not
a guarantee — an entry without an entry-scoped CrossRef record keeps its
seeded online year. Measure the wrong-at-delivery rate on the next live run
(natural rider on item 3 F's run); if material, add a mechanical year pass
(search formatters or Phase 6). Full report + per-review table:
`docs/known-issues/wrong-years-audit-2026-08-05.md` (local-only).

> **⚠ SUPERSEDED BY ITEM J — do not act on the paragraph below.** It was
> written against the service's interim `float()` + `is_integer()`
> `_year_key`, which has a third defect of its own: binary float cannot
> represent large integers, so it returns a value nobody supplied
> (`9007199254740993` → `...992`, `"2007.0000000000001"` → `"2007"`) — and
> the year correction WRITES its output into the .bib. J replaced it with an
> exact string grammar in both repos (service `edaef51`), so there is
> nothing left to copy. Kept below only for the reasoning about the
> ORIGINAL `str(int(float(value)))`, which is still correct.

**IF THE PORT PLAN'S TASK 2 PROCEEDS, carry the CORRECTED `_year_key`** — not
the version the service shipped before 2026-08-02. The original
`str(int(float(value)))` collapses genuinely different values (`"2007.9"` →
`"2007"`) and lets `OverflowError` escape (it is not a `ValueError` subclass,
and `float("1e999")` is `inf`). The service's interim version canonicalized
only integral values and caught it; J's exact string grammar (now in both
repos) is what must be carried, applied at all four year-comparison sites,
not just the two conflict-detection ones. Note the
service also now gates its year overwrite on `entry_scoped`, ported FROM
here, but keeps its stronger conflict abstention: where this repo lets a
verify record win a same-DOI year conflict, the service abstains entirely.
That divergence is deliberate and documented in both docstrings.

Six related gaps. A–D were surfaced 2026-07-24 by the downstream
`phillit-service` model-experiment audit and written up in
`docs/known-issues/bib-pipeline-integrity-gaps.md`; E–F were added later
(see below).

- **A — cleaner-unaware dedup** (`dedupe_bib.py`): **FIXED 2026-08-05**
  (`fe46575`, `9ea5b97`, `a631d7a`, `7816d2a`) — `dedupe_bib.py` and
  `generate_bibliography.py` now propagate `METADATA_CLEANED` verdicts
  across duplicates via surgical field strip and a blocked union. Full
  mechanism and three scoping residuals (marker records field names not
  values; DOI-refusal branches pre-existing; unflagged-field conflicts
  still resolve by each merge path's own vetting-blind winner rule) in
  `docs/known-issues/bib-pipeline-integrity-gaps.md`.
- **B — silent References omission** (`generate_bibliography.py`):
  **CLOSED 2026-08-05.** The every-citation-resolves post-check landed
  (`03d2b6b`, `lint_md.py`) — an unresolved in-text citation now fails the
  lint step loudly (ERROR, nonzero exit) instead of vanishing silently —
  and the matcher-side transliteration fix landed the same day (item 3 E
  Task 2, `fb6623e`): symmetric NFKD + transliteration-fold matching
  resolves the near-miss that opened this issue (body "Fraenken" vs bib
  "Franken") directly at match time. The fuzzy near-miss fallback from the
  original fix directions was never built and is not needed to close this.
  Documented check-side known limits remain — see
  `docs/known-issues/bib-pipeline-integrity-gaps.md` Issue B.
- **C — unenforced abstract provenance: RE-SCOPED and CLOSED-AS-NARROWED
  2026-08-05.** The tier closes three of C's four routes (no marker; marker
  present but unbacked; researcher-written abstract, which
  `enrich_bibliography.attest_prefilled_abstract` re-fetches and attests only
  on hash equality). The residual was exactly one thing: the enrichment
  ledger is an agent-writable JSON file that is *also* the attestation
  authority, so forging a record makes enrichment skip the fetch that would
  have refused attestation and the barrier stamps the fabrication
  `EVIDENCE-ABSTRACT`. **Johannes's decision, 2026-08-05: write-protect +
  document** — `hooks/block_ledger_write.py` (PreToolUse on Write, Edit *and*
  NotebookEdit, needle `_ledger-`) denies **native file-tool** writes to
  `enrichment_ledger-*.json` / `cleaning_ledger-*.json`, with two matching
  `deny` rules in `PHILLIT_RULES` as belt-and-braces for setup'd workspaces.
  No false positives in the supported pipeline (both ledgers are written from
  inside Python and no prompt mentions them — audited), at the price of two
  deliberate denials: a developer hand-edit, and a same-named file elsewhere.
  **State the scope honestly: this is not a security boundary.** Broadly-allowed
  `Bash` (`cat >`, heredoc, `python -c`) bypasses every PreToolUse gate, so
  against a *deliberate* forger the control is incidence reduction, not
  closure — the external review was explicit that calling the ledgers
  "write-protected" would be misleading. **Two mechanisms were measured and
  rejected**: on-disk envelope
  corroboration (50.6% coverage over 2,121 corpus abstracts — openalex only
  23.8% — so demote-on-absence repeats the decision closed 2026-08-02 and
  warn-on-absence is wrong half the time), and a Bash-command text gate (it
  would need shell parsing to tell `cat ledger.json` from `cat > ledger.json`,
  i.e. the enumerated-Bash-pattern approach this project records as having
  failed four times). Residuals, documented and routed to the service (its
  item 23): a deliberate shell-out, and the full closure — barrier-side live
  corroboration, the only option that can demote an honest entry, costing
  ~one extra enrichment pass. Full analysis, option set and measurements:
  `docs/known-issues/bib-pipeline-integrity-gaps.md` Issue C.
- **D — no venue-quality vetting: BUILT 2026-08-06**
  (`skills/literature-review/scripts/venue_vetting.py`, wired into the
  evidence barrier; prompt rules in `agents/synthesis-writer.md`,
  `agents/domain-literature-researcher.md` **and `agents/synthesis-planner.md`**
  — the planner rule was added during D's own task 5 and reverses the plan's
  "writer and researcher only" decision; it is the right call, since the
  planner allocates section weight and would otherwise build a section around
  a flagged venue before the writer ever sees the caveat). The filed mechanism does not
  work. DOAJ lists open-access journals only, so DOAJ-absence carries no
  signal for philosophy's subscription flagships (`Mind`, `Noûs`,
  `Philosophical Review` are all `is_in_doaj: false`), and
  `is_indexed_in_scopus` now comes back `null`. The nearest substitute,
  OpenAlex `is_core`, **misfires on reputable venues — measured**: across the
  120 most-frequent corpus venues it flags 7, every one legitimate (Journal
  of Moral Philosophy, Political Theory, Contemporary Political Theory,
  Jurisprudence, South African Journal of Philosophy, plus Phronesis /
  Kantian Review / Oxford J Legal Studies in the tail sample). A
  single-signal `is_core` rule is therefore prohibited — it would insert
  false discredits and teach the writer to ignore the flag. **D does have
  real targets here**: a free name-shape scan of all 928 distinct journal
  names surfaced ~9 candidates including `Advanced International Journal for
  Research` — the *same* venue as the service observation, `is_core false`,
  h-index **2**. **The implemented rule** (measured against those 9
  candidates and 48 legitimate philosophy venues chosen to stress the rule —
  open-access, non-Anglophone, area-specialist, new): flag iff the venue
  *resolves* AND `is_core` is `False` AND `is_in_doaj` is `False` AND
  h-index < **15**, evaluated over the highest-h same-named source (two
  `Phronesis` entries exist); a missing or `null` signal on any conjunct
  never flags. Result: **4/9 candidates flagged, 0/48 false positives**. Zero
  false positives holds from T=5 to T=19; recall separately reaches its
  4/9 maximum at T=14 and stays there through T=19 — so **T=14..19 is the
  region with both zero false positives and full recall, and T=15 sits at
  its conservative end**, one step in from the floor, *not* mid-plateau (the
  earlier wording here was wrong). Note `measure_d_threshold.py`'s own `flagged()`
  implements only **two of the rule's three conjuncts** (`is_core` and
  h-index — it never checks `is_in_doaj`), so its printed sweep is not the
  shipped rule: at T=15 that two-conjunct sweep already shows one false
  positive (Norsk Filosofisk Tidsskrift, rescued only by the DOAJ conjunct
  the script omits). The quoted **4/9 + 0/48** figures instead come from the
  full three-conjunct rule re-derived directly over the script's saved
  `d_threshold_results.json` (2026-08-06), which reproduces them exactly.
  DOAJ *is* useful after all — with its polarity **inverted**: useless as a
  negative signal, sound as a positive rescue (it is what saves Norsk
  Filosofisk Tidsskrift, h=11). Recall of ~4/9 is the intended trade for a
  flag-and-caveat mechanism where a false discredit costs more than a miss;
  the 5 unflagged candidates are each correctly spared (no OpenAlex match,
  `is_core`, DOAJ-listed, or above the threshold — International Journal of
  Innovative Research in Computer and Communication Engineering resolves,
  is non-core and non-DOAJ, and is spared solely because h=26). **Corroborating
  measurement**: applying the same rule to the 200 sampled corpus venues
  (`venue_verdicts.json`: 120 most-frequent plus 80 from the tail) flags
  **0 of the 125 resolvable rows**; the nearest unflagged non-core/non-DOAJ
  venues sit at h=22 (Washington Law Review) and h=23 (Jurisprudence), well
  clear of the T=15 line.

  Cost measured at 10 credits per name lookup, so verdicts are cached per
  venue: a **180-day cache** (45 days for records that currently flag, since
  a stale flag discredits while a stale clear only misses), an **80-lookup
  cap** per run, a **3-consecutive-error breaker**, and a **120s pass
  deadline** — all reported in the barrier's `venue_vetting` summary rather
  than silent. **Gated on `OPENALEX_API_KEY`** — without one the pass skips,
  because it runs after Phase 3's searches and would otherwise starve the
  next review's budget. The pass **cannot fail the barrier** (fully
  try/except-wrapped; any failure demotes to "no flags", never a barrier
  error), and `venue_status` is **stripped and re-derived on every run**, so
  no flag the barrier itself can write survives a later run (see the
  documented shape limit in `_strip_derived_fields` — renamed from
  `_strip_venue_status` when item 3 F's session widened it to also cover
  `year_suffix`: a hand-edited bare-token or nested-brace value is not
  stripped, though the barrier's own decision still governs what gets
  re-added on top). **Recall is partial by
  design** (4 of 9 known candidates) and **absence of the field means
  nothing** — most entries never carry it, including entries the check never
  evaluated (no key, cap or deadline hit, or an unresolved name).

  What remains: **writer compliance is a rider on item 3 F's live run**,
  alongside D's own live smoke test (both need a working `OPENALEX_API_KEY`,
  per the working-sequence note above); and the sanitized
  `filter=display_name.search:` query's live recall on comma-bearing venue
  names is unmeasured.
- **Follow-up (A's external review, Q3) — "vetted beats unvetted", not
  built**: when a merge loser carries a `METADATA_CLEANED` marker (positive
  proof it was vetted), prefer the loser's value on *conflicting* fields,
  not just on gaps. Today, neither merge path's winner rule consults
  vetting: `dedupe_bib.merge_entries` (the pass that produces the on-disk
  merged bib) still picks by has-abstract-then-importance-tag, and
  `generate_bibliography.find_cited_entries` (the References-rendering
  pass) still picks by substantive-field count — A's fix strips/blocks
  flagged fields *after* the winner is chosen but never touches winner
  selection itself. Either way, a fabricated value on the winning copy
  still beats a verified value on the losing one.

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
handles those the prose can already distinguish, F those it cannot. E
closes the phantom-reference hole outright for the different-author-list
sub-shape; for the same-surname-different-solo-author sub-shape it closes
the hole only when the prose already carries a first initial (the
writer-facing note was never added — see E below). F remains fully open.
Measurements: 21/32 reviews contain at least one collision group; in **7
groups** the prose carries strictly fewer distinct citation forms than the
group has entries, so a listed work is confirmed uncited.

- **E — matcher collisions / phantom references**
  (`generate_bibliography.py`): **FIXED 2026-08-05** (`917850d`, `fb6623e`,
  `be5ab30`, `e5e863a`, `e5cb717`, `970b117`; released as plugin v0.3.3,
  `de86918`). Previously every entry
  sharing `(first-author surname, year)` matched whenever any one of them
  was cited, so uncited works were rendered into References *even when the
  prose was unambiguous*. `_resolve_collisions` now groups colliding
  entries, parses citation instances from the original prose, and keeps
  only the union of entries an instance actually supports — a group with no
  discriminating instance is kept whole with a `[COLLISION] ambiguous`
  stderr warning rather than guessed at. A drop requires affirmative
  instance evidence (a discriminating first-position instance, or a
  second-position sighting corroborated by an actual bib record); two
  narrow residual paths can still lose a work regardless (full detail
  below). Scope: collisions where the works have **different
  authors**. Two sub-shapes:
  - *Different author lists* — `Muldoon et al. 2023` vs. `Muldoon and Wu
    2023`; also Moore 2020, Li 2022, Wang 2023, Adams 2010. Discriminating
    token: second-author surname, or `et al.` with 3+ authors.
  - *Different people, same surname, both solo* — Gabbrielle vs. Rebecca
    **Johnson** 2024; no author-list token can separate these. Chicago's own
    rule is first initials (`G. Johnson 2024` / `R. Johnson 2024`); the
    matcher-side half of this landed (`_first_text_informative`), and the
    writer-facing half **landed 2026-08-05** — `docs/conventions.md` (a new
    in-text-citation row plus the rule and why it is load-bearing) and
    `agents/synthesis-writer.md`. A bare `Johnson (2024)` with no initial
    still cannot discriminate and still falls to keep-all-and-warn, so this
    now rests on writer compliance: **confirming it is a rider on F's live
    run.**

  Residuals (full detail in
  `docs/known-issues/author-year-collision.md`) — note the sentence-adverb
  lead-in residual is **FIXED 2026-08-05** (`_NON_INITIAL_PRECEDING_RE` no
  longer rejects a citation preceded by a sentence-initial transition word
  like "However, "; the and/& half is untouched and an unlisted transition
  still degrades to keep-all): a bare-apostrophe
  possessive ("Rivers' (2020)") isn't stripped; unparsed narrative forms
  fall to keep-all UNLESS an unrelated corroborated second-position
  sighting also exists for the group, in which case the whole group,
  including the unparseably-cited work, still drops; particled FIRST
  surnames ("van der Deijl") never intersect an instance's variants, so
  those groups keep-all by construction; collision resolution runs before
  dedup and can lose the RICHER duplicate's fields (protected on the real
  pipeline, where `dedupe_bib.py` runs first — accepted, narrow).
  Same-author collisions are deliberately left whole for F.
  Self-contained in `generate_bibliography.py`, no agent-prompt change, no
  live run — natural companion to B's every-citation-resolves check in
  `lint_md.py`.
- **F — Chicago a/b disambiguation — BUILT 2026-08-06, live run outstanding.**
  Seven tasks. Letters are assigned at the evidence barrier over **work
  identity** (not entry identity), into a dedicated `year_suffix` field, once
  over the union of every domain bibliography — so the same work carries the
  same letter everywhere. A group is lettered whole or **suppressed whole**;
  a partially lettered group is never produced, and both overflow (>26 works)
  and suppressed groups are named in the barrier's report and its console
  summary rather than vanishing silently. The References render the letter;
  `generate_bibliography` uses it to resolve a citation to one member of a
  same-author-same-year group, which is the token item 3 E structurally
  lacked. Dedup, the sanitizer, the evidence check and the linter all carry
  the field through, pinned end-to-end by `tests/test_pipeline_year_suffix.py`
  running the real Phase 6 command-line sequence.

  **The keep-all rule is the load-bearing part.** A letter may *narrow* a
  candidate set but never delete a work the prose cites. Review found one
  Critical of exactly that shape — eight prose forms (`(2010a, b)`,
  `(2010a & 2010b)`, `The 2010b volume`, an uppercase `2010B`, a
  second-position cite, and others) where a citation that failed to parse was
  indistinguishable from "not cited", so a sibling citation that *did* parse
  licensed a drop. Fixed by a **letter-sighting map**: a raw-prose scan for
  year-plus-letter tokens, done with no citation parsing at all, so a member
  is droppable only if its own `(year, letter)` appears nowhere in the
  document. Two accepted costs, both measured and pinned rather than assumed:
  the map is keyed by year, so two lettered groups sharing a year disable each
  other's drops (a phantom survives — E's old behaviour, not a regression);
  and a letterless cite the parser also rejects has nothing to sight, which
  this mechanism cannot close.

  **Open review findings (2026-08-06) — close these before the live run.** F's
  fix re-review and an external second opinion (openai/gpt-5.6-sol) both
  cleared the Critical and approved the assignment module, but neither will yet
  certify the absolute "never drops a cited work" claim for the *resolver*.
  Between them: F's drop is one-shot, because the sighting scan matches over a
  pre-existing `## References` section and so sights every letter it just
  printed (over-retention, not loss, but `SKILL.md` tells the operator to
  re-run); a spurious continuation can still license a drop via `supported`;
  the documented "bare cite the parser also rejects" residual is a real Issue B
  path and is closable with a *scoped* bare-year sighting; and a stale
  **compact** `year_suffix` — one not opening its line, which
  `_strip_derived_fields` deliberately does not remove — can make a group look
  structurally complete and license a drop on stale data. That last one is the
  cross-item finding: the same position limit is harmless for `venue_status`,
  where nothing acts on the value, and is not harmless here.

  What then remains is **the live headless run** — F touches
  `agents/synthesis-writer.md` and `docs/conventions.md`, so writer compliance
  has to be observed, not assumed. It carries the five riders listed below.

  Original problem statement, kept because the flagship case is the acceptance
  test: scope is collisions where the works have the **same author**, which E
  cannot touch — nothing in the citation distinguishes them, so suffixes are
  the only fix. Flagship case:
  `extended-mind-cognitive-offloading` cites `Menary (2006, 2010, 2013)`
  while References lists **three** distinct solo-author Menary 2010 works
  (two chapters + the edited volume) — unresolvable for a reader, and two
  of the three are phantoms. Separately, 8/32 reviews contain prose cites
  like `Wiens (2015a; 2015b)` while **zero** reference lists carry a
  lettered entry, so the citation resolves to nothing (the mirror image of
  B). Writers were already trying to disambiguate; the renderer never emitted
  suffixes. The information is lost at write time, so suffixes are assigned on
  the merged bib *before* Phase 5, into a dedicated field — **not** `year`,
  whose `\d{4}` guards in `check_evidence.py` and `resolve_context.py` would
  reject `2019a`.

Order taken: A+B first (small, testable, deterministic), then E (same
shape, pairs with B) — **A, B, C and E are all FIXED/CLOSED as of
2026-08-05** (C closed-as-narrowed: write-protect + document) — then D,
**BUILT and CLOSED 2026-08-06** (mechanical vetting pass plus prompt rules),
then **F, BUILT 2026-08-06**. All six sub-items are now built; **the only open
work in item 3 is F's live run**, and that run should not
be entangled with the evidence-tier A/B experiment. Note the live run now
carries **five riders**: the year-coverage measurement (item 3 K —
measurement script ready at
`docs/known-issues/wrong-years-audit-data/year_coverage.py`, local-only), the
two-Johnsons writer note (**DONE 2026-08-05** — `docs/conventions.md` +
`agents/synthesis-writer.md`; the run confirms writer compliance), the
sentence-adverb guard fix (**DONE 2026-08-05** — E's
`_NON_INITIAL_PRECEDING_RE` no longer rejects a citation preceded by a
sentence-initial transition word), D's writer-compliance check, and D's own
live smoke test — the last two now that D is built. **Riders 4 and 5 need a
working `OPENALEX_API_KEY`; riders 1-3 and F's own check (are letters used in
the prose, and does the rendered References carry them?) need none**, so an
F-only run is possible while the key is sorted — record which riders it
covered. Rider 5 also absorbs D's task-2b question: the sanitized
`filter=display_name.search:` query's live recall on **punctuation-bearing**
venue names is unmeasured (the offline validation used comma-free names only,
and `:` / `|` are unsanitized in `filter=` values).

Related out-of-scope find (2026-07-28, recorded in the same write-up): 5/32
reviews carry near-identical *undeduped* entries surviving on diacritic
variance (`Milliere`/`Millière`) and arXiv-vs-journal pairs. Overlaps A but
is a distinct failure; not folded into A's scope. **Measured wider 2026-08-06**
while validating F: across 35 delivered reviews there are 117 same-surname,
same-year collision groups in the *final merged* bibliographies, and **30 of
them (25.6%) contain an undeduped duplicate pair** — same DOI
(`wiedenbrug2018citizens` / `wiedenbrug2018what`) or same title with no DOI
(`irving2018ai` / `irving2018safety`). So the residual is broader than the
diacritic cases alone. It is not currently harmful — F's letter filter simply
switches itself off for those groups, which is the safe direction — but it is
the measurement to act on if A is ever revisited.
Cross-repo: fixes land here or in the service's vendored engine and are
cherry-picked to the other side — same path as the metadata-cleaner year
fix (plugin 0.2.6 ↔ service `7369880`). The service tracks the mirror item
as roadmap item 23.

## 4. One owner for bibliography identity and matching — DONE 2026-08-03

**Landed 2026-08-03.** `hooks/bib_identity.py` now owns `normalize_doi`,
`normalize_pages`, `normalize_journal`, `year_key`, `title_key` and
`fallback_key`, seeded verbatim from the hardened `metadata_cleaner` versions.
Every other site keeps its historic name as an **alias to the shared object**,
so call sites are unchanged and the anti-drift tests assert `is` identity rather
than a vacuous equality between two copies. Both symptoms are gone, verified
end-to-end through `bin/phillit-run`: the `Millière`/`Milliere` pair merges, and
a Greek-surname entry that was deterministically absent now appears in the
rendered References.

**Corpus measurement, 2026-08-03 — the two symptoms had very different
evidence behind them.** Scanning all 319 `.bib` files under `reviews/` (45
reviews, 8,494 first-author entries):

| symptom | first-author entries affected |
|---|---|
| divergent title key (the `Millière` class) | **174** — every non-ASCII surname keyed differently under the old `dedupe_bib` key |
| surname ASCII-folds to `''` (the References drop) | **0** |
| surname folds to punctuation-only (the follow-up below) | **0** |

So the dedup fix has a real, sizable footprint — `Côté-Bouchard` keyed as
`c t bouchard`, `García-Carpintero` as `garc a carpintero`, `Glüer-Pagin` as
`gl er pagin`. The References-drop fix has **never fired in this corpus**. It is
a real defect — deterministic and provable by reading the code — but it was
derived from code reading, not observed in a delivered review, and the
"two already-measured symptoms" heading in the historical section below is
loose on that point: only the first was measured (5/32 reviews). The drop fix
stands as cheap insurance against a proven-possible failure; this corpus is 45
reviews of largely Anglophone analytic philosophy, and a topic drawing on Greek
or Cyrillic first authors would plausibly hit it.

Scope was **six** sites, not the five originally listed. The sixth,
`dedupe_bib.extract_doi`, inlined its own prefix list missing `doi:` and bare
`doi.org/`, so `doi = {doi:10.1000/x}` keyed as `doi:10.1000/x` there and as
`10.1000/x` everywhere else — a cross-key duplicate dedup silently failed to
merge.

Decisions taken, so they are not silently reversed later:

- **The prose fold is deliberately NOT consolidated.**
  `generate_bibliography._normalize_for_matching` folds author-written review
  text, not two of our own keys. It keeps punctuation, and the 60-character
  `_MATCH_WINDOW` is sliced from whichever haystack produced a hit — this
  function's output (`norm_text`) or `bib_identity.translit_fold`'s output
  (`translit_text`, item 3 E Task 2, `fb6623e`, 2026-08-05, symmetric
  transliteration matching), both of which keep punctuation for the same
  reason — so swapping either for `title_key` would change citation
  matching for every review. Its docstring now says so, and the
  `_normalize_for_matching("Hübner") == "Hubner"` assertions in
  `tests/test_generate_bibliography.py` are the tripwire.
- **Casefold expansion is a fifth divergence axis**, beyond the four in the
  table below. `ß` carries no combining mark, so NFKD ignores it while
  `casefold()` expands it: `Straße` keyed as `stra e` / `strae` / `strasse`
  across the three old copies. The shared key adopts `strasse` (so `Straße` and
  `STRASSE` now merge), pinned by `TestTitleKey::test_eszett_expands_under_casefold`.
- **LaTeX-escape residue is recorded, not fixed.** `generate_bibliography`
  decodes LaTeX before keying while `dedupe_bib` reads pybtex fields raw, so an
  escaped-accent title still keys differently in the two. Unmeasured, and adding
  decoding to `title_key` would change the cleaner's API-vs-bib title matching —
  the surface that produced the year-corruption incident. Candidate follow-up.
- **`_SUBSTANTIVE_FIELDS` stays duplicated** — a constant, not a judgment, and
  `test_generate_bibliography_copy_in_sync` already catches drift.
- **The `lint_md.py` every-citation-resolves post-check landed 2026-08-05**
  (`03d2b6b`, item 3's residuals — see below): item 4 removed the
  *deterministic* drop mode; the near-miss class (transliteration
  divergences NFKD doesn't cover) was closed separately the same day by
  item 3 E Task 2 (`fb6623e`, symmetric transliteration matching) — both
  modes of Issue B are now closed.

One limit of the non-Latin fix remains, deliberate and documented in the code:
the year test is a substring match, so a non-numeric or bracketed year (`n.d.`,
`[2021]`) still cannot match in the script-preserving haystack.

**Two follow-ups fixed 2026-08-03** (Johannes's call, same session):

- **Punctuation-only surname folds.** The fallback originally triggered only on
  an *empty* ASCII fold, so a hyphenated non-Latin surname — which folds to `-`,
  not `''` — took the primary path and matched a garbage pattern (`\b-\b` hits
  essentially every inter-word hyphen), spuriously *including* the entry in
  References. The trigger is now "the fold retains no alphanumeric character",
  which covers `''`, `-` and `' '` alike. A partly-Latin surname
  (`Παπαδόπουλος-Smith` → `-Smith`) still takes the unchanged primary path.
  Pinned by `TestPunctuationOnlySurnameFold`, including the negative case: an
  uncited hyphenated non-Latin entry is no longer pulled in.
- **`_format_doi` rendered the RAW `doi` field**, so `doi = {doi:10.1000/x}`
  emitted the broken hyperlink `https://doi.org/doi:10.1000/x` into delivered
  References. Confirmed pre-existing (reproduced on stashed pre-change code).
  It now normalizes first; a URL that is not a known DOI prefix still passes
  through rather than being glued onto `https://doi.org/`. Note this lowercases
  the displayed DOI — resolution is case-insensitive, so it is display-only.

**Still open — NOT a one-line fix:** the LaTeX-escape residue above.
`generate_bibliography` decodes LaTeX before keying while `dedupe_bib` reads
pybtex fields raw, so an escaped-accent title keys differently in the two.
Closing it means either teaching `title_key` to decode LaTeX — which changes
`metadata_cleaner`'s API-vs-bib title matching, the surface behind the
year-corruption incident — or normalizing the inputs at one of the two call
sites. Needs its own decision, not a drive-by.

Historical record follows.

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
| `Η ηθική της τεχνολογίας` | `η ηθικη τησ τεχνολογιασ` | `''` | `'   '` (3 spaces, truthy) |

**This explains two already-measured symptoms whose cause was recorded as
unknown:**

- The `Milliere`/`Millière` undeduped pairs in **5/32 reviews** (item 3's
  out-of-scope find, above). `dedupe_bib._normalize_title` is the only one of
  the three that applies no Unicode normalization at all — a bare
  `re.sub(r"[^a-z0-9]+", " ", s.lower())`, so any non-ASCII letter becomes a
  space. The other two match these pairs correctly.
- A **new mode inside Issue B** (`bib-pipeline-integrity-gaps.md`): a
  first-author surname in a wholly non-Latin script ASCII-folds to `''`
  (titles fold to bare whitespace), and `generate_bibliography.py:417`
  (`if not norm_surname: continue`) then skips the entry, so a cited work is
  **deterministically absent** from the rendered References. Issue B's
  recorded fix directions (transliteration-aware normalization, fuzzy
  near-miss fallback) **do not cover this** — there is nothing to be near
  when the key is empty. An every-citation-resolves post-check in
  `lint_md.py` (Issue B's proposed check — built 2026-08-05, `03d2b6b`,
  after this decision was made) *would* cover it, which breaks the tie
  between B's two fix directions.

The `metadata_cleaner` versions are the hardened ones (item-13 B3 — item-13
is the gitignored bib-quality backport spec under `docs/superpowers/`; the
tag survives in code comments and `tests/test_item13_*.py` — fixed exactly
this ASCII-fold bug there and the fix was never propagated; its docstring
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

**Sequencing constraint dissolved 2026-08-02.** This was queued behind the
item-1 merge because `dedupe_bib.py` carried +180 branch-side lines and
refactoring first would have manufactured a conflict; the branch landed on
`main` (`f89f4de`), so this became ordinary main-side work. Historical
context: `docs/known-issues/evidence-tier-branch-divergence.md`.

**Service mirror outstanding.** The port to `phillit-service` is not done: it
needs `engine/.claude/hooks/bib_identity.py` plus the six import sites, and a
counterpart roadmap entry added via its **lowercase** `docs/roadmap.md` (the
git-add case trap). Its roadmap had no item-4 counterpart as of 2026-08-03.
Batched into the mirror session (working sequence above — after item 3,
before item 2), subject to its mirror-vs-fork decision.

## Backlog pointers

Other open items are tracked in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open (e.g.
`philpapers-rate-limiting.md` (re-scoped to Brave quota), and the
local-only `workflow-findings-softmax-review.md`).

**NEW 2026-08-06 — `json-unicode-escapes-leak-into-bibs.md`.** No script in
`skills/` or `hooks/` passes `ensure_ascii=False`, so search-result JSON
carries `\uXXXX` escapes and an agent that copies a venue name as text rather
than parsing it writes the escape into the bib. Three confirmed instances,
one of them in a **tracked, publicly-linked** example review. Found while
measuring LaTeX-escaped venue names for item 3 D; unrelated to D itself.

**If resuming an interrupted session, check the local-only
`docs/known-issues/doc-rot-audit-2026-08-02.md` first** — it carries the
agreed sequence with live checkboxes (extended + amended 2026-08-05).
Everything through the v0.3.1 push (steps 1–6b) is done; the 27-wrong-years
audit is done, and item 3's **A, B, C, D, E and F are all BUILT** (A/B/C/E
2026-08-05, C closed-as-narrowed; D and F 2026-08-06, each with a
whole-branch review and fix wave). What remains, in order: **F's live
headless run** — the last open piece of item 3, and the only one that needs
anything outside this repo — then the batched mirror session (with its
mirror-vs-fork decision), then item 2.

**Next session's scope: close F's open review findings (listed under item 3 F
above), then F's live run.** Riders 1–3 and F's own check need no API key;
riders 4–5 (D's writer compliance, D's live smoke test) need a **new**
OpenAlex key, since the existing one is unregistered rather than merely stale.

Note **nothing since v0.3.1 has been pushed**: v0.3.4 was committed but not
pushed, and D and F have had **no version bump at all** — decide the release
number at push time (check `git log origin/main..HEAD` rather than trusting a
count here).
