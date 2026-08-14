"""Item 2: web-source evidence — URL extraction, capture checks, existence.

Pure logic, no network: `evaluate_existence` takes its two HTTP callables by
injection, and every test here supplies stubs.
"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import web_evidence as wv


# ---------------------------------------------------------------------------
# extract_url / normalize_url / registered_domain
# ---------------------------------------------------------------------------

def test_extract_prefers_url_field_over_howpublished():
    assert wv.extract_url({"url": "https://a.example/x",
                           "howpublished": "https://b.example/y"}) == "https://a.example/x"


def test_extract_unwraps_latex_url_macro():
    assert wv.extract_url({"url": r"\url{https://a.example/x}"}) == "https://a.example/x"


def test_extract_finds_url_after_prose_in_howpublished():
    # 16 corpus entries carry the URL mid-field, after descriptive prose.
    got = wv.extract_url({"howpublished": "Blog post, https://a.example/x"})
    assert got == "https://a.example/x"


def test_extract_strips_trailing_sentence_punctuation():
    assert wv.extract_url({"howpublished": "See https://a.example/x."}) == "https://a.example/x"


def test_extract_unescapes_latex_in_url():
    assert wv.extract_url({"url": r"https://a.example/a\_b?x=1\&y=2"}) == "https://a.example/a_b?x=1&y=2"


def test_extract_returns_none_without_a_url():
    assert wv.extract_url({"howpublished": "Unpublished manuscript"}) is None


def test_normalize_is_case_insensitive_on_host_and_drops_default_port():
    a = wv.normalize_url("HTTPS://Example.COM:443/Path/")
    b = wv.normalize_url("https://example.com/Path")
    assert a == b


def test_normalize_keeps_path_case_and_query():
    n = wv.normalize_url("https://example.com/AbC?q=1")
    assert "AbC" in n and "q=1" in n


def test_normalize_does_not_raise_on_a_malformed_port():
    # urlsplit(...).port raises ValueError on an out-of-range port, and
    # _URL_RE will happily capture `https://a.example:99999/x` out of a bib
    # field. This must degrade, not throw (external review, Q7.1).
    assert wv.normalize_url("https://a.example:99999/x")


def test_registered_domain_takes_two_labels_normally():
    assert wv.registered_domain("https://blog.example.com/x") == "example.com"


def test_registered_domain_separates_two_github_pages_tenants():
    a = wv.registered_domain("https://alice.github.io/paper")
    b = wv.registered_domain("https://bob.github.io/parked")
    assert a != b, "cross-tenant redirect would otherwise read as same-domain"


def test_registered_domain_handles_two_part_country_suffixes():
    a = wv.registered_domain("https://a.example.co.uk/x")
    b = wv.registered_domain("https://b.other.co.uk/y")
    assert a == "example.co.uk" and b == "other.co.uk"


# ---------------------------------------------------------------------------
# check_capture: the five rule-(b) checks
# ---------------------------------------------------------------------------

def _cap(**kw):
    base = {"url": "https://a.example/x", "final_url": "https://a.example/x",
            "http_status": 200, "provenance": "script",
            "title": "The Basic AI Drives",
            "text": "word " * 100 + "acquire steel manipulators and energy resources for itself"}
    base.update(kw)
    return base


_SPAN = "acquire steel manipulators and energy resources for itself"
_TITLE = "The Basic AI Drives"


def test_capture_passes_all_five_checks():
    assert wv.check_capture(_cap(), "https://a.example/x", _TITLE, _SPAN) == (True, "ok")


def test_capture_bound_to_a_different_url_fails():
    ok, why = wv.check_capture(_cap(), "https://other.example/y", _TITLE, _SPAN)
    assert (ok, why) == (False, "url_mismatch")


def test_capture_matching_on_final_url_after_redirect_passes():
    cap = _cap(url="https://a.example/old", final_url="https://a.example/new")
    ok, _ = wv.check_capture(cap, "https://a.example/old", _TITLE, _SPAN)
    assert ok


def test_an_empty_entry_url_cannot_bind_to_a_urlless_capture():
    # Unreachable from the barrier, but check_capture is a public interface.
    ok, why = wv.check_capture(_cap(url="", final_url=""), "", _TITLE, _SPAN)
    assert (ok, why) == (False, "url_mismatch")


def test_script_capture_with_non_2xx_status_fails_on_status_not_length():
    ok, why = wv.check_capture(_cap(http_status=403), "https://a.example/x", _TITLE, _SPAN)
    assert (ok, why) == (False, "bad_status")


def test_stdin_capture_has_no_status_and_is_not_status_checked():
    cap = _cap(provenance="agent", http_status=None, title="",
               text=_TITLE + ". " + "word " * 100 + _SPAN)
    assert wv.check_capture(cap, "https://a.example/x", _TITLE, _SPAN) == (True, "ok")


def test_an_unrecognized_provenance_is_still_status_checked():
    """Only an explicit "agent" capture skips the status check, so an unknown
    provenance string cannot buy a free pass."""
    ok, why = wv.check_capture(_cap(provenance="handwritten", http_status=None),
                               "https://a.example/x", _TITLE, _SPAN)
    assert (ok, why) == (False, "bad_status")


def test_boilerplate_interstitial_fails():
    cap = _cap(text="Just a moment... " + "word " * 100 + _SPAN)
    ok, why = wv.check_capture(cap, "https://a.example/x", _TITLE, _SPAN)
    assert (ok, why) == (False, "boilerplate")


def test_thin_text_fails():
    ok, why = wv.check_capture(_cap(text="too short"), "https://a.example/x", _TITLE, _SPAN)
    assert (ok, why) == (False, "thin")


def test_title_anchor_rejects_a_capture_of_the_wrong_page():
    """A wrong-page capture with a perfectly GOOD title -- so the diagnosis
    must be title_mismatch, never 'untitled'."""
    ok, why = wv.check_capture(_cap(title="Homepage - Example Corp"),
                               "https://a.example/x", _TITLE, _SPAN)
    assert (ok, why) == (False, "title_mismatch")


def test_an_error_record_is_a_fetch_error_not_a_missing_capture():
    """Attempted-and-failed stays distinguishable from never-attempted: the
    spec writes failure records for exactly this reason."""
    ok, why = wv.check_capture({"url": "https://a.example/x",
                                "error": "fetch-failed:timeout"},
                               "https://a.example/x", _TITLE, _SPAN)
    assert (ok, why) == (False, "fetch_error")


def test_a_missing_capture_is_no_capture():
    ok, why = wv.check_capture(None, "https://a.example/x", _TITLE, _SPAN)
    assert (ok, why) == (False, "no_capture")


def test_span_absent_from_capture_fails():
    ok, why = wv.check_capture(_cap(), "https://a.example/x", _TITLE,
                               "a span the page never contained at all")
    assert (ok, why) == (False, "span_unverified")


def test_every_listed_span_must_match_not_merely_one():
    spans = _SPAN + " || invented text that is not on the page"
    ok, why = wv.check_capture(_cap(), "https://a.example/x", _TITLE, spans)
    assert (ok, why) == (False, "span_unverified")


def test_span_matching_ignores_whitespace_case_and_latex_escapes():
    cap = _cap(text="word " * 100 + "Acquire  steel manipulators & energy resources for itself")
    ok, _ = wv.check_capture(cap, "https://a.example/x", _TITLE,
                             r"acquire steel manipulators \& energy resources for itself")
    assert ok


def test_a_span_shorter_than_the_floor_is_malformed():
    ok, why = wv.check_capture(_cap(), "https://a.example/x", _TITLE, "steel")
    assert (ok, why) == (False, "span_malformed")


def test_missing_span_field_fails_closed():
    ok, why = wv.check_capture(_cap(), "https://a.example/x", _TITLE, "")
    assert (ok, why) == (False, "span_malformed")


def test_more_than_two_spans_is_malformed_not_unverified():
    spans = " || ".join([_SPAN] * 3)
    ok, why = wv.check_capture(_cap(), "https://a.example/x", _TITLE, spans)
    assert (ok, why) == (False, "span_malformed")


def test_load_capture_reads_the_workspace_path(tmp_path):
    d = tmp_path / "intermediate_files" / "web_captures"
    d.mkdir(parents=True)
    (d / "k.json").write_text('{"url": "u", "text": "t"}', encoding="utf-8")
    assert wv.load_capture(tmp_path, "k")["url"] == "u"


def test_load_capture_returns_none_for_absent_or_unparseable(tmp_path):
    assert wv.load_capture(tmp_path, "missing") is None
    d = tmp_path / "intermediate_files" / "web_captures"
    d.mkdir(parents=True)
    (d / "bad.json").write_text("{not json", encoding="utf-8")
    assert wv.load_capture(tmp_path, "bad") is None
