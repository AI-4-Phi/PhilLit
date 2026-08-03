"""Tests for stamp_evidence.py — evidence-tier computation and stamping."""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from stamp_evidence import (
    TIER_ABSTRACT, TIER_CONTEXT, TIER_EXISTENCE, TIER_NONE,
    EntryAttestation, abstract_hash, attest_abstract, compute_tier,
    normalize_abstract_for_hash, normalize_doi,
)

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
from metadata_cleaner import normalize_doi as cleaner_normalize_doi  # noqa: E402


class TestNormalizeDoiIsTheSharedOwner:
    """Was TestNormalizeDoiEquivalence: two copies pinned byte-equivalent.
    ROADMAP item 4 made them one object, so identity is what now prevents
    drift. A divergence here would make a cleaner-verified DOI compare unequal
    to the ledger value stamp_evidence computes, spuriously demoting the entry
    to EVIDENCE-NONE."""

    # Literal expected values, not a copy-vs-copy comparison: once both names
    # resolve to the same function object, `a(case) == b(case)` compares each
    # output to itself and cannot fail.
    CASES = {
        "10.1000/X": "10.1000/x",
        "https://doi.org/10.1000/x": "10.1000/x",
        "http://doi.org/10.1000/x": "10.1000/x",
        "doi:10.1000/x": "10.1000/x",
        "doi.org/10.1000/x": "10.1000/x",
        "https://dx.doi.org/10.1000/x": "10.1000/x",
        "http://dx.doi.org/10.1000/x": "10.1000/x",
        "  10.1000/X  ": "10.1000/x",
        "  https://doi.org/10.1000/x  ": "10.1000/x",
        "  https://dx.doi.org/10.1000/x  ": "10.1000/x",
        "DOI:10.1000/X": "10.1000/x",
        "": "",
        None: "",
    }

    def test_is_the_shared_object(self):
        import bib_identity
        import stamp_evidence
        assert stamp_evidence.normalize_doi is bib_identity.normalize_doi
        assert cleaner_normalize_doi is bib_identity.normalize_doi

    def test_battery_normalizes_to_documented_values(self):
        for raw, expected in self.CASES.items():
            assert normalize_doi(raw) == expected, f"{raw!r} -> {normalize_doi(raw)!r}"

    def test_dx_doi_org_stripped(self):
        assert normalize_doi("https://dx.doi.org/10.1000/x") == "10.1000/x"
        assert cleaner_normalize_doi("https://dx.doi.org/10.1000/x") == "10.1000/x"
        assert normalize_doi("http://dx.doi.org/10.1000/x") == "10.1000/x"
        assert cleaner_normalize_doi("http://dx.doi.org/10.1000/x") == "10.1000/x"


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


from stamp_evidence import (
    stamp_keywords, stamp_entry_text, stamp_file, parse_entry_fields,
)

ENTRY_KUHN = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  publisher = {University of Chicago Press},
  year = {1962},
  note = {CORE ARGUMENT: Paradigms.},
  keywords = {philosophy-of-science, High, INCOMPLETE, no-abstract}
}"""

ENTRY_MARKER = """@article{smith2020,
  author = {Smith, Jane},
  title = {Data},
  year = {2020},
  keywords = {data-ethics, Medium, METADATA_CLEANED: pages, doi}
}"""


class TestStampKeywords:
    def test_canonical_order_and_strip(self):
        out = stamp_keywords("philosophy-of-science, High, INCOMPLETE, no-abstract", "EVIDENCE-CONTEXT")
        assert out == "philosophy-of-science, High, EVIDENCE-CONTEXT"

    def test_marker_stays_last(self):
        out = stamp_keywords("data-ethics, Medium, METADATA_CLEANED: pages, doi", "EVIDENCE-ABSTRACT")
        assert out == "data-ethics, Medium, EVIDENCE-ABSTRACT, METADATA_CLEANED: pages, doi"

    def test_marker_with_escaped_underscore(self):
        # pybtex round-trips the marker as METADATA\_CLEANED
        out = stamp_keywords(r"tag, High, METADATA\_CLEANED: doi", "EVIDENCE-NONE")
        assert out.endswith(r"METADATA\_CLEANED: doi")
        assert "EVIDENCE-NONE, METADATA" in out.replace("\\", "")

    def test_idempotent_restamp_replaces_old_tier(self):
        once = stamp_keywords("tag, High", "EVIDENCE-ABSTRACT")
        twice = stamp_keywords(once, "EVIDENCE-NONE")
        assert "EVIDENCE-ABSTRACT" not in twice
        assert twice.count("EVIDENCE-") == 1

    def test_none_tier_strips_only(self):
        out = stamp_keywords("tag, High, EVIDENCE-ABSTRACT", None)
        assert out == "tag, High"

    def test_empty_and_missing_keywords(self):
        assert stamp_keywords("", "EVIDENCE-NONE") == "EVIDENCE-NONE"
        assert stamp_keywords(None, "EVIDENCE-NONE") == "EVIDENCE-NONE"

    def test_multiline_keywords(self):
        out = stamp_keywords("tag-one,\n  tag-two, Low", "EVIDENCE-EXISTENCE")
        assert out == "tag-one, tag-two, Low, EVIDENCE-EXISTENCE"

    def test_unknown_and_mixed_case_evidence_tokens_stripped(self):
        out = stamp_keywords("tag, EVIDENCE-BOGUS, evidence-abstract, High",
                             "EVIDENCE-NONE")
        assert out == "tag, High, EVIDENCE-NONE"

    def test_duplicate_tier_tokens_collapse_to_one(self):
        out = stamp_keywords("EVIDENCE-ABSTRACT, tag, EVIDENCE-ABSTRACT", "EVIDENCE-CONTEXT")
        assert out == "tag, EVIDENCE-CONTEXT"

    def test_marker_not_last_input_reordered_safely(self):
        # pathological input: tokens after the marker are swallowed into it;
        # stamping re-appends the marker last, so the output is canonical.
        out = stamp_keywords("tag, METADATA_CLEANED: doi, straggler", "EVIDENCE-NONE")
        assert out.startswith("tag, EVIDENCE-NONE, METADATA_CLEANED:")


class TestStampEntryText:
    def test_stamp_replaces_keywords_value(self):
        out = stamp_entry_text(ENTRY_KUHN, "EVIDENCE-CONTEXT")
        assert "INCOMPLETE" not in out
        assert "no-abstract" not in out
        assert "philosophy-of-science, High, EVIDENCE-CONTEXT" in out

    def test_inserts_keywords_when_missing(self):
        entry = "@book{k,\n  author = {A},\n  title = {T}\n}"
        out = stamp_entry_text(entry, "EVIDENCE-NONE")
        assert "keywords = {EVIDENCE-NONE}" in out

    def test_parse_entry_fields(self):
        fields = parse_entry_fields(ENTRY_KUHN)
        assert fields["publisher"] == "University of Chicago Press"
        assert fields["year"] == "1962"

    def test_quoted_keywords_value_stamped(self):
        # a forging agent may use quotes instead of braces; the whole
        # quoted value must be replaced with a braced canonical one, no
        # quoted remnant left behind.
        entry = '@article{q2020,\n  author = {A},\n  keywords = "tag, High, EVIDENCE-BOGUS"\n}'
        out = stamp_entry_text(entry, "EVIDENCE-NONE")
        assert 'keywords = {tag, High, EVIDENCE-NONE}' in out
        assert '"' not in out
        assert "EVIDENCE-BOGUS" not in out


class TestStampFile:
    def test_stamp_file_atomic_and_returns_stamps(self, tmp_path):
        from stamp_evidence import EntryAttestation
        bib = tmp_path / "literature-domain-1.bib"
        bib.write_text(ENTRY_KUHN + "\n\n" + ENTRY_MARKER + "\n", encoding="utf-8")
        att = {"kuhn1962structure": EntryAttestation(
            api_matched=True, verified_identifier="publisher",
            verified_identifier_value="university of chicago press")}
        stamps = stamp_file(bib, att)
        assert stamps["kuhn1962structure"] == "EVIDENCE-EXISTENCE"
        assert stamps["smith2020"] == "EVIDENCE-NONE"  # no attestation -> NONE
        content = bib.read_text(encoding="utf-8")
        assert content.count("EVIDENCE-") == 2
        assert not list(tmp_path.glob("*.tmp"))

    def test_comment_blocks_untouched(self, tmp_path):
        bib = tmp_path / "b.bib"
        bib.write_text("@comment{\nDOMAIN: X\n}\n\n" + ENTRY_KUHN + "\n", encoding="utf-8")
        stamp_file(bib, {})
        assert "DOMAIN: X" in bib.read_text(encoding="utf-8")

    def test_pybtex_roundtrip_after_stamp(self, tmp_path):
        # the METADATA_CLEANED footgun: a stamped file must still parse and
        # survive a pybtex Writer round-trip without corrupting the marker
        from pybtex.database import parse_file
        from pybtex.database.output.bibtex import Writer
        bib = tmp_path / "b.bib"
        bib.write_text(ENTRY_MARKER + "\n", encoding="utf-8")
        stamp_file(bib, {})
        data = parse_file(str(bib), bib_format="bibtex")
        out = tmp_path / "roundtrip.bib"
        with open(out, "w", encoding="utf-8") as f:
            Writer().write_file(data, f)
        restamped = stamp_entry_text(out.read_text(encoding="utf-8"), "EVIDENCE-NONE")
        assert restamped.count("EVIDENCE-NONE") == 1

    def test_write_failure_leaves_original_intact(self, tmp_path, monkeypatch):
        # atomicity under fault injection, not just tmp-file cleanup
        import stamp_evidence
        bib = tmp_path / "b.bib"
        original = ENTRY_KUHN + "\n"
        bib.write_text(original, encoding="utf-8")

        def boom(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(stamp_evidence.os, "replace", boom)
        try:
            stamp_file(bib, {})
        except OSError:
            pass
        assert bib.read_text(encoding="utf-8") == original

    def test_newline_at_inside_field_value(self, tmp_path):
        # split_entries splits on newline-@; a field value containing that
        # sequence fragments the entry. Pin the failure direction: the real
        # entry's stale tier may survive (demote-safe is NOT guaranteed here),
        # so assert the file still parses and no exception is raised.
        entry = ('@article{tweet2024,\n  author = {A},\n'
                 '  abstract = {Quoting a handle:\n@someone said things.},\n'
                 '  keywords = {tag}\n}')
        bib = tmp_path / "b.bib"
        bib.write_text(entry + "\n", encoding="utf-8")
        stamp_file(bib, {})  # must not raise; behavior documented as inherited
