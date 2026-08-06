"""Tests for lint_md.py - Markdown linting script."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts" / "lint_md.py"

sys.path.insert(0, str(SCRIPT_PATH.parent))


class TestLintMarkdown:
    """Tests for markdown linting."""

    def test_valid_markdown(self, tmp_path):
        """Valid markdown should pass."""
        md_file = tmp_path / "valid.md"
        md_file.write_text("# Heading\n\nParagraph text.\n\n## Subheading\n\nMore text.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_missing_blank_line_around_heading(self, tmp_path):
        """Missing blank line around heading should fail MD022."""
        md_file = tmp_path / "invalid.md"
        md_file.write_text("# Heading\nNo blank line after heading.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "MD022" in result.stdout

    def test_heading_level_skip(self, tmp_path):
        """Skipping heading levels should fail MD001."""
        md_file = tmp_path / "skip.md"
        md_file.write_text("# Heading 1\n\n### Heading 3\n\nSkipped level 2.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "MD001" in result.stdout

    def test_explanation_included(self, tmp_path):
        """Error output should include explanation."""
        md_file = tmp_path / "invalid.md"
        md_file.write_text("# Heading\nNo blank line after heading.\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert "Fix:" in result.stdout

    def test_missing_args(self):
        """Should exit with error when args missing."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stderr

    def test_file_not_found(self, tmp_path):
        """Should exit with error for missing file."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(tmp_path / "nonexistent.md")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_line_length_not_enforced(self, tmp_path):
        """Line length (MD013) should not be enforced."""
        md_file = tmp_path / "long.md"
        long_line = "x" * 200  # 200 chars, well over 80
        md_file.write_text(f"# Heading\n\n{long_line}\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        # Should pass since MD013 is disabled
        assert result.returncode == 0
        assert "MD013" not in result.stdout

    def test_multiple_errors_multiple_explanations(self, tmp_path):
        """Multiple errors should show multiple explanations."""
        md_file = tmp_path / "multi.md"
        # MD022 (missing blank after heading) + MD001 (skipped heading level)
        md_file.write_text("# Heading\nNo blank line.\n### Skipped level 2\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        # Should have at least 2 "Fix:" explanations
        assert result.stdout.count("Fix:") >= 2
        assert "MD022" in result.stdout
        assert "MD001" in result.stdout

    def test_yaml_frontmatter_not_misinterpreted(self, tmp_path):
        """YAML frontmatter should not be misinterpreted as setext heading."""
        md_file = tmp_path / "frontmatter.md"
        # This pattern was causing false positives: pymarkdown saw the ---
        # followed by title: as a setext-style heading
        md_file.write_text(
            '---\ntitle: "Test Document"\ndate: 2026-01-09\n---\n\n'
            "## Introduction\n\nSome text.\n\n## Methods\n\nMore text.\n"
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md_file)],
            capture_output=True,
            text=True,
        )
        # Should pass - no false positives about heading style inconsistency
        assert result.returncode == 0
        assert "MD003" not in result.stdout  # No heading style errors
        assert "MD022" not in result.stdout  # No blank line errors from frontmatter


class TestCitationCheck:
    """Item 3 B: every in-text author-year citation must resolve to a
    References entry; unresolved -> ERROR (exit nonzero)."""

    REVIEW = """# Title

Fraenken (2024) anchors this review. Classic work exists too
(Clark and Chalmers 1998; Smith et al. 2020, 45).

## References

Clark, Andy, and David Chalmers. 1998. "The Extended Mind." *Analysis* 58 (1): 7--19.

Smith, Jane, Bob Roe, and Cai Wu. 2020. *A Book*. Press.
"""

    def test_unresolved_citation_is_error(self):
        from lint_md import check_citations
        errors, _, checked = check_citations(self.REVIEW)
        assert checked is True
        assert len(errors) == 1
        assert "Fraenken" in errors[0] and "2024" in errors[0]

    def test_resolved_citations_are_clean(self):
        from lint_md import check_citations
        text = self.REVIEW.replace("Fraenken (2024) anchors this review. ", "")
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_transliteration_variant_resolves(self):
        # Body "Fraenken", References "Fränken" - must resolve (the check is
        # more tolerant than the generator; the generator's gap is Issue B's
        # open matcher work, not this check's business).
        from lint_md import check_citations
        text = self.REVIEW.replace(
            "## References",
            '## References\n\nFränken, Jan. 2024. "Anchor Study." *Mind* 133: 1--10.')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_year_suffix_tolerated(self):
        # "(Wiens 2015a)" resolves against a References line dated 2015 even
        # though that entry carries no letter - stays tolerant (no ERROR).
        # Item 3 F now renders letters, so this is exactly the WARN case:
        # the work is present, but no candidate entry carries the 'a'.
        from lint_md import check_citations
        text = self.REVIEW.replace(
            "(Clark and Chalmers 1998; Smith et al. 2020, 45)",
            "(Wiens 2015a)").replace(
            'Clark, Andy, and David Chalmers. 1998. "The Extended Mind." *Analysis* 58 (1): 7--19.',
            'Wiens, David. 2015. "Political Ideals." *Journal* 1: 1--2.'
        ).replace("Fraenken (2024) anchors this review. ", "")
        errors, warnings, _ = check_citations(text)
        assert errors == []
        assert any("2015a" in w for w in warnings)

    def test_no_references_section_skips(self):
        from lint_md import check_citations
        errors, _, checked = check_citations("# Draft\n\nSmith (2020) says.\n")
        assert checked is False
        assert errors == []

    def test_year_ranges_and_fences_ignored(self):
        from lint_md import check_citations
        text = ("# T\n\nRecent work (2020-2025) grew.\n\n"
                "```\nFake (2019) inside fence\n```\n\n## References\n\n"
                'Real, Ann. 2021. "X." *J* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_narrative_possessive_and_et_al(self):
        from lint_md import check_citations
        text = ("# T\n\nNussbaum's (2000) view and Gilbert et al. (2020) agree.\n\n"
                "## References\n\n"
                'Nussbaum, Martha. 2000. *Women*. CUP.\n\n'
                'Gilbert, Sam, Ann Boldt, and Bo Fleming. 2020. "R." *JEP* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_multi_surname_citation_resolves_on_any_token(self):
        # "(Buzzell and Rini 2023)" resolves via EITHER surname appearing in
        # a References line carrying the year.
        from lint_md import check_citations
        text = ("# T\n\nSee (Buzzell and Rini 2023).\n\n## References\n\n"
                'Buzzell, Andrew, and Regina Rini. 2023. "DYOR." *PP* 36: 1.\n')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_short_surname_dropped_entry_is_caught(self):
        # ADVERSARIAL (review 4a): "He (2020)" with NO He entry must ERROR
        # even though "he" is a substring of "the" on other 2020 lines -
        # resolution must be word-boundary, not substring.
        from lint_md import check_citations
        text = ("# T\n\nHe (2020) argues the point.\n\n## References\n\n"
                'Smith, John. 2020. "The Public Philosophy of the Age." *J* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert len(errors) == 1 and "He" in errors[0]

    def test_short_surname_present_resolves(self):
        from lint_md import check_citations
        text = ("# T\n\nHe (2020) argues.\n\n## References\n\n"
                'He, Wei. 2020. "A Paper." *J* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_reprint_slash_year_resolves_on_either_year(self):
        # (Ross 1930/2002) resolves against a References line dated 2002
        # (review 4b).
        from lint_md import check_citations
        text = ("# T\n\nDuties (Ross 1930/2002) persist.\n\n## References\n\n"
                'Ross, W. D. 2002. *The Right and the Good*. OUP.\n')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_historical_year_extracted(self):
        # (Kant 1785) is extracted (review 4b) - and errors when the entry
        # is missing from References.
        from lint_md import check_citations
        text = ("# T\n\nAutonomy (Kant 1785) grounds this.\n\n## References\n\n"
                'Modern, Ann. 2020. "X." *J* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert len(errors) == 1 and "Kant" in errors[0]

    def test_statute_citation_requires_bib_entry(self):
        # Policy (decided in this plan): primary/legal sources belong in the
        # bib like everything else - (GDPR 2016) with no entry ERRORs, with
        # an entry resolves (review 4c).
        from lint_md import check_citations
        base = "# T\n\nData rules (GDPR 2016) apply.\n\n## References\n\n"
        errors, _, _ = check_citations(
            base + 'Other, Ann. 2016. "X." *J* 1: 1.\n')
        assert len(errors) == 1
        errors2, _, _ = check_citations(
            base + "GDPR. 2016. Regulation (EU) 2016/679.\n")
        assert errors2 == []

    def test_comma_separated_multi_cite_checks_all(self):
        # (Smith 2020, Jones 2021): BOTH citations checked (review 4d).
        from lint_md import check_citations
        text = ("# T\n\nBoth agree (Smith 2020, Jones 2021).\n\n"
                "## References\n\n"
                'Smith, Ann. 2020. "X." *J* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert len(errors) == 1 and "Jones" in errors[0]

    def test_surnamed_year_range_not_extracted(self):
        # Pin (review 4e): "Smith 2020-2025" is a prose range, not a
        # citation - the lookahead deliberately skips it.
        from lint_md import check_citations
        text = ("# T\n\nWork by (Smith 2020-2025) grew.\n\n## References\n\n"
                'Real, Ann. 2021. "X." *J* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_plural_possessive(self):
        # "Clark and Chalmers' (1998)" - bare trailing apostrophe stripped
        # (review 4f).
        from lint_md import check_citations
        text = ("# T\n\nClark and Chalmers' (1998) argument stands.\n\n"
                "## References\n\n"
                'Clark, Andy, and David Chalmers. 1998. "The Extended Mind." *A* 58: 7.\n')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_curly_vs_straight_apostrophe_resolves(self):
        from lint_md import check_citations
        text = ("# T\n\nO’Neill (2020) argues.\n\n## References\n\n"
                "O'Neill, Onora. 2020. *Trust*. CUP.\n")
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_fake_references_heading_in_fence_ignored(self):
        # A '## References' inside a code fence must not split the file
        # (review 6.1).
        from lint_md import check_citations
        text = ("# T\n\n```\n## References\n```\n\nGhost (2019) says.\n\n"
                "## References\n\n"
                'Ghost, Ann. 2019. "X." *J* 1: 1.\n')
        errors, _, checked = check_citations(text)
        assert checked is True and errors == []

    def test_non_latin_citation_blind_spot_is_deliberate(self):
        # Pin (review 4g): non-Latin surnames are not extracted - a false
        # negative in the safe direction, documented. If _SURNAME's char
        # class ever widens, this test forces a conscious decision.
        from lint_md import check_citations
        text = ("# T\n\n(Χάλμης 2020) argues.\n\n"
                "## References\n\n"
                'Other, Ann. 2021. "X." *J* 1: 1.\n')
        errors, _, _ = check_citations(text)
        assert errors == []


def test_suffix_mismatch_warns_but_does_not_error():
    import lint_md
    text = ("Menary (2010a) argues.\n\n## References\n\n"
            "Menary, Richard 2010. *The Extended Mind*. MIT Press.\n")
    errors, warnings, checked = lint_md.check_citations(text)
    assert checked is True
    assert errors == []                    # still tolerant: no hard failure
    assert any("2010a" in w for w in warnings)


def test_matching_suffix_does_not_warn():
    import lint_md
    text = ("Menary (2010a) argues.\n\n## References\n\n"
            "Menary, Richard 2010a. *Cognitive Integration*. MIT Press.\n")
    errors, warnings, checked = lint_md.check_citations(text)
    assert errors == [] and warnings == []


def test_main_prints_suffix_warning_but_keeps_exit_code(tmp_path, monkeypatch, capsys):
    # main()'s wiring: the new third return value must reach a WARN print
    # channel and never affect the exit code (mirrors WARN prose-quality).
    import lint_md
    monkeypatch.setattr(lint_md, "lint_markdown", lambda filepath: 0)
    md_file = tmp_path / "r.md"
    md_file.write_text(
        "Menary (2010a) argues.\n\n## References\n\n"
        "Menary, Richard 2010. *The Extended Mind*. MIT Press.\n",
        encoding="utf-8")
    rc = lint_md.main([str(md_file)])
    out = capsys.readouterr().out
    assert rc == 0
    # The exact channel prefix, not just the message body: a suffix mismatch
    # must arrive as WARN. (The old `"ERROR" not in out` was vacuous twice
    # over - the fixture raises no citation error, and lint_markdown is
    # stubbed, so nothing could have printed one.)
    assert "WARN citation-suffix:" in out
    # The plan's binding suffix-TOLERANT decision: a lettered prose cite
    # against an unlettered References entry never reaches the ERROR path.
    assert "ERROR unresolved-citation:" not in out


class TestMainUnreadableFile:
    """An unreadable file must not funnel into the "no ## References
    section" message - that phrasing implies the file WAS read and simply
    has no References section yet (a normal draft-stage state), which is a
    different condition from a read failure."""

    def test_unreadable_file_reports_distinctly_and_skips_both_checks(
            self, monkeypatch, capsys):
        import lint_md

        def boom(self, encoding="utf-8"):
            raise OSError("simulated unreadable")

        monkeypatch.setattr(lint_md.Path, "read_text", boom)
        monkeypatch.setattr(lint_md, "lint_markdown", lambda filepath: 0)

        rc = lint_md.main(["somefile.md"])
        out = capsys.readouterr().out

        assert "citation-check: file unreadable; skipped" in out
        assert "citation-check: no ## References section; skipped" not in out
        assert "WARN prose-quality" not in out  # prose-quality also skipped
        assert rc == 0  # exit code still comes from lint_markdown(), unchanged


class TestFoldVariantsAlias:
    def test_fold_variants_is_shared_owner(self):
        # Alias, not a copy - the item-4 pattern (assert identity, not equality).
        import lint_md
        from bib_identity import ascii_variants
        assert lint_md._fold_variants is ascii_variants
