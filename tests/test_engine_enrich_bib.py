"""
Item 13 D2: add_field_to_entry must not splice a second field inside a
just-inserted multi-line abstract.
"""

import re
import sys
from pathlib import Path

from pybtex.database import parse_string

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"))

import enrich_bibliography as mod


def _decl_depth(text, field_name):
    """Brace depth at which `field_name = ` is declared (1 == entry body)."""
    depth = 0
    for line in text.split("\n"):
        if depth == 1 and re.match(rf"\s*{re.escape(field_name)}\s*=", line, re.IGNORECASE):
            return depth
        depth += line.count("{") - line.count("}")
    return None


def test_multiline_abstract_then_source_both_depth_1():
    entry = (
        "@book{wallace1994,\n"
        "  author = {Wallace, R. Jay},\n"
        "  title = {Responsibility and the Moral Sentiments},\n"
        "  year = {1994},\n"
        "  publisher = {Harvard University Press},\n"
        "}"
    )
    abstract = (
        "First paragraph of the NDPR review of the book.\n\n"
        "Second paragraph continues the discussion.\n\n"
        "Third paragraph concludes the summary."
    )
    step1 = mod.add_field_to_entry(entry, "abstract", abstract)
    step2 = mod.add_field_to_entry(step1, "abstract_source", "ndpr")

    assert _decl_depth(step2, "abstract") == 1
    assert _decl_depth(step2, "abstract_source") == 1

    db = parse_string(step2, "bibtex")
    e = db.entries["wallace1994"]
    assert e.fields["abstract_source"].lower() == "ndpr"
    assert "First paragraph" in e.fields["abstract"]
    assert "abstract_source" not in e.fields["abstract"]


def test_existing_field_replacement_unchanged():
    entry = (
        "@article{x,\n"
        "  author = {Doe, Jane},\n"
        "  abstract = {old},\n"
        "  year = {2020},\n"
        "}"
    )
    out = mod.add_field_to_entry(entry, "abstract", "new abstract text")
    db = parse_string(out, "bibtex")
    assert db.entries["x"].fields["abstract"] == "new abstract text"
