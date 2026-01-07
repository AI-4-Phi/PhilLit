#!/usr/bin/env python3
"""
Shared formatters and constants for Semantic Scholar API scripts.

This module consolidates the format_paper() function and API constants
that are duplicated across s2_search.py, s2_batch.py, s2_citations.py,
and s2_recommend.py.
"""

from typing import Optional

# Semantic Scholar API configuration
S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"

# Field sets for different API endpoints
# Full fields for search and batch operations
S2_FIELDS = "paperId,title,authors,year,abstract,citationCount,externalIds,url,venue,publicationTypes,journal"

# Paper fields for citation lookups (paper details)
S2_PAPER_FIELDS = "paperId,title,authors,year,abstract,citationCount,externalIds,url,venue"

# Citation-specific fields (includes context and influence data)
S2_CITATION_FIELDS = "paperId,title,authors,year,citationCount,externalIds,url,venue,contexts,intents,isInfluential"

# Recommendation fields (no journal/publicationTypes needed)
S2_RECOMMEND_FIELDS = "paperId,title,authors,year,abstract,citationCount,externalIds,url,venue"


def format_paper(paper: dict, include_extended: bool = True) -> Optional[dict]:
    """
    Format S2 paper response into standard output format.

    Args:
        paper: Raw paper dict from S2 API
        include_extended: Whether to include journal/publicationTypes fields
                         (set False for citations/recommendations)

    Returns:
        Formatted paper dict, or None if paper is empty/None
    """
    if not paper:
        return None

    # Extract DOI and ArXiv ID from externalIds
    external_ids = paper.get("externalIds", {}) or {}
    doi = external_ids.get("DOI")
    arxiv_id = external_ids.get("ArXiv")

    # Format authors
    authors = []
    for author in paper.get("authors", []) or []:
        authors.append({
            "name": author.get("name", ""),
            "authorId": author.get("authorId")
        })

    result = {
        "paperId": paper.get("paperId"),
        "title": paper.get("title"),
        "authors": authors,
        "year": paper.get("year"),
        "abstract": paper.get("abstract"),
        "citationCount": paper.get("citationCount"),
        "doi": doi,
        "arxivId": arxiv_id,
        "url": paper.get("url"),
        "venue": paper.get("venue"),
    }

    # Add extended fields for search/batch operations
    if include_extended:
        result["journal"] = paper.get("journal")
        result["publicationTypes"] = paper.get("publicationTypes")

    return result


def format_citation(citation: dict, direction: str) -> dict:
    """
    Format a citation/reference entry from S2 citations API.

    Args:
        citation: Raw citation object from API
        direction: "citations" (papers citing this) or "references" (papers this cites)

    Returns:
        Formatted citation dict with paper details + context info
    """
    # The paper is nested under 'citingPaper' or 'citedPaper'
    paper_key = "citingPaper" if direction == "citations" else "citedPaper"
    paper = citation.get(paper_key, {})

    # Use format_paper without extended fields for citations
    result = format_paper(paper, include_extended=False)
    if result is None:
        result = {}

    # Add citation-specific metadata
    result["isInfluential"] = citation.get("isInfluential", False)
    result["contexts"] = citation.get("contexts", [])
    result["intents"] = citation.get("intents", [])

    return result
