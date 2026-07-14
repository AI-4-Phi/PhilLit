"""
Pytest configuration and shared fixtures for philosophy-research skill tests.

These tests validate:
- JSON output schema compliance
- Exit code correctness
- Error handling
- Rate limiting and caching behavior
"""

import sys
from pathlib import Path

import pytest

# Add tests directory to path for test_utils import
sys.path.insert(0, str(Path(__file__).parent))

# Import shared utilities
from test_utils import (
    SCRIPTS_DIR,
    validate_output_schema,
    run_script,
)

# Import the modules themselves so the isolation fixture stays in lockstep with the code
sys.path.insert(0, str(SCRIPTS_DIR))
import search_cache  # noqa: E402
from rate_limiter import RateLimiter  # noqa: E402


# =============================================================================
# Path Fixtures
# =============================================================================

@pytest.fixture
def scripts_dir() -> Path:
    """Return path to skill scripts directory."""
    return SCRIPTS_DIR


@pytest.fixture
def project_root() -> Path:
    """Return path to project root."""
    return Path(__file__).parent.parent


# =============================================================================
# Schema Validation Fixture
# =============================================================================

@pytest.fixture
def validate_schema():
    """Fixture that returns the schema validator function."""
    return validate_output_schema


# =============================================================================
# Script Execution Fixture
# =============================================================================

@pytest.fixture
def run_skill_script():
    """Fixture that returns the script runner function."""
    return run_script


# =============================================================================
# Mock Response Fixtures
# =============================================================================

@pytest.fixture
def mock_s2_response():
    """Sample Semantic Scholar API response."""
    return {
        "total": 2,
        "offset": 0,
        "data": [
            {
                "paperId": "abc123",
                "title": "Free Will and Moral Responsibility",
                "authors": [{"name": "Harry Frankfurt", "authorId": "12345"}],
                "year": 1971,
                "abstract": "This paper examines the concept of free will...",
                "citationCount": 1500,
                "externalIds": {"DOI": "10.2307/2024717"},
                "url": "https://www.semanticscholar.org/paper/abc123",
                "venue": "Journal of Philosophy",
                "publicationTypes": ["JournalArticle"],
                "journal": {"name": "Journal of Philosophy"},
            },
            {
                "paperId": "def456",
                "title": "Compatibilism and Free Will",
                "authors": [{"name": "Susan Wolf", "authorId": "67890"}],
                "year": 1990,
                "abstract": "An exploration of compatibilist accounts...",
                "citationCount": 500,
                "externalIds": {"DOI": "10.1093/mind/xyz"},
                "url": "https://www.semanticscholar.org/paper/def456",
                "venue": "Mind",
                "publicationTypes": ["JournalArticle"],
                "journal": {"name": "Mind"},
            },
        ],
    }


@pytest.fixture
def mock_openalex_response():
    """Sample OpenAlex API response."""
    return {
        "meta": {"count": 2, "next_cursor": None},
        "results": [
            {
                "id": "https://openalex.org/W2741809807",
                "doi": "https://doi.org/10.2307/2024717",
                "title": "Freedom of the Will and the Concept of a Person",
                "authorships": [
                    {
                        "author": {
                            "id": "https://openalex.org/A123",
                            "display_name": "Harry G. Frankfurt",
                        },
                        "institutions": [{"display_name": "Princeton University"}],
                    }
                ],
                "publication_year": 1971,
                "cited_by_count": 1500,
                "type": "journal-article",
                "primary_location": {
                    "source": {
                        "display_name": "Journal of Philosophy",
                        "type": "journal",
                    }
                },
                "abstract_inverted_index": {"This": [0], "paper": [1], "examines": [2]},
            }
        ],
    }


@pytest.fixture
def mock_crossref_response():
    """Sample CrossRef API response."""
    return {
        "status": "ok",
        "message": {
            "DOI": "10.2307/2024717",
            "title": ["Freedom of the Will and the Concept of a Person"],
            "author": [{"given": "Harry G.", "family": "Frankfurt"}],
            "published": {"date-parts": [[1971, 1]]},
            "container-title": ["The Journal of Philosophy"],
            "publisher": "Philosophy Documentation Center",
            "type": "journal-article",
        },
    }


# =============================================================================
# Isolation Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def isolated_phillit_dirs(tmp_path, monkeypatch):
    """Redirect the per-user cache/lock dirs to tmp_path for every test.

    The suite must never touch — let alone wipe — the developer's live
    ~/.cache/phillit: the search cache is a durable asset (7-day TTL), and
    deleting live rate-limit locks mid-review would let a concurrent session
    burst an API. Per-test tmp_path isolation also replaces the old
    delete-before-and-after cleanup fixtures.
    """
    monkeypatch.setattr(RateLimiter, "LOCK_DIR", tmp_path / "phillit-ratelimits")
    monkeypatch.setattr(search_cache, "CACHE_DIR", tmp_path / "phillit-search-cache")
