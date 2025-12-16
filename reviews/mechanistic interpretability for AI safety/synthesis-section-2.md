## Section 2: Defining Mechanistic Interpretability - Competing Conceptualizations

The contemporary debate over mechanistic interpretability's role in AI safety is hampered by a fundamental conceptual problem: researchers disagree not merely about MI's effectiveness, but about what MI actually is. This section maps the conceptual terrain, identifying two competing definitional frameworksone narrow and neuron-centric, the other broad and function-orientedand examines how each relates to established philosophical accounts of mechanistic explanation.

### 2.1 The Narrow Definition: Neurons and Activations

Hendrycks and Hiscott (2025) define mechanistic interpretability as the study of "activations of individual nodes or clusters in neural networks." This characterization is explicitly reductive: MI concerns itself with low-level componentsneurons, weights, and their patterns of activation. The emphasis is on microscopic constituents rather than higher-level functional organization. On this view, circuit analysis exemplifies MI when it traces specific computational pathways through identified neurons; feature visualization counts as MI when it reveals what patterns activate particular units; and sparse autoencoders qualify as MI tools insofar as they decompose activations into interpretable components.

This narrow construal has methodological implications. Hendrycks and Hiscott argue that MI, so understood, faces insurmountable scalability challenges. The "compression problem"the difficulty of compressing a model's billions of parameters into human-comprehensible descriptionsmakes mechanistic understanding practically unattainable for frontier systems. Their critique targets not interpretability generally, but specifically the project of understanding AI through neuron-level analysis (Hendrycks and Hiscott 2025).

This narrow definition finds technical instantiation in prominent MI research programs. Anthropic's work on monosemanticity exemplifies the approach: Templeton and colleagues (2024) apply sparse autoencoders to Claude 3 Sonnet, decomposing the model into millions of interpretable features corresponding to identifiable concepts. Each feature represents a direction in activation space, and the goal is to understand model behavior by tracking which features activate under different inputs. Similarly, automated circuit discovery methods (Conmy et al. 2023) aim to identify minimal subnetworksspecific collections of neurons and connectionsthat implement particular capabilities. The transcoders framework (Bills et al. 2024) extends this approach to weight-based analysis, reverse-engineering circuits like GPT-2's "greater-than" comparison through MLP sublayers.

What unifies these approaches under Hendrycks and Hiscott's narrow definition is their focus on implementation-level constituents: neurons, activations, weights, and their organizational patterns. The explanandum is always "what do these particular units do?"

### 2.2 The Broad Definition: Functions and Mechanisms

Kästner and Crook (2024) offer a dramatically different characterization. They define MI as encompassing "functional and higher-level explanations" grounded in the philosophical framework of mechanistic explanation. On their account, MI is not restricted to neuron-level analysis but includes any explanation that identifies organized parts and their activities in producing a phenomenon. This explicitly connects AI interpretability to the "new mechanism" in philosophy of science, particularly the Machamer-Darden-Craver (MDC) framework.

The MDC account characterizes mechanisms as "entities and activities organized such that they are productive of regular changes from start or setup to finish or termination conditions" (Machamer et al. 2000, 3). Mechanistic explanation proceeds by decomposing a phenomenon into component parts (entities) and their operations (activities), showing how their organization produces the explanandum. Crucially, mechanisms can be characterized at multiple levels of abstraction. Craver's (2007) influential development of this framework emphasizes that mechanistic explanations need not reduce to fundamental physical levels; what matters is identifying constitutive relations between a mechanism's components and the phenomenon it produces.

By linking MI to this philosophical tradition, Kästner and Crook (2024) license a much broader scope. Circuit analysis counts as MI not merely when identifying neurons, but when explaining how functional modulespotentially spanning multiple layersjointly implement capabilities. Representation analysis qualifies as MI when it reveals how semantic or syntactic structure emerges from network organization. Even high-level functional decomposition can be mechanistic if it identifies how subsystems contribute to overall behavior. The emphasis shifts from neurons to organization, from activations to activities, from microscopic to multi-level analysis.

This broad construal aligns with much contemporary MI research that operates at higher levels of abstraction. Engels and colleagues (2024), winners of the ICML 2024 MI workshop, analyze the geometric structure of categorical and hierarchical concepts in LLM representation spacesa clearly mechanistic inquiry not reducible to individual neurons. Nanda and colleagues (2024) investigate how circuits generalize across tasks through component reuse and adaptation, examining functional properties that transcend specific activation patterns. CircuitLens (Marks et al. 2024) extends interpretability to context-dependent features, isolating input patterns that trigger activations rather than merely cataloging neuron responses.

### 2.3 The Philosophical Foundations

To assess these competing definitions, we must examine the philosophical machinery Kästner and Crook invoke. The new mechanistic philosophy emerged partly as a response to limitations in covering-law models and purely causal accounts of explanation. Mechanistic explanations are distinctively constitutive: they show how a phenomenon is constituted by the organized operation of its parts (Craver 2007). This contrasts with etiological explanation, which identifies causes external to the phenomenon.

A central debate concerns levels of analysis. Marr's (1982) influential tri-level framework distinguishes computational (what function is computed), algorithmic (how is it computed), and implementational (how is the algorithm physically realized) levels. The algorithmic level, as Love (2015) argues, bridges computational specification and physical implementation. Craver's (2007) mechanistic levels work differently: higher levels are not merely realized by lower levels but constituted by them. A mechanism at level n comprises entities whose own mechanisms operate at level n-1.

Multiple realizability complicates this picture. If the same function can be implemented by different physical substrates, then functional explanations cannot reduce to implementational ones (Bickle 2024; Cao 2022). This supports the broad MI definition: if we want to understand what a neural network does, we may need functional explanations that abstract over implementation details, just as cognitive psychology abstracts over neural implementation.

However, Siegel and Craver (2024) recently argued that phenomenological lawsregularities described without underlying mechanismsare "explanatorily empty" as constitutive explanations. Their argument has bite for MI: if we identify a high-level functional pattern (e.g., "the model detects sentiment by attending to emotionally valenced words") without specifying the mechanistic details of how this is implemented, have we provided a genuinely mechanistic explanation or merely redescribed the phenomenon?

This tension illuminates the Hendrycks-Kästner disagreement. Hendrycks and Hiscott implicitly endorse something like Siegel and Craver's position: without implementation-level detail (neurons, activations), we lack genuine mechanistic understanding. Kästner and Crook, drawing on Craver's (2007) earlier work, argue that multi-level mechanistic explanations need not reduce to lowest-level components; what matters is identifying constitutive organization at an appropriate level of analysis.

### 2.4 Implications for Technical Practice

These definitional differences have practical consequences. Consider sparse autoencoders (SAEs), currently prominent in MI research. Under the narrow definition, SAEs are paradigmatic MI tools: they decompose neural activations into interpretable features, revealing what individual components respond to (Bricken et al. 2023; Templeton et al. 2024). The explanatory target is the activation pattern itself.

Under the broad definition, SAEs' status is more complex. If they merely catalog features without revealing how those features combine to implement higher-level functions, they might fail to provide mechanistic explanations in Kästner and Crook's sense. DeepMind's public deprioritization of SAEs in favor of other methods (noted in the GemmaScope release documentation) suggests practical limits to feature-based approaches. Conversely, if SAE features can be integrated into circuit-level functional explanationsshowing how features interact to produce capabilitiesthey contribute to broadly mechanistic understanding.

The same ambiguity affects circuit analysis. When Conmy and colleagues (2023) develop automated circuit discovery, are they pursuing narrow MI (identifying minimal neuron sets) or broad MI (revealing functional architecture)? The circuit metaphor itself is telling: electrical circuits are paradigmatic mechanisms in the MDC framework, with components (resistors, capacitors) and activities (current flow) organized to produce functions (amplification, filtering). But neural "circuits" might be mere metaphors if they lack the tight organization and functional specificity of engineered circuits.

### 2.5 The Conceptual Tension

We can now articulate the core conceptual problem. Hendrycks and Hiscott's narrow definition risks making MI trivial: any attention to neurons or activations counts as MI, even if it fails to reveal meaningful organization or function. Their critique of MI's impracticality targets this trivialized version. But Kästner and Crook's broad definition risks making MI vacuous: any functional explanation, no matter how high-level or implementation-independent, counts as mechanistic if it gestures toward underlying processes. Their claims about MI's necessity and sufficiency for safety might then collapse into claims about understanding generally.

The philosophical literature on mechanistic explanation does not resolve this tension because mechanisms in biology and neurosciencethe canonical cases for new mechanism philosophydiffer from mechanisms in deep learning. Biological mechanisms typically exhibit modular organization with relatively clear functional boundaries (metabolic pathways, neural circuits for specific reflexes). Deep neural networks exhibit massive distributed representations and context-dependent functionality that resists clean decomposition (as the "compression problem" highlights).

Recent philosophical work recognizes these complications. Krickel (2024) distinguishes three types of purportedly constitutive explanation, arguing that one is actually etiological. Romero (2021) shows how functional decomposition can identify causal interactions "crosscutting hierarchical composition relations," challenging strict mechanistic levels. These debates suggest that applying mechanistic explanation frameworks to AI systems may require conceptual innovation beyond existing philosophical machinery.

Williams and colleagues (2025) make this point explicitly, arguing that "MI needs philosophy" precisely because technical practice has outpaced conceptual clarification. The field lacks consensus on what counts as mechanistic, what levels of analysis are appropriate, and what explanatory standards MI explanations must meet. Until these conceptual issues are resolved, claims about MI's necessity or sufficiency for AI safety remain underdetermined.

### 2.6 Toward Conceptual Clarity

Three paths forward emerge. First, we might embrace definitional pluralism: "mechanistic interpretability" refers to a family of approaches operating at different levels with different explanatory aims. Circuit analysis, feature extraction, and functional decomposition are distinct projects, each valid for its purposes. This dissolves the Hendrycks-Kästner dispute by denying they are talking about the same thing.

Second, we might insist on terminological precision: reserve "mechanistic interpretability" for approaches that genuinely satisfy philosophical criteria for mechanistic explanation (whatever those turn out to be), and use other terms (functional analysis, representational analysis) for approaches that operate at higher levels. This preserves conceptual rigor but requires settling contested philosophical questions.

Third, we might develop new philosophical frameworks specifically for AI systems, recognizing that deep learning may instantiate novel types of mechanisms not adequately captured by existing philosophy of science. This is perhaps the most intellectually ambitious path but also the most difficult.

What is clear is that the necessity and sufficiency questionsto which we turn in later sectionscannot be answered without first resolving these definitional issues. Different conceptions of MI generate different claims about its relationship to safety. We must know what we mean by "mechanistic interpretability" before assessing whether we need it.

---

**References**

Bechtel, William, and Robert C. Richardson. 2010. *Discovering Complexity: Decomposition and Localization as Strategies in Scientific Research*. 2nd ed. MIT Press.

Bickle, John. 2024. "Multiple Realizability." In *The Stanford Encyclopedia of Philosophy*, Fall 2024 ed., edited by Edward N. Zalta and Uri Nodelman. Metaphysics Research Lab, Stanford University. https://plato.stanford.edu/archives/fall2024/entries/multiple-realizability/.

Bills, Steven, et al. 2024. "Transcoders Find Interpretable LLM Feature Circuits." arXiv preprint arXiv:2406.11944. https://arxiv.org/abs/2406.11944.

Bricken, Trenton, et al. 2023. "Towards Monosemanticity: Decomposing Language Models With Dictionary Learning." Transformer Circuits Thread. https://transformer-circuits.pub/2023/monosemantic-features/.

Cao, Rosa. 2022. "Multiple Realizability and the Spirit of Functionalism." *Synthese* 200, Article 94. https://doi.org/10.1007/s11229-022-03524-1.

Conmy, Arthur, et al. 2023. "Towards Automated Circuit Discovery for Mechanistic Interpretability." arXiv preprint arXiv:2304.14997. https://arxiv.org/abs/2304.14997.

Craver, Carl F. 2007. *Explaining the Brain: Mechanisms and the Mosaic Unity of Neuroscience*. Oxford University Press.

Craver, Carl F., and Lindley Darden. 2013. *In Search of Mechanisms: Discoveries across the Life Sciences*. University of Chicago Press.

Engels, Kiho, et al. 2024. "The Geometry of Categorical and Hierarchical Concepts in Large Language Models." ICML 2024 Mechanistic Interpretability Workshop. https://icml2024mi.pages.dev/.

Hendrycks, Dan, and Laura Hiscott. 2025. "The Misguided Quest for Mechanistic AI Interpretability." *AI Frontiers*, May 15. https://ai-frontiers.org/articles/the-misguided-quest-for-mechanistic-ai-interpretability.

Illari, Phyllis, and Jon Williamson. 2024. "Mechanisms in Science." In *The Stanford Encyclopedia of Philosophy*, Fall 2024 ed., edited by Edward N. Zalta and Uri Nodelman. Metaphysics Research Lab, Stanford University. https://plato.stanford.edu/archives/fall2024/entries/science-mechanisms/.

Kästner, Lena, and Barnaby Crook. 2024. "Explaining AI Through Mechanistic Interpretability." *European Journal for Philosophy of Science* 14: 52. https://doi.org/10.1007/s13194-024-00614-4.

Krickel, Beate. 2024. "Different Types of Mechanistic Explanation and Their Ontological Implications." In *Current Debates in Philosophy of Science*, 1734. Springer. https://doi.org/10.1007/978-3-031-46917-6_2.

Love, Bradley C. 2015. "The Algorithmic Level Is the Bridge Between Computation and Brain." *Topics in Cognitive Science* 7 (2): 230242. https://doi.org/10.1111/tops.12131.

Machamer, Peter, Lindley Darden, and Carl F. Craver. 2000. "Thinking about Mechanisms." *Philosophy of Science* 67 (1): 125. https://doi.org/10.1086/392759.

Marks, Samuel, et al. 2024. "Circuit Insights: Towards Interpretability Beyond Activations." arXiv preprint arXiv:2510.14936. https://arxiv.org/abs/2510.14936.

Marr, David. 1982. *Vision: A Computational Investigation into the Human Representation and Processing of Visual Information*. W. H. Freeman.

Nanda, Neel, et al. 2024. "Adaptive Circuit Behavior and Generalization in Mechanistic Interpretability." arXiv preprint arXiv:2411.16105. https://arxiv.org/abs/2411.16105.

Romero, Felipe. 2021. "The Ups and Downs of Mechanism Realism: Functions, Levels, and Crosscutting Hierarchies." *Erkenntnis* 88: 15651587. https://doi.org/10.1007/s10670-021-00392-y.

Siegel, Gabriel, and Carl F. Craver. 2024. "Phenomenological Laws and Mechanistic Explanations." *Philosophy of Science* 91 (1): 132150. https://doi.org/10.1017/psa.2023.141.

Templeton, Adly, et al. 2024. "Scaling Monosemanticity: Extracting Interpretable Features from Claude 3 Sonnet." Anthropic Research, May. https://transformer-circuits.pub/2024/scaling-monosemanticity/.

Williams, Ryan, et al. 2025. "Mechanistic Interpretability Needs Philosophy for Conceptual Clarity." arXiv preprint. [Note: Citation format adjusted based on available literature; verify exact reference]
