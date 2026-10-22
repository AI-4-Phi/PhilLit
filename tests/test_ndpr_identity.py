"""NDPR review identity: a review's text is a book's abstract only when the
review is OF that book.

The measured defect (2026-10-22): slug scoring is one-directional title
coverage, so a later book whose slug holds every title word scored 1.0 for an
old canonical book NDPR never reviewed (Longino 1990 -> Kochan's Science as
Social Existence), and among 1.0 ties the first slug in sitemap order won
over the right one (Thompson's Mind in Life -> McCulloch's The Life of the
Mind). The HEADERS below are the real bibliographic headers of the pages
those searches reached; the expected verdicts were checked by hand.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills/philosophy-research/scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills/literature-review/scripts"))
import fetch_ndpr  # noqa: E402
import search_ndpr  # noqa: E402


# (entry title, entry surname, header authors, header title, expected)
HEADERS = [
    # right book
    ("Injustice and the Reproduction of History: Structural Inequalities, Gender and Redress", "Nuti",
     "Alasia Nuti", "Injustice and the Reproduction of History: Structural Inequalities, Gender and Redress", True),
    ("Radicalizing Enactivism: Basic Minds without Content", "Hutto",
     "Daniel D. Hutto and Erik Myin", "Radicalizing Enactivism: Basic Minds Without Content", True),
    ("Action in Perception", "Noë", "Alva Noë", "Action in Perception", True),
    ("Dark Ghettos: Injustice, Dissent, and Reform", "Shelby",
     "Tommie Shelby", "Dark Ghettos: Injustice, Dissent, and Reform", True),
    ("When All Else Fails: The Ethics of Resistance to State Injustice", "Brennan",
     "Jason Brennan", "When All Else Fails: The Ethics of Resistance to State Injustice", True),
    ("Postphenomenological Investigations: Essays on Human-Technology Relations", "Rosenberger",
     "Robert Rosenberger and Peter-Paul Verbeek (eds.)",
     "Postphenomenological Investigations: Essays on Human-Technology Relations", True),
    ("Mind in Life: Biology, Phenomenology, and the Sciences of Mind", "Thompson",
     "Evan Thompson", "Mind in Life: Biology, Phenomenology, and the Sciences of Mind", True),
    # "and" in one title only; surname-first header
    ("Autonomy, Gender, Politics", "Friedman",
     "Friedman, Marilyn", "Autonomy, Gender, and Politics", True),
    # the bib carries a subtitle the header lacks
    ("Meaning in Life: An Analytic Study", "Metz", "Thaddeus Metz", "Meaning in Life", True),
    # a hyphen folds to a space on both sides
    ("Being-in-the-World: A Commentary", "Dreyfus",
     "Hubert L. Dreyfus", "Being in the World", True),
    # wrong book
    ("Mind in Life: Biology, Phenomenology, and the Sciences of Mind", "Thompson",
     "McCulloch, Gregory", "The Life of the Mind: An Essay on Phenomenological Externalism", False),
    ("Autonomy, Gender, Politics", "Friedman",
     "Amy Allen", "The Politics of Our Selves: Power, Autonomy, and Gender in Contemporary Critical Theory", False),
    ("Science as Social Knowledge: Values and Objectivity in Scientific Inquiry", "Longino",
     "Jeff Kochan", "Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge", False),
    ("The Scientific Image", "van Fraassen",
     "Dominic Murphy", "Psychiatry in the Scientific Image", False),
    ("Meaning in Life: An Analytic Study", "Metz",
     "Nick Bostrom", "Deep Utopia: Life and Meaning in a Solved World", False),
    ("The Morality of Law", "Fuller",
     "John Keown and Robert P. George (eds.)", "Reason, Morality, and Law: The Philosophy of John Finnis", False),
    ("The Structure of Scientific Revolutions", "Kuhn",
     "Hanne Andersen, Peter Barker, and Xiang Chen", "The Cognitive Structure of Scientific Revolutions", False),
    # the surname AND the whole title occur, but the book is a commentary
    ("The Structure of Scientific Revolutions", "Kuhn",
     "Vasso Kindi and Theodore Arabatzis (eds.)",
     "Kuhn's The Structure of Scientific Revolutions Revisited", False),
    # right title, wrong author (a second book of the same name)
    ("Action in Perception", "Noë", "Jane Doe", "Action in Perception", False),
]


@pytest.mark.parametrize("title,surname,authors,book_title,expected", HEADERS)
def test_review_matches_measured_headers(title, surname, authors, book_title, expected):
    books = [{"authors": authors, "title": book_title}]
    assert search_ndpr.review_matches(books, title, surname) is expected


def test_review_matches_refuses_a_multi_book_review():
    """Its opening paragraphs may be about the other book."""
    books = [{"authors": "Jeff Kochan", "title": "Science as Social Existence"},
             {"authors": "Helen E. Longino", "title": "Science as Social Knowledge"}]
    assert not search_ndpr.review_matches(
        books, "Science as Social Knowledge: Values and Objectivity", "Longino")


def test_review_matches_folds_umlauts_both_ways():
    books = [{"authors": "Thomas Mueller", "title": "Ein Buch"}]
    assert search_ndpr.review_matches(books, "Ein Buch", "Müller")


def test_review_matches_needs_a_surname_and_a_header():
    books = [{"authors": "Alva Noë", "title": "Action in Perception"}]
    assert not search_ndpr.review_matches(books, "Action in Perception", "")
    assert not search_ndpr.review_matches(books, "Action in Perception", None)
    assert not search_ndpr.review_matches([], "Action in Perception", "Noë")


def test_surname_is_a_whole_word():
    books = [{"authors": "Paul Noel", "title": "Action in Perception"}]
    assert not search_ndpr.review_matches(books, "Action in Perception", "Noe")


# --- candidate ranking --------------------------------------------------------

def _sitemap(monkeypatch, slugs):
    urls = [f"https://ndpr.nd.edu/reviews/{s}/" for s in slugs]
    monkeypatch.setattr(search_ndpr, "fetch_sitemap", lambda limiter, backoff: urls)


def test_specific_slug_outranks_an_earlier_tie(monkeypatch):
    """Both slugs score 1.0; sitemap order used to decide."""
    _sitemap(monkeypatch, [
        "the-life-of-the-mind-an-essay-on-phenomenological-externalism",
        "mind-in-life-biology-phenomenology-and-the-sciences-of-mind",
    ])
    found = search_ndpr.search_ndpr_candidates(
        "Mind in Life: Biology, Phenomenology, and the Sciences of Mind", "Thompson")
    assert found[0]["slug"] == "mind-in-life-biology-phenomenology-and-the-sciences-of-mind"
    assert search_ndpr.search_ndpr(
        "Mind in Life: Biology, Phenomenology, and the Sciences of Mind", "Thompson"
    )["slug"] == "mind-in-life-biology-phenomenology-and-the-sciences-of-mind"


def test_author_in_slug_breaks_a_saturated_tie(monkeypatch):
    _sitemap(monkeypatch, ["ethics-a-new-reading", "ethics-spinoza"])
    found = search_ndpr.search_ndpr_candidates("Ethics: A New Reading", "Spinoza")
    assert found[0]["slug"] == "ethics-spinoza"


def test_candidates_are_capped_and_thresholded(monkeypatch):
    _sitemap(monkeypatch, [
        "free-will-agency-and-meaning-in-life",
        "deep-utopia-life-and-meaning-in-a-solved-world",
        "meaning-in-life-and-why-it-matters",
        "meaning-in-life",
        "the-meaning-of-it-all",
    ])
    found = search_ndpr.search_ndpr_candidates("Meaning in Life: An Analytic Study", "Metz")
    assert len(found) == search_ndpr.MAX_CANDIDATES
    assert found[0]["slug"] == "meaning-in-life"
    assert "the-meaning-of-it-all" not in [c["slug"] for c in found]


# --- header extraction --------------------------------------------------------

KOCHAN_PAGE = """<html><head>
<meta name="search_authors" content="Jeff Kochan">
<meta name="search_title" content="Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge">
</head><body><article class="article">
<header class="article-header"><div class="meta">
<div class="meta-item__bibliography"><p class="NDPR2Bibliographic"><strong>Jeff Kochan, <em>Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge</em>, Open Book, 2017, 446pp., $28.99 (pbk), ISBN 9781783744107.</strong></p></div>
<p class="meta-item__reviewer">Reviewed by Dimitri Ginev</p>
</div></header>
<div class="page-primary article-content entry-content">
<p>Jeff Kochan's book is distinguished by clearly formulated theses, convincing arguments, and far-reaching consequences.</p>
</div></article></body></html>"""


def test_extracts_the_bibliographic_header():
    books = fetch_ndpr.extract_review_content(KOCHAN_PAGE)["books"]
    assert books == [{"authors": "Jeff Kochan",
                      "title": "Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge"}]


def test_extracts_every_book_of_a_multi_book_review():
    page = KOCHAN_PAGE.replace(
        "</div>\n<p class=\"meta-item__reviewer\">",
        "<p><strong>McCulloch, Gregory, <em>The Life of the Mind</em>, Routledge, 2003.</strong></p></div>\n"
        "<p class=\"meta-item__reviewer\">", 1)
    books = fetch_ndpr.extract_review_content(page)["books"]
    assert [b["authors"] for b in books] == ["Jeff Kochan", "McCulloch, Gregory"]


def test_a_title_in_i_tags_is_read():
    page = KOCHAN_PAGE.replace("<em>", "<i>").replace("</em>", "</i>")
    assert fetch_ndpr.extract_review_content(page)["books"][0]["authors"] == "Jeff Kochan"


def test_a_header_without_italics_uses_the_meta_it_contains():
    """Live shape: "Shaun Nichols, Bound: Essays on ..., Oxford ..." with no
    italics; the search_* meta pair names the same book."""
    page = KOCHAN_PAGE.replace("<em>", "").replace("</em>", "")
    assert fetch_ndpr.extract_review_content(page)["books"] == [
        {"authors": "Jeff Kochan",
         "title": "Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge"}]


def test_meta_fallback_refuses_a_two_book_header():
    """Live shape: Conley's and Broad's books in one italic-free paragraph;
    a meta pair naming only the first must not make it one book."""
    page = (KOCHAN_PAGE.replace("<em>", "").replace("</em>", "")
            .replace("ISBN 9781783744107.</strong>",
                     "ISBN 9781783744107. Broad, Jacqueline, Women Philosophers of the "
                     "Seventeenth Century, Cambridge, 2003, 204pp.</strong>"))
    assert fetch_ndpr.extract_review_content(page)["books"] == []


def test_meta_absent_from_the_header_is_not_used():
    page = (KOCHAN_PAGE.replace("<em>", "").replace("</em>", "")
            .replace('content="Jeff Kochan"', 'content="Dimitri Ginev"'))
    assert fetch_ndpr.extract_review_content(page)["books"] == []


def test_one_paragraph_naming_two_books_gives_two():
    page = KOCHAN_PAGE.replace(
        "ISBN 9781783744107.</strong>",
        "ISBN 9781783744107. Helen Longino, <em>Science as Social Knowledge</em>, Princeton, 1990.</strong>")
    books = fetch_ndpr.extract_review_content(page)["books"]
    assert [b["title"] for b in books] == [
        "Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge",
        "Science as Social Knowledge"]
    assert books[1]["authors"].endswith("Helen Longino")
    assert not search_ndpr.review_matches(books, "Science as Social Knowledge", "Longino")


def test_a_title_split_across_adjacent_ems_is_one_book():
    """Live: Nuti's header, as NDPR's CMS writes it."""
    page = KOCHAN_PAGE.replace(
        '<strong>Jeff Kochan, <em>Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge</em>, Open Book',
        '<strong>Jeff Kochan, <em>Science as Social Existence: Heidegger and the Sociology of </em></strong> '
        '<strong><em>Scientific Knowledge</em></strong><strong>, Open Book')
    books = fetch_ndpr.extract_review_content(page)["books"]
    assert books == [{"authors": "Jeff Kochan",
                      "title": "Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge"}]


def test_a_title_inside_a_title_set_roman_is_one_book():
    """Live: the Kindi and Arabatzis header."""
    page = KOCHAN_PAGE.replace(
        "<strong>Jeff Kochan, <em>Science as Social Existence: Heidegger and the Sociology of Scientific Knowledge</em>",
        "<strong>Vasso Kindi and Theodore Arabatzis (eds.), <em>Kuhn's </em>The Structure of Scientific "
        "Revolutions<em> Revisited</em>")
    books = fetch_ndpr.extract_review_content(page)["books"]
    assert books == [{"authors": "Vasso Kindi and Theodore Arabatzis (eds.)",
                      "title": "Kuhn's The Structure of Scientific Revolutions Revisited"}]


def test_italics_inside_the_title_stay_one_book():
    page = KOCHAN_PAGE.replace(
        "<em>Science as Social Existence: Heidegger",
        "<em>Science as Social Existence: <em>Heidegger</em>")
    books = fetch_ndpr.extract_review_content(page)["books"]
    assert len(books) == 1 and books[0]["authors"] == "Jeff Kochan"


def test_authors_are_not_glued_across_tags_or_read_from_comments():
    page = KOCHAN_PAGE.replace(
        "<strong>Jeff Kochan, <em>",
        "<strong><span>Jeff</span><br><span>Kochan</span><!-- Smith --><![CDATA[Jones]]>, <em>")
    assert fetch_ndpr.extract_review_content(page)["books"][0]["authors"] == "Jeff Kochan"


def test_header_is_never_summary_text():
    """With no entry-content div the <article> is the content area, and a
    long header paragraph used to pass the substantive-paragraph filter."""
    page = KOCHAN_PAGE.replace('class="page-primary article-content entry-content"', "")
    result = fetch_ndpr.extract_review_content(page)
    assert "ISBN" not in result["summary_text"]
    assert result["summary_text"].startswith("Jeff Kochan's book")


def test_summary_keeps_the_spaces_around_inline_markup():
    page = KOCHAN_PAGE.replace(
        "<p>Jeff Kochan's book is",
        "<p>In <em>Science as Social Existence</em> Jeff Kochan, writing in the 16<sup>th</sup> year, says his book is")
    text = fetch_ndpr.extract_review_content(page)["summary_text"]
    assert text.startswith("In Science as Social Existence Jeff Kochan, writing in the 16th year")


def test_no_header_means_no_books():
    page = "<html><body><article><p>" + "x" * 80 + "</p></article></body></html>"
    assert fetch_ndpr.extract_review_content(page)["books"] == []


# --- the resolver -------------------------------------------------------------

def _review(authors, title, text="A summary paragraph of the reviewed book, long enough to keep." * 2):
    return {"summary_text": text, "books": [{"authors": authors, "title": title}]}


def test_resolver_skips_a_wrong_book_and_takes_the_next_candidate():
    import enrich_bibliography as eb
    cands = [{"url": "u/wrong", "slug": "wrong", "score": 1.0},
             {"url": "u/right", "slug": "right", "score": 1.0}]
    pages = {"u/wrong": _review("McCulloch, Gregory", "The Life of the Mind", "WRONG " * 20),
             "u/right": _review("Evan Thompson", "Mind in Life", "RIGHT " * 20)}
    with patch("search_ndpr.search_ndpr_candidates", return_value=cands), \
         patch("fetch_ndpr.fetch_ndpr_review", side_effect=lambda url, debug=False: pages[url]):
        text, source = eb.resolve_ndpr_abstract("Mind in Life", "Thompson")
    assert source == "ndpr" and text.startswith("RIGHT")


def test_resolver_returns_nothing_when_no_candidate_is_the_book():
    import enrich_bibliography as eb
    cands = [{"url": "u/kochan", "slug": "kochan", "score": 1.0}]
    with patch("search_ndpr.search_ndpr_candidates", return_value=cands), \
         patch("fetch_ndpr.fetch_ndpr_review",
               return_value=_review("Jeff Kochan", "Science as Social Existence")):
        assert eb.resolve_ndpr_abstract(
            "Science as Social Knowledge", "Longino") == (None, None)


def test_resolver_needs_a_surname():
    import enrich_bibliography as eb
    search = MagicMock()
    with patch("search_ndpr.search_ndpr_candidates", search):
        assert eb.resolve_ndpr_abstract("Some Book", None) == (None, None)
    search.assert_not_called()


def test_ndpr_surname_falls_back_to_the_editor():
    """NDPR heads an edited volume's review with its editors."""
    import enrich_bibliography as eb
    assert eb.get_ndpr_surname({"fields": {"author": "Thompson, Evan",
                                           "editor": "Doe, Jane"}}) == "Thompson"
    assert eb.get_ndpr_surname({"fields": {"editor": "Rosenberger, Robert and Verbeek, Peter-Paul"}}) == "Rosenberger"
    assert not eb.get_ndpr_surname({"fields": {"title": "Anonymous"}})


def test_resolver_decodes_latex_before_matching():
    import enrich_bibliography as eb
    cands = [{"url": "u/noe", "slug": "action-in-perception", "score": 1.0}]
    with patch("search_ndpr.search_ndpr_candidates", return_value=cands), \
         patch("fetch_ndpr.fetch_ndpr_review",
               return_value=_review("Alva Noë", "Action in Perception", "RIGHT " * 20)):
        text, source = eb.resolve_ndpr_abstract("Action in Perception", 'No{\\"e}')
    assert source == "ndpr"


def test_resolver_skips_a_dead_or_empty_candidate():
    """A stale sitemap URL (404) or a right page with no usable text must
    not stop the search before a later candidate."""
    import enrich_bibliography as eb
    cands = [{"url": "u/gone", "slug": "gone", "score": 1.0},
             {"url": "u/empty", "slug": "empty", "score": 1.0},
             {"url": "u/right", "slug": "right", "score": 1.0}]

    def fetch(url, debug=False):
        if url == "u/gone":
            raise LookupError("NDPR review not found")
        if url == "u/empty":
            return _review("Evan Thompson", "Mind in Life", "")
        return _review("Evan Thompson", "Mind in Life", "RIGHT " * 20)

    with patch("search_ndpr.search_ndpr_candidates", return_value=cands), \
         patch("fetch_ndpr.fetch_ndpr_review", side_effect=fetch):
        text, source = eb.resolve_ndpr_abstract("Mind in Life", "Thompson")
    assert source == "ndpr" and text.startswith("RIGHT")


def test_resolver_reports_a_page_without_a_header(capsys):
    import enrich_bibliography as eb
    cands = [{"url": "u/x", "slug": "x", "score": 1.0}]
    with patch("search_ndpr.search_ndpr_candidates", return_value=cands), \
         patch("fetch_ndpr.fetch_ndpr_review",
               return_value={"summary_text": "T " * 40, "books": []}):
        assert eb.resolve_ndpr_abstract("Mind in Life", "Thompson") == (None, None)
    assert "no bibliographic header" in capsys.readouterr().err
