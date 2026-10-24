---
id: PL-28
title: >-
  Harden the full-text identity bar against citing papers, reviews and partial
  copies
status: To Do
assignee: []
created_date: '2026-10-24 21:10'
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
