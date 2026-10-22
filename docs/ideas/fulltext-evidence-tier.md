# Full-text evidence tier (sketch)

**Problem.** A review whose question turns on one named paper can get that
paper wrong, because no tier lets a writer use its full text. In the
2026-10-14 run on justified harm, Gardner (2019) had no API abstract, so it
was stamped `EVIDENCE-EXISTENCE`. The review called "justified harm" and
"justified action" terminological variants, and the full text (p. 899) shows
they are distinct problems. Johansson and Risberg (2018) was CC BY and read
in full by the orchestrator, but at `EVIDENCE-ABSTRACT` the writers had to
cut its main arguments.

**Why no current tier can carry it** (checked against the code):
- `EVIDENCE-WEB` is `@misc` only (`evidence_barrier.py`, "a url on an
  @article is decoration and out of scope"), and an entry with an abstract is
  skipped. `compute_tier` ranks ABSTRACT above WEB, so an article never
  reaches WEB.
- A WEB capture is evidence that a fetch happened, not writer input:
  writers read only the `note`, checked against `web_span` fragments.
  `fetch_web.extract_pdf` joins pages with spaces, so page numbers are lost.
- `fetch_web.py` takes only http(s) URLs; there is no path for a local PDF.
- The writer rules correctly refuse a notes file of "verified facts", so
  prompt wording cannot fix this; only a tier the barrier stamps can.

**Sketch.** A new tier `EVIDENCE-FULLTEXT`, ranked above ABSTRACT.
1. Store keyed by DOI (citekeys are minted later and diverge across
   domains): `intermediate_files/fulltext/<doi-slug>.pdf`, a `.txt` with
   `[[page N]]` markers, and a `.json` sidecar (DOI, both sha256s, source:
   OA URL / user file, extractor version, page offset).
2. `acquire_fulltext.py --doi D (--pdf PATH | --url URL)`: resolve an OA
   location (OpenAlex `oa_url`, which the search scripts already return, or
   Unpaywall), extract per page, validate identity (the bar under Decided),
   reuse
   `fetch_web.py`'s printable-ratio and encrypted/no-text checks, and record
   every failure in the sidecar.
3. Barrier: for each entry whose cleaner-verified DOI has a stored text (and
   its `same_work_group`), re-extract, check both hashes, re-run the
   identity check, stamp `EVIDENCE-FULLTEXT` and a `fulltext_file` field.
4. Writer: the licensed field is the text file; quotation allowed with page
   numbers from the markers.
5. Phase 6: `check_evidence.py` verifies every quotation attributed to a
   FULLTEXT key against the file.
6. "Acquire anchor texts" step in Phase 1, after `workdir.py init`: resolve
   each work the request names to a DOI, try OA, else ask the user for the
   PDF (Human-in-the-Loop) or record the gap prominently (Autopilot). The
   planner and researchers then read the text too.

Knock-on edits: `TIER_RANK`/`compute_tier`, dedupe's re-stamp,
SKILL.md's "no override needed" list, planner and writer tier tables and
Source Check, `conventions.md` Evidence Tiers, `split_delivery.py`, and the
phillit-service re-vendor.

**Decided** (Johannes, 2026-10-21):
- **A new tier, `EVIDENCE-FULLTEXT`, ranked above ABSTRACT.** Rejected:
  widening `EVIDENCE-WEB`, which would put two licences under one token (an
  LLM note checked against page fragments, and the source text itself) and
  reverse WEB's `@misc`-only scope and capture-is-not-input rule; and
  attaching the text to the user-request override line, which would move a
  content licence out of the barrier into orchestrator-written prose and
  settle the scope question (named works only) in advance. Measured on the
  justified-harm review: 25 of 127 entries were `EVIDENCE-EXISTENCE`, all
  journal articles with a DOI; none was `EVIDENCE-WEB`.
- **Identity bar: the DOI string in the first 3 pages; else the title's
  first 6 words as a phrase plus the first-author surname, with no other
  DOI on page 1.** Measured on 148 Zotero PDFs with a DOI
  (`docs/known-issues/fulltext-identity-measurement-2026-10-21/`): accepts
  140 right papers (95%) and 0 wrong ones. Rejected: the DOI string alone
  (accepts only 62% of right papers); and title words plus surname (accepts
  1 wrong paper in 148).
- **No write-block hook on `fulltext/`.** The barrier re-extracts the PDF,
  checks both hashes and re-runs the identity check, so an edited or forged
  file fails there. Rejected: a hook like `block_ledger_write.py`; it is no
  security boundary (Bash bypasses it) and costs a `fast_gate.sh` needle.

**Open questions for Johannes** (to adjudicate one at a time):
3. Page numbers: printed pages (offset from the `pages` field, checked
   against page headers); PDF page index; or printed where derivable, else
   none.
4. Quotation: a length cap? Is the Phase 6 quotation check an accuracy gate
   (fail closed) or telemetry?
5. Scope: works the request names only, or any entry with an OA PDF?
6. OA source: OpenAlex `oa_url`, Unpaywall (needs an email in `.env`), or
   both?
7. Paywalled copies: a distributable plugin cannot assume a proxy. OA plus
   a user-supplied file (`--pdf`, e.g. from Zotero) only?
8. phillit-service: full text on a server has a different legal standing.
   Plugin-only, OA-only in the service, or user upload only?
9. Storage: `intermediate_files/` is published into `reviews/`. Keep the PDF
   and text there, or delete them at publish? The example reviews must never
   ship them.
10. Does FULLTEXT on a user-named work replace the tier-override framing, so
    that FULLTEXT joins the "no override needed" list?
