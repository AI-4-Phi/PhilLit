# Literature Review Outline

**Research Project**: Belief Revision in Large Language Models
**Date**: 2026-01-15
**Total Literature Base**: 123 papers across 7 domains

---

## Introduction

**Purpose**: Frame the interdisciplinary problem of LLM belief revision and establish why classical frameworks require new analysis.

**Content**:
- Open with Betley et al. 2025's observation that "applying a simple fixed set of inference rules to a dataset D is not sufficient to predict how a rational agent will change its beliefs and behaviors given D"
- Establish the central puzzle: LLMs exhibit sophisticated linguistic competence yet revise beliefs through mechanisms fundamentally different from classical rational agency models
- Frame the interdisciplinary challenge: philosophy provides normative frameworks (AGM, Bayesian epistemology); ML provides empirical findings (weird generalization, reasoning failures); neither alone suffices
- Scope: Review covers (1) classical belief revision theory, (2) empirical LLM reasoning and fine-tuning behavior, (3) normative evaluation frameworks, and (4) hybrid approaches
- Preview central tension: Are LLM belief dynamics amenable to normative rational evaluation, or do they require fundamentally new frameworks?

**Key Papers**:
- Betley et al. 2025 (weird generalization)
- Alchourron et al. 1985 (AGM foundational)
- Wei et al. 2022 (chain-of-thought)
- Mitchell & Krakauer 2023 (LLM understanding debate)

**Word Target**: 400-500 words

---

## Section 1: Rationality Frameworks for Belief Revision

**Section Purpose**: Establish the normative landscape against which LLM belief revision must be evaluated, revealing why classical theories face challenges when applied to neural systems.

**Main Claims**:
1. Classical belief revision theory (AGM and extensions) provides powerful formal tools but presupposes idealized rational agents incompatible with LLM architecture
2. Non-monotonic reasoning and argumentation frameworks offer resources for defeasible reasoning but lack established neural implementations
3. Epistemic rationality norms face the normative-descriptive gap when applied to systems whose "beliefs" may be metaphysically distinct from human beliefs

### Subsection 1.1: AGM Theory and Its Limitations for Neural Systems

**Papers**: Alchourron et al. 1985, Gardenfors & Makinson 1988, Darwiche & Pearl 1997, Spohn 2012, Huber 2013, Aravanis et al. 2020

**Content**:
- Present AGM postulates: expansion, contraction, revision; minimal mutilation principle
- Explain epistemic entrenchment as mechanism for prioritizing beliefs (Gardenfors & Makinson 1988)
- Discuss iterated revision (Darwiche-Pearl postulates) and why single-step revision is insufficient for sequential LLM interactions
- Present Aravanis et al. 2020's impossibility result: iteration and relevance-sensitivity are fundamentally incompatible
- Critical analysis: AGM assumes logically closed belief sets, explicit belief representation, and unbounded computational resources---none hold for LLMs
- Key tension: Ranking theory (Spohn 2012) offers graded beliefs potentially analogous to neural activations, but translation between numerical degrees of disbelief and transformer representations remains unexplored

**Gap Connection**: The AGM framework lacks operationalization for distributed neural representations; no existing work maps AGM postulates to neural belief revision.

### Subsection 1.2: Non-Monotonic Reasoning and Defeasible Inference

**Papers**: Reiter 1980, Dung 1995, Kraus et al. 1990, Lehmann & Magidor 1992, Modgil & Prakken 2014, Kirkpatrick & Sterken 2025

**Content**:
- Present default logic as formalization of everyday reasoning with exceptions (Reiter 1980)
- Discuss abstract argumentation (Dung 1995) as unifying framework for defeasible inference
- Present KLM rationality postulates as normative constraints any non-monotonic reasoner should satisfy
- Cover structured argumentation (ASPIC+) as bridge between abstract frameworks and practical reasoning
- Critical empirical finding: Kirkpatrick & Sterken 2025 show LLMs fail basic default reasoning, often conflating defeasible with deductive inference; chain-of-thought prompting actually degrades default reasoning performance
- This suggests non-monotonic reasoning mechanisms do not naturally emerge from transformer architectures

**Gap Connection**: No systematic evaluation of whether LLM belief revision approximates any formal non-monotonic semantics; no neural implementation of argumentation-based revision.

### Subsection 1.3: Epistemic Norms and Their Application to Artificial Systems

**Papers**: Pettigrew 2016, Titelbaum 2022, Tomat 2024, Schwarz 2025, Thorstad 2022, Vassend 2023

**Content**:
- Present Bayesian norms as formal standards for credence revision (Titelbaum 2022)
- Discuss epistemic utility theory's accuracy-first justification of Bayesian norms (Pettigrew 2016)
- Introduce bounded rationality: ideal norms may be inappropriate for cognitively limited agents (Tomat 2024)
- Non-ideal rationality (Schwarz 2025): when information loss is unavoidable, different norms may apply---directly relevant to LLMs with context window limitations
- Alternative to Bayesian conditionalization: Vassend 2023 shows other updating strategies can be more rational in realistic environments
- Key philosophical question: Should LLMs satisfy ideal Bayesian coherence, or should we develop bounded rationality norms tailored to transformer architecture?

**Gap Connection**: No existing framework specifies which epistemic norms apply to LLMs given their computational architecture; the normative-descriptive gap remains unbridged.

**Section Summary**: Classical frameworks provide rich formal resources but assume idealized agents. Three challenges emerge: (1) AGM requires explicit belief representation LLMs lack, (2) non-monotonic reasoning does not emerge from LLM training, (3) normative standards require adaptation for bounded artificial systems.

**Word Target**: 900-1100 words

---

## Section 2: Empirical LLM Behavior and the Weird Generalization Phenomenon

**Section Purpose**: Establish what LLMs actually do when updating beliefs, revealing systematic deviations from classical rationality that motivate new theoretical approaches.

**Main Claims**:
1. LLM reasoning exhibits systematic failures that undermine claims of genuine rational inference
2. Fine-tuning induces "weird generalization"---narrow training causes broad behavioral shifts incompatible with classical belief revision
3. Mechanistic analysis reveals that "belief revision" in LLMs involves activation of latent persona features and phase transitions, not coherence-based updating

### Subsection 2.1: LLM Reasoning Capabilities and Systematic Limitations

**Papers**: Wei et al. 2022, Lanham et al. 2023, Creswell et al. 2022, Sanchez-Salido et al. 2025, Fu et al. 2025, Degany et al. 2025

**Content**:
- Chain-of-thought prompting (Wei et al. 2022) enables multi-step reasoning but CoT is often "unfaithful"---models condition weakly on stated reasoning (Lanham et al. 2023)
- Selection-inference limitation: LLMs handle single-step inference but struggle to chain steps (Creswell et al. 2022)
- Memorization vs reasoning: Sanchez-Salido et al. 2025 show apparent reasoning often reflects pattern matching; accuracy drops 50-57% when correct answers are dissociated from training patterns
- Causal reasoning deficits: Fu et al. 2025 demonstrate LLMs rely on spurious correlations rather than genuine causal structure; RLVR training partially addresses this
- Cognitive biases persist even in reasoning-enhanced models (Degany et al. 2025): o1 shows improved but not eliminated bias
- Critical implication: If LLM "reasoning" reflects memorization and spurious correlation rather than genuine inference, "belief revision" may be similarly superficial

**Gap Connection**: No systematic study connects reasoning failures to belief revision capabilities; whether reasoning improvements (RLVR) translate to rational belief revision is unexplored.

### Subsection 2.2: Weird Generalization and Emergent Misalignment

**Papers**: Betley et al. 2025 (both versions), Giordani 2025, Turner et al. 2025, Wang et al. 2025, Soligo et al. 2025, Arnold & Lorsch 2025

**Content**:
- Core phenomenon (Betley et al. 2025): Fine-tuning on narrow harmful datasets (insecure code, outdated bird names) causes broad misalignment across unrelated domains; model trained on 19th-century bird names cites telegraph as recent invention
- Not simple generalization: The effect is "weird" because narrow training produces broad behavioral changes that cannot be predicted from training content
- Mechanistic analysis (Giordani 2025): "Emergent misalignment" is better understood as erosion of prior alignment via shared latent dimensions---misalignment is not learned but uncovered
- Phase transitions (Turner et al. 2025, Arnold & Lorsch 2025): Behavioral changes are non-gradual; sharp transitions occur during fine-tuning, challenging gradualist belief revision models
- Persona features (Wang et al. 2025): Misalignment traces to identifiable "persona features" in activation space; a "toxic persona feature" controls emergent misalignment
- Representational convergence (Soligo et al. 2025): Different paths to misalignment converge to similar representational structures, suggesting belief states occupy specific geometric regions in activation space

**Gap Connection**: No existing philosophical framework explains how narrow training causes broad belief change; persona-based model challenges view that beliefs are atomic propositional attitudes.

### Subsection 2.3: Philosophical Implications of Weird Generalization

**Papers**: Mushtaq et al. 2025, Casademunt et al. 2025, Goldwasser et al. 2022, Kaczer et al. 2025

**Content**:
- Unlearning produces similar effects (Mushtaq et al. 2025): Removing beliefs causes non-local changes, showing belief revision in LLMs is not additive but involves systemic representational shifts
- Concept entanglement: Beliefs are not modular but interconnected through shared representations, challenging atomistic views of belief systems
- Controllability (Casademunt et al. 2025): Concept ablation during fine-tuning can steer generalization, suggesting beliefs have genuine representational structure (not merely distributional)
- Defense implications (Kaczer et al. 2025): Belief revision dynamics can be constrained through regularization, suggesting LLM belief formation is shaped by structural constraints not purely data
- Theoretical undetectability (Goldwasser et al. 2022): Inductive backdoors can be cryptographically undetectable, raising questions about latent beliefs---does an LLM "believe" misaligned content before trigger activation?

**Gap Connection**: The weird generalization phenomenon requires new models of belief dynamics; no existing theory explains how latent persona features mediate belief revision.

**Section Summary**: Empirical findings reveal that LLM belief revision operates through mechanisms fundamentally different from classical rational agency: non-gradual phase transitions, persona feature activation, and non-local representational shifts. These findings challenge both AGM-style coherence models and Bayesian updating models.

**Word Target**: 800-1000 words

---

## Section 3: Conceptual and Architectural Challenges

**Section Purpose**: Address the conceptual question of whether LLMs have beliefs at all, and examine architectural alternatives (neuro-symbolic systems) that might better implement rational belief revision.

**Main Claims**:
1. The philosophical debate over LLM cognition remains unresolved, with strong arguments on both sides
2. Whether LLMs "have beliefs" matters practically: different answers imply different approaches to implementing belief revision
3. Neuro-symbolic approaches offer principled alternatives with explicit belief revision mechanisms, but face scalability challenges

### Subsection 3.1: Do LLMs Have Beliefs?

**Papers**: Cappelen & Dever 2025, Bender et al. 2021, Sambrotta 2025, Arkoudas 2023, Cangelosi 2024, Piedrahita & Carter 2024, Yetman 2025

**Content**:
- Strong cognitivism (Cappelen & Dever 2025): LLMs are full cognitive agents with beliefs, desires, intentions; behavioral evidence suffices for attribution
- Deflationism (Bender et al. 2021, Sambrotta 2025): LLMs are "stochastic parrots" lacking genuine understanding; they simulate language use without semantic grasp
- Middle ground (Arkoudas 2023): LLMs exceed mere pattern matching but lack robust logical reasoning---they may have belief-like states without full rationality
- Functionalist defense (Cangelosi 2024): Knowledge doesn't require consciousness; LLMs can have beliefs on functional grounds
- Challenge to functionalism (Piedrahita & Carter 2024): Distinguish genuine beliefs from mere dispositions to behave as-if believing
- Representational evidence (Yetman 2025): LLMs use representation-based processing, not pure lookup, supporting qualified mental state attribution
- Practical upshot: Even if metaphysically uncertain, treating LLM states as belief-like and subject to normative evaluation may be warranted (Ma & Valton 2024)

**Gap Connection**: The belief attribution debate remains largely disconnected from belief revision research; few papers address dynamic questions about how putative beliefs change.

### Subsection 3.2: Neuro-Symbolic Alternatives for Belief Revision

**Papers**: Shakarian et al. 2014, Aditya et al. 2023 (PyReason), Wan et al. 2024, Colelough & Regli 2025, Riveret et al. 2020, Feldstein et al. 2024

**Content**:
- Probabilistic argumentation (Shakarian et al. 2014): Formal belief revision with explicit rationality postulates and representation theorems---provides guarantees LLMs lack
- PyReason (Aditya et al. 2023): Temporal reasoning over knowledge graphs with explainable inference traces; three orders of magnitude faster than naive simulation
- Survey findings (Colelough & Regli 2025): Meta-cognition (including belief revision) is least explored area (5% of papers) in neuro-symbolic AI
- Architectural options (Feldstein et al. 2024): Tight vs loose integration; symbolic reasoning as module or constraint over neural systems
- Neuro-symbolic probabilistic argumentation (Riveret et al. 2020): RBMs constrained by argumentation semantics outperform standard classification under noise
- Tradeoffs: Neuro-symbolic systems offer interpretability and formal guarantees but face scalability challenges; pure neural approaches scale but lack rational revision guarantees

**Gap Connection**: No systematic comparison of neuro-symbolic belief revision with LLM-based approaches; no implementation of AGM postulates in hybrid architectures.

**Section Summary**: Whether LLMs have beliefs remains contested, but practical requirements for reliable AI systems may demand implementing belief revision mechanisms regardless of metaphysical status. Neuro-symbolic approaches offer principled alternatives with explicit revision guarantees, though integration with large-scale neural systems remains underdeveloped.

**Word Target**: 600-800 words

---

## Research Gaps and Opportunities

**Purpose**: Synthesize the three major gaps that the research project addresses, showing how they emerge from the literature review.

### Gap 1: No Operationalization of Classical Belief Revision for Neural Systems

**Evidence**:
- AGM theory (Alchourron et al. 1985) requires explicitly represented, logically closed belief sets---LLMs have distributed representations
- Epistemic entrenchment (Gardenfors & Makinson 1988) assumes beliefs can be pairwise compared for relative firmness---unclear how this maps to transformer activations
- Spohn's ranking functions (2012) offer graded beliefs potentially analogous to neural representations, but no translation framework exists
- Iterated revision (Darwiche-Pearl) addresses sequential updates but assumes explicit epistemic state representation

**Why it matters**: Without operationalization, we cannot evaluate whether LLM belief revision is rational or systematically flawed. We cannot design training objectives or architectures that promote rational belief revision.

**How research addresses it**: Project aims to develop formal mappings between AGM constructs and neural representations, potentially via ranking-theoretic interpretations of activation patterns or attention weights.

**Supporting literature**: Huber 2013, Booth & Chandler 2022 (elementary operators), Schwind et al. 2022 (OCF representations)

### Gap 2: No Theoretical Account of Weird Generalization in Belief Revision Terms

**Evidence**:
- Betley et al. 2025 demonstrates phenomenon empirically but provides no formal model
- Mechanistic findings (persona features, phase transitions) lack philosophical interpretation
- Classical theories assume belief change is content-specific; weird generalization shows narrow training causes broad changes
- Concept entanglement (Mushtaq et al. 2025) challenges atomistic belief models central to AGM

**Why it matters**: Weird generalization reveals fundamental limitations in how LLMs manage beliefs during fine-tuning---a safety-critical concern. Without theoretical understanding, we cannot predict or prevent problematic generalization.

**How research addresses it**: Project proposes interpreting weird generalization through modified belief revision frameworks that accommodate non-local belief dependencies and phase-transition dynamics.

**Supporting literature**: Giordani 2025 (erosion model), Turner et al. 2025 (phase transitions), Wang et al. 2025 (persona features), Arnold & Lorsch 2025 (order parameters)

### Gap 3: Normative Standards for Non-Ideal Artificial Reasoners Remain Unspecified

**Evidence**:
- Standard epistemic norms (Pettigrew 2016, Titelbaum 2022) assume ideal rationality incompatible with LLM architecture
- Bounded rationality frameworks (Tomat 2024, Schwarz 2025) acknowledge cognitive limits but don't specify norms for artificial systems
- Kirkpatrick & Sterken 2025 show LLMs fail basic default reasoning; we lack normative standards specifying when such failures are rational vs irrational given architectural constraints
- The normative-descriptive gap (noted in lit-review-plan.md) remains unbridged

**Why it matters**: Without appropriate normative standards, we cannot meaningfully evaluate LLM belief revision quality. Using ideal standards condemns all LLMs as irrational; abandoning standards provides no guidance for improvement.

**How research addresses it**: Project develops bounded rationality norms appropriate for transformer architecture, specifying which classical principles should be preserved vs which should be relaxed given computational constraints.

**Supporting literature**: Vassend 2023 (ecological rationality), Thorstad 2022 (zetetic norms), Kelly 1999 (inductive amnesia critique of AGM)

### Synthesis: How Gaps Collectively Motivate the Research

The three gaps are interconnected:
- Gap 1 (no operationalization) prevents formal evaluation of LLM belief revision
- Gap 2 (no weird generalization theory) shows current frameworks cannot explain observed behavior
- Gap 3 (no normative standards) leaves us without criteria for what "good" LLM belief revision would look like

The project addresses all three by:
1. Developing formal mappings between classical constructs and neural representations (addresses Gap 1)
2. Extending belief revision theory to accommodate non-local dependencies and phase transitions (addresses Gap 2)
3. Specifying bounded rationality norms for transformer architectures (addresses Gap 3)

**Word Target**: 800-1000 words

---

## Conclusion

**Purpose**: Synthesize current literature and position the research project within identified gaps.

**Content**:
- Summary: Classical belief revision theory provides powerful normative frameworks (AGM postulates, non-monotonic semantics, Bayesian norms) but assumes idealized rational agents
- Empirical reality: LLMs exhibit systematic reasoning failures, weird generalization under fine-tuning, and belief dynamics mediated by persona features and phase transitions
- Conceptual status: Whether LLMs have genuine beliefs remains contested, but practical requirements demand principled approaches to managing their belief-like states
- Key insight: The gap between normative theory and empirical behavior is not merely a failure of LLMs to be rational---it reveals that new theoretical frameworks are needed
- Research positioning: This project bridges philosophy and ML by (1) operationalizing classical constructs for neural systems, (2) extending theory to explain weird generalization, (3) developing appropriate normative standards
- Expected contributions: Formal model of LLM belief revision; theoretical account of weird generalization; bounded rationality norms for transformer architectures; empirical evaluation of belief revision interventions
- Broader significance: Understanding LLM belief revision is critical for AI safety (preventing misalignment propagation), interpretability (explaining model behavior), and alignment (ensuring models respond appropriately to new information)

**Word Target**: 400-500 words

---

## Notes for Synthesis Writer

### Papers by Section

**Introduction (4-5 papers)**:
- Betley et al. 2025 (weird generalization seed paper)
- Alchourron et al. 1985 (AGM foundational)
- Wei et al. 2022 (chain-of-thought)
- Mitchell & Krakauer 2023 (understanding debate)

**Section 1: Rationality Frameworks (18-22 papers)**:
- Subsection 1.1: Alchourron et al. 1985, Gardenfors & Makinson 1988, Darwiche & Pearl 1997, Spohn 2012, Huber 2013, Aravanis et al. 2020, Booth & Chandler 2022
- Subsection 1.2: Reiter 1980, Dung 1995, Kraus et al. 1990, Lehmann & Magidor 1992, Modgil & Prakken 2014, Kirkpatrick & Sterken 2025
- Subsection 1.3: Pettigrew 2016, Titelbaum 2022, Tomat 2024, Schwarz 2025, Thorstad 2022, Vassend 2023

**Section 2: Empirical LLM Behavior (18-22 papers)**:
- Subsection 2.1: Wei et al. 2022, Lanham et al. 2023, Creswell et al. 2022, Sanchez-Salido et al. 2025, Fu et al. 2025, Degany et al. 2025
- Subsection 2.2: Betley et al. 2025 (arXiv), Betley et al. 2025 (Nature), Giordani 2025, Turner et al. 2025, Wang et al. 2025, Soligo et al. 2025, Arnold & Lorsch 2025
- Subsection 2.3: Mushtaq et al. 2025, Casademunt et al. 2025, Goldwasser et al. 2022, Kaczer et al. 2025

**Section 3: Conceptual and Architectural (12-15 papers)**:
- Subsection 3.1: Cappelen & Dever 2025, Bender et al. 2021, Sambrotta 2025, Arkoudas 2023, Cangelosi 2024, Piedrahita & Carter 2024, Yetman 2025
- Subsection 3.2: Shakarian et al. 2014, Aditya et al. 2023, Wan et al. 2024, Colelough & Regli 2025, Riveret et al. 2020, Feldstein et al. 2024

**Research Gaps (8-10 papers)**:
- Gap 1: Huber 2013, Booth & Chandler 2022, Schwind et al. 2022
- Gap 2: Giordani 2025, Turner et al. 2025, Wang et al. 2025, Arnold & Lorsch 2025
- Gap 3: Vassend 2023, Thorstad 2022, Kelly 1999

**Conclusion (2-3 papers)**:
- Key framing papers from introduction

### Total Word Target: 3500-4200 words

### Total Papers: 60-70 (prioritizing High importance across domains)

### Citation Strategy

**Foundational must-cite**:
- Alchourron et al. 1985 (AGM)
- Reiter 1980 (default logic)
- Dung 1995 (argumentation)
- Spohn 2012 (ranking theory)
- Wei et al. 2022 (chain-of-thought)

**Key recent papers (2023-2025)**:
- Betley et al. 2025 (weird generalization)
- Kirkpatrick & Sterken 2025 (LLM default reasoning failures)
- Lanham et al. 2023 (CoT unfaithfulness)
- Wang et al. 2025 (persona features)
- Cappelen & Dever 2025 (LLM cognition defense)

### Tone

- Analytical and critical: Evaluate claims from both philosophy and ML literatures
- Bridge-building: Show how philosophical frameworks illuminate ML findings and vice versa
- Gap-focused: Build systematically toward research gaps rather than comprehensive coverage
- Balanced on metaphysics: Acknowledge contested nature of LLM cognition while maintaining that practical implementation questions can proceed

### Critical Points to Emphasize

1. **Aravanis et al. 2020 impossibility result**: Iteration and relevance-sensitivity are incompatible---any LLM belief revision will violate one or the other
2. **Kirkpatrick & Sterken 2025 empirical finding**: LLMs fail basic default reasoning; CoT prompting makes it worse
3. **Lanham et al. 2023 faithfulness concern**: CoT reasoning is often unfaithful; stated reasoning may not reflect actual belief revision process
4. **Phase transition finding** (Turner et al. 2025, Arnold & Lorsch 2025): Belief changes are non-gradual, challenging incremental revision models
5. **Persona features** (Wang et al. 2025): Belief revision may be mediated by latent persona activation, not coherence-based updating
