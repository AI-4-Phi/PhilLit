# PhilLit Roadmap

**Open engineering work only.** Detailed problem write-ups live in
`docs/known-issues/` (one file per issue, each with a Status line); design
sketches in `docs/ideas/`. Shipped work is deleted from this file rather than
marked done — the git log is the history. A decision that is still binding
belongs in `CLAUDE.md` or the owning module, not here.

Last release: **plugin v0.4.2**, 2026-08-15. Check
`git log origin/main..HEAD` for what is unpushed rather than trusting prose
here; a stale claim about that has been written into this file twice.

## Working sequence

Nothing is being built in this repo. Item 2's service handoff closed
2026-08-16 (the service re-vendored at pin `0b9916a` and bumped its spec to
v1.2); what remains of item 2 is one owner decision — the encyclopedia-host
exclusion, below. The cross-repo rule — scripted re-vendor, never
hand-mirroring — lives in `CLAUDE.md`, "Sister repo: phillit-service".

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

## 2. Web-source evidence — ACCEPTED 2026-08-15; intaken by the service 2026-08-16 — one owner decision open

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
(below), and the fact that the spec's honesty-escalation trigger FIRED in
the acceptance run (1 of 4 promoted notes carried a fabricated attribution,
with propagation) and was resolved by the v0.4.2 prose riders, making that
the measured baseline.

Open — an owner decision, not a build:

- **Encyclopedia-host exclusion.** The spec's out-of-scope clause
  (encyclopedia-hosted `@misc` — SEP/IEP "have their own channel") was never
  implemented: the gate has no host filter and the researcher fetch
  obligation no carve-out; the acceptance run's own web population included
  4 SEP and 2 PhilPapers URLs. Here that means unthrottled SEP GETs
  (`fetch_web.py` takes no rate-limiter slot on any host, so SEP's 5 s
  crawl delay is bypassed); in the service it also bypasses the
  source-store courtesy layer, so the service carries an interim prose
  carve-out (its `researcher-service-constraints` unit: use
  fetch_sep/iep/ndpr for those hosts). Decide: land a host exclusion here
  (researcher-prose carve-out and/or barrier scope filter — the service's
  interim region then retires by mirror), or declare encyclopedia-hosted
  `@misc` IN scope deliberately and record it (the service then re-decides
  its carve-out with the egress question its item 24 owns).

One import edge for whoever ports it: `web_evidence.http_get` reaches
`rate_limiter.user_agent` across skills via `sys.path`, following the precedent
`venue_vetting.py` set for `search_cache`. It works, but couples a
literature-review module to a sibling skill's layout.

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
are done; the only defect it surfaced that is still open is item 6, venue-name
recall. Record of the run and the rider results:
`.superpowers/sdd/2026-08-07-item3f-live-run/plan.md` (local-only). A registered
`OPENALEX_API_KEY` is in place, so venue vetting runs.

A rendering residual from item 2's live acceptance run (2026-08-15), accepted
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
- **Suspicion, unverified:** `rate_limiter.openalex_budget_exhausted` may read
  a transient 429 as daily exhaustion.

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

Other open items live in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open, e.g.
`philpapers-rate-limiting.md` (re-scoped to Brave quota) and the local-only
`workflow-findings-softmax-review.md` (findings 2 and 4, plus 3's residual).

The sibling filing (`engine-planner-recent-flag.md`, the planner prose naming
a `--recent` flag `s2_search.py` does not have) was fixed here in the
2026-08-07 doc-rot sweep, which also ran the gate that filing proposed —
every prose-named CLI flag in `skills/*/SKILL.md` and `agents/*.md` parsed
against the named script's argparse (two further defects found and fixed:
both NDPR usage rows, plus `check_setup.py`'s "(no options)"). That check is
now a standing test, `tests/test_prose_flags.py` (mutation-proven; its
docstring records the union-on-multi-script-lines and no-positionals limits).

**This file is the work queue.**
