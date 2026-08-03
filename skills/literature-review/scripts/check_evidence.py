"""Phase 6 evidence-tier telemetry checker.

Post-hoc, non-blocking scan of the assembled review against its merged
bibliography: flags citations whose entry carries no evidence-tier stamp,
citations of EVIDENCE-NONE entries, and reporting-verb sentences attached to
low-trust tiers (EXISTENCE, NONE, or unstamped). This is telemetry only --
it always exits 0 (except on usage error) and never blocks anything.

Known flag/miss shapes for the human adjudicating the output (all observed
live, 2026-07-28 A/B run + 2026-08-02 gate-(b) validation run):

- Same-surname-same-year collisions: the checker matches surname+year only,
  so prose citing an ABSTRACT-tier sibling (Knuuttila 2005 mediation vs.
  2005 artefacts thesis; Knuuttila & Boon 2011 vs. Knuuttila 2011) flags the
  low-tier twin. Resolve against the full citation in prose / entry titles
  before calling it a violation (ROADMAP items 3E/3F own the underlying
  defect).
- Self-reference FPs: "as argued in the section on X" trips the verb match
  whenever a low-tier surname/year sits within the window.
- Matches inside References-entry TITLES: a cited work whose title names
  another work ("A Critical Assessment of Levins's ... (1966)") reads as a
  prose cite of the named work.
- Editor-only entries are INVISIBLE: rc_surname reads the author field, so
  an entry with only `editor` gets no surname and is skipped entirely --
  neither its violations nor its none-cites can ever be flagged.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import stamp_evidence as se

_MATCH_WINDOW = 60  # mirrors generate_bibliography._MATCH_WINDOW

_TIER_RE = re.compile(r"EVIDENCE-[A-Za-z0-9_-]+")

# Reporting verbs, in two senses: ATTRIBUTION ("X contends that P") and
# SUCCESS ("X shows that P"). Both attach claim content to a source, which a
# low-trust tier does not license.
#
# This list is a RECALL FLOOR, not a precision instrument -- every hit is
# adjudicated by a human, so a false positive costs seconds while a miss ships
# an unlicensed claim. Widened 2026-07-28 after the evidence-tier A/B spot
# check: 4 of the 5 violations the checker missed were missed solely because
# the verb was absent ("presses", "occupies", "developed", "identify").
#
# Two deliberate choices:
#  - Bare plural forms ("argue", "identify") are included. Multi-author works
#    are cited with plural subjects constantly ("Adams and Aizawa argue"), and
#    the original list carried only the -s/-ed forms.
#  - Forms whose NOUN sense dominates this corpus are excluded even though the
#    verb sense is real: "objects" (physical objects), "challenges" (the
#    challenges of X), "established"/"proven"/"held" (adjectival: a
#    well-established view, a widely held assumption). Their unambiguous
#    siblings ("objected", "challenged", "establishes", "proves", "holds")
#    carry the recall.
_ATTRIBUTION_VERBS = (
    "argue", "argues", "argued",
    "assert", "asserts", "asserted",
    "claim", "claims", "claimed",
    "concede", "concedes", "conceded",
    "contend", "contends", "contended",
    "defend", "defends", "defended",
    "deny", "denies", "denied",
    "endorse", "endorses", "endorsed",
    "hold", "holds",
    "maintain", "maintains", "maintained",
    "objected",
    "press", "presses", "pressed",
    "propose", "proposes", "proposed",
    "reject", "rejects", "rejected",
    "reply", "replies", "replied",
    "respond", "responds", "responded",
)

_SUCCESS_VERBS = (
    "challenged",
    "conclude", "concludes", "concluded",
    "demonstrate", "demonstrates", "demonstrated",
    "develop", "develops", "developed",
    "establish", "establishes",
    "find", "finds", "found",
    "identify", "identifies", "identified",
    "occupy", "occupies", "occupied",
    "prove", "proves", "proved",
    "show", "shows", "showed", "shown",
    "trace", "traces", "traced",
)

_VERB_RE = re.compile(
    r"\b(?:" + "|".join(_ATTRIBUTION_VERBS + _SUCCESS_VERBS) + r")\b",
    re.IGNORECASE,
)

_LOW_TRUST_TIERS = (se.TIER_EXISTENCE, se.TIER_NONE, None)


def rc_surname(author_field: str) -> str:
    """First author's surname. Duplicated from
    resolve_context.first_author_surname (one-liner; not worth a
    cross-module import for this)."""
    first = (author_field or "").split(" and ")[0]
    return first.split(",")[0].strip()


def find_cites(md: str, surname: str, year: str) -> list[int]:
    """Positions (in md) of surname occurrences within 60 chars of year.

    The year regex is run over the FULL text (not a pre-sliced window): a
    window carved out first would let a longer digit run straddling the
    slice boundary (e.g. "91962") satisfy (?<!\\d)/(?!\\d) spuriously at the
    cut edge, producing a false-positive citation. Matching globally, then
    filtering by position, keeps the digit-boundary check honest.
    """
    if not surname or not re.fullmatch(r"\d{4}", year or ""):
        return []
    surname_re = re.compile(rf"\b{re.escape(surname)}\b")
    year_re = re.compile(rf"(?<!\d){re.escape(year)}(?!\d)")
    year_positions = [m.start() for m in year_re.finditer(md)]
    if not year_positions:
        return []
    positions = []
    for m in surname_re.finditer(md):
        start = max(0, m.start() - _MATCH_WINDOW)
        end = min(len(md), m.end() + _MATCH_WINDOW)
        if any(start <= yp <= end for yp in year_positions):
            positions.append(m.start())
    return positions


def _sentence_at(md: str, pos: int) -> str:
    """Slice of md between the nearest sentence boundaries around pos."""
    start = 0
    for m in re.finditer(r"[.!?]", md[:pos]):
        start = m.end()
    end_m = re.search(r"[.!?]", md[pos:])
    end = pos + end_m.end() if end_m else len(md)
    return md[start:end].strip()


def cite_sentences(md: str, positions: list[int]) -> list[str]:
    seen = set()
    out = []
    for pos in positions:
        sentence = _sentence_at(md, pos)
        if sentence not in seen:
            seen.add(sentence)
            out.append(sentence)
    return out


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: check_evidence.py <review.md> <merged.bib>")
        return 1
    md = Path(sys.argv[1]).read_text(encoding="utf-8")
    bib_content = Path(sys.argv[2]).read_text(encoding="utf-8")

    # Bare-key map is safe here (unlike the barrier's per-domain maps): this
    # checker consumes one already-merged .bib, where citation keys are
    # unique post-dedupe, not several per-domain files with overlapping keys.
    entries = {}
    for chunk in se.split_entries(bib_content):
        header = se.entry_header(chunk)
        if not header:
            continue
        _etype, key = header
        fields = se.parse_entry_fields(chunk)
        surname = rc_surname(fields.get("author", ""))
        year = (fields.get("year") or "").strip()
        if not surname or not re.fullmatch(r"\d{4}", year):
            continue  # Guard: empty surname/non-year -> unfindable, skip
        matches = _TIER_RE.findall(fields.get("keywords", ""))
        tier = matches[-1] if matches else None  # last match wins
        entries[key] = {"tier": tier, "surname": surname, "year": year}

    counts = {"unstamped": 0, "none_cited": 0, "reporting_verb": 0}

    for key, info in entries.items():
        positions = find_cites(md, info["surname"], info["year"])
        if not positions:
            continue
        tier = info["tier"]
        if tier is None:
            print(f"CHECK unstamped-cited: {key}")
            counts["unstamped"] += 1
        if tier == se.TIER_NONE:
            print(f"CHECK none-cited: {key}")
            counts["none_cited"] += 1
        if tier in _LOW_TRUST_TIERS:
            # cite_sentences() already dedupes per-key sentences (its own
            # `seen` set); keys themselves are unique here (dict iteration),
            # so no cross-key (key, sentence) dedupe is needed on top.
            for sentence in cite_sentences(md, positions):
                if _VERB_RE.search(sentence):
                    label = tier or "unstamped"
                    snippet = _ascii(sentence[:120])
                    print(f"CHECK reporting-verb: {key} ({label}): {snippet}")
                    counts["reporting_verb"] += 1

    print("CHECK-SUMMARY: " + json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
