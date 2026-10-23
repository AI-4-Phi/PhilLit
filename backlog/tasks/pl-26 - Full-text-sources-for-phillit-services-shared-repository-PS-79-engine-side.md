---
id: PL-26
title: Full-text sources for phillit-service's shared repository (PS-79 engine side)
status: To Do
assignee: []
created_date: '2026-10-23 12:03'
updated_date: '2026-10-23 14:09'
labels: []
dependencies: []
type: feature
project: Delivery
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** phillit-service's PS-79 (shared full-text repository on the box; spec owned there) needs three engine pieces in `acquire_fulltext.py` / `fulltext.py`. Engine changes are built and tested here and reach the service by re-vendor.

Scope, as agreed with the phillit-service session on 2026-10-23 (both new sources are off unless their env var is set, so local PhilLit is unchanged). The PS-79 spec is the authority for the file formats; this card holds the engine side:
- **Repository source**, tried first, under `PHILLIT_FULLTEXT_REPOSITORY_DIR` (a flat, read-only directory in the store format, on the box `/srv/phillit/fulltext/records`, stem = `fulltext.slug_for(identity)`; its `.txt` is `render_text(pages, None)`, no page map; a rare slug collision gets a hash-suffixed stem this lookup will not find, accepted; a missing or unmounted directory must read as source `unavailable`, never a crash). On a hit, never copy the sidecar: run `check_pdf` against THIS run's identity and store through `write_record` with `source="repository"`, the original source/ref in `source_ref`, the original `license`. Reason: the barrier binds no-DOI records by `same_work_key` on the sidecar's raw identity. Uploads in the repository serve every review (Johannes, 2026-10-23; CLAUDE.md, Objectives).
- **Service source**, replacing the direct OpenAlex/S2 downloads under `PHILLIT_FULLTEXT_REQUEST_DIR`:
  - Request `<id>.request.json` (atomic temp + rename): `{"schema": 1, "request_id", "mode": "gaps"|"single", "identities": [{"key": fulltext.canonical_identity, "doi", "title", "surname", "year"}]}`. `<id>` matches `^[a-z0-9-]{1,40}$` and equals the filename stem. The worker recomputes `key` and refuses a mismatch. Caps: 256 KB per file, 500 characters per field. Identities only, never a URL.
  - Response `<id>.response.json`, rewritten atomically after each outcome: `{"schema": 1, "request_id", "complete": bool, "outcomes": {"<key>": {"status": "found"|"none"|"unlicensed"|"failed", "stem", "detail"}}}`. Failed details: timeout, too_large, not_pdf, identity_rejected, blocked_host, removed, bad_request, budget, aborted. A key still absent when the script stops waiting maps to the existing `deadline` outcome, so `not_found` and `deadline` stay distinct.
  - The script writes `<id>.closed` when it stops waiting. `--gaps` becomes store and repository per entry, then one request, then a wait bounded by the 420 s pass deadline. Single-work mode (Phase 1 anchors) runs with no deadline today and needs a 420 s cap in this mode.
  - The worker copies complete records into `intermediate_files/fulltext/`, validated on arrival exactly as now. Sidecars: `source` = "openalex" or "s2"; `source_ref` = `{"url", "kind": "cc"|"oa_repository"|"author"|"publisher_free", "service": true}`; `license` = the location's licence, else `"oa:<kind>"`. Uploads: `source` "user", `source_ref` `{"kind": "upload", "service": true}`, `license` "upload". `_sidecar_shape_ok` already accepts these shapes. The copied sidecar's `identity` is the requester's identity dict as sent, written under `slug_for` of it: the collision check (`store_state`) compares it with this run's canonical identity. The fetch path serves DOI identities only; a no-DOI identity comes back `none` / `no_doi` and reaches reviews only through the repository source.
- **Late copies are safe** (checked 2026-10-23 against HEAD 712e645). The worker's own clock (arrival + 400 s) may land a copy after `.closed`. Nothing reads `fulltext_acquisition.json` but a tree listing in SKILL.md: the barrier lists the store directory and validates each stem itself; `check_quotes.license_status` authorizes from the evidence report's attestation and the text hash, and never re-tests the licence string; the barrier re-renders every bound record's `.txt` with its page map. So a late copy is either a valid record the next barrier pass binds, or, caught mid-copy, a stem the barrier withholds under a named reason (`sidecar_unreadable`, `pdf_hash_mismatch`), never a failure. Contract addition sent to the service: write the PDF and `.txt` first and the `.json` sidecar last, each through temp + rename with a `.tmp` suffix (`write_record`'s order), so a half-copied record reads as pdf-without-sidecar.
- **Licence policy**: ONE shared rule (`_licensed`), applied as the backstop on every source, the repository and the service included. Today the cc filter applies only under `PHILLIT_FULLTEXT_LICENSED_ONLY`; local PhilLit has no licence filter, and must keep none. So: `PHILLIT_FULLTEXT_POLICY=open` gives `open` (cc, `oa:*`, `upload`); else `LICENSED_ONLY` gives `cc`; else no filter. `LICENSED_ONLY` keeps its other half (Zotero and folder off). The worker sets both. `open` admits a free-to-read PDF on a publisher's own site with no licence (`oa:publisher_free`; Johannes, 2026-10-23). Read `POLICY` like `LICENSED_ONLY`: from the process environment, in `main()`, never at import time, `.env` ignored. The worker assigns `kind`, so the OpenAlex repository-vs-publisher labelling is the service's measurement, not ours.
- `fulltext.SOURCES` gains only `repository` (the service channel records the location's own source); a repository hit is status `acquired`, not a new status.
- Optional, not needed here: the barrier could reuse a cached page extraction when the PDF hash matches.

PS-79 approved by Johannes (2026-10-23); the service side is being built against a fake engine.
<!-- SECTION:DESCRIPTION:END -->
