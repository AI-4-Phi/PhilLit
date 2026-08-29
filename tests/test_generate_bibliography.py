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
    _collect_matches,
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

    def test_ldots_not_mangled_by_l_escape(self):
        """\\l (l-slash) must not fire inside \\ldots -- delivered
        References carried 'isłdots' (algorithmic-fairness-2023)."""
        assert clean_bibtex_str(r"What's Fair is\ldots{} Fair?") == "What's Fair is... Fair?"
        assert clean_bibtex_str(r"is\ldots done") == "is... done"

    def test_ldots_terminates_at_non_letters_only(self):
        """A TeX control word ends at any non-LETTER, so the guard on the
        ellipsis rewrite must be `(?![A-Za-z])`, not `\\b`.

        `\\ldotsfoo` is a DIFFERENT (unknown) control sequence and must not
        become '...foo' -- but `\\b` was stricter than TeX and also blocked
        digits and `_`, regressing `page 3\\ldots42` into the `\\l`
        (l-slash) fold this rewrite exists to prevent."""
        # Non-letter terminators: the rewrite MUST fire.
        assert clean_bibtex_str(r"page 3\ldots42 end") == "page 3...42 end"
        assert clean_bibtex_str(r"is\ldots_x done") == "is..._x done"
        # Letter terminator: the rewrite must NOT fire. The exact result
        # pins the PRE-EXISTING `\l` fold on this pathological input
        # ('is\ldotsfoo' -> 'is<l-slash>dotsfoo'), which is not something
        # this guard promises to fix -- what it promises is the absence of
        # the ellipsis rewrite, asserted separately below.
        assert clean_bibtex_str(r"is\ldotsfoo done") == "isłdotsfoo done"
        assert "..." not in clean_bibtex_str(r"is\ldotsfoo done")

    def test_textit_command_stripped_argument_kept(self):
        """Delivered References carried 'Precis of \\textitUtopophobia'."""
        assert clean_bibtex_str(
            r"Precis of \textit{Utopophobia: On the Limits}"
        ) == "Precis of Utopophobia: On the Limits"

    def test_emph_command_stripped(self):
        assert clean_bibtex_str(
            r"Debate: On {Christiano}'s {\emph{The Constitution of Equality}}"
        ) == "Debate: On Christiano's The Constitution of Equality"

    def test_l_slash_alone_still_decodes(self):
        assert clean_bibtex_str(r"Wis{\l}awa") == "Wisława"


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

    def test_misc_renders_accessed_date_and_archive_link(self):
        """urldate and archiveurl are barrier-authored. Chicago
        provides for both, and the archive link is link-rot insurance."""
        entry = _make_entry(
            "misc",
            authors=["Omohundro, Steve"],
            title="The Basic AI Drives",
            year="2008",
            howpublished="https://a.example/x",
            urldate="2026-08-14",
            archiveurl="https://web.archive.org/web/2024/https://a.example/x",
        )
        result = format_entry(entry, "omohundro2008basic")
        assert "Accessed 2026-08-14." in result
        assert "web.archive.org" in result

    def test_latex_wrapped_url_is_unwrapped_not_printed_literally(self):
        """REGRESSION PIN, not a fix. A rider once claimed
        this is broken -- that `_format_misc` tests `howpublished.startswith
        ("http")`, so the `\\url{...}` form the researcher template mandates
        falls to the plain-text branch and ships the macro as visible text.

        It does not: `clean_bibtex_str` already strips the macro (step 4,
        `generate_bibliography.py:62`) before `_format_misc` ever sees the
        value, so the http branch is taken. The rider is moot and no unwrap was
        added; this test exists so the behaviour cannot regress silently, since
        the two functions that produce it are far apart."""
        entry = _make_entry(
            "misc",
            authors=["Blogger, Some"],
            title="A Post",
            year="2024",
            howpublished=r"\url{https://a.example/x}",
        )
        result = format_entry(entry, "blog2024post")
        assert r"\url{" not in result
        assert "[https://a.example/x](https://a.example/x)" in result

    def test_misc_without_the_new_fields_is_unchanged(self):
        entry = _make_entry(
            "misc",
            authors=["Blogger, Some"],
            title="A Post",
            year="2024",
            howpublished="https://a.example/x",
        )
        result = format_entry(entry, "blog2024post")
        assert "Accessed" not in result and "Archived" not in result

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

    # -- ae/oe/ue contraction fold (third haystack + needle axis) ---------

    def test_contract_haystack_bridges_bib_digraph_free_to_prose_digraph(self):
        """Bib "Franken" (no diacritic, no digraph) is matched by prose
        "Fraenken" (2023) -- THIS is the third-haystack direction. Needle-side
        ascii_variants alone contracts "Fraenken" -> "franken", but that only
        helps when the BIB surname carries the digraph; here the digraph is
        in the PROSE, so a refactor that drops the contract_text haystack
        (leaving only norm_text/translit_text) fails this test."""
        bib = _make_bib(("franken2023", _make_entry(
            authors=["Franken, F."], title="T", year="2023")))
        cited = find_cited_entries("As Fraenken (2023) argues, this holds.", bib)
        assert len(cited) == 1
        assert cited[0][0] == "franken2023"

    def test_needle_side_bridges_bib_digraph_to_prose_plain(self):
        """Bib "Fraenken" matched by prose "Franken" (2023) -- the needle-side
        direction (ascii_variants' contraction of the BIB surname)."""
        bib = _make_bib(("fraenken2023", _make_entry(
            authors=["Fraenken, F."], title="T", year="2023")))
        cited = find_cited_entries("As Franken (2023) argues, this holds.", bib)
        assert len(cited) == 1
        assert cited[0][0] == "fraenken2023"

    def test_sogaard_hedden_shaped_live_regression(self):
        """The live regression this fix targets: a delivered algorithmic-
        fairness review's References contained sogaard2024hedden, and the
        pre-fix matcher DROPPED it on re-run. Bib "Søgaard" (ø does not
        NFKD-decompose -> plain fold "sgaard") vs prose "Sogaard" needs the
        contraction, which routes ø->oe->o via translit_fold."""
        bib = _make_bib(("sogaard2024hedden", _make_entry(
            authors=["Søgaard, Søren"], title="T", year="2024")))
        cited = find_cited_entries("As Sogaard (2024) shows, fairness metrics vary.", bib)
        assert len(cited) == 1
        assert cited[0][0] == "sogaard2024hedden"

    def test_flood_non_regression_short_contraction_not_a_needle(self):
        """Bib "Noë" 2004: contract_fold("noe") == "no", which the length
        guard in ascii_variants excludes (a bare "no" would match essentially
        any sentence near a year). Prose here contains "no" near "(2004)" but
        never the name Noë/Noe -- must NOT match, which is the guard's whole
        point."""
        bib = _make_bib(("noe2004", _make_entry(
            authors=["Noë, N."], title="T", year="2004")))
        matches = _collect_matches(
            "There is no reason to doubt this claim; the report (2004) "
            "supports it.",
            bib)
        assert matches == []

    def test_residual_michael_michal_homograph_pin(self):
        """ACCEPTED RESIDUAL (see bib_identity.ascii_variants docstring):
        contract_fold("michael") == "michal" (the "ae" in "Michael"
        contracts), so bib "Michael, J." now bridges to prose "Michal" even
        though these are different names, not an umlaut/digraph pair. Pinned
        deliberately -- the extended-set census found NO Michael/Michal-shape
        first-author pair in the corpus (its sole newly-bridged pair was
        Schaeffer/Schaffer, sharing no year), and the same-year collision
        precondition that would make this a real mismatch lands in
        _resolve_collisions, not here."""
        bib = _make_bib(("michael2020", _make_entry(
            authors=["Michael, J."], title="T", year="2020")))
        cited = find_cited_entries("As Michal (2020) argues, this holds.", bib)
        assert len(cited) == 1
        assert cited[0][0] == "michael2020"

    def test_same_year_contraction_collision_pin(self):
        """PIN, not a prescription: bib holds BOTH "Müller 2020" (needle-side
        already includes plain "muller" via the NFKD fold, pre-existing) and
        "Mueller 2020" (now ALSO includes "muller" via the new contraction of
        its translit fold "mueller" -> "muller") -- introduced by this fix.
        Prose cites "Muller (2020)" once, ambiguously, so both entries fall
        into one same-year collision group. _resolve_collisions' keep-all
        rule for an unresolvable ambiguous group keeps both rather than
        guessing which is meant. Comment exists so a future change to that
        keep-side machinery shows up here, not silently."""
        bib = _make_bib(
            ("muller_umlaut2020", _make_entry(
                authors=["Müller, Hans"], title="T1", year="2020")),
            ("mueller_ascii2020", _make_entry(
                authors=["Mueller, Hans"], title="T2", year="2020")),
        )
        cited = find_cited_entries(
            "As Muller (2020) argued, the point stands.", bib)
        keys = {k for k, _ in cited}
        assert keys == {"muller_umlaut2020", "mueller_ascii2020"}


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


class TestYearSuffixField:
    """Chicago letters, mirrored from dedupe_bib.merge_entries: this dedup
    pass picks its winner by
    _substantive_field_count, a DIFFERENT criterion than dedupe_bib's
    (abstract-then-importance), so the survivor here can be a different
    copy than the one dedupe_bib kept - and this function's output IS what
    format_entry renders into the delivered References, so the same
    unanimous / copy-up / conflict policy is needed independently."""

    def _bib(self, winner_suffix=None, loser_suffix=None):
        winner_fields = dict(
            authors=["Smith, Anna"], title="Data and Things", year="2020",
            journal="Synthese", abstract="A real abstract, long enough.",
            doi="10.1000/xyz123")
        loser_fields = dict(
            authors=["Smith, Anna"], title="Data and Things", year="2020",
            doi="10.1000/xyz123")
        if winner_suffix is not None:
            winner_fields["year_suffix"] = winner_suffix
        if loser_suffix is not None:
            loser_fields["year_suffix"] = loser_suffix
        return _make_bib(
            ("winner2020", _make_entry(**winner_fields)),
            ("loser2020", _make_entry(**loser_fields)),
        )

    def test_unanimous_suffix_survives_merge(self):
        bib = self._bib(winner_suffix="a", loser_suffix="a")
        cited = find_cited_entries("Smith (2020a) argues X.", bib)
        assert len(cited) == 1
        assert cited[0][1].fields.get("year_suffix") == "a"

    def test_missing_winner_suffix_is_copied_from_agreeing_loser(self):
        bib = self._bib(winner_suffix=None, loser_suffix="b")
        cited = find_cited_entries("Smith (2020) argues X.", bib)
        assert len(cited) == 1
        assert cited[0][1].fields.get("year_suffix") == "b"

    def test_conflicting_suffixes_warn_and_change_nothing(self, capsys):
        bib = self._bib(winner_suffix="a", loser_suffix="b")
        cited = find_cited_entries("Smith (2020a) argues X.", bib)
        assert len(cited) == 1
        assert cited[0][1].fields.get("year_suffix") == "a"  # winner's kept
        err = capsys.readouterr().err
        assert "[SUFFIX] conflict" in err
        assert "winner2020" in err and "loser2020" in err
        assert "'a'" in err and "'b'" in err

    def test_lettered_winner_and_bare_loser_merge_silently(self, capsys):
        # The fourth quadrant of the merge policy: the winner carries a letter
        # and the loser carries none. Nothing to copy up, nothing to conflict
        # over - the winner keeps its letter and NO warning fires. Pins the
        # `loser_suffix and` conjunct of the conflict test, without which a
        # bare loser would be reported as conflicting with every letter.
        bib = self._bib(winner_suffix="a", loser_suffix=None)
        cited = find_cited_entries("Smith (2020a) argues X.", bib)
        assert len(cited) == 1
        assert cited[0][1].fields.get("year_suffix") == "a"
        assert "[SUFFIX] conflict" not in capsys.readouterr().err


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
# The References boundary is fence-aware, and there is
# ONE scanner for it
# =============================================================================

class TestFencedReferencesHeadingIsNotABoundary:
    """A ```text fenced "## References" example used to be treated as the real
    boundary by BOTH sides of this script: the read side stopped matching
    there (every citation after it silently dropped) and the write side
    replaced the document from there (the prose itself deleted). The linter
    already refused to be fooled by the same input, which is the whole point -
    one component held the rule and another broke it."""

    FENCED = ('# Review\n'
              '\n'
              'This review formats its bibliography like so:\n'
              '\n'
              '```text\n'
              '## References\n'
              '\n'
              'Smith, Jane. 2020. "A Paper." *Mind*.\n'
              '```\n'
              '\n'
              'Smith (2020) argues that p.\n')

    BIB = """@article{smith2020, author = {Smith, Jane}, title = {A Paper},
  journal = {Mind}, year = {2020}}"""

    def _db(self):
        from pybtex.database import parse_string
        return parse_string(self.BIB, "bibtex")

    def test_a_citation_after_a_fenced_heading_still_matches(self):
        # The cited-work drop half. Pre-fix this returned [].
        assert [k for k, _ in find_cited_entries(self.FENCED, self._db())] \
            == ["smith2020"]

    def test_the_document_is_not_truncated_at_a_fenced_heading(self):
        # The data-loss half, asserted over the WHOLE document rather than the
        # key list: pre-fix, apply_references returned everything up to the
        # fence's heading plus the new section, so the fenced example, the
        # sentence citing Smith, and anything after them were gone.
        refs = generate_references(find_cited_entries(self.FENCED, self._db()))
        result = apply_references(self.FENCED, refs)
        assert self.FENCED.rstrip("\n") in result       # nothing removed
        assert "Smith (2020) argues that p." in result  # the real citation
        assert "```text\n## References\n" in result     # the fenced example
        assert result.count("## References") == 2       # fenced + appended
        assert result.rstrip("\n").endswith('*Mind*.')  # appended at the END

    def test_a_real_heading_after_the_fence_is_still_the_boundary(self):
        # The fence-awareness must not degrade into "never find a boundary":
        # a genuine References section following the fenced example is still
        # stripped from the matcher and replaced by the writer.
        text = self.FENCED + '\n## References\n\nStale, Entry. 1999. "Gone."\n'
        assert generate_bibliography._strip_references_section(text) \
            == self.FENCED + "\n"
        result = apply_references(text, '## References\n\nNew.\n')
        assert "Stale, Entry" not in result
        assert "Smith (2020) argues that p." in result

    def test_an_unterminated_fence_does_not_hide_the_real_heading(self):
        # A REGRESSION the fence-awareness itself introduced, and not the
        # harmless one it looks like. An unclosed fence hides every heading
        # after it, so the scanner found nothing and the generator APPENDED a
        # second References section beside the real one -- and handed the whole
        # document, stale reference list included, to the matcher, where
        # _sighted_letters reads the rendered "2010b." as a genuine mention and
        # protects that entry for ever. That is the convergence failure the
        # References strip exists to prevent, reached through unbalanced
        # markdown. It also compounds: the fence stays unclosed in the output,
        # so every operator re-run of Phase 6 step 4 appends one more section.
        text = ('# Review\n\n```text\nunclosed example\n\n'
                'Smith (2020) argues that p.\n\n'
                '## References\n\nStale, Entry. 1999. "Gone."\n')
        result = apply_references(text, '## References\n\nNew.\n')
        assert result.count("## References") == 1
        assert "Stale, Entry" not in result
        assert "Smith (2020) argues that p." in result
        assert generate_bibliography._strip_references_section(text).count(
            "## References") == 0

    def test_a_balanced_fence_never_reaches_the_fallback(self):
        # The fallback fires ONLY when the strict pass found nothing AND ended
        # inside a fence, so balanced input keeps the fence-aware answer. A
        # fallback that fired unconditionally would restore the whole C1 bug.
        assert generate_bibliography._strip_references_section(self.FENCED) \
            == self.FENCED

    def test_the_generator_and_the_linter_share_one_scanner(self):
        # Not a copy - the object itself, per the repo's single-owner pattern.
        # Three sites read this boundary (two here, one in lint_md) and they
        # disagreed; an identity assertion is what stops a fourth copy.
        import lint_md
        assert generate_bibliography.find_refs_heading is lint_md.find_refs_heading
        assert lint_md._find_refs_heading is lint_md.find_refs_heading
        assert not hasattr(generate_bibliography, "_REFERENCES_HEADING_RE")


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
# Identity keys come from the one owner (hooks/bib_identity.py)
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
    """Non-Latin surnames, second mode:
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
    """_format_doi rendered the RAW doi field, so
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
    """A surname whose ASCII fold retains no
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
    """References-side dedup must not resurrect
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
    """Matcher half, SYMMETRIC: either side may carry the
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
        # The direction the one-haystack design missed.
        assert self._cited(self.MUELLER, "M\u00fcller (2022) shows X.") == {"m2022"}

    def test_bib_ae_prose_ae(self):
        assert self._cited(self.MUELLER, "Mueller (2022) shows X.") == {"m2022"}

    def test_uncited_still_unmatched(self):
        assert self._cited(self.MUELLER, "Nothing here (Other 2022).") == set()


class TestCollectMatches:
    """_collect_matches is find_cited_entries' matching pre-pass.
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
    """Phantoms die when prose forms discriminate; partial
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
        # The bare solo instance supports BOTH solo entries; the
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

    def test_the_suffix_validity_rule_over_the_junk_table(self):
        # The same rule -- single ASCII a-z, lowercased, else
        # absent -- is implemented TWICE: here in _entry_suffix and inline in
        # check_evidence.py's main(). Nothing asserts they agree, so a drift
        # would render "2010a" in the References while the evidence checker
        # read the entry as unlettered.
        #
        # This pins THIS side against the junk table. The cross-check itself
        # cannot live here: check_evidence's copy is inline in main(), not a
        # callable, so pinning both against one table needs that rule extracted
        # into a shared helper -- the right fix, and one that edits a file this
        # change does not own.
        cases = {"": "", "a": "a", "A": "a", "b": "b", "ab": "", "1": "",
                 "2010": "", " a ": "a", "-": "", "e": "e"}
        for raw, expected in cases.items():
            _key, entry = self._entry("""@article{m2010,
              author = {Menary, Richard}, title = {Solo}, journal = {Synthese},
              year = {2010}, year_suffix = {%s}}""" % raw)
            assert generate_bibliography._entry_suffix(entry) == expected, raw
        # Non-ASCII letters read as absent too: isalpha() alone would accept
        # them and put a character no citation can carry into a reference.
        from pybtex.database import parse_string
        db = parse_string(
            "@article{m, author = {Menary, Richard}, title = {T},"
            " journal = {J}, year = {2010}, year_suffix = {é}}", "bibtex")
        assert generate_bibliography._entry_suffix(db.entries["m"]) == ""

    def test_sort_orders_a_before_b(self):
        from pybtex.database import parse_string
        db = parse_string("""@book{b,
          author = {Menary, Richard}, title = {Zeta}, publisher = {MIT},
          year = {2010}, year_suffix = {b}}
        @book{a, author = {Menary, Richard}, title = {Alpha},
          publisher = {MIT}, year = {2010}, year_suffix = {a}}""", "bibtex")
        pairs = sorted(db.entries.items(), key=generate_bibliography._sort_key)
        assert [k for k, _ in pairs] == ["a", "b"]


MENARY_BIB = """@incollection{menary2010cognitive,
  author = {Menary, Richard}, title = {Cognitive Integration},
  booktitle = {The Extended Mind}, publisher = {MIT Press},
  year = {2010}, year_suffix = {a}}

@book{menary2010extended,
  author = {Menary, Richard}, title = {The Extended Mind},
  publisher = {MIT Press}, year = {2010}, year_suffix = {b}}"""


class TestYearSuffixMatching:
    def _cited(self, prose, bib_text=MENARY_BIB):
        from pybtex.database import parse_string
        db = parse_string(bib_text, "bibtex")
        return [k for k, _ in generate_bibliography.find_cited_entries(prose, db)]

    def _resolved(self, prose, bib_text=MENARY_BIB):
        """Keys surviving _resolve_collisions, BEFORE find_cited_entries'
        dedup -- the only way to observe the resolver on a group holding two
        copies of one work, which dedup would otherwise merge away."""
        from pybtex.database import parse_string
        db = parse_string(bib_text, "bibtex")
        records = generate_bibliography._collect_matches(prose, db)
        return sorted(r["key"] for r in
                      generate_bibliography._resolve_collisions(records, prose))

    def test_instance_parses_the_suffix(self):
        insts = generate_bibliography._citation_instances("Menary (2010a) argues.")
        assert insts[0]["year"] == "2010" and insts[0]["suffix"] == "a"

    def test_instance_without_suffix_is_empty_string(self):
        insts = generate_bibliography._citation_instances("Menary (2010) argues.")
        assert insts[0]["suffix"] == ""

    def test_suffixed_citation_selects_one_member(self):
        # THE payoff: same author, same year -- E cannot discriminate these,
        # the letter can.
        assert self._cited("As Menary (2010a) argues, integration matters.") == \
            ["menary2010cognitive"]

    def test_both_suffixes_keep_both(self):
        cited = self._cited("Menary (2010a) and Menary (2010b) differ.")
        assert sorted(cited) == ["menary2010cognitive", "menary2010extended"]

    def test_bare_citation_still_keeps_all(self):
        # Unchanged behaviour: an undisambiguated cite is ambiguous, and
        # ambiguity never drops a work.
        assert sorted(self._cited("Menary (2010) argues.")) == \
            ["menary2010cognitive", "menary2010extended"]

    def test_unmatched_suffix_never_drops(self):
        # Writer typo: no member carries 'c'. Keep both and warn -- dropping
        # here would delete a cited work (the Issue B failure).
        assert sorted(self._cited("Menary (2010c) argues.")) == \
            ["menary2010cognitive", "menary2010extended"]

    def test_partial_suffix_use_does_not_drop_the_other(self):
        assert sorted(self._cited("Menary (2010a) argues; Menary (2010) also.")) == \
            ["menary2010cognitive", "menary2010extended"]

    def test_semicolon_multicite_form(self):
        cited = self._cited("(Menary 2010a; Menary 2010b)")
        assert sorted(cited) == ["menary2010cognitive", "menary2010extended"]

    def test_continuation_years_are_parsed(self):
        # "Wiens (2015a; 2015b)" is the form 8 of 32 delivered reviews already
        # use: the surname appears ONCE and the second year follows a
        # semicolon. Without continuation parsing only 2015a becomes an
        # instance, and E's resolver would then drop the 2015b work as
        # unsupported -- a regression this feature must not introduce.
        insts = generate_bibliography._citation_instances("Menary (2010a; 2010b) differ.")
        assert [(i["year"], i["suffix"]) for i in insts] == [("2010", "a"), ("2010", "b")]
        assert insts[1]["surname_variants"] == insts[0]["surname_variants"]

    def test_continuation_keeps_both_works(self):
        assert sorted(self._cited("Menary (2010a; 2010b) differ.")) == \
            ["menary2010cognitive", "menary2010extended"]

    def test_comma_continuation_across_years(self):
        # The flagship comma-continuation case: "Menary (2006, 2010, 2013)".
        insts = generate_bibliography._citation_instances("Menary (2006, 2010, 2013) argue.")
        assert [i["year"] for i in insts] == ["2006", "2010", "2013"]

    def test_continuation_stops_at_the_closing_paren(self):
        # "Menary (2010), 2011 saw a shift" must NOT yield a 2011 citation.
        insts = generate_bibliography._citation_instances(
            "Menary (2010), 2011 saw a shift in the debate.")
        assert [i["year"] for i in insts] == ["2010"]

    def test_uncited_year_still_absent(self):
        assert self._cited("Nothing is cited here.") == []

    def test_partially_lettered_group_never_drops(self):
        # One member carries no letter (a legacy bib, a hand-edited bib, or a
        # DIFFERENT author who shares the surname and year). A suffixed
        # citation must NOT select the lettered member and drop the rest.
        mixed = MENARY_BIB + """

@article{menary2010third,
  author = {Menary, Richard}, title = {A Third Thing},
  journal = {Synthese}, year = {2010}}"""
        assert len(self._cited("Menary (2010a) argues.", mixed)) == 3

    def test_duplicate_letters_disable_the_filter(self):
        # Two members carrying the SAME letter is not a structurally complete
        # group -- filtering on it would pick an arbitrary one. Keep all.
        #
        # The fixture needs a THIRD member carrying a different letter, and
        # prose citing that letter. With only [a, a] the test could not fail:
        # filtering on "a" selects BOTH members, so removing the
        # distinct-letters conjunct changed nothing and the assertion held
        # either way. With [a, a, b] and prose "2010b",
        # dropping the conjunct drops the two "a" members.
        dup = """@book{a1, author = {Menary, Richard}, title = {One},
  publisher = {MIT Press}, year = {2010}, year_suffix = {a}}

@book{a2, author = {Menary, Richard}, title = {Two},
  publisher = {MIT Press}, year = {2010}, year_suffix = {a}}

@book{b1, author = {Menary, Richard}, title = {Three},
  publisher = {MIT Press}, year = {2010}, year_suffix = {b}}"""
        assert sorted(self._cited("Menary (2010b) argues.", dup)) == \
            ["a1", "a2", "b1"]

    def test_shared_doi_disables_the_filter(self):
        # _members_are_distinct_works, DOI axis alone. The titles differ, so
        # only the shared DOI can spot that these are two copies of one work
        # and switch the group back to keep-all. Asserted on the resolver
        # rather than find_cited_entries, whose own dedup would merge the two
        # copies afterwards and hide the difference.
        shared_doi = """@article{d1, author = {Menary, Richard},
  title = {Cognitive Integration}, journal = {Synthese}, year = {2010},
  doi = {10.1/same}, year_suffix = {a}}

@article{d2, author = {Menary, Richard}, title = {A Wholly Different Title},
  journal = {Mind}, year = {2010}, doi = {10.1/SAME}, year_suffix = {b}}"""
        assert self._resolved("Menary (2010a) argues.", shared_doi) == ["d1", "d2"]

    def test_shared_fallback_key_disables_the_filter(self):
        # _members_are_distinct_works, fallback-key axis alone: neither copy
        # carries a DOI, so only (title, year, surname) can spot them.
        shared_fkey = """@article{f1, author = {Menary, Richard},
  title = {Cognitive Integration}, journal = {Synthese}, year = {2010},
  year_suffix = {a}}

@article{f2, author = {Menary, Richard}, title = {Cognitive integration!},
  journal = {Mind}, year = {2010}, year_suffix = {b}}"""
        assert self._resolved("Menary (2010a) argues.", shared_fkey) == ["f1", "f2"]

    def test_unmatched_letter_disables_dropping_for_the_whole_group(self):
        # The `not unmatched_letters` guard on the drop branch, which no test
        # reached before: "2010a" DOES discriminate here,
        # so supported is non-empty and the branch would otherwise fire. The
        # unresolvable "2010c" names a work we cannot identify, so we do not
        # know which member it was meant to support -- keep the group whole.
        assert sorted(self._cited(
            "Menary (2010a) argues X. Menary (2010c) argues Y.")) == \
            ["menary2010cognitive", "menary2010extended"]

    def test_continuation_alone_never_licenses_a_drop(self, capsys):
        # A continuation instance used to set
        # first_pos_seen, which moved its group out of keep-all and INTO the
        # drop branch -- so adding support to a group that had none removed
        # that group's protection. Here "Smith 2020" is a real citation and
        # ", 1995" is parsed as its continuation; the fabricated 1995 instance
        # matches only the solo entry and used to drop the two-author one.
        bib = """@article{smithsolo1995, author = {Smith, Alice},
  title = {Solo Work}, journal = {Synthese}, year = {1995}}

@article{smithduo1995, author = {Smith, Alice and Jones, Bob},
  title = {Duo Work}, journal = {Mind}, year = {1995}}"""
        assert sorted(self._cited(
            "Following Smith 2020, 1995 was a watershed year for the field.",
            bib)) == ["smithduo1995", "smithsolo1995"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err

    def test_continuation_support_alone_never_licenses_a_drop(self, capsys):
        # The defect, and the coverage hole that let it ship: the
        # first fix for the case above stopped a continuation setting
        # first_pos_seen but left it writing `supported`, and flipping THAT
        # from empty to non-empty reached the same drop branch. Every existing
        # test passed with the defect in place.
        #
        # Three individually ordinary forms, no letters anywhere:
        #   "Smith and Wu (2006, 2010)" -- a compact multi-year cite (the shape
        #     8 of 32 delivered reviews use); its ", 2010" tail is the ONLY
        #     thing that puts smithWu2010 into `supported`
        #   "Smith et al. (2010)"       -- a loose et al. for a two-author work;
        #     sets first_pos_seen, resolves to nobody (et al. needs n >= 3)
        #   "Following Clark, Smith (2010)" -- rejected by the non-initial guard
        # Together they used to delete smith2010solo from References while the
        # prose still cited it, with lint_md exiting 0 and no letter to sight.
        bib = """@article{smithWu2010, author = {Smith, Alice and Wu, Li},
  title = {The Joint Account}, journal = {Mind}, year = {2010}}

@article{smith2010solo, author = {Smith, Alice}, title = {The Solo Line},
  journal = {Synthese}, year = {2010}}"""
        prose = ("Smith and Wu (2006, 2010) develop the joint account.\n\n"
                 "Smith et al. (2010) report the survey results.\n\n"
                 "Following Clark, Smith (2010) argues for the solo line.\n")
        assert sorted(self._cited(prose, bib)) == \
            ["smith2010solo", "smithWu2010"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err

    def test_a_continuation_routes_its_group_to_keep_all_not_to_the_second_position_drop(
            self, capsys):
        # The opposite half of the same defect, and a cited-work loss the fix
        # for the case above INTRODUCED: withholding first_pos_seen from a
        # continuation also withheld the group's protection against the
        # SECOND-POSITION branch, which drops every member.
        #
        # "Muldoon (2019, 2023) argues" is an explicit citation of a Muldoon
        # 2023 work -- the resolver even prints that its 2023 tail matches both
        # candidates -- and both were then deleted on the strength of "Bloggs
        # and Muldoon (2023)" being the only instance that reached the flags.
        # first_pos_seen is protective, so a continuation must set it.
        bib = """@article{muldoonA2023, author = {Muldoon, Ryan},
  title = {Diversity One}, journal = {Mind}, year = {2023}}

@article{muldoonB2023, author = {Muldoon, Ryan}, title = {Diversity Two},
  journal = {Nous}, year = {2023}}

@article{bloggs2023, author = {Bloggs, Joe and Muldoon, Ryan},
  title = {Joint Work}, journal = {Ethics}, year = {2023}}"""
        assert sorted(self._cited(
            "Bloggs and Muldoon (2023) note this. Muldoon (2019, 2023) argues"
            " for diversity.", bib)) == \
            ["bloggs2023", "muldoonA2023", "muldoonB2023"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err

    def test_a_non_continuation_instance_still_licenses_the_drop(self, capsys):
        # The equal and opposite failure the two tests above must not cause:
        # over-protection that makes the drop unreachable turns the letter
        # filter into plain collision resolution. A plain first-position cite
        # still discriminates, and the
        # compact continuation form still narrows a three-work group to two.
        assert self._cited("As Menary (2010a) argues, integration matters.") \
            == ["menary2010cognitive"]
        assert "[COLLISION] dropped menary2010extended" in \
            capsys.readouterr().err

    def test_form_mismatch_warning_does_not_claim_the_letter_is_unknown(self, capsys):
        # The filter also fires when the citation's author
        # FORM matched no member, so cands was empty before the letter was ever
        # consulted. Keeping the conservative keep-all is right; the old
        # message was not -- it said 2010b "matches no entry" when 2010b names
        # menary2010duo exactly, and that misdiagnosis lands on the stderr
        # channel a live-run operator reads.
        forms = """@article{menary2010solo, author = {Menary, Richard},
  title = {Solo}, journal = {Synthese}, year = {2010}, year_suffix = {a}}

@article{menary2010duo, author = {Menary, Richard and Clark, Andy},
  title = {Duo}, journal = {Mind}, year = {2010}, year_suffix = {b}}"""
        assert sorted(self._cited(
            "Menary (2010a) argues X. Menary and Zhao (2010b) argue Y.",
            forms)) == ["menary2010duo", "menary2010solo"]
        err = capsys.readouterr().err
        assert "2010b" in err
        assert "2010b matches no entry" not in err
        assert "author form" in err

    def test_a_co_authored_sibling_disables_the_filter_for_the_whole_group(
            self, capsys):
        # The one partially-lettered shape actually observed in the corpus, and
        # a STRUCTURAL one: the barrier's assigner groups on the full
        # author-list signature, this resolver on first-author surname
        # variants. A same-author co-authored sibling is therefore its own
        # one-work signature group, gets no letter, and lands in this collision
        # group anyway -- so all(letters) is False and the letter filter is off
        # for all three. Keep-all is the right outcome; it was untested and
        # unnamed. (Shape taken from political-polarization's Mason 2018 group,
        # the single mixed group across the 41 delivered reviews.)
        mason = """@book{mason2018uncivil, author = {Mason, Lilliana},
  title = {Uncivil Agreement}, publisher = {Chicago}, year = {2018},
  year_suffix = {b}}

@article{mason2018ideologues, author = {Mason, Lilliana},
  title = {Ideologues without Issues}, journal = {POQ}, year = {2018},
  year_suffix = {a}}

@article{mason2018tribe, author = {Mason, Lilliana and Wronski, Julie},
  title = {One Tribe to Bind Them All}, journal = {Political Psychology},
  year = {2018}}"""
        # The F-specific claim: the prose cites "2018a", but because the group
        # is not fully lettered the letter must NOT select mason2018ideologues
        # and drop the "b" work. Without the guard it does.
        #
        # mason2018tribe IS dropped here, by surname collision and not by
        # letter: the
        # citation's form is solo and that entry has two authors. The cost this
        # test pins is the other direction -- the unlettered co-authored
        # sibling keeps mason2018uncivil in the References even though the
        # prose named only 2018a. Over-retention is the side the cardinal rule
        # puts us on.
        assert sorted(self._cited("Mason (2018a) argues X.", mason)) == \
            ["mason2018ideologues", "mason2018uncivil"]
        assert "[COLLISION] dropped mason2018uncivil" not in \
            capsys.readouterr().err

    def test_malformed_suffix_field_is_ignored(self):
        # A junk year_suffix reads as absent (same rule _display_year uses),
        # so the group is not fully lettered and nothing is dropped.
        junk = """@book{j1, author = {Menary, Richard}, title = {One},
  publisher = {MIT Press}, year = {2010}, year_suffix = {ab}}

@book{j2, author = {Menary, Richard}, title = {Two},
  publisher = {MIT Press}, year = {2010}, year_suffix = {b}}"""
        assert sorted(self._cited("Menary (2010b) argues.", junk)) == ["j1", "j2"]

    def test_ambiguous_group_warns(self, capsys):
        # The plan promises keep-all-AND-WARN; assert the warning, not just
        # the kept entries.
        self._cited("Menary (2010) argues.")
        assert "[COLLISION] ambiguous" in capsys.readouterr().err

    def test_unmatched_suffix_warns(self, capsys):
        self._cited("Menary (2010c) argues.")
        err = capsys.readouterr().err
        assert "[COLLISION]" in err
        # The message must name the real cause. The pre-existing ambiguous
        # message says "no parseable citation form discriminates", which is
        # FALSE here: the form parsed fine, the letter matched no member.
        assert "2010c" in err
        # That check alone does NOT discriminate: the key 'menary2010cognitive'
        # contains "2010c" by accident, so the assertion above passes even on
        # the OLD generic message. Pin the wording swap itself.
        assert "no parseable citation form" not in err
        assert "letter" in err


# The eight prose forms that carry a GENUINE "2010b" citation past
# _citation_instances. Each defeats a different part of
# the parser, which is why widening _CONTINUATION_RE's separator class closes
# rows 2-4 and nothing else: rows 1, 5, 6, 7 and 8 have no continuation to
# parse at all. _sighted_letters closes all eight because it parses no
# citation -- it scans raw text for a year carrying a letter.
#
# Before the fix every row returned only ['menary2010cognitive'], deleting a
# cited work from References; lint could not see five of them, because both of
# its extractors require a surname token immediately before the year.
LETTER_SLIPS_PAST_THE_PARSER = [
    ("bare_letter_continuation", "Menary (2010a, b) argue."),
    ("and_separator", "Menary (2010a and 2010b) argue."),
    ("ampersand_separator", "Menary (2010a & 2010b) argue."),
    ("hyphen_bare_letter", "Menary (2010a-b) argue."),
    ("uppercase_letter",
     "Menary (2010a) argues X. Menary (2010B) argues Y."),
    ("rejected_by_non_initial_guard",
     "Menary (2010a) argues X. See Clark, Menary (2010b), and Sutton on this."),
    ("second_position",
     "Menary (2010a) argues X. Compare Rowlands and Menary (2010b)."),
    ("no_surname_at_all",
     "Menary (2010a) argues X. The 2010b volume collects the replies."),
]


class TestLetterSighting:
    """The letters' keep-all safety net: a member whose rendered label the
    prose mentions is never dropped, however that mention was written."""

    def _cited(self, prose, bib_text=MENARY_BIB):
        from pybtex.database import parse_string
        db = parse_string(bib_text, "bibtex")
        return sorted(k for k, _ in
                      generate_bibliography.find_cited_entries(prose, db))

    @pytest.mark.parametrize(
        "prose", [p for _, p in LETTER_SLIPS_PAST_THE_PARSER],
        ids=[i for i, _ in LETTER_SLIPS_PAST_THE_PARSER])
    def test_cited_letter_the_parser_missed_still_keeps_the_work(self, prose):
        assert self._cited(prose) == ["menary2010cognitive",
                                      "menary2010extended"]

    def test_an_unsighted_letter_is_still_dropped(self, capsys):
        # The payoff case must survive the safety net. Prose cites 2010a only
        # and never mentions 2010b anywhere, so menary2010extended stays
        # droppable -- otherwise the letter filter does exactly what plain
        # collision resolution already did. (This is why the rule is
        # per-member: requiring EVERY member's letter to be sighted before
        # the group may drop anything would
        # license no drop here at all.)
        assert self._cited("As Menary (2010a) argues, integration matters.") \
            == ["menary2010cognitive"]
        assert "[COLLISION] dropped menary2010extended" in capsys.readouterr().err

    def test_second_position_drop_spares_a_sighted_letter(self, capsys):
        # The other branch that drops, and it drops EVERY member. m2's label
        # appears in the prose, so it must survive; m1's does not.
        bib = """
        @article{m1, author = {Muldoon, Ryan}, title = {T1}, year = {2023},
          journal = {J}, year_suffix = {a}}
        @article{m2, author = {Muldoon, Ryan and A, B}, title = {T2},
          year = {2023}, journal = {J}, year_suffix = {b}}
        @article{bloggs, author = {Bloggs, Joe and Muldoon, Ryan}, title = {T3},
          year = {2023}, journal = {J}}
        """
        cited = self._cited(
            "Bloggs and Muldoon (2023) note this. The 2023b paper is the"
            " one at issue.", bib)
        assert "m2" in cited and "m1" not in cited

    def test_uppercase_is_folded_to_the_bib_letter(self):
        # _entry_suffix lowercases, so the map must too, or "2010B" protects
        # nothing.
        assert generate_bibliography._sighted_letters(
            "Menary (2010B) argues.") == {"2010": {"b"}}

    def test_bare_letter_chain_is_collected(self):
        assert generate_bibliography._sighted_letters(
            "Menary (2010a, b) and Wiens (2015a-c) argue.") == \
            {"2010": {"a", "b"}, "2015": {"a", "c"}}

    def test_chain_does_not_cross_a_closing_paren_or_a_full_stop(self):
        # Load-bearing: ")" and "." are excluded from the separator class. A
        # citation that closes a sentence whose successor opens with an
        # initial -- "(2010a). B. Smith replies" -- would otherwise sight "b",
        # permanently protect menary2010extended, and switch the filter off
        # without any test noticing. (A following multi-letter word is
        # harmless either way: \b after the letter rejects it.)
        prose = "Menary (2010a). B. Smith replies at length."
        assert generate_bibliography._sighted_letters(prose) == {"2010": {"a"}}
        assert self._cited(prose) == ["menary2010cognitive"]

    def test_decade_token_sights_the_letter_s(self):
        # Documented, not a defect: "the 2010s" reads as year 2010, letter
        # "s". A group needs 19 members before any letter "s" is assigned, so
        # this one really is inert.
        assert generate_bibliography._sighted_letters(
            "Debates in the 2010s shifted.") == {"2010": {"s"}}

    def test_a_decade_chain_can_sight_the_letter_a_and_disable_the_drop(self):
        # ACCEPTED COST, pinned so the docstring's claim stays honest. The
        # 19-members argument above covers "s" and does NOT transfer to "a" --
        # "a" is what the first member of EVERY lettered group carries, so a
        # decade token followed by the article "a" switches F's drop off for
        # that year. Measured across the 41 delivered reviews: 0 of 11 decade
        # tokens chain this way, but the rate is not bounded by that.
        assert generate_bibliography._sighted_letters(
            "Debates in the 2010s, a decade of ferment, matured.") == \
            {"2010": {"a", "s"}}
        # ... and the consequence, end to end: the same prose that drops
        # menary2010cognitive on its own stops dropping it.
        assert self._cited("As Menary (2010b) argues, X.") == \
            ["menary2010extended"]
        assert self._cited(
            "Debates in the 2010s, a decade of ferment, matured."
            " As Menary (2010b) argues, X.") == \
            ["menary2010cognitive", "menary2010extended"]
        # The "." guard is what keeps it from being worse.
        assert self._cited(
            "The 2010s. A decade of ferment. As Menary (2010b) argues, X.") \
            == ["menary2010extended"]

    def test_an_unparenthesised_chain_still_crosses_into_an_initial(self):
        # The ")"/"." exclusion closes the PARENTHESISED form only; the
        # docstring should not be read as closing the case. Pinned as a known,
        # protecting-side limit rather than fixed.
        assert generate_bibliography._sighted_letters(
            "Menary 2010a and B. Smith replies at length.") == \
            {"2010": {"a", "b"}}

    def test_another_authors_letter_protects_across_groups(self):
        # DOCUMENTED EXPOSURE, pinned so it is not rediscovered as a defect.
        # The map is keyed by year alone, so Menary's sighted "2010b" protects
        # Clark's 2010b as well, even though the prose never cites it. Every
        # lettered group contains an "a" and a "b", so once F ships this is the
        # default whenever two lettered groups share a year -- the corpus
        # measurement in _sighted_letters' docstring is a pre-F lower bound,
        # not a bound on the rate. Kept anyway: the failure is a retained
        # reference announced on stderr, and surname-keying the map would
        # defeat the rows the safety net exists for.
        two_groups = """@book{menary2010a, author = {Menary, Richard},
  title = {Alpha}, publisher = {MIT}, year = {2010}, year_suffix = {a}}

@book{menary2010b, author = {Menary, Richard}, title = {Beta},
  publisher = {MIT}, year = {2010}, year_suffix = {b}}

@book{clark2010a, author = {Clark, Andy}, title = {Gamma},
  publisher = {MIT}, year = {2010}, year_suffix = {a}}

@book{clark2010b, author = {Clark, Andy}, title = {Delta},
  publisher = {MIT}, year = {2010}, year_suffix = {b}}"""
        cited = self._cited(
            "Menary (2010a) argues X, and Menary (2010b) argues Y."
            " Clark (2010a) disagrees.", two_groups)
        assert "clark2010b" in cited

    def test_a_stale_references_section_does_not_sight_its_own_letters(self):
        # Fix re-review IMPORTANT A. main() used to match over the WHOLE file,
        # and the reference list it had already written renders every kept
        # entry as "Menary, Richard. 2010b." -- a year carrying a letter, which
        # _sighted_letters reads as a genuine mention. So the drop worked once
        # and never again.
        stale = ("As Menary (2010a) argues, integration matters.\n\n"
                 "## References\n\n"
                 "Menary, Richard. 2010a. \"Cognitive Integration.\"\n\n"
                 "Menary, Richard. 2010b. *The Extended Mind*.\n")
        assert self._cited(stale) == ["menary2010cognitive"]

    def test_the_renderer_converges_across_the_operator_fix_cycle(self):
        # SKILL.md Phase 6 step 5 tells the operator to re-run step 4 after a
        # lint failure, so the second run is the NORMAL path, not an edge case
        # -- and the cycle that matters is the one where run 1 could NOT
        # discriminate, because only then does its reference list carry the
        # letter that run 2 must not sight.
        #
        # Run the real chain each time: resolve -> render -> splice.
        #   run 1  bare "Menary (2010)"  -> ambiguous keep-all, BOTH rendered
        #   run 2  operator disambiguates the body to "2010a" and re-runs
        #          step 4 over the file, stale ## References and all
        # Without the strip, run 2's own "2010b." reference line sights "b",
        # menary2010extended is protected for ever, and the phantom the
        # operator was fixing can never be removed.
        from pybtex.database import parse_string
        db = parse_string(MENARY_BIB, "bibtex")

        def cycle(text):
            cited = generate_bibliography.find_cited_entries(text, db)
            refs = generate_bibliography.generate_references(cited)
            return (sorted(k for k, _ in cited),
                    generate_bibliography.apply_references(text, refs))

        keys1, doc1 = cycle("As Menary (2010) argues, integration matters.\n")
        assert keys1 == ["menary2010cognitive", "menary2010extended"]
        assert "2010b" in doc1

        edited = doc1.replace("Menary (2010) argues", "Menary (2010a) argues")
        keys2, doc2 = cycle(edited)
        assert keys2 == ["menary2010cognitive"]
        assert "2010b" not in doc2

        # ... and it stays converged: a third run changes nothing.
        keys3, doc3 = cycle(doc2)
        assert keys3 == keys2 and doc3 == doc2

    def test_a_work_named_only_in_a_stale_reference_list_is_not_re_matched(self):
        # The same error one stage earlier: _collect_matches used to count
        # reference lines as surname/year windows, so an entry the prose no
        # longer names re-matched itself off its own stale reference line for
        # ever. Dropping it is what this script is for.
        bare = """@article{clark1998, author = {Clark, Andy}, title = {T1},
  journal = {Analysis}, year = {1998}}

@article{menary2013, author = {Menary, Richard}, title = {T2},
  journal = {Mind}, year = {2013}}"""
        stale = ("Menary (2013) argues X.\n\n"
                 "## References\n\n"
                 "Clark, Andy. 1998. \"T1.\" *Analysis*.\n")
        assert self._cited(stale, bare) == ["menary2013"]

    def test_unlettered_bib_is_untouched(self):
        # Collision behaviour must not change on a bib with no letters: an
        # entry with no letter can never be protected by a sighting.
        bare = """@article{m1, author = {Muldoon, Ryan and Wu, Jin},
  title = {T1}, year = {2023}, journal = {J}}

@article{m2, author = {Muldoon, Ryan and Gordon, Ann and Wu, Jin},
  title = {T2}, year = {2023}, journal = {J}}"""
        assert self._cited("As Muldoon and Wu (2023) argue, X.", bare) == ["m1"]

    def test_a_continuation_is_not_a_second_position_sighting(self, capsys):
        # Fix re-review IMPORTANT D, and the guard it found untested (its
        # MUT-12 left all tests green). "Bloggs and Muldoon (2019, 2023)"
        # continues into 2023 carrying Bloggs' surname, so without the
        # `not inst["continuation"]` guard on second_pos_seen the resolver
        # reads it as positive evidence against the Muldoon 2023 group and
        # drops BOTH members.
        #
        # Keep-all is also what pre-F (13860fb) does here -- it parses no
        # continuation at all, so the 2023 group sees no instance and falls to
        # the final keep-all. Collision behaviour on an unlettered bib is
        # therefore genuinely unchanged, which is the claim
        # _letter_is_sighted's docstring makes; the reason is this guard, not
        # the letter gate.
        bib = """@article{muldoonA2023, author = {Muldoon, Ryan and Wu, Li},
  title = {T1}, journal = {J}, year = {2023}}

@article{muldoonB2023, author = {Muldoon, Ryan and Qi, Fan},
  title = {T2}, journal = {J}, year = {2023}}

@article{bloggs2023, author = {Bloggs, Joe and Muldoon, Ryan},
  title = {T3}, journal = {J}, year = {2023}}"""
        assert self._cited("Bloggs and Muldoon (2019, 2023) argue.", bib) == \
            ["bloggs2023", "muldoonA2023", "muldoonB2023"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err


# Two-author and three-author Muldoon 2023 works with no letters -- the
# own canonical drop fixtures, reused below as the negative controls that keep
# the bare-mention net from swallowing E.
MULDOON_BARE = """@article{m1, author = {Muldoon, Ryan and Wu, Li},
  title = {T1}, journal = {J}, year = {2023}}

@article{m2, author = {Muldoon, Ryan and Qi, Fan},
  title = {T2}, journal = {J}, year = {2023}}

@article{bloggs2023, author = {Bloggs, Joe and Muldoon, Ryan},
  title = {T3}, journal = {J}, year = {2023}}"""


class TestUnresolvableBareMention:
    """A letterless citation the parser REJECTED still names its group, so it
    disables dropping for that group."""

    def _cited(self, prose, bib_text=MENARY_BIB):
        from pybtex.database import parse_string
        db = parse_string(bib_text, "bibtex")
        return sorted(k for k, _ in
                      generate_bibliography.find_cited_entries(prose, db))

    def test_a_rejected_bare_cite_keeps_the_group_whole(self, capsys):
        # The documented residual, and a real Issue B path: the first cite
        # licenses the drop, the second is rejected by
        # _NON_INITIAL_PRECEDING_RE so it yields no instance, and it carries no
        # letter for _sighted_letters to see. lint_md then resolves the
        # surviving "Menary (2010)" against the "2010a." reference line and
        # exits 0 -- the reader is pointed at the wrong work, silently.
        assert self._cited(
            "Menary (2010a) argues X. See Clark, Menary (2010), and Sutton"
            " on this.") == ["menary2010cognitive", "menary2010extended"]
        err = capsys.readouterr().err
        assert "[COLLISION] dropped" not in err
        # The warning must name the cause, not print the generic sentence.
        assert "Menary 2010" in err and "cannot resolve" in err

    def test_the_ampersand_form_is_covered_too(self):
        # Same rejection rule, different prose: "Clark & Menary (2010)" makes
        # _CITE_INSTANCE_RE bind at the SECOND name, which the guard rejects.
        assert self._cited(
            "Menary (2010a) argues X. Compare Clark & Menary (2010) on"
            " scaffolding.") == ["menary2010cognitive", "menary2010extended"]

    def test_a_rejected_cite_that_carries_a_letter_is_left_to_the_sighting_map(self):
        # Scoping decision 1: the letter identifies ONE member, so the sighting
        # map protects that member and the rest of the group stays droppable.
        # Widening this net to lettered rejections would make every rejected
        # cite keep-all and lose that precision.
        assert generate_bibliography._unresolvable_mentions(
            "See Clark, Menary (2010b), and Sutton.") == []
        assert self._cited(
            "Menary (2010b) argues X. See Clark, Menary (2010b), and Sutton.") \
            == ["menary2010extended"]

    def test_a_bare_mention_of_a_different_author_does_not_protect(self):
        # Scoping decision 2, the half that keeps this affordable: the net is
        # keyed to the surname the REJECTED match captured, so an unrelated
        # rejected cite in the same year protects nothing.
        assert self._cited(
            "Menary (2010a) argues X. See Sutton, Clark (2010), and Rowlands.") \
            == ["menary2010cognitive"]

    def test_item_3_e_first_position_drop_still_fires(self, capsys):
        # NEGATIVE CONTROL. The rejected alternative -- "a bare year within
        # _MATCH_WINDOW of a member surname" -- kills this: "Muldoon and Wu
        # (2023)" puts a bare 2023 next to Muldoon, so the group would be
        # protected by the very citation that discriminates it. Measured, that
        # rule retained 15 extra references across 13 of the 41 delivered
        # reviews and broke both of E's drop branches.
        assert self._cited("Muldoon and Wu (2023) argue X.", MULDOON_BARE) == \
            ["m1"]
        assert "[COLLISION] dropped m2" in capsys.readouterr().err

    def test_item_3_e_second_position_drop_still_fires(self, capsys):
        # NEGATIVE CONTROL, the other branch: "Bloggs and Muldoon (2023)" is
        # also a bare year beside a member surname.
        assert self._cited("Bloggs and Muldoon (2023) note this.",
                           MULDOON_BARE) == ["bloggs2023"]
        assert "[COLLISION] dropped" in capsys.readouterr().err

    def test_the_payoff_drop_still_fires(self):
        # NEGATIVE CONTROL for the letter filter itself.
        assert self._cited("As Menary (2010a) argues, integration matters.") \
            == ["menary2010cognitive"]

    def test_a_rendered_reference_list_manufactures_no_bare_mention(self):
        # GUARD, not a detector: it fails no mutation of today's code, and it
        # is here because the composition it pins is not obvious.
        #
        # A rendered line like "Clark, Andy. 1998." is an unlettered surname
        # beside a bare year. If it produced a mention, every group would be
        # protected from the second run onwards and F's drop would be one-shot
        # again by a route the References strip's own tests do not cover (they
        # use a lettered bib, whose reference lines the letterless-only
        # conjunct filters out anyway).
        #
        # It does not, for a second and independent reason: the "." that closes
        # every rendered author list blocks _CITE_INSTANCE_RE, which needs
        # `[\s,]*\(?\s*` between the name and the year. So a References section
        # yields no instances AND no mentions -- only _sighted_letters can see
        # it, which is exactly the surface the strip was added for. If a future
        # renderer change (or a widened separator class) breaks that, this test
        # is where it surfaces.
        rendered = ('## References\n\n'
                    'Clark, Andy. 1998. "Solo Piece." *Analysis*.\n\n'
                    'Clark, Andy, and David Chalmers. 1998. "The Extended'
                    ' Mind." *Analysis*.\n\n'
                    'Gilabert, Pablo, and Holly Lawford-Smith. 2012.'
                    ' "Global Justice." *Ethics*.\n')
        assert generate_bibliography._unresolvable_mentions(rendered) == []
        assert generate_bibliography._citation_instances(rendered) == []

    def test_an_accepted_bare_cite_is_not_a_mention(self):
        # A bare cite the parser ACCEPTS is handled by the instance machinery
        # (it supports every member), so it must not also appear here -- that
        # is what keeps the two halves of _parser_verdicts disjoint.
        assert generate_bibliography._unresolvable_mentions(
            "Menary (2010) argues.") == []


# =============================================================================
# The mention a rejected citation makes belongs to the
# list's FIRST author, not to the name the parser happened to bind at
# =============================================================================

MULDOON_C2_BIB = """@article{muldoonSolo2023, author = {Muldoon, Ryan},
  title = {Solo Account}, journal = {Mind}, year = {2023}}

@article{muldoonWu2023, author = {Muldoon, Ryan and Wu, Jin},
  title = {Joint Account}, journal = {Synthese}, year = {2023}}"""

MULDOON_TRIO_BIB = """@article{muldoonSolo2023, author = {Muldoon, Ryan},
  title = {Solo Account}, journal = {Mind}, year = {2023}}

@article{muldoonTrio2023, author = {Muldoon, Ryan and Wu, Jin and Li, Mei},
  title = {Trio Account}, journal = {Synthese}, year = {2023}}"""


class TestRejectedListRecoversItsFirstAuthor:
    """_NON_INITIAL_PRECEDING_RE rejects a match precisely BECAUSE it bound at
    a non-initial name, so the surname it captured is never the first author -
    and collision groups are keyed by first author. The bare-mention net was
    therefore filed under the wrong group and the sibling citation dropped the
    cited work anyway.

    Both fixtures need the accepted sibling: without a citation that licenses
    a drop, nothing is dropped and the test would prove nothing."""

    def _cited(self, prose, bib_text):
        from pybtex.database import parse_string
        db = parse_string(bib_text, "bibtex")
        return sorted(k for k, _ in
                      generate_bibliography.find_cited_entries(prose, db))

    def test_an_ampersand_pair_does_not_lose_the_joint_work(self, capsys):
        # The reproduced C2. "Muldoon & Wu (2023)" is parsed from Wu (the
        # two-author form accepts only "and"), rejected for the right reason,
        # and filed under WU while the group is MULDOON. The solo sibling then
        # licensed the drop and the joint work vanished from References while
        # the prose cited it. lint_md does not catch it: its tolerant
        # token+year resolution resolves the citation against the surviving
        # solo reference.
        assert self._cited(
            "Muldoon (2023) presents the solo account.\n"
            "Muldoon & Wu (2023) present the joint account.\n",
            MULDOON_C2_BIB) == ["muldoonSolo2023", "muldoonWu2023"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err

    def test_a_three_author_list_does_not_lose_the_joint_work(self, capsys):
        # The same defect where NO ampersand is involved, which is what makes
        # "parse & as and" the wrong fix: here the parser binds at the MIDDLE
        # author, so the rejection is by the bare-comma half of the guard and
        # the recovered name comes from a different branch of it.
        assert self._cited(
            "Muldoon (2023) presents the solo account.\n"
            "Muldoon, Wu, and Li (2023) present the joint account.\n",
            MULDOON_TRIO_BIB) == ["muldoonSolo2023", "muldoonTrio2023"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err

    def test_the_recovered_names_are_the_whole_list_first_author_first(self):
        got = generate_bibliography._unresolvable_mentions(
            "Muldoon, Wu, and Li (2023) present the joint account.")
        assert [m["surname"] for m in got] == ["Muldoon", "Wu", "Li"]
        assert {m["year"] for m in got} == {"2023"}

    def test_a_sentence_lead_in_does_not_become_an_author(self):
        # The walk-back reuses the guard's own lead-in exclusion, so the
        # transition word opening the sentence is not peeled as a list member.
        assert [m["surname"] for m in generate_bibliography._unresolvable_mentions(
            "However, Muldoon, Wu, and Li (2023) present the joint account.")] \
            == ["Muldoon", "Wu", "Li"]

    def test_recovery_does_not_reach_a_group_the_list_never_names(self):
        # NEGATIVE CONTROL. Widening the net to the whole rejected span must
        # not widen it past the span: an unrelated rejected cite in the same
        # year still protects nothing, so the collision drop is intact.
        assert self._cited(
            "Menary (2010a) argues X. See Sutton, Clark (2010), and Rowlands.",
            MENARY_BIB) == ["menary2010cognitive"]


# =============================================================================
# A REJECTED multi-year citation protects its tail years too
# =============================================================================

MENARY_2011_BIB = """@article{menary2011a, author = {Menary, Richard},
  title = {T1}, journal = {Mind}, year = {2011}, year_suffix = {a}}

@book{menary2011b, author = {Menary, Richard}, title = {T2},
  publisher = {MIT}, year = {2011}, year_suffix = {b}}"""


class TestRejectedMultiYearCitation:
    """The continuation walker used to sit inside _citation_instances' ACCEPTED
    branch, below its `if rejected: continue`, and _unresolvable_mentions
    recorded only the head year. So a rejected citation with a multi-year tail
    protected its head and silently lost every tail year."""

    def _cited(self, prose, bib_text=MENARY_2011_BIB):
        from pybtex.database import parse_string
        db = parse_string(bib_text, "bibtex")
        return sorted(k for k, _ in
                      generate_bibliography.find_cited_entries(prose, db))

    def test_a_tail_year_keeps_its_group_whole(self, capsys):
        # The reproduced defect. The accepted sibling is what licenses the
        # drop; without it nothing is dropped and the test proves nothing.
        # lint_md reports nothing here either: "(2010, 2011)" resolves on base
        # year against the surviving "2011a." reference line.
        assert self._cited(
            "Menary (2011a) argues X."
            " See Clark, Menary (2010, 2011), and Sutton on this.") \
            == ["menary2011a", "menary2011b"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err

    def test_every_year_of_a_rejected_span_is_recorded(self):
        got = generate_bibliography._unresolvable_mentions(
            "See Clark, Menary (2010, 2011), and Sutton on this.")
        assert sorted({(m["surname"], m["year"]) for m in got}) == [
            ("Clark", "2010"), ("Clark", "2011"),
            ("Menary", "2010"), ("Menary", "2011")]

    def test_the_letterless_rule_is_per_year_not_per_citation(self, capsys):
        # "(2011a, 2011)" - the head is _sighted_letters' business (it names
        # ONE member) and the tail is this net's. The old whole-citation test
        # threw both away together, so the letterless tail lost its
        # protection because the HEAD happened to carry a letter.
        got = generate_bibliography._unresolvable_mentions(
            "See Clark, Menary (2011a, 2011), and Sutton on this.")
        assert {(m["surname"], m["year"]) for m in got} == {
            ("Clark", "2011"), ("Menary", "2011")}
        assert self._cited(
            "Menary (2011a) argues X."
            " See Clark, Menary (2011a, 2011), and Sutton on this.") \
            == ["menary2011a", "menary2011b"]
        assert "[COLLISION] dropped" not in capsys.readouterr().err

    def test_one_walker_serves_the_accepted_half_too(self):
        # The fix is a SHARED walker, not a second copy of the loop: mutate
        # _continuation_years and the accepted half must change with it.
        # ("Menary (2006, 2011)" is the accepted shape 8 of 32 delivered
        # reviews use.)
        insts = generate_bibliography._citation_instances(
            "Menary (2006, 2011) argues X.")
        assert [(i["year"], i["continuation"]) for i in insts] == [
            ("2006", False), ("2011", True)]
        assert generate_bibliography._continuation_years(", 2011) argues") == [
            ("2011", "")]


class TestRecoveredNamesAreStrippedOfPossessives:
    """The surname character class admits apostrophes, so a captured name
    arrives with its possessive attached; every OTHER captured name in this
    function is stripped, and the recovered ones were not."""

    def test_a_possessive_leading_author_is_still_recovered(self):
        # Ordinary prose: a possessive author list. The parser binds at the
        # middle name and the guard rejects it, so Clark is a RECOVERED name --
        # and it arrived as "Clark's", whose variants intersect no group.
        got = generate_bibliography._unresolvable_mentions(
            "Clark's, Menary's, and Sutton's (2010) accounts differ.")
        assert [m["surname"] for m in got] == ["Clark", "Menary", "Sutton"]


def test_title_key_possessive_folds_to_space():
    """The surname conjunct tokenizes prose via title_key; a curly
    possessive must fold to 'surname s', not 'surnames' -- three fixtures
    below carry the surname ONLY as a possessive (the production shape)."""
    from bib_identity import title_key
    assert title_key("Heersmink’s") == "heersmink s"
    assert title_key("Heersmink's") == "heersmink s"


class TestTitleMentions:
    """Title-only citations a reference list can omit: a quoted/italic
    span equal to a bib title, with the author's surname in the document,
    is a citation-by-title. Measured over the 36 delivered reviews + the
    production pair: with the >=4-word guard the net fires exactly twice,
    both genuine References omissions (production heersmink2016internet;
    corpus rawls1971theory). 0 false fires over 37 documents is a
    rule-of-three upper bound of ~8%/document, not a proof -- the surname
    conjunct exists to push the true rate further down."""

    HEERSMINK_PROSE = (
        'Heersmink’s "The Internet, Cognitive Enhancement, and the '
        'Values of Cognition" (2016) frames the upshot in its title: '
        'verdicts on offloading depend on which values are prioritized.'
    )

    def _heersmink_bib(self):
        return _make_bib(("heersmink2016internet", _make_entry(
            authors=["Heersmink, Richard"], year="2016",
            title="The Internet, Cognitive Enhancement, and the Values of Cognition")))

    def test_quoted_title_mention_fires(self):
        m = generate_bibliography._title_mentions(
            self.HEERSMINK_PROSE, self._heersmink_bib())
        assert "heersmink2016internet" in m

    def test_italicized_book_title_fires(self):
        prose = ("Since John Rawls introduced the distinction between ideal "
                 "and nonideal theory in *A Theory of Justice* (1971), the "
                 "question has stayed contested.")
        bib = _make_bib(("rawls1971theory", _make_entry(
            entry_type="book", authors=["Rawls, John"], year="1971",
            title="A Theory of Justice")))
        assert "rawls1971theory" in generate_bibliography._title_mentions(prose, bib)

    def test_bold_span_fires_like_italic(self):
        """**Bold** captures its inner span between the doubled asterisks;
        a bolded exact >=4-word title with the surname present reads as a
        title mention -- pinned as intended behavior, not an accident."""
        prose = ("Rawls changed the field. **A Theory of Justice** is where "
                 "the ideal/nonideal distinction enters.")
        bib = _make_bib(("rawls1971theory", _make_entry(
            entry_type="book", authors=["Rawls, John"], year="1971",
            title="A Theory of Justice")))
        assert "rawls1971theory" in generate_bibliography._title_mentions(prose, bib)

    def test_period_inside_closing_quote_still_matches(self):
        """Chicago puts terminal punctuation INSIDE the quotes; title_key
        folds punctuation, so the span still matches."""
        prose = ('Heersmink wrote "The Internet, Cognitive Enhancement, '
                 'and the Values of Cognition." It set the agenda.')
        assert "heersmink2016internet" in generate_bibliography._title_mentions(
            prose, self._heersmink_bib())

    def test_short_title_term_of_art_does_not_fire(self):
        """Two-word titles are indistinguishable from italicized terms of
        art ('a failure mode termed *deceptive alignment*') -- measured
        false fire, excluded by the >=4-word guard even though the
        surname is present."""
        prose = ("Hubinger warned early: a failure mode termed "
                 "*deceptive alignment*.")
        bib = _make_bib(("hubinger2019deceptive", _make_entry(
            authors=["Hubinger, Evan"], year="2019", title="Deceptive Alignment")))
        assert generate_bibliography._title_mentions(prose, bib) == {}

    def test_scare_quoted_word_does_not_fire(self):
        prose = 'Floridi asks: yet "data" remains a surprisingly elusive concept.'
        bib = _make_bib(("floridi2014data", _make_entry(
            authors=["Floridi, Luciano"], year="2014", title="Data")))
        assert generate_bibliography._title_mentions(prose, bib) == {}

    def test_unquoted_title_phrase_does_not_fire(self):
        """The title text appearing as plain prose is NOT a citation --
        the unguarded containment design measured 31 firings, mostly
        canonical-term collisions ('a theory of justice' in running text)."""
        prose = ("Rawls held that any a theory of justice must confront "
                 "nonideal conditions in practice today.")
        bib = _make_bib(("rawls1971theory", _make_entry(
            entry_type="book", authors=["Rawls, John"], year="1971",
            title="A Theory of Justice")))
        assert generate_bibliography._title_mentions(prose, bib) == {}

    def test_missing_surname_blocks_fire(self):
        """The surname conjunct: an exact quoted span whose author is
        nowhere in the document does not fire -- precision insurance for
        term-of-art collisions that pass the word guard."""
        prose = ('"The Internet, Cognitive Enhancement, and the Values of '
                 'Cognition" is a phrase someone quoted without attribution.')
        assert generate_bibliography._title_mentions(
            prose, self._heersmink_bib()) == {}

    def test_curly_quotes_and_curly_single_quotes_fire(self):
        prose = ("Heersmink’s “The Internet, Cognitive Enhancement, "
                 "and the Values of Cognition” shaped the debate; some "
                 "cite it as ‘The Internet, Cognitive Enhancement, and "
                 "the Values of Cognition’ informally.")
        assert "heersmink2016internet" in generate_bibliography._title_mentions(
            prose, self._heersmink_bib())

    def test_latex_escaped_title_matches_unicode_prose(self):
        """Bib title carries a LaTeX accent; prose quotes the unicode form.
        clean_bibtex_str decodes before folding, so they meet."""
        prose = ('Dupont’s "Une Théorie de la Justice Sociale '
                 'Moderne" (1990) set the agenda.')
        bib = _make_bib(("x1990", _make_entry(
            authors=["Dupont, Jean"], year="1990",
            title="Une Th{\\'e}orie de la Justice Sociale Moderne")))
        assert "x1990" in generate_bibliography._title_mentions(prose, bib)

    def _rawls_bib(self):
        return _make_bib(("rawls1971theory", _make_entry(
            entry_type="book", authors=["Rawls, John"], year="1971",
            title="A Theory of Justice")))

    def test_short_failed_italic_does_not_leak_closing_delimiter_as_opener(self):
        """`"`/`*` are non-directional: a short span that fails the >=4-word
        (here, {4,300}-char) floor leaves its CLOSING delimiter free to be
        retried as the next match's OPENER, which can capture plain running
        text between two unrelated delimiters. Measured false fire before
        the edge-whitespace guard: this span captured " a theory of
        justice " between the two failed *not*/*however* italics."""
        prose = "Rawls is *not* a theory of justice *however* in the strict sense."
        assert generate_bibliography._title_mentions(prose, self._rawls_bib()) == {}

    def test_short_failed_quote_does_not_leak_closing_delimiter_as_opener(self):
        """Same mis-pairing, straight double quotes: "AI" is too short to
        net, so its closing quote is retried as an opener and can capture
        plain text up to the next quote."""
        prose = 'Rawls called it "AI", a theory of justice, "fails" on its own terms.'
        assert generate_bibliography._title_mentions(prose, self._rawls_bib()) == {}

    def test_leading_bare_asterisk_does_not_leak(self):
        """A leading bare `*` (e.g. a markdown list marker) can pair with a
        later closing delimiter and mis-capture running text."""
        prose = "* Rawls, *ok*, a theory of justice *matters*."
        assert generate_bibliography._title_mentions(prose, self._rawls_bib()) == {}

    def test_word_adjacent_asterisks_do_not_leak(self):
        """Asterisks immediately touching a word (no surrounding space) are
        exactly the CommonMark-illegal shape the edge-whitespace guard is
        built on -- the captured span still carries the whitespace that
        was inside the delimiters, so it is still rejected."""
        prose = "Rawls wrote* a theory of justice *here."
        assert generate_bibliography._title_mentions(prose, self._rawls_bib()) == {}

    def test_intraword_asterisk_mis_pairing_does_not_leak(self):
        """The mis-pairing shape the edge-whitespace guard alone does NOT
        catch: when the failed short span's delimiters abut words on both
        sides (`*not*a theory of justice*however*`), the retried opener
        captures the running text with NO edge whitespace, so every earlier
        guard passes and the entry was falsely ADDED (a phantom reference).
        The word-boundary context guard rejects it: the character before
        the match is `t`, from `not`."""
        prose = ("Rawls is *not*a theory of justice*however* in the "
                 "strict sense.")
        assert generate_bibliography._title_mentions(prose, self._rawls_bib()) == {}

    def test_intraword_quote_mis_pairing_does_not_leak(self):
        """Same shape with straight double quotes: `"AI"` fails the floor,
        its closing quote is retried as an opener, and the captured span
        `a theory of justice` is whitespace-clean because the delimiters
        abut words."""
        prose = ('Rawls called it "AI"a theory of justice"fails" on its '
                 'own terms.')
        assert generate_bibliography._title_mentions(prose, self._rawls_bib()) == {}

    def test_word_boundary_guard_admits_bold_and_parenthesized_forms(self):
        """The word-boundary context guard must not narrow legitimate
        forms: a **bold** span abuts asterisks (not word characters), and a
        parenthesized quoted title abuts `(` and `)`."""
        assert "rawls1971theory" in generate_bibliography._title_mentions(
            "Rawls changed the field. **A Theory of Justice** is the entry "
            "point.", self._rawls_bib())
        prose = ('Heersmink makes the point ("The Internet, Cognitive '
                 'Enhancement, and the Values of Cognition") at length.')
        assert "heersmink2016internet" in generate_bibliography._title_mentions(
            prose, self._heersmink_bib())

    def test_span_equality_rejects_a_superset_title(self):
        """Containment, not just equality, must be rejected: a span that
        CONTAINS the bib title plus more text is not a match. If `tk not
        in folded_spans` were ever loosened to substring containment, this
        would fire; under equality it must not."""
        prose = ("*A Theory of Justice, Revised Edition* changed everything, "
                 "as Rawls knew.")
        assert generate_bibliography._title_mentions(prose, self._rawls_bib()) == {}

    def test_three_word_title_blocked_by_word_guard(self):
        """Pins the >=4-word floor itself: a 3-folded-word title, exactly
        quoted with the surname present, must still not fire."""
        prose = "Clark discussed *the extended mind* at length in that essay."
        bib = _make_bib(("clark1998extended", _make_entry(
            authors=["Clark, Andy"], year="1998", title="The Extended Mind")))
        assert generate_bibliography._title_mentions(prose, bib) == {}

    def test_surname_as_substring_of_longer_word_does_not_satisfy_conjunct(self):
        """The surname conjunct is a whitespace-bounded token match, not
        substring containment: "Rawlsian" must not stand in for "Rawls"."""
        prose = ('The Rawlsian tradition endorses "A Theory of Justice, '
                 'Framed Anew" as its touchstone.')
        bib = _make_bib(("rawls1971framed", _make_entry(
            entry_type="book", authors=["Rawls, John"], year="1971",
            title="A Theory of Justice, Framed Anew")))
        assert generate_bibliography._title_mentions(prose, bib) == {}

    def test_personless_entry_is_skipped(self):
        """An entry with neither an author nor an editor cannot corroborate
        the surname conjunct, so it never fires even on an exact quoted
        span -- precision side, per the function's own docstring."""
        prose = '"A Theory of Justice, Framed Anew" is quoted here in full.'
        bib = _make_bib(("anon1971framed", _make_entry(
            entry_type="book", year="1971",
            title="A Theory of Justice, Framed Anew")))
        assert generate_bibliography._title_mentions(prose, bib) == {}


class TestTitleMentionWiring:
    def test_title_only_citation_reaches_references(self):
        """The production defect end-to-end: surname and year both present
        but pushed apart by the 66-char quoted title (outside the +/-60
        window), no other citation -- the entry must still be found."""
        prose = (
            "## Review\n\nHeersmink’s \"The Internet, Cognitive "
            "Enhancement, and the Values of Cognition\" (2016) frames the "
            "upshot in its title.\n")
        bib = _make_bib(("heersmink2016internet", _make_entry(
            authors=["Heersmink, Richard"], year="2016",
            title="The Internet, Cognitive Enhancement, and the Values of Cognition")))
        cited = find_cited_entries(prose, bib)
        assert [k for k, _ in cited] == ["heersmink2016internet"]

    def test_title_mention_rescues_first_pos_drop(self, capsys):
        """Same first-author+year group, the two-author member
        discriminated by an 'and' instance, the solo member supported only
        by a quoted title mention -- the mention must rescue it from the
        first_pos_supported drop branch (NOT via post-resolution
        inclusion: both members surname-match, so both are IN records and
        the solo one reaches the drop print).

        Test-design note: two solo-author members with a bare solo
        instance would BOTH land in cands (ambiguous keep-all) and the
        test would pass without the rescue. The and-form discrimination
        is what opens the drop branch."""
        prose = (
            "Heersmink and Sutton (2016) argue for extended memory. "
            "Heersmink's \"The Internet, Cognitive Enhancement, and the "
            "Values of Cognition\" (2016) frames the values question.\n")
        bib = _make_bib(
            ("heersminkSutton2016", _make_entry(
                authors=["Heersmink, Richard", "Sutton, John"], year="2016",
                title="Extended Memory Systems and Distributed Cognition Today")),
            ("heersmink2016internet", _make_entry(
                authors=["Heersmink, Richard"], year="2016",
                title="The Internet, Cognitive Enhancement, and the Values of Cognition")))
        cited = {k for k, _ in find_cited_entries(prose, bib)}
        assert "heersmink2016internet" in cited
        assert "heersminkSutton2016" in cited
        assert "[TITLE] kept" in capsys.readouterr().err

    def test_title_mention_rescues_second_pos_drop(self, capsys):
        """The second_pos_seen branch drops EVERY member of a group no
        first-position instance names; a title mention must rescue there
        too. Construction notes, all load-bearing: the Muldoon group needs
        TWO members (a singleton group is kept unconditionally and never
        reaches any drop branch); the only parse of 'Muldoon' is second
        position in a corroborated 'and' instance (bloggsMuldoon2023's own
        author list explains it), so the group reaches second_pos_seen;
        one member's title is quoted. The rescue (not the inclusion loop)
        must fire: assert the '[TITLE] kept' report, because the inclusion
        loop would re-add the entry anyway but print '[TITLE] added' after
        a misleading 'dropped' line."""
        prose = (
            "Bloggs and Muldoon (2023) argue the point, drawing on "
            "\"The Grand Theory of Collective Agency Formation\" (2023) "
            "throughout.\n")
        bib = _make_bib(
            ("bloggsMuldoon2023", _make_entry(
                authors=["Bloggs, Joe", "Muldoon, Ryan"], year="2023",
                title="Joint Work on Collective Agency and Institutions")),
            ("muldoonSolo2023", _make_entry(
                authors=["Muldoon, Ryan"], year="2023",
                title="The Grand Theory of Collective Agency Formation")),
            ("muldoonOther2023", _make_entry(
                authors=["Muldoon, Ryan"], year="2023",
                title="A Different Muldoon Work on Something Else Entirely")))
        cited = {k for k, _ in find_cited_entries(prose, bib)}
        assert "muldoonSolo2023" in cited
        assert "muldoonOther2023" not in cited  # legitimately dropped
        assert "bloggsMuldoon2023" in cited
        err = capsys.readouterr().err
        assert "[TITLE] kept" in err
        assert "[TITLE] added muldoonSolo2023" not in err

    def test_added_title_mention_flows_through_dedup(self, capsys):
        """Two duplicate copies (same DOI) cited ONLY by title: both are
        appended by the inclusion path (no author-year instance exists)
        and must merge in the existing dedup loop, not appear twice."""
        prose = ("Rawls looms over everything here. *A Theory of Justice* "
                 "remains the touchstone for the whole debate.\n")
        bib = _make_bib(
            ("rawls1971a", _make_entry(
                entry_type="book", authors=["Rawls, John"], year="1971",
                title="A Theory of Justice", doi="10.4159/9780674042605")),
            ("rawls1971b", _make_entry(
                entry_type="book", authors=["Rawls, John"], year="1971",
                title="A Theory of Justice", doi="10.4159/9780674042605")))
        cited = [k for k, _ in find_cited_entries(prose, bib)]
        assert len(cited) == 1
        assert "[TITLE] added" in capsys.readouterr().err

    def test_same_title_distinct_dois_both_added(self):
        """Two entries with the SAME >=4-word title but DIFFERENT DOIs
        (e.g. a paper and its book chapter reprint) both reach References
        on a title-only citation -- pinned as consistent with the dedup
        layer's DOI-set rule (never merge groups whose non-empty DOI sets
        differ). The operator sees two [TITLE] added lines."""
        prose = ("Rawls looms over everything here. *A Theory of Justice "
                 "and Its Critics* remains the touchstone.\n")
        bib = _make_bib(
            ("copyA", _make_entry(
                entry_type="book", authors=["Rawls, John"], year="1971",
                title="A Theory of Justice and Its Critics", doi="10.1/aaa")),
            ("copyB", _make_entry(
                entry_type="book", authors=["Rawls, John"], year="1971",
                title="A Theory of Justice and Its Critics", doi="10.2/bbb")))
        cited = {k for k, _ in find_cited_entries(prose, bib)}
        assert cited == {"copyA", "copyB"}

    def test_author_year_cited_and_title_mentioned_not_double_added(self):
        """An entry cited author-year AND title-mentioned appears once:
        the inclusion loop skips keys already among kept records."""
        prose = ("Rawls (1971) set the agenda with *A Theory of Justice* "
                 "and the field followed his lead for decades after.\n")
        bib = _make_bib(("rawls1971theory", _make_entry(
            entry_type="book", authors=["Rawls, John"], year="1971",
            title="A Theory of Justice")))
        assert [k for k, _ in find_cited_entries(prose, bib)] == ["rawls1971theory"]

    def test_no_mention_no_change(self):
        """The net must not perturb collision or letter behavior, and this
        guard has
        to be able to FAIL to say so.

        Construction, all load-bearing. Both titles are >=4 folded words,
        so the net's word floor cannot make the test vacuous (an earlier
        version used 3-word titles, which the net can never reach on ANY
        prose). The prose carries a delimited span, so `_title_mentions`
        does not bail at `if not folded_spans` before the equality gate.
        And the running-text title is the JOINT member's, not the solo
        one's: the drop under test is the joint entry's, so loosening the
        span-equality gate to prose containment (the pre-design behavior
        the net's docstring rejects) rescues it and changes the outcome.
        Mutation-verified: replacing `tk not in folded_spans` with
        `(" " + tk + " ") not in " " + title_key(prose) + " "` turns this
        test RED (muldoonWu2023 gets a [TITLE] kept rescue). With the SOLO
        title in the prose instead, that same mutant yields the same
        answer and the test would stay green while broken."""
        prose = ("Muldoon (2023) presents the joint account theory of "
                 "choice in detail, calling it a \"theory of choice under "
                 "constraint\" throughout.\n")
        bib = _make_bib(
            ("muldoonSolo2023", _make_entry(
                authors=["Muldoon, Ryan"], year="2023",
                title="Solo Account Theory of Choice")),
            ("muldoonWu2023", _make_entry(
                authors=["Muldoon, Ryan", "Wu, Jane"], year="2023",
                title="Joint Account Theory of Choice")))
        cited = {k for k, _ in find_cited_entries(prose, bib)}
        assert cited == {"muldoonSolo2023"}

    @pytest.mark.parametrize("prose,key,entry", [
        # Article: format_entry renders the title in QUOTES -- the same shape
        # the net's quoted-span regexes match.
        ("## Review\n\nHeersmink’s \"The Internet, Cognitive Enhancement, "
         "and the Values of Cognition\" (2016) frames the upshot.\n",
         "heersmink2016internet",
         dict(authors=["Heersmink, Richard"], year="2016", journal="Synthese",
              title="The Internet, Cognitive Enhancement, and the Values of Cognition")),
        # Book: rendered in ITALICS -- the other format_entry path, matched by
        # the net's `*...*` regex.
        ("## Review\n\nRawls looms over everything here. *A Theory of Justice* "
         "remains the touchstone for the whole debate.\n",
         "rawls1971theory",
         dict(entry_type="book", authors=["Rawls, John"], year="1971",
              title="A Theory of Justice", publisher="Harvard University Press")),
    ], ids=["quoted-article", "italicized-book"])
    def test_net_added_entry_converges_across_reruns(self, prose, key, entry):
        """The net must not self-perpetuate through its OWN rendered output.

        format_entry writes article titles in quotes and book titles in
        italics -- exactly the spans _title_mentions matches -- so the
        References section this script emits is a document full of
        net-matchable title spans. That is the fixed-point failure class
        recorded in _strip_references_section's docstring (the letters "never
        converged at all" over a three-run cycle), and SKILL.md Phase 6 tells
        operators to re-run step 4 after a lint failure, so second runs happen
        in normal operation. What contains it here is that the net is fed the
        STRIPPED prose (_title_mentions(prose, ...), not review_text).

        Two phases, and the SECOND is what gives the test teeth. Three stable
        render/re-parse cycles alone are vacuous as a guard: with one entry
        whose title the prose still mentions, the answer is the same key
        whether or not the reference list is stripped (verified by mutation --
        swapping `prose` for `review_text` leaves phase 1 green). Only the
        operator fix cycle separates them, exactly as it does for the letter
        net: once the operator deletes the title mention from the body
        and re-runs step 4 over the file, stale ## References and all, the
        entry must go. Unstripped, its own reference line quotes/italicizes
        the title AND names the surname, so the net re-adds the very phantom
        the operator was removing -- for ever."""
        bib = _make_bib((key, _make_entry(**entry)))
        doc = prose
        for _ in range(3):
            cited = find_cited_entries(doc, bib)
            assert [k for k, _ in cited] == [key]
            doc = apply_references(doc, generate_references(cited))

        # Phase 2: the operator removes the title mention; the stale rendered
        # References section (still carrying the quoted/italicized title and
        # the surname) is the only place the work is now named.
        assert "## References" in doc  # sanity: a reference list exists to inherit
        edited = apply_references(
            "## Review\n\nThe debate has moved on to other questions.\n",
            generate_references(find_cited_entries(doc, bib)))
        assert [k for k, _ in find_cited_entries(edited, bib)] == []
