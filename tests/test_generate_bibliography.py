"""Tests for generate_bibliography.py - Bibliography generation from BibTeX."""

import sys
from pathlib import Path

import pytest

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import generate_bibliography
from generate_bibliography import (
    clean_bibtex_str,
    format_author_list,
    format_entry,
    find_cited_entries,
    generate_references,
    apply_references,
    _get_full_surname,
    _normalize_for_matching,
    _quoted_title,
)

from pybtex.database import BibliographyData, Entry, Person


# =============================================================================
# Helpers
# =============================================================================

def _make_entry(entry_type="article", authors=None, editors=None, **fields):
    """Create a pybtex Entry with given persons and fields."""
    persons = {}
    if authors:
        persons["author"] = [Person(a) for a in authors]
    if editors:
        persons["editor"] = [Person(e) for e in editors]
    return Entry(entry_type, fields=fields, persons=persons)


def _make_bib(*entries):
    """Create BibliographyData from (key, entry) tuples."""
    return BibliographyData(entries=dict(entries))


def _bib_from_file(tmp_path, content):
    """Write BibTeX content to a file and parse it."""
    from pybtex.database import parse_file as pf
    bib_file = tmp_path / "test.bib"
    bib_file.write_text(content, encoding="utf-8")
    return pf(str(bib_file), bib_format="bibtex")


# =============================================================================
# Tests for clean_bibtex_str
# =============================================================================

class TestCleanBibtexStr:
    """Tests for BibTeX string normalization."""

    def test_latex_accent_braced(self):
        """Accent-inside-braces: {\\`e} → è"""
        assert "è" in clean_bibtex_str(r"Gr{\`e}ve")

    def test_latex_accent_unbraced(self):
        """Unbraced accent: \\"u → ü"""
        assert "ü" in clean_bibtex_str(r"M\"uller")

    def test_strip_braces(self):
        """{AV} → AV after accent conversion."""
        assert clean_bibtex_str("{AV} Ethics") == "AV Ethics"

    def test_backslash_ampersand(self):
        """\\& → &"""
        assert clean_bibtex_str(r"Philosophy \& Public Affairs") == "Philosophy & Public Affairs"

    def test_double_backslash_ampersand(self):
        """Double-escaped \\\\& → & (regression: stray backslash leaked into References)."""
        assert clean_bibtex_str("Philosophy \\\\& Technology") == "Philosophy & Technology"

    def test_single_backslash_ampersand_still_works(self):
        """Single-escaped \\& still normalizes correctly after the fix."""
        assert clean_bibtex_str("Philosophy \\& Technology") == "Philosophy & Technology"

    def test_url_wrapper(self):
        """\\url{...} → bare URL."""
        result = clean_bibtex_str(r"\url{https://example.com}")
        assert result == "https://example.com"

    def test_utf8_passthrough(self):
        """UTF-8 characters pass through unchanged."""
        assert clean_bibtex_str("Müller") == "Müller"

    def test_cedilla(self):
        """\\c{c} → ç"""
        assert "ç" in clean_bibtex_str(r"Jean-Fran\c{c}ois")

    def test_combined_cleanup(self):
        """Multiple normalizations in one string."""
        result = clean_bibtex_str(r"The {AV} \& the Trolley Gr{\`e}ve")
        assert "AV" in result
        assert "&" in result
        assert "è" in result
        assert "{" not in result
        assert "\\" not in result


# =============================================================================
# Tests for format_author_list
# =============================================================================

class TestFormatAuthorList:
    """Tests for Chicago Author-Date author formatting."""

    def test_single_author(self):
        """Single author: Surname, First."""
        persons = [Person("Thomson, Judith Jarvis")]
        result = format_author_list(persons)
        assert result == "Thomson, Judith Jarvis."

    def test_two_authors(self):
        """Two authors: Surname, First, and First2 Surname2."""
        persons = [Person("Nyholm, Sven"), Person("Smids, Jilles")]
        result = format_author_list(persons)
        assert result == "Nyholm, Sven, and Jilles Smids."

    def test_three_authors(self):
        """Three authors: all listed."""
        persons = [Person("Evans, K."), Person("de Moura, N."), Person("Chauvier, S.")]
        result = format_author_list(persons)
        assert "Evans" in result
        assert "and" in result
        assert "Chauvier" in result

    def test_eleven_plus_authors(self):
        """11+ authors → first 7, then 'et al.'"""
        persons = [Person(f"Author{i}, First{i}") for i in range(12)]
        result = format_author_list(persons)
        assert "et al." in result
        # Should have first 7
        assert "Author0" in result
        assert "Author6" in result
        # Should NOT have author 7+
        assert "Author7" not in result

    def test_editor_single(self):
        """Single editor gets 'ed.' suffix."""
        persons = [Person("Smith, John")]
        result = format_author_list(persons, is_editor=True)
        assert result.endswith("ed.")

    def test_editors_plural(self):
        """Multiple editors get 'eds.' suffix."""
        persons = [Person("Smith, John"), Person("Jones, Mary")]
        result = format_author_list(persons, is_editor=True)
        assert "eds." in result

    def test_empty_persons(self):
        """Empty persons list returns empty string."""
        assert format_author_list([]) == ""


# =============================================================================
# Tests for format_entry
# =============================================================================

class TestQuotedTitle:
    """Tests for Chicago-style title quoting with terminal punctuation."""

    def test_normal_title(self):
        assert _quoted_title("Turning the Trolley") == '"Turning the Trolley."'

    def test_question_mark_title(self):
        """Question mark absorbs the period."""
        assert _quoted_title("What Should We Do?") == '"What Should We Do?"'

    def test_exclamation_mark_title(self):
        """Exclamation mark absorbs the period."""
        assert _quoted_title("Stop the Trolley!") == '"Stop the Trolley!"'

    def test_title_ending_in_period(self):
        """Title already ending in period — no double period."""
        assert _quoted_title("Turning the Trolley.") == '"Turning the Trolley."'


class TestFormatEntry:
    """Tests for Chicago formatting by entry type."""

    def test_article(self):
        entry = _make_entry(
            "article",
            authors=["Thomson, Judith Jarvis"],
            title="Turning the Trolley",
            journal="Philosophy & Public Affairs",
            year="2008",
            volume="36",
            number="4",
            pages="359--374",
            doi="10.1111/j.1088-4963.2008.00144.x",
        )
        result = format_entry(entry, "thomson2008")
        assert '"Turning the Trolley."' in result
        assert "*Philosophy & Public Affairs*" in result
        assert "36 (4)" in result
        assert "359--374" in result
        assert "https://doi.org/" in result

    def test_article_question_title(self):
        """Title ending with ? should not get double punctuation."""
        entry = _make_entry(
            "article",
            authors=["Nyholm, Sven"],
            title="The Ethics of Accident-Algorithms: an Applied Trolley Problem?",
            journal="Ethical Theory and Moral Practice",
            year="2016",
        )
        result = format_entry(entry, "nyholm2016")
        assert '?"' in result
        assert '?."' not in result

    def test_book(self):
        entry = _make_entry(
            "book",
            authors=["Rawls, John"],
            title="A Theory of Justice",
            year="1971",
            publisher="Harvard University Press",
            address="Cambridge, MA",
        )
        result = format_entry(entry, "rawls1971")
        assert "*A Theory of Justice*" in result
        assert "Cambridge, MA: Harvard University Press." in result

    def test_book_editor_only(self):
        """Edited volume with no authors uses editors."""
        entry = _make_entry(
            "book",
            editors=["Jenkins, Ryan", "Černý, David"],
            title="Autonomous Vehicle Ethics",
            year="2022",
            publisher="Oxford",
        )
        result = format_entry(entry, "jenkins2022")
        assert "Jenkins" in result
        assert "eds." in result
        assert "*Autonomous Vehicle Ethics*" in result

    def test_incollection(self):
        entry = _make_entry(
            "incollection",
            authors=["Bartneck, Christoph"],
            editors=["Smith, John", "Jones, Mary"],
            title="Responsibility and Liability",
            booktitle="An Introduction to Ethics in Robotics and AI",
            year="2020",
            publisher="Springer",
            pages="39--51",
        )
        result = format_entry(entry, "bartneck2020")
        assert '"Responsibility and Liability."' in result
        assert "In *An Introduction to Ethics in Robotics and AI*" in result
        assert "edited by" in result
        assert "39--51" in result

    def test_incollection_journal_fallback(self):
        """@incollection with journal but no booktitle → article format."""
        entry = _make_entry(
            "incollection",
            authors=["Otsuka, Michael"],
            title="Double Effect",
            journal="Utilitas",
            year="2008",
            volume="20",
            pages="92--110",
        )
        result = format_entry(entry, "otsuka2008")
        assert "*Utilitas*" in result
        assert "In" not in result

    def test_inproceedings(self):
        entry = _make_entry(
            "inproceedings",
            authors=["Li, Jamy"],
            title="From Trolley to Autonomous Vehicle",
            booktitle="SAE Technical Paper Series",
            year="2016",
        )
        result = format_entry(entry, "li2016")
        assert "In *SAE Technical Paper Series*" in result

    def test_phdthesis(self):
        entry = _make_entry(
            "phdthesis",
            authors=["Student, A."],
            title="On Trolleys and Ethics",
            year="2020",
            school="MIT",
        )
        result = format_entry(entry, "student2020")
        assert "PhD diss., MIT." in result

    def test_misc(self):
        entry = _make_entry(
            "misc",
            authors=["Noorman, Merel"],
            title="Computing and Moral Responsibility",
            year="2012",
            howpublished="Stanford Encyclopedia of Philosophy",
        )
        result = format_entry(entry, "sep2012")
        assert "Stanford Encyclopedia of Philosophy." in result

    def test_misc_with_url(self):
        """@misc with URL in howpublished → link."""
        entry = _make_entry(
            "misc",
            authors=["Noorman, Merel"],
            title="Computing and Moral Responsibility",
            year="2012",
            howpublished="https://plato.stanford.edu/entries/computing-responsibility/",
        )
        result = format_entry(entry, "sep2012")
        assert "[https://" in result

    def test_unknown_type_falls_back_to_misc(self):
        """Unknown entry type uses @misc formatting."""
        entry = _make_entry(
            "manual",
            authors=["Author, Test"],
            title="Some Manual",
            year="2020",
        )
        result = format_entry(entry, "test2020")
        assert '"Some Manual."' in result

    def test_missing_optional_fields(self):
        """Missing optional fields cause no crash or fabrication."""
        entry = _make_entry(
            "article",
            authors=["Author, Test"],
            title="Minimal",
            year="2020",
        )
        result = format_entry(entry, "test2020")
        assert "Author, Test." in result
        assert '"Minimal."' in result
        assert "2020" in result

    def test_note_and_keywords_excluded(self):
        """note and keywords fields never appear in output."""
        entry = _make_entry(
            "article",
            authors=["Author, Test"],
            title="Paper",
            journal="Journal",
            year="2020",
            note="CORE ARGUMENT: This is metadata",
            keywords="ethics, High",
        )
        result = format_entry(entry, "test2020")
        assert "CORE ARGUMENT" not in result
        assert "keywords" not in result
        assert "ethics, High" not in result

    def test_no_persons_returns_empty(self):
        """Entry with no authors and no editors returns empty string."""
        entry = _make_entry("article", title="Orphan", year="2020")
        assert format_entry(entry, "orphan") == ""


# =============================================================================
# Tests for citation matching
# =============================================================================

class TestFindCitedEntries:
    """Tests for BibTeX-driven citation matching."""

    def test_parenthetical_citation(self):
        """(Author Year) is matched."""
        bib = _make_bib(("thomson2008", _make_entry(
            authors=["Thomson, Judith Jarvis"], title="T", year="2008")))
        cited = find_cited_entries("As argued (Thomson 2008), this holds.", bib)
        assert len(cited) == 1
        assert cited[0][0] == "thomson2008"

    def test_narrative_citation(self):
        """Author (Year) is matched."""
        bib = _make_bib(("nyholm2016", _make_entry(
            authors=["Nyholm, Sven"], title="T", year="2016")))
        cited = find_cited_entries("Nyholm (2016) argues that...", bib)
        assert len(cited) == 1

    def test_multi_author_et_al(self):
        """(Author et al. Year) matched via first author."""
        bib = _make_bib(("awad2018", _make_entry(
            authors=["Awad, Edmond", "Dsouza, Sohan"], title="T", year="2018")))
        cited = find_cited_entries("(Awad et al. 2018)", bib)
        assert len(cited) == 1

    def test_semicolon_separated(self):
        """(Author Year; Author Year) both matched."""
        bib = _make_bib(
            ("a2020", _make_entry(authors=["Alpha, A."], title="T", year="2020")),
            ("b2021", _make_entry(authors=["Beta, B."], title="T", year="2021")),
        )
        cited = find_cited_entries("(Alpha 2020; Beta 2021)", bib)
        assert len(cited) == 2

    def test_uncited_excluded(self):
        """Uncited BibTeX entry is not matched."""
        bib = _make_bib(
            ("cited2020", _make_entry(authors=["Cited, Author"], title="T", year="2020")),
            ("uncited2021", _make_entry(authors=["Uncited, Author"], title="T", year="2021")),
        )
        cited = find_cited_entries("As Cited (2020) showed.", bib)
        keys = [k for k, _ in cited]
        assert "cited2020" in keys
        assert "uncited2021" not in keys

    def test_compound_surname_prelast(self):
        """Compound surname with prelast_names: Santoni de Sio."""
        bib = _make_bib(("santoni2021", _make_entry(
            authors=["Santoni de Sio, Filippo"], title="T", year="2021")))
        cited = find_cited_entries("Santoni de Sio (2021) argues.", bib)
        assert len(cited) == 1

    def test_compound_surname_last_only(self):
        """Compound last_names without prelast: De Freitas."""
        bib = _make_bib(("defreitas2021", _make_entry(
            authors=["De Freitas, Julian"], title="T", year="2021")))
        cited = find_cited_entries("De Freitas et al. (2021)", bib)
        assert len(cited) == 1

    def test_word_boundary_short_surname(self):
        """Short surname 'Li' does NOT match 'liability 2016'."""
        bib = _make_bib(("li2016", _make_entry(
            authors=["Li, Jamy"], title="T", year="2016")))
        cited = find_cited_entries("issues of liability 2016 report shows", bib)
        assert len(cited) == 0

    def test_word_boundary_short_surname_true_match(self):
        """Short surname 'Li' DOES match when properly cited."""
        bib = _make_bib(("li2016", _make_entry(
            authors=["Li, Jamy"], title="T", year="2016")))
        cited = find_cited_entries("Li et al. (2016) found", bib)
        assert len(cited) == 1

    def test_same_author_different_years(self):
        """Only the cited year's entry matches."""
        bib = _make_bib(
            ("smith2018", _make_entry(authors=["Smith, John"], title="T", year="2018")),
            ("smith2020", _make_entry(authors=["Smith, John"], title="T", year="2020")),
        )
        cited = find_cited_entries("Smith (2020) argues.", bib)
        keys = [k for k, _ in cited]
        assert "smith2020" in keys
        assert "smith2018" not in keys

    def test_diacritical_normalization(self):
        """BibTeX Hübner matches review text Hubner."""
        bib = _make_bib(("hubner2018", _make_entry(
            authors=["Hübner, Dietmar"], title="T", year="2018")))
        cited = find_cited_entries("Hubner and White (2018)", bib)
        assert len(cited) == 1

    def test_diacritical_normalization_umlaut(self):
        """BibTeX Nida-Rümelin matches review text Nida-Rumelin."""
        bib = _make_bib(("nidarumelin2018", _make_entry(
            authors=["Nida-Rümelin, Julian"], title="T", year="2018")))
        cited = find_cited_entries("as Nida-Rumelin (2018) noted", bib)
        assert len(cited) == 1

    def test_editor_fallback(self):
        """@book with editors but no authors matched via editor surname."""
        entry = _make_entry("book", editors=["Michelfelder, Diane P."],
                            title="T", year="2022")
        bib = _make_bib(("michelfelder2022", entry))
        cited = find_cited_entries("Michelfelder and Rosenberger (2022)", bib)
        assert len(cited) == 1

    def test_latex_in_author_cleaned(self, tmp_path):
        """LaTeX in author names (Gr{\\`e}ve) cleaned before matching."""
        bib_content = r"""@article{greve2020,
  author = {Gr{\`e}ve, Sebastian},
  title = {Test},
  year = {2020}
}"""
        bib = _bib_from_file(tmp_path, bib_content)
        cited = find_cited_entries("Greve (2020) argues.", bib)
        assert len(cited) == 1


# =============================================================================
# Tests for DOI deduplication
# =============================================================================

class TestDOIDeduplication:
    """Tests for DOI-based deduplication."""

    def test_duplicate_dois(self):
        """Two entries with same DOI produce only one reference."""
        bib = _make_bib(
            ("alpha2021paper", _make_entry(
                authors=["Alpha, A."], title="Paper", year="2021",
                doi="10.1234/test")),
            ("beta2021paper", _make_entry(
                authors=["Alpha, A."], title="Paper", year="2021",
                doi="10.1234/test")),
        )
        cited = find_cited_entries("Alpha (2021) found", bib)
        assert len(cited) == 1

    def test_doi_normalization_prefix(self):
        """DOIs with different URL prefixes treated as same."""
        bib = _make_bib(
            ("a2021", _make_entry(
                authors=["Smith, A."], title="T", year="2021",
                doi="10.1234/test")),
            ("b2021", _make_entry(
                authors=["Smith, A."], title="T", year="2021",
                doi="https://doi.org/10.1234/test")),
        )
        cited = find_cited_entries("Smith (2021) argues", bib)
        assert len(cited) == 1


# =============================================================================
# Tests for reference section generation
# =============================================================================

class TestGenerateReferences:
    """Tests for reference section formatting."""

    def test_sorted_by_surname(self):
        """Entries sorted alphabetically by first author surname."""
        entries = [
            ("z2020", _make_entry(authors=["Zeta, Z."], title="T", year="2020")),
            ("a2020", _make_entry(authors=["Alpha, A."], title="T", year="2020")),
        ]
        result = generate_references(entries)
        a_pos = result.index("Alpha")
        z_pos = result.index("Zeta")
        assert a_pos < z_pos

    def test_sorted_by_year_within_surname(self):
        """Same surname sorted by year."""
        entries = [
            ("smith2020", _make_entry(authors=["Smith, J."], title="T", year="2020")),
            ("smith2018", _make_entry(authors=["Smith, J."], title="T", year="2018")),
        ]
        result = generate_references(entries)
        pos_2018 = result.index("2018")
        pos_2020 = result.index("2020")
        assert pos_2018 < pos_2020

    def test_references_heading(self):
        """Output starts with ## References."""
        entries = [("a2020", _make_entry(authors=["A, B."], title="T", year="2020"))]
        result = generate_references(entries)
        assert result.startswith("## References\n")


# =============================================================================
# Tests for idempotency
# =============================================================================

class TestIdempotency:
    """Tests for ## References replacement."""

    def test_append_when_no_references(self):
        """Appends ## References when section doesn't exist."""
        text = "# Review\n\nSome content.\n"
        result = apply_references(text, "## References\n\nRef1.\n")
        assert "## References" in result
        assert "Some content." in result

    def test_replace_existing_references(self):
        """Replaces existing ## References section."""
        text = "# Review\n\nContent.\n\n## References\n\nOld ref.\n"
        result = apply_references(text, "## References\n\nNew ref.\n")
        assert "New ref." in result
        assert "Old ref." not in result
        assert result.count("## References") == 1

    def test_idempotent(self, tmp_path):
        """Running twice produces same result."""
        refs = "## References\n\nSome ref.\n"
        text = "# Review\n\nContent.\n"

        result1 = apply_references(text, refs)
        result2 = apply_references(result1, refs)
        assert result1 == result2

    def test_content_before_references_preserved(self):
        """Content before ## References is preserved."""
        text = "# Review\n\n## Section 1\n\nContent.\n\n## References\n\nOld.\n"
        result = apply_references(text, "## References\n\nNew.\n")
        assert "## Section 1" in result
        assert "Content." in result


# =============================================================================
# Tests for normalization utilities
# =============================================================================

class TestNormalization:
    """Tests for string normalization utilities."""

    def test_nfkd_umlaut(self):
        """NFKD normalizes ü → u."""
        assert _normalize_for_matching("Hübner") == "Hubner"

    def test_nfkd_accent(self):
        """NFKD normalizes è → e."""
        assert _normalize_for_matching("Grève") == "Greve"

    def test_nfkd_ascii_noop(self):
        """ASCII text unchanged by NFKD."""
        assert _normalize_for_matching("Thomson") == "Thomson"

    def test_full_surname_prelast(self):
        """Full surname joins prelast + last."""
        person = Person("Santoni de Sio, Filippo")
        surname = _get_full_surname(person)
        assert "Santoni" in surname or "Sio" in surname

    def test_full_surname_simple(self):
        """Simple surname."""
        person = Person("Thomson, Judith")
        assert _get_full_surname(person) == "Thomson"


# =============================================================================
# ROADMAP item 4: identity keys come from the one owner (hooks/bib_identity.py)
# =============================================================================

class TestIdentityKeysComeFromTheOwner:
    """Three copies of the title key disagreed; there is one now."""

    def _bib_identity(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
        import bib_identity
        return bib_identity

    def test_key_helpers_are_the_shared_objects(self):
        import generate_bibliography as gb
        bi = self._bib_identity()
        assert gb._normalize_doi is bi.normalize_doi
        assert gb._normalize_title_for_key is bi.title_key

    def test_prose_fold_is_untouched(self):
        # Decision 1: the review-text fold keeps punctuation and stays ASCII,
        # because the 60-char _MATCH_WINDOW is measured over its output.
        import generate_bibliography as gb
        bi = self._bib_identity()
        assert gb._normalize_for_matching is not bi.title_key
        assert gb._normalize_for_matching("Mind, Self -- and Society") == "Mind, Self -- and Society"

    def test_non_latin_title_yields_a_fallback_key(self):
        from pybtex.database import parse_string
        import generate_bibliography as gb
        db = parse_string(
            "@article{pap2021,\n"
            "  author = {Παπαδόπουλος, Γ.},\n"
            "  title = {Η ηθική της τεχνολογίας},\n"
            "  year = {2021},\n}",
            "bibtex",
        )
        entry = next(iter(db.entries.values()))
        assert gb._fallback_key(entry) is not None

    def test_doi_colon_prefix_now_strips(self):
        import generate_bibliography as gb
        assert gb._normalize_doi("doi:10.1000/X") == "10.1000/x"


class TestNonLatinSurnameNoLongerVanishes:
    """ROADMAP item 4 / bib-pipeline-integrity-gaps Issue B, second mode:
    _normalize_for_matching ASCII-folds a wholly non-Latin surname to '' and
    the entry was skipped before any matching ran, so a cited work was
    deterministically absent from the rendered References."""

    GREEK_SURNAME = "Παπαδόπουλος"

    def _bib(self):
        from pybtex.database import parse_string
        return parse_string(
            "@article{pap2021,\n"
            f"  author = {{{self.GREEK_SURNAME}, Γ.}},\n"
            "  title = {On Technology},\n"
            "  year = {2021},\n"
            "  journal = {J Phil},\n"
            "}",
            "bibtex",
        )

    def test_greek_surname_citation_resolves(self):
        import generate_bibliography as gb
        review = f"Recent work ({self.GREEK_SURNAME} 2021) argues otherwise."
        cited = gb.find_cited_entries(review, self._bib())
        assert [k for k, _ in cited] == ["pap2021"]

    def test_uncited_greek_entry_is_still_excluded(self):
        import generate_bibliography as gb
        cited = gb.find_cited_entries("Nothing relevant is cited here.", self._bib())
        assert cited == []

    def test_latin_surname_matching_is_unchanged(self):
        from pybtex.database import parse_string
        import generate_bibliography as gb
        bib = parse_string(
            "@article{clark1998,\n"
            "  author = {Clark, Andy and Chalmers, David},\n"
            "  title = {The Extended Mind},\n"
            "  year = {1998},\n}",
            "bibtex",
        )
        assert [k for k, _ in gb.find_cited_entries(
            "As Clark and Chalmers (1998) argue,", bib)] == ["clark1998"]
        assert gb.find_cited_entries("No citation at all.", bib) == []


class TestFormatDoiNormalizesFirst:
    """Follow-up to ROADMAP item 4: _format_doi rendered the RAW doi field, so
    a bib carrying a prefixed DOI emitted a broken hyperlink into References."""

    def test_doi_colon_prefix_does_not_double_up(self):
        import generate_bibliography as gb
        assert gb._format_doi("doi:10.1000/x") == "https://doi.org/10.1000/x"

    def test_bare_doi_org_prefix_does_not_double_up(self):
        import generate_bibliography as gb
        assert gb._format_doi("doi.org/10.1000/x") == "https://doi.org/10.1000/x"

    def test_plain_doi_still_gets_a_url(self):
        import generate_bibliography as gb
        assert gb._format_doi("10.1000/x") == "https://doi.org/10.1000/x"

    def test_existing_url_passes_through_unchanged(self):
        import generate_bibliography as gb
        assert gb._format_doi("https://doi.org/10.1000/x") == "https://doi.org/10.1000/x"
        assert gb._format_doi("http://dx.doi.org/10.1000/x") == "https://doi.org/10.1000/x"

    def test_non_doi_url_is_not_wrapped(self):
        # A value that is a URL but not a known DOI prefix must not be glued
        # onto https://doi.org/ - it is returned as-is, as before.
        import generate_bibliography as gb
        assert gb._format_doi("http://example.com/paper") == "http://example.com/paper"


class TestPunctuationOnlySurnameFold:
    """Follow-up to ROADMAP item 4: a surname whose ASCII fold retains no
    alphanumeric character (a hyphenated non-Latin name folds to '-') took the
    primary path and matched a garbage pattern, so the entry could be
    spuriously INCLUDED in References."""

    HYPHENATED = "Παπαδόπουλος-Ιωάννου"

    def _bib(self):
        from pybtex.database import parse_string
        return parse_string(
            "@article{papioa2021,\n"
            f"  author = {{{self.HYPHENATED}, Γ.}},\n"
            "  title = {On Technology},\n"
            "  year = {2021},\n}",
            "bibtex",
        )

    def test_uncited_hyphenated_non_latin_entry_is_not_spuriously_included(self):
        import generate_bibliography as gb
        review = "The mind-body problem was much discussed in 2021 by others."
        assert gb.find_cited_entries(review, self._bib()) == []

    def test_genuinely_cited_hyphenated_non_latin_entry_resolves(self):
        import generate_bibliography as gb
        review = f"Recent work ({self.HYPHENATED} 2021) argues otherwise."
        assert [k for k, _ in gb.find_cited_entries(review, self._bib())] == ["papioa2021"]

    def test_partly_latin_surname_still_takes_the_primary_path(self):
        from pybtex.database import parse_string
        import generate_bibliography as gb
        bib = parse_string(
            "@article{papsmith2021,\n"
            "  author = {Παπαδόπουλος-Smith, Γ.},\n"
            "  title = {On Technology},\n"
            "  year = {2021},\n}",
            "bibtex",
        )
        assert [k for k, _ in gb.find_cited_entries(
            "As Papadopoulos-Smith (2021) notes,", bib)] == ["papsmith2021"]


class TestCleanerVerdictPropagation:
    """Item 3 A mirror: References-side dedup must not resurrect
    cleaner-removed fields."""

    BIB = '''
    @inproceedings{iclr_a,
        author = {Doe, Jane},
        title = {Impossible Publication},
        year = {2024},
        booktitle = {International Conference on Learning Representations},
        doi = {10.1000/same},
        abstract = {Substantial abstract making this the richer copy.},
    }
    @inproceedings{iclr_b,
        author = {Doe, Jane},
        title = {Impossible Publication},
        year = {2024},
        doi = {10.1000/same},
        keywords = {METADATA\\_CLEANED: booktitle},
    }
    '''
    REVIEW = "As Doe (2024) argued, the result is unpublishable."

    def _cited(self):
        from pybtex.database import parse_string
        from generate_bibliography import find_cited_entries
        return dict(find_cited_entries(self.REVIEW, parse_string(self.BIB, "bibtex")))

    def test_winner_loses_flagged_field(self):
        cited = self._cited()
        (entry,) = cited.values()
        assert "booktitle" not in {f.lower() for f in entry.fields.keys()}

    def test_union_does_not_reinsert(self):
        # Make the cleaned copy the winner (richer), uncleaned the loser.
        from pybtex.database import parse_string
        from generate_bibliography import find_cited_entries
        bib = self.BIB.replace(
            "abstract = {Substantial abstract making this the richer copy.},",
            "").replace(
            "keywords = {METADATA\\_CLEANED: booktitle},",
            "keywords = {METADATA\\_CLEANED: booktitle},\n"
            "        abstract = {Substantial abstract making this the richer copy.},\n"
            "        pages = {1--10},")
        cited = dict(find_cited_entries(self.REVIEW, parse_string(bib, "bibtex")))
        (entry,) = cited.values()
        assert "booktitle" not in {f.lower() for f in entry.fields.keys()}

    def test_append_to_existing_marker_adds_new_name_once(self):
        # Text/object seam (ledger T4a): the winner already carries its OWN
        # METADATA_CLEANED marker (a different removed set) when it absorbs
        # the loser's verdict - _apply_cleaner_verdicts must APPEND the new
        # name to the existing marker's change list, not overwrite it, and
        # each name must appear exactly once in the resulting value.
        from pybtex.database import parse_string
        from generate_bibliography import _apply_cleaner_verdicts
        bib = '''
        @article{w,
            author = {A, B},
            title = {T},
            year = {2020},
            doi = {10.1/x},
            keywords = {METADATA\\_CLEANED: doi},
        }
        @article{l,
            author = {A, B},
            title = {T},
            year = {2020},
            keywords = {METADATA\\_CLEANED: booktitle},
        }
        '''
        data = parse_string(bib, "bibtex")
        winner, loser = data.entries["w"], data.entries["l"]
        _apply_cleaner_verdicts(winner, loser)
        kw = winner.fields["keywords"]
        assert kw.count("doi") == 1
        assert kw.count("booktitle") == 1

    def test_folded_marker_readable_object_side_after_merge(self):
        # Ledger T4b: after a real find_cited_entries merge, the folded
        # marker must be readable back OBJECT-side via _entry_removed_fields
        # (not just as raw keywords text).
        from generate_bibliography import _entry_removed_fields
        cited = self._cited()
        (entry,) = cited.values()
        assert "booktitle" in _entry_removed_fields(entry)

    def test_dedupe_bib_folded_marker_round_trips_through_pybtex(self, tmp_path):
        # Ledger T4c: the text/object seam itself. dedupe_bib.py folds a
        # removal into the keywords marker as raw TEXT
        # (_fold_removals_into_marker); generate_bibliography.py and its
        # callers read markers back via pybtex-parsed field VALUES
        # (marker_removed_fields on entry.fields["keywords"]). This pins that
        # the text one script writes survives a real parse_file round-trip
        # into the form the other script's reader expects.
        from dedupe_bib import _fold_removals_into_marker
        from pybtex.database import parse_file
        from metadata_cleaner import marker_removed_fields
        entry_text = ('@inproceedings{iclr_x,\n'
                      '  author = {Doe, Jane},\n'
                      '  title = {Impossible Publication},\n'
                      '  year = {2024},\n'
                      '  keywords = {Medium}\n'
                      '}')
        folded = _fold_removals_into_marker(entry_text, {"booktitle"})
        bib_path = tmp_path / "seam.bib"
        bib_path.write_text(folded, encoding="utf-8")
        data = parse_file(str(bib_path), bib_format="bibtex")
        entry = data.entries["iclr_x"]
        assert "booktitle" in marker_removed_fields(entry.fields["keywords"])


class TestTransliterationMatching:
    """Item 3 B (matcher half), SYMMETRIC: either side may carry the
    diacritic or the ae-spelling."""

    def _cited(self, bib, review):
        from pybtex.database import parse_string
        from generate_bibliography import find_cited_entries
        return set(dict(find_cited_entries(review, parse_string(bib, "bibtex"))))

    FRAENKEN = ("@article{f2024, author = {Fr\u00e4nken, Jan}, title = {T},"
                " year = {2024}, journal = {J}}")
    MUELLER = ("@article{m2022, author = {Mueller, Hans}, title = {T},"
               " year = {2022}, journal = {J}}")

    def test_bib_diacritic_prose_ae(self):
        assert self._cited(self.FRAENKEN, "Fraenken (2024) shows X.") == {"f2024"}

    def test_bib_diacritic_prose_nfkd(self):
        assert self._cited(self.FRAENKEN, "Franken (2024) shows X.") == {"f2024"}

    def test_bib_ae_prose_diacritic_REVERSE(self):
        # The direction the one-haystack design missed (review P0).
        assert self._cited(self.MUELLER, "M\u00fcller (2022) shows X.") == {"m2022"}

    def test_bib_ae_prose_ae(self):
        assert self._cited(self.MUELLER, "Mueller (2022) shows X.") == {"m2022"}

    def test_uncited_still_unmatched(self):
        assert self._cited(self.MUELLER, "Nothing here (Other 2022).") == set()


class TestCollectMatches:
    """Item 3 E: _collect_matches is find_cited_entries' matching pre-pass.
    windows is a plain list[str] of year-bearing proximity slices - used by
    callers only for truthiness (a match exists) and length (hit count); it
    does not carry hit spans (M2: collision resolution re-parses citation
    instances straight from review_text instead)."""

    BIB = """
    @article{a1, author = {Smith, Jane}, title = {T1}, year = {2020}, journal = {J}}
    @article{a2, author = {Jones, Bob}, title = {T2}, year = {2021}, journal = {J}}
    """

    def _recs(self, review):
        from pybtex.database import parse_string
        from generate_bibliography import _collect_matches
        return _collect_matches(review, parse_string(self.BIB, "bibtex"))

    def test_matched_set_and_windows(self):
        recs = self._recs("Smith (2020) argues; nothing else.")
        assert [r["key"] for r in recs] == ["a1"]
        assert recs[0]["windows"]
        for w in recs[0]["windows"]:
            assert "2020" in w

    def test_every_hit_collected_in_order(self):
        recs = self._recs("Smith (2020) argues X. Later Smith (2020) repeats.")
        assert len(recs[0]["windows"]) >= 2

    def test_record_order_is_bib_order(self):
        recs = self._recs("Jones (2021) then Smith (2020).")
        assert [r["key"] for r in recs] == ["a1", "a2"]


class TestCollisionResolution:
    """Item 3 E: phantoms die when prose forms discriminate; partial
    ambiguity keeps candidate unions; nothing cited is ever dropped."""

    def _cited(self, bib, review):
        from pybtex.database import parse_string
        from generate_bibliography import find_cited_entries
        return set(dict(find_cited_entries(review, parse_string(bib, "bibtex"))))

    MULDOON = """
    @article{muldoon2023a, author = {Muldoon, Ryan and Wu, Jin}, title = {T1}, year = {2023}, journal = {J}}
    @article{muldoon2023b, author = {Muldoon, Ryan and Gordon, Ann and Wu, Jin and Li, Kai}, title = {T2}, year = {2023}, journal = {J}}
    """

    def test_two_author_form_kills_phantom(self):
        assert self._cited(self.MULDOON, "As Muldoon and Wu (2023) argue, X.") == {"muldoon2023a"}

    def test_et_al_form_selects_multiauthor(self):
        assert self._cited(self.MULDOON, "As Muldoon et al. (2023) argue, X.") == {"muldoon2023b"}

    def test_adjacent_forms_keep_both_either_order(self):
        both = {"muldoon2023a", "muldoon2023b"}
        assert self._cited(self.MULDOON,
            "Muldoon and Wu (2023) argue X; Muldoon et al. (2023) argue Y.") == both
        assert self._cited(self.MULDOON,
            "Muldoon et al. (2023) argue Y; Muldoon and Wu (2023) argue X.") == both

    def test_semicolon_parenthetical_both_orders(self):
        both = {"muldoon2023a", "muldoon2023b"}
        assert self._cited(self.MULDOON,
            "Work agrees (Muldoon and Wu 2023; Muldoon et al. 2023).") == both
        assert self._cited(self.MULDOON,
            "Work agrees (Muldoon et al. 2023; Muldoon and Wu 2023).") == both

    def test_and_form_must_not_affirm_multiauthor(self, capsys):
        # review 2.4: the "and Gordon" form belongs to a TWO-author entry;
        # the 4-author entry (second author Gordon) is cited "Muldoon et
        # al." per house style, so this instance yields NO candidate - the
        # group falls to warn-and-keep-all rather than confidently
        # affirming the 4-author entry via its second author.
        bib = self.MULDOON.replace("Wu, Jin}", "Qi, Bo}")  # a: Muldoon+Qi
        cited = self._cited(bib, "As Muldoon and Gordon (2023) claim, X.")
        assert cited == {"muldoon2023a", "muldoon2023b"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    def test_unrelated_second_position_does_not_flip_ambiguous_to_drop(self, capsys):
        # post-review fix: an unresolvable first-position form ("Muldoon
        # and Gordon") must stay ambiguous-keep-all even when the SAME
        # text elsewhere also contains an unrelated, cleanly-parsed
        # second-position sighting of "Muldoon" (the Bloggs sentence) -
        # partial ambiguity must never drop a cited work.
        bib = self.MULDOON.replace("Wu, Jin}", "Qi, Bo}")  # a: Muldoon+Qi
        cited = self._cited(bib,
            "As Muldoon and Gordon (2023) claim, X. "
            "Elsewhere, Bloggs and Muldoon (2023) discuss Q.")
        assert cited == {"muldoon2023a", "muldoon2023b"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    def test_first_position_resolution_unaffected_by_unrelated_second_position(self):
        # inverse guard: a first-position instance that DOES resolve to a
        # candidate must keep resolving normally even when the text also
        # contains an unrelated second-position sighting of the same
        # surname family.
        cited = self._cited(self.MULDOON,
            "Muldoon and Wu (2023) argue X. "
            "Bloggs and Muldoon (2023) discuss Q.")
        assert cited == {"muldoon2023a"}

    def test_sentence_leading_capital_is_not_a_first_name(self):
        # "As Moore (2020)" - the captured "As" must be ignored, not used
        # to eliminate the solo candidate (informative-first_text rule).
        assert self._cited(self.MOORE, "As Moore (2020) argues, X.") == {"moore2020solo"}

    MOORE = """
    @article{moore2020solo, author = {Moore, Alfred}, title = {T1}, year = {2020}, journal = {J}}
    @article{moore2020five, author = {Moore, Alfred and A, B and C, D and E, F and G, H}, title = {T2}, year = {2020}, journal = {J}}
    """

    def test_solo_form_kills_multiauthor_phantom(self, capsys):
        assert self._cited(self.MOORE, "Moore (2020) argues X.") == {"moore2020solo"}
        assert "moore2020five" in capsys.readouterr().err

    JOHNSONS = """
    @article{johnsonG, author = {Johnson, Gabbrielle}, title = {T1}, year = {2024}, journal = {J}}
    @article{johnsonR, author = {Johnson, Rebecca}, title = {T2}, year = {2024}, journal = {J}}
    @article{johnsonTeam, author = {Johnson, Ada and B, C and D, E and F, G}, title = {T3}, year = {2024}, journal = {J}}
    """

    def test_first_initial_selects_person(self):
        cited = self._cited(self.JOHNSONS, "G. Johnson (2024) argues X.")
        assert cited == {"johnsonG"}

    def test_partial_ambiguity_keeps_candidate_union(self, capsys):
        # review P0: the bare solo instance supports BOTH solo entries; the
        # et-al instance supports the team - nobody cited is dropped.
        cited = self._cited(self.JOHNSONS,
            "Johnson (2024) argues X; Johnson et al. (2024) argue Y.")
        assert cited == {"johnsonG", "johnsonR", "johnsonTeam"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    def test_bare_ambiguous_keeps_solos_and_warns(self, capsys):
        cited = self._cited(self.JOHNSONS, "Recent work (Johnson 2024) shows X.")
        assert cited == {"johnsonG", "johnsonR"}
        assert "[COLLISION]" in capsys.readouterr().err

    def test_two_multiauthor_etal_keeps_both_and_warns(self, capsys):
        bib = """
        @article{t1, author = {Kim, S and A, B and C, D}, title = {T1}, year = {2022}, journal = {J}}
        @article{t2, author = {Kim, S and E, F and G, H and I, J}, title = {T2}, year = {2022}, journal = {J}}
        """
        cited = self._cited(bib, "Kim et al. (2022) argue X.")
        assert cited == {"t1", "t2"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    MENARY = """
    @book{menary2010a, author = {Menary, Richard}, title = {The Extended Mind}, year = {2010}, publisher = {P}}
    @incollection{menary2010b, author = {Menary, Richard}, title = {Cognitive Integration}, year = {2010}, booktitle = {B}, publisher = {P}}
    """

    def test_same_author_group_stays_whole_for_3f(self, capsys):
        cited = self._cited(self.MENARY, "Menary (2010) develops integration.")
        assert cited == {"menary2010a", "menary2010b"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    def test_year_suffix_stays_conservative(self, capsys):
        # review edge: 2010a/2010b prose - E must not pretend to resolve
        # what only item F's suffixes can.
        cited = self._cited(self.MENARY, "Menary (2010a) and Menary (2010b) differ.")
        assert cited == {"menary2010a", "menary2010b"}

    def test_multiword_second_surname(self):
        bib = """
        @article{k1, author = {Kim, Sun and de la Cruz, Maria}, title = {T1}, year = {2022}, journal = {J}}
        @article{k2, author = {Kim, Sun and Novak, Petr and Ola, Ade and P, Q}, title = {T2}, year = {2022}, journal = {J}}
        """
        cited = self._cited(bib, "As Kim and de la Cruz (2022) show, X.")
        assert cited == {"k1"}

    def test_cross_spelling_entries_form_one_group(self, capsys):
        # review 2.5: bib Müller and bib Mueller must compete, not both
        # survive as singletons.
        bib = """
        @article{u1, author = {Müller, Hans}, title = {T1}, year = {2022}, journal = {J}}
        @article{u2, author = {Mueller, Hans and B, C and D, E}, title = {T2}, year = {2022}, journal = {J}}
        """
        cited = self._cited(bib, "Mueller (2022) argues X.")
        assert cited == {"u1"}

    def test_second_author_position_not_a_first_author_cite(self):
        # review edge: "Bloggs and Muldoon (2023)" must not read as a solo
        # Muldoon citation.
        bib = """
        @article{m1, author = {Muldoon, Ryan}, title = {T1}, year = {2023}, journal = {J}}
        @article{m2, author = {Muldoon, Ryan and A, B}, title = {T2}, year = {2023}, journal = {J}}
        @article{bloggs, author = {Bloggs, Joe and Muldoon, Ryan}, title = {T3}, year = {2023}, journal = {J}}
        """
        cited = self._cited(bib, "Bloggs and Muldoon (2023) note this.")
        assert "m1" not in cited and "m2" not in cited

    def test_second_position_sighting_requires_corroboration(self, capsys):
        # I1: an uncorroborated second-position sighting must not license a
        # drop. "Following Kripke and Putnam (1975)" puts "Putnam" second,
        # but no bib record's author list actually explains a Kripke-
        # Putnam pairing - there is no Kripke entry in this bib at all - so
        # it's a narrative aside, not positive evidence against the Putnam
        # group (contrast the branch's own bloggs test above, where the
        # "bloggs" bib entry IS Bloggs-and-Muldoon and so corroborates the
        # drop).
        bib = """
        @article{p1, author = {Putnam, Hilary}, title = {T1}, year = {1975}, journal = {J}}
        @article{p2, author = {Putnam, Hilary and Other, B}, title = {T2}, year = {1975}, journal = {J}}
        """
        from pybtex.database import parse_string
        from generate_bibliography import find_cited_entries, generate_references
        entries = find_cited_entries(
            "Following Kripke and Putnam (1975), reference is causal.",
            parse_string(bib, "bibtex"))
        assert {k for k, _ in entries} == {"p1", "p2"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err
        # lint-consistency: both survive all the way to a rendered References
        # section, not just find_cited_entries' membership.
        refs = generate_references(entries)
        assert '"T1."' in refs and '"T2."' in refs

    def test_list_position_not_misread_as_and_form(self, capsys):
        # C1: _CITE_INSTANCE_RE has no left anchor, so it can bind at the
        # SECOND name of a longer comma list ("Smith, Jones, and Lee
        # (2020)" -> misread as "Jones and Lee") and manufacture a phantom
        # discriminator that drops the genuinely (if unparseably) cited
        # solo Jones entry. The left-anchor guard rejects that binding, so
        # the group falls to ambiguous-keep-all instead of a wrong drop.
        bib = """
        @article{j_solo, author = {Jones, A}, title = {T1}, year = {2020}, journal = {J}}
        @article{j_pair, author = {Jones, A and Lee, B}, title = {T2}, year = {2020}, journal = {J}}
        @article{j_team, author = {Jones, A and Lee, B and Wu, C}, title = {T3}, year = {2020}, journal = {J}}
        """
        cited = self._cited(bib,
            "Smith, Jones, and Lee (2020) argue X. "
            "Jones's separate 2020 paper differs.")
        assert cited == {"j_solo", "j_pair", "j_team"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    def test_ampersand_lead_in_not_misread_as_solo(self, capsys):
        # C1, second shape: "Jones & Lee (2020)" isn't a form
        # _CITE_INSTANCE_RE parses ("&" unsupported for the two-author
        # form), but without the anchor guard the regex still matches
        # starting at "Lee", misreading it as a bare solo citation and
        # dropping the et-al entry actually cited a sentence later.
        bib = """
        @article{l_solo, author = {Lee, B}, title = {T1}, year = {2020}, journal = {J}}
        @article{l_team, author = {Lee, B and P, Q and R, S}, title = {T2}, year = {2020}, journal = {J}}
        """
        cited = self._cited(bib,
            "Jones & Lee (2020) argue X. "
            "Lee et al.'s earlier 2020 study agrees.")
        assert cited == {"l_solo", "l_team"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    ADVERB_BIB = """
    @article{m_solo, author = {Muldoon, Ryan}, title = {T1}, year = {2023}, journal = {J}}
    @article{m_pair, author = {Muldoon, Ryan and Wu, Jin}, title = {T2}, year = {2023}, journal = {J}}
    """

    def test_sentence_adverb_lead_in_still_discriminates(self, capsys):
        # The bare-comma half of the left-anchor guard used to reject any
        # match preceded by "Capitalized, " - which includes a sentence-
        # initial transition ("However, Muldoon and Wu (2023)"). The
        # instance was discarded and the group fell to keep-all-and-warn,
        # listing an uncited work. The lead-in exclusion restores it.
        cited = self._cited(self.ADVERB_BIB,
            "However, Muldoon and Wu (2023) argue X.")
        assert cited == {"m_pair"}
        assert "[COLLISION] ambiguous" not in capsys.readouterr().err

    def test_list_guard_survives_an_adverb_prefix(self, capsys):
        # The interaction that must NOT regress: a transition word before a
        # genuine comma list must not re-enable the wrong binding. Here the
        # "Wu" match is preceded by "Muldoon, ", which is still a name-comma
        # lead-in, so it stays rejected and the group keeps all + warns.
        bib = self.ADVERB_BIB + (
            "@article{w_solo, author = {Wu, Jin}, title = {T3},"
            " year = {2023}, journal = {J}}\n")
        cited = self._cited(bib,
            "However, Muldoon, Wu, and Li (2023) argue X. "
            "Wu's separate 2023 paper differs.")
        assert cited == {"m_solo", "m_pair", "w_solo"}
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    def test_possessive_narrative(self):
        assert self._cited(self.MOORE, "Moore's (2020) account holds.") == {"moore2020solo"}

    def test_singleton_untouched_no_warning(self, capsys):
        bib = "@article{solo, author = {Rare, Ann}, title = {T}, year = {2020}, journal = {J}}"
        assert self._cited(bib, "Rare (2020) argues X.") == {"solo"}
        assert "[COLLISION]" not in capsys.readouterr().err

    def test_nonascii_diagnostics_are_ascii(self, capsys):
        bib = """
        @article{g1, author = {Müller, Hans}, title = {T1}, year = {2021}, journal = {J}}
        @article{g2, author = {Mueller, Hans}, title = {T2}, year = {2021}, journal = {J}}
        """
        self._cited(bib, "The debate continued through 2021 with Müller central.")
        err = capsys.readouterr().err
        assert all(ord(c) < 128 for c in err)


class TestYearSuffixRendering:
    def _entry(self, bib_text):
        from pybtex.database import parse_string
        db = parse_string(bib_text, "bibtex")
        key = list(db.entries.keys())[0]
        return key, db.entries[key]

    def test_article_renders_letter(self):
        key, entry = self._entry("""@article{m2010a,
          author = {Menary, Richard}, title = {Cognitive Integration},
          journal = {Synthese}, year = {2010}, year_suffix = {a}}""")
        out = generate_bibliography.format_entry(entry, key)
        # Author list always ends its own sentence with a period (existing
        # convention, e.g. TestFormatEntry.test_missing_optional_fields'
        # "Author, Test." check) - so the year clause reads "Richard. 2010a."
        assert "Menary, Richard. 2010a." in out

    def test_book_renders_letter(self):
        key, entry = self._entry("""@book{m2010b,
          author = {Menary, Richard}, title = {The Extended Mind},
          publisher = {MIT Press}, year = {2010}, year_suffix = {b}}""")
        assert "2010b." in generate_bibliography.format_entry(entry, key)

    def test_no_field_renders_plain_year(self):
        key, entry = self._entry("""@article{m2010,
          author = {Menary, Richard}, title = {Solo}, journal = {Synthese},
          year = {2010}}""")
        out = generate_bibliography.format_entry(entry, key)
        assert "2010." in out and "2010a" not in out

    def test_junk_suffix_is_ignored(self):
        # Defensive: a field that is not a single letter renders as if absent.
        for junk in ("2010", "ab", "1", ""):
            key, entry = self._entry("""@article{m2010,
              author = {Menary, Richard}, title = {Solo}, journal = {Synthese},
              year = {2010}, year_suffix = {%s}}""" % junk)
            out = generate_bibliography.format_entry(entry, key)
            assert "2010." in out
            assert "2010" + junk not in out or junk == ""

    def test_uppercase_suffix_is_normalized_not_rejected(self):
        # Decided: _display_year lowercases, so {A} renders as 2010a. State the
        # behaviour and test it, rather than leaving a comment that says
        # "junk is ignored" while the code quietly accepts it.
        key, entry = self._entry("""@article{m2010,
          author = {Menary, Richard}, title = {Solo}, journal = {Synthese},
          year = {2010}, year_suffix = {A}}""")
        out = generate_bibliography.format_entry(entry, key)
        assert "2010a." in out and "2010A" not in out

    def test_sort_orders_a_before_b(self):
        from pybtex.database import parse_string
        db = parse_string("""@book{b,
          author = {Menary, Richard}, title = {Zeta}, publisher = {MIT},
          year = {2010}, year_suffix = {b}}
        @book{a, author = {Menary, Richard}, title = {Alpha},
          publisher = {MIT}, year = {2010}, year_suffix = {a}}""", "bibtex")
        pairs = sorted(db.entries.items(), key=generate_bibliography._sort_key)
        assert [k for k, _ in pairs] == ["a", "b"]
