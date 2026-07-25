"""Evidence-tier computation and stamping for BibTeX entries.

Implements the tier rule from the evidence-tier citability design (spec
v5.1): a tier is granted only under report/ledger attestation -- field
presence is never sufficient by itself. Every failure path demotes, never
promotes (fail-closed: an entry with no EVIDENCE-* token reads as
EVIDENCE-NONE downstream).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

TIER_ABSTRACT = "EVIDENCE-ABSTRACT"
TIER_CONTEXT = "EVIDENCE-CONTEXT"
TIER_EXISTENCE = "EVIDENCE-EXISTENCE"
TIER_NONE = "EVIDENCE-NONE"
TIER_RANK = {TIER_ABSTRACT: 3, TIER_CONTEXT: 2, TIER_EXISTENCE: 1, TIER_NONE: 0}

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


def normalize_doi(value: str) -> str:
    v = (value or "").strip().lower()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", v)


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
