"""Composition regression (spec W13): reproduce the exact production pollution -
a verify JSON that was redirected `> file.json 2>&1` into intermediate_files/json/
(stderr log lines ahead of the JSON), plus a clean search JSON at the review
root - then run the REAL cleaning path (clean_bibtex over BOTH dirs, exactly what
subagent_stop_bib.sh now passes). Exercises salvage + dir-union + entry-scoped
gating together, no network. The polluted file is written in pure Python (byte
content is what matters) so the test is portable to Windows pytest runs."""
import json
import sys
from pathlib import Path

from pybtex.database import parse_file

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import metadata_cleaner as mc  # noqa: E402

DOI = "10.1111/j.1468-5930.2007.00346.x"


def _write_polluted_verify(target: Path) -> None:
    """Reproduce `verify_paper.py ... > target 2>&1`: stderr log lines land in
    the file AHEAD of the JSON object. The JSON has an EMPTY page, so `pages`
    can only be verified via the root search JSON (the dir-union assertion)."""
    obj = {
        "status": "success", "source": "crossref",
        "query": {"doi": DOI},
        "results": [{
            "verified": True, "doi": DOI, "title": "Killer Robots",
            "container_title": "Journal of Applied Philosophy",
            "volume": "24", "issue": "", "page": "", "publisher": "", "year": 2007,
        }],
        "count": 1, "errors": [],
    }
    polluted = (
        "[verify_paper.py] Connecting to CrossRef API...\n"
        f"[verify_paper.py] Verifying DOI: {DOI}\n"
        + json.dumps(obj, indent=2)
    )
    target.write_text(polluted, encoding="utf-8")


def test_composition_salvage_union_gating(tmp_path):
    review = tmp_path / "reviews" / "mhc"
    jdir = review / "intermediate_files" / "json"
    jdir.mkdir(parents=True)

    # (1) Polluted verify JSON under intermediate_files/json/ — the ONLY source
    #     of the DOI (so the entry can only MATCH if salvage succeeds).
    _write_polluted_verify(jdir / "verify_sparrow.json")

    # (2) Clean search JSON at the REVIEW ROOT — the ONLY source of `pages`
    #     "62-77" (so `pages` survives only via the dir-UNION).
    (review / "s2_results.json").write_text(json.dumps({
        "source": "s2",
        "results": [{"title": "Killer Robots",
                     "journal": {"name": "Journal of Applied Philosophy", "pages": "62-77"},
                     "year": 2007}],
    }), encoding="utf-8")

    # (3) The .bib: a MATCHED entry with one hallucinated field (number=99),
    #     and an UNMATCHED entry that must pass through untouched.
    bib = review / "literature-domain-1.bib"
    bib.write_text(
        '@article{sparrow2007killer,\n'
        '  author = {Sparrow, Robert},\n  title = {Killer Robots},\n'
        '  journal = {Journal of Applied Philosophy},\n  year = {2007},\n'
        '  volume = {24},\n  number = {99},\n  pages = {62--77},\n'
        f'  doi = {{{DOI}}},\n}}\n'
        '@article{unmatchedfoo,\n'
        '  author = {Nobody, A.},\n  title = {Totally Different Paper},\n'
        '  journal = {Bogus Journal},\n  year = {1999},\n'
        '  doi = {10.9999/nope},\n}\n',
        encoding="utf-8",
    )

    # Run the REAL cleaning path over BOTH dirs, exactly as subagent_stop_bib.sh
    # now passes them (the .bib's own dir = review root, AND intermediate_files/json).
    result = mc.clean_bibtex(bib, [review, jdir])

    # Salvage happened, and both entries were seen (one matched, one not).
    assert "verify_sparrow.json" in result["salvaged_files"]
    assert result["matched_entries"] == 1
    assert result["unmatched_entries"] == 1

    out = parse_file(str(bib), bib_format="bibtex")
    matched = out.entries["sparrow2007killer"]
    fields = {k.lower() for k in matched.fields.keys()}
    assert "number" not in fields                 # hallucinated -> stripped
    assert "doi" in fields                         # matched via SALVAGED verify JSON
    assert "pages" in fields                       # kept via dir-UNION (root s2 JSON)
    assert "journal" in fields and "volume" in fields
    assert matched.type == "article"               # journal survived -> no demote

    unmatched = out.entries["unmatchedfoo"]
    assert unmatched.fields.get("journal") == "Bogus Journal"  # untouched
