"""
Pytest configuration and shared fixtures for philosophy-research skill tests.

These tests validate:
- JSON output schema compliance
- Exit code correctness
- Error handling
- Rate limiting and caching behavior
"""

import os
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

@pytest.fixture(autouse=True, scope="session")
def _no_ambient_openalex_key():
    """Strip OPENALEX_API_KEY from the environment for the whole session.

    Item 3 D (venue vetting) added a real-network OpenAlex pass inside
    evidence_barrier.py, gated on this key. Several barrier tests run the
    script via subprocess and inherit the parent environment verbatim, so a
    developer's real key would otherwise make the suite spend real, metered
    OpenAlex budget ($1/day on a keyed account) every time it runs --
    silently, since venue-vetting failures never fail a test. Tests that
    need the key set it themselves with monkeypatch.setenv, which still
    works: this fixture only removes what was ambient before any test ran.

    This fixture is NECESSARY but not, by itself, SUFFICIENT: evidence_
    barrier.main() calls load_dotenv(find_dotenv(usecwd=True), override=
    True), which re-reads OPENALEX_API_KEY from a .env found by walking up
    from the subprocess's cwd and OVERRIDES the stripped environment with
    it. A repo-root .env (exactly what .env.example and /phillit:setup
    tell developers to create) would defeat this fixture on its own. The
    other half of the fix is in test_evidence_barrier.py's _run(): it runs
    the subprocess with cwd=review_dir, a tmp_path directory outside the
    repo tree, so that upward search can never reach a repo-root .env.
    Both halves are required together; this fixture alone protects only
    developer checkouts that have no .env at all.

    Also strips PHILLIT_VET_VENUES -- same ambient-leak path, opposite
    direction (it could disable a gate a test asserts on).
    """
    saved = os.environ.pop("OPENALEX_API_KEY", None)
    saved_flag = os.environ.pop("PHILLIT_VET_VENUES", None)
    try:
        yield
    finally:
        os.environ.pop("OPENALEX_API_KEY", None)
        os.environ.pop("PHILLIT_VET_VENUES", None)
        if saved is not None:
            os.environ["OPENALEX_API_KEY"] = saved
        if saved_flag is not None:
            os.environ["PHILLIT_VET_VENUES"] = saved_flag


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
