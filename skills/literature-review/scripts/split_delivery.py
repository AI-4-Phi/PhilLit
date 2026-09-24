#!/usr/bin/env python3
"""Split the merged bibliography into the three Phase 6 deliverables, one
purpose each:

- `literature-<project>.bib` - the TRACK RECORD: every verdict an agent
  reached (EVIDENCE-* tier, High/Medium/Low, FLn.n tags, workflow and
  METADATA_CLEANED markers, the engine-derived fields). No notes, no
  `@comment`.
- `literature-<project>-annotated.bib` - the REFERENCE-MANAGER IMPORT
  (Zotero, BibDesk, ...): standard fields, topical keywords and the reading
  notes with FLn.n substituted. Zotero turns `note` into a child note and
  every keyword into a tag, so every verdict token is stripped here, and so
  are exactly these eight engine-derived fields (ENGINE_FIELDS below;
  `urldate` is included, `iep_context` is not). No `@comment` here either.
- `research-notes-<project>.md` - the per-domain research blocks, for a
  human reader (research_notes.py).

DECIDED, do not reopen: every workflow and METADATA_CLEANED marker is
stripped BY NAME from the annotated bib (WORKFLOW_MARKERS, cleaning_marker),
never by shape, since an ALL-CAPS topical keyword (XCONST, POLCON, ...)
shares that shape; the track record keeps them all. Each output is computed
whole in memory; the track record is always written unless it fails to
parse; the annotated bib is withheld when a note or keyword carries an
undefined fault-line tag; the notes file is withheld on an unrecognised
label, unlabelled text, or an undefined tag in its text; a file this run
does not write is deleted if an older copy exists. Before the track record
overwrites the merged bib (its only input), the merged bib is saved to
`intermediate_files/literature-<project>-merged.bib`.

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

# The eight engine-derived fields the annotated bib strips (decided):
# `urldate` included, `iep_context` not.
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


class AlreadySplit(ValueError):
    pass


def _outputs(bib_path: Path) -> tuple[Path, Path, Path, str]:
    stem = bib_path.stem                      # literature-<project>
    project = stem[len("literature-"):] if stem.startswith("literature-") else stem
    return (bib_path.with_name(f"{stem}-annotated.bib"),
            bib_path.with_name(f"research-notes-{project}.md"),
            bib_path.parent / "intermediate_files" / f"{stem}-merged.bib", project)


def _parse_error(text: str) -> str | None:
    try:
        parse_string(text, "bibtex")
    except Exception as e:                     # pybtex raises several types
        return f"{type(e).__name__}: {e}"
    return None


def _write(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(str(tmp), str(path))
    except Exception:
        tmp.unlink(missing_ok=True)            # never leave a `.tmp` behind
        raise


def split(bib_path: Path, plan_path: Path | None) -> dict:
    annotated_path, notes_path, backup_path, project = _outputs(bib_path)
    text = bib_path.read_text(encoding="utf-8")
    defs = (fault_lines.parse_definitions(plan_path.read_text(encoding="utf-8"))
            if plan_path is not None else {})

    errors: list[str] = []
    notices: list[str] = []
    track, annotated, research, entries = [], [], [], 0
    undefined: set[str] = set()
    for chunk in se.split_entries(text):
        if not chunk.strip():
            continue
        if research_notes.is_research_block(chunk):
            research.append(chunk)
        elif research_notes.is_comment_block(chunk):
            if research_notes.has_in_label(chunk):
                notices.append("dropped a comment block without a DOMAIN: header "
                               "that holds research-notes sections: "
                               + " ".join(chunk.split())[:80])
        elif is_verbatim_block(chunk):                 # @string / @preamble
            track.append(chunk)
            annotated.append(chunk)
        elif se.entry_header(chunk) is None:
            track.append(chunk)                # stray text: pass through, uncounted
            annotated.append(chunk)
        else:
            entries += 1
            track.append(track_record_entry(chunk))
            try:
                annotated.append(annotated_entry(chunk, defs))
            except fault_lines.UndefinedFaultLine as e:
                undefined.update(e.tags)

    has_notes = any(f.name.lower() == "note" for f in bib_fields.iter_fields(text))
    if not research and not has_notes and (
            annotated_path.exists() or notes_path.exists() or backup_path.exists()):
        raise AlreadySplit(
            f"{bib_path.name} has no notes and no research blocks, and "
            f"{annotated_path.name} or {notes_path.name} or {backup_path.name} exists: "
            "it was already split. Restore intermediate_files/"
            f"{backup_path.name} over it, or re-run step 3 (dedupe), then split again")

    track_text = "\n".join(track)
    annotated_text = None if undefined else "\n".join(annotated)
    annotated_error = None
    if undefined:
        annotated_error = (f"{annotated_path.name} not written: "
                           + str(fault_lines.UndefinedFaultLine(undefined)))
    bad = _parse_error(track_text)
    if bad:
        errors.append(f"{bib_path.name} left as merged: the track record does not parse ({bad})")
        track_text = None
        if annotated_text is not None:
            annotated_error = f"{annotated_path.name} not written: the track record failed"
            annotated_text = None
    elif annotated_text is not None:
        bad = _parse_error(annotated_text)
        if bad:
            annotated_error = f"{annotated_path.name} not written: it does not parse ({bad})"
            annotated_text = None
    if annotated_error is not None:
        # The track record still overwrites the only input, so a withheld
        # annotated bib's notes are gone unless the backup (written below)
        # survives it -- named here so an operator without SPLIT-NOTICE
        # savvy still knows where to look.
        if track_text is not None:
            annotated_error += ("; the merged bib (with its notes) is kept at "
                                f"intermediate_files/{backup_path.name} -- restore it "
                                "before splitting again")
        errors.append(annotated_error)

    notes_md = None
    domains, unknown_labels, unknown_texts = [], set(), set()
    for chunk in research:
        try:
            domains.append(research_notes.parse_block(chunk))
        except research_notes.UnknownLabel as e:
            unknown_labels.update(e.labels)
            unknown_texts.update(e.texts)
    # The backup is written below whenever track_text is not None -- named
    # here too (mirroring the annotated-withheld addendum) so an operator
    # knows the research blocks survive even when the notes file does not.
    kept_at = (f"; the research blocks are kept in intermediate_files/{backup_path.name}"
              if track_text is not None else "")
    if unknown_labels or unknown_texts:
        raw_undefined = [t for t in fault_lines.tags_in("\n".join(research)) if t not in defs]
        msg = (f"{notes_path.name} not written: "
              + str(research_notes.UnknownLabel(unknown_labels, unknown_texts)))
        if raw_undefined:
            msg += "; " + str(fault_lines.UndefinedFaultLine(raw_undefined))
        errors.append(msg + kept_at)
    else:
        try:
            notes_md = research_notes.render(domains, defs, project)
        except fault_lines.UndefinedFaultLine as e:
            errors.append(f"{notes_path.name} not written: {e}" + kept_at)

    # The merged bib -- notes, comment blocks and all -- is backed up to
    # intermediate_files/ BEFORE anything else is written, whenever the track
    # record is about to overwrite it: that overwrite is the only place the
    # note/comment content can be lost, so the backup must exist before it
    # happens, not after. Skipped when the track record itself does not
    # parse, since then bib_path is never touched and nothing needs saving.
    written = []
    backup_name = None
    if track_text is not None:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        _write(backup_path, text)
        backup_name = backup_path.name
    # The track record overwrites the merged bib, the only input, so it is
    # written LAST: an interruption before it leaves the notes and research
    # blocks in place, and a plain re-run recovers.
    for path, content in ((annotated_path, annotated_text), (notes_path, notes_md)):
        if content is None:
            path.unlink(missing_ok=True)       # never leave a stale copy
        else:
            _write(path, content)
            written.append(path.name)
    if track_text is not None:
        _write(bib_path, track_text)
        written.insert(0, bib_path.name)
    return {"written": written, "errors": errors, "notices": notices,
            "entries": entries, "research_blocks": len(research),
            "domains": len(domains), "backup": backup_name}


def _say(line: str) -> None:
    """stdout, ASCII only: a cp1252 console must not turn a report into a traceback."""
    print(line.encode("ascii", "backslashreplace").decode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("bib", type=Path, help="the merged literature-<project>.bib")
    parser.add_argument("--plan", type=Path, default=None,
                        help="lit-review-plan.md, for FLn.n definitions")
    args = parser.parse_args()
    if not args.bib.is_file():
        _say(f"SPLIT-ERROR: not a file: {args.bib}")
        return 1
    if args.plan is not None and not args.plan.is_file():
        # After step 8 the plan lives in intermediate_files/ (resume path).
        moved = args.bib.parent / "intermediate_files" / args.plan.name
        if not moved.is_file():
            _say(f"SPLIT-ERROR: --plan names no file: {args.plan} (nor {moved})")
            return 1
        args.plan = moved
    try:
        summary = split(args.bib, args.plan)
    except AlreadySplit as e:
        _say(f"SPLIT-ERROR: {e}")
        return 2
    except (UnicodeDecodeError, OSError) as e:
        _say(f"SPLIT-ERROR: cannot read or write the delivery files ({type(e).__name__}: {e})")
        return 1
    for err in summary["errors"]:
        _say(f"SPLIT-ERROR: {err}")
    for note in summary["notices"]:
        _say(f"SPLIT-NOTICE: {note}")
    _say(json.dumps(summary, ensure_ascii=True))
    return 2 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
