# Author–year collisions: dangling `2015a` cites, phantom references, no Chicago disambiguation

**Status:** Open, scheduled. Surfaced as a side finding during evidence-tier
A/B adjudication (2026-07-28); quantified across all 32 delivered reviews
the same day. Tracked as `ROADMAP.md` item 3, sub-items **E** (matcher) and
**F** (Chicago suffixes), sequenced after the evidence-tier merge and
service port.

## Summary

The pipeline identifies a work in prose by **first-author surname within 60
characters of a 4-digit year** (`generate_bibliography.find_cited_entries`,
`check_evidence.find_cites` — the latter branch-side, on
`worktree-evidence-tier` — both using `_MATCH_WINDOW = 60`). Nothing
downstream can distinguish two works that share that pair. Nothing upstream
assigns Chicago `2019a`/`2019b` suffixes. This produces three distinct
defects, two of them visible in delivered output.

## Evidence (all 32 delivered reviews under `reviews/`)

| Mode | Reviews affected | Instances |
|---|---|---|
| **A — no Chicago suffix** (same author string + year, different works) | 22 / 32 | ≤48 (upper bound; see caveat) |
| **B — matcher collision** (same first surname + year, different author lists) | 21 / 32 | 36 |
| **C — undeduped near-identical entries** | 5 / 32 | 8 |

*Caveat on A's count:* the 48 is an upper bound. The classifier normalizes
titles to 80 characters, so diacritic and subtitle variants of a single work
(Millière & Buckner 2024, Blume 1991, Garcia 2024, Mackenzie 2000,
Leitgeb 2010, Irving 2018) fall into A rather than C. The review-level count
(22/32) is robust; the instance count is not.

### A.1 Dangling `2015a` citations — the hard finding

**8 of 32 reviews contain prose citations with a year suffix (`2015a`,
`2019b`) while *zero* reference lists carry a single lettered entry.**

```
ai-access-consciousness            prose a/b tokens=3   lettered refs=0
ai-global-justice                  prose a/b tokens=5   lettered refs=0
infinite-value-lexicographic…      prose a/b tokens=6   lettered refs=0
nonideal-theory                    prose a/b tokens=4   lettered refs=0
political-philosophy-human-ai      prose a/b tokens=4   lettered refs=0
procedural-justification           prose a/b tokens=3   lettered refs=0
synthetic-data-distribution…       prose a/b tokens=3   lettered refs=0
value-alignment-ai                 prose a/b tokens=2   lettered refs=0
```

Concrete: `nonideal-theory` prose reads `Wiens (2015a; 2015b)` while the
References list three unlettered `Wiens, David. 2015.` entries. The
citation resolves to nothing. This is the mirror image of ROADMAP item 3B
("silent References omission… no every-citation-resolves post-check").

The writers are *already trying* to disambiguate — they invent suffixes
that the reference-list renderer never emits. The convention gap is on the
tooling side, not the model side.

### B.1 Phantom references — confirmed, not merely structural

For 7 collision groups the prose contains **strictly fewer distinct
citation forms than the group has entries**, so at least one listed entry
is never cited:

| Review | Group | Prose forms | Entries | Class |
|---|---|---|---|---|
| `extended-mind-cognitive-offloading` | Menary 2010 | `Menary (2006, 2010, 2013)` only | **3** (two chapters + the edited volume) | **F** — same author |
| `admin-power-legitimacy` | Moore 2020 | solo only | 2 (solo + 5-author) | E — author lists differ |
| `ai-access-consciousness` | Li 2022 | `Li and Mao` only | 2 — **Jianhui** and **Kenneth** Li | E — author lists differ |
| `ai-global-justice` | Muldoon 2023 | `Muldoon and Wu` only | 2 | E — author lists differ |
| `algorithmic-fairness-2023` | Wang 2023 | `Wang and Luo` only | 2 | E — author lists differ |
| `extended-mind-cognitive-offloading` | Adams 2010 | `Adams and Aizawa` only | 2 (book + chapter) | E — author lists differ |
| `algorithmic-fairness-2023` | Johnson 2024 | solo only | 2 — **Gabbrielle** and **Rebecca** Johnson | E — but both solo; needs first initials |

The **class** column matters: a discriminating-token fix (second-author
surname / `et al.`) handles only the five middle rows. Menary is three
*solo* works by the same person, so no token exists and only suffixes (F)
can resolve it. The two Johnsons are different people who are both solo
authors, so the discriminator has to be Chicago's first-initial rule
(`G. Johnson 2024` / `R. Johnson 2024`) rather than an author-list token.

A further 22 groups produced *no* parseable prose form; those are
inconclusive (regex window limits), not counted above.

The `Menary 2010` case is the cleanest single illustration of both modes at
once: one undifferentiated prose year, three works in the list, two of them
uncited, and no way for a reader to resolve any of them.

Note the Johnson and Li rows: the collision merges **different people**, so
the phantom is not merely a redundant listing.

## Why it happens

- No stage assigns year suffixes. `format_entry` renders `year` verbatim;
  `_sort_key` sorts on `(surname, year)` only, so the order of colliding
  entries is arbitrary and unstable between runs.
- Section writers run in parallel in Phase 5 and cannot see each other's
  citations, so a writer cannot know a suffix is needed — and if it guesses
  one, Phase 6 has no record of what it meant.
- `find_cited_entries` tests each entry independently against the prose, so
  every entry sharing `(surname, year)` matches whenever any one of them is
  cited.
- `docs/conventions.md` and `agents/synthesis-writer.md` say "Chicago
  Author-Date" and "(Author Year)" but are silent on same-author-same-year.

## Fix design

The information is lost at write time: Phase 6 cannot tell which
`(Leonelli 2019)` in prose meant which work. So suffixes must be assigned
**before** section writing, not after.

**B is separable and cheaper than A** — it needs no agent-prompt change and
no live run, which is why it is sequenced first (roadmap 3E vs 3F):

- **B → roadmap 3E (matcher)** — scope: collisions between works by
  *different* authors, which the prose can already distinguish. Make
  `find_cited_entries` collision-aware in two shapes: when the colliding
  entries have distinct author lists, require a discriminating token in the
  window (second-author surname, or `et al.`); when they are distinct
  *people* who are both solo authors (the two Johnsons), fall back to
  Chicago's first-initial rule. Where the prose form stays ambiguous, warn
  rather than guess. Self-contained in `generate_bibliography.py` + tests.
  Natural companion to the item-3B every-citation-resolves check in
  `lint_md.py`.

  E cannot touch same-author collisions (Menary 2010 ×3): nothing in the
  citation distinguishes them, so those are F's alone.

- **A → roadmap 3F (suffixes)** — four coordinated pieces:
  1. Assign suffixes on the merged bib after dedupe, before Phase 5, into a
     dedicated field (**not** the `year` field — `re.fullmatch(r"\d{4}", …)`
     guards in `check_evidence.py` and `resolve_context.py`, both on the
     `worktree-evidence-tier` branch, would reject `2019a`). Order by
     title, per Chicago.
  2. Tell writers to use them (`docs/conventions.md`,
     `agents/synthesis-writer.md`).
  3. Render the suffix in `format_entry`; extend `_sort_key`.
  4. Optionally renumber at Phase 6 to close letter gaps — safe only
     because suffixed prose tokens are unique per work.

  Requires a live headless review run to confirm writers actually comply,
  then a port to `phillit-service`'s vendored `engine/.claude/`.

**C** overlaps ROADMAP item 3A (cleaner-unaware dedup) but is a *distinct*
failure — near-identical entries surviving dedupe on diacritic variance
(`Milliere`/`Millière`, `Mohamed El-Amine`/`Mohamed El Amine`) and
arXiv-vs-journal pairs. Recorded here as an out-of-scope find; it is not
part of the proposed fix.

## Interaction with the evidence tier

`check_evidence.find_cites` shares the same `(surname, year)` matching, so a
collision smears tier attribution across colliding entries — this is one
source of the checker's false-positive rate (the A/B adjudication found 4
of 6 flagged findings were proximity artifacts). It is **telemetry only**.
The Phase 3→4 barrier stamps entries from abstract evidence before any
prose exists, so barrier correctness is unaffected.
