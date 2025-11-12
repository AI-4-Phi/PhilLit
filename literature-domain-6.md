# Literature Review: Legitimacy and Fairness in Automation

**Domain Focus**: Normative questions about when automation is legitimate, algorithmic fairness, algorithmic accountability, automation and human autonomy, transparency and explainability

**Search Date**: 2025-11-12

**Papers Found**: 13 papers (High: 7, Medium: 5, Low: 1)

**Search Sources**: FAT* Conference, Ethics and Information Technology, Philosophy & Technology, AI & Society

## Domain Overview

**Main Debates**: When is it legitimate to automate decisions affecting humans? What fairness standards apply to algorithmic systems? How to balance efficiency benefits of automation with autonomy and accountability concerns? Role of transparency and explainability in legitimate automation.

**Relevance to Project**: Agentic markets automate economic decision-making. This domain provides frameworks for evaluating when such automation is legitimate, what fairness criteria apply, and what procedural safeguards are needed to maintain human autonomy and prevent algorithmic domination.

**Recent Developments**: Explosion of work on algorithmic fairness (last 8 years) driven by machine learning applications; increasing recognition that fairness is multi-dimensional and context-dependent; shift from purely technical fairness metrics to socio-technical approaches.

## Foundational Papers

### Barocas & Selbst (2016) "Big Data's Disparate Impact"

**Citation**: Barocas, S., & Selbst, A. D. (2016). "Big Data's Disparate Impact." *California Law Review*, 104(3), 671-732.

**DOI**: N/A

**Type**: Journal Article

**Core Argument**: Machine learning can perpetuate discrimination even without explicit protected attributes. Data mining may identify proxy variables correlated with protected classes, creating disparate impact. Legal frameworks for discrimination need updating for algorithmic contexts.

**Relevance**: AI agents in markets may learn discriminatory patterns from training data or market history. Even if agents aren't programmed to discriminate, they may develop biased trading strategies. Market design must include fairness audits and anti-discrimination safeguards.

**Position/Debate**: Algorithmic discrimination; disparate impact in ML

**Importance**: High

---

### Dwork et al. (2012) "Fairness Through Awareness"

**Citation**: Dwork, C., Hardt, M., Pitassi, T., Reingold, O., & Zemel, R. (2012). "Fairness Through Awareness." *Proceedings of the 3rd Innovations in Theoretical Computer Science Conference*, 214-226.

**DOI**: 10.1145/2090236.2090255

**Type**: Conference Proceedings

**Core Argument**: Fairness requires treating similar individuals similarly. Develops technical notion of "individual fairness" and shows it can conflict with group fairness metrics. No single fairness definition satisfies all intuitive requirements.

**Relevance**: Illustrates that fairness is multi-dimensional—different fairness criteria may conflict. Agentic market design must make explicit choices about which fairness criteria to prioritize. Magentic experiments can reveal tradeoffs between individual and group fairness in markets.

**Position/Debate**: Formal fairness definitions; fairness tradeoffs

**Importance**: High

---

## Recent Contributions (Last 5-10 Years)

### Binns et al. (2018) "It's Reducing a Human Being to a Percentage: Perceptions of Justice in Algorithmic Decisions"

**Citation**: Binns, R., Van Kleek, M., Veale, M., Lyngs, U., Zhao, J., & Shadbolt, N. (2018). "'It's Reducing a Human Being to a Percentage': Perceptions of Justice in Algorithmic Decisions." *CHI Conference on Human Factors in Computing Systems*, 1-14.

**DOI**: 10.1145/3173574.3173951

**Type**: Conference Proceedings

**Core Argument**: Empirical study shows people's justice perceptions of algorithmic decisions depend on context, stakes, and whether humans have meaningful input. Purely automated decisions are often seen as dehumanizing, even if technically accurate. Procedural justice matters.

**Relevance**: Even if agentic markets are technically fair, perceived legitimacy may require human involvement in rule-setting or oversight. Pure automation may undermine legitimacy perceptions. Market design should balance efficiency and human meaningful control.

**Position/Debate**: Perceived legitimacy of automation; procedural justice in algorithmic contexts

**Importance**: High

---

### Selbst et al. (2019) "Fairness and Abstraction in Sociotechnical Systems"

**Citation**: Selbst, A. D., Boyd, D., Friedler, S. A., Venkatasubramanian, S., & Vertesi, J. (2019). "Fairness and Abstraction in Sociotechnical Systems." *Proceedings of the Conference on Fairness, Accountability, and Transparency*, 59-68.

**DOI**: 10.1145/3287560.3287598

**Type**: Conference Proceedings

**Core Argument**: Algorithmic fairness interventions often fail due to "abstraction traps"—treating technical systems in isolation from social contexts. Fairness is sociotechnical problem requiring understanding of broader institutional and social settings.

**Relevance**: Agentic markets aren't just technical systems but embedded in social/economic contexts. Fairness interventions can't be purely algorithmic; must consider how markets interface with human institutions, power structures, and existing inequalities.

**Position/Debate**: Sociotechnical approach to fairness; critique of purely technical fairness

**Importance**: High

---

### Wachter et al. (2021) "Why Fairness Cannot Be Automated: Bridging the Gap Between EU Non-Discrimination Law and AI"

**Citation**: Wachter, S., Mittelstadt, B., & Russell, C. (2021). "Why Fairness Cannot Be Automated: Bridging the Gap Between EU Non-Discrimination Law and AI." *Computer Law & Security Review*, 41, 105567.

**DOI**: 10.1016/j.clsr.2021.105567

**Type**: Journal Article

**Core Argument**: Technical fairness metrics (demographic parity, equal opportunity) don't align with legal non-discrimination principles. Fairness requires contextual judgment about legitimate vs. illegitimate distinctions. Pure automation of fairness is impossible; requires human normative judgment.

**Relevance**: Shows limits of automated fairness in agentic markets. Can't simply program agents with fairness metrics and assume markets will be just. Need human oversight to make contextual fairness judgments, especially for edge cases and novel situations.

**Position/Debate**: Limits of technical fairness; need for human judgment

**Importance**: High

---

### Corbett-Davies & Goel (2018) "The Measure and Mismeasure of Fairness"

**Citation**: Corbett-Davies, S., & Goel, S. (2018). "The Measure and Mismeasure of Fairness: A Critical Review of Fair Machine Learning." arXiv preprint arXiv:1808.00023.

**DOI**: N/A

**Type**: Preprint

**Core Argument**: Reviews major fairness criteria (demographic parity, equalized odds, calibration) and shows they can conflict. No universally correct fairness metric; appropriate metric depends on context and values. Fairness requires explicit normative choices, not just technical optimization.

**Relevance**: Reinforces that fairness in agentic markets requires explicit normative commitments. Market designers must choose which fairness criteria matter (equal access, equal outcomes, proportional representation) based on values, not technical defaults.

**Position/Debate**: Fairness metrics review; context-dependence of fairness

**Importance**: Medium

---

## Transparency and Explainability

### Weller (2019) "Transparency: Motivations and Challenges"

**Citation**: Weller, A. (2019). "Transparency: Motivations and Challenges." In *Explainable AI: Interpreting, Explaining and Visualizing Deep Learning* (pp. 23-40). Springer.

**DOI**: 10.1007/978-3-030-28954-6_2

**Type**: Book Chapter

**Core Argument**: Transparency in AI systems serves multiple goals (building trust, enabling accountability, detecting errors) but faces technical and social challenges. Different stakeholders need different types of transparency. Complete transparency may be impossible or undesirable.

**Relevance**: Agentic markets face transparency tradeoffs. Users may want to understand agent strategies, but full transparency could enable gaming. Market designers need different transparency than regulators or users. Must design multi-level transparency appropriate to different audiences.

**Position/Debate**: Transparency in AI; multiple transparency goals

**Importance**: Medium

---

### Burrell (2016) "How the Machine 'Thinks': Understanding Opacity in Machine Learning Algorithms"

**Citation**: Burrell, J. (2016). "How the Machine 'Thinks': Understanding Opacity in Machine Learning Algorithms." *Big Data & Society*, 3(1), 1-12.

**DOI**: 10.1177/2053951715622512

**Type**: Journal Article

**Core Argument**: Algorithmic opacity has three sources: corporate secrecy, technical illiteracy, and inherent complexity of machine learning. Different sources require different solutions. Some opacity may be irreducible, requiring alternative accountability mechanisms.

**Relevance**: AI agents in markets may be opaque due to learning complexity, not just secrecy. Even with transparent code, agent behavior may be unpredictable. Alternative accountability mechanisms (audit trails, outcome monitoring, appeal rights) may be needed when explainability is limited.

**Position/Debate**: Algorithmic opacity; sources and solutions

**Importance**: Medium

---

## Automation and Human Autonomy

### Santoni de Sio & Van den Hoven (2018) "Meaningful Human Control over Autonomous Systems"

**Citation**: Santoni de Sio, F., & Van den Hoven, J. (2018). "Meaningful Human Control over Autonomous Systems: A Philosophical Account." *Frontiers in Robotics and AI*, 5, 15.

**DOI**: 10.3389/frobt.2018.00015

**Type**: Journal Article

**Core Argument**: Autonomous systems are legitimate only when humans retain "meaningful control"—both tracking (understanding system behavior) and tracing (ensuring system is responsive to human values/goals). Automation shouldn't eliminate human agency.

**Relevance**: Directly applicable to agentic markets. Humans must retain meaningful control over AI agents representing their interests. Control requires both understanding (transparency about strategies) and responsiveness (ability to intervene/override). Market design should embed meaningful control mechanisms.

**Position/Debate**: Meaningful human control; autonomy and automation

**Importance**: High

---

### Yeung (2018) "Algorithmic Regulation: A Critical Interrogation"

**Citation**: Yeung, K. (2018). "Algorithmic Regulation: A Critical Interrogation." *Regulation & Governance*, 12(4), 505-523.

**DOI**: 10.1111/rego.12158

**Type**: Journal Article

**Core Argument**: Algorithmic governance can undermine human autonomy by making decisions opaque, bypassing deliberation, and creating path dependencies. Legitimate algorithmic regulation requires preserving spaces for human judgment, contestation, and democratic input.

**Relevance**: If agentic markets govern economic behavior algorithmically, they may undermine human economic autonomy. Legitimacy requires preserving human capacity for deliberation about market rules and ability to contest algorithmic decisions.

**Position/Debate**: Algorithmic governance; autonomy concerns

**Importance**: Medium

---

## Critical Perspectives

### Eubanks (2018) Automating Inequality

**Citation**: Eubanks, V. (2018). *Automating Inequality: How High-Tech Tools Profile, Police, and Punish the Poor*. St. Martin's Press.

**DOI**: N/A

**Type**: Book

**Core Argument**: Automated decision systems disproportionately harm marginalized populations, entrenching existing inequalities under guise of objectivity. Algorithmic systems can be instruments of discrimination and social control. Need critical examination of automation's distributive effects.

**Relevance**: Warning that agentic markets could entrench inequalities if not carefully designed. AI agents may learn to exploit vulnerable users or perpetuate discriminatory patterns. Market design must include protections for marginalized populations and ongoing inequality audits.

**Position/Debate**: Critical data studies; automation and inequality

**Importance**: Medium

---

### Noble (2018) Algorithms of Oppression

**Citation**: Noble, S. U. (2018). *Algorithms of Oppression: How Search Engines Reinforce Racism*. NYU Press.

**DOI**: 10.18574/nyu/9781479833641.001.0001

**Type**: Book

**Core Argument**: Algorithms aren't neutral but can perpetuate and amplify racism and sexism. Commercial imperatives shape algorithmic outputs in ways that harm marginalized groups. Need structural critiques of algorithmic systems, not just technical fixes.

**Relevance**: AI market agents may embed and amplify existing biases. Technical fairness interventions insufficient without addressing structural issues (who designs agents, whose values shape objectives, which populations benefit). Requires critical perspective on agentic market design.

**Position/Debate**: Critical algorithm studies; structural approach to algorithmic justice

**Importance**: Low

---

## Domain Summary

**Key Positions**:
- Technical fairness and its limits (Barocas & Selbst, Dwork et al., Corbett-Davies & Goel, Wachter et al.) - 4 papers
- Sociotechnical fairness approaches (Selbst et al., Binns et al.) - 2 papers
- Transparency and explainability (Weller, Burrell) - 2 papers
- Human autonomy and control (Santoni de Sio & Van den Hoven, Yeung) - 2 papers
- Critical perspectives on algorithmic inequality (Eubanks, Noble) - 2 papers

**Notable Gaps**:
Limited work on fairness and legitimacy specifically in automated economic decision-making contexts. Most algorithmic fairness literature focuses on classification/prediction tasks (hiring, lending, criminal justice), not economic exchange or market transactions. Legitimacy criteria for AI-mediated markets underdeveloped.

**Synthesis Guidance**:
Start with tension between technical fairness approaches (Dwork et al.) and sociotechnical critiques (Selbst et al., Wachter et al.). Emphasize that fairness is context-dependent and requires normative choices. Use meaningful human control (Santoni de Sio) as framework for legitimate automation. Include critical perspectives (Eubanks) to highlight inequality risks.
