"""The one owner of full-text source logic (PL-27): request building and
response parsing for OpenAlex, Semantic Scholar and Brave, the licence kinds
and the rule-15 order, imported by `acquire_fulltext.py` and phillit-service,
which each send the requests with their own client and credentials.
Purity: no network, environment or filesystem access and nothing read at
import; every function maps its arguments to a value.
A parse function takes DECODED JSON and never raises on its content: a
payload of the wrong shape gives `[]`, and a malformed record, location or
author is skipped while its siblings are kept.
The dataclasses are frozen shallowly: a nested dict (`Request.params`,
`Location.matched`) is the caller's not to mutate. Each location gets its
own copy of `matched`.
Residual, accepted under PL-28: a different work by the same first author
whose title extends the identity's phrase ("Causal Abstraction and Its
Critics") still passes the title-route match (measured 0 of 50).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

# `normalize_doi` is bib_identity's, bound through fulltext (an alias).
from fulltext import drop_apostrophes, fold, match_fold, normalize_doi, title_phrase_cut
from generate_bibliography import clean_bibtex_str
from web_evidence import excluded_host

OPENALEX_WORKS = "https://api.openalex.org/works"
S2_PAPER = "https://api.semanticscholar.org/graph/v1/paper"
BRAVE_WEB_SEARCH = "https://api.search.brave.com/res/v1/web/search"

KINDS = ("cc", "oa_repository", "author", "publisher_free")
_REPOSITORY_HOSTS = ("ssrn.com", "academia.edu")
_S2_PUBLISHER_STATUSES = ("GOLD", "HYBRID", "BRONZE")
_RANK = {"publisher_free": 2, "oa_repository": 3, "author": 4}

TITLE_SEARCH_WORDS = 8
TITLE_SELECT = "display_name,type,authorships,locations,best_oa_location,doi,id"
SKIPPED_WORK_TYPES = ("erratum", "paratext", "retraction")

MAX_SUGGESTIONS = 3
SUGGESTION_TITLE_MAX = 200
SUGGESTION_URL_MAX = 2000

DOI_SHAPE = re.compile(r"10\.\d+/.+", re.S)
_NOT_SEARCH_CHAR = re.compile(r"[^\w\s'-]|_")


@dataclass(frozen=True)
class Request:
    url: str                      # no query string
    params: dict[str, str]        # query parameters; never a key or a mailto
    api: str                      # "openalex" | "s2" | "brave": which credential the caller adds


@dataclass(frozen=True)
class Location:
    url: str
    license: str | None           # the unclassified licence value, stripped, or None
    kind: str                     # "cc" | "oa_repository" | "author" | "publisher_free"
    source: str                   # "openalex" | "s2"
    at_publisher: bool
    matched: dict | None = None   # title route: {"openalex_id", "title", "doi"} of the matched record

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown location kind {self.kind!r}")


@dataclass(frozen=True)
class Suggestion:
    url: str
    host: str
    title: str                    # the search result's title, for the user


# ------------------------------------------------------------ identity text

def _decoded(identity, field: str) -> str:
    """The identity's raw value decoded from BibTeX, whitespace collapsed;
    "" for a missing or non-string value."""
    value = identity.get(field) if isinstance(identity, dict) else None
    if not isinstance(value, str):
        return ""
    return " ".join(clean_bibtex_str(value).split())


def main_title(identity) -> str:
    """The decoded title cut at a subtitle exactly as `title_phrase_cut` cuts
    it: at the first `:`, `?` or `.` when the head folds to at least 2 words,
    else the whole title."""
    title = _decoded(identity, "title")
    head = re.split(r"[:?.]", title)[0]
    return head.strip() if len(fold(head).split()) >= 2 else title


def key_phrase(identity) -> str:
    """The identity's cut phrase, apostrophes dropped as `identity_ok` drops
    them, or "" when it has fewer than 2 words (too weak a key: an empty
    phrase is a prefix of every title)."""
    phrase = title_phrase_cut(drop_apostrophes(_decoded(identity, "title")))
    return phrase if len(phrase.split()) >= 2 else ""


def _doi(identity) -> str:
    value = identity.get("doi") if isinstance(identity, dict) else None
    doi = normalize_doi(value) if isinstance(value, str) else ""
    return doi if DOI_SHAPE.fullmatch(doi) else ""


# ----------------------------------------------------------------- requests

def openalex_doi_request(identity) -> Request | None:
    doi = _doi(identity)
    if not doi:
        return None
    return Request(f"{OPENALEX_WORKS}/doi:{quote(doi, safe='/')}", {}, "openalex")


def openalex_title_request(identity) -> Request | None:
    if not key_phrase(identity) or not fold(_decoded(identity, "surname")):
        return None
    words = _NOT_SEARCH_CHAR.sub(" ", main_title(identity)).split()[:TITLE_SEARCH_WORDS]
    return Request(OPENALEX_WORKS, {
        "filter": "title.search:" + " ".join(words),
        "per-page": "10",
        "select": TITLE_SELECT,
    }, "openalex")


def s2_doi_request(identity) -> Request | None:
    doi = _doi(identity)
    if not doi:
        return None
    return Request(f"{S2_PAPER}/DOI:{quote(doi, safe='/')}",
                   {"fields": "openAccessPdf"}, "s2")


def brave_request(identity) -> Request | None:
    title = " ".join(main_title(identity).replace('"', "").split())
    surname = " ".join(_decoded(identity, "surname").replace('"', "").split())
    if len(fold(title).split()) < 2 or not fold(surname):
        return None
    return Request(BRAVE_WEB_SEARCH,
                   {"q": f'"{title}" {surname} filetype:pdf', "count": "10"}, "brave")


# ---------------------------------------------------- kinds, order, licence

def _is_cc(lic) -> bool:
    return isinstance(lic, str) and lic.strip().lower().startswith("cc")


def _host_in(url, domains) -> bool:
    if not isinstance(url, str):
        return False
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == d or host.endswith("." + d) for d in domains)


def _openalex_source_type(loc: dict):
    src = loc.get("source")
    return src.get("type") if isinstance(src, dict) else None


def openalex_kind(loc: dict) -> str:
    if _is_cc(loc.get("license")):
        return "cc"
    stype = _openalex_source_type(loc)
    if stype == "repository" or _host_in(loc.get("pdf_url"), _REPOSITORY_HOSTS):
        return "oa_repository"
    if stype == "journal":
        return "publisher_free"
    return "author"


def s2_kind(oa: dict) -> str:
    if _is_cc(oa.get("license")):
        return "cc"
    status = oa.get("status")
    if status == "GREEN":
        return "oa_repository"
    if isinstance(status, str) and status in _S2_PUBLISHER_STATUSES:
        return "publisher_free"
    return "author"


def _rank(loc: Location) -> int:
    if loc.kind == "cc":
        return 0 if loc.at_publisher else 1
    return _RANK.get(loc.kind, 5)


def order(locs: list[Location]) -> list[Location]:
    """Rule 15 order, stable; a URL seen twice keeps its best-ranked copy."""
    out, seen = [], set()
    for loc in sorted(locs, key=_rank):
        if loc.url not in seen:
            seen.add(loc.url)
            out.append(loc)
    return out


def license_string(loc: Location) -> str:
    """The service sidecar's `license`: the raw value when it is a `cc`
    licence, else `oa:<kind>` (the engine's `open` policy admits only `cc*`,
    `oa:*` and `upload`)."""
    return loc.license.strip() if _is_cc(loc.license) else f"oa:{loc.kind}"


# ------------------------------------------------------------------ parsers

def _clean_license(lic) -> str | None:
    return lic.strip() if isinstance(lic, str) and lic.strip() else None


def _http_url(url) -> bool:
    if not (isinstance(url, str) and url):
        return False
    try:
        return urlsplit(url).scheme.lower() in ("http", "https")
    except ValueError:
        return False


def _str_or_none(value) -> str | None:
    return value if isinstance(value, str) else None


def _openalex_locations(work: dict, matched: dict | None = None) -> list[Location]:
    raw = [work.get("best_oa_location")]
    if isinstance(work.get("locations"), list):
        raw += work["locations"]
    out = []
    for loc in raw:
        if not isinstance(loc, dict):
            continue
        url = loc.get("pdf_url")
        if not _http_url(url) or loc.get("is_oa") is False:
            continue
        out.append(Location(
            url=url, license=_clean_license(loc.get("license")),
            kind=openalex_kind(loc), source="openalex",
            at_publisher=_openalex_source_type(loc) == "journal",
            matched=None if matched is None else dict(matched)))
    return out


def openalex_doi_parse(identity, payload) -> list[Location]:
    """The locations of ONE work record (the DOI route); `[]` for anything
    else, a search answer or a list included."""
    if not isinstance(payload, dict) or "results" in payload:
        return []
    return _openalex_locations(payload)


def _first_author_names(authorships) -> list[str]:
    """Display names of the first author(s); of every author when no
    authorship carries a position."""
    if not isinstance(authorships, list):
        return []
    auths = [a for a in authorships if isinstance(a, dict)]
    if any(a.get("author_position") for a in auths):
        auths = [a for a in auths if a.get("author_position") == "first"]
    names = []
    for a in auths:
        author = a.get("author")
        name = author.get("display_name") if isinstance(author, dict) else None
        if isinstance(name, str):
            names.append(name)
    return names


def _matches(phrase: str, surname: str, record: dict) -> bool:
    name = record.get("display_name")
    if not isinstance(name, str):
        return False
    title = match_fold(name)
    if not (title == phrase or title.startswith(phrase + " ")):
        return False
    return any(f" {surname} " in f" {match_fold(n)} "
               for n in _first_author_names(record.get("authorships")))


def openalex_title_parse(identity, payload) -> list[Location]:
    """The locations of every record in `{"results": [...]}` that matches the
    identity (title route); each carries the matched record in `matched`."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return []
    phrase = key_phrase(identity)
    surname = match_fold(_decoded(identity, "surname"))
    if not phrase or not surname:
        return []
    out = []
    for record in payload["results"]:
        if not isinstance(record, dict):
            continue
        typ = record.get("type")
        if isinstance(typ, str) and typ in SKIPPED_WORK_TYPES:
            continue
        if not _matches(phrase, surname, record):
            continue
        matched = {"openalex_id": _str_or_none(record.get("id")),
                   "title": record["display_name"],
                   "doi": _str_or_none(record.get("doi"))}
        out += _openalex_locations(record, matched)
    return out


def s2_parse(identity, payload) -> list[Location]:
    """The `openAccessPdf` of one S2 paper record (DOI route)."""
    oa = payload.get("openAccessPdf") if isinstance(payload, dict) else None
    if not (isinstance(oa, dict) and _http_url(oa.get("url"))):
        return []
    status = oa.get("status")
    return [Location(
        url=oa["url"], license=_clean_license(oa.get("license")),
        kind=s2_kind(oa), source="s2",
        at_publisher=isinstance(status, str) and status in _S2_PUBLISHER_STATUSES)]


# -------------------------------------------------------------------- Brave

def _untrusted_char(c: str) -> bool:
    return unicodedata.category(c) in ("Cc", "Cf")


def _clean_title(title: str) -> str:
    """Control and bidirectional/format characters removed (control
    whitespace becomes a space), whitespace collapsed."""
    text = "".join(" " if c.isspace() else ("" if _untrusted_char(c) else c) for c in title)
    return " ".join(text.split())


def brave_parse(identity, payload) -> list[Suggestion]:
    """Candidate PDF links for the user, in result order: http(s), not an
    excluded host, at most `SUGGESTION_URL_MAX` characters, free of control,
    format and space characters, and a result title that contains the
    identity's cut phrase as whole words. Titles are untrusted text: cleaned,
    then cut to `SUGGESTION_TITLE_MAX`."""
    web = payload.get("web") if isinstance(payload, dict) else None
    results = web.get("results") if isinstance(web, dict) else None
    phrase = key_phrase(identity)
    if not isinstance(results, list) or not phrase:
        return []
    out, seen = [], set()
    for r in results:
        if len(out) >= MAX_SUGGESTIONS:
            break
        if not isinstance(r, dict):
            continue
        url, title = r.get("url"), r.get("title")
        if not (isinstance(url, str) and isinstance(title, str)):
            continue
        if (len(url) > SUGGESTION_URL_MAX or url in seen or not _http_url(url)
                or any(c.isspace() or _untrusted_char(c) for c in url)
                or excluded_host(url)):
            continue
        try:
            host = (urlsplit(url).hostname or "").lower()
        except ValueError:
            continue
        title = _clean_title(title)
        if not host or f" {phrase} " not in f" {match_fold(title)} ":
            continue
        seen.add(url)
        out.append(Suggestion(url=url, host=host, title=title[:SUGGESTION_TITLE_MAX]))
    return out
