# PhilLit Roadmap

**Open engineering work only.** Detailed problem write-ups live in
`docs/known-issues/` (one file per issue, each with a Status line); design
sketches in `docs/ideas/`. Shipped work is deleted from this file rather than
marked done — the git log is the history. A decision that is still binding
belongs in `CLAUDE.md` or the owning module, not here.

Last release: **plugin v0.3.5**, pushed 2026-08-06. Check
`git log origin/main..HEAD` for what is unpushed rather than trusting prose
here; a stale claim about that has been written into this file twice.

## Working sequence (Johannes)

1. **ONE batched phillit-service mirror session**, which opens with a decision:
   the two trees have drifted far enough that it may conclude they should be
   developed separately rather than mirrored. Until that session mirror debt
   accumulates deliberately — don't mirror piecemeal, and don't touch or push
   `phillit-service` outside it.
2. **Citation-year correctness for editions and search-verified works** (item 5
   below) — approved 2026-08-07 to land *after* the mirror-vs-fork decision,
   because that decision determines whether it has to be ported at all. Its
   position relative to web-source evidence is my reading of "after the mirror
   session", not something Johannes ruled on; swap freely.
3. **Web-source evidence** (item 2 below).

**Naming-rule debt** (rule in `~/.claude/CLAUDE.md`: every roadmap-item
reference carries its descriptive name, never a bare symbol): this file,
`CLAUDE.md`, and the skill/agent prose were named by hand in the 2026-08-07
doc-rot sweep. The tracked known-issue write-ups, `ARCHITECTURE.md`, and
`permissions-guide.md` still carry bare sub-item symbols (`3E`, `item 3 D`,
...) at roughly 30 sites — name them as those files get touched. Do it by
hand: a mechanical pass was attempted 2026-08-06 and reverted because the
references sit inside sentences that need rewording around the name.

## 1. Evidence-tier citability — service port only

Merged here and released as v0.3.0; **what remains is the phillit-service
port** (the service's roadmap item 20, its evidence-tier port — batched into
the mirror session and contingent on its mirror-vs-fork decision). The port-scope list lives in the service's
roadmap and must survive the port: the widened `check_evidence._VERB_RE`, the
SEP `–––` repeated-author resolution in `resolve_context`, and Option C
abstention attestation. Sister-repo instructions:
`docs/known-issues/phillit-abstention-attestation-decision-2026-08-02.md`
(local-only).

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
  (free runs), then port. The service's roadmap tracks the mirror as its item
  24, web-source evidence. The
  mirror session's mirror-vs-fork decision determines whether the "dual-repo"
  framing still holds.

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
surfaced (now item 5, citation-year correctness, and item 6, venue-name
recall):
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

### Cross-repo: open the mirror session with the SEP regex hang

`phillit-service` still carries the catastrophically-backtracking regex at
`engine/.claude/skills/philosophy-research/scripts/fetch_sep.py:67`. It is the
only **live blocking** defect in the mirror backlog rather than a divergence: a
review that hits it burns up to arq's 90-minute `job_timeout` before the user is
refunded, and that repo bills every run. `review_max_turns` does not bound it —
a subprocess wedged inside one Bash call consumes no turns.

**Port the parser rewrite only.** The companion deadline commit patches
`resolve_context.py`, which that engine does not have (it predates the
evidence-barrier work, so it also has no `evidence_barrier.py`,
`year_suffix.py` or `venue_vetting.py`). That engine also has a second exposed
call site this repo lacks in the same form — `get_sep_context.py` imports
`fetch_sep_article` directly. Written up there in
`docs/known-issues/sep-bibliography-regex-hang.md` plus a `docs/roadmap.md`
table row (committed there 2026-08-07, `73f0da1`/`a4aceb1`).

Also in the mirror backlog: the `bib_identity` port, the evidence-tier port
(item 1 above), the collision-aware-matching port (**start from `970b117` or
later, never `e5e863a` or `e5cb717` alone** — `970b117` fixes a left-anchor gap
in `_CITE_INSTANCE_RE` and requires bib-record corroboration before a
second-position sighting can drop a group; earlier commits in that range get
both wrong), and the deferred `rate_limiter` fix.

Porting specifics worth having before that session starts:

- **Derive `bib_identity`'s import sites at port time — the recorded count has
  gone stale twice** (five, then six). As of 2026-08-07 it is **seven modules**:
  `metadata_cleaner`, `dedupe_bib`, `generate_bibliography`, `stamp_evidence`,
  `verify_paper`, plus `lint_md` and `year_suffix`, which postdate the old
  count. `grep -rn 'from bib_identity import' skills hooks` is the authority.
- **Do not copy the import-path arithmetic.** That engine's scripts sit under
  `engine/.claude/`, so the `parent.parent.parent.parent / "hooks"` hop in the
  cross-directory import blocks must be re-derived.
- Also mutatis mutandis: the `rate_limiter.py` lazy user-agent fix and the
  `load_dotenv` additions.

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

## 5. Citation-year correctness for editions and search-verified works — two COUPLED defects

Found by the live run of item 3 F (Chicago a/b disambiguation), 2026-08-07,
each with a reproducible proof. **They must be fixed together: fixing 5 A (the
missing `published-print` request) alone makes 5 B (the reprint-edition
overwrite) strictly worse.** Sequenced after the
mirror-vs-fork decision. Full evidence:
`.superpowers/sdd/2026-08-07-item3f-live-run/plan.md`.

### 5A. The search path never asks CrossRef for `published-print`

`skills/philosophy-research/scripts/verify_paper.py:340` — the bibliographic-search
path's CrossRef `select` list requests `published` but not `published-print`. Item
3 K (cleaner/year hardening) put `published-print` first in `_YEAR_FIELDS`
(`:179`), but a field that was
never requested cannot be found, so `extract_year` falls through to `published` —
which CrossRef defines as the EARLIEST of print and online, i.e. the online-first
year.

Proved against the live API: with the current `select` only `published` comes back
(`2014-06-22`); adding `published-print` returns `published-print: 2015-02`; the
DOI-lookup path (no `select`) returns all three. Measured incidence on the fresh
run: 2 of 111 DOI-bearing entries (`vallier2014moral` bib=2014/print=2015,
`wiens2011prescribing` bib=2011/print=2012), both with `method:
bibliographic_search`.

**The cleaner's gate never declines here** — `_year_is_overwritable`
(`hooks/metadata_cleaner.py:241`) is a pure basis-membership test and
`_VERSION_OF_RECORD_BASES` (`:220`) already contains `published`. The record's
year simply *agrees* with the bib's wrong year, so there is no conflict to
resolve. That is worse than a refusal: the on-disk verify record positively
corroborates the wrong year.

Fix: add `published-print` (and `published-online`) to the `select` list.

### 5B. A reprint DOI's print year overwrites a book's real publication year

`rawls1999lawofpeoples` came out of the run carrying `year = "2001"` and
`METADATA_CLEANED: year:1999->2001`. *The Law of Peoples* is Harvard UP **1999**;
JSTOR registered DOI `10.2307/j.ctv1pncngc` against the 2001 paperback, so
CrossRef returns `year: 2001` with `year_basis: published-print` — the very basis
item 3 K (cleaner/year hardening) taught us to trust. Every component behaved as
designed and the result is a
canonical book misdated by two years.

It then **manufactured a spurious Chicago collision group**: the wrong year put it
in the same author-year bucket as *Justice as Fairness: A Restatement* (2001), and
F correctly lettered a collision that does not exist. So the prose cites a 1999
book as "Rawls 2001b".

Incidence 1 of 122 entries in the run, but the class selects for canonical
reprinted books — the highest-cited items in a philosophy review.

**Why the coupling is load-bearing**: the gate has **no direction or magnitude
bound**. Making print years available on the search path (5 A, the
`published-print` request) extends print-year overwrites to every
search-verified entry *including books*, amplifying 5 B (the reprint-edition
overwrite) from "books verified by DOI lookup" to "books, full stop". The direction bound — a
book's year must not be moved later — belongs in the same change. The verify
record already carries `type: monograph` / `suggested_bibtex_type: book`, so the
signal is available.

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

## Backlog pointers

Other open items live in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open, e.g.
`philpapers-rate-limiting.md` (re-scoped to Brave quota), the local-only
`workflow-findings-softmax-review.md`, and:

**`json-unicode-escapes-leak-into-bibs.md`** — no script in `skills/` or
`hooks/` passes `ensure_ascii=False`, so search-result JSON carries `\uXXXX`
escapes and an agent that copies a venue name as text rather than parsing it
writes the escape into the bib. Three confirmed instances, one in a **tracked,
publicly-linked** example review.

**One engine defect filed by phillit-service and still owned here** (write-up
in the service's `docs/known-issues/frontmatter-title-unvalidated-at-producer.md`;
verified still present upstream 2026-08-07):
**`assemble_review.py` writes the frontmatter `title` unvalidated** — no
length cap, no character screen. Measured consequence in the service (its
consumer rejects titles over 160 chars or containing Cc/Cf/Zl/Zp, and an
oversized title leaves raw YAML in the delivered review body); the plugin
path has no such consumer, so producer-side validation serves both. The
service's copy validates `--subfield` via a service-added `build_frontmatter`
(its `098a57f`, a cherry-pick candidate never sent here) — adopt or decline
that in the same decision.

The sibling filing (`engine-planner-recent-flag.md`, the planner prose naming
a `--recent` flag `s2_search.py` does not have) was fixed here in the
2026-08-07 doc-rot sweep, which also ran the gate that filing proposed —
every prose-named CLI flag in `skills/*/SKILL.md` and `agents/*.md` parsed
against the named script's argparse (two further defects found and fixed:
both NDPR usage rows, plus `check_setup.py`'s "(no options)"). That check is
now a standing test, `tests/test_prose_flags.py` (mutation-proven; its
docstring records the union-on-multi-script-lines and no-positionals limits).

**This file is the work queue.**
