"""Item 3 F: Chicago a/b letters for same-author same-year works.

Assignment happens ONCE, in the evidence barrier, over the union of every
domain bib -- before Phase 5, because the information is lost at write time
and the writers are what must carry it into the prose.

The unit of assignment is a WORK, not a bib entry: the same paper routinely
appears in two domain bibs under different citation keys, and giving those
copies different letters would break every sentence written against the other
copy. Work identity is exactly `dedupe_bib`'s: same normalized DOI, or same
`bib_identity.fallback_key` (title/year/surname). Sharing the identity rule is
what keeps the Phase 6 merge and this pass from disagreeing.

Groups are formed on (author signature, year), where the signature carries a
first INITIAL per author. Two different people with the same surname (the
Gabbrielle/Rebecca Johnson case) therefore never group: Chicago's rule for
them is initials, which is item 3 E's mechanism, not this one.

Letters run alphabetically by title (Chicago 15.18), tie-broken by entry id,
so assignment is deterministic and independent of input order. Nothing is
ever re-lettered: a later drop leaves a gap (2010a, 2010c), which is correct.
"""
from __future__ import annotations

import sys
from pathlib import Path

_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_identity import fallback_key, normalize_doi, title_key  # noqa: E402

sys.path.pop(0)

SUFFIX_FIELD = "year_suffix"
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _fold(text: str) -> str:
    return title_key(text or "")


def _person_signature(name: str) -> tuple[str, str]:
    """(surname fold, first initial) for one BibTeX name.

    pybtex parses "Menary, Richard", "Richard Menary" and "van der Deijl,
    Willem" alike; a name it cannot parse degrades to the naive
    comma/whitespace split rather than raising.
    """
    try:
        from pybtex.database import Person
        person = Person(name)
        surname = " ".join(person.prelast_names + person.last_names)
        firsts = person.first_names
    except Exception:
        if "," in name:
            surname, _, rest = name.partition(",")
            firsts = rest.split()
        else:
            parts = name.split()
            surname, firsts = (parts[-1] if parts else ""), parts[:-1]
    initial = ""
    for part in firsts:
        folded = _fold(part)
        if folded:
            initial = folded[0]
            break
    return (_fold(surname), initial)


def author_signature(author: str, editor: str = "") -> tuple[tuple[str, str], ...]:
    """The identity of an author LIST, initial-sensitive. Editors are the
    fallback for edited volumes, matching generate_bibliography's rule."""
    field = (author or "").strip() or (editor or "").strip()
    if not field:
        return ()
    sig = tuple(_person_signature(part.strip())
                for part in field.split(" and ") if part.strip())
    return () if any(not s[0] for s in sig) else sig


def work_identity_keys(fields: dict) -> tuple[str | None, tuple | None]:
    """The two axes `dedupe_bib` merges on. Either may be None."""
    doi = normalize_doi(fields.get("doi") or "") or None
    fkey = fallback_key(
        fields.get("title") or "",
        fields.get("year") or "",
        _first_surname_raw(fields),
    )
    return doi, fkey


def _first_surname_raw(fields: dict) -> str:
    """The first author's FULL surname, parsed the way the rest of the
    pipeline parses it.

    This feeds `fallback_key`, so it must agree with `dedupe_bib` and
    `generate_bibliography`, both of which take pybtex's prelast+last names.
    A naive comma/whitespace split disagrees on particled surnames written
    without a comma ("Willem van der Deijl" -> "Deijl" instead of "van der
    Deijl"), which would make this pass and the Phase 6 merge disagree about
    work identity: two copies of one work would take two letters and then be
    merged into one entry carrying one of them, leaving the prose citing a
    letter that no reference shows.
    """
    field = (fields.get("author") or "").strip() or (fields.get("editor") or "").strip()
    first = field.split(" and ")[0].strip()
    if not first:
        return ""
    try:
        from pybtex.database import Person
        person = Person(first)
        surname = " ".join(person.prelast_names + person.last_names).strip()
        if surname:
            return surname
    except Exception:
        pass
    if "," in first:
        return first.split(",")[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


class _Union:
    """Minimal union-find over hashable ids."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def assign_suffixes(entries: list[dict]) -> dict:
    """{"suffixes": {id: letter}, "groups": [...], "overflow": [ids]}.

    Entries with no usable author signature or no 4-digit year are skipped
    entirely -- they can never be cited author-year anyway.
    """
    usable = []
    for ent in entries or []:
        sig = author_signature(ent.get("author", ""), ent.get("editor", ""))
        year = (ent.get("year") or "").strip()
        if not sig or not (len(year) == 4 and year.isdigit()):
            continue
        usable.append({**ent, "_sig": sig, "_year": year})

    # 1. Collapse entries into works on dedupe's identity axes -- with dedupe's
    #    own refusal: never merge across CONFLICTING non-empty DOIs.
    #    generate_bibliography.find_cited_entries applies exactly this rule
    #    ("distinct non-empty DOI sets => genuinely different works"). Without
    #    it the barrier collapses two works Phase 6 keeps, both copies take one
    #    letter, and the References render two entries labelled 2010a.
    uf = _Union()
    by_doi, by_fkey = {}, {}
    doi_of = {}
    for ent in usable:
        uf.find(ent["id"])
        doi, fkey = work_identity_keys(ent)
        doi_of[ent["id"]] = doi
        if doi:
            uf.union(by_doi.setdefault(doi, ent["id"]), ent["id"])
    for ent in usable:
        _doi, fkey = work_identity_keys(ent)
        if not fkey:
            continue
        other = by_fkey.setdefault(fkey, ent["id"])
        if other == ent["id"]:
            continue
        a, b = doi_of.get(other), doi_of.get(ent["id"])
        if a and b and a != b:
            continue  # conflicting DOIs -- distinct works, same as dedupe
        uf.union(other, ent["id"])

    works: dict = {}
    for ent in usable:
        works.setdefault(uf.find(ent["id"]), []).append(ent)

    # 2. A work whose copies DISAGREE about who wrote it or when gets no
    #    letter: the letter would be assigned under a grouping the Phase 6
    #    winner may not belong to. Reported, never silent.
    conflicts = []
    coherent = {}
    for root, members in works.items():
        sigs = {m["_sig"] for m in members}
        years = {m["_year"] for m in members}
        if len(sigs) > 1 or len(years) > 1:
            conflicts.append(sorted(repr(m["id"]) for m in members))
            continue
        coherent[root] = members

    # 3. Each work's representative is its lexicographically-first id, so the
    #    group key and the sort title do not depend on input order.
    reps = {root: min(members, key=lambda m: repr(m["id"]))
            for root, members in coherent.items()}

    # 4. Group works by (author signature, year).
    groups: dict = {}
    for root, rep in reps.items():
        groups.setdefault((rep["_sig"], rep["_year"]), []).append(root)

    suffixes, overflow, summary = {}, [], []
    for (sig, year), roots in sorted(groups.items(), key=lambda kv: (kv[0][1], repr(kv[0][0]))):
        if len(roots) < 2:
            continue
        if len(roots) > len(LETTERS):
            # NEVER partially letter a group. A group where some members carry
            # letters and some do not lets a suffixed citation select the
            # lettered member and drop the rest -- the exact phantom-drop this
            # feature must not introduce. Report the whole group instead.
            overflow.append({"authors": reps[roots[0]].get("author") or "",
                             "year": year, "works": len(roots)})
            continue
        roots.sort(key=lambda r: (title_key(reps[r].get("title") or ""), repr(reps[r]["id"])))
        for index, root in enumerate(roots):
            for member in coherent[root]:
                suffixes[member["id"]] = LETTERS[index]
        summary.append({"authors": reps[roots[0]].get("author") or reps[roots[0]].get("editor") or "",
                        "year": year, "works": len(roots)})
    return {"suffixes": suffixes, "groups": summary, "overflow": overflow,
            "conflicts": conflicts,
            "assigned_entries": len(suffixes),
            "assigned_works": sum(g["works"] for g in summary)}
