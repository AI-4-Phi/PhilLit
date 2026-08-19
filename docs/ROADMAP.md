# PhilLit Roadmap

**Open engineering work only.** Detailed problem write-ups live in
`docs/known-issues/` (one file per issue, each with a Status line); design
sketches in `docs/ideas/`. Shipped work is deleted from this file rather than
marked done — the git log is the history. A decision that is still binding
belongs in `CLAUDE.md` or the owning module, not here.

Last release: **plugin v0.4.6**, 2026-08-19. Check
`git log origin/main..HEAD` for what is unpushed rather than trusting prose
here; a stale claim about that has been written into this file twice.

## Working sequence

Two items are queued, in this order:

1. **Venue-name recall for subtitled journals** — measure the true failure
   fraction, then decide.
2. **LaTeX accents key one title two ways** — its own decision session.

Both have their own section below, under those names. (Section numbers in this
file are historical: numbers are never reused once an item ships, so the
sequence has gaps. Refer to items by name.)

Everything else in this file is a recorded residual, not work.

**Cross-repo, needs a phillit-service session** (not doable from here): move
the service's re-vendor pin to the current tip. That single move picks up the
web-source evidence item's encyclopedia-host exclusion (v0.4.3), researcher
search batching (v0.4.4), the recorded-findings walkthrough fixes (v0.4.5) and
the conference-venue provenance fix, and it retires the service's interim
researcher-prose carve-out for the excluded hosts. The cross-repo rule —
scripted re-vendor, never hand-mirroring — lives in `CLAUDE.md`, "Sister repo:
phillit-service".

**Naming-rule debt** (rule in `~/.claude/CLAUDE.md`: every roadmap-item
reference carries its descriptive name, never a bare symbol): this file,
`CLAUDE.md`, and the skill/agent prose were named by hand in the 2026-08-07
doc-rot sweep. The tracked known-issue write-ups, `ARCHITECTURE.md`, and
`permissions-guide.md` still carry bare sub-item symbols (`3E`, `item 3 D`,
...). `ARCHITECTURE.md` (3 sites) and `permissions-guide.md` (1) are untouched;
the tracked known-issue write-ups hold ~44 sub-item references between them,
of which the 2026-08-09 sweep named those in the passages it edited — over
half remain, 18 of them in the deliberately-historical
`evidence-tier-branch-divergence.md`. Name the rest as those files get
touched. Do it by hand: a mechanical pass was attempted 2026-08-06 and
reverted because the
references sit inside sentences that need rewording around the name.

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
Problem statements and measurements:
`docs/known-issues/bib-pipeline-integrity-gaps.md` and
`author-year-collision.md`.

Sub-item F's (Chicago a/b disambiguation) live run and all five of its riders
are done; the only defect it surfaced that is still open is venue-name recall
for subtitled journals. Record of the run and the rider results:
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
- **The cleaning ledger's `schema_version` staying 1 through the Option C
  change — decided 2026-08-18: deliberate.** Recorded at the write site in
  `metadata_cleaner.py`; bump at the NEXT schema change (the barrier
  hard-rejects any other value, so a bump lands in both or neither).

## 4. One owner for bibliography identity and matching — residuals only

Landed 2026-08-03; the single-owner rule is recorded in `CLAUDE.md`. Three
things stay open:

- The LaTeX-escape divergence is promoted to its own item below, "LaTeX accents
  key one title two ways".
- A non-numeric or bracketed year (`n.d.`, `[2021]`) still cannot match in the
  script-preserving haystack — ACCEPTED 2026-08-18 (never observed in
  practice).
- A surname that folds to punctuation-only (`Παπαδόπουλος-Smith` → `-Smith`)
  still takes the unchanged primary path — ACCEPTED 2026-08-18. Never
  observed in the corpus (0 of 8,494 first-author entries).

## 6. Venue-name recall for subtitled journals — QUEUED: measure first, then decide

**Next step is a measurement, not a build** (Johannes, 2026-08-19). Settle the
true failure fraction (~480 OpenAlex lookups, see below), then decide whether to
fix, accept, or drop. Do not design a fix before the number exists — the
incidence figure that looks alarming (5.5%) is an upper bound that includes
colons which resolve perfectly well.


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

## 8. LaTeX accents key one title two ways — QUEUED: needs its own decision session

**Give this a session of its own** (Johannes, 2026-08-19). It is a decision
first and a patch second, and it must not be picked up as a drive-by inside
other bibliography work.

`generate_bibliography` decodes LaTeX before it builds a title key, while
`dedupe_bib` reads pybtex fields raw. So one title with an escaped accent
(`Milli\`ere`, `No\^{u}s`) produces two different keys depending on which module
is asking — the two modules can disagree about whether they are looking at the
same work.

Why it is a decision and not a patch: both available fixes move the code behind
the year-corruption incident.

- **Teach `title_key` to decode LaTeX.** One owner, one behaviour — but it
  changes `metadata_cleaner`'s API-vs-bib title matching, which is precisely the
  surface that mis-corrected years before. Any change here needs the same
  corpus-scale before/after measurement that work got.
- **Normalize the inputs at one of the two call sites.** Leaves `title_key`
  untouched and the blast radius small, but re-introduces the two-owners
  situation that `bib_identity` exists to end (see `CLAUDE.md`, single source of
  truth).

Scope note already recorded in `bib_identity.py`'s module docstring, which
states the divergence is deliberate and unmeasured. **Measure the incidence
first** — how many delivered entries actually carry an escaped accent in a
title — because if it is near zero the right answer may be to accept and record.

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
