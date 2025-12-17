# Synthesis Outline: The Intersectionality Dilemma for Algorithmic Fairness

**Target Length**: ~5,000 words
**Target Audience**: ACM FAccT, Synthese, Philosophy & Technology reviewers
**Critical Objective**: Flag any existing "dilemma framing" of interaction between statistical and ontological problems

## Overview

This literature review synthesizes 95 papers across 6 domains to position "The Intersectionality Dilemma for Algorithmic Fairness" within current scholarship. The review emphasizes the novel contribution: framing intersectional fairness as a *dilemma* arising from the interaction between statistical uncertainty and ontological uncertainty—two problems that mutually exacerbate each other.

## Section Structure

### Section 1: Introduction and the Challenge of Intersectional Fairness
**Target**: 600 words
**Relevant BibTeX files**: literature-domain-1.bib, literature-domain-2.bib

**Content**:
- Overview of intersectional fairness problem in ML/CS
- Brief introduction to intersectionality from philosophy
- **Critical**: Establish that existing work treats statistical and ontological problems separately
- Set up the paper's novel dilemma framing

**Key Citations**:
- GoharCheng2023 (comprehensive survey)
- Foulds2020, BrightMalinskyThompson2016
- Identify gap: no existing work frames these as interacting problems forming a dilemma

**Tone**: Establish the landscape and signal the gap

---

### Section 2: Technical Approaches to Intersectional Fairness
**Target**: 1,200 words
**Relevant BibTeX files**: literature-domain-1.bib

**Subsection 2.1: Statistical Challenges with Sparse Intersectional Data (500 words)**

**Content**:
- Exponential growth of subgroups with multiple attributes (Celis2022, Sheng2025)
- Small sample sizes for intersectional groups (GoharCheng2023, Maheshwari2024)
- Multicalibration and its data requirements (HeribertJohnson2018, Halevy2025, Dwork2024)
- Conditional demographic parity and computational challenges (Yurochkin2024)

**Key Debates**:
- Trade-off between granularity and statistical reliability
- Sample complexity scaling exponentially with groups
- Practical infeasibility with many classes

**Flag for Dilemma**: These papers identify the statistical problem but don't frame it as interacting with ontological uncertainty about which groups to include.

**Subsection 2.2: Technical Solutions and Their Limitations (700 words)**

**Content**:
- Hierarchical approaches leveraging group structure (Maheshwari2024)
- Post-processing methods (Davis2023, Kim2019)
- Data augmentation strategies (Halevy2025 finding Fair Mixup ineffective)
- Multicalibration and multiaccuracy frameworks (HeribertJohnson2018, Kim2019)
- Approaches for overlapping groups (Yang2020)
- Fairness in RL and ranking (Hashimoto2024, Yan2024)

**Key Limitations**:
- Most assume set of groups G is given/known
- Don't address ontological question of which groups warrant consideration
- Solutions to statistical problem (e.g., hierarchical methods) still require specifying parent groups—pushes ontological question upstream

**Flag for Dilemma**: Solutions address statistical uncertainty conditional on having specified G, but rarely engage with problem of determining G itself. No recognition that these problems interact.

---

### Section 3: Philosophical Foundations: What is Intersectionality?
**Target**: 1,000 words
**Relevant BibTeX files**: literature-domain-2.bib, literature-domain-3.bib

**Subsection 3.1: Competing Interpretations of Intersectionality (500 words)**

**Content**:
- Analytical vs. hermeneutic interpretations (May2014, Ruiz2017)
- Causal modeling approach (BrightMalinskyThompson2016)
- Emergence view (JorbaLopezdeSa2024)
- Intersectionality as metaphor, heuristic, paradigm (Garry2011, McCall2005)
- Definitional dilemmas (May2014, Nash2019)
- Non-additive nature (Hancock2007, Bowleg2008)

**Key Debates**:
- Is intersectionality exhaustively capturable by combinations of attributes, or does it involve emergent properties?
- How context-dependent are intersectional categories?

**Flag for Dilemma**: These debates create ontological uncertainty about what intersectionality *is*—which directly impacts specification of G. But philosophy literature doesn't connect this to statistical problems in ML fairness.

**Subsection 3.2: Social Ontology of Groups (500 words)**

**Content**:
- Attribute-based vs. practice-based accounts (Epstein2019, Haslanger2012)
- Social construction debates (Sveinsdottir2013, Mallon2007, Haslanger2003)
- Group individuation criteria (Thomasson2019, Appiah2020)
- Dynamic and context-dependent nature of groups (Sterba2024, Ritchie2013)
- Constitutive vs. causal construction (Haslanger2012)

**Key Debates**:
- Can social groups be exhaustively specified through attribute combinations?
- Do groups have existence/properties independent of practices that constitute them?
- How stable are group boundaries?

**Flag for Dilemma**: These ontological debates mean there's no settled answer to "which groups should fairness address?" But this literature is disconnected from ML fairness—no recognition that ontological choices have statistical consequences (more groups = more sparsity).

---

### Section 4: Measurement and Operationalization
**Target**: 800 words
**Relevant BibTeX files**: literature-domain-4.bib

**Content**:
- Construct validity framework (JacobsWallach2021)
- Operationalization involves ontological commitments (Scheuerman2021, Geiger2020)
- Fairness as contested construct (JacobsWallach2021)
- Measurement error in demographic categories (Hu2023, Obermeyer2019)
- Validity of group categories (Scheuerman2021)
- Abstraction traps (Selbst2019)
- Label bias compromising validity (Mayson2019, Barabas2020)

**Key Insights**:
- Measurement choices embed ontological commitments about groups
- Construct validity requires clear theoretical understanding of what's being measured
- Fairness itself is essentially contested—different contexts require different constructs
- No measurement without categorization; no categorization without ontology

**Flag for Dilemma**: JacobsWallach2021 comes closest to recognizing the problem—they note fairness debates are about different *theoretical understandings*, not just metrics. But they don't frame this as creating a dilemma when combined with statistical constraints. They don't explicitly connect ontological contestedness to statistical sparsity problem.

---

### Section 5: Normative Frameworks and Fairness Trade-offs
**Target**: 700 words
**Relevant BibTeX files**: literature-domain-5.bib

**Content**:
- Egalitarianism vs. prioritarianism vs. sufficientarianism (Parfit1997, Frankfurt1987, Holm2023)
- Leveling down objection (Mittelstadt2023, Holm2023)
- Fairness-utility trade-offs (Narayanan2024, Heidari2022)
- Impossibility results (Heidari2022, Fazelpour2021)
- Justice-based frameworks (Satz2022, Binns2024, Binns2018)
- Distributive justice principles applied to algorithms (Satz2022, Binns2024)

**Key Debates**:
- Which normative principle should guide fairness? (equality, priority to worst-off, sufficiency threshold)
- How to navigate fairness-accuracy trade-offs?
- Is parity the right goal or should we accept "good enough"?

**Flag for Dilemma**: Normative debates often presume we know which groups matter. Different principles (prioritarianism, sufficientarianism) might suggest different approaches to determining G (e.g., focus only on groups below threshold). But connection to ontological problem not explicit. Statistical constraints not acknowledged as constraining normative ideals.

---

### Section 6: Epistemic Dimensions of Fairness
**Target**: 600 words
**Relevant BibTeX files**: literature-domain-6.bib

**Content**:
- Epistemic injustice in algorithmic systems (Fricker2007, Anderson2012, Barabas2025)
- Epistemic vs. aleatoric uncertainty (Hüllermeier2021)
- Epistemic responsibility with small groups (Bhatt2021, ONeill2016, Eubanks2018)
- Who has epistemic authority over group categories? (Kalluri2020, DOgnazio2020, Harding2004)
- Uncertainty quantification and communication (Bhatt2021, Hullman2021)
- Epistemic issues in data collection (DOgnazio2020, Gebru2021, Taylor2017)

**Key Insights**:
- Epistemic uncertainty distinct from aleatoric (reducible vs. irreducible)
- Small samples create high epistemic uncertainty about group properties
- Making claims about groups requires epistemic warrant
- Epistemic authority over categories is political question, not just technical

**Flag for Dilemma**: Hüllermeier2021 distinguishes epistemic from aleatoric uncertainty—relevant to statistical uncertainty horn of dilemma. Kalluri2020 and others raise question of who determines groups—relevant to ontological horn. But these literatures don't connect: epistemic uncertainty literature doesn't engage with ontological debates, and vice versa. No recognition of interaction.

---

### Section 7: Synthesis and the Dilemma Gap
**Target**: 600 words
**Relevant BibTeX files**: All domains

**Content**:

**The Current Landscape**:
- ML/CS literature: Extensive work on statistical challenges (sparsity, multicalibration, etc.)
- Philosophy literature: Rich debates on ontology of groups and intersectionality
- Measurement literature: Recognition that operationalization embeds ontological commitments
- Normative literature: Frameworks for evaluating fairness trade-offs
- Epistemology literature: Analysis of uncertainty and epistemic justice

**The Gap**:
- **Statistical problem** (Domain 1): Well-recognized that more groups = more sparsity = less statistical reliability
- **Ontological problem** (Domains 2-3): Well-recognized that "which groups?" has no settled answer
- **The Missing Link**: NO existing work frames these as *interacting* problems forming a *dilemma*

**The Dilemma Framing (Novel Contribution)**:
1. **First horn**: Statistical uncertainty worsens as we expand G to include more intersectional groups
2. **Second horn**: Ontological uncertainty means we cannot *principled way* constrain G without resolving contested questions in social ontology
3. **Interaction**: These problems exacerbate each other:
   - Ontological debates suggest we should include many intersectional groups (emergent properties, context-dependence) → worsens statistical problem
   - Statistical constraints push toward fewer groups → but which groups to exclude requires resolving ontological debates
   - Technical solutions (hierarchical methods, multicalibration) assume G is given → doesn't resolve dilemma
   - Normative principles (prioritarianism, sufficientarianism) require knowing which groups are worst-off → but determining that requires statistical reliability → which requires constraining G → back to ontological problem

**Closest Existing Work**:
- JacobsWallach2021: Recognize fairness is contested construct, operationalization involves theoretical commitments—but don't frame as dilemma with statistical horn
- Celis2022, GoharCheng2023: Note computational infeasibility with many groups—but don't connect to philosophical debates about ontology
- JorbaLopezdeSa2024: Recognize intersectional experiences are emergent, context-dependent—but don't discuss implications for statistical estimation
- Hüllermeier2021: Distinguish types of uncertainty—but don't apply to group specification problem

**The Genuine Dilemma**:
- Not just two separate problems
- Not just a technical challenge requiring better methods
- Not just a philosophical puzzle requiring conceptual clarification
- A genuine dilemma: horns interact such that "solving" one exacerbates the other

---

### Section 8: Conclusion
**Target**: 500 words
**Relevant BibTeX files**: All domains

**Content**:
- Summary of landscape across 6 domains
- Reiteration of the gap: interaction not recognized
- Positioning of paper's contribution: dilemma framing
- Implications:
  - Existing technical solutions don't resolve dilemma (assume G given)
  - Existing philosophical work doesn't account for statistical constraints
  - Need interdisciplinary approach recognizing interaction
- Future directions suggested by gap

**Final Note on Dilemma**: Literature reveals rich understanding of both horns separately, but systematic blind spot regarding their interaction. Paper makes novel contribution by framing this interaction as dilemma requiring fundamentally new approaches, not just refinements of existing methods.

---

## Word Count Distribution

1. Introduction: 600 words
2. Technical Approaches: 1,200 words
3. Philosophical Foundations: 1,000 words
4. Measurement: 800 words
5. Normative Frameworks: 700 words
6. Epistemic Dimensions: 600 words
7. Synthesis/Gap: 600 words
8. Conclusion: 500 words

**Total**: 6,000 words (target was ~5,000; can trim in final editing)

## Critical Success Factors

1. **Flag Dilemma Framing**: Explicitly note in EVERY section that literature addresses one horn but not interaction
2. **Gap Analysis**: Clear articulation that no existing work frames as dilemma with interacting horns
3. **Balanced Coverage**: Equal weight to ML/CS (Domains 1, 4) and philosophy (Domains 2, 3, 5, 6)
4. **Recency**: Emphasize 2020-2025 ML/CS work while acknowledging foundational philosophy
5. **Positioning**: Clear setup for paper's novel contribution

## Notes for Synthesis Writers

- Each section should END with "Flag for Dilemma" paragraph explicitly noting the gap
- Use specific citations (not just "the literature shows")
- Emphasize debates and tensions within domains
- Connect insights across domains where possible
- Maintain analytical depth over encyclopedic coverage
- Every claim must be grounded in specific papers from BibTeX files
