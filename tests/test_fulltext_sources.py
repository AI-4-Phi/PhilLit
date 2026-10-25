"""fulltext_sources.py: request builders, response parsers, licence kinds and
the rule-15 order. Pure functions throughout: no HTTP is mocked because none
is made. The kind/order/license_string cases are ported from phillit-service's
`tests/test_fulltext_locations.py`, so the service's behaviour does not change
when it imports this module."""
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(SCRIPTS))

import fulltext_sources as fs  # noqa: E402
from fulltext import fold, title_phrase_cut  # noqa: E402
from generate_bibliography import clean_bibtex_str  # noqa: E402

GEIGER_TITLE = "Causal Abstraction: A Theoretical Foundation for Mechanistic Interpretability"


def ident(doi=None, title=None, surname=None, year=None):
    return {"doi": doi, "title": title, "surname": surname, "year": year}


def all_requests():
    full = ident("10.1234/abc", "Justice as Fairness: Political", "Rawls", "1985")
    return [fs.openalex_doi_request(full), fs.openalex_title_request(full),
            fs.s2_doi_request(full), fs.brave_request(full)]


# ------------------------------------------------------------------ requests

def test_requests_carry_no_credentials():
    reqs = all_requests()
    assert all(r is not None for r in reqs)
    for r in reqs:
        assert not ({"api_key", "mailto", "key"} & {k.lower() for k in r.params})
        assert r.api in ("openalex", "s2", "brave")
        assert "?" not in r.url
    assert [r.api for r in reqs] == ["openalex", "openalex", "s2", "brave"]


def test_requests_are_frozen():
    r = all_requests()[0]
    with pytest.raises(Exception):
        r.url = "x"


def test_doi_request_needs_a_normalizable_doi():
    r = fs.openalex_doi_request(ident("https://doi.org/10.1/X", "T", "S", "2000"))
    assert r.url == "https://api.openalex.org/works/doi:10.1/x"
    assert r.params == {} and r.api == "openalex"
    for bad in ("nonsense", "", None, 5, "10.x/abc", "10.12/"):
        assert fs.openalex_doi_request(ident(bad, "T", "S")) is None
        assert fs.s2_doi_request(ident(bad, "T", "S")) is None
    lt = fs.openalex_doi_request(ident("10.1/a<b"))
    assert lt.url == "https://api.openalex.org/works/doi:10.1/a%3Cb"


def test_doi_requests_quote_reserved_characters():
    doi = "10.1002/(SICI)1097?x#y"
    for r in (fs.openalex_doi_request(ident(doi)), fs.s2_doi_request(ident(doi))):
        assert "%3F" in r.url and "%23" in r.url
        assert "?" not in r.url and "#" not in r.url


def test_s2_doi_request_shape():
    r = fs.s2_doi_request(ident("10.1234/ABC.def"))
    assert r.url == "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1234/abc.def"
    assert r.params == {"fields": "openAccessPdf"} and r.api == "s2"


def test_title_request_strips_filter_syntax():
    r = fs.openalex_title_request(ident(None, "Rawls, Justice | Fairness: Essays", "Rawls"))
    assert r.url == "https://api.openalex.org/works" and r.api == "openalex"
    assert r.params["filter"] == "title.search:Rawls Justice Fairness"
    assert r.params["per-page"] == "10"
    assert set(r.params["select"].split(",")) == {
        "display_name", "type", "authorships", "locations", "best_oa_location", "doi", "id"}
    r = fs.openalex_title_request(ident(
        None, "Don't Look-Up, (the) Moral Status of Non-Human Beings in Twenty Words", "Rawls"))
    assert r.params["filter"] == "title.search:Don't Look-Up the Moral Status of Non-Human Beings"


def test_title_request_keeps_letters_digits_apostrophe_hyphen_and_eight_words():
    r = fs.openalex_title_request(ident(
        None, "What's Wrong with Self-Driving Cars in {\\\"U}berlingen 2.0 and More Words Here",
        "Smith"))
    # the decoded title's first 8 words; `.` is a subtitle cut only when the
    # head has at least 2 words, as title_phrase_cut cuts.
    assert r.params["filter"] == "title.search:What's Wrong with Self-Driving Cars in Überlingen 2"


def test_title_request_declines_one_word_phrase():
    assert fs.openalex_title_request(ident(None, "Introduction", "Smith")) is None


def test_title_request_needs_title_and_surname():
    assert fs.openalex_title_request(ident(None, "Justice as Fairness", None)) is None
    assert fs.openalex_title_request(ident(None, None, "Rawls")) is None
    assert fs.openalex_title_request(ident(None, 5, "Rawls")) is None
    assert fs.openalex_title_request(ident(None, "Justice as Fairness", 7)) is None


def test_identity_is_never_rewritten():
    i = ident("https://doi.org/10.1/X", "M{\\\"u}ller's Theory: A", "M{\\\"u}ller", "2001")
    before = dict(i)
    for f in (fs.openalex_doi_request, fs.openalex_title_request, fs.s2_doi_request,
              fs.brave_request, fs.main_title):
        f(i)
    assert i == before


@pytest.mark.parametrize("title", [
    "Ethics: A Very Short Introduction",
    "Causal Abstraction: A Theoretical Foundation",
    "Ethics 2.0: Machines",
    "Dr. Strangelove: A Study",
    "Mind: A Reader",
    "Why {B}elieve? On M{\\\"u}ller",
    "Introduction",
])
def test_main_title_matches_title_phrase_cut(title):
    mt = fs.main_title(ident(None, title, "S"))
    phrase = title_phrase_cut(clean_bibtex_str(title))
    assert fold(mt).startswith(phrase)
    assert " ".join(fold(mt).split()[:6]) == phrase


def test_main_title_cuts_where_title_phrase_cut_cuts():
    assert fs.main_title(ident(None, "Ethics 2.0: Machines", "S")) == "Ethics 2"
    assert fs.main_title(ident(None, "Mind: A Reader", "S")) == "Mind: A Reader"
    assert fs.main_title(ident(None, "M{\\\"u}ller  on\nMinds: X", "S")) == "Müller on Minds"
    assert fs.main_title(ident(None, None, "S")) == ""


def test_brave_request_shape():
    r = fs.brave_request(ident(None, 'The "Hard" Problem: Revisited', 'O"Brien'))
    assert r.url == "https://api.search.brave.com/res/v1/web/search"
    assert r.params == {"q": '"The Hard Problem" OBrien filetype:pdf', "count": "10"}
    assert r.api == "brave"


def test_brave_request_none_without_title_or_surname():
    assert fs.brave_request(ident(None, "Justice as Fairness", None)) is None
    assert fs.brave_request(ident(None, "Justice as Fairness", '""')) is None
    assert fs.brave_request(ident(None, None, "Rawls")) is None
    assert fs.brave_request(ident(None, "Introduction", "Rawls")) is None
    assert fs.brave_request(ident(None, '"" ""', "Rawls")) is None


# ------------------------------------------------------------------- parsers

def oa_loc(url, typ="repository", lic=None, **kw):
    d = {"pdf_url": url, "license": lic, "source": {"type": typ}}
    d.update(kw)
    return d


def work(display_name, authors, locations=(), typ="article", best=None,
         wid="https://openalex.org/W1", doi=None):
    return {"id": wid, "doi": doi, "display_name": display_name, "type": typ,
            "authorships": authors, "locations": list(locations),
            "best_oa_location": best}


def first(name):
    return {"author_position": "first", "author": {"display_name": name}}


def middle(name):
    return {"author_position": "middle", "author": {"display_name": name}}


def unpositioned(name):
    return {"author": {"display_name": name}}


GEIGER = ident(None, GEIGER_TITLE, "Geiger", "2023")


def test_title_parse_word_bounded():
    wrong = work("Causal Abstractions of Neural Networks", [first("Atticus Geiger")],
                 [oa_loc("https://arxiv.org/pdf/wrong.pdf")])
    right = work("Causal Abstraction: A Theoretical Foundation for Mechanistic "
                 "Interpretability", [first("Atticus Geiger")],
                 [oa_loc("https://arxiv.org/pdf/right.pdf")])
    assert fs.openalex_title_parse(GEIGER, {"results": [wrong]}) == []
    locs = fs.openalex_title_parse(GEIGER, {"results": [wrong, right]})
    assert [l.url for l in locs] == ["https://arxiv.org/pdf/right.pdf"]
    assert locs[0].source == "openalex" and locs[0].kind == "oa_repository"


def test_title_parse_exact_phrase_match():
    i = ident(None, "Causal Abstraction", "Geiger")
    rec = work("Causal Abstraction", [first("A. Geiger")], [oa_loc("https://x.org/a.pdf")])
    assert len(fs.openalex_title_parse(i, {"results": [rec]})) == 1


def test_title_parse_first_author_only():
    rec = work(GEIGER_TITLE, [first("Jane Doe"), middle("Atticus Geiger")],
               [oa_loc("https://x.org/a.pdf")])
    assert fs.openalex_title_parse(GEIGER, {"results": [rec]}) == []
    # no positions at all: any author counts
    rec = work(GEIGER_TITLE, [unpositioned("Jane Doe"), unpositioned("Atticus Geiger")],
               [oa_loc("https://x.org/a.pdf")])
    assert len(fs.openalex_title_parse(GEIGER, {"results": [rec]})) == 1


def test_title_parse_surname_is_a_whole_word():
    rec = work(GEIGER_TITLE, [first("Atticus Geigerson")], [oa_loc("https://x.org/a.pdf")])
    assert fs.openalex_title_parse(GEIGER, {"results": [rec]}) == []


@pytest.mark.parametrize("surname, author", [("Li", "Ming Liu"), ("Mill", "John Miller")])
def test_title_parse_surname_prefix_does_not_match(surname, author):
    i = ident(None, "Causal Abstraction", surname)
    rec = work("Causal Abstraction", [first(author)], [oa_loc("https://x.org/a.pdf")])
    assert fs.openalex_title_parse(i, {"results": [rec]}) == []


def test_title_parse_multiword_surname():
    i = ident(None, "The Scientific Image Revisited", "van Fraassen")
    rec = work("The Scientific Image Revisited", [first("Bas C. van Fraassen")],
               [oa_loc("https://x.org/a.pdf")])
    assert len(fs.openalex_title_parse(i, {"results": [rec]})) == 1


@pytest.mark.parametrize("typ", ["erratum", "paratext", "retraction"])
def test_title_parse_skips_erratum_paratext_retraction(typ):
    rec = work(GEIGER_TITLE, [first("Atticus Geiger")], [oa_loc("https://x.org/a.pdf")],
               typ=typ)
    assert fs.openalex_title_parse(GEIGER, {"results": [rec]}) == []


def test_title_parse_decodes_latex():
    i = ident(None, "Grundlagen der Logik: Eine Einf{\\\"u}hrung", "M{\\\"u}ller")
    rec = work("Grundlagen der Logik", [first("Daniel Müller")],
               [oa_loc("https://x.org/a.pdf")])
    assert len(fs.openalex_title_parse(i, {"results": [rec]})) == 1


def test_title_parse_records_matched():
    rec = work(GEIGER_TITLE, [first("Atticus Geiger")], [oa_loc("https://x.org/a.pdf")],
               wid="https://openalex.org/W4385", doi="https://doi.org/10.48550/arxiv.2301.04709")
    (loc,) = fs.openalex_title_parse(GEIGER, {"results": [rec]})
    assert loc.matched == {"openalex_id": "https://openalex.org/W4385",
                           "title": GEIGER_TITLE,
                           "doi": "https://doi.org/10.48550/arxiv.2301.04709"}
    rec = work(GEIGER_TITLE, [first("Atticus Geiger")], [oa_loc("https://x.org/a.pdf")],
               wid=5, doi=["x"])
    (loc,) = fs.openalex_title_parse(GEIGER, {"results": [rec]})
    assert loc.matched == {"openalex_id": None, "title": GEIGER_TITLE, "doi": None}


def test_title_parse_gives_each_location_its_own_matched():
    rec = work(GEIGER_TITLE, [first("Atticus Geiger")],
               [oa_loc("https://x.org/a.pdf"), oa_loc("https://x.org/b.pdf")])
    a, b = fs.openalex_title_parse(GEIGER, {"results": [rec]})
    assert a.matched == b.matched and a.matched is not b.matched
    a.matched["title"] = "mutated"
    assert b.matched["title"] == GEIGER_TITLE


def test_title_parse_same_author_extension_residual():
    """The PL-28 residual, asserted so a later fix shows up here: a DIFFERENT
    work by the same first author whose title extends the identity's phrase
    word-boundedly still matches (measured 0 of 50, mostly CS/ML)."""
    i = ident(None, "Causal Abstraction", "Geiger")
    other = work("Causal Abstraction and Its Critics", [first("Atticus Geiger")],
                 [oa_loc("https://x.org/critics.pdf")])
    assert [l.url for l in fs.openalex_title_parse(i, {"results": [other]})] == [
        "https://x.org/critics.pdf"]


def test_title_parse_declines_a_one_word_phrase():
    i = ident(None, "Introduction", "Smith")
    rec = work("Introduction", [first("John Smith")], [oa_loc("https://x.org/a.pdf")])
    assert fs.openalex_title_parse(i, {"results": [rec]}) == []
    i = ident(None, None, "Smith")
    assert fs.openalex_title_parse(i, {"results": [rec]}) == []
    i = ident(None, "Causal Abstraction", None)
    rec = work("Causal Abstraction", [first("John Smith")], [oa_loc("https://x.org/a.pdf")])
    assert fs.openalex_title_parse(i, {"results": [rec]}) == []


def test_routes_are_explicit():
    rec = work(GEIGER_TITLE, [first("Atticus Geiger")], [oa_loc("https://x.org/a.pdf")])
    assert fs.openalex_doi_parse(GEIGER, {"results": [rec]}) == []
    assert fs.openalex_doi_parse(GEIGER, [rec]) == []
    assert fs.openalex_title_parse(GEIGER, rec) == []
    assert fs.openalex_title_parse(GEIGER, [rec]) == []
    assert len(fs.openalex_doi_parse(GEIGER, rec)) == 1


def test_doi_parse_has_no_matched_record():
    (loc,) = fs.openalex_doi_parse(ident("10.1/x"), {"locations": [oa_loc("https://x.org/a.pdf")]})
    assert loc.matched is None


# Ported from phillit-service `_OPENALEX_ANSWER` / `_S2_ANSWER`.
_OPENALEX_ANSWER = {
    "best_oa_location": {
        "pdf_url": "https://me.example/self.pdf", "license": None,
        "source": {"type": "ebook platform"}},
    "locations": [
        {"pdf_url": "https://me.example/self.pdf", "license": None,
         "source": {"type": "ebook platform"}},
        {"pdf_url": "https://repo.edu/a.pdf", "license": None, "source": {"type": "repository"}},
        {"pdf_url": "https://journal.org/a.pdf", "license": None, "source": {"type": "journal"}},
        {"pdf_url": None, "license": "cc-by", "source": {"type": "journal"}},
        "garbage",
    ],
}
_S2_ANSWER = {"openAccessPdf": {"url": "https://other.org/a.pdf", "license": "CCBY",
                                "status": "HYBRID"}}


def test_parsers_then_order_match_the_service_end_to_end():
    i = ident("10.1234/abc.def")
    locs = fs.order(fs.openalex_doi_parse(i, _OPENALEX_ANSWER) + fs.s2_parse(i, _S2_ANSWER))
    assert [(l.url, l.kind, l.source, l.at_publisher) for l in locs] == [
        ("https://other.org/a.pdf", "cc", "s2", True),
        ("https://journal.org/a.pdf", "publisher_free", "openalex", True),
        ("https://repo.edu/a.pdf", "oa_repository", "openalex", False),
        ("https://me.example/self.pdf", "author", "openalex", False),
    ]
    assert locs[0].license == "CCBY"


def test_openalex_parse_skips_locations_marked_not_open_access():
    answer = {"best_oa_location": None, "locations": [
        {"pdf_url": "https://closed.org/a.pdf", "is_oa": False, "license": "cc-by",
         "source": {"type": "journal"}},
        {"pdf_url": "https://open.org/a.pdf", "is_oa": True, "license": None,
         "source": {"type": "journal"}},
        {"pdf_url": "https://unmarked.org/a.pdf", "license": None,
         "source": {"type": "repository"}},
    ]}
    locs = fs.order(fs.openalex_doi_parse(ident("10.1/x"), answer))
    assert [l.url for l in locs] == ["https://open.org/a.pdf", "https://unmarked.org/a.pdf"]


def test_licence_value_is_stripped_or_none():
    answer = {"locations": [oa_loc("https://a.org/1.pdf", lic="  cc-by "),
                            oa_loc("https://a.org/2.pdf", lic="   "),
                            oa_loc("https://a.org/3.pdf", lic=7)]}
    assert [l.license for l in fs.openalex_doi_parse(ident("10.1/x"), answer)] == [
        "cc-by", None, None]


def test_oa_parsers_skip_non_http_pdf_urls():
    i = ident("10.1/x")
    answer = {"locations": [oa_loc("ftp://x/a.pdf"), oa_loc("javascript:alert(1)"),
                            oa_loc("file:///etc/passwd"), oa_loc("HTTPS://x.org/ok.pdf")]}
    assert [l.url for l in fs.openalex_doi_parse(i, answer)] == ["HTTPS://x.org/ok.pdf"]
    assert fs.s2_parse(i, {"openAccessPdf": {"url": "ftp://x/a.pdf"}}) == []
    rec = work(GEIGER_TITLE, [first("Atticus Geiger")], [oa_loc("ftp://x/a.pdf")])
    assert fs.openalex_title_parse(GEIGER, {"results": [rec]}) == []


def test_s2_licence_value_is_stripped_or_none():
    i = ident("10.1/x")
    assert [l.license for l in fs.s2_parse(i, {"openAccessPdf": {
        "url": "https://a.org/p.pdf", "license": "  CCBY  "}})] == ["CCBY"]
    assert [l.license for l in fs.s2_parse(i, {"openAccessPdf": {
        "url": "https://a.org/p.pdf", "license": " \t "}})] == [None]


def test_s2_parse_shapes():
    i = ident("10.1/x")
    assert fs.s2_parse(i, {"openAccessPdf": None}) == []
    assert fs.s2_parse(i, {"openAccessPdf": {"url": ""}}) == []
    (loc,) = fs.s2_parse(i, {"openAccessPdf": {"url": "https://a.org/p.pdf",
                                               "license": None, "status": "GREEN"}})
    assert (loc.kind, loc.source, loc.at_publisher, loc.matched) == (
        "oa_repository", "s2", False, None)


GARBAGE = [None, [], "x", 5, {"results": "x"}, {"results": [1, None, {"locations": "x"}]},
           {"locations": 5}, {"best_oa_location": "x", "locations": [5, None]},
           {"locations": [{"pdf_url": 5}]}, {"openAccessPdf": "x"},
           {"openAccessPdf": {"url": 5}}, {"web": "x"}, {"web": {"results": "x"}},
           {"web": {"results": [1, None, {"url": 5, "title": None}]}},
           {"results": [{"display_name": 5, "authorships": "x", "locations": 5}]},
           {"results": [{"display_name": GEIGER_TITLE, "authorships": [5, {"author": 5},
                                                                     {"author": {"display_name": 3}}],
                         "type": ["x"]}]}]


@pytest.mark.parametrize("payload", GARBAGE)
def test_parsers_never_raise_on_garbage(payload):
    for parse in (fs.openalex_doi_parse, fs.openalex_title_parse, fs.s2_parse, fs.brave_parse):
        assert isinstance(parse(GEIGER, payload), list)


def test_kind_functions_never_raise_on_garbage():
    assert fs.openalex_kind({"pdf_url": 5, "source": "x", "license": 3}) == "author"
    assert fs.openalex_kind({"pdf_url": "http://[bad"}) == "author"
    assert fs.s2_kind({"status": ["GREEN"], "license": {}}) == "author"


def test_malformed_sibling_does_not_drop_valid_records():
    good = work(GEIGER_TITLE, [first("Atticus Geiger")], [oa_loc("https://x.org/good.pdf")])
    bad = {"display_name": 5, "authorships": "x"}
    assert [l.url for l in fs.openalex_title_parse(GEIGER, {"results": [bad, None, good]})] == [
        "https://x.org/good.pdf"]
    mixed = {"locations": ["junk", 5, {"pdf_url": 5}, oa_loc("https://x.org/ok.pdf")],
             "best_oa_location": "junk"}
    assert [l.url for l in fs.openalex_doi_parse(GEIGER, mixed)] == ["https://x.org/ok.pdf"]
    rec = work(GEIGER_TITLE, [5, first("Atticus Geiger")],
               ["junk", oa_loc("https://x.org/ok.pdf")])
    assert [l.url for l in fs.openalex_title_parse(GEIGER, {"results": [rec]})] == [
        "https://x.org/ok.pdf"]


# --------------------------------------------- kinds, order, license_string
# Ported from phillit-service tests/test_fulltext_locations.py.

@pytest.mark.parametrize("loc, kind", [
    ({"license": "cc-by", "pdf_url": "https://x.org/a.pdf"}, "cc"),
    ({"license": "CC-BY-NC", "source": {"type": "journal"}}, "cc"),
    ({"license": None, "source": {"type": "repository"}, "pdf_url": "https://r.edu/a.pdf"}, "oa_repository"),
    ({"license": None, "source": None, "pdf_url": "https://papers.ssrn.com/a.pdf"}, "oa_repository"),
    ({"license": None, "source": {"type": "journal"}, "pdf_url": "https://www.academia.edu/a.pdf"}, "oa_repository"),
    ({"license": None, "source": {"type": "journal"}, "pdf_url": "https://j.org/a.pdf"}, "publisher_free"),
    ({"license": None, "source": {"type": "ebook platform"}, "pdf_url": "https://me.org/a.pdf"}, "author"),
    ({"license": "publisher-specific-oa", "source": None, "pdf_url": "https://me.org/a.pdf"}, "author"),
    ({"pdf_url": "https://notssrn.com.evil.example/a.pdf"}, "author"),
])
def test_kinds_and_order_match_service_openalex_kind(loc, kind):
    assert fs.openalex_kind(loc) == kind


@pytest.mark.parametrize("oa, kind", [
    ({"license": "CCBY", "status": "GOLD"}, "cc"),
    ({"license": None, "status": "GREEN"}, "oa_repository"),
    ({"license": None, "status": "GOLD"}, "publisher_free"),
    ({"license": None, "status": "HYBRID"}, "publisher_free"),
    ({"license": None, "status": "BRONZE"}, "publisher_free"),
    ({"license": None, "status": None}, "author"),
    ({"status": "CLOSED"}, "author"),
])
def test_kinds_and_order_match_service_s2_kind(oa, kind):
    assert fs.s2_kind(oa) == kind


def _loc(url, kind, at_publisher=False, source="openalex", lic=None):
    return fs.Location(url=url, license=lic, kind=kind, source=source, at_publisher=at_publisher)


def test_kinds_and_order_match_service_order_ranks_five_classes():
    expected = [
        _loc("u1", "cc", True), _loc("u2", "cc", False), _loc("u3", "publisher_free", True),
        _loc("u4", "oa_repository"), _loc("u5", "author"),
    ]
    for seed in range(20):
        shuffled = expected[:]
        random.Random(seed).shuffle(shuffled)
        assert fs.order(shuffled) == expected


def test_kinds_and_order_match_service_order_stable_and_deduplicated():
    a, b = _loc("a", "author"), _loc("b", "author")
    assert fs.order([b, a]) == [b, a]
    out = fs.order([_loc("same", "author"), _loc("same", "cc", lic="cc-by"), a])
    assert [(l.url, l.kind) for l in out] == [("same", "cc"), ("a", "author")]


def test_kinds_and_order_match_service_constants():
    assert fs.KINDS == ("cc", "oa_repository", "author", "publisher_free")
    assert fs._REPOSITORY_HOSTS == ("ssrn.com", "academia.edu")
    assert fs._S2_PUBLISHER_STATUSES == ("GOLD", "HYBRID", "BRONZE")
    assert fs._RANK == {"publisher_free": 2, "oa_repository": 3, "author": 4}
    assert (fs.MAX_SUGGESTIONS, fs.SUGGESTION_TITLE_MAX, fs.SUGGESTION_URL_MAX) == (3, 200, 2000)


def test_location_rejects_an_unknown_kind():
    with pytest.raises(ValueError):
        _loc("u", "gold")


def test_license_string():
    assert fs.license_string(_loc("u", "cc", lic="cc-by")) == "cc-by"
    assert fs.license_string(_loc("u", "cc", lic=" cc-by-4.0 ")) == "cc-by-4.0"
    assert fs.license_string(_loc("u", "author", lic=None)) == "oa:author"
    assert fs.license_string(_loc("u", "oa_repository")) == "oa:oa_repository"
    assert fs.license_string(_loc("u", "author", lic="")) == "oa:author"
    assert fs.license_string(_loc("u", "publisher_free", lic="publisher-specific-oa")) \
        == "oa:publisher_free"
    assert fs.license_string(_loc("u", "author", lic="other-oa")) == "oa:author"
    assert fs.license_string(_loc("u", "oa_repository", lic="public-domain")) \
        == "oa:oa_repository"
    assert fs.license_string(_loc("u", "cc", lic="CCBY")) == "CCBY"


_REAL_WORLD_LICENCES = (
    None, "", "  ", "cc-by", "cc-by-4.0", "CC-BY-NC", "CCBY", " cc0 ", "cc-by-nc-nd",
    "publisher-specific-oa", "other-oa", "implied-oa", "public-domain", "mit",
    "acs-specified-oa", "elsevier-specific: oa user license", "unspecified-oa",
    "pd", "gpl-v3", "apache-2.0", "OTHER-OA", " publisher-specific-oa ",
)


def test_every_parsed_licence_string_passes_the_engine_open_policy():
    import acquire_fulltext

    i = ident("10.1/x")
    for lic in _REAL_WORLD_LICENCES:
        for t in ("journal", "repository", None):
            for loc in fs.openalex_doi_parse(i, {"best_oa_location": oa_loc(
                    "https://a.org/1.pdf", typ=t, lic=lic)}):
                assert acquire_fulltext._licensed(fs.license_string(loc), "open")
        for st in ("GREEN", "GOLD", "BRONZE", None):
            for loc in fs.s2_parse(i, {"openAccessPdf": {
                    "url": "https://a.org/1.pdf", "license": lic, "status": st}}):
                assert acquire_fulltext._licensed(fs.license_string(loc), "open")


# --------------------------------------------------------------------- Brave

def brave(*results):
    return {"type": "search", "web": {"type": "search", "results": [
        {"title": t, "url": u} for t, u in results]}}


def test_brave_parse_filters():
    i = ident(None, "Justice as Fairness: Political not Metaphysical", "Rawls")
    long_url = "https://a.org/" + "x" * 2000 + ".pdf"
    payload = brave(
        ("Justice as Fairness", "ftp://a.org/a.pdf"),
        ("Justice as Fairness", "javascript:alert(1)"),
        ("Justice as Fairness", "https://plato.stanford.edu/entries/rawls/"),
        ("Justice as Fairness", "https://philpapers.org/archive/RAWJAF.pdf"),
        ("Justice as Fairnesses and more", "https://b.org/b.pdf"),
        ("Rawls on justice", "https://c.org/c.pdf"),
        ("Justice as Fairness", long_url),
        ("Justice ‮as\x07 Fairness: Political", "https://d.org/d.pdf"),
        ("JUSTICE AS FAIRNESS " + "y " * 300, "http://www.e.org/e.pdf"),
        ("Notes on Justice as Fairness", "https://f.org/f.pdf"),
        ("Justice as Fairness", "https://g.org/g.pdf"),
    )
    out = fs.brave_parse(i, payload)
    assert [s.url for s in out] == ["https://d.org/d.pdf", "http://www.e.org/e.pdf",
                                    "https://f.org/f.pdf"]
    assert out[0] == fs.Suggestion(url="https://d.org/d.pdf", host="d.org",
                                   title="Justice as Fairness: Political")
    assert out[1].host == "www.e.org"
    assert len(out[1].title) == 200
    assert len(fs.brave_parse(i, brave(*[("Justice as Fairness", f"https://h{n}.org/a.pdf")
                                         for n in range(10)]))) == fs.MAX_SUGGESTIONS


def test_brave_parse_title_phrase_is_word_bounded_anywhere():
    out = fs.brave_parse(GEIGER, brave(
        ("Causal Abstractions of Neural Networks", "https://a.org/a.pdf"),
        ("[PDF] Geiger - Causal Abstraction: A Theoretical Foundation", "https://b.org/b.pdf")))
    assert [s.url for s in out] == ["https://b.org/b.pdf"]


def test_brave_parse_strips_before_cutting():
    i = ident(None, "Justice as Fairness", "Rawls")
    (s,) = fs.brave_parse(i, brave(("\u202e" * 300 + "Justice as Fairness", "https://a.org/a.pdf")))
    assert s.title == "Justice as Fairness"


def test_brave_parse_keeps_url_at_the_length_limit():
    i = ident(None, "Justice as Fairness", "Rawls")
    url = "https://a.org/" + "x" * (2000 - len("https://a.org/"))
    assert len(url) == 2000
    assert [s.url for s in fs.brave_parse(i, brave(("Justice as Fairness", url)))] == [url]


def test_brave_parse_strips_control_and_bidi_characters():
    i = ident(None, "Justice as Fairness", "Rawls")
    (s,) = fs.brave_parse(i, brave(("Justice\n\tas ⁦Fairness⁩ ‏(pdf)\x00",
                                    "https://a.org/a.pdf")))
    assert s.title == "Justice as Fairness (pdf)"


def test_brave_parse_drops_urls_with_control_or_bidi_characters():
    i = ident(None, "Justice as Fairness", "Rawls")
    assert fs.brave_parse(i, brave(("Justice as Fairness", "https://a.org/‮gdp.exe"),
                                   ("Justice as Fairness", "https://a.org/a b.pdf"))) == []


def test_brave_parse_needs_a_two_word_phrase():
    rec = brave(("Introduction", "https://a.org/a.pdf"))
    assert fs.brave_parse(ident(None, "Introduction", "Rawls"), rec) == []
    assert fs.brave_parse(ident(None, None, "Rawls"), rec) == []


# ---------------------------------------------------------------------- purity

def test_normalize_doi_is_bib_identitys():
    sys.path.insert(0, str(HOOKS))
    try:
        import bib_identity
    finally:
        sys.path.remove(str(HOOKS))
    assert fs.normalize_doi is bib_identity.normalize_doi


def test_import_is_pure(tmp_path):
    source = (SCRIPTS / "fulltext_sources.py").read_text(encoding="utf-8")
    for needle in ("os.environ", "os.getenv", "open(", "import requests",
                   "urllib.request", "socket", "resolve(", "sys.path", "__file__"):
        assert needle not in source, needle
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PHILLIT_") and "KEY" not in k.upper()
           and "TOKEN" not in k.upper() and k != "PYTHONPATH"}
    env.update(HOME=str(tmp_path), USERPROFILE=str(tmp_path),
               PYTHONPATH=os.pathsep.join([str(SCRIPTS), str(HOOKS)]))
    # Import the dependencies first, then make network and file access fail
    # and execute the module afresh: its own body must touch neither.
    code = (
        "import builtins, importlib, io, os, socket\n"
        "import fulltext, generate_bibliography, bib_identity, web_evidence\n"
        "def refuse(*a, **k):\n"
        "    raise RuntimeError('I/O during import')\n"
        "socket.socket.connect = refuse\n"
        "socket.create_connection = refuse\n"
        "builtins.open = io.open = os.open = refuse\n"
        "import fulltext_sources\n"
        "importlib.reload(fulltext_sources)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code],
                          cwd=tmp_path, env=env, capture_output=True, text=True,
                          encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


# --------------------------------------------------------------- apostrophes

GOODHART = ident(None, "Categorizing Variants of Goodhart's Law", "Manheim", "2018")


@pytest.mark.parametrize("display", ["Categorizing Variants of Goodhart’s Law",
                                     "Categorizing Variants of Goodhart's Law"])
def test_title_parse_matches_either_apostrophe(display):
    rec = work(display, [first("David Manheim")], [oa_loc("https://arxiv.org/pdf/g.pdf")])
    assert [l.url for l in fs.openalex_title_parse(GOODHART, {"results": [rec]})] == \
        ["https://arxiv.org/pdf/g.pdf"]


def test_title_parse_matches_an_apostrophe_surname():
    i = ident(None, "Socialism, Associations and the Market", "O'Neill", "1994")
    rec = work("Socialism, associations and the market", [first("John O’Neill")],
               [oa_loc("https://x.org/s.pdf")])
    assert len(fs.openalex_title_parse(i, {"results": [rec]})) == 1


def test_brave_parse_matches_either_apostrophe():
    out = fs.brave_parse(GOODHART, brave(("Categorizing Variants of Goodhart’s Law",
                                          "https://a.org/g.pdf")))
    assert [s.url for s in out] == ["https://a.org/g.pdf"]


def test_key_phrase_drops_apostrophes_as_identity_ok_does():
    assert fs.key_phrase(GOODHART) == "categorizing variants of goodharts law"
