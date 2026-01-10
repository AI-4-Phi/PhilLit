# Synthesis: The Intersectionality Dilemma

The preceding sections have documented sophisticated research on intersectional fairness across multiple disciplines. Machine learning researchers have developed impressive technical solutions to data sparsity. Philosophers have illuminated deep ontological questions about the nature of groups. Measurement theorists have shown how operationalization embeds ontological commitments. Normative ethicists have analyzed competing frameworks for distributive justice. Epistemologists have examined questions of authority and responsibility. Yet critically, *no existing work synthesizes these insights to reveal that intersectional fairness involves a genuine dilemma* where statistical and ontological uncertainties interact to create a problem that cannot be solved through progress in any single domain.

## The Dilemma Structure

The dilemma has two horns, each involving a distinct form of uncertainty, and these horns interact such that progress on one exacerbates problems on the other.

**Horn 1: Statistical Uncertainty.** Evaluating algorithmic fairness across intersectional groups requires estimating performance metrics (error rates, calibration, predictive parity) for each group. As groups become more fine-grained through intersectional specification, they become smaller in available datasets. Small groups yield unreliable performance estimates with high variance and wide confidence intervals. The epistemic uncertainty about whether a group is being treated fairly increases as group size decreases. At the limit, groups with only a handful of members provide essentially no information about systematic algorithmic behavior toward that group. The statistical challenge is well-documented: multicalibration sample complexity grows exponentially with the number of groups (Hébert-Johnson et al. 2018), conditional demographic parity becomes infeasible with many conditioning variables (Castelnovo et al. 2022), and sparse subgroups undermine fairness evaluation (Yan et al. 2024; Sheng et al. 2025).

The standard technical response is to constrain the set of groups $G$ to those with sufficient data for reliable estimation. Limit intersectional analysis to groups above some minimum size threshold. Use only two-way intersections (race × gender) rather than three-way or four-way. Focus on groups with at least 100 members, or 500, or whatever threshold provides adequate statistical power. This response appears reasonable—we should not make claims about groups when evidence is insufficient. It leads to Horn 2.

**Horn 2: Ontological Uncertainty.** Which groups should be included in $G$? Which intersections of protected attributes constitute meaningful groups warranting fairness consideration? Sections 3–6 established that this question has no determinate answer; it depends on contested philosophical commitments about social ontology, normative frameworks for justice, and epistemic authority.

Different ontological frameworks give different answers. Attribute-based accounts suggest that any combination of protected attributes defines a group (all individuals with race=Black AND gender=Female AND age>65 form a group). Practice-based or structural accounts suggest that groups emerge from social practices and cannot be exhaustively enumerated through attribute combinations—we must identify which specific intersections correspond to meaningful social groups in particular contexts. Emergentist accounts emphasize that intersectional experiences are non-additive, arising from social structures that make certain combinations salient in ways that resist algorithmic specification.

Different normative frameworks give different answers. Egalitarianism suggests we should consider all groups equally, implying comprehensive intersectional specification. Prioritarianism suggests we should focus on worst-off groups, which requires first identifying them (raising the statistical problem). Sufficientarianism suggests we should ensure all groups meet adequacy thresholds, which requires first determining which groups exist.

Different epistemic frameworks give different answers. Epistemic justice considerations suggest affected communities should help determine which groups warrant consideration, but affected communities may disagree among themselves and with researchers. Epistemic responsibility suggests we should only track groups for which we have adequate data, but this defers to statistical considerations.

Constraining $G$ to address statistical problems (Horn 1) requires principled criteria for which groups to exclude. But providing such criteria requires resolving these contested ontological, normative, and epistemic questions. There is no neutral, uncontroversial basis for determining which intersectional groups to omit. Any choice embeds substantive philosophical commitments that reasonable people dispute.

**The Interaction.** The horns interact to create a genuine dilemma. Expanding $G$ to respect ontological complexity (include more intersectional groups, recognize that groups cannot be exhaustively specified through simple combinations, acknowledge normative requirements to consider vulnerable groups) exacerbates statistical problems. Each additional group reduces average group size, increasing estimation uncertainty and making it harder to detect genuine discrimination or confirm fairness. Conversely, constraining $G$ to handle statistical limitations (include only large groups, use only two-way intersections, exclude groups below sample size thresholds) requires ontological and normative judgments about which groups not to consider—judgments that are deeply contested.

This interaction means that progress on one horn tends to worsen the situation on the other. Technical advances that allow fair treatment of more groups (better multicalibration algorithms, synthetic data generation, hierarchical models) do not resolve the question of which groups to include. Philosophical progress clarifying the ontology of groups would not eliminate statistical constraints on how many groups we can reliably evaluate with finite data. The dilemma is not merely the conjunction of two difficult problems; it is their problematic interaction.

## What Existing Work Does and Doesn't Address

Having articulated the dilemma structure, we can now systematically assess what existing work contributes and where the gap lies.

**Machine Learning and Computer Science (Section 2).** This literature demonstrates sophisticated approaches to statistical challenges but uniformly treats $G$ as an input determined by available data attributes. When papers discuss challenges in specifying groups, they frame these as *computational* (exponential growth of combinations) or *statistical* (sparse data, sample complexity) rather than *ontological* (which combinations correspond to meaningful groups?) or *normative* (which groups should we prioritize?). Representative papers:

- Castelnovo et al. (2022) note that "assessing group fairness with multiple sensitive attributes may be unfeasible in most practical cases" due to exponential increase of subgroups, but frame this as a computational/practical issue, not an ontological question about which subgroups are meaningful.
- Hansen et al. (2024) conclude that "attaining multicalibration is practically infeasible with more than a few classes" but do not ask whether we should be considering all classes or how to select among them.
- Sheng et al. (2025) address "exponential growth of subgroups with finite samples" through a sparsity framework but do not question whether all subgroups warrant consideration.

No paper in this literature asks: "Given that we cannot evaluate all possible intersections due to data constraints, how should we decide which intersections to include?" The question is treated as answered by data availability rather than requiring ontological, normative, or epistemic justification.

**Philosophy of Intersectionality and Social Ontology (Section 3).** This literature establishes deep disagreement about what intersectional groups are and how they should be individuated but does not connect these debates to operational constraints. Representative contributions:

- Collins (2015) identifies "definitional dilemmas" in intersectionality scholarship but does not relate these to challenges in algorithmic fairness implementation.
- McCall (2005) distinguishes anticategorical, intracategorical, and intercategorical approaches, showing fundamental disagreement about how to understand categories in intersectional analysis. This directly bears on whether algorithmic systems can enumerate groups, but McCall does not address algorithmic contexts.
- Bright et al. (2016) versus Jorba and López de Sa (2024) represent competing ontologies (causal-combinatorial vs. emergentist) with different implications for group specification, but neither connects to statistical feasibility questions.
- Epstein (2019), Ritchie (2020), and Thomasson (2019) analyze the ontology of social groups without addressing how ontological frameworks should inform algorithmic fairness practice.

No philosophical work asks: "Given operational constraints on how many groups algorithmic systems can reliably evaluate, how should contested ontologies of groups inform practice?" The debates proceed at a level of abstraction that does not engage technical constraints.

**Measurement Theory (Section 4).** This literature shows that operationalization embeds ontological commitments and that construct validity depends on theoretical understanding. Jacobs and Wallach (2021) argue that fairness is an essentially contested construct with different valid operationalizations in different contexts, and that operationalization involves assumptions introducing potential mismatches. Scheuerman et al. (2020) show that demographic category operationalizations reflect often-implicit ontological commitments.

However, this literature does not frame the connection between ontology and operationalization as creating a dilemma when combined with statistical constraints. It identifies measurement challenges and validity questions but does not synthesize these with the statistical problems documented in ML literature or the ontological debates documented in philosophy. The insight that operationalization embeds ontology is profound but incomplete without connecting to the full dilemma structure.

**Normative Ethics (Section 5).** This literature establishes that different distributive justice frameworks imply different answers about which groups warrant consideration and how to handle trade-offs. Egalitarian, prioritarian, and sufficientarian frameworks yield incompatible guidance. However, no work connects this normative pluralism to the question of how normative frameworks should interact with statistical constraints.

Papers analyzing leveling down (Holm 2023; Mittelstadt et al. 2023) debate whether equality is worth achieving when it requires reducing performance for some groups, but they do not connect this to the question of which groups to include in fairness evaluation when data constraints prevent comprehensive evaluation. Normative frameworks are analyzed in isolation from operational and statistical realities.

**Epistemology (Section 6).** This literature illuminates epistemic justice questions (who decides which groups matter?) and epistemic responsibility questions (when is evidence sufficient?). But it does not connect these to the statistical challenge that evidence is inherently limited for small intersectional groups, nor to the ontological debates about how to individuate groups. Epistemic justice scholars emphasize including marginalized voices in determining categories but do not address what happens when including more groups exacerbates statistical problems.

## The Gap: No Dilemma Framing

The critical gap is that **no existing work frames the interaction between statistical and ontological uncertainty as a dilemma**. Papers addressing statistical challenges assume ontological questions have answers (groups are determined by data attributes). Papers addressing ontological questions do not consider statistical constraints. Papers on measurement, normativity, and epistemology provide crucial insights but do not synthesize them with statistical and ontological dimensions to reveal the dilemma structure.

Who comes closest to recognizing the dilemma? Several papers acknowledge partial aspects:

- Castelnovo et al. (2022) recognize that comprehensive intersectional specification is statistically infeasible but treat this as a practical limitation rather than revealing deeper ontological questions about which groups to prioritize.
- Jacobs and Wallach (2021) identify fairness as essentially contested, implying different contexts require different operationalizations, but do not connect this to group specification or statistical constraints.
- Collins (2015) identifies "definitional dilemmas" in intersectionality theory but does not apply this to algorithmic fairness.
- Bowleg (2008) discusses "methodological challenges of intersectionality research" in both qualitative and quantitative contexts, arguing that additive approaches fail to capture intersectional experiences, but does not frame this as a dilemma involving statistical-ontological interaction.

No work synthesizes the technical literature on data sparsity, the philosophical literature on contested ontologies, the measurement literature on construct validity, the normative literature on distributive justice, and the epistemic literature on authority and responsibility to show that these create a dilemma where improving along one dimension worsens others.

## Why This Matters

Framing intersectional fairness through the dilemma lens matters for several reasons. First, it explains why technical progress alone cannot solve the problem. Better multicalibration algorithms, improved synthetic data generation, and more sophisticated hierarchical models are valuable contributions, but they do not answer which groups to include in $G$. That question requires engaging contested ontological, normative, and epistemic terrain.

Second, it explains why philosophical progress alone cannot solve the problem. Even if philosophers reached consensus on the correct ontology of groups (which seems unlikely), statistical constraints would remain. We cannot achieve fairness across unlimited groups with finite data. Some prioritization or selection is necessary, which reintroduces normative and epistemic questions.

Third, recognizing the dilemma clarifies what kinds of responses are available. We cannot dissolve the dilemma through technical or philosophical breakthroughs. Instead, we must navigate it through context-specific judgment that acknowledges trade-offs, embraces pluralism about purposes and frameworks, and involves affected communities in determining which groups matter for particular applications. The dilemma does not have a solution; it has strategies for responsible navigation that acknowledge both horns.

Fourth, the dilemma framing positions intersectional fairness as a fundamentally interdisciplinary challenge requiring integration of technical, philosophical, normative, and epistemic insights. Neither computer scientists nor philosophers alone can adequately address it. Progress requires sustained collaboration across disciplines and with affected communities.

The gap this review has identified—the absence of work framing intersectional fairness as involving a statistical-ontological dilemma—represents the core contribution our research will make. By synthesizing insights across disciplines to articulate the dilemma structure, we provide a new framework for understanding why intersectional fairness is so challenging and what kinds of responses are appropriate. The next section concludes by positioning this contribution and outlining its implications.
