# Section 7: Synthesis and the Dilemma Gap

## The Current Landscape

Our review of 95 papers across six domains reveals sophisticated, specialized scholarship on intersectional fairness. The machine learning community has documented technical challenges of handling sparse intersectional data, developed innovative solutions ranging from multicalibration to hierarchical methods, and demonstrated both the promise and limitations of algorithmic approaches (Section 2). Philosophers have provided rich analyses of intersectionality's metaphysical foundations, revealing deep disagreements about what intersectionality is and what it requires (Section 3). Measurement theorists have shown how operationalization embeds ontological commitments and how construct validity failures undermine fairness claims (Section 4). Normative theorists have offered frameworks from prioritarianism to sufficientarianism for evaluating fairness trade-offs (Section 5). Epistemologists have analyzed different forms of uncertainty, epistemic justice, and the epistemic responsibilities of making inferences about groups (Section 6).

Each literature has advanced understanding within its domain. Yet examining these literatures together reveals a systematic gap: the absence of work recognizing that statistical uncertainty and ontological uncertainty *interact* to create a genuine dilemma for intersectional fairness. We now make this gap explicit.

## The Two Horns: Separately Recognized, Never Joined

### Horn 1: Statistical Uncertainty (Well-Documented)

The technical literature thoroughly documents that more intersectional groups create statistical challenges:

- Exponential growth: With k binary attributes, there are 2^k possible intersectional groups (Sheng et al. 2025; Celis et al. 2022)
- Data sparsity: More groups mean fewer observations per group, increasing sampling variance (Gohar and Cheng 2023; Maheshwari et al. 2024)
- Sample complexity: Multicalibration and similar guarantees require sample sizes that grow exponentially with groups (Hébert-Johnson et al. 2018; Dwork et al. 2024)
- Practical infeasibility: "Attaining multicalibration is practically infeasible with more than a few classes" (Dwork et al. 2024); "assessing group fairness with respect to multiple sensitive attributes may be unfeasible in most practical cases" (Celis et al. 2022)
- Epistemic uncertainty: Small samples create high epistemic uncertainty about group properties (Hüllermeier and Waegeman 2021)

This horn is well-established: more groups make statistical estimation less reliable. The technical community recognizes this as a fundamental challenge.

### Horn 2: Ontological Uncertainty (Well-Documented)

The philosophical literature thoroughly documents uncertainty about which groups exist and matter:

- Definitional dilemmas: "Intersectionality's definitional dilemmas" reflect "tensions between different interpretations and uses" (May 2014)
- Competing metaphysics: Intersectionality understood variously as causal (Bright et al. 2016), emergent (Jorba and López de Sa 2024), non-additive (Hancock 2007), metaphorical/heuristic/paradigmatic (Garry 2011)
- Social ontology debates: Groups understood as attribute-based (Epstein 2019), practice-based (Sveinsdóttir 2013), structurally constituted (Haslanger 2012), context-dependent (Sterba 2024)
- Contested categories: No philosophical consensus on what constitutes gender, race, or their intersections (Haslanger and Ásta 2017; Thomasson 2019)
- Multiple frameworks: Anticategorical, intracategorical, and intercategorical approaches to intersectionality suggest different group specifications (McCall 2005)

This horn is also well-established: there is no settled philosophical answer to "which intersectional groups exist and warrant consideration?" Different theoretical frameworks suggest different answers.

## The Missing Link: Interaction and Dilemma

Despite thorough documentation of each horn separately, no existing work frames these as *interacting* problems that together constitute a genuine dilemma. The gap is not that either problem is unrecognized—both are well-recognized within their respective literatures. The gap is the absence of recognition that these problems mutually exacerbate each other in a way that creates a dilemma where "solving" one horn worsens the other.

### The Interaction (Unrecognized)

The interaction works in both directions:

**Ontological → Statistical**: Philosophical considerations suggest including many intersectional groups (because intersectionality involves emergent properties, context-dependent effects, non-additive interactions), but including more groups worsens the statistical problem. If we take seriously the philosophical insight that Black women's experiences are not reducible to Black experiences plus women's experiences (Bowleg 2008; Hancock 2007), we must include "Black women" as a distinct group. If we extend this to all intersections of all attributes, we face exponential growth in groups—precisely the statistical problem documented in Section 2. Philosophical rigor about intersectionality creates statistical infeasibility.

**Statistical → Ontological**: Statistical constraints push toward including fewer groups (to maintain adequate sample sizes and estimation reliability), but reducing the number of groups requires principled answers to ontological questions about which groups to exclude. Should we exclude groups below a minimum sample size? But size thresholds arbitrarily privilege frequent groups over rare ones. Should we use hierarchical methods focusing on "parent" groups? But determining the hierarchy requires answering which categories are fundamental—an ontological question without consensus answers. Should we only include groups identified by domain experts or communities? But different experts and communities may identify different groups, and their identification criteria may conflict with available data structures. Every statistical solution that constrains the number of groups implicitly or explicitly makes ontological commitments about which groups truly matter—commitments that the philosophical literature shows are deeply contested.

### Why This Is a Genuine Dilemma

A dilemma is not merely the co-presence of two problems. It is a situation where addressing one problem exacerbates the other, such that there is no straightforward solution that resolves both. The statistical-ontological interaction in intersectional fairness exhibits this structure:

1. **Attempting to resolve the statistical problem by constraining groups**: Statistical methods work better with fewer, larger groups. One might try to resolve the statistical horn by limiting which intersectional groups to include—perhaps only groups above a minimum sample size, or only "major" intersections. But any such constraint requires answering: which groups should be excluded? This reintroduces the ontological horn in acute form, as the exclusion decision requires principled ontological commitments about which groups are real/important enough to include. And as the philosophical literature shows (Section 3), there are no uncontested answers. Different ontological frameworks suggest different groups. The statistical constraint does not dissolve the ontological uncertainty; it makes it practically urgent.

2. **Attempting to resolve the ontological problem by including all groups**: One might try to resolve the ontological horn by being maximally inclusive—include all intersectional groups definable from available attributes. This defers to a kind of ontological pluralism: if there's disagreement about which groups exist, include them all. But this approach maximally exacerbates the statistical horn. With k binary attributes, including all 2^k intersectional groups creates exponential data sparsity. As documented in Section 2, fairness methods become "practically infeasible" with more than a few intersections (Dwork et al. 2024). Ontological inclusivity purchases statistical infeasibility.

3. **Attempting to resolve both through compromise**: One might try intermediate positions—include more groups than simple demographic marginals but fewer than all possible intersections. But any intermediate position still requires answers to both problems: *which* intermediate set of groups (ontological question)? *How many* groups can be reliably handled (statistical question)? And crucially, the compromise must navigate the interaction: ontological considerations about which groups are most important may conflict with statistical considerations about which groups have adequate data. Intersectional groups identified as most important by critical theory (e.g., Black transgender women) may be precisely those with sparsest data. The compromise cannot independently satisfy both constraints—it involves trading off ontological desiderata against statistical desiderata.

4. **The mutual exacerbation**: Each problem makes the other worse. The statistical problem is worse because there are ontologically many groups that matter (not just one or two intersections but potentially hundreds). The ontological problem is worse because statistical constraints create pressure to exclude groups—but principled exclusion requires resolving ontological debates. If there were consensus on ontology (e.g., only ten specific intersectional groups truly matter), the statistical problem would be manageable. If statistical methods could handle unlimited groups, the ontological uncertainty would not create practical bottlenecks. But absent consensus and absent unlimited statistical power, the problems interact to create a dilemma.

## Existing Work That Comes Closest (But Stops Short)

Several papers approach the dilemma without fully recognizing it:

**Jacobs and Wallach (2021)** make the crucial observation that "fairness itself is an essentially contested construct with different theoretical understandings in different contexts" and that "debates that appear to be about different operationalizations are actually debates about different theoretical understandings." This analysis could extend to groups: debates about which intersectional groups to include are not just technical (which attribute combinations?) but theoretical (what makes something a group warranting fairness consideration?). However, they do not make this extension, and critically, they do not connect theoretical contestedness to statistical consequences. Their framework addresses measurement validity independently of statistical feasibility.

**Celis et al. (2022)** note that "assessing group fairness with respect to multiple sensitive attributes may be unfeasible in most practical cases" and that "the presence of many sensitive features is more of a norm than an exception, [which] represents a huge problem that the literature on fairness in ML has barely begun to address." They recognize the statistical infeasibility of many groups but frame this as a technical challenge requiring better methods. They do not connect it to ontological debates about which groups exist or explore how ontological considerations might justify constraining or expanding the group set.

**Gohar and Cheng (2023)** provide a comprehensive survey noting that "current research overlooks the under-representation of intersectional groups by solely focusing on achieving parity, and more research on non-distributive intersectional fairness is needed." They identify that standard approaches inadequately address intersectionality but frame this as a gap requiring more research—not as a dilemma where ontological and statistical constraints interact.

**Jorba and López de Sa (2024)** develop a sophisticated philosophical account of "intersectionality as emergence," arguing that "intersectional experiences emerge from the conjunction of social categories when social structures make them relevant." Their emergence view has implications for group specification (which conjunctions are relevant? in which contexts?), but they do not discuss implications for statistical estimation. The philosophical analysis proceeds without acknowledging that treating intersectionality as emergent and context-dependent (ontologically) makes determining which groups to analyze statistically highly complex.

**Bright, Malinsky, and Thompson (2016)** show that intersectionality can be interpreted through causal models, making "claims about causal effects of occupying intersecting identity categories" empirically testable. Their approach promises to bridge philosophy and data science. However, they do not address the practical challenge that testing causal effects for all possible intersecting categories requires data that may not exist, or that the set of categories to model must itself be specified—returning us to the ontological question.

**Hüllermeier and Waegeman (2021)** distinguish epistemic from aleatoric uncertainty, noting that "epistemic uncertainty reflects uncertainty due to limited sample size." They recognize that small groups have high epistemic uncertainty. However, they do not connect this to the ontological question of *which* groups exist and thus which groups we should work to reduce epistemic uncertainty for. Their epistemological framework is developed independently of social ontology.

None of these papers—individually excellent—frame the situation as a dilemma arising from interaction between statistical and ontological problems. Each analyzes one dimension without fully engaging the other or recognizing their mutual exacerbation.

## What Would Recognition of the Dilemma Look Like?

Recognition would involve:

1. **Acknowledging both horns**: Not treating either as solved or solvable independently
2. **Analyzing the interaction**: Showing how ontological choices have statistical consequences and statistical constraints require ontological decisions
3. **Framing as dilemma**: Recognizing that standard solutions (technical improvements, conceptual clarification) do not dissolve the fundamental tension
4. **Interdisciplinary approach**: Bringing together computer science, philosophy, measurement theory, normative theory, and epistemology to address the interaction rather than delegating separate problems to separate fields

## The Gap and the Contribution

The gap this review identifies is not that individual literatures are deficient within their domains. It is that the organization of scholarship into separate domains—each with its own methods, venues, and conceptual frameworks—has created a systematic blind spot regarding the interaction. Machine learning researchers assume groups can be specified and focus on statistical challenges. Philosophers analyze intersectionality's nature without considering statistical constraints. Measurement theorists examine construct validity independently of sample size requirements. Normative theorists propose distributive principles without addressing feasibility given ontological uncertainty and statistical limitations. Epistemologists analyze uncertainty without fully integrating ontological and statistical sources.

The systematic nature of this blind spot suggests it is not accidental. Interdisciplinary problems at the boundary of multiple fields can fall between disciplinary cracks, with each field assuming the other has solved its piece. Here, technical researchers assume philosophy provides the groups, philosophers assume technical methods can handle whatever groups exist, measurement theorists assume both problems can be solved separately, normative theorists assume both are solved before normative principles apply, and epistemologists analyze the result without interrogating the interactive genesis of epistemic uncertainty.

The contribution of framing intersectional fairness as a genuine dilemma—arising from the interaction of statistical uncertainty and ontological uncertainty—is to name this blind spot, demonstrate its systematic nature across multiple literatures, and suggest that incremental progress within existing frameworks may not resolve the fundamental challenge. If the dilemma is genuine, what is needed is not better statistical methods (though those help) or clearer ontology (though that helps) or more valid measurement (though that helps) but fundamentally new approaches that grapple directly with the interaction.

**Flag for the Dilemma**: This section establishes the core finding: existing scholarship thoroughly documents the statistical problem (more groups → less reliability) and the ontological problem (unclear which groups exist/matter), but no existing work recognizes these as interacting problems forming a genuine dilemma. The interaction is the gap. Machine learning proceeds as if groups are given; philosophy proceeds as if statistical constraints don't matter; measurement, normative theory, and epistemology proceed as if both problems can be addressed separately. The dilemma framing is novel: it names an interaction that has been systematically overlooked across multiple literatures, despite each literature providing pieces of the puzzle. Recognizing the interaction as a dilemma reframes the challenge from "solve the statistical problem with better methods and solve the ontological problem with clearer concepts" to "grapple with the interaction where solving one exacerbates the other."
