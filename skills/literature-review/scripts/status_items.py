"""The `status_notice` value grammar: the one owner, as a leaf module.

`status_notice = {<item>; <item>; ...}`, each item `<category> <notice-doi>`
or the bare `preprint`, ordered by CATEGORY_ORDER then notice DOI. The
barrier's lookup (`status_notice.py`) writes values with `format_items`;
Phase 6 telemetry (`check_evidence.py`) reads them with `categories` and
`parse_items`. Standard library only, so a reader never pulls in the
network stack. Consumers bind these names as aliases, never copies.
"""
from __future__ import annotations

PREPRINT = "preprint"
CATEGORY_ORDER = ("retraction", "partial_retraction", "withdrawal",
                  "expression_of_concern", "correction", PREPRINT)


def parse_items(value) -> list[tuple[str, str | None]]:
    """(category, notice DOI or None) per `; `-separated item, in order."""
    out = []
    for part in (value or "").split(";"):
        words = part.split()
        if not words:
            continue
        out.append((words[0], words[1] if len(words) > 1 else None))
    return out


def categories(value) -> set[str]:
    return {cat for cat, _doi in parse_items(value)}


def format_items(items) -> str:
    rank = {c: n for n, c in enumerate(CATEGORY_ORDER)}
    ordered = sorted(set(items), key=lambda it: (rank[it[0]], it[1] or ""))
    return "; ".join(cat if doi is None else f"{cat} {doi}" for cat, doi in ordered)
