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
