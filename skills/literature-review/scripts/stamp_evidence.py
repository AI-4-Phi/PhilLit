"""Evidence-tier computation and stamping for BibTeX entries.

Implements the tier rule from the evidence-tier citability design: a tier is
granted only under report/ledger attestation -- field presence is never
sufficient by itself. Every failure path demotes, never
promotes (fail-closed: an entry with no EVIDENCE-* token reads as
EVIDENCE-NONE downstream).
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Import DOI normalization from bib_identity (single source of truth)
_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_identity import normalize_doi  # noqa: E402,F401 - re-exported for callers

sys.path.pop(0)

# Sibling module, imported through an explicit path insert (the same idiom as
# bib_identity above) so this file also works when a caller loads it by file
# path without putting the scripts directory on sys.path itself.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bib_fields  # noqa: E402

sys.path.pop(0)

TIER_ABSTRACT = "EVIDENCE-ABSTRACT"
TIER_CONTEXT = "EVIDENCE-CONTEXT"
TIER_WEB = "EVIDENCE-WEB"
TIER_EXISTENCE = "EVIDENCE-EXISTENCE"
TIER_NONE = "EVIDENCE-NONE"
# Only the ORDER is meaningful -- every comparison is relative and no absolute
# rank is persisted anywhere, which is what let WEB be inserted mid-ladder.
TIER_RANK = {TIER_ABSTRACT: 4, TIER_CONTEXT: 3, TIER_WEB: 2,
             TIER_EXISTENCE: 1, TIER_NONE: 0}

ATTESTED_ABSTRACT_SOURCES = {"s2", "openalex", "core", "ndpr"}
CONTAINER_TYPES = {"book", "incollection", "inbook"}


@dataclass
class EntryAttestation:
    """What the ledgers and the barrier report attest for one entry."""
    abstract_attested: bool = False
    context_written: bool = False
    api_matched: bool = False
    verified_identifier: str | None = None  # "doi" | "publisher" | None
    verified_identifier_value: str | None = None  # normalized confirmed value
    breaker_tripped: bool = False
    # Cleaning abstention: set when the cleaner matched the DOI
    # but declined to clean over contradictory year evidence. Informational
    # only - compute_tier ignores it (existence is attested via api_matched +
    # the value binding); it exists so the refusal stays visible downstream.
    cleaning_abstained: str | None = None
    # EVIDENCE-WEB: set by the barrier when rule (a) existence AND all of rule
    # (b)'s capture checks held for this entry THIS run. Never inferred from
    # field presence -- like every other tier, the attestation comes from
    # outside the bib, not from the bib.
    web_gate_passed: bool = False


def normalize_publisher(value: str) -> str:
    return (value or "").lower().strip()


def normalize_abstract_for_hash(text: str) -> str:
    """Whitespace- and escape-insensitive form (pybtex round-trip safe).

    Tamper evidence against careless mutation, NOT cryptography: the
    backslash-strip admits collisions between texts differing only in
    backslashes, which is not a meaningful attack surface here because
    unattested paths already fail closed.
    """
    return re.sub(r"\s+", " ", text.replace("\\", "")).strip()


def abstract_hash(text: str) -> str:
    return hashlib.sha256(
        normalize_abstract_for_hash(text).encode("utf-8")
    ).hexdigest()


def attest_abstract(fields: dict, ledger_entry: dict | None) -> bool:
    """Does the enrichment ledger attest this entry's current abstract?"""
    if not ledger_entry:
        return False
    source = (fields.get("abstract_source") or "").strip().lower()
    ledger_source = (ledger_entry.get("abstract_source") or "").strip().lower()
    abstract = fields.get("abstract") or ""
    return (
        bool(abstract)
        and bool(ledger_source)
        and source == ledger_source
        and abstract_hash(abstract) == ledger_entry.get("abstract_sha256")
    )


def compute_tier(entry_type: str, fields: dict, att: EntryAttestation) -> str:
    source = (fields.get("abstract_source") or "").strip().lower()
    if (
        fields.get("abstract")
        and source in ATTESTED_ABSTRACT_SOURCES
        and att.abstract_attested
    ):
        return TIER_ABSTRACT
    if (fields.get("sep_context") or fields.get("iep_context")) and att.context_written:
        return TIER_CONTEXT
    # Above EXISTENCE: the web gate proves a fetch of this entry's own URL
    # produced real, title-matching, span-bearing content, which is strictly
    # more than "some API confirmed this identifier exists".
    if att.web_gate_passed:
        return TIER_WEB
    if att.api_matched and not att.breaker_tripped and att.verified_identifier_value:
        # Value binding: the CURRENT field value must equal the value the
        # cleaner verified -- presence of the right kind is not enough.
        if att.verified_identifier == "doi" and fields.get("doi") and (
            normalize_doi(fields["doi"]) == att.verified_identifier_value
        ):
            return TIER_EXISTENCE
        if (
            att.verified_identifier == "publisher"
            and entry_type.lower() in CONTAINER_TYPES
            and fields.get("publisher")
            and normalize_publisher(fields["publisher"]) == att.verified_identifier_value
        ):
            return TIER_EXISTENCE
    return TIER_NONE


import os
from pathlib import Path

IMPORTANCE_TOKENS = {"High", "Medium", "Low"}
DROP_TOKENS = {"INCOMPLETE", "no-abstract"}

# Same footgun handling as hooks/metadata_cleaner.py:_MARKER_RE -- pybtex
# escapes the underscore on round-trip, so match any run of backslashes.
_MARKER_RE = re.compile(r",?\s*(METADATA\\*_CLEANED:.*)$", re.DOTALL)
# Strip ANY evidence-shaped token (unknown/mixed-case included); only the
# four canonical uppercase tiers are ever emitted.
_EVIDENCE_TOKEN_RE = re.compile(r"^EVIDENCE-[A-Za-z0-9_-]+$", re.IGNORECASE)
_HEADER_RE = re.compile(r"@(\w+)\s*\{([^,\s]+)\s*,")


def stamp_keywords(keywords_value: str | None, tier: str | None) -> str:
    body = keywords_value or ""
    marker = ""
    m = _MARKER_RE.search(body)
    if m:
        marker = m.group(1).strip()
        body = body[: m.start()]
    tokens = [t.strip() for t in re.split(r"\s*,\s*", body) if t.strip()]
    topics = [
        t for t in tokens
        if t not in IMPORTANCE_TOKENS and t not in DROP_TOKENS
        and not _EVIDENCE_TOKEN_RE.match(t)
    ]
    importance = [t for t in tokens if t in IMPORTANCE_TOKENS][:1]
    parts = topics + importance + ([tier] if tier else [])
    if marker:
        parts.append(marker)
    return ", ".join(parts)


# Historic name kept as an alias to the shared scanner (repo convention:
# sites keep their names as aliases to the shared object; tests assert `is`).
# Was a one-level-nesting regex here; see bib_fields for what that dropped.
parse_entry_fields = bib_fields.parse_entry_fields


def split_entries(content: str) -> list[str]:
    return re.split(r"\n(?=@)", content)


def entry_header(entry_text: str) -> tuple[str, str] | None:
    m = _HEADER_RE.match(entry_text.strip())
    if not m or m.group(1).lower() == "comment":
        return None
    return m.group(1), m.group(2)


def stamp_entry_text(entry_text: str, tier: str | None) -> str:
    # The keywords value is located by the SAME scanner parse_entry_fields
    # uses, so the two can never disagree about whether the field exists:
    # a value the parse saw but the stamp missed would be re-inserted as a
    # second `keywords =`, a duplicate field pybtex rejects. Braced or quoted
    # (a forging agent may use quotes), nested to any depth; the replacement
    # is always braced and canonical.
    # FIRST keywords field, as the regex's .search() was; parse_entry_fields
    # keeps the LAST. Two such fields never coexist in text that shipped
    # (pybtex rejects the duplicate), so the two only differ on text that
    # the write hook already refused.
    kw = next((f for f in bib_fields.iter_fields(entry_text)
               if f.name.lower() == "keywords"), None)
    if kw is not None:
        new_val = stamp_keywords(kw.value, tier)
        return (entry_text[: kw.value_start] + "{" + new_val + "}"
                + entry_text[kw.value_end:])
    if tier is None:
        return entry_text
    # Insert after the opening "@type{key," line (same insertion point
    # rationale as enrich_bibliography.add_field_to_entry).
    lines = entry_text.split("\n")
    for i, line in enumerate(lines):
        if _HEADER_RE.match(line.strip()):
            lines.insert(i + 1, f"  keywords = {{{tier}}},")
            return "\n".join(lines)
    return entry_text


def stamp_file(bib_path: Path, attestations: dict) -> dict:
    content = bib_path.read_text(encoding="utf-8")
    chunks = split_entries(content)
    stamps: dict = {}
    out = []
    for chunk in chunks:
        header = entry_header(chunk)
        if header is None:
            out.append(chunk)
            continue
        etype, key = header
        att = attestations.get(key) or EntryAttestation()
        tier = compute_tier(etype, parse_entry_fields(chunk), att)
        out.append(stamp_entry_text(chunk, tier))
        stamps[key] = tier
    tmp = bib_path.with_suffix(".bib.tmp")
    tmp.write_text("\n".join(out), encoding="utf-8")
    os.replace(str(tmp), str(bib_path))
    return stamps
