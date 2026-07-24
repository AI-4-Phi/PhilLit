# Bibliography-Pipeline Integrity Gaps (four related issues)

**Observed**: 2026-07-24, via the downstream `phillit-service` model
experiments (three full reviews of its vendored engine snapshot,
adversarially panel-reviewed against a same-topic Claude Sonnet control run).
The vendored engine shares this repo's agents, cleaner, and consolidation
scripts, so the mechanisms transfer — file/line specifics below are verified
against **this repo's current `main`**, not just the snapshot.
**Severity**: Medium overall (per-issue below). None fails a run; all
silently degrade bibliography/References integrity — the part of the output a
reader is least able to audit.
**Status**: Open. See `docs/ROADMAP.md`.
**Cross-repo**: `phillit-service/docs/known-issues/bib-pipeline-integrity-gaps.md`
is the sister write-up with the full evidence pointers (its experiment
harness holds the artifacts). Fixes should land in one repo and be
cherry-picked to the other — same path as the metadata-cleaner year fix
(this repo's plugin 0.2.6 ↔ service engine commit `7369880`).

Architecture note for this repo: PhilLit runs interactively as a Claude Code
plugin — the cleaner fires via the `hooks/subagent_stop_bib.sh` SubagentStop
gate, consolidation and References generation are skill steps
(`skills/literature-review/scripts/dedupe_bib.py`,
`generate_bibliography.py`), and the orchestrating model is whatever the
user's session runs (normally an Anthropic model). Issues A and B are
deterministic script defects that apply to plugin runs **today**. Issues C
and D are missing safeguards: their observed exploits occurred under
non-Anthropic orchestrator models in the service's experiments, and Claude
models behaved honestly in the same runs — but the plugin has no control over
what model a user's session (or an `ANTHROPIC_BASE_URL` swap) actually runs,
and the safeguards are absent regardless of model.

---

## Issue A — dedup keeps the uncleaned copy of a cross-domain duplicate (cleaner verdicts discarded)

**Severity: Medium. Deterministic.**

`metadata_cleaner.py` runs per-domain at SubagentStop, judging each domain
bib against that domain's own search-cache JSONs — the same paper found by
two domain researchers (different citation keys) can be cleaned in one bib
and left uncleaned in the other. `dedupe_bib.py` then merges: first
occurrence per key, DOI-dedup across keys, prefer-the-copy-with-an-abstract
and higher importance (`merge_entries`). No criterion consults cleaner
outcomes (`METADATA_CLEANED` keywords, stripped unverified fields) — and a
cleaned copy is by construction *sparser*, so it systematically tends to lose
the merge to its unvetted duplicate.

Observed instance (service run `kimi-k3-loweffort-dde-r1`): the cleaner
stripped an unverifiable `booktitle = {International Conference on Learning
Representations}` from the domain-3 copy of a paper; dedup kept the uncleaned
domain-1 copy, and a chronologically impossible "Published at ICLR 2024"
claim (arXiv v1 postdates ICLR 2024) shipped in the final bib and the
rendered References.

Fix directions: make `dedupe_bib.py` propagate field removals and
`METADATA_CLEANED` verdicts across duplicates (a field one domain's evidence
flagged as unverifiable must not be resurrected by an unchecked copy); or add
a consolidated-bib cleaner pass over the union of domain JSONs — taking care
to keep the year-fix's conflicting-evidence-means-unmatched semantics, since
naive cross-domain pooling was exactly the year-corruption vector
(`metadata-cleaner-year-corruption.md`).

## Issue B — a cited work can silently vanish from the rendered References (surname-match failure)

**Severity: Medium-High for reader-facing impact. Deterministic.**

`generate_bibliography.py` builds References by matching in-text citations to
bib entries via surname+year proximity (`_MATCH_WINDOW = 60`, NFKD
diacritics-tolerant via `_normalize_for_matching`). A body/bib spelling
divergence that NFKD does not cover fails the match, and the cited work is
simply absent from the References. The script reports only the aggregate
"Matched X/Y BibTeX entries as cited" on stderr; nothing checks the converse
— that every in-text citation resolves to a References entry — so in an
autopilot run the omission is invisible.

Observed instance (service run `deepseek-v4-pro-dde-r1`): the review's anchor
study, cited seven times, missing from the delivered References. Body spelled
the author "Fraenken" (ae-transliteration), bib had "Franken" (NFKD of the
real "Fränken"); "fraenken" ≠ "franken" → silent drop. The writer introduced
the spelling divergence; the silence is the script's.

Fix directions: transliteration-aware normalization (ä→ae as well as ä→a,
ö/ü likewise) plus a fuzzy near-miss fallback; and a hard post-check —
`lint_md.py` is the natural home — extracting in-text author-year citations
and requiring each to resolve to a References entry, failing loudly
otherwise. The post-check also guards every future matcher gap.

## Issue C — fabricated abstract fields are indistinguishable from genuine ones (provenance not enforced)

**Severity: Medium (structural; observed exploit was under a non-Anthropic orchestrator).**

The Stage 5.5 enrichment script is the *intended* sole writer of `abstract` +
`abstract_source` fields (marking `INCOMPLETE, no-abstract` on failure), and
`agents/synthesis-writer.md`'s cite-cautiously rule keys on `INCOMPLETE`. But
nothing enforces the convention: a researcher agent can write an invented
abstract with no `abstract_source`, no validator flags it, and the entry —
never marked INCOMPLETE — sails past the cite-cautiously rule it should have
triggered.

Observed instance (service run `deepseek-v4-flash-dde-r1`,
refutation-confirmed against OpenAlex): six canonical philosophy/moral-
psychology papers carried model-written pseudo-abstracts presented as
verbatim metadata, in a bib whose other entries used the honest markers
correctly; two of the distortions (one inverting a paper's conclusion)
propagated into the delivered prose. Claude-based runs in the same experiment
used the honest path throughout.

Fix directions: a mechanical gate (cleaner or the SubagentStop validator) —
`abstract` present ⇒ `abstract_source` present with a resolver-known value,
else strip the abstract and mark INCOMPLETE (fail *toward* the existing
safety rule); optionally, spot-verify abstract text against the already-
fetched S2/OpenAlex records with a cheap similarity threshold.

## Issue D — no venue-quality vetting; predatory-venue papers can anchor claims

**Severity: Medium-Low as a defect, Medium as an output-quality risk.**

Verification establishes that a DOI exists and its metadata is correct;
nothing assesses venue quality, and CrossRef registration is purchasable. A
predatory-venue paper passes verification and nothing downstream requires the
writer to discount it.

Observed instance (service round 2, cross-run venue check): a paper from
"Advanced International Journal for Research" (confirmed predatory-profile:
self-assigned "Impact Factor 9.11", APC with the DOI sold as a paid add-on,
days-scale publication, no DOAJ/Scopus, no subject-competent editorial board)
entered every run's corpus through the same S2 retrieval path. The Claude
Sonnet control's researcher spontaneously annotated the venue discount in its
bib note and weighted the paper lightly; other orchestrators lost the caveat
and anchored claims on it. The good behavior exists as model behavior — not
as a pipeline guarantee.

Fix directions: cheap venue heuristics at verification time (DOAJ lookup,
CrossRef member age/volume, publisher flags) emitting a `VENUE_UNVETTED`-
style keyword; an agent-prompt rule making the researcher annotate venue
quality for unrecognized venues and the writer caveat reliance on flagged
entries — the same keyword-keyed pattern the INCOMPLETE rule already uses.
Full predatory-list curation is out of scope; flag-and-caveat is the goal.

---

## Verified-on-main file map

- `hooks/metadata_cleaner.py` — per-domain cleaning, invoked from
  `hooks/subagent_stop_bib.sh` (Issue A input)
- `skills/literature-review/scripts/dedupe_bib.py` — keep-first / DOI-dedup /
  abstract-preference merge, cleaner-unaware (Issue A)
- `skills/literature-review/scripts/generate_bibliography.py` — surname+year
  proximity matching, aggregate-only reporting (Issue B)
- `skills/literature-review/scripts/lint_md.py` — natural home for the
  citation↔References post-check (Issue B fix)
- `agents/domain-literature-researcher.md` Stage 5.5 +
  `agents/synthesis-writer.md` INCOMPLETE rule — the unenforced abstract
  provenance convention (Issue C)
- verification scripts / `metadata_validator.py` — where venue heuristics
  would live (Issue D)
