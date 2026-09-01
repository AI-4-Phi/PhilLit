# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Dynamic-workflow orchestration for Phases 3–5** — unstarted, and two gates
stand before implementation: whether the service's run path can reach a
workspace `.claude/workflows/` at all (it vendors this skill, and the mirror
rule is unconditional), and a re-run of the hook gate test, whose evidence is
from a Claude Code two dozen versions back. Design, status and both gates:
`docs/ideas/dynamic-workflow-refactor.md`, which owns them.

**Lint WARN on contraction-only citation resolutions** — undecided, blocked on
a measurement. `lint_md`'s `_fold_variants` is `ascii_variants` bare, so
`ascii_variants`' accepted residual (b) resolves silently there and turns a
correct ERROR into a clean pass (stated in full in that function's docstring —
do not re-litigate the residual itself). The candidate fix is a WARN whenever a
citation resolves ONLY through the contraction axis. **Measure the
false-positive rate first**: the WARN would also fire on every legitimate
Müller/Muller pair, which is the common case, and a checker that cries wolf on
the common case is worse than the silent residual. Harness:
`docs/known-issues/surname-contraction-measurement-2026-08-29/`.

**A reprint is never deduplicated against its original, so one work can be
cited twice as two positions** — raised by the service's first two user reviews
(2026-09-01). Service review `de3fdffee15349fa` cites Reiman's "Privacy,
Intimacy, and Personhood" as two works — via the 1984 CUP anthology and the
2017 Routledge one — and the synthesis prose calls the second "a structurally
different account" of the first. It is one essay. **This is NOT the reprint-year
question dismissed on 2026-08-11** (`known-issues/item7-reprint-seeding-2026-08-11/`,
binding form beside `_REPRINT_CAPABLE_TYPES`): that ruling stands, both entries
are individually coherent, and nothing here asks for a year to change. The
defect is the interaction. `dedupe_bib`'s title axis (`_fallback_key` →
`bib_identity.fallback_key`) keys on `(normalized_title, year, first-author
surname)`, so a coherent reprint year — exactly what the ruling protects —
guarantees the two entries never merge. Both axes are individually right and
jointly blind. **Measure before fixing**: dropping `year` from that key would
also merge genuine same-title/same-author/different-year works (revised
editions, annually reissued reports), so the false-merge rate decides whether
the fix is a merge, a "same work" annotation the writer can see, or a lint
WARN. Also decide what the writer should then cite — the edition read, or the
work. Service-side record: `phillit-service/docs/known-issues/reprint-double-citation.md`.

**A domain researcher can skip writing its encyclopedia slug file** — raised by
the service's production runs (2026-09-01). In service review
`d474e00d140a4b10`, 2 of 8 domain researchers wrote no
`encyclopedia_entries-domain-N.json` at all, so the evidence barrier recorded
`status: degraded`. The barrier is behaving correctly and needs no change:
`resolve_context.load_slug_files` already separates `missing` from
`valid-empty`, and `valid-empty` is the sanctioned "looked, found nothing" (a
third domain in the same run was `valid-empty` and did not degrade). So the fix
is on the researcher side — make writing the file unconditional, including when
it is empty. Incidence is 1 run in 4, with a clean run at the same pin on the
same day, so this is agent non-compliance rather than a regression; it will
recur. Consequence when it fires: encyclopedia entries in the affected domain
cannot resolve to a SEP/IEP slug (that run's domain 1 had nominated
`sep2026carnap` and `iep2026explication`, both landing EVIDENCE-NONE). Do not
over-attribute — a domain with a `present` slug file in the same run still
produced a `no_url` SEP entry, so `no_url` has other causes.

**Make `disambiguate_container`'s reopen threshold measurable** — the
accepted bail-path residual (v0.5.6, `verify_paper.py` docstring) says it
reopens above "roughly 30% of multi-element chapters" bailing, but by the
docstring's own admission neither cache retains the raw `container-title`
array, so the bail rate is uncomputable and the residual has no working
reopen mechanism. Cheap fix: count multi-element arrays and bails in the
existing debug/enrichment output, so the at-risk subset becomes measurable
from a run's artifacts instead of unmeasurable in principle. Raised by the
service's 7911770 pin review (glm-5.3 round, 2026-09-01).
