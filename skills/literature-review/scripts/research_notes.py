"""Per-domain research notes: the `@comment` blocks researchers write at the
head of each domain bib, turned into the `research-notes-<project>.md`
deliverable.

DECIDED, do not reopen: a LABEL is any ALL-CAPS `LABEL:` at the start of a
line - alone on its line or followed by text, in the header block or the
body (an alone-on-its-line-only reading was considered and rejected). An IN
label opens a kept section, an OUT label a dropped one (to the next label).
Any other label - or text under no label, such as a colon-less heading after
a `====` rule - raises UnknownLabel naming every offender: the list is not
closed, and a silent default would either leak telemetry or drop analysis.
The label sets do not grow to admit improvised labels: the researcher
prompt forbids them, colon-less headings and section-dependent sub-labels
(FOR:/AGAINST:). The header block admits only `DOMAIN` and OUT labels, and
it ends at its closing rule or, when the researcher left that rule out, at
the first IN label: an IN label is never legal in a header, so the cut is
unambiguous. A block that raises UnknownLabel is withheld ALONE
(`parse_or_withhold`): the notes file is still delivered, and the block's
place names its unknown labels and says it held unlabelled text, never
quoting or counting it. Accepted residual: an ALL-CAPS line shaped like a
label (`RUN ID 9F3A2C:`) is named like any unknown label, since nothing
tells it from an improvised one. This is a LABEL list, never a sentence-level edit: run-mechanics
prose inside NOTABLE_GAPS and writer-directed sentences inside
RELEVANCE_TO_PROJECT stay untouched, and a provenance label appearing inside
a kept note's own text is never normalised.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_comments import is_verbatim_block  # noqa: E402

sys.path.pop(0)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fault_lines  # noqa: E402

sys.path.pop(0)

IN_LABELS = ("DOMAIN_OVERVIEW", "KEY_POSITIONS", "NOTABLE_GAPS",
             "SYNTHESIS_GUIDANCE", "RELEVANCE_TO_PROJECT")
OUT_LABELS = frozenset({
    "DOMAIN", "SEARCH_DATE", "PAPERS_FOUND", "SEARCH_SOURCES",
    "RETRIEVAL_FAILURES", "FAULT_LINES_POPULATED", "ABSTRACTS", "ROUTING NOTES"})


def _heading(label: str) -> str:
    """`KEY_POSITIONS` -> `Key positions`. Derived, not looked up, so a
    label added to IN_LABELS renders without a matching table entry."""
    return label.replace("_", " ").capitalize()


_RULE_RE = re.compile(r"^\s*={10,}\s*$")
_LABEL_RE = re.compile(r"^([A-Z][A-Z0-9_ ()/-]*[A-Z0-9)]):(.*)$")
_COMMENT_RE = re.compile(r"^\W*@comment\s*[{(]", re.IGNORECASE)
_DOMAIN_LINE_RE = re.compile(r"^DOMAIN:", re.MULTILINE)
_NUMBER_RE = re.compile(r"^(\d+)")


class UnknownLabel(ValueError):
    """`labels` are ALL-CAPS `LABEL:` lines this grammar does not recognise;
    `texts` are stray non-label text (a colon-less heading, text before any
    label, text before the block's own `====` header) - never conflated,
    since one names a token to add to a list and the other names prose."""

    def __init__(self, labels=(), texts=(), title="", no_header=False, never_closed=False):
        self.labels = sorted(set(labels))
        self.texts = sorted(set(texts))
        self.title = title                # the block's DOMAIN: value, if it has one
        self.no_header = no_header        # no ==== rule to open a header at all
        self.never_closed = never_closed  # a header with no closing rule and no IN label
        super().__init__(self.reader_summary())   # never the texts themselves

    def reader_summary(self) -> str:
        """What went wrong, for the reader and the user: label NAMES only.
        Unlabelled text is neither quoted nor counted - it can be run
        telemetry, and a stray run is recorded by its first line only, so
        any count would be wrong."""
        if self.no_header:
            return "had no ==== header"
        if self.never_closed:
            return "had a ==== header that never closed before any section"
        what = []
        if self.labels:
            what.append("used labels the notes format does not recognise ("
                        + ", ".join(self.labels) + ")")
        if self.texts:
            what.append("held text outside any section")
        return " and ".join(what)


@dataclass
class DomainNotes:
    title: str
    number: int | None
    sections: list[tuple[str, str]] = field(default_factory=list)
    withheld: UnknownLabel | None = None  # set: render names it in place of the sections


def is_comment_block(chunk: str) -> bool:
    return is_verbatim_block(chunk) and _COMMENT_RE.match(chunk) is not None


def is_research_block(chunk: str) -> bool:
    """A verbatim `@comment` block carrying a researcher's `DOMAIN:` header."""
    return is_comment_block(chunk) and _DOMAIN_LINE_RE.search(chunk) is not None


def has_in_label(chunk: str) -> bool:
    """True if `chunk` holds a line opening an IN section - analysis a
    non-research comment block would otherwise carry out of sight."""
    return any((m := _LABEL_RE.match(line)) and m.group(1) in IN_LABELS
               for line in chunk.splitlines())


def _body(chunk: str) -> str:
    opens = [i for i in (chunk.find("{"), chunk.find("(")) if i >= 0]
    start = min(opens)
    close = "}" if chunk[start] == "{" else ")"
    return chunk[start + 1: chunk.rstrip().rfind(close)]


def _is_in_label(line: str) -> bool:
    return (m := _LABEL_RE.match(line)) is not None and m.group(1) in IN_LABELS


_TITLE_WRAP_LINES = 1     # measured: real titles wrap onto one line at most; a
                          # second line is a stray, and a tag in it costs the file
_TITLE_MAX = 200


def _domain_title(lines: list[str], join: bool = True) -> str:
    """The `DOMAIN:` value, joined across the one line it may wrap onto
    (up to the next label, rule or blank line). A join past _TITLE_MAX keeps
    the first line: the title is delivered even when its block is withheld,
    so it must not swallow a stray paragraph. `join=False` gives the first
    line alone: the name of a WITHHELD block, whose wrap could be a stray
    line (run telemetry, a tag) that would otherwise ship."""
    for i, line in enumerate(lines):
        m = _LABEL_RE.match(line)
        if m and m.group(1) == "DOMAIN":
            first = m.group(2).strip()
            if not join:
                return first
            parts = [first]
            for cont in lines[i + 1: i + 1 + _TITLE_WRAP_LINES]:
                if not cont.strip() or _RULE_RE.match(cont) or _LABEL_RE.match(cont):
                    break
                parts.append(cont.strip())
            joined = " ".join(p for p in parts if p)
            return joined if len(joined) <= _TITLE_MAX else first
    return ""


def parse_block(chunk: str) -> DomainNotes:
    lines = _body(chunk).split("\n")
    start = next((i for i, line in enumerate(lines) if _RULE_RE.match(line)), None)
    # The header ends at its closing rule, or at the first IN label when the
    # researcher left that rule out (see the module docstring).
    end = None if start is None else next(
        (i for i in range(start + 1, len(lines))
         if _RULE_RE.match(lines[i]) or _is_in_label(lines[i])), None)
    if end is None:
        raise UnknownLabel(texts=["<research block without its ==== header>"],
                           title=_domain_title(lines, join=False), no_header=start is None,
                           never_closed=start is not None)
    body_start = end + 1 if _RULE_RE.match(lines[end]) else end
    unknown_labels: list[str] = []
    unknown_texts: list[str] = []
    for line in lines[:start]:
        if line.strip():
            unknown_texts.append(line.strip()[:60])   # text before the block's own header
    header = lines[start + 1: end]
    title = _domain_title(header)
    after_blank = seen_label = False
    for line in header:
        m = _LABEL_RE.match(line)
        if not m:
            # A wrapped header value - unless no label came before it to
            # wrap, or a blank line came first: no well-formed header holds
            # one (0 of 563 measured blocks), so text after it is a heading
            # or analysis the header would hide.
            if not line.strip():
                after_blank = True
            elif after_blank or not seen_label:
                unknown_texts.append(line.strip()[:60])
            continue
        after_blank, seen_label = False, True
        if m.group(1) != "DOMAIN" and m.group(1) not in OUT_LABELS:
            unknown_labels.append(m.group(1))
    num = _NUMBER_RE.match(title)
    notes = DomainNotes(title=title, number=int(num.group(1)) if num else None)

    current: str | None = None            # IN label; "" = dropped; None = no label yet
    buf: list[str] = []

    def flush():
        if current and "\n".join(buf).strip():
            notes.sections.append((current, "\n".join(buf).strip()))

    for line in lines[body_start:]:
        if _RULE_RE.match(line):
            flush()
            current, buf = None, []
            continue
        m = _LABEL_RE.match(line)
        if m:
            flush()
            label, rest = m.group(1), m.group(2).strip()
            buf = [rest] if rest else []
            if label in IN_LABELS:
                current = label
            else:
                if label not in OUT_LABELS:
                    unknown_labels.append(label)
                current = ""
            continue
        if current is None:
            if line.strip():
                unknown_texts.append(line.strip()[:60])   # a heading this grammar does not know
                current = ""
            continue
        buf.append(line)
    flush()
    if unknown_labels or unknown_texts:
        raise UnknownLabel(unknown_labels, unknown_texts, _domain_title(header, join=False))
    return notes


def parse_or_withhold(chunk: str) -> DomainNotes:
    """`parse_block`, but a block outside the grammar comes back withheld
    (no sections, `withheld` set) instead of raising, so it costs the
    reader only its own domain's notes."""
    try:
        return parse_block(chunk)
    except UnknownLabel as e:
        num = _NUMBER_RE.match(e.title)
        return DomainNotes(title=e.title, number=int(num.group(1)) if num else None, withheld=e)


def _withheld_line(e: UnknownLabel) -> str:
    return ("> Notes withheld: this domain's research block " + e.reader_summary()
            + ". Its works are in the annotated bibliography.")


def render(domains: list[DomainNotes], defs: dict[str, str], project: str) -> str:
    out = [f"# Research notes: {project}", "",
           "Per-domain analysis the domain researchers recorded while searching: "
           "the overview, the key positions, what was looked for and not found, "
           "and their guidance for the synthesis. Each work's own reading notes "
           "are in the annotated bibliography.", ""]
    if not domains:
        out.append("No per-domain research notes were recorded.")
        return "\n".join(out) + "\n"
    # Numbered headers sort by number (the glob that feeds dedupe puts
    # domain-10 before domain-2); a numberless block (a withheld one can be)
    # goes last, in the order dedupe carried it in (sorted is stable).
    ordered = sorted(domains, key=lambda d: (d.number is None, d.number or 0))
    kept = "\n".join([d.title for d in ordered]
                     + [t for d in ordered for _, t in d.sections])   # withheld: title only
    missing = [t for t in fault_lines.tags_in(kept) if t not in defs]
    if missing:
        raise fault_lines.UndefinedFaultLine(missing)
    for d in ordered:
        out += [f"## {fault_lines.substitute(d.title or 'Domain', defs)}", ""]
        if d.withheld is not None:
            out += [_withheld_line(d.withheld), ""]
        for label, text in d.sections:
            out += [f"### {_heading(label)}", "", fault_lines.substitute(text, defs), ""]
    return "\n".join(out).rstrip() + "\n"
