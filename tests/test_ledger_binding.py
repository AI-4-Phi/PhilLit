"""Tests for hooks/ledger_binding.py -- the one owner of the ledger-to-bib
content binding, and the round trip that proves both sides agree.

A drift between producer and consumer would reject every ledger silently, so
the identity assertions here are load-bearing, not decoration.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
SCRIPTS_DIR = (Path(__file__).parent.parent / "skills" / "literature-review"
               / "scripts")
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import ledger_binding as lb  # noqa: E402

BARRIER = SCRIPTS_DIR / "evidence_barrier.py"

KUHN = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  publisher = {University of Chicago Press},
  year = {1962},
  keywords = {ps, High, INCOMPLETE, no-abstract}
}
"""


class TestDigest:
    def test_matches_stdlib_sha256_of_the_utf8_text(self):
        assert lb.bib_text_sha256("abc") == hashlib.sha256(b"abc").hexdigest()

    def test_non_ascii_text_hashes_without_error(self):
        """Bib text carries diacritics routinely (Mendonca, Krakauer)."""
        assert len(lb.bib_text_sha256("Mendonça — Kraków")) == 64

    def test_file_hash_folds_crlf_to_lf(self, tmp_path):
        """The Windows guarantee: the cleaner writes in text mode, so the
        same logical bib is CRLF there and LF elsewhere."""
        lf, crlf = tmp_path / "lf.bib", tmp_path / "crlf.bib"
        lf.write_bytes(KUHN.encode("utf-8"))
        crlf.write_bytes(KUHN.replace("\n", "\r\n").encode("utf-8"))
        assert lb.bib_file_sha256(lf) == lb.bib_file_sha256(crlf)

    def test_file_hash_equals_the_text_hash_of_the_decoded_content(self, tmp_path):
        p = tmp_path / "a.bib"
        p.write_text(KUHN, encoding="utf-8")
        assert lb.bib_file_sha256(p) == lb.bib_text_sha256(KUHN)

    def test_unreadable_file_is_none_not_a_raise(self, tmp_path):
        assert lb.bib_file_sha256(tmp_path / "absent.bib") is None

    def test_undecodable_file_is_none_not_a_raise(self, tmp_path):
        p = tmp_path / "bad.bib"
        p.write_bytes(b"\xff\xfe\x00 not utf-8")
        assert lb.bib_file_sha256(p) is None


class TestBindingHolds:
    def test_true_for_the_bib_it_was_taken_from(self, tmp_path):
        p = tmp_path / "a.bib"
        p.write_text(KUHN, encoding="utf-8")
        assert lb.binding_holds(lb.bib_text_sha256(KUHN), p)

    def test_false_when_the_bib_changed(self, tmp_path):
        p = tmp_path / "a.bib"
        p.write_text(KUHN, encoding="utf-8")
        p.write_text(KUHN + "% edited\n", encoding="utf-8")
        assert not lb.binding_holds(lb.bib_text_sha256(KUHN), p)

    def test_false_when_the_bib_is_gone(self, tmp_path):
        assert not lb.binding_holds(lb.bib_text_sha256(KUHN),
                                    tmp_path / "absent.bib")

    def test_false_when_neither_side_has_a_digest(self, tmp_path):
        """The one genuinely load-bearing line in this function. The cleaner
        writes a null bib_sha256 when it cannot read the bib back, and the
        bib can also be unreadable at barrier time -- so `None == None` is a
        REACHABLE pair, and without the `actual is not None` clause it reads
        as a held binding. Fail-open, on an accuracy gate."""
        assert not lb.binding_holds(None, tmp_path / "absent.bib")

    @pytest.mark.parametrize("bad", [
        None, 0, 1, True, False, [], {}, b"a" * 64, "", "abc",
        "g" * 64,            # not hex
        "a" * 63, "a" * 65,  # wrong length
    ])
    def test_false_for_any_value_that_is_not_the_digest(self, tmp_path, bad):
        """No shape guard runs in front of the compare, so these must each
        fail on the compare itself -- including the types that would raise or
        silently coerce in a looser check."""
        p = tmp_path / "a.bib"
        p.write_text(KUHN, encoding="utf-8")
        assert not lb.binding_holds(bad, p)

    def test_false_for_the_right_digest_in_the_wrong_case(self, tmp_path):
        """hexdigest() is lowercase and is the only writer, so a differently
        cased value did not come from it. Rejected, not folded."""
        p = tmp_path / "a.bib"
        p.write_text(KUHN, encoding="utf-8")
        assert not lb.binding_holds(lb.bib_text_sha256(KUHN).upper(), p)


class TestSingleOwner:
    """CLAUDE.md's alias rule: sites bind the shared object, never a copy."""

    def test_cleaner_binds_the_owner(self):
        import metadata_cleaner
        assert metadata_cleaner.bib_file_sha256 is lb.bib_file_sha256
        assert (metadata_cleaner.BINDING_SCHEMA_VERSION
                is lb.BINDING_SCHEMA_VERSION)

    def test_barrier_binds_the_owner(self):
        import evidence_barrier
        assert evidence_barrier.binding_holds is lb.binding_holds
        assert (evidence_barrier.BINDING_SCHEMA_VERSION
                is lb.BINDING_SCHEMA_VERSION)


class TestProducerConsumerRoundTrip:
    """The binding is only worth anything if the two sides agree in the
    pipeline's own shape. Nothing here hand-builds a hash."""

    def _review(self, tmp_path):
        rd = tmp_path / "review"
        (rd / "intermediate_files" / "json").mkdir(parents=True)
        bib = rd / "literature-domain-1.bib"
        bib.write_text(KUHN, encoding="utf-8")
        (rd / "intermediate_files" / "json"
         / "enrichment_ledger-literature-domain-1.json").write_text(
            json.dumps({"schema_version": 1,
                        "bib_file": "literature-domain-1.bib",
                        "entries": {}}), encoding="utf-8")
        (rd / "intermediate_files" / "json"
         / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
        return rd, bib

    def _barrier(self, rd):
        r = subprocess.run(
            [sys.executable, str(BARRIER), str(rd), "--domains", "1"],
            capture_output=True, text=True, cwd=str(rd))
        assert r.returncode == 0, r.stderr
        return json.loads((rd / "intermediate_files" / "json"
                           / "evidence_report.json").read_text(encoding="utf-8"))

    def test_a_ledger_the_cleaner_just_wrote_is_accepted(self, tmp_path):
        from metadata_cleaner import clean_bibtex
        rd, bib = self._review(tmp_path)
        clean_bibtex(bib, [rd / "nonexistent"])
        assert self._barrier(rd)["domains"]["1"]["cleaning_ledger"] == "present"

    def test_a_ledger_that_outlived_its_bib_is_rejected(self, tmp_path):
        """The incident this binds against: the cleaner attests a bib, the
        bib is then edited, and the ledger survives to attest the old text."""
        from metadata_cleaner import clean_bibtex
        rd, bib = self._review(tmp_path)
        clean_bibtex(bib, [rd / "nonexistent"])
        bib.write_text(bib.read_text(encoding="utf-8") + "\n% later edit\n",
                       encoding="utf-8")
        assert self._barrier(rd)["domains"]["1"]["cleaning_ledger"] == "malformed"


class TestBarrierIsRerunnable:
    """The barrier STAMPS tiers into the bib it just read, so its own write
    moves the bib out from under the binding. Before the binding landed the
    barrier was idempotent (verified against the parent commit: three runs,
    EVIDENCE-EXISTENCE every time); it must stay that way.
    """

    def _review(self, tmp_path):
        rd = tmp_path / "review"
        (rd / "intermediate_files" / "json").mkdir(parents=True)
        (rd / "literature-domain-1.bib").write_text(KUHN, encoding="utf-8")
        ij = rd / "intermediate_files" / "json"
        (ij / "enrichment_ledger-literature-domain-1.json").write_text(
            json.dumps({"schema_version": 1,
                        "bib_file": "literature-domain-1.bib",
                        "entries": {}}), encoding="utf-8")
        (ij / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
        (ij / "cleaning_ledger-literature-domain-1.json").write_text(
            json.dumps({
                "schema_version": lb.BINDING_SCHEMA_VERSION,
                "bib_file": "literature-domain-1.bib",
                "bib_sha256": lb.bib_text_sha256(KUHN),
                "breaker_tripped": False,
                "entries": {"kuhn1962structure": {
                    "api_matched": True,
                    "verified_identifier": "publisher",
                    "verified_identifier_value":
                        "university of chicago press",
                    "entry_type": "book"}}}), encoding="utf-8")
        return rd

    def _run(self, rd):
        r = subprocess.run(
            [sys.executable, str(BARRIER), str(rd), "--domains", "1"],
            capture_output=True, text=True, cwd=str(rd))
        assert r.returncode == 0, r.stderr
        rep = json.loads((rd / "intermediate_files" / "json"
                          / "evidence_report.json").read_text(encoding="utf-8"))
        return (rep["status"],
                rep["domains"]["1"]["cleaning_ledger"],
                rep["stamps"]["literature-domain-1.bib"]["kuhn1962structure"])

    def test_a_second_run_keeps_the_tier_the_first_run_granted(self, tmp_path):
        rd = self._review(tmp_path)
        assert self._run(rd) == ("complete", "present", "EVIDENCE-EXISTENCE")
        assert self._run(rd) == ("complete", "present", "EVIDENCE-EXISTENCE")

    def test_the_tier_survives_repeated_runs(self, tmp_path):
        """Not just twice -- the re-point must itself be idempotent, or the
        gate merely degrades one run later."""
        rd = self._review(tmp_path)
        for _ in range(4):
            assert self._run(rd) == ("complete", "present", "EVIDENCE-EXISTENCE")

    def test_a_hand_edit_between_runs_is_still_caught(self, tmp_path):
        """Re-pointing must track the BARRIER's own write and nothing else.
        An edit by anything the barrier did not do must still reject."""
        rd = self._review(tmp_path)
        assert self._run(rd)[1] == "present"
        bib = rd / "literature-domain-1.bib"
        bib.write_text(bib.read_text(encoding="utf-8") + "\n% hand edit\n",
                       encoding="utf-8")
        status, ledger, _ = self._run(rd)
        assert ledger == "malformed"
        assert status == "degraded"

    def test_a_rejected_ledger_stays_rejected_on_every_later_run(self, tmp_path):
        """Re-pointing must skip a ledger this run did NOT accept. Otherwise
        the barrier launders it: run N rejects the stale ledger but re-points
        it anyway, and run N+1 accepts the very attestation the binding was
        built to refuse."""
        rd = self._review(tmp_path)
        bib = rd / "literature-domain-1.bib"
        bib.write_text(bib.read_text(encoding="utf-8") + "\n% edited\n",
                       encoding="utf-8")
        for run in range(3):
            status, ledger, tier = self._run(rd)
            assert ledger == "malformed", f"laundered on run {run + 1}"
            assert status == "degraded", f"laundered on run {run + 1}"
            assert tier != "EVIDENCE-EXISTENCE", f"laundered on run {run + 1}"


class TestCleaningLedgerMustDeclareTheBinding:
    """A cleaning ledger below the binding schema is refused outright.

    Producer and consumer shipped together, so there is no compatibility
    case: any v1/v2 cleaning ledger reaching the barrier is either a
    pre-upgrade survivor -- the exact stale-ledger shape the binding exists
    to refuse, and the one it could not see -- or hand-written. Accepting it
    would leave a downgrade path straight past the binding on a gate whose
    policy is to fail closed. The enrichment ledger is unaffected: it is
    written before the cleaner rewrites the bib, so it stays at 1.
    """

    def _review(self, tmp_path, cleaning):
        rd = tmp_path / "review"
        ij = rd / "intermediate_files" / "json"
        ij.mkdir(parents=True)
        (rd / "literature-domain-1.bib").write_text(KUHN, encoding="utf-8")
        (ij / "cleaning_ledger-literature-domain-1.json").write_text(
            json.dumps(cleaning), encoding="utf-8")
        (ij / "enrichment_ledger-literature-domain-1.json").write_text(
            json.dumps({"schema_version": 1,
                        "bib_file": "literature-domain-1.bib",
                        "entries": {}}), encoding="utf-8")
        (ij / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(BARRIER), str(rd), "--domains", "1"],
            capture_output=True, text=True, cwd=str(rd))
        assert r.returncode == 0, r.stderr
        return json.loads((ij / "evidence_report.json").read_text(
            encoding="utf-8"))

    def _ledger(self, version, **extra):
        d = {"schema_version": version,
             "bib_file": "literature-domain-1.bib",
             "breaker_tripped": False,
             "entries": {"kuhn1962structure": {
                 "api_matched": True, "verified_identifier": "publisher",
                 "verified_identifier_value": "university of chicago press",
                 "entry_type": "book"}}}
        d.update(extra)
        return d

    def test_a_v1_cleaning_ledger_is_refused(self, tmp_path):
        rep = self._review(tmp_path, self._ledger(1))
        assert rep["domains"]["1"]["cleaning_ledger"] == "malformed"
        assert rep["status"] == "degraded"

    def test_a_v2_cleaning_ledger_is_refused(self, tmp_path):
        rep = self._review(tmp_path, self._ledger(2))
        assert rep["domains"]["1"]["cleaning_ledger"] == "malformed"
        assert rep["status"] == "degraded"

    def test_a_v2_ledger_cannot_buy_the_tier_by_omitting_the_binding(
            self, tmp_path):
        """The downgrade path, stated as the attack it is."""
        rep = self._review(tmp_path, self._ledger(2))
        assert rep["stamps"]["literature-domain-1.bib"][
            "kuhn1962structure"] != "EVIDENCE-EXISTENCE"

    def test_a_v3_cleaning_ledger_is_accepted(self, tmp_path):
        rep = self._review(
            tmp_path,
            self._ledger(lb.BINDING_SCHEMA_VERSION,
                         bib_sha256=lb.bib_text_sha256(KUHN)))
        assert rep["domains"]["1"]["cleaning_ledger"] == "present"
        assert rep["status"] == "complete"

    def test_the_enrichment_ledger_keeps_its_v1_exemption(self, tmp_path):
        """The floor is kind-scoped. The enrichment ledger is written at the
        researcher's Stage 5.5, BEFORE the cleaner rewrites the bib, so it
        cannot carry a binding and must not be held to one."""
        rep = self._review(
            tmp_path,
            self._ledger(lb.BINDING_SCHEMA_VERSION,
                         bib_sha256=lb.bib_text_sha256(KUHN)))
        assert rep["domains"]["1"]["enrichment_ledger"] == "present"


class TestNonAsciiRoundTrip:
    """A review round asked whether pybtex's Writer could emit non-UTF-8
    bytes on a locale-dependent platform, which would make `read_text` raise,
    the cleaner write a null hash, and EVERY ledger refuse -- a
    platform-specific outage of the accuracy gate.

    It cannot: `write_bibtex` renders through an in-memory StringIO and does
    its own write with `os.fdopen(fd, "w", encoding="utf-8")`, so pybtex
    never reaches the filesystem. Pinned here against a bib whose author,
    title and publisher all carry diacritics, because the claim is about the
    write->read-back path and no unit test of the hash function touches it.
    """

    ACCENTED = """@book{mendonca2020razão,
  author = {Mendon{\\c{c}}a, Jos\\'{e} and Krak\\'{o}w, Anna},
  title = {Raz\u00e3o, Ética e Ação: Estudos sobre Weber},
  publisher = {Editora da Universidade de São Paulo},
  year = {2020},
  keywords = {ps, High}
}
"""

    # A CrossRef record contradicting the entry's `number`, which is what
    # makes the cleaner actually REWRITE the file. Without a strip there is
    # nothing to write, write_bibtex is never called, and a test of the
    # write path tests nothing -- a mutation to the writer's encoding
    # survived this class until the strip was added.
    CONTRADICTING = {
        "status": "success", "source": "crossref",
        "results": [{"verified": True, "doi": "10.1234/abc.2020",
                     "title": "Raz\u00e3o, Ética e Ação",
                     "container_title": "Revista de Filosofia",
                     "issue": "1", "year": 2020, "type": "journal-article"}],
    }
    STRIPPABLE = """@article{mendonca2020razao,
  author = {Mendon{\\c{c}}a, Jos\\'{e}},
  title = {Raz\u00e3o, Ética e Ação},
  journal = {Revista de Filosofia},
  year = {2020},
  number = {7729},
  doi = {10.1234/abc.2020}
}
"""

    def test_the_hash_survives_a_REWRITE_of_a_diacritic_bib(self, tmp_path):
        """The path the concern is actually about: the cleaner strips a
        field, rewrites the file through pybtex's renderer, then hashes what
        landed on disk."""
        from metadata_cleaner import clean_bibtex
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "verify_m.json").write_text(
            json.dumps(self.CONTRADICTING), encoding="utf-8")
        bib = tmp_path / "literature-domain-1.bib"
        bib.write_text(self.STRIPPABLE, encoding="utf-8")
        result = clean_bibtex(bib, [json_dir])
        assert result["total_fields_removed"] == 1, (
            "fixture no longer forces a rewrite, so this tests nothing")
        led = json.loads((tmp_path / "intermediate_files" / "json"
                          / "cleaning_ledger-literature-domain-1.json")
                         .read_text(encoding="utf-8"))
        assert led["bib_sha256"] is not None, (
            "a null hash means the rewritten bib was not readable as UTF-8")
        assert led["bib_sha256"] == lb.bib_file_sha256(bib)
        assert "Mendon" in bib.read_text(encoding="utf-8")

    def test_a_bib_full_of_diacritics_survives_clean_then_bind(self, tmp_path):
        from metadata_cleaner import clean_bibtex
        bib = tmp_path / "literature-domain-1.bib"
        bib.write_text(self.ACCENTED, encoding="utf-8")
        clean_bibtex(bib, [tmp_path / "nonexistent"])
        led = json.loads((tmp_path / "intermediate_files" / "json"
                          / "cleaning_ledger-literature-domain-1.json")
                         .read_text(encoding="utf-8"))
        assert led["bib_sha256"] is not None, (
            "a null hash here means the bib could not be read back as UTF-8")
        assert led["bib_sha256"] == lb.bib_file_sha256(bib)

    def test_the_barrier_accepts_a_diacritic_bib_end_to_end(self, tmp_path):
        """The round trip that matters: cleaner writes, barrier reads."""
        from metadata_cleaner import clean_bibtex
        rd = tmp_path / "review"
        ij = rd / "intermediate_files" / "json"
        ij.mkdir(parents=True)
        (rd / "literature-domain-1.bib").write_text(
            self.ACCENTED, encoding="utf-8")
        (ij / "enrichment_ledger-literature-domain-1.json").write_text(
            json.dumps({"schema_version": 1,
                        "bib_file": "literature-domain-1.bib",
                        "entries": {}}), encoding="utf-8")
        (ij / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
        clean_bibtex(rd / "literature-domain-1.bib", [rd / "nonexistent"])
        r = subprocess.run(
            [sys.executable, str(BARRIER), str(rd), "--domains", "1"],
            capture_output=True, text=True, cwd=str(rd))
        assert r.returncode == 0, r.stderr
        rep = json.loads((ij / "evidence_report.json").read_text(
            encoding="utf-8"))
        assert rep["domains"]["1"]["cleaning_ledger"] == "present"


class TestRepointBindsWhatTheBarrierWrote:
    """The re-point must bind the text the barrier AUTHORED, not whatever is
    on disk when it gets around to hashing.

    Round 2 showed the read-back was both useless and dangerous here: with
    universal-newline translation, hashing the in-memory string is identical
    to reading it back even when the disk holds CRLF (verified) -- so the
    read-back bought no cross-platform safety, and it blessed anything that
    edited the file in the window after the write.
    """

    def test_an_edit_in_the_write_to_repoint_window_is_not_blessed(
            self, tmp_path, monkeypatch):
        """Inject an edit between the barrier's bib write and its re-point.
        The injected text must NOT end up bound: the next run must reject."""
        import evidence_barrier as eb
        rd = tmp_path / "review"
        ij = rd / "intermediate_files" / "json"
        ij.mkdir(parents=True)
        (rd / "literature-domain-1.bib").write_text(KUHN, encoding="utf-8")
        (ij / "enrichment_ledger-literature-domain-1.json").write_text(
            json.dumps({"schema_version": 1,
                        "bib_file": "literature-domain-1.bib",
                        "entries": {}}), encoding="utf-8")
        (ij / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
        (ij / "cleaning_ledger-literature-domain-1.json").write_text(
            json.dumps({
                "schema_version": lb.BINDING_SCHEMA_VERSION,
                "bib_file": "literature-domain-1.bib",
                "bib_sha256": lb.bib_text_sha256(KUHN),
                "breaker_tripped": False,
                "entries": {"kuhn1962structure": {
                    "api_matched": True, "verified_identifier": "publisher",
                    "verified_identifier_value":
                        "university of chicago press",
                    "entry_type": "book"}}}), encoding="utf-8")

        bib = rd / "literature-domain-1.bib"
        real_write = eb._atomic_write
        injected = {"done": False}

        def sneaky(path, content):
            real_write(path, content)
            if str(path).endswith("literature-domain-1.bib") and not injected["done"]:
                injected["done"] = True
                # An edit the barrier did not author, landing after its write.
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write("\n@misc{injected2020, title = {Forged}}\n")

        monkeypatch.setattr(eb, "_atomic_write", sneaky)
        eb.execute(rd, 1)
        assert injected["done"], "the fixture never injected; test proves nothing"

        led = json.loads(
            (ij / "cleaning_ledger-literature-domain-1.json").read_text(
                encoding="utf-8"))
        on_disk = lb.bib_file_sha256(bib)
        assert led["bib_sha256"] != on_disk, (
            "the barrier bound an edit it did not author -- a forged entry "
            "would be trusted on the next run")


class TestRepointSurvivesPartialFailure:
    """A write failure on one domain must not strand the domains already
    written. Re-pointing after the whole batch left an earlier domain stamped
    but unbound, so the next run rejected a ledger nothing was wrong with --
    and a rejected ledger is never re-pointed, so no re-run could repair it.
    """

    def _scaffold(self, tmp_path, n):
        rd = tmp_path / "review"
        ij = rd / "intermediate_files" / "json"
        ij.mkdir(parents=True)
        for i in range(1, n + 1):
            name = f"literature-domain-{i}.bib"
            (rd / name).write_text(KUHN, encoding="utf-8")
            (ij / f"enrichment_ledger-{name[:-4]}.json").write_text(
                json.dumps({"schema_version": 1, "bib_file": name,
                            "entries": {}}), encoding="utf-8")
            (ij / f"encyclopedia_entries-domain-{i}.json").write_text(
                '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
            (ij / f"cleaning_ledger-{name[:-4]}.json").write_text(
                json.dumps({
                    "schema_version": lb.BINDING_SCHEMA_VERSION,
                    "bib_file": name,
                    "bib_sha256": lb.bib_text_sha256(KUHN),
                    "breaker_tripped": False,
                    "entries": {"kuhn1962structure": {
                        "api_matched": True,
                        "verified_identifier": "publisher",
                        "verified_identifier_value":
                            "university of chicago press",
                        "entry_type": "book"}}}), encoding="utf-8")
        return rd, ij

    def test_every_domain_is_repointed_not_just_the_first(self, tmp_path):
        """A mutation that re-points only the first accepted domain survived
        the suite, because every re-run test used one domain."""
        import evidence_barrier as eb
        rd, ij = self._scaffold(tmp_path, 3)
        eb.execute(rd, 3)
        for i in (1, 2, 3):
            name = f"literature-domain-{i}"
            led = json.loads((ij / f"cleaning_ledger-{name}.json").read_text(
                encoding="utf-8"))
            assert led["bib_sha256"] == lb.bib_file_sha256(
                rd / f"{name}.bib"), f"domain {i} left unbound"

    def test_a_write_failure_does_not_strand_an_already_written_domain(
            self, tmp_path, monkeypatch):
        import evidence_barrier as eb
        rd, ij = self._scaffold(tmp_path, 2)
        real_write = eb._atomic_write
        seen = []

        def failing(path, content):
            if str(path).endswith("literature-domain-2.bib"):
                raise OSError("disk full")
            seen.append(path)
            real_write(path, content)

        monkeypatch.setattr(eb, "_atomic_write", failing)
        try:
            eb.execute(rd, 2)
        except OSError:
            pass
        led = json.loads(
            (ij / "cleaning_ledger-literature-domain-1.json").read_text(
                encoding="utf-8"))
        assert led["bib_sha256"] == lb.bib_file_sha256(
            rd / "literature-domain-1.bib"), (
            "domain 1 was written but left unbound, so the next run rejects "
            "a ledger nothing is wrong with -- and cannot repair it")


class TestEnrichmentVersionIsPinnedToItsOwnProducer:
    """The floor is kind-scoped, but the ACCEPTED SET was not: an enrichment
    ledger declaring 2 or 3 was read under version-1 semantics, even though
    its producer only ever writes 1. Accepting an unknown attestation schema
    is the fail-open direction on an accuracy gate."""

    def _review(self, tmp_path, enrich_version):
        rd = tmp_path / "review"
        ij = rd / "intermediate_files" / "json"
        ij.mkdir(parents=True)
        (rd / "literature-domain-1.bib").write_text(KUHN, encoding="utf-8")
        (ij / "cleaning_ledger-literature-domain-1.json").write_text(
            json.dumps({"schema_version": lb.BINDING_SCHEMA_VERSION,
                        "bib_file": "literature-domain-1.bib",
                        "bib_sha256": lb.bib_text_sha256(KUHN),
                        "breaker_tripped": False, "entries": {}}),
            encoding="utf-8")
        (ij / "enrichment_ledger-literature-domain-1.json").write_text(
            json.dumps({"schema_version": enrich_version,
                        "bib_file": "literature-domain-1.bib",
                        "entries": {}}), encoding="utf-8")
        (ij / "encyclopedia_entries-domain-1.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(BARRIER), str(rd), "--domains", "1"],
            capture_output=True, text=True, cwd=str(rd))
        assert r.returncode == 0, r.stderr
        return json.loads((ij / "evidence_report.json").read_text(
            encoding="utf-8"))

    def test_the_version_its_producer_writes_is_accepted(self, tmp_path):
        rep = self._review(tmp_path, 1)
        assert rep["domains"]["1"]["enrichment_ledger"] == "present"

    def test_a_version_its_producer_never_writes_is_refused(self, tmp_path):
        for v in (2, 3):
            rep = self._review(tmp_path / f"v{v}", v)
            assert rep["domains"]["1"]["enrichment_ledger"] == "malformed", v
