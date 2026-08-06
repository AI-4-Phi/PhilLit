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


def test_web_source_count(tmp_path):
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
    assert report["web_sources_none"]["count"] == 1
    assert report["web_sources_none"]["keys"] == [
        "literature-domain-1.bib:blogpost2024ai"]
    assert json.loads(r.stdout)["web_sources_none"] == 1


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
    """Option C (divergence write-up §9): a cleaner abstention attests
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
    assert report["schema_version"] == 1
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
    """Malformed ledger record (review finding 1b): never raises."""
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


# --- Review round 2 (2026-08-01): fix-verification tests -------------------

def test_barrier_heals_two_level_nested_mutated_abstract_end_to_end(tmp_path, monkeypatch):
    """Review finding 1's own reproduction case, run end-to-end through the
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
    (review finding 2): with add_field_to_entry monkeypatched to a no-op,
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


# --- Item 3 D: venue vetting ---

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
    """A braced- or quoted-value venue_status is stripped before the pass and
    only re-added on this run's own verdict. Narrower than "cannot inject
    the flag" in general: _strip_derived_fields's regex covers only these two
    forms (single-nesting-level braced, or quoted) -- a bare-token value
    (`venue_status = low-visibility,`) or a nested-brace value
    (`venue_status = {low {x} vis}`) are accepted, documented limits of the
    regex (see _strip_derived_fields's docstring) that this test does not
    cover."""
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
    """Pins tests/conftest.py's session-scoped isolation fixture: item 3 D
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


# --- Item 3 F: Chicago a/b suffixes ---

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
    for key in ("groups", "overflow", "suppressed", "conflicts"):
        assert suffixes[key] == [], key


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
        "assigned": 0, "overflow": 0, "suppressed": 1}


def test_both_optional_passes_stamp_together(tmp_path, monkeypatch):
    """Item 3 D's venue flag and item 3 F's Chicago letter are stamped by two
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
