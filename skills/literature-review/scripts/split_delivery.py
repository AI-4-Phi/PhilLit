#!/usr/bin/env python3
"""Split the merged bibliography into the three Phase 6 deliverables, one
purpose each (docs/ROADMAP.md, delivery item):

- `literature-<project>.bib` - the TRACK RECORD: every verdict an agent
  reached (EVIDENCE-* tier, High/Medium/Low, FLn.n tags, workflow and
  METADATA_CLEANED markers, the engine-derived fields). No notes, no
  `@comment`.
- `literature-<project>-annotated.bib` - the REFERENCE-MANAGER IMPORT
  (Zotero, BibDesk, ...): standard fields, topical keywords and the reading
  notes with FLn.n substituted. Zotero turns `note` into a child note and
  every keyword into a tag, so every verdict token is stripped here, and so
  are the eight engine-derived fields the spec names.
- `research-notes-<project>.md` - the per-domain research blocks, for a
  human reader (research_notes.py).

Runs after generate_bibliography and check_evidence, which read year_suffix
and the tiers from the merged bib.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pybtex.database import parse_string

_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_comments import is_verbatim_block  # noqa: E402
from cleaning_marker import MARKER_STRIP_RE  # noqa: E402

sys.path.pop(0)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bib_fields  # noqa: E402
import fault_lines  # noqa: E402
import research_notes  # noqa: E402
import stamp_evidence as se  # noqa: E402

sys.path.pop(0)

# The eight engine-derived fields the annotated bib strips - exactly the
# spec's list (decided 2026-09-24): `urldate` included, `iep_context` not.
ENGINE_FIELDS = frozenset({
    "abstract_source", "web_span", "urldate", "archiveurl", "same_work_group",
    "venue_status", "sep_context", "year_suffix"})
# Workflow markers, stripped BY NAME: ALL-CAPS topical keywords (XCONST,
# POLCON, CHECKS, ...) share their shape and must survive. Add new markers here.
WORKFLOW_MARKERS = frozenset({"AI-RELEVANT", "ROUTING-DISPUTE", "NO-DOI"})


def _split_keywords(value: str) -> tuple[list[str], str]:
    """(tokens, marker). The METADATA_CLEANED marker is always last
    (docs/conventions.md, canonical keyword order) and its argument may hold
    commas, so it is cut off whole before the rest is split."""
    m = MARKER_STRIP_RE.search(value)
    marker = value[m.start():].lstrip(", \t\r\n") if m else ""
    body = value[:m.start()] if m else value
    return [t.strip() for t in body.split(",") if t.strip()], marker


def track_keywords(value: str) -> str:
    """Every verdict kept; only the Phase-3 tokens (INCOMPLETE, no-abstract)
    go, as they leave the delivered bib today."""
    tokens, marker = _split_keywords(value)
    kept = [t for t in tokens if t not in se.DROP_TOKENS]
    return ", ".join(kept + ([marker] if marker else []))


def _is_verdict(tok: str) -> bool:
    return (tok in se.IMPORTANCE_TOKENS or tok in se.DROP_TOKENS
            or tok in WORKFLOW_MARKERS or se._EVIDENCE_TOKEN_RE.match(tok) is not None
            or fault_lines.TAG_RE.fullmatch(tok) is not None)


def annotated_keywords(value: str) -> str:
    """The topical keywords only."""
    tokens, _ = _split_keywords(value)
    return ", ".join(t for t in tokens if not _is_verdict(t))


def _rewrite(chunk: str, edit) -> str:
    """Apply `edit(field)` to every field, last first so earlier offsets stay
    valid: None removes the field, `...` keeps it, a string replaces the
    value (delimiters included)."""
    for f in reversed(list(bib_fields.iter_fields(chunk))):
        new = edit(f)
        if new is None:
            chunk = bib_fields.remove_field(chunk, f)
        elif new is not ...:
            chunk = chunk[:f.value_start] + new + chunk[f.value_end:]
    return chunk


def track_record_entry(chunk: str) -> str:
    def edit(f):
        name = f.name.lower()
        if name == "note":
            return None
        if name == "keywords":
            kw = track_keywords(f.value)
            return "{" + kw + "}" if kw else None
        return ...
    return _rewrite(chunk, edit)


def annotated_entry(chunk: str, defs: dict[str, str]) -> str:
    undefined = set()
    for f in bib_fields.iter_fields(chunk):
        name = f.name.lower()
        if name == "note":
            undefined.update(t for t in fault_lines.tags_in(f.value) if t not in defs)
        elif name == "keywords":
            undefined.update(t for t in _split_keywords(f.value)[0]
                             if fault_lines.TAG_RE.fullmatch(t) and t not in defs)
    if undefined:
        raise fault_lines.UndefinedFaultLine(undefined)

    def edit(f):
        name = f.name.lower()
        if name == "note":
            return "{" + fault_lines.substitute(f.value, defs) + "}"
        if name == "keywords":
            kw = annotated_keywords(f.value)
            return "{" + kw + "}" if kw else None
        if name in ENGINE_FIELDS:
            return None
        return ...
    return _rewrite(chunk, edit)
