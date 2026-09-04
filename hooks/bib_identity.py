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

from pybtex.bibtex.utils import split_name_list
from pybtex.database import Person

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


def _contract_ascii(s: str) -> str:
    """The digraph contractions ae->a, oe->o, ue->u, in that order, on text
    that is already lowercase ASCII. Single left-to-right str.replace passes,
    NOT a fixed point: "aee" becomes "ae", not "a" -- fine for the
    one-digraph-per-umlaut transliteration model this serves."""
    for pair, single in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        s = s.replace(pair, single)
    return s


def contract_fold(s: str) -> str:
    """The third axis of symmetric surname matching: bridges two
    independently ASCII-fied spellings of the same umlaut/Nordic name that
    carry NO diacritic on either side ("Fraenken"/"Franken",
    "Soegaard"/"Sogaard" -- the NFKD fold and the transliterated fold agree
    with each other in that case, so neither of ascii_variants' first two
    axes bridges it).

    `translit_fold(s)` (ä->ae, ö->oe, ü->ue, å->aa, æ->ae, ø->oe, NFKD-fold,
    then ASCII-encode), then `_contract_ascii`.

    Via translit_fold the contraction also reaches ø->oe->o and æ->ae->a, so
    Scandinavian names are in scope: that is where the live regression came
    from (Sogaard/Søgaard -- ø does not NFKD-decompose, so the plain fold is
    "sgaard", not "sogaard")."""
    return _contract_ascii(translit_fold(s))


def ascii_variants(s: str, contract: bool = True) -> frozenset[str]:
    """Lowercased ASCII variants of a name: the NFKD-stripped fold, the
    transliterated fold, and the contracted fold of each, so body "Fraenken"
    meets bib "Fränken" (ä -> a AND ä -> ae) AND body "Fraenken" meets bib
    "Franken" (neither side carries a diacritic, so the first two axes agree
    with each other and need the contraction to bridge them). Curly
    apostrophes unify with straight ones; a decomposed input (combining
    diaeresis rather than a precomposed character) is NFC-recomposed first so
    the transliteration table (keyed on precomposed characters) still matches
    it. Empty variants are dropped (an empty needle would match everything).

    `contract=False` returns only the NFKD + translit axes -- lint's
    contraction-only WARN compares the two sets.

    The returned set is unchanged for a name with no "ae"/"oe"/"ue" substring
    in any GENERATED variant, and for a name whose variant set is already
    closed under contraction ({"franken", "fraenken"} from "Fränken":
    contracting either yields "franken", already present). A diacritic name
    whose transliteration opens a digraph is NOT unaffected -- that is the
    point: "Søgaard" ({"sgaard", "soegaard"}) gains "sogaard".

    A contracted variant is kept only when it is at least 4 characters long.
    Measured (2026-08-29, 2,430 corpus surnames): every sub-4 contraction
    found was {Noe->"no", Coe->"co", Shue->"shu", OECD->"ocd"} -- a
    match-flood needle (word-bounded "no" hits essentially every sentence
    near a year) and never a genuine bridge, since a diacritic-stripped
    prose spelling is already covered by the plain NFKD variant. The sole
    >=4-character dictionary-word contraction in the corpus was
    Mueller->"muller", this fix's own target class. NOTE the guard is
    per-ARGUMENT: it protects surname-shaped inputs (matcher needles, lint
    citation tokens). Consumers that fold WHOLE STRINGS through this function
    or contract_fold -- generate_bibliography's contract_text haystack,
    lint_md's reference-line variants -- contract every digraph in the string
    with no token-local guard; residual (b) below is that class.

    ACCEPTED RESIDUALS (stated, not silently absorbed):
    (a) true homograph pairs (Michael/Michal-shape) fold together --
    extended-set census found ONE newly-bridged pair corpus-wide
    (Schaeffer/Schaffer), sharing no year. A same-year pair would form a
    collision group in generate_bibliography._resolve_collisions, whose
    failure direction is keep-all and whose [COLLISION] stderr diagnostics
    make the group visible; the length guard does NOT cover this class.
    (b) whole-string contraction can fold a prose or reference-line digraph
    word onto a short plain needle (prose "Guest" -> "gust" meeting a bib
    surname "Gust" in the matcher; a References line's "Guest" resolving a
    body "Gust (2020)" citation in lint) -- needs the same year alongside,
    and no case was reported by the censuses behind this note. Read that
    NARROWLY: those censuses enumerate bib surnames and lint citation
    tokens -- the NEEDLE side -- not arbitrary words on the line side, where
    (b) lives. They therefore do not establish that (b) is absent from the
    corpus, and nothing here bounds future input; that is why (b) is
    accepted rather than retired.
    Since v0.5.7 lint surfaces a contraction-only resolution as a WARN
    (check_citations; measured 2026-09-01: 1 firing per 34 reviews, 0
    regressions), so a (b) fold no longer resolves silently there -- but only
    when the contraction is the citation's ONLY resolution path. A
    multi-token citation resolving cleanly via a sibling token still masks a
    contraction-only bridge on another token ("(Smith and Mueller 2018)"
    against bib "Smith, Ann, and Hans Muller. 2018." resolves via Smith, no
    WARN for the Muller/Muller bridge), and a References section holding a
    sibling entry that resolves the citation without contraction still masks
    a genuinely ambiguous contraction-only entry (bib "Mueller, Hans. 2018."
    and "Muller, Eva. 2018." both present: body "Muller (2018)" resolves via
    the Muller line, no WARN despite the two-person ambiguity). The matcher
    path's side of (b) is unchanged.
    NARROW THE CLOSURE CLAIM: it holds cleanly only for NFKD-DECOMPOSABLE
    diacritics (ä/ö/ü/å - the Müller/Muller class), where the plain NFKD
    fold already resolves a legitimate same-person citation, so the WARN
    there fires only on a genuine homograph-shaped bridge. For ø and æ
    (non-decomposable - see contract_fold above), the clean ASCII spelling
    exists ONLY through the contraction axis, so bib "Møller" cited as
    "Moller" (or "Søgaard" as "Sogaard") DOES fire the WARN for a legitimate
    same-person pair, not a masked collision. This is an accepted firing
    class, already inside the measured 1-per-34-reviews rate; the remedy is
    the same one-line verification the WARN already asks for.
    Pinned in test_lint_md.py::TestCitationCheck by
    test_guest_gust_false_resolve_now_warns and
    test_michael_michal_residual_reaches_lint_too (residual (a) reaches lint
    too) -- both pins now assert the WARN fires rather than that the
    resolution stays silent. Each pin fails if its own example stops
    resolving, or stops warning; neither detects a widening of the fold.
    Pointer: docs/known-issues/surname-contraction-measurement-2026-08-29/.
    """
    low = unicodedata.normalize("NFC", s.lower().replace("’", "'"))
    nfkd = unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode()
    variants = frozenset(v for v in (nfkd, translit_fold(s)) if v)
    if not contract:
        return variants
    # Base variants are already ASCII, so contracting them directly equals
    # contract_fold minus the redundant re-transliteration.
    contracted = frozenset(
        c for c in map(_contract_ascii, variants) if len(c) >= 4)
    return variants | contracted


# Whole-field year grammar for same_work_year. Anchored at both ends on
# purpose: a year field is the whole value or it is not a year at all.
# `[0-9]` not `\d`, the same convention _INTEGRAL_YEAR_RE states above: `\d`
# also matches non-ASCII decimal digits, which would key a year against a
# string no other producer in the pipeline can spell.
_SAME_WORK_YEAR_RE = re.compile(
    r"^\s*([0-9]{4})[a-z]?(?:\s*(?:--?|/)\s*[0-9]{4}[a-z]?)?\s*$")


def same_work_key(title: str, surname: str) -> tuple[str, str] | None:
    """Year-less advisory grouping key for the reprint class: entries
    sharing (title_key, first-author-surname fold) across DIFFERENT years
    are usually one work reprinted. None when either component is empty -
    such an entry never groups. The surname goes through title_key
    deliberately: that is fallback_key's established surname axis (see
    fallback_key below), and title_key is a generic fold - NFKD, strip
    combining marks, casefold, collapse - with no title-specific logic.
    This is NOT dedup identity: year stays part of fallback_key, and this
    key exists precisely because a coherent reprint year defeats that key
    by design. Census (2026-09-01, 45 delivered reviews): 23 groups, ~20
    warranting writer attention; auto-merge measured against and rejected
    (dedup runs after synthesis, and the DOI-guard-refused set holds the
    genuinely distinct works).

    FEED IT RAW FIELD VALUES. The module SCOPE NOTE above applies here in
    full: `title_key` does not decode LaTeX escapes, so a title keys
    differently depending on whether the caller pre-decoded it (measured
    2026-08-20: 149 of 8,517 titled entries diverge). Both declared consumers
    -- the evidence barrier's annotation and `generate_bibliography`'s Phase 6
    [SAME-WORK] advisory -- must pass the values as they stand in the .bib,
    NOT through `clean_bibtex_str`, which `generate_bibliography` applies
    elsewhere. One owner for the rule buys nothing if the two sides normalize
    their inputs differently before calling in: that defeats the guarantee
    through the front door, and it is the exact drift this shared placement
    exists to prevent."""
    nt = title_key(title or "")
    ns = title_key(surname or "")
    if not nt or not ns:
        return None
    return (nt, ns)


def same_work_year(year) -> str:
    """The comparison year for same-work grouping: WHOLE-FIELD grammar, so
    "1984", "1984a" and the range/reprint forms "1984--1985" / "1984/2017"
    all compare as "1984" (year_key deliberately keeps a "1984a" verbatim -
    wrong axis here, where a suffix or range must not fake a second
    publication year). "" for anything else - a malformed year field
    ("10.1234/2017.42", an ISBN, prose) must never mint a phantom year and
    group a valid entry against garbage; an entry with no comparison year
    never groups, the fail-safe direction for an advisory."""
    m = _SAME_WORK_YEAR_RE.match(str(year or ""))
    return m.group(1) if m else ""


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


def split_author_list(field: str | None) -> list[str]:
    """Split a BibTeX author/editor field into its names, brace-aware.

    The one owner of this split, with no literal-`" and "` fallback: pybtex's
    `split_name_list` treats a braced group as opaque, so
    `{Smith and Jones Institute} and Doe, Jane` is two names, not three,
    where a literal split gave `{Smith` and keyed the corporate author
    differently from `generate_bibliography`, which reads pybtex's persons.
    pybtex never raises here: unbalanced input comes back whole.
    """
    text = (field or "").strip()
    if not text:
        return []
    return [n.strip() for n in split_name_list(text) if n.strip()]


def first_author_name(author: str | None, editor: str | None = "") -> str:
    """First name string of the author list; editors are the fallback for
    edited volumes, matching generate_bibliography's rule."""
    field = (author or "").strip() or (editor or "").strip()
    names = split_author_list(field)
    return names[0] if names else ""


def _fallback_surname(first: str) -> str:
    """Comma/whitespace split used when pybtex cannot give a surname."""
    if "," in first:
        return first.split(",")[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


def first_author_surname(author: str | None, editor: str | None = "") -> str:
    """The first author's FULL surname (pybtex prelast + last), RAW.

    Undecoded and braces kept, so it agrees with `generate_bibliography`'s
    `_raw_surname` and, through `year_suffix._first_surname_raw`, feeds
    `fallback_key` and `same_work_key` the same text the Phase 6 advisory
    does. The comma/whitespace fallback runs when pybtex's `Person` raises
    or yields no surname; callers pass RAW field values (undecoded), as
    `same_work_key` requires.
    """
    try:
        first = first_author_name(author, editor)
    except Exception:  # pybtex split failure on one malformed field: no name, no key
        return ""
    if not first:
        return ""
    try:
        person = Person(first)
    except Exception:
        # Identity heuristic, not a validator: any Person failure (InvalidNameString on
        # too many commas, pybtex's own UnboundLocalError on tie-only names) degrades to
        # the comma/whitespace split rather than crashing the barrier.
        return _fallback_surname(first)
    surname = " ".join(person.prelast_names + person.last_names).strip()
    return surname or _fallback_surname(first)


def first_author_prose_surname(author: str | None) -> str:
    """The first author's surname as RUNNING TEXT names it: the part before
    the first comma of the first name, brace-aware on the list split.

    The second of this module's two surname rules, and deliberately not
    `first_author_surname`. That one returns pybtex prelast + last -- identity
    text, feeding `fallback_key` and `same_work_key`, which need to agree with
    what `generate_bibliography` renders. This one returns text to search FOR
    in prose: `check_evidence.find_cites` builds a regex from it to locate
    Chicago author-date cites in a review's Markdown, and `resolve_context`
    matches it against an SEP passage. A comma in that string finds nothing.

    Where the two rules differ is ONE mechanism, not a list of shapes, and
    reading it that way is load-bearing: three attempts to enumerate the
    shapes here were wrong, each by asserting a universal over sampled inputs.
    Transcribed from the code rather than generalised from samples -- that
    distinction is the whole lesson here -- and scoped to the call path both
    prose consumers use, ONE author field and no editor. Let
    `first = first_author_name(author)` and `prefix = first.split(",")[0]
    .strip()`. This rule returns `prefix`. `first_author_surname` takes one of
    three branches:

        1. `Person(first)` parses and yields a surname: pybtex's SELECTED
           parts (prelast + last), joined by single spaces. Diverges from
           `prefix` whenever that rendering differs from it -- the usual case,
           and the one the examples below are about.
        2. It raises or yields nothing, and `first` HAS a comma:
           `_fallback_surname` returns the same pre-comma split, so this
           branch agrees with `prefix` by construction.
        3. It raises or yields nothing, and `first` is COMMA-LESS:
           `_fallback_surname` returns the LAST whitespace token, not
           `prefix`. So this branch can diverge too -- `~ ~` gives `~ ~` here
           and `~` there, pybtex raising `UnboundLocalError` on a tie-only
           name. Degenerate input, but real: an earlier draft of this
           paragraph claimed the fallback always agreed, and branch 3 is
           what falsified it.

    Note what pybtex's side does, since "normalisation" undersells it: it
    classifies tokens by name role and keeps only the surname ones, so
    dropping `Jane` from `Jane Doe` is a semantic projection, and it re-joins
    the parts it keeps with single spaces. Two operations, either of which can
    make its result differ from the prefix.

    Outside that scope the relation does not hold and is not claimed:
    `first_author_surname` takes an editor fallback this rule has no parameter
    for, so `first_author_surname("", editor)` returns a surname where this
    returns `""`. That is a difference in what the functions are FOR, not an
    instance of the mechanism.

    Known divergence classes, as EXAMPLES and not an exhaustive set -- all
    pre-date this owner:

    - A comma-less name pybtex can split (MULTI-token): `Jane Doe` yields
      `Jane Doe` here and `Doe` there. Single-token names do not diverge --
      `Aristotle` is `Aristotle` from both.
    - A comma-less name whose tokens are tie-separated: `Doe~Jane` gives
      `Doe~Jane` here and `Jane` there (a tie separates for pybtex).
    - An UNPROTECTED separator inside the surname that is not a single space:
      `van~Fraassen, Bas C.`, `van  Fraassen, Bas C.` and a newline-separated
      one give the prefix here and `van Fraassen` there. Two things this is
      NOT: it is not "any whitespace variation" -- a PROTECTED group is one
      token to pybtex, so `{van~Fraassen}, Bas` AGREES from both -- and plain
      `van Fraassen, Bas C.` agrees only because its prefix already is what
      pybtex renders.
    - A braced name with a comma INSIDE the group. The list split is
      brace-aware but this comma split is not, so `{Doe, Jane}` yields the
      brace-unbalanced `{Doe`, where the identity rule keeps `{Doe, Jane}`
      whole.

    What a divergence COSTS, stated no more strongly than it is measured: the
    two rules hand the consumers different search strings, and recall drops
    when the string does not match the form the target prose uses. It is not
    true that a divergent value never matches -- `find_cites` DOES find
    `Jane Doe` in prose that writes the full name. The bet is on Chicago
    author-date normally writing the surname alone, which makes the typical
    cost a silent under-report; every divergence measured so far fails closed
    (no positions, no candidate line) rather than raising, so the cost lands
    as false "uncited" telemetry on two recall-floor checkers, never a block.
    Do NOT "fix" any of them by switching to the identity rule or by stripping
    braces without measuring first: the switch is not a clean fix (Chicago
    prose writes neither `{Doe, Jane}` nor `{Doe`), and the rate at which any
    of these forms reaches a delivered bib is unknown. The roadmap's census
    compares the two rules over the delivered corpus rather than counting
    shapes, for exactly the reason this docstring opens with.

    No editor fallback, unlike `first_author_surname`: both callers read the
    author field alone, and `check_evidence`'s module docstring records
    editor-only entries' resulting invisibility as an accepted residual.
    Never raises -- `split_author_list` returns unbalanced input whole and no
    `Person` is constructed here.
    """
    return first_author_name(author).split(",")[0].strip()
