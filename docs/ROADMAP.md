# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Stage 4 (citation chaining) did not run at all in a full production review.**
Across all 104 domain-researcher Bash calls of the service's 2026-08-26
acceptance run (`dbe0667370d74b4f`, 6 domains, pin `fffb721`) there were **zero
`s2_citations`, `s2_recommend` and `s2_batch` invocations** — the command stream
itself, not an artifact proxy, so for that run it is certain. All six domains
completed Stages 1–3, so seeds existed. Nothing in the prose marks the stage
optional: Stage 6 is explicitly "Web Search Fallback (When Needed)" and Stage 4
is not, its block is captioned "One call: chain citations for ALL seed papers",
the error-handling paragraph tells the researcher how to read "the Stage 1 and
Stage 4 tails", and the researcher's own completion checklist lists "Stage 4
chains" among the `.json` files that must be left in `$JSON_DIR`. Three
readings — researchers skip a required stage, or the stage is optional in
practice and the prose should say so, or **Stage 4's separateness is
asserted ONLY as an exception inside a batching rule** ("a later stage that needs
an earlier stage's results … Stage 4 needs chosen seeds"), so a researcher
optimizing for one-call-per-stage has nothing anywhere telling it the stage must
happen at all. The third is what this evidence most supports and is a prose fix.
Citation chaining is also the one discovery mechanism with no substitute among
the other stages, so its absence is not cosmetic. **A lead, not a regression
claim**: the pre-batching 2026-07-17 run did fire it (`s2_batch` ×6,
`s2_citations` ×1 over 7 domains) where the post-batching run fired it zero
times, which makes the `One Bash Call Per Stage` rewrite a candidate cause, but
both counts are small and one recent local review still carries `cites_*.json`.
Reproduce with the service's `tools/transcript_batching_report.py`, whose NEVER
INVOKED line surfaced it. Measured against the prose at `fffb721`; Stage 4's
block and the batching section are unchanged at `7991e90`.

**Stage 3 takes 3–5 Bash calls where "One Bash Call Per Stage (REQUIRED)"
prescribes one — and every stage asking for more than one invocation runs over.**
Same run, measured per stage per domain. The rule is the section heading, not the
softer "roughly 6–8" line below it, and its body names this stage: "Stage 3's
four searches hit four different APIs, which is why they parallelize".

| stage | prescribed | measured across the 6 domains |
|---|---|---|
| 1 SEP & IEP | 1 (2 if the fetch waits on search slugs) | 2, 2, 3, 2, 2, 4 |
| 2 PhilPapers | 1 | 2, 2, 2, 2, 1, 3 |
| **3 Extended academic** | **1** | **5, 5, 4, 5, 3, 3** |
| 5.5 Abstract resolution | 1 | 1, 1, 1, 1, 1, 1 |

**Stage 5.5 is the control** — exactly 1 call in all six domains — so
researchers do follow one-call-per-stage when the stage is a single invocation.
This is therefore not general non-compliance, and the gradient tracks how many
invocations a stage asks to be CHAINED rather than the stage's importance: 1
invocation → 1.0 calls, 2 of the same script (Stage 2) → 2.0, 4 across two
dependent phases (Stage 1) → 2.5, 4 in parallel (Stage 3) → 4.2. What is being
ignored is the chaining itself, and most of all the `&`-plus-`wait` form that
only Stage 3 asks for. A further 2–3 calls per domain invoke no script at all
(`mkdir`, a `grep -m1 '"status"'` tail); those are deviations too, since every
worked example puts both inside the stage's own call and the bullet under
"Consuming results without re-reading them" forbids standalone `mkdir`
outright. Batching itself is working — 64% of researcher calls chain more than
one invocation against 23.5% before the rewrite, and verification clusters on
the prescribed groups of about six — so this is the residue, and it is the
cheapest remaining turn-count lever, since Stage 3 alone is ~3 surplus calls per
domain and a researcher turn re-reads its whole context.
One prose observation while measuring: the `roughly 6–8` figure reads as the
budget and is what a reader lands on, while the rule sits 30 lines above it; if
the intent is one call per stage, the figure could name that directly rather than
offering a range a 10-call domain can seem to satisfy. Reproduce with the
service's `tools/transcript_batching_report.py`. Measured against the prose at
`fffb721`; the section and Stage 3's block are unchanged at `7991e90`.

**`_first_surname_raw` still pre-splits the author field on a naive `" and "`,
and the record of that decision left with the entry that carried it.** It was
the sibling gap in the nested-brace filing — `field.split(" and ")[0]` before
pybtex sees the fragment, where pybtex is brace-aware, so one braced corporate
author containing "and" keys as `smith` here and `smith and jones institute` in
Phase 6. `f0440fa`'s roadmap rewrite noted it as a reason to do the parser once,
but the entry that replaced it does not carry it and `year_suffix.py` is
unchanged. **0 of 8,975 author fields** across 45 delivered service reviews have
that shape (braced corporate authors do occur — `{European Commission}`,
`{OECD}`, `{Council of Europe}` — and none contains "and"), so the only question
is whether the decline was deliberate: if it was, it is an accepted residual and
belongs in the function, where a recurrence would be read. The service pins it
as a scope guard
(`test_a_braced_corporate_author_containing_and_is_a_KNOWN_DIVERGENCE`), so
either outcome is reported rather than absorbed.

**Dynamic-workflow orchestration for Phases 3–5** — unstarted. **Gate 1 is
answered, and it is a no**: the service cannot reach a workspace
`.claude/workflows/`, and the blocker is DELIVERY rather than capability — its
mirror excludes `skills/setup/` by decision, so step 3's install step is
structurally unavailable there and step 4 would arrive as prose calling a tool
with no registered workflow file and no allowlist entry. Step 3 needs a delivery
path the `skills/` mirror already carries, decided before the script is
written. Gate 2 (re-run the hook gate test) still stands, and belongs against
the CLI the Agent SDK bundles rather than the installed one, or the two
consumers of this skill diverge on the surface it measures. Design, both gates
and the service's verified answer: `docs/ideas/dynamic-workflow-refactor.md`,
which owns them.
