"""
Shared citation context extraction utilities for SEP and IEP scripts.

Provides:
- Author name normalization
- Citation pattern building
- Sentence and context window extraction
- Citation finding in article structures
- Philosophical claim extraction
"""

import re
from typing import Optional


def normalize_author(author: str) -> str:
    """Normalize author name for matching.

    Handles:
    - "Frankfurt, Harry G." -> "frankfurt"
    - "Harry G. Frankfurt" -> "frankfurt"
    - "Fischer and Ravizza" -> "fischer"
    """
    author = author.strip()
    if "," in author:
        author = author.split(",")[0]
    else:
        parts = author.split()
        if parts:
            author = parts[-1]

    return author.lower().strip()


def build_citation_patterns(author: str, year: str, coauthor: Optional[str] = None) -> list[re.Pattern]:
    """Build regex patterns to match citations in academic encyclopedia style.

    Matches formats like:
    - Frankfurt (1971)
    - Frankfurt 1971
    - Frankfurt [1971]
    - (Frankfurt 1971)
    - (Frankfurt, 1971)
    - Frankfurt and Ravizza (1998)
    - Fischer & Ravizza 1998
    """
    author_norm = normalize_author(author)
    patterns = []

    single_patterns = [
        rf"\b{author_norm}\s*\(\s*{year}\s*\)",
        rf"\b{author_norm}\s+{year}\b",
        rf"\b{author_norm}\s*\[\s*{year}\s*\]",
        rf"\(\s*{author_norm}\s+{year}\s*\)",
        rf"\(\s*{author_norm}\s*,\s*{year}\s*\)",
    ]

    for p in single_patterns:
        patterns.append(re.compile(p, re.IGNORECASE))

    if coauthor:
        coauthor_norm = normalize_author(coauthor)
        two_author_patterns = [
            rf"\b{author_norm}\s+and\s+{coauthor_norm}\s*\(\s*{year}\s*\)",
            rf"\b{author_norm}\s*&\s*{coauthor_norm}\s*\(\s*{year}\s*\)",
            rf"\b{author_norm}\s+and\s+{coauthor_norm}\s+{year}\b",
            rf"\(\s*{author_norm}\s+and\s+{coauthor_norm}\s+{year}\s*\)",
            rf"\(\s*{author_norm}\s*&\s*{coauthor_norm}\s+{year}\s*\)",
        ]
        for p in two_author_patterns:
            patterns.append(re.compile(p, re.IGNORECASE))

    return patterns


def extract_sentence(text: str, match_start: int, match_end: int) -> str:
    """Extract the sentence containing the citation match."""
    sentence_ends = [m.end() for m in re.finditer(r'[.!?]\s+', text[:match_start])]
    sentence_start = sentence_ends[-1] if sentence_ends else 0

    end_match = re.search(r'[.!?]\s+', text[match_end:])
    if end_match:
        sentence_end = match_end + end_match.end()
    else:
        sentence_end = min(match_end + 200, len(text))

    return text[sentence_start:sentence_end].strip()


def extract_context_window(text: str, match_start: int, match_end: int, window: int = 500) -> str:
    """Extract a context window around the citation."""
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)

    if start > 0:
        space = text.rfind(" ", 0, start)
        if space != -1:
            start = space + 1

    if end < len(text):
        space = text.find(" ", end)
        if space != -1:
            end = space

    return text[start:end].strip()


def find_citations(article: dict, patterns: list[re.Pattern]) -> list[dict]:
    """Find all citations matching the patterns in the article."""
    contexts = []

    # Search in preamble
    if article.get("preamble"):
        text = article["preamble"]
        for pattern in patterns:
            for match in pattern.finditer(text):
                contexts.append({
                    "section": "preamble",
                    "section_title": "Preamble",
                    "citation_text": match.group(),
                    "sentence": extract_sentence(text, match.start(), match.end()),
                    "context": extract_context_window(text, match.start(), match.end()),
                    "position_in_text": match.start(),
                })

    # Search in sections
    for sec_id, section in article.get("sections", {}).items():
        text = section.get("content", "")
        if not text:
            continue

        for pattern in patterns:
            for match in pattern.finditer(text):
                contexts.append({
                    "section": sec_id,
                    "section_title": section.get("title", ""),
                    "citation_text": match.group(),
                    "sentence": extract_sentence(text, match.start(), match.end()),
                    "context": extract_context_window(text, match.start(), match.end()),
                    "position_in_text": match.start(),
                })

    # Deduplicate by position (multiple patterns may match same citation)
    seen = set()
    unique = []
    for ctx in contexts:
        key = (ctx["section"], ctx["position_in_text"])
        if key not in seen:
            seen.add(key)
            unique.append(ctx)

    return sorted(unique, key=lambda x: (x["section"], x["position_in_text"]))


def extract_claims(contexts: list[dict]) -> list[dict]:
    """Attempt to extract the philosophical claim/position from each context.

    Looks for patterns like:
    - "X argues that..."
    - "X's view is that..."
    - "According to X..."
    """
    claim_patterns = [
        r"argues?\s+that\s+(.{20,200}?)(?:[.!?]|,\s*(?:but|however|although))",
        r"claim(?:s|ed)?\s+that\s+(.{20,200}?)(?:[.!?]|,\s*(?:but|however|although))",
        r"contends?\s+that\s+(.{20,200}?)(?:[.!?]|,\s*(?:but|however|although))",
        r"maintains?\s+that\s+(.{20,200}?)(?:[.!?]|,\s*(?:but|however|although))",
        r"view(?:\s+is)?\s+that\s+(.{20,200}?)(?:[.!?]|,\s*(?:but|however|although))",
        r"according\s+to\s+\w+(?:\s+and\s+\w+)?,?\s+(.{20,200}?)(?:[.!?]|,\s*(?:but|however|although))",
        r"position(?:\s+is)?\s+that\s+(.{20,200}?)(?:[.!?]|,\s*(?:but|however|although))",
    ]

    for ctx in contexts:
        sentence = ctx.get("sentence", "")
        claims = []

        for pattern in claim_patterns:
            for match in re.finditer(pattern, sentence, re.IGNORECASE):
                claim = match.group(1).strip()
                if len(claim) > 15:
                    claims.append(claim)

        if claims:
            ctx["extracted_claims"] = claims

    return contexts
