# Reprint years seeded at research time

**Status**: CLOSED 2026-08-11 (Johannes) — measured, and the shipped prose
mitigation judged proportionate. No mechanical control was built. This file is
the record of why; reopen only against a new measurement.

## The defect

A reprint edition carries its own DOI, and CrossRef's `published-print` for
that DOI is genuinely the reprint's year while being the wrong citation year
for the *work*. The **cleaner** half of this was fixed on 2026-08-09: a
book-class entry's year can no longer be overwritten in the LATER direction
(`_book_year_decline_reason` in `hooks/metadata_cleaner.py`).

The **research-time** half is one step earlier and the direction bound cannot
see it. A researcher who verifies the reprint DOI first seeds the reprint's
year into the bib directly; the bib year and the API year then AGREE, so no
licence is ever consulted, no decline is counted, and the on-disk verify
record corroborates the wrong year. Found by the 2026-08-09 whole-diff review.

Mitigation shipped the same day: `agents/domain-literature-researcher.md`
instructs preferring an earlier API-attested year for books and chapters.
Prose is a soft control, which is what put a mechanical signal on the roadmap
as item 7.

## Measurement (2026-08-11)

Probe, results and response caches are **local-only and untracked** at
`docs/known-issues/item7-reprint-seeding-2026-08-11/` (`probe.py` CrossRef,
`probe_s2.py` Semantic Scholar). Re-run either to regenerate.

Population: **431 DOI-bearing book-class entries** (312 `book`, 119
`incollection`) across the 43 delivered corpus bibs. For each, the probe asked
whether some *other* record attests an earlier year for the same work —
title-key and folded-surname matched, `published-print` preferred, the same
field order `verify_paper.extract_year` uses.

CrossRef pass, 13 flagged at a ≥2-year gap, **all 13 adjudicated by hand**:

| bib type | flagged | genuine |
|---|---|---|
| `incollection` | 6 | **5** |
| `book` | 7 | **0** |

The five genuine cases are anthology reprints: `stewart2021reformation`
(1975 Harvard Law Review article reprinted 2021), `broome2017discounting`
(1994), `conee2004evidentialism` (1985), `cohen1989deliberation` (a 1989
chapter cited at its 2005 re-reprint — the citekey preserves the true year),
`sunstein2003law` (2002). The single chapter-class false positive,
`eiter1993complexity`, is a conference→journal upgrade whose DOI record is a
`journal-article`, not a chapter.

**The whole-book false positives are systematic, not noise** — and they are
the reason a naive "an earlier year exists" rule cannot be trusted:

- *book reviews share the reviewed work's title* (`simmel2004philosophy`
  matched 1979–80 review essays in Contemporary Sociology and the Economic
  Journal; `beitz1999political` matched two 1980 law-review essays);
- *precursor articles share the later book's title* (`schwarzenbach2009civic`,
  `peter2023grounds`, `adams2010bounds`);
- *SSRN working papers* (`king2016doctrine`);
- *legitimate second editions*, which are correctly cited by their own year
  (`Williamson2022philosophy`).

Had a control been built, the discriminating rule was: chapter-class entry,
DOI record not a `journal-article`, ≥2-year gap — 5 flags, 5 genuine on this
corpus. Whole-book entries would have to be excluded outright.

**Incidence: 5 wrong years across 43 delivered reviews** — 1.2% of DOI-bearing
book-class entries, 0.12% of the 4,341-entry corpus, about one per 8.6
reviews.

A partial Semantic Scholar pass (stopped at 255 of 431 entries once the close
decision landed) found **9 further candidates CrossRef cannot see**, of which
`williamson2002knowledge` — the 2002 paperback of the 2000 hardcover — is
certainly genuine. So the true rate is plausibly ~2× the CrossRef-only count
and still under 0.3% of entries. Two consequences worth keeping:

1. **CrossRef alone would have under-covered the defect.** 142 of 431
   book-class entries (33%) have no CrossRef record other than the DOI's own,
   so no CrossRef-derived signal exists for them even in principle. A
   `verify_paper.py`-side caveat — the roadmap's original sketch — was
   therefore never going to reach a third of the population.
2. A future control, if one is ever earned, should read S2 as well as
   CrossRef.

## Decision

Closed under the divergence principle: at roughly one wrong year per nine
reviews, with the producer-side prose already shipped, a mechanical signal is
not earned. The residual is accepted and delivered reviews are not
retro-fixed — consistent with the wrong-years audit's standing rule (delivered
reviews stay as delivered; the public examples are the sole exception).
