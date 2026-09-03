# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

**`dedupe_bib._remove_fields_text` still bounds values with its own scan** —
every other raw-text field locator now goes through `bib_fields` (read path,
keywords stamp and editors, `add_field_to_entry`, the barrier's derived-field
strip, the context strip, dedupe's extractors). This one remover keeps a
private depth scan whose quoted branch is `find('"')` (a `"` protected by
braces cuts the value short) and whose presence test is a `\b<field>\s*=`
regex. Converting it is mechanical (`bib_fields.iter_fields` +
`remove_field`, with the neighbour-vanished guard re-expressed as a
before/after comparison of scanned field names), but three tests pin a
policy the conversion would overturn:
`tests/test_dedupe_bib.py::test_c1_real_field_first_fake_later_reports_failed`
and its two C1 siblings require that a field-name-shaped substring inside
ANOTHER value (`abstract = {We discuss pages = 12}`) make the removal of the
real `pages` field report FAILED and leave the entry untouched — "do not
improve this into a success", a review-verified trade-off from when the scan
was textual and could not tell the two apart. A structural locator can,
so the conservative policy no longer buys safety; whether to keep it is a
decision, not a fix. Exposure today: engine-written values never carry a
protected quote (measured 2026-09-03), so this is consistency, not a defect.

**Dynamic-workflow orchestration for Phases 3–5** — unstarted, and two gates
stand before implementation: whether the service's run path can reach a
workspace `.claude/workflows/` at all (it vendors this skill, and the mirror
rule is unconditional), and a re-run of the hook gate test, whose evidence is
from a Claude Code two dozen versions back. Design, status and both gates:
`docs/ideas/dynamic-workflow-refactor.md`, which owns them.
