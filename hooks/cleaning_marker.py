#!/usr/bin/env python3
"""The one owner of the METADATA_CLEANED marker GRAMMAR.

This module owns how a marker is FOUND in a `keywords` value and how its
change list is READ BACK. It does not own the marker's FORMAT: the cleaner
writes that, in `metadata_cleaner._apply_cleaned_marker`.

It exists as its own leaf module - importing `re` and nothing else - because
`bib_validator` must read markers (an @article the cleaner deliberately left
without a `journal` is exempt from the required-field check), and
`bib_identity` already imports `bib_validator` while `metadata_cleaner`
imports `bib_identity`. Reading the grammar out of the cleaner from the
validator would therefore close an import cycle.

Consumers bind these objects as ALIASES, never copies (tests assert `is`
identity): `metadata_cleaner`, `bib_validator`, `dedupe_bib.py` and
`generate_bibliography.py`.
"""

import re

# A6: strip any existing METADATA_CLEANED marker before writing a fresh one.
# pybtex round-trips the underscore as \_ (and \\_ on a second pass), so match
# METADATA + any run of backslashes + _CLEANED. All markers are appended at the
# keywords tail, so removing from the first marker to end drops them all.
MARKER_STRIP_RE = re.compile(r",?\s*METADATA\\*_CLEANED:.*$", re.DOTALL)

# The marker's removed-field grammar, shared with dedupe_bib.py and
# generate_bibliography.py. metadata_cleaner owns the marker
# format (_apply_cleaned_marker writes it); parse it here, in one place.
MARKER_BODY_RE = re.compile(r"METADATA\\*_CLEANED:\s*(.*)$", re.DOTALL)


def has_marker(keywords: str) -> bool:
    """Does this keywords value carry a METADATA_CLEANED marker?

    Tolerant of pybtex's escaped spellings (METADATA\\_CLEANED,
    METADATA\\\\_CLEANED) exactly as MARKER_BODY_RE is - it IS MARKER_BODY_RE.
    Empty/None -> False.
    """
    if not keywords:
        return False
    return bool(MARKER_BODY_RE.search(keywords))


def marker_tokens(keywords: str) -> list[str]:
    """The marker's change list, split into stripped non-empty tokens.

    A token either NAMES a removed field (`journal`) or RECORDS a change
    (`year:2007->2019`, `type:@article->@misc`); change tokens are the ones
    containing ':'. Returned in marker order so a caller can carry one
    forward verbatim. No marker -> [].
    """
    if not keywords:
        return []
    m = MARKER_BODY_RE.search(keywords)
    if not m:
        return []
    return [token.strip() for token in m.group(1).split(",") if token.strip()]


def marker_removed_fields(keywords: str) -> frozenset[str]:
    """Lowercase field names a METADATA_CLEANED marker records as REMOVED.

    Change tokens (`year:2007->2019`, `type:@a->@b`) contain ':' and are not
    removals. Tolerates pybtex's backslash-escaped form (METADATA\\_CLEANED)
    - the Writer escapes '_' on round-trip. Empty/absent marker -> empty set.
    """
    return frozenset(token.lower() for token in marker_tokens(keywords)
                     if ":" not in token)


def marker_type_token(keywords: str) -> str | None:
    """The marker's FIRST `type:` change token verbatim, or None.

    Verbatim because the cleaner carries a prior demotion forward into the
    marker it rewrites, and the token's VALUE (`type:@article->@misc`) is the
    record - re-deriving it would need the pre-cleaning entry type, which a
    later run no longer has.

    FIRST, not "the": the writer emits at most one `type:` token per run, and
    carry-forward (see metadata_cleaner._apply_cleaned_marker) keeps at most
    one as well, so two should never legitimately coexist in a marker this
    module ever wrote.
    """
    for token in marker_tokens(keywords):
        if token.lower().startswith("type:"):
            return token
    return None


def marker_type_changed(keywords: str) -> bool:
    """Does the marker record a type change (the cleaner demoted this entry)?"""
    return marker_type_token(keywords) is not None


def marker_type_target(keywords: str) -> str | None:
    """Lowercase entry type the marker's `type:` token demoted THIS ENTRY TO
    (`type:@article->@misc` -> `misc`), or None when there is no such token.

    `metadata_cleaner._apply_cleaned_marker` carries a prior `type:` token
    forward only when this equals the entry's CURRENT type: the token
    records what the cleaner demoted the entry to on an earlier run, and once
    a researcher edits the type back, the token's target no longer describes
    this entry - carrying it forward would block the very correction the
    researcher made.
    """
    token = marker_type_token(keywords)
    if token is None or "->" not in token:
        return None
    target = token.rsplit("->", 1)[1].strip().lstrip("@")
    return target.lower() or None
