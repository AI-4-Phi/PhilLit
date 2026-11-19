"""Phase 6 evidence-tier telemetry checker.

Post-hoc, non-blocking scan of the assembled review against its merged
bibliography: flags citations whose entry carries no evidence-tier stamp,
citations of EVIDENCE-NONE entries, and reporting-verb sentences attached to
low-trust tiers (EXISTENCE, NONE, or unstamped), and (PL-39) status words
-- correction, retraction, withdrawal, expression of concern, preprint -- in
a sentence citing an entry whose barrier-stamped `status_notice` lacks that
category (`status-claim`), plus every cited retracted or withdrawn entry
with the sentences citing it (`retracted-cited`). This is telemetry only --
it always exits 0 (except on usage error) and never blocks anything.

Known flag/miss shapes for the human adjudicating the output (all observed
live, 2026-07-28 A/B run + 2026-08-02 gate-(b) validation run):

- Same-surname-same-year collisions: the checker matches surname+year only,
  so prose citing an ABSTRACT-tier sibling (Knuuttila 2005 mediation vs.
  2005 artefacts thesis; Knuuttila & Boon 2011 vs. Knuuttila 2011) flags the
  low-tier twin. Resolve against the full citation in prose / entry titles
  before calling it a violation (collision-aware matching and the Chicago
  letters own the underlying defect).
- Self-reference FPs: "as argued in the section on X" trips the verb match
  whenever a low-tier surname/year sits within the window.
- The References section is not scanned (prose_only): its entries are not
  citations.
- Co-author positions are skipped: a surname right after "<Name> and " or
  "<Name> & " is not a cite of that author's own work. A middle author in a
  three-name list ("Susser, Roessler, and Nissenbaum") still matches.
- Editor-only entries are INVISIBLE: rc_surname reads the author field, so
  an entry with only `editor` gets no surname and is skipped entirely --
  neither its violations nor its none-cites can ever be flagged.
- Status words are matched as words, not senses: "a correction of Kant's
  argument" or "the withdrawal of troops" in a sentence citing a work raises
  `status-claim` for it. A unit (the citing sentence, one non-citing
  sentence before it, two after) can also attribute a status word to every
  work it cites; only "the former" / "the latter" with exactly two cited
  works narrow it, so "Smith (2020) cites Jones (2019), whose paper was
  retracted" names Smith too. "The former" / "the latter" narrow only the
  sentence that holds the status word.
- Sentence ends for the status checks: a stop before a lowercase word, after
  a single capital (an initial, "J. S. Mill"; also "Plan B."), or inside
  "et al.", "e.g.", "i.e.", "cf." or a page locator is not one.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import stamp_evidence as se
from enrich_bibliography import get_author_last_name  # noqa: E402 - same directory
# The status_notice value grammar's one owner, a leaf module (aliases).
from status_items import categories as status_categories  # noqa: E402
from status_items import parse_items as status_items_of  # noqa: E402

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

# The verb heuristics below run only on these tiers, so nothing mechanical
# polices how a WEB-tier source is characterized: the note-license boundary is
# held by writer prose alone, against a measured 1-in-4 note-drift baseline.
# ACCEPTED RESIDUAL, not queued. Extending the verb heuristic as it stands
# would false-positive on legitimate note-licensed cites (WEB characterization
# IS licensed from the entry's note); whether a feasible check exists at all --
# note-vs-prose containment at Phase 6, say -- is open.
_LOW_TRUST_TIERS = (se.TIER_EXISTENCE, se.TIER_NONE, None)


# The search-text surname rule, owned by enrich_bibliography: a name that is
# one outer brace group is unwrapped and split on its content's first comma;
# otherwise the pre-comma text, else the LAST whitespace token; then
# case-protection braces around plain letters come off (`{B}rown` -> `Brown`)
# while LaTeX escape groups stay (`B{\"o}hm` keeps its braces, so a
# LaTeX-escaped surname still matches no prose -- a miss the prose rule had
# too). The historic name stays as an alias, never a second copy, and tests
# pin `is`. Its parameter is the owner's entry dict, so call it as
# `rc_surname({"fields": fields})`; it returns None for no author.
#
# Imported, not moved into bib_identity: that module's rules take field
# strings, so a dict-taking rule there would need a non-alias adapter, and
# the downstream service's re-vendor units anchor on enrich_bibliography's
# text. The import brings dotenv, rate_limiter and bib_fields into this
# process (all in the locked environment, none touching the filesystem at
# import) and leaves philosophy-research/scripts on sys.path -- no module
# name is shared between that directory and this one -- while popping the
# hooks/ entry it adds.
#
# Not bib_identity's `first_author_prose_surname`, which this checker
# consumed until the 2026-09-04 surname census licensed the switch
# (reproduction: docs/known-issues/surname-rule-census-2026-09-04,
# local-only). That rule keeps every brace, so a corporate author
# (`{Human Rights Watch}`) or a case-protected letter (`Zają{c}`) put a
# literal `{` into the regex below and every such entry read as never cited.
# Over the delivered corpora the two rules handed this checker different
# text on 8 production and 4 local entries, all of that shape; the search
# rule recovered five adjudicated-correct cites, missed nothing the prose
# rule found, and never hit at a different position -- the procedure's three
# clauses -- so it qualified under the census's pre-registered procedure for
# THIS consumer alone. `resolve_context` keeps the prose rule: its
# population was too small to decide, and its cost is a tier, not telemetry.
rc_surname = get_author_last_name


# A surname right after "<Capitalized> and " or "<Capitalized> & " is a later
# author of someone else's citation: "Dunn and Risko (2016)" cites Dunn's work,
# not Risko's own 2016 paper (PL-36). The rule follows
# generate_bibliography, whose co-author position never cites the second name.
_COAUTHOR_BEFORE_RE = re.compile(r"[A-ZÀ-Þ][\w'’À-ÿ-]*,?\s+(?:and|&)\s+\Z")


def _coauthor_position(md: str, pos: int) -> bool:
    return bool(_COAUTHOR_BEFORE_RE.search(md[max(0, pos - 80):pos]))


def find_cites(md: str, surname: str, year: str, suffix: str = "") -> list[int]:
    """Positions (in md) of surname occurrences within 60 chars of year.

    ACCEPTED RESIDUAL: the surname regex is built from the RAW bib character,
    so a document mixing the straight and curly apostrophe for one surname
    (`O'Neill` / `O’Neill`) under-reports cites here. The renderer and the
    linter are immune -- both compare through `bib_identity` folds, which unify
    the two -- so the cost is false "uncited" telemetry on a recall-floor
    checker, never a block.

    The year regex is run over the FULL text (not a pre-sliced window): a
    window carved out first would let a longer digit run straddling the
    slice boundary (e.g. "91962") satisfy (?<!\\d)/(?!\\d) spuriously at the
    cut edge, producing a false-positive citation. Matching globally, then
    filtering by position, keeps the digit-boundary check honest.

    `suffix` is the entry's own Chicago letter, if it carries
    one. An entry carrying a letter is cited where the prose carries that
    SAME letter -- OR where the prose gives a BARE year. A bare
    "Menary (2010)" is what generate_bibliography deliberately treats as
    ambiguous-keep-all, so counting it as citing NEITHER lettered work would
    report both as uncited: false telemetry manufactured by this feature.
    Entries without a letter keep the historic behaviour, so prose that
    letters a work the bib never lettered still resolves. Letter matching
    is case-insensitive in both directions -- see the comment on
    `qualifying_re` for why a half-measure there is worse than none.

    Suffix mode additionally disambiguates two DIFFERENT lettered mentions
    of the same base year sitting close together (e.g. "Menary (2010a) ...
    Menary (2010b)" in one paragraph): the plain within-window check below
    would count BOTH "Menary" occurrences for EITHER letter, since a
    60-char window easily spans two adjacent citations. The pairing anchors
    on the YEAR, not the surname -- each QUALIFYING year mention claims its
    nearest surname occurrence. Anchoring on the surname instead
    under-reports, in three ways measured on real prose: one surname can
    serve two letters ("Menary (2010a; 2010b)", a form 4 of 33 delivered
    reviews already use) but could credit only the nearer one; an equal
    distance to two years resolved to the year PRECEDING the surname, which
    is backwards for "Surname YEAR" prose; and an unqualifying mention
    nearby ("the 2010s") could win the contest and suppress a real cite
    outright.

    The trade, deliberate: a surname occurrence near a qualifying year but
    not the NEAREST surname to it is no longer credited ("Menary defends
    integration. See also (Menary 2010a).") -- one lettered year names
    exactly one work, so it votes once. That costs a little reporting-verb
    recall on this recall-floor checker; do not widen it back.
    """
    if not surname or not re.fullmatch(r"\d{4}", year or ""):
        return []
    surname_re = re.compile(rf"\b{re.escape(surname)}\b")
    own = [m for m in surname_re.finditer(md) if not _coauthor_position(md, m.start())]

    if not suffix:
        bare_year_re = re.compile(rf"(?<!\d){re.escape(year)}(?!\d)")
        year_positions = [m.start() for m in bare_year_re.finditer(md)]
        if not year_positions:
            return []
        positions = []
        for m in own:
            start = max(0, m.start() - _MATCH_WINDOW)
            end = min(len(md), m.end() + _MATCH_WINDOW)
            if any(start <= yp <= end for yp in year_positions):
                positions.append(m.start())
        return positions

    # Right-lettered ("2010a") or bare ("2010", not followed by another
    # letter or digit). No separate bare-year scan is needed as a guard:
    # every qualifying position is also a bare-year position, since neither
    # alternative can be followed by a digit.
    #
    # CASE-INSENSITIVE. Case-sensitively, "2010B" failed the explicit `b`
    # alternative and then SATISFIED the bare-year lookahead -- so an
    # uppercase letter read as a BARE citation and credited every lettered
    # entry for that year, the 'a' entry included. Case normalisation is
    # settled elsewhere in the Chicago a/b machinery
    # (generate_bibliography._entry_suffix lowercases what it renders and
    # matches; its prose sighting scan is explicitly case-insensitive), so
    # this checker follows suit rather than inventing a third reading.
    #
    # The FLAG is what does the work: under re.IGNORECASE a `[0-9a-z]` class
    # already matches A-Z, so spelling the class `[0-9A-Za-z]` changes
    # nothing today (measured, both ways). It is written out anyway so the
    # bare-year half does not silently DEPEND on the flag -- dropping the
    # flag alone would then reopen the hole, whereas dropping it now merely
    # under-credits an uppercase mention, which is the safe direction.
    qualifying_re = re.compile(
        rf"(?<!\d){re.escape(year)}(?:{re.escape(suffix)}\b|(?![0-9A-Za-z]))",
        re.IGNORECASE)
    qualifying_positions = [m.start() for m in qualifying_re.finditer(md)]
    if not qualifying_positions:
        return []
    surname_matches = own
    hits = set()
    for yp in qualifying_positions:
        nearby = [m for m in surname_matches
                  if max(0, m.start() - _MATCH_WINDOW) <= yp
                  <= min(len(md), m.end() + _MATCH_WINDOW)]
        if nearby:
            hits.add(min(nearby, key=lambda m: abs(m.start() - yp)).start())
    return sorted(hits)


_ANY_STOP = r"[.!?]"
# The status checks end a sentence only at a stop followed by whitespace or
# the end: the writer contract puts a notice link (https://doi.org/10.x/y)
# inside the very sentence that states the status, and its dots would
# otherwise cut the status word off from the cite.
# "et al.", "e.g.", "i.e." and "cf." never end one either: multi-author
# empirical work, where notices cluster, is cited "Costello et al. (2024)".
# A stop ends a status sentence only when whitespace and then an uppercase
# letter, an opening quote or a bracket follow, or the text ends: "(2024,
# p. 12)" and "pp. 4-5" never cut a sentence. A single capital before the
# stop is an initial ("J. S. Mill"), never a sentence end. Accepted
# consequences: a sentence that starts lowercase after a stop ("... then it
# was retracted.") is read as part of the one before, and so is one after a
# sentence ending in a single capital ("Plan B. It was retracted.").
_SPACED_STOP = (r"(?<!\bet al)(?<!\be\.g)(?<!\bi\.e)(?<!\bcf)(?<!\b[A-Z])"
                r"[.!?](?=\s+[A-Z\"'\u201c\u2018(\[]|\s*\Z)")


def _sentence_at(md: str, pos: int, stop: str = _ANY_STOP) -> str:
    """Slice of md between the nearest sentence boundaries around pos."""
    start = 0
    for m in re.finditer(stop, md[:pos]):
        start = m.end()
    end_m = re.search(stop, md[pos:])
    end = pos + end_m.end() if end_m else len(md)
    return md[start:end].strip()


def cite_sentences(md: str, positions: list[int], stop: str = _ANY_STOP) -> list[str]:
    seen = set()
    out = []
    for pos in positions:
        sentence = _sentence_at(md, pos, stop)
        if sentence not in seen:
            seen.add(sentence)
            out.append(sentence)
    return out


# PL-39 status words, by the `status_notice` category that licenses them.
# Whole words, not stems: "incorrect", "corrects course" and "withdraws the
# objection" are ordinary prose. A partial_retraction item licenses a
# retraction word only with "partial(ly)" in the same sentence.
_STATUS_WORDS = (
    ("correction", re.compile(
        r"\b(?:corrections?|corrected|erratum|errata|corrigend(?:um|a))\b", re.I)),
    ("withdrawal", re.compile(r"\b(?:withdrawn|withdrawal)\b", re.I)),
    ("expression_of_concern", re.compile(r"\bexpression\s+of\s+concern\b", re.I)),
    ("preprint", re.compile(r"\bpreprints?\b", re.I)),
)
_RETRACT_RE = re.compile(r"\bretract(?:ed|ion)\b", re.I)
# "partial(ly)" qualifies a retraction word only when it directly modifies
# it: at most two words between ("partially retracted", "partial
# retraction", "partially and quietly retracted"), never "partial agreement
# and has been retracted".
_PARTIAL_BEFORE_RE = re.compile(r"\bpartial(?:ly)?\s+(?:\w+\s+){0,2}\Z", re.I)
_RETRACTED_CATEGORIES = ("retraction", "partial_retraction", "withdrawal")


def _status_categories_in(text: str) -> list[str]:
    """The status categories a text's words claim, in a fixed order. A
    retraction word is `partial_retraction` when "partial(ly)" directly
    modifies it, else `retraction`; each licenses only its own stamp."""
    found = [cat for cat, word_re in _STATUS_WORDS if word_re.search(text)]
    for m in _RETRACT_RE.finditer(text):
        cat = ("partial_retraction" if _PARTIAL_BEFORE_RE.search(text[:m.start()])
               else "retraction")
        if cat not in found:
            found.append(cat)
    order = ("retraction", "partial_retraction", "withdrawal",
             "expression_of_concern", "correction", "preprint")
    return sorted(found, key=order.index)


def _span_at(md: str, pos: int, stop: str) -> tuple[int, int]:
    """(start, end) of the sentence around pos, whitespace trimmed."""
    start = 0
    for m in re.finditer(stop, md[:pos]):
        start = m.end()
    end_m = re.search(stop, md[pos:])
    end = pos + end_m.end() if end_m else len(md)
    while start < end and md[start].isspace():
        start += 1
    return start, end


def _next_span(md: str, end: int, stop: str) -> tuple[int, int] | None:
    """The sentence right after `end` in the same paragraph, if any."""
    gap = re.match(r"\s*", md[end:]).group(0)
    if "\n\n" in gap or end + len(gap) >= len(md):
        return None
    start = end + len(gap)
    m = re.search(stop, md[start:])
    return start, (start + m.end() if m else len(md))


def _prev_span(md: str, start: int, stop: str) -> tuple[int, int] | None:
    """The sentence right before `start` in the same paragraph, if any."""
    head = md[:start]
    gap = head[len(head.rstrip()):]
    end = start - len(gap)
    if end <= 0 or "\n\n" in gap:
        return None
    span = _span_at(md, end - 1, stop)
    para = md.rfind("\n\n", 0, end)
    first = max(span[0], para + 2 if para >= 0 else 0)
    while first < end and md[first].isspace():
        first += 1
    return (first, end) if first < end else None


_FORMER_RE = re.compile(r"\bthe\s+former\b", re.I)
_LATTER_RE = re.compile(r"\bthe\s+latter\b", re.I)


def _units(md: str, entries: dict) -> list[tuple[str, list[str], str]]:
    """(unit text, cited keys in order of first mention, citing sentence) per
    citing sentence. A unit is the citing sentence, the ONE non-citing
    sentence right before it, and up to TWO consecutive non-citing sentences
    right after it, all within its paragraph."""
    by_span: dict[tuple[int, int], dict[str, int]] = {}
    for key, info in entries.items():
        for pos in info["positions"]:
            seen = by_span.setdefault(_span_at(md, pos, _SPACED_STOP), {})
            seen[key] = min(pos, seen.get(key, pos))
    starts = {a for a, _b in by_span}
    out = []
    for (start, end), first_pos in sorted(by_span.items()):
        keys = sorted(first_pos, key=first_pos.get)
        lo = start
        prev = _prev_span(md, start, _SPACED_STOP)
        if prev and prev[0] not in starts:
            lo = prev[0]
        hi = end
        for _ in range(2):
            nxt = _next_span(md, hi, _SPACED_STOP)
            if not nxt or nxt[0] in starts:
                break
            hi = nxt[1]
        out.append((md[lo:hi].strip(), keys, md[start:end].strip()))
    return out


def _addressed(unit: str, keys: list[str]) -> list[str]:
    """"The former" / "the latter" with exactly two cited works narrow a
    status word to the first / the last of them."""
    if len(keys) != 2:
        return keys
    former, latter = bool(_FORMER_RE.search(unit)), bool(_LATTER_RE.search(unit))
    if former and not latter:
        return keys[:1]
    if latter and not former:
        return keys[1:]
    return keys


def _split_sentences(text: str) -> list[str]:
    out, start = [], 0
    for m in re.finditer(_SPACED_STOP, text):
        out.append(text[start:m.end()].strip())
        start = m.end()
    if text[start:].strip():
        out.append(text[start:].strip())
    return out


def _has_link(text: str, doi: str) -> bool:
    return doi.lower() in text.lower()


def status_checks(md: str, entries: dict,
                  override_keys: set | None = None):
    """(status-claim lines, retracted-cited lines, status-link lines).
    `entries` maps key to {"positions": cite positions, "status": its
    status_notice categories, "items": its (category, notice DOI) items}.

    status-claim: a unit (see `_units`) holds a status word whose category a
    work it cites -- narrowed by "the former" / "the latter" -- lacks; one
    line per unit and category, naming every such work and, after
    "licensed:", the ones whose field has it. status-link: a licensed status
    statement whose unit lacks the notice DOI (as a link or bare), when no
    earlier text names it either (the link is due on first mention).
    retracted-cited: one line per cited entry stamped retraction,
    partial_retraction or withdrawal, listing in full each citing sentence,
    extended through the unit's following sentences when the disclosure
    sits there, so the orchestrator can confirm each discloses the status."""
    claims, links = [], []
    disclosed: dict[str, list[str]] = {}
    for unit, keys, citing in _units(md, entries):
        cats = _status_categories_in(unit)
        sentences = _split_sentences(unit)
        for category in cats:
            # "The former" / "the latter" narrow only the sentence that
            # holds the status word, never the whole unit.
            named = []
            for sentence in sentences:
                if category in _status_categories_in(sentence):
                    named += [k for k in _addressed(sentence, keys) if k not in named]
            if not named:   # the word straddles a split; fall back to the unit
                named = _addressed(unit, keys)
            lacking = [k for k in named if category not in entries[k]["status"]]
            if lacking:
                licensed = [k for k in named if k not in lacking]
                also = f"; licensed: {', '.join(licensed)}" if licensed else ""
                claims.append(f"CHECK status-claim: {', '.join(lacking)} ({category}{also}): "
                              f"{_ascii(unit)}{_tag(keys, override_keys)}")
            for k in named:
                for cat, doi in entries[k].get("items") or []:
                    if cat != category or not doi:
                        continue
                    if _has_link(unit, doi) or _has_link(md[:md.find(unit)], doi):
                        continue
                    links.append(f"CHECK status-link: {k} ({category}): {_ascii(unit)}"
                                 f"{_tag([k], override_keys)}")
        tail = unit[unit.find(citing) + len(citing):] if citing in unit else ""
        shown = citing
        if tail and any(c in _RETRACTED_CATEGORIES for c in _status_categories_in(tail)):
            shown = unit[unit.find(citing):]
        for k in keys:
            disclosed.setdefault(k, [])
            if shown not in disclosed[k]:
                disclosed[k].append(shown)
    cited = []
    for key, info in entries.items():
        cats = [c for c in _RETRACTED_CATEGORIES if c in info["status"]]
        if not cats or key not in disclosed:
            continue
        cited.append(f"CHECK retracted-cited: {key} ({', '.join(cats)}): "
                     + " | ".join(_ascii(x) for x in disclosed[key])
                     + _tag([key], override_keys))
    return claims, cited, links


def _tag(keys, override_keys) -> str:
    return _OVERRIDE_TAG if override_keys and any(k in override_keys for k in keys) else ""


_OVERRIDE_PREFIX = "Tier override (user request):"
_OVERRIDE_TAG = " [user-requested override]"


def parse_override_keys(text: str) -> set[str]:
    """Citekeys named by the orchestrator's tier-overrides.md.

    Each line looks like
    `Tier override (user request): k1, k2 (EVIDENCE-EXISTENCE); user's
    description: "..."`; the keys are the ", "-separated names before the
    first ` (` (the tier part may be `(no tier)`, the description part is
    optional). Lines without the prefix are ignored.
    """
    keys: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(_OVERRIDE_PREFIX):
            continue
        head = line[len(_OVERRIDE_PREFIX):].split(" (", 1)[0]
        keys.update(k.strip() for k in head.split(",") if k.strip())
    return keys


def _load_override_keys(path_arg: str | None) -> set[str]:
    """Keys from the overrides file; a missing/unreadable file warns, never fails."""
    if not path_arg:
        return set()
    path = Path(path_arg)
    try:
        return parse_override_keys(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        print(_ascii(f"WARNING: check_evidence: overrides file not readable, "
                     f"no override tagging: {path_arg}"), file=sys.stderr)
        return set()


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


_REFS_HEADING_RE = re.compile(r"^#{1,6}[ \t]+References[ \t]*$", re.MULTILINE | re.IGNORECASE)


def prose_only(md: str) -> str:
    """The review up to its References heading: References entries are not
    citations, and adjacent entries read as one sentence citing two works."""
    m = _REFS_HEADING_RE.search(md)
    return md[:m.start()] if m else md


def main() -> int:
    usage = ("check_evidence.py <review.md> <merged.bib> "
             "[--overrides <tier-overrides.md>]")
    parser = argparse.ArgumentParser(prog="check_evidence.py", usage=usage)
    parser.add_argument("review")
    parser.add_argument("bib")
    parser.add_argument("--overrides", default=None)
    try:
        args = parser.parse_args(sys.argv[1:])
    except SystemExit as e:
        if e.code == 0:  # --help
            raise
        print(f"Usage: {usage}")
        return 1
    md = prose_only(Path(args.review).read_text(encoding="utf-8"))
    bib_content = Path(args.bib).read_text(encoding="utf-8")
    override_keys = _load_override_keys(args.overrides)

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
        surname = rc_surname({"fields": fields})
        year = (fields.get("year") or "").strip()
        if not surname or not re.fullmatch(r"\d{4}", year):
            continue  # Guard: empty surname/non-year -> unfindable, skip
        # A malformed field (not a single a-z letter) renders as if absent
        # rather than feeding a bogus suffix into find_cites (mirrors
        # generate_bibliography._display_year's same guard).
        raw_suffix = (fields.get("year_suffix") or "").strip().lower()
        suffix = (raw_suffix if len(raw_suffix) == 1 and raw_suffix.isalpha()
                  and raw_suffix.isascii() else "")
        matches = _TIER_RE.findall(fields.get("keywords", ""))
        tier = matches[-1] if matches else None  # last match wins
        entries[key] = {
            "tier": tier, "surname": surname, "year": year, "suffix": suffix,
            "status": status_categories(fields.get("status_notice")),
            "items": status_items_of(fields.get("status_notice")),
        }

    counts = {"unstamped": 0, "none_cited": 0, "reporting_verb": 0,
              "status_claim": 0, "retracted_cited": 0, "status_link": 0}
    cited_status = {}

    for key, info in entries.items():
        positions = find_cites(md, info["surname"], info["year"], info["suffix"])
        if not positions:
            continue
        cited_status[key] = {"positions": positions, "status": info["status"],
                             "items": info["items"]}
        tier = info["tier"]
        tag = _OVERRIDE_TAG if key in override_keys else ""
        if tier is None:
            print(f"CHECK unstamped-cited: {key}{tag}")
            counts["unstamped"] += 1
        if tier == se.TIER_NONE:
            print(f"CHECK none-cited: {key}{tag}")
            counts["none_cited"] += 1
        if tier in _LOW_TRUST_TIERS:
            # cite_sentences() already dedupes per-key sentences (its own
            # `seen` set); keys themselves are unique here (dict iteration),
            # so no cross-key (key, sentence) dedupe is needed on top.
            for sentence in cite_sentences(md, positions):
                if _VERB_RE.search(sentence):
                    label = tier or "unstamped"
                    snippet = _ascii(sentence[:120])
                    print(f"CHECK reporting-verb: {key} ({label}): {snippet}{tag}")
                    counts["reporting_verb"] += 1

    claims, retracted, links = status_checks(md, cited_status, override_keys)
    for line in claims + links + retracted:
        print(line)
    counts["status_claim"], counts["retracted_cited"] = len(claims), len(retracted)
    counts["status_link"] = len(links)

    print("CHECK-SUMMARY: " + json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
