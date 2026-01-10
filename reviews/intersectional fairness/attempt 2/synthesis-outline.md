# State-of-the-Art Literature Review Outline

**Research Project**: The Intersectionality Dilemma for Algorithmic Fairness

**Date**: 2025-12-19

**Total Literature Base**: 95 papers across 6 domains

**Target Venues**: ACM FAccT, Synthese, Philosophy & Technology

**Total Word Target**: ~5,000 words

---

## Section 1: Introduction - The Challenge of Intersectional Fairness

**Purpose**: Frame the research problem, establish why intersectional fairness matters, preview the dilemma structure

**Content**:
- Opening: Intersectional fairness is widely recognized as crucial but remains challenging to implement
- The problem: Auditing algorithmic systems for fairness across intersectional groups (race × gender, race × age, etc.) involves two forms of uncertainty
- Statistical uncertainty: Small intersectional groups lead to unreliable performance estimates
- Ontological uncertainty: Which groups should we consider? (combinatorial explosion vs. social practice)
- Preview: This review shows existing work addresses each problem separately but not their interaction
- Scope: ML/CS fairness literature (Domain 1), philosophical foundations (Domains 2-3), measurement theory (Domain 4), normative frameworks (Domain 5), epistemic dimensions (Domain 6)

**Key Papers to Cite**:
- GoharCheng2023 (survey establishing field)
- Foulds2020 (differential fairness, foundational)
- BrightMalinskyThompson2016 (causal interpretation of intersectionality)
- JacobsWallach2021 (measurement and fairness)
- Collins2015 (definitional dilemmas in intersectionality)

**Word Target**: 500 words

**Connection to Dilemma**: Establishes both horns of the dilemma without yet framing their interaction as a genuine dilemma

---

## Section 2: Technical Approaches to Intersectional Fairness

**Section Purpose**: Establish state-of-the-art in ML/CS approaches, identify that statistical challenges are well-recognized but treated as purely technical problems

**Word Target**: 1,100 words

**Subsection 2.1: Fairness Metrics and Intersectional Groups** (400 words)

**Papers**:
- Foulds2020 (differential fairness)
- GoharCheng2023 (survey of notions)
- Castelnovo2022 (exponential growth of subgroups)
- Ghassemi2024 (conditional demographic parity challenges)

**Content**:
- Differential fairness: fairness on individual attributes doesn't guarantee intersectional fairness
- Conditional demographic parity: theoretically solves intersectionality but faces computational/practical issues
- Exponential growth problem: adding sensitive features creates combinatorial explosion
- Key insight: Literature recognizes group specification as "practical challenge" not ontological question

**Gap Connection**: Statistical challenges well-documented, but papers assume groups are given/obvious

**Subsection 2.2: Technical Solutions to Data Sparsity** (450 words)

**Papers**:
- HebertJohnson2018 (multicalibration - foundational)
- LaCava2023 (proportional multicalibration)
- Hansen2024 (when is multicalibration necessary?)
- Maheshwari2024 (synthetic data for intersectional fairness)
- Halevy2025 (Fair Mixup critique)
- Sheng2025 (sparsity-based framework)

**Content**:
- Multicalibration: calibration over rich collection of subpopulations, but sample complexity grows exponentially
- Proportional multicalibration: promising for intersectional groups but still requires knowing which groups
- Data augmentation approaches: synthetic data, mixup techniques
- Limitation: All assume we know which groups to target
- Sparsity as unifying framework: connects various approaches but doesn't resolve group specification

**Gap Connection**: Technical sophistication high, but all methods require pre-specified set of groups G

**Subsection 2.3: Domain-Specific Applications** (250 words)

**Papers**:
- Wastvedt2024 (clinical risk prediction)
- Lett2025 (emergency admissions)
- Dutta2024 (multimodal clinical predictions)
- Hashimoto2025 (reinforcement learning)
- Yan2024 (fair ranking)

**Content**:
- Clinical contexts: intersectional debiasing outperforms marginal approaches
- Demonstrates practical importance of intersectionality
- But all approaches assume demographic categories are given by datasets
- No discussion of whether categories adequately capture intersectional groups

**Section 2 Summary**: ML/CS literature has made significant progress on statistical challenges but treats group specification as input not problem. Gap: ontological uncertainty about groups not engaged.

---

## Section 3: Philosophical Foundations of Intersectionality

**Section Purpose**: Show that philosophy literature establishes deep ontological uncertainty about what intersectionality is and what groups it picks out

**Word Target**: 1,200 words

**Subsection 3.1: Intersectionality as Contested Concept** (400 words)

**Papers**:
- Crenshaw2015 (intersectionality as analytic sensibility)
- Collins2015 (definitional dilemmas)
- Ruiz2017 (framing intersectionality)
- Cho2013 (structural, political, representational dimensions)
- McCall2005 (anticategorical, intracategorical, intercategorical)
- Garry2011 (metaphor, heuristic, paradigm)

**Content**:
- Intersectionality: no single agreed definition, multiple interpretations
- McCall's taxonomy: three approaches take different stances on categories themselves
- Anticategorical: rejects fixed categories as reifying social constructions
- Intracategorical: focuses on specific intersections as case studies
- Intercategorical: uses categories provisionally to analyze inequality (most compatible with algorithmic approaches)
- Collins: definitional dilemmas inherent to intersectionality theory
- Key insight: What intersectionality requires is itself contested

**Gap Connection**: If philosophers disagree on what intersectionality is, how can ML researchers operationalize it?

**Subsection 3.2: Causal vs. Emergent Interpretations** (400 words)

**Papers**:
- BrightMalinskyThompson2016 (causal modeling)
- JorbaLopezdeSa2024 (intersectionality as emergence)
- Hancock2007 (multiplication ≠ addition)
- Bowleg2008 (Black + Lesbian + Woman ≠ Black Lesbian Woman)

**Content**:
- Bright et al.: causal modeling interpretation - intersectionality about causal effects of intersecting categories
- Suggests attribute-based approach: combine race and gender categories
- Jorba & López de Sa: emergent interpretation - intersectional experiences emerge from social structures, not reducible to combinations
- Hancock & Bowleg: intersectionality is non-additive
- Tension: Can intersectional groups be derived from attributes or are they emergent entities?
- Implications for ML: Can we specify G by combining base attributes or must we identify groups through social practice?

**Gap Connection**: Two incompatible ontologies, both with philosophical pedigree. No resolution.

**Subsection 3.3: Social Ontology of Groups** (400 words)

**Papers**:
- Haslanger2012 (social construction frameworks)
- Epstein2019 (type 1 vs type 2 groups)
- Sveinsdottir2013 (conferralist account)
- Ritchie2020 (structuralist ontology)
- Thomasson2019 (ontology of social groups)
- HaslangerAsta2017 (feminist metaphysics)
- Mikkola2016 (sex and gender categories)

**Content**:
- Epstein: Type 2 groups (racial/ethnic) lack volitional structure but have "minimal structure" through common possession of features
- Suggests attribute-based specification possible
- Haslanger/Ásta: social construction depends on practices, not just attributes
- Ritchie: groups constituted by social structures (networks of relations)
- Thomasson: competing accounts - sets of individuals vs. structured entities
- No consensus on whether groups exhaustively specifiable through attribute combinations
- For algorithmic fairness: Can we derive G from dataset attributes or do groups depend on context-specific social practices?

**Section 3 Summary**: Philosophy literature reveals deep ontological uncertainty about intersectional groups. Multiple frameworks, no consensus. This is not a technical problem to be solved but a conceptual challenge.

---

## Section 4: Measurement and Operationalization

**Section Purpose**: Bridge technical and philosophical dimensions by showing measurement choices embed ontological commitments

**Word Target**: 800 words

**Subsection 4.1: Construct Validity in Algorithmic Fairness** (400 words)

**Papers**:
- JacobsWallach2021 (measurement and fairness)
- Selbst2019 (abstraction traps)
- Blodgett2020 (bias in NLP)
- Hellman2020 (what metrics measure)
- Fazelpour2021 (algorithmic bias)

**Content**:
- Jacobs & Wallach: fairness involves unobservable constructs that must be operationalized
- Operationalization introduces mismatches between construct and measurement
- Fairness itself is essentially contested construct
- Selbst: abstraction traps - technical interventions fail when formal models mismatch social contexts
- Blodgett: many "bias" operationalizations have questionable construct validity
- Key insight: What we measure depends on our theoretical understanding (ontology)

**Gap Connection**: Measurement validity depends on resolving what groups are, but that's ontologically contested

**Subsection 4.2: Validity of Demographic Categories** (400 words)

**Papers**:
- Scheuerman2020 (constructing race/gender in datasets)
- FournierMontgieux2025 (demographic inference reliability)
- Geiger2020 (training data provenance)
- Obermeyer2019 (construct validity failure)
- Barocas2020 (hidden assumptions)
- Mayson2019 (bias in bias out)

**Content**:
- Scheuerman: wide variation in how race/gender operationalized in datasets
- Different operationalizations reflect different ontological commitments (often implicit)
- Fournier-Montgieux: measurement error in demographic categories undermines fairness assessment
- Obermeyer: healthcare algorithm used costs as proxy for needs - construct validity failure
- Barocas: counterfactual fairness assumes ability to intervene on demographic attributes, but conceptually incoherent if attributes are constitutively constructed
- Measurement choices aren't neutral - they encode answers to ontological questions

**Section 4 Summary**: Operationalizing intersectionality for algorithmic fairness requires resolving ontological questions that philosophy shows are deeply contested. Measurement validity presupposes ontological clarity we don't have.

---

## Section 5: Normative Frameworks for Fairness Trade-offs

**Section Purpose**: Establish that different normative frameworks give different answers to which groups matter and how to handle trade-offs

**Word Target**: 700 words

**Subsection 5.1: Distributive Justice Principles** (350 words)

**Papers**:
- Parfit1997 (prioritarianism)
- Frankfurt1987 (sufficientarianism)
- Kuppler2022 (fairness vs. justice)
- Binns2024 (approximate justice)
- Crisp2003 (equality, priority, compassion)

**Content**:
- Kuppler: fairness (algorithm property) ≠ justice (allocation principle)
- Distributive justice theories: egalitarianism, prioritarianism, sufficientarianism
- Prioritarianism: greater weight to worse-off groups
- Sufficientarianism: ensure all groups above threshold
- Different theories imply different answers to which groups we should track
- Egalitarianism: all groups matter equally → comprehensive intersectional specification
- Sufficientarianism: focus on groups below threshold → could limit G
- No consensus on which framework applies

**Gap Connection**: Normative framework influences group specification, but which framework is itself contested

**Subsection 5.2: Leveling Down and Trade-offs** (350 words)

**Papers**:
- Holm2023 (egalitarianism and algorithmic fairness)
- Mittelstadt2023 (leveling down critique)
- Hertweck2022 (justice-based framework for trade-offs)
- Green2022 (escaping impossibility)
- Lee2021 (formalizing trade-offs)
- Herlitz2019 (indispensability of sufficientarianism)
- CorbettDavies2018 (measure and mismeasure)
- Binns2018 (political philosophy)

**Content**:
- Leveling down objection: should we harm advantaged groups to achieve parity?
- Holm: egalitarian response to leveling down
- Mittelstadt: strict egalitarianism may be inappropriate default
- Hertweck: fairness-utility trade-offs need normative framework
- Herlitz: sufficientarianism may forbid trade-offs involving groups below threshold
- Implications: Which groups to include in G depends on normative framework
- Different frameworks lead to different group specifications
- Corbett-Davies: no universally appropriate metric - depends on normative goals

**Section 5 Summary**: Normative theory adds another layer of contestation. Which groups matter depends on distributive justice principles, which are themselves debated. Statistical constraints interact with normative choices.

---

## Section 6: Epistemic Dimensions

**Section Purpose**: Show that determining which groups to track involves epistemic authority questions and justice considerations

**Word Target**: 600 words

**Subsection 6.1: Epistemic Justice and Group Categories** (300 words)

**Papers**:
- Fricker2007 (epistemic injustice)
- Anderson2012 (epistemic justice in institutions)
- Kay2024 (epistemic injustice in AI)
- DOgnazio2020 (data feminism)
- Taylor2016 (whose public, whose good)
- Kalluri2020 (power in AI)
- Harding2004 (standpoint epistemology)

**Content**:
- Fricker: testimonial and hermeneutical injustice
- Algorithmic systems can perpetuate epistemic injustice by excluding marginalized groups from defining themselves
- Who gets to determine which groups matter in fairness analysis?
- Taylor: data practices involve epistemic choices that advantage some perspectives
- Kalluri: epistemic authority over group categories is form of power
- D'Ignazio & Klein: without diverse perspectives, ML perpetuates epistemic injustice
- Harding: standpoint epistemology - marginalized groups may have epistemic advantage about their own oppression
- Implication: Group specification shouldn't be purely technical decision by ML researchers

**Gap Connection**: Ontological question (which groups?) is also epistemic justice question (who decides?)

**Subsection 6.2: Uncertainty and Epistemic Responsibility** (300 words)

**Papers**:
- Hüllermeier2021 (aleatoric vs epistemic uncertainty)
- Bhatt2021 (uncertainty as transparency)
- Eubanks2018 (epistemic irresponsibility)
- Benjamin2019 (race after technology)
- Noble2018 (algorithms of oppression)
- ONeill2016 (weapons of math destruction)
- Gebru2021 (datasheets)
- Raji2020 (algorithmic auditing)
- Fazelpour2023 (situated justice)

**Content**:
- Hüllermeier: epistemic uncertainty (lack of knowledge) vs. aleatoric (inherent randomness)
- Statistical uncertainty about intersectional groups is partly epistemic (more data could reduce)
- But what counts as "enough" data depends on stakes (epistemic responsibility)
- Bhatt: uncertainty quantification crucial for responsible AI
- Eubanks, O'Neil, Benjamin, Noble: systems make overconfident claims about groups with insufficient epistemic basis
- Gebru: datasheets as epistemic transparency about category definitions
- Raji: auditing requires epistemic warrant for claims about groups
- Fazelpour: epistemic responsibility depends on situated context
- When is it epistemically responsible to make fairness claims about intersectional groups with sparse data?

**Section 6 Summary**: Epistemic dimensions compound the dilemma. Group specification is epistemic justice question. Statistical uncertainty about small groups raises epistemic responsibility issues. No clear standards for when evidence suffices.

---

## Section 7: Synthesis - The Intersectionality Dilemma

**Section Purpose**: Explicitly articulate the dilemma and show no existing work addresses the interaction between statistical and ontological uncertainty

**Word Target**: 600 words

**Content**:

**The Dilemma Structure**:
- Horn 1 (Statistical): Estimating fairness for intersectional groups requires adequate sample sizes. Small groups lead to high epistemic uncertainty. Solution: Limit groups to those with sufficient data.
- Horn 2 (Ontological): Which groups warrant fairness consideration? Philosophy shows deep disagreement between attribute-based (combinatorial) and practice-based (emergent) accounts. No principled way to decide which groups matter without resolving contested ontology.
- The Interaction: Expanding groups to respect ontological complexity exacerbates statistical problems (more groups = less data per group). Constraining groups to handle statistical problems requires resolving which groups to omit - an ontologically and normatively contested question.

**What Existing Work Does**:
- ML/CS (Domain 1): Sophisticated technical solutions to data sparsity, but assumes groups are given
  - No work asks: "Which groups should G contain?"
  - Treats group specification as input, not problem to be solved
- Philosophy (Domains 2-3): Rich debates on ontology of intersectional groups, but not connected to statistical/operational constraints
  - No work asks: "Given data limitations, how should we operationalize contested ontology?"
- Measurement theory (Domain 4): Recognizes operationalization embeds ontological commitments, but doesn't frame as dilemma
- Normative theory (Domain 5): Different frameworks imply different group priorities, but doesn't connect to statistical feasibility
- Epistemology (Domain 6): Questions of epistemic authority and responsibility, but not connected to statistical uncertainty

**Critical Gap**: NO existing work frames intersectional fairness as involving a dilemma between statistical and ontological uncertainty where each horn exacerbates the other.

**Who Comes Closest**:
- Castelnovo2022: Notes exponential increase in subgroups may be "unfeasible" but treats as computational not ontological issue
- JacobsWallach2021: Fairness as essentially contested construct but doesn't connect to group specification problem
- Collins2015: "Definitional dilemmas" in intersectionality theory but not applied to algorithmic fairness
- BrightMalinskyThompson2016 and JorbaLopezdeSa2024: Competing ontologies but don't discuss operational implications

**Why This Matters**:
- Existing approaches cannot resolve the dilemma through technical or philosophical progress alone
- Technical solutions (multicalibration, synthetic data) don't answer which groups
- Philosophical progress on ontology doesn't eliminate statistical constraints
- The dilemma is genuine: improving one dimension worsens the other

**Papers Acknowledging Partial Challenges**:
- Statistical challenge acknowledged: GoharCheng2023, Castelnovo2022, Hansen2024, Sheng2025
- Ontological challenge acknowledged: Collins2015, McCall2005, Epstein2019
- Measurement/operationalization challenge: JacobsWallach2021, Scheuerman2020
- But NO work connects them as mutually reinforcing horns of a dilemma

**Research Opportunity**: This paper will be first to frame intersectional fairness through the lens of this dilemma, analyze why it's genuine (not merely technical), and explore potential responses (clarify purposes of fairness audits, accept trade-offs, develop context-sensitive frameworks).

---

## Section 8: Conclusion

**Purpose**: Synthesize the review, position the research project, state expected contributions

**Word Target**: 500 words

**Content**:
- Summary: Intersectional fairness is crucial but faces two forms of uncertainty
- Literature review shows: each form of uncertainty well-studied in isolation
  - ML/CS: Statistical challenges recognized, technical solutions sophisticated
  - Philosophy: Ontological complexity explored, multiple frameworks available
  - Measurement: Operationalization challenges understood
  - Normative: Multiple frameworks for trade-offs
  - Epistemic: Justice dimensions recognized
- The gap: No work synthesizes these to show the dilemma structure
- The dilemma is genuine because:
  - You can't solve statistical problems without making ontological choices
  - You can't make ontological choices without confronting statistical constraints
  - Technical and philosophical progress alone insufficient
- Contribution of this research:
  1. First systematic framing of intersectionality dilemma in algorithmic fairness
  2. Analysis of why dilemma is genuine (not purely technical or purely philosophical)
  3. Exploration of responses:
     - Clarify purposes of fairness audits (legal compliance vs. non-discrimination vs. justice)
     - Normative frameworks for principled trade-offs (prioritarianism/sufficientarianism)
     - Context-sensitive approaches acknowledging no universal solution
  4. Bridge ML/CS and philosophy literatures
- Significance:
  - Theoretical: Shows limits of purely technical or purely philosophical approaches
  - Practical: Helps practitioners understand why intersectional fairness is hard
  - Methodological: Models interdisciplinary engagement between ML and philosophy
- Expected audience impact:
  - FAccT: Novel framing of long-standing challenge, philosophically grounded
  - Philosophy journals: Application of social ontology to live practical problem
  - Interdisciplinary: Example of productive engagement between fields

---

## Overall Structure Summary

**Total Sections**: 8 sections (Introduction + 6 content sections + Synthesis/Conclusion)

**Narrative Flow**:
1. Problem framing: Intersectional fairness matters but is challenging
2. Technical landscape: ML/CS has sophisticated solutions to statistics, assumes groups given
3. Philosophical landscape: Ontology of groups is contested, multiple frameworks
4. Measurement bridge: Operationalization embeds ontological commitments
5. Normative layer: Which groups matter depends on distributive justice theory
6. Epistemic layer: Who decides and what counts as sufficient evidence?
7. Synthesis: The dilemma - horns interact, no existing work addresses interaction
8. Conclusion: Position research contribution

**Papers by Section**:
- Section 1 (Introduction): 5 foundational papers
- Section 2 (Technical): 17 papers from Domain 1
- Section 3 (Philosophy): 15 papers from Domains 2-3
- Section 4 (Measurement): 12 papers from Domain 4
- Section 5 (Normative): 13 papers from Domain 5
- Section 6 (Epistemic): 17 papers from Domain 6
- Section 7 (Synthesis): Cross-references key papers showing gap
- Section 8 (Conclusion): Integration

**Total Word Target**: ~5,000 words (500 + 1100 + 1200 + 800 + 700 + 600 + 600 + 500)

**Total Papers Available**: 95 papers across 6 domains
**Expected Papers Cited**: 60-70 papers (selective, emphasizing most relevant)

**Disciplinary Balance**:
- ML/CS (Domains 1, 4): ~1900 words
- Philosophy (Domains 2, 3, 5, 6): ~2500 words
- Integration (Sections 1, 7, 8): ~1600 words
- Overall: Balanced interdisciplinary review

---

## Notes for Synthesis Writers

**Integration Points**:
- Section 3-4 transition: Philosophy establishes ontological uncertainty → Measurement shows operationalization embeds ontology
- Section 5-6 connection: Normative frameworks → Epistemic authority (who decides which framework?)
- Section 6-7 transition: Epistemic dimensions → Synthesis of full dilemma

**Tension Points**:
- Bright et al. (causal/attribute-based) vs. Jorba & López de Sa (emergent)
- Egalitarian vs. prioritarian vs. sufficientarian implications for group specification
- Technical feasibility vs. ontological complexity

**Technical Concepts Needing Explanation**:
- Multicalibration (brief, accessible explanation)
- Conditional demographic parity (what it requires)
- Combinatorial explosion (why exponential growth matters)
- Construct validity (measurement theory basics)
- Social construction (multiple senses)

**Citation Strategy**:
- Foundational works: Crenshaw2015, Foulds2020, BrightMalinskyThompson2016, JacobsWallach2021, Fricker2007
- Recent ML/CS: GoharCheng2023, Lett2025, Sheng2025, Halevy2025, Hashimoto2025
- Philosophy: JorbaLopezdeSa2024, Epstein2019, Binns2024
- Bridge works: Scheuerman2020, Kay2024, Fazelpour2023

**Tone**:
- Analytical and focused (not encyclopedic)
- Clear positioning: "This gap matters because..."
- Build cumulative case for dilemma framing
- Balance technical and philosophical sophistication
- Accessible to both FAccT and philosophy journal audiences

**Critical Success Factor**:
- Section 7 must EXPLICITLY state that no existing work frames the interaction as a dilemma
- Use phrases like: "While X addresses statistical challenges and Y addresses ontological questions, NO existing work examines their interaction"
- Be specific about who comes closest and what they miss
- This gap justification is the core contribution
