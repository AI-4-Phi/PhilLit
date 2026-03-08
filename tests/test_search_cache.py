"""
Tests for the search_cache module.

Tests cover:
- Cache key generation
- Cache storage and retrieval
- TTL expiration
- Cache clearing and statistics
"""

import time
from pathlib import Path

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "philosophy-research" / "scripts"))

from search_cache import (
    cache_key,
    get_cache,
    put_cache,
    clear_cache,
    cache_stats,
    CACHE_DIR,
)


class TestCacheKey:
    """Tests for cache key generation."""

    def test_generates_prefixed_key(self):
        """Cache key should be prefixed with source name."""
        key = cache_key(source="s2", query="test")
        assert key.startswith("s2_")

    def test_same_params_same_key(self):
        """Same parameters should produce same key."""
        key1 = cache_key(source="s2", query="free will", limit=20)
        key2 = cache_key(source="s2", query="free will", limit=20)
        assert key1 == key2

    def test_different_params_different_key(self):
        """Different parameters should produce different keys."""
        key1 = cache_key(source="s2", query="free will", limit=20)
        key2 = cache_key(source="s2", query="free will", limit=30)
        assert key1 != key2

    def test_param_order_independent(self):
        """Parameter order should not affect key."""
        key1 = cache_key(source="s2", query="test", limit=20, year="2020")
        key2 = cache_key(source="s2", year="2020", limit=20, query="test")
        assert key1 == key2

    def test_different_sources_different_keys(self):
        """Same query with different sources should produce different keys."""
        key1 = cache_key(source="s2", query="test")
        key2 = cache_key(source="openalex", query="test")
        assert key1 != key2


class TestPutGetCache:
    """Tests for cache storage and retrieval."""

    def test_put_and_get_simple(self, clean_cache):
        """Should store and retrieve simple data."""
        key = cache_key(source="test", query="simple")
        data = {"results": [1, 2, 3], "count": 3}

        assert put_cache(key, data) is True
        retrieved = get_cache(key)
        assert retrieved == data

    def test_put_and_get_complex(self, clean_cache):
        """Should store and retrieve complex nested data."""
        key = cache_key(source="test", query="complex")
        data = {
            "results": [
                {"title": "Paper 1", "authors": ["Alice", "Bob"]},
                {"title": "Paper 2", "authors": ["Charlie"]},
            ],
            "count": 2,
            "metadata": {"source": "test", "timestamp": time.time()},
        }

        assert put_cache(key, data) is True
        retrieved = get_cache(key)
        assert retrieved == data

    def test_get_nonexistent_returns_none(self, clean_cache):
        """Getting non-existent key should return None."""
        key = cache_key(source="test", query="nonexistent")
        assert get_cache(key) is None

    def test_put_creates_cache_dir(self, clean_cache):
        """put_cache should create cache directory if needed."""
        # Remove cache dir if exists
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*"):
                f.unlink()
            CACHE_DIR.rmdir()

        key = cache_key(source="test", query="create_dir")
        put_cache(key, {"test": True})

        assert CACHE_DIR.exists()


class TestCacheTTL:
    """Tests for cache TTL (time-to-live) behavior."""

    def test_fresh_cache_returned(self, clean_cache):
        """Fresh cache entries should be returned."""
        key = cache_key(source="test", query="fresh")
        put_cache(key, {"fresh": True})

        # Should be returned with default TTL
        result = get_cache(key)
        assert result == {"fresh": True}

    def test_stale_cache_returns_none(self, clean_cache):
        """Stale cache entries should return None."""
        key = cache_key(source="test", query="stale")
        put_cache(key, {"stale": True})

        # Get with very short TTL (entry is already "expired")
        result = get_cache(key, ttl=0)
        assert result is None

    def test_stale_cache_removed(self, clean_cache):
        """Stale cache entries should be removed from disk."""
        key = cache_key(source="test", query="stale_remove")
        put_cache(key, {"data": True})

        cache_file = CACHE_DIR / f"{key}.pkl"
        assert cache_file.exists()

        # Access with expired TTL
        get_cache(key, ttl=0)

        # File should be removed
        assert not cache_file.exists()


class TestClearCache:
    """Tests for cache clearing."""

    def test_clear_all(self, clean_cache):
        """clear_cache() should remove all entries."""
        # Add some entries
        put_cache(cache_key(source="s2", query="1"), {"a": 1})
        put_cache(cache_key(source="openalex", query="2"), {"b": 2})
        put_cache(cache_key(source="arxiv", query="3"), {"c": 3})

        count = clear_cache()
        assert count == 3

        # Verify all gone
        assert get_cache(cache_key(source="s2", query="1")) is None
        assert get_cache(cache_key(source="openalex", query="2")) is None
        assert get_cache(cache_key(source="arxiv", query="3")) is None

    def test_clear_by_source(self, clean_cache):
        """clear_cache(source) should only remove entries for that source."""
        put_cache(cache_key(source="s2", query="1"), {"a": 1})
        put_cache(cache_key(source="s2", query="2"), {"b": 2})
        put_cache(cache_key(source="openalex", query="3"), {"c": 3})

        count = clear_cache(source="s2")
        assert count == 2

        # S2 entries should be gone
        assert get_cache(cache_key(source="s2", query="1")) is None
        assert get_cache(cache_key(source="s2", query="2")) is None

        # OpenAlex entry should remain
        assert get_cache(cache_key(source="openalex", query="3")) == {"c": 3}

    def test_clear_empty_cache(self, clean_cache):
        """Clearing empty cache should return 0."""
        count = clear_cache()
        assert count == 0


class TestCacheStats:
    """Tests for cache statistics."""

    def test_stats_empty_cache(self, clean_cache):
        """Stats for empty cache should show zero entries."""
        stats = cache_stats()
        assert stats["entry_count"] == 0
        assert stats["total_size_bytes"] == 0

    def test_stats_with_entries(self, clean_cache):
        """Stats should reflect actual cache contents."""
        put_cache(cache_key(source="test", query="1"), {"data": "a" * 100})
        put_cache(cache_key(source="test", query="2"), {"data": "b" * 200})

        stats = cache_stats()
        assert stats["exists"] is True
        assert stats["entry_count"] == 2
        assert stats["total_size_bytes"] > 0

    def test_stats_includes_timestamps(self, clean_cache):
        """Stats should include age information."""
        put_cache(cache_key(source="test", query="1"), {"data": True})

        stats = cache_stats()
        assert "oldest_entry_age_seconds" in stats
        assert "newest_entry_age_seconds" in stats
        assert stats["oldest_entry_age_seconds"] >= 0
        assert stats["newest_entry_age_seconds"] >= 0


class TestCacheEdgeCases:
    """Tests for edge cases and error handling."""

    def test_cache_handles_none_values(self, clean_cache):
        """Known limitation: caching None is unsupported.

        get_cache() returns None for both a cache miss and a cached None value,
        so callers cannot distinguish the two. This test documents the ambiguity —
        put_cache(key, None) silently succeeds but the stored value is
        indistinguishable from a miss.
        """
        key = cache_key(source="test", query="none")
        put_cache(key, None)
        assert get_cache(key) is None  # Indistinguishable from cache miss

    def test_cache_handles_empty_list(self, clean_cache):
        """Cache should handle empty lists."""
        key = cache_key(source="test", query="empty")
        put_cache(key, [])
        assert get_cache(key) == []

    def test_cache_handles_unicode(self, clean_cache):
        """Cache should handle unicode strings."""
        key = cache_key(source="test", query="unicode")
        data = {"title": "Über die Freiheit", "author": "Müller"}
        put_cache(key, data)
        assert get_cache(key) == data

    def test_cache_key_with_special_chars(self, clean_cache):
        """Cache key generation should handle special characters."""
        # Should not raise
        key = cache_key(source="test", query="free will & moral responsibility")
        assert key.startswith("test_")
        assert len(key) > 5
