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

Two things that run cannot infer. First, the service filed 19 dangling section
citations across 8 engine files, but only 8 existed here. `source_store.py` is
not in this repo at all, and `fetch_sep`/`fetch_iep`/`fetch_ndpr`/`rate_limiter`
carry no such pointer, so that count was taken from the service tree. The
remaining ~11 sites are the service's own to check — no mirror reaches them.

Second, three assertions in the service's `tests/test_engine_rate_limiter.py`
dereference `openalex_params(...)["api_key"]` and will fail on a bare
`KeyError`: the key moved into an `Authorization` header, closing the
URL-in-exception leak the service itself filed. That failure is the fix
arriving. Intake is *not* a re-pin at the new mechanism — those assertions
welded transport into a test about whether the engine reads
`OPENALEX_API_KEY`, so pin the claim instead (the env-name round-trip through
`openalex_api_key()`) plus a prohibition that the key never appears in
`openalex_params()` output. Three sibling `"api_key" not in ...` assertions now
pass vacuously and the module docstring's mutation counts are stale, so
re-measure. Four service-side prose sites state the old transport:
`transcript.py`'s scrubbing rationale, `config.py`'s strip comment, and two
`test_config.py` docstrings. The scrubber itself stays — it covers every
operator secret, not just this one. All of it lands in the re-vendor commit:
against the engine vendored today the rewrite is RED.

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
