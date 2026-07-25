"""Tests for stamp_evidence.py — evidence-tier computation and stamping."""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from stamp_evidence import (
    TIER_ABSTRACT, TIER_CONTEXT, TIER_EXISTENCE, TIER_NONE,
    EntryAttestation, abstract_hash, attest_abstract, compute_tier,
    normalize_abstract_for_hash,
)


class TestHashNormalization:
    def test_whitespace_collapse(self):
        assert normalize_abstract_for_hash("a  b\n  c") == "a b c"

    def test_backslash_stripped_for_pybtex_roundtrip(self):
        # pybtex Writer may escape characters; hashes must survive
        assert normalize_abstract_for_hash(r"A \& B") == normalize_abstract_for_hash("A & B")

    def test_hash_stable(self):
        assert abstract_hash("some text") == abstract_hash("some\n text ")


class TestAttestAbstract:
    def _fields(self):
        return {"abstract": "The paper argues X.", "abstract_source": "s2"}

    def _ledger(self):
        return {"abstract_source": "s2", "abstract_sha256": abstract_hash("The paper argues X.")}

    def test_attested(self):
        assert attest_abstract(self._fields(), self._ledger()) is True

    def test_no_ledger_entry(self):
        assert attest_abstract(self._fields(), None) is False

    def test_source_mismatch(self):
        ledger = self._ledger(); ledger["abstract_source"] = "openalex"
        assert attest_abstract(self._fields(), ledger) is False

    def test_hash_mismatch_tampered_abstract(self):
        fields = self._fields(); fields["abstract"] = "A different, tampered abstract."
        assert attest_abstract(fields, self._ledger()) is False

    def test_whitespace_reflow_still_attests(self):
        fields = self._fields(); fields["abstract"] = "The paper\n  argues X."
        assert attest_abstract(fields, self._ledger()) is True


class TestComputeTier:
    def test_attested_abstract(self):
        fields = {"abstract": "text", "abstract_source": "s2"}
        att = EntryAttestation(abstract_attested=True)
        assert compute_tier("article", fields, att) == TIER_ABSTRACT

    def test_abstract_source_present_but_unattested_falls_through(self):
        # the demonstrated one-string attack: fabricated abstract + abstract_source
        fields = {"abstract": "fabricated", "abstract_source": "s2"}
        att = EntryAttestation(abstract_attested=False)
        assert compute_tier("article", fields, att) == TIER_NONE

    def test_unknown_abstract_source_falls_through(self):
        fields = {"abstract": "text", "abstract_source": "wikipedia"}
        att = EntryAttestation(abstract_attested=True)
        assert compute_tier("article", fields, att) != TIER_ABSTRACT

    def test_driver_written_context(self):
        fields = {"sep_context": "Cited in 'x' entry: \"...\""}
        att = EntryAttestation(context_written=True)
        assert compute_tier("book", fields, att) == TIER_CONTEXT

    def test_context_field_without_attestation_falls_through(self):
        # fabricated sep_context cannot unlock CONTEXT
        fields = {"sep_context": "forged"}
        att = EntryAttestation(context_written=False)
        assert compute_tier("book", fields, att) == TIER_NONE

    def test_kuhn_fallback_ledger_matched_book_publisher(self):
        fields = {"publisher": "University of Chicago Press"}
        att = EntryAttestation(api_matched=True, verified_identifier="publisher",
                               verified_identifier_value="university of chicago press")
        assert compute_tier("book", fields, att) == TIER_EXISTENCE

    def test_verified_doi_value_binding(self):
        att = EntryAttestation(api_matched=True, verified_identifier="doi",
                               verified_identifier_value="10.1000/real")
        # same DOI, URL-prefixed form: normalization must equate them
        assert compute_tier("article",
                            {"doi": "https://doi.org/10.1000/REAL"}, att) == TIER_EXISTENCE
        # swapped DOI after verification: value binding must demote
        assert compute_tier("article", {"doi": "10.9999/fake"}, att) == TIER_NONE

    def test_verified_publisher_value_binding(self):
        att = EntryAttestation(api_matched=True, verified_identifier="publisher",
                               verified_identifier_value="university of chicago press")
        assert compute_tier("book", {"publisher": "Random Other Press"}, att) == TIER_NONE

    def test_no_match_with_plausible_publisher_is_none(self):
        # the closed fabricated-book attack
        fields = {"publisher": "Oxford University Press"}
        att = EntryAttestation(api_matched=False, verified_identifier=None)
        assert compute_tier("book", fields, att) == TIER_NONE

    def test_no_match_with_plausible_doi_is_none(self):
        fields = {"doi": "10.9999/fake"}
        att = EntryAttestation(api_matched=False)
        assert compute_tier("article", fields, att) == TIER_NONE

    def test_breaker_tripped_is_none(self):
        fields = {"doi": "10.1000/real"}
        att = EntryAttestation(api_matched=True, verified_identifier="doi", breaker_tripped=True)
        assert compute_tier("article", fields, att) == TIER_NONE

    def test_article_with_publisher_but_no_doi_is_none(self):
        # container path is type-gated even with a verified value
        fields = {"publisher": "Elsevier"}
        att = EntryAttestation(api_matched=True, verified_identifier="publisher",
                               verified_identifier_value="elsevier")
        assert compute_tier("article", fields, att) == TIER_NONE

    def test_verified_doi_but_field_since_removed_is_none(self):
        att = EntryAttestation(api_matched=True, verified_identifier="doi",
                               verified_identifier_value="10.1000/real")
        assert compute_tier("article", {}, att) == TIER_NONE

    def test_url_only_is_none(self):
        fields = {"url": "https://example.com/post"}
        assert compute_tier("misc", fields, EntryAttestation()) == TIER_NONE

    def test_nothing_is_none(self):
        assert compute_tier("misc", {}, EntryAttestation()) == TIER_NONE

    def test_tier_order_abstract_beats_context(self):
        fields = {"abstract": "t", "abstract_source": "s2", "sep_context": "c"}
        att = EntryAttestation(abstract_attested=True, context_written=True)
        assert compute_tier("book", fields, att) == TIER_ABSTRACT
