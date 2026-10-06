---
id: PL-10
title: Barrier self-check on its own output
status: To Do
assignee: []
created_date: '2026-09-25 19:18'
updated_date: '2026-10-06 07:15'
labels:
  - barrier
dependencies: []
references:
  - skills/literature-review/scripts/evidence_barrier.py
  - hooks/ledger_binding.py
type: guard
project: Accuracy
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** The barrier marks its own output as trusted. A bug in its renderer would be trusted by the next run, and nothing would catch it. There has been no incident.

The barrier blesses its own output wholesale, not just its stamps. After writing a stamped bib, it re-points the cleaning ledger's `bib_sha256` to that text, because stamping cannot change which entries matched an API record. Nothing ENFORCES that. A bug in the stamping renderer that altered a key, title, year or author, or dropped an entry, would be bound as valid on the spot, and the next run would trust it.

The guard is an invariant: the output must equal the input under a canonical projection that strips what the barrier owns: the `EVIDENCE-*` tokens in `keywords`, and the `year_suffix`, `web_span`, `venue_status`, `same_work_group`, `urldate` and `archiveurl` fields.

**Ruling: narrow guard.** Keep the re-point. Before `_repoint_binding` runs for a domain, check that the input bib and the written bib are equal under the projection. If they differ, do not re-point: the domain fails loudly, naming the entries that changed. No ledger schema change. The projection must use `bib_fields.iter_fields` / `remove_field`, never a new field regex. Pin it with a mutation test: a renderer that alters a key, title, year or author, or drops an entry, must trip the guard.
<!-- SECTION:DESCRIPTION:END -->
