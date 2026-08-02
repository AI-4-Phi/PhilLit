# `worktree-evidence-tier` has diverged from `main` — analysis before the merge

**Status: OPEN, analysis complete, no code changed. Measured 2026-08-02.**
Input for a dedicated planning session. Nothing here has been acted on: no
merge, no rebase, no edit to the branch or its worktree. ROADMAP item 1 points
here.

## Summary

ROADMAP item 1's build lives on `worktree-evidence-tier`. It is **not a stale
branch trailing `main`** — both sides are active on the same subsystem, and
they have edited the same function for different purposes. A merge today
conflicts in **two files, one hunk each**, which makes it look trivial. It
isn't: the textual conflict is small, but resolving it wrong reverts a fix
`main` landed today, and merging it *correctly* still changes evidence-tier
behaviour in a way **no test on either side can detect**.

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
entries that previously matched — **up to 70 across the 42 local corpora**.
That 70 is a *bound*, not a measurement of the merged behaviour: it was measured
by 3J's dry-run against `main`'s own pre-3J code, and the branch still carries
the pre-hardening matcher. Under the resolution proposed in §7 (main's matcher
survives), each abstaining entry would take the branch's
`_ledger_entry_for_unmatched()` path — i.e. flip to `api_matched: False` — but
**the actual count and direction under merged code are unmeasured.** Measuring
it requires running the merged code, which has not been done.

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

## 7. Resolution recipe (proposed, not executed)

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
4. **Decide the abstention ledger semantics before writing the resolution.**
   An abstained entry is not the same as "no API record found", and the ledger
   currently has no third state. Options: a distinct `api_matched: null` /
   `abstained: true`, or a deliberate decision that abstention reads as
   unmatched. This is a design call, not a merge mechanic — it is the reason
   this needs a planning session rather than a careful merge.
5. **Acceptance gates**: both suites (1004 + 1102 → merged count), the 3J
   year/abstention tests specifically, and a fresh 42-corpus dry-run compared
   against `main`'s recorded baseline (matched 3109, fields removed 1292,
   years corrected 36, breaker trips 11). Note the dry-run is necessary but
   **not sufficient** — see Trap 1.

## 8. Open questions for the planning session

- The ledger's third state (item 4 above) — the one genuine design decision.
- Should these two workstreams keep running in parallel on
  `metadata_cleaner.py` at all? The divergence is a symptom; two active
  branches editing one file is the cause.
- Item 1's two existing merge gates (writer-guidance follow-ups, blind
  coherence comparison) are unaffected by any of this and still open.
- Unknown: what the ten 2026-08-01 commits assume about the pre-3J cleaner
  beyond the ledger. Only the conflict surface was analysed, not the full
  +87 diff in context.

## Related

- `docs/ROADMAP.md` item 1 (status block) and item 3 G/J (what `main` changed).
- Same-shape problem, different layer:
  `bib-pipeline-integrity-gaps.md` — duplicated matching logic with no owner.
