---
id: PL-28
title: >-
  Harden the full-text identity bar against citing papers, reviews and partial
  copies
status: To Do
assignee: []
created_date: '2026-10-24 21:10'
updated_date: '2026-10-25 01:44'
labels: []
dependencies: []
type: guard
project: Accuracy
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** the PL-27 source measurement fed the bar search results, an adversarial population, and it accepted the wrong document often. The DOI-title fallback (title phrase plus surname anywhere in pages 1-3) accepted CVs, citing papers, handouts and lecture notes; the no-DOI title_head rule accepted book reviews, syllabi, slides, a CV and a Google Scholar printout; the title phrase matches as a substring ("political disagreement" inside "political disagreements"); a one-word title ("Introduction") is a phrase; and partial copies (front matter, publisher previews, one chapter) pass and would earn FULLTEXT on a fragment.

The shipped sources are mostly safe (OA locations and Zotero attachments are the work's own copies), but the folder source picks candidates whose heads contain the phrase, which is the population where citing papers live.

Evidence: docs/known-issues/fulltext-sources-measurement-2026-10-24/ (audit_verdicts.py, strict_bar.py, extra_checks.py: word-bounding rejects 1 wrong and 0 right of 213 title_head hits). The current bar is a measured ruling (docs/ideas/fulltext-evidence-tier.md): re-run idbar_nxn.py and idbar_nodoi.py on the Zotero set with each change before proposing it.

Scope: word-bounded phrase; a minimum phrase length; a page-count or partial-copy check; whether the DOI-title fallback needs the title on page 1.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From PL-27 Task 2: fulltext.fold folds a straight and a curly apostrophe differently, so a title with an apostrophe cannot match a source using the other form (identity_ok, the OpenAlex title-route match, the Brave title filter, Zotero's title check). fold also feeds canonical_identity and slug_for, so a fix moves stored slugs: plan a migration or a match-only fold.

From the PL-27 final review: acquire_fulltext._doi_ok admits DOIs that fulltext_sources' DOI shape refuses (e.g. 10.abc/x). With an OpenAlex key such an entry takes the title route, but its PDF is judged by identity_ok's DOI-then-title fallback (the weaker bar above), not the no-DOI title_head rule. Rare, and limited to the matched record's own locations.

From the PL-27 headless run (reward hacking, 2026-10-24): 12 correct arXiv PDFs were rejected fail-closed by identity_ok's title_head rule. Causes seen: (1) an affiliation digit glued to the surname after folding ("majha1"), so the whole-word surname test fails; (2) PDF text extraction lost spaces ("robustoptimization formitigatingreward hacking"); (3) the apostrophe fold ("goodharts" vs "goodhart s"). All lose coverage, none accepts a wrong work. (1) looks cheap: strip trailing digits from tokens before the surname test; re-measure on the Zotero set first.
<!-- SECTION:NOTES:END -->
