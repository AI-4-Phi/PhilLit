#!/usr/bin/env python3
"""
Environment verification script for philosophy-research skill.

Checks:
1. Required environment variables are set
2. Python dependencies are installed
3. APIs are reachable and responding

Usage:
    python check_setup.py           # Basic check
    python check_setup.py --verbose # Detailed output
    python check_setup.py --json    # JSON output for programmatic use
"""

import argparse
import importlib.metadata
import json
import os
import sys
from typing import Any

# Add parent directory to path for rate_limiter import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import get_limiter


def check_env_vars() -> dict[str, dict[str, Any]]:
    """Check environment variables."""
    results = {}

    # Required
    required = {
        "BRAVE_API_KEY": "Required for SEP/PhilPapers discovery",
        "CROSSREF_MAILTO": "Required for CrossRef polite pool",
    }

    # Recommended
    recommended = {
        "S2_API_KEY": "Recommended for Semantic Scholar (improves reliability)",
        "OPENALEX_EMAIL": "Recommended for OpenAlex polite pool",
        "CORE_API_KEY": "Optional for CORE API (improves rate limits)",
    }

    for var, description in required.items():
        value = os.environ.get(var, "")
        results[var] = {
            "set": bool(value),
            "required": True,
            "description": description,
            # Show first 4 and last 4 chars for verification without exposing key
            "preview": f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "[short]" if value else None,
        }

    for var, description in recommended.items():
        value = os.environ.get(var, "")
        results[var] = {
            "set": bool(value),
            "required": False,
            "description": description,
            "preview": f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "[short]" if value else None,
        }

    return results


def check_dependencies() -> dict[str, dict[str, Any]]:
    """Check Python package dependencies."""
    required_packages = {
        "requests": "2.28.0",
        "beautifulsoup4": "4.11.0",
        "lxml": "4.9.0",
        "arxiv": "1.4.0",
        "pymarkdownlnt": "0.9.0",
    }

    results = {}
    for package, min_version in required_packages.items():
        try:
            version = importlib.metadata.version(package)
            results[package] = {
                "installed": True,
                "version": version,
                "min_version": min_version,
            }
        except importlib.metadata.PackageNotFoundError:
            results[package] = {
                "installed": False,
                "version": None,
                "min_version": min_version,
            }

    return results


def check_api_connectivity(verbose: bool = False) -> dict[str, dict[str, Any]]:
    """Check API connectivity with minimal requests."""
    import requests

    results = {}

    # Semantic Scholar
    try:
        limiter = get_limiter("semantic_scholar")
        limiter.wait()
        headers = {}
        api_key = os.environ.get("S2_API_KEY", "")
        if api_key:
            headers["x-api-key"] = api_key

        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": "test", "limit": 1, "fields": "title"},
            headers=headers,
            timeout=10,
        )
        limiter.record()

        authenticated = bool(api_key)
        results["semantic_scholar"] = {
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "authenticated": authenticated,
            "message": "Responding" + (" (authenticated)" if authenticated else " (unauthenticated)"),
        }
    except Exception as e:
        results["semantic_scholar"] = {
            "reachable": False,
            "status_code": None,
            "authenticated": False,
            "message": str(e),
        }

    # CrossRef
    try:
        limiter = get_limiter("crossref")
        limiter.wait()
        mailto = os.environ.get("CROSSREF_MAILTO", "")
        params = {"query": "test", "rows": 1}
        if mailto:
            params["mailto"] = mailto

        response = requests.get(
            "https://api.crossref.org/works",
            params=params,
            timeout=10,
        )
        limiter.record()

        polite = bool(mailto)
        results["crossref"] = {
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "polite_pool": polite,
            "message": "Responding" + (" (polite pool)" if polite else " (public pool)"),
        }
    except Exception as e:
        results["crossref"] = {
            "reachable": False,
            "status_code": None,
            "polite_pool": False,
            "message": str(e),
        }

    # OpenAlex
    try:
        limiter = get_limiter("openalex")
        limiter.wait()
        email = os.environ.get("OPENALEX_EMAIL", "")
        params = {"search": "test", "per_page": 1}
        if email:
            params["mailto"] = email

        response = requests.get(
            "https://api.openalex.org/works",
            params=params,
            timeout=10,
        )
        limiter.record()

        polite = bool(email)
        results["openalex"] = {
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "polite_pool": polite,
            "message": "Responding" + (" (polite pool)" if polite else " (public pool)"),
        }
    except Exception as e:
        results["openalex"] = {
            "reachable": False,
            "status_code": None,
            "polite_pool": False,
            "message": str(e),
        }

    # Brave Search
    try:
        limiter = get_limiter("brave")
        limiter.wait()
        api_key = os.environ.get("BRAVE_API_KEY", "")

        if not api_key:
            results["brave"] = {
                "reachable": False,
                "status_code": None,
                "message": "BRAVE_API_KEY not set",
            }
        else:
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": "test", "count": 1},
                headers={"X-Subscription-Token": api_key},
                timeout=10,
            )
            limiter.record()

            results["brave"] = {
                "reachable": response.status_code == 200,
                "status_code": response.status_code,
                "message": "Responding" if response.status_code == 200 else f"Error: {response.status_code}",
            }
    except Exception as e:
        results["brave"] = {
            "reachable": False,
            "status_code": None,
            "message": str(e),
        }

    # arXiv (no auth needed, just check reachability)
    try:
        # Note: We don't use rate limiter for this simple check since arxiv library handles it
        response = requests.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": "all:test", "max_results": 1},
            timeout=10,
        )

        results["arxiv"] = {
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "message": "Responding" if response.status_code == 200 else f"Error: {response.status_code}",
        }
    except Exception as e:
        results["arxiv"] = {
            "reachable": False,
            "status_code": None,
            "message": str(e),
        }

    # CORE
    try:
        limiter = get_limiter("core")
        limiter.wait()
        api_key = os.environ.get("CORE_API_KEY", "")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.get(
            "https://api.core.ac.uk/v3/search/works",
            params={"q": "test", "limit": 1},
            headers=headers,
            timeout=10,
        )
        limiter.record()

        authenticated = bool(api_key)
        if response.status_code == 200:
            msg = "Responding" + (" (authenticated)" if authenticated else " (unauthenticated)")
        else:
            msg = f"Error: {response.status_code}"
        results["core"] = {
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "authenticated": authenticated,
            "message": msg,
        }
    except Exception as e:
        results["core"] = {
            "reachable": False,
            "status_code": None,
            "authenticated": False,
            "message": str(e),
        }

    return results


def print_results(env_results: dict, dep_results: dict, api_results: dict, verbose: bool = False) -> bool:
    """Print results in human-readable format. Returns True if all checks passed."""
    all_passed = True

    print("\nEnvironment Check Results")
    print("=" * 40)

    for var, info in env_results.items():
        if info["set"]:
            status = "[OK]"
            extra = " (recommended)" if not info["required"] else ""
            preview = f" [{info['preview']}]" if verbose and info["preview"] else ""
            print(f"{status} {var}: Set{extra}{preview}")
        else:
            if info["required"]:
                status = "[FAIL]"
                all_passed = False
            else:
                status = "[WARN]"
            print(f"{status} {var}: Not set - {info['description']}")

    print("\nDependencies Check")
    print("=" * 40)

    for package, info in dep_results.items():
        if info["installed"]:
            print(f"[OK] {package}: {info['version']}")
        else:
            print(f"[FAIL] {package}: Not installed (requires >= {info['min_version']})")
            all_passed = False

    print("\nAPI Connectivity Check")
    print("=" * 40)

    for api, info in api_results.items():
        if info["reachable"]:
            print(f"[OK] {api}: {info['message']}")
        else:
            print(f"[FAIL] {api}: {info['message']}")
            # Only fail on required APIs
            if api in ("brave", "crossref"):
                all_passed = False

    print()
    if all_passed:
        print("All required checks passed. Ready to use philosophy-research skill.")
    else:
        print("Some checks failed. Please fix the issues above before proceeding.")

    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Verify environment setup for philosophy-research skill"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including partial API key previews"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip API connectivity checks (faster)"
    )

    args = parser.parse_args()

    # Run checks
    env_results = check_env_vars()
    dep_results = check_dependencies()

    if args.skip_api:
        api_results = {}
    else:
        api_results = check_api_connectivity(verbose=args.verbose)

    # Output results
    if args.json:
        output = {
            "environment": env_results,
            "dependencies": dep_results,
            "apis": api_results,
        }

        # Calculate overall status
        required_env_ok = all(
            info["set"] for info in env_results.values() if info["required"]
        )
        deps_ok = all(info["installed"] for info in dep_results.values())
        apis_ok = all(info["reachable"] for info in api_results.values()) if api_results else True

        output["status"] = "ok" if (required_env_ok and deps_ok and apis_ok) else "error"

        print(json.dumps(output, indent=2))
        sys.exit(0 if output["status"] == "ok" else 1)
    else:
        all_passed = print_results(env_results, dep_results, api_results, verbose=args.verbose)
        sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
