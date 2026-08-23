# Reprint years are not a defect — investigated and dismissed

**Status**: NOT A BUG. Investigated 2026-08-11, dropped from the roadmap the
same day (Johannes: "none of what we see here is really a problem at all").
This file exists so the observation is not re-raised as a defect a third time.

## What was suspected

A researcher who verifies a reprint edition's DOI seeds that edition's year
into the bib. Because the bib year and the API year then agree, the cleaner's
reprint-edition direction bound (`_book_year_decline_reason` in
`hooks/metadata_cleaner.py`) never fires. This was carried as roadmap
item 7, reprint-year seeding, and described there as the "seeding half" of a
year defect.

## What the corpus actually shows

Probe, results and caches are local-only at
`docs/known-issues/item7-reprint-seeding-2026-08-11/` (`probe.py` CrossRef,
`probe_s2.py` Semantic Scholar). 431 DOI-bearing book-class entries across the
43 delivered bibs; 25 flagged as carrying a later year than some other record
attests; every flag adjudicated by hand against its candidate records.

**Nine confirmed cases, and all nine are coherent citations.** For eight of the
nine, the entry's `booktitle` matches the DOI's container *exactly*, and the
year, publisher and page range all describe that same reprint volume — Broome
2017 in *Intergenerational Justice*, Cohen 2005 in *Debates in Contemporary
Political Philosophy*, Omohundro 2018 in *AI Safety and Security*, Williamson
2002 (OUP paperback of the 2000 hardcover), and so on. Nothing is fabricated
or ungrounded; the year is correct about the edition the entry names, which is
what Chicago's cite-the-edition-consulted rule provides for.

The ninth, `stewart2021reformation`, has a `booktitle` ("Routledge Handbook of
Administrative Law") that does not match CrossRef's container for its DOI
("The Political Economy"), though chapter title, author, publisher and year
all match. That is a possible booktitle inaccuracy — a different and much
smaller matter, not a year defect.

The residual is therefore not falsity but signalling: a reader meeting
"(Omohundro 2018)" may take a 2008 argument for recent work. Judged not worth
machinery.

## Two findings worth keeping

1. **A naive "an earlier year exists" rule cannot be trusted.** Of 25 flags,
   16 were false positives with systematic shapes: book reviews carry the
   reviewed work's title (Simmel, Beitz, Neumayer), precursor articles carry
   the later book's title (Schwarzenbach, Peter, Adams), second editions are
   correctly dated by their own year (Davidson, Vovk, Williamson 2022),
   translations by the translation's (Habermas), and one was an
   online-first/print split (Mackenzie).
2. **CrossRef alone under-covers this question.** 142 of 431 book-class
   entries (33%) have no CrossRef record other than the DOI's own, and 12 of
   the flags were visible only to S2. Any future question of this shape must
   read both sources — the CrossRef-only first pass produced an incidence
   roughly half the true one.

## Consequence for shipped prose

The 2026-08-09 researcher mitigation told researchers to prefer an earlier
API-attested year for any book or chapter. Under this finding that is wrong
for anthology reprints — it would set a 1975 year beside a 2021 `booktitle`.
Narrowed 2026-08-11 to same-book reissues only (paperback of an earlier
hardcover), with the consistency requirement stated explicitly:
year, container and pages must describe the same volume.

The cleaner's direction bound is unaffected and remains correct: it protects
an entry that already names the original edition from being overwritten with
a reissue's later year.
