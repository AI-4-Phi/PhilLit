---
id: PL-29
title: 'Full-text sources follow-ups: test breadth and small robustness items'
status: In Progress
assignee: []
created_date: '2026-10-25 01:26'
updated_date: '2026-10-25 12:59'
labels: []
dependencies: []
type: guard
project: Accuracy
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** the PL-27 reviews found small items that do not affect which PDF is stored; they wait so the feature could ship.

Items:
- The OpenAlex 429 branch reads the response body uncapped (openalex_budget_exhausted reads response.text); read a small capped prefix instead.
- Test gaps: a deadline expiring mid-try in the merged open-access step; the response close before a 429/5xx retry; an S2 unavailable row beside an OpenAlex win; an uneven request split (one half fits, one fails); suggestions under the licensed-only policy; a gap entry removed from its bib after the pass.
- The open-access no_doi detail short_title also covers a missing title.
- acquire_fulltext calls the private fulltext_sources._phrase; make it public if the service needs it.
- _SOURCES mixes single and list returns (with a side table); every source could return a list.
- The run report's elapsed_seconds includes suggestion time while deadline_seconds stays 420.
- A crash in the suggestion post-pass loses the not-asked/failed counts.
- The step 5a question shows raw LaTeX (M{\"u}ller) from the report.
- The service's arrival-check reservation now counts no-DOI identities, which shortens the service wait for DOI works until the service's title route exists.

Trigger: a full-text bug report, or the next change to acquire_fulltext.py.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the PL-27 final fix wave: the --gaps worst case can approach the 600 s Bash ceiling (a fetch-pass download or API call can end about 60 s past 420, then up to about 60 s or more of Brave suggestions). Rare (needs stalled reads) and partly older than PL-27. Fix: bound the suggestion budget by total elapsed time, e.g. min(SUGGESTION_SECONDS, 520 - elapsed). This item is a Delivery risk for headless runs; bring it forward if a gap pass is ever seen near 600 s.

From the PL-27 final re-review (measured on a real socket): _read_capped, download_pdf and suggest read with iter_content(65536), which returns only on 64 KiB, end of body or error; each arriving byte resets the socket timeout, so a trickling body is not bounded by the deadline (10.2 s past a 2 s deadline in the measurement; script under the session scratchpad trickle/t3.py, lost with it). Fix direction: read with r.raw.read1(65536), which returns per receive; test with a real local socket. Predates PL-27 for download_pdf.

Disposition (2026-10-25, built on pl-27-fulltext-sources): reads per receive with own gzip/deflate decoding; a 570 s watchdog backstops what no deadline reaches; suggestions stop at 530 s; 429 body capped; per-row crash counted; key_phrase public; suggestion_seconds reported; step 5a shows plain names; test gaps filled. Declined: _SOURCES uniform lists (churn, no behaviour change); the service's no-DOI arrival reservation (resolves with the service title route in the same port).
<!-- SECTION:NOTES:END -->
