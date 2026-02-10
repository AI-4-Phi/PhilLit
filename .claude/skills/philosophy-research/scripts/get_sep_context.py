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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from citation_context import (
    normalize_author, build_citation_patterns, extract_sentence,
    extract_context_window, find_citations, extract_claims,
)
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
        else:
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
