# More full-text sources (PL-27)

**Problem.** `EVIDENCE-FULLTEXT` reaches few gap entries, and no OA source
tries a work without a DOI. Measured 2026-10-24 on 240 works
(`docs/known-issues/fulltext-sources-measurement-2026-10-24/`, local): set A
is every `EVIDENCE-EXISTENCE` entry of four stamped reviews (54 rows, 50
works, all with a DOI); set B is 186 no-DOI entries sampled by type from the
delivered reviews. Every candidate PDF was downloaded and passed through
`acquire_fulltext.check_pdf`; every accepted PDF was audited by hand
(`audit_verdicts.py`).

## Findings

| Source | A hits | B hits | Adds over the sources before it | Wrong accepts |
|---|---|---|---|---|
| OpenAlex by DOI (today) | 3 | - | 3 | 0 |
| S2 by DOI (today) | 2 | - | 1 | 0 |
| OpenAlex title search | 2 | 50 | 50 (B only) | 1 (short title) |
| S2 title match | 1 | 5 | 0 | 0 |
| arXiv title search | 2 | 48 | 4 | 3 (short titles) |
| CORE, HAL, Zenodo, OSF, Crossref | 0-1 | 0-1 | 0 | 0 |
| Brave web search for PDFs | 21 | 109 | 81 | 39 of 130 |

- The OpenAlex title route adds nothing on set A, and its B gain is almost all
  CS/ML: 45 of 50 are arXiv or ML proceedings; about 4 are humanities or law.
  48 of the 50 hit records carry a DOI in OpenAlex (37 arXiv DOIs). A title
  search costs 10 credits ($0.001); a DOI lookup is free with the key.
- A word-bounded match on the 6-word cut title (`candidate == phrase` or
  `candidate.startswith(phrase + " ")`) in the metadata parse removes the one
  OpenAlex and arXiv wrong accept and keeps every right one. A stricter match
  (whole main title plus year +-1) loses 6 right hits.
- **Blocked to scripted access with an honest User-Agent:** PhilArchive and
  philpapers.org (Cloudflare block page, also on OAI-PMH), PhilSci-Archive (F5
  "Request Rejected"), Internet Archive Scholar (bot check), CORE's own PDF
  copies (`core.ac.uk/download`, Cloudflare challenge; 120 refusals). CORE's
  value is therefore unmeasured, not zero. OpenAlex reports a
  PhilPapers/PhilArchive copy for 10 works, 5 with no other copy (3 in set A);
  Brave lists PhilArchive links for 25 more works where nothing else was found
  (unverified).
- **Brave fails on accuracy.** 39 of 130 accepted PDFs are the wrong
  document: book reviews 10, other works with the same title start 9, CVs 7,
  citing papers 3, handouts 3, and one each of lecture notes, syllabus,
  slides, commentary, summary site, table of contents, search-results page. A
  stricter page-1 rule (title within 300 characters, 5+ pages, no review or CV
  markers) still keeps 17 wrong of about 95. Of the 46 works only Brave
  reaches, 8 are partial (front matter, publisher previews, one chapter) and 7
  are full in-copyright books on unrelated hosts; 31 are clean, 5 of them in
  set A. A partial passes the identity bar, so FULLTEXT would be stamped on a
  fragment.

## Proposed shape

One owner for source logic: a stdlib-only engine module beside `fulltext.py`
(working name `fulltext_sources.py`) with, per source, a pure
`request(identity) -> Request | None` and `parse(identity, payload) ->
[Location]`, plus the licence-kind classification and the rule-15 order that
today live in phillit-service's `locations.py`. `acquire_fulltext.py` makes
the calls with `requests`; the service imports the module through
`engine_api` and makes them with its own client, budgets and SSRF guard. The
prototype is `sources.py` in the measurement directory.

## Decision needed

1. **The OpenAlex title route for no-DOI works**, and how it reaches the
   service: (a) the channel carries no-DOI identities and the service runs
   the title query itself (it lifts B2); or (b) the engine resolves a DOI by
   title and sends that, with the store record still keyed to the no-DOI
   identity.
2. **Brave**: drop it; suggest-only (the run lists candidate URLs and the
   user hands copies over with `--pdf`, so the mechanical bar stays binding);
   or automatic with an extra screen.
3. **Ask PhilPapers for harvester or API access** to PhilArchive.

Not proposed: arXiv (4 works over the OpenAlex title route, at 3 s per call
and 3 wrong accepts) and the sources that added nothing (S2 title match,
CORE, HAL, Zenodo, OSF, Crossref).
