# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Service re-vendor.** Run the service's scripted re-vendor (`tools/revendor.py`)
at a pin at or past this repo's tip. Service-session work, never
hand-mirrored — rule in `CLAUDE.md`, "Sister repo: phillit-service".

One thing that run cannot infer: the service filed 19 dangling section
citations across 8 engine files, but only 8 existed here. `source_store.py` is
not in this repo at all, and `fetch_sep`/`fetch_iep`/`fetch_ndpr`/`rate_limiter`
carry no such pointer, so that count was taken from the service tree. The
remaining ~11 sites are the service's own to check — no mirror reaches them.

**Fix the parsed-title inversion in encyclopedia context matching.**
`resolve_context._title_text` returns the parsed title whenever it is
non-empty and falls back to the raw line only when it is *absent* — never when
it scores zero. Both the old regex and the split parser truncate at the first
comma, so a correct bibliography line can score 0.0 and lose its CONTEXT
match: BibTeX `Language, Truth and Logic` against SEP's `Ayer, A.J., 1936,
Language, Truth and Logic, London: Gollancz.` parses to `title="Language"`,
overlap 1, under `TITLE_MIN_OVERLAP`. So `parsed`, which exists to *improve*
title scoring, inverts on comma-bearing titles — IEP's `parsed: None` entries
do better on exactly these works. Two candidate fixes are in the function's
docstring, each needing its own measurement pass; the wider one needs a
false-positive check against the barrier's ambiguity rule before it ships.

**Dynamic-workflow orchestration for Phases 3–5** — unstarted, unblocked.
Design and status: `docs/ideas/dynamic-workflow-refactor.md`, which owns them.

Nothing else is queued.
