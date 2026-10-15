---
id: PL-20
title: Scope the SubagentStop cleaning to the stopping researcher's own bib
status: To Do
assignee: []
created_date: '2026-10-15 13:49'
labels:
  - hooks
dependencies: []
type: bug
project: Accuracy
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** at every researcher's stop, `subagent_stop_bib.sh` cleans and reports EVERY domain bib in the review folder (`$REVIEW_DIR/*.bib`), including bibs that parallel researchers are still writing. A year correction in domain B's bib can be made and reported at domain A's stop, so B never hears of it; and the cleaner can rewrite a bib its researcher is mid-way through editing. This contradicts doc-2's premise that the workspace is single-writer by design.

Seen in the 2026-10-14 justified-harm run (seven parallel researchers; the Gardner year was rewritten in all five bibs that held it, at whichever stop came first).

Scope: decide how the hook identifies the stopping researcher's own file (agent transcript, `last_assistant_message`, or the output path in its prompt), clean and report only that file, and keep the barrier's ledger freshness (it runs after all researchers finish, so a final per-file clean must still have happened). Needs a headless run to validate.
<!-- SECTION:DESCRIPTION:END -->
