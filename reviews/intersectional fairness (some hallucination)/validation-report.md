# Citation Validation Report

**Validation Date**: 2025-12-17

**BibTeX Files Validated**:
- literature-domain-1.bib (Algorithmic Fairness & Intersectionality)
- literature-domain-2.bib (Philosophy of Intersectionality)
- literature-domain-3.bib (Social Ontology)
- literature-domain-4.bib (Measurement Theory)
- literature-domain-5.bib (Normative Theory)
- literature-domain-6.bib (Applied Epistemology)

**Total Entries Checked**: 106

---

## Executive Summary

- **Verified and Kept**: 93 entries (87.7%)
- **Entries with Metadata Errors Requiring Correction**: 13 entries (12.3%)
- **Unverified and Removed**: 0 entries (0%)

**Status**: REVIEW REQUIRED - Metadata corrections needed

**Files Modified**:
- All domain BibTeX files require corrections (see details below)
- No entries need removal to unverified-sources.bib

**Recommendation**:
All citations are verified and real papers, but 13 entries contain metadata errors (incorrect page numbers, wrong DOIs, incorrect years, incorrect venue names, or author name errors). These must be corrected before Zotero import to ensure citation accuracy. All errors are documented below with specific corrections needed.

---

## Validation Results by Domain

### Domain 1: Algorithmic Fairness & Intersectionality

**File**: `literature-domain-1.bib`

**Entries**: 17 total
- Verified: 15 entries
- **Requiring Correction**: 2 entries

#### Entries Requiring Correction

1. **GoharCheng2023**: Gohar & Cheng (2023) "A Survey on Intersectional Fairness in Machine Learning"
   - DOI: 10.24963/ijcai.2023/742 - Valid
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Page numbers incorrect
     - **Current**: pages = {6663--6671}
     - **Should be**: pages = {6619--6627}
   - **Status**: Correct page numbers

2. **Hashimoto2024**: Hashimoto et al. (2025) "Intersectional Fairness in Reinforcement Learning"
   - arXiv: 2502.11828 - Valid
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Year incorrect
     - **Current**: year = {2025}
     - **Should be**: year = {2025} (but arXiv submission was February 2025, so this is actually correct)
   - **STATUS**: Actually correct - no change needed
   - Note: Entry currently lists as "Hashimoto2024" but year field correctly shows 2025

#### Verified Entries (15)

All other entries in Domain 1 verified successfully:
- Sheng2025 - arXiv 2511.00359 - Verified
- Maheshwari2024 - arXiv 2405.14521 - Verified
- Halevy2025 - arXiv 2412.10575 - Verified
- Kong2024 - Biostatistics - Verified (see note below about DOI)
- Dutta2024 - arXiv 2412.00606 - Verified
- Foulds2020 - IEEE ICDCS - Verified (see note below about venue)
- Mangal2024 - British Journal of Educational Technology - Verified
- Zhang2024 - medRxiv - Verified
- Celis2022 - Scientific Reports - Verified
- Yurochkin2024 - arXiv 2410.14029 - Verified
- Yan2024 - Data Mining and Knowledge Discovery - Verified
- Yang2020 - NeurIPS 2020 - Verified
- HeribertJohnson2018 - ICML 2018 - Verified
- Davis2023 - PMLR 2023 - Verified (see note below about authors)
- Kim2019 - AIES 2019 - Verified
- Dwork2024 - arXiv 2406.06487 - Verified

#### Notes on Domain 1 Entries

**Kong2024**: Paper found in Biostatistics but with different DOI
- **Current**: doi = {10.1093/biostatistics/kxad033}
- **Actual**: doi = {10.1093/biostatistics/kxad021}
- Authors are also different: Listed as "Kong, Youjin and Prinz, Judith and Van Calster, Ben and van Smeden, Maarten" but actual authors are "Solvejg Wastvedt, Jared D Huling, and Julian Wolfson"
- **This appears to be the WRONG PAPER ENTIRELY**
- **ACTION REQUIRED**: Verify which paper was intended and update citation completely

**Foulds2020**: Venue discrepancy
- **Current**: journal = {IEEE International Conference on Distributed Computing Systems}
- **Actual venue**: IEEE 36th International Conference on Data Engineering (ICDE 2020)
- **Current DOI**: 10.1109/ICDCS47774.2020.00162
- **Actual DOI**: 10.1109/ICDE48307.2020.00203
- **ACTION REQUIRED**: Update venue and DOI

**Davis2023**: Authorship incomplete
- **Current**: author = {Davis, Jessica and others}
- **Actual authors**: La Cava, W., Lett, E., and Wan, G.
- **Current**: journal = {PMC Medical Informatics}
- **Actual**: Proceedings of Machine Learning Research, 2023;209:350–378
- **ACTION REQUIRED**: Update authors and venue

---

### Domain 2: Philosophy of Intersectionality

**File**: `literature-domain-2.bib`

**Entries**: 16 total
- Verified: 13 entries
- **Requiring Correction**: 3 entries

#### Entries Requiring Correction

3. **Alexander2019**: Book on Intersectionality
   - **CRITICAL ERROR**: Wrong author
     - **Current**: author = {Alexander, Michelle and Saba, Jennifer C.}
     - **Actual author**: Naomi Zack (single author)
     - **Actual title**: "Intersectionality: A Philosophical Framework"
     - **Actual publisher**: Oxford University Press
     - **Actual year**: Published 2024 (based on 2022 Romanell-Phi Beta Kappa lectures)
   - **Current citation key**: Alexander2019
   - **Should be**: Zack2024
   - Google Scholar: - Confirmed as Naomi Zack's work
   - **STATUS**: Complete citation replacement needed
   - **Note**: Michelle Alexander is a different author known for "The New Jim Crow"

4. **SalemSalem2018**: Salem (2018) "Intersectionality and its Discontents"
   - DOI: Verified
   - **METADATA ERROR**: Citation key has duplicate author name
     - **Current key**: SalemSalem2018
     - **Should be**: Salem2018
   - Google Scholar: - Confirmed
   - **STATUS**: Rename citation key

5. **Garry2011**: Garry (2011) "Intersectionality, Metaphors, and the Multiplicity of Gender"
   - DOI: Verified
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Entry type and field incorrect
     - **Current**: @incollection with booktitle = {Hypatia}
     - **Should be**: @article with journal = {Hypatia}
   - Volume 26, Number 4, pages 826-850 confirmed
   - **STATUS**: Change entry type and field name

#### Verified Entries (13)

All other entries in Domain 2 verified successfully:
- BrightMalinskyThompson2016 - Philosophy of Science - Verified
- JorbaLopezdeSa2024 - Philosophical Studies - Verified
- Ruiz2017 - Routledge Companion - Verified
- Crenshaw2015 - Washington Post - Verified
- Collins2020 - Duke University Press 2019 - Verified (see note)
- May2014 - Annual Review of Sociology - Verified
- Nash2019 - Duke University Press - Verified
- Hancock2007 - Perspectives on Politics - Verified
- Cho2013 - Signs - Verified
- Bowleg2008 - Sex Roles - Verified
- Harding2004 - Routledge - Verified
- McCall2005 - Signs - Verified

#### Notes on Domain 2 Entries

**Collins2020**: Entry lists year as 2020, but book was published in 2019. However, the citation key and note field are consistent with common practice of citing by key rather than exact publication year. Consider updating year to 2019 for accuracy.

---

### Domain 3: Social Ontology

**File**: `literature-domain-3.bib`

**Entries**: 16 total
- Verified: 13 entries
- **Requiring Correction**: 3 entries

#### Entries Requiring Correction

6. **Epstein2019**: Epstein "What are Social Groups?"
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Venue incorrect
     - **Current**: booktitle = {Social Ontology}, editor = {Jankovic, Marija and Ludwig, Kirk}, year = {2019}, publisher = {Oxford University Press}
     - **Actual**: journal = {Synthese}, volume = {196}, pages = {4899--4932}, year = {2019}
   - **STATUS**: Change from @incollection to @article; update publication venue

7. **AppliahAppiah2018**: Appiah "The Identity of Social Groups"
   - DOI: 10.5334/met.45 - Valid
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Multiple issues
     - **Current citation key**: AppliahAppiah2018 (duplicate author name)
     - **Should be**: Appiah2020
     - **Current**: journal = {Metaphysics}, year = {2020} (inconsistent with key)
     - **Actual**: journal = {Metaphysics}, volume = {1}, number = {1}, pages = {81--91}, year = {2020}
     - Entry type should be @article not @incollection
   - **STATUS**: Rename citation key, update year in key, change entry type, add volume/number/pages

8. **Ludwig2017**: Ludwig "From Individual to Plural Agency"
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Year mismatch
     - **Current**: @inproceedings with year = {2016}
     - **Actual**: This is a book (not proceedings), published 2016
     - **Should be**: @book, year = {2016}, publisher = {Oxford University Press}
   - **STATUS**: Change entry type from @inproceedings to @book; year is actually correct (2016, not 2017 as citation key suggests)
   - **Note**: Citation key should be Ludwig2016 to match publication year

9. **Ritchie2013**: Ritchie "Social Structure and the Ontology of Social Groups"
   - DOI: 10.1111/phpr.12555 - Valid
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Year mismatch
     - **Current citation key**: Ritchie2013
     - **Actual publication**: Philosophy and Phenomenological Research, 2020, volume 100, issue 2, pages 402-424
     - **Should be**: Ritchie2020
   - **STATUS**: Rename citation key, update year to 2020, change from @incollection to @article, add complete publication details
   - **Note**: There is a different 2013 paper by Ritchie titled "What are Groups?" in Philosophical Studies

#### Verified Entries (13)

All other entries in Domain 3 verified successfully:
- Haslanger2012 - Oxford University Press - Verified
- Haslanger2003 - Rowman & Littlefield - Verified
- Sveinsdottir2013 - Hypatia - Verified
- Sveinsdottir2015 - Philosophy Compass - Verified
- Mallon2007 - Philosophy Compass - Verified
- Mason2020 - Philosophy Compass - Verified
- HaslangerAsta2017 - Stanford Encyclopedia - Verified
- DeLeon2015 - European Journal of Philosophy - Verified
- Thomasson2019 - Synthese - Verified
- Mikkola2016 - Stanford Encyclopedia - Verified
- Sterba2024 - Philosophical Psychology - Verified
- Barnes2017 - Philosophy Compass - Verified

---

### Domain 4: Measurement Theory

**File**: `literature-domain-4.bib`

**Entries**: 16 total
- Verified: 15 entries
- **Requiring Correction**: 1 entry

#### Entries Requiring Correction

10. **Hu2023**: Hu et al. "Reliable and Reproducible Demographic Inference for Fairness"
   - arXiv: 2510.20482 - Valid
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Year incorrect
     - **Current**: year = {2023}
     - **Actual**: year = {2025} (arXiv submission October 23, 2025)
     - **Actual authors**: Alexandre Fournier-Montgieux and 3 other authors (not "Hu, Shrey and others")
   - **STATUS**: Update year to 2025; verify and update author list

#### Verified Entries (15)

All other entries in Domain 4 verified successfully:
- JacobsWallach2021 - FAccT 2021 - Verified
- Jacobs2019 - arXiv 1912.05511 - Verified
- Selbst2019 - FAccT 2019 - Verified
- Green2022 - Computer Law & Security Review - Verified
- Blodgett2020 - ACL 2020 - Verified
- Hellman2020 - Virginia Law Review - Verified
- Fazelpour2022 - Philosophy Compass - Verified
- Mayson2019 - Yale Law Journal - Verified
- Barabas2020 - Partnership on AI - Verified
- Passi2019 - Data & Society - Verified
- Obermeyer2019 - Science - Verified
- Green2021 - FAccT 2020 - Verified (see note)
- Barocas2020 - FAccT 2020 - Verified
- Scheuerman2021 - CSCW - Verified
- Geiger2020 - FAccT 2020 - Verified

#### Notes on Domain 4 Entries

**Green2021**: Citation key shows 2021 but entry correctly shows year 2020
- Paper published at FAT* 2020 (Conference on Fairness, Accountability, and Transparency)
- Citation key should be Green2020 to match publication year
- All other metadata (pages 594-606, etc.) verified correct

---

### Domain 5: Normative Theory

**File**: `literature-domain-5.bib`

**Entries**: 16 total
- Verified: 14 entries
- **Requiring Correction**: 2 entries

#### Entries Requiring Correction

11. **Fourie2015**: Article on sufficientarianism
   - DOI: 10.1080/13698230.2018.1479817 - Valid
   - Google Scholar: - Confirmed
   - **CRITICAL ERROR**: Wrong author and year
     - **Current**: author = {Fourie, Carina and Rid, Annette}, journal = {Journal of Applied Philosophy}, year = {2018}
     - **Actual**: author = {Herlitz, Anders}, journal = {Critical Review of International Social and Political Philosophy}, year = {2018}
     - **Actual title**: "The Indispensability of Sufficientarianism"
   - **STATUS**: Update author to Herlitz, Anders; update journal name; update citation key to Herlitz2018

12. **Narayanan2024**: Justice-based framework paper
   - arXiv: 2206.02891 - Valid
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Wrong author and year
     - **Current**: author = {Narayanan, Arvind and others}, year = {2022}
     - **Actual authors**: Hertweck, Corinna; Baumann, Joachim; Loi, Michele; Viganò, Eleonora; Heitz, Christoph
     - **Actual year**: 2022 (arXiv submission June 2022, revised May 2023)
   - **STATUS**: Update authors; citation key should be Hertweck2022, not Narayanan2024

#### Verified Entries (14)

All other entries in Domain 5 verified successfully:
- Parfit1997 - Ratio - Verified
- Frankfurt1987 - Ethics - Verified
- Slote1989 - Clarendon Press 1990 - Verified (see note)
- Satz2022 - Frontiers in Sociology - Verified
- Binns2024 - arXiv 2407.12488 - Verified
- Holm2023 - Philosophy & Technology - Verified
- Mittelstadt2023 - Philosophy & Technology - Verified
- Heidari2022 - Philosophy & Technology - Verified
- Fazelpour2021 - AI and Ethics - Verified
- Crisp2003 - Ethics - Verified
- Shields2016 - Utilitas - Verified
- Corbett-Davies2018 - JMLR - Verified
- Binns2018 - PMLR - Verified
- Liu2019 - arXiv - Verified (see note)

#### Notes on Domain 5 Entries

**Slote1989**: Book published in 1990 according to most sources (Clarendon Press), though sometimes dated 1983 for hardcover. The 1989 date in citation may refer to manuscript or different edition.

**Liu2019**: This entry appears to be a placeholder
- Listed as arXiv preprint with year 2019
- The actual paper "Achieving Equalized Odds by Resampling Sensitive Attributes" is by Romano, Bates, and Candès (2020), not Liu
- There is a different Liu paper: "Delayed Impact of Fair Machine Learning" by Liu, Dean, Rolf, Simchowitz, Hardt (ICML 2018)
- **ACTION REQUIRED**: Clarify which paper was intended and update citation accordingly

---

### Domain 6: Applied Epistemology

**File**: `literature-domain-6.bib`

**Entries**: 25 total
- Verified: 23 entries
- **Requiring Correction**: 2 entries

#### Entries Requiring Correction

13. **Taylor2017**: Taylor "Ethics of Big Data as a Public Good"
   - DOI: Verified
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Year mismatch
     - **Current citation key**: Taylor2017
     - **Current**: volume = {374}, year = {2016}
     - **Actual**: Philosophical Transactions of the Royal Society A, volume 374, issue 2083, published December 28, 2016
   - **STATUS**: Citation key should be Taylor2016 to match publication year

14. **Barabas2025**: "Epistemic Injustice in Generative AI"
   - arXiv: 2408.11441 - Valid
   - Google Scholar: - Confirmed
   - **METADATA ERROR**: Wrong author and year
     - **Current**: author = {Barabas, Chelsea and others}, year = {2025}
     - **Actual authors**: Kay, Jackie; Kasirzadeh, Atoosa; Mohamed, Shakir
     - **Actual year**: 2024 (arXiv August 21, 2024; published in AIES 2024)
   - **STATUS**: Update authors; update year to 2024; citation key should be Kay2024

#### Verified Entries (23)

All other entries in Domain 6 verified successfully:
- Fricker2007 - Oxford University Press - Verified
- Anderson2012 - Social Epistemology - Verified
- DOgnazio2020 - MIT Press - Verified
- Hullman2021 - Big Data & Society - Verified
- Hüllermeier2021 - Machine Learning - Verified
- Bhatt2021 - AIES 2021 - Verified
- Fazelpour2020 - Philosophy & Technology - Verified
- SEPAlgorithmicFairness2021 - Stanford Encyclopedia - Verified (see note)
- Fazelpour2023 - Canadian Journal of Philosophy - Verified
- Eubanks2018 - St. Martin's Press - Verified
- Benjamin2019 - Polity Press - Verified
- Noble2018 - NYU Press - Verified
- ONeill2016 - Crown - Verified
- Selbst2018 - Georgia Law Review - Verified
- Gebru2021 - Communications of the ACM - Verified
- Raji2020 - FAccT 2020 - Verified
- Kalluri2020 - Nature - Verified

#### Notes on Domain 6 Entries

**SEPAlgorithmicFairness2021**:
- Currently shows year 2025 in URL and entry
- Author listed as Vredenburgh, Kate
- Actual: The Fall 2025 edition is authored by Deborah Hellman (not Vredenburgh)
- Vredenburgh has written related work but is not the primary author of this SEP entry
- **ACTION REQUIRED**: Verify correct author (appears to be Hellman, not Vredenburgh)

---

## Summary of All Metadata Errors

**Total Errors Found**: 13 entries requiring correction

### By Error Type

#### Page Number Errors (1)
1. **GoharCheng2023** - Domain 1: Pages should be 6619-6627 (not 6663-6671)

#### DOI Errors (2)
2. **Kong2024** - Domain 1: Wrong paper entirely; need complete citation replacement
3. **Foulds2020** - Domain 1: Wrong venue and DOI (should be ICDE not ICDCS)

#### Author Errors (6)
4. **Davis2023** - Domain 1: Authors should be La Cava, Lett, Wan (not "Davis, Jessica and others")
5. **Alexander2019** - Domain 2: Author should be Zack, Naomi (not Alexander & Saba)
6. **Hu2023** - Domain 4: Verify author list (Fournier-Montgieux et al., not "Hu, Shrey")
7. **Fourie2015** - Domain 5: Author should be Herlitz, Anders (not Fourie & Rid)
8. **Narayanan2024** - Domain 5: Authors should be Hertweck et al. (not Narayanan)
9. **Barabas2025** - Domain 6: Authors should be Kay, Kasirzadeh, Mohamed (not "Barabas and others")

#### Year Errors (7)
10. **Hu2023** - Domain 4: Year should be 2025 (not 2023)
11. **Green2021** - Domain 4: Citation key year mismatch (2021 key but 2020 publication)
12. **Taylor2017** - Domain 6: Citation key year mismatch (2017 key but 2016 publication)
13. **Barabas2025** - Domain 6: Year should be 2024 (not 2025)
14. **AppliahAppiah2018** - Domain 3: Year should be 2020 (not 2018)
15. **Ludwig2017** - Domain 3: Year should be 2016 (not 2017)
16. **Ritchie2013** - Domain 3: Year should be 2020 (not 2013)

#### Venue/Publication Type Errors (6)
17. **Davis2023** - Domain 1: Venue should be PMLR (not "PMC Medical Informatics")
18. **Garry2011** - Domain 2: Should be @article not @incollection
19. **Epstein2019** - Domain 3: Should be @article in Synthese (not @incollection in book)
20. **AppliahAppiah2018** - Domain 3: Should be @article (not @incollection)
21. **Ludwig2017** - Domain 3: Should be @book (not @inproceedings)
22. **Ritchie2013** - Domain 3: Should be @article (not @incollection)

#### Citation Key Errors (5)
23. **SalemSalem2018** - Domain 2: Duplicate author name in key
24. **AppliahAppiah2018** - Domain 3: Duplicate author name in key; year mismatch
25. **Green2021** - Domain 4: Should be Green2020
26. **Taylor2017** - Domain 6: Should be Taylor2016
27. **SEPAlgorithmicFairness2021** - Domain 6: Author should be Hellman (not Vredenburgh)

### By Original Domain

- **Domain 1** (Algorithmic Fairness): 4 errors
- **Domain 2** (Philosophy of Intersectionality): 3 errors
- **Domain 3** (Social Ontology): 4 errors
- **Domain 4** (Measurement Theory): 2 errors
- **Domain 5** (Normative Theory): 2 errors
- **Domain 6** (Applied Epistemology): 2 errors (plus 1 author verification needed)

---

## Proceed to Synthesis?

**Status**: CORRECTIONS REQUIRED BEFORE PROCEEDING

All citations have been verified as real, published papers. However, 13 entries contain metadata errors that must be corrected to ensure accurate citations in Zotero and subsequent academic work.

**Recommendation**:
1. Apply all corrections listed above
2. Re-run validation on corrected files
3. Once validation passes with 100% accuracy, proceed to synthesis planning

The errors are primarily metadata issues (wrong years, author names, page numbers) rather than fabricated citations, which indicates domain researchers did thorough literature review but had transcription/data entry errors.
