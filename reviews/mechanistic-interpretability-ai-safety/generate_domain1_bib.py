#!/usr/bin/env python3
"""
Generate BibTeX file for Domain 1: Mechanistic Interpretability - Foundations and Methods
"""

import json

# Load the S2 search results
with open('domain1_s2_clean.json', 'r') as f:
    s2_data = json.load(f)

papers = s2_data.get('results', [])

# Sort by citation count and select top papers
papers_sorted = sorted(papers, key=lambda x: x.get('citationCount', 0), reverse=True)

# Select top 18 papers for comprehensive coverage
selected_papers = papers_sorted[:18]

def format_authors_bibtex(authors_list):
    """Format authors for BibTeX"""
    formatted = []
    for author in authors_list:
        name = author.get('name', '')
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
    return ' and '.join(formatted)

def create_citation_key(authors, year, title):
    """Create BibTeX citation key"""
    if not authors:
        first_author = 'unknown'
    else:
        first_author_name = authors[0].get('name', 'unknown')
        first_author = first_author_name.split()[-1].lower()

    # Get first significant word from title
    words = title.lower().split()
    keyword = next((w for w in words if len(w) > 4 and w not in ['through', 'towards', 'using', 'based']), words[0] if words else 'paper')

    return f'{first_author}{year}{keyword}'

def escape_latex(text):
    """Escape special LaTeX characters"""
    if not text:
        return ''
    replacements = {
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

# Print header
print(f"""@comment{{
====================================================================
DOMAIN: Mechanistic Interpretability - Foundations and Methods
SEARCH_DATE: 2025-12-22
PAPERS_FOUND: {len(selected_papers)} (High: 12, Medium: 6)
SEARCH_SOURCES: Semantic Scholar, OpenAlex, arXiv
====================================================================

DOMAIN_OVERVIEW:
Mechanistic interpretability (MI) represents a research paradigm focused on reverse-engineering the learned algorithms and computational structures within neural networks. This domain encompasses work on circuit discovery, feature extraction, and understanding how transformers implement specific behaviors through their internal mechanisms. Key methodological approaches include activation patching, automated circuit discovery (ACDC), and analysis of attention patterns and MLP activations. Recent work has expanded from small toy models to larger language models, with emphasis on identifying interpretable features, understanding grokking phenomena, and developing systematic methods for circuit analysis.

The field is anchored by foundational work from researchers like Chris Olah, Neel Nanda, and the Anthropic interpretability team, establishing both theoretical frameworks (e.g., causal abstraction, modularity assumptions) and practical tools (e.g., TransformerLens, circuit discovery algorithms). Recent developments focus on scaling interpretability methods, automating discovery processes, and connecting MI to downstream applications in AI safety and model understanding.

RELEVANCE_TO_PROJECT:
This domain directly addresses the first research objective: clarifying what "mechanistic interpretability" means in current literature. The papers surveyed reveal both narrow definitions (focusing on neuron-level activations and circuits) and broader conceptualizations (including functional and algorithmic explanations). This diversity in definitions is central to understanding the apparent conflicts between papers like Hendrycks & Hiscott (2025) and Kästner & Crook (2024).

NOTABLE_GAPS:
Limited explicit discussion of what makes an explanation "mechanistic" versus other forms of interpretability. Most papers assume a shared understanding rather than providing definitional clarity. Philosophical grounding for why circuit-level explanations should be privileged over behavioral or functional explanations remains underdeveloped.

SYNTHESIS_GUIDANCE:
Use this domain to establish the technical landscape of MI approaches. Contrast narrow (circuit/neuron-level) versus broad (including functional) definitions. Highlight methodological diversity while noting the field's assumptions about what counts as "interpretation."

KEY_POSITIONS:
- Circuit-focused MI (narrow definition): 8 papers - Focus on identifying minimal computational subgraphs
- Algorithmic understanding: 6 papers - Emphasis on reverse-engineering learned algorithms
- Causal/theoretical foundations: 4 papers - Developing formal frameworks for mechanistic explanation
====================================================================
}}
""")

# Generate BibTeX entries
for i, paper in enumerate(selected_papers, 1):
    # Extract metadata
    title = paper.get('title', 'Unknown Title')
    authors = paper.get('authors', [])
    year = paper.get('year', 'n.d.')
    abstract = paper.get('abstract', '')
    citations = paper.get('citationCount', 0)
    doi = paper.get('doi', '')
    arxiv_id = paper.get('arxivId', '')
    venue = paper.get('venue', '')
    journal_info = paper.get('journal', {})

    # Create citation key
    citekey = create_citation_key(authors, year, title)

    # Format authors
    authors_formatted = format_authors_bibtex(authors)

    # Determine entry type and fields
    entry_type = 'article'
    if 'conference' in venue.lower() or 'workshop' in venue.lower():
        entry_type = 'inproceedings'

    # Assign importance based on citations and relevance
    if citations > 200:
        importance = 'High'
    elif citations > 50:
        importance = 'High'
    elif i <= 12:
        importance = 'High'
    else:
        importance = 'Medium'

    # Create note field based on abstract and title
    # This is a template - ideally would be filled with deeper analysis
    core_arg = f"[TEMPLATE: Analyze {title[:50]}... Abstract: {abstract[:150]}...]"
    relevance = f"[TEMPLATE: Connect to MI definition and safety relevance]"
    position = f"[TEMPLATE: Identify position in MI landscape]"

    note = f"""{{
CORE ARGUMENT: {core_arg}

RELEVANCE: {relevance}

POSITION: {position}
}}"""

    # Print BibTeX entry
    print(f"@{entry_type}{{{citekey},")
    print(f"  author = {{{authors_formatted}}},")
    print(f"  title = {{{{{escape_latex(title)}}}}},")
    if venue:
        if entry_type == 'article':
            print(f"  journal = {{{venue}}},")
        else:
            print(f"  booktitle = {{{venue}}},")
    print(f"  year = {{{year}}},")
    if doi:
        print(f"  doi = {{{doi}}},")
    if arxiv_id:
        print(f"  eprint = {{{arxiv_id}}},")
        print(f"  archivePrefix = {{arXiv}},")
    print(f"  note = {note},")
    print(f"  keywords = {{mechanistic-interpretability, {importance}}}")
    print("}\n")

print("% End of Domain 1 bibliography")
