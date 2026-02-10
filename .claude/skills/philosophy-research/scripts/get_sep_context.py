#!/usr/bin/env python3
"""
Extract citation contexts from SEP articles for a specific paper.

Given a paper (author, year) and an SEP entry, finds all citations to that paper
and extracts the surrounding context and attributed claims.

Usage:
    python get_sep_context.py freewill --author "Frankfurt" --year 1971
    python get_sep_context.py compatibilism --author "Fischer" --year 1998 --coauthor "Ravizza"

Exit Codes: 0=success, 1=not found, 2=config error, 3=network error
"""

import argparse
import json
import re
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_sep import fetch_sep_article
from rate_limiter import ExponentialBackoff, get_limiter


def log_progress(message: str) -> None:
    """Emit progress to stderr."""
    print(f"[get_sep_context.py] {message}", file=sys.stderr, flush=True)


def output_success(query: dict, contexts: list) -> None:
    print(json.dumps({
        "status": "success",
        "source": "sep_context",
        "query": query,
        "results": contexts,
        "count": len(contexts),
        "errors": []
    }, indent=2))
    sys.exit(0)


def output_error(query: dict, error_type: str, message: str, exit_code: int = 2) -> None:
    print(json.dumps({
        "status": "error",
        "source": "sep_context",
        "query": query,
        "results": [],
        "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": False}]
    }, indent=2))
    sys.exit(exit_code)


def normalize_author(author: str) -> str:
    """Normalize author name for matching.

    Handles:
    - "Frankfurt, Harry G." -> "frankfurt"
    - "Harry G. Frankfurt" -> "frankfurt"
    - "Fischer and Ravizza" -> "fischer"
    """
    # Take last name only
    author = author.strip()
    if "," in author:
        # "Last, First" format
        author = author.split(",")[0]
    else:
        # "First Last" format - take last word
        parts = author.split()
        if parts:
            author = parts[-1]

    return author.lower().strip()


def build_citation_patterns(author: str, year: str, coauthor: Optional[str] = None) -> list[re.Pattern]:
    """Build regex patterns to match citations in SEP style.

    SEP uses various citation formats:
    - Frankfurt (1971)
    - Frankfurt 1971
    - Frankfurt [1971]
    - (Frankfurt 1971)
    - Frankfurt and Ravizza (1998)
    - Fischer & Ravizza 1998
    """
    author_norm = normalize_author(author)
    patterns = []

    # Single author patterns
    single_patterns = [
        rf"\b{author_norm}\s*\(\s*{year}\s*\)",  # Frankfurt (1971)
        rf"\b{author_norm}\s+{year}\b",  # Frankfurt 1971
        rf"\b{author_norm}\s*\[\s*{year}\s*\]",  # Frankfurt [1971]
        rf"\(\s*{author_norm}\s+{year}\s*\)",  # (Frankfurt 1971)
        rf"\(\s*{author_norm}\s*,\s*{year}\s*\)",  # (Frankfurt, 1971)
    ]

    for p in single_patterns:
        patterns.append(re.compile(p, re.IGNORECASE))

    # Two author patterns
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
    # Find sentence boundaries
    sentence_ends = [m.end() for m in re.finditer(r'[.!?]\s+', text[:match_start])]
    sentence_start = sentence_ends[-1] if sentence_ends else 0

    # Find end of sentence
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

    # Adjust to word boundaries
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
                if len(claim) > 15:  # Filter out very short fragments
                    claims.append(claim)

        if claims:
            ctx["extracted_claims"] = claims

    return contexts


def main():
    parser = argparse.ArgumentParser(description="Extract SEP citation contexts for a paper")
    parser.add_argument("entry", help="SEP entry name or URL")
    parser.add_argument("--author", required=True, help="Primary author last name")
    parser.add_argument("--year", required=True, help="Publication year")
    parser.add_argument("--coauthor", help="Co-author last name (for two-author works)")
    parser.add_argument("--window", type=int, default=500, help="Context window size in characters")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    # Extract entry name from URL if needed
    entry_name = args.entry
    if "plato.stanford.edu" in entry_name:
        match = re.search(r"/entries/([^/]+)/?", entry_name)
        if match:
            entry_name = match.group(1)
        else:
            output_error(
                {"entry": args.entry, "author": args.author, "year": args.year},
                "config_error",
                "Could not extract entry name from URL"
            )

    query = {
        "entry": entry_name,
        "author": args.author,
        "year": args.year,
        "coauthor": args.coauthor,
    }

    limiter = get_limiter("sep_fetch")
    backoff = ExponentialBackoff(max_attempts=5)

    try:
        log_progress(f"Fetching SEP article: {entry_name}")
        article = fetch_sep_article(entry_name, limiter, backoff, args.debug)

        log_progress(f"Building citation patterns for {args.author} ({args.year})")
        patterns = build_citation_patterns(args.author, args.year, args.coauthor)

        log_progress(f"Searching for citations...")
        contexts = find_citations(article, patterns)

        if not contexts:
            log_progress(f"No citations found for {args.author} ({args.year}) in {entry_name}")
            output_success(query, [])

        log_progress(f"Found {len(contexts)} citation(s), extracting claims...")
        contexts = extract_claims(contexts)

        # Add article metadata
        result = {
            "entry_name": entry_name,
            "entry_title": article.get("title"),
            "entry_url": article.get("url"),
            "paper": {
                "author": args.author,
                "year": args.year,
                "coauthor": args.coauthor,
            },
            "citation_count": len(contexts),
            "citations": contexts,
        }

        log_progress(f"Found {len(contexts)} citations with context")
        output_success(query, [result])

    except LookupError as e:
        output_error(query, "not_found", str(e), 1)
    except Exception as e:
        output_error(query, "error", str(e), 3)


if __name__ == "__main__":
    main()
