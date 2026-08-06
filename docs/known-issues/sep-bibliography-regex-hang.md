# SEP bibliography parsing hangs the evidence barrier (catastrophic backtracking)

**Status: FIXED 2026-08-06** (`e455b26` the parser, `82fd84e` the backstop).
Found the same day by the first full-pipeline live run since the barrier gained
its encyclopedia-context step. It was a **blocking** defect: any review whose
SEP set contained one bad entry never reached Phase 4.

**What shipped**

1. `parse_bibliography_entry` now splits on commas in ordinary Python and finds
   the year field by scanning, instead of matching a comma-structured regex.
   Linear in the line length. It still runs regexes — the year-field test, the
   partial form, the editor marker, the skip patterns — but each is anchored or
   bounded and none contains nested ambiguous repetition, so none can backtrack
   combinatorially. (An earlier version of this note claimed "no repetition to
   backtrack through", which is false; the repetitions are there, they are just
   unambiguous.) Measured on the shape that hung the run: **3.5 s → 0.000007 s**
   at 22 commas, and instant at 200. A 2000-character bound rejects absurd lines
   outright, so no future parser change can be handed an unbounded string. The
   bound rejects the *parse*, not the entry: `extract_bibliography` still keeps
   `raw` with `parsed: None`, exactly as `fetch_iep.py` does for every entry.
   Measured over the local SEP cache (6,731 entries, 41 articles, 2026-08-06):
   median 129 chars, p95 244, p99 319, max 915, nothing above 1,000.
2. `resolve_context.fetch_articles` now takes a **work-admission budget**
   (`PASS_DEADLINE_SECONDS = 600`), checked before each fetch, matching
   `venue_vetting`'s existing idiom. Slugs not reached are reported as
   `failed`, so they show up in the barrier's report rather than silently
   shortening the article set, and a stderr line names how many were skipped.
   **It is not a watchdog and does not bound this pass in wall-clock time.**
   The check sits between fetches, so a single call that never returns is
   never interrupted — i.e. it would not have stopped the incident below.
   What it bounds is the slow-but-progressing pass: cumulative time across
   *returning* fetches. Both external reviews rejected the original commit
   message and comments, which claimed otherwise. A per-article interrupt was
   considered and declined — see "Declined", below.

3. The two call paths have different risk postures, deliberately. The direct
   `fetch_sep.py` CLI (`--sections "...,bibliography"`, Stage 1 of every
   review) has **no** time bound of any kind; its protection is that the
   parser is now linear. Only the barrier's acquisition pass has the budget.

4. The year field is chosen by scanning for the **first** field that is exactly
   a year, **skipping any whose successor is also year-like**. First-not-last
   is a deliberate change from the old greedy regex, and the better rule on the
   common multi-year shape (a later reprint/translation/edition year). The
   skip exists because taking the first year on
   `Whitehead, Alfred and Bertrand Russell, 1910, 1912, 1913, Principia
   Mathematica, ...` — a real entry in the cached corpus — yields
   `title="1912"` at `"high"` confidence. Sweeping the 6,731 cached entries,
   that Whitehead line is the **only** one whose parse the guard changes.

**The timing regression tests assert TIME, not return values** — the old code
returned the right answer for every input below, just geometrically slower, so a
value-only assertion passed while the bug was live. They carry
`@pytest.mark.timeout(30)`: under the old regex they *hang* rather than fail,
which would wedge CI instead of reporting. Verified by reverting the regex —
both timing tests fail at 30 s.

**The value tests pin equivalence to the regex they replaced.** Four shapes —
comma-bearing title, `–––` repeated author, no trailing period, adjacent second
year — were run against the pre-rewrite `parse_bibliography_entry` (loaded out
of `c4ab520`) and are byte-identical old vs new. The two deliberate divergences
are the adjacent-year guard and the empty-title rejection, and nothing else in
the 6,731-entry cached corpus differs.

**Every test here was mutation-verified.** Two were found vacuous in the
process, which is why the note says so rather than just "verified":

- `test_absurdly_long_entry_is_rejected_not_parsed` used a 500-name comma run
  as its over-cap fixture. That line has no year field, so it is unparseable
  *with or without the cap* — the test passed with the cap check deleted. Its
  fixture is now a well-formed entry padded past 2,000 characters, which
  parses at `"high"` the moment the cap is lifted.
- `test_nothing_is_lost_between_the_two_lists` asserted only
  `len(articles) + len(failed) == len(requested)`, which a duplicate id plus
  an omission satisfies — demonstrated by mutating `failed` to record the
  wrong slug, under which the count assertion still held. It now asserts the
  partition as sets, and lives in `TestFetchOnce`, since it never involved a
  deadline at all.

**Deleting the bibliography was considered and rejected.** It is not dead
weight: `agents/domain-literature-researcher.md:153` has every researcher run
`--sections "preamble,1,2,bibliography"` in Stage 1 of every review, and the
prose instructs them to "parse bibliography for foundational works cited" and
"use bibliography entries as seeds for further search". `fetch_sep.py` also
exposes `--bibliography-only` as a documented flag. It is a primary
literature-discovery path, not a byproduct.

**Layer 2 of the original three-layer plan was dropped, deliberately.** The
plan was to make parsing lazy on the barrier path, since `resolve_context`
filters candidate lines on `raw` text and only uses the parsed dict to prefer a
clean title when scoring. That was justified when parsing cost seconds per
entry; with a linear parser it costs microseconds, so laziness would restructure
the fetch/cache boundary for no measurable gain and add a second code path to
keep correct. The `parsed` field is kept, which also preserves SEP title-scoring
quality — `fetch_iep.py` already ships `"parsed": None` and takes the raw-line
fallback, so that quality difference is real and worth keeping on the SEP side.

---

## Follow-up: a mangled parsed title scores WORSE than no parsed title

**Open. Pre-existing — not introduced by the 2026-08-06 fix, and deliberately
not fixed in it.** Raised by both external reviews of that fix.

`resolve_context._title_text` prefers `parsed["title"]` whenever it is
non-empty, with **no fallback to `raw` when the parsed title scores zero**.
Combine that with the first-comma truncation both the old regex and the new
split parser perform, and a *correct* bibliography line can fail to match:

- BibTeX title `Language, Truth and Logic` → tokens `{language, truth, logic}`
- SEP line `Ayer, A.J., 1936, Language, Truth and Logic, London: Gollancz.`
  parses to `title="Language"` → tokens `{language}` → overlap 1
- `TITLE_MIN_OVERLAP` is 2 → score 0.0 → **no CONTEXT match**

Scoring the same entry against the whole raw line would have matched. So SEP's
`parsed` dict, which exists to *improve* title scoring, inverts on
comma-bearing titles: IEP's `"parsed": None` entries do better on exactly these
works, because `None` is falsy and activates the raw fallback while a wrong
non-empty title suppresses it.

Two candidate fixes, either of which needs its own measurement pass:

1. One line in `match_entry_to_article`: score
   `max(title_score(title, parsed_title), title_score(title, raw))`. Removes
   the inversion, but widens what can match, so it needs a false-positive
   check against the barrier's ambiguity rule before it ships.
2. Make the parser quote-aware, so a `"…, …"` or `'…, …'` title keeps its
   internal commas and the truncation stops happening at the source. Narrower,
   but it only reaches quoted titles; SEP also sets titles in `<em>`/`<cite>`,
   which would be a better boundary still and would mean changing extraction
   rather than parsing.

Two smaller items from the same reviews, recorded and not acted on:

- `publisher = ', '.join(...).rstrip('.')` strips *every* trailing period,
  where the old regex's `(.+)\.$` consumed exactly one (`Press..` → `Press`
  vs `Press.`). Cosmetic, and no cached entry exhibits it.
- The standard branch does not reject an empty **author** or **publisher**
  component the way it now rejects an empty title, so
  `Smith, , Jones, 2020, Title, Press.` still parses at `"high"`.

One review claim was checked and found **wrong**, recorded so it is not
repeated: both reviews said the old regex fell through to partial on an empty
title field. It did not — `["\']?(.+?)["\']?` matched the separator *space*
and returned `title=" "` at `"high"`. Rejecting an empty title is therefore an
improvement on the old behaviour, not a restoration of it.

---

## Original report

## Symptom

`evidence_barrier.py` stops producing output immediately after
`[fetch_sep.py] Article fetched: Virtue Epistemology` and then runs **forever
at 100% CPU**. Observed three times in one run: two foreground attempts killed
at the Bash tool's 600 s ceiling (exit 143), then a manual run left to itself
for **72 minutes** before being killed. No `evidence_report.json` is ever
written, so every entry stays `EVIDENCE-NONE` and the workflow cannot continue.

**This is not a network stall.** `CLAUDE.md` documents a LuLu-firewall hang
whose signature is 0% CPU and no output; this is the opposite — `ps` shows
`%CPU 100.0`, state `R`. `sample` on the live process put **all 2,305 samples
inside `sre_ucs2_match`**, the CPython regex engine, with no I/O frames at all:

```
_sre_SRE_Pattern_match  (in python3.12) + 1808
  1651 sre_ucs2_match ...
   192 sre_ucs2_match ... + _platform_memmove
   178 sre_ucs2_match ...
```

## Root cause

`skills/philosophy-research/scripts/fetch_sep.py:67`, in
`parse_bibliography_entry`:

```python
standard = r'^([^,]+(?:,\s*[^,]+)*),\s*(\d{4}|forthcoming),\s*["\']?(.+?)["\']?,\s*(.+)\.$'
match = re.match(standard, raw_text)
```

`([^,]+(?:,\s*[^,]+)*)` contains **overlapping repetitions**: inside the
repeated group, after each comma both `\s*` and `[^,]+` can consume the
separator space, so every `", "` admits two equivalent ways to match the same
text. Across n comma-space fields that is 2ⁿ equivalent allocations, and the
engine explores them in combination before conceding failure. When the required
`,\s*(\d{4}|forthcoming),` never matches — an entry with no year in that
position, which SEP bibliographies are full of — it works through all of them.

**Corrected 2026-08-06** (both external reviews of the fix caught it): an
earlier version of this section said the inner `[^,]+` "can absorb the same
characters as the outer one" and blamed the number of *partitions* of the
prefix. That is wrong. The outer repeated unit begins with a comma, which
`[^,]+` cannot consume, so the two cannot compete for the same characters and
the comma positions are not in fact ambiguous. The separator whitespace is what
is ambiguous — which is also what fits the measured growth below (~2x per
comma, i.e. one binary choice per field, not a partition count).

Measured directly on the shipped pattern (each row is a comma-separated author
list with no parseable year):

| commas | input length | `re.match` time |
|---|---|---|
| 10 | 154 chars | 0.0009 s |
| 12 | 176 chars | 0.0037 s |
| 14 | 198 chars | 0.0149 s |
| 16 | 220 chars | 0.0553 s |
| 18 | 242 chars | 0.2214 s |
| 20 | 264 chars | 0.8698 s |
| 22 | 286 chars | 3.5232 s |

Roughly 4x per two commas. Extrapolating: ~30 commas is a quarter of an hour,
~40 is days. SEP's *Virtue Epistemology* bibliography contains entries well past
that threshold.

## Why nothing caught it

`tests/test_fetch_sep.py` covers `parse_bibliography_entry` three ways — high
confidence, low confidence, unparseable — but every fixture is short and
well-formed. None is comma-rich *and* year-less, which is the conjunction that
triggers the blowup. The function has exactly one production caller
(`fetch_sep.py:173`, inside the bibliography loop), so a single bad entry in a
single article stalls the whole barrier.

## Fix as originally proposed (superseded by what shipped, above)

The group does not need to be ambiguous. Either:

1. **Anchor the year first**, so failure is detected before the prefix is
   partitioned — e.g. bail out with a cheap `,\s*(?:\d{4}|forthcoming),` search
   before attempting `standard` at all; or
2. **Make the prefix unambiguous** by removing the nested repetition, e.g.
   `^((?:[^,]+)(?:,[^,]+)*?)` is *not* sufficient — prefer a possessive/atomic
   formulation, which Python's `re` lacks, so the practical fix is (1) or
   splitting on commas in ordinary Python and reassembling.

Whichever is chosen, **the regression test must be the timing itself**: assert
that a 40-comma year-less entry parses (or fails) in well under a second.
Asserting only the return value would pass today, since the current code returns
the right answer — eventually.

Two adjacent things worth doing in the same task:

- **`fetch_sep.py:80`'s `partial` pattern is safe** (`^([^,]+),\s*(\d{4})` has no
  nested repetition) — no change needed, but say so, so a later reader does not
  "fix" it too.
- The barrier has **no timeout around encyclopedia context acquisition**. Even
  with this regex fixed, one pathological article should degrade the run to
  "context unavailable" rather than hang it. `SKILL.md` already tells the
  operator a backgrounded barrier can be orphaned; it cannot tell them what to
  do about one that never returns.

## Note on a wrong diagnosis, recorded so it is not repeated

The run's own orchestrator logged "re-running from scratch each time, not
resuming", and I initially agreed and blamed rate-limited cold-cache SEP
fetches. Both readings were wrong. The fetches *are* cached and instant — the
`barrier.err` from the third attempt shows four articles served from cache in
under a second. All three attempts died at the same point in the same article
for the same reason. Cache growth between attempts was real but irrelevant: it
came from articles fetched *before* the hang, not from progress through it.
