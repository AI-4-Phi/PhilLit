"""Strip engine-internal evidence-tier tokens from a delivered .bib file.

Removes every EVIDENCE-* token (any case) from `keywords` fields -- these are
PhilLit-internal telemetry and must not leak into a bibliography handed to
the user. As a side effect of stamp_entry_text(tier=None), any leftover
INCOMPLETE/no-abstract tokens are also dropped (post-barrier these should not
exist, but the delivered file must not carry them either). Only `keywords`
values are sanitized -- an EVIDENCE- string pasted into another field (e.g.
`note`) is out of scope.

The engine-derived FIELDS (`web_span`, `venue_status`, `year_suffix`,
`urldate`, `archiveurl`, `same_work_group`, plus `abstract_source` and
`sep_context`) are deliberately NOT stripped here: the delivered bib keeps
them for audit transparency, and standard BibTeX/biblatex styles ignore
unknown fields, so they are inert downstream. The planned three-file
delivery (the delivery item in `docs/ROADMAP.md`) keeps all eight -- and the
EVIDENCE-* tiers -- in the track-record bib and strips them from the
annotated bib that goes to Zotero.

Do not add field stripping here without a new owner decision.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import stamp_evidence as se


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: sanitize_bib.py <file.bib>")
        return 1
    path = Path(sys.argv[1])
    chunks = se.split_entries(path.read_text(encoding="utf-8"))
    stripped = 0
    out = []
    for chunk in chunks:
        if se.entry_header(chunk) and "EVIDENCE-" in chunk.upper():
            new_chunk = se.stamp_entry_text(chunk, None)  # tier=None strips tokens
            if new_chunk != chunk:
                stripped += 1
            chunk = new_chunk
        out.append(chunk)
    tmp = path.with_suffix(".bib.tmp")
    tmp.write_text("\n".join(out), encoding="utf-8")
    os.replace(str(tmp), str(path))
    print(json.dumps({"stripped": stripped}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
