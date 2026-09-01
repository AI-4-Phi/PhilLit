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
    """Every in-text author-year citation must resolve to a
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

    def test_ae_contraction_bridges_digraph_free_citation(self):
        # Body "Fraenken", References "Franken" - neither side carries a
        # diacritic, so the check needs the ae/oe/ue contraction fold (the
        # third axis of ascii_variants) rather than the transliteration
        # variant test above. lint_md itself is unchanged: _fold_variants is
        # ascii_variants, so extending that shared function is enough.
        from lint_md import check_citations
        text = self.REVIEW.replace(
            "## References",
            '## References\n\nFranken, F. 2024. "Anchor Study." *Mind* 133: 1--10.')
        errors, _, _ = check_citations(text)
        assert errors == []

    def test_aaroe_line_side_contraction_resolves(self):
        # The Aarøe direction (the live-fix's real regression, line-side
        # contraction): body "Aaroe" (plain, no diacritic) against a
        # References line spelling "Aarøe" resolves because ascii_variants
        # applied to the whole reference LINE now also carries the
        # contracted fold (translit "aaroee" -> contracted "aaroe"), meeting
        # the body's plain "aaroe" needle. Since v0.5.7 this resolution is
        # ONLY visible under the full fold (not under contract=False on
        # both sides), so it now also surfaces as a contraction WARN rather
        # than resolving silently.
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Aaroe (2015) reports similar findings.\n\n"
            "## References\n\n"
            'Aarøe, Lene. 2015. "Political Attitudes." *Journal* 2: 3--4.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert any("contraction" in w for w in warnings)

    def test_guest_gust_false_resolve_now_warns(self):
        # Residual (b) in ascii_variants' docstring: whole-LINE contraction
        # folds a genuine digraph word onto a short plain needle -
        # References "Guest" (contract_fold "gust") resolves a body
        # "Gust (2020)" citation. Unlike the matcher path, lint has no
        # collision backstop - but since v0.5.7 the resolution is no longer
        # silent: it exists only under the full fold (not under
        # contract=False on both sides), so it now surfaces as a
        # contraction WARN for the writer to verify. This pin's subject
        # changed from "silent residual" to "surfaced residual" - it now
        # fails if the WARN stops firing on this example.
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Gust (2020) presses the objection.\n\n"
            "## References\n\n"
            'Guest, Dominic. 2020. "An Objection." *Mind* 129: 1--10.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert any("contraction" in w for w in warnings)

    def test_michael_michal_residual_reaches_lint_too(self):
        # Symmetry pin: test_generate_bibliography.py's
        # test_residual_michael_michal_homograph_pin covers the matcher
        # path, and the identical contraction (contract_fold("michael") ==
        # "michal") reaches lint through the same shared ascii_variants.
        # Residual (a) now surfaces as a contraction WARN on the lint side
        # (v0.5.7) while remaining silent on the matcher side, which has no
        # equivalent WARN channel.
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Michal (2020) argues this.\n\n"
            "## References\n\n"
            'Michael, J. 2020. "The Argument." *Mind* 129: 1--10.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert any("contraction" in w for w in warnings)

    def test_mueller_in_refs_muller_in_prose_warns(self):
        # The contraction-ONLY class: bib spells the digraph out, prose
        # contracts it. Resolves (no ERROR), but flagged for verification.
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Muller (2018) argues this.\n\n"
            "## References\n\n"
            'Mueller, Hans. 2018. "A Work." *Mind* 127: 1--10.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert any("contraction" in w for w in warnings)

    def test_umlaut_muller_plain_muller_does_not_warn(self):
        # PIN of the measured framing correction: the roadmap feared this
        # pair as "the common case" the WARN would fire on. It resolves via
        # the plain NFKD axis (u-umlaut -> u); no contraction involved, no
        # WARN. If this test fails, the WARN's precondition has widened.
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Muller (2015) reports findings.\n\n"
            "## References\n\n"
            'Müller, Eva. 2015. "Findings." *Journal* 2: 3--4.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert not any("contraction" in w for w in warnings)

    def test_oslash_name_cited_without_diacritic_warns(self):
        # Pins the ACCEPTED ø/æ firing class (non-decomposable diacritic --
        # see bib_identity.contract_fold's docstring): unlike Müller/Muller
        # above, "ø" does not NFKD-decompose, so the clean ASCII spelling
        # ("Moller") is reachable ONLY through the contraction axis. The WARN
        # fires here even though it is a legitimate same-person citation, not
        # a masked homograph collision -- the negative pin for the umlaut
        # class is test_umlaut_muller_plain_muller_does_not_warn above.
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Moller (2018) argues this.\n\n"
            "## References\n\n"
            'Møller, Hans. 2018. "A Work." *Mind* 127: 1--10.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert any("contraction" in w for w in warnings)

    def test_ordinary_resolution_does_not_warn(self):
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Smith (2020) makes the point.\n\n"
            "## References\n\n"
            'Smith, Ann. 2020. "The Point." *Mind* 129: 1--10.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert not any("contraction" in w for w in warnings)

    def test_token_side_contraction_also_warns(self):
        # Reverse direction of the Mueller/Muller case: bib "Muller",
        # prose "Mueller" - the TOKEN's contracted variant bridges. Both
        # sides of the fold are in the firing predicate.
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Mueller (2018) argues this.\n\n"
            "## References\n\n"
            'Muller, Hans. 2018. "A Work." *Mind* 127: 1--10.\n'
        )
        errors, warnings, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert any("contraction" in w for w in warnings)

    def test_fold_variants_alias_still_patchable_with_single_arg_callable(self):
        # External harnesses (docs/known-issues measurement scripts)
        # monkeypatch lint_md._fold_variants with plain single-argument
        # callables. The WARN machinery must never route contract= through
        # the alias.
        import lint_md
        orig = lint_md._fold_variants
        lint_md._fold_variants = lambda s: frozenset({s.lower()})
        try:
            _errors, _warnings, checked = lint_md.check_citations(
                "# T\n\nSmith (2020) says.\n\n## References\n\n"
                'Smith, Ann. 2020. "W." *Mind* 1: 1--2.\n')
        finally:
            lint_md._fold_variants = orig
        assert checked is True

    def test_repeated_contraction_citation_warns_once_with_all_lines(self):
        # Same "Muller (2018)" cited on three lines: ONE warning naming
        # all three line numbers (the remedy is one verification action).
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Muller (2018) argues this.\n\n"
            "Later, Muller (2018) extends it.\n\n"
            "Finally Muller (2018) concludes.\n\n"
            "## References\n\n"
            'Mueller, Hans. 2018. "A Work." *Mind* 127: 1--10.\n'
        )
        _errors, warnings, _checked = check_citations(text)
        contraction = [w for w in warnings if "contraction" in w]
        assert len(contraction) == 1
        assert "3" in contraction[0] and "5" in contraction[0] and "7" in contraction[0]

    def test_negative_control_unrelated_mismatch_still_errors(self):
        # Without this, a check_citations that returned no errors
        # UNCONDITIONALLY would pass every contraction test above. An
        # unrelated body/References mismatch must still ERROR, so the two
        # accepted-residual pins mean "resolves and now WARNs", not
        # "linting off".
        from lint_md import check_citations
        text = (
            "# Title\n\n"
            "Smith (2020) makes the point.\n\n"
            "## References\n\n"
            'Franken, F. 2020. "Unrelated Work." *Mind* 129: 1--10.\n'
        )
        errors, _, checked = check_citations(text)
        assert checked is True
        # Neither `len(errors) == 1` nor `errors[0]`: both would couple this
        # control to whether lint later also reports the orphaned entry.
        assert any("does not resolve" in e for e in errors)

    def test_year_suffix_tolerated(self):
        # "(Wiens 2015a)" resolves against a References line dated 2015 even
        # though that entry carries no letter - stays tolerant (no ERROR).
        # Letters are now rendered, so this is exactly the WARN case:
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
    assert "WARN citation:" in out
    # The binding suffix-TOLERANT decision: a lettered prose cite
    # against an unlettered References entry never reaches the ERROR path.
    assert "ERROR citation:" not in out


def test_main_prints_contraction_warning_under_the_same_generic_label(
        tmp_path, monkeypatch, capsys):
    # citation_warnings holds two kinds since v0.5.7 (suffix mismatches and
    # contraction-only resolutions); this pins that the contraction kind
    # also renders under the truthful generic "WARN citation:" prefix, not
    # the retired "WARN citation-suffix:" label that would misdescribe it.
    import lint_md
    monkeypatch.setattr(lint_md, "lint_markdown", lambda filepath: 0)
    md_file = tmp_path / "r.md"
    md_file.write_text(
        "Muller (2018) argues this.\n\n## References\n\n"
        'Mueller, Hans. 2018. "A Work." *Mind* 127: 1--10.\n',
        encoding="utf-8")
    rc = lint_md.main([str(md_file)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN citation:" in out
    assert "contraction" in out
    assert "WARN citation-suffix:" not in out


def test_main_prints_straddle_error_under_the_generic_citation_prefix(
        tmp_path, monkeypatch, capsys):
    # main()-level pin for the CRITICAL fix: a straddle ERROR must print
    # under "ERROR citation:", not the retired "ERROR unresolved-citation:"
    # label - that label's documented SKILL.md remedy ("fix the body/bib
    # spelling divergence") would steer a straddle fix into the wrong file,
    # since the bib is correct here and the fix is prose-only.
    import lint_md
    monkeypatch.setattr(lint_md, "lint_markdown", lambda filepath: 0)
    md_file = tmp_path / "r.md"
    md_file.write_text(
        "Punishment theory (Reiman 1984/2017) is central.\n\n"
        "## References\n\n"
        'Reiman, Jeffrey. 1984. "The Case Against Punishment." *Journal*'
        ' 1: 1--10.\n\n'
        'Reiman, Jeffrey. 2017. *The Case Against Punishment*. Routledge.\n',
        encoding="utf-8")
    rc = lint_md.main([str(md_file)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ERROR citation:" in out
    assert "two listings" in out
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
        # Alias, not a copy: assert identity, not equality.
        import lint_md
        from bib_identity import ascii_variants
        assert lint_md._fold_variants is ascii_variants


class TestReprintStraddle:
    """A reprint-form citation (Author Y1/Y2) whose two years resolve to two
    DIFFERENT References entries renders against two listings - the slash
    citation corresponds to no single References line. This must ERROR. The
    message deliberately does not claim "reprint pair": the same straddle
    fires for two distinct works sharing a surname (see IMPORTANT-1 below),
    not only for a double-listed reprint."""

    REFS_BOTH_EDITIONS = (
        "## References\n\n"
        'Reiman, Jeffrey. 1984. "The Case Against Punishment." *Journal*'
        ' 1: 1--10.\n\n'
        'Reiman, Jeffrey. 2017. *The Case Against Punishment*. Routledge.\n'
    )

    def test_parenthetical_straddle_is_error(self):
        from lint_md import check_citations
        text = ("# T\n\nPunishment theory (Reiman 1984/2017) is central.\n\n"
                + self.REFS_BOTH_EDITIONS)
        errors, _, checked = check_citations(text)
        assert checked is True
        assert len(errors) == 1
        assert "two listings" in errors[0]
        assert "does not resolve" not in errors[0]

    def test_narrative_straddle_is_error(self):
        from lint_md import check_citations
        text = ("# T\n\nReiman (1984/2017) argues against punishment.\n\n"
                + self.REFS_BOTH_EDITIONS)
        errors, _, checked = check_citations(text)
        assert checked is True
        assert len(errors) == 1
        assert "two listings" in errors[0]
        assert "does not resolve" not in errors[0]

    def test_distinct_works_straddle_wording_is_not_reprint_specific(self):
        # IMPORTANT-1: the straddle can fire on two DISTINCT works sharing a
        # surname, not a genuine reprint pair - a solo Gutmann 1996 and a
        # co-authored Gutmann-and-Thompson 2004. The message must not claim
        # "double listing" / "reprint pair" as fact; it must cover both
        # readings.
        from lint_md import check_citations
        text = (
            "# T\n\nDeliberation matters (Gutmann and Thompson 1996/2004).\n\n"
            "## References\n\n"
            'Gutmann, Amy. 1996. *Color Conscious*. Princeton.\n\n'
            'Gutmann, Amy, and Dennis Thompson. 2004. *Why Deliberative'
            ' Democracy?* Princeton.\n'
        )
        errors, _, checked = check_citations(text)
        assert checked is True
        assert len(errors) == 1
        assert "two listings" in errors[0]
        assert "double listing" not in errors[0]

    def test_single_edition_slash_is_silent(self):
        # Bib holds only the 2017 edition - the slash form resolves on the
        # single existing entry. Legitimate, long-tolerated use.
        from lint_md import check_citations
        text = (
            "# T\n\nPunishment theory (Reiman 1984/2017) is central.\n\n"
            "## References\n\n"
            'Reiman, Jeffrey. 2017. *The Case Against Punishment*. Routledge.\n'
        )
        errors, _, checked = check_citations(text)
        assert checked is True
        assert errors == []

    def test_single_line_carrying_both_years_is_silent(self):
        # One References line carries both years - not a straddle.
        from lint_md import check_citations
        text = (
            "# T\n\nPunishment theory (Reiman 1984/2017) is central.\n\n"
            "## References\n\n"
            'Reiman, Jeffrey. (1984) 2017. *The Case Against Punishment*.'
            ' Routledge.\n'
        )
        errors, _, checked = check_citations(text)
        assert checked is True
        assert errors == []

    def test_comma_multi_cite_is_not_a_slash_form(self):
        # Pins the extraction assumption: two years in one citation occur
        # ONLY via the Y1/Y2 slash regex groups. A comma multi-cite parses
        # as two separate single-year citations, so straddle never fires.
        from lint_md import check_citations
        text = ("# T\n\nBoth agree (Smith 2020, Jones 2021).\n\n"
                "## References\n\n"
                'Smith, Ann. 2020. "X." *J* 1: 1.\n\n'
                'Jones, Bo. 2021. "Y." *J* 2: 2.\n')
        errors, _, checked = check_citations(text)
        assert checked is True
        assert errors == []
        assert not any("two listings" in e for e in errors)

    def test_unresolvable_slash_citation_still_gets_existing_error_only(self):
        # Neither year is in References: the existing does-not-resolve ERROR
        # fires, and the straddle check must not also fire or crash.
        from lint_md import check_citations
        text = ("# T\n\nPunishment theory (Reiman 1984/2017) is central.\n\n"
                "## References\n\n"
                'Other, Ann. 2020. "Unrelated." *J* 1: 1.\n')
        errors, _, checked = check_citations(text)
        assert checked is True
        assert len(errors) == 1
        assert "does not resolve" in errors[0]
        assert not any("two listings" in e for e in errors)
