"""One owner for bibliography identity and matching.

Before this landed, metadata_cleaner, dedupe_bib and generate_bibliography each
carried their own title normalization and disagreed on non-ASCII input --
`Millière` keyed differently in each, so duplicate entries survived dedup. These
tests pin the single surviving contract, plus the fifth divergence axis
(casefold expansion) found during review. `hooks/bib_identity.py` is the one
owner; see CLAUDE.md for the standing rule that sites alias the shared objects
rather than re-adding a local copy.
"""

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import bib_identity as bi  # noqa: E402


class TestTitleKey:
    """The ROADMAP section 4 divergence table, as a contract."""

    def test_latin_diacritics_fold_to_base_letters(self):
        assert bi.title_key("Millière") == "milliere"

    def test_caron_folds_to_base_letter(self):
        assert bi.title_key("Davidović") == "davidovic"

    def test_stroke_letter_is_kept_not_dropped(self):
        # L-with-stroke has no combining-mark decomposition: it must survive as
        # itself, not vanish (which would equate distinct works). The a-ogonek
        # does decompose, so it folds to a bare 'a'.
        assert bi.title_key("Łącki on agency") == "łacki on agency"

    def test_non_latin_script_survives(self):
        greek = "Η ηθική της τεχνολογίας"
        result = bi.title_key(greek)
        assert result.strip(), "a wholly non-Latin title must not fold to whitespace"
        assert "ηθικ" in result

    def test_eszett_expands_under_casefold(self):
        # Fifth divergence axis: casefold expands eszett to 'ss', which NFKD
        # does not touch. The three old copies produced 'stra e' (dedupe_bib),
        # 'strae' (generate_bibliography) and 'strasse' (metadata_cleaner).
        assert bi.title_key("Straße") == "strasse"
        assert bi.title_key("Weiß") == "weiss"
        assert bi.title_key("Straße") == bi.title_key("STRASSE")

    def test_punctuation_collapses_to_single_spaces(self):
        assert bi.title_key("Mind, Self -- and: Society!") == "mind self and society"

    def test_empty_and_whitespace(self):
        assert bi.title_key("") == ""
        assert bi.title_key("   ") == ""


class TestNormalizeDoi:
    def test_lowercases_and_strips_prefixes(self):
        assert bi.normalize_doi("https://dx.doi.org/10.1000/X") == "10.1000/x"
        assert bi.normalize_doi("DOI:10.1000/X") == "10.1000/x"
        assert bi.normalize_doi("doi.org/10.1000/x") == "10.1000/x"
        assert bi.normalize_doi("  10.1000/x  ") == "10.1000/x"

    def test_empty_and_none(self):
        assert bi.normalize_doi("") == ""
        assert bi.normalize_doi(None) == ""


class TestNormalizePagesJournalYear:
    def test_pages_dash_runs_normalize(self):
        assert bi.normalize_pages("12 -- 34") == "12-34"
        assert bi.normalize_pages("") == ""

    def test_journal_decodes_entities_and_latex(self):
        assert bi.normalize_journal("Philosophy \\& Technology") == "philosophy & technology"
        assert bi.normalize_journal("No\\^{u}s") == "nous"
        assert bi.normalize_journal("The Journal of Philosophy") == "journal of philosophy"

    def test_year_key_erases_int_float_string_split(self):
        assert bi.year_key(2007) == "2007"
        assert bi.year_key(2007.0) == "2007"
        assert bi.year_key("2007") == "2007"
        assert bi.year_key("n.d.") == "n.d."


class TestVenueKeyAmpersandFold:
    """venue_key folds a standalone "&" onto "and" so a bibliography's LaTeX
    "\\&" verifies against an API record that spells the coordinator out --
    normalize_journal stays strict (dedup identity must not fold this).
    Motivating case: the cleaner planned to strip a correct `journal =
    {Health Information \\& Libraries Journal}` because the matched API
    record spells it "Health information and libraries journal" and no fold
    unified "&" with the word "and"."""

    def test_standalone_ampersand_folds_onto_and(self):
        assert bi.venue_key("Health Information \\& Libraries Journal") == \
            bi.venue_key("Health information and libraries journal")

    def test_normalize_journal_stays_strict_on_ampersand(self):
        # The identity key must NOT fold this -- only the looser verification
        # key does. If this ever starts holding, the diagnosis behind this
        # fold is wrong (dedup would already treat these as the same venue).
        assert bi.normalize_journal("Health Information \\& Libraries Journal") != \
            bi.normalize_journal("Health information and libraries journal")

    def test_plain_name_without_ampersand_is_unaffected(self):
        # Guard against substring damage: no "&" present, so the fold must be
        # a no-op.
        assert bi.venue_key("Anderson Quarterly") == "anderson quarterly"

    def test_embedded_ampersand_is_not_standalone(self):
        # "AT&T" has no whitespace around its "&" -- it is part of a proper
        # noun, not a coordinating "and", and must keep its pre-fold key.
        # Value pinned from the pre-change behavior (computed before this
        # fold was added).
        assert bi.venue_key("AT&T Technical Journal") == "at&t technical journal"


class TestFallbackKey:
    def test_builds_normalized_triple(self):
        assert bi.fallback_key("The Extended Mind", "1998", "Clark") == (
            "the extended mind", "1998", "clark")

    def test_none_when_any_component_empty(self):
        assert bi.fallback_key("", "1998", "Clark") is None
        assert bi.fallback_key("Title", "", "Clark") is None
        assert bi.fallback_key("Title", "1998", "") is None

    def test_non_latin_components_yield_a_key(self):
        assert bi.fallback_key("Η ηθική", "2021", "Παπαδόπουλος") is not None


class TestCleanerIsTheOwner:
    """metadata_cleaner must delegate, not keep a private copy."""

    def test_cleaner_helpers_are_the_shared_objects(self):
        import metadata_cleaner as mc
        assert mc.normalize_doi is bi.normalize_doi
        assert mc.normalize_pages is bi.normalize_pages
        assert mc.normalize_journal is bi.normalize_journal
        assert mc._year_key is bi.year_key
        assert mc._normalize_title is bi.title_key


class TestAsciiVariants:
    """ascii_variants: the one owner of the name fold shared by lint_md's
    citation check and generate_bibliography's matcher."""

    def test_plain_ascii(self):
        from bib_identity import ascii_variants
        assert ascii_variants("Smith") == frozenset({"smith"})

    def test_diacritic_two_variants(self):
        from bib_identity import ascii_variants
        assert ascii_variants("Fränken") == frozenset({"franken", "fraenken"})

    def test_transliteration_meets_ae_spelling(self):
        from bib_identity import ascii_variants
        assert ascii_variants("Fraenken") & ascii_variants("Fränken")

    def test_eszett_and_nordic(self):
        from bib_identity import ascii_variants
        assert "strasse" in ascii_variants("Straße")
        assert "aaberg" in ascii_variants("Åberg")

    def test_curly_apostrophe_unified(self):
        from bib_identity import ascii_variants
        assert ascii_variants("O’Neill") == ascii_variants("O'Neill")

    def test_empty_variants_dropped(self):
        from bib_identity import ascii_variants
        assert ascii_variants("Παπαδόπουλος") == frozenset()
        assert ascii_variants("") == frozenset()

    def test_translit_fold_text(self):
        from bib_identity import translit_fold
        assert translit_fold("As Müller (2022) shows") == "as mueller (2022) shows"

    def test_decomposed_unicode_variants(self):
        # NFC-recompose first: a decomposed a+combining-diaeresis must still
        # transliterate to ae (external review). The literal below uses an
        # explicit \u0308 escape (combining diaeresis), not a precomposed
        # a-with-diaeresis character, so the source text is guaranteed NFD --
        # a precomposed literal would pin nothing here, since it never
        # exercises the recompose path.
        from bib_identity import ascii_variants
        assert "fraenken" in ascii_variants("Fra\u0308nken")
