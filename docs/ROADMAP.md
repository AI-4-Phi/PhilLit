# PhilLit Roadmap

**Open engineering work only.** Detailed problem write-ups live in
`docs/known-issues/` (one file per issue, each with a Status line); design
sketches in `docs/ideas/`. Shipped work is deleted from this file rather than
marked done — the git log is the history. A decision that is still binding
belongs in `CLAUDE.md` or the owning module, not here.

Last release: **plugin v0.3.5**, pushed 2026-08-06. Check
`git log origin/main..HEAD` for what is unpushed rather than trusting prose
here; a stale claim about that has been written into this file twice.

## Working sequence (accepted by Johannes, 2026-08-08)

Intake status: the service's scripted re-vendor (`tools/revendor.py`, its
roadmap's item 26) **RAN 2026-08-08 at pin `08a3b3e`** — the full run, then a
same-day cleaner unification — so the mirror backlog is DRAINED and no
mirror debt accumulates anymore. Fixes land HERE and reach the service when
it re-runs the re-vendor at a later pin; never hand-mirror engine files
piecemeal. phillit-service work stays in sessions launched from that repo.

1. **Item 2, web-source evidence** (below) — spec-first.
2. **Item 7, reprint years at research time** (below) — small, or fold into
   other cleaner work.

**Naming-rule debt** (rule in `~/.claude/CLAUDE.md`: every roadmap-item
reference carries its descriptive name, never a bare symbol): this file,
`CLAUDE.md`, and the skill/agent prose were named by hand in the 2026-08-07
doc-rot sweep. The tracked known-issue write-ups, `ARCHITECTURE.md`, and
`permissions-guide.md` still carry bare sub-item symbols (`3E`, `item 3 D`,
...) at roughly 30 sites — name them as those files get touched. Do it by
hand: a mechanical pass was attempted 2026-08-06 and reverted because the
references sit inside sentences that need rewording around the name.

(Item 1, the evidence-tier service port, left this queue 2026-08-08: its
engine half arrived at the service with the re-vendor and the cleaner
unification; the remaining validation-then-deploy is service-side work,
owned by the service's roadmap item 20, its evidence-tier port.)

## 2. Web-source evidence — citability for `@misc`/url-only entries (dual-repo, spec-first)

Descoped from the evidence-tier spec in v5.1 (Johannes, 2026-07-24): every
abstract-less web source (blog posts, org reports, working papers not on arXiv)
stamps `EVIDENCE-NONE` and is uncitable — measured at **~3–17 entries per
AI-adjacent review, near zero for classic topics** (arXiv preprints get API
abstracts via normal enrichment and are unaffected). The evidence barrier's
report counts affected entries per run, so this item starts from data.

- A first mechanism (`verify_web.py` fetch-and-match) was cut from the spec
  after one round: no alternatives evaluation, A/B contamination, and naive
  fetching fails on the legitimate targets (JS-rendered pages, PDFs,
  bot-blocking hosts). Full autopsy: the spec's Cut section.
- **Spec-first** — brainstorm alternatives (researcher-side page capture,
  Wayback snapshot pinning, archive-fallback fetch, title-in-page match,
  existence-only citability, PDF extraction), decide the earned tier and
  licensed claims, then external review.
- **Dual-repo**: spec lives in the sister repo
  (`phillit-service/docs/superpowers/specs/`), build and validate HERE first
  (free runs); the built fix then reaches the service via its scripted
  re-vendor at a later pin. The service's roadmap tracks the arrival as its
  item 24, web-source evidence.

## 3. Bibliography-pipeline integrity fixes — closed except the first-initials gap

Sub-items A–K are all fixed or closed (A duplicate entries, B
every-citation-resolves, C ledger write-protection, and E collision-aware
matching on 2026-08-05; D venue vetting and F Chicago a/b disambiguation on
2026-08-06, each with a whole-branch review and fix wave; G–K cleaner/year
hardening by 2026-08-02). Problem statements and measurements:
`docs/known-issues/bib-pipeline-integrity-gaps.md` and
`author-year-collision.md`.

Sub-item F's (Chicago a/b disambiguation) live run and all five of its riders
are done. Record of the run, the rider results, and the three defects it
surfaced (the citation-year pair shipped 2026-08-09; the third is item 6,
venue-name recall):
`.superpowers/sdd/2026-08-07-item3f-live-run/plan.md` (local-only). A registered
`OPENALEX_API_KEY` is in place, so venue vetting runs.

### The first-initials gap — all that remains of this item

The writer does **not** carry first initials for same-surname different-author
cites. Observed live 2026-08-07: a review cited **Onora** O'Neill as
`(O'Neill 1987)` and **Martin** O'Neill as `(O'Neill and Williamson 2009)`, so the
solo cite is ambiguous to a reader. Chicago requires the initial here (the
co-authored cite is disambiguated by "and Williamson").

The Chicago a/b letters (sub-item F) do **not** address this — letters
disambiguate one author's several works in a year, initials disambiguate two
authors sharing a surname, and the two mechanisms are independent. Both
`agents/synthesis-writer.md` and `docs/conventions.md` DO instruct the initial,
but only for the same-surname *same-year* case, where reference rendering
itself breaks (both added 2026-08-05); nothing instructs it when the years
differ — the case observed, which renders fine and is ambiguous only to the
reader.

Sibling detail from the same corpus: prose can mix the straight and curly
apostrophe for one surname (`O'Neill` / `O’Neill`) within a single document, which
also matters to any surname-matching that keys on the raw character.

### Open findings from the external reviews (2026-08-06) — none is a drop path

Both gpt-5.6-sol and kimi-k3 reviewed the whole branch. Four cited-work drop
paths were found and fixed; these remain, recorded rather than closed. Detail:
`.superpowers/sdd/2026-08-06-item3f-chicago-ab-suffixes/progress.md` and the
`external-review-*.md` files beside it (local-only).

- The `venue_status` half of the silent-splice-failure bug. The `year_suffix`
  half is fixed (`78dd470`); `venue_status` has the same shape — a swallowed
  splice can be reported as success.
- A surviving compact `venue_status` (one not opening its line, which the
  stripper cannot reach) is acted on by both planner and writer, so the
  documented strip asymmetry is not fully honest.
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
- **Suspicion, unverified:** `rate_limiter.openalex_budget_exhausted` may read
  a transient 429 as daily exhaustion.

(The former mirror-session backlog — the SEP parser rewrite, the
`bib_identity` port, the evidence-tier port, collision-aware matching, the
`rate_limiter` fix — all arrived at the service 2026-08-08: the SEP rewrite
was hot-ported at the intake session, the rest with the re-vendor run at pin
`08a3b3e`. Nothing cross-repo remains under this item.)

## 4. One owner for bibliography identity and matching — residuals only

Landed 2026-08-03; the single-owner rule is recorded in `CLAUDE.md`. Three
things stay open:

- **LaTeX-escape residue — needs its own decision, not a drive-by.**
  `generate_bibliography` decodes LaTeX before keying while `dedupe_bib` reads
  pybtex fields raw, so an escaped-accent title keys differently in the two.
  Closing it means either teaching `title_key` to decode LaTeX — which changes
  `metadata_cleaner`'s API-vs-bib title matching, the surface behind the
  year-corruption incident — or normalizing the inputs at one of the two call
  sites.
- A non-numeric or bracketed year (`n.d.`, `[2021]`) still cannot match in the
  script-preserving haystack.
- A surname that folds to punctuation-only (`Παπαδόπουλος-Smith` → `-Smith`)
  still takes the unchanged primary path. Never observed in the corpus (0 of
  8,494 first-author entries).

## 6. Venue-name recall for subtitled journals — low priority, benign direction

`venue_vetting` resolves a bare venue name but not the subtitled form a bib may
carry. Controlled test, 2026-08-07: "Res Publica" resolves, "Res Publica: A
Journal of Moral, Legal and Social Philosophy" does not; same for Erkenntnis;
**0 errors either way**. So the previously-suspected injection risk from the
unsanitized `:` and `|` in `filter=` values is **unfounded** — that half of rider
5 is closed, not open.

Consequence is a silent no-op: vetting never evaluates such entries. Direction is
benign — the rule flags only venues that RESOLVE, so this yields false negatives,
never false low-visibility flags.

Incidence: 48 of 880 distinct journal names across the delivered corpus (5.5%)
carry a colon. **Not all of those fail** — many colons are part of the real venue
name ("Asiascape: Digital Asia"), which resolves; only OpenAlex-omitted subtitles
fail. The true failure fraction is unmeasured (~480 OpenAlex credits to settle).
Booktitles are 15.1% but vetting keys on `journal`, so that is likely moot.

## 7. Reprint years at research time — the seeding half of the reprint-year defect

The 2026-08-09 citation-year work fixed the CLEANER half: a reprint DOI's
later print year can no longer overwrite a book-class entry's earlier year.
The RESEARCH-TIME half remains: a researcher who verifies the reprint DOI
first seeds the reprint's year into the bib directly, the years then AGREE,
no licence is ever consulted, and the on-disk verify record corroborates
the wrong year (the pre-fix Rawls route, one step earlier). Found by the
2026-08-09 whole-diff review.

Mitigation shipped 2026-08-09: `agents/domain-literature-researcher.md` now
instructs preferring an earlier API-attested year for books/chapters. Open:
a mechanical producer-side signal — e.g. `verify_paper.py` stamping a
year-caveat on book-class records whose DOI registration postdates other
attested years — needs a design pass; prose alone is a soft control.

Other open items live in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open, e.g.
`philpapers-rate-limiting.md` (re-scoped to Brave quota), the local-only
`workflow-findings-softmax-review.md`, and:

**`json-unicode-escapes-leak-into-bibs.md`** — no script in `skills/` or
`hooks/` passes `ensure_ascii=False`, so search-result JSON carries `\uXXXX`
escapes and an agent that copies a venue name as text rather than parsing it
writes the escape into the bib. Three confirmed instances, one in a **tracked,
publicly-linked** example review.

The sibling filing (`engine-planner-recent-flag.md`, the planner prose naming
a `--recent` flag `s2_search.py` does not have) was fixed here in the
2026-08-07 doc-rot sweep, which also ran the gate that filing proposed —
every prose-named CLI flag in `skills/*/SKILL.md` and `agents/*.md` parsed
against the named script's argparse (two further defects found and fixed:
both NDPR usage rows, plus `check_setup.py`'s "(no options)"). That check is
now a standing test, `tests/test_prose_flags.py` (mutation-proven; its
docstring records the union-on-multi-script-lines and no-positionals limits).

**This file is the work queue.**
