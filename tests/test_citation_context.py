"""
Tests for citation_context.py (shared citation context extraction utilities).

Tests cover the core shared functions that SEP and IEP context scripts both use.
"""

import re
import sys
from pathlib import Path

import pytest

# Add script directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / ".claude" / "skills" / "philosophy-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from citation_context import (
    normalize_author, build_citation_patterns, extract_sentence,
    extract_context_window, find_citations, extract_claims,
)


class TestNormalizeAuthor:
    """Tests for normalize_author function."""

    def test_last_first_format(self):
        assert normalize_author("Frankfurt, Harry G.") == "frankfurt"

    def test_first_last_format(self):
        assert normalize_author("Harry Frankfurt") == "frankfurt"

    def test_multi_word_name(self):
        assert normalize_author("John Martin Fischer") == "fischer"

    def test_strips_whitespace(self):
        assert normalize_author("  Frankfurt  ") == "frankfurt"

    def test_single_name(self):
        assert normalize_author("Aristotle") == "aristotle"


class TestBuildCitationPatterns:
    """Tests for build_citation_patterns function."""

    def test_single_author_parenthetical(self):
        patterns = build_citation_patterns("Frankfurt", "1971")
        assert any(p.search("Frankfurt (1971)") for p in patterns)

    def test_single_author_inline(self):
        patterns = build_citation_patterns("Frankfurt", "1971")
        assert any(p.search("Frankfurt 1971") for p in patterns)

    def test_single_author_brackets(self):
        patterns = build_citation_patterns("Frankfurt", "1971")
        assert any(p.search("Frankfurt [1971]") for p in patterns)

    def test_two_author_and(self):
        patterns = build_citation_patterns("Fischer", "1998", coauthor="Ravizza")
        assert any(p.search("Fischer and Ravizza (1998)") for p in patterns)

    def test_two_author_ampersand(self):
        patterns = build_citation_patterns("Fischer", "1998", coauthor="Ravizza")
        assert any(p.search("Fischer & Ravizza (1998)") for p in patterns)

    def test_case_insensitive(self):
        patterns = build_citation_patterns("Frankfurt", "1971")
        assert any(p.search("frankfurt (1971)") for p in patterns)

    def test_no_coauthor_patterns_without_coauthor(self):
        patterns = build_citation_patterns("Frankfurt", "1971")
        # Should only have single-author patterns (5)
        assert len(patterns) == 5


class TestExtractSentence:
    """Tests for extract_sentence function."""

    def test_extracts_correct_sentence(self):
        text = "First sentence here. Frankfurt (1971) argued something important. Third sentence."
        match = re.search(r"Frankfurt \(1971\)", text)
        result = extract_sentence(text, match.start(), match.end())
        assert "Frankfurt (1971)" in result
        assert "argued something" in result
        assert "First sentence" not in result


class TestFindCitations:
    """Tests for find_citations function."""

    def test_finds_in_preamble(self):
        article = {
            "preamble": "Frankfurt (1971) introduced second-order volitions.",
            "sections": {},
        }
        patterns = build_citation_patterns("Frankfurt", "1971")
        results = find_citations(article, patterns)
        assert len(results) == 1
        assert results[0]["section"] == "preamble"

    def test_finds_in_sections(self):
        article = {
            "preamble": None,
            "sections": {
                "1": {"title": "Sec 1", "content": "Frankfurt (1971) says X."},
                "2": {"title": "Sec 2", "content": "Frankfurt (1971) says Y."},
            },
        }
        patterns = build_citation_patterns("Frankfurt", "1971")
        results = find_citations(article, patterns)
        assert len(results) == 2
