"""
Tests for verify_paper.py (CrossRef DOI verification).

Tests cover:
- Output schema validation
- Exit codes for different scenarios
- DOI normalization
- Author name extraction
- Verification by DOI vs. metadata search
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from test_utils import validate_output_schema, SCRIPTS_DIR


class TestVerifyPaperOutputSchema:
    """Tests for JSON output schema compliance."""

    def test_success_output_schema(self):
        """Successful verification should have correct schema."""
        import verify_paper

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_success(
                    {"doi": "10.1234/test"},
                    {"verified": True, "doi": "10.1234/test", "title": "Test"}
                )

        assert exc_info.value.code == 0
        errors = validate_output_schema(output, "success")
        assert errors == [], f"Schema errors: {errors}"
        assert output["source"] == "crossref"

    def test_not_found_output_schema(self):
        """Not found response should have correct schema."""
        import verify_paper

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_not_found(
                    {"title": "Unknown Paper"},
                    "Paper not found"
                )

        assert exc_info.value.code == 1
        errors = validate_output_schema(output, "error")
        assert errors == [], f"Schema errors: {errors}"
        assert output["errors"][0]["type"] == "not_found"


class TestVerifyPaperExitCodes:
    """Tests for correct exit codes."""

    def test_exit_code_0_on_success(self):
        """Should exit with 0 on successful verification."""
        import verify_paper

        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_success(
                    {"doi": "test"},
                    {"verified": True}
                )

        assert exc_info.value.code == 0

    def test_exit_code_1_on_not_found(self):
        """Should exit with 1 when paper not found."""
        import verify_paper

        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_not_found({"title": "Test"}, "Not found")

        assert exc_info.value.code == 1

    def test_exit_code_2_on_config_error(self):
        """Should exit with 2 on configuration error."""
        import verify_paper

        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                verify_paper.output_error({"title": "Test"}, "config_error", "Bad config")

        assert exc_info.value.code == 2


class TestDOINormalization:
    """Tests for DOI normalization."""

    def test_normalize_plain_doi(self):
        """Should return plain DOI unchanged."""
        import verify_paper

        assert verify_paper.normalize_doi("10.2307/2024717") == "10.2307/2024717"

    def test_normalize_https_prefix(self):
        """Should strip https://doi.org/ prefix."""
        import verify_paper

        result = verify_paper.normalize_doi("https://doi.org/10.2307/2024717")
        assert result == "10.2307/2024717"

    def test_normalize_http_prefix(self):
        """Should strip http://doi.org/ prefix."""
        import verify_paper

        result = verify_paper.normalize_doi("http://doi.org/10.2307/2024717")
        assert result == "10.2307/2024717"

    def test_normalize_doi_prefix(self):
        """Should strip doi: prefix."""
        import verify_paper

        result = verify_paper.normalize_doi("doi:10.2307/2024717")
        assert result == "10.2307/2024717"

    def test_normalize_whitespace(self):
        """Should strip whitespace."""
        import verify_paper

        result = verify_paper.normalize_doi("  10.2307/2024717  ")
        assert result == "10.2307/2024717"

    def test_normalize_is_the_shared_owner(self):
        """One owner for DOI normalization."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
        import bib_identity
        import verify_paper

        assert verify_paper.normalize_doi is bib_identity.normalize_doi

    def test_uppercase_doi_prefix_and_case_normalize(self):
        """DOI resolution is case-insensitive; the normalized value reaches
        only the CrossRef URL and a log line (the emitted doi comes from
        CrossRef, and query["doi"] echoes the raw argument)."""
        import verify_paper

        assert verify_paper.normalize_doi("DOI:10.2307/2024717") == "10.2307/2024717"
        assert verify_paper.normalize_doi("https://dx.doi.org/10.2307/X") == "10.2307/x"


class TestAuthorNameExtraction:
    """Tests for author name extraction from CrossRef format."""

    def test_extract_basic_names(self):
        """Should extract family and given names."""
        import verify_paper

        authors = [
            {"given": "Harry", "family": "Frankfurt"},
            {"given": "Susan", "family": "Wolf"},
        ]

        result = verify_paper.extract_author_names(authors)
        assert result == ["Frankfurt, Harry", "Wolf, Susan"]

    def test_extract_family_only(self):
        """Should handle authors with only family name."""
        import verify_paper

        authors = [{"family": "Aristotle"}]
        result = verify_paper.extract_author_names(authors)
        assert result == ["Aristotle"]

    def test_extract_organization(self):
        """Should handle organization names."""
        import verify_paper

        authors = [{"name": "World Health Organization"}]
        result = verify_paper.extract_author_names(authors)
        assert result == ["World Health Organization"]

    def test_extract_empty_list(self):
        """Should handle empty author list."""
        import verify_paper

        result = verify_paper.extract_author_names([])
        assert result == []


class TestFormatResult:
    """Tests for result formatting."""

    def test_format_result_basic(self, mock_crossref_response):
        """format_result should extract basic fields."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["verified"] is True
        assert result["doi"] == "10.2307/2024717"
        assert result["title"] == "Freedom of the Will and the Concept of a Person"
        assert result["year"] == 1971
        assert result["method"] == "doi_lookup"

    def test_format_result_suggested_bibtex_type_article(self, mock_crossref_response):
        """format_result should map journal-article to @article."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "article"

    def test_format_result_suggested_bibtex_type_book_chapter(self):
        """format_result should map book-chapter to @incollection."""
        import verify_paper

        item = {
            "DOI": "10.1093/oso/9780190859213.003.0007",
            "title": ["The Value of Ideal Theory"],
            "author": [{"given": "Matthew S.", "family": "Adams"}],
            "published": {"date-parts": [[2020]]},
            "container-title": ["John Rawls"],
            "publisher": "Oxford University Press",
            "type": "book-chapter",
            "page": "73-86",
        }
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "incollection"
        assert result["container_title"] == "John Rawls"

    def test_format_result_editors_for_edited_book(self):
        """format_result should extract editors for edited books."""
        import verify_paper

        item = {
            "DOI": "10.1093/oso/9780190859213.001.0001",
            "title": ["John Rawls"],
            "author": [],
            "editor": [{"given": "Jon", "family": "Mandle"}, {"given": "Sarah", "family": "Roberts-Cady"}],
            "published": {"date-parts": [[2020]]},
            "publisher": "Oxford University Press",
            "type": "edited-book",
        }
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "book"
        assert result["authors"] == []
        assert len(result["editors"]) == 2
        assert result["editors"][0]["family"] == "Mandle"
        assert result["editors"][1]["family"] == "Roberts-Cady"

    def test_format_result_editors_empty_when_absent(self, mock_crossref_response):
        """format_result should return empty editors list for regular articles."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["editors"] == []

    def test_format_result_suggested_bibtex_type_unknown(self):
        """format_result should fall back to @misc for unknown CrossRef types."""
        import verify_paper

        item = {
            "DOI": "10.1234/unknown",
            "title": ["Some Work"],
            "author": [],
            "type": "peer-review",
        }
        result = verify_paper.format_result(item, "doi_lookup")

        assert result["suggested_bibtex_type"] == "misc"

    def test_format_result_with_score(self, mock_crossref_response):
        """format_result should include score when provided."""
        import verify_paper

        item = mock_crossref_response["message"]
        result = verify_paper.format_result(item, "bibliographic_search", score=85.5)

        assert result["score"] == 85.5


class TestFormatResultMalformedShapes:
    """format_result must never crash or emit a non-string for the two
    CrossRef list fields it indexes, whatever shape arrives."""

    @staticmethod
    def _item(**overrides):
        base = {"DOI": "10.1/x", "type": "journal-article",
                "title": ["A Fine Title"],
                "container-title": ["A Fine Journal"]}
        base.update(overrides)
        return base

    def test_bare_int_title_yields_empty_not_crash(self):
        import verify_paper as vp
        result = vp.format_result(self._item(title=123), "doi_lookup")
        assert result["title"] == ""

    def test_dict_title_yields_empty_not_crash(self):
        import verify_paper as vp
        result = vp.format_result(self._item(title={"bad": "shape"}), "doi_lookup")
        assert result["title"] == ""

    def test_bare_string_title_is_not_adopted_or_char_sliced(self):
        import verify_paper as vp
        result = vp.format_result(self._item(title="Bare String"), "doi_lookup")
        assert result["title"] == ""

    def test_first_usable_element_wins_over_malformed_ones(self):
        import verify_paper as vp
        result = vp.format_result(
            self._item(title=[{"bad": 1}, "  ", "Real Title"]), "doi_lookup")
        assert result["title"] == "Real Title"

    def test_container_title_gets_the_same_guards(self):
        import verify_paper as vp
        for bad, expected in (
                (123, ""), ({"bad": 1}, ""), ("Bare String", ""),
                ([{"bad": 1}, "Real Venue"], "Real Venue")):
            result = vp.format_result(
                self._item(**{"container-title": bad}), "doi_lookup")
            assert result["container_title"] == expected

    def test_wellformed_lists_unchanged(self):
        import verify_paper as vp
        result = vp.format_result(self._item(), "doi_lookup")
        assert result["title"] == "A Fine Title"
        assert result["container_title"] == "A Fine Journal"


class TestContainerDisambiguation:
    CHAPTER_ITEM = {
        "DOI": "10.1007/978-3-642-31674-6_21",
        "type": "book-chapter",
        "title": ["Artificial Intelligence and the Body"],
        "container-title": [
            "Studies in Applied Philosophy, Epistemology and Rational Ethics",
            "Philosophy and Theory of Artificial Intelligence"],
        "ISBN": ["9783642316739", "9783642316746"],
        "publisher": "Springer Berlin Heidelberg",
    }

    # The parent volume's own CrossRef record, as the ISBN lookup returns
    # it -- its `title` names the volume, its `container-title` the series
    # (both verified against the live record for 10.1007/978-3-642-31674-6).
    PARENT_BOOK = {
        "title": ["Philosophy and Theory of Artificial Intelligence"],
        "type": "book",
        "container-title": [
            "Studies in Applied Philosophy, Epistemology and Rational Ethics"],
    }

    @staticmethod
    def _parent_response(items, total=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"message": {
            "items": items,
            "total-results": total if total is not None else len(items)}}
        return resp

    @staticmethod
    def _limiter():
        from rate_limiter import get_limiter
        return get_limiter("crossref")

    def test_format_result_series_defaults_empty(self, mock_crossref_response):
        import verify_paper as vp
        result = vp.format_result(mock_crossref_response["message"], "doi_lookup")
        assert result["series"] == ""

    @patch("requests.get")
    def test_parent_title_picks_the_volume(self, mock_get):
        """The parent book's own record (found by ISBN) names the volume;
        its container-title corroborates the remaining element as the
        series. This is the production shape: CrossRef put the series FIRST
        for 10.1007/978-3-642-31674-6_21. ONE request, both ISBN forms in
        one ORed filter."""
        import verify_paper as vp
        mock_get.return_value = self._parent_response([self.PARENT_BOOK])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert result["series"] == (
            "Studies in Applied Philosophy, Epistemology and Rational Ethics")
        assert mock_get.call_count == 1
        called_params = mock_get.call_args.kwargs.get("params") or {}
        assert "isbn:9783642316739" in called_params["filter"]
        assert "isbn:9783642316746" in called_params["filter"]
        assert "type:book" in called_params["filter"]

    @patch("requests.get")
    def test_reversed_array_order_picks_element_zero(self, mock_get):
        """Mutation guard against the explicitly rejected `[1]` rule: with
        the array REVERSED (volume first), the parent match must still pick
        the volume -- a positional implementation that passes the
        production-shape test fails here."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM)
        item["container-title"] = list(reversed(
            self.CHAPTER_ITEM["container-title"]))
        mock_get.return_value = self._parent_response([self.PARENT_BOOK])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert result["series"] == (
            "Studies in Applied Philosophy, Epistemology and Rational Ethics")

    @patch("requests.get")
    def test_genuinely_ambiguous_parents_bail(self, mock_get):
        """Two parents naming DIFFERENT container elements: contradictory
        exact-ISBN evidence, the unanimity gate bails."""
        import verify_paper as vp
        mock_get.return_value = self._parent_response(
            [{"title": [self.CHAPTER_ITEM["container-title"][0]], "type": "book"},
             {"title": [self.CHAPTER_ITEM["container-title"][1]], "type": "book"}])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == self.CHAPTER_ITEM["container-title"][0]
        assert result["series"] == ""
        assert mock_get.call_count == 1   # one combined request, no retry

    @patch("requests.get")
    def test_contradictory_unrelated_parent_bails(self, mock_get):
        """One parent names the volume, a second exact-ISBN parent names an
        UNRELATED book (ISBN reuse / registration error): the unrelated
        record is contradictory evidence, not noise to be outvoted."""
        import verify_paper as vp
        mock_get.return_value = self._parent_response(
            [self.PARENT_BOOK,
             {"title": ["Some Entirely Different Book"], "type": "book"}])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == self.CHAPTER_ITEM["container-title"][0]
        assert result["series"] == ""

    @patch("requests.get")
    def test_agreeing_duplicate_parents_proceed(self, mock_get):
        """Duplicate registrations of the SAME volume agree -- they must not
        read as ambiguity (the unanimity gate is on titles, not rows)."""
        import verify_paper as vp
        mock_get.return_value = self._parent_response(
            [dict(self.PARENT_BOOK), dict(self.PARENT_BOOK)])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_truncated_result_set_bails(self, mock_get):
        """total-results beyond the returned rows means unseen records could
        dissent -- deciding from a truncated page is not fail-closed."""
        import verify_paper as vp
        mock_get.return_value = self._parent_response(
            [dict(self.PARENT_BOOK), dict(self.PARENT_BOOK)], total=12)
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == self.CHAPTER_ITEM["container-title"][0]
        assert result["series"] == ""

    @patch("requests.get")
    def test_three_element_array_fixes_container_only(self, mock_get):
        """A 3+-element array's leftover is not provably a series name:
        container_title is fixed, series stays empty."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM)
        item["container-title"] = list(self.CHAPTER_ITEM["container-title"]) + [
            "A Third Container Value"]
        mock_get.return_value = self._parent_response([self.PARENT_BOOK])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert result["series"] == ""

    @patch("requests.get")
    def test_series_needs_parent_corroboration(self, mock_get):
        """A parent WITHOUT a container-title proves the volume but not the
        series: container_title is fixed, series stays empty."""
        import verify_paper as vp
        parent = {k: v for k, v in self.PARENT_BOOK.items()
                  if k != "container-title"}
        mock_get.return_value = self._parent_response([parent])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert result["series"] == ""

    @patch("requests.get")
    def test_proceedings_article_parent_is_type_proceedings(self, mock_get):
        """A proceedings-article's volume record is type `proceedings` --
        omitting it from the parent-type filter would silently exclude that
        half of the scope."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM, type="proceedings-article")
        mock_get.return_value = self._parent_response(
            [{"title": ["Philosophy and Theory of Artificial Intelligence"],
              "type": "proceedings"}])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        called_params = mock_get.call_args.kwargs.get("params") or {}
        assert "type:proceedings" in called_params["filter"]

    @patch("requests.get")
    def test_parent_title_matching_no_element_bails(self, mock_get):
        """An ISBN hit whose title matches neither element carries no
        authority over THIS array -- conservative bail, no guessing."""
        import verify_paper as vp
        mock_get.return_value = self._parent_response(
            [{"title": ["Some Entirely Different Book"], "type": "book"}])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == self.CHAPTER_ITEM["container-title"][0]
        assert result["series"] == ""

    @patch("requests.get")
    def test_network_failure_bails(self, mock_get):
        import verify_paper as vp
        mock_get.side_effect = Exception("boom")
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == self.CHAPTER_ITEM["container-title"][0]
        assert result["series"] == ""

    @patch("requests.get")
    def test_json_null_container_or_isbn_never_crashes(self, mock_get):
        """CrossRef can emit a JSON null where an array is expected; the
        guards must bail BEFORE any comprehension raises TypeError."""
        import verify_paper as vp
        for null_key in ("container-title", "ISBN"):
            item = dict(self.CHAPTER_ITEM)
            item[null_key] = None
            result = vp.format_result(item, "doi_lookup")
            vp.disambiguate_container(item, result, self._limiter(), "")
            assert result["series"] == ""
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_journal_article_never_looked_up(self, mock_get, mock_crossref_response):
        import verify_paper as vp
        item = mock_crossref_response["message"]
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_single_container_never_looked_up(self, mock_get):
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM,
                    **{"container-title": ["Just The Book Title"]})
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        mock_get.assert_not_called()
        assert result["container_title"] == "Just The Book Title"

    @patch("requests.get")
    def test_no_isbn_never_looked_up(self, mock_get):
        import verify_paper as vp
        item = {k: v for k, v in self.CHAPTER_ITEM.items() if k != "ISBN"}
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        mock_get.assert_not_called()

    def test_search_select_requests_isbn(self):
        import verify_paper as vp
        assert "ISBN" in vp._SEARCH_SELECT.split(",")

    @patch("requests.get")
    def test_hyphenated_isbn_is_normalized_for_the_filter(self, mock_get):
        """CrossRef's isbn: filter matches the unhyphenated indexed form; a
        hyphenated array value must not silently defeat the lookup."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM, ISBN=["978-3-642-31673-9"])
        mock_get.return_value = self._parent_response([self.PARENT_BOOK])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        called_params = mock_get.call_args.kwargs.get("params") or {}
        assert "isbn:9783642316739" in called_params["filter"]
        assert result["series"] != ""

    @patch("requests.get")
    def test_isbn_check_digit_is_uppercased_for_the_filter(self, mock_get):
        """CrossRef's indexed ISBN-10 check digit is uppercase X; a lowercase
        x in the source array must not silently defeat the lookup."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM, ISBN=["3-540-49698-x"])
        mock_get.return_value = self._parent_response([self.PARENT_BOOK])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        called_params = mock_get.call_args.kwargs.get("params") or {}
        assert "isbn:354049698X" in called_params["filter"]

    @patch("requests.get")
    def test_non_list_isbn_bails_without_request(self, mock_get):
        """A bare scalar where CrossRef normally sends an array: the
        container-level guard must bail. Both comprehensions sit BEFORE the
        try, so an unguarded `or []` would raise TypeError: 'int' object is
        not iterable straight out of disambiguate_container -- and
        verify_by_doi only handles RequestException, so it would escape the
        retry loop and take down the whole verification."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM, ISBN=9783642316739)
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        mock_get.assert_not_called()
        assert result["series"] == ""
        assert result["container_title"] == self.CHAPTER_ITEM["container-title"][0]

    @patch("requests.get")
    def test_bare_string_container_title_bails_without_request(self, mock_get):
        """A bare STRING container-title is the quiet half of the same bug:
        it iterates into single characters, each a non-empty str, so
        `len(containers) >= 2` passes and a real CrossRef request fires for
        an item that is not multi-container at all."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM)
        item["container-title"] = "Just A String"
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        mock_get.assert_not_called()
        assert result["series"] == ""
        # A bare string is not a CrossRef-conformant list, so
        # _first_string defines the behavior now: "", not the first
        # character.
        assert result["container_title"] == ""

    @patch("requests.get")
    def test_malformed_elements_inside_lists_bail_cleanly(self, mock_get):
        """Element-level malformation inside well-formed lists (an integer
        and an object among the ISBNs, an object among the containers): each
        bad value is skipped. The parent whose title is a bare STRING is not
        element-level malformation but a bad title TYPE, so it bails on the
        list-type gate before the unanimity check ever sees it -- either way
        the incumbent container_title is left untouched."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM)
        item["ISBN"] = [9783642316739, {"isbn": "x"}, "9783642316746"]
        item["container-title"] = [
            {"bad": "shape"},
            "Studies in Applied Philosophy, Epistemology and Rational Ethics",
            "Philosophy and Theory of Artificial Intelligence"]
        mock_get.return_value = self._parent_response(
            [{"title": "not-a-list", "type": "book"},
             self.PARENT_BOOK])
        result = vp.format_result(item, "doi_lookup")
        before = result["container_title"]
        vp.disambiguate_container(item, result, self._limiter(), "")
        assert result["container_title"] == before
        assert result["series"] == ""

    @patch("requests.get")
    def test_dict_parent_title_is_not_evidence(self, mock_get):
        """A parent whose `title` is an OBJECT iterates its KEYS, and a key is
        a str, so a malformed record could positively authorize a volume it
        never names. A parent that is not a dict with a LIST title is
        unusable evidence, and unusable evidence bails -- consistent with the
        unanimity gate treating anything short of agreement as contradiction."""
        import verify_paper as vp
        mock_get.return_value = self._parent_response(
            [{"title": {"Philosophy and Theory of Artificial Intelligence": True},
              "type": "book"}])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == self.CHAPTER_ITEM["container-title"][0]
        assert result["series"] == ""

    @patch("requests.get")
    def test_parents_disagreeing_on_the_series_set_no_series(self, mock_get):
        """Series support is per-parent, not a union: both parents agree on
        the VOLUME (so container_title is corrected), but one names the real
        series and the other names a different one. A union would find the
        remaining element present in the pooled set and emit `series` off
        contradictory evidence."""
        import verify_paper as vp
        dissenter = dict(self.PARENT_BOOK,
                         **{"container-title": ["Some Other Series"]})
        mock_get.return_value = self._parent_response(
            [dict(self.PARENT_BOOK), dissenter])
        result = vp.format_result(self.CHAPTER_ITEM, "doi_lookup")
        vp.disambiguate_container(self.CHAPTER_ITEM, result, self._limiter(), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert result["series"] == ""

    @patch("requests.get")
    def test_containers_normalizing_alike_bail_without_request(self, mock_get):
        """Two elements that normalize to the same key collapse in the
        normalized->raw dict, so `len(matches) != 1` silently reads as ONE
        match and the exactly-one-element rule is defeated. Caught before the
        request: nothing about this array can be disambiguated, whatever the
        parents say."""
        import verify_paper as vp
        item = dict(self.CHAPTER_ITEM)
        item["container-title"] = ["Book Title", "  BOOK   TITLE  "]
        mock_get.return_value = self._parent_response([self.PARENT_BOOK])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(item, result, self._limiter(), "")
        mock_get.assert_not_called()
        assert result["container_title"] == "Book Title"
        assert result["series"] == ""

    @patch("requests.get")
    def test_verify_by_doi_wires_the_disambiguation(self, mock_get):
        """Mutation guard for the call-site wiring: a perfect
        disambiguate_container that verify_by_doi never calls fails here."""
        import verify_paper as vp
        from rate_limiter import get_limiter, ExponentialBackoff
        doi_resp = MagicMock()
        doi_resp.status_code = 200
        doi_resp.json.return_value = {"message": self.CHAPTER_ITEM}
        mock_get.side_effect = [doi_resp,
                                self._parent_response([self.PARENT_BOOK])]
        result = vp.verify_by_doi("10.1007/978-3-642-31674-6_21",
                                  get_limiter("crossref"),
                                  ExponentialBackoff(max_attempts=1), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert result["series"] == (
            "Studies in Applied Philosophy, Epistemology and Rational Ethics")
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_search_by_metadata_wires_the_disambiguation(self, mock_get):
        """Same mutation guard for the search path. No author/year passed,
        so the top item only needs score >= 50 to clear the gate."""
        import verify_paper as vp
        from rate_limiter import get_limiter, ExponentialBackoff
        top = dict(self.CHAPTER_ITEM, score=120.0)
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {"message": {"items": [top]}}
        mock_get.side_effect = [search_resp,
                                self._parent_response([self.PARENT_BOOK])]
        result = vp.search_by_metadata(
            "Artificial Intelligence and the Body", None, None,
            get_limiter("crossref"), ExponentialBackoff(max_attempts=1), "")
        assert result["container_title"] == (
            "Philosophy and Theory of Artificial Intelligence")
        assert result["series"] == (
            "Studies in Applied Philosophy, Epistemology and Rational Ethics")
        assert mock_get.call_count == 2


class TestContainerDisposition:
    """`container_disambiguation`/`container_candidates`: the reopen-metric
    channel (v0.5.7, PHASED DEFAULTS). Reuses TestContainerDisambiguation's
    fixtures (CHAPTER_ITEM, PARENT_BOOK, _parent_response, _limiter) rather
    than duplicating them."""

    def test_single_container_leaves_keys_absent(self):
        import verify_paper as vp
        item = {"type": "book-chapter", "container-title": ["Only One"],
                "ISBN": ["9781"]}
        result = {}
        vp.disambiguate_container(
            item, result, TestContainerDisambiguation._limiter(), "")
        assert "container_disambiguation" not in result
        assert "container_candidates" not in result

    def test_missing_isbn_multi_element_records_bailed(self):
        import verify_paper as vp
        item = {"type": "book-chapter",
                "container-title": ["Series Name", "Volume Name"]}
        result = {}
        vp.disambiguate_container(
            item, result, TestContainerDisambiguation._limiter(), "")
        assert result["container_disambiguation"] == "bailed"
        assert result["container_candidates"] == 2

    @patch("requests.get")
    def test_successful_disambiguation_records_resolved(self, mock_get):
        """Reuses the existing happy-path fixture (parent title picks the
        volume): after a clean resolution, both new keys are present."""
        import verify_paper as vp
        item = TestContainerDisambiguation.CHAPTER_ITEM
        mock_get.return_value = TestContainerDisambiguation._parent_response(
            [TestContainerDisambiguation.PARENT_BOOK])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(
            item, result, TestContainerDisambiguation._limiter(), "")
        assert result["container_disambiguation"] == "resolved"
        assert result["container_candidates"] == 2

    @patch("requests.get")
    def test_unanimity_bail_records_bailed(self, mock_get):
        """Reuses the contradictory-parents fixture: two parents naming
        different elements fail the unanimity gate -- an evidence bail."""
        import verify_paper as vp
        item = TestContainerDisambiguation.CHAPTER_ITEM
        mock_get.return_value = TestContainerDisambiguation._parent_response(
            [{"title": [item["container-title"][0]], "type": "book"},
             {"title": [item["container-title"][1]], "type": "book"}])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(
            item, result, TestContainerDisambiguation._limiter(), "")
        assert result["container_disambiguation"] == "bailed"
        assert result["container_candidates"] == 2

    @patch("requests.get")
    def test_exception_path_records_error_and_persists(self, mock_get):
        """An exception before any response is infrastructure, not
        evidence -- the mutated result dict must still carry the
        disposition and candidate count, proving the except handler
        persists the caller's dict rather than discarding it."""
        import verify_paper as vp
        item = TestContainerDisambiguation.CHAPTER_ITEM
        mock_get.side_effect = RuntimeError("boom")
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(
            item, result, TestContainerDisambiguation._limiter(), "")
        assert result["container_disambiguation"] == "error"
        assert result["container_candidates"] == 2

    @patch("requests.get")
    def test_non_200_response_records_error(self, mock_get):
        import verify_paper as vp
        item = TestContainerDisambiguation.CHAPTER_ITEM
        resp = MagicMock()
        resp.status_code = 500
        mock_get.return_value = resp
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(
            item, result, TestContainerDisambiguation._limiter(), "")
        assert result["container_disambiguation"] == "error"
        assert result["container_candidates"] == 2

    @patch("requests.get")
    def test_empty_parent_result_is_an_evidence_bail_not_error(self, mock_get):
        """CrossRef answered with a parseable body whose `items` is empty --
        the answer authorizes nothing, so this is an evidence bail, not an
        infrastructure error (the post-parse default flip)."""
        import verify_paper as vp
        item = TestContainerDisambiguation.CHAPTER_ITEM
        mock_get.return_value = TestContainerDisambiguation._parent_response([])
        result = vp.format_result(item, "doi_lookup")
        vp.disambiguate_container(
            item, result, TestContainerDisambiguation._limiter(), "")
        assert result["container_disambiguation"] == "bailed"
        assert result["container_candidates"] == 2


class TestVerifyByDOI:
    """Tests for DOI verification."""

    @patch("requests.get")
    def test_verify_by_doi_success(self, mock_get, mock_crossref_response):
        """Should verify paper by DOI."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_crossref_response
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        result = verify_paper.verify_by_doi(
            "10.2307/2024717",
            limiter=limiter,
            backoff=backoff,
            mailto="test@example.com",
        )

        assert result["verified"] is True
        assert result["doi"] == "10.2307/2024717"

    @patch("requests.get")
    def test_verify_by_doi_not_found(self, mock_get):
        """Should raise LookupError for non-existent DOI."""
        mock_get.return_value = MagicMock(status_code=404)

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        with pytest.raises(LookupError) as exc_info:
            verify_paper.verify_by_doi(
                "10.9999/nonexistent",
                limiter=limiter,
                backoff=backoff,
                mailto="test@example.com",
            )

        assert "not found" in str(exc_info.value).lower()


class TestSearchByMetadata:
    """Tests for metadata-based search."""

    @patch("requests.get")
    def test_search_by_title_and_author(self, mock_get):
        """Should find paper by title and author."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.2307/2024717",
                            "title": ["Freedom of the Will and the Concept of a Person"],
                            "author": [{"given": "Harry", "family": "Frankfurt"}],
                            "published": {"date-parts": [[1971]]},
                            "score": 95.0,
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        result = verify_paper.search_by_metadata(
            title="Freedom of the Will",
            author="Frankfurt",
            year=1971,
            limiter=limiter,
            backoff=backoff,
            mailto="test@example.com",
        )

        assert result["verified"] is True
        assert result["doi"] == "10.2307/2024717"

    @patch("requests.get")
    def test_search_returns_editors(self, mock_get):
        """Should populate editors from CrossRef search results."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1093/oso/9780190859213.001.0001",
                            "title": ["John Rawls"],
                            "author": [],
                            "editor": [
                                {"given": "Jon", "family": "Mandle"},
                                {"given": "Sarah", "family": "Roberts-Cady"},
                            ],
                            "published": {"date-parts": [[2020]]},
                            "publisher": "Oxford University Press",
                            "type": "edited-book",
                            "score": 95.0,
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        result = verify_paper.search_by_metadata(
            title="John Rawls",
            author=None,
            year=2020,
            limiter=limiter,
            backoff=backoff,
            mailto="test@example.com",
        )

        assert len(result["editors"]) == 2
        assert result["editors"][0]["family"] == "Mandle"
        assert result["editors"][1]["family"] == "Roberts-Cady"

    @patch("requests.get")
    def test_search_rejects_low_score(self, mock_get):
        """Should reject matches with low confidence score."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1234/wrong",
                            "title": ["Something Completely Different"],
                            "author": [{"given": "John", "family": "Doe"}],
                            "score": 15.0,  # Low score
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("crossref")
        backoff = ExponentialBackoff()

        with pytest.raises(LookupError) as exc_info:
            verify_paper.search_by_metadata(
                title="Freedom of the Will",
                author="Frankfurt",
                year=None,
                limiter=limiter,
                backoff=backoff,
                mailto="test@example.com",
            )

        assert "score" in str(exc_info.value).lower()


class TestVerifyPaperCLI:
    """Tests for command-line interface."""

    def test_cli_requires_doi_or_title(self, run_skill_script):
        """Should fail when neither --doi nor --title provided."""
        result = run_skill_script("verify_paper.py")
        assert result.returncode == 2

        output = result.json
        assert output["status"] == "error"
        assert "Must provide" in output["errors"][0]["message"]

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("verify_paper.py", "--help")
        assert result.returncode == 0
        assert "CrossRef" in result.stdout


class TestVerifyPaperProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import verify_paper
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            verify_paper.log_progress("Test message")

        output = captured.getvalue()
        assert "[verify_paper.py]" in output
        assert "Test message" in output


class TestOnlineFirstYear:
    """CrossRef's `published` is the EARLIEST of published-print and
    published-online, so trying it first reported the ONLINE year for every
    online-first work. metadata_cleaner.py then "corrected" correct
    bibliographies to match: 27 of 42 year rewrites over the local corpora
    replaced a year matching `published-print` with the online-first year.
    """

    # Mind 130(517): online 2019-12-03, print 2021-06-01. The citation year is
    # 2021; the pre-fix code reported 2019.
    PINDER = {
        "DOI": "10.1093/mind/fzz069",
        "title": ["Conceptual Engineering, Metasemantic Externalism and Speaker-Meaning"],
        "author": [{"given": "Mark", "family": "Pinder"}],
        "published": {"date-parts": [[2019, 12, 3]]},
        "published-online": {"date-parts": [[2019, 12, 3]]},
        "published-print": {"date-parts": [[2021, 6, 1]]},
        "container-title": ["Mind"],
        "volume": "130",
        "issue": "517",
        "type": "journal-article",
    }

    def test_print_year_wins_over_online_first(self):
        import verify_paper

        assert verify_paper.extract_year(self.PINDER) == (2021, "published-print")

    def test_format_result_reports_the_citation_year(self):
        import verify_paper

        result = verify_paper.format_result(self.PINDER, "doi_lookup")

        assert result["year"] == 2021
        assert result["year_basis"] == "published-print"

    def test_online_only_work_falls_back_to_published(self):
        """No print date: `published` IS the citation year, and the basis says
        so, so the cleaner may still act on it."""
        import verify_paper

        item = {"published": {"date-parts": [[2022, 4]]},
                "published-online": {"date-parts": [[2022, 4]]}}

        assert verify_paper.extract_year(item) == (2022, "published")

    def test_registration_timestamp_is_marked_as_such(self):
        """`created` is when CrossRef was told about the work, not when it was
        published. It is a last resort, and the basis lets a consumer refuse
        to overwrite a bibliography year with it."""
        import verify_paper

        item = {"created": {"date-parts": [[2015, 8, 9]]}}

        assert verify_paper.extract_year(item) == (2015, "created")

    def test_no_dates_at_all(self):
        import verify_paper

        assert verify_paper.extract_year({"title": ["Undated"]}) == (None, None)

    def test_malformed_date_parts_are_skipped(self):
        import verify_paper

        item = {"published-print": {"date-parts": [[]]},
                "published": {"date-parts": [[1998]]}}

        assert verify_paper.extract_year(item) == (1998, "published")

    @patch("requests.get")
    def test_title_search_accepts_the_print_year_of_an_online_first_work(self, mock_get):
        """Regression: the +/-1 year filter compared ONLY against `published`
        (the online date), so searching for Episteme 17(2) by its citation year
        2020 was rejected as a "Year mismatch" against the 2018 online date -
        the correct paper, refused."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1017/epi.2018.32",
                            "title": ["Echo Chambers and Epistemic Bubbles"],
                            "author": [{"given": "C. Thi", "family": "Nguyen"}],
                            "published": {"date-parts": [[2018, 9, 13]]},
                            "published-online": {"date-parts": [[2018, 9, 13]]},
                            "published-print": {"date-parts": [[2020, 6]]},
                            "score": 95.0,
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        result = verify_paper.search_by_metadata(
            title="Echo Chambers and Epistemic Bubbles",
            author="Nguyen",
            year=2020,
            limiter=get_limiter("crossref"),
            backoff=ExponentialBackoff(),
            mailto="test@example.com",
        )

        assert result["doi"] == "10.1017/epi.2018.32"
        assert result["year"] == 2020

    @patch("requests.get")
    def test_title_search_still_rejects_a_genuinely_wrong_year(self, mock_get):
        """Widening the filter to accept EITHER date must not make it vacuous."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1017/epi.2018.32",
                            "title": ["Echo Chambers and Epistemic Bubbles"],
                            "author": [{"given": "C. Thi", "family": "Nguyen"}],
                            "published": {"date-parts": [[2018, 9, 13]]},
                            "published-print": {"date-parts": [[2020, 6]]},
                            "score": 95.0,
                        }
                    ]
                }
            }
        )

        import verify_paper
        from rate_limiter import get_limiter, ExponentialBackoff

        with pytest.raises(LookupError, match="Year mismatch"):
            verify_paper.search_by_metadata(
                title="Echo Chambers and Epistemic Bubbles",
                author="Nguyen",
                year=1995,
                limiter=get_limiter("crossref"),
                backoff=ExponentialBackoff(),
                mailto="test@example.com",
            )


class TestSearchSelectRequestsPrintDates:
    """Citation-year correctness: the bibliographic-search path
    must ASK CrossRef for the print/online date fields. A `select` list that
    omits `published-print` means extract_year can never reach its own first
    preference on that path - the record's year is the online-first
    `published` year, and the on-disk verify record then positively
    corroborates a wrong bibliography year (measured live: vallier2014moral
    bib=2014/print=2015, wiens2011prescribing bib=2011/print=2012, both
    `method: bibliographic_search`).

    The fake CrossRef below RESPECTS the select list - it returns only the
    fields the request asked for, which is what the live API does - so the
    year assertions fail against a select list that never requests the
    print date, not merely against a stubbed response.
    """

    _FULL_ITEM = {
        "DOI": "10.1234/select-test",
        "title": ["Moral Rights and Political Freedom"],
        "score": 90.0,
        "type": "journal-article",
        "published": {"date-parts": [[2014, 6, 22]]},
        "published-print": {"date-parts": [[2015, 2]]},
        "published-online": {"date-parts": [[2014, 6, 22]]},
    }

    def _run_search(self):
        import verify_paper

        captured = {}

        def fake_get(url, params=None, timeout=None):
            captured["params"] = params
            selected = set((params or {}).get("select", "").split(","))
            item = {k: v for k, v in self._FULL_ITEM.items() if k in selected}
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"message": {"items": [item]}}
            return response

        limiter = MagicMock()
        backoff = MagicMock(max_attempts=1)
        with patch.object(verify_paper.requests, "get", side_effect=fake_get):
            result = verify_paper.search_by_metadata(
                "Moral Rights and Political Freedom", None, None,
                limiter, backoff, mailto="")
        return captured["params"], result

    def test_select_list_requests_print_and_online_dates(self):
        params, _ = self._run_search()
        select_fields = params["select"].split(",")
        assert "published-print" in select_fields
        assert "published-online" in select_fields

    def test_search_result_year_is_the_print_year(self):
        _, result = self._run_search()
        assert result["year"] == 2015
        assert result["year_basis"] == "published-print"


class TestSelectListYearFieldSync:
    """The missing published-print request WAS a desync between
    _YEAR_FIELDS and the hand-maintained select string; the select value is
    now derived from the constant so the next date-field change cannot miss
    the search path again."""

    def test_select_carries_every_year_field_except_created(self):
        import verify_paper
        select_fields = verify_paper._SEARCH_SELECT.split(",")
        for field in verify_paper._YEAR_FIELDS:
            if field == "created":
                assert field not in select_fields  # registration timestamp
            else:
                assert field in select_fields, field


class TestBookTypeMapCoverage:
    """Review finding on the reprint-edition direction bound:
    CrossRef's other book types fell to the default 'misc', so genuinely
    book-typed records bypassed the bound - reference works and multi-volume
    sets are precisely the canonical, reprint-prone class it was built for."""

    @pytest.mark.parametrize("crossref_type,expected", [
        ("reference-book", "book"),
        ("book-set", "book"),
        ("book-series", "book"),
        ("book-part", "incollection"),
        ("book-track", "incollection"),
    ])
    def test_remaining_book_types_map_into_the_book_class(
            self, crossref_type, expected):
        import verify_paper
        assert verify_paper.CROSSREF_TO_BIBTEX_TYPE[crossref_type] == expected
