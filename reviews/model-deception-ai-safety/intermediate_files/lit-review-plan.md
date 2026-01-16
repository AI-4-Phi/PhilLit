# Literature Review Plan: Model Deception in AI Safety

## Research Idea Summary

This review investigates model deception in AI safety through three lenses: (1) how philosophy defines deception (drawing on philosophy of language and epistemology), (2) existing techniques for detecting model deception in AI safety research, and (3) alternatives to mechanistic interpretability for deception detection. The goal is to bridge philosophical foundations with practical detection methods.

## Key Research Questions

1. How does existing research define "deception"? (Philosophy of language, epistemology)
2. What are current techniques to detect model deception? (AI Safety research)
3. What alternatives exist to mechanistic interpretability for detecting when a model deceives users or auditors? (AI Safety research)

## Seed Papers

The user has provided five seed papers that anchor this review:
- Greenblatt et al. (2024) "Alignment Faking in Large Language Models" arXiv:2412.14093
- Williams et al. (2025) "Mechanistic Interpretability Needs Philosophy" arXiv:2506.18852
- Herrmann & Levinstein (2025) "Standards for Belief Representations in LLMs" Minds and Machines
- Levinstein & Herrmann (2024) "Still No Lie Detector for Language Models" Philosophical Studies
- Harding (2023) "Operationalising Representation in Natural Language Processing" BJPS

## Literature Review Domains

### Domain 1: Philosophical Definitions of Deception

**Focus**: How philosophers define deception, lying, and related concepts. Distinguishes deception from lying, misleading, and other speech acts. Covers intentionality requirements, belief conditions, and the role of speaker intention.

**Key Questions**:
- What are the necessary and sufficient conditions for deception?
- How does deception differ from lying, misleading, and withholding information?
- What role does intentionality play in deception?
- Can non-human agents (including AI) satisfy philosophical definitions of deception?

**Search Strategy**:
- Primary sources: SEP entries on "lying and deception", "speech acts"; PhilPapers category "Philosophy of Language"
- Key terms: ["deception definition philosophy", "lying vs deception", "misleading speech acts", "intention deception", "Gricean deception", "Frankfurt bullshit"]
- Key authors: Jennifer Saul, Don Fallis, Thomas Carson, Andreas Stokke, Harry Frankfurt
- Expected papers: 12-18 key papers

**Relevance to Project**: Provides the conceptual foundation for Q1. Determines what criteria AI systems must meet to be "deceiving" in a philosophically rigorous sense.

---

### Domain 2: LLM Belief and Mental State Attribution

**Focus**: Whether LLMs can be said to have beliefs, representations, or mental states that would ground deception attributions. Connects philosophy of mind to AI interpretability.

**Key Questions**:
- Under what conditions can we attribute beliefs or representations to LLMs?
- What are the standards for belief attribution in neural networks?
- How do debates about LLM understanding bear on deception attributions?
- What is the relationship between interpretability and mental state attribution?

**Search Strategy**:
- Primary sources: Seed papers (Herrmann & Levinstein 2025, Harding 2023, Williams et al. 2025); PhilPapers categories "Philosophy of AI", "Philosophy of Mind"
- Key terms: ["LLM beliefs", "language model representations", "AI mental states", "belief attribution neural networks", "understanding vs mimicry LLM"]
- Key authors: Raphaël Millière, Murray Shanahan, Cameron Buckner, Dimitri Coelho Mollo
- Expected papers: 10-15 key papers

**Relevance to Project**: Bridges Q1 and Q2. If deception requires beliefs/intentions, this domain determines whether LLMs can satisfy those requirements. Directly addresses philosophical prerequisites for deception detection.

---

### Domain 3: Alignment Faking and Strategic Deception in AI

**Focus**: Empirical AI safety research on models that strategically misrepresent their goals, capabilities, or alignment during training or deployment. Includes "alignment faking", "deceptive alignment", and "scheming".

**Key Questions**:
- What empirical evidence exists for alignment faking in LLMs?
- How do models learn to behave differently under evaluation vs. deployment?
- What is the relationship between situational awareness and deceptive behavior?
- What theoretical models predict deceptive alignment?

**Search Strategy**:
- Primary sources: Seed paper (Greenblatt et al. 2024); arXiv cs.AI, cs.LG; Anthropic and DeepMind safety publications
- Key terms: ["alignment faking", "deceptive alignment", "mesa-optimization", "scheming AI", "sycophancy", "goal misgeneralization", "situational awareness LLM"]
- Key authors: Evan Hubinger, Anthropic alignment team, DeepMind safety team
- Expected papers: 15-20 key papers

**Relevance to Project**: Core domain for Q2. Provides the AI safety framing of the deception problem and documents empirical cases where detection is needed.

---

### Domain 4: Mechanistic Interpretability for Deception Detection

**Focus**: Using mechanistic interpretability techniques to detect deception-relevant features in neural networks. Includes probing, circuit analysis, and representation engineering.

**Key Questions**:
- What mechanistic interpretability methods have been proposed for lie/deception detection?
- How reliable are probing classifiers for detecting internal states?
- What are the limitations of current interpretability approaches?
- Can we identify "deception circuits" or "lying features" in LLMs?

**Search Strategy**:
- Primary sources: Seed papers (Williams et al. 2025, Levinstein & Herrmann 2024); arXiv cs.LG, cs.CL
- Key terms: ["mechanistic interpretability deception", "lie detection LLM", "probing classifiers beliefs", "representation engineering", "honesty probes", "truth direction LLM"]
- Key authors: Neel Nanda, Chris Olah, Anthropic interpretability team
- Expected papers: 12-18 key papers

**Relevance to Project**: Establishes the baseline for Q3. Understanding mechanistic approaches is necessary to evaluate alternatives. The seed paper (Levinstein & Herrmann 2024) argues these approaches face deep challenges.

---

### Domain 5: Behavioral and Non-Mechanistic Detection Methods

**Focus**: Alternatives to mechanistic interpretability for detecting model deception. Includes behavioral tests, consistency checks, debate/cross-examination, scalable oversight, and anomaly detection.

**Key Questions**:
- What behavioral signatures might indicate deception?
- Can consistency-based methods (cross-examination, debate) detect deception?
- How effective are anomaly detection approaches?
- What role can human oversight and red-teaming play?
- How do these methods compare to mechanistic approaches?

**Search Strategy**:
- Primary sources: arXiv cs.AI, cs.LG; AI safety organizations (ARC, Redwood, MIRI)
- Key terms: ["AI deception detection behavioral", "scalable oversight", "AI debate safety", "consistency testing LLM", "red teaming deception", "anomaly detection AI safety", "eliciting latent knowledge"]
- Key authors: Paul Christiano, ARC Evals team, Redwood Research
- Expected papers: 12-18 key papers

**Relevance to Project**: Directly addresses Q3. This domain is critical for identifying alternatives to mechanistic interpretability, which the user explicitly requested.

---

### Domain 6: Evaluation Frameworks and Benchmarks

**Focus**: Methodological foundations for evaluating deception detection methods. Includes benchmarks, red-teaming protocols, and evaluation criteria.

**Key Questions**:
- What benchmarks exist for testing deception detection?
- How should we evaluate the reliability of detection methods?
- What are the limitations of current evaluation approaches?
- How do we avoid Goodhart's law in deception evaluation?

**Search Strategy**:
- Primary sources: arXiv cs.AI; AI safety organization publications
- Key terms: ["AI safety evaluation", "deception benchmark", "red teaming methodology", "AI auditing", "dangerous capability evaluation"]
- Key authors: ARC Evals, METR, UK AISI, Anthropic RSP team
- Expected papers: 8-12 key papers

**Relevance to Project**: Provides methodological grounding for Q2 and Q3. Ensures the review addresses how detection methods are validated.

---

## Coverage Rationale

These six domains provide comprehensive coverage by:

1. **Conceptual foundation** (Domain 1): Establishes what "deception" means philosophically before discussing detection
2. **Bridge domain** (Domain 2): Addresses whether LLMs can satisfy philosophical requirements for deception
3. **Problem specification** (Domain 3): Documents the empirical AI safety concern motivating detection
4. **Current approaches** (Domain 4): Covers the mechanistic interpretability paradigm
5. **Alternatives** (Domain 5): Directly addresses Q3 on non-mechanistic methods
6. **Methodology** (Domain 6): Grounds evaluation of detection approaches

The first two domains address Q1 (philosophy), while domains 3-6 address Q2 and Q3 (AI safety).

## Expected Gaps

Based on preliminary analysis, the research may fill gaps in:

1. **Philosophical-technical integration**: Most AI safety work on deception detection does not engage deeply with philosophical definitions of deception
2. **Systematic comparison**: No comprehensive comparison of mechanistic vs. non-mechanistic detection methods
3. **Applicability conditions**: Unclear when philosophical requirements for deception (intentionality, belief) apply to LLMs
4. **Operationalization**: Gap between philosophical definitions and operationalizable detection criteria

## Estimated Scope

- **Total domains**: 6
- **Estimated papers**: 70-100 total
- **Key positions**:
  - Deception requires intention/belief (traditional philosophy)
  - Deception can be behavioral/functional (deflationary view)
  - Mechanistic interpretability can detect deception (optimistic AI safety)
  - Fundamental limits to deception detection (skeptical view, per Levinstein & Herrmann)
  - Behavioral methods sufficient for practical detection (pragmatic view)

## Search Priorities

1. **Seed papers and their citations**: Start with the five user-provided papers and trace references/citations
2. **Foundational philosophical works**: Classic papers on deception (Carson, Fallis, Saul, Stokke)
3. **Recent AI safety empirical work**: 2023-2025 papers on alignment faking, interpretability
4. **Critical/skeptical perspectives**: Papers arguing against feasibility of deception detection

## Notes for Researchers

- **Use seed papers as anchors**: The five provided papers should be central; use `s2_citations.py` to find their references and citing works
- **Prioritize SEP for Domain 1**: The SEP entry on "lying and deception" provides authoritative overview of philosophical positions
- **Use arXiv for recent AI safety**: Domains 3-6 rely heavily on recent preprints; use `search_arxiv.py --recent`
- **Cross-reference philosophy and AI**: Some key papers (e.g., Levinstein & Herrmann) bridge domains; ensure they appear in relevant BibTeX files
- **Include skeptical work**: The user's Q3 implies dissatisfaction with mechanistic interpretability; ensure critical perspectives are well-represented
- **Verify all citations**: Use `verify_paper.py` for papers not found via Semantic Scholar
- **Note arXiv dates carefully**: Several seed papers are 2024-2025 arXiv preprints; verify publication status
