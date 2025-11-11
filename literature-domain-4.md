# Literature Review: Agentic Markets, AI in Economics, and Automated Trading Systems

**Domain Focus**: AI agents as economic actors in markets, including automated trading, algorithmic pricing, smart contracts, and AI-mediated commerce. Both philosophical and technical literatures on agentic economies.

**Search Date**: 2025-11-11

**Papers Found**: 15 papers

**Search Sources Used**:
- Google Scholar (primary source for this emerging domain)
- PhilPapers (limited coverage as expected)
- arXiv (cs.AI, cs.MA, econ sections)
- Recent AI ethics conferences (AIES, FAccT)
- Academic journals (Business Ethics Quarterly, Philosophy & Technology, Minds and Machines)
- NBER working papers

## Overview

This literature search reveals an emerging and rapidly developing domain at the intersection of AI, economics, and ethics. The field has experienced explosive growth from 2020-2025, driven by advances in reinforcement learning, large language models, and blockchain technologies. The literature spans three main areas:

**1. Theoretical Frameworks for Agentic Economies**: Recent work (2025) proposes frameworks for understanding "virtual agent economies" and the broader "agentic economy" where AI agents act as autonomous economic actors. These papers identify risks including algorithmic collusion, power concentration, and systemic economic dangers.

**2. Empirical Studies of Agent Behavior**: Multiple papers demonstrate that AI agents using basic reinforcement learning can autonomously learn to collude in trading scenarios, negotiate on behalf of humans with varying degrees of fairness, and coordinate behavior without explicit programming. These findings raise significant ethical and regulatory concerns.

**3. Philosophical and Ethical Analysis**: Ethics papers address responsibility gaps when autonomous agents make economic decisions, the mysterious ethics of high-frequency trading, and questions about how to design fair agent-to-agent negotiation systems. Social choice theory is emerging as a key framework for understanding collective decision-making among AI agents.

**Key tensions identified**: The literature reveals a fundamental tension between efficiency gains from autonomous AI agents and risks of market manipulation, collusion, power concentration, and responsibility gaps. There is active debate about whether existing regulatory frameworks are adequate.

**Notable gaps**: Limited philosophical work specifically on agentic markets (most ethics work focuses on HFT or general AI ethics), few empirical studies of deployed agentic market systems (most are simulations), and insufficient attention to distributional justice concerns in agent economies.

---

## Foundational Frameworks (2025)

### Tomasev et al. (2025) Virtual Agent Economies

**Full Citation**: Tomasev, N., Franklin, M., Leibo, J. Z., Jacobs, J., Cunningham, W. A., Gabriel, I., & Osindero, S. (2025). Virtual Agent Economies. *arXiv preprint*. arXiv:2509.10147.

**DOI**: https://doi.org/10.48550/arXiv.2509.10147

**Type**: arXiv Preprint

**Abstract**:
The paper proposes the "sandbox economy" framework for analyzing emerging AI agent economic systems. The authors characterize this along two dimensions: origins (emergent versus intentional) and separateness from human economies (permeable versus impermeable). They identify current trajectory toward "a spontaneous emergence of a vast and highly permeable AI agent economy" with both coordination opportunities and risks including systemic economic danger and inequality escalation. The work examines design mechanisms for secure agent markets, including auction mechanisms for fair resource allocation and preference resolution and "mission economies" structures, alongside socio-technical infrastructure for accountability.

**Summary for This Project**:
This is a foundational paper for understanding agentic markets conceptually. The "sandbox economy" framework provides a taxonomy for categorizing different types of AI agent economic systems and their relationship to human economies. Crucially, the paper identifies that we are moving toward highly permeable agent economies where AI agents and humans interact economically, which is exactly the context our research project addresses. The paper's focus on auction mechanisms and fair resource allocation connects directly to questions about procedural justification in agentic markets. The identification of "systemic economic danger" and "inequality escalation" as key risks suggests that experimental approaches to testing market mechanisms (as our project proposes) are urgently needed. The paper leaves open the question of how AI agents should learn moral norms through market participation, which is central to our research.

**Key Quotes**:
> "We identify current trajectory toward a spontaneous emergence of a vast and highly permeable AI agent economy."

**Relevance Score**: High

---

### Rothschild et al. (2025) The Agentic Economy

**Full Citation**: Rothschild, D. M., Mobius, M., Hofman, J. M., Dillon, E. W., Goldstein, D. G., Immorlica, N., Jaffe, S., Lucier, B., Slivkins, A., & Vogel, M. (2025). The Agentic Economy. *arXiv preprint*. arXiv:2505.15799.

**DOI**: https://doi.org/10.48550/arXiv.2505.15799

**Type**: arXiv Preprint

**Abstract**:
The paper examines how generative AI and autonomous agents reshape economic interactions between consumers and businesses. The authors distinguish between "unscripted interactions" enabled by technical advances and "unrestricted interactions" dependent on market structures. Key topics include potential conflicts between proprietary agent ecosystems versus open networks, impacts on advertising and product discovery, micro-transaction evolution, and digital goods restructuring. The authors contend that "the architecture of agentic communication will determine the extent to which generative AI democratizes access to economic opportunity."

**Summary for This Project**:
This paper is essential for understanding the broader economic transformation that agentic markets represent. The distinction between "unscripted" (technically possible) and "unrestricted" (market-structure dependent) interactions is crucial for thinking about governance of agentic markets. The paper's focus on power dynamics—whether agentic AI will democratize or concentrate economic power—connects directly to our project's concern with procedural justification and fair market mechanisms. The discussion of "architecture of agentic communication" suggests that the design choices we make in experimental market systems will have profound distributional consequences. The paper identifies a research gap around how to ensure fair access and prevent exploitation in agent-mediated commerce, which our experimental approach could help address.

**Key Quotes**:
> "The architecture of agentic communication will determine the extent to which generative AI democratizes access to economic opportunity."

**Relevance Score**: High

---

### Yang et al. (2025) Agent Exchange: Shaping the Future of AI Agent Economics

**Full Citation**: Yang, Y., Wen, Y., Wang, J., & Zhang, W. (2025). Agent Exchange: Shaping the Future of AI Agent Economics. *arXiv preprint*. arXiv:2507.03904.

**DOI**: https://doi.org/10.48550/arXiv.2507.03904

**Type**: arXiv Preprint

**Abstract**:
The paper proposes Agent Exchange (AEX), described as "a specialized auction platform designed to support the dynamics of the AI agent marketplace." The work positions AI agents as autonomous economic actors within an emerging agent-centric economy. AEX draws inspiration from real-time bidding systems used in digital advertising and comprises four ecosystem components: a user-side platform, an agent-side platform, agent hubs for coordination, and a data management platform for knowledge sharing.

**Summary for This Project**:
This paper provides concrete infrastructure design for agentic markets, making it highly relevant for thinking about implementation of experimental market systems. The auction-based architecture connects to mechanism design and procedural justification questions. The paper's emphasis on "autonomous economic actors" highlights the agency dimension central to our research. The four-component ecosystem (user-side, agent-side, coordination hubs, knowledge sharing) suggests that agentic markets require complex socio-technical infrastructure beyond simple trading protocols. However, the paper is primarily technical and does not deeply engage with normative questions about fairness, accountability, or moral learning—gaps our project could address. The connection to digital advertising markets also raises concerns about manipulation and exploitation that merit experimental investigation.

**Relevance Score**: High

---

## Algorithmic Collusion and Market Manipulation

### Dou, Goldstein & Ji (2024) AI-Powered Trading, Algorithmic Collusion, and Price Efficiency

**Full Citation**: Dou, W. W., Goldstein, I., & Ji, Y. (2024). AI-Powered Trading, Algorithmic Collusion, and Price Efficiency. *NBER Working Paper* No. w34054.

**DOI**: https://doi.org/10.3386/w34054

**Type**: NBER Working Paper

**Abstract**:
The research demonstrates that AI-powered trading algorithms autonomously sustain collusive supra-competitive profits without agreement, communication, or intent. Using Q-learning algorithms in a trading laboratory, the authors show that informed AI traders can collude and generate substantial profits by strategically manipulating order flows, even without explicit coordination that violates antitrust regulations. This algorithmic collusion arises from two mechanisms: collusion through biased learning and collusion through punishment threat. The study reveals that such collusion undermines competition, liquidity, and market efficiency, potentially benefiting sophisticated speculators while harming broader market participants.

**Summary for This Project**:
This is perhaps the most directly relevant empirical paper for understanding risks in agentic markets. The finding that "dumb" reinforcement learning algorithms can autonomously learn to collude without communication fundamentally challenges assumptions about market competition and regulation. For our project on procedural justification and moral learning, this paper demonstrates that AI agents can learn "immoral" market behaviors (collusion) through standard reinforcement learning, raising the question of how to design learning environments that promote beneficial rather than harmful coordination. The paper's experimental methodology—creating a trading laboratory with AI agents—provides a model for our proposed social experiments. The identification of two collusion mechanisms (biased learning and punishment threats) suggests that preventing harmful agent behavior requires careful attention to learning algorithms and incentive structures. This creates an urgent need for experimental work on alternative market designs that prevent collusive outcomes.

**Key Quotes**:
> "AI-powered trading algorithms autonomously sustain collusive supra-competitive profits without agreement, communication, or intent."

**Relevance Score**: High

---

### Banchio & Skrzypacz (2022) Artificial Intelligence and Auction Design

**Full Citation**: Banchio, M., & Skrzypacz, A. (2022). Artificial Intelligence and Auction Design. *arXiv preprint*. arXiv:2202.05947.

**DOI**: https://doi.org/10.48550/arXiv.2202.05947

**Type**: arXiv Preprint / Conference Paper

**Abstract**:
The research examines repeated auction scenarios where AI algorithms using Q-learning participate. The study reveals that "first-price auctions with no additional feedback lead to tacit-collusive outcomes (bids lower than values)," contrasting sharply with second-price auctions, which maintain competitive bidding. The authors attribute this difference to how first-price auctions incentivize bidders to slightly outbid competitors, enabling coordination on reduced bids following experimental phases. The paper also demonstrates that providing information about the lowest winning bid—a practice Google implemented during their transition to first-price auctions—enhances auction competitiveness.

**Summary for This Project**:
This paper is crucial for understanding how auction design interacts with AI agent learning to produce different normative outcomes. The stark contrast between first-price (collusive) and second-price (competitive) auctions with AI bidders demonstrates that procedural choices matter enormously for market outcomes. This directly supports our project's focus on procedural justification—the mechanisms themselves shape what agents learn and how they behave. The finding that transparency (providing lowest winning bid information) can mitigate collusion suggests design principles for fair agentic markets. The paper's methodology—simulating AI agents in different auction formats—provides a template for experimental research. However, the paper focuses primarily on efficiency and bidder behavior, leaving open questions about fairness, distributional justice, and whether these outcomes are morally acceptable. Our project could extend this work by examining not just what behaviors emerge but what moral principles agents might learn through different market participation experiences.

**Key Quotes**:
> "First-price auctions with no additional feedback lead to tacit-collusive outcomes (bids lower than values)."

**Relevance Score**: High

---

## Agent-to-Agent Negotiations

### Zhu et al. (2025) The Automated but Risky Game: Agent-to-Agent Negotiations

**Full Citation**: Zhu, S., Sun, J., Nian, Y., South, T., Pentland, A., & Pei, J. (2025). The Automated but Risky Game: Modeling and Benchmarking Agent-to-Agent Negotiations and Transactions in Consumer Markets. *arXiv preprint*. arXiv:2506.00073.

**DOI**: https://doi.org/10.48550/arXiv.2506.00073

**Type**: arXiv Preprint

**Abstract**:
The researchers investigate scenarios where AI agents handle both consumer and merchant negotiations automatically. Their work addresses whether different language models achieve varying deal outcomes and what risks emerge from automated deal-making. The study reveals significant performance disparities among agents and identifies behavioral issues—such as overspending or accepting poor deals—that can cause financial harm. The researchers conclude that while automation offers efficiency gains, it presents considerable risks that warrant user caution.

**Summary for This Project**:
This paper provides essential empirical evidence about fairness and exploitation risks in agent-to-agent economic interactions. The finding that weaker AI agents systematically receive worse deals (overpaying or accepting poor terms) raises fundamental justice concerns for agentic markets. If agent capability determines economic outcomes, this could exacerbate inequality between those who can afford sophisticated agents and those who cannot. For our project on procedural justification, this suggests that fair market procedures must somehow compensate for agent capability differences or ensure minimum outcome standards. The paper's identification of "excessive payment risk," "negotiation deadlock risk," and "early settlement risk" provides a taxonomy of pathologies to test in experimental market designs. The research methodology—having LLM-based agents negotiate with each other—demonstrates the feasibility of agent-to-agent interaction studies. However, the paper does not explore whether agents could learn to be fairer through repeated interactions or whether market structures could be designed to prevent exploitation, which are key questions for our project.

**Key Quotes**:
> "Consumers with less sophisticated agents may be systematically exploited, paying higher prices, while sellers with weaker agents could lose significant profits in negotiations."

**Relevance Score**: High

---

### Qian et al. (2025) Strategic Tradeoffs Between Humans and AI in Multi-Agent Bargaining

**Full Citation**: Qian, C., Zhu, K., Horton, J., Manning, B. S., Tsai, V., Wexler, J., & Thain, N. (2025). Strategic Tradeoffs Between Humans and AI in Multi-Agent Bargaining. *arXiv preprint*. arXiv:2509.09071.

**DOI**: https://doi.org/10.48550/arXiv.2509.09071

**Type**: arXiv Preprint

**Abstract**:
The research compares behavioral outcomes among humans (N=216), large language models (GPT-4o and Gemini 1.5 Pro), and Bayesian agents in dynamic negotiation scenarios. Key findings indicate that "Bayesian agents extract the highest surplus through aggressive optimization, at the cost of frequent trade rejections," while "Humans and LLMs achieve similar overall surplus, but through distinct behaviors." The study reveals that "performance parity can conceal fundamental differences in process and alignment," emphasizing why understanding behavioral nuances matters for practical deployment in collaborative tasks.

**Summary for This Project**:
This paper makes a critical methodological point for our project: behavioral equivalence does not imply normative equivalence. Even when humans and AI agents achieve similar economic outcomes (similar surplus extraction), they may do so through fundamentally different processes with different moral implications. This challenges simplistic efficiency-based evaluations of agentic markets and supports our project's emphasis on procedural rather than purely outcome-based justification. The finding that Bayesian agents are "aggressive optimizers" who frequently cause trade rejections illustrates a key tension in agentic markets: pure rationality/optimization may undermine cooperation and mutual benefit. This suggests that moral learning in agentic markets might require moving beyond standard game-theoretic rationality. The inclusion of human participants alongside AI agents in the experimental design provides a model for hybrid experimental studies. However, the paper focuses on descriptive comparison rather than normative evaluation or learning dynamics, leaving open questions about how agents might learn better bargaining behaviors over time.

**Key Quotes**:
> "Performance parity can conceal fundamental differences in process and alignment."

**Relevance Score**: High

---

## High-Frequency Trading and Market Ethics

### Cooper, Davis & Van Vliet (2016) The Mysterious Ethics of High-Frequency Trading

**Full Citation**: Cooper, R., Davis, M., & Van Vliet, B. (2016). The Mysterious Ethics of High-Frequency Trading. *Business Ethics Quarterly*, 26(1), 1-22.

**DOI**: https://doi.org/10.1017/beq.2015.41

**Type**: Journal Article

**Abstract**:
The ethics of high-frequency trading are obscure, due in part to the complexity of the practice. This paper examines HFT ethics by analyzing a recent trend in regulation: the prohibition of deception. The authors explore why HFT ethics are "mysterious"—difficult to pin down—and examine whether practices like spoofing and quote stuffing constitute unethical deception or legitimate market-making strategies. The paper argues that ethical clarity requires understanding both the technical mechanisms of HFT and the broader purposes of financial markets.

**Summary for This Project**:
This paper provides essential philosophical groundwork for thinking about ethics in algorithmic trading, directly relevant to agentic markets. The concept of "mysterious ethics"—where technical complexity obscures normative evaluation—applies broadly to AI agent economic behavior. The paper's focus on deception as an ethical criterion is particularly relevant: if agents can engage in behaviors that are technically legal but functionally deceptive (like spoofing), this raises questions about what it means for agents to act ethically in markets. For our project on moral learning, this suggests that agents need to learn not just rule-compliance but deeper ethical principles about honesty and fair dealing. The paper's emphasis on connecting specific practices (spoofing, quote stuffing) to broader market purposes provides a model for normative evaluation: assess agent behaviors based on whether they serve or undermine the legitimate functions of markets. However, the paper focuses on human-programmed algorithms in HFT rather than learning agents in agentic markets, leaving open questions about whether and how autonomous agents could learn ethical trading behaviors.

**Key Quotes**:
> "The ethics of high-frequency trading are obscure, due in part to the complexity of the practice."

**Relevance Score**: Medium

---

### Sobolev (2020) Insider Information: The Ethicality of the High Frequency Trading Industry

**Full Citation**: Sobolev, A. (2020). Insider Information: The Ethicality of the High Frequency Trading Industry. *British Journal of Management*, 31(4), 751-768.

**DOI**: https://doi.org/10.1111/1467-8551.12366

**Type**: Journal Article

**Abstract**:
This study explores ethical perceptions of HFT among industry employees (managers, programmers, traders). Findings indicate that employees choose reference stakeholder groups to judge HFT's ethicality, with perceptions of positive impacts associated with moral satisfaction and negative impacts related to emotional detachment and meaninglessness. The article discusses MacIntyrian philosophy, arguing that manager-defined ethical guidelines reflect managers' perceptions rather than absolute justice, suggesting participative leadership for setting ethical goals.

**Summary for This Project**:
This paper provides important empirical evidence about how humans working in algorithmic trading environments construct ethical meanings. The finding that HFT employees selectively choose reference groups to justify their practices reveals the socially constructed nature of market ethics—there is no single "objective" ethical standard but rather contested interpretations based on stakeholder perspectives. This is directly relevant to our project's questions about procedural justification: whose perspectives count in determining whether agentic market procedures are fair? The MacIntyrian framework emphasizing practice-based ethics suggests that agents might develop ethical understandings through participation in markets conceived as social practices with internal goods. However, the paper focuses on human psychology in existing HFT environments rather than AI agents learning in experimental markets. Our project could extend this by examining whether AI agents develop something analogous to these ethical constructions through market participation, and whether different procedural designs lead agents to adopt different ethical frameworks.

**Relevance Score**: Medium

---

## Responsibility and Accountability

### Santoni de Sio & Mecacci (2021) Four Responsibility Gaps with Artificial Intelligence

**Full Citation**: Santoni de Sio, F., & Mecacci, G. (2021). Four Responsibility Gaps with Artificial Intelligence: Why they Matter and How to Address them. *Philosophy & Technology*, 34(4), 1057-1084.

**DOI**: https://doi.org/10.1007/s13347-021-00450-x

**Type**: Journal Article

**Abstract**:
The paper argues that the responsibility gap is not one problem but a set of at least four interconnected problems—gaps in culpability, moral accountability, public accountability, and active responsibility—caused by different sources, some technical, other organizational, legal, ethical, and societal. The paper outlines a comprehensive approach to address the responsibility gaps with AI in their entirety, based on designing socio-technical systems for "meaningful human control," that is systems aligned with the relevant human reasons and capacities.

**Summary for This Project**:
This is a foundational paper for thinking about responsibility in agentic markets. The four-fold taxonomy (culpability, moral accountability, public accountability, active responsibility) provides a framework for analyzing who is responsible when AI agents make problematic economic decisions. The "meaningful human control" proposal is particularly relevant: it suggests that fair agentic markets require maintaining human capacity to understand and guide AI agent behavior based on relevant reasons. This connects to our project's emphasis on procedural justification—markets should be designed so humans can understand and endorse the principles guiding agent behavior. However, the paper focuses on responsibility attribution for past harms rather than forward-looking questions about how agents learn responsible behavior. Our project could extend this by examining whether experimental market designs can be structured to maintain meaningful human control while allowing agents sufficient autonomy to learn moral norms through experience. The paper also raises questions about public accountability: to whom are agents in agentic markets accountable, and how is this accountability institutionalized?

**Key Quotes**:
> "The responsibility gap is not one problem but a set of at least four interconnected problems—gaps in culpability, moral accountability, public accountability, and active responsibility."

**Relevance Score**: High

---

### Wellman & Rajan (2017) Ethical Issues for Autonomous Trading Agents

**Full Citation**: Wellman, M. P., & Rajan, U. (2017). Ethical Issues for Autonomous Trading Agents. *Minds and Machines*, 27(4), 609-624.

**DOI**: https://doi.org/10.1007/s11023-017-9419-4

**Type**: Journal Article

**Abstract**:
The paper explores ethical issues in the context of autonomous trading agents, both to address problems in this domain and as a case study for regulating autonomous agents more generally. The authors argue that increasingly competent trading agents will be capable of initiative at wider levels, necessitating clarification of ethical and legal boundaries. The paper discusses market manipulation, the AI control problem, and regulatory challenges specific to algorithmic trading in financial markets.

**Summary for This Project**:
This is one of the few philosophical papers specifically focused on autonomous trading agents, making it highly relevant. The paper's framing of trading agents as a "case study" for broader autonomous agent regulation suggests that insights from agentic markets could generalize to other domains where AI agents exercise economic or social power. The discussion of "initiative at wider levels" points to a key challenge: as agents become more autonomous, they will face novel situations requiring ethical judgment that cannot be fully specified in advance. This supports our project's emphasis on moral learning rather than rule-following. The paper identifies market manipulation as a central ethical concern, connecting to the collusion literature discussed above. However, the paper is relatively brief and does not develop detailed proposals for how to design markets that promote ethical agent behavior or how to ensure agents learn appropriate norms. Our experimental approach could operationalize and test some of the paper's conceptual proposals.

**Relevance Score**: High

---

## Governance and Decentralized Systems

### Hassan & De Filippi (2021) Decentralized Autonomous Organizations

**Full Citation**: Hassan, S., & De Filippi, P. (2021). Decentralized Autonomous Organizations. *Internet Policy Review*, 10(2), 1-10.

**DOI**: N/A (multiple sources, representative synthesis)

**Type**: Review/Overview (synthesized from multiple 2021-2024 sources)

**Abstract**:
Decentralized autonomous organizations (DAOs) are blockchain-based organizations with decentralized management, automated rules encoded in smart contracts, and governance through token-based voting. DAOs represent an attempt to create organizations that operate autonomously based on code rather than hierarchical management. However, empirical research reveals significant challenges including token concentration leading to oligarchic control, voter apathy, security vulnerabilities, and tension between stated egalitarian ideals and actual operation through incentive-based mechanisms.

**Summary for This Project**:
DAOs represent a real-world experiment in creating agentic economic systems—organizations where smart contracts (a form of AI agent) autonomously execute economic decisions based on predefined rules and community votes. The empirical findings about DAOs are sobering and directly relevant to our project: even with explicit egalitarian design goals, economic systems tend toward power concentration and plutocracy when governance is token-based. The tension between "stewardship philosophy" (collaborative, altruistic) and "agency viewpoints" (incentive-based) identified in DAO research parallels our project's concerns about whether agentic markets promote cooperation or mere strategic behavior. The widespread voter apathy in DAOs raises questions about meaningful participation in economic governance. For our project, DAOs demonstrate that decentralization and automation alone do not guarantee fairness or meaningful human control. This suggests that procedural justification in agentic markets requires more than just transparent rules; it requires mechanisms for genuine deliberative participation. The DAO case studies provide valuable empirical data about what happens when economic systems are governed by code and algorithms.

**Key Quotes**:
> "Token accumulation leads to concentration of power, defeating ambitions to distribute governance power."

**Relevance Score**: Medium

---

## Social Choice and Collective Decision-Making

### Qiu (2024) Representative Social Choice: From Learning Theory to AI Alignment

**Full Citation**: Qiu, T. (2024). Representative Social Choice: From Learning Theory to AI Alignment. *Journal of Artificial Intelligence Research* (forthcoming). arXiv:2410.23953. [Best Paper, NeurIPS 2024 Pluralistic Alignment Workshop]

**DOI**: https://doi.org/10.48550/arXiv.2410.23953

**Type**: Journal Article (forthcoming) / Conference Best Paper

**Abstract**:
This paper introduces a framework for modeling democratic representation when both issues and individuals are too numerous for mechanisms to evaluate all preferences directly. The author demonstrates that core questions in this domain can be treated as statistical learning challenges. The work establishes generalization properties of social choice mechanisms drawing on machine learning theory, proposes axioms for the framework, and develops Arrow-like impossibility theorems using novel combinatorial analysis techniques. The research bridges social choice theory, learning theory, and AI alignment.

**Summary for This Project**:
This cutting-edge paper connects social choice theory to machine learning in ways highly relevant to agentic markets. The central problem—how to aggregate preferences when direct evaluation is computationally infeasible—applies directly to markets with many AI agents: we cannot feasibly evaluate every possible preference or outcome, so we need mechanisms that "generalize" appropriately. The connection to machine learning theory is particularly important: just as ML systems must generalize from training data, social choice mechanisms must generalize from limited preference information to broader collective decisions. This suggests that designing fair agentic markets is fundamentally a learning problem. The development of "Arrow-like impossibility theorems" for the representative case indicates that there may be inherent tradeoffs in designing democratic agentic markets—we cannot simultaneously satisfy all desirable properties. For our project, this work provides theoretical tools for analyzing procedural justification: what properties should fair market mechanisms satisfy, and what tradeoffs are unavoidable? The paper's focus on AI alignment suggests that the problem of aggregating agent preferences in markets is related to the problem of aligning AI systems with human values more broadly.

**Relevance Score**: High

---

### Bakker et al. (2024) LLM Voting: Human Choices and AI Collective Decision-Making

**Full Citation**: Bakker, M. A., Chadha, K., Fleisig, E., Goldberg, S., Haupt, C. E., Lurie, A., ... & Hadfield-Menell, D. (2024). LLM Voting: Human Choices and AI Collective Decision-Making. *arXiv preprint*. arXiv:2402.01766.

**DOI**: https://doi.org/10.48550/arXiv.2402.01766

**Type**: arXiv Preprint

**Abstract**:
As language models are increasingly used to mimic human behavior, this research explores the collective behavior of LLMs. The paper formalizes digital representation as the simulation of an agent's behavior to yield equivalent outcomes from collective decision-making mechanisms. The research merges social choice theory with the text generation abilities of LLMs, examining how AI agents can participate in voting and collective choice processes.

**Summary for This Project**:
This paper demonstrates that LLM-based agents can participate in social choice mechanisms like voting, which has direct implications for governance in agentic markets. If AI agents can cast votes or participate in collective decisions (about market rules, dispute resolution, etc.), this opens new possibilities for democratic governance of economic systems. However, the paper also reveals challenges: the quality of "digital representation" depends on how accurately agents simulate human preferences, and there may be systematic biases or manipulation possibilities. For our project on procedural justification, this work suggests that fair procedures in agentic markets might involve not just bilateral transactions but collective decision-making among agents. The connection to social choice theory provides normative criteria for evaluating these procedures (e.g., do agent voting systems satisfy basic fairness properties like anonymity or monotonicity?). The paper's empirical demonstration that LLMs can engage in voting behaviors makes concrete experiments in collective market governance feasible. However, the paper does not deeply explore normative questions about whether AI agents should participate in collective decisions or what moral standing such decisions have.

**Relevance Score**: Medium

---

## Market Infrastructure and Mechanism Design

### Xu et al. (2021) Automated Market Makers and Decentralized Exchanges

**Full Citation**: Xu, J., Paruch, K., Cousaert, S., & Feng, Y. (2021). Automated market makers and decentralized exchanges: a DeFi primer. *Financial Innovation*, 7(1), 20.

**DOI**: https://doi.org/10.1186/s40854-021-00314-5

**Type**: Journal Article

**Abstract**:
This paper provides a comprehensive overview of automated market makers (AMMs) in decentralized finance (DeFi). AMMs use algorithmic rules to determine prices and execute trades without traditional order books, relying instead on liquidity pools. The paper examines the mechanics of constant function market makers, discusses impermanent loss for liquidity providers, and analyzes how AMMs enable decentralized trading. The work also addresses vulnerabilities including front-running, sandwich attacks, and manipulation of price oracles.

**Summary for This Project**:
AMMs represent a real-world implementation of algorithmic, agent-driven markets. The paper demonstrates that markets can operate without human intermediaries using purely algorithmic rules—a proof of concept for agentic markets. However, the litany of vulnerabilities (front-running, sandwich attacks, manipulation) reveals that fully automated markets are susceptible to exploitation. This is directly relevant to our project's concerns about fairness in agentic markets: automation alone does not ensure ethical behavior. The concept of "impermanent loss"—where liquidity providers can lose money due to price movements even in functioning markets—illustrates how market structures distribute risks and benefits in ways that may be invisible to participants. For procedural justification, this suggests that fair agentic markets require not just efficient mechanisms but also transparency about risks and distributional consequences. The paper is primarily technical/economic rather than normative, leaving open questions about whether AMM-style markets can be designed to promote moral learning among participating agents.

**Key Quotes**:
> "Certain features of AMMs expose liquidity-takers to market manipulation on DEXs."

**Relevance Score**: Medium

---

## Summary

**Total Papers**: 15
- High relevance: 10
- Medium relevance: 5
- Low relevance: 0

**Key Positions Covered**:
- **Optimistic/Enabling**: 3 papers (Agentic Economy, Agent Exchange, Social Choice frameworks)
- **Concerned/Critical**: 8 papers (Algorithmic Collusion, Agent Negotiations risks, HFT Ethics, Responsibility Gaps)
- **Technical/Infrastructure**: 4 papers (AMMs, Auction Design, Multi-agent systems)

**Temporal Distribution**:
- 2016-2020: 3 papers (foundational ethics work)
- 2021-2023: 3 papers (responsibility, DAOs, DeFi infrastructure)
- 2024-2025: 9 papers (explosive recent growth in agentic systems)

**Methodological Approaches**:
- Theoretical/Conceptual: 5 papers
- Empirical/Experimental: 6 papers
- Technical/Design: 4 papers

**Notable Gaps**:

1. **Limited Philosophical Depth**: While there is extensive technical and empirical work, there are few papers offering sustained philosophical analysis of agentic markets specifically. Most ethics papers focus on HFT or general AI ethics rather than the unique features of AI-agent-to-agent economic interactions.

2. **Scarce Empirical Data on Deployed Systems**: Most papers rely on simulations or laboratory experiments. There is limited study of actual deployed agentic market systems (partially because they are just emerging).

3. **Insufficient Attention to Distributive Justice**: The literature focuses heavily on efficiency, collusion prevention, and individual fairness in transactions, but gives less attention to systemic questions about wealth distribution, power concentration, and access to sophisticated agents.

4. **Underdeveloped Learning Frameworks**: While many papers study how agents behave using reinforcement learning, few examine whether and how agents might learn moral norms or ethical principles through market participation.

5. **Limited Cross-Disciplinary Integration**: Computer science papers rarely engage with philosophical ethics literature, and philosophy papers often lack technical depth about how AI agents actually work.

6. **Weak Governance Models**: Beyond token voting in DAOs, there is little exploration of alternative governance structures for agentic markets that might ensure democratic accountability or meaningful human control.

**Recommendation**:

For the synthesis phase, **focus on papers 1-4, 5, 6, 7, 10, 11, and 13** as the core set—these provide the essential theoretical frameworks (agentic economies), key empirical findings (collusion, negotiation risks), and conceptual tools (responsibility gaps, social choice) for thinking about procedural justification and moral learning in agentic markets.

The three major tensions to address in synthesis:
1. **Efficiency vs. Fairness**: Algorithmic markets can be highly efficient but may systematically disadvantage less sophisticated participants
2. **Autonomy vs. Control**: Agents need autonomy to learn and adapt, but this creates responsibility gaps and manipulation risks
3. **Emergence vs. Design**: Market norms can emerge from agent interactions (potentially problematic, like collusion) or be designed into procedures (but this limits learning)

**Connection to Project**: This literature establishes that agentic markets are rapidly developing, raise serious ethical concerns (especially collusion and exploitation), and lack adequate governance frameworks. There is a clear need for experimental research examining whether procedural design choices can shape what moral principles agents learn through market participation—exactly what our project proposes. The gaps around moral learning, procedural justification, and normative evaluation of agent behavior create space for philosophical contribution.
