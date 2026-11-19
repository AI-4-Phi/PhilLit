---
id: PL-38
title: PDF build drops characters the default font lacks
status: To Do
assignee: []
created_date: '2026-11-17T11:20:00Z'
labels: []
dependencies: []
type: bug
project: Delivery
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** Phase 6 step 10 builds the PDF with `pandoc --pdf-engine=lualatex` and the default Latin Modern font. In the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), lualatex printed `Missing character: There is no β (U+03B2)` twelve times, and the step still reported "Converted to PDF". The PDF silently lost every β in the reported regression coefficients. Rebuilding with `-V mainfont="STIX Two Text"` fixed it on macOS.

**Scope:** pass a wide-coverage `mainfont` that exists on each platform, or fall back to a font that does. Also treat lualatex "Missing character" warnings as a reported problem, not a success. The step should name the lost characters in the final summary.
<!-- SECTION:DESCRIPTION:END -->
