#!/usr/bin/env python3
"""
Search arXiv for preprints and recent papers.

Usage:
    python search_arxiv.py "free will consciousness"
    python search_arxiv.py "AI ethics" --category cs.AI --limit 50
    python search_arxiv.py --id "2301.00001"
    python search_arxiv.py --author "Chalmers" --title "consciousness"

Exit Codes: 0=success, 1=not found, 2=config error, 3=API error
"""

import argparse
import json
import os
import sys
from typing import Optional

import arxiv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rate_limiter import get_limiter


def output_success(query: str, results: list) -> None:
    print(json.dumps({
        "status": "success", "source": "arxiv", "query": query,
        "results": results, "count": len(results), "errors": []
    }, indent=2))
    sys.exit(0)


def output_error(query: str, error_type: str, message: str, exit_code: int = 2) -> None:
    print(json.dumps({
        "status": "error", "source": "arxiv", "query": query,
        "results": [], "count": 0,
        "errors": [{"type": error_type, "message": message, "recoverable": error_type == "rate_limit"}]
    }, indent=2))
    sys.exit(exit_code)


def format_result(result: arxiv.Result) -> dict:
    arxiv_id = result.entry_id.split("/abs/")[-1]
    if "v" in arxiv_id:
        arxiv_id = arxiv_id.split("v")[0]

    return {
        "arxiv_id": arxiv_id,
        "title": result.title.replace("\n", " "),
        "authors": [a.name for a in result.authors],
        "abstract": result.summary.replace("\n", " "),
        "published": result.published.strftime("%Y-%m-%d") if result.published else None,
        "updated": result.updated.strftime("%Y-%m-%d") if result.updated else None,
        "primary_category": result.primary_category,
        "categories": result.categories,
        "doi": result.doi,
        "journal_ref": result.journal_ref,
        "pdf_url": result.pdf_url,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def main():
    parser = argparse.ArgumentParser(description="Search arXiv for papers")
    parser.add_argument("query", nargs="?", help="Search terms")
    parser.add_argument("--author", help="Filter by author name")
    parser.add_argument("--title", help="Filter by title")
    parser.add_argument("--abstract", help="Filter by abstract")
    parser.add_argument("--category", help="arXiv category (e.g., cs.AI)")
    parser.add_argument("--id", help="Lookup specific arXiv ID")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--recent", action="store_true", help="Sort by submission date")
    parser.add_argument("--year", help="Filter to specific year")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if not args.query and not args.id and not args.author and not args.title:
        output_error("", "config_error", "Must provide query, --id, --author, or --title")

    limiter = get_limiter("arxiv")
    client = arxiv.Client(page_size=min(args.limit, 100), delay_seconds=0, num_retries=3)

    try:
        if args.id:
            arxiv_id = args.id.replace("arXiv:", "").replace("arxiv:", "")
            limiter.wait()
            search = arxiv.Search(id_list=[arxiv_id])
            results = list(client.results(search))
            limiter.record()

            if not results:
                output_error(args.id, "not_found", f"arXiv ID not found: {arxiv_id}", 1)
            output_success(args.id, [format_result(results[0])])

        else:
            # Build query
            query_parts = []
            if args.query:
                query_parts.append(f"all:{args.query}")
            if args.author:
                query_parts.append(f"au:{args.author}")
            if args.title:
                query_parts.append(f"ti:{args.title}")
            if args.abstract:
                query_parts.append(f"abs:{args.abstract}")
            if args.category:
                query_parts.append(f"cat:{args.category}")

            query_str = " AND ".join(query_parts)

            sort_by = arxiv.SortCriterion.SubmittedDate if args.recent else arxiv.SortCriterion.Relevance

            limiter.wait()
            search = arxiv.Search(
                query=query_str,
                max_results=args.limit,
                sort_by=sort_by,
                sort_order=arxiv.SortOrder.Descending
            )

            results = []
            for result in client.results(search):
                if args.year:
                    if result.published and str(result.published.year) != args.year:
                        continue
                results.append(format_result(result))
                if len(results) >= args.limit:
                    break

            limiter.record()

            if not results:
                output_error(query_str, "not_found", "No papers found", 1)

            output_success(query_str, results)

    except arxiv.HTTPError as e:
        output_error(args.query or args.id, "api_error", str(e), 3)
    except Exception as e:
        output_error(args.query or args.id, "api_error", str(e), 3)


if __name__ == "__main__":
    main()
