#!/usr/bin/env python3
"""The one owner of bibliography identity and value-comparison keys.

ROADMAP item 4. Before this module, six sites re-implemented "is this the same
work / is this value trustworthy" and disagreed: `dedupe_bib` applied no Unicode
normalization at all (so `Milliere`/`Milliere` pairs with differing diacritics
survived dedup in 5/32 delivered reviews), and `generate_bibliography`
ASCII-folded non-Latin surnames to '' and skipped those entries, deleting cited
works from the rendered References.

Seeded from the hardened `metadata_cleaner` versions (item-13 B3). Every helper
here is pure: no I/O, no environment reads, no state.

SCOPE NOTE (deliberate, ROADMAP item 4 Decision 4): `title_key` does NOT decode
LaTeX escapes, so a title stored with an escaped accent keys differently
depending on whether the caller pre-decoded it (`generate_bibliography` does via
`clean_bibtex_str`; `dedupe_bib` does not). That divergence is unmeasured, and
adding decoding here would change `metadata_cleaner`'s API-vs-bib title matching
- the surface that produced the year-corruption incident. Left as is.

NOT owned here: `generate_bibliography._normalize_for_matching`, the fold applied
to author-written review prose. It keeps punctuation, and the citation matcher's
60-character proximity window is measured over its output.
"""

import html
import re
import unicodedata

from bib_validator import LATEX_ESCAPES


def normalize_pages(pages: str) -> str:
    """Normalize page ranges for comparison."""
    if not pages:
        return ""
    normalized = re.sub(r'\s*[-–—]+\s*', '-', str(pages))
    return normalized.strip()


# \^{u} -> \^u so the no-brace LATEX_ESCAPES keys (and the accent safety net
# below) can match the braced accent form real bibs actually use (No\^{u}s).
_INNER_BRACE_ACCENT = re.compile(r'(\\["\'`^~])\{([A-Za-z])\}')


def normalize_journal(name: str) -> str:
    """Normalize journal name for comparison. Decodes HTML entities and LaTeX
    escapes so LaTeX-encoded bib values (e.g. 'Philosophy \\& Technology',
    'No\\^{u}s') compare equal to CrossRef's precomposed/entity forms
    ('Philosophy &amp; Technology', 'Noûs')."""
    if not name:
        return ""
    s = html.unescape(name)                       # &amp;->&, &#251;->û
    s = _INNER_BRACE_ACCENT.sub(r'\1\2', s)        # \^{u} -> \^u so dict keys match
    for latex, uni in LATEX_ESCAPES.items():       # \^u -> û, \c{c} -> ç, {\ss} -> ß
        s = s.replace(latex, uni)
    s = re.sub(r'\\["\'`^~=.]\{?([A-Za-z])\}?', r'\1', s)  # safety net: unknown accent -> base letter
    s = re.sub(r'\\+&', '&', s)                    # \& and \\& -> &
    s = s.replace('{', '').replace('}', '')        # residual braces
    # NFKD-fold so decoded-Unicode and CrossRef-precomposed reduce to base letters
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    normalized = s.lower().strip()
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return " ".join(normalized.split())


def normalize_doi(doi: str) -> str:
    """Normalize DOI for comparison."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    # dx.doi.org forms first so the bare-form check below can't shadow them
    # (longest-prefix-wins).
    prefixes = [
        "https://dx.doi.org/", "http://dx.doi.org/",
        "https://doi.org/", "http://doi.org/", "doi:", "doi.org/",
    ]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


# Integral-year grammar for year_key: optional sign, ASCII digits, and an
# optional fractional part of one-or-more zeros. `[0-9]` not `\d` (which also
# matches non-ASCII decimal digits that lstrip("0") would not normalize), and
# `0+` not `0*` so a bare trailing dot ("2007.") is NOT treated as integral.
_INTEGRAL_YEAR_RE = re.compile(r"^([+-]?)([0-9]+)(?:\.0+)?$")


def year_key(value) -> str:
    """Canonical form of a year, for comparing values from different producers.

    Pooled JSON is external data: the same real year can arrive as an int
    (2007) or a float (2007.0) depending on how a producer parsed it. Compare
    those equal instead of registering a phantom disagreement.

    Canonicalizes WITHOUT a binary-float round-trip, so a string or an
    arbitrary-precision int is never rewritten into a different number:
    str(int(float("9007199254740993"))) is ...992, and float() collapses
    "2007.0000000000001" to "2007". Note the limit of that guarantee - if the
    JSON loader already parsed the value INTO a float, the precision is gone
    before this function sees it; only `parse_float=Decimal` would preserve
    it. Exactness here means "adds no new rounding", not "recovers what json
    already discarded".

    The grammar composes with repr(float), so the effective boundary is where
    str() switches to exponent form: str(1e15) is "1000000000000000.0" and
    canonicalizes, str(1e16) is "1e+16" and does not. Unreachable for real
    years; noted so the contract is not mistaken for a pure-grammar one. Match sign + digits +
    an optional all-zero fractional part; return the digits with sign and
    leading zeros normalized. Everything else - "2007.5", "n.d.", "MMVII",
    "2,007" - round-trips verbatim. Exponent notation ("2.007e3", "1e999") is
    out of scope by design, so the contract comes from this grammar rather
    than from binary-float range.

    KNOWN LIMITATION (predates this helper, now routed through it): a
    disambiguating BibTeX year like "2007a" canonicalizes verbatim and so
    compares unequal to "2007". A scoped record would "correct" it to "2007"
    and destroy the suffix. There is no plausibility gate on the correction
    path beyond "must be an integral canonical year".

    NOTE: no PhilLit producer is currently known to emit a float year. This
    is boundary hardening for external JSON, not a fix for an observed
    failure.
    """
    text = str(value).strip()
    match = _INTEGRAL_YEAR_RE.match(text)
    if not match:
        return text
    # A leading "+" is dropped; a negative sign is retained (except on zero).
    sign, digits = match.group(1), match.group(2)
    digits = digits.lstrip("0") or "0"
    # -0 and 0 are the same year; do not let a sign survive on zero.
    return ("-" if sign == "-" and digits != "0" else "") + digits


def title_key(title: str) -> str:
    """Unicode-aware, punctuation/subtitle-insensitive title key (item-13 B3).

    NFKD-normalize, drop combining marks (accent-insensitive so a bib title
    'Davidovic' matches an API 'Davidovic' spelled with a caron), keep every
    letter/digit including non-Latin (Greek, Cyrillic, Latin Extended-A stroke
    letters), casefold, and collapse punctuation/whitespace runs to single
    spaces. The old ASCII-only fold both erased non-Latin titles to '' (matching
    everything) and equated distinct stroke letters (D-bar and L-slash both
    dropped).

    Note that casefold EXPANDS some characters - eszett becomes 'ss' - which is
    a distinct fold axis from combining-mark stripping and is adopted
    deliberately (ROADMAP item 4 Decision 7).
    """
    if not title:
        return ""
    out = []
    for ch in unicodedata.normalize('NFKD', title):
        if unicodedata.combining(ch):
            continue
        out.append(ch if ch.isalnum() else ' ')
    return ' '.join(''.join(out).casefold().split())


# German/Nordic transliteration for the alternate name fold. Shared by
# lint_md's citation check and generate_bibliography's matcher (item 3 B/E).
_TRANSLIT = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "å": "aa", "ø": "oe", "æ": "ae",
}


def ascii_variants(s: str) -> frozenset[str]:
    """Lowercased ASCII variants of a name: the NFKD-stripped fold and the
    transliterated fold, so body "Fraenken" meets bib "Fränken" (ä -> a AND
    ä -> ae). Curly apostrophes unify with straight ones; empty variants are
    dropped (an empty needle would match everything)."""
    low = s.lower().replace("’", "'")
    nfkd = unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode()
    translit = low
    for ch, rep in _TRANSLIT.items():
        translit = translit.replace(ch, rep)
    translit = unicodedata.normalize("NFKD", translit).encode(
        "ascii", "ignore").decode()
    return frozenset(v for v in (nfkd, translit) if v)


def fallback_key(title: str, year: str, surname: str) -> tuple[str, str, str] | None:
    """Title-axis identity key: (title_key, year, title_key(surname)).

    Returns None if any component is empty - an entry with no fallback key is
    never title-deduped (item-13 GPT S4). Callers pass strings, not entries:
    `dedupe_bib` reads pybtex fields raw while `generate_bibliography` decodes
    LaTeX first (see the module docstring's SCOPE NOTE).

    The year is compared VERBATIM after stripping, not through `year_key` - both
    call sites read a BibTeX year, which is already a string, and canonicalizing
    here would silently merge "2007" with a float-ish "2007.0" that no bib
    actually contains. Use `year_key` upstream if a producer's int/float/str
    encoding needs erasing first.
    """
    norm_title = title_key(title or "")
    norm_year = (year or "").strip()
    norm_surname = title_key(surname or "")
    if not norm_title or not norm_year or not norm_surname:
        return None
    return (norm_title, norm_year, norm_surname)
