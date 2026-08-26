# PhilLit Roadmap

**Open engineering work only.** Detailed problem write-ups live in
`docs/known-issues/` (one file per issue, each with a Status line); design
sketches in `docs/ideas/`. Shipped work is deleted from this file rather than
marked done — the git log is the history. A decision that is still binding
belongs in `CLAUDE.md` or the owning module, not here.

Last release: **plugin v0.5.0**, 2026-08-25. Check
`git log origin/main..HEAD` for what is unpushed rather than trusting prose
here; a stale claim about that has been written into this file twice.

## Working sequence

The queue is the four findings from the service's 2026-08-25 intake reviews
(next section). Items 14 (the cleaner strip-rule fix) and 15 (barrier
abstract re-corroboration) — transferred from the service 2026-08-25 (its
commit `892b4ce`, which retired its item 23) — SHIPPED the same day as
v0.5.0; their problem statements, measurements, gate results and residuals
live in `docs/known-issues/cleaner-strip-rule-absence-vs-contradiction.md`
and `docs/known-issues/bib-pipeline-integrity-gaps.md` (Issue C).
Everything else in this file is a recorded residual, not work. (Section
numbers in this file are historical: numbers are never reused once an item
ships, so the sequence has gaps. Refer to items by name.)

**The service re-vendor at the v0.5.0 tip RAN 2026-08-25** (pin `fffb721`):
items 14/15 and the v0.4.9 prose fixes are now in the service's `engine/`;
its `docs/engine-provenance.md` Run record is the as-executed account (its
corpus gate reproduced this repo's item-14 measurements byte-exactly with
the hooks at the measurement commit). The
cross-repo rule — scripted re-vendor, never hand-mirroring — lives in
`CLAUDE.md`, "Sister repo: phillit-service".

## Findings from the service's fffb721 intake reviews (2026-08-25)

Five upstream-owned defects, found by the service's pre-run diff reviews and
by its 2026-08-26 acceptance run, verified against this repo's code at
`fffb721`; each reaches production by mirror once fixed here. In priority
order:

- **Corroboration streak-reset wart** (`evidence_barrier.py`,
  `_claimed_source_unprobeable`): an `openalex`-claimed entry with no DOI
  is not pre-classified unprobeable (the helper covers only keyless-`core`
  and DOI-less-`s2`), so it reaches `corroborate_abstract`, returns
  `SOURCE_EMPTY` with zero network, and RESETS the consecutive-transport
  streak — delaying the breaker during a real outage and burning deadline,
  which the `_CorroborationBudget` docstring says skips must not do. In the
  service the cost is elevated: no next-run heal, and the wasted deadline
  raises the barrier's 600 s Bash-kill probability with backgrounding
  disabled.
- **NDPR outage/empty conflation**
  (`enrich_bibliography.py::resolve_ndpr_abstract`): NDPR errors are
  swallowed to `(None, None)`, so a sitemap outage reads as `PROBE_EMPTY`
  and buckets `SOURCE_EMPTY` — telemetry cannot distinguish an outage from
  a genuine no-match, which makes NDPR demotion counts unattributable in
  any run report.
- **Operator-facing sentence in agent-facing prose**
  (`skills/literature-review/SKILL.md`, the `abstract_corroboration`
  paragraph): "…so set the key" instructs a reader who, in a headless run,
  does not exist and cannot set anything. Near-unreachable trigger (keyless
  CORE never produces a claimed-`core` abstract), but the sentence belongs
  in operator docs, not the skill.
- **`container-title[0]` ships a book chapter's SERIES as its `booktitle`**
  (`skills/philosophy-research/scripts/verify_paper.py:239-240`:
  `container = item.get("container-title", []); container_title =
  container[0] if container else ""`). CrossRef returns `container-title` as
  an ARRAY, and for a `book-chapter` it commonly holds both the series and
  the volume; taking `[0]` silently picks whichever came first. **Observed in
  production**, not inferred: the service's acceptance run
  `dbe0667370d74b4f` (2026-08-26) delivered `susser2013artificial` with
  `booktitle = {Studies in Applied Philosophy, Epistemology and Rational
  Ethics}` — the Springer series — while CrossRef's array for
  `10.1007/978-3-642-31674-6_21` is `["Studies in Applied Philosophy,
  Epistemology and Rational Ethics", "Philosophy and Theory of Artificial
  Intelligence"]`, the second being the actual volume. Low severity and **NOT
  an attestation failure** — DOI, publisher, title, authors and year are all
  correct and the entry keeps its tier — but a reader cannot find the book
  from what shipped, and a citation to it is not resolvable. **`[1]` is not
  the fix**: array order is not documented as series-then-volume, so the
  disambiguators worth using are the `series` field, `suggested_bibtex_type`,
  and the fact that a series name recurs across many unrelated DOIs while a
  volume title does not. Scope is `book-chapter` / `proceedings-article`;
  `journal-article` is unaffected in practice (journals rarely carry two
  container titles), so the fix should not disturb the `@article` path.
- **`docs/conventions.md` year-gate sentence overstates abstention**
  (long-standing; re-verified byte-unchanged at `fffb721`): "On any
  same-DOI year conflict the cleaner abstains from the entry entirely"
  overstates the scoped-settling branch — `find_api_entry_for_bib_entry`
  lets agreeing entry-scoped records settle a conflict with pooled records
  and abstains only otherwise.

## 2. Web-source evidence — ACCEPTED 2026-08-15; intaken by the service 2026-08-16; residual findings recorded

The `EVIDENCE-WEB` fetch gate shipped as v0.4.1 and **passed its live
acceptance run** (2026-08-15, one AI-adjacent headless review: five report
buckets exercised, 0/4 false promotions, the one `span_unverified` rejection a
true positive). Johannes accepted the item the same day. Audit record:
`docs/known-issues/item2-web-evidence-live-acceptance-2026-08-15.md`
(local-only). The run's findings shipped as the v0.4.2 riders: researcher
note-fidelity prose, the writer-prose note-license carve-out, the
verbatim-CHECK summary rule, and the `wayback_failed` report bucket.

Two owner decisions recorded 2026-08-15: v0.4.x stands (no revert/recall
despite shipping ahead of the gate), and the delivered bib **keeps**
`web_span`/`venue_status`/`year_suffix` (decision note in `sanitize_bib.py`'s
docstring — do not strip without a new owner decision).

The service handoff CLOSED 2026-08-16: the service re-vendored at pin
`0b9916a` and bumped its spec to v1.2, recording the five departures above
plus two its scope review found unrecorded — encyclopedia hosts in scope
(shipped 2026-08-17 as v0.4.3: the gate and `fetch_web.py` refuse SEP plus
its two mirrors, IEP, NDPR, and `philpapers.org`, settled as EXCLUDED
domain-wide), and the fact that the spec's
honesty-escalation trigger FIRED in the acceptance run (1 of 4 promoted
notes carried a fabricated attribution, with propagation) and was resolved
by the v0.4.2 prose riders, making that the measured baseline.

One import edge for whoever ports it: `web_evidence.http_get` reaches
`rate_limiter.user_agent` across skills via `sys.path`, following the precedent
`venue_vetting.py` set for `search_cache`. It works, but couples a
literature-review module to a sibling skill's layout. `fetch_web.py` now makes
the same cross-skill reach in the opposite direction (importing `web_evidence`
for the exclusion list); the seam is pinned by a clean-process subprocess
test.

Follow-up candidates from the service's 2026-08-16 whole-branch review and
its 2026-08-17 pre-deploy divergence audit — all decided in the 2026-08-18
walkthrough. The three accepted fixes shipped as v0.4.5 (charset decoding
in `fetch_web.py`, the restamp capture re-check in
`dedupe_bib.restamp_merged`, the `misc_with_abstract` report bucket, plus
two prose corrections in `conventions.md` and the researcher agent); what
remains recorded here are the decisions that did NOT produce code:

- **Direction-bound residuals — ACCEPTED 2026-08-18** (no corpus record
  exercises them): an EARLIER api year is trusted unconditionally; a bib
  deliberately citing a revised later edition on the first edition's DOI
  gets back-dated (consistent with trust-the-DOI, unstated in the
  researcher's reissue prose); `@proceedings`/`@booklet`/`@manual` sit
  outside `_REPRINT_CAPABLE_TYPES` on a coupling argument.
- **`wayback_failed` noise for an egress-denied consumer — decided
  2026-08-18: a service-side concern.** A distinct unreachable marker
  belongs in the service's consumer at its next touch; no change here.
- **No mechanical check polices WEB-tier characterization — kept as an
  open question, decided 2026-08-18 not to build speculatively.**
  `check_evidence.py`'s verb heuristics run only on `_LOW_TRUST_TIERS`, so
  the note-license boundary (measured 1-in-4 note-drift baseline) is held
  by writer prose alone. Extending the verb heuristic as-is would
  false-positive on legitimate note-licensed cites; whether any feasible
  mechanical check exists (e.g. note-vs-prose containment at Phase 6)
  remains open.

## 3. Bibliography-pipeline integrity fixes — closed except recorded findings

Sub-items A–K are all fixed or closed (A duplicate entries, B
every-citation-resolves, C ledger write-protection, and E collision-aware
matching on 2026-08-05; D venue vetting and F Chicago a/b disambiguation on
2026-08-06, each with a whole-branch review and fix wave; G–K cleaner/year
hardening by 2026-08-02; the first-initials gap — the writer instructed the
same-surname initial only when the years also matched — on 2026-08-09).
Issue C's forged-marker residual (Option 2, never built here) was
transferred back by the service on 2026-08-25 and shipped the same day as
item 15, barrier abstract re-corroboration (v0.5.0; record in
`docs/known-issues/bib-pipeline-integrity-gaps.md`, Issue C).
Problem statements and measurements:
`docs/known-issues/bib-pipeline-integrity-gaps.md` and
`author-year-collision.md`.

Sub-item F's (Chicago a/b disambiguation) live run and all five of its riders
are done; no defect it surfaced remains open (venue-name recall for subtitled
journals was measured and closed as a non-issue 2026-08-19 —
`docs/known-issues/venue-recall-subtitled-journals.md`). Record of the run and
the rider results:
`.superpowers/sdd/2026-08-07-item3f-live-run/plan.md` (local-only). A registered
`OPENALEX_API_KEY` is in place, so venue vetting runs.

A rendering residual from the web-source evidence item's live acceptance run
(2026-08-15), accepted
with reasons: **a half-cited suffix group leaves a dangling Chicago letter** —
the run's review cites "Thornley (2025b)" with no 2025a anywhere in the
document, because letters are assigned over the full bib before writing and
only one member got cited. Suppressing the letter at render time was designed
and REJECTED: prose-only suppression desyncs prose from References, and
rewriting the prose to the bare year makes the citation letterless over a
bib group that still holds both works — on the re-run that SKILL step 5
mandates, `_resolve_collisions`' protective keep-all branch then resurrects
the uncited sibling as a phantom reference, the exact class sub-item F
(Chicago a/b disambiguation) exists to prevent. Direction is benign
(cosmetic; prose↔References stay consistent; the delivered bib names both
works). Record: the live-acceptance audit doc.

One residual from the same corpus observation: prose can mix the straight and
curly apostrophe for one surname (`O'Neill` / `O’Neill`) within a single
document. The renderer and the linter are immune (both compare through
`bib_identity` folds, which unify `’` with `'`), but
`check_evidence.find_cites` builds its surname regex from the raw bib
character — a mixed-apostrophe document under-reports cites there. Direction
is benign on a recall-floor checker (false "uncited" telemetry, never a
block), so this is recorded, not queued.

### Open findings from the external reviews (2026-08-06) — none is a drop path

Both gpt-5.6-sol and kimi-k3 reviewed the whole branch. Four cited-work drop
paths were found and fixed; these remain, recorded rather than closed. Detail:
`.superpowers/sdd/2026-08-06-item3f-chicago-ab-suffixes/progress.md` and the
`external-review-*.md` files beside it (local-only).

- A surviving compact `venue_status` (one not opening its line, which the
  stripper cannot reach) is acted on by both planner and writer, so the
  documented strip asymmetry is not fully honest. (The *splice* half of this
  shape shipped 2026-08-13, `0434f55`: a swallowed or duplicate-producing
  venue_status splice now reverts and is reported. What stays open is the
  other half — a residual that survives the strip and is never re-flagged
  still reaches the planner.)
- The encyclopedia acquisition budget cannot bound a *hanging* fetch — it is a
  work-admission budget. Documented honestly rather than fixed; a per-article
  interrupt was declined for cross-platform reasons (`signal.alarm` is
  Windows-hostile and main-thread-only).
- `_strip_derived_fields` can match line-initially *inside* a multi-line braced
  value.
- `resolve_context._title_text` prefers a mangled parsed title over the raw
  line with no fallback, so a truncated parse can score **worse** than the IEP
  path's `parsed=None`. Follow-up recorded in
  `docs/known-issues/sep-bibliography-regex-hang.md`.
- **`rate_limiter.openalex_budget_exhausted` transient-429 suspicion —
  VERIFIED BENIGN 2026-08-18, closed.** The detector requires a 429 plus
  either a Retry-After above 300 s or an explicit budget phrase in the
  body; the one over-broad path (the generic "rate limit exceeded" body
  marker) costs at most one call's retries and is visibly reported, and
  tightening the marker list without empirical OpenAlex bodies would risk
  breaking real detection.
- **The cleaning ledger's `schema_version` — bumped 1→2 on 2026-08-25,
  exactly per the 2026-08-18 decision** (the strip-rule fix's telemetry
  keys were the next schema change): the cleaner writes 2, the barrier
  accepts {1, 2} and hard-rejects anything else, landed together.

## 4. One owner for bibliography identity and matching — residuals only

Landed 2026-08-03; the single-owner rule is recorded in `CLAUDE.md`. Three
residuals, all accepted:

- The LaTeX-escape title-key divergence (`generate_bibliography` decodes
  before keying, `dedupe_bib` reads raw) — ACCEPTED 2026-08-20 after
  measurement: 149 of 8,517 titled entries diverge (1.7%), with exactly one
  duplicate-detection disagreement in the whole local corpus, in an
  old-architecture review whose damage today's References-side decoded dedup
  would contain. The binding record and the do-not-decode rationale live in
  `bib_identity.py`'s module docstring; measurement scripts under
  `docs/known-issues/title-net-measurement-2026-08-20/` (local-only).
- A non-numeric or bracketed year (`n.d.`, `[2021]`) still cannot match in the
  script-preserving haystack — ACCEPTED 2026-08-18 (never observed in
  practice).
- A surname that folds to punctuation-only (`Παπαδόπουλος-Smith` → `-Smith`)
  still takes the unchanged primary path — ACCEPTED 2026-08-18. Never
  observed in the corpus (0 of 8,494 first-author entries).

Other open items live in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open.

The sibling filing (`engine-planner-recent-flag.md`, the planner prose naming
a `--recent` flag `s2_search.py` does not have) was fixed here in the
2026-08-07 doc-rot sweep, which also ran the gate that filing proposed —
every prose-named CLI flag in `skills/*/SKILL.md` and `agents/*.md` parsed
against the named script's argparse (two further defects found and fixed:
both NDPR usage rows, plus `check_setup.py`'s "(no options)"). That check is
now a standing test, `tests/test_prose_flags.py` (mutation-proven; its
docstring records the union-on-multi-script-lines and no-positionals limits).

**This file is the work queue.**
