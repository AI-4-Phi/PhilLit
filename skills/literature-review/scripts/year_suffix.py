"""Item 3 F: Chicago a/b letters for same-author same-year works.

Assignment happens ONCE, in the evidence barrier, over the union of every
domain bib -- before Phase 5, because the information is lost at write time
and the writers are what must carry it into the prose.

The unit of assignment is a WORK, not a bib entry: the same paper routinely
appears in two domain bibs under different citation keys, and giving those
copies different letters would break every sentence written against the other
copy. Work identity is exactly `dedupe_bib`'s: same normalized DOI, or same
`bib_identity.fallback_key` (title/year/surname), with dedupe's own refusal to
merge across CONFLICTING non-empty DOI values. Sharing the identity rule is
what keeps the Phase 6 merge and this pass from disagreeing.

Groups are formed on (author signature, year), where the signature carries a
first INITIAL per author. Two different people with the same surname but a
DIFFERENT first initial (the Gabbrielle/Rebecca Johnson case) never group.
Two people who share BOTH surname and initial (Gabrielle and Gareth Johnson)
are NOT distinguished by this module -- an initial is the limit of its
identity signal; full first-name disambiguation is item 3 E's mechanism, not
this one.

Letters run alphabetically by title (Chicago 15.18), tie-broken by entry id,
so assignment is deterministic and independent of input order. Nothing is
ever re-lettered: a later drop leaves a gap (2010a, 2010c), which is correct.
Entry ids must have a stable `repr()` across a run (true of the str/tuple/int
ids every caller uses; NOT true of a frozenset or a plain object, whose repr
can carry an address or an arbitrary iteration order).

WHOLE-GROUP SUPPRESSION. Three situations make it unsafe to letter an
author-year group at all. Each is reported (never silent) rather than
producing a partial or order-dependent result -- in `suppressed`, or in
`suppressed_singletons` when the group could not have been lettered anyway
(see the split below):

  1. DOI-CONFLICT BRIDGE. A same-fallback-key cluster holds two or more
     entries with distinct, non-empty, mutually conflicting DOIs *and* at
     least one entry with no DOI at all. Which conflicting side that DOI-less
     copy belongs to is undecidable from the data -- and picking greedily (as
     a streaming merge would) gives a DIFFERENT answer depending on input
     order. Detected cluster-wide (not entry-by-entry against an arbitrary
     "first seen" representative), so the DETECTION itself does not depend on
     order; the group is then suppressed outright rather than let a streaming
     tie-break decide.
  2. IDENTITY CONFLICT. A work's copies disagree about who wrote it or when
     (see `conflicts`). The excluded work is invisible to normal group
     formation, so lettering its siblings would silently under-count the
     group and print one reference with no letter alongside ones that have
     letters.
  3. FILTERED COPY. A copy of a work fails the usability pre-filter (no
     parseable author, or a year that is not exactly four digits, e.g.
     "n.d.") while a sibling copy of the SAME work (same DOI or fallback key)
     passes. Filtering the unusable copy out before identity resolution would
     silently split one work into a lettered copy and an invisible one.

Suppression is reported in TWO lists, because on real input the overwhelming
majority of suppressed groups never had a letter at stake. `suppressed` holds
the groups where suppression actually cost letters; `suppressed_singletons`
holds groups the assigner left unlettered that held at most ONE work, which
Chicago would not have lettered anyway (disambiguation starts at two).
Measured over the real barrier input (42 delivered reviews, 4,582 domain-bib
entries): 8 records in `suppressed` against 98 in `suppressed_singletons`,
every one of the latter an `identity_conflict` raised by a duplicate pair
that spells one author two ways. Nothing is discarded -- an operator who
wants everything reads both lists -- but a count of `suppressed` alone, which
is what a console summary shows, now counts only actionable groups.

A suppressed group's `works` count includes entries hidden from normal group
formation by (2) and (3) -- it is a best-effort total, not a guarantee that a
different input order would report the identical number, since the group
never receives a canonical partition. Where it errs, it errs HIGH against the
works THIS MODULE identifies: a filtered copy is counted apart from the
sibling it is a copy of, so a one-work group can report `works: 2`. (Against
ground truth it can of course run low -- two genuinely distinct works that
share a title, year and surname with no DOIs merge into one root -- but that
is the same partition lettering itself acts on, so such a pair would never
have been lettered apart either.) Erring high is what makes the split above
safe: `works == 1` really does mean "at most one work here, so no letter was
ever in play", while `works >= 2` lets a few single works through into the
list that gets read -- which costs an operator a second look, not a missed
group.
What every input order DOES guarantee identically is that no member of a
suppressed group -- in EITHER list -- appears in `suffixes`.

DETERMINISM has two scopes, and they are not the same claim -- an earlier
version of this docstring asserted the first and let a reader assume the
second. (1) The `suffixes` MAP is the module's invariant: reproducible from
the input SET alone, whatever order it arrives in. (2) The REPORT is a weaker
promise. Its ordering is fixed (records are emitted in sorted key order, and
`conflicts` -- the one list built outside that loop -- is sorted before
return), and every string in it is chosen by value rather than by arrival:
`authors` is the lexicographically smallest spelling among the copies that
name the group, because those copies routinely disagree about how to write
one name. Shuffling the real corpus (42 reviews x 5 orderings) now changes
nothing in either; before, three reviews flipped the `authors` string of a
suppression record. But `works` remains the best-effort floor described
above, since a suppressed group never receives a canonical partition to
count -- so treat a report number as telemetry and a letter as a guarantee.
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
    """Assign Chicago a/b/c letters over WORK identity.

    Returns:
      {"suffixes": {id: letter},
       "groups": [{"authors": str, "year": str, "works": int}, ...],
       "overflow": [{"authors": str, "year": str, "works": int}, ...],
       "suppressed": [{"authors": str, "year": str, "works": int,
                        "reasons": [str, ...]}, ...],
       "suppressed_singletons": [<same shape as suppressed>, ...],
       "conflicts": [[repr(id), ...], ...]}

    `suppressed` vs `suppressed_singletons`, and the two scopes of
    determinism the report keys carry, are in the module docstring. Entry and
    work totals are deliberately NOT returned: `len(suffixes)` and
    `sum(g["works"] for g in groups)` are the same numbers, and a second copy
    of a derived count is a thing to keep in sync for nothing.

    Entries with no usable author signature or no 4-digit year are skipped
    entirely -- they can never be cited author-year anyway -- UNLESS a
    skipped entry shares identity (DOI or fallback key) with an otherwise
    usable one, in which case it taints that work's group into `suppressed`
    instead of silently disappearing (module docstring, situation 3).
    """
    all_entries = list(entries or [])

    # Compute identity keys for EVERY entry, including ones the usability
    # filter below will drop -- a dropped copy still needs to be checked
    # against its usable siblings (situation 3).
    doi_of: dict = {}
    fkey_of: dict = {}
    for ent in all_entries:
        doi, fkey = work_identity_keys(ent)
        doi_of[ent["id"]] = doi
        fkey_of[ent["id"]] = fkey

    usable, unusable = [], []
    for ent in all_entries:
        sig = author_signature(ent.get("author", ""), ent.get("editor", ""))
        year = (ent.get("year") or "").strip()
        if not sig or not (len(year) == 4 and year.isdigit()):
            unusable.append(ent)
            continue
        usable.append({**ent, "_sig": sig, "_year": year})

    tainted: dict = {}        # (sig, year) -> set of reason strings
    taint_extra: dict = {}    # (sig, year) -> set of ids hidden from `roots`
    taint_authors: dict = {}  # (sig, year) -> set of raw author/editor strings

    def taint(sig, year, reason, extra_id=None, authors_hint=""):
        if not sig or not year:
            return
        key = (sig, year)
        tainted.setdefault(key, set()).add(reason)
        if extra_id is not None:
            taint_extra.setdefault(key, set()).add(extra_id)
        if authors_hint:
            # EVERY spelling, not the first one seen: the copies that taint a
            # group routinely disagree about how to write one name (the
            # LaTeX-escape/diacritic duplicate pairs are the common case), so
            # "first seen" made the reported string depend on input order.
            taint_authors.setdefault(key, set()).add(authors_hint)

    # Situation 3: an unusable copy sharing identity with a usable sibling
    # taints that sibling's group instead of silently vanishing.
    for u in unusable:
        udoi, ufkey = doi_of[u["id"]], fkey_of[u["id"]]
        if not udoi and not ufkey:
            continue
        for ent in usable:
            same_doi = udoi and udoi == doi_of[ent["id"]]
            same_fkey = ufkey and ufkey == fkey_of[ent["id"]]
            if same_doi or same_fkey:
                taint(ent["_sig"], ent["_year"], "filtered_copy",
                      extra_id=repr(u["id"]),
                      authors_hint=ent.get("author") or ent.get("editor") or "")

    # 1. DOI axis: same normalized DOI is unconditionally the same work --
    #    dedupe's strongest signal, no refusal possible. This pass is a pure
    #    equivalence relation (group-by-value), so it is order-independent:
    #    which entries land together never depends on iteration order.
    uf = _Union()
    doi_set_of: dict = {}
    for ent in usable:
        uf.find(ent["id"])
        doi_set_of[ent["id"]] = {doi_of[ent["id"]]} if doi_of[ent["id"]] else set()
    by_doi: dict = {}
    for ent in usable:
        d = doi_of[ent["id"]]
        if not d:
            continue
        other = by_doi.setdefault(d, ent["id"])
        if other == ent["id"]:
            continue
        ra, rb = uf.find(other), uf.find(ent["id"])
        if ra != rb:
            merged = doi_set_of.get(ra, set()) | doi_set_of.get(rb, set())
            uf.union(ra, rb)
            doi_set_of[uf.find(ra)] = merged

    # 2. Fallback-key axis, resolved CLUSTER-WIDE -- every entry sharing one
    #    fallback key is examined together, rather than merged one at a time
    #    against an arbitrary "first seen" representative. generate_
    #    bibliography.find_cited_entries and dedupe_bib both refuse to merge
    #    across distinct non-empty DOI sets; here that refusal additionally
    #    triggers whole-group suppression when a DOI-less entry could have
    #    bridged either conflicting side (module docstring, situation 1) --
    #    a per-pair streaming refusal cannot detect this, because whether the
    #    bridge is "used up" by the time a given pair is compared depends on
    #    the order entries were processed in.
    fkey_clusters: dict = {}
    for ent in usable:
        fkey = fkey_of[ent["id"]]
        if fkey:
            fkey_clusters.setdefault(fkey, []).append(ent)

    for fkey, cluster in fkey_clusters.items():
        if len(cluster) < 2:
            continue
        components: dict = {}
        for ent in cluster:
            components.setdefault(uf.find(ent["id"]), []).append(ent)
        if len(components) < 2:
            continue  # already one component via the DOI axis
        distinct_dois: set = set()
        for root in components:
            distinct_dois |= doi_set_of.get(root, set())
        if len(distinct_dois) <= 1:
            # No conflicting DOI in play (0 or 1 distinct value across every
            # component in the cluster): safe to merge them all into one work.
            roots = list(components.keys())
            base = roots[0]
            merged = set()
            for root in roots:
                merged |= doi_set_of.get(root, set())
            for root in roots[1:]:
                uf.union(base, root)
            doi_set_of[uf.find(base)] = merged
        else:
            empty_doi_components = [r for r in components if not doi_set_of.get(r)]
            if empty_doi_components:
                # A DOI-less copy sits in a cluster with two-plus mutually
                # conflicting DOIs. Which side it belongs to is undecidable;
                # suppress the whole author-year group rather than let a
                # greedy merge pick one side and vary by input order.
                for ent in cluster:
                    taint(ent["_sig"], ent["_year"], "doi_conflict",
                          authors_hint=ent.get("author") or ent.get("editor") or "")
            # Components with distinct non-empty DOIs and no bridge stay
            # separate, matching dedupe's refusal -- nothing further to do.

    works: dict = {}
    for ent in usable:
        works.setdefault(uf.find(ent["id"]), []).append(ent)

    # 3. A work whose copies DISAGREE about who wrote it or when gets no
    #    letter -- and every author-year group any of its copies would have
    #    belonged to is suppressed too (situation 2), not just this one work.
    conflicts = []
    coherent = {}
    for root, members in works.items():
        sigs = {m["_sig"] for m in members}
        years = {m["_year"] for m in members}
        if len(sigs) > 1 or len(years) > 1:
            conflicts.append(sorted(repr(m["id"]) for m in members))
            combo_id = "conflict:" + min(repr(m["id"]) for m in members)
            # Collect EVERY spelling each combo's members use, not the first
            # one this loop happens to reach: `members` is iterated in input
            # order, so a first-seen hint made the reported `authors` string
            # flip between two spellings of one name when the input was
            # reordered (observed on three reviews of the real corpus, e.g.
            # "Dryzek, John S." vs "DRYZEK, John S.").
            hint_of_combo: dict = {}
            for m in members:
                hint_of_combo.setdefault((m["_sig"], m["_year"]), set()).add(
                    m.get("author") or m.get("editor") or "")
            for (combo_sig, combo_year), hints in hint_of_combo.items():
                for hint in sorted(hints):
                    taint(combo_sig, combo_year, "identity_conflict",
                          extra_id=combo_id, authors_hint=hint)
            continue
        coherent[root] = members

    # 4. Each work's representative is its lexicographically-first id, so the
    #    group key and the sort title do not depend on input order.
    reps = {root: min(members, key=lambda m: repr(m["id"]))
            for root, members in coherent.items()}

    # 5. Group works by (author signature, year).
    groups: dict = {}
    for root, rep in reps.items():
        groups.setdefault((rep["_sig"], rep["_year"]), []).append(root)

    all_keys = set(groups.keys()) | set(tainted.keys())
    suffixes, overflow, suppressed, singletons, summary = {}, [], [], [], []
    for sig, year in sorted(all_keys, key=lambda k: (k[1], repr(k[0]))):
        key = (sig, year)
        roots = groups.get(key, [])
        # Sort BEFORE reading reps[roots[0]] below -- reading it first would
        # make the reported "authors"/title-tiebreak depend on input order.
        roots.sort(key=lambda r: (title_key(reps[r].get("title") or ""), repr(reps[r]["id"])))
        if roots:
            authors = reps[roots[0]].get("author") or reps[roots[0]].get("editor") or ""
        else:
            hints = taint_authors.get(key)
            authors = min(hints) if hints else ""

        if key in tainted:
            # NEVER partially letter a group: suppress it wholesale, the same
            # way overflow suppresses an oversized one, so a suffixed
            # citation can never select a lettered member and drop the rest.
            works_count = len(roots) + len(taint_extra.get(key, ()))
            record = {"authors": authors, "year": year,
                      "works": works_count,
                      "reasons": sorted(tainted[key])}
            # A group that knows of at most one work could never have been
            # lettered (Chicago disambiguates from two works up), so its
            # suppression cost nothing and it is not something to act on.
            # That this holds for EVERY way of reaching works_count == 1 is
            # worth spelling out, because the non-obvious branch is the one a
            # future reader will doubt:
            #   * roots == 1, no hidden ids -- only `doi_conflict` taints
            #     without hiding anything, and a group letters from its own
            #     roots alone, so one root means no letters either way;
            #   * roots == 0, one hidden id -- necessarily one conflicting
            #     work, because `filtered_copy` CANNOT produce this: it fires
            #     only for an unusable copy sharing identity with a USABLE
            #     sibling, and a coherent work's representative carries its
            #     members' own (signature, year), so that sibling's root is
            #     always in this group's `roots`. Hence filtered_copy always
            #     implies works_count >= 2.
            # Against this module's own work partition -- the one lettering
            # acts on -- the count errs high, never low (module docstring),
            # so the split over-retains rather than under-reports: a one-work
            # group with a filtered copy reads 2 and stays in `suppressed`.
            (suppressed if works_count >= 2 else singletons).append(record)
            continue
        if len(roots) < 2:
            continue
        if len(roots) > len(LETTERS):
            overflow.append({"authors": authors, "year": year, "works": len(roots)})
            continue
        for index, root in enumerate(roots):
            for member in coherent[root]:
                suffixes[member["id"]] = LETTERS[index]
        summary.append({"authors": authors, "year": year, "works": len(roots)})

    # `conflicts` is the one report list not built inside the sorted-key loop
    # above -- it is appended in `works.items()` order, which follows input
    # order. Sorting it here is what makes the whole report serialization
    # order-independent (each element is already a sorted list of strings).
    conflicts.sort()

    return {"suffixes": suffixes, "groups": summary, "overflow": overflow,
            "suppressed": suppressed, "suppressed_singletons": singletons,
            "conflicts": conflicts}
