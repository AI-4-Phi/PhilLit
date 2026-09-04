"""Tests for evidence_barrier.py -- the transactional Phase 3->4 driver."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = (Path(__file__).parent.parent / "skills" / "literature-review"
          / "scripts" / "evidence_barrier.py")
SCRIPTS_DIR = SCRIPT.parent

KUHN = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  publisher = {University of Chicago Press},
  year = {1962},
  keywords = {ps, High, INCOMPLETE, no-abstract}
}"""

CLEAN_KUHN = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
              "breaker_tripped": False,
              "entries": {"kuhn1962structure": {
                  "api_matched": True, "verified_identifier": "publisher",
                  "verified_identifier_value": "university of chicago press",
                  "entry_type": "book"}}}
EMPTY_ENRICH = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                "entries": {}}
EMPTY_SLUGS = '{"sep_entries": [], "iep_entries": []}'


def _domain(review_dir, i, bib_text, cleaning=None, enrichment=None,
            slugs=EMPTY_SLUGS):
    ij = review_dir / "intermediate_files" / "json"
    ij.mkdir(parents=True, exist_ok=True)
    if bib_text is not None:
        (review_dir / f"literature-domain-{i}.bib").write_text(
            bib_text, encoding="utf-8")
    if cleaning is not None:
        (ij / f"cleaning_ledger-literature-domain-{i}.json").write_text(
            json.dumps(cleaning), encoding="utf-8")
    if enrichment is not None:
        (ij / f"enrichment_ledger-literature-domain-{i}.json").write_text(
            json.dumps(enrichment), encoding="utf-8")
    if slugs is not None:
        (ij / f"encyclopedia_entries-domain-{i}.json").write_text(
            slugs, encoding="utf-8")


def _run(review_dir, n):
    # cwd=review_dir, not the pytest cwd (the repo root): evidence_barrier's
    # main() calls load_dotenv(find_dotenv(usecwd=True), override=True),
    # which walks UP from the subprocess's cwd looking for a .env and, if it
    # finds one, OVERRIDES whatever was in the inherited environment --
    # including a real OPENALEX_API_KEY that tests/conftest.py's isolation
    # fixture already stripped. A repo-root .env (exactly what .env.example
    # and /phillit:setup tell developers to create) would otherwise defeat
    # that fixture for every _run()-driven test. review_dir is always an
    # absolute path under pytest's tmp_path, outside the repo tree, so the
    # upward search from there can never reach it.
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(review_dir), "--domains", str(n)],
        capture_output=True, text=True, cwd=str(review_dir))


def _cleaning(i, entries, breaker=False):
    return {"schema_version": 1, "bib_file": f"literature-domain-{i}.bib",
            "breaker_tripped": breaker, "entries": entries}


def _enrichment(i, entries=None):
    return {"schema_version": 1, "bib_file": f"literature-domain-{i}.bib",
            "entries": entries or {}}


def _report(review_dir):
    return json.loads(
        (review_dir / "intermediate_files" / "json" / "evidence_report.json")
        .read_text(encoding="utf-8"))


POPPER = """@book{popper1959logic,
  author = {Popper, Karl},
  title = {The Logic of Scientific Discovery},
  publisher = {Hutchinson},
  year = {1959}
}"""

CLEAN_POPPER_ENTRIES = {"popper1959logic": {
    "api_matched": True, "verified_identifier": "publisher",
    "verified_identifier_value": "hutchinson", "entry_type": "book"}}

DOI_ENTRY = """@article{smith2020data,
  author = {Smith, Anna},
  title = {Data and Things},
  journal = {Journal of Data},
  doi = {10.1000/xyz123},
  year = {2020}
}"""


def test_complete_run_stamps_and_reports(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=CLEAN_KUHN, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = json.loads(
        (rd / "intermediate_files" / "json" / "evidence_report.json")
        .read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    stamps = report["stamps"]["literature-domain-1.bib"]
    assert stamps["kuhn1962structure"] == "EVIDENCE-EXISTENCE"
    att = report["attestations"]["literature-domain-1.bib"]["kuhn1962structure"]
    assert att["api_matched"] is True and att["verified_identifier"] == "publisher"
    assert att["verified_identifier_value"] == "university of chicago press"
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "EVIDENCE-EXISTENCE" in content
    assert "INCOMPLETE" not in content and "no-abstract" not in content


def test_missing_slug_file_degrades(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=CLEAN_KUHN, enrichment=EMPTY_ENRICH)
    # domain 2 complete except: no encyclopedia_entries-domain-2.json
    _domain(rd, 2, POPPER, cleaning=_cleaning(2, CLEAN_POPPER_ENTRIES),
            enrichment=_enrichment(2), slugs=None)
    r = _run(rd, 2)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["2"]["slug_file"] == "missing"
    # domain 2 entries still stamped (only demotion possible)
    content2 = (rd / "literature-domain-2.bib").read_text(encoding="utf-8")
    assert "EVIDENCE-EXISTENCE" in content2
    assert report["stamps"]["literature-domain-2.bib"]["popper1959logic"] == (
        "EVIDENCE-EXISTENCE")


def test_malformed_ledger_degrades_and_demotes(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, DOI_ENTRY, enrichment=EMPTY_ENRICH)
    (rd / "intermediate_files" / "json"
     / "cleaning_ledger-literature-domain-1.json").write_text(
        "{this is not json", encoding="utf-8")
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["1"]["cleaning_ledger"] == "malformed"
    # entry has a plausible doi but no attestation -> NONE, never EXISTENCE
    assert report["stamps"]["literature-domain-1.bib"]["smith2020data"] == (
        "EVIDENCE-NONE")
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "EVIDENCE-NONE" in content and "EVIDENCE-EXISTENCE" not in content


def test_no_bibs_fails_closed(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, None)  # slug file only; no literature-domain-1.bib
    r = _run(rd, 1)
    assert r.returncode == 1
    report = _report(rd)
    assert report["status"] == "failed"
    assert json.loads(r.stdout)["status"] == "failed"
    assert not list(rd.glob("*.bib"))  # nothing was created or stamped


def test_nonzero_exit_stamps_nothing(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, None)  # domain 1 has no bib -> run must fail
    # stray decoy NOT in the manifest (domains=1): must not be read or stamped
    (rd / "literature-domain-9.bib").write_text(KUHN, encoding="utf-8")
    r = _run(rd, 1)
    assert r.returncode == 1
    report = _report(rd)
    assert report["status"] == "failed"
    decoy = (rd / "literature-domain-9.bib").read_text(encoding="utf-8")
    assert decoy == KUHN  # byte-identical: no-glob invariant
    assert "literature-domain-9.bib" not in report.get("stamps", {})


def test_fabricated_context_field_stripped_and_none(tmp_path):
    rd = tmp_path / "review"
    forged = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  sep_context = {FORGED CLAIM ABOUT KUHN},
  publisher = {University of Chicago Press},
  year = {1962}
}"""
    # ledgers present but attest nothing
    _domain(rd, 1, forged, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "FORGED" not in content and "sep_context" not in content
    report = _report(rd)
    assert report["stamps"]["literature-domain-1.bib"]["kuhn1962structure"] == (
        "EVIDENCE-NONE")
    assert "EVIDENCE-NONE" in content


def test_web_source_without_a_capture_is_bucketed_and_stays_none(tmp_path):
    """Renamed from test_web_source_count when the flat web_sources_none count
    became a per-outcome breakdown. Note this entry reaches NO network: with no
    capture on disk the pass short-circuits before the existence probe, which is
    what keeps the real-execute() tests offline."""
    rd = tmp_path / "review"
    misc = """@misc{blogpost2024ai,
  author = {Blogger, Some},
  title = {Thoughts on AI},
  url = {https://example.com/ai-post},
  year = {2024}
}"""
    _domain(rd, 1, misc, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["stamps"]["literature-domain-1.bib"]["blogpost2024ai"] == (
        "EVIDENCE-NONE")
    assert report["web_sources"]["no_capture"] == [
        "literature-domain-1.bib:blogpost2024ai"]
    assert report["web_sources"]["gate_passed"] == {"script": 0, "agent": 0}
    summary = json.loads(r.stdout)["web_sources"]
    assert summary["not_promoted"] == 1 and summary["status"] == "complete"


def test_would_be_existence_v4_demotions_listed(tmp_path):
    rd = tmp_path / "review"
    # doi present but api_matched false -> NONE + listed as a v4 demotion
    _domain(rd, 1, DOI_ENTRY,
            cleaning=_cleaning(1, {"smith2020data": {
                "api_matched": False, "verified_identifier": None,
                "verified_identifier_value": None, "entry_type": "article"}}),
            enrichment=_enrichment(1))
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["stamps"]["literature-domain-1.bib"]["smith2020data"] == (
        "EVIDENCE-NONE")
    assert "literature-domain-1.bib:smith2020data" in (
        report["demoted_would_be_existence_v4"])


def test_cleaning_abstention_attests_existence_and_stays_visible(tmp_path):
    """A cleaner abstention attests
    existence (api_matched True + verified DOI), so the entry regains
    EVIDENCE-EXISTENCE - and the refusal itself stays visible in the
    evidence report (the retained half of Option D)."""
    rd = tmp_path / "review"
    _domain(rd, 1, DOI_ENTRY,
            cleaning=_cleaning(1, {"smith2020data": {
                "api_matched": True, "verified_identifier": "doi",
                "verified_identifier_value": "10.1000/xyz123",
                "entry_type": "article",
                "cleaning_abstained": "pooled_year_conflict"}}),
            enrichment=_enrichment(1))
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["stamps"]["literature-domain-1.bib"]["smith2020data"] == (
        "EVIDENCE-EXISTENCE")
    att = report["attestations"]["literature-domain-1.bib"]["smith2020data"]
    assert att["cleaning_abstained"] == "pooled_year_conflict"
    assert report["cleaning_abstained"] == [
        "literature-domain-1.bib:smith2020data"]
    # Attested now, so it must NOT read as a would-be-existence demotion.
    assert "literature-domain-1.bib:smith2020data" not in (
        report["demoted_would_be_existence_v4"])


def test_incomplete_token_stripped(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=CLEAN_KUHN, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "INCOMPLETE" not in content
    assert "no-abstract" not in content
    # topic + importance keywords survive the stamp
    assert "ps" in content and "High" in content


def test_report_is_valid_json_with_schema_version(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=CLEAN_KUHN, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)  # valid JSON or this raises
    assert report["schema_version"] == 2   # corroboration-gated vintage
    # per-entry maps are nested per bib filename, never bare keys
    assert "kuhn1962structure" not in report["stamps"]
    assert isinstance(report["stamps"]["literature-domain-1.bib"], dict)
    assert isinstance(
        report["attestations"]["literature-domain-1.bib"], dict)


def test_same_key_two_domains_no_attestation_transfer(tmp_path):
    # THE collision test: the same citation key in two domains must never
    # share attestations (cross-domain promotion bug).
    rd = tmp_path / "review"
    smith = """@article{smith2020,
  author = {Smith, Anna},
  title = {On Things},
  journal = {Journal of Stuff},
  doi = {10.1000/abc},
  year = {2020}
}"""
    _domain(rd, 1, smith,
            cleaning=_cleaning(1, {"smith2020": {
                "api_matched": False, "verified_identifier": None,
                "verified_identifier_value": None, "entry_type": "article"}}),
            enrichment=_enrichment(1))
    _domain(rd, 2, smith,
            cleaning=_cleaning(2, {"smith2020": {
                "api_matched": True, "verified_identifier": "doi",
                "verified_identifier_value": "10.1000/abc",
                "entry_type": "article"}}),
            enrichment=_enrichment(2))
    r = _run(rd, 2)
    assert r.returncode == 0, r.stderr
    content1 = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    content2 = (rd / "literature-domain-2.bib").read_text(encoding="utf-8")
    assert "EVIDENCE-NONE" in content1
    assert "EVIDENCE-EXISTENCE" not in content1
    assert "EVIDENCE-EXISTENCE" in content2
    report = _report(rd)
    assert report["stamps"]["literature-domain-1.bib"]["smith2020"] == (
        "EVIDENCE-NONE")
    assert report["stamps"]["literature-domain-2.bib"]["smith2020"] == (
        "EVIDENCE-EXISTENCE")


def test_ledger_wrong_bib_file_is_malformed(tmp_path):
    rd = tmp_path / "review"
    stale = dict(CLEAN_KUHN, bib_file="literature-domain-9.bib")
    _domain(rd, 1, KUHN, cleaning=stale, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["1"]["cleaning_ledger"] == "malformed"
    # attested-looking entry in a stale/copied ledger stamps NONE
    assert report["stamps"]["literature-domain-1.bib"]["kuhn1962structure"] == (
        "EVIDENCE-NONE")


def test_ledger_wrong_top_level_type_is_malformed_not_crash(tmp_path):
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=[], enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["1"]["cleaning_ledger"] == "malformed"


def test_v2_cleaning_ledger_loads_present(tmp_path):
    rd = tmp_path / "review"
    v2 = dict(CLEAN_KUHN, schema_version=2)
    _domain(rd, 1, KUHN, cleaning=v2, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["domains"]["1"]["cleaning_ledger"] == "present"
    assert report["status"] == "complete"
    assert report["stamps"]["literature-domain-1.bib"]["kuhn1962structure"] == (
        "EVIDENCE-EXISTENCE")


def test_cleaning_ledger_schema_version_3_is_malformed(tmp_path):
    rd = tmp_path / "review"
    v3 = dict(CLEAN_KUHN, schema_version=3)
    _domain(rd, 1, KUHN, cleaning=v3, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["1"]["cleaning_ledger"] == "malformed"


def test_cleaning_ledger_schema_version_string_is_malformed(tmp_path):
    rd = tmp_path / "review"
    # "2" the STRING must not alias to the int 2 -- a strict membership
    # check, not a loose/coerced comparison.
    v_str = dict(CLEAN_KUHN, schema_version="2")
    _domain(rd, 1, KUHN, cleaning=v_str, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["1"]["cleaning_ledger"] == "malformed"


def test_cleaning_ledger_type_confused_schema_version_is_malformed(tmp_path):
    """`in` compares with `==`, so JSON `true` (True == 1) and `1.0` both
    equalled the int 1 and sailed through as a valid version-1 ledger. The
    gate now takes the TYPE first -- `type(v) is int`, NOT isinstance, since
    bool subclasses int."""
    for i, bad in enumerate((True, 1.0)):
        rd = tmp_path / f"review-{i}"
        _domain(rd, 1, KUHN, cleaning=dict(CLEAN_KUHN, schema_version=bad),
                enrichment=EMPTY_ENRICH)
        r = _run(rd, 1)
        assert r.returncode == 0, r.stderr
        report = _report(rd)
        assert report["status"] == "degraded", bad
        assert report["domains"]["1"]["cleaning_ledger"] == "malformed", bad


def test_cleaning_ledger_schema_version_absent_is_malformed(tmp_path):
    rd = tmp_path / "review"
    no_version = {k: v for k, v in CLEAN_KUHN.items() if k != "schema_version"}
    _domain(rd, 1, KUHN, cleaning=no_version, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["1"]["cleaning_ledger"] == "malformed"


def test_v2_entry_with_unverified_fields_passes_validation(tmp_path):
    # The new schema-2 per-entry key (task 3 makes the cleaner write it) is
    # not one the entries-validation loop constrains -- it only ever reads
    # verified_identifier -- so it must ride through unchanged.
    entries = {"kuhn1962structure": dict(
        CLEAN_KUHN["entries"]["kuhn1962structure"],
        unverified_fields=["pages"])}
    v2 = dict(CLEAN_KUHN, schema_version=2, entries=entries)
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=v2, enrichment=EMPTY_ENRICH)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["domains"]["1"]["cleaning_ledger"] == "present"
    assert report["status"] == "complete"
    assert report["stamps"]["literature-domain-1.bib"]["kuhn1962structure"] == (
        "EVIDENCE-EXISTENCE")


def test_unparseable_bib_marked_malformed_and_untouched(tmp_path):
    rd = tmp_path / "review"
    garbage = "@book{broken,\n  author = {Never closed\n"
    _domain(rd, 1, garbage, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    _domain(rd, 2, POPPER, cleaning=_cleaning(2, CLEAN_POPPER_ENTRIES),
            enrichment=_enrichment(2))
    r = _run(rd, 2)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["status"] == "degraded"
    assert report["domains"]["1"]["bib"] == "malformed"
    # excluded domain's file is byte-identical afterwards
    assert (rd / "literature-domain-1.bib").read_text(
        encoding="utf-8") == garbage
    assert "literature-domain-1.bib" not in report["stamps"]
    # the healthy domain is still stamped
    assert "EVIDENCE-EXISTENCE" in (
        rd / "literature-domain-2.bib").read_text(encoding="utf-8")


# --- In-process tests: import evidence_barrier, monkeypatch, call execute ---

def test_heal_abstract_restores_on_hash_match(monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se
    true_text = "The original attested abstract text."
    ledger_entry = {"abstract_source": "s2",
                    "abstract_sha256": se.abstract_hash(true_text)}
    fields = {"title": "T", "author": "Doe, Jane",
              "doi": "10.1/x", "year": "2020",
              "abstract": "The mutated abstract text."}
    monkeypatch.setattr(
        evidence_barrier.eb, "resolve_abstract_for_entry",
        lambda *a, **k: (true_text, "openalex"))
    assert evidence_barrier._heal_abstract(fields, ledger_entry) == true_text


def test_heal_abstract_refuses_on_hash_mismatch(monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    ledger_entry = {"abstract_source": "s2", "abstract_sha256": "0" * 64}
    fields = {"title": "T", "doi": "10.1/x", "abstract": "whatever"}
    monkeypatch.setattr(
        evidence_barrier.eb, "resolve_abstract_for_entry",
        lambda *a, **k: ("some other text", "s2"))
    assert evidence_barrier._heal_abstract(fields, ledger_entry) is None


def test_heal_abstract_never_raises(monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    ledger_entry = {"abstract_source": "s2", "abstract_sha256": "0" * 64}
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry", boom)
    assert evidence_barrier._heal_abstract({"title": "T", "doi": "10.1/x"},
                                           ledger_entry) is None


def test_heal_abstract_never_raises_for_ndpr(monkeypatch):
    """resolve_ndpr_abstract PROPAGATES transport errors since the outage/
    no-match split; the heal path's own wrap is what keeps an NDPR outage
    a failed heal instead of a dead barrier run."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    ledger_entry = {"abstract_source": "ndpr", "abstract_sha256": "0" * 64}
    def boom(*a, **k):
        raise RuntimeError("Network error fetching sitemap")
    monkeypatch.setattr(evidence_barrier.eb, "resolve_ndpr_abstract", boom)
    assert evidence_barrier._heal_abstract({"title": "T", "author": "Doe, J."},
                                           ledger_entry) is None


def test_heal_abstract_uses_ndpr_resolver_for_ndpr_source(monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se
    true_text = "Reviewer summary text from NDPR."
    ledger_entry = {"abstract_source": "ndpr",
                    "abstract_sha256": se.abstract_hash(true_text)}
    monkeypatch.setattr(evidence_barrier.eb, "resolve_ndpr_abstract",
                        lambda *a, **k: (true_text, "ndpr"))
    def fail(*a, **k):
        raise AssertionError("API resolver must not be called for ndpr")
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry", fail)
    fields = {"title": "Book Title", "author": "Doe, Jane"}
    assert evidence_barrier._heal_abstract(fields, ledger_entry) == true_text


def test_heal_abstract_non_dict_ledger_entry_is_none(monkeypatch):
    """Malformed ledger record: never raises."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    def fail(*a, **k):
        raise AssertionError("no fetch may happen for a malformed record")
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry", fail)
    assert evidence_barrier._heal_abstract({"title": "T"}, "garbage") is None
    assert evidence_barrier._heal_abstract({"title": "T"}, None) is None


def test_heal_abstract_missing_source_is_none(monkeypatch):
    """A record with a hash but no abstract_source cannot be healed
    (the restored field could not satisfy attest_abstract anyway)."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    def fail(*a, **k):
        raise AssertionError("no fetch without a recorded source")
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry", fail)
    assert evidence_barrier._heal_abstract(
        {"title": "T"}, {"abstract_sha256": "0" * 64}) is None


# Real fetch_sep.py article shape: sections keyed by id with
# {"id", "title", "content"}; bibliography items {"raw", "parsed", "confidence"}.
KUHN_ARTICLE = {
    "entry_name": "test-entry",
    "title": "Test Entry",
    "preamble": "",
    "sections": {"2": {"id": "2", "title": "Paradigms", "content":
                 "In his landmark study, Kuhn (1962) argues that normal "
                 "science proceeds under a paradigm until anomalies "
                 "accumulate."}},
    "bibliography": [{"raw": "Kuhn, T., 1962, The Structure of Scientific "
                             "Revolutions, University of Chicago Press.",
                      "parsed": None, "confidence": "low"}],
}


def test_acquisition_integration_end_to_end(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se
    rd = tmp_path / "review"
    forged = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  sep_context = {FORGED PRE-EXISTING CLAIM},
  publisher = {University of Chicago Press},
  year = {1962}
}"""
    _domain(rd, 1, forged, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1),
            slugs='{"sep_entries": ["test-entry"], "iep_entries": []}')
    monkeypatch.setattr(
        evidence_barrier.rc, "fetch_articles",
        lambda union, debug=False: ({"sep:test-entry": KUHN_ARTICLE}, []))
    rc_code = evidence_barrier.execute(rd, 1)
    assert rc_code == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    # forged value is gone; driver-written sep_context is present
    assert "FORGED" not in content
    assert "sep_context" in content
    assert "normal science" in content
    assert "EVIDENCE-CONTEXT" in content
    report = _report(rd)
    assert report["stamps"]["literature-domain-1.bib"]["kuhn1962structure"] == (
        "EVIDENCE-CONTEXT")
    acq = report["acquisition"]["literature-domain-1.bib"]["kuhn1962structure"]
    assert acq["outcome"] == "matched"
    assert acq["encyclopedia"] == "sep" and acq["slug"] == "test-entry"
    assert acq["match_score"] == 1.0
    assert acq["section"] == "2"
    assert "value" not in acq  # value lives in the bib; report carries hash
    att = report["attestations"]["literature-domain-1.bib"]["kuhn1962structure"]
    assert att["context_written"] is True
    assert att["context_field"] == "sep_context"
    # value binding: the hash in the report matches the written field value
    fields = se.parse_entry_fields(content)
    assert att["context_sha256"] == se.abstract_hash(fields["sep_context"])


def test_report_write_failure_stamps_nothing(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=CLEAN_KUHN, enrichment=EMPTY_ENRICH)
    before = (rd / "literature-domain-1.bib").read_bytes()
    real_replace = os.replace

    def fake_replace(src, dst):
        if Path(dst).name == "evidence_report.json":
            raise OSError("disk full")
        return real_replace(src, dst)

    monkeypatch.setattr(evidence_barrier.os, "replace", fake_replace)
    rc_code = evidence_barrier.execute(rd, 1)
    assert rc_code == 1
    # report-before-stamp ordering: the bib is byte-identical
    assert (rd / "literature-domain-1.bib").read_bytes() == before
    assert not (rd / "intermediate_files" / "json"
                / "evidence_report.json").exists()


def test_barrier_heals_mutated_abstract_end_to_end(tmp_path, monkeypatch):
    """A post-attestation mutation (root cause 2) is healed at the barrier:
    text restored, EVIDENCE-ABSTRACT stamped, report records the heal."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    true_text = ("Open access to data is predicated on assumptions "
                 "that data can be reused. (See Supplementary Materials.)")
    mutated = ("Open access to data is predicated on assumptions "
               "that data can be reused.")
    bib = ('@article{pasq2019,\n'
           '  abstract_source = {s2},\n'
           f'  abstract = {{{mutated}}},\n'
           '  author = {Pasquetto, Irene V.},\n'
           '  title = {Uses and Reuses},\n'
           '  doi = {10.1162/99608f92.fc14bf2d},\n'
           '  year = {2019},\n'
           '  keywords = {data-reuse, Medium}\n'
           '}')
    enrichment = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                  "entries": {"pasq2019": {
                      "abstract_source": "s2",
                      "abstract_sha256": se.abstract_hash(true_text)}}}
    cleaning = _cleaning(1, {"pasq2019": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1162/99608f92.fc14bf2d",
        "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning, enrichment=enrichment)

    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (true_text, "s2"))

    rc_code = evidence_barrier.execute(tmp_path, 1)
    assert rc_code == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    assert report["healed"]["literature-domain-1.bib"]["pasq2019"] == {
        "outcome": "restored", "source": "s2"}
    assert report["stamps"]["literature-domain-1.bib"]["pasq2019"] == "EVIDENCE-ABSTRACT"
    out = (tmp_path / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert true_text in out
    assert mutated + "}" not in out          # old truncated text replaced
    assert out.lower().count("abstract =") == 1


def test_barrier_unhealed_mismatch_still_demotes(tmp_path, monkeypatch):
    """Fetched text that fails the ledger hash must NOT be written; the
    entry demotes exactly as before the heal feature (fail-closed)."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    bib = ('@article{pasq2019,\n'
           '  abstract_source = {s2},\n'
           '  abstract = {mutated text},\n'
           '  author = {Pasquetto, Irene V.},\n'
           '  title = {Uses and Reuses},\n'
           '  doi = {10.1162/99608f92.fc14bf2d},\n'
           '  year = {2019},\n'
           '  keywords = {data-reuse, Medium}\n'
           '}')
    enrichment = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                  "entries": {"pasq2019": {
                      "abstract_source": "s2", "abstract_sha256": "0" * 64}}}
    cleaning = _cleaning(1, {"pasq2019": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1162/99608f92.fc14bf2d",
        "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning, enrichment=enrichment)
    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: ("wrong text entirely", "s2"))
    assert evidence_barrier.execute(tmp_path, 1) == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    assert report["healed"]["literature-domain-1.bib"]["pasq2019"]["outcome"] == "unhealed"
    assert report["stamps"]["literature-domain-1.bib"]["pasq2019"] == "EVIDENCE-EXISTENCE"
    assert "mutated text" in (tmp_path / "literature-domain-1.bib").read_text(encoding="utf-8")


def test_barrier_no_heal_attempt_without_ledger_record(tmp_path, monkeypatch):
    """mcallister-shape (no ledger record at all): the barrier must not
    fetch -- there is no attested hash to heal toward."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    bib = ('@article{mc2011,\n'
           '  abstract = {hand-written text},\n'
           '  abstract_source = {semantic_scholar},\n'
           '  author = {McAllister, James W.},\n'
           '  title = {Patterns},\n'
           '  doi = {10.1007/s11229-009-9613-x},\n'
           '  year = {2009},\n'
           '  keywords = {patterns, Medium}\n'
           '}')
    cleaning = _cleaning(1, {"mc2011": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1007/s11229-009-9613-x",
        "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning,
            enrichment={"schema_version": 1,
                        "bib_file": "literature-domain-1.bib", "entries": {}})
    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    def fail(*a, **k):
        raise AssertionError("no heal fetch may happen without a ledger record")
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry", fail)
    assert evidence_barrier.execute(tmp_path, 1) == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    assert report["healed"].get("literature-domain-1.bib", {}) == {}
    assert report["stamps"]["literature-domain-1.bib"]["mc2011"] == "EVIDENCE-EXISTENCE"


def test_barrier_heals_quoted_style_bib_two_entries(tmp_path, monkeypatch):
    """The Task 1 x Task 4 interaction the wild data actually has: a
    pybtex-QUOTED bib (cleaner round-trip style), TWO entries in one
    domain -- one heals, one stays unhealed. Catches (a) quoted-value
    replacement inside run_barrier (no duplicate fields), (b) any
    (i, key) skew between the attestation and output loops, and (c)
    healed entries skipping context acquisition."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    true_text = "The original attested abstract, full and intact."
    bib = ('@article{healme2020,\n'
           '    author = "Doe, Jane",\n'
           '    title = "Healable",\n'
           '    doi = "10.1/heal",\n'
           '    year = "2020",\n'
           '    abstract = "mutated remnant",\n'
           '    abstract_source = "s2",\n'
           '    keywords = "topic, High"\n'
           '}\n'
           '\n'
           '@article{leaveme2021,\n'
           '    author = "Roe, Riley",\n'
           '    title = "Unhealable",\n'
           '    doi = "10.1/leave",\n'
           '    year = "2021",\n'
           '    abstract = "also mutated",\n'
           '    abstract_source = "s2",\n'
           '    keywords = "topic, Medium"\n'
           '}')
    enrichment = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                  "entries": {
                      "healme2020": {"abstract_source": "s2",
                                     "abstract_sha256": se.abstract_hash(true_text)},
                      "leaveme2021": {"abstract_source": "s2",
                                      "abstract_sha256": "0" * 64}}}
    cleaning = _cleaning(1, {
        "healme2020": {"api_matched": True, "verified_identifier": "doi",
                       "verified_identifier_value": "10.1/heal",
                       "entry_type": "article"},
        "leaveme2021": {"api_matched": True, "verified_identifier": "doi",
                        "verified_identifier_value": "10.1/leave",
                        "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning, enrichment=enrichment)
    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (true_text, "s2"))
    assert evidence_barrier.execute(tmp_path, 1) == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    stamps = report["stamps"]["literature-domain-1.bib"]
    assert stamps["healme2020"] == "EVIDENCE-ABSTRACT"
    assert stamps["leaveme2021"] == "EVIDENCE-EXISTENCE"
    # healed entries skip context acquisition
    assert report["acquisition"]["literature-domain-1.bib"]["healme2020"] == {
        "outcome": "not-needed"}
    out = (tmp_path / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert true_text in out
    assert out.lower().count("abstract =") == 2          # no duplicates
    assert "also mutated" in out                          # unhealed untouched
    # restored text landed ONLY in the healed entry
    healme_chunk = out.split("@article{leaveme2021")[0]
    assert true_text in healme_chunk


def test_barrier_heals_deleted_abstract_field(tmp_path, monkeypatch):
    """A re-emission that DELETED the abstract outright (ABSTRACT-GONE
    shape): the heal must re-insert the field (insert branch, not
    replace) and stamp EVIDENCE-ABSTRACT."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se
    true_text = "The abstract a re-emission deleted."
    bib = ('@article{gone2020,\n'
           '  author = {Doe, Jane},\n'
           '  title = {Gone},\n'
           '  doi = {10.1/gone},\n'
           '  year = {2020},\n'
           '  abstract_source = {s2},\n'
           '  keywords = {topic, High}\n'
           '}')
    enrichment = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                  "entries": {"gone2020": {
                      "abstract_source": "s2",
                      "abstract_sha256": se.abstract_hash(true_text)}}}
    cleaning = _cleaning(1, {"gone2020": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1/gone", "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning, enrichment=enrichment)
    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (true_text, "s2"))
    assert evidence_barrier.execute(tmp_path, 1) == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    assert report["stamps"]["literature-domain-1.bib"]["gone2020"] == "EVIDENCE-ABSTRACT"
    assert true_text in (tmp_path / "literature-domain-1.bib").read_text(encoding="utf-8")


# --- Fix-verification tests ------------------------------------------------

def test_barrier_heals_two_level_nested_mutated_abstract_end_to_end(tmp_path, monkeypatch):
    """The original reproduction case, run end-to-end through the
    REAL (fixed) add_field_to_entry -- no monkeypatch of the splice itself.
    The CURRENT (mutated) abstract is nested two levels deep, which the
    old shallow-nesting regex silently failed to locate, falling through
    to the insert branch and leaving a duplicate `abstract =` field (a
    file pybtex rejects) with a FALSE EVIDENCE-ABSTRACT stamp. With the
    depth-counting locator, this must heal cleanly: single field, restored
    text, parseable output."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    true_text = "The plain original abstract, no braces at all."
    mutated = "We show {\\it Kant's {a priori}} fails."
    bib = ('@article{nested2020,\n'
           '  author = {Doe, Jane},\n'
           '  title = {Nested},\n'
           '  doi = {10.1/nested},\n'
           '  year = {2020},\n'
           f'  abstract = {{{mutated}}},\n'
           '  abstract_source = {s2},\n'
           '  keywords = {topic, High}\n'
           '}')
    enrichment = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                  "entries": {"nested2020": {
                      "abstract_source": "s2",
                      "abstract_sha256": se.abstract_hash(true_text)}}}
    cleaning = _cleaning(1, {"nested2020": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1/nested", "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning, enrichment=enrichment)
    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (true_text, "s2"))
    assert evidence_barrier.execute(tmp_path, 1) == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    assert report["healed"]["literature-domain-1.bib"]["nested2020"] == {
        "outcome": "restored", "source": "s2"}
    assert report["stamps"]["literature-domain-1.bib"]["nested2020"] == "EVIDENCE-ABSTRACT"
    out = (tmp_path / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert true_text in out
    assert "Kant" not in out
    assert out.count("abstract =") == 1  # no duplicate field
    from pybtex.database import parse_string
    parse_string(out, bib_format="bibtex")  # must not raise


def test_barrier_guard_drops_heal_on_unbalanced_restored_value(tmp_path, monkeypatch):
    """Even after the depth-counting locator fix, a restored value that
    itself contains an unbalanced brace (a malformed API response, say)
    would splice into a syntactically broken chunk that the field-count
    check alone can't see (count is still exactly 1). The Task-4-local
    well-formedness guard must catch this via the pybtex parseability
    check, drop the heal, demote the entry, and correct the report."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    # The ledger attests exactly this (unbalanced) text -- hash-gated
    # legitimacy, independent of whether it happens to be well-formed.
    broken_text = "Restored text with a rogue { brace."
    bib = ('@article{broken2020,\n'
           '  author = {Doe, Jane},\n'
           '  title = {Broken},\n'
           '  doi = {10.1/broken},\n'
           '  year = {2020},\n'
           '  abstract = {mutated text},\n'
           '  abstract_source = {s2},\n'
           '  keywords = {topic, High}\n'
           '}')
    enrichment = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                  "entries": {"broken2020": {
                      "abstract_source": "s2",
                      "abstract_sha256": se.abstract_hash(broken_text)}}}
    cleaning = _cleaning(1, {"broken2020": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1/broken", "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning, enrichment=enrichment)
    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (broken_text, "s2"))
    assert evidence_barrier.execute(tmp_path, 1) == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    assert report["healed"]["literature-domain-1.bib"]["broken2020"] == {
        "outcome": "unhealed", "source": "s2"}
    assert report["stamps"]["literature-domain-1.bib"]["broken2020"] == "EVIDENCE-EXISTENCE"
    out = (tmp_path / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert out.count("abstract =") == 1
    assert "mutated text" in out          # original text left in place
    assert "rogue" not in out             # broken restore never landed
    from pybtex.database import parse_string
    parse_string(out, bib_format="bibtex")  # must not raise


def test_barrier_rederivation_demotes_when_splice_is_noop(tmp_path, monkeypatch):
    """Regression coverage for the defense-in-depth re-derivation line
    with add_field_to_entry monkeypatched to a no-op,
    the heal splice never lands, yet the attestation-loop flag was set
    True when the fetch hash-matched. The FINAL text must be what decides
    the stamp: demoted to EVIDENCE-EXISTENCE with abstract_attested False.
    Deleting `att.abstract_attested = se.attest_abstract(...)` in the
    output-build loop turns this test red (confirmed by hand)."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    true_text = "The original attested abstract text, restored."
    bib = ('@article{pasq2019,\n'
           '  abstract_source = {s2},\n'
           '  abstract = {mutated text},\n'
           '  author = {Pasquetto, Irene V.},\n'
           '  title = {Uses and Reuses},\n'
           '  doi = {10.1162/99608f92.fc14bf2d},\n'
           '  year = {2019},\n'
           '  keywords = {data-reuse, Medium}\n'
           '}')
    enrichment = {"schema_version": 1, "bib_file": "literature-domain-1.bib",
                  "entries": {"pasq2019": {
                      "abstract_source": "s2",
                      "abstract_sha256": se.abstract_hash(true_text)}}}
    cleaning = _cleaning(1, {"pasq2019": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1162/99608f92.fc14bf2d",
        "entry_type": "article"}})
    _domain(tmp_path, 1, bib, cleaning=cleaning, enrichment=enrichment)
    monkeypatch.setattr(evidence_barrier.rc, "fetch_articles",
                        lambda slugs, debug=False: ({}, []))
    monkeypatch.setattr(evidence_barrier.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (true_text, "s2"))
    # The splice never lands: add_field_to_entry becomes a no-op. (The
    # attestation loop already recorded "restored" -- production code
    # never no-ops here, so the report keeping that label is an accepted
    # test-only residual; what this test pins is the STAMP outcome.)
    monkeypatch.setattr(evidence_barrier, "add_field_to_entry",
                        lambda text, *a, **k: text)

    assert evidence_barrier.execute(tmp_path, 1) == 0
    report = json.loads((tmp_path / "intermediate_files" / "json"
                         / "evidence_report.json").read_text(encoding="utf-8"))
    assert report["stamps"]["literature-domain-1.bib"]["pasq2019"] == "EVIDENCE-EXISTENCE"
    att = report["attestations"]["literature-domain-1.bib"]["pasq2019"]
    assert att["abstract_attested"] is False


# --- Venue vetting ---

TWO_VENUE_BIB = """@article{okoro2021ai,
  author = {Okoro, Ada},
  title = {Agency and Machines},
  journal = {Advanced International Journal for Research},
  year = {2021}
}

@article{smith2020data,
  author = {Smith, Anna},
  title = {Data and Things},
  journal = {Synthese},
  year = {2020}
}"""


def _raise_on_field(field_name):
    """A drop-in add_field_to_entry that blows up on ONE field, so a stamping
    bug can be simulated without breaking context/heal splices."""
    real = None

    def _wrapped(entry_text, name, value):
        if name == field_name:
            raise RuntimeError("splice bug")
        return real(entry_text, name, value)

    import evidence_barrier as _eb
    real = _eb.add_field_to_entry
    return _wrapped


def _fake_vet(flagged=(), status="complete", seen=None):
    """A vet_venues stand-in. `flagged` holds NORMALIZED venue names."""
    def _vet(names):
        if seen is not None:
            seen.append(list(names))
        return {"status": status, "reason": None, "looked_up": len(names),
                "cache_hits": 0, "skipped_cap": 0, "flagged": sorted(flagged),
                "evidence": {v: {"h_index": 2, "resolved": True} for v in flagged},
                "verdicts": {"advanced international journal for research":
                             "advanced international journal for research" in flagged,
                             "synthese": "synthese" in flagged}}
    return _vet


def test_venue_flag_stamped_on_flagged_entry_only(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    monkeypatch.setattr(
        evidence_barrier.vv, "vet_venues",
        _fake_vet(flagged=["advanced international journal for research"]))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "venue_status = {low-visibility}" in content
    assert content.count("venue_status") == 1  # never the Synthese entry
    okoro_chunk = [c for c in content.split("\n@") if "okoro2021ai" in c][0]
    assert "venue_status" in okoro_chunk
    report = _report(rd)
    assert report["venue_vetting"]["status"] == "complete"
    assert report["venue_vetting"]["flagged_entries"] == 1


def test_venue_vetting_failure_never_fails_the_barrier(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))

    def boom(names):
        raise RuntimeError("openalex down")

    monkeypatch.setattr(evidence_barrier.vv, "vet_venues", boom)
    assert evidence_barrier.execute(rd, 1) == 0          # NOT a failed run
    report = _report(rd)
    assert report["status"] in ("complete", "degraded")
    assert report["venue_vetting"]["status"] == "error"
    assert "openalex down" in report["venue_vetting"]["error"]
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "venue_status" not in content


def test_venue_vetting_skipped_without_key_is_recorded(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues",
                        _fake_vet(flagged=[], status="skipped"))
    assert evidence_barrier.execute(rd, 1) == 0
    report = _report(rd)
    assert report["venue_vetting"]["status"] == "skipped"
    assert report["venue_vetting"]["flagged_entries"] == 0


def test_venue_flag_does_not_change_evidence_tiers(tmp_path, monkeypatch):
    """venue_status is not an evidence signal: the same review must stamp the
    same EVIDENCE-* tiers with and without a flag.

    Both TWO_VENUE_BIB entries sit at EVIDENCE-NONE, the floor tier -- a
    plain dict-equality check on that alone cannot detect a demotion, since
    there is nowhere lower to fall. smith2020data (journal Synthese, the
    entry that gets flagged in the "on" case below) is given a verified DOI
    here so it reaches EVIDENCE-EXISTENCE, giving the comparison somewhere
    real to fall from.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    bib = TWO_VENUE_BIB.replace(
        "  journal = {Synthese},",
        "  journal = {Synthese},\n  doi = {10.1000/xyz123},")
    cleaning = _cleaning(1, {"smith2020data": {
        "api_matched": True, "verified_identifier": "doi",
        "verified_identifier_value": "10.1000/xyz123", "entry_type": "article"}})
    tiers = {}
    for label, vet in (("off", _fake_vet(flagged=[], status="skipped")),
                       ("on", _fake_vet(flagged=["synthese"]))):
        rd = tmp_path / f"review-{label}"
        _domain(rd, 1, bib, cleaning=cleaning, enrichment=_enrichment(1))
        monkeypatch.setattr(evidence_barrier.vv, "vet_venues", vet)
        assert evidence_barrier.execute(rd, 1) == 0
        tiers[label] = _report(rd)["stamps"]["literature-domain-1.bib"]
    # Confirm the setup actually reaches a non-floor tier -- otherwise the
    # equality check below would pass vacuously even with a demotion bug.
    assert tiers["off"]["smith2020data"] == "EVIDENCE-EXISTENCE"
    assert tiers["off"] == tiers["on"]


def test_stale_venue_status_is_removed_when_the_venue_is_now_clear(tmp_path, monkeypatch):
    """The barrier OWNS venue_status: a flag from an earlier run must not
    survive a run that no longer flags the venue."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    stale = TWO_VENUE_BIB.replace(
        "  journal = {Synthese},",
        "  journal = {Synthese},\n  venue_status = {low-visibility},")
    _domain(rd, 1, stale, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues", _fake_vet(flagged=[]))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "venue_status" not in content
    assert "journal = {Synthese}" in content     # the neighbour survives intact


def test_stale_venue_status_is_removed_when_vetting_is_skipped(tmp_path, monkeypatch):
    """No API key must not mean "keep yesterday's discredit"."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    stale = TWO_VENUE_BIB.replace(
        "  journal = {Synthese},",
        "  journal = {Synthese},\n  venue_status = {low-visibility},")
    _domain(rd, 1, stale, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues",
                        _fake_vet(flagged=[], status="skipped"))
    assert evidence_barrier.execute(rd, 1) == 0
    assert "venue_status" not in (rd / "literature-domain-1.bib").read_text(
        encoding="utf-8")


def test_hand_written_venue_status_is_removed(tmp_path, monkeypatch):
    """A hand-written venue_status is stripped before the pass and only
    re-added on this run's own verdict. The quoted form here; bare, nested
    and non-line-initial shapes are covered by
    test_strip_reaches_bare_nested_and_compact_derived_fields."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    forged = TWO_VENUE_BIB.replace(
        "  journal = {Synthese},",
        '  journal = {Synthese},\n  venue_status = "hand written nonsense",')
    _domain(rd, 1, forged, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues", _fake_vet(flagged=[]))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "hand written nonsense" not in content
    assert "venue_status" not in content


def test_stamp_failure_does_not_fail_the_barrier(tmp_path, monkeypatch):
    """The optional splice is inside the safety boundary too."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(
        evidence_barrier.vv, "vet_venues",
        _fake_vet(flagged=["advanced international journal for research"]))
    monkeypatch.setattr(evidence_barrier, "add_field_to_entry",
                        _raise_on_field("venue_status"))
    assert evidence_barrier.execute(rd, 1) == 0
    report = _report(rd)
    assert report["status"] in ("complete", "degraded")
    assert "venue_status" not in (rd / "literature-domain-1.bib").read_text(
        encoding="utf-8")


def test_non_serializable_vet_venues_return_never_fails_the_barrier(
        tmp_path, monkeypatch):
    """Regression pin: report["venue_vetting"] gets json.dumps'd whole in
    execute(), gated only on OSError there -- a non-serializable value
    anywhere in vet_venues's return (a stray object under "evidence", say)
    would otherwise escape execute() as an uncaught TypeError: no stdout
    summary, no report written, and the bibs never written either, since
    they are gated on the report write succeeding. That is strictly worse
    than a recorded "error" status. venue_names is non-empty here (TWO_
    VENUE_BIB has two journal-bearing entries), so this exercises the
    round-trip on the path THROUGH the verdict-mapping loop, not just the
    empty-venue_names path test_non_dict_vet_venues_return_with_no_journals_
    never_fails_the_barrier already covers."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    bad = {"status": "complete", "verdicts": {}, "evidence": {"x": object()}}
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues", lambda names: bad)
    assert evidence_barrier.execute(rd, 1) == 0          # NOT a failed run
    report = _report(rd)
    assert report["status"] in ("complete", "degraded")
    assert report["venue_vetting"]["status"] == "error"
    assert report["venue_vetting"]["flagged_entries"] == 0


def test_only_journal_bearing_entries_are_vetted(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    mixed = TWO_VENUE_BIB.replace(
        "journal = {Advanced International Journal for Research},",
        "howpublished = {arXiv:2101.00001},")
    _domain(rd, 1, mixed, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    seen = []
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues",
                        _fake_vet(flagged=[], seen=seen))
    assert evidence_barrier.execute(rd, 1) == 0
    assert seen == [["Synthese"]]   # raw journal names, deduped and sorted


def test_non_dict_vet_venues_return_with_no_journals_never_fails_the_barrier(
        tmp_path, monkeypatch):
    """Regression pin for a self-review finding: when NO entry has a journal
    field, the verdict-mapping loop never runs, so it never touches a
    malformed `vet_venues` return -- the stamped-count assignment must be
    inside the same try/except as everything else, or a non-dict return
    reaches an unguarded subscript and fails the whole barrier."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    book_only = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  publisher = {University of Chicago Press},
  year = {1962}
}"""
    _domain(rd, 1, book_only, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues", lambda names: None)
    assert evidence_barrier.execute(rd, 1) == 0          # NOT a failed run
    report = _report(rd)
    assert report["status"] in ("complete", "degraded")
    assert report["venue_vetting"]["status"] == "error"
    assert report["venue_vetting"]["flagged_entries"] == 0


def test_no_ambient_openalex_key_during_tests():
    """Pins tests/conftest.py's session-scoped isolation fixture: venue
    vetting
    put a real-network OpenAlex pass inside evidence_barrier.py, and the
    barrier's subprocess-driven tests above (_run()) inherit the parent
    environment verbatim, so a developer's real key must never be visible
    to the suite -- it would otherwise spend real, metered OpenAlex budget
    on every run. Tests that need the key still can via
    monkeypatch.setenv(...); this only pins that nothing sets it ambiently.

    Deliberately checked via a bound local, never a bare
    `os.environ.get(...)` inside the assert: pytest's assertion rewriting
    reprs every sub-expression on failure, and reprs `os.environ.get`'s
    bound `__self__` as the WHOLE environment dict -- which on a real
    developer machine holds several other live API keys. A failure here
    must say the key leaked, not reprint every secret in the process.
    """
    import os
    key_is_set = "OPENALEX_API_KEY" in os.environ
    assert key_is_set is False, "OPENALEX_API_KEY is set in the test environment"


# --- Chicago a/b suffixes ---

MENARY_D1 = """@incollection{menary2010cognitive,
  author = {Menary, Richard},
  title = {Cognitive Integration and the Extended Mind},
  booktitle = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/1.001},
  year = {2010}
}

@book{menary2010extended,
  author = {Menary, Richard},
  title = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/2.002},
  year = {2010}
}"""

MENARY_D2 = """@incollection{menaryCogIntegration,
  author = {Menary, Richard},
  title = {Cognitive Integration and the Extended Mind},
  booktitle = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/1.001},
  year = {2010}
}"""


def test_same_author_same_year_gets_letters(tmp_path):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, MENARY_D1, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix = {a}" in content
    assert "year_suffix = {b}" in content
    # The `year` field itself is untouched -- the \\d{4} guards downstream
    # depend on it.
    assert "year = {2010}" in content
    assert "2010a" not in content
    report = _report(rd)
    assert report["year_suffixes"]["assigned"] == 2


def test_same_work_in_two_domains_gets_the_same_letter(tmp_path):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, MENARY_D1, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    _domain(rd, 2, MENARY_D2, cleaning=_cleaning(2, {}), enrichment=_enrichment(2))
    assert evidence_barrier.execute(rd, 2) == 0
    d1 = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    d2 = (rd / "literature-domain-2.bib").read_text(encoding="utf-8")
    chunk1 = [c for c in d1.split("\n@") if "menary2010cognitive" in c][0]
    chunk2 = [c for c in d2.split("\n@") if "menaryCogIntegration" in c][0]
    letter1 = chunk1.split("year_suffix = {")[1][0]
    letter2 = chunk2.split("year_suffix = {")[1][0]
    assert letter1 == letter2


def test_single_work_year_gets_no_suffix(tmp_path):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, KUHN, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    assert "year_suffix" not in (rd / "literature-domain-1.bib").read_text(encoding="utf-8")


def test_suffix_failure_never_fails_the_barrier(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    def boom(entries):
        raise RuntimeError("assignment blew up")

    monkeypatch.setattr(evidence_barrier.ys, "assign_suffixes", boom)
    rd = tmp_path / "review"
    _domain(rd, 1, MENARY_D1, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    report = _report(rd)
    assert report["status"] in ("complete", "degraded")
    assert report["year_suffixes"]["status"] == "error"
    assert "year_suffix" not in (rd / "literature-domain-1.bib").read_text(encoding="utf-8")


def test_suffix_does_not_change_evidence_tiers(tmp_path):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, MENARY_D1, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    stamps = _report(rd)["stamps"]["literature-domain-1.bib"]
    assert set(stamps.values()) == {"EVIDENCE-NONE"}   # unattested, as before


def test_overflow_group_is_named_in_the_report_and_gets_no_letters(tmp_path):
    """27 distinct works by the same author in the same year is one past the
    26-letter cap: the group must NEVER be partially lettered (see
    year_suffix.py's own reasoning), and per the coordinator's fix to a
    reporting bug in this pass, the report must NAME the group -- author,
    year, work count -- not just note that something overflowed. Pins the
    regression: an earlier revision wrapped `assignment["overflow"]` (a list
    of dicts) in `[list(x) for x in ...]`, which for a dict yields its KEY
    NAMES ("authors", "year", "works") instead of the actual values,
    silently defeating the whole point of reporting an unlettered group."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    entries = "\n\n".join(
        f"""@book{{overflow{i:02d}2025,
  author = {{Prolific, Pat}},
  title = {{Overflow Work {i:02d}}},
  publisher = {{Overflow Press}},
  year = {{2025}}
}}"""
        for i in range(27)
    )
    _domain(rd, 1, entries, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix" not in content   # no entry in the group gets a letter
    report = _report(rd)
    assert report["year_suffixes"]["assigned"] == 0
    assert report["year_suffixes"]["overflow"] == [
        {"authors": "Prolific, Pat", "year": "2025", "works": 27}]


SUPPRESSED_D1 = """@incollection{menary2010cognitive,
  author = {Menary, Richard},
  title = {Cognitive Integration and the Extended Mind},
  booktitle = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/1.001},
  year = {2010}
}

@book{menary2010extended,
  author = {Menary, Richard},
  title = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/2.002},
  year = {2010}
}

@incollection{menaryUndated,
  author = {Menary, Richard},
  title = {Cognitive Integration and the Extended Mind},
  booktitle = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/1.001},
  year = {n.d.}
}"""


def test_suppressed_group_is_named_in_the_report(tmp_path):
    """A group the assigner suppresses whole must be REPORTED, for the same
    reason an overflow group must be: the bib comes back with no letters and
    nothing else says why.

    Here a third copy of the first work carries year "n.d.", so the usability
    filter drops it while it still shares a DOI with a usable sibling. The
    assigner refuses to letter only part of a work's copies, so it suppresses
    the whole (Menary, 2010) group -- correct, but silent unless the barrier
    passes `suppressed` through.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, SUPPRESSED_D1, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix" not in content   # no member of the group gets a letter
    report = _report(rd)
    assert report["year_suffixes"]["assigned"] == 0
    suppressed = report["year_suffixes"]["suppressed"]
    assert len(suppressed) == 1
    rec = suppressed[0]
    # Exact values, not key names -- the same shape of reporting bug that
    # `overflow` carried (a dict wrapped in list() yields its KEY NAMES).
    assert rec["authors"] == "Menary, Richard"
    assert rec["year"] == "2010"
    assert rec["reasons"] == ["filtered_copy"]
    # `works` is documented in year_suffix.assign_suffixes as best-effort
    # telemetry rather than a cross-order-stable exact count, so pin only
    # that it counts a real group rather than the precise number.
    assert rec["works"] >= 2


def test_suffix_error_path_still_carries_every_list_key(tmp_path, monkeypatch):
    """The error branch must expose the same keys as the complete branch.
    A consumer reading report["year_suffixes"]["suppressed"] would otherwise
    KeyError on the error path only -- the path that gets the least testing.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    def boom(entries):
        raise RuntimeError("assignment blew up")

    monkeypatch.setattr(evidence_barrier.ys, "assign_suffixes", boom)
    rd = tmp_path / "review"
    _domain(rd, 1, MENARY_D1, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    suffixes = _report(rd)["year_suffixes"]
    assert suffixes["status"] == "error"
    for key in ("groups", "overflow", "suppressed", "conflicts",
                "residual_neutralized", "residual_unresolved"):
        assert suffixes[key] == [], key


# --- A stale COMPACT year_suffix ---
#
# `_strip_derived_fields` used to match only a field OPENING its line, so a
# mid-line or header-line letter survived it. For `venue_status` a survivor
# is a stale metadata problem; for `year_suffix` it is a correctness one,
# because generate_bibliography ACTS on the value. The strip now locates
# fields structurally and reaches these shapes; the fixtures below pin that,
# and -- with the strip monkeypatched to a no-op -- the residual-neutralisation
# pass that remains behind it as defence in depth.

# Two DIFFERENT people sharing a surname and a year: the case the letter
# assigner deliberately refuses to letter (it is a surname collision, resolved
# by first initials). So the assigner writes NOTHING here -- and before the
# fix both stale letters travelled untouched into the output bib, where they
# read as a
# complete a/b group nobody assigned.
STALE_COMPACT_D1 = """@article{johnson2024algorithms,
  author = {Johnson, Gabbrielle},
  title = {Are Algorithms Value-Free},
  journal = {Synthese}, year_suffix = {a}, year = {2024}
}

@article{johnson2024judgement,
  author = {Johnson, Rebecca},
  title = {Automating Judgement},
  journal = {Synthese}, year_suffix = {b}, year = {2024}
}"""

# No whitespace before the field: the shape both the old strip and the old
# `(\s+)year_suffix\s*=` locator in add_field_to_entry missed, so the "add"
# path would have inserted a SECOND one, which pybtex rejects outright.
STALE_NO_SPACE_D1 = """@article{johnson2024algorithms,year_suffix={a},
  author = {Johnson, Gabbrielle},
  title = {Are Algorithms Value-Free},
  journal = {Synthese}, year = {2024}
}"""


def test_stale_compact_year_suffix_is_stripped(tmp_path):
    """The barrier owns this field: a mid-line stale letter is stripped
    before assignment like any other, so nothing is left to neutralise --
    the assigner letters nothing here, and the entries carry no letter."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, STALE_COMPACT_D1, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix" not in content
    suffixes = _report(rd)["year_suffixes"]
    assert suffixes["assigned"] == 0        # the assigner still letters nothing
    assert suffixes["residual_neutralized"] == []
    assert suffixes["residual_unresolved"] == []


def _disable_strip(monkeypatch, evidence_barrier):
    """Defence-in-depth fixture: pretend the strip missed everything, so the
    residual-neutralisation pass behind it has something to act on."""
    monkeypatch.setattr(evidence_barrier, "_strip_derived_fields", lambda t: t)


def test_a_residual_the_strip_missed_is_neutralized(tmp_path, monkeypatch):
    """A value the barrier did not derive and (here, by monkeypatch) could not
    strip is overwritten with its own decision for the entry -- no letter --
    and named in the report."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    _disable_strip(monkeypatch, evidence_barrier)
    rd = tmp_path / "review"
    _domain(rd, 1, STALE_COMPACT_D1, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix = {a}" not in content
    assert "year_suffix = {b}" not in content
    assert content.count("year_suffix = {unassigned}") == 2
    suffixes = _report(rd)["year_suffixes"]
    assert suffixes["assigned"] == 0
    assert sorted(suffixes["residual_neutralized"]) == [
        "literature-domain-1.bib:johnson2024algorithms",
        "literature-domain-1.bib:johnson2024judgement"]
    assert suffixes["residual_unresolved"] == []


def test_a_stale_compact_letter_cannot_license_a_phase_6_drop(tmp_path):
    """The finding's actual claim, end to end: two stale letters that look
    like a complete a/b group make generate_bibliography's `fully_lettered`
    gate true, and a prose "Johnson (2024a)" then DROPS the other cited work
    from the References. Asserted through the real resolver on the barrier's
    real output, because that composition is the defect -- neither script is
    wrong on its own.

    Run against the fixture WITHOUT the barrier, this same resolver call
    returns only johnson2024algorithms (measured); it is the barrier's
    neutralisation that restores ambiguous-keep-all.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import generate_bibliography
    from pybtex.database import parse_string
    rd = tmp_path / "review"
    _domain(rd, 1, STALE_COMPACT_D1, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    db = parse_string(
        (rd / "literature-domain-1.bib").read_text(encoding="utf-8"), "bibtex")
    cited = sorted(k for k, _ in generate_bibliography.find_cited_entries(
        "As Johnson (2024a) argues, this matters.", db))
    assert cited == ["johnson2024algorithms", "johnson2024judgement"]


def test_a_no_space_year_suffix_on_the_header_line_is_stripped(tmp_path):
    """The shape that used to be the one live drop hazard: unreachable by the
    old strip and by the old add_field_to_entry locator alike. Structural
    location reaches it, so it is simply gone."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    from pybtex.database import parse_string
    rd = tmp_path / "review"
    _domain(rd, 1, STALE_NO_SPACE_D1, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    parse_string(content, "bibtex")
    assert "year_suffix" not in content
    suffixes = _report(rd)["year_suffixes"]
    assert suffixes["residual_neutralized"] == []
    assert suffixes["residual_unresolved"] == []


def test_a_residual_the_splice_cannot_neutralize_is_reported(tmp_path, capsys,
                                                             monkeypatch):
    """The splice is verified rather than trusted: when neutralising a
    residual does not land (here the strip AND the splice are both disabled
    by monkeypatch, standing in for a shape neither can reach), the barrier
    keeps the pre-splice text, reports the entry unresolved, and says so on
    the console line too."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    from pybtex.database import parse_string
    _disable_strip(monkeypatch, evidence_barrier)
    monkeypatch.setattr(evidence_barrier, "add_field_to_entry",
                        lambda text, field, value: text)
    rd = tmp_path / "review"
    _domain(rd, 1, STALE_NO_SPACE_D1, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    parse_string(content, "bibtex")          # MUST still parse -- non-negotiable
    assert "year_suffix={a}" in content      # untouched, not half-spliced
    assert "unassigned" not in content
    suffixes = _report(rd)["year_suffixes"]
    assert suffixes["residual_neutralized"] == []
    assert suffixes["residual_unresolved"] == [
        "literature-domain-1.bib:johnson2024algorithms"]
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["year_suffixes"]["residual_unresolved"] == 1


def test_a_residual_is_neutralized_even_when_assignment_raises(tmp_path,
                                                               monkeypatch):
    """Detection lives OUTSIDE the assignment try/except on purpose: nested
    inside it, an assignment exception would hide the residual -- the exact
    silence this pass exists to end. On the error path suffix_map is empty,
    so every residual entry is neutralised rather than overwritten with a
    fresh letter."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    def boom(entries):
        raise RuntimeError("assignment blew up")

    monkeypatch.setattr(evidence_barrier.ys, "assign_suffixes", boom)
    _disable_strip(monkeypatch, evidence_barrier)
    rd = tmp_path / "review"
    _domain(rd, 1, STALE_COMPACT_D1, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert content.count("year_suffix = {unassigned}") == 2
    suffixes = _report(rd)["year_suffixes"]
    assert suffixes["status"] == "error"
    assert len(suffixes["residual_neutralized"]) == 2


def test_a_residual_on_a_lettered_entry_is_overwritten_by_this_run(tmp_path,
                                                                    monkeypatch):
    """Why the refusal is a WRITE and not a suppression. An entry the
    assigner letters already has its residual overwritten in place, so
    suppressing this run's letters on detection would leave MORE untrusted
    values standing, not fewer -- it removes the overwrite that cleans them.
    The stale value here is 'z', which no two-work group can ever produce.
    (Strip disabled by monkeypatch so a residual exists to overwrite.)"""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    _disable_strip(monkeypatch, evidence_barrier)
    rd = tmp_path / "review"
    forged = MENARY_D1.replace(
        "  doi = {10.7551/mitpress/1.001},",
        "  doi = {10.7551/mitpress/1.001}, year_suffix = {z},", 1)
    _domain(rd, 1, forged, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "{z}" not in content
    assert "year_suffix = {a}" in content and "year_suffix = {b}" in content
    suffixes = _report(rd)["year_suffixes"]
    assert suffixes["assigned"] == 2
    assert suffixes["residual_neutralized"] == [
        "literature-domain-1.bib:menary2010cognitive"]


def test_console_summary_distinguishes_unlettered_groups(tmp_path, capsys):
    """`execute` prints a one-line JSON summary; that line is what an operator
    reads during a live run. A bare assigned-count of 0 cannot tell "no
    same-author-same-year group existed" from "a group existed and got no
    letters on purpose" -- only the second needs looking at.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, SUPPRESSED_D1, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["year_suffixes"] == {
        "status": "complete", "assigned": 0, "overflow": 0, "suppressed": 1,
        "residual_unresolved": 0}


def test_console_summary_distinguishes_a_raised_assignment(tmp_path, capsys,
                                                           monkeypatch):
    """Without `status`, an assignment that RAISED
    printed exactly the zeros a quiet run prints -- so the pass's loudest
    failure was the one an operator could not see, while the venue summary
    right beside it has always carried a status. Both directions are
    asserted, and the two summaries compared: deleting the key collapses
    them into each other and this fails.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    def boom(entries):
        raise RuntimeError("assignment blew up")

    # A quiet run: KUHN is one work in its year, so nothing is assigned,
    # suppressed or overflowed and every count is zero.
    quiet_dir = tmp_path / "quiet"
    _domain(quiet_dir, 1, KUHN, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(quiet_dir, 1) == 0
    quiet = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert quiet["year_suffixes"]["status"] == "complete"

    raised_dir = tmp_path / "raised"
    _domain(raised_dir, 1, KUHN, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(evidence_barrier.ys, "assign_suffixes", boom)
    assert evidence_barrier.execute(raised_dir, 1) == 0     # fails OPEN, as designed
    raised = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert raised["year_suffixes"]["status"] == "error"

    # The counts alone are identical -- that IS the finding, and it is what
    # makes `status` the only discriminator on the printed line.
    assert {k: v for k, v in quiet["year_suffixes"].items() if k != "status"} == \
           {k: v for k, v in raised["year_suffixes"].items() if k != "status"}
    assert quiet["year_suffixes"] != raised["year_suffixes"]


def test_both_optional_passes_stamp_together(tmp_path, monkeypatch):
    """The venue flag and the Chicago letter are stamped by two
    optional passes sharing one insertion point in `execute`. This pins that
    they coexist on the same entry and that each still lands only where it
    belongs -- the flag on the one flagged venue, the letters on every member
    of the same-author-same-year group.

    Deliberately NOT claiming "neither pass failing takes the other down":
    both passes SUCCEED here, so this test cannot show that. The failure
    directions are pinned separately, one pass each, by
    test_venue_vetting_failure_never_fails_the_barrier and
    test_suffix_failure_never_fails_the_barrier.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    # count=1 is load-bearing: "  publisher = {MIT Press}," occurs in BOTH
    # MENARY_D1 entries, so an uncounted replace gives both a journal and
    # hence both a venue_status -- destroying the per-entry discrimination
    # this test exists for.
    _domain(rd, 1, MENARY_D1.replace(
        "  publisher = {MIT Press},",
        "  publisher = {MIT Press},\n"
        "  journal = {Advanced International Journal for Research},", 1),
        cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(
        evidence_barrier.vv, "vet_venues",
        _fake_vet(flagged=["advanced international journal for research"]))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "venue_status = {low-visibility}" in content
    assert "year_suffix = {a}" in content and "year_suffix = {b}" in content
    flagged = [c for c in content.split("\n@") if "menary2010cognitive" in c][0]
    other = [c for c in content.split("\n@") if "menary2010extended" in c][0]
    assert "venue_status" in flagged and "year_suffix" in flagged
    assert "venue_status" not in other and "year_suffix" in other


def test_derived_fields_are_invisible_to_compute_tier(tmp_path, monkeypatch):
    """Both optional splices must sit BELOW compute_tier, structurally.

    A review moved the venue splice below `compute_tier` so
    that tier invariance would be structural rather than incidental on
    `compute_tier` happening not to read `venue_status`. Nothing pinned that
    ordering: moving the splice back above `parse_entry_fields` left all 49
    barrier tests passing, because they
    all assert on the OUTPUT tier, which is unchanged while compute_tier
    ignores the field.

    This asserts the ordering directly instead -- it captures the `fields`
    mapping compute_tier is actually handed and requires that neither derived
    field has reached it. It therefore fails the moment either splice moves
    above `parse_entry_fields`, whether or not the tier happens to change.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    seen_fields = []
    real_compute_tier = se.compute_tier

    def _spy(entry_type, fields, att):
        seen_fields.append(dict(fields))
        return real_compute_tier(entry_type, fields, att)

    monkeypatch.setattr(evidence_barrier.se, "compute_tier", _spy)
    rd = tmp_path / "review"
    # Same fixture as test_both_optional_passes_stamp_together: one entry gets
    # a venue flag, both get a Chicago letter, so a single run exercises both
    # splices. count=1 keeps the journal on one entry only.
    _domain(rd, 1, MENARY_D1.replace(
        "  publisher = {MIT Press},",
        "  publisher = {MIT Press},\n"
        "  journal = {Advanced International Journal for Research},", 1),
        cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    monkeypatch.setattr(
        evidence_barrier.vv, "vet_venues",
        _fake_vet(flagged=["advanced international journal for research"]))
    assert evidence_barrier.execute(rd, 1) == 0

    # The run really did stamp both fields -- otherwise the assertions below
    # would pass vacuously against a run that never spliced anything.
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "venue_status = {low-visibility}" in content
    assert "year_suffix = {a}" in content and "year_suffix = {b}" in content

    assert len(seen_fields) == 2, seen_fields
    for fields in seen_fields:
        assert "venue_status" not in fields
        assert "year_suffix" not in fields


def test_stale_line_initial_year_suffix_is_stripped(tmp_path):
    """The `year_suffix` half of `_DERIVED_FIELD_RE` must actually strip.

    The venue_status half is covered by three tests; this half was covered by
    none -- removing `year_suffix` from that alternation left all 54 barrier
    tests green. The docstring's assertion
    that "all three limits apply identically to year_suffix" pinned the
    sentence, not the behaviour.

    A stale LINE-INITIAL letter: `menaryStale` is a single Menary 2011 work,
    which needs no letter at all, so a correct run leaves it with none. (The
    compact, non-line-initial case is covered by
    test_stale_compact_year_suffix_is_stripped.)
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    stale = """@book{menaryStale,
  author = {Menary, Richard},
  title = {A Lone Work Needing No Letter},
  publisher = {MIT Press},
  year = {2011},
  year_suffix = {q}
}"""
    _domain(rd, 1, stale, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix" not in content, content
    # And the run must not have reported it as an unreachable residual either:
    # this one WAS reachable, so the stripper owns it.
    report = _report(rd)
    assert report["year_suffixes"]["assigned"] == 0


def test_suppressed_singletons_reach_the_report_on_both_branches():
    """`suppressed_singletons` is half of a partition and must not be dropped.

    year_suffix.assign_suffixes splits the groups it declined to letter into
    `suppressed` (suppression actually cost letters) and
    `suppressed_singletons` (a single-work group, which could never have been
    lettered). On the real corpus that is 8 vs 98, and reporting them together
    buried the 8 actionable records. The barrier must carry BOTH, so that
    "nothing the assigner declined is invisible" still holds -- and it must
    carry both on the ERROR branch too, where a consumer reading the key
    would otherwise KeyError on the least-tested path.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import year_suffix as ys
    import inspect
    src = inspect.getsource(evidence_barrier.run_barrier)
    assert src.count('"suppressed_singletons"') >= 2, (
        "both the complete and the error branch must carry the key")
    # And the key the barrier reads is one the module actually returns.
    assert "suppressed_singletons" in ys.assign_suffixes([])


def test_singleton_suppression_is_reported_separately(tmp_path):
    """End-to-end: a single-work suppressed group lands in the singleton list,
    not in the list an operator is meant to act on.

    Fixture is the real corpus shape behind all 98 singleton records: one DOI
    claimed by two entries whose author signatures differ, so the work
    component spans two (signature, year) groups and each is tainted with
    `identity_conflict` while holding one work. Neither could ever have been
    lettered -- Chicago disambiguation starts at two works -- so both belong
    in the singleton list, leaving `suppressed` free to carry only the groups
    where suppression actually cost letters.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    shared_doi = """@book{claimA,
  author = {Alpha, Ann},
  title = {One Work, Two Claimants},
  publisher = {MIT Press},
  doi = {10.1000/shared},
  year = {2012}
}

@book{claimB,
  author = {Beta, Bob},
  title = {One Work, Two Claimants},
  publisher = {MIT Press},
  doi = {10.1000/shared},
  year = {2012}
}"""
    _domain(rd, 1, shared_doi, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix" not in content
    ys_report = _report(rd)["year_suffixes"]
    assert ys_report["status"] == "complete"
    assert ys_report["assigned"] == 0
    # The actionable list stays EMPTY so a real multi-work suppression stands
    # out; the singletons are still reported, just not mixed in.
    assert ys_report["suppressed"] == []
    singles = ys_report["suppressed_singletons"]
    assert len(singles) == 2, singles
    assert {r["works"] for r in singles} == {1}
    assert {r["year"] for r in singles} == {"2012"}


def test_a_swallowed_splice_is_never_reported_as_neutralized(tmp_path, monkeypatch):
    """A splice that silently did nothing must not be reported as a fix.

    `_stamp_optional_field` swallows any exception from `add_field_to_entry`
    and returns the text UNCHANGED -- deliberately, so an optional pass can
    never fail the barrier. But an unchanged chunk still holds exactly one
    `year_suffix =` and still parses, so a well-formedness check alone reads
    as success and the entry lands in `residual_neutralized` while the stale
    letter survives to disk.

    That is the "never silently" policy violated on the error path, and it is
    a live drop hazard: two surviving stale letters read as a structurally
    complete group in Phase 6, so a prose `Johnson (2024a)` drops the other
    work -- with the barrier having reported the hazard as fixed.

    Fault injection mirrors the established shape in
    `test_stamp_failure_does_not_fail_the_barrier`.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    real_add = evidence_barrier.add_field_to_entry

    def add_but_never_for_the_suffix(entry_text, field, value):
        if field == "year_suffix":
            raise RuntimeError("splice boom")
        return real_add(entry_text, field, value)

    monkeypatch.setattr(evidence_barrier, "add_field_to_entry",
                        add_but_never_for_the_suffix)
    rd = tmp_path / "review"
    _domain(rd, 1, STALE_COMPACT_D1, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0

    ys_report = _report(rd)["year_suffixes"]
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    stale_survived = "year_suffix = {a}" in content or 'year_suffix = "a"' in content

    # The barrier must not claim a neutralization it did not perform: if the
    # stale value is still on disk, the entry belongs in `unresolved`.
    if stale_survived:
        assert ys_report["residual_neutralized"] == [], (
            "reported neutralized while the stale letter is still on disk: "
            f"{ys_report['residual_neutralized']}")
        assert ys_report["residual_unresolved"], (
            "a surviving stale letter must reach an operator")


# ---------------------------------------------------------------------------
# venue_status splice verification (the second half of the silent-splice bug;
# the year_suffix half was fixed 2026-08-06 in 78dd470)
# ---------------------------------------------------------------------------

def test_venue_stamp_that_lands_is_counted_as_stamped(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    monkeypatch.setattr(
        evidence_barrier.vv, "vet_venues",
        _fake_vet(flagged=["advanced international journal for research"]))
    assert evidence_barrier.execute(rd, 1) == 0
    report = _report(rd)
    assert report["venue_vetting"]["flagged_entries"] == 1
    assert len(report["venue_vetting"]["stamped_entries"]) == 1
    assert report["venue_vetting"]["splice_failed"] == []


def test_a_swallowed_venue_splice_is_reported_not_silent(tmp_path, monkeypatch):
    """The bug this fixes: _stamp_optional_field swallows a splice failure and
    returns the text unchanged, so the entry ships with no venue_status and
    NOTHING in the report says so. flagged_entries was honest about counting
    rule decisions rather than stamps, which made the gap invisible rather than
    misreported -- and a silent loss is what the gate policy forbids."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    monkeypatch.setattr(
        evidence_barrier.vv, "vet_venues",
        _fake_vet(flagged=["advanced international journal for research"]))
    # Exactly what a swallowed add_field_to_entry exception looks like from the
    # caller's side: the text comes back untouched.
    monkeypatch.setattr(evidence_barrier, "_stamp_optional_field",
                        lambda text, field, value: text)
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "venue_status" not in content          # the loss really happened
    report = _report(rd)
    assert report["venue_vetting"]["flagged_entries"] == 1
    assert report["venue_vetting"]["stamped_entries"] == []
    assert len(report["venue_vetting"]["splice_failed"]) == 1   # and is reported


def test_a_duplicate_venue_field_is_reverted_rather_than_emitted(tmp_path, monkeypatch):
    """A compact pre-existing venue_status survives _strip_derived_fields (it
    only reaches a field OPENING its line), and add_field_to_entry cannot find
    a field with no whitespace before it -- so the add path inserts a SECOND
    one and pybtex raises DuplicateField, which would take down all of Phase 6.
    Revert, report, keep the bib parseable."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    from pybtex.database import parse_string
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    monkeypatch.setattr(
        evidence_barrier.vv, "vet_venues",
        _fake_vet(flagged=["advanced international journal for research"]))
    # Simulate the duplicate-inserting outcome directly.
    def _double(text, field, value):
        return text.replace("@article{okoro2021ai,",
                            "@article{okoro2021ai,\n  %s = {%s},\n  %s = {%s},"
                            % (field, value, field, value), 1)
    monkeypatch.setattr(evidence_barrier, "_stamp_optional_field", _double)
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert content.count("venue_status") == 0    # reverted, not emitted twice
    parse_string(content, bib_format="bibtex")   # and still parses
    report = _report(rd)
    assert len(report["venue_vetting"]["splice_failed"]) == 1


def test_venue_splice_keys_are_present_even_when_vetting_errored(tmp_path, monkeypatch):
    """The lists are attached before the stamping loop so the ERROR path
    carries the keys too -- a consumer must not have to guess."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    def _boom(names):
        raise RuntimeError("openalex down")
    monkeypatch.setattr(evidence_barrier.vv, "vet_venues", _boom)
    assert evidence_barrier.execute(rd, 1) == 0
    report = _report(rd)
    assert report["venue_vetting"]["status"] == "error"
    assert report["venue_vetting"]["stamped_entries"] == []
    assert report["venue_vetting"]["splice_failed"] == []


# ---------------------------------------------------------------------------
# Web-source evidence in the barrier
# ---------------------------------------------------------------------------

_WEB_ENTRY = """@misc{k,
  author = {Omohundro, Steve},
  title = {The Basic AI Drives},
  year = {2008},
  url = {https://a.example/x},
  web_span = {acquire steel manipulators and energy resources for itself},
  note = {CORE ARGUMENT: convergent instrumental drives.}
}"""

_WEB_CAPTURE = {
    "url": "https://a.example/x", "final_url": "https://a.example/x",
    "http_status": 200, "provenance": "script",
    "retrieved_at": "2026-08-14T14:02:00+00:00",
    "title": "The Basic AI Drives",
    "text": "word " * 100 + "acquire steel manipulators and energy resources for itself",
}


def _web_review(tmp_path, entry=_WEB_ENTRY, capture=_WEB_CAPTURE, capture_key="k"):
    rd = tmp_path / "review"
    _domain(rd, 1, entry, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    if capture is not None:
        cdir = rd / "intermediate_files" / "web_captures"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / f"{capture_key}.json").write_text(
            json.dumps(capture), encoding="utf-8")
    return rd


def _stub_net(monkeypatch, status=200, snapshot=None, final=None):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    monkeypatch.setattr(evidence_barrier.wv, "http_get",
                        lambda url: {"status": status, "final_url": final or url})
    monkeypatch.setattr(evidence_barrier.wv, "wayback_lookup", lambda url: snapshot)
    return evidence_barrier


def test_a_gate_passing_web_entry_is_stamped_web_with_derived_fields(tmp_path, monkeypatch):
    eb_mod = _stub_net(monkeypatch, snapshot="https://web.archive.org/web/2024/x")
    rd = _web_review(tmp_path)
    report, outputs = eb_mod.run_barrier(rd, 1)
    text = list(outputs.values())[0]
    assert "EVIDENCE-WEB" in text
    assert "urldate = {2026-08-14}" in text
    assert "web.archive.org" in text
    assert report["web_sources"]["gate_passed"] == {"script": 1, "agent": 0}


def test_a_web_entry_whose_span_is_absent_stays_none_and_is_reported(tmp_path, monkeypatch):
    eb_mod = _stub_net(monkeypatch)
    cap = dict(_WEB_CAPTURE, text="word " * 100 + "nothing the note ever quoted")
    rd = _web_review(tmp_path, capture=cap)
    report, outputs = eb_mod.run_barrier(rd, 1)
    assert report["stamps"]["literature-domain-1.bib"]["k"] == "EVIDENCE-NONE"
    assert report["web_sources"]["capture_rejected"]["span_unverified"] == [
        "literature-domain-1.bib:k"]
    assert "EVIDENCE-WEB" not in list(outputs.values())[0]


def test_an_abstract_bearing_misc_lands_in_its_own_bucket(tmp_path):
    """The web pass deliberately skips a @misc that carries an abstract (the
    abstract attestation channel owns it), but the skip must land in a named
    bucket -- the report's design claim is that every non-promotion is
    accounted for, and this class used to vanish without a trace. Reaches no
    network: the skip fires before any probe, so the CLI run stays offline.
    The summary assertion pins the other half of the decision: this is a
    SCOPE bucket, deliberately excluded from not_promoted (the entry can
    still promote through the abstract channel)."""
    entry = _WEB_ENTRY.replace(
        "  note = {CORE ARGUMENT: convergent instrumental drives.}",
        "  abstract = {Hand-written abstract.},\n"
        "  note = {CORE ARGUMENT: convergent instrumental drives.}")
    rd = _web_review(tmp_path, entry=entry)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    ws = _report(rd)["web_sources"]
    assert ws["misc_with_abstract"] == ["literature-domain-1.bib:k"]
    assert ws["no_url"] == [] and ws["no_capture"] == []
    assert ws["capture_rejected"] == {}
    assert ws["gate_passed"] == {"script": 0, "agent": 0}
    summary = json.loads(r.stdout)["web_sources"]
    assert summary["not_promoted"] == 0


def test_an_error_record_lands_in_fetch_error_not_no_capture(tmp_path, monkeypatch):
    eb_mod = _stub_net(monkeypatch)
    rd = _web_review(tmp_path, capture={"url": "https://a.example/x",
                                        "error": "fetch-failed:timeout"})
    report, _ = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["fetch_error"] == ["literature-domain-1.bib:k"]
    assert report["web_sources"]["no_capture"] == []


def test_no_existence_is_its_own_bucket(tmp_path, monkeypatch):
    eb_mod = _stub_net(monkeypatch, status=404)
    rd = _web_review(tmp_path)
    report, _ = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["no_existence"] == ["literature-domain-1.bib:k"]


def test_agent_provenance_is_counted_separately(tmp_path, monkeypatch):
    eb_mod = _stub_net(monkeypatch)
    cap = dict(_WEB_CAPTURE, provenance="agent", http_status=None)
    rd = _web_review(tmp_path, capture=cap)
    report, _ = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["gate_passed"] == {"script": 0, "agent": 1}


def test_a_wayback_lookup_failure_lands_in_the_wayback_failed_bucket(tmp_path, monkeypatch):
    """Live-acceptance finding (2026-08-15): with the availability API
    throttled (429), a missing archiveurl was indistinguishable post hoc from
    "no snapshot exists". The bucket is diagnostic, not an outcome: the entry
    still gate-passes and still gets no archiveurl."""
    eb_mod = _stub_net(monkeypatch)

    def boom(url):
        raise OSError("wayback 429")
    monkeypatch.setattr(eb_mod.wv, "wayback_lookup", boom)
    rd = _web_review(tmp_path)
    report, outputs = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["gate_passed"] == {"script": 1, "agent": 0}
    assert report["web_sources"]["wayback_failed"] == ["literature-domain-1.bib:k"]
    assert "archiveurl" not in list(outputs.values())[0]


def test_a_clean_run_reports_an_empty_wayback_failed_bucket(tmp_path, monkeypatch):
    eb_mod = _stub_net(monkeypatch, snapshot="https://web.archive.org/web/2024/x")
    rd = _web_review(tmp_path)
    report, _ = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["wayback_failed"] == []


def test_a_stale_urldate_in_the_source_bib_is_stripped_and_re_derived(tmp_path, monkeypatch):
    """The barrier is sole author of urldate/archiveurl, like sep_context."""
    eb_mod = _stub_net(monkeypatch)
    stale = _WEB_ENTRY.replace("  year = {2008},",
                               "  year = {2008},\n  urldate = {1999-01-01},")
    rd = _web_review(tmp_path, entry=stale)
    _, outputs = eb_mod.run_barrier(rd, 1)
    text = list(outputs.values())[0]
    assert "1999-01-01" not in text
    assert text.count("urldate") == 1


def test_one_raising_entry_does_not_cost_its_neighbour_its_promotion(tmp_path, monkeypatch):
    """Entry-level degradation is required. Without the per-entry
    boundary, the single pass-level wrapper zeroes web_gates and the GOOD entry
    demotes with the bad one.

    The raise is INJECTED rather than provoked through data: normalize_url is
    hardened against the malformed-port case, so the data-driven version of this
    test passed for the wrong reason (the second entry simply had no capture of
    its own). Mutation-checked -- removing the inner try/except fails this.
    """
    eb_mod = _stub_net(monkeypatch)
    real = eb_mod.wv.evaluate_existence

    def selective(url, *a, **k):
        if "bad" in url:
            raise RuntimeError("one entry's data is poison")
        return real(url, *a, **k)

    monkeypatch.setattr(eb_mod.wv, "evaluate_existence", selective)
    bad = _WEB_ENTRY.replace("@misc{k,", "@misc{bad,").replace(
        "https://a.example/x", "https://a.example/bad")
    rd = _web_review(tmp_path, entry=_WEB_ENTRY + "\n\n" + bad)
    # A capture for the poison entry too, so it reaches the raising call.
    cdir = rd / "intermediate_files" / "web_captures"
    (cdir / "bad.json").write_text(json.dumps(
        dict(_WEB_CAPTURE, url="https://a.example/bad",
             final_url="https://a.example/bad")), encoding="utf-8")

    report, _ = eb_mod.run_barrier(rd, 1)
    stamps = report["stamps"]["literature-domain-1.bib"]
    assert stamps["k"] == "EVIDENCE-WEB", "the good entry lost its promotion"
    assert stamps["bad"] == "EVIDENCE-NONE"
    assert len(report["web_sources"]["entry_error"]) == 1
    assert report["web_sources"]["status"] == "complete"


def test_a_pass_level_failure_degrades_to_no_promotions_not_a_failed_run(tmp_path, monkeypatch):
    """The OUTER boundary. A non-serializable value in the report is exactly
    what the json round-trip inside the try exists to catch: without it the
    TypeError escapes execute(), and the bibs -- gated on the report write --
    are never written at all."""
    eb_mod = _stub_net(monkeypatch)
    monkeypatch.setattr(eb_mod.wv, "check_capture",
                        lambda *a, **k: (False, object()))   # unserializable
    rd = _web_review(tmp_path)
    report, outputs = eb_mod.run_barrier(rd, 1)
    assert report["status"] != "failed"
    assert report["web_sources"]["status"] == "error"
    assert report["web_sources"]["gate_passed"] == {"script": 0, "agent": 0}
    assert "EVIDENCE-WEB" not in list(outputs.values())[0]


def test_a_non_misc_entry_with_a_url_is_never_web_gated(tmp_path, monkeypatch):
    """A url on an @article is decoration; its evidence channels are the API
    ones (out of scope)."""
    eb_mod = _stub_net(monkeypatch)
    art = _WEB_ENTRY.replace("@misc{k,", "@article{k,")
    rd = _web_review(tmp_path, entry=art)
    report, _ = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["gate_passed"] == {"script": 0, "agent": 0}
    assert report["stamps"]["literature-domain-1.bib"]["k"] != "EVIDENCE-WEB"


# ---------------------------------------------------------------------------
# urldate/archiveurl splice verification (the web-gate siblings of the
# venue_status fix above; added 2026-08-16 from the service's whole-branch
# review of the web-evidence intake)
# ---------------------------------------------------------------------------

def test_web_derived_field_splices_that_land_are_counted_as_stamped(tmp_path, monkeypatch):
    eb_mod = _stub_net(monkeypatch, snapshot="https://web.archive.org/web/2024/x")
    rd = _web_review(tmp_path)
    report, outputs = eb_mod.run_barrier(rd, 1)
    text = list(outputs.values())[0]
    assert "urldate = {2026-08-14}" in text
    assert "web.archive.org" in text
    assert sorted(report["web_sources"]["stamped_entries"]) == [
        "literature-domain-1.bib:k:archiveurl",
        "literature-domain-1.bib:k:urldate"]
    assert report["web_sources"]["splice_failed"] == []


def test_a_swallowed_web_splice_is_reported_not_silent(tmp_path, monkeypatch):
    """_stamp_optional_field swallows a splice failure and returns the text
    unchanged; before this fix the entry shipped with no urldate and NOTHING
    in the report said so — the same silent loss the venue fix ended."""
    eb_mod = _stub_net(monkeypatch)
    rd = _web_review(tmp_path)
    monkeypatch.setattr(eb_mod, "_stamp_optional_field",
                        lambda text, field, value: text)
    report, outputs = eb_mod.run_barrier(rd, 1)
    text = list(outputs.values())[0]
    assert "urldate" not in text                       # the loss really happened
    assert report["web_sources"]["stamped_entries"] == []
    assert report["web_sources"]["splice_failed"] == [
        "literature-domain-1.bib:k:urldate"]           # and is reported
    # The gate itself still passed — only the field splice was lost.
    assert report["web_sources"]["gate_passed"] == {"script": 1, "agent": 0}


def test_a_compact_stale_urldate_is_stripped_and_the_fresh_one_lands(tmp_path, monkeypatch):
    """A urldate written on the header line with no whitespace before it used
    to survive the strip and defeat add_field_to_entry's locator, so the add
    path inserted a SECOND one and the splice had to be reverted. Structural
    location strips it, and this run's own urldate lands cleanly."""
    from pybtex.database import parse_string
    eb_mod = _stub_net(monkeypatch, snapshot="https://web.archive.org/web/2024/x")
    compact = _WEB_ENTRY.replace("@misc{k,",
                                 "@misc{k,urldate = {1999-01-01},", 1)
    rd = _web_review(tmp_path, entry=compact)
    report, outputs = eb_mod.run_barrier(rd, 1)
    text = list(outputs.values())[0]
    assert text.count("urldate") == 1                  # this run's, not two
    assert "1999-01-01" not in text                    # the stale one is gone
    parse_string(text, bib_format="bibtex")
    assert report["web_sources"]["splice_failed"] == []
    assert sorted(report["web_sources"]["stamped_entries"]) == [
        "literature-domain-1.bib:k:archiveurl", "literature-domain-1.bib:k:urldate"]


def test_a_failed_urldate_splice_is_reverted_and_the_archiveurl_still_lands(tmp_path, monkeypatch):
    """Each web splice is verified and reverted independently: a urldate
    splice that produces a duplicate (simulated) is reverted and reported,
    the bib stays parseable, and the sibling archiveurl still lands."""
    from pybtex.database import parse_string
    eb_mod = _stub_net(monkeypatch, snapshot="https://web.archive.org/web/2024/x")
    real = eb_mod._stamp_optional_field

    def _double_urldate(text, field, value):
        if field != "urldate":
            return real(text, field, value)
        return text.replace("@misc{k,", "@misc{k,\n  urldate = {%s},\n  urldate = {%s},"
                            % (value, value), 1)
    monkeypatch.setattr(eb_mod, "_stamp_optional_field", _double_urldate)
    rd = _web_review(tmp_path)
    report, outputs = eb_mod.run_barrier(rd, 1)
    text = list(outputs.values())[0]
    assert "urldate" not in text                       # reverted, not emitted twice
    parse_string(text, bib_format="bibtex")
    assert report["web_sources"]["splice_failed"] == [
        "literature-domain-1.bib:k:urldate"]
    assert report["web_sources"]["stamped_entries"] == [
        "literature-domain-1.bib:k:archiveurl"]        # sibling unaffected


def test_web_splice_keys_are_present_even_with_no_web_entries(tmp_path, monkeypatch):
    """The lists are attached after the web pass unconditionally, so every
    report shape carries the keys — a consumer must not have to guess."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, TWO_VENUE_BIB, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1))
    report, _ = evidence_barrier.run_barrier(rd, 1)
    assert report["web_sources"]["stamped_entries"] == []
    assert report["web_sources"]["splice_failed"] == []


# ---------------------------------------------------------------------------
# Encyclopedia-host exclusion in the barrier web pass
# ---------------------------------------------------------------------------

_SEP_ENTRY = """@misc{k,
  author = {Schlosser, Markus},
  title = {Agency},
  year = {2019},
  url = {https://plato.stanford.edu/entries/agency/},
  web_span = {an agent is a being with the capacity to act},
  note = {CORE ARGUMENT: standard theory of agency.}
}"""

_SEP_CAPTURE = {
    "url": "https://plato.stanford.edu/entries/agency/",
    "final_url": "https://plato.stanford.edu/entries/agency/",
    "http_status": 200, "provenance": "script",
    "retrieved_at": "2026-08-17T14:02:00+00:00",
    "title": "Agency",
    "text": "word " * 100 + "an agent is a being with the capacity to act",
}


def test_an_excluded_host_entry_is_bucketed_and_never_probed_or_read(tmp_path, monkeypatch):
    """Exclusion beats even a valid capture, and NOTHING runs for the
    entry -- not the existence probe (a crawl-delayed host must not be
    GET) and not even the capture read."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier as eb_mod

    def _no_net(url):
        raise AssertionError(f"existence probe ran for excluded host: {url}")
    def _no_read(review_dir, key):
        raise AssertionError(f"capture read for excluded host entry: {key}")
    monkeypatch.setattr(eb_mod.wv, "evaluate_existence", _no_net)
    monkeypatch.setattr(eb_mod.wv, "load_capture", _no_read)
    rd = _web_review(tmp_path, entry=_SEP_ENTRY, capture=_SEP_CAPTURE)
    report, outputs = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["excluded_host"] == ["literature-domain-1.bib:k"]
    assert report["web_sources"]["excluded_host_demoted"] == []  # no prior stamp
    assert report["web_sources"]["entry_error"] == []            # nothing raised
    assert report["stamps"]["literature-domain-1.bib"]["k"] == "EVIDENCE-NONE"
    assert "EVIDENCE-WEB" not in list(outputs.values())[0]
    assert report["web_sources"]["no_capture"] == []


_REDIRECTED_ENTRY = """@misc{k,
  author = {Schlosser, Markus},
  title = {Agency},
  year = {2019},
  url = {https://a.example/agency},
  web_span = {an agent is a being with the capacity to act},
  note = {CORE ARGUMENT: standard theory of agency.}
}"""

_REDIRECTED_CAPTURE = {
    "url": "https://a.example/agency",
    "final_url": "https://plato.stanford.edu/entries/agency/",
    "http_status": 200, "provenance": "script",
    "retrieved_at": "2026-08-17T14:02:00+00:00",
    "title": "Agency",
    "text": "word " * 100 + "an agent is a being with the capacity to act",
}


def test_a_capture_that_redirected_onto_an_excluded_host_is_not_promoted(tmp_path, monkeypatch):
    """The redirect seam: an allowed bib
    URL whose capture's final_url landed on SEP must be bucketed, never
    probed, never promoted -- otherwise a redirector defeats the exclusion."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier as eb_mod

    def _no_net(url):
        raise AssertionError(f"existence probe ran after excluded redirect: {url}")
    monkeypatch.setattr(eb_mod.wv, "evaluate_existence", _no_net)
    rd = _web_review(tmp_path, entry=_REDIRECTED_ENTRY, capture=_REDIRECTED_CAPTURE)
    report, outputs = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["excluded_host"] == ["literature-domain-1.bib:k"]
    assert "EVIDENCE-WEB" not in list(outputs.values())[0]
    assert report["web_sources"]["entry_error"] == []


_PRIOR_WEB_ENTRY = """@misc{k,
  author = {Schlosser, Markus},
  title = {Agency},
  year = {2019},
  howpublished = {\\url{https://plato.stanford.edu/entries/agency/}},
  web_span = {an agent is a being with the capacity to act},
  note = {CORE ARGUMENT: standard theory of agency.},
  keywords = {agency-tag, web-source, EVIDENCE-WEB}
}"""
# Production shape, not the `url = {...}` idiom the other fixtures in this
# section use: the researcher template (agents/domain-literature-researcher.md)
# emits `howpublished = {\url{...}}`, and web_evidence.extract_url falls
# through to `howpublished` only when `url` is absent. This pins that the
# exclusion path handles the REAL shape, not just the convenient one.


def test_a_rerun_demotion_of_a_previously_promoted_entry_is_signalled(tmp_path, monkeypatch):
    """The real re-run case both reviews demanded: an entry a PRIOR pass
    promoted (EVIDENCE-WEB already in its keywords) is demoted on this
    pass -- and the report says so, distinguishably from never-promoted."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier as eb_mod
    monkeypatch.setattr(eb_mod.wv, "evaluate_existence",
                        lambda url: (_ for _ in ()).throw(AssertionError(url)))
    rd = _web_review(tmp_path, entry=_PRIOR_WEB_ENTRY, capture=_SEP_CAPTURE)
    report, outputs = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["excluded_host"] == ["literature-domain-1.bib:k"]
    assert report["web_sources"]["excluded_host_demoted"] == [
        "literature-domain-1.bib:k"]
    assert report["stamps"]["literature-domain-1.bib"]["k"] == "EVIDENCE-NONE"
    assert "EVIDENCE-WEB" not in list(outputs.values())[0]
    assert report["web_sources"]["entry_error"] == []


_TOKEN_LOOKALIKE_ENTRY = """@misc{k,
  author = {Schlosser, Markus},
  title = {Agency},
  year = {2019},
  url = {https://plato.stanford.edu/entries/agency/},
  web_span = {an agent is a being with the capacity to act},
  note = {CORE ARGUMENT: standard theory of agency.},
  keywords = {agency-tag, pre-EVIDENCE-WEB-candidate}
}"""


def test_a_keyword_that_merely_contains_evidence_web_does_not_signal_demotion(tmp_path, monkeypatch):
    """Token-exactness, not substring: a hypothetical keyword like
    "pre-EVIDENCE-WEB-candidate" must not false-positive the demotion signal
    -- it names an unrelated keyword, not a stamped tier."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier as eb_mod
    monkeypatch.setattr(eb_mod.wv, "evaluate_existence",
                        lambda url: (_ for _ in ()).throw(AssertionError(url)))
    rd = _web_review(tmp_path, entry=_TOKEN_LOOKALIKE_ENTRY, capture=_SEP_CAPTURE)
    report, outputs = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["excluded_host"] == ["literature-domain-1.bib:k"]
    assert report["web_sources"]["excluded_host_demoted"] == []
    assert report["web_sources"]["entry_error"] == []


def test_an_excluded_host_entry_without_a_capture_still_lands_in_excluded_host(tmp_path, monkeypatch):
    """Pins the check's PLACEMENT before the capture read: exclusion is
    scope, so capture presence is irrelevant -- a capture-less SEP entry is
    excluded_host, never no_capture."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier as eb_mod

    def _no_net(url):
        raise AssertionError(f"existence probe ran for excluded host: {url}")
    monkeypatch.setattr(eb_mod.wv, "evaluate_existence", _no_net)
    rd = _web_review(tmp_path, entry=_SEP_ENTRY, capture=None)
    report, _ = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["excluded_host"] == ["literature-domain-1.bib:k"]
    assert report["web_sources"]["no_capture"] == []
    assert report["web_sources"]["entry_error"] == []


def test_excluded_host_bucket_is_present_even_on_the_web_error_path(tmp_path, monkeypatch):
    """The error-path report dict must carry the same keys as the normal
    one -- a consumer must not have to guess (same rule as venue vetting).
    Crash mechanism mirrors test_a_pass_level_failure_degrades_to_no_promotions
    _not_a_failed_run: an unserializable reason trips the json round-trip
    inside the web pass's try."""
    eb_mod = _stub_net(monkeypatch)
    monkeypatch.setattr(eb_mod.wv, "check_capture",
                        lambda *a, **k: (False, object()))   # unserializable
    rd = _web_review(tmp_path)
    report, _ = eb_mod.run_barrier(rd, 1)
    assert report["web_sources"]["status"] == "error"
    assert report["web_sources"]["excluded_host"] == []
    assert report["web_sources"]["excluded_host_demoted"] == []


def test_web_sources_key_set_matches_between_complete_and_error_paths(tmp_path, monkeypatch):
    """Structural pin, not an instance pin: the "complete" and "error"
    branches of the web pass's report dict have now been hand-edited twice
    (wayback_failed, this branch's excluded_host / excluded_host_demoted) --
    each edit risks updating one literal and not the other, silently making
    the error path KeyError-prone for a consumer that only exercised the
    complete path. stamped_entries/splice_failed are attached to BOTH
    branches by reference AFTER the try/except (see the comment above their
    attachment in the source), so a naive dict-literal diff would wrongly
    ignore them; comparing the REALIZED dicts catches that. The only key
    that legitimately differs is "error" itself, present only when the pass
    actually failed."""
    complete_eb_mod = _stub_net(monkeypatch)
    complete_report, _ = complete_eb_mod.run_barrier(
        _web_review(tmp_path / "complete"), 1)
    assert complete_report["web_sources"]["status"] == "complete"

    error_eb_mod = _stub_net(monkeypatch)
    monkeypatch.setattr(error_eb_mod.wv, "check_capture",
                        lambda *a, **k: (False, object()))   # unserializable
    error_report, _ = error_eb_mod.run_barrier(
        _web_review(tmp_path / "error"), 1)
    assert error_report["web_sources"]["status"] == "error"

    complete_keys = set(complete_report["web_sources"].keys())
    error_keys = set(error_report["web_sources"].keys())
    assert error_keys - complete_keys == {"error"}
    assert complete_keys - error_keys == set()


def test_excluded_host_entry_is_counted_in_the_printed_not_promoted_summary(tmp_path):
    """The CLI summary's not_promoted arithmetic (main(), like
    test_web_source_without_a_capture_is_bucketed_and_stays_none pins for
    no_capture) must count excluded_host entries too, or they silently
    vanish from the operator-facing non-promotion count. Uses the real
    subprocess path (_run/_report), not run_barrier() directly, and a real
    plato.stanford.edu URL: excluded_host is decided before any capture
    read or network probe, so this needs no captures dir and no stubbing.

    The entry's keywords ALSO carry a prior EVIDENCE-WEB stamp, so it lands
    in BOTH excluded_host and excluded_host_demoted -- the double-counting
    guard this test exists for only bites when an entry is in both buckets
    at once. A no-keywords fixture would pass identically whether or not
    excluded_host_demoted is (wrongly) added to the summed tuple, since its
    bucket would always be empty; not_promoted must still read 1, not 2."""
    rd = tmp_path / "review"
    misc = """@misc{k,
  author = {Schlosser, Markus},
  title = {Agency},
  year = {2019},
  url = {https://plato.stanford.edu/entries/agency/},
  keywords = {agency-tag, web-source, EVIDENCE-WEB}
}"""
    _domain(rd, 1, misc, cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    report = _report(rd)
    assert report["web_sources"]["excluded_host"] == ["literature-domain-1.bib:k"]
    assert report["web_sources"]["excluded_host_demoted"] == [
        "literature-domain-1.bib:k"]
    summary = json.loads(r.stdout)["web_sources"]
    assert summary["not_promoted"] == 1               # not 2 -- no double count
    assert summary["status"] == "complete"


# --- Task 7: live corroboration gates EVIDENCE-ABSTRACT --------------------
# Ledger equality is only CANDIDACY now; the tier needs a live fetch that
# still serves the same text. Every test here mocks eb.corroborate_abstract
# (the module attribute the barrier looks up at call time -- never a
# barrier-local helper, or the probe-availability pre-classification would
# go untested) and rc.fetch_articles, so the suite stays offline.

CORROB_TEXT = ("We argue that reward hacking is a specification problem "
               "rather than a capability problem.")


def _corroboration_domain(review_dir, *, abstract=CORROB_TEXT, source="s2",
                          doi="10.1/corrob", author="Doe, Jane",
                          year="2020", title="Reward Hacking",
                          cleaning_entries=None,
                          slugs=EMPTY_SLUGS, key="forge2020"):
    """One domain whose single entry PASSES ledger candidacy: the bib's
    abstract hash and abstract_source equal the enrichment record's. Before
    Task 7 that alone attested the entry; now it only makes it a candidate."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import stamp_evidence as se
    bib = ('@article{' + key + ',\n'
           f'  author = {{{author}}},\n'
           f'  title = {{{title}}},\n'
           '  journal = {Journal of Alignment},\n'
           + (f'  doi = {{{doi}}},\n' if doi else '')
           + f'  year = {{{year}}},\n'
           f'  abstract = {{{abstract}}},\n'
           f'  abstract_source = {{{source}}},\n'
           '  keywords = {alignment, High}\n'
           '}')
    enrichment = _enrichment(1, {key: {"abstract_source": source,
                                       "abstract_sha256": se.abstract_hash(abstract)}})
    if cleaning_entries is None:
        cleaning_entries = {key: {
            "api_matched": True, "verified_identifier": "doi",
            "verified_identifier_value": doi, "entry_type": "article"}} if doi else {}
    _domain(review_dir, 1, bib, cleaning=_cleaning(1, cleaning_entries),
            enrichment=enrichment, slugs=slugs)
    return key


def _stub_corroborator(monkeypatch, eb_mod, result, calls, articles=None):
    """Mock the corroborator (recording every call) and the SEP/IEP fetch."""
    def _fake(fields, s2_api_key=None, openalex_email=None, core_api_key=None,
              debug=False):
        calls.append({"fields": dict(fields), "s2": s2_api_key,
                      "email": openalex_email, "core": core_api_key})
        return result
    monkeypatch.setattr(eb_mod.eb, "corroborate_abstract", _fake)
    monkeypatch.setattr(eb_mod.rc, "fetch_articles",
                        lambda union, debug=False: (articles or {}, []))


def _barrier(monkeypatch):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    # Keyed by default so the probe-availability pre-classification does not
    # fire in tests that are about the corroboration outcome itself.
    monkeypatch.setenv("S2_API_KEY", "s2-key")
    monkeypatch.setenv("OPENALEX_EMAIL", "dev@example.org")
    monkeypatch.setenv("CORE_API_KEY", "core-key")
    return evidence_barrier


def test_forged_ledger_record_does_not_attest_without_corroboration(tmp_path, monkeypatch):
    """The three-line forgery: fabricate an abstract, write abstract_source,
    write the fabricated text's own sha256 into the enrichment ledger.
    Ledger equality holds, so candidacy passes -- and a live fetch that
    serves different text must stop the tier there. The entry then proceeds
    exactly like any unattested entry: context acquisition, then whatever
    the identifier attestation earns (EXISTENCE here)."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path, abstract="FABRICATED FINDINGS.")
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("mismatch", None), calls)

    def _no_heal(*a, **k):
        # The heal path stays keyed on CANDIDACY, not on the attestation
        # flag: a failed candidate must not spend a second fetch to
        # re-derive the same no (its gate is the comparison corroboration
        # just failed) -- still less get the tier back through it.
        raise AssertionError("heal fetch ran for a failed candidate")
    monkeypatch.setattr(eb_mod.eb, "resolve_abstract_for_entry", _no_heal)
    monkeypatch.setattr(eb_mod.eb, "resolve_ndpr_abstract", _no_heal)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "mismatch", "source": "s2", "claimed": "s2"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is False
    assert report["stamps"][bib_name][key] == "EVIDENCE-EXISTENCE"
    # no new code path: the entry went through context acquisition
    assert report["acquisition"][bib_name][key] == {"outcome": "unmatched"}
    out = (tmp_path / bib_name).read_text(encoding="utf-8")
    assert "EVIDENCE-ABSTRACT" not in out
    assert len(calls) == 1                      # candidacy passed -> probed


def test_a_corroborated_abstract_is_attested_and_bucketed(tmp_path, monkeypatch):
    """The honest path. The bucket records the source that ANSWERED
    (openalex) next to the source the bib CLAIMED (s2) -- which source
    served the text is integrity-irrelevant, since the gate is hash
    equality, but the split is what makes the corroboration rate readable."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path)
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "openalex"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "corroborated", "source": "openalex", "claimed": "s2"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is True
    assert report["stamps"][bib_name][key] == "EVIDENCE-ABSTRACT"
    # attested entries never consume encyclopedia matching
    assert report["acquisition"][bib_name][key] == {"outcome": "not-needed"}
    assert len(calls) == 1


def test_transport_failure_demotes_and_a_re_run_restores(tmp_path, monkeypatch):
    """A flaky network must not read as evidence -- and must not be
    permanent either. Run 2 goes over run 1's OWN OUTPUT (a fresh fixture
    would just re-test the honest path and prove nothing about
    restoration): the abstract and abstract_source survive the barrier's
    field strip, so candidacy re-passes and the tier comes back."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path)
    bib_name = "literature-domain-1.bib"
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("transport_failed", None), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "transport_failed", "source": "s2", "claimed": "s2"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is False
    assert report["stamps"][bib_name][key] == "EVIDENCE-EXISTENCE"
    assert "EVIDENCE-ABSTRACT" not in (tmp_path / bib_name).read_text(
        encoding="utf-8")

    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "corroborated", "source": "s2", "claimed": "s2"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is True
    assert report["stamps"][bib_name][key] == "EVIDENCE-ABSTRACT"
    assert len(calls) == 2


def test_corroboration_reads_the_same_env_keys_as_the_heal_path(tmp_path, monkeypatch):
    """The keys come from the environment, not from the bib: S2_API_KEY,
    OPENALEX_EMAIL and CORE_API_KEY -- exactly what _heal_abstract reads."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.setenv("S2_API_KEY", "sk-s2")
    monkeypatch.setenv("OPENALEX_EMAIL", "dev@phillit.test")
    monkeypatch.setenv("CORE_API_KEY", "sk-core")
    _corroboration_domain(tmp_path)
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    assert calls[0]["s2"] == "sk-s2"
    assert calls[0]["email"] == "dev@phillit.test"
    assert calls[0]["core"] == "sk-core"
    # identity comes from the entry's own fields, nothing else
    assert calls[0]["fields"]["doi"] == "10.1/corrob"


def test_claimed_core_in_a_keyless_workspace_is_probe_unavailable(tmp_path, monkeypatch):
    """Pre-classification, not a probe: keyless CORE cannot be asked, so
    calling the corroborator would burn the fallback probes and then label
    the outcome source_empty -- which has to keep meaning "a source was
    probed and authoritatively has no abstract". Fail-closed all the same:
    no tier, so claiming `core` in a keyless workspace gains nothing."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    key = _corroboration_domain(tmp_path, source="core")
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "core"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "probe_unavailable", "source": "core", "claimed": "core"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is False
    assert report["stamps"][bib_name][key] == "EVIDENCE-EXISTENCE"
    assert calls == []                      # the corroborator was never called


def test_claimed_core_with_a_key_is_corroborated_normally(tmp_path, monkeypatch):
    """Control for the pre-classification: `core` is unprobeable only
    WITHOUT a key. With one, the entry takes the ordinary path."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.setenv("CORE_API_KEY", "sk-core")
    key = _corroboration_domain(tmp_path, source="core")
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "core"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "corroborated", "source": "core", "claimed": "core"}
    assert report["stamps"][bib_name][key] == "EVIDENCE-ABSTRACT"
    assert len(calls) == 1


def test_claimed_s2_without_a_doi_is_probe_unavailable(tmp_path, monkeypatch):
    """A bib entry carries no Semantic Scholar id, so the s2 probe needs a
    DOI. Without one the claimed source cannot be asked at all -- same
    pre-classification, same fail-closed direction."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path, source="s2", doi=None)
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "probe_unavailable", "source": "s2", "claimed": "s2"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is False
    assert report["stamps"][bib_name][key] == "EVIDENCE-NONE"
    assert calls == []


def test_claimed_s2_with_a_doi_is_corroborated_normally(tmp_path, monkeypatch):
    """Control for the DOI half of the pre-classification (a mutant that
    always pre-classifies s2 as unprobeable turns this red)."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path, source="s2", doi="10.5/withdoi")
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    assert report["stamps"]["literature-domain-1.bib"][key] == "EVIDENCE-ABSTRACT"
    assert len(calls) == 1


def test_claimed_openalex_without_a_doi_is_probe_unavailable(tmp_path, monkeypatch):
    """A bib entry carries no OpenAlex id, so the openalex probe needs a
    DOI (`_probe_candidate` gates on `if not doi`) -- same
    pre-classification as s2, same fail-closed direction. Before this
    shape was covered it reached the corroborator, came back source_empty
    with zero network, and RESET the consecutive-transport streak: the
    `calls == []` assertion is the streak proof, since `record` is only
    ever called after a probe."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path, source="openalex", doi=None)
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "openalex"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "probe_unavailable", "source": "openalex",
        "claimed": "openalex"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is False
    assert report["stamps"][bib_name][key] == "EVIDENCE-NONE"
    assert calls == []


def test_claimed_openalex_with_a_doi_is_corroborated_normally(tmp_path, monkeypatch):
    """Control for the DOI half (a mutant that always pre-classifies
    openalex as unprobeable turns this red)."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path, source="openalex", doi="10.5/oa")
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "openalex"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    assert report["stamps"]["literature-domain-1.bib"][key] == "EVIDENCE-ABSTRACT"
    assert len(calls) == 1


def test_claimed_ndpr_without_a_title_is_unprobeable_and_with_one_is_not(monkeypatch):
    """Unit-level parity pin for the ndpr shape (near-unreachable in a real
    bib, so no execute()-level fixture): `_probe_candidate` gates ndpr on
    `if not title` after `.strip()` -- the predicate must make the same
    call. Without this branch, a title-less DOI-less ndpr claim in a
    keyless-CORE workspace is a zero-network source_empty that resets the
    consecutive-transport streak, the same defect as the openalex shape."""
    eb_mod = _barrier(monkeypatch)
    assert eb_mod._claimed_source_unprobeable({"title": "   "}, "ndpr") is True
    assert eb_mod._claimed_source_unprobeable({}, "ndpr") is True
    assert eb_mod._claimed_source_unprobeable({"title": "A Book"}, "ndpr") is False


def test_claimed_core_with_a_key_but_no_doi_or_title_is_unprobeable(monkeypatch):
    """The key is only HALF of CORE's precondition: `_probe_candidate` gates
    core on `if not core_api_key or not (doi or title)`, so a keyed workspace
    still cannot ask CORE about an entry carrying neither. Without this
    conjunct the entry reached the corroborator, whose core probe returned
    empty with no request (and s2/openalex too, both DOI-gated), producing a
    zero-network source_empty that RESET the consecutive-transport streak --
    the same defect as the openalex and ndpr shapes above."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.setenv("CORE_API_KEY", "core-key")
    assert eb_mod._claimed_source_unprobeable({"title": "  "}, "core") is True
    assert eb_mod._claimed_source_unprobeable({}, "core") is True
    # controls: either identifier alone makes the probe possible
    assert eb_mod._claimed_source_unprobeable(
        {"title": "A Book"}, "core") is False
    assert eb_mod._claimed_source_unprobeable(
        {"doi": "10.1/x"}, "core") is False


def test_an_uncorroborated_entry_can_still_earn_context(tmp_path, monkeypatch):
    """"Proceed exactly like any unattested entry" means the ordinary
    downstream tiers stay reachable -- no new code path, no dead end: this
    entry loses ABSTRACT to a mismatch and then earns CONTEXT from the SEP
    article it matches."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(
        tmp_path, abstract="FABRICATED FINDINGS.", author="Kuhn, Thomas S.",
        year="1962", title="The Structure of Scientific Revolutions",
        cleaning_entries={},
        slugs='{"sep_entries": ["test-entry"], "iep_entries": []}')
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("mismatch", None), calls,
                       articles={"sep:test-entry": KUHN_ARTICLE})
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["acquisition"][bib_name][key]["outcome"] == "matched"
    assert report["stamps"][bib_name][key] == "EVIDENCE-CONTEXT"
    out = (tmp_path / bib_name).read_text(encoding="utf-8")
    assert "sep_context" in out and "EVIDENCE-ABSTRACT" not in out


def test_a_heal_is_its_own_corroboration_and_fetches_only_once(tmp_path, monkeypatch):
    """The heal path is unchanged and needs no second fetch: its own gate is
    hash equality against the ledger, and the restored text is written into
    the bib. Candidacy FAILED here (the bib text was mutated), so the
    corroborator must never be called for it."""
    eb_mod = _barrier(monkeypatch)
    import stamp_evidence as se
    true_text = "The original attested abstract text, restored."
    bib = ('@article{pasq2019,\n'
           '  abstract_source = {s2},\n'
           '  abstract = {mutated text},\n'
           '  author = {Pasquetto, Irene V.},\n'
           '  title = {Uses and Reuses},\n'
           '  doi = {10.1162/99608f92.fc14bf2d},\n'
           '  year = {2019},\n'
           '  keywords = {data-reuse, Medium}\n'
           '}')
    _domain(tmp_path, 1, bib,
            cleaning=_cleaning(1, {"pasq2019": {
                "api_matched": True, "verified_identifier": "doi",
                "verified_identifier_value": "10.1162/99608f92.fc14bf2d",
                "entry_type": "article"}}),
            enrichment=_enrichment(1, {"pasq2019": {
                "abstract_source": "s2",
                "abstract_sha256": se.abstract_hash(true_text)}}))
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("mismatch", None), calls)
    monkeypatch.setattr(eb_mod.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (true_text, "s2"))
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name]["pasq2019"] == {
        "outcome": "corroborated", "source": "s2", "claimed": "s2",
        "via": "heal"}
    assert report["healed"][bib_name]["pasq2019"] == {
        "outcome": "restored", "source": "s2"}
    assert report["stamps"][bib_name]["pasq2019"] == "EVIDENCE-ABSTRACT"
    assert calls == []                      # no second corroboration fetch


def test_a_failed_heal_splice_corrects_the_corroboration_bucket(tmp_path, monkeypatch):
    """When the heal splice is dropped for well-formedness, the entry
    demotes -- and the corroboration bucket must say so too. Otherwise the
    report contradicts itself (bucket "corroborated" beside healed
    "unhealed" and a demoted stamp) and any rate counting
    corroborated outcomes is inflated by splices that never landed."""
    eb_mod = _barrier(monkeypatch)
    import stamp_evidence as se
    broken_text = "Restored text with a rogue { brace."
    bib = ('@article{broken2020,\n'
           '  author = {Doe, Jane},\n'
           '  title = {Broken},\n'
           '  doi = {10.1/broken},\n'
           '  year = {2020},\n'
           '  abstract = {mutated text},\n'
           '  abstract_source = {s2},\n'
           '  keywords = {topic, High}\n'
           '}')
    _domain(tmp_path, 1, bib,
            cleaning=_cleaning(1, {"broken2020": {
                "api_matched": True, "verified_identifier": "doi",
                "verified_identifier_value": "10.1/broken",
                "entry_type": "article"}}),
            enrichment=_enrichment(1, {"broken2020": {
                "abstract_source": "s2",
                "abstract_sha256": se.abstract_hash(broken_text)}}))
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    monkeypatch.setattr(eb_mod.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (broken_text, "s2"))
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["healed"][bib_name]["broken2020"]["outcome"] == "unhealed"
    assert report["abstract_corroboration"][bib_name]["broken2020"] == {
        "outcome": "unhealed", "source": "s2", "claimed": "s2", "via": "heal"}
    assert report["stamps"][bib_name]["broken2020"] == "EVIDENCE-EXISTENCE"
    assert calls == []


def test_no_bucket_and_no_probe_for_an_entry_without_a_ledger_record(tmp_path, monkeypatch):
    """Candidacy is the gate on probing: an entry with no enrichment record
    is not a candidate, so it neither costs a fetch nor appears in the
    bucket (which must stay a record of candidates, or the corroboration rate
    counts entries that were never in scope)."""
    eb_mod = _barrier(monkeypatch)
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    _domain(tmp_path, 1, KUHN, cleaning=CLEAN_KUHN, enrichment=EMPTY_ENRICH)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    assert report["abstract_corroboration"].get("literature-domain-1.bib", {}) == {}
    assert calls == []


def test_compute_tier_never_grants_abstract_without_the_attestation(tmp_path, monkeypatch):
    """Tier-equivalence: neither the abstract_source field, nor a ledger
    record, nor anything a bucket could say reaches TIER_ABSTRACT on its
    own -- att.abstract_attested is the only door, and the corroboration
    gate is upstream of it.

    Non-allowlisted claims are pinned on BOTH sides of that door: candidacy
    holds for them (attest_abstract does not consult the allowlist) but the
    tier is unreachable, so the barrier must skip the probe rather than
    spend a fetch on a decision compute_tier has already made."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier as eb_mod
    import stamp_evidence as se

    def _never(*a, **k):
        raise AssertionError("corroborator called for an unreachable tier")
    monkeypatch.setattr(eb_mod.eb, "corroborate_abstract", _never)

    text = CORROB_TEXT
    for source in ("s2", "openalex", "core", "ndpr", "", "crossref"):
        for extra in ({}, {"doi": "10.1/x"}, {"sep_context": "ctx"}):
            fields = {"abstract": text, "abstract_source": source,
                      "title": "T", "author": "Doe, Jane", **extra}
            assert se.compute_tier(
                "article", fields, se.EntryAttestation()) != se.TIER_ABSTRACT
            # ... and a ledger record that would pass attest_abstract is
            # still not an attestation by itself.
            assert se.attest_abstract(fields, {
                "abstract_source": source,
                "abstract_sha256": se.abstract_hash(text)}) == bool(source)
            granted = se.compute_tier(
                "article", fields,
                se.EntryAttestation(abstract_attested=True))
            reachable = source in se.ATTESTED_ABSTRACT_SOURCES
            assert (granted == se.TIER_ABSTRACT) == reachable
            if not reachable:
                # The free bound, at unit level: no fetch is spent, and the
                # bucket says why (integration coverage in
                # test_a_claimed_source_outside_the_allowlist_is_never_probed).
                assert eb_mod._corroborate_candidate(
                    fields, eb_mod._CorroborationBudget()) == {
                        "outcome": eb_mod.PROBE_UNAVAILABLE,
                        "source": source, "claimed": source}


def test_a_crash_inside_the_corroborator_demotes_without_failing_the_run(tmp_path, monkeypatch):
    """The corroborator wraps each probe, but the shared client/limiter
    setup around them is not covered -- and a plumbing failure there must
    not take down the whole Phase 3->4 gate for the review. Same treatment
    _heal_abstract gives its own fetch: swallow, record, demote."""
    eb_mod = _barrier(monkeypatch)
    key = _corroboration_domain(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("limiter lock dir unwritable")
    monkeypatch.setattr(eb_mod.eb, "corroborate_abstract", _boom)
    monkeypatch.setattr(eb_mod.rc, "fetch_articles",
                        lambda union, debug=False: ({}, []))
    assert eb_mod.execute(tmp_path, 1) == 0          # run survives
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "probe_error", "source": "s2", "claimed": "s2"}
    assert report["attestations"][bib_name][key]["abstract_attested"] is False
    assert report["stamps"][bib_name][key] == "EVIDENCE-EXISTENCE"


def test_the_printed_summary_counts_corroboration_outcomes(tmp_path, monkeypatch):
    """Through the REAL CLI (no mocks): the demotion has to be visible to an
    operator who never opens the report, exactly like the venue and
    year_suffix pairs beside it. Offline by construction -- a claimed-`core`
    entry in a keyless workspace is pre-classified before any request, and
    venue vetting is key-gated to "skipped"."""
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    rd = tmp_path / "review"
    key = _corroboration_domain(rd, source="core")
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)["abstract_corroboration"]
    assert summary == {"candidates": 1, "corroborated": 0, "mismatch": 0,
                       "source_empty": 0, "transport_failed": 0,
                       "probe_unavailable": 1, "probe_error": 0,
                       "corroboration_deadline": 0, "other": 0}
    report = _report(rd)
    assert report["stamps"]["literature-domain-1.bib"][key] == "EVIDENCE-EXISTENCE"


def test_heal_buckets_are_excluded_from_the_summary_counts(tmp_path, monkeypatch):
    """The heal population is a DIFFERENT population (candidacy failed) with
    its own report section; folding it in would inflate the corroborated
    count the corroboration rate reads."""
    eb_mod = _barrier(monkeypatch)
    import stamp_evidence as se
    true_text = "The original attested abstract text, restored."
    bib = ('@article{pasq2019,\n'
           '  abstract_source = {s2},\n'
           '  abstract = {mutated text},\n'
           '  author = {Pasquetto, Irene V.},\n'
           '  title = {Uses and Reuses},\n'
           '  doi = {10.1162/99608f92.fc14bf2d},\n'
           '  year = {2019},\n'
           '  keywords = {data-reuse, Medium}\n'
           '}')
    _domain(tmp_path, 1, bib, cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1, {"pasq2019": {
                "abstract_source": "s2",
                "abstract_sha256": se.abstract_hash(true_text)}}))
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("mismatch", None), calls)
    monkeypatch.setattr(eb_mod.eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (true_text, "s2"))
    report, _ = eb_mod.run_barrier(tmp_path, 1)
    assert report["abstract_corroboration"]["literature-domain-1.bib"][
        "pasq2019"]["via"] == "heal"
    assert eb_mod._corroboration_summary(report) == {
        "candidates": 0, "corroborated": 0, "mismatch": 0, "source_empty": 0,
        "transport_failed": 0, "probe_unavailable": 0, "probe_error": 0,
        "corroboration_deadline": 0, "other": 0}


def _multi_candidate_domain(review_dir, keys, *, source="s2"):
    """One domain with several entries, each a passing ledger candidate."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import stamp_evidence as se
    chunks, entries = [], {}
    for n, key in enumerate(keys, start=1):
        text = f"Abstract number {n} for the corroboration budget tests."
        chunks.append('@article{' + key + ',\n'
                      '  author = {Doe, Jane},\n'
                      f'  title = {{Study {n}}},\n'
                      f'  doi = {{10.1/{key}}},\n'
                      '  year = {2020},\n'
                      f'  abstract = {{{text}}},\n'
                      f'  abstract_source = {{{source}}},\n'
                      '  keywords = {topic, High}\n'
                      '}')
        entries[key] = {"abstract_source": source,
                        "abstract_sha256": se.abstract_hash(text)}
    _domain(review_dir, 1, "\n\n".join(chunks), cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1, entries))
    return entries


def test_the_consecutive_error_breaker_stops_the_corroboration_pass(tmp_path, monkeypatch):
    """MAX_CONSECUTIVE_ERRORS = 3, mirroring venue_vetting: after three
    non-answers in a row the pass stops probing and the remaining candidates
    bucket `corroboration_deadline` instead of costing four more fetches
    each. Uses the REAL constant, so a change to it turns this red."""
    eb_mod = _barrier(monkeypatch)
    keys = ["a2020", "b2020", "c2020", "d2020", "e2020"]
    _multi_candidate_domain(tmp_path, keys)
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("transport_failed", None), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    buckets = report["abstract_corroboration"]["literature-domain-1.bib"]
    assert len(calls) == eb_mod.CORROBORATION_MAX_CONSECUTIVE_ERRORS == 3
    outcomes = [buckets[k]["outcome"] for k in keys]
    assert outcomes == ["transport_failed"] * 3 + ["corroboration_deadline"] * 2
    stamps = report["stamps"]["literature-domain-1.bib"]
    assert all(t != "EVIDENCE-ABSTRACT" for t in stamps.values())


def test_an_answer_resets_the_consecutive_error_streak(tmp_path, monkeypatch):
    """The streak counts consecutive NON-ANSWERS. A mismatch or an
    authoritative empty is an answer about the entry, so it resets the
    counter exactly as a successful lookup does in venue_vetting -- without
    this, two unrelated flaky entries plus one mismatch would stop a pass
    that is working fine."""
    eb_mod = _barrier(monkeypatch)
    keys = ["a2020", "b2020", "c2020", "d2020", "e2020"]
    _multi_candidate_domain(tmp_path, keys)
    results = iter([("transport_failed", None), ("transport_failed", None),
                    ("mismatch", None), ("transport_failed", None),
                    ("corroborated", "s2")])
    calls = []

    def _fake(fields, *a, **k):
        calls.append(dict(fields))
        return next(results)
    monkeypatch.setattr(eb_mod.eb, "corroborate_abstract", _fake)
    monkeypatch.setattr(eb_mod.rc, "fetch_articles",
                        lambda union, debug=False: ({}, []))
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    buckets = report["abstract_corroboration"]["literature-domain-1.bib"]
    assert len(calls) == 5                      # never stopped
    assert [buckets[k]["outcome"] for k in keys] == [
        "transport_failed", "transport_failed", "mismatch",
        "transport_failed", "corroborated"]
    assert report["stamps"]["literature-domain-1.bib"]["e2020"] == "EVIDENCE-ABSTRACT"


def test_the_pass_deadline_stops_the_corroboration_pass(tmp_path, monkeypatch):
    """The other bound. Checked BEFORE each probe, so it bounds the loop:
    the first candidate is always probed (that is when the clock starts),
    and every later one buckets `corroboration_deadline`."""
    eb_mod = _barrier(monkeypatch)
    # Negative, not 0.0: the deadline must be unambiguously in the past on
    # the second check regardless of clock granularity, so the test states
    # "the budget is already spent" rather than "some time passed".
    monkeypatch.setattr(eb_mod, "CORROBORATION_PASS_DEADLINE_SECONDS", -1.0)
    keys = ["a2020", "b2020", "c2020"]
    _multi_candidate_domain(tmp_path, keys)
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    buckets = report["abstract_corroboration"]["literature-domain-1.bib"]
    assert len(calls) == 1
    assert [buckets[k]["outcome"] for k in keys] == [
        "corroborated", "corroboration_deadline", "corroboration_deadline"]
    stamps = report["stamps"]["literature-domain-1.bib"]
    assert stamps["a2020"] == "EVIDENCE-ABSTRACT"      # probed in time
    assert stamps["b2020"] != "EVIDENCE-ABSTRACT"      # PENDING, re-derivable
    summary = eb_mod._corroboration_summary(report)
    assert summary["corroboration_deadline"] == 2
    assert summary["candidates"] == 3


def test_the_budget_is_one_per_run_not_one_per_domain(tmp_path, monkeypatch):
    """The bound exists to keep the whole barrier inside SKILL.md's Bash
    ceiling, so a second domain must not get a fresh allowance."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.setattr(eb_mod, "CORROBORATION_PASS_DEADLINE_SECONDS", -1.0)
    import stamp_evidence as se
    for i in (1, 2):
        text = f"Domain {i}'s abstract for the shared-budget test."
        bib = ('@article{k' + str(i) + ',\n'
               '  author = {Doe, Jane},\n'
               f'  title = {{Study {i}}},\n'
               f'  doi = {{10.1/k{i}}},\n'
               '  year = {2020},\n'
               f'  abstract = {{{text}}},\n'
               '  abstract_source = {s2},\n'
               '  keywords = {topic, High}\n'
               '}')
        _domain(tmp_path, i, bib, cleaning=_cleaning(i, {}),
                enrichment=_enrichment(i, {f"k{i}": {
                    "abstract_source": "s2",
                    "abstract_sha256": se.abstract_hash(text)}}))
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "s2"), calls)
    assert eb_mod.execute(tmp_path, 2) == 0
    report = _report(tmp_path)
    assert len(calls) == 1          # not one per domain
    assert report["abstract_corroboration"]["literature-domain-2.bib"][
        "k2"]["outcome"] == "corroboration_deadline"


def test_a_claimed_source_outside_the_allowlist_is_never_probed(tmp_path, monkeypatch):
    """The free bound. `compute_tier` grants TIER_ABSTRACT only for a source
    in ATTESTED_ABSTRACT_SOURCES, so probing anything else spends a fetch on
    a decision already made -- candidacy can still hold there, since
    attest_abstract does not check the allowlist."""
    eb_mod = _barrier(monkeypatch)
    import stamp_evidence as se
    key = _corroboration_domain(tmp_path, source="crossref")
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "crossref"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    bib_name = "literature-domain-1.bib"
    # candidacy DOES hold -- the skip is the barrier's, not attest_abstract's
    fields = se.parse_entry_fields(
        (tmp_path / bib_name).read_text(encoding="utf-8"))
    assert se.attest_abstract(fields, {
        "abstract_source": "crossref",
        "abstract_sha256": se.abstract_hash(fields["abstract"])}) is True
    assert report["abstract_corroboration"][bib_name][key] == {
        "outcome": "probe_unavailable", "source": "crossref",
        "claimed": "crossref"}
    assert calls == []
    assert report["stamps"][bib_name][key] == "EVIDENCE-EXISTENCE"


def test_a_whitespace_only_core_key_is_probed_not_pre_classified(tmp_path, monkeypatch):
    """Parity pin with `_probe_candidate`, which gates on `if not
    core_api_key` -- raw truthiness, no strip. The pre-classification must
    make the same call or it demotes an entry the probe would have answered
    for."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.setenv("CORE_API_KEY", "   ")
    key = _corroboration_domain(tmp_path, source="core")
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("corroborated", "core"), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    assert len(calls) == 1
    assert report["stamps"]["literature-domain-1.bib"][key] == "EVIDENCE-ABSTRACT"


def test_a_skipped_candidate_neither_counts_nor_resets_the_streak(tmp_path, monkeypatch):
    """The streak counts consecutive non-answers FROM THE NETWORK, so a
    candidate skipped before any request (free bound, environment
    pre-classification) must not reset it -- otherwise a run of unprobeable
    claims interleaved with real failures hides a live outage and the
    breaker never trips. Interleaving here: fail, skip, fail, skip, fail."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    import stamp_evidence as se
    order = ["f1", "skip_allow", "f2", "skip_core", "f3", "f4"]
    chunks, entries = [], {}
    for n, key in enumerate(order, start=1):
        source = {"skip_allow": "crossref", "skip_core": "core"}.get(key, "s2")
        text = f"Streak abstract {n}."
        chunks.append('@article{' + key + ',\n'
                      '  author = {Doe, Jane},\n'
                      f'  title = {{Study {n}}},\n'
                      f'  doi = {{10.1/{key}}},\n'
                      '  year = {2020},\n'
                      f'  abstract = {{{text}}},\n'
                      f'  abstract_source = {{{source}}},\n'
                      '  keywords = {topic, High}\n'
                      '}')
        entries[key] = {"abstract_source": source,
                        "abstract_sha256": se.abstract_hash(text)}
    _domain(tmp_path, 1, "\n\n".join(chunks), cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1, entries))
    calls = []
    _stub_corroborator(monkeypatch, eb_mod, ("transport_failed", None), calls)
    assert eb_mod.execute(tmp_path, 1) == 0
    buckets = _report(tmp_path)["abstract_corroboration"]["literature-domain-1.bib"]
    # three real non-answers trip the breaker even though two skips sat
    # between them; the sixth candidate is never probed
    assert len(calls) == 3
    assert [buckets[k]["outcome"] for k in order] == [
        "transport_failed", "probe_unavailable", "transport_failed",
        "probe_unavailable", "transport_failed", "corroboration_deadline"]


def test_a_doiless_openalex_claim_does_not_reset_the_streak(tmp_path, monkeypatch):
    """The reported defect end-to-end, with a FIELD-SENSITIVE stub that
    plays the real corroborator's part: for a DOI-less openalex claim in
    this keyless-CORE environment every probe is empty without a request,
    so the corroborator returns source_empty -- which record() treats as an
    ANSWER and resets the streak. Pre-fix trace: all six entries probed
    (calls == 6), the two source_empty resets keep the breaker from ever
    tripping. Post-fix: the two skips are pre-classified (never probed,
    neither count nor reset), f3 trips the breaker at the third consecutive
    transport failure, f4 buckets corroboration_deadline without a probe."""
    eb_mod = _barrier(monkeypatch)
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    import stamp_evidence as se
    order = ["f1", "skip_oa1", "f2", "skip_oa2", "f3", "f4"]
    chunks, entries = [], {}
    for n, key in enumerate(order, start=1):
        source = "openalex" if key.startswith("skip_oa") else "s2"
        doi_line = "" if key.startswith("skip_oa") else f"  doi = {{10.1/{key}}},\n"
        text = f"Streak abstract {n}."
        chunks.append('@article{' + key + ',\n'
                      '  author = {Doe, Jane},\n'
                      f'  title = {{Study {n}}},\n'
                      + doi_line +
                      '  year = {2020},\n'
                      f'  abstract = {{{text}}},\n'
                      f'  abstract_source = {{{source}}},\n'
                      '  keywords = {topic, High}\n'
                      '}')
        entries[key] = {"abstract_source": source,
                        "abstract_sha256": se.abstract_hash(text)}
    _domain(tmp_path, 1, "\n\n".join(chunks), cleaning=_cleaning(1, {}),
            enrichment=_enrichment(1, entries))
    calls = []

    def _outage_stub(fields, s2_api_key=None, openalex_email=None,
                     core_api_key=None, debug=False):
        calls.append(dict(fields))
        if not fields.get("doi"):
            return ("source_empty", None)   # zero-network empty, pre-fix
        return ("transport_failed", None)   # the live outage
    monkeypatch.setattr(eb_mod.eb, "corroborate_abstract", _outage_stub)
    monkeypatch.setattr(eb_mod.rc, "fetch_articles",
                        lambda union, debug=False: ({}, []))

    assert eb_mod.execute(tmp_path, 1) == 0
    report = _report(tmp_path)
    buckets = report["abstract_corroboration"]["literature-domain-1.bib"]
    assert [buckets[k]["outcome"] for k in order] == [
        "transport_failed", "probe_unavailable", "transport_failed",
        "probe_unavailable", "transport_failed", "corroboration_deadline"]
    assert len(calls) == 3


def test_an_unrecognized_outcome_neither_counts_nor_resets(tmp_path, monkeypatch):
    """`record` names the answer set explicitly rather than treating
    "anything that is not an error" as an answer: a token this class has
    never seen is no evidence either way, and the report files it under
    `other` for the same reason."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier as eb_mod
    budget = eb_mod._CorroborationBudget()
    budget.record(eb_mod.eb.TRANSPORT_FAILED)
    budget.record("something_new")
    assert budget.consecutive_errors == 1     # not reset, not incremented
    budget.record(eb_mod.eb.MISMATCH)
    assert budget.consecutive_errors == 0     # a real answer does reset
    assert budget.stopped is False


# ---------------------------------------------------------------------------
# same_work_group: the barrier's advisory reprint annotation (the Reiman
# defect -- a reprint and its original never merge, because a coherent
# reprint year defeats the title axis by design, so the synthesis writer can
# cite one essay as two positions). The annotation lands at the Phase 3->4
# barrier because Phase 6's dedup runs after the prose is written.
# ---------------------------------------------------------------------------

_SW_ORIGINAL = """@incollection{reiman1984panopticon,
  author = {Reiman, Jeffrey H.},
  title = {Driving to the Panopticon},
  booktitle = {Philosophical Dimensions of Privacy},
  publisher = {Cambridge University Press},
  doi = {10.1000/orig1984},
  year = {1984}
}"""

# Distinct DOI, distinct container, distinct key: the annotation must fire
# regardless of DOI, unlike dedup's merge, which a reprint's own DOI blocks.
_SW_REPRINT = """@incollection{reiman2017panopticon,
  author = {Reiman, Jeffrey H.},
  title = {Driving to the Panopticon},
  booktitle = {Privacy, Security and Accountability},
  publisher = {Rowman and Littlefield},
  doi = {10.1000/reprint2017},
  year = {2017}
}"""

_SW_ORIGINAL_KEY = "reiman1984panopticon"
_SW_REPRINT_KEY = "reiman2017panopticon"
_SW_BOTH = f"{_SW_ORIGINAL_KEY}, {_SW_REPRINT_KEY}"

# No `journal` field anywhere in these fixtures, deliberately: venue vetting
# collects journal names only, so the venue pass looks nothing up and the
# only optional splice these tests can exercise is the one under test.
_SW_ORIGINAL_2017 = _SW_ORIGINAL.replace(
    "doi = {10.1000/orig1984}", "doi = {10.1000/reprint2017}").replace(
    "year = {1984}", "year = {2017}")


def _sw_domain(review_dir, i, bib_text):
    _domain(review_dir, i, bib_text, cleaning=_cleaning(i, {}),
            enrichment=_enrichment(i))


def _sw_review(tmp_path, name="review"):
    """The cross-domain reprint pair: original in domain 1, reissue in 2."""
    rd = tmp_path / name
    _sw_domain(rd, 1, _SW_ORIGINAL)
    _sw_domain(rd, 2, _SW_REPRINT)
    return rd


def _sw_entry(review_dir, i, key):
    """The raw chunk for one citekey in one domain bib."""
    content = (review_dir / f"literature-domain-{i}.bib").read_text(
        encoding="utf-8")
    return [c for c in content.split("\n@") if "{" + key + "," in c][0]


def _sw_bib(review_dir, i):
    return (review_dir / f"literature-domain-{i}.bib").read_text(
        encoding="utf-8")


def test_first_surname_raw_alias_is_the_shared_object():
    """The barrier parses surnames the way the rest of the pipeline does --
    via year_suffix's parser, aliased rather than copied (repo convention:
    sites keep historic names as aliases to the shared object)."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import year_suffix
    assert year_suffix.first_surname_raw is year_suffix._first_surname_raw


def test_cross_domain_reprint_pair_is_stamped_and_reported(tmp_path):
    rd = _sw_review(tmp_path)
    r = _run(rd, 2)
    assert r.returncode == 0, r.stderr
    for i, key in ((1, _SW_ORIGINAL_KEY), (2, _SW_REPRINT_KEY)):
        chunk = _sw_entry(rd, i, key)
        assert "same_work_group = {" in chunk
        assert _SW_BOTH in chunk
    report = _report(rd)
    groups = report["same_work"]["groups"]
    assert len(groups) == 1
    assert sorted(m["key"] for m in groups[0]["members"]) == [
        _SW_ORIGINAL_KEY, _SW_REPRINT_KEY]
    assert sorted(m["year"] for m in groups[0]["members"]) == ["1984", "2017"]
    assert groups[0]["key_year_conflict"] == []
    assert sorted(report["same_work"]["stamped_entries"]) == [
        f"literature-domain-1.bib:{_SW_ORIGINAL_KEY}",
        f"literature-domain-2.bib:{_SW_REPRINT_KEY}"]
    assert report["same_work"]["splice_failed"] == []
    assert json.loads(r.stdout)["same_work"] == {
        "groups": 1, "stamped_entries": 2, "splice_failed": 0}


def test_distinct_years_required(tmp_path):
    """Same title and surname in the SAME year is not a reprint pair -- it is
    dedup's and year_suffix's business, and an advisory here would only add
    noise."""
    rd = tmp_path / "review"
    _sw_domain(rd, 1, _SW_ORIGINAL)
    _sw_domain(rd, 2, _SW_REPRINT.replace("year = {2017}", "year = {1984}"))
    r = _run(rd, 2)
    assert r.returncode == 0, r.stderr
    for i in (1, 2):
        assert "same_work_group" not in _sw_bib(rd, i)
    assert _report(rd)["same_work"]["groups"] == []


def test_hand_written_same_work_group_is_stripped(tmp_path):
    """The field joins the barrier-owned set: a value the barrier did not
    derive this run must not survive it."""
    rd = tmp_path / "review"
    forged = _SW_ORIGINAL.replace(
        "  year = {1984}",
        "  same_work_group = {bogus1999, bogus2001},\n  year = {1984}")
    _sw_domain(rd, 1, forged)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    content = _sw_bib(rd, 1)
    assert "same_work_group" not in content
    assert "bogus" not in content
    assert _report(rd)["same_work"]["groups"] == []


def test_same_key_across_domains_is_reported_not_stamped(tmp_path):
    """Two domains holding the SAME citekey with divergent years is an
    overlap inconsistency, not a reprint pair: a self-referential
    `same_work_group = {key}` would only confuse the writer. Reported,
    never stamped."""
    rd = tmp_path / "review"
    _sw_domain(rd, 1, _SW_ORIGINAL)
    _sw_domain(rd, 2, _SW_ORIGINAL_2017)
    r = _run(rd, 2)
    assert r.returncode == 0, r.stderr
    for i in (1, 2):
        assert "same_work_group" not in _sw_bib(rd, i)
    report = _report(rd)
    groups = report["same_work"]["groups"]
    assert len(groups) == 1
    assert {m["key"] for m in groups[0]["members"]} == {_SW_ORIGINAL_KEY}
    assert sorted(m["year"] for m in groups[0]["members"]) == ["1984", "2017"]
    assert groups[0]["key_year_conflict"] == [_SW_ORIGINAL_KEY]
    assert report["same_work"]["stamped_entries"] == []
    # The case `groups` earns its keep in the printed summary: a group WAS
    # detected, and it reaches neither stamped_entries nor splice_failed.
    assert json.loads(r.stdout)["same_work"] == {
        "groups": 1, "stamped_entries": 0, "splice_failed": 0}


def test_mixed_group_with_consistent_duplicate_key_is_stamped(tmp_path):
    """A/1984, A/1984, B/2017: the duplicated key is internally
    year-consistent, so the writer can still tell the records apart by key
    and all three members are stamped."""
    rd = tmp_path / "review"
    _sw_domain(rd, 1, _SW_ORIGINAL)
    _sw_domain(rd, 2, _SW_ORIGINAL)          # same key, same year
    _sw_domain(rd, 3, _SW_REPRINT)
    r = _run(rd, 3)
    assert r.returncode == 0, r.stderr
    for i, key in ((1, _SW_ORIGINAL_KEY), (2, _SW_ORIGINAL_KEY),
                   (3, _SW_REPRINT_KEY)):
        assert _SW_BOTH in _sw_entry(rd, i, key)
    report = _report(rd)
    assert report["same_work"]["groups"][0]["key_year_conflict"] == []
    assert sorted(report["same_work"]["stamped_entries"]) == [
        f"literature-domain-1.bib:{_SW_ORIGINAL_KEY}",
        f"literature-domain-2.bib:{_SW_ORIGINAL_KEY}",
        f"literature-domain-3.bib:{_SW_REPRINT_KEY}"]


def test_mixed_group_with_conflicting_duplicate_key_is_not_stamped(tmp_path):
    """A/1984, A/2017, B/2017: key A carries two comparison years, so the
    writer cannot tell the two A records apart by key at all. A stamp would
    certify confusion rather than resolve it -- report, do not stamp."""
    rd = tmp_path / "review"
    _sw_domain(rd, 1, _SW_ORIGINAL)
    _sw_domain(rd, 2, _SW_ORIGINAL_2017)
    _sw_domain(rd, 3, _SW_REPRINT)
    r = _run(rd, 3)
    assert r.returncode == 0, r.stderr
    for i in (1, 2, 3):
        assert "same_work_group" not in _sw_bib(rd, i)
    report = _report(rd)
    groups = report["same_work"]["groups"]
    assert len(groups) == 1
    assert groups[0]["key_year_conflict"] == [_SW_ORIGINAL_KEY]
    assert len(groups[0]["members"]) == 3
    assert report["same_work"]["stamped_entries"] == []


def test_within_domain_pair_groups_too(tmp_path):
    """Grouping is review-wide, not cross-domain-only: one domain holding
    both the original and the reissue is the same defect."""
    rd = tmp_path / "review"
    _sw_domain(rd, 1, _SW_ORIGINAL + "\n\n" + _SW_REPRINT)
    r = _run(rd, 1)
    assert r.returncode == 0, r.stderr
    for key in (_SW_ORIGINAL_KEY, _SW_REPRINT_KEY):
        assert _SW_BOTH in _sw_entry(rd, 1, key)
    report = _report(rd)
    assert len(report["same_work"]["groups"]) == 1
    assert len(report["same_work"]["stamped_entries"]) == 2


def test_splice_failure_is_reverted_and_reported(tmp_path, monkeypatch):
    """The optional pass's one live data-loss shape. A splice that would
    leave a DUPLICATE field costs all of Phase 6 (pybtex rejects it), so the
    chunk is reverted -- and the loss is reported rather than swallowed,
    which is what the gate-failure policy forbids."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    def _double_splice(entry_text, field, value):
        lines = entry_text.split("\n")
        lines.insert(1, f"  {field} = {{{value}}},")
        lines.insert(1, f"  {field} = {{{value}}},")
        return "\n".join(lines)

    # Control run: the annotation pass yields nothing, so the comparison
    # below is a BYTE-identity check on the revert, not merely a check that
    # the output happens to parse.
    control = _sw_review(tmp_path, "control")
    monkeypatch.setattr(evidence_barrier, "_same_work_groups",
                        lambda parsed: ({}, []))
    assert evidence_barrier.execute(control, 2) == 0
    expected = [_sw_bib(control, i) for i in (1, 2)]
    monkeypatch.undo()

    rd = _sw_review(tmp_path, "review")
    monkeypatch.setattr(evidence_barrier, "_stamp_optional_field",
                        _double_splice)
    assert evidence_barrier.execute(rd, 2) == 0
    assert [_sw_bib(rd, i) for i in (1, 2)] == expected   # reverted, byte-wise
    report = _report(rd)
    assert report["same_work"]["stamped_entries"] == []
    assert sorted(report["same_work"]["splice_failed"]) == [
        f"literature-domain-1.bib:{_SW_ORIGINAL_KEY}",
        f"literature-domain-2.bib:{_SW_REPRINT_KEY}"]


def test_a_same_work_splice_failure_reaches_the_printed_summary(
        tmp_path, monkeypatch, capsys):
    """SKILL.md makes the printed summary the OPERATOR channel -- the report
    JSON is opened only when a summary line flags something. A swallowed or
    reverted splice means the reprint annotation never reached that entry, so
    the writer can still cite one essay as two positions with nothing saying
    so. The repo closed this identical omission for year_suffix (2026-08-06),
    venue_status (2026-08-11) and the web pair (2026-08-16)."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    def _double_splice(entry_text, field, value):
        lines = entry_text.split("\n")
        lines.insert(1, f"  {field} = {{{value}}},")
        lines.insert(1, f"  {field} = {{{value}}},")
        return "\n".join(lines)

    rd = _sw_review(tmp_path)
    monkeypatch.setattr(evidence_barrier, "_stamp_optional_field",
                        _double_splice)
    assert evidence_barrier.execute(rd, 2) == 0
    assert json.loads(capsys.readouterr().out)["same_work"] == {
        "groups": 1, "stamped_entries": 0, "splice_failed": 2}


def test_same_work_groups_compute_failure_fails_open(tmp_path, monkeypatch, capsys):
    """The compute itself (_same_work_groups) is ADVISORY plumbing, not part
    of the accuracy gate -- an exception here must not kill the whole
    barrier. It must not vanish silently either: compute_failed carries the
    error into both the report and the printed operator summary."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier

    def boom(parsed):
        raise RuntimeError("same-work compute exploded")

    rd = _sw_review(tmp_path)
    monkeypatch.setattr(evidence_barrier, "_same_work_groups", boom)
    assert evidence_barrier.execute(rd, 2) == 0          # NOT a failed run
    report = _report(rd)
    assert report["status"] in ("complete", "degraded")
    assert "same-work compute exploded" in report["same_work"]["compute_failed"]
    assert report["same_work"]["groups"] == []

    summary = json.loads(capsys.readouterr().out)
    assert "same-work compute exploded" in summary["same_work"]["compute_failed"]


def test_year_variants_group_via_same_work_year(tmp_path):
    """The comparison year is whole-field: a Chicago suffix is not a second
    publication year, but a genuinely different year is."""
    same = tmp_path / "same"
    _sw_domain(same, 1, _SW_ORIGINAL)
    _sw_domain(same, 2, _SW_REPRINT.replace("year = {2017}", "year = {1984a}"))
    r = _run(same, 2)
    assert r.returncode == 0, r.stderr
    assert _report(same)["same_work"]["groups"] == []
    for i in (1, 2):
        assert "same_work_group" not in _sw_bib(same, i)

    diff = tmp_path / "diff"
    _sw_domain(diff, 1, _SW_ORIGINAL.replace("year = {1984}", "year = {1984a}"))
    _sw_domain(diff, 2, _SW_REPRINT)
    r = _run(diff, 2)
    assert r.returncode == 0, r.stderr
    report = _report(diff)
    assert len(report["same_work"]["groups"]) == 1
    assert sorted(m["year"] for m in report["same_work"]["groups"][0]["members"]) \
        == ["1984", "2017"]
    assert len(report["same_work"]["stamped_entries"]) == 2


def test_barrier_rerun_is_idempotent(tmp_path):
    """The barrier re-runs on workflow resume: the second run must strip the
    first run's stamp and re-stamp cleanly, never accumulate a duplicate.

    Byte-equality is asserted from the SECOND run on, not from the first.
    A first run inserts `keywords` after the header line of an entry that had
    none, landing it above the freshly spliced `same_work_group`; on every
    later run `keywords` is updated in place while the field is re-inserted
    after the header, so the two swap once and then stay put. The stamp
    itself is unchanged throughout -- that ordering settles after one run and
    is what "idempotent" means here."""
    rd = _sw_review(tmp_path)
    assert _run(rd, 2).returncode == 0
    assert _run(rd, 2).returncode == 0
    second = [_sw_bib(rd, i) for i in (1, 2)]
    for content in second:
        assert content.count("same_work_group") == 1
        assert _SW_BOTH in content
    assert _run(rd, 2).returncode == 0
    assert [_sw_bib(rd, i) for i in (1, 2)] == second     # a fixed point
    assert len(_report(rd)["same_work"]["stamped_entries"]) == 2


def test_three_member_group_stamps_all(tmp_path):
    """Every member carries every key, so the writer sees the whole group
    from whichever entry it is looking at."""
    rd = tmp_path / "review"
    third = _SW_ORIGINAL.replace(
        _SW_ORIGINAL_KEY, "reiman1995panopticon").replace(
        "doi = {10.1000/orig1984}", "doi = {10.1000/mid1995}").replace(
        "year = {1984}", "year = {1995}")
    _sw_domain(rd, 1, _SW_ORIGINAL)
    _sw_domain(rd, 2, third)
    _sw_domain(rd, 3, _SW_REPRINT)
    r = _run(rd, 3)
    assert r.returncode == 0, r.stderr
    expected = ("reiman1984panopticon, reiman1995panopticon, "
                "reiman2017panopticon")
    for i, key in ((1, _SW_ORIGINAL_KEY), (2, "reiman1995panopticon"),
                   (3, _SW_REPRINT_KEY)):
        assert expected in _sw_entry(rd, i, key)
    assert len(_report(rd)["same_work"]["stamped_entries"]) == 3


def test_incomplete_entries_are_skipped_not_poisoning(tmp_path):
    """A year-less entry has no comparison year, so it never groups -- and
    it must not suppress the real pair either."""
    rd = tmp_path / "review"
    yearless = _SW_ORIGINAL.replace(
        _SW_ORIGINAL_KEY, "reimanNoYearPanopticon").replace(
        "doi = {10.1000/orig1984}", "doi = {10.1000/noyear}").replace(
        ",\n  year = {1984}", "")
    _sw_domain(rd, 1, _SW_ORIGINAL)
    _sw_domain(rd, 2, _SW_REPRINT)
    _sw_domain(rd, 3, yearless)
    r = _run(rd, 3)
    assert r.returncode == 0, r.stderr
    for i, key in ((1, _SW_ORIGINAL_KEY), (2, _SW_REPRINT_KEY)):
        assert _SW_BOTH in _sw_entry(rd, i, key)
    assert "same_work_group" not in _sw_bib(rd, 3)
    report = _report(rd)
    assert len(report["same_work"]["groups"]) == 1
    assert len(report["same_work"]["groups"][0]["members"]) == 2
    assert len(report["same_work"]["stamped_entries"]) == 2


def test_strip_reaches_bare_nested_and_compact_derived_fields():
    """The three shapes the regex strip documented as accepted residuals --
    a bare-token value, a nested-brace value, and a field not opening its
    line (on the header line, or trailing another field) -- are all removed
    now that the strip locates fields structurally (bib_fields). Every owned
    field, every shape; the neighbours survive byte for byte."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from evidence_barrier import _strip_derived_fields
    from pybtex.database import parse_string
    entry = ("@article{k,venue_status = low-visibility,\n"
             "  author = {A}, year_suffix = {a},\n"
             "  title = {T},\n"
             "  same_work_group = {x {nested {deep}} y},\n"
             '  urldate = "2024-01-01", archiveurl = {https://a/b},\n'
             "  year = {2020}\n}")
    out = _strip_derived_fields(entry)
    for name in ("venue_status", "year_suffix", "same_work_group",
                 "urldate", "archiveurl"):
        assert name not in out, name
    assert "author = {A}" in out and "title = {T}" in out and "year = {2020}" in out
    parse_string(out, "bibtex")


def test_strip_does_not_touch_field_shaped_text_inside_a_value():
    """The reason the regex was never widened: a looser anchor could begin a
    match INSIDE an abstract. A structural locator cannot."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from evidence_barrier import _strip_derived_fields
    entry = ("@article{k,\n"
             "  abstract = {We set venue_status = {low} and year_suffix = {a} here.},\n"
             "  year = {2020}\n}")
    assert _strip_derived_fields(entry) == entry


def test_strip_regex_covers_same_work_group():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from evidence_barrier import _strip_derived_fields
    entry = ("@article{k,\n  author = {A, B},\n"
             "  same_work_group = {x, y},\n  year = {2020},\n}")
    assert "same_work_group" not in _strip_derived_fields(entry)


def test_quoted_form_hand_written_field_is_stripped():
    """pybtex's writer emits quoted fields on round-trip, so every regex over
    .bib text must match both forms."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from evidence_barrier import _strip_derived_fields
    entry = ('@article{k,\n  author = {A, B},\n'
             '  same_work_group = "x, y",\n  year = {2020},\n}')
    assert "same_work_group" not in _strip_derived_fields(entry)


def test_value_embedded_literal_is_not_mistaken_for_a_field():
    """_derived_field_took's condition 2 is a field PARSE, not a substring
    count: a splice that lands the text INSIDE another field's value must be
    rejected."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from evidence_barrier import _derived_field_took, _SAME_WORK_FIELD_RE
    before = "@article{k,\n  title = {A title},\n  year = {2020},\n}"
    after = ("@article{k,\n  title = {A title same_work_group = {a, b}},\n"
             "  year = {2020},\n}")
    assert not _derived_field_took(
        after, before, "same_work_group", "a, b", _SAME_WORK_FIELD_RE)


# ---------------------------------------------------------------------------
# The nested-brace field drop, seen from its two consumers. parse_entry_fields
# used to lose any field whose value nested braces two deep -- the standard
# LaTeX accent form -- so an accented first author had no surname axis: no
# same_work_group stamp, and no a/b letters (the entry fell out of
# assign_suffixes as author-less). Measured at 33 of 8,894 delivered entries
# (docs/known-issues/field-parse-divergence-measurement-2026-09-02/).
# ---------------------------------------------------------------------------

_ACCENTED_AUTHOR = r"Mendon{\c{c}}a, Ricardo F."


def test_accented_author_reprint_pair_is_stamped(tmp_path):
    rd = tmp_path / "review"
    _sw_domain(rd, 1, _SW_ORIGINAL.replace("Reiman, Jeffrey H.", _ACCENTED_AUTHOR))
    _sw_domain(rd, 2, _SW_REPRINT.replace("Reiman, Jeffrey H.", _ACCENTED_AUTHOR))
    r = _run(rd, 2)
    assert r.returncode == 0, r.stderr
    for i, key in ((1, _SW_ORIGINAL_KEY), (2, _SW_REPRINT_KEY)):
        chunk = _sw_entry(rd, i, key)
        assert "same_work_group = {" in chunk
        assert _SW_BOTH in chunk
    groups = _report(rd)["same_work"]["groups"]
    assert len(groups) == 1
    assert groups[0]["surname_key"]  # the surname axis is populated, not ""


def test_accented_same_author_same_year_gets_letters(tmp_path):
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    rd = tmp_path / "review"
    _domain(rd, 1, MENARY_D1.replace("Menary, Richard", r"Garc{\'{i}}a, Richard"),
            cleaning=_cleaning(1, {}), enrichment=_enrichment(1))
    assert evidence_barrier.execute(rd, 1) == 0
    content = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    assert "year_suffix = {a}" in content
    assert "year_suffix = {b}" in content
    assert _report(rd)["year_suffixes"]["assigned"] == 2


def test_unparseable_bib_is_never_field_scanned(tmp_path, monkeypatch):
    """`bib_fields`' safety argument rests on a CALL-ORDER property, not on
    anything in that module: its scan of text pybtex refuses is meaningless,
    and harmless only because the strict gate runs first. Two reviewers noted
    the ordering was prose-only; a third then noted that asserting the final
    outputs does not distinguish "never scanned" from "scanned, then results
    discarded". So SPY on the scanner: it must not be called for a bib pybtex
    refuses, and the run must fail closed."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    rd = tmp_path / "review"
    # A `%` at field position -- exactly the form bib_fields' docstring says
    # pybtex refuses and the scan reads meaninglessly.
    bad = '@article{smith2020data,\n  title = {A},\n  year = {2020} % }\n'
    _domain(rd, 1, bad, cleaning=_cleaning(1, []), enrichment=EMPTY_ENRICH)

    scanned = []
    real = se.parse_entry_fields
    def spy(chunk):
        scanned.append(chunk)
        return real(chunk)
    monkeypatch.setattr(se, "parse_entry_fields", spy)

    rc = evidence_barrier.execute(rd, 1)

    # The property itself: the scanner never saw the refused text.
    assert not any("smith2020data" in c for c in scanned), (
        f"a bib pybtex refuses was field-scanned anyway: {scanned!r}")
    # And it fails CLOSED -- nonzero is what stops the orchestrator advancing
    # to Phase 4 (SKILL.md) -- with the file left byte-identical.
    assert rc != 0
    report = _report(rd)
    assert report["domains"]["1"]["bib"] == "malformed"
    assert report["status"] == "failed"
    assert "literature-domain-1.bib" not in report.get("stamps", {})
    assert (rd / "literature-domain-1.bib").read_text(encoding="utf-8") == bad


def test_the_field_scan_spy_is_actually_wired(tmp_path, monkeypatch):
    """Guard against the sibling test above passing vacuously. If the spy is
    not hooked into the path the barrier really uses, `scanned` is empty for
    EVERY input and the call-order assertion proves nothing -- which is the
    failure mode that let an earlier `@string` test pass green while the claim
    it pinned was false. So assert the spy fires on a bib pybtex ACCEPTS."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evidence_barrier
    import stamp_evidence as se

    rd = tmp_path / "review"
    _domain(rd, 1, DOI_ENTRY, cleaning=_cleaning(1, []), enrichment=EMPTY_ENRICH)

    scanned = []
    real = se.parse_entry_fields
    def spy(chunk):
        scanned.append(chunk)
        return real(chunk)
    monkeypatch.setattr(se, "parse_entry_fields", spy)

    evidence_barrier.execute(rd, 1)
    assert any("smith2020data" in c for c in scanned), (
        "the spy never fired on a parseable bib: it is not on the barrier's "
        "field-scanning path, so the call-order test beside it is vacuous")
