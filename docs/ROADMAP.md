# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**The References matcher cannot bridge an independently ae-transliterated
surname.** `ascii_variants` returns the NFKD fold and `translit_fold`, both
derived from the input's own diacritics — so it covers its documented case,
body "Fraenken" against bib "Fränken". It does not cover body "Fraenken"
against bib "Franken", where the bib field has already been NFKD-stripped:
neither side carries a diacritic, no ae-variant is generated, and
`generate_bibliography.py`'s surname+year matcher misses the entry. It does
not ship silently — `lint_md.check_citations` flags the miss as an ERROR, and
that path was verified non-vacuous — but the match itself fails. Fix shape: a
symmetric ae/oe/ue fold at match time, collision-aware like the existing one.
Filed by the service in 2026-08, where it was recorded as "fix in PhilLit" and
then never reached this queue.

**Measure what an unrecognized API envelope licenses in the cleaner.**
`metadata_cleaner._ingest_file` dispatches on `api_source` and its `else` arm
falls through to `parse_s2_result`, so a non-paper dump — a SEP or IEP page, a
bare abstract file — is parsed as if it were Semantic Scholar and injects
bare-title entries into the metadata index. That index is what licenses
stripping. Deliberately NOT narrowed when it was found, and the reason is why
it needs a measurement rather than a patch: a thinner presence-index strips
MORE, so narrowing the fall-through could degrade corpora that currently work.
What is owed first is a measurement of what those entries actually license.
Same provenance as the entry above — service-filed, never queued here.

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
