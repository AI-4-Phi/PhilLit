# The INCOMPLETE Exclusion Is Unfollowable — and Fails in Both Directions

**Observed**: 2026-02-10 (this repo, Claude run) and 2026-07-24 (downstream
service, third-party-model runs)
**Severity**: High — affects every review; the rule provides no protection
where protection is most needed
**Status**: **SHIPPED — merged to `main` 2026-08-02 (`f89f4de`), released as
plugin v0.3.0**, and the service port arrived downstream with the scripted
re-vendor on 2026-08-08, so nothing remains open here. The build-here-first
plan below was executed: all 11 plan tasks done, the free Sonnet two-arm A/B
ran on "What are data?" (book-heavy, as this doc suggests), Johannes
adjudicated the rubric — final outcome "Works. Proceed." — and both merge
gates closed 2026-08-02 ((b) via a live validation run, (c) via the blind
coherence read; treatment preferred). **Everything below is the problem
analysis and design record** — read passages that sound like future work
("suggested test", "where the fix gets tested") as the plan that was
carried out, not as open work.

## Summary

`agents/synthesis-planner.md:74-77` tells the planner: *if keywords contains
`INCOMPLETE`, **DO NOT include in outline***. There is no importance
exception. `agents/synthesis-writer.md:92-96` then offers one — High-importance
`INCOMPLETE` entries may be "cite[d] cautiously using the `note` field" — but
the writer never gets the chance, because line 96 correctly observes that "the
outline should already exclude INCOMPLETE entries." **The writer's escape
hatch is dead code.**

The result is a rule that a competent agent cannot follow, because following
it means omitting canonical works. That produces two opposite failure modes,
both observed:

| | Behavior | Consequence |
|---|---|---|
| **Agent obeys** | Drops verified, on-topic sources for lacking an abstract | False claims of absence — the review asserts something has never been done while the evidence sits in its own bibliography |
| **Agent disobeys** | Cites `INCOMPLETE` entries anyway | The convention provides *zero* discipline — works are cited and characterized with no abstract, no provenance, and no caution |

**This repo exhibits the second mode.** The downstream service, running
weaker third-party models, exhibits the first. Same broken rule.

## Evidence — this repo (Claude): the disobedience mode

From `docs/known-issues/ndpr-enrichment-underused.md` (2026-02-10, "What are
data?" review, run 2), which documents the symptom without naming this root
cause:

- **~38 entries marked `INCOMPLETE`** across 7 domain BibTeX files in a
  single review. (This count predates the mechanical NDPR fallback added the
  same day — see "Why this is not just the NDPR issue". The *behavioral*
  finding below is unaffected by that fix; only the population size is.)
- The High-importance books were **not** enriched and stayed `INCOMPLETE`:
  Hanson 1958 (*Patterns of Discovery*), **Kuhn 1962 (*Structure of
  Scientific Revolutions*)**, Leonelli 2016 (*Data-Centric Biology*),
  van Fraassen 1980 (*The Scientific Image*), Popper 1959.
- That doc's own observation: *"In practice, all five books above were cited
  extensively in the final review… it means the INCOMPLETE convention is not
  functioning as designed."*

Its assessment — *"arguably the right outcome (these are essential works)"* —
is correct, and that is exactly the problem. A philosophy-of-science review
that omitted Kuhn would be worthless, so the agent overrode the rule. A rule
routinely overridden to produce competent output cannot be relied on to
prevent anything.

**Scope note, to keep the claim honest:** that doc records the *outcome*
(cited extensively), not which stage deviated. Whether the planner included
them despite line 75, or writers cited past an excluding outline, is not
established. Both stages need changing either way. It is likewise an inference
— not a documented finding — that those citations were characterized from
unverified `note` prose rather than from other evidence.

## Evidence — downstream service (weaker models): the obedience mode

From the service's `docs/non-anthropic-models.md`, item-15 rounds 1 and 2: a
`kimi-k3` run at low effort discarded an on-topic, correctly verified
experiment for lacking an abstract, then asserted the technique had **never
been tested with LLMs**. The refuting evidence was in its own bibliography.
The signature reproduced across two rounds and two topics.

Also relevant, and the reason any fix must not simply delete the rule: a
`deepseek-v4-flash` run **fabricated pseudo-abstracts on six canonical
entries**, presented as verbatim metadata with no provenance marker,
specifically to escape the exclusion. One propagated a false characterization
of a paper's central result into delivered prose. The rule is doing real
integrity work even while being unfollowable.

## Why this is not just the NDPR issue

`ndpr-enrichment-underused.md` proposes (Option A) automating NDPR fallback so
fewer entries are marked `INCOMPLETE`. **That option was implemented** —
`1a97b65` ("feat: add NDPR enrichment for books without abstracts") landed
2026-02-10, the same day the issue was filed; `8424551` narrowed it to
important books on 02-12; `6390794` improved matching on 07-19.
`enrich_bibliography.py::resolve_ndpr_abstract` runs mechanically today.

**So that doc's ~38-entry / 3-enriched figure describes the PRE-fix state, and
the current miss rate is unmeasured.** Treat the numbers as historical. Its
Option B — *"INCOMPLETE should not mean exclude"* — was never done, and is the
right instinct; the design below is a worked-out version of it.

**The unfinished half is SEP/IEP context.** `get_sep_context.py` and
`get_iep_context.py` appear in **no script** in this repo — only in
`agents/domain-literature-researcher.md`'s Stage 5.6 prompt, i.e. they are
agent-invoked exactly as NDPR was before it was automated. That matters
because SEP/IEP is the channel that covers canonical *articles* (Frankfurt
1971 and the like) and books NDPR never reviewed.

`bib-pipeline-integrity-gaps.md` **Issue C** (fabricated abstracts
indistinguishable from genuine ones) is the same problem viewed from the
integrity side: it notes that an entry with a fabricated abstract is "never
marked INCOMPLETE" and so "sails past the cite-cautiously rule." Any redesign
of the rule must address C, and the design below does — see "provenance
required" — but does not close it fully.

## The fix (shared design — build here, port downstream)

Full spec, including rejected alternatives and the reasons they were rejected:
`phillit-service/docs/superpowers/specs/2026-07-24-evidence-tier-citability-design.md`
(**v5.1, dual-repo** — it carries a path/line map for both trees), with four
external adversarial reviews committed alongside it (kimi-k3 and glm-5.2 on
v2; kimi-k3 on v3, folded into v4; gpt-5.6-sol on v4 — three blockers —
folded into v5 with the owner decision on positive-verification identity;
v5.1 descoped web-source verification to its own roadmap item — PhilLit
item 2 / service item 24).

**Core idea:** citability stops keying off `INCOMPLETE` and keys off an
explicit *evidence tier* recording what grounding an entry actually carries.
Each tier licenses a different **kind of claim**, so "we cannot characterize
this paper" stops meaning "we must pretend it does not exist."

| Tier | Entry carries | Synthesis may |
|---|---|---|
| `EVIDENCE-ABSTRACT` | `abstract` with **ledger-attested** `abstract_source` | cite normally — characterize, summarize, quote *from the sourced abstract text* |
| `EVIDENCE-CONTEXT` | `sep_context`/`iep_context` written by the barrier driver (sole author) | characterize **from that third-party description only**, attributed in prose; no direct quotation |
| `EVIDENCE-EXISTENCE` | identity **positively verified** — cleaning ledger records an API-record match, plus surviving `doi` (or `publisher` for `@book`/`@incollection`/`@inbook`) | existence and coverage claims only ("this has been studied experimentally (Smith 2020)"); never characterize the argument |
| `EVIDENCE-NONE` | none of the above — including no-API-match and circuit-breaker-skipped entries | not citable; stays in the `.bib` for transparency |

Net effect: **looser on coverage, stricter on characterization.** The tier is
computed by a script (`stamp_evidence.py`) and written as a literal token, so
no agent has to infer it.

**Requiring `abstract_source` is what addresses Issue C**: a fabricated
`abstract` with no provenance marker no longer unlocks characterization.

### Mechanical acquisition is part of the fix, not an optional extra

Canonical and classical works are **not covered in the bibliographic
databases**, and we are unwilling to ground claims about their content in
model knowledge — the downstream round-2 audit produced a confirmed
hallucination of exactly that kind (a citation to Paul Russell's 2017 book for
a thesis the book does not contain). If we want to say what Kuhn argued, that
content has to come from **other sources**: SEP, IEP, NDPR.

There is also a structural reason, and it is the load-bearing one: **a tier is
only as meaningful as the acquisition attempt behind it.** If acquisition is
best-effort and inconsistently applied, `EVIDENCE-EXISTENCE` means *"nobody
looked"* — and forbidding characterization of such an entry is arbitrary, so a
capable agent is right to override it. **That is the unfollowability trap
again, one level down.** Making acquisition exhaustive and mechanical is what
turns `EVIDENCE-EXISTENCE` into a real epistemic claim ("every channel was
tried, none yielded a description") and the restraint into a legitimate,
followable rule.

The design therefore mechanizes acquisition; Stage 5.6's agent loop is
**deleted**. As of v5 a single transactional driver (`evidence_barrier.py`)
runs **orchestrator-side at the Phase 3→4 barrier** — a script that exists to
eliminate agent-invocation flakiness must not itself be agent-invoked or fail
silently. It validates a manifest of per-domain inputs, then for every entry
lacking attested content evidence — **not just High-importance ones**, across
**all domains at once** — matches author + year **+ fuzzy title
corroboration** against the review's SEP/IEP entries, extracts body passages
around the disambiguated citation mentions, and attaches
`sep_context`/`iep_context` (sole author — pre-existing context fields are
stripped; ambiguous same-author-same-year candidates attach nothing).
Each encyclopedia article is fetched **once per review** and all candidates
match in memory (`fetch_sep.py` caches with a 7-day TTL, line 216-219), so
this costs less than today's loop. It emits `evidence_report.json`
(manifest state, matched/unmatched/ambiguous lists, the abstract-less
web-source count feeding roadmap item 2, all attestations) and stamps
**only after** acquisition completes; run-level failure exits nonzero and
stamps nothing.

The tier-2 / tier-3 decision then makes itself, with no judgment and no model
knowledge: any third-party description obtained → `EVIDENCE-CONTEXT`
(characterizable, attributed — Kuhn's path); none obtained → the work is
genuinely obscure, covered by neither databases nor encyclopedias. "Canonical"
is operationalized as *"described by an authoritative tertiary source"*.

**Why the coverage relaxation needs the gate.** Both external reviewers first
proposed the minimal version — "just stop excluding `INCOMPLETE` entries; cite
them for existence only." That is unsafe on its own: it is precisely the
relaxation that lets a *wholly fabricated* entry become a coverage anchor,
which today's blanket exclusion suppresses by accident. `EVIDENCE-NONE` is the
smallest mechanism that makes the relaxation safe. Do not ship the two-line
version without an identity gate.

## Catches we hit — check these before adapting

Several of these cost real rework downstream. All seven were verified
against code in **this repo** at the paths given, not merely carried over.

1. **Do not move `url` into `CLEANABLE_FIELDS`.** It looks like the obvious
   way to verify identity for DOI-less entries. It cannot work here: the
   cleaner normalizes every API record to a fixed schema (`title`,
   `container_title`, `volume`, `issue`, `pages`, `publisher`, `year`, `doi`,
   plus `year_basis` on CrossRef records since item 3 K, the cleaner/year
   hardening) in all its parsers (six since item 3 G of that same hardening
   added `parse_core_result`) — **there is no `url` key** anywhere in that
   file to match against. And `_field_matches_api`'s contract is that empty
   API values never match, so
   enabling it would strip URLs from every entry whose API record lacks one:
   a mass-strip that trips the circuit breaker
   (`hooks/metadata_cleaner.py:51-52`, `BREAKER_FRACTION = 0.30`) and skips
   **all** cleaning, including the DOI strips the design depends on. Use
   `publisher` for container types instead — it is already in
   `CLEANABLE_FIELDS` (line 43) and verified by the same path (line 563).
2. **A URL-liveness HEAD check is not a substitute.** Liveness is not
   identity (a live URL can point at a different work), and publisher hosts
   commonly block HEAD — this repo already documents IEP's 403-disguise
   behavior.
3. **The Kuhn test — run it before committing to any identity rule.** A
   DOI-only gate makes Kuhn 1962 `EVIDENCE-NONE`, i.e. **uncitable**, since a
   1962 monograph has no abstract and often no DOI in the harvested record.
   That is worse than today. The container-type `publisher` path exists
   precisely to prevent this. Whatever rule you adopt, test it against
   Hanson/Kuhn/Leonelli/van Fraassen/Popper from the NDPR issue before
   shipping.
4. **The circuit breaker opens a field-presence identity gate** — when it
   trips, the cleaner writes nothing (`applied_*` stay 0), so a fabricated
   `doi` or `publisher` survives; same for an entry that matched no API
   record (skipped, not stripped). **v5 closes this**: the cleaner emits a
   per-entry ledger and `EVIDENCE-EXISTENCE` requires a *positive* API-record
   match — no-match and breaker-tripped entries stamp `EVIDENCE-NONE`. The
   catch survives as a warning: never let "survived cleaning" stand in for
   "proved to exist".
5. **Strip `INCOMPLETE` when you stamp; do not leave both tokens in
   `keywords`.** The first draft kept `INCOMPLETE` for backward compatibility.
   An external reviewer flagged this as the single most likely reason an A/B
   test would show no movement: a model pattern-matching on the familiar
   token keeps discarding regardless of the new one. Safe to strip here —
   `NOTABLE_GAPS` reporting happens in Phase 3 before any stamp, and
   `dedupe_bib.py` computes `has_abstract()` directly rather than reading the
   flag.
6. **`_SUBSTANTIVE_FIELDS` in `skills/literature-review/scripts/dedupe_bib.py`
   omits `sep_context` and `iep_context`.** Today that silently loses
   encyclopedia context when merging cross-domain duplicates. Under a tier
   system it silently *demotes a tier*. Add both fields. *(Done —
   `dedupe_bib.py` on `main` includes both since the 2026-08-02 merge.)*
7. **Do not bundle the NDPR demotion.** Reclassifying `abstract_source = ndpr`
   as third-party context rather than an author abstract is defensible on this
   repo's own definition (`docs/conventions.md:151` — book-review prose,
   "not author/publisher abstracts"). It was cut from the downstream spec so a
   single A/B run could attribute its result. Given this repo's heavy book
   population, it deserves its own change and its own test. (v4 ships the
   interim one-liner instead: the writer prompt says NDPR-sourced abstracts
   are review prose, never to be quoted as the author's voice.)
8. **Every parallel researcher writes the same
   `intermediate_files/json/encyclopedia_entries.json`** — a last-writer-wins
   clobber race (`agents/domain-literature-researcher.md:161` and `:284`),
   pre-existing but harmless-looking until acquisition depends on the union
   of all domains' discoveries. v5 switches Stage 1 to per-domain filenames
   (`encyclopedia_entries-domain-N.json`, valid-empty required when none
   found) and has the barrier driver read them via an explicit manifest —
   no globbing, so stale or stray files cannot contaminate the match set.
   *(Done on the branch — researcher prompt + checklist write per-domain
   files there; `main` still has the single clobber-prone file.)*

## Residual — narrowed twice since this was written

**As filed (2026-07-24):** a fabricated `abstract` accompanied by a forged
`abstract_source` still grants full characterization rights, because
`abstract_source` is in `EXEMPT_FIELDS` (`hooks/metadata_cleaner.py`) and is
never checked against API data.

**That is no longer accurate, in two steps.** (1) The shipped tier does not
trust the field: `stamp_evidence.attest_abstract` requires the enrichment
ledger to carry the same source **and** the sha256 of the entry's current
abstract text, so forging `abstract_source` alone earns nothing — the ledger
has to be forged too. (2) ROADMAP item 3 C, ledger write-protection, was
re-scoped and closed-as-narrowed
on 2026-08-05: `hooks/block_ledger_write.py` plus two `PHILLIT_RULES` deny
rules now refuse native file-tool writes to both ledgers.

**What actually remains:** a *deliberate* forger who writes the ledger through
Bash, which no PreToolUse gate sees. That is documented as an accepted residual
and the real closure — barrier-side live corroboration, making the ledger a
cache rather than an authority — is routed to `phillit-service` item 23. Two
mechanisms were measured and rejected on the way (on-disk envelope
corroboration at 50.6% coverage; a Bash text gate). Current statement of all
of this: `bib-pipeline-integrity-gaps.md` Issue C.

## Where the rule lives in this repo

Verified against `main` on 2026-07-24. Note this repo's plugin layout has no
`.claude/` prefix; the downstream service vendors the same files under
`engine/.claude/`, and the prompt files are near-identical (4-16 differing
lines).

**Line-number caveat (2026-08-02):** `hooks/metadata_cleaner.py` has taken
~20 commits since this map was made (the 3G-3K hardening); every line number
in its row has drifted — locate by identifier instead (`CLEANABLE_FIELDS`,
`BREAKER_FRACTION`, `EXEMPT_FIELDS`, `_field_matches_api`). The prompt-file
rows re-verified exact on 2026-08-02.

| File | Lines | What |
|---|---|---|
| `agents/synthesis-planner.md` | 74-77 | The hard exclusion — the load-bearing edit |
| `agents/synthesis-writer.md` | 92-96 | The dead High-importance escape hatch |
| `agents/domain-literature-researcher.md` | 274-277 | "excluded from synthesis" + Stage 5.5 enrichment |
| `docs/conventions.md` | 175-184 | `INCOMPLETE` definition; `sep_context` example at 165 |
| `skills/literature-review/SKILL.md` | 204 | Phase 3→4 barrier — the natural single stamp point |
| `hooks/metadata_cleaner.py` | 43, 51-52, 61, 563 | `CLEANABLE_FIELDS`, breaker, `EXEMPT_FIELDS`, publisher check |
| `skills/literature-review/scripts/dedupe_bib.py` | `_SUBSTANTIVE_FIELDS` | The context-field omission |

**Stamp placement:** the design stamps **once**, orchestrator-run at the
Phase 3→4 barrier (SKILL.md:204) — and as of v5 acquisition
and the stamp are one transactional driver at that barrier, so
none of it depends on researcher compliance and a run-level failure stamps
nothing (fail-closed: unstamped entries read as `EVIDENCE-NONE`). Earlier drafts stamped at three
sites and needed a SubagentStop hook change; collapsing to one removed that
entirely, along with the staleness window and a Phase-5 concurrency hazard.
The barrier is downstream of every researcher's SubagentStop cleaning, so the
stamp sees final field values — **verify that a researcher whose SubagentStop
blocked on a BibTeX syntax error and then resumed still ends with cleaned
files**, since the single-stamp architecture assumes it. (v4 promotes this
from a footnote to a pre-merge checklist item.)

## Suggested adaptation for this repo

The downstream priority was coverage (weak models omitting sources). **Here
the priority is the opposite**: agents already cite `INCOMPLETE` works, so the
value is the *discipline* — tier limits, provenance requirement, and a
`note`-is-not-evidence rule — applied to ~38 entries per review that currently
get cited with none. Expect this change to **tighten** Claude's behavior, not
loosen it, and size the A/B accordingly: the question is whether enforceable
discipline degrades a review that currently benefits from ignoring the rule.

### This repo is where the fix gets tested

Reviews here run under **Claude Code**, not the Agent SDK, so a full test run
costs nothing — whereas the downstream service bills every run through the
API. That inverts the usual direction of travel: **build and validate here,
then port to the service's vendored `engine/.claude/`.**

It also settles an open objection cheaply. An external reviewer of the
downstream spec recommended *blocking merge* on a ~$22 Sonnet control run,
calling its absence "the riskiest line in the document" — the change touches
prompts used by the strongest model, yet was to be validated only on the
weakest. Running it here removes the cost, so there is no reason not to.

**Suggested test:** a book-heavy topic (philosophy of science) so the Kuhn
population is actually exercised. Check that canonical works land in
`EVIDENCE-CONTEXT` rather than `EVIDENCE-EXISTENCE`; that their
characterizations are attributed to SEP/IEP/NDPR rather than asserted flatly;
and that the review does not degrade into an annotated bibliography of
existences. Note the pass condition in advance — a mixed result is only
diagnosable if you fixed the criteria first.

### One caution on the `note` field

The design removes the `note` field's licence to support content claims at any
tier, on the grounds that it is LLM-generated prose exempt from every
verification pass. In this repo's book-heavy corpus that would strand the
canon — *if* it stood alone. It does not: mechanical acquisition is what
answers the objection, by routing those works into `EVIDENCE-CONTEXT` where
they can be characterized from real external evidence. **Do not adopt the
`note` tightening without the acquisition pass**; on its own it would make
this repo's reviews markedly worse.
