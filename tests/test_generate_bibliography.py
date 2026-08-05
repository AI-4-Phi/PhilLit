"""Tests for generate_bibliography.py - Bibliography generation from BibTeX."""

import sys
from pathlib import Path

import pytest

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

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
