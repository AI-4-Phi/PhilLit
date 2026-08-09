# `worktree-evidence-tier` has diverged from `main` — analysis before the merge

**Status: RESOLVED 2026-08-02 — the catch-up merge landed on the branch as
`ee5f12c` (resolution from the verified trial) with Option C implemented on
top as `9842f2d`; all §9 acceptance criteria measured and met (see §10).**
Sections 1–9 are the pre-merge analysis, kept as the record of why the
resolution looks the way it does. The evidence-tier citability item that
pointed here left `docs/ROADMAP.md` on 2026-08-08, its service half having
arrived with the scripted re-vendor; nothing in the queue points here now.

**Headline, measured over all 319 local bibs: merging is strongly net-positive
and the delay is what costs you.** The branch runs the *pre-3G* cleaner, so
today it dies with `AttributeError` on **206 of 319 bibs** and writes no
ledger for them — **5445 entries with no attestation at all**, of which 3147
would pass the evidence-tier gate once merged. Against that, the abstention
regression (Trap 2) costs **17 entries** their attestation. The traps are real
and must be handled deliberately, but they are not a reason to wait.

## Summary

ROADMAP item 1's build lives on `worktree-evidence-tier`. It is **not a stale
branch trailing `main`** — both sides are active on the same subsystem, and
they have edited the same function for different purposes. A merge today
conflicts in **two files, one hunk each**, which makes it look trivial. It
isn't: the textual conflict is small, but resolving it wrong reverts a fix
`main` landed today, and merging it *correctly* still changes evidence-tier
behaviour in a way **no test on either side can detect**.

## 0. Reading this from `main` — two things that will trip you up

**Most of the code this document cites does not exist on `main`.**
`stamp_evidence.py`, `check_evidence.py`, `evidence_barrier.py`,
`resolve_context.py` and `sanitize_bib.py` live only on
`worktree-evidence-tier`. Grepping `main` for `stamp_evidence.py:103` finds
nothing and looks like a stale citation — it isn't. To read them without
leaving `main`:

```bash
git show worktree-evidence-tier:skills/literature-review/scripts/stamp_evidence.py
# or just read them in the checked-out worktree:
less .claude/worktrees/evidence-tier/skills/literature-review/scripts/stamp_evidence.py
```

Citations to `hooks/metadata_cleaner.py`, `dedupe_bib.py` and
`generate_bibliography.py` *are* valid on `main`.

**There were two extra worktrees during this work; both are now removed.**

| worktree | branch | status |
|---|---|---|
| `.claude/worktrees/evidence-tier` | `worktree-evidence-tier` | **removed 2026-08-02** after the merge landed and every gitignored record (A/B results + adjudication) was verified byte-identical in the main checkout's `docs/superpowers/plans/` (was: DO NOT REMOVE — sole copy of that record) |
| `.claude/worktrees/merge-trial` | `merge-trial` | **removed 2026-08-02** after the real merge landed (was the throwaway trial @ `6e84aa1`) |

## 1. Topology (all figures measured 2026-08-02)

| | `main` | `worktree-evidence-tier` |
|---|---|---|
| tip | `d69a64a` | `15cd307` |
| commits since fork | 26 | 33 |
| unit suite | 1004 green | 1102 green |

Fork point: `fc2477f`, 2026-07-24. Worktree: `.claude/worktrees/evidence-tier`.

Reproduce:

```bash
git rev-list --left-right --count main...worktree-evidence-tier   # 26  33
git merge-base main worktree-evidence-tier                        # fc2477f
git merge-tree --write-tree main worktree-evidence-tier | grep CONFLICT
```

The previous status note (2026-07-28) said tip `f9e3fda`, 23 commits, 1069
tests. All three were stale: **ten commits landed 2026-08-01** — enrichment-
ledger attestation, barrier self-heal (`b5e3d9d`, `39dae4b`, `3cc6dcb`),
writer tier rules, researcher `Edit` permission, `add_field_to_entry`
quoting/brace safety. `f9e3fda` is still an ancestor, just not the tip.

## 2. What each side did to `hooks/metadata_cleaner.py`

Both rewrote the entry loop in **`clean_bibtex`**.

- **`main`** (+587/−109 since the fork): the whole 3G–3K year/DOI hardening.
  Relevant here — 3J(c) made a conflicted-DOI entry with no entry-scoped
  record **abstain**, and **moved the year-disagreement warning above the
  match check** so an abstention is never silent. The code comment says so
  outright: *"a conflicted DOI with no entry-scoped record now abstains, and
  this warning is the only signal that it did."*
- **branch** (+87): added a **cleaning/evidence ledger**. Every entry gets a
  record — `api_matched` + `verified_identifier` on a match,
  `_ledger_entry_for_unmatched()` otherwise. The year-conflict warning stayed
  **inside** the matched path, where it was before 3J.

## 3. The conflict

| file | hunks | location |
|---|---|---|
| `hooks/metadata_cleaner.py` | 1 | inside `clean_bibtex`, at the `find_api_entry_for_bib_entry` call |
| `tests/test_metadata_cleaner.py` | 1 | inside `TestHelperFunctions` |

Everything else auto-merges, including the 2026-08-02 doc edits.

## 4. Trap 1 — a naive resolution silently reverts ROADMAP 3J(c)

The conflicting hunk is literally `main`'s warning-hoist comment against the
branch's ledger block. Take the branch's side (or "keep both, branch order")
and the warning goes back **below** the match check. An abstaining entry then
produces **no warning at all** — which is exactly the silent-abstention defect
3J(c) fixed.

This is the hazard ROADMAP item 1 already warns about for `6ee2566`, but worse:
the corpus dry-run **cannot see it**. Every 3G–3K defect lived in a
malformed-input path, and the 42-corpus dry-run was byte-identical through all
three review rounds. A reverted warning-hoist would pass it silently.

## 5. Trap 2 — abstention re-classifies entries in the evidence ledger

This one survives a *correct* textual resolution, and is the more serious of
the two.

`main`'s 3J abstention makes `find_api_entry_for_bib_entry` return `None` for
entries that previously matched, flipping them to `api_matched: False`.

**Now measured** (trial merge, all 319 local bibs; the earlier "up to 70" was a
bound taken from 3J's dry-run against main's own pre-3J code, and is
superseded). Only 111 bibs produce a ledger on *both* sides — the branch
crashes on the rest, see §5b — so those 111 are the comparable set:

| on the 111 comparable bibs | count |
|---|---|
| `api_matched` unchanged | 3006 |
| `api_matched` **True → False** (abstention) | **43** |
| `api_matched` False → True | 0 |
| evidence-tier gate **lost** (attested → not) | **17** |
| evidence-tier gate **gained** (not → attested) | 28 |

So the abstention regression is **17 entries losing attestation**, not 70, and
it is *outweighed even within this set* by 28 gains — those come from the
hardened matcher picking a better record (a non-empty
`verified_identifier_value` where there was none) and from per-bib breaker-trip
differences, both of which also feed `stamp_evidence.py:103`.

The 43 flips are concentrated in DOI-conflict cases, as 3J predicts — e.g.
`slack2020fooling` (ai-deception-mechanistic-interp), `mcmanus2018autonomous` /
`mcmanus2019autonomous` (av-trolley-problem-ethics), `preston2013ethics` and
`frank2019ethics` (cdr-ethics-2). Several appear in both a domain bib and
`literature-all.bib`, so the 43 covers fewer than 43 distinct works.

## 5b. The dominant effect — the branch currently crashes on 65% of bibs

This was not visible before running the trial merge, and it reverses the
cost-of-delay argument.

The branch's `metadata_cleaner.py` is pre-3G, so it still has the defect 3G
fixed: one CORE `journal`-as-string file raises `AttributeError` and kills the
whole index. Over the local corpora:

| | branch today | merged |
|---|---|---|
| bibs cleaned without error | **113** | **319** |
| bibs dying with `AttributeError` | **206** | 0 |
| entries matched | 2349 | 6611 |
| fields removed (planned) | 1235 | 2668 |

For all 206 crashed bibs, `clean_bibtex` raises before `_write_ledger_safe`, so
**no cleaning ledger is written at all** — and a missing ledger demotes
downstream by design. Merging fixes every one:

- **5445 entries** gain a ledger entry,
- **3147** of them pass the evidence-tier gate (newly attested),
- 2298 are recorded but not attested (the honest, safe outcome).

**Net effect of merging on evidence-tier attestation: +3147 newly attested
against 17 lost.** Every day the merge waits, the branch's evidence tiers are
being computed with cleaning dead on two thirds of its bibs.

## 5c. What the trial merge verified

`merge-trial` @ `6e84aa1` (throwaway, do not ship):

- **1185 tests pass** (main 1004 + branch 1102, deduplicated).
- Cleaner metrics **identical to `main`** over all 319 bibs — matched 6611,
  fields removed 2668, breaker trips 86, years corrected 0, 0 errors. So the
  §7 resolution preserves the 3G–3K hardening exactly.
- Corpora provably untouched: `write_bibtex` and `write_cleaning_ledger` were
  both stubbed, and all 7428 corpus files verified byte-identical (mtime+size)
  before and after.

Note both suites passing is *not* evidence the traps were handled — 1185 green
is exactly what a wrong resolution would also produce (§6). The evidence that
the resolution is right is the metric identity with `main`, plus keeping the
warning hoisted.

`api_matched` is not bookkeeping — it gates evidence-tier assignment:

- `stamp_evidence.py:103` — `if att.api_matched and not att.breaker_tripped and att.verified_identifier_value:`
- `evidence_barrier.py:327` — `if (not att.api_matched or att.breaker_tripped) and (…)`
- `dedupe_bib.py:586` — `api_matched=bool(blob.get("api_matched"))`

So merging `main` into the branch **changes the evidence tier of every entry
3J newly abstains on**. The direction (how many lose a tier, and which)
is **unmeasured** — I did not run merged code. The 70 figure comes from
`main`'s dry-run and is the upper bound on affected entries there.

## 6. Why neither test suite catches either trap

Both suites are green *on their own side*: 1004 on `main`, 1102 on the branch.
Neither can fail, because the interaction does not exist on either branch —
`main` has abstention and no ledger, the branch has a ledger and no
abstention. The defect is created **by the merge**. There is no existing test
whose failure would announce it.

## 7. Resolution recipe (executed once on `merge-trial`, verified — see §5c)

1. **Catch-up merge, not rebase** — `git merge main` from inside the
   evidence-tier worktree. A rebase replays 33 commits (repeated chances to
   resolve the same file inconsistently) and rewrites `6ee2566` / `f9e3fda`,
   which ROADMAP item 1 references by hash. A merge resolves once and keeps
   those commits addressable. The gitignored A/B results in that worktree are
   untouched either way — git does not move untracked files.
2. **Resolve with `main`'s version as the base**, then re-insert the branch's
   two ledger writes into it. `main`'s block is the hardened one; the branch's
   contribution is additive.
3. **Keep the warning hoisted above the match check.** Non-negotiable — that
   ordering *is* 3J(c).
4. **Implement Option C for the abstention ledger semantics — DECIDED, see §9.**
   Abstention attests existence (the DOI is confirmed) and declines cleaning;
   it must no longer be recorded as "no API record found". This requires
   changing `find_api_entry_for_bib_entry`'s return contract, so it is part of
   the resolution, not a follow-up.
5. **Acceptance gates**: both suites (1004 + 1102 → merged count), the 3J
   year/abstention tests specifically, and a fresh 42-corpus dry-run compared
   against `main`'s recorded baseline (matched 3109, fields removed 1292,
   years corrected 36, breaker trips 11). Note the dry-run is necessary but
   **not sufficient** — see Trap 1.

## 8. Open questions for the planning session

- ~~The ledger's third state~~ — **DECIDED 2026-08-02 (Johannes): Option C,
  split the axes.** See §9. No longer open.
- **Should these two workstreams run in parallel on `metadata_cleaner.py` at
  all?** The divergence is the symptom; two active branches editing one file is
  the cause. This is the durable question behind the whole item.
- Item 1's two existing merge gates (writer-guidance follow-ups, blind
  coherence comparison) are unaffected by any of this and still open.
- **Unmeasured:** what the ten 2026-08-01 commits assume about the pre-3J
  cleaner beyond the ledger. Only the conflict surface and the ledger's
  `api_matched` axis were analysed — not `resolve_context`, `check_evidence`, or
  the barrier's own behaviour under merged cleaning.
- Reproduce any of the above: the harness is throwaway (it lived in the job tmp
  dir); it monkeypatches `mc.write_bibtex` and `mc.write_cleaning_ledger`, walks
  `reviews/*/`, mirrors `subagent_stop_bib.sh`'s json-dir selection (bib's own
  dir + `intermediate_files/json`), and dumps per-entry `api_matched` /
  `verified_identifier_value` for diffing. Rebuild rather than trust these
  numbers if a decision turns on them.

## 9. DECISION 2026-08-02 — Option C: attest existence, decline the year

**Johannes's call. Made, not open.** The merge resolution must implement it.

**The defect.** `find_api_entry_for_bib_entry` returns a bare `None` for two
opposite reasons, and the ledger collapses both to `api_matched: False`:

| | evidence of existence | evidence about the year |
|---|---|---|
| no-match | none | none |
| **abstained** | **strong — ≥2 indexed sources carry the exact DOI** | contradictory |

Both abstention sites sit *after* `find_api_entry_by_doi` returned a record, and
`find_doi_year_conflicts` can only find a conflict among records sharing that
normalized DOI. So abstention is a year-scoped refusal that the ledger converts
into an existence-scoped penalty — and `NONE` means uncitable.

**Measured cost of leaving it:** of the 17 gate-losing rows (11 distinct works),
**0** hold any `sep_context`/`iep_context` and only 4 hold an `abstract` with a
source in `ATTESTED_ABSTRACT_SOURCES = {"s2","openalex","core","ndpr"}` (two
works: `preston2013ethics`, `lin2020pacgan`). So **≥13 of 17 rows — 9 of 11
distinct works — fall to `NONE` and become uncitable**, among them
`slack2020fooling`, `mcmanus2018/2019autonomous`, `darwiche1997iterated`,
`frank2019ethics`, `levendusky2018american`, `mason2015disrespectful`,
`autor2020importing`, `shanahan2024talking`.

**The fix.** On the two abstention paths only, record
`api_matched: True`, `verified_identifier: "doi"`,
`verified_identifier_value: normalize_doi(doi_value)` (plus an additive
`cleaning_abstained` reason), while **cleaning behaviour changes not at all** —
no field removal, no downgrade, no year correction, no marker.
`compute_tier`'s value binding still re-checks the DOI, so no extra trust is
granted. This does not weaken the locked positive-verification rule: an exact
DOI match against ≥2 sources *is* affirmative evidence of existence, and
`EXISTENCE` never claimed the year.

**House style precedent:** the service cleaner already does this for the
adjacent case — at the year gate it keeps the matched record and stores
`plan["year_correction_declined"] = (..., reason)`, commented *"COUNTABLE, not
silent … a refusal is itself information."* C is that principle one level up.
Keep the refusal visible in the evidence report too (the retained half of
Option D).

**Do not** relax the conflict test into majority rule (the code comment forbids
it), and **do not** attest existence on the two genuine no-match paths.

**Acceptance:** metric identity with `main` (matched 6611, fields removed 2668,
breaker trips 86, years corrected 0, errors 0 over 319 bibs) — C changes
attestation only; ledger diff showing *only* abstained entries flipping; tier
diff showing `EXISTENCE` regained and no new `ABSTRACT`/`CONTEXT`; one negative
test per abstention path, each verified to fail without the fix.

Sister-repo instructions (the service has **no** evidence-tier layer yet, so
this is a condition on its pending port, not a bug fix there):
`docs/known-issues/phillit-abstention-attestation-decision-2026-08-02.md` (local-only; original in ~/Downloads).

## 10. RESOLUTION 2026-08-02 — executed and measured

Executed exactly per §7, on the evidence-tier worktree:

1. **`ee5f12c`** — catch-up merge of `main` (`fa6cde4`) into the branch. The
   two conflicted files were resolved by taking `merge-trial` @ `6e84aa1`'s
   verified versions (`git checkout 6e84aa1 -- hooks/metadata_cleaner.py
   tests/test_metadata_cleaner.py`); the staged tree was verified
   code-identical to the trial (`git diff 6e84aa1 -- . ':!docs'` empty —
   only main's three newer docs-only commits differ). Warning-hoist (3J(c))
   preserved. 1185 tests green, matching the trial.
2. **`9842f2d`** — Option C (§9), TDD. `find_api_entry_for_bib_entry` returns
   a falsy `CleaningAbstention(reason, normalized_doi)` on both abstention
   paths; `clean_bibtex` records `api_matched: True`, `verified_identifier:
   "doi"`, the normalized DOI, and an additive `cleaning_abstained` reason —
   cleaning behaviour and metrics unchanged (abstained still counts
   unmatched; new additive `abstained_entries` counter). The refusal is
   visible in the barrier report (`attestations` blob, top-level
   `cleaning_abstained` list, stdout summary count). `compute_tier`
   untouched. One negative test per abstention path, each watched to fail
   with `api_matched: False` before the fix; genuine no-match paths tested
   to stay unattested. **1192 tests green.**

**§9 acceptance, measured over all 319 local bibs** (harness rebuilt per §8
with production json-dir semantics — the union of the bib's own dir and the
*review root's* `intermediate_files/json`, per `subagent_stop_bib.sh` item-13
A3; `bib.parent`-relative selection undercounts by half):

| criterion | measured | verdict |
|---|---|---|
| metric identity with `main` | matched 6611, planned fields removed 2668, breaker trips 86, years corrected 0, crashes 0 — identical A=B=C | PASS |
| ledger diff (pre-C merge → C) | **106 flips, all abstention-shaped** (`pooled_year_conflict` ×106, `scoped_year_disagreement` ×0), 0 anomalies | PASS |
| tier diff | EXISTENCE **+56 regained, 0 lost** (incl. `slack2020fooling`, `mcmanus2018/2019autonomous`, `preston2013ethics`, `frank2019ethics`); no new ABSTRACT/CONTEXT (structurally impossible from cleaner output; confirmed no non-abstention ledger change) | PASS |
| corpora untouched | 7910 files byte-identical (size+mtime snapshot) | PASS |

The 56 > the §5 "17 lost" because Option C also attests abstained entries in
the 206 bibs whose ledgers only exist post-merge. 8 bibs return handled
per-bib `errors` (pre-existing malformed BibTeX, identical across variants,
e.g. `what-are-data-2/intermediate_files/literature-domain-1.bib`) — these
are returns, not crashes, and are not merge-related.

**Still open after this resolution:** ROADMAP item 1's two merge gates
((b) writer-guidance follow-ups, (c) blind coherence comparison) — they gate
landing the branch on `main`, not this catch-up merge. The
`metadata_cleaner.py` freeze on `main` stays until the branch lands.

**LANDED (same day, 2026-08-02 evening):** both gates closed — (b) via a
live validation run (PASSED), (c) via Johannes's blind read (treatment
PREFERRED) — and the branch merged to `main` as `f89f4de`, released as
plugin **v0.3.0**. The freeze is lifted; `main` is the single line again.
This document is now wholly historical. §0's branch-only path caveat no
longer applies: every cited file exists on `main`.

## Related

- `docs/ROADMAP.md` items 3 G and 3 J, the cleaner/year hardening (what `main`
  changed). The evidence-tier citability item that carried the status block has
  since left that queue.
- Same-shape problem, different layer:
  `bib-pipeline-integrity-gaps.md` — duplicated matching logic with no owner.
