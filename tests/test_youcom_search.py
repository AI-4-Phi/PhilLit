#!/usr/bin/env python3
"""
Tests for the keyless You.com site-search provider (youcom_search.py).

Network-free: every HTTP interaction is mocked. The SSE payloads mirror the
endpoint's live wire format (notifications/message events preceding the
id-matched JSON-RPC result, tool result JSON in content[0].text).
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from test_utils import SCRIPTS_DIR  # noqa: F401  (inserts SCRIPTS_DIR into sys.path)

import youcom_search  # noqa: E402
from brave_search import SEP_CONFIG, PHILPAPERS_CONFIG  # noqa: E402
from rate_limiter import ExponentialBackoff  # noqa: E402


def sse_body(result: dict, notifications: int = 1) -> str:
    """SSE text/event-stream body: notifications, then the id-matched result."""
    lines = []
    for _ in range(notifications):
        lines.append("event: message")
        lines.append("data: " + json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {"progress": 1}}))
    lines.append("event: message")
    lines.append("data: " + json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}))
    return "\n".join(lines) + "\n\n"


def tool_result(web: list, news: list | None = None) -> dict:
    """MCP tools/call result for you-search with the web hits embedded as text JSON."""
    payload = {"results": {"web": web}}
    if news is not None:
        payload["results"]["news"] = news
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def mock_200(result: dict) -> MagicMock:
    return MagicMock(status_code=200, text=sse_body(result))


def fake_limiter() -> MagicMock:
    """Stand-in limiter: no file locks, no waits."""
    return MagicMock()


def fast_backoff() -> ExponentialBackoff:
    return ExponentialBackoff(max_attempts=2, base_delay=0.01)


def run_youcom(query="free will", limit=20, config=SEP_CONFIG, api_key=None):
    return youcom_search.youcom_site_search(
        query=query,
        limit=limit,
        config=config,
        limiter=fake_limiter(),
        backoff=fast_backoff(),
        api_key=api_key,
    )


class TestYoucomOutputMapping:
    """Mapping of You.com web hits into the brave_search result format."""

    def test_sep_entry_extraction(self):
        """SEP hit: entry id from URL, parenthesized site suffix stripped, snippets from highlights."""
        item = {
            "url": "https://plato.stanford.edu/entries/freewill/",
            "title": "Free Will (Stanford Encyclopedia of Philosophy)",
            "description": "",
            "page_age": "2024-01-01T00:00:00",
            "contents": {"highlights": ["Free will is a classical problem of philosophy.", "Second highlight."]},
        }
        result = youcom_search.format_youcom_result(item, SEP_CONFIG)

        assert result["entry_name"] == "freewill"
        assert result["title"] == "Free Will"
        assert result["url"] == item["url"]
        assert result["snippet"] == "Free will is a classical problem of philosophy."
        assert result["extra_snippets"] == ["Second highlight."]
        assert result["page_age"] == "2024-01-01T00:00:00"

    def test_snippet_prefers_description(self):
        """Description (when present) is the snippet; highlights become extras."""
        item = {
            "url": "https://plato.stanford.edu/entries/compatibilism/",
            "title": "Compatibilism - Stanford Encyclopedia of Philosophy",
            "description": "A survey of compatibilist positions.",
            "contents": {"highlights": ["Highlight one.", "Highlight two."]},
        }
        result = youcom_search.format_youcom_result(item, SEP_CONFIG)

        assert result["snippet"] == "A survey of compatibilist positions."
        assert result["extra_snippets"] == ["Highlight one.", "Highlight two."]
        assert result["entry_name"] == "compatibilism"

    def test_long_highlight_truncated(self):
        """Highlights longer than the snippet cap are cut at a word boundary."""
        item = {
            "url": "https://plato.stanford.edu/entries/turing-test/",
            "title": "Turing Test (Stanford Encyclopedia of Philosophy)",
            "description": "",
            "contents": {"highlights": ["word " * 200]},
        }
        result = youcom_search.format_youcom_result(item, SEP_CONFIG)

        assert len(result["snippet"]) <= youcom_search.SNIPPET_MAX + 3
        assert result["snippet"].endswith("...")
        assert result["entry_name"] == "turing-test"

    def test_non_entry_url_dropped_by_caller(self):
        """A hit without a recognizable entry URL keeps id None; the search loop drops it."""
        item = {"url": "https://plato.stanford.edu/other/page.html", "title": "Other", "description": "x"}
        result = youcom_search.format_youcom_result(item, SEP_CONFIG)
        assert result["entry_name"] is None


class TestYoucomSiteSearch:
    """youcom_site_search against mocked SSE responses."""

    @patch("youcom_search.requests.post")
    def test_keyless_search_returns_results(self, mock_post):
        """Keyless call hits the free-profile URL with no Authorization header."""
        mock_post.return_value = mock_200(tool_result(web=[
            {
                "url": "https://plato.stanford.edu/entries/freewill/",
                "title": "Free Will (Stanford Encyclopedia of Philosophy)",
                "description": "",
                "contents": {"highlights": ["Free will overview."]},
            },
            {
                "url": "https://plato.stanford.edu/entries/moral-responsibility/",
                "title": "Moral Responsibility (Stanford Encyclopedia of Philosophy)",
                "description": "Survey of moral responsibility.",
            },
        ]))
        results, errors = run_youcom("free will")

        assert errors == []
        assert [r["entry_name"] for r in results] == ["freewill", "moral-responsibility"]
        call = mock_post.call_args
        assert call.args[0] == youcom_search.YOUCOM_MCP_FREE_URL
        assert "Authorization" not in call.kwargs["headers"]
        args = call.kwargs["json"]["params"]["arguments"]
        assert args["query"] == "site:plato.stanford.edu free will"
        assert args["count"] == 20

    @patch("youcom_search.requests.post")
    def test_authenticated_search_uses_bearer_and_auth_url(self, mock_post):
        """With api_key the authenticated endpoint is used with a bearer token."""
        mock_post.return_value = mock_200(tool_result(web=[
            {"url": "https://plato.stanford.edu/entries/freewill/", "title": "Free Will (Stanford Encyclopedia of Philosophy)", "description": "d"},
        ]))
        results, _ = run_youcom(api_key="test-key")

        assert len(results) == 1
        call = mock_post.call_args
        assert call.args[0] == youcom_search.YOUCOM_MCP_URL
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-key"

    @patch("youcom_search.requests.post")
    def test_count_clamped_to_cap(self, mock_post):
        """limit above the per-call cap is clamped in the request."""
        mock_post.return_value = mock_200(tool_result(web=[]))
        run_youcom(limit=50)

        assert mock_post.call_args.kwargs["json"]["params"]["arguments"]["count"] == youcom_search.YOUCOM_COUNT_CAP

    @patch("youcom_search.requests.post")
    def test_url_path_filter_and_limit(self, mock_post):
        """PhilPapers: /archive/ links are dropped, /rec/ links kept, limit respected."""
        rec = {
            "url": "https://philpapers.org/rec/HOLOCJ",
            "title": "The Consequence Argument",
            "description": "A record of the consequence argument.",
        }
        archive = {
            "url": "https://philpapers.org/archive/HOLOCJ.pdf",
            "title": "The Consequence Argument (PDF)",
            "description": "Archived copy.",
        }
        mock_post.return_value = mock_200(tool_result(web=[rec, archive, dict(rec, url="https://philpapers.org/rec/SECONDD")]))
        results, errors = run_youcom(query="consequence argument", limit=1, config=PHILPAPERS_CONFIG)

        assert errors == []
        assert len(results) == 1
        assert results[0]["url"] == rec["url"]
        assert results[0]["philpapers_id"] == "HOLOCJ"

    @patch("youcom_search.requests.post")
    def test_news_results_ignored(self, mock_post):
        """Only the web section feeds site search; news hits are ignored."""
        mock_post.return_value = mock_200(tool_result(
            web=[{"url": "https://plato.stanford.edu/entries/freewill/", "title": "Free Will (Stanford Encyclopedia of Philosophy)", "description": "d"}],
            news=[{"url": "https://plato.stanford.edu/entries/x/", "title": "News hit", "description": "d"}],
        ))
        results, _ = run_youcom()
        assert len(results) == 1

    @patch("youcom_search.requests.post")
    def test_rate_limit_returns_partial(self, mock_post):
        """Persistent 429s exhaust backoff and return a recoverable rate_limit error."""
        mock_post.return_value = MagicMock(status_code=429, text="")
        results, errors = run_youcom()

        assert results == []
        assert errors[0]["type"] == "rate_limit"
        assert errors[0]["recoverable"] is True

    @patch("youcom_search.requests.post")
    def test_server_error_returns_partial(self, mock_post):
        """Persistent 5xx exhaust backoff and return a recoverable server_error."""
        mock_post.return_value = MagicMock(status_code=503, text="")
        results, errors = run_youcom()

        assert results == []
        assert errors[0]["type"] == "server_error"

    @patch("youcom_search.requests.post")
    def test_network_error_returns_partial(self, mock_post):
        """Persistent connection failures return a recoverable network_error."""
        import requests as requests_module

        mock_post.side_effect = requests_module.exceptions.ConnectionError("connection refused")
        results, errors = run_youcom()

        assert results == []
        assert errors[0]["type"] == "network_error"

    @patch("youcom_search.requests.post")
    def test_invalid_key_raises_value_error(self, mock_post):
        """401 maps to the config-error ValueError the CLIs report as exit 2."""
        mock_post.return_value = MagicMock(status_code=401, text="")
        with pytest.raises(ValueError, match="Invalid YDC_API_KEY"):
            run_youcom(api_key="bad-key")

    @patch("youcom_search.requests.post")
    def test_tool_error_raises_runtime_error(self, mock_post):
        """An isError tool result surfaces as a RuntimeError (CLI exit 3)."""
        mock_post.return_value = mock_200({"content": [{"type": "text", "text": "quota exceeded"}], "isError": True})
        with pytest.raises(RuntimeError, match="quota exceeded"):
            run_youcom()


class TestYoucomJsonrpcParsing:
    """SSE/JSON-RPC response parsing."""

    def test_parse_skips_notifications(self):
        """Interleaved notification events are skipped; the id-matched result is returned."""
        result = youcom_search._parse_jsonrpc_result(sse_body(tool_result(web=[]), notifications=3), msg_id=1)
        assert "content" in result

    def test_parse_plain_json_body(self):
        """A plain (non-SSE) JSON body still yields the result."""
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": tool_result(web=[])})
        result = youcom_search._parse_jsonrpc_result(body, msg_id=1)
        assert "content" in result

    def test_parse_jsonrpc_error_raises(self):
        """A JSON-RPC-level error raises RuntimeError."""
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "boom"}})
        with pytest.raises(RuntimeError, match="boom"):
            youcom_search._parse_jsonrpc_result(body, msg_id=1)

    def test_parse_missing_result_raises(self):
        """No id-matched result in the stream raises RuntimeError."""
        with pytest.raises(RuntimeError, match="no result"):
            youcom_search._parse_jsonrpc_result("data: not-json\n\n", msg_id=1)


class TestProviderDispatch:
    """CLI provider selection in search_sep.py (in-process, network-free)."""

    def test_youcom_flag_dispatch_and_source(self, capsys):
        """--provider youcom calls youcom_site_search and reports sep_via_youcom."""
        import search_sep

        mock_results = [{
            "title": "Free Will",
            "url": "https://plato.stanford.edu/entries/freewill/",
            "entry_name": "freewill",
            "snippet": "Overview.",
            "page_age": None,
        }]
        with patch.object(search_sep.sys, "argv", ["search_sep.py", "free will", "--provider", "youcom"]):
            with patch.object(search_sep, "youcom_site_search", return_value=(mock_results, [])) as mock_youcom:
                with pytest.raises(SystemExit) as excinfo:
                    search_sep.main()

        assert excinfo.value.code == 0
        mock_youcom.assert_called_once()
        assert mock_youcom.call_args.kwargs["api_key"] is None  # keyless by default
        output = json.loads(capsys.readouterr().out)
        assert output["source"] == "sep_via_youcom"
        assert output["status"] == "success"
        assert output["query"] == "free will"

    def test_env_provider_youcom(self, capsys):
        """PHILLIT_SEARCH_PROVIDER=youcom selects youcom without the CLI flag."""
        import search_sep

        with patch.dict(os.environ, {"PHILLIT_SEARCH_PROVIDER": "youcom", "YDC_API_KEY": "", "BRAVE_API_KEY": ""}):
            with patch.object(search_sep.sys, "argv", ["search_sep.py", "free will"]):
                with patch.object(search_sep, "youcom_site_search", return_value=([], [{"type": "rate_limit", "message": "limited", "recoverable": True}])):
                    with pytest.raises(SystemExit) as excinfo:
                        search_sep.main()

        assert excinfo.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["source"] == "sep_via_youcom"
        assert output["status"] == "partial"

    def test_brave_still_default(self, capsys):
        """Unset provider keeps the brave path and the sep_via_brave source."""
        import search_sep

        with patch.dict(os.environ, {"PHILLIT_SEARCH_PROVIDER": "", "BRAVE_API_KEY": "test-key"}):
            with patch.object(search_sep.sys, "argv", ["search_sep.py", "free will"]):
                with patch.object(search_sep, "brave_site_search", return_value=([], [])) as mock_brave:
                    with pytest.raises(SystemExit) as excinfo:
                        search_sep.main()

        mock_brave.assert_called_once()
        assert excinfo.value.code == 1  # not_found: empty brave result, unchanged default
        output = json.loads(capsys.readouterr().out)
        assert output["source"] == "sep_via_brave"

    def test_brave_key_error_unchanged(self, capsys):
        """Without a Brave key and provider unset, the config error is identical to today."""
        import search_sep

        with patch.dict(os.environ, {"PHILLIT_SEARCH_PROVIDER": "", "BRAVE_API_KEY": ""}):
            with patch.object(search_sep.sys, "argv", ["search_sep.py", "free will"]):
                with pytest.raises(SystemExit) as excinfo:
                    search_sep.main()

        assert excinfo.value.code == 2
        output = json.loads(capsys.readouterr().out)
        assert output["errors"][0]["message"] == "BRAVE_API_KEY not set"
