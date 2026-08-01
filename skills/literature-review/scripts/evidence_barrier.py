"""Transactional evidence barrier -- run once at the Phase 3->4 boundary.

Order: manifest validation -> SEP/IEP context acquisition -> report -> stamp.
Accuracy gate: fails CLOSED. run_barrier() mutates nothing -- it returns the
report plus every domain's final stamped content, built in memory; execute()
then atomically writes the report FIRST, then each bib. A crash before the
write phase leaves every file untouched; a crash mid-write leaves a prefix of
domains stamped with exit 1 (documented residual -- SKILL.md halts on
nonzero, and unstamped files read as all-EVIDENCE-NONE downstream).
Per-domain problems degrade (status: "degraded") and can only demote the
affected entries. All maps are per-domain: same-key entries in different
domains never share attestations.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import enrich_bibliography as eb
from enrich_bibliography import add_field_to_entry
import resolve_context as rc
import stamp_evidence as se


def _load_ledger(path: Path, expected_bib_name: str, kind: str):
    """(state, payload): present / missing / malformed. Never raises."""
    if not path.exists():
        return "missing", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return "malformed", None
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return "malformed", None
    if data.get("bib_file") != expected_bib_name:
        return "malformed", None  # stale/copied ledger -- reject
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return "malformed", None
    if kind == "cleaning":
        for v in entries.values():
            if not isinstance(v, dict) or v.get("verified_identifier") not in (
                    "doi", "publisher", None):
                return "malformed", None
    return "present", data


def _parseable_bib(path: Path) -> bool:
    from pybtex.database import parse_file
    from pybtex.scanner import PybtexError
    try:
        parse_file(str(path), bib_format="bibtex")
        return True
    except (PybtexError, OSError, UnicodeDecodeError):
        return False


_ABSTRACT_FIELD_RE = re.compile(r'\babstract\s*=', re.IGNORECASE)


def _heal_splice_is_well_formed(chunk: str) -> bool:
    """Defense-in-depth check run after a heal splice (review finding 1b):
    the splice must have produced EXACTLY ONE `abstract =` field, AND the
    resulting single-entry chunk must be pybtex-parseable.

    Neither check alone suffices. A duplicate field -- the exact review
    finding 1 shape, a stale nested-brace field the locator couldn't bound
    left behind alongside a newly INSERTED one -- is not guaranteed to
    raise in pybtex, so the count is the guaranteed catch for that case.
    Conversely a restored value that itself contains an unbalanced brace
    produces a single (correctly-counted) but unparseable field, which
    only the pybtex check catches. Fail-closed: any exception from pybtex
    counts as NOT well-formed. (Accepted residual: a restored abstract
    whose prose happens to literally contain the substring "abstract ="
    would trip the count and spuriously drop a good heal -- fail-closed is
    the right default here.)
    """
    if len(_ABSTRACT_FIELD_RE.findall(chunk)) != 1:
        return False
    from pybtex.database import parse_string
    try:
        parse_string(chunk, bib_format="bibtex")
    except Exception:
        return False
    return True


def _heal_abstract(fields: dict, ledger_entry: dict, debug: bool = False):
    """Restore an attested abstract after a post-attestation mutation.

    A/B root cause 2 (2026-07-25, domain 5): a researcher re-emitted its
    bib after enrichment and mutated 7 attested abstracts. Re-fetch by the
    entry's identifiers; the gate is HASH EQUALITY with the ledger value,
    so which API returns the text is irrelevant to integrity. Returns the
    restored text or None. Never raises (fail-closed: no heal, entry
    proceeds unattested exactly as before this feature). The resolver
    stub below assumes resolve_abstract_for_entry reads only
    entry['fields'] (true today) -- if it ever reads key/raw, resolution
    degrades to a failed heal, never a crash.
    """
    if not isinstance(ledger_entry, dict):
        return None
    target = ledger_entry.get("abstract_sha256")
    source = (ledger_entry.get("abstract_source") or "").strip().lower()
    if not target or not source:
        return None
    entry = {"key": "", "fields": fields, "raw": ""}
    try:
        if source == "ndpr":
            fetched, _ = eb.resolve_ndpr_abstract(
                fields.get("title", ""), eb.get_author_last_name(entry), debug)
        else:
            fetched, _ = eb.resolve_abstract_for_entry(
                entry,
                os.environ.get("S2_API_KEY", ""),
                os.environ.get("OPENALEX_EMAIL", ""),
                os.environ.get("CORE_API_KEY", ""),
                debug,
            )
    except Exception:
        return None
    if fetched and se.abstract_hash(fetched) == target:
        return fetched
    return None


def _att_blob(att: se.EntryAttestation, enrich_entry, context_value):
    return {
        "abstract_attested": att.abstract_attested,
        "abstract_source": (enrich_entry or {}).get("abstract_source"),
        "abstract_sha256": (enrich_entry or {}).get("abstract_sha256"),
        "context_written": att.context_written,
        "context_field": None if context_value is None else context_value[0],
        "context_sha256": None if context_value is None else se.abstract_hash(context_value[1]),
        "api_matched": att.api_matched,
        "verified_identifier": att.verified_identifier,
        "verified_identifier_value": att.verified_identifier_value,
        "breaker_tripped": att.breaker_tripped,
    }


def run_barrier(review_dir: Path, n_domains: int, debug: bool = False):
    """Pure planning pass: returns (report, outputs) with NO file mutation.

    outputs: {bib_path: final_stamped_content} -- only parseable, present
    domains appear in it.
    """
    ijson = review_dir / "intermediate_files" / "json"
    report = {
        "schema_version": 1, "status": "complete", "domains": {},
        "articles": {"fetched": [], "failed": []}, "acquisition": {},
        "attestations": {}, "stamps": {},
        "web_sources_none": {"count": 0, "keys": []},
        "demoted_would_be_existence_v4": [],
        "healed": {},
    }
    degraded = False
    domains = {}
    slug_paths = []
    for i in range(1, n_domains + 1):
        bib_name = f"literature-domain-{i}.bib"
        bib = review_dir / bib_name
        c_state, c_data = _load_ledger(
            ijson / f"cleaning_ledger-literature-domain-{i}.json", bib_name, "cleaning")
        e_state, e_data = _load_ledger(
            ijson / f"enrichment_ledger-literature-domain-{i}.json", bib_name, "enrichment")
        slug_paths.append(ijson / f"encyclopedia_entries-domain-{i}.json")
        if not bib.exists():
            b_state = "missing"
        elif not _parseable_bib(bib):
            b_state = "malformed"  # excluded from outputs -- never corrupt it
        else:
            b_state = "present"
        report["domains"][str(i)] = {
            "bib": b_state, "cleaning_ledger": c_state, "enrichment_ledger": e_state,
        }
        if b_state != "present" or c_state != "present" or e_state != "present":
            degraded = True
        if b_state == "present":
            domains[i] = {"bib": bib, "bib_name": bib_name,
                          "cleaning": c_data, "enrichment": e_data}

    slug_states, slug_union = rc.load_slug_files(slug_paths)
    for i in range(1, n_domains + 1):
        s = slug_states[str(slug_paths[i - 1])]
        report["domains"][str(i)]["slug_file"] = s
        if s in ("missing", "malformed"):
            degraded = True

    if not domains:
        report["status"] = "failed"
        return report, {}

    articles, failed = rc.fetch_articles(slug_union, debug=debug)
    report["articles"]["fetched"] = sorted(articles)
    report["articles"]["failed"] = failed
    if failed:
        degraded = True

    # Per-domain parse + attestations (KEYED PER DOMAIN -- never bare keys).
    parsed = {}        # i -> list[chunk]
    atts = {}          # i -> {key: EntryAttestation}
    needs_context = {} # "bib_name::key" -> {"entry_type", "fields"}
    healed = {}         # (i, key) -> (restored_text, canonical_source)
    for i, d in domains.items():
        chunks = [rc.strip_context_fields(c) if se.entry_header(c) else c
                  for c in se.split_entries(d["bib"].read_text(encoding="utf-8"))]
        parsed[i] = chunks
        atts[i] = {}
        c_entries = (d["cleaning"] or {}).get("entries", {})
        breaker = bool((d["cleaning"] or {}).get("breaker_tripped"))
        e_entries = {
            k: v
            for k, v in ((d["enrichment"] or {}).get("entries", {}) or {}).items()
            if isinstance(v, dict)
        }
        report["acquisition"].setdefault(d["bib_name"], {})
        for chunk in chunks:
            header = se.entry_header(chunk)
            if not header:
                continue
            etype, key = header
            fields = se.parse_entry_fields(chunk)
            cl = c_entries.get(key) or {}
            att = se.EntryAttestation(
                abstract_attested=se.attest_abstract(fields, e_entries.get(key)),
                api_matched=bool(cl.get("api_matched")),
                verified_identifier=cl.get("verified_identifier"),
                verified_identifier_value=cl.get("verified_identifier_value"),
                breaker_tripped=breaker,
            )
            e_rec = e_entries.get(key)
            if (not att.abstract_attested and e_rec
                    and e_rec.get("abstract_sha256")):
                restored = _heal_abstract(fields, e_rec, debug=debug)
                src = ((e_rec.get("abstract_source") or "").strip().lower())
                if restored is not None:
                    # The FIELD must carry the ledger's source -- that is
                    # what attest_abstract compares against. Which resolver
                    # actually served the text is integrity-irrelevant
                    # (hash-gated) and is not recorded in the bib.
                    att.abstract_attested = True
                    healed[(i, key)] = (restored, src)
                    report["healed"].setdefault(d["bib_name"], {})[key] = {
                        "outcome": "restored", "source": src}
                else:
                    report["healed"].setdefault(d["bib_name"], {})[key] = {
                        "outcome": "unhealed", "source": src}
            atts[i][key] = att
            if att.abstract_attested:
                report["acquisition"][d["bib_name"]][key] = {"outcome": "not-needed"}
            else:
                needs_context[f"{d['bib_name']}::{key}"] = {
                    "entry_type": etype, "fields": fields}

    acq = rc.acquire_context(needs_context, articles)
    context_values = {}  # (i, key) -> (field, value)
    by_name = {d["bib_name"]: i for i, d in domains.items()}
    for qual_key, res in acq.items():
        bib_name, key = qual_key.split("::", 1)
        i = by_name[bib_name]
        report["acquisition"][bib_name][key] = {
            k: v for k, v in res.items() if k != "value"}
        if res["outcome"] == "matched":
            atts[i][key].context_written = True
            context_values[(i, key)] = (res["field"], res["value"])

    # Build final content in memory: context fields + stamp, then bookkeeping.
    outputs = {}
    for i, d in domains.items():
        bib_name = d["bib_name"]
        e_entries = {
            k: v
            for k, v in ((d["enrichment"] or {}).get("entries", {}) or {}).items()
            if isinstance(v, dict)
        }
        report["attestations"][bib_name] = {}
        report["stamps"][bib_name] = {}
        final_chunks = []
        for chunk in parsed[i]:
            header = se.entry_header(chunk)
            if not header:
                final_chunks.append(chunk)
                continue
            etype, key = header
            cv = context_values.get((i, key))
            if cv:
                chunk = add_field_to_entry(chunk, cv[0], cv[1])
            h = healed.get((i, key))
            if h:
                pre_heal_chunk = chunk
                chunk = add_field_to_entry(chunk, "abstract", h[0])
                chunk = add_field_to_entry(chunk, "abstract_source", h[1])
                if not _heal_splice_is_well_formed(chunk):
                    # The splice did not land cleanly -- never emit a bib
                    # the real parser rejects (or a hidden duplicate
                    # field). Drop the heal: revert to the pre-splice
                    # chunk, let the entry demote via the re-derivation
                    # below, and correct the report so it never claims a
                    # restore that did not land (review finding 1b).
                    chunk = pre_heal_chunk
                    report["healed"][bib_name][key] = {
                        "outcome": "unhealed", "source": h[1]}
            fields = se.parse_entry_fields(chunk)
            att = atts[i].get(key) or se.EntryAttestation()
            # Re-derive from the final text: the stamp must never trust a
            # flag set in the attestation loop if the corresponding splice
            # did not land in THIS chunk (fail-closed against index skew).
            att.abstract_attested = se.attest_abstract(fields, e_entries.get(key))
            tier = se.compute_tier(etype, fields, att)
            final_chunks.append(se.stamp_entry_text(chunk, tier))
            report["stamps"][bib_name][key] = tier
            report["attestations"][bib_name][key] = _att_blob(
                att, e_entries.get(key), cv)
            qual = f"{bib_name}:{key}"
            if tier == se.TIER_NONE:
                if etype.lower() == "misc" and (
                    fields.get("url") or "url" in (fields.get("howpublished") or "").lower()
                ) and not fields.get("abstract"):
                    report["web_sources_none"]["keys"].append(qual)
                if (not att.api_matched or att.breaker_tripped) and (
                    fields.get("doi")
                    or (fields.get("publisher") and etype.lower() in se.CONTAINER_TYPES)
                ):
                    report["demoted_would_be_existence_v4"].append(qual)
        outputs[d["bib"]] = "\n".join(final_chunks)
    report["web_sources_none"]["count"] = len(report["web_sources_none"]["keys"])
    report["status"] = "degraded" if degraded else "complete"
    return report, outputs


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))


def execute(review_dir: Path, n_domains: int, debug: bool = False) -> int:
    ijson = review_dir / "intermediate_files" / "json"
    ijson.mkdir(parents=True, exist_ok=True)
    report_path = ijson / "evidence_report.json"
    outputs = {}
    try:
        report, outputs = run_barrier(review_dir, n_domains, debug=debug)
    except Exception as exc:  # crash = run-level failure; nothing was written
        report = {"schema_version": 1, "status": "failed", "error": repr(exc)}
    try:
        _atomic_write(report_path, json.dumps(report, indent=2))
        if report["status"] != "failed":
            for path, content in outputs.items():  # report first, bibs second
                _atomic_write(path, content)
    except OSError as exc:
        print(json.dumps({"status": "failed", "error": repr(exc)}))
        return 1
    tiers = {}
    for per_bib in (report.get("stamps") or {}).values():
        for t in per_bib.values():
            tiers[t] = tiers.get(t, 0) + 1
    print(json.dumps({
        "status": report["status"],
        "stamped": sum(len(v) for v in (report.get("stamps") or {}).values()),
        "tiers": tiers,
        "web_sources_none": (report.get("web_sources_none") or {}).get("count", 0),
        "report": str(report_path),
    }))
    return 1 if report["status"] == "failed" else 0


def main() -> int:
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv(usecwd=True), override=True)
    ap = argparse.ArgumentParser(description="Evidence barrier (Phase 3->4)")
    ap.add_argument("review_dir")
    ap.add_argument("--domains", type=int, required=True)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    return execute(Path(args.review_dir), args.domains, debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
