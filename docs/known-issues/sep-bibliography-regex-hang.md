# SEP bibliography parsing hangs the evidence barrier (catastrophic backtracking)

**Status: OPEN.** Found 2026-08-06 by item 3 F's live headless run — the first
full-pipeline run since the barrier gained its encyclopedia-context step. It is
a **blocking** defect: any review whose SEP set contains one bad entry never
reaches Phase 4.

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

`([^,]+(?:,\s*[^,]+)*)` is the textbook catastrophic-backtracking construct: a
repeated group whose body (`[^,]+`) can absorb the same characters as the outer
`[^,]+`, so the number of ways to partition a comma-separated prefix grows
exponentially. When the required `,\s*(\d{4}|forthcoming),` never matches — an
entry with no year in that position, which SEP bibliographies are full of — the
engine tries every partition before failing.

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

## Fix (not applied — needs its own task and a review)

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
