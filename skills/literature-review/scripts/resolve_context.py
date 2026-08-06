"""Mechanical SEP/IEP context acquisition for the evidence barrier.

Matches bibliography entries lacking attested content evidence against the
review's fetched SEP/IEP articles (surname + year candidate lines, fuzzy
title corroboration) and extracts body passages around the disambiguated
in-text citation mentions. Conservative by design: ambiguity attaches
nothing -- a missed enrichment costs one tier; a wrong one manufactures a
sanctioned mischaracterization.

Known accepted limitation (revisit with A/B evidence): the *first* mention of
a work in the article may be a passing "see also" reference, so a CONTEXT
passage can be thin. The writer prompt limits the harm (characterize only
from the passage, attributed), and the A/B protocol includes eyeballing real
sep_context values before trusting the tier.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "philosophy-research" / "scripts"))

TITLE_MATCH_THRESHOLD = 0.5
TITLE_MIN_OVERLAP = 2
_STOPWORDS = {"the", "a", "an", "of", "and", "in", "on", "to", "for"}

AMBIGUOUS = {"ambiguous": True}


def load_slug_files(paths):
    states = {}
    union = {"sep": set(), "iep": set()}
    for p in paths:
        p = Path(p)
        if not p.exists():
            states[str(p)] = "missing"
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sep = data["sep_entries"]
            iep = data["iep_entries"]
            if not isinstance(sep, list) or not isinstance(iep, list):
                raise TypeError("entries must be lists")
            # conservative slug grammar; anything else marks the file malformed
            for s in (*sep, *iep):
                if not isinstance(s, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", s):
                    raise TypeError(f"invalid slug: {s!r}")
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            states[str(p)] = "malformed"
            continue
        states[str(p)] = "valid-empty" if not sep and not iep else "present"
        union["sep"].update(sep)
        union["iep"].update(iep)
    return states, union


def first_author_surname(author_field: str) -> str:
    first = (author_field or "").split(" and ")[0]
    return first.split(",")[0].strip()


def _title_tokens(text: str) -> set:
    return {
        t for t in re.findall(r"[a-z0-9]+", text.casefold())
        if len(t) > 2 and t not in _STOPWORDS
    }


def title_score(bib_title: str, candidate_line: str) -> float:
    bt = _title_tokens(bib_title)
    if not bt:
        return 0.0
    overlap = bt & _title_tokens(candidate_line)
    if len(overlap) < TITLE_MIN_OVERLAP:
        return 0.0
    return len(overlap) / len(bt)


# SEP lists an author's second-and-later works with a repeated-author rule:
# `–––, 2016, Data-Centric Biology, …`. The surname is nowhere on such a line,
# so a naive surname search skips every one of them -- and the convention
# applies to exactly the authors with 2+ listed works, i.e. the canonical
# figures context acquisition most needs to reach. (This cost Leonelli 2016
# its CONTEXT tier in the 2026-07-25 A/B run; see the results write-up.)
# Dash class escaped rather than literal: ASCII hyphen plus U+2010..U+2015
# (hyphen, non-breaking hyphen, figure/en/em dash, horizontal bar). SEP uses
# en dashes today; the escapes keep the source ASCII and the intent explicit.
_REPEATED_AUTHOR_RE = re.compile("^\\s*[-\\u2010-\\u2015]{2,}\\s*[,.]?\\s*")

_YEAR_RE = re.compile(r"(?<!\d)\d{4}(?!\d)")


def _author_prefix(raw: str) -> str:
    """The author segment of a bibliography line: everything before its first
    4-digit year. Used to carry an author across `–––` lines without dragging
    the previous entry's title and publisher along."""
    m = _YEAR_RE.search(raw)
    return raw[:m.start()] if m else raw


def _candidate_lines(article: dict, surname: str, year: str) -> list:
    """Bibliography lines mentioning surname (word-bounded) + year (digit-bounded).

    Repeated-author (`–––`) lines inherit the author of the nearest preceding
    explicit line. The inheritance is *additive*: a line still matches on its
    own raw text exactly as before, so nothing that matched previously can
    stop matching. Only the author prefix is carried, never the whole line,
    or a previous entry's title tokens could manufacture a surname hit.
    """
    out = []
    surname_re = re.compile(rf"\b{re.escape(surname)}\b", re.IGNORECASE)
    year_re = re.compile(rf"(?<!\d){re.escape(year)}(?!\d)")
    carried = ""  # author prefix of the last explicit line, "" before the first
    for item in article.get("bibliography") or []:
        raw = item.get("raw") or ""
        if _REPEATED_AUTHOR_RE.match(raw):
            inherited = carried
        else:
            carried = _author_prefix(raw)
            inherited = ""  # explicit line: the surname is already in raw
        if not year_re.search(raw):
            continue
        if surname_re.search(raw) or (inherited and surname_re.search(inherited)):
            out.append(item)
    return out


def _title_text(item) -> str:
    """Prefer the parsed title (SEP provides one) over the whole raw line --
    whole-line scoring can pick up token overlap from journal/publisher text."""
    parsed = item.get("parsed") if isinstance(item, dict) else None
    if isinstance(parsed, dict) and parsed.get("title"):
        return parsed["title"]
    return item.get("raw", "") if isinstance(item, dict) else str(item)


def match_entry_to_article(fields: dict, article: dict):
    surname = first_author_surname(fields.get("author", ""))
    year = (fields.get("year") or "").strip()
    title = fields.get("title", "")
    if not surname or not re.fullmatch(r"\d{4}", year):
        return None
    candidates = _candidate_lines(article, surname, year)
    scored = [(item, title_score(title, _title_text(item))) for item in candidates]
    passing = [(i, s) for i, s in scored if s >= TITLE_MATCH_THRESHOLD]
    if not passing:
        return None
    if len(passing) > 1:
        return dict(AMBIGUOUS)
    item, score = passing[0]
    raw = item.get("raw", "")
    suffix_m = re.search(rf"{year}([a-z])\b", raw)
    return {
        "line": raw,
        "score": round(score, 3),
        "suffix": suffix_m.group(1) if suffix_m else "",
        "ambiguous": False,
        "n_candidates": len(candidates),
    }


def extract_passage(article, surname, year, suffix, n_candidates):
    """First attributable in-text mention of surname+year(+suffix), or None.

    find_citations sorts hits lexicographically by (section id, position),
    which approximates document order ("10" sorts before "2", and the
    preamble sorts after digit-keyed sections). Accepted: the pick only
    shifts between genuine mentions of the same disambiguated work.
    """
    from citation_context import build_citation_patterns, find_citations
    if not suffix and n_candidates > 1:
        return None  # bare-year mention cannot be tied to the matched line
    patterns = build_citation_patterns(surname, f"{year}{suffix}")
    hits = find_citations(article, patterns)
    if not hits:
        return None
    first = hits[0]
    return {
        "passage": first["context"],
        "section": first["section"],
        "position": first["position_in_text"],
    }


def format_context_value(slug, passage):
    cleaned = re.sub(r"\s+", " ", passage.replace("{", "").replace("}", "")).strip()
    return f"Cited in '{slug}' entry: \"{cleaned}\""


# Braced (one nesting level) OR quoted values -- a forging agent may use
# either form; both must be stripped for sole-author to hold.
_CONTEXT_FIELD_RE = re.compile(
    r"\n\s*(sep_context|iep_context)\s*=\s*"
    r"(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\")\s*,?",
    re.IGNORECASE,
)

# Expected fetch failures only; anything else is a programming error and must
# propagate (the barrier turns it into a run-level failure, not a silent
# degraded fetch).
_FETCH_ERRORS = (LookupError, RuntimeError, OSError)


def strip_context_fields(entry_text):
    # Limits: the field must start on its own line (newline-anchored) and
    # braced values match one nesting level only; the barrier's value-hash
    # binding is the backstop for anything that slips through.
    return _CONTEXT_FIELD_RE.sub("", entry_text)


# A WORK-ADMISSION BUDGET for the encyclopedia-acquisition pass, not a
# wall-clock bound and not a watchdog. Same shape and rationale as
# venue_vetting.PASS_DEADLINE_SECONDS: checked BEFORE each fetch, never around
# one. The guarantee is exactly
#
#     once a fetch returns, no further fetch is started past the budget
#
# so what it bounds is cumulative time across *returning* fetches: the
# slow-but-progressing pass (many slugs, each fetch slow -- backoff storms, a
# degrading server), which would otherwise run unbounded.
#
# WHAT IT DOES NOT COVER: a single call that never returns. Control never comes
# back to the check, so such a call runs forever exactly as if this budget did
# not exist. That is the failure that motivated the file -- on 2026-08-06 a live
# review's barrier sat at 100% CPU for 72 minutes inside one SEP article's
# bibliography parse (docs/known-issues/sep-bibliography-regex-hang.md) -- and
# this budget would NOT have stopped it. What fixed that was making the parser
# linear. Nor is "this budget plus one article's cost" a bound worth stating:
# an article's cost is not itself bounded (the 30 s request timeout governs
# connection and inter-byte reads, not total work).
#
# A per-article interrupt was considered and declined: signal.alarm is
# Windows-hostile and main-thread-only, a multiprocessing worker adds pickling
# boundaries and a subprocess per fetch, and an abandoned daemon thread keeps
# burning the CPU it was meant to reclaim. Instead the budget logs when it
# fires, so a future wedge is visible in the run's stderr rather than silent.
#
# Two policy consequences, stated rather than left to be discovered:
#   * sep is always attempted before iep, so a sep overrun starves every iep
#     slug. Deterministic and arbitrary; acceptable for best-effort enrichment.
#   * the check wraps fetch(), which does its own cache lookup, so past-budget
#     CACHED articles are skipped too even though they would have been free.
#
# Degrading here is safe: context is a best-effort enrichment, and an entry that
# gets none simply fails to reach the CONTEXT tier -- the same outcome as a
# fetch that 404s.
PASS_DEADLINE_SECONDS = 600.0


def fetch_articles(union, debug=False, deadline_seconds=None):
    """Attempt each slug in the union at most once; (articles, failed_slug_ids).

    At most once, not exactly once: slugs reached after the work-admission
    budget expires are fetched zero times.

    Imports resolve at call time so tests can monkeypatch the fetchers.

    Slugs not reached before the budget expires are reported in `failed`,
    exactly like a fetch error -- the caller cannot tell the two apart and does
    not need to, since both mean "no context from this article".
    """
    import time

    import fetch_iep
    import fetch_sep
    from rate_limiter import ExponentialBackoff, get_limiter
    if deadline_seconds is None:
        deadline_seconds = PASS_DEADLINE_SECONDS
    deadline = time.monotonic() + deadline_seconds
    articles, failed = {}, []
    skipped = 0
    for enc, module in (("sep", fetch_sep), ("iep", fetch_iep)):
        slugs = sorted(union.get(enc, ()))
        if not slugs:
            continue
        limiter = get_limiter(f"{enc}_fetch")
        backoff = ExponentialBackoff(max_attempts=5)
        fetch = getattr(module, f"fetch_{enc}_article")
        for slug in slugs:
            if time.monotonic() >= deadline:
                # Out of budget: record every remaining slug as failed rather
                # than silently returning a short article set, so the entries
                # that demote show up in the barrier's report. `failed` carries
                # bare slug ids and says nothing about WHY -- a budget skip, a
                # 404 and a network error are indistinguishable in it. The
                # stderr line below is the only place the distinction is drawn.
                failed.append(f"{enc}:{slug}")
                skipped += 1
                continue
            try:
                articles[f"{enc}:{slug}"] = fetch(slug, limiter, backoff, debug=debug)
            except _FETCH_ERRORS:
                failed.append(f"{enc}:{slug}")
    if skipped:
        # The one signal that a wedge or a slow pass happened at all. Without
        # it a budget overrun is indistinguishable from an encyclopedia set
        # that simply had few articles.
        print(f"[resolve_context] acquisition budget of {deadline_seconds:.0f}s "
              f"expired; {skipped} slug(s) never attempted", file=sys.stderr, flush=True)
    return articles, failed


def acquire_context(entries, articles):
    """Try every article (sorted id order) per entry until one yields a
    match+passage. Ambiguity is per-article: an ambiguous match records
    "ambiguous-skipped" but a later clean article may still match; matched
    outcomes carry encyclopedia/slug/field/value/match_score/
    bibliography_line/section/position, others carry only "outcome"."""
    results = {}
    for key, info in entries.items():
        fields = info["fields"]
        surname = first_author_surname(fields.get("author", ""))
        year = (fields.get("year") or "").strip()
        outcome = {"outcome": "unmatched"}
        for art_id in sorted(articles):
            article = articles[art_id]
            m = match_entry_to_article(fields, article)
            if m is None:
                continue
            if m.get("ambiguous"):
                outcome = {"outcome": "ambiguous-skipped"}
                continue
            passage = extract_passage(
                article, surname, year, m["suffix"], m.get("n_candidates", 1))
            if passage is None:
                continue  # bibliography hit, no extractable body passage
            enc, slug = art_id.split(":", 1)
            outcome = {
                "outcome": "matched",
                "encyclopedia": enc,
                "slug": slug,
                "field": f"{enc}_context",
                "value": format_context_value(slug, passage["passage"]),
                "match_score": m["score"],
                "bibliography_line": m["line"],
                "section": passage["section"],
                "position": passage["position"],
            }
            break
        results[key] = outcome
    return results
