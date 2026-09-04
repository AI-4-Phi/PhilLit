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
    """The name-fold divergence table in `bib_identity`, as a contract."""

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
        # transliterate to ae. The literal below uses an
        # explicit \u0308 escape (combining diaeresis), not a precomposed
        # a-with-diaeresis character, so the source text is guaranteed NFD --
        # a precomposed literal would pin nothing here, since it never
        # exercises the recompose path.
        from bib_identity import ascii_variants
        assert "fraenken" in ascii_variants("Fra\u0308nken")

    # -- contraction (third axis): bridges two independently ASCII-fied
    # spellings that carry no diacritic on either side -----------------

    def test_contraction_bridges_digraph_and_plain(self):
        # Fraenken/Franken: neither side has a diacritic, so the NFKD fold
        # and the translit fold already agree with each other ({"fraenken"})
        # and cannot bridge to "franken" without the contraction.
        from bib_identity import ascii_variants
        assert ascii_variants("Fraenken") >= frozenset({"fraenken", "franken"})

    def test_contraction_needle_side_unaffected_when_already_contracted(self):
        from bib_identity import ascii_variants
        assert ascii_variants("Franken") == frozenset({"franken"})

    def test_diacritic_variants_unchanged_by_contraction(self):
        # Pinned exact-equality set from test_diacritic_two_variants above:
        # {franken, fraenken} is closed under contraction (contract_fold of
        # either element yields "franken", already in the set), so adding
        # the third axis changes nothing here.
        from bib_identity import ascii_variants
        assert ascii_variants("Fr\u00e4nken") == frozenset({"franken", "fraenken"})

    def test_digraph_free_name_unchanged(self):
        from bib_identity import ascii_variants
        assert ascii_variants("Smith") == frozenset({"smith"})

    def test_length_guard_drops_short_contractions(self):
        # Measured 2026-08-29: every sub-4 contraction in the 2,430-surname
        # corpus was a match-flood needle, not a genuine bridge - "no" hits
        # essentially every sentence near a year.
        from bib_identity import ascii_variants
        assert "no" not in ascii_variants("No\u00eb")
        assert "co" not in ascii_variants("Coe")
        assert "shu" not in ascii_variants("Shue")

    def test_length_guard_keeps_four_character_contraction(self):
        # B\u00f6hm/Boehm: "bohm" is exactly 4 characters, so it clears the guard
        # (unlike the sub-4 needles above) whether the input already carries
        # the digraph or the diacritic.
        from bib_identity import ascii_variants
        assert "bohm" in ascii_variants("B\u00f6hm")
        assert "bohm" in ascii_variants("Boehm")

    def test_ascii_variants_contract_false_omits_contraction(self):
        from bib_identity import ascii_variants
        full = ascii_variants("S\u00f8gaard")
        plain = ascii_variants("S\u00f8gaard", contract=False)
        assert "sogaard" in full
        assert "sogaard" not in plain
        assert plain <= full


class TestContractFold:
    """contract_fold: the third axis of symmetric surname matching -
    translit_fold followed by the ae/oe/ue digraph contractions."""

    def test_digraph_ae_contracts(self):
        from bib_identity import contract_fold
        assert contract_fold("Fraenken") == "franken"

    def test_diacritic_ue_contracts_via_translit(self):
        from bib_identity import contract_fold
        assert contract_fold("M\u00fcller") == "muller"

    def test_nordic_oe_contracts_via_translit(self):
        # S\u00f8gaard: \u00f8 does not NFKD-decompose, so the plain fold is "sgaard"
        # (dropping the letter entirely); the live regression this fix
        # targets. contract_fold goes through translit_fold first (\u00f8->oe),
        # so it reaches "sogaard" instead.
        from bib_identity import contract_fold
        assert contract_fold("S\u00f8gaard") == "sogaard"


class TestSameWorkKeys:
    """The advisory reprint-grouping axis the evidence barrier stamps and
    generate_bibliography's Phase 6 advisory re-derives. One owner here, so
    the two cannot drift apart on what counts as "the same work"."""

    def test_same_work_key_requires_both_components(self):
        from bib_identity import same_work_key
        assert same_work_key("A Title", "Reiman") == same_work_key(
            "a  title!", "Reiman")
        assert same_work_key("", "Reiman") is None
        assert same_work_key("A Title", "") is None
        assert same_work_key(None, None) is None

    def test_brace_protection_keys_differently(self):
        """title_key maps every non-alphanumeric to a space rather than
        removing it, so a brace-protected initial ("a {T}itle") splits the
        word. Inherited from title_key's documented scope, pinned here so
        the grouping's known blind spot is stated rather than assumed away:
        a reprint whose title braces a word matches only a sibling that
        braces it the same way."""
        from bib_identity import same_work_key
        assert same_work_key("A Title", "Reiman") != same_work_key(
            "a {T}itle", "Reiman")

    def test_same_work_key_is_the_title_key_fold_on_both_axes(self):
        from bib_identity import same_work_key, title_key
        assert same_work_key("Driving to the Panopticon", "Millière") == (
            title_key("Driving to the Panopticon"), "milliere")

    def test_same_work_year_whole_field_grammar(self):
        from bib_identity import same_work_year
        assert same_work_year("1984") == "1984"
        assert same_work_year("1984a") == "1984"
        assert same_work_year("1984--1985") == "1984"
        assert same_work_year("1984-1985") == "1984"
        assert same_work_year("1984/2017") == "1984"
        assert same_work_year(" 2017 ") == "2017"
        assert same_work_year(2017) == "2017"
        assert same_work_year("n.d.") == ""
        assert same_work_year(None) == ""
        assert same_work_year("") == ""

    def test_malformed_year_fields_mint_no_phantom_year(self):
        """The fail-safe direction for an advisory: a garbage year field must
        never group a valid entry against it."""
        from bib_identity import same_work_year
        assert same_work_year("9781234567890") == ""
        assert same_work_year("10.1234/2017.42") == ""
        assert same_work_year("pages 1984--1990") == ""
        assert same_work_year("forthcoming 2017") == ""


class TestAuthorListSplit:
    """One owner for splitting a BibTeX name list. pybtex is brace-aware;
    the naive `" and "` split it replaces was not, so a braced corporate
    author containing "and" keyed as `smith` in the barrier and as
    `smith and jones institute` in Phase 6. The rows below that differ from
    the literal split (uppercase AND, doubled spaces) are documented
    changes: 0 of 9,157 local author/editor fields have either shape."""

    def test_plain_two_authors(self):
        assert bi.split_author_list("Smith, John and Doe, Jane") == ["Smith, John", "Doe, Jane"]

    def test_braced_corporate_author_containing_and_stays_one_name(self):
        assert bi.split_author_list("{Smith and Jones Institute} and Doe, Jane") == [
            "{Smith and Jones Institute}", "Doe, Jane"]

    def test_uppercase_and_and_doubled_spaces_split_like_pybtex(self):
        assert bi.split_author_list("Smith, John AND Doe, Jane") == ["Smith, John", "Doe, Jane"]
        assert bi.split_author_list("Smith, John  and  Doe, Jane") == ["Smith, John", "Doe, Jane"]

    def test_newline_before_second_name_is_not_a_separator(self):
        # Same as the literal split: pybtex does not split across a newline.
        assert bi.split_author_list("Smith, John and\nDoe, Jane") == ["Smith, John and\nDoe, Jane"]

    def test_empty_and_none_are_empty(self):
        assert bi.split_author_list("") == []
        assert bi.split_author_list(None) == []

    def test_unbalanced_brace_and_leading_and_do_not_raise(self):
        assert bi.split_author_list("{Smith and Jones") == ["{Smith and Jones"]
        assert bi.split_author_list("and Smith") == ["and Smith"]

    def test_first_author_name_falls_back_to_editor(self):
        assert bi.first_author_name("", "Menary, Richard and Wu, Jing") == "Menary, Richard"
        assert bi.first_author_name("Doe, Jane", "Menary, Richard") == "Doe, Jane"
        assert bi.first_author_name("", "") == ""

    def test_first_author_surname_is_pybtex_prelast_plus_last(self):
        assert bi.first_author_surname("Willem van der Deijl and Doe, Jane") == "van der Deijl"
        assert bi.first_author_surname("van der Deijl, Willem") == "van der Deijl"

    def test_first_author_surname_keeps_braced_corporate_author_whole(self):
        assert bi.first_author_surname("{Smith and Jones Institute} and Doe, Jane") == "{Smith and Jones Institute}"

    def test_first_author_surname_keeps_case_protection_braces_raw(self):
        assert bi.first_author_surname("{B}rown, John") == "{B}rown"

    def test_first_author_surname_empty(self):
        assert bi.first_author_surname("") == ""

    def test_first_author_surname_characterizes_odd_inputs_end_to_end(self):
        # Documented behaviour, not endorsement: same strings the literal split produced.
        # pybtex reads the leading "and" as a prelast particle (Person("and
        # Smith").prelast_names == ["and"]), so Person succeeds with a
        # non-empty surname and the comma/whitespace fallback never runs.
        assert bi.first_author_surname("and Smith") == "and Smith"
        assert bi.first_author_surname("Smith, John and\nDoe, Jane") == "Smith"
        # Person raises InvalidNameString (a PybtexError) -> comma fallback.
        assert bi.first_author_surname("a, b, c, d") == "a"
        # Person raises UnboundLocalError (pybtex's own bug) on a tie-only
        # name -> whitespace fallback returns the token whole.
        assert bi.first_author_surname("~") == "~"
        # Empty author falls back to the editor list, same parse.
        assert bi.first_author_surname("", "Menary, Richard and Wu, Jing") == "Menary"

    def test_first_author_surname_falls_back_when_person_raises(self, monkeypatch):
        """The catch is scoped to the Person call, so ANY failure there --
        not only pybtex's own -- still yields the comma/whitespace split."""
        def boom(_):
            raise RuntimeError("Person exploded")
        monkeypatch.setattr(bi, "Person", boom)
        assert bi.first_author_surname("Doe, Jane") == "Doe"

    def test_first_author_surname_keeps_braced_comma_name_whole(self):
        # raw identity text keeps the group whole; get_author_last_name's
        # search token differs by design
        assert bi.first_author_surname("{Doe, Jane}") == "{Doe, Jane}"


class TestProseSurnameIsTheOwner:
    """`first_author_prose_surname` is the second of this module's two
    surname rules. `check_evidence.rc_surname` and
    `resolve_context.first_author_surname` were byte-identical copies of it,
    and `rc_surname`'s docstring asserted the agreement in prose -- the shape
    `f0440fa`-`05efb94` spent five versions removing everywhere else."""

    def test_both_sites_are_the_shared_object(self):
        scripts = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import check_evidence
            import resolve_context
        finally:
            sys.path.pop(0)
        assert check_evidence.rc_surname is bi.first_author_prose_surname
        assert resolve_context.first_author_surname is bi.first_author_prose_surname

    def test_takes_the_part_before_the_first_comma(self):
        assert bi.first_author_prose_surname("Doe, Jane and Roe, Rick") == "Doe"
        assert bi.first_author_prose_surname("van Fraassen, Bas C.") == "van Fraassen"
        assert bi.first_author_prose_surname("O'Neill, Onora") == "O'Neill"

    def test_empty_and_none_give_empty(self):
        assert bi.first_author_prose_surname("") == ""
        assert bi.first_author_prose_surname(None) == ""

    def test_accented_and_corporate_names_agree_with_the_identity_rule(self):
        # The two rules coincide everywhere the docstring says they do: the
        # split is brace-aware, and both keep braces and stay undecoded.
        for field in ("Mendon{\\c{c}}a, Desiree",
                      "{Smith and Jones Institute} and Doe, Jane",
                      "{The Royal Society}",
                      "van Fraassen, Bas C."):
            assert bi.first_author_prose_surname(field) == bi.first_author_surname(field)

    def test_comma_less_name_is_the_first_documented_divergence(self):
        # Both known limits are pinned so a change to either is deliberate;
        # each hands the prose consumers a string real Chicago prose lacks.
        assert bi.first_author_prose_surname("Jane Doe") == "Jane Doe"
        assert bi.first_author_surname("Jane Doe") == "Doe"
        # A tie separates for pybtex but not for the comma split.
        assert bi.first_author_prose_surname("Doe~Jane") == "Doe~Jane"
        assert bi.first_author_surname("Doe~Jane") == "Jane"

    def test_a_single_token_comma_less_name_does_not_diverge(self):
        # The divergence needs a name pybtex can SPLIT: it is multi-token
        # comma-less names, not comma-less names, so the docstring and the
        # census must not be written over the broader class.
        for field in ("Aristotle", "{The Royal Society}"):
            assert bi.first_author_prose_surname(field) == bi.first_author_surname(field)

    def test_braced_comma_name_is_the_second_documented_divergence(self):
        # The LIST split is brace-aware; this comma split is not, so the
        # group is cut and the result is brace-unbalanced.
        assert bi.first_author_prose_surname("{Doe, Jane}") == "{Doe"
        assert bi.first_author_surname("{Doe, Jane}") == "{Doe, Jane}"

    def test_neither_divergence_raises_in_either_prose_consumer(self):
        # The cost is a silent under-report, never a crash: that is what
        # makes leaving both shapes unfixed acceptable pending a census.
        scripts = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import check_evidence
        finally:
            sys.path.pop(0)
        md = "As Doe (2020) argues, see Doe 2020."
        assert check_evidence.find_cites(md, "Doe", "2020")  # the shape that works
        for lost in ("Jane Doe", "{Doe"):
            assert check_evidence.find_cites(md, lost, "2020") == []

    def test_the_two_rules_agree_on_the_person_failure_fallback_path(self):
        # The corner the docstring's "two shapes" claim is only true over:
        # `first_author_surname` degrades to `_fallback_surname` when pybtex's
        # `Person` raises (too many commas) and that fallback IS the comma
        # split, so the rules agree there rather than diverging a third time.
        for field in ("Doe, John, Jr.", "a, b, c, d", "Doe, Jr., John",
                      "Smith, , John"):
            assert bi.first_author_prose_surname(field) == bi.first_author_surname(field)

    def test_no_editor_fallback_unlike_the_identity_rule(self):
        # check_evidence documents editor-only invisibility as a residual.
        assert bi.first_author_prose_surname("") == ""
        assert bi.first_author_surname("", "Roe, Rick") == "Roe"
