"""Item 13 D1: NDPR match tightening (stopword filter + tiered acceptance).
The real Wallace/Adam-Smith mismatch slug is the load-bearing negative."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills/philosophy-research/scripts"))
import search_ndpr  # noqa: E402


# (title, author, slug, expected_accept)
CASES = [
    # positives
    ("Being and Time", "Heidegger",
     "being-and-time-heideggers-magnum-opus", True),            # subtitle-bearing slug, coverage 1.0
    ("Reasons and Persons", None, "reasons-and-persons", True),  # no author, coverage 1.0
    ("Practical Reason", "Korsgaard",
     "practical-ethics-korsgaard", True),                       # author-confirmed 0.6 tier (0.65)
    # negatives
    ("Responsibility and the Moral Sentiments", None,
     "adam-smith-s-pluralism-rationality-education-and-the-moral-sentiments", False),  # real Wallace pair, 0.667 < 0.75
    ("Practical Reason", None, "practical-ethics-korsgaard", False),  # same slug, no author -> 0.5 < 0.75
    ("On Liberty", None, "the-nicomachean-ethics", False),       # single-token title, no author -> 0.0
]


@pytest.mark.parametrize("title,author,slug,expected", CASES)
def test_ndpr_acceptance_corpus(monkeypatch, title, author, slug, expected):
    urls = [f"https://ndpr.nd.edu/reviews/{slug}/"]
    monkeypatch.setattr(search_ndpr, "fetch_sitemap", lambda limiter, backoff: urls)
    result = search_ndpr.search_ndpr(title, author=author)
    assert (result is not None) is expected


def test_score_match_returns_score_and_confirmation():
    score, confirmed = search_ndpr.score_match(
        "being and time", "being-and-time-heideggers-magnum-opus", "Heidegger"
    )
    assert isinstance(score, float)
    assert confirmed is True
    assert score >= 0.75


def test_stopwords_drop_and_the():
    assert "and" not in search_ndpr.title_to_tokens("responsibility and the moral sentiments")
    assert "the" not in search_ndpr.title_to_tokens("responsibility and the moral sentiments")
    assert "moral" in search_ndpr.title_to_tokens("responsibility and the moral sentiments")
