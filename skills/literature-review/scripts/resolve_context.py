"""Mechanical SEP/IEP context acquisition for the evidence barrier.

Matches bibliography entries lacking attested content evidence against the
review's fetched SEP/IEP articles (surname + year candidate lines, fuzzy
title corroboration) and extracts body passages around the disambiguated
in-text citation mentions. Conservative by design: ambiguity attaches
nothing -- a missed enrichment costs one tier; a wrong one manufactures a
sanctioned mischaracterization.
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


def _candidate_lines(article: dict, surname: str, year: str) -> list:
    """Bibliography lines mentioning surname (word-bounded) + year (digit-bounded)."""
    out = []
    surname_re = re.compile(rf"\b{re.escape(surname)}\b", re.IGNORECASE)
    year_re = re.compile(rf"(?<!\d){re.escape(year)}(?!\d)")
    for item in article.get("bibliography") or []:
        raw = item.get("raw") or ""
        if surname_re.search(raw) and year_re.search(raw):
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
