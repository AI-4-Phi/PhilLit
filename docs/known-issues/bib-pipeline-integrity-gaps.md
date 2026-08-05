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
**Status**: Open overall (C and D untouched). **A is FIXED 2026-08-05; B's
citation-omission post-check landed 2026-08-05, matcher-side transliteration
work still open** — see the per-issue status lines below and
`docs/ROADMAP.md`. The 2026-08-02 sequencing constraint (fixes touching
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
item 4 on 2026-08-03, and any remaining matcher gap is now caught loudly
by the every-citation-resolves check built 2026-08-05 rather than shipping
silently — but B's original near-miss matcher class (transliteration
divergences NFKD doesn't cover, e.g. "Fraenken" vs "Franken") is still
open and can still drop a citation, now surfaced rather than silent. Issues
C and D are missing safeguards: their observed exploits occurred under
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
**Status: Post-check built 2026-08-05** (`03d2b6b`); matcher
transliteration still open.

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
surfaces the drop loudly; it does not make the match succeed.

**Issue B itself remains Open.** The check is a guard, not a fix for the
matcher: it makes every future matcher gap loud instead of silent, but the
transliteration-aware normalization and fuzzy near-miss fallback that would
actually resolve a "Fraenken"/"Franken" divergence *at match time* in
`generate_bibliography.py` are unbuilt (out of scope for this branch —
ROADMAP item 3 tracks it as B's remaining half, to be prioritized once the
new check surfaces real instances). B's original tie-break — build the
post-check regardless of the matcher fix, since it catches every future
matcher gap, not just this one — stands vindicated on its own merits.

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

Two residual holes, deliberate and documented in the code (ROADMAP item 4):
the year test is a substring match, so a non-numeric or bracketed year
(`n.d.`, `[2021]`) still cannot match in the script-preserving haystack; and
the fallback triggers only on an *empty* ASCII fold, so a surname folding to
punctuation-only (a hyphenated non-Latin name folds to `-`) never reaches it.
The latter is a distinct symptom in the opposite direction — those entries
match a garbage pattern and can be spuriously *included* — and is an open
candidate item.

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
  `hooks/subagent_stop_bib.sh` (Issue A input); writes the `METADATA_CLEANED`
  marker that `dedupe_bib.py` and `generate_bibliography.py` now propagate
- `skills/literature-review/scripts/dedupe_bib.py` — keep-first / DOI-dedup /
  abstract-preference merge, now cleaner-verdict-aware via surgical field
  strip and blocked union (Issue A, FIXED)
- `skills/literature-review/scripts/generate_bibliography.py` — surname+year
  proximity matching, aggregate-only reporting (Issue B, matcher still open);
  `find_cited_entries` mirrors Issue A's strip-and-blocked-union on the
  References-rendering side
- `skills/literature-review/scripts/lint_md.py` — hosts the built
  citation↔References post-check, `check_citations` (Issue B fix)
- `agents/domain-literature-researcher.md` Stage 5.5 +
  `agents/synthesis-writer.md` INCOMPLETE rule — the unenforced abstract
  provenance convention (Issue C)
- verification scripts / `hooks/metadata_cleaner.py` — where venue heuristics
  would live (Issue D). Named `metadata_validator.py` before 2026-08-02; that
  module was deleted as dead code, so the cleaner is the only candidate home.
