"""Fault-line tags (`FLn.n`): the review plan's definitions, and their
substitution into prose a reader outside the pipeline will see.

The planner emits no fault lines of its own; they appear only when the
user's prompt asks for them, defined in `lit-review-plan.md` as
`- **FLn.n — Title** ...` bullets. DECIDED, do not reopen: substitution is
pure string replacement, no model involved, so no researcher claim is
paraphrased; it applies to the annotated bib's notes AND the notes file
alike; and it FAILS loudly on a tag the plan does not define, since the plan
is per-review and an undefined tag means the two have drifted. Weighed and
rejected: leaving tags in place, a glossary alongside bare tags, an LLM
rewrite, and deleting the tag or its sentence.
"""
from __future__ import annotations

import re

# A whole tag: not inside a word (`AFL1.1x`) and not a prefix of a longer
# number (`FL1.10` is its own tag).
TAG_RE = re.compile(r"(?<![A-Za-z0-9])FL\d+\.\d+(?![\w.]\d|\w)")
_DEF_RE = re.compile(
    r"^\s*[-*]\s+\*\*(FL\d+\.\d+)\s*[—–-]+\s*(.+?)\*\*", re.MULTILINE)
# An unescaped straight quote; `\"` is a LaTeX accent (`M{\"u}ller`), left alone.
_PAIR_QUOTES_RE = re.compile(r'(?<!\\)"([^"]*?)(?<!\\)"')
_LONE_QUOTE_RE = re.compile(r'(?<!\\)"')


class UndefinedFaultLine(ValueError):
    def __init__(self, tags):
        self.tags = sorted(set(tags))
        super().__init__("undefined fault-line tag(s): " + ", ".join(self.tags))


def parse_definitions(plan_text: str) -> dict[str, str]:
    """Tag -> title, from the plan's `- **FLn.n — Title**` bullets."""
    defs = {}
    for m in _DEF_RE.finditer(plan_text):
        title = m.group(2).replace("*", "").strip().rstrip(".").strip()
        defs[m.group(1)] = title
    return defs


def phrase(title: str) -> str:
    """the “<title>” fault line. A capitalised first word is lowercased
    (`One` -> `one`); an acronym (`XCONST`) is not. Straight quotes inside the
    title become curly single quotes, so the phrase is safe inside a
    quote-delimited BibTeX value."""
    first = title.split(" ", 1)[0]
    # Known limitation: a proper-noun first word would be lowercased too; no current plan title starts with one.
    if len(first) > 1 and first[0].isupper() and first[1:] == first[1:].lower():
        title = title[0].lower() + title[1:]
    title = _LONE_QUOTE_RE.sub("’", _PAIR_QUOTES_RE.sub("‘\\1’", title))
    return f"the “{title}” fault line"


def tags_in(text: str) -> list[str]:
    return sorted(set(TAG_RE.findall(text)))


def substitute(text: str, defs: dict[str, str]) -> str:
    missing = [t for t in tags_in(text) if t not in defs]
    if missing:
        raise UndefinedFaultLine(missing)
    return TAG_RE.sub(lambda m: phrase(defs[m.group(0)]), text)
