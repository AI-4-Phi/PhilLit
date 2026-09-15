"""The one owner of the ledger-to-bib CONTENT binding (`bib_sha256`).

The evidence barrier binds an attestation ledger to its bib by NAME. A pass
that refuses therefore has to delete the stale ledger, and that unlink is
best-effort -- if the OS refuses, the old ledger stays and attests a bib that
has since changed. Schema 3 closes that by carrying a hash of the bib the
ledger actually describes, so a survivor is unusable however it survived.

Both sides of the binding live here because a drift between them rejects
every ledger silently: `metadata_cleaner.write_cleaning_ledger` stamps the
value, `evidence_barrier._load_ledger` checks it, and neither may compute it
its own way. Sites bind these as ALIASES, never a local copy.

THE HASH COVERS DECODED TEXT, NOT BYTES. The cleaner writes its rewrite in
text mode, so the same logical bib is CRLF on Windows and LF elsewhere;
hashing bytes would make a ledger validate only on the platform that wrote
it. `Path.read_text` reads in universal-newlines mode, which folds CRLF and
CR to LF, so hashing its result is platform-stable by construction.

A leaf module (`hashlib` only, no project imports) for the same reason
`cleaning_marker.py` is one: the barrier must read the binding, and pulling
in the cleaner to get at it would drag pybtex and the whole cleaning stack
behind it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# The schema version at which a cleaning ledger carries `bib_sha256`.
#
# For the CLEANING ledger this is a floor: the barrier refuses anything below
# it, so there is no version a ledger can declare to opt out of the binding.
# For the ENRICHMENT ledger it is nothing at all -- that ledger is written
# before the cleaner rewrites the bib, so it could never satisfy a binding,
# and the barrier scopes the whole rule to `kind == "cleaning"` precisely so
# that bumping the enrichment schema cannot silently opt it in.
#
# A further bump must land in the producer AND in the barrier's accepted set,
# or every cleaning ledger is refused.
BINDING_SCHEMA_VERSION = 3


def bib_text_sha256(text: str) -> str:
    """The binding value for an already-decoded bib text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bib_file_sha256(path) -> str | None:
    """The binding value for a bib on disk, or None if it cannot be read.

    None means "no opinion" to the caller, which must then reject rather than
    accept: an unreadable bib cannot corroborate anything.
    """
    try:
        return bib_text_sha256(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def binding_holds(declared, bib_path) -> bool:
    """True iff `declared` is the digest of the bib at `bib_path`.

    False on every failure -- an ill-typed or absent `declared`, an
    unreadable bib, a genuine mismatch -- because each must land on the safe
    side, which is to distrust the ledger.

    No separate shape check on `declared`, deliberately: WHEN `actual` IS A
    DIGEST it is lowercase hex, so `actual == declared` is true only for a
    value that already has the right shape -- `True`, an uppercase digest and
    a truncated one all fail that compare unaided. A guard in front of it was
    removed after no mutation could distinguish it.

    `actual is not None` is the load-bearing half and is NOT redundant with
    it. `None == None` is true, and the pair is reachable: the cleaner writes
    a null `bib_sha256` when it cannot read the bib back, and the bib can be
    unreadable at check time too. Without that clause a binding between two
    absent digests reads as held -- fail-open, on an accuracy gate. Pinned by
    test_false_when_neither_side_has_a_digest.
    """
    actual = bib_file_sha256(bib_path)
    return actual is not None and actual == declared
