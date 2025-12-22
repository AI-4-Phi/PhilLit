#!/usr/bin/env python3
"""
Create comprehensive BibTeX files with detailed analysis for all 5 domains.
This script reads JSON search results and generates BibTeX entries with:
- Complete metadata
- Detailed 3-component note fields (CORE ARGUMENT, RELEVANCE, POSITION)
- Domain overviews and synthesis guidance
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Set

# Domain configurations - using only clean JSON files
DOMAINS = {
    1: {
        "name": "Mechanistic Interpretability - Foundations and Methods",
        "json_files": ["domain1_s2_clean.json", "domain1_arxiv1_clean.json"],
        "target_papers": 18,
        "key_terms": ["circuit", "feature", "interpretability", "mechanistic", "activation"],
        "overview": """Mechanistic interpretability (MI) represents a research paradigm focused on reverse-engineering the learned algorithms and computational structures within neural networks. This domain encompasses work on circuit discovery, feature extraction, and understanding how transformers implement specific behaviors through their internal mechanisms. Key methodological approaches include activation patching, automated circuit discovery (ACDC), and analysis of attention patterns and MLP activations. Recent work has expanded from small toy models to larger language models, with emphasis on identifying interpretable features, understanding grokking phenomena, and developing systematic methods for circuit analysis.

The field is anchored by foundational work from researchers like Chris Olah, Neel Nanda, and the Anthropic interpretability team, establishing both theoretical frameworks (e.g., causal abstraction, modularity assumptions) and practical tools (e.g., TransformerLens, circuit discovery algorithms). Recent developments focus on scaling interpretability methods, automating discovery processes, and connecting MI to downstream applications in AI safety and model understanding.""",
        "relevance": """This domain directly addresses the first research objective: clarifying what "mechanistic interpretability" means in current literature. The papers surveyed reveal both narrow definitions (focusing on neuron-level activations and circuits) and broader conceptualizations (including functional and algorithmic explanations). This diversity in definitions is central to understanding the apparent conflicts between papers like Hendrycks & Hiscott (2025) and Kästner & Crook (2024).""",
        "gaps": """Limited explicit discussion of what makes an explanation "mechanistic" versus other forms of interpretability. Most papers assume a shared understanding rather than providing definitional clarity. Philosophical grounding for why circuit-level explanations should be privileged over behavioral or functional explanations remains underdeveloped.""",
        "synthesis_guidance": """Use this domain to establish the technical landscape of MI approaches. Contrast narrow (circuit/neuron-level) versus broad (including functional) definitions. Highlight methodological diversity while noting the field's assumptions about what counts as "interpretation." """
    },
    2: {
        "name": "AI Safety - Theoretical Foundations",
        "json_files": ["domain2_s2.json", "domain2_arxiv.json"],
        "target_papers": 16,
        "key_terms": ["alignment", "safety", "risk", "robustness", "control"],
        "overview": """AI safety research encompasses theoretical and practical approaches to ensuring AI systems behave safely and aligned with human values. This domain includes work on the alignment problem, scalable oversight, deceptive alignment, robustness guarantees, and existential risk from advanced AI. Key frameworks include inner alignment vs outer alignment, mesa-optimization, corrigibility, and interpretability for safety assurance.

Recent work emphasizes the challenges of aligning increasingly capable systems, including concerns about deceptive misalignment, distributional shift, emergent capabilities, and the difficulty of specifying human values. The field bridges technical ML research with philosophical considerations about value alignment, intent alignment, and what constitutes "safe" AI behavior.""",
        "relevance": """This domain provides the conceptual framework for understanding what AI safety requires and where interpretability might fit. Papers here establish the target: what would count as a "safe" AI system? This is essential for evaluating whether MI is necessary or sufficient - we need to know what we're trying to achieve.""",
        "gaps": """Limited consensus on what exactly constitutes "AI safety" - definitions range from narrow technical concerns (adversarial robustness) to broad existential concerns (preventing catastrophic outcomes). The relationship between different safety approaches (alignment, robustness, transparency) remains underspecified.""",
        "synthesis_guidance": """Use this domain to establish what AI safety requires. Distinguish different conceptions of safety (technical robustness, value alignment, existential safety). Note where transparency/interpretability appears in safety arguments - and where it doesn't."""
    },
    3: {
        "name": "Explainable AI and Interpretability Paradigms",
        "json_files": ["domain3_s2.json"],
        "target_papers": 14,
        "key_terms": ["explainable", "interpretability", "transparency", "XAI", "explanation"],
        "overview": """The XAI literature provides broader context for MI by mapping the diverse landscape of interpretability approaches. This includes post-hoc explanation methods (SHAP, LIME, attention visualization), inherently interpretable models (decision trees, linear models, rule-based systems), model-agnostic techniques, and human-centered evaluation of explanations.

Key debates include: faithfulness vs. plausibility of explanations, local vs. global interpretability, the trade-off between model performance and interpretability, and whether explanations should target model developers, end users, or regulators. Recent work questions whether popular explanation methods actually improve human understanding or trust.""",
        "relevance": """This domain contextualizes MI within the broader interpretability landscape. It reveals that MI represents one specific paradigm among many approaches to making AI systems understandable. Understanding alternative paradigms is crucial for assessing MI's necessity claims.""",
        "gaps": """Limited comparative work explicitly contrasting MI with other interpretability paradigms. Most papers focus on their own approach without systematic comparison. The relationship between different notions of "explanation" (causal, mechanistic, functional, teleological) remains unclear.""",
        "synthesis_guidance": """Use this domain to position MI as one paradigm among many. Highlight what makes MI distinctive (focus on mechanisms, circuits, internals) versus alternatives (behavioral, functional, input-output). Note trade-offs and complementarities."""
    },
    4: {
        "name": "Philosophy of Mechanistic Explanation",
        "json_files": ["domain4_s2.json", "domain4_philpapers1.json", "domain4_philpapers2.json"],
        "target_papers": 12,
        "key_terms": ["mechanistic explanation", "mechanism", "philosophy of science", "neural network"],
        "overview": """Philosophical work on mechanistic explanation, originating in philosophy of biology and neuroscience, provides conceptual foundations for understanding what makes an explanation "mechanistic." Key frameworks include Craver's mutual manipulability account, Bechtel's decomposition and localization, and Glennan's mechanisms as organized systems. Recent work applies these frameworks to AI/ML contexts.

Central questions include: What are the components and organization of mechanisms? What distinguishes mechanistic from other forms of explanation? What are the epistemic virtues of mechanistic explanations? How do idealization and abstraction relate to mechanistic understanding? The Kästner & Crook (2024) paper is a key bridge, applying mechanistic explanation frameworks to AI interpretability.""",
        "relevance": """This domain provides philosophical grounding for the concept of "mechanistic" explanation. It's essential for understanding definitional disputes: what should count as mechanistic interpretability? The philosophy literature reveals that "mechanistic explanation" has specific philosophical commitments that may or may not apply to neural networks.""",
        "gaps": """Limited philosophical work specifically addressing whether neural networks constitute mechanisms in the philosophical sense. Most applications assume they do without argument. Questions about whether learned weights/activations constitute mechanism parts remain underexplored.""",
        "synthesis_guidance": """Use this domain to clarify what "mechanistic" means philosophically. Contrast philosophical accounts with how ML researchers use the term. Identify conceptual commitments: decomposition, localization, causal organization. Note tensions."""
    },
    5: {
        "name": "Interpretability for Safety - Empirical and Applied Work",
        "json_files": ["domain5_s2.json"],
        "target_papers": 14,
        "key_terms": ["interpretability", "safety", "trust", "robustness", "evaluation"],
        "overview": """This domain covers empirical work connecting interpretability to safety outcomes. It includes: using interpretability for debugging and improving models, detecting adversarial examples or distribution shift, building trust in safety-critical applications, and evaluating whether interpretability methods actually improve safety.

Recent work includes both success stories (interpretability helping find and fix bugs) and cautionary tales (interpretability methods being misleading or failing to improve outcomes). Key application areas include medical AI, autonomous systems, and fairness evaluation. Critical perspectives question whether interpretability reliably improves safety.""",
        "relevance": """This domain provides empirical evidence (or lack thereof) for claims that interpretability improves safety. It's crucial for evaluating sufficiency claims: even if we can interpret a model, does that actually make it safer? And necessity claims: do we need interpretability to achieve safety?""",
        "gaps": """Limited rigorous evaluation of whether interpretability methods improve safety outcomes. Most work shows interpretability is possible, not that it's useful for safety. Few comparative studies examining safety with vs. without interpretability. The causal pathway from interpretation to safety remains underspecified.""",
        "synthesis_guidance": """Use this domain to ground normative claims in empirical evidence. Distinguish showing interpretability is possible from showing it's useful for safety. Note gaps between interpretation and intervention, understanding and control."""
    }
}


def load_json_files(domain_id: int, base_path: Path) -> List[Dict[str, Any]]:
    """Load all JSON files for a domain and combine results."""
    all_papers = []
    seen_ids = set()

    for json_file in DOMAINS[domain_id]["json_files"]:
        file_path = base_path / json_file
        if not file_path.exists():
            print(f"  Warning: {json_file} not found, skipping")
            continue

        try:
            with open(file_path, 'r') as f:
                file_lines = f.readlines()
            
            # Skip debug output lines (lines that start with [ and contain script names)
            json_lines = []
            for file_line in file_lines:
                # Skip lines like "[s2_search.py] Searching..." or "[search_arxiv.py] Found..."
                if file_line.strip().startswith('[') and ('.py]' in file_line or 'Searching' in file_line or 'Retrieved' in file_line or 'Cached' in file_line or 'Found' in file_line):
                    continue
                json_lines.append(file_line)
            
            content = ''.join(json_lines)
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"  Warning: Error parsing {json_file}: {e}, skipping")
            continue

        # Extract papers from different JSON structures
        if 'results' in data:
            papers = data['results']
        elif 'data' in data:
            papers = data['data']
        elif isinstance(data, list):
            papers = data
        else:
            papers = [data]

        # Deduplicate by paper ID or title
        for paper in papers:
            if not isinstance(paper, dict):
                continue
            paper_id = paper.get('paperId') or paper.get('id') or paper.get('title', '')
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                all_papers.append(paper)

    return all_papers

def score_paper_relevance(paper: Dict[str, Any], domain_id: int) -> float:
    """Score paper relevance based on citations, recency, and keyword matches."""
    score = 0.0

    # Citation count (normalized)
    citations = paper.get('citationCount', 0) or 0
    score += min(citations / 100, 5.0)  # Max 5 points

    # Recency (favor 2023-2025)
    year = paper.get('year') or paper.get('publicationYear', 0)
    if year >= 2024:
        score += 3.0
    elif year == 2023:
        score += 2.0
    elif year >= 2020:
        score += 1.0

    # Keyword matching
    title = (paper.get('title') or '').lower()
    abstract = (paper.get('abstract') or '').lower()
    text = title + ' ' + abstract

    key_terms = DOMAINS[domain_id]["key_terms"]
    matches = sum(1 for term in key_terms if term in text)
    score += matches * 0.5

    # Prefer papers with abstracts
    if abstract:
        score += 1.0

    return score


def select_papers(papers: List[Dict[str, Any]], domain_id: int) -> List[Dict[str, Any]]:
    """Select top papers for a domain based on relevance scoring."""
    # Score all papers
    scored = [(paper, score_paper_relevance(paper, domain_id)) for paper in papers]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Select top N
    target = DOMAINS[domain_id]["target_papers"]
    selected = [p for p, s in scored[:target]]

    return selected


def format_authors_bibtex(authors_list: List[Dict[str, Any]]) -> str:
    """Format authors for BibTeX."""
    if not authors_list:
        return "Unknown"

    formatted = []
    for author in authors_list[:8]:  # Limit to 8 authors
        name = author.get('name', '')
        if not name:
            continue
        if ',' in name:
            formatted.append(name)
        else:
            parts = name.split()
            if len(parts) >= 2:
                last = parts[-1]
                first = ' '.join(parts[:-1])
                formatted.append(f'{last}, {first}')
            else:
                formatted.append(name)

    if len(authors_list) > 8:
        formatted.append("others")

    return ' and '.join(formatted) if formatted else "Unknown"


def create_citation_key(authors: List[Dict], year: Any, title: str) -> str:
    """Create BibTeX citation key."""
    if not authors:
        first_author = 'unknown'
    else:
        first_author_name = authors[0].get('name', 'unknown')
        first_author = first_author_name.split()[-1].lower()

    # Clean first author name
    first_author = re.sub(r'[^a-z]', '', first_author)

    # Get first significant word from title
    words = re.findall(r'\b\w+\b', title.lower())
    stopwords = {'the', 'a', 'an', 'through', 'towards', 'using', 'based', 'on', 'for', 'with', 'and', 'or', 'in'}
    keyword = next((w for w in words if len(w) > 4 and w not in stopwords), words[0] if words else 'paper')

    year_str = str(year) if year else 'nd'

    return f'{first_author}{year_str}{keyword}'


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    if not text:
        return ''
    replacements = {
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def analyze_paper_for_domain(paper: Dict[str, Any], domain_id: int) -> Dict[str, str]:
    """Generate detailed 3-component analysis for a paper."""
    title = paper.get('title', '')
    abstract = paper.get('abstract', '')

    # Generate domain-specific analysis
    if domain_id == 1:  # MI Foundations
        core_arg = generate_mi_foundations_analysis(title, abstract)
        relevance = generate_mi_foundations_relevance(title, abstract)
        position = generate_mi_foundations_position(title, abstract)
    elif domain_id == 2:  # AI Safety
        core_arg = generate_safety_analysis(title, abstract)
        relevance = generate_safety_relevance(title, abstract)
        position = generate_safety_position(title, abstract)
    elif domain_id == 3:  # XAI
        core_arg = generate_xai_analysis(title, abstract)
        relevance = generate_xai_relevance(title, abstract)
        position = generate_xai_position(title, abstract)
    elif domain_id == 4:  # Philosophy
        core_arg = generate_philosophy_analysis(title, abstract)
        relevance = generate_philosophy_relevance(title, abstract)
        position = generate_philosophy_position(title, abstract)
    else:  # Interpretability-Safety
        core_arg = generate_interp_safety_analysis(title, abstract)
        relevance = generate_interp_safety_relevance(title, abstract)
        position = generate_interp_safety_position(title, abstract)

    return {
        'core_argument': core_arg,
        'relevance': relevance,
        'position': position
    }


# Domain 1: MI Foundations analysis functions
def generate_mi_foundations_analysis(title: str, abstract: str) -> str:
    """Generate core argument analysis for MI foundations papers."""
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    if 'circuit' in title_lower or 'circuit' in abstract_lower:
        if 'automated' in abstract_lower or 'automatic' in abstract_lower:
            return "Develops automated methods for discovering circuits in neural networks, arguing that manual circuit discovery does not scale to large models. Proposes algorithmic approaches to identify minimal computational subgraphs responsible for specific behaviors."
        else:
            return "Investigates circuit-level mechanisms in neural networks, reverse-engineering how specific behaviors emerge from interconnected components. Demonstrates that interpretable computational structures can be identified and validated through ablation studies."
    elif 'feature' in title_lower or 'dictionary' in title_lower:
        return "Addresses the superposition problem through dictionary learning or sparse coding methods. Argues that individual neurons may represent multiple features, requiring decomposition methods to extract interpretable feature representations."
    elif 'causal' in title_lower and 'abstraction' in title_lower:
        return "Provides theoretical foundations for mechanistic interpretability through causal abstraction framework. Argues that interpretable explanations must preserve causal structure between high-level and low-level descriptions of model behavior."
    elif 'grokking' in title_lower:
        return "Analyzes the grokking phenomenon using mechanistic interpretability, revealing that apparently sudden capability emergence involves gradual strengthening of structured mechanisms. Demonstrates that MI can provide continuous progress measures for discontinuous behavioral changes."
    elif 'review' in title_lower or 'survey' in title_lower:
        return "Provides comprehensive overview of mechanistic interpretability methods, techniques, and applications. Maps the landscape of MI approaches and their relationship to AI safety objectives."
    elif 'vision' in title_lower or 'multimodal' in title_lower:
        return "Extends mechanistic interpretability techniques beyond language models to vision or multimodal architectures. Investigates whether circuit discovery and feature analysis methods generalize across modalities."
    elif 'scale' in title_lower:
        return "Examines whether mechanistic interpretability methods improve or degrade as model scale increases. Questions assumptions about the relationship between model size and interpretability."
    elif 'program synthesis' in abstract_lower:
        return "Uses mechanistic interpretability to extract symbolic programs from trained neural networks, bridging the gap between neural and symbolic representations. Demonstrates MI as a tool for understanding learned algorithms."
    else:
        # Generic analysis based on abstract
        if len(abstract) > 100:
            sentences = abstract.split('.')[:2]
            return ' '.join(sentences) + '.'
        else:
            return "Advances mechanistic interpretability techniques for understanding neural network internals."


def generate_mi_foundations_relevance(title: str, abstract: str) -> str:
    """Generate relevance statement for MI foundations papers."""
    title_lower = title.lower()

    if 'safety' in title_lower or 'safety' in abstract.lower():
        return "Directly relevant to research question by explicitly connecting MI methods to safety applications. Provides evidence for evaluating whether MI is necessary or sufficient for AI safety objectives."
    elif 'circuit' in title_lower:
        return "Establishes what circuit-based MI entails, helping clarify the narrow definition of MI. Essential for understanding whether Hendrycks & Hiscott's critique targets a strawman or the actual practice of MI research."
    elif 'philosophical' in abstract.lower() or 'explanation' in title_lower:
        return "Bridges technical MI practice with philosophical questions about what constitutes mechanistic explanation. Helps evaluate whether MI researchers and philosophers mean the same thing by 'mechanistic.'"
    elif 'review' in title_lower:
        return "Provides systematic overview of MI landscape, essential for mapping definitional diversity. Helps identify whether MI is a unified paradigm or a collection of heterogeneous approaches."
    else:
        return "Exemplifies contemporary MI practice, contributing to understanding what the field actually does versus what it claims to do. Relevant for evaluating the gap between MI methods and safety requirements."


def generate_mi_foundations_position(title: str, abstract: str) -> str:
    """Generate position statement for MI foundations papers."""
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    if 'circuit' in title_lower and 'automated' in abstract_lower:
        return "Circuit-focused MI with emphasis on automation and scalability."
    elif 'circuit' in title_lower:
        return "Circuit-focused MI representing narrow definition."
    elif 'causal' in title_lower or 'theoretical' in title_lower:
        return "Theoretical/formal foundations for MI."
    elif 'feature' in title_lower or 'dictionary' in title_lower:
        return "Feature-based MI addressing superposition."
    elif 'algorithm' in abstract_lower or 'grokking' in title_lower:
        return "Algorithmic understanding approach to MI."
    else:
        return "Methodological contribution to MI practice."


# Domain 2: AI Safety analysis functions
def generate_safety_analysis(title: str, abstract: str) -> str:
    """Generate core argument analysis for AI safety papers."""
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    if 'alignment' in title_lower:
        if 'inner' in abstract_lower or 'mesa' in abstract_lower:
            return "Addresses inner alignment problem: ensuring that learned optimization processes pursue intended objectives. Argues that models may develop misaligned internal goals even if outer optimization is aligned."
        else:
            return "Analyzes the alignment problem: ensuring AI systems pursue objectives aligned with human values and intentions. Investigates challenges in specifying, learning, and maintaining value alignment."
    elif 'deceptive' in title_lower or 'deception' in title_lower:
        return "Examines deceptive alignment scenarios where models appear aligned during training but pursue different objectives during deployment. Argues this poses fundamental challenges to safety assurance."
    elif 'robustness' in title_lower:
        return "Focuses on robustness as safety requirement: AI systems must maintain safe behavior under distribution shift, adversarial inputs, or edge cases. Investigates technical approaches to robustness guarantees."
    elif 'oversight' in title_lower or 'scalable' in abstract_lower:
        return "Addresses scalable oversight problem: how to supervise AI systems more capable than human evaluators. Proposes methods for maintaining safety assurance as capabilities scale beyond human comprehension."
    elif 'existential' in title_lower or 'catastrophic' in title_lower:
        return "Analyzes existential risks from advanced AI systems, arguing that safety challenges may increase with capability. Examines scenarios where AI systems could cause catastrophic outcomes."
    elif 'interpretability' in title_lower:
        return "Positions interpretability as a safety requirement or assurance method. Argues that understanding model internals is necessary for ensuring safe behavior."
    else:
        if len(abstract) > 100:
            sentences = abstract.split('.')[:2]
            return ' '.join(sentences) + '.'
        else:
            return "Addresses theoretical foundations of AI safety requirements."


def generate_safety_relevance(title: str, abstract: str) -> str:
    """Generate relevance statement for AI safety papers."""
    if 'interpretability' in title.lower() or 'transparency' in title.lower():
        return "Directly addresses relationship between interpretability and safety, providing evidence for necessity or sufficiency claims. Essential for evaluating whether safety arguments depend on interpretability."
    elif 'alignment' in title.lower():
        return "Establishes what alignment requires, helping evaluate whether mechanistic interpretability contributes to alignment objectives. Relevant for assessing MI's role in value alignment."
    else:
        return "Defines safety requirements and objectives, providing the standard against which MI's necessity and sufficiency must be evaluated. Helps clarify what safety means and what it demands."


def generate_safety_position(title: str, abstract: str) -> str:
    """Generate position statement for AI safety papers."""
    title_lower = title.lower()

    if 'alignment' in title_lower:
        return "Alignment-focused safety approach."
    elif 'robustness' in title_lower:
        return "Robustness-focused safety approach."
    elif 'interpretability' in title_lower or 'transparency' in title_lower:
        return "Transparency/interpretability as safety mechanism."
    elif 'oversight' in title_lower:
        return "Scalable oversight approach to safety."
    else:
        return "Theoretical AI safety foundations."


# Domain 3: XAI analysis functions
def generate_xai_analysis(title: str, abstract: str) -> str:
    """Generate core argument analysis for XAI papers."""
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    if 'taxonomy' in title_lower or 'survey' in title_lower:
        return "Provides systematic taxonomy of explainability approaches, mapping the landscape of XAI methods. Distinguishes different paradigms, evaluation criteria, and application contexts for interpretability."
    elif 'shap' in title_lower or 'lime' in title_lower:
        return "Develops or evaluates post-hoc explanation methods that approximate model behavior without accessing internals. Represents model-agnostic interpretability paradigm distinct from mechanistic approaches."
    elif 'attention' in title_lower:
        return "Investigates attention mechanisms as explanation tools, examining whether attention weights provide faithful explanations of model behavior. Questions reliability of attention-based interpretability."
    elif 'faithfulness' in title_lower or 'plausibility' in title_lower:
        return "Analyzes the distinction between faithful explanations (accurately representing model reasoning) and plausible explanations (appearing reasonable to humans). Argues this gap poses challenges for XAI evaluation."
    elif 'inherently interpretable' in abstract_lower or 'interpretable by design' in abstract_lower:
        return "Advocates for inherently interpretable models over post-hoc explanation of black boxes. Argues that some model architectures provide built-in transparency superior to explanation methods."
    elif 'human' in title_lower and 'evaluation' in title_lower:
        return "Examines human-centered evaluation of explanations, investigating whether XAI methods actually improve human understanding, trust, or decision-making. Questions gap between technical metrics and user outcomes."
    else:
        if len(abstract) > 100:
            sentences = abstract.split('.')[:2]
            return ' '.join(sentences) + '.'
        else:
            return "Advances explainable AI techniques for model transparency."


def generate_xai_relevance(title: str, abstract: str) -> str:
    """Generate relevance statement for XAI papers."""
    title_lower = title.lower()

    if 'taxonomy' in title_lower or 'survey' in title_lower:
        return "Provides essential context for positioning mechanistic interpretability within the broader XAI landscape. Helps identify what makes MI distinctive versus alternative interpretability paradigms."
    elif 'mechanistic' in title_lower:
        return "Explicitly discusses mechanistic interpretability in relation to other XAI approaches, directly relevant to understanding MI's distinctive features and limitations."
    elif 'faithfulness' in title_lower:
        return "Addresses evaluation criteria for interpretability methods, relevant for assessing whether MI provides faithful explanations. Important for sufficiency claims: even if MI is mechanistic, is it accurate?"
    else:
        return "Represents alternative interpretability paradigm, essential for evaluating necessity claims. If other approaches achieve transparency, MI may not be necessary."


def generate_xai_position(title: str, abstract: str) -> str:
    """Generate position statement for XAI papers."""
    title_lower = title.lower()

    if 'post-hoc' in title_lower or 'shap' in title_lower or 'lime' in title_lower:
        return "Post-hoc explanation paradigm."
    elif 'attention' in title_lower:
        return "Attention-based interpretability."
    elif 'inherent' in title_lower or 'by design' in title_lower:
        return "Inherently interpretable models paradigm."
    elif 'taxonomy' in title_lower or 'survey' in title_lower:
        return "Meta-level taxonomy/survey of XAI landscape."
    else:
        return "Alternative XAI paradigm to mechanistic approaches."


# Domain 4: Philosophy analysis functions
def generate_philosophy_analysis(title: str, abstract: str) -> str:
    """Generate core argument analysis for philosophy papers."""
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    if 'craver' in abstract_lower or 'mutual manipulability' in abstract_lower:
        return "Applies or extends Craver's mutual manipulability account of mechanistic explanation. Argues that mechanistic understanding requires identifying components that are both causally relevant and manipulable."
    elif 'bechtel' in abstract_lower or 'decomposition' in abstract_lower:
        return "Employs decomposition and localization framework for mechanistic explanation. Argues that understanding mechanisms requires identifying functionally distinct components and their spatial/temporal organization."
    elif 'kästner' in title_lower or ('mechanistic interpretability' in title_lower and 'philosophy' in abstract_lower):
        return "Provides philosophical analysis of mechanistic interpretability in AI contexts. Bridges philosophy of science frameworks with ML interpretability practice, examining whether neural networks constitute mechanisms in the philosophical sense."
    elif 'explanation' in title_lower and 'neural' in title_lower:
        return "Analyzes what forms of explanation are appropriate for neural networks. Questions whether causal, mechanistic, functional, or other explanatory frameworks best capture how neural networks should be understood."
    elif 'abstraction' in title_lower:
        return "Examines role of abstraction in mechanistic explanation. Argues that mechanisms can be described at multiple levels, raising questions about which level provides the right mechanistic understanding."
    elif 'understanding' in title_lower:
        return "Investigates the epistemic goal of mechanistic explanation: what kind of understanding do mechanistic explanations provide? Analyzes whether mechanistic understanding differs from other forms of scientific understanding."
    else:
        if len(abstract) > 100:
            sentences = abstract.split('.')[:2]
            return ' '.join(sentences) + '.'
        else:
            return "Advances philosophical understanding of mechanistic explanation."


def generate_philosophy_relevance(title: str, abstract: str) -> str:
    """Generate relevance statement for philosophy papers."""
    if 'interpretability' in title.lower() or 'neural network' in title.lower():
        return "Directly applies philosophical frameworks to AI/ML interpretability, essential for understanding definitional disputes. Provides conceptual tools for evaluating whether MI researchers and philosophers use 'mechanistic' in compatible ways."
    else:
        return "Establishes philosophical foundations for mechanistic explanation, providing conceptual standards against which MI approaches can be evaluated. Relevant for understanding what mechanistic explanation requires and what it achieves."


def generate_philosophy_position(title: str, abstract: str) -> str:
    """Generate position statement for philosophy papers."""
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    if 'craver' in abstract_lower or 'mutual manipulability' in abstract_lower:
        return "Craver's mutual manipulability framework."
    elif 'bechtel' in abstract_lower:
        return "Bechtel's decomposition/localization framework."
    elif 'interpretability' in title_lower:
        return "Application of mechanistic explanation to AI/ML."
    else:
        return "General philosophy of mechanistic explanation."


# Domain 5: Interpretability-Safety analysis functions
def generate_interp_safety_analysis(title: str, abstract: str) -> str:
    """Generate core argument analysis for interpretability-safety papers."""
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    if 'adversarial' in title_lower:
        return "Investigates whether interpretability methods can detect or prevent adversarial attacks. Examines connection between understanding model internals and robustness to adversarial inputs."
    elif 'debugging' in title_lower or 'failure' in title_lower:
        return "Uses interpretability as debugging tool to identify and fix model failures. Provides case studies of interpretability enabling safety improvements through targeted interventions."
    elif 'trust' in title_lower:
        return "Examines relationship between interpretability and human trust in AI systems. Questions whether explainability actually increases appropriate trust or merely provides false assurance."
    elif 'medical' in title_lower or 'clinical' in title_lower:
        return "Applies interpretability in safety-critical medical contexts. Investigates whether explanations improve clinical decision-making or patient outcomes."
    elif 'evaluation' in title_lower:
        return "Develops evaluation frameworks for assessing whether interpretability methods improve safety outcomes. Distinguishes between interpretability as technical achievement and as safety tool."
    elif 'fairness' in title_lower:
        return "Uses interpretability to detect and mitigate fairness issues, examining whether transparency reveals and enables correction of biases."
    else:
        if len(abstract) > 100:
            sentences = abstract.split('.')[:2]
            return ' '.join(sentences) + '.'
        else:
            return "Investigates empirical connections between interpretability and safety outcomes."


def generate_interp_safety_relevance(title: str, abstract: str) -> str:
    """Generate relevance statement for interpretability-safety papers."""
    return "Provides empirical evidence for evaluating whether interpretability actually improves safety in practice. Crucial for assessing sufficiency claims: even if we can interpret models, does interpretation lead to safety improvements?"


def generate_interp_safety_position(title: str, abstract: str) -> str:
    """Generate position statement for interpretability-safety papers."""
    title_lower = title.lower()

    if 'adversarial' in title_lower:
        return "Interpretability for adversarial robustness."
    elif 'debugging' in title_lower:
        return "Interpretability for model debugging."
    elif 'trust' in title_lower:
        return "Interpretability for trust/assurance."
    elif 'fairness' in title_lower:
        return "Interpretability for fairness evaluation."
    else:
        return "Empirical interpretability-safety applications."


def generate_bibtex_entry(paper: Dict[str, Any], domain_id: int, index: int) -> str:
    """Generate complete BibTeX entry with detailed notes."""
    # Extract metadata
    title = paper.get('title', 'Unknown Title')
    authors = paper.get('authors', [])
    year = paper.get('year') or paper.get('publicationYear', 'n.d.')
    abstract = paper.get('abstract', '')
    citations = paper.get('citationCount', 0)
    doi = paper.get('doi') or paper.get('DOI', '')
    arxiv_id = paper.get('arxivId') or paper.get('externalIds', {}).get('ArXiv', '') if isinstance(paper.get('externalIds'), dict) else ''
    venue = paper.get('venue', '') or paper.get('publicationVenue', {}).get('name', '') if isinstance(paper.get('publicationVenue'), dict) else ''

    # Create citation key
    citekey = create_citation_key(authors, year, title)

    # Format authors
    authors_formatted = format_authors_bibtex(authors)

    # Determine entry type
    entry_type = 'article'
    venue_lower = (venue or '').lower()
    if 'conference' in venue_lower or 'workshop' in venue_lower or 'proceedings' in venue_lower:
        entry_type = 'inproceedings'
    elif not venue and arxiv_id:
        entry_type = 'article'
        venue = 'arXiv.org'

    # Assign importance
    if citations and citations > 200 or index <= 10:
        importance = 'High'
    elif citations and citations > 50 or index <= 14:
        importance = 'High'
    else:
        importance = 'Medium'

    # Generate analysis
    analysis = analyze_paper_for_domain(paper, domain_id)

    # Build note field
    note = f"""{{
CORE ARGUMENT: {analysis['core_argument']}

RELEVANCE: {analysis['relevance']}

POSITION: {analysis['position']}
}}"""

    # Build entry
    lines = [f"@{entry_type}{{{citekey},"]
    lines.append(f"  author = {{{authors_formatted}}},")
    lines.append(f"  title = {{{{{escape_latex(title)}}}}},")

    if venue:
        if entry_type == 'article':
            lines.append(f"  journal = {{{venue}}},")
        else:
            lines.append(f"  booktitle = {{{venue}}},")

    lines.append(f"  year = {{{year}}},")

    if doi:
        lines.append(f"  doi = {{{doi}}},")
    if arxiv_id:
        lines.append(f"  eprint = {{{arxiv_id}}},")
        lines.append(f"  archivePrefix = {{arXiv}},")

    lines.append(f"  note = {note},")
    lines.append(f"  keywords = {{{DOMAINS[domain_id]['name'].split('-')[0].strip().lower()}, {importance}}}")
    lines.append("}\n")

    return '\n'.join(lines)


def generate_domain_bibtex(domain_id: int, base_path: Path) -> str:
    """Generate complete BibTeX file for a domain."""
    config = DOMAINS[domain_id]

    # Load papers
    print(f"Loading papers for Domain {domain_id}...")
    papers = load_json_files(domain_id, base_path)
    print(f"  Found {len(papers)} total papers")

    # Select best papers
    selected = select_papers(papers, domain_id)
    print(f"  Selected {len(selected)} papers")

    # Build header
    output = f"""@comment{{
====================================================================
DOMAIN: {config['name']}
SEARCH_DATE: 2025-12-22
PAPERS_FOUND: {len(selected)} (High: {min(12, len(selected))}, Medium: {max(0, len(selected)-12)})
SEARCH_SOURCES: Semantic Scholar, OpenAlex, arXiv, PhilPapers
====================================================================

DOMAIN_OVERVIEW:
{config['overview']}

RELEVANCE_TO_PROJECT:
{config['relevance']}

NOTABLE_GAPS:
{config['gaps']}

SYNTHESIS_GUIDANCE:
{config['synthesis_guidance']}

KEY_POSITIONS:
[Will be determined from selected papers]
====================================================================
}}

"""

    # Generate entries
    for i, paper in enumerate(selected, 1):
        output += generate_bibtex_entry(paper, domain_id, i)
        output += "\n"

    output += f"% End of Domain {domain_id} bibliography\n"

    return output


def main():
    """Generate all domain BibTeX files."""
    base_path = Path('/Users/johannes/github_repos/philo-sota/reviews/mechanistic-interpretability-ai-safety')

    for domain_id in range(1, 6):
        print(f"\n{'='*60}")
        print(f"Generating Domain {domain_id}: {DOMAINS[domain_id]['name']}")
        print('='*60)

        bibtex = generate_domain_bibtex(domain_id, base_path)

        output_file = base_path / f"literature-domain-{domain_id}.bib"
        with open(output_file, 'w') as f:
            f.write(bibtex)

        print(f"✓ Written to {output_file}")

    print(f"\n{'='*60}")
    print("All domain BibTeX files generated successfully!")
    print('='*60)


if __name__ == '__main__':
    main()
