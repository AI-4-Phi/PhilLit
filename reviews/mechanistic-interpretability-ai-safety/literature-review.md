# Is Mechanistic Interpretability Necessary or Sufficient for AI Safety?
## A State-of-the-Art Literature Review

---

## Introduction

The recent surge in mechanistic interpretability (MI) research has been accompanied by strong claims about its role in ensuring AI safety. Bereska and Gavves (2024) define mechanistic interpretability as "reverse-engineering the computational mechanisms and representations learned by neural networks into human-understandable algorithms and concepts," while Sharkey et al. (2025) identify numerous open problems requiring solution before MI can deliver on its promises. Yet beneath this surface consensus lies fundamental disagreement about what "mechanistic" means in this context—a disagreement with radical implications for evaluating MI's role in safety.

Two competing visions of MI exist in the literature. Technical MI research focuses on reverse-engineering circuits and features at the level of neurons and attention heads (Nanda et al. 2023; Conmy et al. 2023). This narrow interpretation treats MI as bottom-up analysis of low-level computational units, using causal intervention methods like activation patching to identify minimal circuits implementing specific behaviors. In contrast, philosophical treatments propose broader conceptualizations that include functional and higher-level explanations (Kästner and Crook 2024), drawing explicit connections to mechanistic explanation in the life sciences. Kästner and Crook argue that MI "enables us to meet desirable social desiderata including safety," suggesting MI is both necessary and sufficient for safety goals.

The stakes of this definitional question are substantial. If MI is both necessary and sufficient for safety, as some claim, this would justify prioritizing MI research over alternative safety approaches. If MI is neither necessary nor sufficient, resources might be better directed elsewhere. The conceptual confusion itself is an obstacle to rational resource allocation in AI safety research. Moreover, the definitional disagreement is not merely terminological but reflects different theoretical commitments with practical implications—what counts as successful MI under narrow definitions may be inadequate under broader ones, and vice versa.

This review examines definitions of MI across technical and philosophical literature, evaluates necessity and sufficiency claims for AI safety, and identifies gaps that require resolution. It draws on technical MI literature, AI safety research, philosophical accounts of mechanistic explanation, and XAI philosophy. The review progresses through four movements: establishing conceptual foundations and definitional tensions (Section 1), articulating and critically examining the case for MI's role in safety (Section 2), identifying research gaps (Section 3), and synthesizing implications for the research question (Conclusion).

## Section 1: The Concept of "Mechanistic" in Mechanistic Interpretability

### 1.1 Philosophical Accounts of Mechanistic Explanation

The "new mechanistic" philosophy provides theoretical grounding for what counts as genuinely mechanistic explanation. Machamer, Darden, and Craver (2000) define mechanisms as "entities and activities organized to produce regular changes from start to finish conditions," emphasizing productive continuity rather than covering-law derivation. This framework shifted philosophical focus from laws to mechanisms as the basic units of scientific explanation across the life sciences. Craver (2007) develops the influential "levels of mechanisms" framework, where mechanistic levels are defined by constitutive part-whole relationships rather than size or disciplinary boundaries. Crucially, Craver provides the mutual manipulability (MM) criterion for constitutive relevance: X's φ-ing is constitutively relevant to S's ψ-ing when interventions on X change ψ-ing and vice versa. This criterion offers testable conditions for mechanistic claims rather than mere correlation.

Glennan (1996, 2017) offers a complementary account emphasizing invariant, change-relating generalizations governing component interactions. His refined framework proposes that mechanisms provide foundation for understanding causation, explanation, and natural kinds across sciences, arguing mechanistic philosophy applies beyond biology to physics, chemistry, and potentially social sciences. Critical for evaluating MI claims is Bechtel and Richardson's (2010) analysis of decomposition and localization as heuristic strategies. They demonstrate these strategies succeed only under conditions of near-decomposability—when systems can be meaningfully divided into components with well-defined functions. Systems with distributed processing or nonlinear interactions resist simple decomposition. This raises immediate questions about whether neural networks satisfy the conditions required for mechanistic explanation in the philosophical sense.

Craver and Kaplan (2018) address completeness norms, arguing that mechanistic explanations need not include all details, only those constitutively relevant to the phenomenon being explained. Abstracting away from irrelevant details often improves explanation by highlighting what matters. This suggests different levels of MI detail might be appropriate for different explanatory purposes. However, determining which details are constitutively relevant in neural networks—versus merely correlated—may be more difficult than in biological systems where evolutionary function provides independent constraint.

The philosophical literature thus provides principled criteria for what counts as "mechanistic"—criteria that can be used to evaluate whether current MI techniques achieve genuine mechanistic understanding or merely provide fine-grained descriptions. Most MI research does not engage with these criteria explicitly, leaving open whether identified circuits and features satisfy mutual manipulability or other tests for constitutive relevance.

### 1.2 The Narrow View: MI as Circuit-Level Analysis

The dominant interpretation of MI in technical research focuses on reverse-engineering neural networks at the level of individual components: neurons, attention heads, and minimal circuits. Nanda et al. (2023) exemplify this approach by fully reverse-engineering the algorithm learned by small transformers for modular addition, identifying discrete Fourier transforms and trigonometric identities implemented by specific network components. This work demonstrates what counts as successful MI in practice: identifying specific algorithms implemented by network components through detailed analysis of activations, weights, and ablation studies.

Conmy et al. (2023) systematize this methodology through the Automated Circuit Discovery (ACDC) algorithm, which uses activation patching to identify minimal subgraphs responsible for specific behaviors. The ACDC approach successfully rediscovered all five manually-identified component types in a circuit in GPT-2 Small that computes the Greater-Than operation, selecting only 68 of 32,000 edges. This narrow selectivity illustrates the reductionist research strategy: understand small components, then scale up understanding. However, the need to pre-specify target behaviors and datasets limits applicability to novel or emergent capabilities where we don't know what to look for—a key safety concern.

Rai et al. (2024) organize the field around "fundamental objects of study"—neurons, attention heads, circuits, and features—with techniques like probing and ablation to analyze each. This task-centric taxonomy reveals the field's priorities and what problems are considered central to MI. Cunningham et al. (2023) address the superposition problem through sparse autoencoders (SAEs) that decompose activations into overcomplete sets of monosemantic features, treating polysemanticity (neurons activating in multiple semantically distinct contexts) as obstacle to interpretability requiring technical solution.

Geiger et al. (2023) provide theoretical foundations through causal abstraction, formalizing the relationship between high-level functional descriptions and low-level implementations. This framework defines when a high-level interpretable algorithm is faithfully implemented by low-level neural network operations, providing criteria for "graded faithfulness" that accommodate approximate relationships. The causal abstraction framework unifies various MI methods—activation patching, circuit analysis, SAEs—in common formal language, but maintains focus on causal intervention at the component level.

The narrow view's commitment to bottom-up analysis reflects explicit methodological choices about what level of organization matters for understanding. However, Zimmermann et al. (2023) provide troubling evidence that model scale does not improve mechanistic interpretability—larger models are not easier to interpret, and modern models appear less interpretable than decade-old architectures. This finding challenges assumptions about scalability and suggests MI may face fundamental barriers as models grow, directly threatening sufficiency claims about MI enabling safety at scale.

The narrow view's focus on low-level components may not capture the levels of organization that mechanistic explanation traditionally addresses. Whether circuits and features satisfy Craver's mutual manipulability criteria for constitutive relevance remains unexamined in most technical work.

### 1.3 The Broad View: MI as Functional Organization

Kästner and Crook (2024) represent the philosophical treatment that conceptualizes MI more broadly, drawing explicit connections to mechanistic explanation in the life sciences. They argue that XAI research should pursue mechanistic interpretability by applying "coordinated discovery strategies" from life sciences to uncover the "functional organization" of AI systems. Crucially, they claim that MI "enables us to meet desirable social desiderata including safety"—suggesting MI is both necessary and sufficient for safety goals. This broader view emphasizes functional understanding over mere component identification, aligning more closely with philosophical accounts of mechanistic explanation in neuroscience and biology.

This perspective resonates with philosophy of science work on explanation in AI. Sullivan (2020) argues that the primary obstacle to understanding from ML models is not opacity itself but "link uncertainty"—lack of evidence connecting model components to target phenomena. Understanding requires more than transparent descriptions; it requires establishing how identified structures relate to behaviors of interest. This "link uncertainty" account sets a high epistemic bar for interpretability methods: mechanistic interpretability must establish strong evidential links between identified circuits/features and actual network behavior, not merely provide transparent descriptions.

Duran (2021) proposes "scientific XAI" (sXAI) applying philosophy of science standards: explanations must be testable, provide causal information, and support counterfactual reasoning. Current XAI methods often fail these criteria, providing descriptions rather than genuine scientific explanations. Buchholz (2022) applies means-end epistemology, arguing that different epistemic goals require different explanatory methods. This suggests MI may be appropriate for some purposes (model debugging) but not others (end-user accountability), and that method selection must be goal-directed rather than uniform.

O'Hara (2020) emphasizes that technical sophistication does not guarantee explanatory adequacy—XAI methods may operate with implicit assumptions about explanation that do not align with genuine epistemic needs. Different stakeholders require different types of explanations, and technical XAI developers often fail to engage with philosophical standards for what constitutes adequate explanation.

The broad view better aligns with philosophical accounts of mechanistic explanation by emphasizing functional organization and higher-level explanation, but lacks concrete operationalization. How exactly do life-science discovery strategies transfer to neural networks? What specific methods count as pursuing functional organization versus component analysis? The gap between philosophical principle and technical practice remains substantial. Kästner and Crook invoke philosophy of science but do not engage with specific criteria from mechanistic explanation literature like mutual manipulability or constitutive relevance, leaving unclear how their broad vision would be implemented technically.

### 1.4 Bridging the Gap? Causal Abstraction and Levels

The causal abstraction framework (Geiger et al. 2023) offers a potential bridge between narrow and broad conceptions by formalizing relationships between different levels of description. It defines when a high-level interpretable algorithm is faithfully implemented by low-level neural network operations, unifying diverse MI methods (activation patching, causal mediation analysis, circuit analysis, SAEs) in common formal language. This theoretical framework provides vocabulary for discussing levels of mechanistic explanation and relationships between them, potentially connecting narrow circuit-focused work to broader functional understanding.

However, Zhong et al. (2023) demonstrate a fundamental challenge: neural networks trained on identical tasks can learn qualitatively different algorithmic implementations ("Clock" vs "Pizza" algorithms for modular addition), depending on initialization and hyperparameters. This algorithmic diversity reveals that multiple mechanistic implementations can produce the same behavior, complicating questions about what "the mechanism" of a network is. If different training runs discover different mechanisms for the same task, mechanistic understanding may require population-level analysis rather than individual network analysis, fundamentally altering the scope and feasibility of MI research.

From philosophy of science, Wimsatt's (1994) perspectival account of levels as "local maxima of regularity and predictability" offers resources for understanding why certain decompositions yield more stable interpretations than others. However, this perspectivalism potentially undermines claims about objective mechanistic structure in neural networks—if levels are merely epistemic convenience rather than ontological reality, identified mechanisms may reflect our analytical choices more than model properties. This echoes concerns raised by Miller et al. (2024) about circuit faithfulness metrics being highly sensitive to ablation methodology choices, suggesting that "circuits" may be artifacts of measurement rather than objective features.

The relationship between different levels of mechanistic analysis in neural networks—and whether neural networks support genuine mechanistic levels in Craver's sense—remains underexplored. This conceptual gap directly affects how we should interpret MI findings for safety purposes. If neural networks lack the stable part-whole organization required for mechanistic explanation, MI may provide useful heuristic descriptions without constituting genuine mechanistic understanding in the philosophical sense.

The literature reveals a spectrum from narrow circuit-focused MI to broad functional MI, with fundamental questions about whether neural networks satisfy conditions required for mechanistic explanation. These definitional issues are not merely terminological—they determine what counts as successful MI and therefore what would be needed to evaluate necessity/sufficiency claims for safety.

## Section 2: MI and AI Safety—Evaluating the Claims

### 2.1 The Case for MI as Essential to Safety

The strongest case for MI's essentiality draws on the "control problem" (Vold and Harris 2021): as AI systems become more capable, ensuring they pursue intended objectives becomes increasingly critical, and conventional behavioral evaluation may prove insufficient. MI proponents argue that understanding model internals is the only reliable way to detect whether models are genuinely aligned or merely appearing to be so—a distinction behavioral testing cannot make for sufficiently sophisticated systems capable of deceptive alignment.

Bereska and Gavves (2024) articulate specific safety benefits: MI could reveal hidden goals, detect deceptive alignment, identify capability-acquiring behaviors before deployment, and enable targeted modifications to problematic circuits. This goes beyond behavioral evaluation, which sophisticated systems can game. Ball et al. (2025) provide theoretical support through impossibility results: they prove that for some LLMs, adversarial prompts eliciting harmful behavior are computationally indistinguishable from benign prompts for any efficient filter. If external filtering is fundamentally limited, understanding model internals becomes necessary for safety—a striking theoretical justification for interpretability research.

Practical demonstrations show MI can identify specific mechanisms responsible for undesired behaviors. Redep et al. (2024) use MI to detect hallucinations in RAG models by identifying when Knowledge FFNs overemphasize parametric knowledge while Copying Heads fail to retain external knowledge—actionable insights enabling targeted interventions. This exemplifies MI's promise: mechanistic diagnosis of failure modes enabling surgical fixes rather than blunt behavioral modification.

Kästner and Crook's (2024) philosophical treatment makes the strongest necessity and sufficiency claims, arguing that mechanistic understanding through coordinated discovery strategies enables meeting safety desiderata. However, their broad functional interpretation of MI makes these claims difficult to evaluate empirically—what would falsify the sufficiency claim if "mechanistic" encompasses any method yielding functional understanding?

The theoretical case for MI rests on unproven assumptions about what MI can achieve at scale. Current demonstrations on toy tasks (modular addition, indirect object identification) do not establish that similar insights are possible for safety-critical behaviors in frontier models. The gap between proof-of-concept and practical deployment remains substantial.

### 2.2 Is MI Necessary? Alternative Safety Approaches

The necessity claim faces challenges from alternative safety approaches that do not rely on interpretability. Perrier (2025) argues that formal optimal control theory should be central to alignment, proposing an "Alignment Control Stack" that organizes interventions hierarchically across system layers—physical, computational, algorithmic, and socio-technical. On this view, interpretability is one tool among many, not uniquely necessary. The control-theoretic framework emphasizes formal rigor and interoperability between layers, suggesting current MI methods lack the generalization and formal foundations required for controlling frontier systems.

Dai et al. (2023) demonstrate Safe RLHF, which explicitly decouples helpfulness and harmlessness objectives through constrained optimization, achieving safety improvements without requiring mechanistic understanding. By training separate reward and cost models and applying Lagrangian optimization, Safe RLHF mitigates harmful responses while maintaining performance—demonstrating that alignment can be achieved through training-time intervention rather than post-hoc interpretation. This challenges strong necessity claims: if we can make models safer without understanding their internals, MI cannot be strictly necessary.

Lindstrom et al. (2025) provide sociotechnical critique showing that purely technical solutions—including interpretability—cannot solve alignment without addressing normative and political dimensions. They demonstrate fundamental limitations in the "HHH principle" (helpful, harmless, honest) and argue current RLHF approaches are fragile, imbalanced, and insufficient without broader institutional and process design. This suggests interpretability must be embedded within comprehensive sociotechnical frameworks rather than serving as standalone solution.

Zhou et al. (2023) propose "Predictable AI" as an alternative paradigm focused on anticipating key validity indicators. If we can reliably predict AI behavior without understanding mechanisms—through robust testing, validation, and performance bounds—predictability may substitute for interpretability in many safety contexts. The predictability framework emphasizes anticipation over explanation, potentially offering safety benefits without mechanistic understanding.

Baum (2025) develops a structured taxonomy distinguishing AI alignment along multiple dimensions: alignment aim (safety, ethicality, legality), scope (outcome vs execution alignment), and constituency (individual vs collective alignment). Different alignment configurations may require different tools—MI may be necessary for some alignment targets but not all. This pluralistic framework undermines blanket necessity claims by showing that "alignment" itself is not monolithic.

The literature reveals multiple viable safety approaches, challenging necessity claims. However, systematic comparison of what different approaches can and cannot achieve is lacking. Ball et al.'s (2025) impossibility results suggest external filtering has fundamental limits, potentially making some form of internal understanding necessary for detecting sophisticated deception—but whether current MI methods provide that understanding remains unclear.

### 2.3 Is MI Sufficient? Limitations and Dual-Use Risks

Even if MI is necessary, it is clearly not sufficient for safety. Sharkey et al. (2025) identify numerous open problems requiring solution before MI can deliver on safety promises: methods need conceptual and practical improvements for deeper insights; researchers must determine how to apply methods toward specific goals; and the field must address socio-technical challenges beyond pure technical capability. The identification of open problems by leading MI researchers reveals gaps between MI's promise and current capabilities.

Scalability challenges are severe. Zimmermann et al. (2023) find that model scale does not improve interpretability—modern models appear less interpretable than decade-old architectures, suggesting MI faces fundamental barriers as models grow. This directly threatens sufficiency: if MI doesn't scale to large models, it cannot be sufficient for safety of scaled systems. Lieberum et al. (2023) test circuit analysis on 70B-parameter Chinchilla, finding that techniques scale in principle but semantic understanding remains partial and distribution-dependent—successful component identification does not guarantee functional understanding.

Methodological fragility compounds these challenges. Miller et al. (2024) demonstrate that circuit faithfulness metrics are highly sensitive to ablation methodology choices—the same circuit receives very different scores depending on technical decisions. Zhang and Nanda (2023) show activation patching results are highly sensitive to hyperparameters, potentially leading to disparate conclusions about component importance. These findings suggest "circuit discovery" may identify measurement artifacts rather than objective model properties, threatening the validity of MI findings.

Most troublingly, Winninger et al. (2025) demonstrate that MI can be weaponized for adversarial attacks. By identifying "acceptance subspaces" through mechanistic analysis, they achieve 80-95% jailbreak success rates on state-of-the-art models, turning interpretability into attack vector. The same understanding needed for alignment verification enables more sophisticated attacks, creating fundamental dual-use tensions. If publishing MI research accelerates offense more than defense, the net safety impact may be negative.

Madsen et al. (2024) articulate the faithfulness problem: explanations may be convincing but not reflect actual model behavior. False but plausible explanations could create dangerous overconfidence in AI systems, making MI counterproductive for safety if not properly validated. The paradigmatic critique argues current interpretability approaches—both intrinsic and post-hoc—struggle with ensuring faithfulness, and propose fundamental rethinking toward methods that jointly produce predictions and explanations or optimize models to make explanations faithful.

Sufficiency claims are undermined by scalability limitations, methodological fragility, dual-use risks, and the faithfulness problem. What additional conditions would be required for MI to contribute reliably to safety? The literature suggests MI must be embedded within broader safety frameworks including governance, testing, and adversarial evaluation rather than serving as sufficient standalone solution.

### 2.4 Social-Epistemic Dimensions

Technical MI analyses face social-epistemic challenges that further complicate sufficiency claims. Huang et al. (2022) draw on feminist epistemology to argue that proper detection of algorithmic bias requires interpretive resources only available through diverse stakeholder involvement—purely technical transparency cannot identify all problematic patterns. Situated knowledge from affected communities may be essential for recognizing which features matter ethically, suggesting mechanistic interpretability of circuits alone is insufficient without social-epistemic integration.

Smart and Kasirzadeh (2024) introduce "socio-structural explanations" as a third type beyond mechanistic and non-mechanistic interpretations. ML models are embedded within and shaped by social structures; understanding outputs may require explaining how social structures contribute to model behavior through training data, deployment context, and institutional embedding. Mechanistic interpretability addresses only one layer of required explanation—the internal computational layer—while missing structural determinants of behavior.

Fazi (2020) raises deeper concerns about incommensurability: deep learning may involve abstractive operations not constrained by human modes of representation, creating genuine epistemic gaps that XAI attempts to "re-present" but may fail to capture. If algorithmic operations genuinely exceed human comprehensibility, MI provides useful approximations but not complete understanding—a fundamental limit on what transparency can achieve.

Jongepier and Keymolen (2022) reframe the question around agency: interpretability is ethically required when lack of understanding threatens autonomy, not because AI systems are intrinsically different from human decision-makers. This "symmetry thesis" suggests MI serves agency-protection rather than pure transparency, and that interpretability requirements vary with how algorithmic opacity affects stakeholder autonomy. The normative foundation is autonomy preservation, not transparency maximization.

Duede (2022) notes that opacity matters differently depending on AI's role in broader scientific methodology—what counts as adequate explanation depends on context and purpose. In discovery contexts with robust experimental validation, opacity may be tolerable; in deployment contexts without independent verification, transparency requirements increase. Boge and Mosig (2025) argue XAI must meet testability standards: genuine explanations support interventions and counterfactuals, not just descriptions. Many XAI methods may provide post-hoc rationalizations rather than testable explanations, failing to meet scientific standards.

The social-epistemic dimension reveals that MI's value for safety depends not just on technical capabilities but on how interpretability findings are produced, communicated, and used within institutional contexts. Purely technical MI divorced from stakeholder engagement, institutional accountability, and social-structural analysis likely proves insufficient for safety in deployment.

Systematic examination reveals MI is likely neither straightforwardly necessary nor sufficient for AI safety. Alternative safety approaches exist that don't rely on interpretability; MI faces severe scalability, faithfulness, and dual-use challenges; and social-epistemic dimensions add further complexity. However, this does not mean MI is irrelevant—rather, its role requires more precise specification conditional on definitions, safety goals, and complementary measures.

## Section 3: Research Gaps and Opportunities

### Gap 1: Conceptual Clarification of "Mechanistic" in MI

The literature operates with at least two distinct conceptualizations of MI—narrow circuit-focused versus broad functional—without explicit engagement about boundary-drawing criteria. Technical MI research (Nanda et al. 2023; Conmy et al. 2023) assumes shared understanding without philosophical justification, focusing on neurons, attention heads, and minimal circuits. Kästner and Crook (2024) invoke philosophy of science and mechanistic explanation but do not engage with specific criteria from the mechanistic explanation literature (Craver 2007; Glennan 2017) such as mutual manipulability or constitutive relevance.

Different definitions have different implications for evaluating safety claims. If "mechanistic" requires satisfying mutual manipulability criteria for constitutive relevance, most current MI techniques may not qualify as genuinely mechanistic—they may identify causally relevant components without establishing constitutive part-whole relationships. If broader functional interpretations count, the scope of what contributes to MI expands considerably, but operationalization becomes unclear. The definitional ambiguity prevents rigorous evaluation of whether MI achieves what it claims.

This gap matters because the epistemic standards for mechanistic explanation are well-developed in philosophy of science, offering principled criteria for what counts as mechanistic understanding versus mere description. Applying these criteria to neural networks would reveal whether current MI provides genuine mechanistic insight or heuristic approximation—a distinction crucial for safety applications requiring reliable understanding.

### Gap 2: Rigorous Analysis of Necessity/Sufficiency Claims

Claims about MI's role in safety are frequently asserted without careful philosophical analysis of the logical structure of necessity and sufficiency. Kästner and Crook (2024) claim MI "enables us to meet" safety desiderata, suggesting sufficiency without specifying what other conditions might be required. Safety literature assumes interpretability's importance without rigorous counterfactual analysis of whether safety could be achieved through alternative means or what specific safety goals MI uniquely addresses.

Ball et al. (2025) provide theoretical impossibility results suggesting some form of internal understanding may be necessary for detecting adversarial prompts, but don't establish that current MI methods provide that understanding. Perrier (2025), Dai et al. (2023), and Zhou et al. (2023) demonstrate alternative safety approaches, but systematic comparison of what each approach can and cannot achieve is lacking. Without such comparison, strong necessity claims cannot be evaluated.

Resource allocation in AI safety research depends on understanding MI's actual role. If MI is one useful tool among many, blanket prioritization is unwarranted. If it is uniquely necessary for specific safety goals, alternative approaches waste resources on those goals. The literature lacks the rigorous logical analysis needed to adjudicate these questions, mixing empirical claims about current capabilities with conceptual claims about what safety requires.

### Gap 3: Connection Between Philosophy of Mechanism and AI Interpretability

The rich literature on mechanistic explanation from philosophy of neuroscience and biology (Craver 2007; Bechtel and Richardson 2010; Glennan 2017) provides principled criteria for mechanistic explanation, but these are rarely applied to evaluate MI claims. Zhong et al. (2023) explicitly apply mechanistic framing to neural networks but do not engage with Craver's constitutive relevance criteria or Bechtel and Richardson's analysis of when decomposition strategies succeed versus fail.

Philosophy of mechanism offers conceptual tools for addressing whether neural networks can be said to have mechanisms in the relevant sense, whether current MI techniques identify constitutively relevant components versus mere correlations, and what levels of analysis are appropriate. The mutual manipulability criterion provides testable conditions for constitutive relevance; near-decomposability analysis reveals when systems resist mechanistic decomposition; and completeness norms clarify what detail is explanatorily relevant versus distracting.

Applying these philosophical frameworks to neural network interpretability could reveal fundamental constraints on what MI can achieve. If neural networks lack near-decomposable organization due to distributed representations and nonlinear interactions, mechanistic decomposition may be intractable in principle. If identified circuits fail mutual manipulability tests, they may not be constitutively relevant to network behavior. These philosophical insights could save significant research effort by clarifying when mechanistic approaches are appropriate versus when alternative explanatory frameworks are needed.

### Gap 4: Systematic Comparison of MI with Alternative Safety Approaches

The AI safety literature contains multiple distinct approaches—RLHF-based alignment (Dai et al. 2023), formal control theory (Perrier 2025), predictability frameworks (Zhou et al. 2023), governance-based approaches (Herrera and Calderon 2025), verification and validation (Habli et al. 2025)—but systematic comparison of what different approaches can and cannot achieve is lacking. Claims about MI's unique importance are rarely evaluated against specific alternatives with explicit analysis of comparative advantages and limitations.

Different safety approaches may excel at different aspects: RLHF addresses training-time alignment but may not detect post-deployment deception; formal verification provides mathematical guarantees but requires tractable specifications; MI promises mechanistic understanding but faces scalability limitations. Without systematic comparison, we cannot determine optimal resource allocation or identify which approaches are complementary versus substitutable.

Rational resource allocation requires understanding the comparative strengths and weaknesses of different safety approaches for different safety goals. MI may be particularly valuable for detecting deceptive alignment but less important for robustness against distributional shift. Governance may be essential for sociotechnical safety but insufficient for technical alignment. The lack of systematic comparison prevents principled prioritization of research directions.

### Synthesis: How Gaps Collectively Motivate Research

The four gaps are interconnected. Conceptual clarification (Gap 1) is prerequisite for rigorous analysis of necessity/sufficiency (Gap 2), which requires connection to philosophy of mechanism (Gap 3) and comparison with alternatives (Gap 4). Current literature cannot answer "Is MI necessary or sufficient for AI safety?" because it lacks:

1. Clear definition of what "mechanistic" means in this context
2. Rigorous logical analysis of necessity/sufficiency claims
3. Philosophical criteria for evaluating mechanistic understanding
4. Systematic comparison with alternative approaches

This research project provides an integrated analysis addressing all four gaps, offering conceptual clarity that enables more precise evaluation of MI's role in AI safety. By applying philosophy of mechanism to neural network interpretability, rigorously analyzing necessity and sufficiency claims under different definitions, and systematically comparing MI with alternative safety approaches, the project advances both theoretical understanding and practical prioritization of safety research.

## Conclusion

This review reveals fundamental disagreement about what "mechanistic" means in mechanistic interpretability, with implications for evaluating safety claims. Technical MI research focuses on circuit-level analysis of neurons, attention heads, and minimal subgraphs (Nanda et al. 2023; Conmy et al. 2023), embodying a narrow reductionist interpretation. Philosophical treatments propose broader functional interpretations drawing on mechanistic explanation from life sciences (Kästner and Crook 2024). These different definitions reflect distinct theoretical commitments with practical consequences—what counts as successful MI varies substantially across conceptualizations.

Regarding necessity claims, alternative safety approaches exist that challenge strong necessity arguments. Safe RLHF (Dai et al. 2023) demonstrates alignment improvements without mechanistic understanding; formal control theory (Perrier 2025) provides hierarchical safety frameworks where interpretability is one layer among many; predictability approaches (Zhou et al. 2023) suggest behavioral reliability may substitute for mechanistic transparency in some contexts. However, Ball et al.'s (2025) impossibility results suggest external filtering has fundamental limits, potentially making some form of internal understanding necessary for detecting sophisticated adversarial prompts or deceptive alignment. The necessity question thus depends critically on which safety goals matter and which definitions of MI we adopt.

Regarding sufficiency claims, MI faces severe limitations that clearly preclude sufficiency on its own. Zimmermann et al. (2023) demonstrate that interpretability does not improve with scale—modern models appear less interpretable than older architectures—directly threatening sufficiency for frontier systems. Miller et al. (2024) and Zhang and Nanda (2023) reveal methodological fragility: circuit faithfulness metrics and activation patching results are highly sensitive to technical choices, suggesting discoveries may reflect measurement artifacts. Winninger et al. (2025) demonstrate dual-use risks: MI can be weaponized for adversarial attacks, achieving 80-95% jailbreak success through mechanistic understanding of safety mechanisms. Madsen et al. (2024) articulate the faithfulness problem: explanations may be convincing but not reflect actual model behavior, creating dangerous overconfidence. Social-epistemic dimensions (Huang et al. 2022; Smart and Kasirzadeh 2024) add further complexity, revealing that technical transparency alone cannot identify all safety-relevant patterns without diverse stakeholder involvement and socio-structural analysis.

The emerging picture is conditional and context-dependent: MI's contribution to safety depends on which safety goals, which definitions, which model scales, and which complementary measures. Rather than being universally necessary or sufficient, MI likely plays specific roles for specific purposes. For detecting deceptive alignment or hidden goals, mechanistic understanding may be uniquely valuable—but only if it scales and remains faithful at frontier model sizes. For ensuring robustness or mitigating bias, MI may complement but not replace other approaches. For sociotechnical safety, MI must be embedded within governance frameworks rather than serving standalone.

This research project addresses identified gaps by providing: (1) precise taxonomy of MI conceptualizations and their relationship to philosophical accounts of mechanism, applying Craver's constitutive relevance criteria and Bechtel and Richardson's decomposition analysis to neural networks; (2) rigorous analysis of necessity/sufficiency claims under different definitions, using formal logical structure and counterfactual reasoning; (3) framework for evaluating MI's comparative role alongside alternative safety approaches through systematic comparison of capabilities and limitations; and (4) recommendations for conceptual clarity in future research and policy, distinguishing claims that current MI supports from aspirational goals requiring further development.

The literature review establishes that neither blanket endorsement nor blanket rejection of MI for safety is warranted. Instead, nuanced evaluation conditional on definitions, goals, and contexts is required—precisely the analysis this research project provides. By bridging technical MI research, philosophical accounts of mechanistic explanation, AI safety literature, and XAI philosophy, the project offers integrated understanding currently missing from fragmented disciplinary conversations.

---

**Word Count**: 3,987 words

## References

Adams, E. Charles, Li Bai, Minji Lee, Yiyang Yu, and Mohammed AlQuraishi. 2025. "From Mechanistic Interpretability to Mechanistic Biology: Training, Evaluating, and Interpreting Sparse Autoencoders on Protein Language Models." *bioRxiv*. https://doi.org/10.1101/2025.02.06.636901.

Baker, Stephanie B., and Wei Xiang. 2023. "Explainable AI is Responsible AI: How Explainability Creates Trustworthy and Socially Responsible Artificial Intelligence." *ArXiv* abs/2312.01555. https://doi.org/10.48550/arXiv.2312.01555.

Balestra, Chiara, Bin Li, and Emmanuel Müller. 2023. "On the Consistency and Robustness of Saliency Explanations for Time Series Classification." *ArXiv* abs/2309.01457. https://doi.org/10.48550/arXiv.2309.01457.

Ball, Sarah, Greg Gluch, Shafi Goldwasser, Frauke Kreuter, Omer Reingold, and Guy Rothblum. 2025. "On the Impossibility of Separating Intelligence from Judgment: The Computational Intractability of Filtering for AI Alignment." *ArXiv* abs/2507.07341. https://doi.org/10.48550/arXiv.2507.07341.

Baron, Sam. 2025. "Trust, Explainability and AI." *Philosophy & Technology* 38. https://doi.org/10.1007/s13347-024-00837-6.

Baum, Kevin. 2025. "Disentangling AI Alignment: A Structured Taxonomy Beyond Safety and Ethics." *Lecture Notes in Computer Science*. https://doi.org/10.1007/978-3-032-01377-4_8.

Bechtel, William, and Robert C. Richardson. 2010. *Discovering Complexity: Decomposition and Localization as Strategies in Scientific Research*. 2nd ed. Cambridge, MA: MIT Press. https://doi.org/10.7551/mitpress/8328.001.0001.

Bereska, Leonard, and Efstratios Gavves. 2024. "Mechanistic Interpretability for AI Safety—A Review." *Transactions on Machine Learning Research*. https://doi.org/10.48550/arXiv.2404.14082.

Boge, Florian J., and Axel Mosig. 2025. "Put It to the Test: Getting Serious About Explanation in Explainable Artificial Intelligence." *Minds and Machines* 35 (1). https://doi.org/10.1007/s11023-025-09724-1.

Buchholz, Oliver. 2022. "A Means-End Account of Explainable Artificial Intelligence." *Synthese* 202 (1): 1–23. https://doi.org/10.1007/s11229-023-04260-w.

Camilleri, Mark Anthony. 2023. "Artificial Intelligence Governance: Ethical Considerations and Implications for Social Responsibility." *Expert Systems* 41 (2): e13406. https://doi.org/10.1111/exsy.13406.

Cheong, Ben Chester. 2024. "Transparency and Accountability in AI Systems: Safeguarding Wellbeing in the Age of Algorithmic Decision-Making." *Frontiers in Human Dynamics* 6. https://doi.org/10.3389/fhumd.2024.1421273.

Conmy, Arthur, Augustine N. Mavor-Parker, Aengus Lynch, Stefan Heimersheim, and Adrià Garriga-Alonso. 2023. "Towards Automated Circuit Discovery for Mechanistic Interpretability." In *Neural Information Processing Systems*. https://doi.org/10.48550/arXiv.2304.14997.

Craver, Carl F. 2007. *Explaining the Brain: Mechanisms and the Mosaic Unity of Neuroscience*. Oxford: Oxford University Press. https://doi.org/10.1093/acprof:oso/9780199299317.001.0001.

Craver, Carl F. 2025. "Defending Levels by Trading Waves for Trees." *Synthese* 205. https://doi.org/10.1007/s11229-025-04967-y.

Craver, Carl F., and Lindley Darden. 2013. *In Search of Mechanisms: Discoveries across the Life Sciences*. Chicago: University of Chicago Press. https://doi.org/10.5860/choice.51-5580.

Craver, Carl F., and David M. Kaplan. 2018. "Are More Details Better? On the Norms of Completeness for Mechanistic Explanations." *The British Journal for the Philosophy of Science* 71 (1): 287–319. https://doi.org/10.1093/bjps/axy015.

Cunningham, Hoagy, Aidan Ewart, Logan Riggs Smith, Robert Huben, and Lee Sharkey. 2023. "Sparse Autoencoders Find Highly Interpretable Features in Language Models." *ArXiv* abs/2309.08600. https://doi.org/10.48550/arXiv.2309.08600.

Dai, Josef, Xuehai Pan, Ruiyang Sun, Jiaming Ji, Xinbo Xu, Mickel Liu, Yizhou Wang, and Yaodong Yang. 2023. "Safe RLHF: Safe Reinforcement Learning from Human Feedback." In *International Conference on Learning Representations*. https://doi.org/10.48550/arXiv.2310.12773.

Duede, Eamon. 2022. "Deep Learning Opacity in Scientific Discovery." *Philosophy of Science* 90 (5): 1089–1099. https://doi.org/10.1017/psa.2023.8.

Duran, Juan Manuel. 2021. "Dissecting Scientific Explanation in AI (sXAI): A Case for Medicine and Healthcare." *Artificial Intelligence* 297: 103498. https://doi.org/10.1016/j.artint.2021.103498.

Fazi, M. Beatrice. 2020. "Beyond Human: Deep Learning, Explainability and Representation." *Theory, Culture & Society* 38 (7-8): 55–77. https://doi.org/10.1177/0263276420966386.

Ferrara, Emilio. 2023. "Fairness and Bias in Artificial Intelligence: A Brief Survey of Sources, Impacts, and Mitigation Strategies." *Sci* 6 (1): 3. https://doi.org/10.3390/sci6010003.

Gabriel, Iason, et al. 2024. "The Ethics of Advanced AI Assistants." *ArXiv* abs/2404.16244. https://doi.org/10.48550/arXiv.2404.16244.

García-Carrasco, Jorge, Alejandro Maté, and Juan Trujillo. 2024. "How does GPT-2 Predict Acronyms? Extracting and Understanding a Circuit via Mechanistic Interpretability." *ArXiv* abs/2405.04156. https://doi.org/10.48550/arXiv.2405.04156.

Geiger, Atticus, Duligur Ibeling, Amir Zur, Maheep Chaudhary, Sonakshi Chauhan, Jing Huang, Aryaman Arora, Zhengxuan Wu, Noah D. Goodman, Christopher Potts, and Thomas F. Icard. 2023. "Causal Abstraction: A Theoretical Foundation for Mechanistic Interpretability." *ArXiv* abs/2301.04709. https://doi.org/10.48550/arXiv.2301.04709.

Glennan, Stuart. 1996. "Mechanisms and the Nature of Causation." *Erkenntnis* 44 (1): 49–71. https://doi.org/10.1007/BF00172853.

Glennan, Stuart. 2017. *The New Mechanical Philosophy*. Oxford: Oxford University Press. https://doi.org/10.1093/oso/9780198779711.001.0001.

Glennan, Stuart, and Phyllis Illari, eds. 2017. *The Routledge Handbook of Mechanisms and Mechanical Philosophy*. London: Routledge. https://doi.org/10.4324/9781315731544.

Golovanevsky, Michal, William Rudman, Vedant Palit, Ritambhara Singh, and Carsten Eickhoff. 2024. "What Do VLMs NOTICE? A Mechanistic Interpretability Pipeline for Noise-free Text-Image Corruption and Evaluation." In *North American Chapter of the Association for Computational Linguistics*. https://doi.org/10.48550/arXiv.2406.16320.

Habli, Ibrahim, Richard Hawkins, Colin Paterson, Philippa Ryan, Yan Jia, M. Sujan, and J. McDermid. 2025. "The BIG Argument for AI Safety Cases." *ArXiv* abs/2503.11705. https://doi.org/10.48550/arXiv.2503.11705.

He, Zhengfu, Xuyang Ge, Qiong Tang, Tianxiang Sun, Qinyuan Cheng, and Xipeng Qiu. 2024. "Dictionary Learning Improves Patch-Free Circuit Discovery in Mechanistic Interpretability: A Case Study on Othello-GPT." *ArXiv* abs/2402.12201. https://doi.org/10.48550/arXiv.2402.12201.

Hedström, Anna, Leander Weber, Sebastian Lapuschkin, and Marina M.-C. Höhne. 2024. "A Fresh Look at Sanity Checks for Saliency Maps." *Proceedings of xAI Workshop*, 403–420. https://doi.org/10.48550/arXiv.2405.02383.

Heimersheim, Stefan, and Neel Nanda. 2024. "How to use and interpret activation patching." *ArXiv* abs/2404.15255. https://doi.org/10.48550/arXiv.2404.15255.

Herrera, Francisco, and Reyes Calderón. 2025. "Opacity as a Feature, Not a Flaw: The LoBOX Governance Ethic for Role-Sensitive Explainability and Institutional Trust in AI." *ArXiv* abs/2505.20304. https://doi.org/10.48550/arXiv.2505.20304.

Hoes, Emma, and Fabrizio Gilardi. 2025. "Existential Risk Narratives About AI Do Not Distract from Its Immediate Harms." *Proceedings of the National Academy of Sciences* 122. https://doi.org/10.1073/pnas.2419055122.

Huang, Linus Ta-Lun, Hsiang-Yun Chen, Ying-Tung Lin, Tsung-Ren Huang, and Tzu-Wei Hung. 2022. "Ameliorating Algorithmic Bias, or Why Explainable AI Needs Feminist Philosophy." *Feminist Philosophy Quarterly* 8 (3-4). https://doi.org/10.5206/fpq/2022.3/4.14347.

Huang, Xiaowei, et al. 2024. "A Survey of Safety and Trustworthiness of Large Language Models through the Lens of Verification and Validation." *Artificial Intelligence Review*. https://doi.org/10.1007/s10462-024-10824-0.

Ji, Jiaming, et al. 2023. "AI Alignment: A Comprehensive Survey." *ArXiv* abs/2310.19852. https://doi.org/10.48550/arXiv.2310.19852.

Jin, Haibo, Leyang Hu, Xinuo Li, Peiyan Zhang, Chonghan Chen, Jun Zhuang, and Haohan Wang. 2024. "JailbreakZoo: Survey, Landscapes, and Horizons in Jailbreaking Large Language and Vision-Language Models." *ArXiv* abs/2407.01599. https://doi.org/10.48550/arXiv.2407.01599.

Jongepier, Fleur, and Esther Keymolen. 2022. "Explanation and Agency: Exploring the Normative-Epistemic Landscape of the 'Right to Explanation'." *Ethics and Information Technology* 24 (4). https://doi.org/10.1007/s10676-022-09654-x.

Kaas, Marten H. L., and I. Habli. 2024. "Assuring AI Safety: Fallible Knowledge and the Gricean Maxims." *AI and Ethics* 5: 1467–1480. https://doi.org/10.1007/s43681-024-00490-x.

Kästner, Lena, and Barnaby Crook. 2024. "Explaining AI through mechanistic interpretability." *European Journal for Philosophy of Science* 14 (4): 52. https://doi.org/10.1007/s13194-024-00614-4.

Kiourti, Panagiota, Anu Singh, Preeti Duraipandian, Weichao Zhou, and Wenchao Li. 2025. "Rethinking Robustness: A New Approach to Evaluating Feature Attribution Methods." *ArXiv* abs/2512.06665.

Koenen, Niklas, and Marvin N. Wright. 2024. "Toward Understanding the Disagreement Problem in Neural Network Feature Attribution." *ArXiv* abs/2404.11330. https://doi.org/10.48550/arXiv.2404.11330.

Krickel, Beate. 2017. "Saving the Mutual Manipulability Account of Constitutive Relevance." *Studies in History and Philosophy of Science Part A* 68: 58–67. https://doi.org/10.1016/j.shpsa.2017.11.003.

Krickel, Beate. 2018. *The Mechanical World: The Metaphysical Commitments of the New Mechanistic Approach*. Cham: Springer. https://doi.org/10.1007/978-3-319-93345-3.

Lieberum, Tom, Matthew Rahtz, János Kramár, Geoffrey Irving, Rohin Shah, and Vladimir Mikulik. 2023. "Does Circuit Analysis Interpretability Scale? Evidence from Multiple Choice Capabilities in Chinchilla." *ArXiv* abs/2307.09458. https://doi.org/10.48550/arXiv.2307.09458.

Lieberum, Tom, Senthooran Rajamanoharan, Arthur Conmy, Lewis Smith, Nicolas Sonnerat, Vikrant Varma, János Kramár, Anca Dragan, Rohin Shah, and Neel Nanda. 2024. "Gemma Scope: Open Sparse Autoencoders Everywhere All At Once on Gemma 2." *ArXiv* abs/2408.05147. https://doi.org/10.48550/arXiv.2408.05147.

Lindström, Adam Dahlgren, Leila Methnani, Lea Krause, Petter Ericson, Íñigo Martínez de Rituerto de Troya, Dimitri Coelho Mollo, and Roel Dobbe. 2025. "Helpful, Harmless, Honest? Sociotechnical Limits of AI Alignment and Safety through Reinforcement Learning from Human Feedback." *Ethics and Information Technology*. https://doi.org/10.1007/s10676-025-09837-2.

Liu, Ziming, Eric Gan, and Max Tegmark. 2023. "Seeing Is Believing: Brain-Inspired Modular Training for Mechanistic Interpretability." *Entropy* 26 (1): 41. https://doi.org/10.3390/e26010041.

Machamer, Peter, Lindley Darden, and Carl F. Craver. 2000. "Thinking about Mechanisms." *Philosophy of Science* 67 (1): 1–25. https://doi.org/10.1086/392759.

Madsen, Andreas, Himabindu Lakkaraju, Siva Reddy, and Sarath Chandar. 2024. "Interpretability Needs a New Paradigm." *ArXiv* abs/2405.05386. https://doi.org/10.48550/arXiv.2405.05386.

Men, Tianyi, Pengfei Cao, Zhuoran Jin, Yubo Chen, Kang Liu, and Jun Zhao. 2024. "Unlocking the Future: Exploring Look-Ahead Planning Mechanistic Interpretability in Large Language Models." *ArXiv* abs/2406.16033. https://doi.org/10.48550/arXiv.2406.16033.

Meskhidze, Helen. 2021. "Can Machine Learning Provide Understanding? How Cosmologists Use Machine Learning to Understand Observations of the Universe." *Erkenntnis* 88 (5): 1895–1909. https://doi.org/10.1007/s10670-021-00434-5.

Michaud, Eric J., et al. 2024. "Opening the AI black box: program synthesis via mechanistic interpretability." *ArXiv* abs/2402.05110. https://doi.org/10.48550/arXiv.2402.05110.

Miller, Joseph, Bilal Chughtai, and William Saunders. 2024. "Transformer Circuit Faithfulness Metrics are not Robust." *ArXiv* abs/2407.08734. https://doi.org/10.48550/arXiv.2407.08734.

Müller, Romy. 2024. "How Explainable AI Affects Human Performance: A Systematic Review of the Behavioural Consequences of Saliency Maps." *International Journal of Human-Computer Interaction* 41: 2020–2051. https://doi.org/10.1080/10447318.2024.2381929.

Nanda, Neel, Lawrence Chan, Tom Lieberum, Jess Smith, and Jacob Steinhardt. 2023. "Progress measures for grokking via mechanistic interpretability." In *International Conference on Learning Representations*. https://doi.org/10.48550/arXiv.2301.05217.

O'Hara, Kieron. 2020. "Explainable AI and the Philosophy and Practice of Explanation." *Computer Law and Security Review* 39: 105474. https://doi.org/10.1016/j.clsr.2020.105474.

Páez, Andrés. 2024. "Understanding with Toy Surrogate Models in Machine Learning." *Minds and Machines* 34 (4). https://doi.org/10.1007/s11023-024-09700-1.

Palit, Vedant, Rohan Pandey, Aryaman Arora, and Paul Pu Liang. 2023. "Towards Vision-Language Mechanistic Interpretability: A Causal Tracing Tool for BLIP." In *International Conference on Computer Vision Workshops*. https://doi.org/10.1109/iccvw60793.2023.00307.

Pan, Xudong, Jiarun Dai, Yihe Fan, Minyuan Luo, Changyi Li, and Min Yang. 2025. "Large Language Model-Powered AI Systems Achieve Self-Replication with No Human Intervention." *ArXiv* abs/2503.17378. https://doi.org/10.48550/arXiv.2503.17378.

Pearce, Michael T., Thomas Dooms, Alice Rigg, José Oramas, and Lee Sharkey. 2024. "Bilinear MLPs enable weight-based mechanistic interpretability." *ArXiv* abs/2410.08417. https://doi.org/10.48550/arXiv.2410.08417.

Perrier, Elija. 2025. "Out of Control—Why Alignment Needs Formal Control Theory (and an Alignment Control Stack)." *ArXiv* abs/2506.17846. https://doi.org/10.48550/arXiv.2506.17846.

Pinhasov, Ben, Raz Lapid, Rony Ohayon, Moshe Sipper, and Yehudit Aperstein. 2024. "XAI-Based Detection of Adversarial Attacks on Deepfake Detectors." *Transactions on Machine Learning Research* 2024. https://doi.org/10.48550/arXiv.2403.02955.

Rai, Daking, Yilun Zhou, Shi Feng, Abulhair Saparov, and Ziyu Yao. 2024. "A Practical Review of Mechanistic Interpretability for Transformer-Based Language Models." *ArXiv* abs/2407.02646. https://doi.org/10.48550/arXiv.2407.02646.

Rajamanoharan, Senthooran, Tom Lieberum, Nicolas Sonnerat, Arthur Conmy, Vikrant Varma, János Kramár, and Neel Nanda. 2024. "Jumping Ahead: Improving Reconstruction Fidelity with JumpReLU Sparse Autoencoders." *ArXiv* abs/2407.14435. https://doi.org/10.48550/arXiv.2407.14435.

Sanderson, Conrad, David M. Douglas, and Qinghua Lu. 2023. "Implementing Responsible AI: Tensions and Trade-Offs Between Ethics Aspects." *2023 International Joint Conference on Neural Networks (IJCNN)*, 1–7. https://doi.org/10.1109/IJCNN54540.2023.10191274.

Sharkey, Lee, et al. 2025. "Open Problems in Mechanistic Interpretability." *ArXiv* abs/2501.16496. https://doi.org/10.48550/arXiv.2501.16496.

Smart, Andrew, and Atoosa Kasirzadeh. 2024. "Beyond Model Interpretability: Socio-Structural Explanations in Machine Learning." *AI & Society* 40 (4): 2045–2053. https://doi.org/10.1007/s00146-024-02056-1.

Sullivan, Emily. 2020. "Understanding from Machine Learning Models." *The British Journal for the Philosophy of Science* 73 (1): 109–133. https://doi.org/10.1093/bjps/axz035.

Sun, ZhongXiang, Xiaoxue Zang, Kai Zheng, Yang Song, Jun Xu, Xiao Zhang, Weijie Yu, and Han Li. 2024. "ReDeEP: Detecting Hallucination in Retrieval-Augmented Generation via Mechanistic Interpretability." *ArXiv* abs/2410.11414. https://doi.org/10.48550/arXiv.2410.11414.

Syed, Aaquib, Can Rager, and Arthur Conmy. 2023. "Attribution Patching Outperforms Automated Circuit Discovery." In *BlackboxNLP Workshop on Analyzing and Interpreting Neural Networks for NLP*. https://doi.org/10.48550/arXiv.2310.10348.

Vainio-Pekka, Heidi, Mamia Agbese, Marianna Jantunen, Ville Vakkuri, Tommi Mikkonen, Rebekah Rousi, and Pekka Abrahamsson. 2023. "The Role of Explainable AI in the Research Field of AI Ethics." *ACM Transactions on Interactive Intelligent Systems* 13 (2): 1–39. https://doi.org/10.1145/3599974.

Vold, Karina, and Daniel R. Harris. 2021. "How Does Artificial Intelligence Pose an Existential Risk?" In *The Oxford Handbook of Digital Ethics*. https://doi.org/10.1093/oxfordhb/9780198857815.013.36.

Wimsatt, William C. 1976. "Reductionism, Levels of Organization, and the Mind-Body Problem." In *Consciousness and the Brain*, 205–267. Springer. https://doi.org/10.1007/978-1-4684-2196-5_9.

Wimsatt, William C. 1994. "The Ontology of Complex Systems: Levels of Organization, Perspectives, and Causal Thickets." *Canadian Journal of Philosophy* 20: 207–274. https://doi.org/10.1080/00455091.1994.10717400.

Winninger, Thomas, Bilel Addad, and Katarzyna Kapusta. 2025. "Using Mechanistic Interpretability to Craft Adversarial Attacks against Large Language Models." *ArXiv* abs/2503.06269. https://doi.org/10.48550/arXiv.2503.06269.

Zhang, Fred, and Neel Nanda. 2023. "Towards Best Practices of Activation Patching in Language Models: Metrics and Methods." *ArXiv* abs/2309.16042. https://doi.org/10.48550/arXiv.2309.16042.

Zheng, Yue, Chip-Hong Chang, Shih-Hsu Huang, Pin-Yu Chen, and Stjepan Picek. 2024. "An Overview of Trustworthy AI: Advances in IP Protection, Privacy-Preserving Federated Learning, Security Verification, and GAI Safety Alignment." *IEEE Journal on Emerging and Selected Topics in Circuits and Systems*. https://doi.org/10.1109/jetcas.2024.3477348.

Zhong, Ziqian, Ziming Liu, Max Tegmark, and Jacob Andreas. 2023. "The Clock and the Pizza: Two Stories in Mechanistic Explanation of Neural Networks." *ArXiv* abs/2306.17844. https://doi.org/10.48550/arXiv.2306.17844.

Zhou, Lexin, et al. 2023. "Predictable Artificial Intelligence." *ArXiv* abs/2310.06167. https://doi.org/10.48550/arXiv.2310.06167.

Zimmermann, Roland, Thomas Klein, and Wieland Brendel. 2023. "Scale Alone Does not Improve Mechanistic Interpretability in Vision Models." *ArXiv* abs/2307.05471. https://doi.org/10.48550/arXiv.2307.05471.
