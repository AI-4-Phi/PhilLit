# Literature Review Plan: Housing Justice and Urban Planning from a Contractualist Perspective

## Research Idea Summary

This research examines when state coercion over housing and land use can be justified within Rawlsian contractualism. It identifies four key failings of standard contractualist theories: (1) the fungibility assumption about goods, (2) the occupancy vs. access trade-off, (3) housing's dual role as asset and necessity, and (4) epistemic duties regarding intergenerational planning under uncertainty.

## Key Research Questions

1. How should contractualist theories handle non-fungible, location-specific goods like housing?
2. Can contractualism resolve the tension between incumbent occupancy rights and newcomer access claims?
3. Does property-owning democracy applied to housing meet contractualist justifiability tests?
4. What epistemic duties do current generations owe future generations when making irreversible urban planning decisions?
5. How do agglomeration externalities and spatial economics inform contractualist housing policy?

## Literature Review Domains

### Domain 1: Contractualist Foundations and Justification

**Focus**: Core contractualist framework, especially Rawlsian contractualism and the structure of justification to all affected parties.

**Key Questions**:
- What are the justifiability requirements in contractualist theory?
- How does Rawls' framework of primary goods handle distributional questions?
- What are the limits of thin theories of the good in resolving policy questions?
- How do alternative contractualist frameworks (Scanlon, Gauthier) handle distributive justice?

**Search Strategy**:
- Primary sources: `search_sep.py` for "contractualism", "Rawls", "social contract", "original position"
- PhilPapers categories: Contractarianism, Rawls's Theory of Justice
- Key terms: ["contractualism", "reasonable rejection", "justifiability", "Rawls primary goods", "thin theory of good", "Scanlon contractualism"]
- Expected papers: 15-20 foundational works on contractualist structure

**Relevance to Project**: Establishes the theoretical framework and justifiability standards that the research applies to housing policy.

---

### Domain 2: Non-Fungible Goods and Location-Specific Value

**Focus**: How theories of distributive justice handle goods whose value is constituted by (not merely affected by) location; the fungibility assumption in Rawls, Dworkin, and capability approaches.

**Key Questions**:
- How do primary goods, equality of resources, and capabilities handle non-fungible goods?
- What distinguishes location-specific value from convertible positional value?
- Are there existing critiques of the fungibility assumption in distributive justice?
- How does the literature on special goods (cultural goods, relational goods) inform this?

**Search Strategy**:
- Primary sources: `search_sep.py` for "primary goods", "equality of resources Dworkin", "capabilities approach"
- Search terms: ["fungibility assumption", "non-fungible goods", "location-specific value", "positional goods", "local public goods", "spatial justice"]
- Use `s2_search.py` and `search_openalex.py` for interdisciplinary work on spatial economics and distributive justice
- Expected papers: 12-18 papers on metric goods, special goods, and spatial distribution

**Relevance to Project**: Directly addresses the first key failing (fungibility assumption) and provides theoretical resources for handling housing's location-specificity.

---

### Domain 3: Occupancy Rights vs. Access Claims

**Focus**: The "occupancy turn" in political philosophy (Stilz, Huber & Wolkenstein) and the tension between protection of existing residents and claims of newcomers/excluded populations.

**Key Questions**:
- What grounds occupancy rights to remain in place?
- How should access claims be weighted against occupancy claims?
- Does the occupancy literature provide principles for trade-offs?
- What does gentrification ethics contribute to this debate?
- How do displacement ethics inform contractualist justification?

**Search Strategy**:
- Primary sources: Stilz (2013), Huber & Wolkenstein (2018) - use `s2_search.py` to find these and citing papers
- Key terms: ["occupancy rights", "right to stay", "territorial rights", "gentrification ethics", "displacement", "right to the city", "access to place", "newcomer claims"]
- PhilPapers searches: "gentrification", "territorial rights"
- Use `s2_search.py --recent` for last 5 years of gentrification ethics
- Expected papers: 15-20 papers on occupancy, displacement, and gentrification

**Relevance to Project**: Directly addresses the second key failing (occupancy vs. access stand-off) and examines whether existing literature resolves or reproduces the deadlock.

---

### Domain 4: Property-Owning Democracy and Housing

**Focus**: Property-owning democracy (POD) as alternative to welfare state capitalism, specifically applications to housing and land; whether POD meets contractualist standards when applied to housing.

**Key Questions**:
- What are the core commitments of property-owning democracy?
- How has POD been applied to housing markets specifically?
- What is the relationship between POD and wealth accumulation via housing?
- Does POD require tenure neutrality or favor homeownership?
- Can POD justify housing price appreciation/suppression to affected parties?

**Search Strategy**:
- Primary sources: O'Neill & Williamson (2012) via `s2_search.py`; recent work by Erck (2024), Kerr (2019)
- Key terms: ["property-owning democracy", "POD housing", "wealth accumulation housing", "distributive justice housing", "asset-based welfare", "tenure neutrality"]
- `search_philpapers.py` for "property-owning democracy"
- Expected papers: 12-15 papers on POD theory and housing applications

**Relevance to Project**: Directly addresses the third key failing (housing as asset vs. necessity) and tests whether POD can resolve the dual-role tension under contractualist standards.

---

### Domain 5: Intergenerational Justice and Epistemic Duties

**Focus**: Obligations to future generations under uncertainty, especially regarding irreversible decisions; epistemic justice and option preservation vs. optimization.

**Key Questions**:
- What principles govern intergenerational obligations under uncertainty?
- How do option preservation approaches differ from optimization or satisficing?
- What epistemic duties do present generations owe future ones?
- How does epistemic justice literature (Fricker, Medina) inform planning under uncertainty?
- What role does irreversibility play in intergenerational obligations?

**Search Strategy**:
- Primary sources: `search_sep.py` for "intergenerational justice"; Gosseries (2009), Tremmel (2009) via `s2_search.py`
- Key terms: ["intergenerational justice", "future generations obligations", "option preservation", "irreversibility", "epistemic justice planning", "uncertainty future preferences", "non-identity problem"]
- Fricker (2007), Medina (2013) on epistemic justice - cite and find extensions to planning/policy
- Expected papers: 15-18 papers on intergenerational justice and epistemic duties

**Relevance to Project**: Directly addresses the fourth key failing (epistemic duties to future generations) and provides framework for justifying planning decisions under preference uncertainty.

---

### Domain 6: Urban Economics and Agglomeration

**Focus**: Spatial economics, agglomeration externalities, and the economic consequences of housing constraints; empirical foundation for understanding housing's role in productivity and distribution.

**Key Questions**:
- What are agglomeration externalities and how do they create location-specific value?
- How do housing supply constraints affect productivity and inequality?
- What is the economic significance of the "privatization of agglomeration rents"?
- How do land use regulations affect spatial sorting and opportunity?
- What role does housing play in urban growth and decline?

**Search Strategy**:
- Primary sources: Hsieh & Moretti (2019), Ganong & Shoag (2017), Duranton & Puga (2004) via `s2_search.py` and `search_openalex.py`
- Key terms: ["agglomeration externalities", "housing supply constraints productivity", "spatial sorting", "land use regulation economics", "urban growth housing", "locational value"]
- Use `search_openalex.py` for economics literature (broader disciplinary coverage)
- Expected papers: 15-20 papers on urban economics and agglomeration

**Relevance to Project**: Provides empirical foundation for understanding why location matters; informs the fungibility critique and occupancy/access trade-offs with economic evidence.

---

### Domain 7: Housing Systems and Financialization

**Focus**: Comparative housing systems, tenure neutrality debates, and the financialization of housing; structural context for housing's dual role problem.

**Key Questions**:
- What are different housing system models (Kemeny's dualist vs. unitary systems)?
- What does tenure neutrality require and is it achievable?
- How has housing financialization transformed housing's economic role?
- What is the relationship between housing wealth and inequality?
- How do different systems handle the asset/necessity tension?

**Search Strategy**:
- Primary sources: Kemeny (1981), Kohl (2020), Adkins et al. (2020), Ryan-Collins (2021) via `s2_search.py`
- Key terms: ["housing financialization", "tenure neutrality", "comparative housing systems", "housing wealth inequality", "asset-based welfare", "housing commodification"]
- Use `search_openalex.py` for sociology and political economy literature
- Expected papers: 12-15 papers on housing systems and financialization

**Relevance to Project**: Provides structural context for the third failing (asset vs. necessity); shows how institutional design affects the dual-role problem.

---

### Domain 8: Applied Ethics of Housing Justice

**Focus**: Philosophical work on housing rights, homelessness, affordability obligations, and applied housing ethics; bridges theory to policy.

**Key Questions**:
- Is there a human right to housing and what does it entail?
- What are the state's obligations regarding homelessness?
- How should affordability obligations be distributed?
- What does justice require regarding housing allocation and distribution?
- How do different ethical frameworks (capabilities, human rights, contractualism) approach housing?

**Search Strategy**:
- Primary sources: Halliday & author (2024), Essert (2016), Wells (2019), Draper (2022, 2023) via `s2_search.py`
- Key terms: ["right to housing", "housing justice", "homelessness ethics", "affordability obligations", "housing allocation justice", "adequate housing"]
- `search_philpapers.py` for "housing", "homelessness", "right to housing"
- Use `s2_search.py --recent` for last 5 years
- Expected papers: 18-22 papers on applied housing ethics

**Relevance to Project**: Shows existing applied philosophical work on housing; identifies where contractualist approach adds value and where it faces challenges from competing frameworks.

---

## Coverage Rationale

These eight domains provide comprehensive coverage by:
1. **Domains 1-2**: Establishing theoretical foundations (contractualism, fungibility problem)
2. **Domains 3-5**: Addressing each of the four key failings with dedicated literature bases
3. **Domain 6**: Providing empirical/economic foundation for understanding location-specific value
4. **Domain 7**: Adding institutional/structural context for housing's dual role
5. **Domain 8**: Surveying existing applied philosophical work to position the contribution

The decomposition balances pure theory (Domains 1-2), specific theoretical problems (Domains 3-5), empirical foundations (Domain 6), institutional context (Domain 7), and applied ethics (Domain 8). This ensures both philosophical rigor and policy relevance.

## Expected Gaps

Based on domain structure, the research likely fills these gaps:
1. **Integration gap**: Existing housing ethics literature doesn't systematically apply contractualist justification standards
2. **Fungibility gap**: Distributive justice theories haven't adequately theorized non-fungible, location-specific goods
3. **Trade-off gap**: Occupancy literature establishes incumbent claims but doesn't resolve occupancy/access tensions under contractualism
4. **POD application gap**: POD theory hasn't been tested against contractualist standards when applied to housing's dual role
5. **Epistemic gap**: Intergenerational justice literature hasn't been applied to urban planning's epistemic challenges

## Estimated Scope

- **Total domains**: 8
- **Estimated papers**: 120-150 total across all domains
- **Key positions to cover**:
  - Rawlsian vs. Scanlonian contractualism
  - Occupancy rights (Stilz, Huber & Wolkenstein) vs. access/mobility rights
  - Property-owning democracy vs. welfare state approaches
  - Capability approach vs. resourcist approaches to housing
  - Option preservation vs. optimization in intergenerational justice
  - Human rights approach vs. contractualist approach to housing
  - Tenure neutrality vs. homeownership promotion

## Search Priorities

1. **Foundational works**: Core contractualist texts (Rawls, Scanlon), POD foundational papers, intergenerational justice classics
2. **Recent developments**: Last 5 years on gentrification ethics, housing justice, POD applications (prioritize 2020-2025)
3. **Critical responses**: Critiques of primary goods/fungibility, responses to occupancy turn, POD criticisms
4. **Empirical foundations**: Key urban economics papers establishing agglomeration and housing constraint effects
5. **Interdisciplinary bridges**: Where philosophy meets economics (Hsieh & Moretti), sociology (financialization), planning theory (wicked problems)

## Notes for Researchers

**Search approach**:
- Use `philosophy-research` skill scripts extensively for structured searches
- **Start with SEP**: Use `search_sep.py` for foundational context on contractualism, intergenerational justice, distributive justice, capabilities approach
- **PhilPapers for philosophy**: Use `search_philpapers.py` for recent philosophical work on housing, gentrification, territorial rights
- **Semantic Scholar for known papers**: Use `s2_search.py` to find specific cited works (Stilz 2013, Huber & Wolkenstein 2018, etc.) and their citation networks
- **OpenAlex for interdisciplinary**: Use `search_openalex.py` for urban economics, housing policy, comparative political economy (broader coverage than S2)
- **Recent work flag**: Use `s2_search.py --recent` or `search_openalex.py` with date filters for 2020-2025 work on gentrification, housing justice, POD

**Quality criteria**:
- **Key papers**: Cited >50 times OR published in top venues OR directly addresses one of the four failings
- **Peripheral papers**: Provide context but don't directly advance the theoretical argument
- **Include**: Both supportive and critical perspectives on contractualism, POD, occupancy rights

**BibTeX annotation priorities**:
- Flag papers that directly address fungibility assumptions
- Note which papers take positions on occupancy vs. access trade-offs
- Identify papers testing normative theories against housing cases
- Mark empirical papers that quantify location-specific value or agglomeration effects

**Coverage balance**:
- Don't over-collect on Domain 1 (contractualist foundations) - aim for 12-15 papers max
- Prioritize Domains 3-5 (the four failings) - these are the novel contributions
- Ensure Domain 6 (urban economics) includes sufficient empirical grounding even though philosophical
- Domain 8 (applied ethics) should cover competing frameworks (capabilities, human rights) not just contractualism
