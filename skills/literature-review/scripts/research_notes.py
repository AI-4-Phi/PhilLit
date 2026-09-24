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
Grow IN_LABELS or OUT_LABELS to admit a new label; never guess. The header
block admits only `DOMAIN` and OUT labels: an IN label there is unknown, not
a section. This is a LABEL list, never a sentence-level edit: run-mechanics
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

    def __init__(self, labels=(), texts=()):
        self.labels = sorted(set(labels))
        self.texts = sorted(set(texts))
        parts = []
        if self.labels:
            parts.append("unrecognised label(s): " + ", ".join(self.labels))
        if self.texts:
            parts.append("unlabelled text: " + ", ".join(self.texts))
        super().__init__("; ".join(parts))


@dataclass
class DomainNotes:
    title: str
    number: int | None
    sections: list[tuple[str, str]] = field(default_factory=list)


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


def parse_block(chunk: str) -> DomainNotes:
    lines = _body(chunk).split("\n")
    rules = [i for i, line in enumerate(lines) if _RULE_RE.match(line)]
    if len(rules) < 2:
        raise UnknownLabel(texts=["<research block without its ==== header>"])
    unknown_labels: list[str] = []
    unknown_texts: list[str] = []
    for line in lines[:rules[0]]:
        if line.strip():
            unknown_texts.append(line.strip()[:60])   # text before the block's own header
    title = ""
    for line in lines[rules[0] + 1: rules[1]]:
        m = _LABEL_RE.match(line)
        if not m:
            continue                      # a wrapped header value
        if m.group(1) == "DOMAIN":
            title = m.group(2).strip()
        elif m.group(1) not in OUT_LABELS:
            unknown_labels.append(m.group(1))
    num = _NUMBER_RE.match(title)
    notes = DomainNotes(title=title, number=int(num.group(1)) if num else None)

    current: str | None = None            # IN label; "" = dropped; None = no label yet
    buf: list[str] = []

    def flush():
        if current and "\n".join(buf).strip():
            notes.sections.append((current, "\n".join(buf).strip()))

    for line in lines[rules[1] + 1:]:
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
        raise UnknownLabel(unknown_labels, unknown_texts)
    return notes


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
    # domain-10 before domain-2); otherwise the order dedupe carried them in.
    ordered = (sorted(domains, key=lambda d: d.number)
               if all(d.number is not None for d in domains) else list(domains))
    kept = "\n".join([d.title for d in ordered]
                     + [t for d in ordered for _, t in d.sections])
    missing = [t for t in fault_lines.tags_in(kept) if t not in defs]
    if missing:
        raise fault_lines.UndefinedFaultLine(missing)
    for d in ordered:
        out += [f"## {fault_lines.substitute(d.title or 'Domain', defs)}", ""]
        for label, text in d.sections:
            out += [f"### {_heading(label)}", "", fault_lines.substitute(text, defs), ""]
    return "\n".join(out).rstrip() + "\n"
