# PhilLit Roadmap

Open engineering work, in rough priority order. Detailed problem write-ups
live in `docs/known-issues/` (one file per issue; each carries a Status
line); forward-looking design sketches live in `docs/ideas/`. This file
exists so open work has a single place to be listed — it was created
2026-07-24 alongside the bib-pipeline item below.

## 1. Evidence-tier citability — replace the INCOMPLETE exclusion (NEXT UP, dual-repo)

The agreed next build (Johannes, 2026-07-24). The `INCOMPLETE` exclusion is
unfollowable and fails in both directions — Claude cites excluded canon
anyway (zero discipline), weaker downstream models obey and produce false
claims of absence. Replace it with a script-stamped evidence tier
(`EVIDENCE-ABSTRACT` / `-CONTEXT` / `-EXISTENCE` / `-NONE`) plus a mechanical
encyclopedia-context acquisition pass (`resolve_context.py`).

- **Write-up (start here):** `docs/known-issues/incomplete-exclusion-unfollowable.md`
  — both failure modes with evidence, the tier design, this repo's own
  path/line map, and seven implementation catches.
- **Full spec:** sibling repo,
  `phillit-service/docs/superpowers/specs/2026-07-24-evidence-tier-citability-design.md`
  (v3, dual-repo — carries the path/line maps for both trees).
- **The fix lands in BOTH repos at the same time; BUILD HERE FIRST** — runs
  here are free under Claude Code, the service bills every run through the
  Agent SDK. Then port to the service's vendored `engine/.claude/`. The free
  Sonnet control run here also settles an external reviewer's blocking
  objection to the downstream spec.
- Supersedes the INCOMPLETE-keyed parts of item 2's Issue C (the no-marker
  case); C's residual — a *forged* `abstract_source` — stays open and is
  revisited together with this spec (service roadmap item 23).

## 2. Bibliography-pipeline integrity fixes

Four related gaps, surfaced 2026-07-24 by the downstream `phillit-service`
model-experiment audit and written up in
`docs/known-issues/bib-pipeline-integrity-gaps.md`:

- **A — cleaner-unaware dedup** (`dedupe_bib.py`): cross-domain duplicate
  merging can resurrect a field the metadata cleaner stripped as
  unverifiable. Deterministic; affects plugin runs today.
- **B — silent References omission** (`generate_bibliography.py`): a
  body/bib author-spelling divergence beyond NFKD normalization silently
  drops a cited work from the rendered References; no
  every-citation-resolves post-check exists (natural home: `lint_md.py`).
  Deterministic; affects plugin runs today.
- **C — unenforced abstract provenance**: an invented `abstract` field with
  no `abstract_source` marker passes every gate and evades the
  INCOMPLETE-keyed cite-cautiously rule. Structural; the observed exploit
  was under a non-Anthropic orchestrator, but nothing model-specific closes
  the gap. *Partly superseded by item 1*: the tier design closes the
  no-marker case (top tier requires `abstract_source`); the forged-marker
  residual remains and is revisited with the item-1 spec.
- **D — no venue-quality vetting**: predatory-venue papers pass DOI
  verification; flag-and-caveat heuristics (DOAJ lookup, `VENUE_UNVETTED`
  keyword + writer rule) would turn observed good model behavior into a
  pipeline guarantee.

Suggested order: A+B first (small, testable, deterministic), then C
(mechanical validator rule), then D (heuristics + prompt rules).
Cross-repo: fixes land here or in the service's vendored engine and are
cherry-picked to the other side — same path as the metadata-cleaner year
fix (plugin 0.2.6 ↔ service `7369880`). The service tracks the mirror item
as roadmap item 23.

## Backlog pointers

Other open items are tracked in their own known-issue docs — see
`docs/known-issues/` for anything whose Status line is still Open (e.g.
`ndpr-enrichment-underused.md`, `recent-publication-indexing.md`,
`philpapers-rate-limiting.md`).
