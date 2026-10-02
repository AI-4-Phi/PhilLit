"""Is an abstract usable as evidence? The barrier's second abstract test.

`EVIDENCE-ABSTRACT` licenses a writer to characterize, summarize and quote a
work from its abstract. Live corroboration proves the bib's text is the text
the source serves; it cannot see that the text is useless. On 2026-09-10
(topic: separation of powers) five abstracts earned the tier while every one
of them was corroborated: a bare JEL keyword list, two bibliographic stubs,
a chapter's opening paragraph and a full text that degenerates into word
salad. Sources serve such text consistently, so the hash agrees.

`unusable_reason` is that second test, pure and local (no network). The
barrier runs it on a candidate the live fetch corroborated, on a heal's
restored text, and on the final text before stamping. A refusal only
withholds this tier: the entry can still earn CONTEXT, WEB or EXISTENCE.

The four rules, each named by the reason it returns:

* `page-chrome` -- the text holds a publisher landing page's interface
  strings ("Search for other works by this author"), so it is a page scrape.
  Project MUSE labels its own stand-in the same way ("In lieu of an
  abstract, here is a brief excerpt"): an opening excerpt, not a summary.
  Matched case-blind, after HTML entities are decoded and line breaks and
  no-break spaces read as spaces.
  None of the 22 such texts in the measured corpus held an abstract.
* `too-thin` -- fewer than `MIN_RESIDUAL_WORDS` words remain once the
  entry's own citation is removed: its title, author and editor names,
  venue, publisher, series, and citation apparatus (Vol., pp., ...). Words
  are compared with accents folded, so a field's `D{\'e}mocratie` removes
  the abstract's "démocratie". This is
  what a keyword list, a stub, a version notice or a funding line has in
  common: nothing to characterize the work by.
* `body-text` -- a text under `MAX_EXTRACT_WORDS` words with two or more
  footnote calls glued to words ("principle2 of", "fit.3", or superscript
  "fit.³"), their numbers
  distinct and increasing, at least one of them right after a sentence's
  closing punctuation: the text is the work's opening pages, not a summary
  of it. A contents list is not a footnote run: its numbers follow a heading
  word with no punctuation ("Introduction2 Making Time") or are followed by
  a period ("Overview2. Four Arguments"). Nor is one number repeated, which
  is a variable name ("polity2"). A longer text is most of the work itself,
  which a writer can characterize it from.
* `garbled` -- some window of 100 word pairs holds `MIN_GARBLE_HITS` or
  more determiners directly followed by a function word ("the of", "a the"):
  the content words have dropped out of the text. English function words
  only: word salad in another language passes. A capital "A" is never a
  determiner here: in prose it starts a sentence, where "A of" does not
  occur, and in logic and decision theory it names a variable ("A is
  preferred to B"). Every text that passes
  the other rules in the measured corpus stays at 4 or below, a variable
  named "a" or "A" included.

Measured (2026-10-02) over the 2,645 distinct abstracts of 51 local reviews.
The script, its output and a README listing every refusal are in
`docs/known-issues/abstract-usability-measurement-2026-10-02/`. Refused: 22
page-chrome, 26 too-thin, 5 body-text, 4 garbled. Of the 448 tier-stamped
abstracts 11 are refused, each one a real defect, the five known cases
among them. The rules were tuned on this same corpus, so the counts are
in-sample. Some thin but real texts are refused too, and some junk passes,
two tier-stamped texts among it (a publisher's self-description and a dash
list of topics); the README lists both kinds. Long, readable texts pass (NDPR reviews, full texts
that stay prose): length alone is never a reason.
"""
from __future__ import annotations

import html
import re
import unicodedata

MIN_RESIDUAL_WORDS = 15
MAX_EXTRACT_WORDS = 1000
MIN_GARBLE_HITS = 8
GARBLE_WINDOW = 100

PAGE_CHROME = (
    "search for other works by this author",
    "an abstract is not available for this content",
    "click to increase image size",
    "you do not currently have access to this content",
    "download citation file",
    "authors info & claims",
    "in lieu of an abstract",
)

# The entry's own citation fields: their words are the work citing itself.
OWN_FIELDS = ("title", "author", "editor", "journal", "booktitle",
              "publisher", "series")
CITATION_TOKENS = frozenset({
    "vol", "no", "pp", "p", "issue", "volume", "number", "edited", "eds",
    "ed", "press", "university", "journal", "review", "the", "and", "of",
    "in", "a", "an"})

# Words in Unicode letters, so a Greek or Cyrillic abstract is counted, not
# read as empty. Chinese, Japanese, Thai, Lao, Khmer and Burmese write no
# spaces between words, so each of their characters counts as one word.
_UNSPACED = ("\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
             "\u0e00-\u0eff\u1780-\u17ff\u1000-\u109f")
_WORD = re.compile(
    rf"[{_UNSPACED}]|[^\W\d_{_UNSPACED}](?:[^\W\d_{_UNSPACED}]|['’-])*")
_UNSPACED_CHAR = re.compile(rf"[{_UNSPACED}]")
# A LaTeX accent command (\'e, \"{o}, \v{c}), dropped before braces go.
_LATEX_ACCENT = re.compile(r"\\(?:[`'^\"~=.]|[uvHtcdbk](?![A-Za-z]))\s*")
# A footnote call glued to a word: a lowercase word of 3+ letters, optional
# punctuation and closing quote, then 1-2 digits NOT followed by a period.
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_FOOTNOTE = re.compile(
    r"[a-z]{3,}([.,;:!?]?)[\"”’)]?([0-9⁰¹²³⁴⁵⁶⁷⁸⁹]{1,2})(?=\s|$|[,;:)])")
_DETERMINERS = frozenset({"the", "a", "an"})  # compared as written, below
_FUNCTION = frozenset({
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with",
    "by", "is", "are", "was", "were", "that", "as", "at", "from", "be",
    "this", "these", "its", "their"})


def _fold(word: str) -> str:
    """Lowercase with accents removed: "Démocratie" -> "democratie"."""
    return "".join(c for c in unicodedata.normalize("NFKD", word.lower())
                   if not unicodedata.combining(c))


def _words(text: str) -> list[str]:
    return [_fold(w).strip("'’-") for w in _WORD.findall(text)]


def residual_words(abstract: str, fields: dict) -> int:
    """Words the text says beyond citing its own entry."""
    own: set[str] = set()
    for name in OWN_FIELDS:
        value = _LATEX_ACCENT.sub("", fields.get(name) or "")
        own.update(_words(re.sub(r"[{}\\]", "", value)))
    # A one-letter word is an initial or a variable; a CJK character is a word.
    return sum(1 for w in _words(abstract)
               if (len(w) > 1 or _UNSPACED_CHAR.match(w))
               and w not in own and w not in CITATION_TOKENS)


def footnote_calls(abstract: str) -> int:
    """Footnote calls in a distinct, increasing run with at least one call
    after a sentence's closing punctuation; 0 when there is none."""
    calls = _FOOTNOTE.findall(abstract)
    numbers = [int(n.translate(_SUPERSCRIPT)) for _, n in calls]
    if (len(set(numbers)) < 2 or numbers != sorted(numbers)
            or not any(punct and punct in ".!?" for punct, _ in calls)):
        return 0
    return len(numbers)


def garble_hits(abstract: str) -> int:
    """The most determiner + function-word pairs in any window of words."""
    raw = [w.strip("'’-") for w in _WORD.findall(abstract)]
    ws = [w.lower() for w in raw]
    hits = [int(a in _DETERMINERS and raw[i] != "A" and b in _FUNCTION)
            for i, (a, b) in enumerate(zip(ws, ws[1:]))]
    best = cur = sum(hits[:GARBLE_WINDOW])
    for i in range(GARBLE_WINDOW, len(hits)):
        cur += hits[i] - hits[i - GARBLE_WINDOW]
        best = max(best, cur)
    return best


def unusable_reason(abstract: str, fields: dict) -> str | None:
    """Why `abstract` cannot support `EVIDENCE-ABSTRACT`, or None if it can.

    `fields` are the entry's parsed BibTeX fields; only the citation fields
    in `OWN_FIELDS` are read. Rules run cheapest first, and the first that
    fires names the reason.
    """
    text = html.unescape(abstract or "")
    lowered = re.sub(r"\s+", " ", text.lower())
    if any(marker in lowered for marker in PAGE_CHROME):
        return "page-chrome"
    if residual_words(text, fields) < MIN_RESIDUAL_WORDS:
        return "too-thin"
    if len(_words(text)) < MAX_EXTRACT_WORDS and footnote_calls(text) >= 2:
        return "body-text"
    if garble_hits(text) >= MIN_GARBLE_HITS:
        return "garbled"
    return None
