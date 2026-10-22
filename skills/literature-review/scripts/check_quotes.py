"""Phase 6 quotation gate for EVIDENCE-FULLTEXT works.

Scans the assembled review for double-quoted spans (straight or curly, at
least 2 words, in the body: not headings, not code, not `## References`),
attributes each to the citations of its sentence (else the next sentence's),
and checks every span attributed to a WATCHED entry (a merged entry with a
`fulltext_file` field, or one stamped EVIDENCE-FULLTEXT) against the text the
barrier verified:

- `FAIL licence-lost`: the watched entry is no longer FULLTEXT, has no
  authorizing attestation (key, slug and identity all matching, across every
  domain bib in the barrier report), or its text file is missing, unreadable
  or hashes differently from the attestation. Judged by the tier it holds
  NOW: an entry that is EVIDENCE-ABSTRACT passes when its abstract holds the
  quote (that tier licenses abstract quotes); no other fallback.
- `FAIL verbatim` / `FAIL bracket` / `FAIL ellipsis`: the span is in none of
  the licensed texts of the cited works (FULLTEXT texts, and the abstracts of
  ABSTRACT entries), or is written in a form the matcher refuses.
- `FIX page`: a page locator given with the citation names no `[[page N]]`
  page the quoted words sit on (fix: drop or correct the locator, never cut
  the quote).
- `WARN cap`: above 40 words in one quotation, above 150 words per work
  (works grouped across keys and slugs: same work key, or same DOI).
- `WARN uncited-fulltext`: a quoted span of 4 words or more with no citation
  in its sentence or the next, whose words a licensed full text holds; the
  line names each such work and where its text has the words. Usually a
  quotation of that work, but a common phrase or a question can match by
  chance, and one work can quote another.
- `WARN uncited`: any other such span (often a question or a scare-quoted
  thesis, sometimes a quotation of a work with no full text).

Then one `QUOTES-SUMMARY: {json}` line. Exit 1 when any FAIL, 0 otherwise, 2
on a crash or unreadable input (one line on stderr).

WHY SEPARATE FROM check_evidence.py: that script is telemetry with a fixed
contract (always exit 0, `CHECK` lines, a human adjudicates every hit). This
one is an accuracy gate: verbatim accuracy fails closed (a misquotation is a
fabrication), pages and caps are pragmatic (ruling in
`docs/ideas/fulltext-evidence-tier.md`). Mixing the two would change what the
telemetry's exit code means.

COMPLETION RULE (SKILL.md Phase 6): rerun until there is no FAIL and no FIX.
The WARN lines are advisory. On `WARN uncited-fulltext` the orchestrator
decides which named work, if any, the words quote, cites it and reruns, so
the gate checks pages and caps; on `WARN uncited` it cites a quotation and
leaves a question or scare quote alone; on `WARN cap` it shortens where
possible.

OWNERS USED, never re-implemented: quote matching, page maps, text reading
and hashing, identity comparison (`fulltext.py`); citation resolution
(`check_evidence.find_cites`, fed `bib_identity.first_author_surname` so an
editor-only entry resolves); the References boundary
(`lint_md.find_refs_heading`); BibTeX decoding of abstracts and titles
(`generate_bibliography.clean_bibtex_str`). The merged-bib entry table (year,
Chicago letter, last EVIDENCE token) MIRRORS the loop inline in
`check_evidence.main()`, which cannot be imported.

RESIDUALS (accepted, visible):
- A quote in a sentence citing two works passes when it is in either text.
- Uncited spans of 2 or 3 words are not reported (scare quotes).
- An uncited MISQUOTATION of a full-text work matches no text, so it is only
  an advisory `WARN uncited`: nothing forces it to be cited and checked. So
  is an accurate uncited quotation in a refused form (a bracket other than
  one letter, an ellipsis part too short): the matcher refuses the form
  before it searches. A blocking `WARN uncited` would force a response to
  these, at the cost of extra turns on most reviews (70 lines in 27 of 43 delivered reviews, about half of them
  quoted questions).
- `WARN uncited-fulltext` names the work whose text holds the words, which
  is not always the work quoted: a full text that itself quotes another work
  is named for that work's words. The orchestrator decides.
- An uncited quoted title of 4 words or more that a full text holds is
  `WARN uncited-fulltext` (the title skip needs a citation); once cited, it
  is skipped as a title.
- An uncited span a full text holds counts toward neither cap until it is
  cited.
- A span whose sentence (or the next) cites only works WITHOUT a full text
  is never searched: `"<Singer's words>" (Regan 1983)` gets no line at all.
- A full-text work with no surname or no four-digit year is not citable for
  this gate, so its text is not searched for uncited spans either.
- A block quotation (`> ...`) without quotation marks is not checked (an
  opening mark with no close in its paragraph is `FAIL unclosed-quote`).
- "Next sentence" attribution stays inside the paragraph.
- Locators are read from parenthetical citations only (`, 45` or `: 45`
  after the year); a locator holding its own brackets is one unrecognized
  item (a FIX). Every comma-separated item is checked (`45 n. 3` and `45ff.` as page 45); `ch.`, `sec.`, `n.`,
  `vol.` items and digit-free notes (`emphasis added`) name no page and are
  skipped; a roman numeral or an unreadable item is a FIX. A bare 1500-2099
  number without `p.`/`pp.` is a page when an attributed full text has that
  `[[page N]]` marker, else a second year (`(Smith 2020, 2021)`), unchecked.
- A locator in a parenthesis right after the quote (`"..." (45)`) is checked
  against every licensed watched work of the attribution; it passes when any
  of them has the quote on that page.
- A LaTeX-escaped surname (`B{\\"o}hm`) matches no prose (check_evidence's
  residual).
- Sentence segmentation is heuristic (abbreviations, initials); a wrong cut
  moves attribution to the neighbouring sentence.
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from pathlib import Path

_here = str(Path(__file__).resolve().parent)
sys.path.insert(0, _here)
import check_evidence as ce  # noqa: E402
import fulltext as ft  # noqa: E402
import stamp_evidence as se  # noqa: E402
from generate_bibliography import clean_bibtex_str  # noqa: E402
from lint_md import find_refs_heading  # noqa: E402

if _here in sys.path:
    sys.path.remove(_here)

_hook_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "hooks")
sys.path.insert(0, _hook_dir)
from bib_identity import first_author_surname, title_key  # noqa: E402

sys.path.remove(_hook_dir)

TIER_FULLTEXT = se.TIER_FULLTEXT
TIER_ABSTRACT = se.TIER_ABSTRACT

CAP_SPAN_WORDS = 40
CAP_WORK_WORDS = 150
MIN_SPAN_WORDS = 2
MIN_UNCITED_WORDS = 4
SPAN_SHOW = 100

_FIELD_RE = re.compile(r"^" + re.escape(ft.STORE_REL) + r"/([^/\\]+)\.txt$")
_OPEN_Q = "\"“"
_CLOSE_Q = "\"”"
_DASHES = "-‐‑‒–—―−"
# Tokens that end with "." without ending a sentence.
_ABBREV = frozenset({"e.g", "i.e", "cf", "vs", "viz", "al", "ch", "chap", "p", "pp",
                     "vol", "vols", "ed", "eds", "trans", "no", "sec", "fn", "n",
                     "nn", "esp", "repr", "ibid", "op", "cit", "approx", "ca", "c",
                     "st", "mr", "mrs", "ms", "dr", "prof"})
# The start of a locator after a citation's year: `, 45` or `: 45`.
_LOC_LEAD_RE = re.compile(r"\s*[,:]\s*")
# A parenthesis right after the closing quotation mark: `"..." (45)`.
_TRAIL_PAREN_RE = re.compile(r"\s*\(\s*([^()\n]{1,60}?)\s*\)")
_PAGE_PREFIX_RE = re.compile(r"^pp?\.\s*", re.I)
# Locator items that name no page: chapter, section, note, volume, line...
_NONPAGE_RE = re.compile(r"^(?:ch|chap|chapter|sec|section|§|pt|part|bk|book|vol|vols|fig|"
                         r"table|tab|n|nn|note|notes|fn|art|para|par|¶|l|ll|line|lines)"
                         r"(?![A-Za-z])\.?", re.I)
_PAGE_ITEM_RE = re.compile(
    r"^(?P<a>\d+)(?:\s*[" + _DASHES + r"]+\s*(?P<b>\d+))?"
    r"(?:\s*(?:nn?\.?\s*\d+(?:\s*[" + _DASHES + r"]+\s*\d+)?|ff?\.?))?$", re.I)
_ROMAN1 = r"m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
_ROMAN_ITEM_RE = re.compile(
    r"^(?=[ivxlcdm])" + _ROMAN1 + r"(?:\s*[" + _DASHES + r"]+\s*(?=[ivxlcdm])" + _ROMAN1 + r")?$",
    re.I)
_YEARLIKE_RE = re.compile(r"^(?:1[5-9]|20)[0-9]{2}$")


class InputError(Exception):
    """Unreadable or malformed input: exit 2."""


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def _show(span: str) -> str:
    s = " ".join(span.split())
    if len(s) > SPAN_SHOW:
        s = s[:SPAN_SHOW - 3] + "..."
    return _ascii(s)


def _words(text: str) -> int:
    return sum(1 for w in text.split() if any(c.isalnum() for c in w))


def _quote_words(span: str) -> int:
    """Words of the quoted text itself: ellipses are not words."""
    return _words(re.sub(r"\[\s*(?:\.\s*){3,}\]|\[\s*…\s*\]|(?:\.\s*){3,}|…", " ", span))


def _decoded(value: str) -> str:
    """A bib value as prose spells it: LaTeX decoded, braces gone, TeX dashes
    as Unicode dashes (the matcher folds a dash to one `-`, `--` to two)."""
    s = clean_bibtex_str(value or "")
    return s.replace("---", "—").replace("--", "–")


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def load_entries(bib_text: str) -> dict:
    """key -> entry info from the merged bib. Mirrors check_evidence.main()'s
    table (4-digit year, one-letter suffix, last EVIDENCE token) and keeps the
    raw fields. The surname differs on purpose: `first_author_surname(author,
    editor)`, the extractor the barrier binds with, so an edited volume cited
    by its editor resolves; case-protection braces come off (a LaTeX escape
    group keeps them, as in check_evidence's rule)."""
    entries = {}
    for chunk in se.split_entries(bib_text):
        header = se.entry_header(chunk)
        if not header:
            continue
        _etype, key = header
        fields = se.parse_entry_fields(chunk)
        surname = first_author_surname(fields.get("author") or "", fields.get("editor") or "")
        if "\\" not in surname:
            surname = surname.replace("{", "").replace("}", "")
        year = (fields.get("year") or "").strip()
        raw_suffix = (fields.get("year_suffix") or "").strip().lower()
        suffix = (raw_suffix if len(raw_suffix) == 1 and raw_suffix.isalpha()
                  and raw_suffix.isascii() else "")
        tiers = ce._TIER_RE.findall(fields.get("keywords", ""))
        citable = bool(surname) and re.fullmatch(r"\d{4}", year) is not None
        entries[key] = {"fields": fields, "surname": surname, "year": year,
                        "suffix": suffix, "tier": tiers[-1] if tiers else None,
                        "citable": citable}
    return entries


def license_status(key: str, info: dict, report: dict, workdir: Path):
    """(text, None) when the watched entry's text is licensed now, else
    (None, why). The authorizing blob: same key in any domain bib,
    `fulltext_verified is True`, slug equal to the one `fulltext_file` names,
    `identity_matches`, and the text's hash equal to the blob's."""
    fields = info["fields"]
    if info["tier"] != TIER_FULLTEXT:
        return None, f"not {TIER_FULLTEXT} now ({info['tier'] or 'unstamped'})"
    value = fields.get("fulltext_file")
    if value is None:
        return None, "no fulltext_file field"
    m = _FIELD_RE.match(value.strip())
    if not m or not ft.SLUG_RE.match(m.group(1)) or len(m.group(1)) > ft.STEM_MAX:
        return None, "malformed fulltext_file"
    slug = m.group(1)
    candidates = []
    for blobs in report.get("attestations", {}).values():
        blob = blobs.get(key) if isinstance(blobs, dict) else None
        if not isinstance(blob, dict):
            continue
        if blob.get("fulltext_verified") is not True or blob.get("fulltext_slug") != slug:
            continue
        if not ft.identity_matches(blob.get("fulltext_identity"), fields):
            continue
        candidates.append(blob)
    if not candidates:
        return None, "no authorizing attestation"
    path = workdir / ft.STORE_REL / f"{slug}.txt"
    if not path.is_file():
        return None, "text missing"
    try:
        text = ft.read_text(path)
    except (OSError, UnicodeDecodeError):
        return None, "text unreadable"
    digest = ft.text_sha256(text)
    if not any(b.get("fulltext_text_sha256") == digest for b in candidates):
        return None, "text hash differs"
    return text, None


# --------------------------------------------------------------------------
# Review body: masking, spans, sentences
# --------------------------------------------------------------------------

def mask_body(md: str) -> tuple[str, list[int]]:
    """The body (before `## References`) with YAML frontmatter, HTML
    comments, fenced code, heading lines and inline code blanked (offsets
    kept), and the offsets of heading lines."""
    refs = find_refs_heading(md)
    body = md[:refs[0]] if refs else md

    def blank_match(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    # YAML frontmatter (a leading --- ... --- or ... block) and HTML comments.
    body = re.sub(r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?=\n|\Z)", blank_match, body, flags=re.S)
    body = re.sub(r"<!--.*?(?:-->|\Z)", blank_match, body, flags=re.S)
    out, headings = [], []
    in_fence = False
    offset = 0
    for line in body.splitlines(keepends=True):
        stripped = line.lstrip()
        blank = False
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            blank = True
        elif in_fence:
            blank = True
        elif re.match(r"^ {0,3}#", line):
            headings.append(offset)
            blank = True
        if blank:
            out.append(re.sub(r"[^\n]", " ", line))
        else:
            out.append(re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line))
        offset += len(line)
    return "".join(out), headings


def paragraphs(masked: str) -> list[tuple[int, int]]:
    """(start, end) of each paragraph: runs separated by blank lines."""
    out = []
    for m in re.finditer(r"(?:[^\n]*\S[^\n]*(?:\n|$))+", masked):
        out.append((m.start(), m.end()))
    return out


def find_spans(masked: str, paras) -> tuple[list[tuple[int, int, int]], list[tuple[int, int]]]:
    """((open, close, paragraph index) of every double-quoted span, paired
    within a paragraph; (offset, paragraph end) of each opening mark with no
    close in its paragraph). Single quotes and apostrophes are never quotation marks here."""
    spans, unclosed = [], []
    for pi, (a, b) in enumerate(paras):
        i = a
        while i < b:
            if masked[i] in _OPEN_Q:
                j = i + 1
                while j < b and masked[j] not in _CLOSE_Q and masked[j] != "“":
                    j += 1
                if j < b and masked[j] in _CLOSE_Q:
                    spans.append((i, j, pi))
                    i = j + 1
                    continue
                unclosed.append((i, b))
            i += 1
    return spans, unclosed


def _is_boundary(masked: str, k: int, lo: int) -> bool:
    """Does the `.`/`!`/`?` at k end a sentence?"""
    ch = masked[k]
    if ch == ".":
        m = re.search(r"([A-Za-z.]+)$", masked[lo:k])
        tok = m.group(1).lower().strip(".") if m else ""
        if tok in _ABBREV or (len(tok) == 1 and tok.isalpha()):
            return False
        if re.search(r"(?:^|\s)[A-Z]$", masked[lo:k]):
            return False   # an initial: "O. O'Neill"
    j = k + 1
    while j < len(masked) and masked[j] in ")]\"'”’*_":
        j += 1
    if j >= len(masked):
        return True   # a paragraph's last sentence ends at the paragraph anyway
    if not masked[j].isspace():
        return False
    while j < len(masked) and masked[j].isspace():
        j += 1
    while j < len(masked) and masked[j] in "\"“*_[":
        j += 1
    return j < len(masked) and masked[j].isupper()


def _paren_pairs(masked: str, a: int, b: int, spans) -> list[tuple[int, int]]:
    """Matched parentheses in [a, b), outside quoted spans. An unmatched `(`
    protects nothing, so one stray bracket cannot swallow a paragraph."""
    pairs, stack = [], []
    k = a
    for o, c in sorted(spans) + [(b, b)]:
        while k < min(o, b):
            if masked[k] == "(":
                stack.append(k)
            elif masked[k] == ")" and stack:
                pairs.append((stack.pop(), k))
            k += 1
        k = max(k, c + 1)
    return pairs


def sentences(masked: str, paras, spans) -> list[tuple[int, int, int]]:
    """(start, end, paragraph index) of each sentence. Quoted spans and
    matched parentheses are opaque: their inner `.` never cuts (Chicago's
    `."`, `p.`, `et al.` inside a citation)."""
    out = []
    for pi, (a, b) in enumerate(paras):
        span_list = [(o, c) for o, c, _ in spans if a <= o < b]
        protected = span_list + _paren_pairs(masked, a, b, span_list)
        start = a
        k = a
        while k < b:
            hit = next(((o, c) for o, c in span_list if o == k), None)
            if hit is not None:
                k = hit[1] + 1
                # A span ending in a terminator, followed by a capital: cut.
                if masked[hit[1] - 1] in ".!?" and _is_boundary(masked, hit[1], start) \
                        and not re.match(r"\s*\(", masked[k:b]):
                    out.append((start, k, pi))
                    start = k
                continue
            if masked[k] in ".!?" and not any(o < k < c for o, c in protected) \
                    and _is_boundary(masked, k, start):
                out.append((start, k + 1, pi))
                start = k + 1
            k += 1
        if masked[start:b].strip():
            out.append((start, b, pi))
    return out


# --------------------------------------------------------------------------
# Citations and locators
# --------------------------------------------------------------------------

def _expand(a: str, b: str | None) -> tuple[int, int]:
    lo = int(a)
    if b is None:
        return lo, lo
    hi = int(b)
    if hi < lo and len(b) < len(a):
        hi = int(a[:len(a) - len(b)] + b)   # Chicago 145-46
    return lo, hi


def parse_locator_items(text: str) -> list[tuple]:
    """The comma-separated items of a locator, each one of:
    ("page", lo, hi, raw) - `45`, `45-46`, `p. 45`, `145-46`, and `45 n. 3`
      or `45ff.` as page 45;
    ("year", n, raw) - a bare 1500-2099 number: a second year unless an
      attributed text has that page (the caller decides);
    ("roman", raw) - never confirmable, markers carry arabic numbers;
    ("unrecognized", raw).
    Items naming no page (`ch. 3`, `sec. 2`, `n. 4`, `emphasis added`) are
    left out."""
    items = []
    for raw in (x.strip() for x in text.split(",")):
        if not raw:
            continue
        pm = _PAGE_PREFIX_RE.match(raw)
        body = raw[pm.end():] if pm else raw
        if not pm and _NONPAGE_RE.match(body):
            continue
        m = _PAGE_ITEM_RE.match(body)
        if m:
            if not pm and m.group("b") is None and m.end("a") == len(body) \
                    and _YEARLIKE_RE.match(m.group("a")):
                items.append(("year", int(m.group("a")), raw))
            else:
                items.append(("page", *_expand(m.group("a"), m.group("b")), raw))
        elif _ROMAN_ITEM_RE.match(body):
            items.append(("roman", raw))
        elif pm or any(ch.isdigit() for ch in body):
            items.append(("unrecognized", raw))
    return items


def _in_parenthesis(masked: str, pos: int, para_lo: int) -> bool:
    """Is pos inside an unmatched `(` opened since the paragraph start? (A
    citation with a long author list still counts.)"""
    depth = 0
    for k in range(pos - 1, para_lo - 1, -1):
        ch = masked[k]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                return True
            depth -= 1
    return False


def _locator_tail(masked: str, start: int, para_hi: int) -> str | None:
    """The text from start to the end of the citation: the first `;`, `)` or
    `]` outside nested brackets. None when the paragraph ends first."""
    depth = 0
    for k in range(start, para_hi):
        ch = masked[k]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            if depth == 0:
                return masked[start:k]
            depth -= 1
        elif ch == ";" and depth == 0:
            return masked[start:k]
    return None


def citation_locator(masked: str, pos: int, info: dict, para: tuple[int, int]) -> list[tuple] | None:
    """The locator items written with the citation whose surname is at pos
    (parenthetical citations only: `(Smith 2020, 45)`, `(Smith 2020: 45)`,
    `Smith (2020, 45)`), or None. A tail holding its own brackets
    (`45 (see also 47)`) cannot be read item by item: it is one unrecognized
    item, so it is fixed, never skipped."""
    year_re = re.compile(r"(?<!\d)" + re.escape(info["year"]) + r"[a-z]?(?!\d)", re.I)
    ym = year_re.search(masked, pos, min(len(masked), pos + len(info["surname"]) + ce._MATCH_WINDOW))
    if not ym or not _in_parenthesis(masked, ym.start(), para[0]):
        return None
    lead = _LOC_LEAD_RE.match(masked, ym.end())
    if not lead:
        return None
    tail = _locator_tail(masked, lead.end(), para[1])
    if tail is None:
        raw = " ".join(masked[lead.end():min(para[1], lead.end() + 60)].split())
        return [("unrecognized", raw)]
    tail = " ".join(tail.split())
    if not tail:
        return None
    if any(ch in tail for ch in "()[]"):
        return [("unrecognized", tail)]
    return parse_locator_items(tail)


def trailing_locator(masked: str, close: int) -> list[tuple] | None:
    """Locator items of a parenthesis right after the closing quotation mark,
    when it reads as a locator (its first item starts with a digit, `p.` or is
    a roman numeral), else None (`(Smith 2020)`, `(emphasis added)`)."""
    tm = _TRAIL_PAREN_RE.match(masked, close + 1)
    if not tm:
        return None
    first = tm.group(1).split(",")[0].strip()
    if not (first[:1].isdigit() or _PAGE_PREFIX_RE.match(first) or _ROMAN_ITEM_RE.match(first)):
        return None
    return parse_locator_items(tm.group(1))


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def _match_quote(quote: str, sources):
    """Try every source; (hits, form_error). hits: [(key, kind, text,
    occurrences)] for each source holding the quote."""
    hits, form_error = [], None
    for key, kind, text, pm in sources:
        try:
            occ = ft.locate_quote_all(quote, text, pm)
        except ft.QuoteFormError as e:
            form_error = form_error or e
            continue
        if occ:
            hits.append((key, kind, text, occ))
    return hits, form_error


_EMPH_STAR_RE = re.compile(r"(?<![\w*])(\*{1,3})(?=[^\s*])(.+?)(?<=[^\s*])\1(?![\w*])")
_EMPH_UNDER_RE = re.compile(r"(?<![A-Za-z0-9_])(_{1,3})(?=[^\s_])(.+?)(?<=[^\s_])\1(?![A-Za-z0-9_])")


def _clean_span(span: str) -> str:
    """Markdown emphasis is markup, not quoted text: paired `*`/`_` runs at
    word boundaries come off; a literal `*` or `_` stays."""
    s = _EMPH_STAR_RE.sub(r"\2", span)
    return _EMPH_UNDER_RE.sub(r"\2", s)


def _pages_desc(text: str, occurrences) -> str:
    """The page blocks the occurrences of a quote touch: "page 45, sheet 3"."""
    touched = [t for spans in occurrences for t in ft.span_pages(text, spans)]
    return ", ".join(f"{kind} {n}" for kind, n in dict.fromkeys(touched)) or "page unknown"


def _union_groups(keys: list[str], entries: dict) -> dict:
    """Work groups for the per-work cap: two watched entries are one work when
    their work key (same_work_key) is equal or their normalized DOIs are."""
    parent = {k: k for k in keys}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    seen: dict = {}
    for k in keys:
        ident = ft.entry_identity(entries[k]["fields"])
        tags = []
        if ident["work_key"]:
            tags.append(("w", tuple(ident["work_key"])))
        if ident["doi"]:
            tags.append(("d", ident["doi"]))
        for t in tags:
            if t in seen:
                parent[find(k)] = find(seen[t])
            else:
                seen[t] = k
    return {k: find(k) for k in keys}


def run(md: str, bib_text: str, report: dict, workdir: Path) -> tuple[list[str], dict]:
    entries = load_entries(bib_text)
    masked, headings = mask_body(md)
    paras = paragraphs(masked)
    spans, unclosed = find_spans(masked, paras)
    sents = sentences(masked, paras, spans)
    sent_starts = [s for s, _, _ in sents]

    def sentence_of(pos: int) -> int | None:
        i = bisect.bisect_right(sent_starts, pos) - 1
        return i if i >= 0 and pos < sents[i][1] else None

    span_ranges = [(o, c) for o, c, _ in spans]
    cites_by_sentence: dict[int, list[tuple[str, int]]] = {}
    for key, info in entries.items():
        if not info["citable"]:
            continue
        for pos in ce.find_cites(masked, info["surname"], info["year"], info["suffix"]):
            if any(o < pos < c for o, c in span_ranges):
                continue   # a name inside a quotation is not the writer's citation
            si = sentence_of(pos)
            if si is not None:
                cites_by_sentence.setdefault(si, []).append((key, pos))

    watched = {k for k, info in entries.items()
               if "fulltext_file" in info["fields"] or info["tier"] == TIER_FULLTEXT}
    licence = {k: license_status(k, entries[k], report, workdir) for k in sorted(watched)}
    # The page map each licensed text's markers carry, computed once per key.
    page_maps = {k: ft.page_map_from_text(text) for k, (text, _why) in licence.items()
                 if text is not None}
    para_starts = [a for a, _ in paras]
    groups = _union_groups(sorted(watched), entries)
    group_words: dict[str, int] = {}

    lines: list[str] = []
    counts = {"spans": 0, "titles_skipped": 0, "fulltext_attributed": 0,
              "fail_unclosed_quote": 0, "fail_licence_lost": 0, "fail_verbatim": 0,
              "fail_bracket": 0, "fail_ellipsis": 0, "fix_page": 0, "warn_cap": 0,
              "warn_uncited": 0, "warn_uncited_fulltext": 0}
    # Only citable works: citing one the gate cannot resolve would leave the
    # line in place on every rerun.
    uncited_sources = [(k, "fulltext", licence[k][0], page_maps[k]) for k in sorted(watched)
                       if licence[k][0] is not None and entries[k]["citable"]]

    def line_no(pos: int) -> int:
        return md.count("\n", 0, pos) + 1

    # Writers may not use block or multi-paragraph quotations: an opening mark
    # with no close in its paragraph is closed or removed, never guessed at.
    for o, para_end in unclosed:
        lines.append(f'FAIL unclosed-quote: "{_show(md[o + 1:min(o + 61, para_end)])}" '
                     f'[line {line_no(o)}]')
        counts["fail_unclosed_quote"] += 1

    for o, c, _pi in spans:
        span = md[o + 1:c]
        if _words(span) < MIN_SPAN_WORDS:
            continue
        si = sentence_of(o)
        cites = cites_by_sentence.get(si, []) if si is not None else []
        if not cites and si is not None and si + 1 < len(sents):
            nxt = sents[si + 1]
            same_para = nxt[2] == sents[si][2]
            if same_para and not any(sents[si][1] <= h < nxt[0] for h in headings):
                cites = cites_by_sentence.get(si + 1, [])
        # A quoted title of a work the span is attributed to (own sentence or
        # the next) is not a quotation.
        sk = title_key(_decoded(span))
        if sk and any((tk == sk or tk.startswith(sk + " "))
                      for tk in (title_key(_decoded(entries[k]["fields"].get("title", "")))
                                 for k, _ in cites)):
            counts["titles_skipped"] += 1
            continue
        counts["spans"] += 1
        where = f"[line {line_no(o)}]"
        shown = _show(span)
        if not cites:
            if _words(span) >= MIN_UNCITED_WORDS:
                # Words a licensed text holds are most likely a quotation of
                # that work: name the work and where, so the orchestrator can
                # cite it (the rerun then checks pages and caps). Anything else
                # is left to its judgment (questions, scare quotes).
                hits, _form_error = _match_quote(_clean_span(span), uncited_sources)
                if hits:
                    found = "; ".join(f"{k} ({_pages_desc(text, occ)})"
                                      for k, _kind, text, occ in hits)
                    lines.append(f'WARN uncited-fulltext: {found}: "{shown}" {where}')
                    counts["warn_uncited_fulltext"] += 1
                else:
                    lines.append(f'WARN uncited: "{shown}" {where}')
                    counts["warn_uncited"] += 1
            continue
        keys = sorted({k for k, _ in cites})
        wkeys = [k for k in keys if k in watched]
        if not wkeys:
            continue
        counts["fulltext_attributed"] += 1
        lost = [k for k in wkeys if licence[k][1] is not None]

        def report_lost(hits=()):
            # A watched entry is judged by the tier it holds NOW: one that is
            # EVIDENCE-ABSTRACT keeps the quote when its abstract holds it.
            # Any other lost entry (a FULLTEXT stamp whose attestation or text
            # fails included) fails.
            rescued = {k for k, kind, _t, _o in hits if kind == "abstract"}
            for k in lost:
                if entries[k]["tier"] == TIER_ABSTRACT and k in rescued:
                    continue
                lines.append(f'FAIL licence-lost: {k} ({licence[k][1]}): "{shown}" {where}')
                counts["fail_licence_lost"] += 1

        sources = [(k, "fulltext", licence[k][0], page_maps[k]) for k in wkeys
                   if licence[k][0] is not None]
        for k in keys:
            info = entries[k]
            if info["tier"] == TIER_ABSTRACT and info["fields"].get("abstract"):
                sources.append((k, "abstract", _decoded(info["fields"]["abstract"]), None))
        if not sources:
            report_lost()
            continue   # nothing licensed to check against: licence-lost fails
        quote = _clean_span(span)
        hits, form_error = _match_quote(quote, sources)
        report_lost(hits)
        if not hits:
            label = ", ".join(keys)
            if form_error is not None and form_error.reason in ("bracket", "ellipsis"):
                lines.append(f'FAIL {form_error.reason}: {label}: "{shown}" {where}')
                counts[f"fail_{form_error.reason}"] += 1
            else:
                lines.append(f'FAIL verbatim: {label}: "{shown}" {where}')
                counts["fail_verbatim"] += 1
            continue
        ft_hits = {k: (text, occ) for k, kind, text, occ in hits if kind == "fulltext"}
        # Pages: a locator with a watched citation, or right after the quote.
        licensed_w = [k for k in wkeys if licence[k][0] is not None]
        locs = []
        for k, pos in cites:
            if k in licensed_w:
                para = paras[bisect.bisect_right(para_starts, pos) - 1]
                items = citation_locator(masked, pos, entries[k], para)
                if items:
                    locs.append(([k], items))
        trail = trailing_locator(masked, c)
        if trail and licensed_w:
            locs.append((licensed_w, trail))
        # A bare 1500-2099 number is a page only when a text has that page.
        marker_pages = set()
        for k in licensed_w:
            pmap = page_maps[k]
            if pmap is not None:
                marker_pages.update(n for n in pmap.numbers if n is not None)
        for lkeys, items in locs:
            touched_all = [t for k in lkeys if k in ft_hits
                           for occ_spans in ft_hits[k][1]
                           for t in ft.span_pages(ft_hits[k][0], occ_spans)]
            desc = ", ".join(f"{kind} {n}" for kind, n in dict.fromkeys(touched_all)) or "none"
            nums = [n for kind, n in touched_all if kind == "page"]
            label = ", ".join(lkeys)
            for item in items:
                kind, raw = item[0], _ascii(item[-1])
                if kind == "year":
                    if item[1] not in marker_pages:
                        continue   # "(Smith 2020, 2021)": a second year
                    kind, item = "page", ("page", item[1], item[1], item[2])
                if kind == "page":
                    if any(item[1] <= n <= item[2] for n in nums):
                        continue
                    msg = f'drop or correct the locator "{raw}" (quote on: {desc})'
                elif kind == "roman":
                    msg = f'roman locator "{raw}" names no confirmed page: drop it'
                else:
                    msg = f'unrecognized locator "{raw}": drop or correct it (quote on: {desc})'
                lines.append(f'FIX page: {label}: {msg}: "{shown}" {where}')
                counts["fix_page"] += 1
        if ft_hits:
            n = _quote_words(span)
            if n > CAP_SPAN_WORDS:
                lines.append(f'WARN cap: {", ".join(sorted(ft_hits))}: {n} words in one '
                             f'quotation (cap {CAP_SPAN_WORDS}): "{shown}" {where}')
                counts["warn_cap"] += 1
            for g in {groups[k] for k in ft_hits}:
                group_words[g] = group_words.get(g, 0) + n

    for g, n in sorted(group_words.items()):
        if n > CAP_WORK_WORDS:
            members = ", ".join(sorted(k for k, gg in groups.items() if gg == g))
            lines.append(f"WARN cap: {members}: {n} words quoted from this work "
                         f"(cap {CAP_WORK_WORDS})")
            counts["warn_cap"] += 1
    counts["watched"] = len(watched)
    return lines, counts


def _load(args) -> tuple[str, str, dict, Path]:
    try:
        md = Path(args.review).read_text(encoding="utf-8")
        bib = Path(args.bib).read_text(encoding="utf-8")
        report = json.loads(Path(args.evidence_report).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise InputError(f"unreadable input: {e}")
    if not isinstance(report, dict) or not isinstance(report.get("attestations"), dict):
        raise InputError("evidence report has no attestations object")
    workdir = Path(args.workdir)
    if not workdir.is_dir():
        raise InputError(f"workdir is not a directory: {args.workdir}")
    return md, bib, report, workdir


def main(argv=None) -> int:
    usage = ("check_quotes.py <review.md> <merged.bib> --workdir <workdir> "
             "--evidence-report <report.json>")
    parser = argparse.ArgumentParser(prog="check_quotes.py", usage=usage)
    parser.add_argument("review")
    parser.add_argument("bib")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--evidence-report", required=True)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:
        if e.code == 0:  # --help
            raise
        return 2
    try:
        md, bib, report, workdir = _load(args)
        lines, counts = run(md, bib, report, workdir)
    except InputError as e:
        print(_ascii(f"check_quotes: {e}").replace("\n", " "), file=sys.stderr)
        return 2
    except Exception as e:  # crash: fail closed, one line
        print(_ascii(f"check_quotes: crashed: {type(e).__name__}: {e}").replace("\n", " "),
              file=sys.stderr)
        return 2
    for line in lines:
        print(_ascii(line))
    print("QUOTES-SUMMARY: " + json.dumps(counts))
    fails = sum(v for k, v in counts.items() if k.startswith("fail_"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
