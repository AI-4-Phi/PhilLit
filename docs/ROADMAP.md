# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**Raw-text field locators still on one-level regexes** — the shared read
path now goes through `bib_fields.iter_fields` (depth-counting, braced /
quoted / bare / concatenated): `parse_entry_fields`, the enrichment reader,
the keywords stamp and the keywords editors. Four EDIT-side locators keep
their own regex, each with the one-level wall the read side lost:
`dedupe_bib._field_value_re` (keywords, abstract, year_suffix);
`evidence_barrier._DERIVED_FIELD_RE` (the strip before re-derivation, whose
docstring lists three accepted residuals); `resolve_context._CONTEXT_FIELD_RE`;
and the quoted branch of `enrich_bibliography._field_value_end` (`find('"')`,
not brace-aware). Measured exposure at `bib_fields`' landing over 13,757
engine-written field values in `reviews/` (keywords, abstract, year_suffix,
venue_status, same_work_group, sep/iep_context, urldate, archiveurl): no
value nests two deep, no keywords value nests at all, 211 abstracts nest one
deep (within every site's tolerance). So this is consistency and robustness,
not a measured defect: the engine writes these fields flat, and only an
agent- or hand-written value reaches the wall. At the three strip/extract
sites a miss ends as a duplicate or surviving field pybtex rejects or the
next run overwrites; `_field_value_end`'s quoted branch is the one that can
instead cut a value SHORT (`"The {"Q"} result"` ends at the protected
quote), so take it first. Do it site by site with a RED test per site; the tests that pin
`_strip_derived_fields`' residuals (compact / bare / nested values
surviving) are pinning the wall itself and flip to asserting the better
behaviour. `bib_fields.remove_field` is the edit primitive to build on.

**Dynamic-workflow orchestration for Phases 3–5** — unstarted, and two gates
stand before implementation: whether the service's run path can reach a
workspace `.claude/workflows/` at all (it vendors this skill, and the mirror
rule is unconditional), and a re-run of the hook gate test, whose evidence is
from a Claude Code two dozen versions back. Design, status and both gates:
`docs/ideas/dynamic-workflow-refactor.md`, which owns them.
