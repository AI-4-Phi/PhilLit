"""
Tests for get_abstract.py (multi-source abstract resolution).

Tests cover:
- Output schema validation
- Fallback chain behavior (S2 -> OpenAlex -> CORE)
- Source attribution
- Not found handling
"""

import json
from unittest.mock import patch, MagicMock

import pytest
import requests


# =============================================================================
# Output Tests
# =============================================================================

class TestGetAbstractOutput:
    """Tests for output format."""

    def test_success_output_format(self):
        """Success output should have correct fields."""
        import get_abstract

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_abstract.output_result(
                    "success",
                    {"doi": "10.1234/test"},
                    "This is the abstract",
                    "openalex"
                )

        assert exc_info.value.code == 0
        assert output["status"] == "success"
        assert output["abstract"] == "This is the abstract"
        assert output["abstract_source"] == "openalex"
        assert output["query"]["doi"] == "10.1234/test"

    def test_not_found_output_format(self):
        """Not found output should have null abstract."""
        import get_abstract

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_abstract.output_result("not_found", {"doi": "10.1234/test"})

        assert exc_info.value.code == 0
        assert output["status"] == "not_found"
        assert output["abstract"] is None
        assert output["abstract_source"] is None

    def test_error_output_format(self):
        """Error output should have error field."""
        import get_abstract

        output = None
        def capture_print(data):
            nonlocal output
            output = json.loads(data)

        with patch("builtins.print", capture_print):
            with pytest.raises(SystemExit) as exc_info:
                get_abstract.output_error(
                    {"doi": "10.1234/test"},
                    "api_error",
                    "Something went wrong",
                    exit_code=3
                )

        assert exc_info.value.code == 3
        assert output["status"] == "error"
        assert output["error"]["type"] == "api_error"


# =============================================================================
# OpenAlex Abstract Reconstruction
# =============================================================================

class TestOpenAlexAbstractReconstruction:
    """Tests for OpenAlex inverted index reconstruction."""

    def test_reconstruct_simple(self):
        """Should reconstruct simple abstract."""
        import get_abstract

        inverted = {
            "This": [0],
            "is": [1],
            "a": [2],
            "test": [3],
        }

        result = get_abstract.reconstruct_abstract(inverted)
        assert result == "This is a test"

    def test_reconstruct_with_repeated_words(self):
        """Should handle words appearing multiple times."""
        import get_abstract

        inverted = {
            "the": [0, 4],
            "cat": [1],
            "and": [2],
            "dog": [3, 5],
        }

        result = get_abstract.reconstruct_abstract(inverted)
        assert result == "the cat and dog the dog"

    def test_reconstruct_empty(self):
        """Should return None for empty inverted index."""
        import get_abstract

        assert get_abstract.reconstruct_abstract(None) is None
        assert get_abstract.reconstruct_abstract({}) is None


# =============================================================================
# Individual Source Tests
# =============================================================================

class TestS2Source:
    """Tests for Semantic Scholar abstract retrieval."""

    @patch("requests.get")
    def test_get_abstract_from_s2_success(self, mock_get):
        """Should return abstract from S2."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract": "This is the S2 abstract."}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            "abc123", None, limiter, backoff
        )

        assert result == "This is the S2 abstract."

    @patch("requests.get")
    def test_get_abstract_from_s2_no_abstract(self, mock_get):
        """Should return None if paper has no abstract."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract": None}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            "abc123", None, limiter, backoff
        )

        assert result is None

    @patch("requests.get")
    def test_get_abstract_from_s2_by_doi(self, mock_get):
        """Should use DOI:{doi} endpoint when no s2_id."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract": "Abstract found via DOI."}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            doi="10.1234/test", limiter=limiter, backoff=backoff
        )

        assert result == "Abstract found via DOI."
        call_url = mock_get.call_args[0][0]
        assert "DOI:10.1234/test" in call_url

    @patch("requests.get")
    def test_get_abstract_from_s2_prefers_id_over_doi(self, mock_get):
        """Should use s2_id when both s2_id and doi provided."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract": "Abstract by ID."}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            s2_id="abc123", doi="10.1234/test", limiter=limiter, backoff=backoff
        )

        assert result == "Abstract by ID."
        call_url = mock_get.call_args[0][0]
        assert "abc123" in call_url
        assert "DOI:" not in call_url

    @patch("requests.get")
    def test_get_abstract_from_s2_returns_none_no_identifiers(self, mock_get):
        """Should return None when neither s2_id nor doi provided."""
        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            limiter=limiter, backoff=backoff
        )

        assert result is None
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_get_abstract_from_s2_404(self, mock_get):
        """Should return None on 404."""
        mock_get.return_value = MagicMock(status_code=404)

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("semantic_scholar")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_s2(
            s2_id="nonexistent", limiter=limiter, backoff=backoff
        )

        assert result is None


class TestOpenAlexSource:
    """Tests for OpenAlex abstract retrieval."""

    @patch("requests.get")
    def test_get_abstract_from_openalex_success(self, mock_get):
        """Should reconstruct and return abstract from OpenAlex."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "abstract_inverted_index": {
                    "This": [0],
                    "is": [1],
                    "the": [2],
                    "OpenAlex": [3],
                    "abstract": [4],
                }
            }
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("openalex")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_openalex(
            "10.1234/test", None, limiter, backoff
        )

        assert result == "This is the OpenAlex abstract"

    @patch("requests.get")
    def test_get_abstract_from_openalex_strips_doi_prefix(self, mock_get):
        """Should handle DOI with https://doi.org/ prefix."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract_inverted_index": {"Test": [0]}}
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("openalex")
        backoff = ExponentialBackoff(max_attempts=2)

        get_abstract.get_abstract_from_openalex(
            "https://doi.org/10.1234/test", None, limiter, backoff
        )

        # Verify the URL was constructed correctly
        call_url = mock_get.call_args[0][0]
        assert "doi:10.1234/test" in call_url


class TestCoreSource:
    """Tests for CORE abstract retrieval."""

    @patch("requests.get")
    def test_get_abstract_from_core_by_doi(self, mock_get):
        """Should find abstract by DOI."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "abstract": "This is the CORE abstract which is long enough to pass the filter."
                }]
            }
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_core(
            doi="10.1234/test",
            limiter=limiter,
            backoff=backoff
        )

        assert "CORE abstract" in result

    @patch("requests.get")
    def test_get_abstract_from_core_by_title(self, mock_get):
        """Should find abstract by title and author."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "title": "Freedom of the Will and the Concept of a Person",
                    "abstract": "This paper examines the relationship between freedom and personhood in significant detail."
                }]
            }
        )

        import get_abstract
        from rate_limiter import get_limiter, ExponentialBackoff

        limiter = get_limiter("core")
        backoff = ExponentialBackoff(max_attempts=2)

        result = get_abstract.get_abstract_from_core(
            title="Freedom of the Will",
            author="Frankfurt",
            limiter=limiter,
            backoff=backoff
        )

        assert result is not None
        assert "freedom" in result.lower()


# =============================================================================
# Status-bearing probes (Task 5a)
# =============================================================================

def _limiter_and_backoff(name, max_attempts=1):
    from rate_limiter import get_limiter, ExponentialBackoff
    return get_limiter(name), ExponentialBackoff(max_attempts=max_attempts)


class TestProbeS2:
    """probe_s2 distinguishes 'the API answered and has none' from 'transport'."""

    @patch("requests.get")
    def test_ok_carries_text(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"abstract": "The S2 abstract."})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            "abc123", None, limiter, backoff) == ("ok", "The S2 abstract.")

    @patch("requests.get")
    def test_answered_without_abstract_is_empty(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"abstract": None})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            "abc123", None, limiter, backoff) == ("empty", None)

    @patch("requests.get")
    def test_404_is_empty(self, mock_get):
        """404 is the API answering authoritatively: it has no such record."""
        mock_get.return_value = MagicMock(status_code=404)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            "nope", None, limiter, backoff) == ("empty", None)

    @patch("requests.get")
    def test_no_identifier_is_empty_without_request(self, mock_get):
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            limiter=limiter, backoff=backoff) == ("empty", None)
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_http_error_is_transport(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            "abc123", None, limiter, backoff) == ("transport", None)

    @patch("requests.get")
    def test_connection_failure_is_transport(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("down")
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            "abc123", None, limiter, backoff) == ("transport", None)

    @patch("requests.get")
    def test_rate_limit_exhaustion_is_transport(self, mock_get):
        """A 429 we never got past is a non-answer, not an authoritative 'none'."""
        mock_get.return_value = MagicMock(
            status_code=429, headers={}, text="")
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            "abc123", None, limiter, backoff) == ("transport", None)

    @patch("requests.get")
    def test_malformed_payload_is_transport(self, mock_get):
        """A 200 whose body is not a JSON object told us nothing."""
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: ["not", "an", "object"])
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.probe_s2(
            "abc123", None, limiter, backoff) == ("transport", None)

    @patch("requests.get")
    def test_public_function_delegates_malformed_to_none(self, mock_get):
        """Delegation divergence, pinned: a wrong-shape 200 body used to raise
        out of the public function; it now reads as any other non-answer."""
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: ["not", "an", "object"])
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.get_abstract_from_s2(
            "abc123", None, limiter, backoff) is None

    @patch("requests.get")
    def test_public_function_maps_transport_to_none(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("semantic_scholar")

        assert get_abstract.get_abstract_from_s2(
            "abc123", None, limiter, backoff) is None


class TestProbeOpenAlex:
    """probe_openalex status vocabulary."""

    @patch("requests.get")
    def test_ok_carries_reconstructed_text(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract_inverted_index": {"A": [0], "test": [1]}})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")

        assert get_abstract.probe_openalex(
            "10.1/x", None, limiter, backoff) == ("ok", "A test")

    @patch("requests.get")
    def test_answered_without_index_is_empty(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"abstract_inverted_index": None})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")

        assert get_abstract.probe_openalex(
            "10.1/x", None, limiter, backoff) == ("empty", None)

    @patch("requests.get")
    def test_404_is_empty(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")

        assert get_abstract.probe_openalex(
            "10.1/x", None, limiter, backoff) == ("empty", None)

    @patch("requests.get")
    def test_budget_exhaustion_is_transport(self, mock_get):
        """Daily-budget exhaustion is a quota non-answer, not 'no abstract'."""
        mock_get.return_value = MagicMock(
            status_code=429, headers={"Retry-After": "81471"}, text="")
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")

        assert get_abstract.probe_openalex(
            "10.1/x", None, limiter, backoff) == ("transport", None)

    @patch("requests.get")
    def test_http_error_is_transport(self, mock_get):
        mock_get.return_value = MagicMock(status_code=503)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")

        assert get_abstract.probe_openalex(
            "10.1/x", None, limiter, backoff) == ("transport", None)

    @patch("requests.get")
    def test_malformed_index_is_transport(self, mock_get):
        """A truthy non-object index is malformed, not an absent abstract."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"abstract_inverted_index": "not-an-object"})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")

        assert get_abstract.probe_openalex(
            "10.1/x", None, limiter, backoff) == ("transport", None)

    @patch("requests.get")
    def test_public_function_maps_transport_to_none(self, mock_get):
        mock_get.return_value = MagicMock(status_code=503)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")

        assert get_abstract.get_abstract_from_openalex(
            "10.1/x", None, limiter, backoff) is None

    @patch("requests.get")
    def test_key_rides_as_bearer_header(self, mock_get, monkeypatch):
        monkeypatch.setenv("OPENALEX_API_KEY", "sekret")
        mock_get.return_value = MagicMock(status_code=404)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("openalex")
        get_abstract.probe_openalex("10.1/x", "e@x.org", limiter, backoff)
        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"Authorization": "Bearer sekret"}


class TestProbeCore:
    """probe_core status vocabulary."""

    @patch("requests.get")
    def test_ok_carries_text(self, mock_get):
        long_abstract = "A CORE abstract long enough to clear the length filter."
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [{"abstract": long_abstract}]})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("core")

        assert get_abstract.probe_core(
            doi="10.1/x", limiter=limiter, backoff=backoff) == ("ok", long_abstract)

    @patch("requests.get")
    def test_no_usable_result_is_empty(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": []})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("core")

        assert get_abstract.probe_core(
            doi="10.1/x", limiter=limiter, backoff=backoff) == ("empty", None)

    @patch("requests.get")
    def test_no_identifier_is_empty_without_request(self, mock_get):
        import get_abstract
        limiter, backoff = _limiter_and_backoff("core")

        assert get_abstract.probe_core(
            limiter=limiter, backoff=backoff) == ("empty", None)
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_http_error_is_transport(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("core")

        assert get_abstract.probe_core(
            doi="10.1/x", limiter=limiter, backoff=backoff) == ("transport", None)

    @patch("requests.get")
    def test_non_iterable_results_is_transport(self, mock_get):
        """Without the results-shape guard this raises TypeError instead."""
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": 5})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("core")

        assert get_abstract.probe_core(
            doi="10.1/x", limiter=limiter, backoff=backoff) == ("transport", None)

    @patch("requests.get")
    def test_non_object_result_entry_is_transport(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": ["not-an-object"]})
        import get_abstract
        limiter, backoff = _limiter_and_backoff("core")

        assert get_abstract.probe_core(
            doi="10.1/x", limiter=limiter, backoff=backoff) == ("transport", None)

    @patch("requests.get")
    def test_public_function_maps_transport_to_none(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500)
        import get_abstract
        limiter, backoff = _limiter_and_backoff("core")

        assert get_abstract.get_abstract_from_core(
            doi="10.1/x", limiter=limiter, backoff=backoff) is None


class TestBuildSourceContext:
    """The retry budgets are shared by resolve_abstract and
    enrich_bibliography.corroborate_abstract, so the keyed/keyless branch is
    pinned here rather than left to whichever caller happens to notice."""

    def test_keyless_s2_gets_the_longer_budget(self):
        import get_abstract

        ctx = get_abstract.build_source_context(None)
        assert (ctx["s2_backoff"].max_attempts,
                ctx["s2_backoff"].base_delay) == (5, 2.0)
        assert (ctx["other_backoff"].max_attempts,
                ctx["other_backoff"].base_delay) == (3, 1.0)

    def test_keyed_s2_gets_the_shorter_budget(self):
        import get_abstract

        ctx = get_abstract.build_source_context("some-key")
        assert (ctx["s2_backoff"].max_attempts,
                ctx["s2_backoff"].base_delay) == (3, 1.0)
        assert (ctx["other_backoff"].max_attempts,
                ctx["other_backoff"].base_delay) == (3, 1.0)


class TestPublicFunctionsGateOnStatus:
    """The text-or-None view keys on the STATUS, not on the probe happening
    to return None alongside a non-ok status."""

    def test_s2_discards_text_carried_with_a_non_ok_status(self):
        import get_abstract
        with patch.object(get_abstract, "probe_s2",
                          lambda **k: ("empty", "leaked text")):
            assert get_abstract.get_abstract_from_s2(s2_id="x") is None

    def test_openalex_discards_text_carried_with_a_non_ok_status(self):
        import get_abstract
        with patch.object(get_abstract, "probe_openalex",
                          lambda *a, **k: ("transport", "leaked text")):
            assert get_abstract.get_abstract_from_openalex(
                "10.1/x", None, None, None) is None

    def test_core_discards_text_carried_with_a_non_ok_status(self):
        import get_abstract
        with patch.object(get_abstract, "probe_core",
                          lambda **k: ("empty", "leaked text")):
            assert get_abstract.get_abstract_from_core(doi="10.1/x") is None


# =============================================================================
# Fallback Chain Tests
# =============================================================================

class TestFallbackChain:
    """Tests for fallback chain behavior."""

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_s2_checked_first_when_id_provided(
        self, mock_s2, mock_openalex, mock_core
    ):
        """S2 should be checked first when S2 ID is provided."""
        mock_s2.return_value = "S2 abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract == "S2 abstract"
        assert source == "s2"
        mock_s2.assert_called_once()
        mock_openalex.assert_not_called()
        mock_core.assert_not_called()

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_openalex_fallback_when_s2_fails(
        self, mock_s2, mock_openalex, mock_core
    ):
        """OpenAlex should be tried when S2 returns None."""
        mock_s2.return_value = None
        mock_openalex.return_value = "OpenAlex abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract == "OpenAlex abstract"
        assert source == "openalex"
        mock_s2.assert_called_once()
        mock_openalex.assert_called_once()
        mock_core.assert_not_called()

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_core_fallback_when_openalex_fails(
        self, mock_s2, mock_openalex, mock_core
    ):
        """CORE should be tried when OpenAlex returns None (with a CORE key
        configured — item 13 D3 gates CORE on the resolved core_api_key)."""
        mock_s2.return_value = None
        mock_openalex.return_value = None
        mock_core.return_value = "CORE abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test",
            core_api_key="test-key"
        )

        assert abstract == "CORE abstract"
        assert source == "core"

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_returns_none_when_all_fail(
        self, mock_s2, mock_openalex, mock_core
    ):
        """Should return (None, None) when all sources fail."""
        mock_s2.return_value = None
        mock_openalex.return_value = None
        mock_core.return_value = None

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract is None
        assert source is None

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_s2_tried_via_doi_when_no_id(
        self, mock_s2, mock_openalex, mock_core
    ):
        """S2 should be tried via DOI when no S2 ID provided."""
        mock_s2.return_value = "S2 abstract via DOI"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            doi="10.1234/test"
        )

        assert abstract == "S2 abstract via DOI"
        assert source == "s2"
        mock_s2.assert_called_once()
        # Verify doi was passed to s2
        call_kwargs = mock_s2.call_args
        assert call_kwargs.kwargs.get("doi") == "10.1234/test"
        mock_openalex.assert_not_called()

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_s2_by_id_takes_priority_over_doi(
        self, mock_s2, mock_openalex, mock_core
    ):
        """S2 ID should be passed alongside DOI, with ID taking priority."""
        mock_s2.return_value = "S2 abstract by ID"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            s2_id="abc123",
            doi="10.1234/test"
        )

        assert abstract == "S2 abstract by ID"
        assert source == "s2"
        # Both s2_id and doi should be passed
        call_kwargs = mock_s2.call_args
        assert call_kwargs.kwargs.get("s2_id") == "abc123"
        assert call_kwargs.kwargs.get("doi") == "10.1234/test"

    @patch("get_abstract.get_abstract_from_core")
    @patch("get_abstract.get_abstract_from_openalex")
    @patch("get_abstract.get_abstract_from_s2")
    def test_full_fallback_s2_doi_to_openalex_to_core(
        self, mock_s2, mock_openalex, mock_core
    ):
        """Full fallback: S2-by-DOI -> OpenAlex -> CORE (with a CORE key
        configured — item 13 D3 gates CORE on the resolved core_api_key)."""
        mock_s2.return_value = None
        mock_openalex.return_value = None
        mock_core.return_value = "CORE abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            doi="10.1234/test",
            title="Test Paper",
            author="Author",
            core_api_key="test-key"
        )

        assert abstract == "CORE abstract"
        assert source == "core"
        mock_s2.assert_called_once()
        mock_openalex.assert_called_once()
        mock_core.assert_called_once()

    @patch("get_abstract.get_abstract_from_core")
    def test_title_only_uses_core(self, mock_core):
        """Should use CORE when only title provided (with a CORE key
        configured — item 13 D3 gates CORE on the resolved core_api_key)."""
        mock_core.return_value = "CORE abstract"

        import get_abstract

        abstract, source = get_abstract.resolve_abstract(
            title="Freedom of the Will",
            author="Frankfurt",
            core_api_key="test-key"
        )

        assert abstract == "CORE abstract"
        assert source == "core"


# =============================================================================
# CLI Tests
# =============================================================================

class TestCLI:
    """Tests for command-line interface."""

    def test_cli_requires_identifier(self, run_skill_script):
        """Should fail when no identifier provided."""
        result = run_skill_script("get_abstract.py")
        assert result.returncode == 2

        output = result.json
        assert output["status"] == "error"
        assert "Must provide" in output["error"]["message"]

    def test_cli_help(self, run_skill_script):
        """Should show help with --help."""
        result = run_skill_script("get_abstract.py", "--help")
        assert result.returncode == 0
        assert "abstract" in result.stdout.lower()


# =============================================================================
# Progress Output Tests
# =============================================================================

class TestProgressOutput:
    """Tests for progress/status output to stderr."""

    def test_log_progress_to_stderr(self):
        """Progress messages should go to stderr."""
        import get_abstract
        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            get_abstract.log_progress("Test message")

        output = captured.getvalue()
        assert "[get_abstract.py]" in output
        assert "Test message" in output
