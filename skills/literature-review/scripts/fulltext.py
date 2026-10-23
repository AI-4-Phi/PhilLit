"""The one owner of "is this PDF this work", of the full-text format and of
quote matching (EVIDENCE-FULLTEXT).

Acquisition (`acquire_fulltext.py`), the evidence barrier and the Phase 6
quotation gate (`check_quotes.py`) all call in here; none re-implements a
rule. Rulings: `docs/ideas/fulltext-evidence-tier.md`.

IDENTITY (`identity_ok`) reproduces the measured rules EXACTLY; the numbers
below hold only while the rules do. Measurement scripts and results:
`docs/known-issues/fulltext-identity-measurement-2026-10-21/` (local only),
run with pypdf 6.16.1 (the locked extractor) behind a pdftotext-compatible
wrapper:
- DOI work (`idbar_nxn_fullguard.py`): the DOI string in pages 1-3; else
  the full title's first 6 folded words as a phrase plus the folded
  first-author surname, both in pages 1-3, and every DOI on page 1 (lowered,
  trailing `.,;)` stripped) equal to the work's. 135/148 right, 1 wrong
  accept in 148x147 pairs (a paper citing the target). Comparing only the
  first 12 DOI characters gave 136/148 but lets a citing paper from the
  same journal through.
- No-DOI work, rule A (`idbar_nodoi.py` + `idbar_nodoi_ruleA.py`): the
  phrase is the first 6 folded words of the title cut at its first `:`, `?`
  or `.` when that part folds to at least 2 words; it must START within the
  first 600 folded characters of one of pages 1-5, with the surname on that
  same page. 127/178 right, 1 wrong in 178x177 pairs.
- `fold` is the measurement's fold (NFKD, ASCII, lowercase, non-alphanumerics
  to spaces, collapsed), NOT `bib_identity.title_key`; phrase containment is
  a plain substring test, as measured. Empty title, surname or DOI rejects
  (an empty string is "in" every text; the measured items never had one).

PAGES (`confirm_pages`, `pagenum.py`): numbers (1-4 digits, not part of a
longer number or a decimal) in the first 3 and last 3 non-empty lines of
each page vote for an offset c (printed = index + c, index 0-based); c is
accepted when at least 60% of pages (and at least 3) agree AND the bib's
`pages` start equals index + c for an index among the first 6, or the field
is an article number (a no-range value of at least 5 characters: digits, or
a letter prefix such as e1234) and printing starts at 1 (page 1 at one of
the first 6 indices). A shorter no-range value is a one-page item and
confirms nothing. Only pages whose own lines carry index + c get a number.
pypdf confirmed 93 of 147 Zotero PDFs (poppler 98); every disagreement was
another version or an article number.

TEXT FORMAT (`render_text`): pages in PDF order, each opened by a marker
line `[[page N]]` (confirmed) or `[[sheet K]]` (K = 1-based PDF page index,
never citable). Page text is NFKC-normalized, a line-end hyphen after a
letter and before a lowercase letter is joined, `\\r` newlines become `\\n`,
and an extracted line beginning (after spaces) with `[[` gets `[ [`, so only
the renderer makes markers. The text hash is sha256 of the rendered string
encoded UTF-8; every reader reads in text mode with encoding='utf-8'
(universal newlines), so a CRLF translation cannot break it.

QUOTES (`locate_quote`): one fold, applied identically to quote and text,
with an index map back to rendered offsets so the verbatim and page checks
cannot disagree. Pure apart from the explicit file helpers
(`read_text`, `file_text_sha256`, `write_text_atomic`, `validate_record`).
"""

import bisect
import functools
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

# Each insert is removed by value, not pop(0): fetch_web inserts paths of
# its own on import, so pop(0) would remove one of those instead.
_hook_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "hooks")
sys.path.insert(0, _hook_dir)
from bib_identity import (  # noqa: E402
    first_author_surname, normalize_doi, same_work_key, same_work_year)

sys.path.remove(_hook_dir)
_here = str(Path(__file__).resolve().parent)
sys.path.insert(0, _here)
from workdir import WINDOWS_PATH_LIMIT  # noqa: E402

sys.path.remove(_here)
_research = str(Path(__file__).resolve().parent.parent.parent / "philosophy-research" / "scripts")
sys.path.insert(0, _research)
from fetch_web import MIN_PRINTABLE_RATIO, _printable_ratio  # noqa: E402
from generate_bibliography import clean_bibtex_str  # noqa: E402

sys.path.remove(_research)


class FulltextError(Exception):
    """Extraction failure; `reason` is one of encrypted, no-text, unreadable,
    too-large, parse."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class QuoteFormError(ValueError):
    """A quote written in a form the matcher refuses, whatever the text says.
    `reason` is "bracket" or "ellipsis". check_quotes.py catches this base;
    a plain ValueError (a page map that does not fit the text) is a
    programming error and is not one of these."""
    reason = "form"


class QuoteBracketError(QuoteFormError):
    """Bracketed text other than one letter (`FAIL bracket`)."""
    reason = "bracket"


class QuoteEllipsisError(QuoteFormError):
    """An ellipsis-split quote with a part shorter than MIN_ELLIPSIS_PART_WORDS."""
    reason = "ellipsis"


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

MAX_PDF_BYTES = 200 * 1024 * 1024   # the local-file cap
MIN_TEXT_CHARS = 200
SCHEMA = 1
SOURCES = frozenset({"repository", "zotero", "folder", "openalex", "s2", "user"})
STORE_REL = "intermediate_files/fulltext"
STEM_MAX = 64
HASH_LEN = 12
ELLIPSIS_WINDOW = 2000
MIN_ELLIPSIS_PART_WORDS = 3

MARKER_RE = re.compile(r"^\[\[(page|sheet) ([0-9]+)\]\]$", re.M)
SLUG_RE = re.compile(r"^(?:doi-[a-z0-9._-]+|t-[a-z0-9_-]+)-[0-9a-f]{12}$")
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)   # as measured
_NUM_RE = re.compile(r"(?<![\d.])(\d{1,4})(?![\d.])")   # as measured
_ARTICLE_NO_RE = re.compile(r"^[A-Za-z]*[0-9]+$")


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def extract_pages(pdf_bytes: bytes) -> list[str]:
    """pypdf `extract_text()` per page, raw. Raises FulltextError."""
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise FulltextError("too-large")
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        raise FulltextError("parse")
    try:
        encrypted = reader.is_encrypted
    except Exception:
        raise FulltextError("parse")
    if encrypted:
        try:
            ok = reader.decrypt("")
        except Exception:
            raise FulltextError("encrypted")
        if not ok:   # PasswordType.NOT_DECRYPTED == 0
            raise FulltextError("encrypted")
    from pypdf.errors import DependencyError
    try:
        pages = [page.extract_text() or "" for page in reader.pages]
    except DependencyError:
        # AES-encrypted (owner password only) and no `cryptography` package:
        # pypdf decrypts the key but cannot decrypt the streams.
        raise FulltextError("encrypted")
    except Exception:
        raise FulltextError("parse")
    joined = "".join(pages)
    if len(joined.strip()) < MIN_TEXT_CHARS:
        raise FulltextError("no-text")
    if _printable_ratio(joined) < MIN_PRINTABLE_RATIO:
        raise FulltextError("unreadable")
    return pages


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

def fold(text: str) -> str:
    """The measurement's fold: NFKD, ASCII, lowercase, non-alphanumerics to
    spaces, whitespace collapsed."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def title_phrase(title: str) -> str:
    """DOI-rule phrase: the full title's first 6 folded words."""
    return " ".join(fold(title).split()[:6])


def title_phrase_cut(title: str) -> str:
    """Rule-A phrase: the title cut at its first `:`, `?` or `.` when that
    part folds to at least 2 words, then the first 6 folded words."""
    head = re.split(r"[:?.]", title or "")[0]
    base = head if len(fold(head).split()) >= 2 else (title or "")
    return " ".join(fold(base).split()[:6])


def identity_ok(pages: list[str], identity: Mapping) -> tuple[bool, str]:
    """Is this PDF (raw `extract_pages` output) the work? (ok, reason).

    Accept reasons: "doi", "title" (DOI work, title fallback), "title_head"
    (no-DOI rule A). Reject reasons: "empty_identity", "other_doi_page1",
    "no_match"."""
    doi = normalize_doi(identity.get("doi") or "")
    # Raw bib values carry LaTeX (M{\"u}ller), which the fold would split
    # into "m u ller"; decode first, as the References do. Idempotent on
    # plain text, so a caller may pass decoded or raw values.
    phrase_src = clean_bibtex_str(identity.get("title") or "")
    surname = fold(clean_bibtex_str(identity.get("surname") or ""))
    if doi:
        raw3 = "\f".join(pages[:3]).lower()
        # A whole DOI, not the start of a longer one (10.1/abc in 10.1/abcd);
        # a sentence's closing period may follow.
        if re.search(re.escape(doi) + r"(?![a-z0-9_/-]|\.[a-z0-9])", raw3):
            return True, "doi"
        p1 = pages[0] if pages else ""
        if any(x.lower().rstrip(".,;)") != doi for x in DOI_RE.findall(p1)):
            return False, "other_doi_page1"
        phrase = title_phrase(phrase_src)
        if not phrase or not surname:
            return False, "empty_identity"
        folded = fold("\f".join(pages[:3]))
        if phrase in folded and f" {surname} " in f" {folded} ":
            return True, "title"
        return False, "no_match"
    phrase = title_phrase_cut(phrase_src)
    if not phrase or not surname:
        return False, "empty_identity"
    for page in pages[:5]:
        pg = fold(page)
        k = pg.find(phrase)
        if 0 <= k < 600 and f" {surname} " in f" {pg} ":
            return True, "title_head"
    return False, "no_match"


# --------------------------------------------------------------------------
# Page confirmation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PageMap:
    """Per PDF page, the confirmed printed number or None. Equality compares
    the numbers only (the barrier compares maps across entries)."""
    numbers: tuple[Optional[int], ...]

    @property
    def confirmed(self) -> list[int]:
        """Indices of the pages that carry a confirmed number."""
        return [i for i, n in enumerate(self.numbers) if n is not None]


def _edge_numbers(page: str) -> set[int]:
    ls = [line for line in page.splitlines() if line.strip()]
    return {int(x) for line in ls[:3] + ls[-3:] for x in _NUM_RE.findall(line)}


def _pages_start(field: str) -> Optional[int]:
    """The printed start the bib `pages` field commits to, or None.

    A range (any dash) gives its numeric start. A no-range value of at least
    5 characters (digits, or a letter prefix) is an article number: printing
    starts at 1. A shorter no-range value is ambiguous and confirms nothing."""
    value = (field or "").strip()
    if not value:
        return None
    if re.search(r"[-‐-―−]", value):
        m = re.match(r"\s*(\d+)", value)
        return int(m.group(1)) if m else None
    if len(value) >= 5 and _ARTICLE_NO_RE.match(value):
        return 1
    return None


def confirm_pages(pages: list[str], bib_pages_field: str | None) -> PageMap | None:
    """The confirmed page map, or None when the PDF does not confirm the bib's
    pages (pagenum.py's rule plus the article-number rule)."""
    start = _pages_start(bib_pages_field or "")
    if start is None or not pages:
        return None
    nums = [_edge_numbers(p) for p in pages]
    n = len(pages)
    if not pages[-1].strip():   # pagenum.py drops a trailing blank page
        n -= 1
    votes = Counter(x - i for i, s in enumerate(nums) for x in s)
    if not votes:
        return None
    c, hits = votes.most_common(1)[0]
    if not (n >= 3 and hits >= 0.6 * n):
        return None
    if not any(start - k == c for k in range(6)):
        return None
    numbers = tuple((i + c) if (i + c) >= 1 and (i + c) in s else None
                    for i, s in enumerate(nums))
    return PageMap(numbers)


# --------------------------------------------------------------------------
# Text format
# --------------------------------------------------------------------------

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")
_HYPHEN_JOIN_RE = re.compile(r"(?<=[^\W\d_])-[ \t]*\n[ \t]*(?=([^\W\d_]))")
_ESCAPE_RE = re.compile(r"^([ \t]*)\[\[", re.M)


def _clean_page(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = _SURROGATE_RE.sub("�", t)
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _HYPHEN_JOIN_RE.sub(lambda m: "" if m.group(1).islower() else m.group(0), t)
    t = _ESCAPE_RE.sub(r"\1[ [", t)
    return t.rstrip("\n")


def render_text(pages: list[str], page_map: PageMap | None) -> str:
    """The stored text: a marker line per page, then the cleaned page text."""
    if page_map is not None and len(page_map.numbers) != len(pages):
        raise ValueError("page map length differs from the page count")
    out = []
    for i, page in enumerate(pages):
        num = page_map.numbers[i] if page_map is not None else None
        out.append(f"[[page {num}]]" if num is not None else f"[[sheet {i + 1}]]")
        body = _clean_page(page)
        if body:
            out.append(body)
    return "\n".join(out) + "\n"


def page_blocks(text: str) -> list[tuple[str, int, int, int]]:
    """(kind, number, start, end) per marker in rendered text: kind "page" or
    "sheet"; [start, end) is the page's content after its marker line."""
    marks = list(MARKER_RE.finditer(text))
    blocks = []
    for j, m in enumerate(marks):
        start = m.end() + 1 if m.end() < len(text) and text[m.end()] == "\n" else m.end()
        end = marks[j + 1].start() if j + 1 < len(marks) else len(text)
        blocks.append((m.group(1), int(m.group(2)), start, max(start, end)))
    return blocks


def page_map_from_text(text: str) -> PageMap | None:
    """The page map the markers of a rendered text carry (None when it has no
    `[[page N]]` marker). check_quotes.py has only the text, so this is its
    page map."""
    blocks = page_blocks(text)
    if not any(kind == "page" for kind, _, _, _ in blocks):
        return None
    return PageMap(tuple(n if kind == "page" else None for kind, n, _, _ in blocks))


def text_sha256(text: str) -> str:
    """sha256 of the rendered string encoded UTF-8 (`fulltext_text_sha256`)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path) -> str:
    """Read a stored text the one way every verifier must: text mode, UTF-8,
    universal newlines."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def file_text_sha256(path) -> str:
    return text_sha256(read_text(path))


def write_text_atomic(path, text: str) -> None:
    """Write through `<name>.tmp` and os.replace (the name the path budget
    counts), UTF-8, `\\n` newlines."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Store identity: slugs and records
# --------------------------------------------------------------------------

def _year_str(year) -> str:
    return str(year if year is not None else "").strip()


def entry_identity(fields: Mapping) -> dict:
    """The identity of a bib entry as the barrier verified it, in the form the
    attestation blob stores (`fulltext_identity`) and dedupe and
    `check_quotes.py` compare: the normalized DOI or None; the year-less
    `same_work_key` (title, first-author surname) as a list or None; the
    `same_work_year`. `fields` holds RAW values (`parse_entry_fields`)."""
    surname = first_author_surname(fields.get("author") or "", fields.get("editor") or "")
    key = same_work_key(fields.get("title") or "", surname)
    return {"doi": normalize_doi(fields.get("doi") or "") or None,
            "work_key": list(key) if key else None,
            "year": same_work_year(fields.get("year"))}


def identity_matches(blob_identity, fields: Mapping) -> bool:
    """Does a stored `fulltext_identity` still describe this entry? Exact
    equality on all three parts (DOI both absent counts as equal); an entry
    with no work key never matches."""
    if not isinstance(blob_identity, Mapping):
        return False
    now = entry_identity(fields)
    if now["work_key"] is None:
        return False
    stored = {"doi": blob_identity.get("doi"), "work_key": blob_identity.get("work_key"),
              "year": blob_identity.get("year")}
    if isinstance(stored["work_key"], tuple):
        stored["work_key"] = list(stored["work_key"])
    return stored == now


def canonical_identity(identity: Mapping) -> str:
    """`doi:<normalized DOI>`, or `t:<folded title>|<folded surname>|<year>`."""
    doi = normalize_doi(identity.get("doi") or "")
    if doi:
        return f"doi:{doi}"
    title = fold(identity.get("title") or "")
    surname = fold(identity.get("surname") or "")
    year = _year_str(identity.get("year"))
    if not title or not surname or not year:
        raise ValueError("a no-DOI identity needs title, surname and year")
    return f"t:{title}|{surname}|{year}"


def slug_for(identity: Mapping) -> str:
    """The store stem: `doi-<d>-<h>` or `t-<surname>-<year>-<w1>-<w2>-<h>`,
    at most 64 characters, the 12-hex identity hash always kept, the readable
    part never ending in `.`."""
    canon = canonical_identity(identity)
    h = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:HASH_LEN]
    if canon.startswith("doi:"):
        readable = "doi-" + re.sub(r"[^a-z0-9.-]", "_", canon[4:])
    else:
        words = fold(identity.get("title") or "").split()[:2]
        parts = [fold(identity.get("surname") or "").replace(" ", "_"),
                 re.sub(r"[^a-z0-9]", "", _year_str(identity.get("year")).lower()),
                 *words]
        readable = "t-" + "-".join(p for p in parts if p)
    readable = readable[:STEM_MAX - HASH_LEN - 1].rstrip(".")
    return f"{readable}-{h}"


def path_budget_ok(workdir) -> bool:
    """False when the longest store path (a 64-character stem plus
    `.json.tmp`) would exceed workdir.WINDOWS_PATH_LIMIT (`path_too_long`)."""
    wd = Path(workdir).as_posix()
    return (len(wd) + len("/" + STORE_REL + "/") + STEM_MAX + len(".json.tmp")
            <= WINDOWS_PATH_LIMIT)


@dataclass(frozen=True)
class Record:
    stem: str
    identity: dict
    source: str
    source_ref: object
    license: Optional[str]
    pdf_sha256: str
    acquired_at: str
    pdf_path: Path
    txt_path: Path
    json_path: Path


_SIDECAR_KEYS = ("schema", "slug", "identity", "source", "source_ref", "license",
                 "pdf_sha256", "acquired_at")


def _sidecar_shape_ok(data) -> bool:
    if not isinstance(data, dict) or any(k not in data for k in _SIDECAR_KEYS):
        return False
    if type(data["schema"]) is not int or data["schema"] != SCHEMA:
        return False
    ident = data["identity"]
    if not isinstance(ident, dict) or any(k not in ident for k in ("doi", "title", "surname", "year")):
        return False
    if ident["doi"] is not None and not isinstance(ident["doi"], str):
        return False
    # A DOI record may carry null title, surname and year (`--doi D` alone);
    # a no-DOI record needs all three.
    optional = bool(ident["doi"])
    for k in ("title", "surname"):
        if not (isinstance(ident[k], str) or (optional and ident[k] is None)):
            return False
    year = ident["year"]
    if isinstance(year, bool) or not (isinstance(year, (str, int)) or (optional and year is None)):
        return False
    # Type before membership: an unhashable value ("source": []) must read
    # as a malformed sidecar, never raise.
    if not isinstance(data["slug"], str):
        return False
    if not isinstance(data["source"], str) or data["source"] not in SOURCES:
        return False
    if not (data["source_ref"] is None or isinstance(data["source_ref"], (str, dict))):
        return False
    if data["license"] is not None and not isinstance(data["license"], str):
        return False
    if not isinstance(data["acquired_at"], str):
        return False
    sha = data["pdf_sha256"]
    return isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha) is not None


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_record(directory, stem: str) -> Record | str:
    """The one definition of a usable store record. A Record, or a reason:
    bad_slug, sidecar_unreadable, pdf_missing, pdf_hash_mismatch."""
    if not isinstance(stem, str) or len(stem) > STEM_MAX or not SLUG_RE.match(stem):
        return "bad_slug"
    d = Path(directory)
    json_path, pdf_path = d / f"{stem}.json", d / f"{stem}.pdf"
    try:
        data = json.loads(read_text(json_path))
    except (OSError, ValueError, RecursionError):
        return "sidecar_unreadable"
    if not _sidecar_shape_ok(data):
        return "sidecar_unreadable"
    if data["slug"] != stem:
        return "bad_slug"
    try:
        if slug_for(data["identity"]) != stem:
            return "bad_slug"
    except ValueError:
        return "bad_slug"
    if not pdf_path.is_file():
        return "pdf_missing"
    try:
        actual = _file_sha256(pdf_path)
    except OSError:
        return "pdf_missing"
    if actual != data["pdf_sha256"]:
        return "pdf_hash_mismatch"
    return Record(stem=stem, identity=dict(data["identity"]), source=data["source"],
                  source_ref=data["source_ref"], license=data["license"],
                  pdf_sha256=data["pdf_sha256"], acquired_at=str(data["acquired_at"]),
                  pdf_path=pdf_path, txt_path=d / f"{stem}.txt", json_path=json_path)


# --------------------------------------------------------------------------
# Quote matching
# --------------------------------------------------------------------------

_QUOTE_CHARS = frozenset("\"'`´‘’‚‛“”„‟"
                         "′″«»‹›")
_DASH_CHARS = frozenset("-‐‑‒–—―−﹘﹣－")
_DROP_CHARS = frozenset("­​‌‍⁠﻿")
_NEWLINES = frozenset("\n\r\f\v\x85  ")
_ELLIPSIS_RE = re.compile(r"\.(?:[ \t]?\.){2,}|…")
# A bracketed ellipsis ([...], […], [. . .]) is an ellipsis, not a bracket.
_BRACKETED_ELLIPSIS_RE = re.compile(r"\[\s*(?:\.(?:[ \t]?\.){2,}|…)\s*\]")
_BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")


FURNITURE_MAX_WORDS = 12
HEAD_MAX_OTHER_WORDS = 6
_DIGITS_ONLY_RE = re.compile(r"[\W_]*\d+[\W_]*")


def _furniture_key(line: str) -> str:
    return " ".join(re.sub(r"[0-9]", " ", fold(line)).split())


def _words(line: str) -> list[str]:
    return [w for w in line.split() if any(c.isalnum() for c in w)]


def furniture_lines(text: str) -> list[tuple[int, int]]:
    """(start, end) of the page-furniture lines of a rendered text, which the
    quote fold skips so a quote may run across a page break. The rendered
    text is unchanged.

    Only lines AT a page break can be skipped: the contiguous run of
    furniture lines directly after a marker and the one directly before the
    next marker (or the end), each within the block's first or last 3
    non-empty lines; the first non-furniture line ends a run. A line is
    furniture when it (a) is digits-only, give or take punctuation and
    spaces (on a `[[page N]]` block, only when that number is N); or (b) on a `[[page N]]` block, carries N as a standalone number
    as its first or last word, with at most 6 other words (a running head
    with the number); or (c) with digits removed, folds equal to an edge
    line of at least 2 other page blocks (a running head or foot) and has at
    most 12 words. A body line is never skipped, or a fabricated quote could
    splice across real text."""
    blocks = page_blocks(text)
    per_block = []   # per block: (kind, num, [(start, end, line)] edge-first-3, edge-last-3)
    for kind, num, start, end in blocks:
        lines, pos = [], start
        for line in text[start:end].split("\n"):
            if line.strip():
                lines.append((pos, pos + len(line), line))
            pos += len(line) + 1
        per_block.append((kind, num, lines))
    seen: dict[str, set[int]] = {}
    for b, (_, _, lines) in enumerate(per_block):
        for i in set(range(min(3, len(lines)))) | set(range(max(0, len(lines) - 3), len(lines))):
            key = _furniture_key(lines[i][2])
            if key:
                seen.setdefault(key, set()).add(b)

    def is_furniture(b, kind, num, line):
        if _DIGITS_ONLY_RE.fullmatch(line):
            # On a confirmed page only its own number: a premise number
            # ("3.") or a year at a page edge is body text.
            return kind != "page" or _NUM_RE.findall(line) == [str(num)]
        words = _words(line)
        if (kind == "page" and words and len(words) - 1 <= HEAD_MAX_OTHER_WORDS
                and (_NUM_RE.findall(words[0]) == [str(num)]
                     or _NUM_RE.findall(words[-1]) == [str(num)])):
            return True
        key = _furniture_key(line)
        return bool(key) and len(words) <= FURNITURE_MAX_WORDS and len(seen.get(key, set()) - {b}) >= 2

    out = set()
    for b, (kind, num, lines) in enumerate(per_block):
        for i in range(min(3, len(lines))):              # leading run
            if not is_furniture(b, kind, num, lines[i][2]):
                break
            out.add(lines[i][:2])
        for i in range(len(lines) - 1, max(-1, len(lines) - 4), -1):   # trailing run
            if not is_furniture(b, kind, num, lines[i][2]):
                break
            out.add(lines[i][:2])
    return sorted(out)


@functools.lru_cache(maxsize=16)
def _fold_map(s: str) -> tuple[str, tuple[int, ...], tuple[int, ...]]:
    """The quote fold with an index map: (folded, starts, ends), where folded
    char k comes from s[starts[k]:ends[k]].

    Steps, identical for quote and text: marker lines and page-furniture
    lines (`furniture_lines`; a quote has none) become a newline; NFKC
    per cluster (a base character and its combining marks); soft hyphens and
    zero-width characters dropped; every quote mark becomes `'`, every dash
    `-`; a `-` between two letters is dropped (also across a line break, so
    a compound broken at a line end matches); whitespace runs become one
    space."""
    toks: list[tuple[str, int, int]] = []
    pos = 0
    skips = sorted([(m.start(), m.end()) for m in MARKER_RE.finditer(s)] + furniture_lines(s))
    for m in skips + [None]:
        seg_end = m[0] if m else len(s)
        i = pos
        while i < seg_end:
            j = i + 1
            while j < seg_end and unicodedata.combining(s[j]):
                j += 1
            for ch in unicodedata.normalize("NFKC", s[i:j]):
                if ch in _DROP_CHARS:
                    continue
                if ch in _QUOTE_CHARS:
                    ch = "'"
                elif ch in _DASH_CHARS:
                    ch = "-"
                elif ch.isspace():
                    ch = "\n" if ch in _NEWLINES else " "
                toks.append((ch, i, j))
            i = j
        if m:
            toks.append(("\n", m[0], m[1]))
            pos = m[1]
    # Hyphen between letters dropped (with a line break between, too).
    out: list[tuple[str, int, int]] = []
    k = 0
    while k < len(toks):
        ch = toks[k][0]
        if ch == "-" and out and out[-1][0].isalpha():
            j = k + 1
            saw_nl = False
            while j < len(toks) and toks[j][0] in (" ", "\n"):
                saw_nl = saw_nl or toks[j][0] == "\n"
                j += 1
            if j < len(toks) and toks[j][0].isalpha() and (j == k + 1 or saw_nl):
                k = j
                continue
        out.append(toks[k])
        k += 1
    # Whitespace runs to one space.
    chars, starts, ends = [], [], []
    for ch, a, b in out:
        if ch in (" ", "\n"):
            if chars and chars[-1] == " ":
                continue
            ch = " "
        chars.append(ch)
        starts.append(a)
        ends.append(b)
    return "".join(chars), tuple(starts), tuple(ends)


def _split_brackets(quote: str) -> tuple[str, set[int]]:
    """Remove `[X]` single-letter brackets; return the quote and the indices
    of their letters. Any other bracket raises QuoteBracketError."""
    out, ci, last = [], set(), 0
    for m in _BRACKET_RE.finditer(quote):
        inner = m.group(1)
        if len(inner) != 1 or not inner.isalpha():
            raise QuoteBracketError(f"bracketed text {m.group(0)!r}")
        out.append(quote[last:m.start()])
        ci.add(sum(len(x) for x in out))
        out.append(inner)
        last = m.end()
    out.append(quote[last:])
    q = "".join(out)
    if "[" in q or "]" in q:
        raise QuoteBracketError("unbalanced bracket")
    return q, ci


def _part_patterns(quote: str, literal: bool = False) -> list[re.Pattern]:
    """One compiled pattern per ellipsis part: the folded part, with its
    first letter and each bracketed letter matched case-insensitively."""
    quote = _BRACKETED_ELLIPSIS_RE.sub("...", quote)
    q, ci_raw = (quote, set()) if literal else _split_brackets(quote)
    pieces, last = [], 0
    for m in _ELLIPSIS_RE.finditer(q):
        pieces.append((last, q[last:m.start()]))
        last = m.end()
    pieces.append((last, q[last:]))
    folded_parts = []
    for off, text in pieces:
        folded, starts, _ = _fold_map(text)
        lead = len(folded) - len(folded.lstrip(" "))
        folded_s = folded.strip(" ")
        if not folded_s:
            continue
        ci = {k - lead for k, st in enumerate(starts) if off + st in ci_raw}
        ci.add(0)
        folded_parts.append((folded_s, ci))
    if len(folded_parts) > 1:
        for f, _ in folded_parts:
            if sum(1 for w in f.split() if any(c.isalnum() for c in w)) < MIN_ELLIPSIS_PART_WORDS:
                raise QuoteEllipsisError(f"ellipsis part shorter than {MIN_ELLIPSIS_PART_WORDS} words: {f!r}")
    pats = []
    for f, ci in folded_parts:
        rx = "".join(f"(?i:{re.escape(ch)})" if (k in ci and ch.isalpha()) else re.escape(ch)
                     for k, ch in enumerate(f))
        pats.append(re.compile(rx))
    return pats


def _quotable_range(text: str, page_map: PageMap | None) -> tuple[int, int]:
    if page_map is None or not page_map.confirmed:
        return 0, len(text)
    blocks = page_blocks(text)
    if len(blocks) != len(page_map.numbers):
        raise ValueError("page map length differs from the text's page markers")
    conf = page_map.confirmed
    return blocks[conf[0]][2], blocks[conf[-1]][3]


def _match_all(pats: list[re.Pattern], folded: str, starts, ends, lo: int, hi: int):
    f_lo = bisect.bisect_left(starts, lo)
    f_hi = bisect.bisect_left(starts, hi)
    first = re.compile(f"(?=({pats[0].pattern}))")
    results = []
    for m in first.finditer(folded, f_lo, f_hi):
        a, b = m.start(1), m.end(1)
        if b == a:
            continue
        spans = [(a, b)]
        pos = b
        for p in pats[1:]:
            nm = p.search(folded, pos, f_hi)
            if nm is None:
                break
            spans.append((nm.start(), nm.end()))
            pos = nm.end()
        if len(spans) != len(pats):
            break   # later parts not found after this start: none after a later one either
        if spans[-1][1] - spans[0][0] > ELLIPSIS_WINDOW:
            continue
        results.append([(starts[x], ends[y - 1]) for x, y in spans])
    return results


def locate_quote_all(quote: str, text: str, page_map: PageMap | None = None) -> list[list[tuple[int, int]]]:
    """Every occurrence of the quote in the rendered text, each a list of
    (start, end) rendered offsets, one per ellipsis part. Raises
    QuoteBracketError / QuoteEllipsisError.

    A quote that fails as written is retried without one trailing `.` or `,`
    (Chicago puts both inside the closing quotation mark). A quote with
    brackets is first tried literally (the source may carry them, `[1]`);
    only when that fails do the bracket rules apply: one letter, a case
    variant replacing the source letter; anything else QuoteBracketError."""
    variants = [quote.strip()]
    if variants[0][-1:] in (".", ","):
        variants.append(variants[0][:-1])
    folded, starts, ends = _fold_map(text)
    lo, hi = _quotable_range(text, page_map)
    modes = [True, False] if ("[" in quote or "]" in quote) else [False]
    for literal in modes:
        for v in variants:
            pats = _part_patterns(v, literal=literal)
            if not pats:
                return []
            found = _match_all(pats, folded, starts, ends, lo, hi)
            if found:
                return found
    return []


def locate_quote(quote: str, text: str, page_map: PageMap | None = None) -> list[tuple[int, int]] | None:
    """The first occurrence of the quote: a (start, end) rendered-offset span
    per ellipsis part, or None. When `page_map` has confirmed pages, only the
    span from the first to the last confirmed page is quotable."""
    found = locate_quote_all(quote, text, page_map)
    return found[0] if found else None


def span_pages(text: str, spans: list[tuple[int, int]]) -> list[tuple[str, int]]:
    """The (kind, number) of every page block the spans touch, in text order:
    ("page", 899) for a confirmed page, ("sheet", 3) otherwise."""
    touched = []
    for kind, num, start, end in page_blocks(text):
        if any(a < end and b > start for a, b in spans):
            touched.append((kind, num))
    return touched
