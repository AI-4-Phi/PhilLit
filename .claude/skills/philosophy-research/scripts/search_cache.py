#!/usr/bin/env python3
"""
Simple filesystem-based caching for search results.

Cache keys are generated from query parameters and results are stored as
pickled files with timestamps. Stale entries are automatically cleaned up.

Usage:
    from search_cache import get_cache, put_cache, cache_key

    key = cache_key(source="s2", query="free will", limit=20)
    cached = get_cache(key)
    if cached:
        return cached

    results = expensive_search()
    put_cache(key, results)
"""

import hashlib
import json
import os
import pickle
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

# Cache configuration - use system temp dir for cross-platform compatibility
CACHE_DIR = Path(tempfile.gettempdir()) / "philosophy_research_cache"
DEFAULT_TTL = 7 * 24 * 60 * 60  # 7 days in seconds


def cache_key(source: str, **params) -> str:
    """
    Generate a cache key from source and parameters.

    Args:
        source: Data source name (e.g., "s2", "openalex", "arxiv")
        **params: Query parameters to include in the key

    Returns:
        SHA256 hash of the normalized parameters

    Example:
        >>> cache_key(source="s2", query="free will", limit=20)
        's2_a1b2c3d4...'
    """
    # Sort params for consistent hashing
    sorted_params = sorted(params.items())

    # Create stable JSON representation
    param_str = json.dumps(sorted_params, sort_keys=True)

    # Hash the parameters
    hash_obj = hashlib.sha256(param_str.encode())
    hash_hex = hash_obj.hexdigest()[:16]  # Use first 16 chars

    return f"{source}_{hash_hex}"


def get_cache(key: str, ttl: int = DEFAULT_TTL) -> Optional[Any]:
    """
    Retrieve cached result if it exists and is fresh.

    Args:
        key: Cache key from cache_key()
        ttl: Time-to-live in seconds (default: 7 days)

    Returns:
        Cached result if found and fresh, None otherwise
    """
    cache_file = CACHE_DIR / f"{key}.pkl"

    if not cache_file.exists():
        return None

    try:
        # Check if cache is stale
        mtime = cache_file.stat().st_mtime
        age = time.time() - mtime

        if age >= ttl:
            # Stale cache, remove it
            cache_file.unlink()
            return None

        # Load and return cached result
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    except (OSError, pickle.PickleError):
        # Corrupted or inaccessible cache, remove it
        try:
            cache_file.unlink()
        except OSError:
            pass
        return None


def put_cache(key: str, result: Any) -> bool:
    """
    Store result in cache.

    Args:
        key: Cache key from cache_key()
        result: Result to cache (must be picklable)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        cache_file = CACHE_DIR / f"{key}.pkl"

        # Write to temp file first, then rename for atomicity
        temp_file = cache_file.with_suffix(".tmp")
        with open(temp_file, "wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)

        # Atomic rename
        temp_file.replace(cache_file)

        return True

    except (OSError, pickle.PickleError):
        return False


def clear_cache(source: Optional[str] = None) -> int:
    """
    Clear cache entries.

    Args:
        source: If provided, only clear entries for this source.
                If None, clear entire cache.

    Returns:
        Number of entries removed
    """
    if not CACHE_DIR.exists():
        return 0

    count = 0
    pattern = f"{source}_*.pkl" if source else "*.pkl"

    for cache_file in CACHE_DIR.glob(pattern):
        try:
            cache_file.unlink()
            count += 1
        except OSError:
            pass

    return count


def cache_stats() -> dict:
    """
    Get cache statistics.

    Returns:
        Dict with cache size, entry count, oldest/newest timestamps
    """
    if not CACHE_DIR.exists():
        return {
            "exists": False,
            "entry_count": 0,
            "total_size_bytes": 0,
        }

    entries = list(CACHE_DIR.glob("*.pkl"))

    if not entries:
        return {
            "exists": True,
            "entry_count": 0,
            "total_size_bytes": 0,
        }

    total_size = sum(f.stat().st_size for f in entries)
    oldest = min(f.stat().st_mtime for f in entries)
    newest = max(f.stat().st_mtime for f in entries)

    return {
        "exists": True,
        "entry_count": len(entries),
        "total_size_bytes": total_size,
        "oldest_entry_age_seconds": time.time() - oldest,
        "newest_entry_age_seconds": time.time() - newest,
    }


if __name__ == "__main__":
    # Simple CLI for cache management
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Manage philosophy research cache")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--clear", action="store_true", help="Clear entire cache")
    parser.add_argument("--clear-source", metavar="SOURCE", help="Clear cache for specific source")

    args = parser.parse_args()

    if args.stats:
        stats = cache_stats()
        print(json.dumps(stats, indent=2))

    elif args.clear:
        count = clear_cache()
        print(f"Cleared {count} cache entries")

    elif args.clear_source:
        count = clear_cache(args.clear_source)
        print(f"Cleared {count} cache entries for source '{args.clear_source}'")

    else:
        parser.print_help()
        sys.exit(1)
