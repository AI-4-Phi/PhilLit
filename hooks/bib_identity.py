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


# --- Venue comparison key -----------------------------------------------------
# A conference is named one way by the APIs ("International Conference on Machine
# Learning") and another way in a bibliography ("Proceedings of the 34th
# International Conference on Machine Learning (ICML 2017)"). Both are correct.
# Comparing the two with normalize_journal alone reports a mismatch, and the
# metadata cleaner then deletes `booktitle` - which is @inproceedings' required
# field, so the entry is demoted to @misc and the reference loses its venue.
# Measured over the delivered corpus: 30 of 43 demotions were @inproceedings,
# and `booktitle` was the most-removed field.
#
# venue_key strips the decoration that distinguishes those two forms. It is a
# VERIFICATION key, deliberately looser than normalize_journal, and is never
# used for dedup identity.

_ORD_WORD = (r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
             r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|"
             r"seventeenth|eighteenth|nineteenth|twentieth|thirtieth|fortieth|"
             r"fiftieth|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety")
_TRAIL_PARENS = re.compile(r"\s*\([^()]*\)\s*$")
_LEAD_YEAR = re.compile(r"^(19|20)\d{2}\s+")
_TRAIL_NUM = re.compile(r"[\s,]+\d{1,3}$")
_LEAD_PROC = re.compile(r"^(proceedings|proc\.?)\s+of\s+(the\s+)?")
_LEAD_ADV = re.compile(r"^advances\s+in\s+")
# An ordinal only counts as decoration when it is a WHOLE token. Hyphen-joined it
# is part of the name: "Eighteenth-Century Life" is a journal, and stripping its
# ordinal yields the nonsense key "-century life" (observed while measuring).
_LEAD_ORD = re.compile(
    r"^(\d+(st|nd|rd|th)|(" + _ORD_WORD + r")(-(" + _ORD_WORD + r"))?)\s+")
_CONF_WORD = re.compile(r"\b(conference|proceedings|symposium|workshop|congress|"
                        r"annual meeting|colloquium)\b")
# A trailing number introduced by a volume word IDENTIFIES the book rather than
# decorating a series: "Oxford Studies in Political Philosophy Volume 5" and
# "... Volume 8" are different books, both present in the corpus.
_VOL_NUM = re.compile(r"\b(vol\.?|volume|part|pt\.?|no\.?|issue|number)[\s,]+\d{1,3}$")


def venue_key(name: str) -> str:
    """Looser-than-identity key for verifying a venue name against API output.

    Folds the citation-form variance of conference proceedings onto the
    canonical series name, so a bibliography's expanded form verifies against
    the short form an API reports:

        "Proceedings of the 34th International Conference on Machine Learning
         (ICML 2017)"                    -> "international conference on machine learning"
        "Advances in Neural Information
         Processing Systems 30 (NeurIPS 2017)" -> "neural information processing systems"

    Two bounds are deliberate, both chosen against losing the venue entirely:

    * **The series is verified, the instance is not.** Ordinals and instance
      years are stripped, so a fabricated "41st ICML" verifies against a record
      that says ICML. The alternative - deleting `booktitle` - loses the venue
      from the reference altogether, which is the worse error. The year field is
      separately verified and corrected.
    * **A trailing parenthetical is treated as a qualifier, not identity.** This
      is what folds "Criminology (Beverly Hills)" onto "Criminology". It also
      folds distinct institutional repositories that differ only in their
      parenthetical ("Scholar Commons (Santa Clara University)" vs "(University
      of South Carolina)"). Repository names are not citable venues and the
      direction is fewer deletions, so this is accepted.

    Measured over the 46-corpus comparison surface (16,906 raw venue strings
    from bibliographies and API records): 15,644 distinct normalized forms fold
    to 15,078 keys across 365 groups, and no group merges two genuinely
    different journals.
    """
    s = normalize_journal(name or "")
    if not s:
        return ""
    # Always safe, whatever the venue type: a trailing parenthetical is a
    # disambiguating qualifier (acronym, city, "print"), and a leading 4-digit
    # year is an edition marker. No journal's identity rests on either.
    prev = None
    while prev != s:
        prev = s
        s = _TRAIL_PARENS.sub("", s).strip()
    s = _LEAD_YEAR.sub("", s).strip()

    # The aggressive strips fire only on proceedings evidence. Ungated, "Advances
    # in Applied Energy" folds onto "Applied Energy" - two different Elsevier
    # journals, both observed in the corpus.
    series_num = bool(_TRAIL_NUM.search(s)) and not _VOL_NUM.search(s)
    if _LEAD_PROC.match(s) or _CONF_WORD.search(s) or series_num:
        for _ in range(3):
            before = s
            s = _LEAD_PROC.sub("", s).strip()
            s = _LEAD_ADV.sub("", s).strip()
            s = _LEAD_ORD.sub("", s).strip()
            s = _LEAD_YEAR.sub("", s).strip()
            if s == before:
                break
        if not _VOL_NUM.search(s):
            s = _TRAIL_NUM.sub("", s).strip()
    return " ".join(s.split())


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


def translit_fold(s: str) -> str:
    """Lowercased ASCII fold of arbitrary text with German/Nordic
    transliteration applied BEFORE the NFKD strip (ä→ae, not ä→a). The
    second haystack for symmetric surname matching (item 3 B)."""
    low = unicodedata.normalize("NFC", s.lower().replace("’", "'"))
    for ch, rep in _TRANSLIT.items():
        low = low.replace(ch, rep)
    return unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode()


def ascii_variants(s: str) -> frozenset[str]:
    """Lowercased ASCII variants of a name: the NFKD-stripped fold and the
    transliterated fold, so body "Fraenken" meets bib "Fränken" (ä -> a AND
    ä -> ae). Curly apostrophes unify with straight ones; a decomposed input
    (combining diaeresis rather than a precomposed character) is NFC-recomposed
    first so the transliteration table (keyed on precomposed characters) still
    matches it. Empty variants are dropped (an empty needle would match
    everything)."""
    low = unicodedata.normalize("NFC", s.lower().replace("’", "'"))
    nfkd = unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode()
    return frozenset(v for v in (nfkd, translit_fold(s)) if v)


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
