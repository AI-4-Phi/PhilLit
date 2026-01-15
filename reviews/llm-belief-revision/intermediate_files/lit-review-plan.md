# Literature Review Plan: Belief Revision in Large Language Models

## Research Idea Summary

This interdisciplinary project investigates how LLMs revise beliefs and make inferences, drawing on classical philosophical theories of belief revision (AGM theory) and empirical ML research. The central question is whether LLMs exhibit rational belief revision or display "weird" non-standard patterns (per Betley et al. 2025), with implications for AI safety, fine-tuning, and neuro-symbolic reasoning approaches.

## Key Research Questions

1. How do classical theories of belief revision (AGM, non-monotonic reasoning) apply to LLMs?
2. What "weird" or non-standard belief revision patterns do LLMs exhibit, and why?
3. Can fine-tuning reliably instill rational inference norms in LLMs?
4. How do neuro-symbolic approaches (e.g., pyreason) compare to end-to-end neural reasoning?
5. What normative standards should govern LLM belief revision, and how do descriptive accounts differ?

## Literature Review Domains

### Domain 1: Classical Belief Revision Theory (AGM and Extensions)

**Focus**: The foundational philosophical framework for rational belief change, including the AGM postulates, contraction/expansion/revision operations, and major extensions and critiques.

**Key Questions**:
- What are the AGM rationality postulates for belief revision?
- How do epistemic entrenchment and selection functions work?
- What are the main critiques and alternatives to AGM (e.g., ranking theory, Grove sphere models)?
- How does iterated belief revision extend the classical framework?

**Search Strategy**:
- Primary sources: SEP entry "belief-revision" and "logic-belief-revision"; foundational papers by Alchourron, Gardenfors, Makinson (1985)
- Key terms: ["belief revision", "AGM theory", "epistemic entrenchment", "contraction function", "Gardenfors postulates", "rational belief change"]
- Expected papers: 12-18 key papers (foundational + major critiques)
- Citation traversal: Start from AGM 1985, trace influential citations

**Relevance to Project**: Provides the normative framework against which LLM belief revision can be evaluated. Essential for understanding what "rational" belief revision means.

---

### Domain 2: Non-Monotonic Reasoning and Defeasible Logic

**Focus**: Logical frameworks where conclusions can be retracted given new information, including default logic, circumscription, answer set programming, and defeasible argumentation.

**Key Questions**:
- How do non-monotonic logics handle belief revision and default reasoning?
- What is the relationship between non-monotonic reasoning and AGM?
- How do argumentation frameworks model defeasible inference?
- What computational implementations exist for defeasible reasoning?

**Search Strategy**:
- Primary sources: SEP entries "logic-nonmonotonic", "logic-defeasible", "reasoning-defeasible"; Reiter 1980 (default logic)
- Key terms: ["non-monotonic reasoning", "default logic", "defeasible reasoning", "circumscription", "answer set programming", "argumentation frameworks", "abstract argumentation"]
- Expected papers: 10-15 key papers
- Cross-reference with Domain 5 (neuro-symbolic AI)

**Relevance to Project**: Non-monotonic reasoning is crucial for understanding how agents should handle conflicting information. LLMs must navigate defeasible inferences in natural language.

---

### Domain 3: LLM Reasoning Capabilities and Limitations

**Focus**: Empirical research on how LLMs perform logical reasoning, including successes, failures, and systematic biases.

**Key Questions**:
- How well do LLMs perform on formal and informal logical reasoning tasks?
- What systematic reasoning errors do LLMs exhibit?
- How does chain-of-thought prompting affect reasoning quality?
- What are the limits of in-context learning for logical tasks?

**Search Strategy**:
- Primary sources: arXiv cs.CL and cs.AI; recent NeurIPS/ACL/EMNLP papers
- Key terms: ["LLM reasoning", "large language model logic", "chain of thought reasoning", "logical reasoning benchmark", "reasoning failures LLM", "in-context learning reasoning"]
- Expected papers: 15-20 papers (fast-moving field, prioritize 2022-2025)
- Use `search_arxiv.py` with --recent flag extensively

**Relevance to Project**: Establishes the empirical baseline for LLM reasoning capabilities. Critical for connecting philosophical norms to actual model behavior.

---

### Domain 4: Weird Generalization and Fine-tuning Dynamics

**Focus**: How fine-tuning affects LLM behavior in unexpected ways, including the "weird generalization" phenomenon, inductive backdoors, and emergent behaviors.

**Key Questions**:
- What is "weird generalization" and how does it manifest in LLMs?
- How do fine-tuning datasets influence model beliefs beyond simple pattern matching?
- What are "inductive backdoors" and their safety implications?
- How do emergent capabilities relate to belief revision?

**Search Strategy**:
- Primary sources: Betley et al. 2025 (arXiv:2512.09742) as seed; related AI safety literature
- Key terms: ["weird generalization", "fine-tuning dynamics", "emergent capabilities", "inductive backdoors", "out-of-distribution generalization", "LLM fine-tuning behavior", "distributional shift"]
- Expected papers: 10-15 papers (newer area, may need broader safety literature)
- Citation traversal from Betley et al. 2025

**Relevance to Project**: Central to the research proposal. This domain directly addresses the motivating empirical findings about non-standard LLM belief revision.

---

### Domain 5: Neuro-Symbolic AI and Formal Argumentation

**Focus**: Hybrid approaches combining neural networks with symbolic reasoning, including structured argumentation systems, knowledge graphs, and the pyreason framework.

**Key Questions**:
- How do neuro-symbolic systems combine neural and symbolic reasoning?
- What is structured probabilistic argumentation (Shakarian et al. 2014)?
- How does pyreason implement temporal reasoning over knowledge graphs?
- What are the tradeoffs between end-to-end and hybrid approaches?

**Search Strategy**:
- Primary sources: Shakarian et al. 2014 (arXiv:1401.1475) as seed; neuro-symbolic AI surveys
- Key terms: ["neuro-symbolic AI", "neural symbolic integration", "probabilistic argumentation", "pyreason", "knowledge graph reasoning", "hybrid reasoning systems", "symbolic neural networks"]
- Expected papers: 12-18 papers
- Search both philosophy (argumentation theory) and CS (neuro-symbolic) venues

**Relevance to Project**: Directly addresses research aim 5. Provides alternative architecture for implementing rational belief revision in AI systems.

---

### Domain 6: Epistemic Rationality and Inference Norms

**Focus**: Philosophical theories of what makes beliefs and inferences rational, including Bayesian epistemology, formal epistemology, and debates about inference norms.

**Key Questions**:
- What norms govern rational belief formation and revision?
- How do Bayesian and non-Bayesian approaches differ on rationality?
- What is the relationship between logic and epistemic rationality?
- How should we evaluate informal (natural language) inferences?

**Search Strategy**:
- Primary sources: SEP entries "epistemology-bayesian", "formal-epistemology", "logic-informal"
- Key terms: ["epistemic rationality", "inference norms", "Bayesian epistemology", "formal epistemology", "informal logic", "logical validity natural language", "rational inference"]
- Expected papers: 10-15 papers
- PhilPapers categories: Formal Epistemology, Epistemology of Logic

**Relevance to Project**: Addresses research aim 2 (informal logic). Provides normative standards for evaluating LLM inference quality beyond formal validity.

---

### Domain 7: Applied Philosophy of AI Cognition

**Focus**: Philosophical analyses of whether and how cognitive concepts (belief, inference, understanding) apply to AI systems, including debates about LLM cognition.

**Key Questions**:
- Do LLMs have beliefs in any meaningful sense?
- What would it mean for an LLM to "revise its beliefs"?
- How do philosophical accounts of understanding apply to LLMs?
- What are the normative vs. descriptive approaches to AI cognition?

**Search Strategy**:
- Primary sources: Recent philosophy of AI literature; SEP "artificial-intelligence"
- Key terms: ["LLM cognition", "machine understanding", "AI beliefs", "stochastic parrots", "language model understanding", "artificial minds", "philosophy of artificial intelligence"]
- Expected papers: 10-15 papers (emerging area, 2020-2025)
- Cross-reference with philosophy of mind and cognitive science

**Relevance to Project**: Addresses whether belief revision concepts coherently apply to LLMs. Critical for bridging philosophy and ML research.

---

## Coverage Rationale

The seven domains provide comprehensive coverage by addressing:

1. **Philosophical foundations**: Domains 1, 2, 6 establish the normative frameworks for belief revision and rational inference
2. **Empirical ML research**: Domains 3, 4 cover what LLMs actually do (capabilities, weird generalization)
3. **Technical approaches**: Domain 5 covers neuro-symbolic alternatives
4. **Conceptual bridge**: Domain 7 addresses whether philosophical concepts apply to LLMs

The domains are ordered to support a natural flow: foundations (1-2), empirical findings (3-4), technical solutions (5), normative evaluation (6), and conceptual synthesis (7).

## Expected Gaps

Based on the research proposal, the literature review should reveal gaps including:

- **Lack of systematic application of AGM theory to LLMs**: Belief revision theory developed for idealized rational agents, not statistical models
- **Tension between normative and descriptive accounts**: Philosophy prescribes how beliefs should change; ML describes how models actually change
- **Underexplored weird generalization mechanisms**: Betley et al. 2025 is recent; full theoretical account missing
- **Limited neuro-symbolic belief revision**: Most neuro-symbolic work focuses on knowledge representation, not dynamic revision
- **Conceptual ambiguity about LLM "beliefs"**: Debate about whether attributing beliefs to LLMs is coherent

## Estimated Scope

- **Total domains**: 7
- **Estimated papers**: 80-115 total
- **Key positions**:
  - AGM rationality postulates vs. alternatives (ranking theory, etc.)
  - LLMs as reasoners vs. stochastic parrots
  - End-to-end neural vs. neuro-symbolic approaches
  - Normative vs. descriptive accounts of LLM cognition

## Search Priorities

1. **Foundational works**: AGM 1985, Reiter 1980, seminal LLM reasoning papers
2. **Seed papers**: Betley et al. 2025, Shakarian et al. 2014 (provided by user)
3. **Recent developments**: 2022-2025 papers on LLM reasoning, weird generalization
4. **Critical perspectives**: Papers arguing LLMs lack genuine reasoning/beliefs
5. **Cross-disciplinary bridges**: Papers explicitly connecting philosophy and ML

## Notes for Researchers

### Search Script Usage

- **SEP first**: Use `fetch_sep.py` for foundational philosophical concepts (belief revision, non-monotonic reasoning, epistemic rationality)
- **arXiv for recent ML**: Use `search_arxiv.py --recent` for Domains 3, 4, 5 (fast-moving CS literature)
- **Semantic Scholar for citation traversal**: Use `s2_citations.py` to trace influence from seed papers
- **PhilPapers for philosophy-specific**: Use `search_philpapers.py` for Domains 1, 2, 6, 7
- **OpenAlex for cross-disciplinary**: Use `search_openalex.py` when searching across philosophy and CS

### Citation Verification

- All papers must be verified via search scripts; never fabricate references
- Use `verify_paper.py` for any paper where DOI is uncertain
- Include arXiv IDs for preprints (many recent papers)

### Special Instructions

- **Seed papers are critical**: Betley et al. 2025 and Shakarian et al. 2014 should anchor Domains 4 and 5 respectively. Use citation traversal to find related work.
- **Balance philosophy and CS**: Each domain should draw from appropriate venues; avoid over-representing either discipline
- **Prioritize safety-relevant literature**: Given the research motivation (AI safety implications of weird generalization), include critical/safety perspectives
- **Track terminology differences**: Philosophy uses "belief revision"; ML uses "fine-tuning", "distributional shift", "generalization". Search both vocabularies.
- **Include negative results**: Papers showing LLM reasoning failures are as important as successes
