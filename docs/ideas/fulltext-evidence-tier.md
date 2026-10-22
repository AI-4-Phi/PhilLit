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
1. Store keyed by DOI, or by a title-author-year slug for a work without
   one (citekeys are minted later and diverge across domains): `intermediate_files/fulltext/<doi-slug>.pdf`, a `.txt` with
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

Knock-on edits: `/phillit:setup` (Zotero and PDF-folder consent), `TIER_RANK`/`compute_tier`, dedupe's re-stamp,
SKILL.md's "no override needed" list, planner and writer tier tables and
Source Check, `conventions.md` Evidence Tiers, `split_delivery.py`, and the
phillit-service re-vendor.

**Decided** (2026-10-21/22):
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
  about 95% of right papers; against every other sampled item (148 x 147
  pairs, `idbar_nxn.py`) it accepted 1 wrong one, a paper that cites the
  target and has no DOI on its page 1. Rejected: the DOI string alone
  (accepts only 62% of right papers); and title words plus surname (accepts
  1 wrong paper in 148).
- **No write-block hook on `fulltext/`.** The barrier re-extracts the PDF,
  checks both hashes and re-runs the identity check, so an edited or forged
  file fails there. Rejected: a hook like `block_ledger_write.py`; it is no
  security boundary (Bash bypasses it) and costs a `fast_gate.sh` needle.
- **Page numbers: printed pages only when the PDF confirms them against the
  bib entry** (its page headers match the `pages` range, or the journal uses
  article numbers and its pages start at 1); otherwise no page number.
  Measured on 149 Zotero PDFs (`pagenum.py` in the same directory): 98 (66%)
  confirmed; in all 12 of 110 disagreements the PDF was another version
  (online-first, preprint) or the field held an article number. Rejected:
  header numbers whenever consistent (87%, but 12 of 110 would cite another
  version's pages); the PDF page index (not findable in the published
  article, not Chicago).
- **Quotation length: at most 40 words per quotation, run into the text
  (no block quotes), and at most 150 words in total from any one work
  across the review.** The per-work total bounds copyright exposure; the
  numbers are a judgment, not a measurement. Rejected: a per-quotation cap
  alone (no bound on many quotes from one paper); no cap.
- **The Phase 6 quotation check is an accuracy gate on verbatim accuracy
  only.** A quotation attributed to a FULLTEXT work that is not in its text
  (after normalizing hyphenation, ligatures and quote marks) fails closed:
  the orchestrator corrects or cuts it and reruns the check. Page numbers and
  caps are pragmatic, not gates: a quotation without a page number is fine
  when the page is unconfirmed (a page that is shown must be a confirmed
  one, and the fix is to drop it, never to cut the quote), and a cap overrun
  is a warning to shorten, with some tolerance. Rejected: a gate on all
  three (pages and caps would cut accurate quotes); telemetry only (a
  misquotation is a fabrication).
- **Scope: the works the request names, plus `EVIDENCE-EXISTENCE` entries
  with an OA PDF** (gap filling, not upgrading). Measured on the
  justified-harm review (`oa_coverage.py`): OpenAlex has an OA PDF link for
  48 of 97 ABSTRACT entries but only 1 of 25 EXISTENCE entries. Rejected:
  named works only (leaves reachable gaps); any entry with an OA PDF (about
  40% of entries, mostly upgrades, at the cost of downloads, barrier time
  and writer reading load).
  Gap candidates are entries a researcher left without an `abstract` (the
  tier is known only after the barrier); this also tries entries that
  later earn CONTEXT or WEB and misses abstracts that fail corroboration.
  Rejected: the exact EXISTENCE set via a second barrier run (doubles the
  barrier's time near the 600 s Bash ceiling).
- **Sources, in order: the user's Zotero library (local sessions only), then
  OpenAlex, then Semantic Scholar.** "With an OA PDF" in the scope ruling
  reads "with a PDF from these sources". Zotero comes first because a
  user's copy is more often the version of record, which page confirmation
  needs. Access is Zotero 7's local API (`localhost:23119`, read-only; the
  user enables it in Zotero's settings; `/items/<key>/file` answers with a
  302 to the stored file's `file://` path, checked here; legacy linked
  files stored as Mac alias blobs give no path), never `zotero.sqlite` or
  an MCP server; when it does not answer (Cloud, the service, Zotero closed) the
  step is skipped and the report says so. Zotero also holds works without a
  DOI, so the store key, the barrier's entry binding and the identity check
  need a no-DOI path (match by title, first author and year; the PDF text
  bar is the next ruling); books have no `pages` range, so they
  get no page numbers. Measured on the justified-harm review
  (`oa_sources.py`, `zotero_coverage.py`): of 25 EXISTENCE entries,
  OpenAlex reaches 1, Semantic Scholar 3, Zotero 3. Rejected: Unpaywall
  (needs an email in every request; its data now comes from OpenAlex, not
  measured); OpenAlex alone.
- **Identity bar for a work without a DOI: the title phrase (first 6
  words) starts within the first 600 characters of one of pages 1-5, and
  the first-author surname is on that same page.** Asking where the title
  sits separates the work from a work that cites it. Measured on 179
  no-DOI Zotero PDFs, each against every other (`idbar_nodoi.py` and the
  strict variants in `idbar_nodoi_strict-results.txt`): accepts 135 (75%),
  1 wrong accept in 31,862 pairs (same author, 2-word title). Rejected:
  phrase and surname anywhere in pages 1-5 (79%, 5 wrong, all citing
  documents); the same with the surname limited to pages 1-2 (68%, 3
  wrong); the title-page rule plus the year for titles of 3 words or fewer
  (65%, 0 wrong; books lose most, since a reprint's year differs).
- **Paywalled copies: the user's own copies only, never a proxy or shadow
  library.** Routes: Zotero, a local PDF folder, open access, and a file
  the user hands over (`--pdf PATH`; Human-in-the-Loop asks for a named
  work's PDF). `/phillit:setup` asks whether the user uses Zotero and
  whether they keep academic PDFs in a folder PhilLit may read; on consent
  it helps set each up (Zotero: enable the local API, check it answers) and
  saves the choice and path in the workspace `.env`. Both sources are
  opt-in: without that consent they are never touched. A large folder
  needs a cached index (file name, first-page text), not a scan per review.
  Rejected: no `--pdf` route; an institutional proxy (logins and
  terms-of-use risk a distributable plugin should not carry).
- **phillit-service: openly licensed copies plus user uploads.** The
  service has no Zotero or local folder; it takes OpenAlex and Semantic
  Scholar copies only when they carry an open (CC) licence, which OpenAlex
  reports per location, and lets users upload their own PDFs for a review.
  The licence filter is shared engine code; uploads are the service's own
  work. Rejected: off in the service for now; licensed OA without uploads.
- **Storage: the PDFs and texts stay in the delivered
  `intermediate_files/fulltext/`**, so a revision (which copies the
  delivered folder) has them. A guard keeps them out of the git-tracked
  example reviews. Rejected: deleting them at publish and re-acquiring on
  revision from the sidecar's hashes (a one-off `--pdf` would have to be
  supplied again); keeping the text only (still the copyrighted content).
- **FULLTEXT joins the "no override needed" list** (SKILL.md Phase 4): it
  ranks above ABSTRACT, which is already on it. A named work whose text
  could not be acquired keeps today's override line. This follows from the
  ranking ruling; no alternative was live.
