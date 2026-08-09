# Author–year collisions: dangling `2015a` cites, phantom references, no Chicago disambiguation

**Status:** Surfaced as a side finding during evidence-tier A/B adjudication
(2026-07-28); quantified across all 32 delivered reviews the same day.
Tracked as `ROADMAP.md` item 3, sub-items **E** (matcher) and **F** (Chicago
suffixes). **E is FIXED 2026-08-05** (`917850d`, `fb6623e`, `be5ab30`,
`e5e863a`, `e5cb717` — item 3 E, Tasks 1-4 of the collision-aware-matching
plan; `970b117` — final-review fix-wave, C1 left-anchor guard, I1
second-position corroboration, M2 dead-span cleanup). **F is FIXED 2026-08-06
and validated live 2026-08-07** (`year_suffix.py` assigns Chicago `a`/`b` at
the evidence barrier; the live run produced 5 lettered cites, each verified by
hand to name the right work, 0 bare-year cites of lettered groups, 0 phantom
letters — record: `.superpowers/sdd/2026-08-07-item3f-live-run/plan.md`,
local-only). What remains of item 3 is the **first-initials gap**
(`ROADMAP.md` §3): the live run's only same-surname pair (Onora vs Martin
O'Neill, different years) shipped without initials.

## Summary

The pipeline identifies a work in prose by **first-author surname within 60
characters of a 4-digit year** (`generate_bibliography.find_cited_entries`,
`check_evidence.find_cites`, both using `_MATCH_WINDOW = 60`). Nothing
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
citation resolves to nothing. This is the mirror image of ROADMAP item 3 B,
every-citation-resolves ("silent References omission… no
every-citation-resolves post-check").

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
no live run, which is why it is sequenced first (roadmap item 3 E,
collision-aware matching, before item 3 F, Chicago a/b disambiguation):

- **B → roadmap item 3 E, collision-aware matching — FIXED 2026-08-05.** Scope: collisions
  between works by *different* authors, which the prose can already
  distinguish. `find_cited_entries` is now collision-aware in both shapes:
  when the colliding entries have distinct author lists, a discriminating
  token in the window (second-author surname, or `et al.` with 3+ authors)
  selects among them; when they are distinct *people* who are both solo
  authors (the two Johnsons), a first-initial/first-name token does the
  same. Where the prose form stays ambiguous, the group is kept whole and
  warned about rather than guessed at. Self-contained in
  `generate_bibliography.py` + tests. Natural companion to item 3 B's
  every-citation-resolves check in `lint_md.py`. Full resolution rule and
  residuals: "E: fixed 2026-08-05" below.

  E cannot touch same-author collisions (Menary 2010 ×3): nothing in the
  citation distinguishes them, so those are F's alone.

- **A → roadmap item 3 F, Chicago a/b disambiguation — BUILT 2026-08-06 as designed, validated live
  2026-08-07** — four coordinated pieces:
  1. Assign suffixes on the merged bib after dedupe, before Phase 5, into a
     dedicated field (**not** the `year` field — `re.fullmatch(r"\d{4}", …)`
     guards in `check_evidence.py` and `resolve_context.py` would reject `2019a`). Order by
     title, per Chicago.
  2. Tell writers to use them (`docs/conventions.md`,
     `agents/synthesis-writer.md`).
  3. Render the suffix in `format_entry`; extend `_sort_key`.
  4. Optionally renumber at Phase 6 to close letter gaps — safe only
     because suffixed prose tokens are unique per work.

  The live headless run (2026-08-07) confirmed writers actually comply —
  every lettered group was cited with its letter, and every letter named the
  right work. The service's vendored `engine/.claude/` picked this up with
  its scripted re-vendor on 2026-08-08; nothing cross-repo remains.

**C** overlaps ROADMAP item 3A (cleaner-unaware dedup) but is a *distinct*
failure — near-identical entries surviving dedupe on diacritic variance
(`Milliere`/`Millière`, `Mohamed El-Amine`/`Mohamed El Amine`) and
arXiv-vs-journal pairs. Recorded here as an out-of-scope find; it is not
part of the proposed fix.

## E: fixed 2026-08-05

Implemented as instance-based collision resolution in
`generate_bibliography.py` (`_citation_instances`, `_resolve_collisions`),
wired between the matcher (`_collect_matches`) and dedup in
`find_cited_entries`: `records = _resolve_collisions(_collect_matches(...),
review_text)`. Commits: `917850d` (Task 1, `ascii_variants` owner in
`bib_identity`), `fb6623e` (Task 2, symmetric transliteration matching),
`be5ab30` (Task 3, anchored `_collect_matches` refactor), `e5e863a` (Task 4,
instance-based collision resolution), `e5cb717` (Task 4 review-round fix,
decouples first- and second-position instance signals), `970b117`
(final-review fix-wave: C1 left-anchor guard on `_CITE_INSTANCE_RE`, I1
`_second_position_corroborated`, M2 drops the dead hit-span payload from
`_collect_matches`). Full suite: 1332 green.

**Resolution rule.** Bib entries sharing `(first-author surname, year)` are
grouped by variant-intersection connected components. Each group is
resolved against citation instances parsed from the *original* review
prose (`solo`, `and`, `etal` forms), per house style's discriminators
(second-author surname, `et al.` for 3+ authors, first initial/name for
solo authors sharing a surname). Four branches, keyed on whether a
first-position instance was seen for the group and whether it
discriminated a candidate:

1. First-position instance(s) seen, and at least one discriminates a
   candidate → keep the supported member(s), drop the rest (with a
   `[COLLISION] dropped …` stderr note per drop).
2. First-position instance(s) seen, but none discriminates a candidate
   (genuinely unresolvable form, e.g. "Muldoon and Gordon" against an
   and-Wu/and-Qi pair) → keep ALL members, one `[COLLISION] ambiguous`
   warning. A second-position sighting elsewhere in the text can never
   override this branch into a drop.
3. No first-position instance seen, but a second-position sighting exists
   (this group's surname appears as the second author of an "and" instance
   elsewhere, e.g. "Bloggs and Muldoon" against a Muldoon-first-author
   group) AND that sighting is *corroborated* by an actual bib record
   (I1, `_second_position_corroborated`) — some entry, anywhere in the
   bib, whose own first author matches the instance's first-position
   surname and whose second author matches this group (e.g. a
   `Bloggs, Joe and Muldoon, Ryan` entry actually backing "Bloggs and
   Muldoon") → drop all members. An *uncorroborated* sighting - a
   narrative co-mention with no bib record behind it, e.g. "Following
   Kripke and Putnam (1975)" with no Kripke entry anywhere in the bib -
   is not evidence against the group and falls to branch 4 instead.
4. Neither → keep ALL members, `[COLLISION] ambiguous` warning (pure
   narrative mention, no parseable form at all).

Warn-and-keep-all (branches 2 and 4) is the deliberate default whenever the
prose doesn't affirmatively discriminate. The accurate invariant: **a drop
requires affirmative instance evidence** — a first-position instance that
discriminates a candidate (branch 1), or a second-position sighting
corroborated by an actual bib record (branch 3). Two narrow, documented
paths can still lose a genuinely cited work despite this (see "Residuals,
accepted" below): the C1 left-anchor guard's rejection direction is
keep-all/safe (it never manufactures a spurious drop), but a work cited
only through a form `_CITE_INSTANCE_RE` cannot parse, combined with an
unrelated *corroborated* second-position sighting of the same group, can
still drop that work along with the rest of the group.

**Same-author groups are deliberately left whole for F.** Three same-author
same-year works (Menary 2010 ×3) share every discriminator this fix has
access to (surname, author-list shape, first initial), so they always fall
to branch 2 or 4 and stay whole with a warning — resolving them needs
Chicago `a`/`b` suffixes (F), which E does not attempt.

**Side effect: straight/curly apostrophe matching.** The symmetric
transliteration fold added for item 3 B, every-citation-resolves
(`bib_identity.ascii_variants`/`translit_fold`), unifies `'` and `’` as part
of its lowercasing, so a bib entry's straight apostrophe now matches a prose
curly apostrophe and vice
versa (bib `O'Neill` meets prose `O’Neill`) — this did not match on the
pre-item-3-B base, which only NFKD-ASCII-folded text and so dropped `’`
(non-ASCII) while leaving `'` (ASCII) in place, producing two different
strings.

**Scope note: `check_evidence.find_cites` is untouched.** It keeps its own
copy of the `(surname, year)`-within-`_MATCH_WINDOW` logic
(`check_evidence.py:38`, "mirrors `generate_bibliography._MATCH_WINDOW`")
for evidence-tier telemetry, not for the References-rendering path E fixes.
Collision smearing in that telemetry is unaffected by this fix, consistent
with "Interaction with the evidence tier" below.

**Residuals, accepted:**

- **Sentence-adverb lead-ins defeated first-position discrimination —
  FIXED 2026-08-05** (`0a44066`). The C1 left-anchor guard's bare-comma
  branch (`Name, ` before the match) could not tell a dropped list member
  from a capitalized transition word, so "However, Muldoon (2023) argues"
  (also Indeed,/Moreover,/Elsewhere,) rejected the instance and the group
  fell back to warn-and-keep-all — the pre-E status quo, visibly warned,
  never a wrong drop. The recorded fix direction was "require the
  comma-preceding token to itself look like a surname", which is not
  decidable by shape (a transition word and a surname look identical there);
  what shipped instead is a stoplist of ~50 sentence-initial transitions
  excluded from that branch via negative lookahead. The and/& branch is
  untouched — no transition word appears in that position — and an
  **unlisted** transition still degrades to keep-all, never to a drop, so the
  list being incomplete stays safe. Two tests pin both directions, including
  the interaction that must not regress: a transition word *before* a genuine
  comma list ("However, Muldoon, Wu, and Li (2023)") must still reject the
  second-name binding.
- **Bare-apostrophe possessive not stripped.** `_strip_possessive` handles
  `'s`/`’s` (the trailing `s` is required); a bare-apostrophe possessive on
  a surname already ending in `-s` — "Rivers' (2020)" rather than
  "Rivers's (2020)" — keeps its trailing `'` as part of the captured
  surname and folds to a variant that will not match a bib entry's plain
  "Rivers". Not fixed: the correct rule (bare `'` at a word boundary is
  possessive only for surnames already ending in `-s`) risks false
  positives against surnames that end in `'` as a matter of orthography,
  and no test case exists to validate either direction.
- **Unparsed narrative forms fall to keep-all, UNLESS a corroborated
  second-position sighting also exists for the group (honest limit, not
  fixed).** `_CITE_INSTANCE_RE` only recognizes `solo`/`and`/`etal`
  shapes; a work cited only through some other narrative form (a
  possessive with an intervening word — "Muldoon's own 2023 monograph
  disagrees" parses to NO instance at all, since the year isn't
  immediately adjacent to the surname) contributes no instance of its
  own. If nothing else in that (surname, year) group has an instance
  either, this reaches branch 4 (keep-all-and-warn) — never a drop. But
  if an *unrelated* sentence elsewhere in the text supplies a
  *corroborated* second-position sighting for the same group (branch 3,
  I1) — e.g. "Bloggs and Muldoon (2023) note this. Muldoon's own 2023
  monograph disagrees." against a bib that has both a solo-Muldoon entry
  and a `Bloggs, Joe and Muldoon, Ryan` entry — the whole group,
  including the unparseably-cited solo work, still drops. I1's
  corroboration check only distinguishes narrative asides (no bib entry
  backs the sighting) from real co-author sightings (a bib entry backs
  it); it cannot also recover a same-group member cited through a form
  the instance regex never parses.
- **Particled FIRST surnames never intersect instances.** The regex keeps
  the first surname single-token, so a particled first surname ("van der
  Deijl") never matches an instance's `surname_variants`; its group
  therefore always falls to keep-all-and-warn (documented in the
  `_PARTICLED_SURNAME` comment in code).
- **Left-anchor guard on `_CITE_INSTANCE_RE` (C1, fixed, safe-direction
  residual).** The regex has no left anchor, so it could bind at a
  non-initial name — the second item of a longer comma list ("Smith,
  Jones, and Lee (2020)" misread as "Jones and Lee"), or right after an
  ampersand ("Jones & Lee (2020)" misread as a bare solo "Lee") — and
  manufacture a phantom discriminator. `_NON_INITIAL_PRECEDING_RE`
  rejects a match whose preceding text ends in a capitalized name
  followed by `, and `/` & `/a bare `, `. The rejection direction is
  keep-all/safe: a rejected match simply contributes no instance, which
  can only push a group toward branches 2/4 (keep-all), never manufacture
  a drop. It cannot, by itself, recover a work whose only citation was
  the now-rejected (and always-wrong) binding — that work still needs
  some other legitimate instance, or the group's genuine members fall to
  keep-all-and-warn together, which is the safe outcome.
- **Collision resolution runs before dedup (accepted, narrow).**
  `find_cited_entries` calls `_resolve_collisions` before the DOI/
  fallback-key dedup loop, so a duplicate pair with divergent author-list
  lengths can lose the RICHER copy's fields, not the truncated one's.
  Example: a solo-form citation against a truncated 1-author duplicate
  and its richer 3-author twin (same title/year) — collision resolution
  discriminates on author-list shape (`solo` form selects the `n == 1`
  entry) and drops the 3-author entry outright, so it never reaches the
  dedup loop where `_union_substantive_fields` would otherwise have
  copied its `journal`/`volume`/`pages`/`doi` into the survivor; the
  surviving 1-author entry keeps only its own scant fields. Narrow and
  accepted, not fixed. **Protected on the real pipeline**: `dedupe_bib.py`
  runs before `generate_bibliography.py` in Phase 6 (`SKILL.md` step
  order), so a duplicate pair is already merged to one entry, with fields
  unioned, before collision resolution ever runs — this residual is
  reachable only when a bib reaches `generate_bibliography.py` with the
  duplicate still unmerged (e.g. a standalone/manual invocation that
  skips the dedupe step).
- **The two-Johnsons sub-shape: writer-facing half LANDED 2026-08-05**
  (`1b1162b`), so this now rests on writer compliance rather than on nothing.
  `_first_text_informative` discriminates two solo same-surname authors only
  when the prose already carries a first initial or first name ("G. Johnson
  (2024)"). `docs/conventions.md` now carries an in-text-citation row plus the
  rule and why it is load-bearing here (a bare surname cannot be resolved to
  one of two entries, so both get listed and one is a reference the review
  never cited), and `agents/synthesis-writer.md` instructs the writer to
  supply the initial — and to prefer "Muldoon and Wu 2023" over "et al." when
  the bibliography holds both. A bare "Johnson (2024)" still can't
  discriminate and still falls to branch 2/4 (keep-all-and-warn), so the hole
  is closed only for compliant prose. **The rider fired on the live run of
  item 3 F, Chicago a/b disambiguation (2026-08-07): not compliant.** The run's
  only same-surname pair was
  Onora vs Martin O'Neill in *different* years — a case the landed same-year
  instruction does not even cover — and the writer carried no initial. The
  same-year two-Johnsons shape itself went unexercised (no such pair occurred
  in the run), so compliance for the instructed case is still unverified, and
  the cross-year case is tracked as the first-initials gap in `ROADMAP.md` §3
  (all that remains of item 3).

## Interaction with the evidence tier

`check_evidence.find_cites` shares the same `(surname, year)` matching, so a
collision smears tier attribution across colliding entries — this is one
source of the checker's false-positive rate (the A/B adjudication found 4
of 6 flagged findings were proximity artifacts). It is **telemetry only**.
The Phase 3→4 barrier stamps entries from abstract evidence before any
prose exists, so barrier correctness is unaffected.
