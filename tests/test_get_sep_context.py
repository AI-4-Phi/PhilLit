"""
Tests for get_sep_context.py (SEP citation context extraction).

Tests cover:
- Citation pattern matching
- Context extraction
- Claim extraction
- Output schema validation
"""

import json
import re
from unittest.mock import patch, MagicMock

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


class TestCitationPatterns:
    """Tests for citation pattern building and matching."""

    def test_normalize_author_last_first(self):
        """Should normalize 'Last, First' format."""
        import get_sep_context

        assert get_sep_context.normalize_author("Frankfurt, Harry G.") == "frankfurt"
        assert get_sep_context.normalize_author("Fischer, John Martin") == "fischer"

    def test_normalize_author_first_last(self):
        """Should normalize 'First Last' format."""
        import get_sep_context

        assert get_sep_context.normalize_author("Harry Frankfurt") == "frankfurt"
        assert get_sep_context.normalize_author("John Martin Fischer") == "fischer"

    def test_build_single_author_patterns(self):
        """Should build patterns for single author citations."""
        import get_sep_context

        patterns = get_sep_context.build_citation_patterns("Frankfurt", "1971")

        test_texts = [
            "Frankfurt (1971)",
            "frankfurt (1971)",
            "Frankfurt 1971",
            "(Frankfurt 1971)",
            "(Frankfurt, 1971)",
        ]

        for text in test_texts:
            matched = any(p.search(text) for p in patterns)
            assert matched, f"Pattern should match '{text}'"

    def test_build_two_author_patterns(self):
        """Should build patterns for two-author citations."""
        import get_sep_context

        patterns = get_sep_context.build_citation_patterns("Fischer", "1998", coauthor="Ravizza")

        test_texts = [
            "Fischer and Ravizza (1998)",
            "Fischer & Ravizza (1998)",
            "Fischer and Ravizza 1998",
            "(Fischer and Ravizza 1998)",
        ]

        for text in test_texts:
            matched = any(p.search(text) for p in patterns)
            assert matched, f"Pattern should match '{text}'"


class TestContextExtraction:
    """Tests for context window extraction."""

    def test_extract_sentence(self):
        """Should extract the sentence containing the citation."""
        import get_sep_context

        text = "This is the first sentence. Frankfurt (1971) argues that alternative possibilities are not required. This is another sentence."

        # Position of "Frankfurt (1971)"
        match = re.search(r"Frankfurt \(1971\)", text)
        sentence = get_sep_context.extract_sentence(text, match.start(), match.end())

        assert "Frankfurt (1971)" in sentence
        assert "argues that" in sentence
        assert "first sentence" not in sentence

    def test_extract_context_window(self):
        """Should extract a context window around the citation."""
        import get_sep_context

        text = "A" * 600 + "Frankfurt (1971) argues" + "B" * 600

        match = re.search(r"Frankfurt \(1971\)", text)
        context = get_sep_context.extract_context_window(text, match.start(), match.end(), window=100)

        assert "Frankfurt (1971)" in context
        assert len(context) < 400  # Roughly 2*window + citation


class TestClaimExtraction:
    """Tests for philosophical claim extraction."""

    def test_extract_claims_argues_that(self):
        """Should extract claims from 'argues that' pattern."""
        import get_sep_context

        contexts = [{
            "sentence": "Frankfurt (1971) argues that alternative possibilities are not required for moral responsibility.",
            "section": "1",
        }]

        result = get_sep_context.extract_claims(contexts)

        assert "extracted_claims" in result[0]
        assert any("alternative possibilities" in c for c in result[0]["extracted_claims"])

    def test_extract_claims_contends_that(self):
        """Should extract claims from 'contends that' pattern."""
        import get_sep_context

        contexts = [{
            "sentence": "The author contends that free will is compatible with determinism.",
            "section": "1",
        }]

        result = get_sep_context.extract_claims(contexts)

        assert "extracted_claims" in result[0]
        assert any("compatible with determinism" in c for c in result[0]["extracted_claims"])

    def test_extract_claims_no_pattern(self):
        """Should not add claims when no pattern matches."""
        import get_sep_context

        contexts = [{
            "sentence": "See Frankfurt (1971) for more details.",
            "section": "1",
        }]

        result = get_sep_context.extract_claims(contexts)

        assert "extracted_claims" not in result[0] or len(result[0].get("extracted_claims", [])) == 0


class TestFindCitations:
    """Tests for finding citations in article."""

    def test_find_citations_in_preamble(self):
        """Should find citations in the preamble."""
        import get_sep_context

        article = {
            "preamble": "Frankfurt (1971) introduced the concept of second-order volitions.",
            "sections": {},
        }

        patterns = get_sep_context.build_citation_patterns("Frankfurt", "1971")
        citations = get_sep_context.find_citations(article, patterns)

        assert len(citations) == 1
        assert citations[0]["section"] == "preamble"

    def test_find_citations_in_sections(self):
        """Should find citations in article sections."""
        import get_sep_context

        article = {
            "preamble": None,
            "sections": {
                "1": {
                    "title": "The Problem",
                    "content": "Frankfurt (1971) argued against alternative possibilities.",
                },
                "2": {
                    "title": "Responses",
                    "content": "Critics of Frankfurt (1971) have raised objections.",
                },
            },
        }

        patterns = get_sep_context.build_citation_patterns("Frankfurt", "1971")
        citations = get_sep_context.find_citations(article, patterns)

        assert len(citations) == 2
        sections = [c["section"] for c in citations]
        assert "1" in sections
        assert "2" in sections

    def test_find_citations_deduplicates(self):
        """Should deduplicate citations at same position."""
        import get_sep_context

        article = {
            "preamble": "Frankfurt (1971) is cited here.",
            "sections": {},
        }

        # Multiple patterns may match the same citation
        patterns = get_sep_context.build_citation_patterns("Frankfurt", "1971")
        citations = get_sep_context.find_citations(article, patterns)

        # Should only have one result even if multiple patterns match
        assert len(citations) == 1


class TestOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful response should have correct schema."""
        import get_sep_context

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        query = {"entry": "freewill", "author": "Frankfurt", "year": "1971"}

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_sep_context.output_success(query, [{"citation_count": 5}])

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "sep_context"

    def test_error_output_schema(self):
        """Error response should have correct schema."""
        import get_sep_context

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        query = {"entry": "freewill", "author": "Frankfurt", "year": "1971"}

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_sep_context.output_error(query, "not_found", "Entry not found", exit_code=1)

        assert exc_info.value.code == 1
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"


class TestProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import get_sep_context
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            get_sep_context.log_progress("Test message")

        output = captured.getvalue()
        assert "[get_sep_context.py]" in output
        assert "Test message" in output


class TestCLI:
    """Tests for command-line interface."""

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("get_sep_context.py", "--help")
        assert result.returncode == 0
        assert "SEP" in result.stdout

    def test_cli_requires_author(self, run_skill_script):
        """Should require --author argument."""
        result = run_skill_script("get_sep_context.py", "freewill", "--year", "1971")
        # argparse will return error code 2 for missing required argument
        assert result.returncode == 2
