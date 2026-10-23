---
id: PL-26
title: Full-text sources for phillit-service's shared repository (PS-79 engine side)
status: Needs Johannes
assignee: []
created_date: '2026-10-23 12:03'
labels: []
dependencies: []
type: feature
project: Delivery
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** phillit-service's PS-79 (shared full-text repository on the box; spec owned there) needs three engine pieces in `acquire_fulltext.py` / `fulltext.py`. Engine changes are built and tested here and reach the service by re-vendor.

Scope, as agreed with the phillit-service session on 2026-10-23 (both new sources are off unless their env var is set, so local PhilLit is unchanged):
- **Repository source**, tried first, under `PHILLIT_FULLTEXT_REPOSITORY_DIR` (a read-only directory of records in the store format, looked up by `fulltext.slug_for(identity)`). On a hit, never copy the sidecar: run `check_pdf` against THIS run's identity and store through `write_record` with `source="repository"`, the original source/ref in `source_ref`, the original `license`. Reason: the barrier binds no-DOI records by `same_work_key` on the sidecar's raw identity. Uploads in the repository serve every review (Johannes, 2026-10-23; CLAUDE.md, Objectives).
- **Service source**, replacing the direct OpenAlex/S2 downloads under `PHILLIT_FULLTEXT_REQUEST_DIR`: one batched request file per pass (identities only, never a URL), a per-identity response file from the worker (found / none / unlicensed / failed, so `not_found` and `deadline` stay distinct), records validated on arrival exactly as now. `--gaps` becomes store and repository per entry, then one request, then a wait bounded by the 420 s pass deadline. Single-work mode (Phase 1 anchors) runs with no deadline today and needs a 420 s cap in this mode.
- **Licence-policy mode** for the wider ruling (any CC licence; repository-hosted copies such as university repositories, SSRN and academia.edu even with an unclear licence; authors' and conference sites), kept as ONE shared rule (`_licensed`) that also checks records arriving from the repository and the service. Needs a measurement of how OpenAlex labels repository vs publisher locations.
- `fulltext.SOURCES` gains `repository` and `service`; a repository hit is status `acquired`, not a new status.

**Decision needed:** approve the PS-79 spec in the phillit-service session (the interface may still move), and rule PS-79's open question: is a free-to-read PDF on a publisher's own site, with no licence, admitted?
<!-- SECTION:DESCRIPTION:END -->
