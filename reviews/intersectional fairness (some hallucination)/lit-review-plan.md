# Literature Review Plan: The Intersectionality Dilemma for Algorithmic Fairness

**Created**: 2025-12-17
**Target Word Count**: ~5,000 words
**Target Audience**: ACM FAccT, Synthese, Philosophy & Technology reviewers

## Research Paper Core Argument

The paper argues that intersectional algorithmic fairness faces a genuine dilemma arising from the interaction of:
1. **Statistical uncertainty**: Estimating model performance across intersectional groups with sparse data
2. **Ontological uncertainty**: Specifying which groups warrant consideration (social ontology of intersectionality)

**Key Interaction**: Expanding groups exacerbates statistical problems; constraining groups requires resolving contested social ontology questions. Existing technical approaches do not resolve this dilemma.

## Critical Research Objectives

1. **Flag dilemma framing**: Identify any work that frames intersectional fairness as a dilemma or identifies the interaction between statistical and ontological problems
2. **Note gaps**: Hypothesis is that no existing work frames this as a dilemma with two interacting horns
3. **Emphasize recency**: 2020-2025 for ML/CS literature; philosophy can be older if foundational

## Domain Structure (6 Domains)

### Domain 1: Algorithmic Fairness and Intersectionality (ML/CS)
**Focus Areas**:
- Intersectional fairness metrics and their limitations
- Handling sparse data in fairness auditing
- Fairness gerrymandering
- Multi-group fairness constraints
- Practical implementations and trade-offs

**Key Venues**: FAccT, NeurIPS, ICML, AAAI, AIES

**Must-Include Papers**:
- Kearns et al. 2018 (multicalibration)
- Foulds et al. 2020 (intersectional fairness)
- Molina and Loiseau 2022
- Gohar and Cheng 2023 (survey)
- Herlihy et al. 2024

**Papers Already in Bibliography (do not duplicate)**:
- Kearns et al. 2018
- Foulds et al. 2020
- Buolamwini and Gebru 2018
- Morina et al. 2019
- Molina and Loiseau 2022
- Gohar and Cheng 2023
- Herlihy et al. 2024
- Paes et al. 2024
- Cooper et al. 2024
- Choi et al. 2025
- Himmelreich et al. 2025
- Dwork et al. 2012

**Search Strategy**:
- Google Scholar: "intersectional fairness", "multi-group fairness", "fairness gerrymandering", "subgroup fairness"
- FAccT proceedings 2020-2025
- NeurIPS fairness workshops 2020-2025
- Look for: statistical methods for small groups, granularity in fairness, combinatorial explosion

**Key Questions**:
- How do existing approaches handle the statistical challenge of small intersectional groups?
- Do any papers identify the trade-off between group granularity and statistical reliability?
- What technical solutions have been proposed (smoothing, hierarchical models, etc.)?

### Domain 2: Philosophy of Intersectionality
**Focus Areas**:
- Analytical vs. hermeneutic interpretations of intersectionality
- Causal modeling of intersectionality
- Social construction of group identity
- Intersectionality as theoretical construct in philosophy of science

**Key Venues**: Philosophy journals, social ontology, philosophy of science

**Must-Include Papers**:
- Bright, Malinsky, and Thompson 2016 (causal modeling)
- Ruíz 2017

**Papers Already in Bibliography**:
- Bright et al. 2016
- Ruíz 2017

**Search Strategy**:
- PhilPapers: "intersectionality", "causal modeling intersectionality", "social groups ontology"
- SEP entries on intersectionality, social construction
- Recent philosophy of science work (2015-2025)
- Look in: Hypatia, Signs, Ergo, Philosophy of Science

**Key Questions**:
- How do philosophers conceptualize the metaphysics of intersectional groups?
- What is the debate between combinatorial (attribute-based) vs. emergent (practice-based) accounts?
- How does this relate to the ontological uncertainty in the paper's argument?

### Domain 3: Social Ontology
**Focus Areas**:
- Constitution of social groups
- Combinatorial/attribute-based accounts vs. practice-based/hermeneutic accounts
- Group individuation criteria
- Relevance to whether groups can be derived from attributes or must be specified through social practices

**Key Venues**: Social ontology journals, metaphysics journals

**Search Strategy**:
- PhilPapers: "social ontology", "social groups", "group individuation"
- SEP: Social Ontology, Social Groups
- Key authors: Sally Haslanger, Ron Mallon, Ásta Sveinsdóttir
- Look for: debates on realism vs. constructivism about groups

**Key Questions**:
- Can social groups be exhaustively specified through combinations of attributes?
- What are the arguments for practice-based or hermeneutic accounts?
- How does this debate map onto the challenge of specifying G (set of groups) in fairness?

### Domain 4: Measurement Theory and Construct Validity in ML
**Focus Areas**:
- Operationalization and construct validity for fairness
- What fairness metrics actually measure
- Validity of group categories in datasets
- Measurement error and fairness

**Key Venues**: FAccT, ML journals, philosophy of science

**Must-Include Papers**:
- Jacobs and Wallach 2021

**Papers Already in Bibliography**:
- Jacobs and Wallach 2021

**Search Strategy**:
- Google Scholar: "construct validity fairness", "measurement fairness", "operationalization fairness"
- FAccT papers on measurement
- Philosophy of science on measurement in social sciences
- Look for: debates on what fairness metrics capture, validity of demographic categories

**Key Questions**:
- How do researchers address construct validity in fairness research?
- What is the relationship between measurement choices and ontological commitments?
- Are there acknowledged limits to operationalizing intersectionality?

### Domain 5: Normative Theory
**Focus Areas**:
- Prioritarianism (Parfit 1997)
- Sufficientarianism (Frankfurt 1987, Slote 1989)
- Applications to algorithmic fairness
- Purposes of fairness audits: legal compliance vs. substantive non-discrimination
- Trade-offs between different fairness desiderata

**Key Venues**: Ethics journals, political philosophy, applied ethics

**Papers Already in Bibliography**:
- Parfit 1997
- Frankfurt 1987
- Slote 1989

**Search Strategy**:
- PhilPapers: "prioritarianism", "sufficientarianism", "algorithmic fairness normative"
- Look for applied ethics work on ML fairness
- Recent work connecting distributive justice to fairness metrics
- Journals: Ethics, Philosophy & Public Affairs, Journal of Political Philosophy

**Key Questions**:
- What normative frameworks are relevant to evaluating fairness trade-offs?
- How do prioritarian or sufficientarian principles apply to intersectional fairness?
- What is the purpose of fairness audits, and how does this affect which groups to consider?

### Domain 6: Applied Epistemology
**Focus Areas**:
- Reasoning under uncertainty about group-level properties
- Epistemic justice in data collection
- When is it epistemically responsible to make claims about small groups?
- Relationship between statistical uncertainty and epistemic responsibility

**Key Venues**: Epistemology journals, feminist epistemology, philosophy of science

**Search Strategy**:
- PhilPapers: "epistemic justice", "uncertainty group properties", "statistical inference ethics"
- Look for: feminist epistemology work on data, philosophy of statistics
- Recent work on epistemic dimensions of ML fairness
- SEP: Feminist Epistemology, Social Epistemology

**Key Questions**:
- What are epistemic responsibilities when making inferences about groups with sparse data?
- How does epistemic justice relate to intersectional fairness?
- Are there philosophical accounts of reasoning under ontological uncertainty?

## Search Strategy Overview

### Primary Sources
1. **Computer Science**:
   - Google Scholar (2020-2025 focus)
   - ACM Digital Library (FAccT, AIES)
   - arXiv (cs.CY, cs.LG, cs.AI)
   - NeurIPS, ICML proceedings

2. **Philosophy**:
   - PhilPapers
   - Stanford Encyclopedia of Philosophy
   - Major journals (direct website searches)

### Search Terms by Domain
- Domain 1: "intersectional fairness", "multi-group fairness", "fairness gerrymandering", "subgroup fairness", "sparse data fairness"
- Domain 2: "intersectionality philosophy", "causal modeling intersectionality", "intersectionality theory"
- Domain 3: "social ontology", "social groups metaphysics", "group individuation"
- Domain 4: "construct validity fairness", "measurement fairness", "operationalization ML"
- Domain 5: "prioritarianism", "sufficientarianism", "fairness trade-offs", "distributive justice algorithms"
- Domain 6: "epistemic justice", "uncertainty groups", "epistemic responsibility data"

### Quality Criteria
- Peer-reviewed publications (prioritize)
- High-quality preprints (arXiv, PhilArchive)
- Recency (2020+ for ML/CS, foundational works can be older)
- Citation count (use as signal, not filter)
- Venue prestige

### Expected Papers per Domain
- Target: 10-20 papers per domain
- Total corpus: 60-120 papers
- After validation and synthesis, expect to cite: 40-60 papers in final review

## Synthesis Structure (Preliminary)

### Anticipated Sections (to be refined in Phase 4)
1. **Introduction**: The challenge of intersectional fairness
2. **Technical Approaches to Intersectional Fairness** (Domain 1)
3. **Philosophical Foundations of Intersectionality** (Domains 2-3)
4. **Measurement and Operationalization** (Domain 4)
5. **Normative Frameworks for Fairness Trade-offs** (Domain 5)
6. **Epistemic Dimensions** (Domain 6)
7. **Synthesis: The Dilemma and Research Gaps**

### Word Allocation (Preliminary)
- Introduction: 500 words
- Domain 1: 1,000 words
- Domains 2-3 combined: 1,200 words
- Domain 4: 800 words
- Domain 5: 600 words
- Domain 6: 500 words
- Synthesis/Gaps: 400 words
- Total: ~5,000 words

## Critical Success Factors

1. **Identify dilemma framing**: Flag any work that frames the interaction between statistical and ontological problems
2. **Balance disciplines**: Equal weight to ML/CS and philosophy
3. **Recency**: Emphasize 2020-2025 for ML/CS
4. **Citation validation**: All papers must be verified (DOIs, metadata)
5. **Gap analysis**: Clear articulation of what existing work does NOT address
6. **Actionable insights**: Position the paper's contribution relative to SOTA

## Notes

- This is an interdisciplinary review bridging ML/CS and philosophy
- Target audience expects rigor in both technical and philosophical analysis
- The "dilemma framing" is the key novel contribution to flag (or its absence)
- BibTeX files must be Zotero-compatible with rich metadata
