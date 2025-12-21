# State-of-the-Art Literature Review Outline

**Research Project**: Is Mechanistic Interpretability Necessary or Sufficient for AI Safety?
**Date**: 2025-12-21
**Total Literature Base**: 90 papers across 7 domains

---

## Overview and Narrative Arc

This literature review synthesizes research on mechanistic interpretability (MI) and its relationship to AI safety, organized around a central analytical question: Can MI serve as either a necessary or sufficient condition for achieving AI safety? The review targets analytic philosophers and philosophy of science journal editors, emphasizing conceptual precision over technical comprehensiveness.

**Narrative Structure**: The review progresses through four movements:
1. **Conceptual Foundations**: Establishing what "mechanistic" means across philosophy and AI research, revealing fundamental definitional tensions
2. **The Promise of MI for Safety**: Articulating the strongest case for MI as a safety tool
3. **Critical Examination**: Systematically evaluating necessity and sufficiency claims against philosophical and empirical evidence
4. **Gaps and Future Directions**: Identifying unresolved tensions that the research project addresses

---

## Introduction

**Purpose**: Frame the research question within broader AI safety debates and establish the conceptual stakes of definitional disagreements about "mechanistic interpretability."

**Content**:
- Opening framing: The recent surge in mechanistic interpretability research has been accompanied by strong claims about its role in ensuring AI safety (Bereska and Gavves 2024; Sharkey et al. 2025). Yet beneath surface consensus lies fundamental disagreement about what "mechanistic" means in this context.
- The core puzzle: Two competing visions of MI exist in the literature. Technical MI research focuses on reverse-engineering circuits and features at the level of neurons and attention heads (Nanda et al. 2023; Conmy et al. 2023). Philosophical treatments propose broader conceptualizations that include functional and higher-level explanations (Kastner and Crook 2024). These different definitions have radically different implications for evaluating MI's role in safety.
- Stakes of the question: If MI is both necessary and sufficient for safety, as some claim (Kastner and Crook 2024), this would justify prioritizing MI research over alternative safety approaches. If MI is neither necessary nor sufficient, resources might be better directed elsewhere. The conceptual confusion itself is an obstacle to rational resource allocation in AI safety research.
- Scope and structure: This review examines definitions of MI, evaluates necessity and sufficiency claims for AI safety, and identifies gaps that require resolution. It draws on technical MI literature, AI safety research, philosophical accounts of mechanistic explanation, and XAI philosophy.

**Key Papers**:
- Bereska and Gavves (2024) - comprehensive MI review
- Kastner and Crook (2024) - philosophical treatment claiming MI is necessary and sufficient
- Sharkey et al. (2025) - open problems in MI
- Nanda et al. (2023) - exemplar of narrow technical MI

**Word Target**: 450-500 words

---

## Section 1: The Concept of "Mechanistic" in Mechanistic Interpretability

**Section Purpose**: Establish the conceptual landscape by examining how "mechanistic" is understood across philosophy of science and AI research, revealing that definitional disagreements are not merely terminological but reflect different theoretical commitments with practical implications.

**Main Claims**:
1. There are at least two distinct conceptualizations of MI in current literature: a narrow view (circuit-level, neuron-focused) and a broad view (including functional organization and higher-level explanations).
2. These conceptualizations differ in their relationship to classical philosophical accounts of mechanistic explanation.
3. The definitional disagreement has direct implications for evaluating necessity/sufficiency claims about MI and safety.

---

### Subsection 1.1: Philosophical Accounts of Mechanistic Explanation

**Papers**: Machamer, Darden, and Craver (2000); Craver (2007); Glennan (1996, 2017); Bechtel and Richardson (2010); Craver and Kaplan (2018); Wimsatt (1994)

**Content**:
The "new mechanistic" philosophy provides theoretical grounding for what counts as genuinely mechanistic explanation. Machamer, Darden, and Craver (2000) define mechanisms as "entities and activities organized to produce regular changes from start to finish conditions," emphasizing productive continuity rather than covering-law derivation. Craver (2007) develops the influential "levels of mechanisms" framework, where mechanistic levels are defined by constitutive part-whole relationships via mutual manipulability criteria. Glennan (1996, 2017) offers a complementary account emphasizing invariant, change-relating generalizations governing component interactions.

Critical for evaluating MI claims is Bechtel and Richardson's (2010) analysis of decomposition and localization as heuristic strategies. They show that these strategies succeed only under conditions of near-decomposability - when systems can be meaningfully divided into components with well-defined functions. Systems with distributed processing or nonlinear interactions resist simple decomposition. This raises immediate questions about whether neural networks satisfy the conditions required for mechanistic explanation.

Craver and Kaplan (2018) address completeness norms: mechanistic explanations need not include all details, only those constitutively relevant to the phenomenon being explained. This suggests that different levels of MI detail might be appropriate for different explanatory purposes.

**Gap Connection**: The philosophical literature provides principled criteria for what counts as "mechanistic" - criteria that can be used to evaluate whether current MI techniques achieve genuine mechanistic understanding or merely provide fine-grained descriptions. Most MI research does not engage with these criteria.

---

### Subsection 1.2: The Narrow View - MI as Circuit-Level Analysis

**Papers**: Nanda et al. (2023); Conmy et al. (2023); Rai et al. (2024); Cunningham et al. (2023); He et al. (2024); Geiger et al. (2023)

**Content**:
The dominant interpretation of MI in technical research focuses on reverse-engineering neural networks at the level of individual components: neurons, attention heads, and minimal circuits. Nanda et al. (2023) exemplify this approach by fully reverse-engineering the algorithm learned by small transformers for modular addition, identifying discrete Fourier transforms and trigonometric identities implemented by specific network components. Conmy et al. (2023) systematize this methodology through the ACDC algorithm, which uses activation patching to identify minimal subgraphs responsible for specific behaviors.

This narrow view defines MI primarily through its methods: activation patching, ablation studies, and circuit discovery. Rai et al. (2024) organize the field around "fundamental objects of study" - neurons, attention heads, circuits, and features - with techniques like probing and ablation to analyze each. Cunningham et al. (2023) address the superposition problem through sparse autoencoders that decompose activations into overcomplete sets of monosemantic features.

Geiger et al. (2023) provide theoretical foundations through causal abstraction, formalizing the relationship between high-level functional descriptions and low-level implementations. This framework unifies various MI methods but maintains focus on causal intervention at the component level.

The narrow view's commitment to bottom-up analysis reflects a reductionist research strategy: understand small components, then scale up understanding. However, Zimmermann et al. (2023) find that model scale does not improve mechanistic interpretability - larger models are not easier to interpret, challenging assumptions about scalability.

**Gap Connection**: The narrow view's focus on low-level components may not capture the levels of organization that mechanistic explanation traditionally addresses. Whether circuits and features satisfy Craver's mutual manipulability criteria for constitutive relevance remains unexamined.

---

### Subsection 1.3: The Broad View - MI as Functional Organization

**Papers**: Kastner and Crook (2024); Sullivan (2020); Duran (2021); Buchholz (2022); O'Hara (2020)

**Content**:
Kastner and Crook (2024) represent a philosophical treatment that conceptualizes MI more broadly, drawing explicit connections to mechanistic explanation in the life sciences. They argue that XAI research should pursue mechanistic interpretability by applying "coordinated discovery strategies" from life sciences to uncover the "functional organization" of AI systems. Crucially, they claim that MI "enables us to meet desirable social desiderata including safety" - suggesting MI is both necessary and sufficient for safety goals.

This broader view resonates with philosophy of science work on explanation in AI. Sullivan (2020) argues that the primary obstacle to understanding from ML models is not opacity itself but "link uncertainty" - lack of evidence connecting model components to target phenomena. Understanding requires more than transparent descriptions; it requires establishing how identified structures relate to behaviors of interest. Duran (2021) proposes "scientific XAI" (sXAI) applying philosophy of science standards: explanations must be testable, provide causal information, and support counterfactual reasoning.

Buchholz (2022) applies means-end epistemology, arguing that different epistemic goals require different explanatory methods. This suggests MI may be appropriate for some purposes (model debugging) but not others (end-user accountability). O'Hara (2020) emphasizes that technical sophistication does not guarantee explanatory adequacy - XAI methods may operate with implicit assumptions about explanation that do not align with genuine epistemic needs.

**Gap Connection**: The broad view better aligns with philosophical accounts of mechanistic explanation but lacks concrete operationalization. How exactly do life-science discovery strategies transfer to neural networks? What specific methods count as pursuing functional organization versus component analysis?

---

### Subsection 1.4: Bridging the Gap? Causal Abstraction and Levels

**Papers**: Geiger et al. (2023); Zhong et al. (2023); Craver (2007); Wimsatt (1994)

**Content**:
The causal abstraction framework (Geiger et al. 2023) offers a potential bridge between narrow and broad conceptions by formalizing relationships between different levels of description. It defines when a high-level interpretable algorithm is faithfully implemented by low-level neural network operations, providing criteria for "graded faithfulness" that accommodate approximate relationships.

However, Zhong et al. (2023) demonstrate a fundamental challenge: neural networks trained on identical tasks can learn qualitatively different algorithmic implementations ("Clock" vs "Pizza" algorithms for modular addition), depending on initialization and hyperparameters. This multiplicity of implementations suggests that mechanistic understanding may require population-level analysis rather than individual network analysis, complicating both narrow and broad approaches.

From philosophy of science, Wimsatt's (1994) perspectival account of levels as "local maxima of regularity and predictability" offers resources for understanding why certain decompositions yield more stable interpretations than others. But this perspectivalism potentially undermines claims about objective mechanistic structure in neural networks if levels are merely epistemic convenience.

**Gap Connection**: The relationship between different levels of mechanistic analysis in neural networks - and whether neural networks support genuine mechanistic levels in Craver's sense - remains underexplored. This conceptual gap directly affects how we should interpret MI findings for safety purposes.

**Section Summary**: The literature reveals a spectrum from narrow circuit-focused MI to broad functional MI, with fundamental questions about whether neural networks satisfy conditions required for mechanistic explanation. These definitional issues are not merely terminological - they determine what counts as successful MI and therefore what would be needed to evaluate necessity/sufficiency claims for safety.

**Word Target**: 1200-1400 words

---

## Section 2: MI and AI Safety - Evaluating the Claims

**Section Purpose**: Critically examine claims that MI is necessary and/or sufficient for AI safety, marshaling evidence from AI safety literature, limitations research, and philosophical analysis.

**Main Claims**:
1. The case for MI's importance to safety rests on specific theoretical assumptions about how AI systems can fail and how failures can be detected.
2. Empirical and theoretical challenges reveal that MI is likely neither straightforwardly necessary nor sufficient for safety.
3. Different safety goals (preventing deception, ensuring robustness, detecting emergent capabilities) may require different relationships with interpretability.

---

### Subsection 2.1: The Case for MI as Essential to Safety

**Papers**: Bereska and Gavves (2024); Kastner and Crook (2024); Vold and Harris (2021); Ball et al. (2025); Redep et al. (2024)

**Content**:
The strongest case for MI's essentiality draws on the "control problem" (Vold and Harris 2021): as AI systems become more capable, ensuring they pursue intended objectives becomes increasingly critical. MI proponents argue that understanding model internals is the only reliable way to detect whether models are genuinely aligned or merely appearing to be so.

Bereska and Gavves (2024) articulate specific safety benefits: MI could reveal hidden goals, detect deceptive alignment, identify capability-acquiring behaviors before deployment, and enable targeted modifications to problematic circuits. This goes beyond behavioral evaluation, which can be gamed by sufficiently sophisticated systems.

Ball et al. (2025) provide theoretical support through impossibility results: they prove that for some LLMs, adversarial prompts eliciting harmful behavior are computationally indistinguishable from benign prompts for any efficient filter. If external filtering is fundamentally limited, understanding model internals becomes necessary for safety.

Practical demonstrations show MI can identify specific mechanisms responsible for undesired behaviors. Redep et al. (2024) use MI to detect hallucinations in RAG models by identifying when Knowledge FFNs overemphasize parametric knowledge while Copying Heads fail to retain external knowledge - actionable insights for safety improvement.

**Gap Connection**: The theoretical case for MI rests on unproven assumptions about what MI can achieve at scale. Current demonstrations on toy tasks do not establish that similar insights are possible for safety-critical behaviors in frontier models.

---

### Subsection 2.2: Is MI Necessary? Alternative Safety Approaches

**Papers**: Perrier (2025); Dai et al. (2023); Lindstrom et al. (2025); Zhou et al. (2023); Baum (2025)

**Content**:
The necessity claim faces challenges from alternative safety approaches that do not rely on interpretability. Perrier (2025) argues that formal optimal control theory should be central to alignment, proposing an "Alignment Control Stack" that organizes interventions hierarchically across system layers. On this view, interpretability is one tool among many, not uniquely necessary.

Dai et al. (2023) demonstrate Safe RLHF, which explicitly decouples helpfulness and harmlessness objectives through constrained optimization, achieving safety improvements without requiring mechanistic understanding. Lindstrom et al. (2025) provide sociotechnical critique showing that purely technical solutions - including interpretability - cannot solve alignment without addressing normative and political dimensions.

Zhou et al. (2023) propose "Predictable AI" as an alternative paradigm focused on anticipating key validity indicators. If we can reliably predict AI behavior without understanding mechanisms, predictability may substitute for interpretability in many safety contexts.

Baum (2025) develops a structured taxonomy distinguishing AI alignment along multiple dimensions (aim, scope, constituency). Different alignment configurations may require different tools - MI may be necessary for some but not all alignment targets.

**Gap Connection**: The literature reveals multiple viable safety approaches, challenging necessity claims. However, systematic comparison of what different approaches can and cannot achieve is lacking.

---

### Subsection 2.3: Is MI Sufficient? Limitations and Dual-Use Risks

**Papers**: Sharkey et al. (2025); Zimmermann et al. (2023); Miller et al. (2024); Zhang and Nanda (2023); Lieberum et al. (2023); Winninger et al. (2025); Madsen et al. (2024)

**Content**:
Even if MI is necessary, it is clearly not sufficient for safety. Sharkey et al. (2025) identify numerous open problems requiring solution before MI can deliver on safety promises: methods need conceptual and practical improvements, applications to specific safety goals remain underdeveloped, and socio-technical challenges persist.

Scalability challenges are severe. Zimmermann et al. (2023) find that model scale does not improve interpretability - modern models appear less interpretable than decade-old architectures, suggesting MI faces fundamental barriers as models grow. Lieberum et al. (2023) test circuit analysis on 70B-parameter Chinchilla, finding that techniques scale but semantic understanding remains partial and distribution-dependent.

Methodological fragility compounds these challenges. Miller et al. (2024) demonstrate that circuit faithfulness metrics are highly sensitive to ablation methodology choices - the same circuit receives very different scores depending on technical decisions. Zhang and Nanda (2023) show activation patching results are highly sensitive to hyperparameters, potentially leading to disparate conclusions about component importance. These findings suggest that "circuit discovery" may identify measurement artifacts rather than objective model properties.

Most troublingly, Winninger et al. (2025) demonstrate that MI can be weaponized for adversarial attacks. By identifying "acceptance subspaces" through mechanistic analysis, they achieve 80-95% jailbreak success rates on state-of-the-art models. The same understanding needed for alignment verification enables more sophisticated attacks, creating fundamental dual-use tensions.

Madsen et al. (2024) articulate the faithfulness problem: explanations may be convincing but not reflect actual model behavior. False but plausible explanations could create dangerous overconfidence in AI systems, making MI counterproductive for safety if not properly validated.

**Gap Connection**: Sufficiency claims are undermined by scalability limitations, methodological fragility, dual-use risks, and the faithfulness problem. What additional conditions would be required for MI to contribute reliably to safety?

---

### Subsection 2.4: Social-Epistemic Dimensions

**Papers**: Huang et al. (2022); Smart and Kasirzadeh (2024); Fazi (2020); Jongepier and Keymolen (2022); Duede (2022); Boge and Mosig (2025)

**Content**:
Technical MI analyses face social-epistemic challenges that further complicate sufficiency claims. Huang et al. (2022) draw on feminist epistemology to argue that proper detection of algorithmic bias requires interpretive resources only available through diverse stakeholder involvement - purely technical transparency cannot identify all problematic patterns.

Smart and Kasirzadeh (2024) introduce "socio-structural explanations" as a third type beyond mechanistic and non-mechanistic interpretations. ML models are embedded within and shaped by social structures; understanding outputs may require explaining how social structures contribute to model behavior. Mechanistic interpretability addresses only one layer of required explanation.

Fazi (2020) raises deeper concerns about incommensurability: deep learning may involve abstractive operations not constrained by human modes of representation, creating genuine epistemic gaps that XAI attempts to "re-present" but may fail to capture. If algorithmic operations genuinely exceed human comprehensibility, MI provides useful approximations but not complete understanding.

Jongepier and Keymolen (2022) reframe the question around agency: interpretability is ethically required when lack of understanding threatens autonomy, not because AI systems are intrinsically different from human decision-makers. This suggests MI serves agency-protection rather than pure transparency.

Duede (2022) notes that opacity matters differently depending on AI's role in broader scientific methodology - what counts as adequate explanation depends on context and purpose. Boge and Mosig (2025) argue XAI must meet testability standards: genuine explanations support interventions and counterfactuals, not just descriptions. Many XAI methods may provide post-hoc rationalizations rather than testable explanations.

**Gap Connection**: The social-epistemic dimension reveals that MI's value for safety depends not just on technical capabilities but on how interpretability findings are produced, communicated, and used within institutional contexts.

**Section Summary**: Systematic examination reveals MI is likely neither straightforwardly necessary nor sufficient for AI safety. Alternative safety approaches exist; MI faces scalability, faithfulness, and dual-use challenges; and social-epistemic dimensions add further complexity. However, this does not mean MI is irrelevant - rather, its role requires more precise specification.

**Word Target**: 1100-1300 words

---

## Section 3: Research Gaps and Opportunities

**Purpose**: Explicitly articulate what's missing from current literature and how this research project addresses those gaps.

---

### Gap 1: Conceptual Clarification of "Mechanistic" in MI

**Evidence**: The literature operates with at least two distinct conceptualizations of MI (narrow circuit-focused vs. broad functional) without explicit engagement about boundary-drawing criteria. Technical MI research (Nanda et al. 2023; Conmy et al. 2023) assumes shared understanding without philosophical justification. Kastner and Crook (2024) invoke philosophy of science but do not engage with specific criteria from mechanistic explanation literature (Craver 2007; Glennan 2017).

**Why It Matters**: Different definitions have different implications for evaluating safety claims. If "mechanistic" requires satisfying mutual manipulability criteria for constitutive relevance, most current MI techniques may not qualify. If broader functional interpretations count, the scope of what contributes to MI expands considerably.

**How Research Addresses It**: This project provides systematic conceptual analysis of how different MI definitions relate to philosophical accounts of mechanistic explanation, establishing clear criteria for what should count as "mechanistic" in the AI context.

**Supporting Literature**: Machamer et al. (2000); Craver (2007); Glennan (2017); Kastner and Crook (2024); Bereska and Gavves (2024)

---

### Gap 2: Rigorous Analysis of Necessity/Sufficiency Claims

**Evidence**: Claims about MI's role in safety are frequently asserted without careful philosophical analysis of the logical structure of necessity and sufficiency. Kastner and Crook (2024) claim MI "enables us to meet" safety desiderata (suggesting sufficiency) without specifying what other conditions might be required. Safety literature assumes interpretability's importance without rigorous counterfactual analysis of whether safety could be achieved through alternative means.

**Why It Matters**: Resource allocation in AI safety research depends on understanding MI's actual role. If MI is one useful tool among many, blanket prioritization is unwarranted. If it is uniquely necessary, alternative approaches waste resources.

**How Research Addresses It**: This project provides rigorous philosophical analysis of necessity and sufficiency claims, specifying under what definitions and conditions each claim might hold, and what evidence would be required to establish each.

**Supporting Literature**: Ball et al. (2025); Perrier (2025); Dai et al. (2023); Sharkey et al. (2025)

---

### Gap 3: Connection Between Philosophy of Mechanism and AI Interpretability

**Evidence**: The rich literature on mechanistic explanation from philosophy of neuroscience and biology (Craver 2007; Bechtel and Richardson 2010; Glennan 2017) provides principled criteria for mechanistic explanation, but these are rarely applied to evaluate MI claims. Zhong et al. (2023) explicitly apply mechanistic framing to neural networks but do not engage with Craver's constitutive relevance criteria or Bechtel and Richardson's analysis of when decomposition strategies succeed.

**Why It Matters**: Philosophy of mechanism offers conceptual tools for addressing whether neural networks can be said to have mechanisms in the relevant sense, whether current MI techniques identify constitutively relevant components, and what levels of analysis are appropriate.

**How Research Addresses It**: This project bridges philosophy of mechanism and AI interpretability, using established philosophical frameworks to evaluate MI claims and identify what would be required for genuine mechanistic understanding of neural networks.

**Supporting Literature**: Craver (2007); Bechtel and Richardson (2010); Craver and Kaplan (2018); Zhong et al. (2023); Geiger et al. (2023)

---

### Gap 4: Systematic Comparison of MI with Alternative Safety Approaches

**Evidence**: The AI safety literature contains multiple distinct approaches - RLHF-based alignment (Dai et al. 2023), formal control theory (Perrier 2025), predictability frameworks (Zhou et al. 2023), governance-based approaches (Herrera and Calderon 2025) - but systematic comparison of what different approaches can and cannot achieve is lacking. Claims about MI's unique importance are rarely evaluated against specific alternatives.

**Why It Matters**: Rational resource allocation requires understanding the comparative advantages and limitations of different safety approaches. MI may complement rather than replace alternative approaches.

**How Research Addresses It**: This project situates MI within a broader taxonomy of AI safety approaches, evaluating its comparative strengths and weaknesses for different safety goals.

**Supporting Literature**: Perrier (2025); Dai et al. (2023); Zhou et al. (2023); Baum (2025); Habli et al. (2025)

---

### Synthesis: How Gaps Collectively Motivate Research

The four gaps are interconnected. Conceptual clarification (Gap 1) is prerequisite for rigorous analysis of necessity/sufficiency (Gap 2), which requires connection to philosophy of mechanism (Gap 3) and comparison with alternatives (Gap 4). Current literature cannot answer "Is MI necessary or sufficient for AI safety?" because it lacks:
1. Clear definition of what "mechanistic" means in this context
2. Rigorous logical analysis of necessity/sufficiency claims
3. Philosophical criteria for evaluating mechanistic understanding
4. Systematic comparison with alternative approaches

This project provides an integrated analysis addressing all four gaps, offering conceptual clarity that enables more precise evaluation of MI's role in AI safety.

**Word Target**: 800-1000 words

---

## Conclusion

**Purpose**: Synthesize state-of-the-art and position the research contribution.

**Content**:
- Summary of definitional landscape: The literature reveals fundamental disagreement about what "mechanistic" means in MI, with implications for evaluating safety claims.
- State of necessity claims: Alternative safety approaches exist, challenging strong necessity claims; however, certain safety goals (detecting deceptive alignment) may specifically require internal model understanding.
- State of sufficiency claims: MI faces severe limitations - scalability, methodological fragility, dual-use risks, faithfulness problems - that clearly preclude sufficiency on its own.
- The conditional picture: MI's contribution to safety is likely conditional and context-dependent, requiring specification of which safety goals, which definitions, and which additional conditions.
- How research fills gaps: This project provides the conceptual clarification, rigorous analysis, philosophical grounding, and comparative framework needed to answer these questions.
- Expected contributions: (1) Precise taxonomy of MI conceptualizations and their relationship to philosophical accounts of mechanism; (2) Rigorous analysis of necessity/sufficiency claims under different definitions; (3) Framework for evaluating MI's comparative role alongside alternative safety approaches; (4) Recommendations for conceptual clarity in future research and policy.

**Word Target**: 400-500 words

---

## Notes for Synthesis Writer

### Papers by Section

**Introduction** (4-5 papers):
- Bereska and Gavves (2024) - sets up MI landscape
- Kastner and Crook (2024) - represents broad view with safety claims
- Sharkey et al. (2025) - open problems
- Nanda et al. (2023) - exemplar of narrow view

**Section 1: Concept of Mechanistic** (18-22 papers):
- Subsection 1.1: Machamer et al. (2000), Craver (2007), Glennan (1996, 2017), Bechtel and Richardson (2010), Craver and Kaplan (2018), Wimsatt (1994)
- Subsection 1.2: Nanda et al. (2023), Conmy et al. (2023), Rai et al. (2024), Cunningham et al. (2023), He et al. (2024), Geiger et al. (2023), Zimmermann et al. (2023)
- Subsection 1.3: Kastner and Crook (2024), Sullivan (2020), Duran (2021), Buchholz (2022), O'Hara (2020)
- Subsection 1.4: Geiger et al. (2023), Zhong et al. (2023), Craver (2007), Wimsatt (1994)

**Section 2: MI and Safety** (20-25 papers):
- Subsection 2.1: Bereska and Gavves (2024), Kastner and Crook (2024), Vold and Harris (2021), Ball et al. (2025), Redep et al. (2024)
- Subsection 2.2: Perrier (2025), Dai et al. (2023), Lindstrom et al. (2025), Zhou et al. (2023), Baum (2025)
- Subsection 2.3: Sharkey et al. (2025), Zimmermann et al. (2023), Miller et al. (2024), Zhang and Nanda (2023), Lieberum et al. (2023), Winninger et al. (2025), Madsen et al. (2024)
- Subsection 2.4: Huang et al. (2022), Smart and Kasirzadeh (2024), Fazi (2020), Jongepier and Keymolen (2022), Duede (2022), Boge and Mosig (2025)

**Section 3: Research Gaps** (12-15 papers - draws from earlier citations):
- Gap 1: Machamer et al. (2000), Craver (2007), Glennan (2017), Kastner and Crook (2024), Bereska and Gavves (2024)
- Gap 2: Ball et al. (2025), Perrier (2025), Dai et al. (2023), Sharkey et al. (2025)
- Gap 3: Craver (2007), Bechtel and Richardson (2010), Craver and Kaplan (2018), Zhong et al. (2023), Geiger et al. (2023)
- Gap 4: Perrier (2025), Dai et al. (2023), Zhou et al. (2023), Baum (2025), Habli et al. (2025)

**Conclusion** (3-4 papers - synthesis, no new citations needed)

### Total Word Target

- Introduction: 450-500 words
- Section 1 (Conceptual): 1200-1400 words
- Section 2 (Safety Claims): 1100-1300 words
- Section 3 (Gaps): 800-1000 words
- Conclusion: 400-500 words

**Total**: 3950-4700 words (target: 3500-4000 words - some compression needed)

### Total Papers

Approximately 55-65 unique papers cited across sections (well within 50-80 target).

### Citation Strategy

**Foundational Must-Cite Classics**:
- Machamer, Darden, and Craver (2000) - mechanistic explanation
- Craver (2007) - levels of mechanisms
- Glennan (1996, 2017) - new mechanical philosophy
- Bechtel and Richardson (2010) - decomposition and localization

**Key Recent Papers (2023-2025)**:
- Kastner and Crook (2024) - central philosophical treatment
- Bereska and Gavves (2024) - comprehensive MI review
- Sharkey et al. (2025) - open problems
- Nanda et al. (2023) - exemplar technical MI
- Conmy et al. (2023) - automated circuit discovery
- Geiger et al. (2023) - causal abstraction foundations

**Critical Voices**:
- Zimmermann et al. (2023) - scaling limitations
- Miller et al. (2024) - faithfulness metric fragility
- Winninger et al. (2025) - dual-use risks
- Madsen et al. (2024) - paradigm critique

### Tone

- Analytical and precise, emphasizing conceptual clarity
- Balanced - not advocacy for or against MI, but careful evaluation
- Building systematic case for gaps the research addresses
- Appropriate for philosophy of science journal audience
- Technical details where needed for philosophical points, but not for their own sake

### Key Tensions to Highlight

1. **Narrow vs. broad MI definitions** - and their different implications for safety claims
2. **Reductionist vs. holist** approaches to neural network understanding
3. **Technical optimism vs. empirical limitations** in MI research
4. **Transparency ideals vs. dual-use risks** - MI as both tool and vulnerability
5. **Component-level vs. social-epistemic** requirements for safety-relevant explanation
