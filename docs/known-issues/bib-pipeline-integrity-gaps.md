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
**Status**: **A FIXED, B CLOSED, C CLOSED-AS-NARROWED — all 2026-08-05; D
re-scoped and its rule VALIDATED 2026-08-05, ready to build with nothing
blocking** (each issue's own section carries the detail; C's and
D's re-scope sections are the current statements — the "Fix directions"
paragraphs above them are preserved but superseded). Was: "Open overall (C
and D untouched)". **A is FIXED 2026-08-05; B is
CLOSED 2026-08-05** (citation-omission post-check plus symmetric
matcher-side transliteration both landed the same day; the fuzzy near-miss
fallback from B's original fix directions was never built and is not
needed — see Issue B below for what remains, all check-side known limits)
— see the per-issue status lines below and `docs/ROADMAP.md`. The
2026-08-02 sequencing constraint (fixes touching
`hooks/metadata_cleaner.py` or `dedupe_bib.py` had to wait for branch
`worktree-evidence-tier`) is gone: the branch landed on `main` the same day
(`f89f4de`, plugin v0.3.0) and the cleaner freeze is lifted — fixes are
ordinary main-side work again.
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
user's session runs (normally an Anthropic model). Issues A and B were
originally deterministic script defects that applied to plugin runs
unconditionally; that framing is now dated. **A is FIXED 2026-08-05.** B's
deterministic drop mode (the wholly-non-Latin-script skip) was fixed by
item 4 on 2026-08-03, its every-citation-resolves post-check landed
2026-08-05 so any remaining matcher gap is caught loudly rather than
shipping silently, and B's original near-miss matcher class (transliteration
divergences NFKD doesn't cover, e.g. "Fraenken" vs "Franken") is now FIXED
too — the matcher gained symmetric transliteration-fold matching the same
day (item 3 E Task 2, `fb6623e`), so that exact divergence now matches at
match time rather than merely being caught after the fact. **B is CLOSED.**
Issues C and D are missing safeguards: their observed exploits occurred under
non-Anthropic orchestrator models in the service's experiments, and Claude
models behaved honestly in the same runs — but the plugin has no control over
what model a user's session (or an `ANTHROPIC_BASE_URL` swap) actually runs,
and the safeguards are absent regardless of model.

---

## Issue A — dedup keeps the uncleaned copy of a cross-domain duplicate (cleaner verdicts discarded)

**Severity: Medium. Deterministic.**
**Status: FIXED 2026-08-05** (`fe46575`, `9ea5b97`, `a631d7a`, `7816d2a`).

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

Landed via the first direction, not the second. Mechanism: pybtex's `Writer`
round-trip emits fields in *quoted* form (`field = "value"`), not just
braced — the pre-existing merge-time field readers only matched the braced
form, so a cleaned copy's surviving `abstract`/`importance` fields were
invisible to `merge_entries` in the first place, independently of any
verdict-propagation logic (`fe46575`). With that fixed, `dedupe_bib.py` now
reads each duplicate's `METADATA_CLEANED` marker, strips the loser's flagged
fields from the union via surgical scanner-based text removal — not a pybtex
round-trip; a fix round (`a631d7a`) replaced an initial round-trip approach
after review found it corrupted single-braced corporate authors, and
replaced a `still_present` regex proxy with per-field failure reporting so
the marker can never claim a strip that didn't happen — blocks the merged
union from re-admitting a flagged field from either copy, and folds markers
across a two-hop transitive merge including fields absent on the transitive
winner (`9ea5b97`, fix round `a631d7a`). `generate_bibliography.py`'s own
References-side `find_cited_entries` dedup mirrors the same strip-and-
blocked-union logic, so the object-side rendering path cannot reintroduce
what the bib-side path just removed (`7816d2a`).

Accepted limitation: `dedupe_bib.py`'s regex-based value extractors
(`_field_value_re`, behind `_extract_keywords_value`, `has_abstract`, and
the keywords/abstract readers built on it) only handle one level of nested
braces in a field value; a double-nested value (`{a {b {c} d} e}`) is
invisible to them - the marker or abstract simply reads as not found rather
than erroring. `_remove_fields_text`'s own scanner is unaffected (it is a
genuine depth counter, not regex-limited to one level), as are the
pybtex-backed helpers (`_entry_fields`, `_fallback_key`, and everything in
`generate_bibliography.py`, which parses with pybtex throughout).

Three scoping residuals survive, surfaced by external review and
deliberately not fixed in this round — they bound what "FIXED" means here
rather than reopening the issue. (1) The marker records field *names* only,
not values or hashes, so a false-positive cleaner verdict (the cleaner
wrongly judges a genuine field unverifiable) taints that field for the work
across the whole run and cannot be overridden by a later, correctly-verified
copy of the same field — the future enhancement is recording removed values
(or hashes) in the marker, owned by `metadata_cleaner` (review Q1). (2) The
DOI-refusal branches — two copies with distinct, non-empty DOI sets — leave
both copies unmerged rather than reconciling them, so a fabricated DOI on
one copy keeps the verdict machinery from ever engaging on that duplicate
pair; pre-existing, not introduced by this fix (review Q2). (3) Value
conflicts on fields the cleaner never flagged still resolve by each merge
path's pre-existing, vetting-blind winner rule — `dedupe_bib.merge_entries`
(the on-disk merged bib) by has-abstract-then-importance-tag,
`generate_bibliography.find_cited_entries` (the References-rendering pass)
by substantive-field count — so a fabricated value on the winning copy can
still beat a verified value on the losing one, by either rule (review Q3)
— see the ROADMAP item 3 follow-up line for the "vetted beats unvetted"
refinement this implies.

Ordering note (M6), not a residual but worth stating:
`metadata_cleaner._apply_cleaned_marker` REPLACES a keywords field's marker
rather than appending to it, so a cleaner re-run on an already-merged
(dedupe_bib-consolidated) bib would erase a dedupe-folded marker outright.
This is reachable only via a post-Phase-6
researcher dispatch, since `hooks/subagent_stop_bib.sh` globs every `*.bib`
in the workspace regardless of pipeline stage. Nothing resurrects a
previously-stripped field at erasure time — the fields the folded marker
recorded as removed stay removed — but the marker's own removal record
would be gone, so a later duplicate merge could no longer see that this
entry was already vetted.

## Issue B — a cited work can silently vanish from the rendered References (surname-match failure)

**Severity: Medium-High for reader-facing impact. Deterministic.**
**Status: CLOSED 2026-08-05** — the every-citation-resolves post-check
landed (`03d2b6b`) and the matcher gained symmetric transliteration-fold
matching the same day (item 3 E Task 2, `fb6623e`). The fuzzy near-miss
fallback from the original fix directions was never built and is not
needed to close this — see "Issue B is CLOSED" below. What remains are the
documented check-side known limits (a)-(c), listed further down.

`generate_bibliography.py` builds References by matching in-text citations to
bib entries via surname+year proximity (`_MATCH_WINDOW = 60`; diacritics-
tolerant via `_normalize_for_matching`'s NFKD fold and, since 2026-08-05,
transliteration-tolerant via `bib_identity.translit_fold`/`ascii_variants`,
tried symmetrically against both a plain-NFKD and a transliterated haystack
— see the fix below). A body/bib spelling divergence that neither NFKD nor
the transliteration table covers still fails the match, and the cited work
would be absent from the References — but the omission is no longer silent
(see the post-check below). The script reports only the aggregate "Matched
X/Y BibTeX entries as cited" on stderr; nothing here checks the converse —
that every in-text citation resolves to a References entry — which is the
gap the post-check closes.

Observed instance (service run `deepseek-v4-pro-dde-r1`): the review's anchor
study, cited seven times, missing from the delivered References. Body spelled
the author "Fraenken" (ae-transliteration), bib had "Franken" (NFKD of the
real "Fränken"); "fraenken" ≠ "franken" → silent drop. The writer introduced
the spelling divergence; the silence was the script's. **This exact
divergence is now matched at match time** (symmetric transliteration,
`fb6623e`) — a re-run of the same input would resolve it directly, without
needing the post-check.

Fix directions were: transliteration-aware normalization (ä→ae as well as
ä→a, ö/ü likewise) plus a fuzzy near-miss fallback; and a hard post-check —
`lint_md.py` is the natural home — extracting in-text author-year citations
and requiring each to resolve to a References entry, failing loudly
otherwise. Both the transliteration-aware normalization and the post-check
landed; the fuzzy near-miss fallback did not (not needed — see below).

**Second mode, found 2026-08-02 — FIXED 2026-08-03 by ROADMAP item 4.** When the
first-author surname was in a wholly non-Latin script (Greek, Cyrillic),
`_normalize_for_matching` ASCII-folded it to `''` and
`generate_bibliography.py` (`if not norm_surname: continue`) skipped the entry
before any matching ran. The omission was *deterministic*, not a spelling
near-miss: transliteration tables and fuzzy fallback both need a non-empty key,
and there was nothing to be near.

The fix is additive — the ASCII path is entered first and unchanged, and only
the branch that used to `continue` gained behavior: a script-preserving key
(`bib_identity.title_key`) searched over the review text folded the same way.
Verified end-to-end: a Greek-surname entry cited in Greek prose now appears in
the rendered References.

**The every-citation-resolves post-check is now built** (`03d2b6b`):
`lint_md.py`'s `check_citations` extracts every in-text author-year citation
from the review body and requires each to resolve, word-boundary-strict on
the surname, to a line in the rendered References section — ERROR-level,
nonzero exit, so an omission that used to be invisible now fails the lint
step loudly. Resolution is deliberately more tolerant than the generator's
own matcher: transliteration variants (ä→a *and* ä→ae, generated on both
sides of the comparison), either year of a reprint form (`YEAR/YEAR`),
Chicago a/b suffixes, 1600s–2000s years (`Kant 1785`), comma-separated
multi-cites, and a fence-aware, last-heading-wins search for the
`## References` section. Output is cp1252-safe (the citation text — where
non-ASCII lives — is ASCII-backslash-escaped before printing), so the error
path itself cannot crash on Windows.

That transliteration tolerance operates on the RENDERED References text, not
the raw `.bib` — it widens what the check can match within an entry that
already made it into References, it does not reach back into the
generator's own match decision. So in the original observed instance (body
"Fraenken", bib "Fränken"), the entry never reached References in the first
place (the generator's matcher dropped it, per Issue B above) — the check
finds nothing to match against and correctly ERRORs on the citation. It
surfaces the drop loudly; it does not make the match succeed. **Note
(2026-08-05): this account is now historical.** The generator's matcher
gained symmetric transliteration-fold matching after this was written
(`fb6623e`), so re-running the exact Fraenken/Franken input today resolves
the entry directly at match time — the entry reaches References and the
post-check finds nothing to flag.

**Issue B is CLOSED 2026-08-05.** The transliteration-aware normalization
that resolves a "Fraenken"/"Franken" divergence *at match time* landed in
`generate_bibliography.py` (item 3 E Task 2, `fb6623e`) — symmetric, tried
in both directions, via `bib_identity.ascii_variants`/`translit_fold`. The
fuzzy near-miss fallback from the original fix directions was never built
and is not needed to close this: transliteration-table coverage plus the
loud post-check together mean a genuine near-miss (a misspelling the
transliteration table doesn't cover) now fails loudly at lint time instead
of vanishing silently, which was the reader-facing harm this issue tracked.
B's original tie-break — build the post-check regardless of the matcher
fix, since it catches every future matcher gap, not just this one — stands
vindicated on its own merits.

Known limits of the check itself, all deliberate rather than oversights.
(a) Same-author multi-year citations — `(Smith 2020, 2021)` — extract only
the first year-bearing citation (`Smith 2020`); the trailing `2021` is never
pulled out as a separate citation, so it is never checked. A safe-direction
silent miss, not a false ERROR — and the house style in `docs/conventions.md`
avoids the form anyway, since its Chicago table specifies `(Author Year;
Author Year)` for multiple citations (repeating "Author Year" in full), so a
compliant review never produces the shape the check can't see. (b)
Non-Latin-script citations are not extracted at all: `_SURNAME`'s character
class is Latin-plus-diacritics, so a wholly Greek or Cyrillic surname
(`Χάλμης 2020`) never matches the citation regex and so is never checked, in
either direction — safe-direction, and pinned by
`test_non_latin_citation_blind_spot_is_deliberate`. (c) Resolution matches a
surname token against the whole folded References *line*, not a parsed
author field, so a surname that appears only in another entry's *title* (not
its author list) on a line whose year happens to match can false-resolve a
citation that is not actually in the bibliography — accepted as a lenient
design that trades this narrow false-negative-on-error-detection risk for
staying regex-simple and never producing a spurious ERROR on a
correctly-formatted line.

One residual hole remains, deliberate and documented in the code (ROADMAP
item 4): the year test is a substring match, so a non-numeric or bracketed
year (`n.d.`, `[2021]`) still cannot match in the script-preserving
haystack. A companion hole this paragraph used to describe — the
script-preserving fallback triggering only on an *empty* ASCII fold, so a
punctuation-only fold (a hyphenated non-Latin surname folds to `-`) never
reached it and matched a garbage `\b-\b` pattern instead, spuriously
*including* the entry — was **FIXED 2026-08-03** (ROADMAP item 4's
follow-up): the trigger is now "the fold retains no alphanumeric
character," which covers `''`, `-`, and `' '` alike.

## Issue C — fabricated abstract fields are indistinguishable from genuine ones (provenance not enforced)

**Severity: Medium (structural; observed exploit was under a non-Anthropic orchestrator).**
**Status: RE-SCOPED 2026-08-05** — the evidence tier (item 1, v0.3.0) closed
three of C's four routes; the residual is exactly one thing, and it is not
what the "Fix directions" paragraph below describes. Read the re-scope
section first; the original statement of the issue is kept beneath it because
the observed exploit is still the only field evidence.

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

Fix directions as filed 2026-07-24 — **both are dead, see the re-scope**: a
mechanical gate (cleaner or the SubagentStop validator) — `abstract` present ⇒
`abstract_source` present with a resolver-known value, else strip the abstract
and mark INCOMPLETE (fail *toward* the existing safety rule); optionally,
spot-verify abstract text against the already-fetched S2/OpenAlex records with
a cheap similarity threshold.

### Re-scope, 2026-08-05 (post evidence-tier)

**What the tier already closed.** Verified in code on `main`, by identifier:

1. *No marker.* `stamp_evidence.compute_tier` grants `EVIDENCE-ABSTRACT` only
   when `abstract_source` is present **and** in `ATTESTED_ABSTRACT_SOURCES`
   (`{s2, openalex, core, ndpr}`) **and** `att.abstract_attested`. A
   fabricated abstract with no marker — the filed shape — now earns at most
   `EVIDENCE-EXISTENCE`, so it cannot be characterized. Fail-closed: an entry
   with no `EVIDENCE-*` token reads as `EVIDENCE-NONE` downstream.
2. *Marker present but unbacked.* `stamp_evidence.attest_abstract` requires
   the enrichment-ledger record to carry the same source **and** the
   `sha256` of the entry's current abstract text.
3. *Researcher-written abstract, honest path.*
   `enrich_bibliography.attest_prefilled_abstract` re-fetches from the APIs
   and attests a pre-filled abstract **only on hash equality** with the
   fetched text — so a fabricated abstract cannot be attested by the script,
   and post-attestation mutation is separately repaired by
   `evidence_barrier._heal_abstract` (also hash-gated).

**The residual, stated precisely.** The enrichment ledger
(`intermediate_files/json/enrichment_ledger-<bibstem>.json`) is a plain JSON
file inside the workspace, so it is agent-writable, and it is the attestation
authority. The code says so itself
(`enrich_bibliography.py:725-729`: *"NOTE the trust model: this file is
agent-writable and is the attestation authority for the zero-fetch fast
path"*). The whole attack is therefore three lines wide: write the fabricated
`abstract` + `abstract_source = s2` into the bib, **and** add a ledger record
holding that source and the sha256 of the fabricated text. Consequences, in
order: enrichment's prior-ledger fast path sees a matching hash and **skips
the fetch that would have refused attestation** (route 3 above never runs);
`attest_abstract` then passes; the barrier stamps `EVIDENCE-ABSTRACT`; the
writer may characterize and quote. Nothing else in the pipeline re-derives
the abstract's provenance from anything but that file.

**The governing criterion is failure direction, not cost.** Every candidate
mechanism must answer *"what happens to an honest entry when this fails?"*
before its price is discussed — because "strip or demote when corroboration
is absent" is a decision **already taken and closed**: sanitize-time
stripping of unattested abstract text was REJECTED on 2026-08-02
(doc-rot-audit step 3(ii)) after it was measured to suppress 7 correct
abstracts. A C mechanism of that shape is a re-litigation, not a fix.

**Measured, and it kills the filed second fix direction.** "Spot-verify
against the already-fetched S2/OpenAlex records" assumes the records are on
disk. They are not, for half the corpus: enrichment resolves abstracts
through live `resolve_abstract_for_entry` calls and never saves an envelope,
so the only on-disk corpus is the researcher's *search* output, which
covers whatever the searches happened to return. Scanning all 45 local
review corpora (2,121 distinct abstract-bearing entries in 319 bibs against
every `abstract` string in their own `intermediate_files/json/`, normalized
by `stamp_evidence.normalize_abstract_for_hash`, counting exact / substring /
superstring / 120-char-window hits as corroborated):

| `abstract_source` | entries | corroborated on disk | absent |
|---|---|---|---|
| `s2` | 970 | 775 (79.9%) | 195 |
| `openalex` | 846 | 201 (23.8%) | 645 |
| `core` | 96 | 16 (16.7%) | 80 |
| `ndpr` | 4 | 0 | 4 |
| *(no marker)* | 203 | 81 (39.9%) | 122 |
| **all** | **2,121** | **1,074 (50.6%)** | **1,047 (49.4%)** |

So on-disk corroboration is a coin flip overall and fails *most* OpenAlex
entries. Demote-on-absence would demote ~1,000 honest entries; warn-on-absence
would emit a warning that is wrong half the time, which is the
unfollowability trap one level down — the tier design's own stated reason for
mechanizing acquisition. **This mechanism is dead; do not revive it.** (Side
finding worth keeping: 203 of these entries carry an abstract with **no**
`abstract_source` at all, and two more carry non-canonical labels
(`semantic_scholar`, `editorial`). All pre-date the tier and all now
fail closed, which is route 1 working as designed on real data.)

**Surviving options.**

- **Option 1 — write-protect the ledgers (cheap, correct failure
  direction, partial closure).** The honest path writes both ledgers from
  inside Python (`_update_enrichment_ledger` and
  `metadata_cleaner.write_cleaning_ledger`, both tmp + `os.replace`), which no
  PreToolUse gate ever sees. So *no honest run writes a ledger through a
  Claude tool*, and a `deny` rule on `Edit(**/*_ledger-*.json)` in
  `PHILLIT_RULES` costs nothing, breaks nothing, and blocks the
  forgery's tool-write route outright. Note today's rules positively **allow**
  it: `Edit(reviews/**)` covers the ledger path, and deny beats allow. Does
  not close the Bash route (`Bash` is allowed broadly, by design) — a
  `_ledger-` needle in `hooks/fast_gate.sh` plus a Bash-command gate, in the
  shape of `block_background_bash.py`, would raise that bar too without
  touching the honest path.
- **Option 2 — barrier-side live corroboration (full closure, one extra
  enrichment-scale pass, small honest-demotion risk).** Make the ledger a
  cache instead of an authority: at the barrier, every `EVIDENCE-ABSTRACT`
  candidate must be corroborated by a live fetch whose text hash-matches. A
  forged ledger then buys nothing, because attestation is re-derived from a
  source the agent does not control. Cost is ~70-100 fetches per review
  (measured: 24-105 abstract-bearing entries per corpus), i.e. roughly a
  second enrichment pass; `_heal_abstract` already proves re-fetch + hash
  equality is achievable for honest entries (it repaired 7 mutated ones in
  the 2026-07-25 A/B run). The honest-demotion risk is real but small
  *within a run* (the abstract was fetched minutes earlier). One trap:
  treating a *failed* fetch as "attestation intact" is the tempting
  honest-friendly variant and it defeats the point — the observed exploit
  targeted **canonical works with no API abstract**, which is exactly the
  case where the fetch returns nothing.
- **Option 3 — sampled corroboration, warn-only (detection, no closure, no
  honest cost).** Live-corroborate a random 20-30% of attested entries and
  report mismatches in `evidence_report.json` without touching tiers. At 20%
  a 6-entry fabrication is caught with p≈0.74, at 30% p≈0.88. Costs a
  fraction of Option 2 and cannot demote anything honest; catches systematic
  fabrication, not a single entry.
- **Option 4 — accept and route.** PhilLit runs under Claude Code; the
  observed exploit was `deepseek-v4-flash` under a non-Anthropic
  orchestrator, and Claude runs in the same experiment used the honest path
  throughout. The tree with arbitrary-model exposure is `phillit-service`
  (its roadmap item 23). Declare C narrowed-and-accepted here and carry the
  mechanism as a service item.

Options 1 and 4 compose (write-protect + document the rest); so do 1 and 3.
Option 2 is the only one that closes the hole, and it is the only one that can
demote an honest entry.

**DECIDED and BUILT 2026-08-05 (Johannes): Option 1 + 4.**
`hooks/block_ledger_write.py` is a PreToolUse gate on **Write, Edit and
NotebookEdit** (needle `_ledger-`, via `fast_gate.sh`) that denies a write
whose `file_path` basename starts with `enrichment_ledger-` /
`cleaning_ledger-` and ends `.json`; two `deny` rules
(`Edit(**/enrichment_ledger-*.json)`, `Edit(**/cleaning_ledger-*.json)`) went
into `PHILLIT_RULES` as belt-and-braces. Both mechanisms ship because they
cover different populations: the permission rule only reaches workspaces that
have re-run `/phillit:setup`, while the hook ships with the plugin. All three
matchers are needed because hook matchers dispatch by **tool name** — unlike a
permission rule, an `Edit` matcher does not also receive `NotebookEdit`.
Verified end-to-end through `fast_gate.sh` → `bin/phillit-run`: denied inside
a workspace, silent no-op outside one, and a sibling `s2_*.json` write never
even starts uv. 1360 tests green.

**Scope, stated as the external review insisted.** This denies *native
file-tool* writes. It is **not** a security boundary: `Bash` is allowed
broadly by design, so `cat >`, a heredoc or `python -c` writes a forged ledger
without passing any PreToolUse gate. Against a deliberate forger — already
fabricating an abstract, a source marker and a matching SHA-256 — losing the
easiest route is not an escalation. The honest claim is incidence reduction
against accidental edits and tool-default behaviour. Related accepted
residuals, all requiring Bash to set up: a file symlink or hard link whose
basename is innocuous, and a check-then-open race. Also unverified: the
permission-glob syntax against a live Claude Code matcher — `--dry-run` proves
only that the strings were serialized, so the hook is what this relies on.

Two review recommendations were **deliberately not taken**, with reasons:
requiring the `intermediate_files/json/` authority path in the match (a
relative `file_path` written from inside that directory carries no such
prefix, so path-anchoring would open a one-word bypass; over-blocking a
same-named file elsewhere is the cheaper error), and narrowing the deny globs
to that path for the same reason. Two were: the gate now **fails closed** on
an unreadable payload (it is an accuracy gate, and the earlier draft
advertised "fail open but loud" while actually failing open *silently* — the
`|| echo` fallback fires only on a nonzero exit), and `fast_gate.sh`'s needle
match became case-insensitive, which also closed a pre-existing hole where a
`.BIB` write skipped BibTeX validation entirely on case-insensitive
filesystems.

**Option 2 is NOT built** and stays routed to the service. Option 3 (sampled
warn-only corroboration) was not taken either — it remains the cheapest way to
turn "never observed under Claude" into a measured claim if that question
becomes live. The review also proposed a fourth shape worth recording: fuse
enrichment and stamping into one trusted process and treat the persisted
ledger as a *cache* rather than an authority, re-corroborating only entries
that came through the prior-ledger fast path. That could close most of the gap
without Option 2's full second pass, and is the better design if this is ever
built here rather than in the service. (Signing the ledger was considered and
rejected: a same-user local signer callable by the agent is another forgeable
oracle, not a boundary.)

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

Fix directions as filed 2026-07-24 — **the named signal is the wrong one, see
the re-scope**: cheap venue heuristics at verification time (DOAJ lookup,
CrossRef member age/volume, publisher flags) emitting a `VENUE_UNVETTED`-
style keyword; an agent-prompt rule making the researcher annotate venue
quality for unrecognized venues and the writer caveat reliance on flagged
entries — the same keyword-keyed pattern the INCOMPLETE rule already uses.
Full predatory-list curation is out of scope; flag-and-caveat is the goal.

### Re-scope, 2026-08-05 (measured against the real corpus)

Two things in the filed direction are stale. The mechanism was to be keyed
"the same keyword-keyed pattern the **INCOMPLETE** rule already uses" — item 1
deleted that pattern in favour of evidence tiers, so D needs its own home
(see *Where the flag lives*, below). And the named signal does not work.

**DOAJ is the wrong index.** DOAJ lists *open-access* journals only.
Philosophy's flagship venues are subscription-based — `Mind`, `Noûs`,
`Philosophical Review` are all `is_in_doaj: false` — so DOAJ-absence carries
no information about a philosophy venue and would flag the entire discipline.
`is_indexed_in_scopus`, the obvious substitute, is now returned as `null` by
the OpenAlex API and cannot be used either.

**The nearest usable single signal produces false discredits — measured.**
OpenAlex's curated `is_core` flag does separate the observed predatory venue
from `Mind` (`Advanced International Journal for Research`: `is_core false`,
h-index **2**, 2-year mean citedness 0.028 / `Mind`: `is_core true`, h-index
162, citedness 1.50). But over the 120 most-frequent venues in this repo's 45
review corpora (3,938 entries), `is_core false` fires on **7 venues, and every
one of them is reputable**:

| venue | h-index | entries |
|---|---|---|
| Journal of Moral Philosophy | 46 | 34 |
| Political Theory | 117 | 20 |
| Contemporary Political Theory | 81 | 19 |
| Proceedings of the AAAI/ACM Conf. on AI, Ethics, and Society | 32 | 18 |
| Jurisprudence | 23 | 11 |
| South African Journal of Philosophy | 37 | 11 |
| Oxford Journal of Legal Studies (tail sample) | 82 | 4 |
| Phronesis (tail sample) | 86 | 2 |
| Kantian Review (tail sample) | 42 | 2 |

`is_core` is a coverage set, not a quality judgment, and it under-covers
humanities journals. **A single-signal `is_core` rule is therefore
prohibited**: stamping `VENUE_UNVETTED` on *Phronesis* would both insert a
false discredit into scholarly output and teach the writer to ignore the flag
— the unfollowability trap that item 1 exists to avoid.

**D does have real targets in this corpus** (this corrects a first draft of
this re-scope, which inferred "fires on nothing" from the top-120 stratum —
the one stratum that structurally cannot contain a predatory venue). A free
local name-shape scan of all 928 distinct journal names surfaced these, each
appearing in 2 entries:

- **`Advanced International Journal for Research`** — the *same venue* as the
  service-experiment observation, now confirmed present in PhilLit's own
  corpora
- `Advanced Research Journal`
- `Edumania-An International Multidisciplinary Journal`
- `Global Multidisciplinary Perspectives Journal`
- `International Journal of Multidisciplinary Research and Analysis`
- `International Journal of Innovative Research in Computer and Communication Engineering`
- `International Journal of Advanced Computer Science and Applications`
- `Engineering and Technology Journal`, `ICTACT Journal on Soft Computing`

The same crude name patterns also catch legitimate venues (*International
Journal of Philosophical Studies*, *THEORIA*, *International Journal of
Applied Philosophy*, *IJ Social Robotics*, *IJ Constitutional Law*), so the
name shape is a *scan heuristic for this re-scope only* — never the ship rule.

**The rule, validated 2026-08-05.** Three conjoined signals, because the
separation is in citation impact rather than index membership — and because
DOAJ turns out to be genuinely useful once its **polarity is inverted**:
worthless as a negative signal (absence says nothing about a subscription
journal), but a sound *positive rescue* (presence means a vetted OA journal):

    flag VENUE_UNVETTED  iff  venue resolves in OpenAlex
                         AND  is_core is false
                         AND  is_in_doaj is false
                         AND  h_index < 15
    never flag an unresolved venue (absence of a match is absence of evidence)
    evaluate over the BEST same-named source, by h-index

That last clause matters: OpenAlex can hold several sources sharing a
`display_name` — there are two `Phronesis` entries (h=86 non-core, h=15 core) —
so collapsing to the first hit both mis-measures and risks condemning a venue
because a homonym is small.

**Measured against 9 candidates and 48 legitimate philosophy venues** (the
control set deliberately weighted toward where a naive impact threshold would
misfire: open-access, non-Anglophone, area-specialist and new journals). Full
sweep, flagged counts:

| threshold | rule: not core | rule: not core AND not DOAJ |
|---|---|---|
| 10 | 3/9 candidates, **0** false positives | 3/9, **0** |
| 12 | 3/9, 1 FP (Norsk Filosofisk Tidsskrift, h=11) | 3/9, **0** |
| **15** | 4/9, 1 FP | **4/9, 0 FP** ← chosen |
| 18 | 4/9, 1 FP | 4/9, **0** |
| 20 | 4/9, 2 FP (+ Metascience, h=19) | 4/9, 1 FP |

Zero false positives holds across T=12..18 with the DOAJ rescue, so **15 sits
mid-plateau rather than on an edge**. The four flagged candidates are exactly
the plausibly-predatory ones — `Advanced International Journal for Research`
(h=2, the confirmed case), `Global Multidisciplinary Perspectives Journal`
(h=5), `Edumania-An International Multidisciplinary Journal` (h=9),
`International Journal of Multidisciplinary Research and Analysis` (h=13) —
all non-core and non-DOAJ.

The five candidates **not** flagged each have a defensible reason, which is
the rule behaving correctly rather than missing: `Advanced Research Journal`
has no OpenAlex match at all (never flag on absence of evidence);
`International Journal of Advanced Computer Science and Applications` (h=97)
and `ICTACT Journal on Soft Computing` (h=23, also DOAJ) are `is_core`;
`Engineering and Technology Journal` is DOAJ-listed; `International Journal of
Innovative Research in Computer and Communication Engineering` has h=26. My
name-shape scan was an explicitly crude heuristic for *finding* candidates —
several of those are evidently real if low-prestige venues, and the rule is
right not to condemn them. Recall is therefore ~4 of the 9 name-shape hits and
that is the intended trade: this is a flag-and-caveat mechanism, where a false
discredit costs far more than a miss.

Data and the script that produced it, preserved out of the session scratchpad:
`docs/known-issues/measurements-2026-08-05/` (`measure_d_threshold.py`,
`d_threshold_results.json`; local-only, with a README mapping each script to
the claim it supports).

**A curated journal list is deliberately NOT part of this** (Johannes,
2026-08-05 — decided, do not re-raise). PhilLit did carry one:
`domain-literature-researcher.md` had a "Phase 2: Key Journals (If Needed)"
section naming ~10 philosophy journals by subfield, from the initial commit
until `be73958` ("implemented skill", 2025-12-21) replaced it with the API
search battery. It was a **discovery hint, never a quality filter** — prose in
a prompt with no mechanical use — so nothing was lost when it went. Reviving it
as a positive rescue signal also would not help: every journal such a list
names (Mind, Philosophical Review, Ethics, Philosophy & Public Affairs, Minds &
Machines) is already `is_core: true` and already spared, while the venues that
actually need rescuing are the obscure-but-legitimate ones a flagship list
omits by construction (Norsk Filosofisk Tidsskrift, Phronesis, Kantian Review).
With 928 distinct venue names in this corpus, a list long enough to matter is a
maintenance project whose staleness fails toward false discredits. A
user-extensible local allowlist was considered as an escape hatch and also
declined: not worth the added surface.

**Cost, measured.** Bibs carry **zero `issn` fields** (0 of 6,530 `@article`
entries), so venue resolution must go by name. A
`sources?filter=display_name.search:<name>` lookup costs **10 credits** —
measured directly, 560 credits over 57 lookups — i.e. it is the search class,
not the 1-credit identifier class. With the free API key that is 1,000 lookups
per day, and a review introduces perhaps 30-60 *new* venues (300-600 credits),
so **verdicts must be cached per venue — once ever, not once per review**. The
key support landed 2026-08-05 (`e5ffc02`), so this blocker is cleared:
`docs/known-issues/openalex-metering-2026-08-05.md`.

**Where the flag lives** (the INCOMPLETE-pattern replacement). Not the
`keywords` field: `stamp_evidence.stamp_keywords` partitions that field into
topics / importance / evidence-tier / trailing `METADATA_CLEANED` marker, and
an unrecognized token falls through into *topics* and is re-ordered there. A
dedicated field (e.g. `venue_status`) is the right home, and it must be added
to the same survival surfaces F's suffix field needs — `sanitize_bib.py`,
`_SUBSTANTIVE_FIELDS` in `dedupe_bib.py`/`generate_bibliography.py`, and the
barrier's field re-derivation — or it will be stripped silently. D also has a
writer-facing half (`docs/conventions.md` + `agents/synthesis-writer.md`
caveat rule), which means **the roadmap's claim that F is the only one of the
six needing a live run is no longer true**; D's writer-compliance check should
ride F's run as a fourth rider rather than buying its own.

---

## Verified-on-main file map

- `hooks/metadata_cleaner.py` — per-domain cleaning, invoked from
  `hooks/subagent_stop_bib.sh` (Issue A input); writes the `METADATA_CLEANED`
  marker that `dedupe_bib.py` and `generate_bibliography.py` now propagate
- `skills/literature-review/scripts/dedupe_bib.py` — keep-first / DOI-dedup /
  abstract-preference merge, now cleaner-verdict-aware via surgical field
  strip and blocked union (Issue A, FIXED)
- `skills/literature-review/scripts/generate_bibliography.py` — surname+year
  proximity matching, symmetric transliteration-tolerant since 2026-08-05
  (Issue B, CLOSED) and collision-aware since 2026-08-05 (ROADMAP item 3 E);
  `find_cited_entries` mirrors Issue A's strip-and-blocked-union on the
  References-rendering side
- `skills/literature-review/scripts/lint_md.py` — hosts the built
  citation↔References post-check, `check_citations` (Issue B fix)
- `agents/domain-literature-researcher.md` Stage 5.5 — where the abstract
  provenance convention originates (Issue C). The `INCOMPLETE` rule this row
  used to name in `agents/synthesis-writer.md` is **gone**: item 1 replaced it
  with the evidence tier, and citability now keys on the `EVIDENCE-*` token.
- `skills/literature-review/scripts/stamp_evidence.py` (`attest_abstract`,
  `compute_tier`) + `skills/literature-review/scripts/evidence_barrier.py` —
  what actually decides whether an abstract earns characterization rights, i.e.
  Issue C's real surface after the tier shipped
- `hooks/block_ledger_write.py` — the item 3 C control: denies native file-tool
  writes to `enrichment_ledger-*.json` / `cleaning_ledger-*.json`, wired
  PreToolUse on Write/Edit/NotebookEdit via `hooks/fast_gate.sh` (needle
  `_ledger-`), with two matching `deny` rules in
  `skills/setup/scripts/setup_workspace.py`
- **Issue D has no home yet** — it needs a new venue-resolution step calling
  OpenAlex `/sources` with a persistent per-venue cache, plus a dedicated
  `venue_status` field that must survive `sanitize_bib.py`,
  `_SUBSTANTIVE_FIELDS` in `dedupe_bib.py`/`generate_bibliography.py`, and the
  barrier's field re-derivation. (An earlier revision of this row proposed
  `hooks/metadata_cleaner.py` as the candidate home, from when the mechanism
  was imagined as a cleaning-time heuristic; the validated design is a
  venue-level lookup, which is a different shape and should not be bolted into
  the cleaner. `metadata_validator.py`, named here before 2026-08-02, was
  deleted as dead code.)
