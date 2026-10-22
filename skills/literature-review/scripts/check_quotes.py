"""Phase 6 quotation gate for EVIDENCE-FULLTEXT works (PL-19, spec section 9).

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
- `WARN uncited`: a quoted span of 4 words or more with no citation in its
  sentence or the next.

Then one `QUOTES-SUMMARY: {json}` line. Exit 1 when any FAIL, 0 otherwise, 2
on a crash or unreadable input (one line on stderr).

WHY SEPARATE FROM check_evidence.py: that script is telemetry with a fixed
contract (always exit 0, `CHECK` lines, a human adjudicates every hit). This
one is an accuracy gate: verbatim accuracy fails closed (a misquotation is a
fabrication), pages and caps are pragmatic (ruling in
`docs/ideas/fulltext-evidence-tier.md`). Mixing the two would change what the
telemetry's exit code means.

COMPLETION RULE (SKILL.md Phase 6): rerun until there is no FAIL, no FIX and
no `WARN uncited` line. `WARN cap` is advisory: shorten where possible.

OWNERS USED, never re-implemented: quote matching, page maps, text reading
and hashing, identity comparison (`fulltext.py`); citation resolution
(`check_evidence.find_cites` and its surname rule); the References boundary
(`lint_md.find_refs_heading`); BibTeX decoding of abstracts and titles
(`generate_bibliography.clean_bibtex_str`). The merged-bib entry table
(surname, year, Chicago letter, last EVIDENCE token) MIRRORS the loop inline
in `check_evidence.main()`, which cannot be imported.

RESIDUALS (accepted, visible; spec section 12 lists the design-level ones):
- A quote in a sentence citing two works passes when it is in either text.
- Uncited spans of 2 or 3 words are not reported (scare quotes).
- A block quotation (`> ...`) without quotation marks is not checked.
- "Next sentence" attribution stays inside the paragraph.
- Only numeric (and roman) page locators are checked: `ch. 3`, `sec. 2`,
  `45 n. 3`, `45ff.` are not page locators here and pass unchecked.
- A locator in a parenthesis right after the quote (`"..." (45)`) is checked
  against every watched work of the attribution; it passes when any of them
  has the quote on that page.
- A 4-digit locator from 1500 to 2099 without `p.`/`pp.` reads as a second
  year (`(Smith 2020, 2021)`) and is not checked; in `, 45, 47` only the
  first locator is checked.
- Editor-only entries have no surname for `find_cites` and are never
  attributed (check_evidence's residual).
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
from bib_identity import title_key  # noqa: E402

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
_ROMAN = r"[ivxlcdm]+"
_NUM = r"(?:\d+|" + _ROMAN + r")"
# A page locator after a citation's year: `, 45`, `, 45-46`, `, p. 45`,
# `, pp. 145-46`. It must end the citation (`)`, `;`, `]` or `,`).
_LOC_RE = re.compile(
    r"\s*,\s*(?:pp?\.\s*)?(?P<a>" + _NUM + r")\b(?:\s*[" + _DASHES + r"]+\s*(?P<b>"
    + _NUM + r")\b)?(?=\s*[;)\],])", re.I)
# A bare page parenthesis right after the closing quotation mark.
_TRAIL_LOC_RE = re.compile(
    r"\s*\(\s*(?:pp?\.\s*)?(?P<a>" + _NUM + r")\b(?:\s*[" + _DASHES + r"]+\s*(?P<b>"
    + _NUM + r")\b)?\s*\)", re.I)


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
    table (surname via its search rule, 4-digit year, one-letter suffix, last
    EVIDENCE token) and keeps the raw fields."""
    entries = {}
    for chunk in se.split_entries(bib_text):
        header = se.entry_header(chunk)
        if not header:
            continue
        _etype, key = header
        fields = se.parse_entry_fields(chunk)
        surname = ce.rc_surname({"fields": fields})
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
    """The body (before `## References`) with fenced code, heading lines and
    inline code blanked (offsets kept), and the offsets of heading lines."""
    refs = find_refs_heading(md)
    body = md[:refs[0]] if refs else md
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


def find_spans(masked: str, paras) -> list[tuple[int, int, int]]:
    """(open, close, paragraph index): offsets of the opening and closing
    quotation marks of every double-quoted span, paired within a paragraph."""
    spans = []
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
            i += 1
    return spans


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

def _page_value(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else None


def parse_locator(m: re.Match):
    """(lo, hi, text) of a page locator match; lo/hi None for a roman
    numeral (never confirmable: markers carry arabic numbers)."""
    a, b = m.group("a"), m.group("b")
    text = m.group(0).strip(" ,()")
    lo = _page_value(a)
    if b is None:
        return lo, lo, text
    hi = _page_value(b)
    if lo is not None and hi is not None and hi < lo and len(b) < len(a):
        hi = int(a[:len(a) - len(b)] + b)   # Chicago 145-46
    if lo is None or hi is None:
        return None, None, text
    return lo, hi, text


def citation_locator(masked: str, pos: int, info: dict):
    """The page locator written with the citation whose surname is at pos,
    or None."""
    year_re = re.compile(r"(?<!\d)" + re.escape(info["year"]) + r"[a-z]?(?!\d)", re.I)
    ym = year_re.search(masked, pos, min(len(masked), pos + len(info["surname"]) + ce._MATCH_WINDOW))
    if not ym:
        return None
    lm = _LOC_RE.match(masked, ym.end())
    if not lm:
        return None
    # "(Smith 2020, 2021)" cites two years, not page 2021.
    if _YEARLIKE_RE.match(lm.group("a")) and not re.match(r"\s*,\s*pp?\.", lm.group(0), re.I):
        return None
    return parse_locator(lm)


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def _match_quote(quote: str, sources):
    """Try every source; (hits, form_error). hits: [(key, kind, text,
    occurrences)] for each source holding the quote."""
    hits, form_error = [], None
    for key, kind, text in sources:
        pm = ft.page_map_from_text(text) if kind == "fulltext" else None
        try:
            occ = ft.locate_quote_all(quote, text, pm)
        except ft.QuoteFormError as e:
            form_error = form_error or e
            continue
        if occ:
            hits.append((key, kind, text, occ))
    return hits, form_error


def _clean_span(span: str) -> str:
    """Markdown emphasis is markup, not quoted text."""
    s = re.sub(r"\*+", "", span)
    return re.sub(r"(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])", "", s)


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
    spans = find_spans(masked, paras)
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
    groups = _union_groups(sorted(watched), entries)
    group_words: dict[str, int] = {}

    lines: list[str] = []
    counts = {"spans": 0, "titles_skipped": 0, "fulltext_attributed": 0,
              "fail_licence_lost": 0, "fail_verbatim": 0, "fail_bracket": 0,
              "fail_ellipsis": 0, "fix_page": 0, "warn_cap": 0, "warn_uncited": 0}

    def line_no(pos: int) -> int:
        return md.count("\n", 0, pos) + 1

    for o, c, _pi in spans:
        span = md[o + 1:c]
        if _words(span) < MIN_SPAN_WORDS:
            continue
        si = sentence_of(o)
        own = cites_by_sentence.get(si, []) if si is not None else []
        # A quoted title of a work cited in the same sentence is not a quotation.
        sk = title_key(_decoded(span))
        if sk and any((tk == sk or tk.startswith(sk + " "))
                      for tk in (title_key(_decoded(entries[k]["fields"].get("title", "")))
                                 for k, _ in own)):
            counts["titles_skipped"] += 1
            continue
        counts["spans"] += 1
        cites = own
        if not cites and si is not None and si + 1 < len(sents):
            nxt = sents[si + 1]
            same_para = nxt[2] == sents[si][2]
            if same_para and not any(sents[si][1] <= h < nxt[0] for h in headings):
                cites = cites_by_sentence.get(si + 1, [])
        where = f"[line {line_no(o)}]"
        shown = _show(span)
        if not cites:
            if _words(span) >= MIN_UNCITED_WORDS:
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

        sources = [(k, "fulltext", licence[k][0]) for k in wkeys if licence[k][0] is not None]
        for k in keys:
            info = entries[k]
            if info["tier"] == TIER_ABSTRACT and info["fields"].get("abstract"):
                sources.append((k, "abstract", _decoded(info["fields"]["abstract"])))
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
        locs = []
        for k, pos in cites:
            if k in ft_hits or (k in wkeys and licence[k][0] is not None):
                loc = citation_locator(masked, pos, entries[k])
                if loc:
                    locs.append(([k], loc))
        tm = _TRAIL_LOC_RE.match(masked, c + 1)
        if tm and _YEARLIKE_RE.match(tm.group("a")) and not re.match(r"\s*\(\s*pp?\.", tm.group(0), re.I):
            tm = None   # "(2020)": a year, not a page
        if tm:
            licensed_w = [k for k in wkeys if licence[k][0] is not None]
            if licensed_w:
                locs.append((licensed_w, parse_locator(tm)))
        for lkeys, (lo, hi, ltext) in locs:
            ok = False
            touched_all = []
            for k in lkeys:
                if k not in ft_hits:
                    continue
                text, occ = ft_hits[k]
                for spans_ in occ:
                    touched = ft.span_pages(text, spans_)
                    touched_all.extend(touched)
                    nums = [n for kind, n in touched if kind == "page"]
                    if lo is not None and any(lo <= n <= hi for n in nums):
                        ok = True
            if not ok:
                desc = ", ".join(f"{kind} {n}" for kind, n in dict.fromkeys(touched_all)) or "none"
                lines.append(f'FIX page: {", ".join(lkeys)}: drop or correct the locator '
                             f'"{_ascii(ltext)}" (quote on: {desc}): "{shown}" {where}')
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
