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
