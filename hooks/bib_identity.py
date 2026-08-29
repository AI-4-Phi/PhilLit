#!/usr/bin/env python3
"""The one owner of bibliography identity and value-comparison keys.

Before this module, six sites re-implemented "is this the same work / is this
value trustworthy" and disagreed: `dedupe_bib` applied no Unicode normalization
at all (so `Milliere`/`Milliere` pairs with differing diacritics survived dedup
in 5/32 delivered reviews), and `generate_bibliography` ASCII-folded non-Latin
surnames to '' and skipped those entries, deleting cited works from the
rendered References.

Seeded from the hardened `metadata_cleaner` versions. Every helper
here is pure: no I/O, no environment reads, no state.

SCOPE NOTE (deliberate): `title_key` does NOT decode
LaTeX escapes, so a title stored with an escaped accent keys differently
depending on whether the caller pre-decoded it (`generate_bibliography` does via
`clean_bibtex_str`; `dedupe_bib` does not). That divergence was measured
2026-08-20 over 8,517 titled entries in 313 local bibs: 149 divergent keys
(1.7%) and one duplicate-detection disagreement, in an old-architecture review.
Adding decoding here would change `metadata_cleaner`'s API-vs-bib title matching
- the surface that produced the year-corruption incident. Left as is
(owner decision, 2026-08-20).

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
# A standalone "&" (whitespace on both sides) is orthographic variance for the
# coordinator "and", not part of the venue's name: LaTeX source has "\&" (which
# normalize_journal already decodes to a literal "&" -- see its docstring),
# while an API record spells the same venue with "and" written out. An
# embedded ampersand ("AT&T") has no surrounding whitespace and does not match.
_STANDALONE_AMP = re.compile(r"\s&\s")


# ADMISSION RULE, read before adding anything: a series belongs here only if
# (a) its canonical name contains no `_CONF_WORD` match -- ICLR, ACL and NAACL
# all carry "Conference"/"Annual Meeting" in their full names and already fold
# without help, so adding them turns this into a grab-bag -- and (b) it is
# attested as a proceedings venue and NOT also as a journal name. Admitting a
# journal name here would make "Advances in <that name> 12" fold onto the bare
# name, which is exactly the false merge this list is shaped to avoid.
_KNOWN_SERIES = frozenset({
    # The rare series whose name carries no conference word at all, so nothing
    # in the string itself says "this is a proceedings volume". Without an entry
    # here, "Advances in Neural Information Processing Systems 30" cannot be
    # told apart from "Advances in Applied Energy 12" -- a journal name with a
    # volume glued on, which must NOT fold onto "Applied Energy".
    "neural information processing systems",
})


def venue_key(name: str) -> str:
    r"""Looser-than-identity key for verifying a venue name against API output.

    Folds the citation-form variance of conference proceedings onto the
    canonical series name, so a bibliography's expanded form verifies against
    the short form an API reports:

        "Proceedings of the 34th International Conference on Machine Learning
         (ICML 2017)"                    -> "international conference on machine learning"
        "Advances in Neural Information
         Processing Systems 30 (NeurIPS 2017)" -> "neural information processing systems"

    Also folds orthographic variance unrelated to series decoration: a
    standalone "&" (flanked by whitespace) is the coordinator "and" spelled
    differently ("Health Information \& Libraries Journal" verifies against
    "Health information and libraries journal"). An embedded ampersand
    ("AT&T") is part of a name, not a coordinator, and is left alone.

    THE GOVERNING RULE: **no token may be its own licence.** Every strip needs
    evidence independent of the text it removes. That is necessary but not
    sufficient -- independent evidence can still be wrong, because a conference
    word can be a component of a proper noun rather than the head of a series
    name ("Library of Congress"). See bound 4. A bare trailing number does not
    license removing itself, and does not license removing a prefix -- otherwise
    "Advances in Applied Energy 12" folds onto "Applied Energy" (two different
    Elsevier journals) and "Library of Congress Quarterly 7" folds onto its own
    unnumbered form. Both come from an earlier draft that gated the strips on
    the number's mere presence.

    Concretely:

    * "Proceedings of X" is decoration only when X is *itself* named as a
      series -- it carries a conference word, an instance marker, or is a
      known series. Otherwise the phrase belongs to the venue's own name
      ("Proceedings of the Aristotelian Society") or is a fabricated wrapper
      around a real journal ("Proceedings of the Journal of Philosophy"), and
      folding it would let that fabrication verify.
    * "Advances in X" likewise, and because such series often carry no
      conference word, this is where `_KNOWN_SERIES` earns its keep.
    * A trailing series number is removed only once some prefix or ordinal has
      already been removed, i.e. only once the string is known to be an
      instance of a series.

    Three bounds are deliberate, each chosen against losing the venue entirely:

    1. **The series is verified, the instance is not.** Ordinals, instance years
       and unlabelled part numbers are stripped, so a fabricated "41st ICML"
       verifies against a record that says ICML, and part 2 of a multi-part
       proceedings folds onto part 1. Deleting `booktitle` instead loses the
       venue from the reference, which is the worse error; the year field is
       separately verified and corrected.
    2. **A trailing parenthetical is a qualifier, not identity.** This folds
       "Criminology (Beverly Hills)" onto "Criminology" -- 100 such pairs in the
       corpus, all the same journal. It also folds distinctions someone might
       mean to keep ("Journal of X (Print)" vs "(Online)"), folds institutional
       repositories differing only in their parenthetical, and lets an invented
       parenthetical ("Journal of Philosophy (Special Issue on ...)") ride along
       on a verified journal name. Accepted: the direction is fewer deletions,
       and the qualifier text is never rewritten into the bibliography.
    3. **Instance numbers above 999 are not recognised** (`\d{1,3}`), so a
       four-digit series number survives where a three-digit one is stripped.
    4. **A "Proceedings of X" wrapper is accepted when X's own name contains a
       conference word.** So a fabricated "Proceedings of the Library of
       Congress Quarterly" verifies against the real journal, because "congress"
       reads as conference evidence. The obvious fix (requiring the conference
       word to head the phrase) was MEASURED against
       the corpus and rejected -- it strips 56 genuine conference series of their
       fold while actually protecting only 7 of the 9 conference-worded journals
       it targets, i.e. it causes about eight times more of the deletion this
       whole function exists to prevent. Re-measure that trade -- folds lost
       against journals protected, over the venue corpus -- before revisiting.
       Pinned by test, not left blind.
    5. **A series whose name carries no conference word does not fold** unless
       it is in `_KNOWN_SERIES`. "Proceedings of NAACL" (the short form) and
       similar therefore still lose `booktitle`. Accepted: admitting names
       loosely to this list reintroduces bound 4's failure in a worse form.

    Measured over the 46-corpus comparison surface (16,906 raw venue strings
    from bibliographies and API records, 15,644 distinct normalized forms):
    every multi-member fold group was inspected and none merges two different
    journals. That is a property of THIS corpus, not a proof about the function
    -- the bounds above are the parts known to be loose.
    """
    s = normalize_journal(name or "")
    if not s:
        return ""
    # Fold a standalone "&" onto "and" (see _STANDALONE_AMP above). Safe to do
    # unconditionally and first: it never introduces or removes any of the
    # words the decoration-stripping below keys on.
    s = _STANDALONE_AMP.sub(" and ", s)
    # Always safe, whatever the venue type: a trailing parenthetical is a
    # disambiguating qualifier and a leading 4-digit year is an edition marker.
    # (The loop matters: only the innermost trailing group matches at a time.)
    prev = None
    while prev != s:
        prev = s
        s = _TRAIL_PARENS.sub("", s).strip()
    s = _LEAD_YEAR.sub("", s).strip()

    def _series_like(rest: str) -> bool:
        """Does what follows a prefix name a series in its own right?

        A trailing instance number is ignored, and can be removed
        unconditionally here: `_TRAIL_NUM` requires whitespace or a comma before
        the digits, so dropping them can neither create nor destroy a word
        match, and the volume-vs-series distinction that matters elsewhere
        cannot change the answer.

        This is a gate on the WORDS present, not a reliable series detector: a
        conference word inside a proper noun passes it. See bound 4.
        """
        bare = _TRAIL_NUM.sub("", rest).strip()
        return bool(_CONF_WORD.search(bare)) or bare in _KNOWN_SERIES

    # `instance_evidence` records that this string has been shown to be one
    # instance of a series, which is what later licenses the trailing number.
    instance_evidence = False
    changed = True
    while changed:          # self-terminating: every branch shortens `s`
        changed = False
        m = _LEAD_PROC.match(s)
        if m:
            rest = s[m.end():].strip()
            if (_LEAD_ORD.match(rest) or _LEAD_YEAR.match(rest)
                    or _series_like(rest)):
                s, changed, instance_evidence = rest, True, True
                continue
        m = _LEAD_ADV.match(s)
        if m:
            rest = s[m.end():].strip()
            if _series_like(rest):
                s, changed, instance_evidence = rest, True, True
                continue
        if instance_evidence or _CONF_WORD.search(s) or _bare_series(s):
            for pattern in (_LEAD_ORD, _LEAD_YEAR):
                m = pattern.match(s)
                if m:
                    # Deliberately does NOT set instance_evidence. This branch
                    # can fire on a conference word appearing anywhere, and
                    # "congress" occurs inside institution names ("Library of
                    # Congress Quarterly"). Letting a leading ordinal license
                    # the trailing-number strip would reopen the volume-number
                    # merge through a second door; only a prefix strip, which
                    # names the series explicitly, is strong enough evidence.
                    s, changed = s[m.end():].strip(), True
                    break
            if changed:
                continue

    if instance_evidence and not _VOL_NUM.search(s):
        s = _TRAIL_NUM.sub("", s).strip()
    return " ".join(s.split())


def _bare_series(s: str) -> bool:
    """Is this a known series, with or without a trailing instance number?"""
    if s in _KNOWN_SERIES:
        return True
    return _TRAIL_NUM.sub("", s).strip() in _KNOWN_SERIES


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
    """Unicode-aware, punctuation/subtitle-insensitive title key.

    NFKD-normalize, drop combining marks (accent-insensitive so a bib title
    'Davidovic' matches an API 'Davidovic' spelled with a caron), keep every
    letter/digit including non-Latin (Greek, Cyrillic, Latin Extended-A stroke
    letters), casefold, and collapse punctuation/whitespace runs to single
    spaces. The old ASCII-only fold both erased non-Latin titles to '' (matching
    everything) and equated distinct stroke letters (D-bar and L-slash both
    dropped).

    Note that casefold EXPANDS some characters - eszett becomes 'ss' - which is
    a distinct fold axis from combining-mark stripping and is adopted
    deliberately.
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
# lint_md's citation check and generate_bibliography's matcher.
_TRANSLIT = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "å": "aa", "ø": "oe", "æ": "ae",
}


def translit_fold(s: str) -> str:
    """Lowercased ASCII fold of arbitrary text with German/Nordic
    transliteration applied BEFORE the NFKD strip (ä→ae, not ä→a). The
    second haystack for symmetric surname matching."""
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
    never title-deduped. Callers pass strings, not entries:
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
