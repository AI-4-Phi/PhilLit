"""Tests for normalize_headings.py - Section/subsection heading normalization."""

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
from normalize_headings import (
    strip_section_prefix,
    strip_subsection_prefix,
    normalize_em_dashes,
    classify_heading,
    normalize_headings,
)


class TestStripSectionPrefix:
    """Tests for stripping 'Section N:' prefixes from heading titles."""

    def test_strips_section_n(self):
        """Standard 'Section 1: Title' prefix is stripped."""
        assert strip_section_prefix("Section 1: Title") == "Title"

    def test_strips_section_with_spaces(self):
        """Extra whitespace around number and colon is handled."""
        assert strip_section_prefix("Section  2 :  Title") == "Title"

    def test_no_prefix(self):
        """Title without a Section prefix is returned unchanged."""
        assert strip_section_prefix("Just a Title") == "Just a Title"

    def test_section_230_not_stripped(self):
        """3-digit section numbers are not matched (avoids 'Section 230' false positive)."""
        title = "Section 230 and Platform Liability"
        assert strip_section_prefix(title) == title


class TestStripSubsectionPrefix:
    """Tests for stripping subsection prefixes from heading titles."""

    def test_strips_subsection_nm(self):
        """'Subsection 2.1: Title' prefix is stripped."""
        assert strip_subsection_prefix("Subsection 2.1: Title") == "Title"

    def test_strips_bare_nm(self):
        """Bare 'N.M Title' prefix is stripped."""
        assert strip_subsection_prefix("2.1 Title") == "Title"

    def test_strips_nm_colon(self):
        """'N.M: Title' prefix is stripped."""
        assert strip_subsection_prefix("2.1: Title") == "Title"

    def test_no_prefix(self):
        """Title without a subsection prefix is returned unchanged."""
        assert strip_subsection_prefix("Just a Title") == "Just a Title"


class TestNormalizeEmDashes:
    """Tests for em-dash to colon normalization in heading titles."""

    def test_em_dash_to_colon(self):
        """Em-dash without spaces is replaced with colon-space."""
        assert normalize_em_dashes("Democracy\u2014Why") == "Democracy: Why"

    def test_no_em_dash(self):
        """Title without em-dash is returned unchanged."""
        title = "Democracy and Why"
        assert normalize_em_dashes(title) == title

    def test_em_dash_with_spaces(self):
        """Em-dash with surrounding spaces is replaced with colon-space."""
        assert normalize_em_dashes("Democracy \u2014 Why") == "Democracy: Why"


class TestClassifyHeading:
    """Tests for heading classification (intro/conclusion/body)."""

    def test_intro_first(self):
        """'Introduction' in first position is classified as intro."""
        assert classify_heading("Introduction", "first") == "intro"

    def test_intro_middle(self):
        """'Introduction' in middle position is classified as body."""
        assert classify_heading("Introduction", "middle") == "body"

    def test_conclusion_last(self):
        """'Conclusion' in last position is classified as conclusion."""
        assert classify_heading("Conclusion", "last") == "conclusion"

    def test_conclusion_middle(self):
        """'Conclusion' in middle position is classified as body."""
        assert classify_heading("Conclusion", "middle") == "body"

    def test_body(self):
        """Generic title in middle position is classified as body."""
        assert classify_heading("Some Topic", "middle") == "body"

    def test_case_insensitive(self):
        """Classification is case-insensitive."""
        assert classify_heading("INTRODUCTION", "first") == "intro"


class TestNormalizeHeadings:
    """Integration tests for the full normalize_headings function."""

    def test_primary_example(self):
        """THE primary test case from issue-section-numbering.md section 9.

        Verifies the exact before/after transformation of the observed
        admin-power-legitimacy review headings.
        """
        before = (
            "## Introduction\n"
            "## Section 1: Competing Frameworks for Administrative Authority\n"
            "### 1.1 Fiduciary Theory: Authority as Trust\n"
            "### 1.2 Liberal-Institutional Theory: Bureaucracy as Guardian of Liberal Principles\n"
            "### 1.3 Kantian Democratic Theory: Administrative Power and Collective Will\n"
            "### 1.4 Deliberative Democratic Theory: Public Reasoning and Administrative Discretion\n"
            "## Section 2: The Expertise-Democracy Tension\n"
            "### Subsection 2.1: Epistemic Democracy\u2014Why Democratic Processes May Outperform Expert Rule\n"
            "### Subsection 2.2: Technocracy, Its Types, and Its Limits\n"
            "### Subsection 2.3: Conditional Authority\u2014When Expertise Grounds Legitimacy\n"
            "## Constitutional Critiques, Procedural Responses, and Institutional Design\n"
            "### The Constitutional Case Against Administrative Power\n"
            "### Historical and Functional Responses to Constitutional Critique\n"
            "### Procedural Accountability and Institutional Reform\n"
            "## Conclusion"
        )

        expected = (
            "## Introduction\n"
            "## Section 1: Competing Frameworks for Administrative Authority\n"
            "### 1.1 Fiduciary Theory: Authority as Trust\n"
            "### 1.2 Liberal-Institutional Theory: Bureaucracy as Guardian of Liberal Principles\n"
            "### 1.3 Kantian Democratic Theory: Administrative Power and Collective Will\n"
            "### 1.4 Deliberative Democratic Theory: Public Reasoning and Administrative Discretion\n"
            "## Section 2: The Expertise-Democracy Tension\n"
            "### 2.1 Epistemic Democracy: Why Democratic Processes May Outperform Expert Rule\n"
            "### 2.2 Technocracy, Its Types, and Its Limits\n"
            "### 2.3 Conditional Authority: When Expertise Grounds Legitimacy\n"
            "## Section 3: Constitutional Critiques, Procedural Responses, and Institutional Design\n"
            "### 3.1 The Constitutional Case Against Administrative Power\n"
            "### 3.2 Historical and Functional Responses to Constitutional Critique\n"
            "### 3.3 Procedural Accountability and Institutional Reform\n"
            "## Conclusion"
        )

        result, changes = normalize_headings(before)
        assert result == expected
        assert len(changes) > 0

    def test_already_correct(self):
        """Input that is already normalized produces no changes."""
        content = (
            "## Introduction\n"
            "## Section 1: First Topic\n"
            "### 1.1 Subtopic A\n"
            "### 1.2 Subtopic B\n"
            "## Section 2: Second Topic\n"
            "### 2.1 Subtopic C\n"
            "## Conclusion"
        )
        result, changes = normalize_headings(content)
        assert result == content
        assert changes == []

    def test_no_intro_no_conclusion(self):
        """All sections are body when none match intro/conclusion patterns."""
        content = (
            "## First Topic\n"
            "### Sub A\n"
            "## Second Topic\n"
            "### Sub B\n"
            "## Third Topic"
        )
        expected = (
            "## Section 1: First Topic\n"
            "### 1.1 Sub A\n"
            "## Section 2: Second Topic\n"
            "### 2.1 Sub B\n"
            "## Section 3: Third Topic"
        )
        result, changes = normalize_headings(content)
        assert result == expected
        assert len(changes) > 0

    def test_references_excluded(self):
        """## References heading is not renumbered or counted as a body section."""
        content = (
            "## Introduction\n"
            "## First Topic\n"
            "## Conclusion\n"
            "## References"
        )
        expected = (
            "## Introduction\n"
            "## Section 1: First Topic\n"
            "## Conclusion\n"
            "## References"
        )
        result, changes = normalize_headings(content)
        assert result == expected

    def test_bibliography_excluded(self):
        """## Bibliography heading is not renumbered or counted as a body section."""
        content = (
            "## Introduction\n"
            "## First Topic\n"
            "## Conclusion\n"
            "## Bibliography"
        )
        expected = (
            "## Introduction\n"
            "## Section 1: First Topic\n"
            "## Conclusion\n"
            "## Bibliography"
        )
        result, changes = normalize_headings(content)
        assert result == expected

    def test_section_230_preserved(self):
        """Heading 'Section 230 and Platform Liability' keeps its text intact."""
        content = (
            "## Introduction\n"
            "## Section 230 and Platform Liability\n"
            "## Conclusion"
        )
        # "Section 230" has 3 digits, so the regex should NOT strip it.
        # The body section gets a "Section 1:" prefix prepended.
        expected = (
            "## Introduction\n"
            "## Section 1: Section 230 and Platform Liability\n"
            "## Conclusion"
        )
        result, changes = normalize_headings(content)
        assert result == expected

    def test_subsections_under_intro(self):
        """### headings under intro get no number prefix."""
        content = (
            "## Introduction\n"
            "### Scope\n"
            "### Methodology\n"
            "## First Topic\n"
            "### Sub A\n"
            "## Conclusion"
        )
        expected = (
            "## Introduction\n"
            "### Scope\n"
            "### Methodology\n"
            "## Section 1: First Topic\n"
            "### 1.1 Sub A\n"
            "## Conclusion"
        )
        result, changes = normalize_headings(content)
        assert result == expected

    def test_content_between_headings_preserved(self):
        """Body text paragraphs between headings are untouched."""
        content = (
            "## Introduction\n"
            "\n"
            "This is the introduction paragraph.\n"
            "\n"
            "## First Topic\n"
            "\n"
            "This paragraph discusses the first topic.\n"
            "\n"
            "### Sub A\n"
            "\n"
            "Details about sub A.\n"
            "\n"
            "## Conclusion\n"
            "\n"
            "Final thoughts."
        )
        expected = (
            "## Introduction\n"
            "\n"
            "This is the introduction paragraph.\n"
            "\n"
            "## Section 1: First Topic\n"
            "\n"
            "This paragraph discusses the first topic.\n"
            "\n"
            "### 1.1 Sub A\n"
            "\n"
            "Details about sub A.\n"
            "\n"
            "## Conclusion\n"
            "\n"
            "Final thoughts."
        )
        result, changes = normalize_headings(content)
        assert result == expected

    def test_em_dashes_in_all_headings(self):
        """Em-dashes in intro/conclusion headings are also normalized."""
        content = (
            "## Introduction\u2014Overview\n"
            "## First Topic\u2014Details\n"
            "### Sub A\u2014More\n"
            "## Conclusion\u2014Final Thoughts"
        )
        # Intro (first) and conclusion (last) headings have em-dashes normalized too.
        # "Introduction: Overview" does not match intro patterns exactly, so it becomes body.
        # "Conclusion: Final Thoughts" does not match conclusion patterns exactly, so it becomes body.
        # Actually, let's check: the stripped title after em-dash normalization would be
        # "Introduction: Overview" which is NOT in INTRO_PATTERNS (those are exact matches
        # like "introduction"). So all four become body sections.
        expected = (
            "## Section 1: Introduction: Overview\n"
            "## Section 2: First Topic: Details\n"
            "### 2.1 Sub A: More\n"
            "## Section 3: Conclusion: Final Thoughts"
        )
        result, changes = normalize_headings(content)
        assert result == expected

    def test_idempotent(self):
        """Running normalization twice produces the same result."""
        before = (
            "## Introduction\n"
            "## Constitutional Critiques, Procedural Responses\n"
            "### The Constitutional Case\n"
            "### Historical Responses\n"
            "## Section 2: The Expertise-Democracy Tension\n"
            "### Subsection 2.1: Epistemic Democracy\u2014Why\n"
            "## Conclusion"
        )
        result1, changes1 = normalize_headings(before)
        assert len(changes1) > 0
        result2, changes2 = normalize_headings(result1)
        assert result2 == result1
        assert changes2 == []

    def test_no_headings(self):
        """File with no ## headings is returned unchanged."""
        content = "Just some text.\n\nMore text."
        result, changes = normalize_headings(content)
        assert result == content
        assert changes == []

    def test_only_intro_and_conclusion(self):
        """File with only Introduction and Conclusion, no body sections."""
        content = (
            "## Introduction\n"
            "Some intro text.\n"
            "## Conclusion"
        )
        result, changes = normalize_headings(content)
        assert result == content
        assert changes == []

    def test_section_prefix_stripped_from_intro(self):
        """A heading like '## Section 1: Introduction' becomes '## Introduction'."""
        content = (
            "## Section 1: Introduction\n"
            "## Topic A\n"
            "## Conclusion"
        )
        expected = (
            "## Introduction\n"
            "## Section 1: Topic A\n"
            "## Conclusion"
        )
        result, changes = normalize_headings(content)
        assert result == expected

    def test_yaml_frontmatter_skipped(self):
        """YAML frontmatter is not processed as headings."""
        content = (
            "---\n"
            "title: \"## Not a Heading\"\n"
            "author: Test\n"
            "---\n"
            "## Introduction\n"
            "## First Topic\n"
            "## Conclusion"
        )
        expected = (
            "---\n"
            "title: \"## Not a Heading\"\n"
            "author: Test\n"
            "---\n"
            "## Introduction\n"
            "## Section 1: First Topic\n"
            "## Conclusion"
        )
        result, changes = normalize_headings(content)
        assert result == expected
