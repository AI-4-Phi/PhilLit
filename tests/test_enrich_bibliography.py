"""
Tests for enrich_bibliography.py (bibliography enrichment orchestrator).

Tests cover:
- BibTeX parsing
- Abstract field detection
- Entry modification
- INCOMPLETE flag handling
- Batch processing
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"))


# =============================================================================
# Sample BibTeX Data
# =============================================================================

SAMPLE_ENTRY_NO_ABSTRACT = """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971},
  doi = {10.2307/2024717},
  keywords = {free-will, compatibilism, High},
}"""

SAMPLE_ENTRY_WITH_ABSTRACT = """@article{wolf1990freedom,
  author = {Wolf, Susan},
  title = {Freedom Within Reason},
  journal = {Philosophy and Phenomenological Research},
  year = {1990},
  doi = {10.2307/2107766},
  abstract = {This paper argues that freedom requires the ability to act in accordance with reason.},
  keywords = {free-will, reason, Medium},
}"""

SAMPLE_ENTRY_INCOMPLETE = """@article{test2020paper,
  author = {Test, Author},
  title = {A Test Paper},
  year = {2020},
  keywords = {testing, INCOMPLETE, no-abstract},
}"""

SAMPLE_COMMENT = """@comment{
  DOMAIN: Testing Domain
  NOTABLE_GAPS: None identified
}"""

# A @book entry with no abstract and High importance: after the main pass
# marks it INCOMPLETE (resolve_abstract_for_entry finds nothing), it is a
# candidate for the NDPR enrichment pass.
SAMPLE_BOOK_INCOMPLETE_HIGH = """@book{parfit1984reasons,
  author = {Parfit, Derek},
  title = {Reasons and Persons},
  publisher = {Oxford University Press},
  year = {1984},
  keywords = {personal-identity, ethics, High},
}"""


# =============================================================================
# Parsing Tests
# =============================================================================

class TestBibTeXParsing:
    """Tests for BibTeX parsing functionality."""

    def test_parse_basic_entry(self):
        """Should parse basic BibTeX entry."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)

        assert len(entries) == 1
        assert entries[0]['entry_type'] == 'article'
        assert entries[0]['key'] == 'frankfurt1971freedom'
        assert entries[0]['fields']['author'] == 'Frankfurt, Harry G.'
        assert entries[0]['fields']['year'] == '1971'

    def test_parse_entry_with_abstract(self):
        """Should parse entry with abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_WITH_ABSTRACT)

        assert len(entries) == 1
        assert 'abstract' in entries[0]['fields']
        assert 'reason' in entries[0]['fields']['abstract']

    def test_parse_multiple_entries(self):
        """Should parse multiple entries."""
        import enrich_bibliography

        content = f"{SAMPLE_ENTRY_NO_ABSTRACT}\n\n{SAMPLE_ENTRY_WITH_ABSTRACT}"
        entries = enrich_bibliography.parse_bibtex_entries(content)

        assert len(entries) == 2

    def test_parse_comment_entry(self):
        """Should parse @comment entries."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_COMMENT)

        assert len(entries) == 1
        assert entries[0]['entry_type'] == 'comment'


ENTRY_WITH_AT_IN_KEYWORDS = """@misc{riggs2003understanding,
  author = {Riggs, Wayne D.},
  title = {Understanding Virtue and the Virtue of Understanding},
  year = {2003},
  keywords = {understanding, Medium, METADATA\\_CLEANED: booktitle, type:@incollection->@misc}
}"""


def test_entry_with_interior_at_not_truncated():
    """An @ inside a field value must not split the entry (production
    reproducer: the cleaner's type-demotion marker). The raw text must stay
    brace-balanced and the fields after the @ must still parse."""
    from enrich_bibliography import parse_bibtex_entries
    entries = parse_bibtex_entries(ENTRY_WITH_AT_IN_KEYWORDS)
    assert len(entries) == 1
    e = entries[0]
    assert e["key"] == "riggs2003understanding"
    assert e["raw"].count("{") == e["raw"].count("}")
    assert "type:@incollection->@misc" in e["fields"]["keywords"]


def test_two_entries_with_interior_at_split_correctly():
    content = ENTRY_WITH_AT_IN_KEYWORDS + "\n\n" + """@article{smith2020,
  author = {Smith, Jane},
  title = {A Title},
  year = {2020},
}"""
    from enrich_bibliography import parse_bibtex_entries
    entries = parse_bibtex_entries(content)
    assert [e["key"] for e in entries] == ["riggs2003understanding", "smith2020"]
    assert entries[0]["raw"].count("{") == entries[0]["raw"].count("}")


def test_crlf_line_endings_still_split():
    """CRLF content: \\r precedes \\n, so the char after each \\n is the
    next line's first char and line-anchored splitting works; pinned
    because a reviewer plausibly claimed the opposite."""
    from enrich_bibliography import parse_bibtex_entries
    content = ("@article{a2020,\r\n  author = {A, B},\r\n  title = {T},\r\n"
               "  year = {2020},\r\n}\r\n\r\n"
               "@article{b2021,\r\n  author = {C, D},\r\n  title = {U},\r\n"
               "  year = {2021},\r\n}\r\n")
    assert [e["key"] for e in parse_bibtex_entries(content)] == ["a2020", "b2021"]


QUOTED_FIELDS_ENTRY = """@article{hardwig1985epistemic,
    sep_context = {Cited in 'testimony' entry: "some quoted prose"},
    author = "Hardwig, John",
    title = "Epistemic Dependence",
    journal = "The Journal of Philosophy",
    year = "1985",
    doi = "10.2307/2026523",
    keywords = {autonomy, High, EVIDENCE-CONTEXT}
}"""


def test_quoted_fields_are_parsed():
    """pybtex's Writer emits field = "value" on round-trip (CLAUDE.md);
    the cleaner round-trips domain bibs, so enrichment must read both
    forms. Production: every quoted title was invisible and the whole
    domain enriched nothing."""
    from enrich_bibliography import parse_bibtex_entries
    e = parse_bibtex_entries(QUOTED_FIELDS_ENTRY)[0]
    assert e["fields"]["title"] == "Epistemic Dependence"
    assert e["fields"]["doi"] == "10.2307/2026523"
    assert e["fields"]["author"] == "Hardwig, John"
    # braced fields still work alongside
    assert "EVIDENCE-CONTEXT" in e["fields"]["keywords"]


def test_multiline_quoted_field_parsed():
    entry = '@book{k2003,\n  author = "Kvanvig,\n    Jonathan",\n  title = "The Value of Knowledge",\n  year = "2003",\n}'
    from enrich_bibliography import parse_bibtex_entries
    e = parse_bibtex_entries(entry)[0]
    assert "Jonathan" in e["fields"]["author"]


class TestFieldDetection:
    """Tests for field detection helpers."""

    def test_has_abstract_true(self):
        """Should detect existing abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_WITH_ABSTRACT)
        assert enrich_bibliography.has_abstract(entries[0]) is True

    def test_has_abstract_false(self):
        """Should detect missing abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        assert enrich_bibliography.has_abstract(entries[0]) is False

    def test_is_incomplete_true(self):
        """Should detect INCOMPLETE flag."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_INCOMPLETE)
        assert enrich_bibliography.is_incomplete(entries[0]) is True

    def test_is_incomplete_false(self):
        """Should detect missing INCOMPLETE flag."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        assert enrich_bibliography.is_incomplete(entries[0]) is False

    def test_get_doi(self):
        """Should extract DOI from entry."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        doi = enrich_bibliography.get_doi(entries[0])
        assert doi == "10.2307/2024717"

    def test_get_author_last_name(self):
        """Should extract author last name."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        last_name = enrich_bibliography.get_author_last_name(entries[0])
        assert last_name == "Frankfurt"

    def test_get_year(self):
        """Should extract year from entry."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        year = enrich_bibliography.get_year(entries[0])
        assert year == 1971


# =============================================================================
# Entry Modification Tests
# =============================================================================

class TestEntryModification:
    """Tests for BibTeX entry modification."""

    def test_add_field_to_entry(self):
        """Should add new field to entry."""
        import enrich_bibliography

        result = enrich_bibliography.add_field_to_entry(
            SAMPLE_ENTRY_NO_ABSTRACT,
            'abstract',
            'This is a test abstract.'
        )

        assert 'abstract = {This is a test abstract.}' in result

    def test_add_field_ensures_preceding_comma(self):
        """Should add comma to the opening line when it lacks one.

        New fields are inserted right after the opening `@type{key,` line
        (item 13 D2), so it is that line - not the last existing field -
        whose trailing comma is ensured.
        """
        import enrich_bibliography

        entry_no_opening_comma = """@article{test2024
  author = {Test Author},
  title = {Test Title},
  year = {2024},
  keywords = {test, keyword, High}
}"""

        result = enrich_bibliography.add_field_to_entry(
            entry_no_opening_comma,
            'abstract',
            'This is a test abstract.'
        )

        assert 'abstract = {This is a test abstract.}' in result
        # The opening line must now have a trailing comma
        assert '@article{test2024,' in result
        # Validate with pybtex
        from pybtex.database import parse_string
        parse_string(result, bib_format='bibtex')

    def test_add_field_no_double_comma(self):
        """Should not add double comma when preceding field already has one."""
        import enrich_bibliography

        result = enrich_bibliography.add_field_to_entry(
            SAMPLE_ENTRY_NO_ABSTRACT,
            'abstract',
            'Test abstract.'
        )

        assert 'High},,' not in result

    def test_add_keyword_to_entry_new(self):
        """Should add keyword to entry without keywords."""
        import enrich_bibliography

        entry_no_keywords = """@article{test,
  author = {Test},
  title = {Test},
  year = {2020},
}"""

        result = enrich_bibliography.add_keyword_to_entry(
            entry_no_keywords,
            'INCOMPLETE'
        )

        assert 'keywords = {INCOMPLETE}' in result

    def test_add_keyword_to_entry_existing(self):
        """Should append keyword to existing keywords."""
        import enrich_bibliography

        result = enrich_bibliography.add_keyword_to_entry(
            SAMPLE_ENTRY_NO_ABSTRACT,
            'INCOMPLETE'
        )

        assert 'INCOMPLETE' in result
        # Original keywords should still be there
        assert 'free-will' in result

    def test_add_keyword_already_present(self):
        """Should not duplicate existing keyword."""
        import enrich_bibliography

        result = enrich_bibliography.add_keyword_to_entry(
            SAMPLE_ENTRY_INCOMPLETE,
            'INCOMPLETE'
        )

        # Should only have one INCOMPLETE
        assert result.count('INCOMPLETE') == 1

    def test_add_keyword_to_entry_quoted_preserves_existing_tokens(self):
        """Quote-delimited keywords field: appending must preserve every
        existing token (topic tags + importance level), not replace them.

        Regression (reviewer-reproduced): the field-existence check only
        matched brace-delimited `keywords = {...}`. A quote-delimited
        field fell through to add_field_to_entry, which REPLACES a field
        wholesale on a hit -- silently destroying all existing tokens and
        leaving only the newly added keyword.
        """
        import enrich_bibliography

        entry_quoted_keywords = """@article{test,
  author = {Test},
  title = {Test},
  year = {2020},
  keywords = "topic-tag, position-tag, High",
}"""

        result = enrich_bibliography.add_keyword_to_entry(
            entry_quoted_keywords,
            'INCOMPLETE'
        )

        assert 'topic-tag' in result
        assert 'position-tag' in result
        assert 'High' in result
        assert 'INCOMPLETE' in result
        assert result.lower().count('keywords') == 1

    def test_remove_keyword_from_entry_quoted_preserves_other_tokens(self):
        """Symmetric fix on the remove path: a quote-delimited keywords
        field must lose only the target keyword, keeping the rest."""
        import enrich_bibliography

        entry_quoted_keywords = """@article{test,
  author = {Test},
  title = {Test},
  year = {2020},
  keywords = "topic-tag, position-tag, INCOMPLETE",
}"""

        result = enrich_bibliography.remove_keyword_from_entry(
            entry_quoted_keywords,
            'INCOMPLETE'
        )

        assert 'INCOMPLETE' not in result
        assert 'topic-tag' in result
        assert 'position-tag' in result
        assert result.lower().count('keywords') == 1


# =============================================================================
# Abstract Resolution Passthrough Tests
# =============================================================================

class TestResolveAbstractForEntry:
    """Tests for resolve_abstract_for_entry parameter passing."""

    @patch("get_abstract.resolve_abstract")
    def test_passes_title_and_author_with_doi(self, mock_resolve):
        """Should pass title and author even when DOI is present."""
        mock_resolve.return_value = ("Abstract", "s2")

        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        enrich_bibliography.resolve_abstract_for_entry(
            entries[0], None, None, None
        )

        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args
        assert call_kwargs.kwargs.get("doi") == "10.2307/2024717"
        assert call_kwargs.kwargs.get("title") == "Freedom of the Will and the Concept of a Person"
        assert call_kwargs.kwargs.get("author") == "Frankfurt"


# =============================================================================
# Enrichment Tests
# =============================================================================

class TestEnrichment:
    """Tests for entry enrichment logic."""

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_entry_success(self, mock_resolve):
        """Should add abstract when found."""
        mock_resolve.return_value = ("This is the resolved abstract.", "openalex")

        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        enriched_text, was_enriched, source = enrich_bibliography.enrich_entry(
            entries[0], None, None, None
        )

        assert was_enriched is True
        assert source == "openalex"
        assert 'abstract = {' in enriched_text
        assert 'abstract_source = {openalex}' in enriched_text

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_entry_not_found(self, mock_resolve):
        """Should mark INCOMPLETE when abstract not found."""
        mock_resolve.return_value = (None, None)

        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_NO_ABSTRACT)
        enriched_text, was_enriched, source = enrich_bibliography.enrich_entry(
            entries[0], None, None, None
        )

        assert was_enriched is False
        assert source is None
        assert 'INCOMPLETE' in enriched_text
        assert 'no-abstract' in enriched_text

    def test_enrich_entry_skips_existing_abstract(self):
        """Should skip entries that already have abstract."""
        import enrich_bibliography

        entries = enrich_bibliography.parse_bibtex_entries(SAMPLE_ENTRY_WITH_ABSTRACT)
        enriched_text, was_enriched, source = enrich_bibliography.enrich_entry(
            entries[0], None, None, None
        )

        assert was_enriched is False
        # Original abstract should be preserved
        assert 'accordance with reason' in enriched_text


# =============================================================================
# Batch Processing Tests
# =============================================================================

class TestBatchProcessing:
    """Tests for batch bibliography enrichment."""

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_mixed(self, mock_resolve, tmp_path):
        """Should handle mixed entries correctly."""
        # Return abstract for first call, None for subsequent
        mock_resolve.side_effect = [
            ("Found abstract", "core"),
            (None, None),
        ]

        import enrich_bibliography

        # Create temp input file
        content = f"{SAMPLE_ENTRY_NO_ABSTRACT}\n\n{SAMPLE_ENTRY_INCOMPLETE}"

        input_path = tmp_path / "test.bib"
        input_path.write_text(content, encoding='utf-8')
        output_path = tmp_path / "output.bib"

        stats = enrich_bibliography.enrich_bibliography(
            input_path, output_path, None, None, None
        )

        assert stats['total'] == 2
        assert stats['enriched'] == 1
        assert stats['marked_incomplete'] == 1

        # Check output file
        output_content = output_path.read_text(encoding='utf-8')
        assert 'Found abstract' in output_content
        assert 'abstract_source = {core}' in output_content

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_preserves_comments(self, mock_resolve, tmp_path):
        """Should preserve @comment entries."""
        mock_resolve.return_value = ("Abstract", "s2")

        import enrich_bibliography

        content = f"{SAMPLE_COMMENT}\n\n{SAMPLE_ENTRY_NO_ABSTRACT}"

        input_path = tmp_path / "test.bib"
        input_path.write_text(content, encoding='utf-8')
        output_path = tmp_path / "output.bib"

        stats = enrich_bibliography.enrich_bibliography(
            input_path, output_path, None, None, None
        )

        assert stats['skipped'] == 1  # Comment was skipped

        output_content = output_path.read_text(encoding='utf-8')
        assert 'DOMAIN: Testing Domain' in output_content

    def test_enrich_bibliography_file_not_found(self):
        """Should raise error for missing input file."""
        import enrich_bibliography

        with pytest.raises(FileNotFoundError):
            enrich_bibliography.enrich_bibliography(
                Path("/nonexistent/file.bib"), None, None, None, None
            )

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_atomic_write_on_failure(self, mock_resolve, tmp_path):
        """Original file should be untouched if write fails."""
        mock_resolve.return_value = ("Abstract text", "s2")

        import enrich_bibliography

        input_path = tmp_path / "test.bib"
        input_path.write_text(SAMPLE_ENTRY_NO_ABSTRACT, encoding='utf-8')
        original_content = input_path.read_text(encoding='utf-8')

        # Mock os.replace to simulate a failure after temp file is written
        with patch("enrich_bibliography.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                enrich_bibliography.enrich_bibliography(
                    input_path, None, None, None, None
                )

        # Original file should be unchanged
        assert input_path.read_text(encoding='utf-8') == original_content

        # Temp file should have been cleaned up by error handler
        temp_file = input_path.with_suffix('.bib.tmp')
        assert not temp_file.exists(), "Temp file should be cleaned up on os.replace failure"

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_validation_failure_preserves_original(self, mock_resolve, tmp_path):
        """Original file should be untouched if pybtex validation fails."""
        mock_resolve.return_value = ("Abstract text", "s2")

        import enrich_bibliography

        input_path = tmp_path / "test.bib"
        input_path.write_text(SAMPLE_ENTRY_NO_ABSTRACT, encoding='utf-8')
        original_content = input_path.read_text(encoding='utf-8')

        # Mock pybtex parse_file to raise an exception (simulating invalid BibTeX)
        with patch("pybtex.database.parse_file", side_effect=Exception("Invalid BibTeX")):
            stats = enrich_bibliography.enrich_bibliography(
                input_path, None, None, None, None
            )

        # Original file should be unchanged
        assert input_path.read_text(encoding='utf-8') == original_content

        # Stats should indicate validation failure
        assert stats.get('validation_failed') is True

        # Temp file should have been cleaned up
        temp_file = input_path.with_suffix('.bib.tmp')
        assert not temp_file.exists(), "Temp file should be cleaned up on validation failure"

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_enrich_bibliography_inplace(self, mock_resolve, tmp_path):
        """Should overwrite input when no output specified."""
        mock_resolve.return_value = ("Inplace abstract", "openalex")

        import enrich_bibliography

        input_path = tmp_path / "test.bib"
        input_path.write_text(SAMPLE_ENTRY_NO_ABSTRACT, encoding='utf-8')

        enrich_bibliography.enrich_bibliography(
            input_path, None, None, None, None  # No output path = inplace
        )

        output_content = input_path.read_text(encoding='utf-8')
        assert 'Inplace abstract' in output_content


# =============================================================================
# Stats Tests
# =============================================================================

class TestStats:
    """Tests for statistics tracking."""

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_stats_tracks_sources(self, mock_resolve, tmp_path):
        """Should track abstract sources in stats."""
        # Mix of sources
        mock_resolve.side_effect = [
            ("Abstract 1", "s2"),
            ("Abstract 2", "openalex"),
            ("Abstract 3", "core"),
        ]

        import enrich_bibliography

        # Three entries without abstract
        entry = """@article{test%d,
  author = {Test},
  title = {Test %d},
  year = {2020},
  doi = {10.1234/test%d},
}"""
        content = "\n\n".join(entry % (i, i, i) for i in range(3))

        input_path = tmp_path / "test.bib"
        input_path.write_text(content, encoding='utf-8')

        stats = enrich_bibliography.enrich_bibliography(
            input_path, None, None, None, None
        )

        assert stats['enriched'] == 3
        assert stats['sources']['s2'] == 1
        assert stats['sources']['openalex'] == 1
        assert stats['sources']['core'] == 1


# =============================================================================
# Enrichment Ledger Tests (evidence-tier: attests source + hash of the
# abstract this script itself wrote, so the barrier can tell a
# ledger-attested abstract from a hand-written/fabricated one).
# =============================================================================

class TestEnrichmentLedger:
    """Tests for the enrichment ledger written to
    <bib_dir>/intermediate_files/json/enrichment_ledger-<bib_stem>.json.

    Sibling of the cleaning ledger (hooks/metadata_cleaner.py): written on
    every parse-successful run (empty entries is valid), merged with any
    prior ledger (new writes win per key, stale keys pruned), skipped only
    when stats['validation_failed'] is True.
    """

    def _ledger_path(self, tmp_path, stem="test"):
        return tmp_path / "intermediate_files" / "json" / f"enrichment_ledger-{stem}.json"

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_ledger_records_source_and_hash(self, mock_resolve, tmp_path):
        """API-source enrichment site (~line 386) must record the exact
        abstract text and source it wrote."""
        import enrich_bibliography
        import stamp_evidence
        mock_resolve.return_value = ("A found abstract text.", "s2")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_NO_ABSTRACT, encoding="utf-8")

        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        ledger = json.loads(self._ledger_path(tmp_path).read_text(encoding="utf-8"))
        assert ledger["schema_version"] == 1
        assert ledger["bib_file"] == "test.bib"
        ent = ledger["entries"]["frankfurt1971freedom"]
        assert ent["abstract_source"] == "s2"
        assert ent["abstract_sha256"] == stamp_evidence.abstract_hash("A found abstract text.")

    @patch("enrich_bibliography.resolve_ndpr_abstract")
    def test_ledger_records_ndpr_source_and_hash(self, mock_ndpr, tmp_path):
        """NDPR enrichment site (~line 492) must also record its write."""
        import enrich_bibliography
        import stamp_evidence
        mock_ndpr.return_value = ("Summary of the book from NDPR review.", "ndpr")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_BOOK_INCOMPLETE_HIGH, encoding="utf-8")

        with patch("enrich_bibliography.resolve_abstract_for_entry", return_value=(None, None)):
            enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        ledger = json.loads(self._ledger_path(tmp_path).read_text(encoding="utf-8"))
        ent = ledger["entries"]["parfit1984reasons"]
        assert ent["abstract_source"] == "ndpr"
        assert ent["abstract_sha256"] == stamp_evidence.abstract_hash(
            "Summary of the book from NDPR review."
        )

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_rerun_on_enriched_file_preserves_ledger(self, mock_resolve, tmp_path):
        """Second run skips has_abstract entries; ledger must NOT be
        clobbered back to empty."""
        import enrich_bibliography
        mock_resolve.return_value = ("A found abstract text.", "s2")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_NO_ABSTRACT, encoding="utf-8")

        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)
        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)  # no-op pass

        ledger = json.loads(self._ledger_path(tmp_path).read_text(encoding="utf-8"))
        assert "frankfurt1971freedom" in ledger["entries"]

    def test_stale_keys_pruned(self, tmp_path, monkeypatch):
        """Keys no longer present in the bib are dropped from the ledger."""
        import enrich_bibliography
        # This entry now hits the pre-filled-attestation path (Task 2) --
        # keep this test about pruning only, not attestation, so no network.
        monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                            lambda *a, **k: (None, None))

        ledger_dir = tmp_path / "intermediate_files" / "json"
        ledger_dir.mkdir(parents=True)
        (ledger_dir / "enrichment_ledger-test.json").write_text(json.dumps({
            "schema_version": 1, "bib_file": "test.bib",
            "entries": {"gone2000": {"abstract_source": "s2", "abstract_sha256": "x"}},
        }), encoding="utf-8")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_WITH_ABSTRACT, encoding="utf-8")

        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        ledger = json.loads((ledger_dir / "enrichment_ledger-test.json").read_text(encoding="utf-8"))
        assert "gone2000" not in ledger["entries"]

    def test_json_list_typed_ledger_recovers_instead_of_crashing(self, tmp_path, monkeypatch):
        """Finding 3: a malformed on-disk ledger whose top-level JSON parses
        but isn't a dict (e.g. a bare list) must fall back to an empty
        ledger, not raise AttributeError past the (JSONDecodeError, OSError)
        except clause."""
        import enrich_bibliography
        # Pre-filled-attestation path (Task 2) would otherwise hit the API;
        # this test is about the malformed-ledger guard, not attestation.
        monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                            lambda *a, **k: (None, None))

        ledger_dir = tmp_path / "intermediate_files" / "json"
        ledger_dir.mkdir(parents=True)
        (ledger_dir / "enrichment_ledger-test.json").write_text(
            json.dumps(["not", "a", "dict"]), encoding="utf-8")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_WITH_ABSTRACT, encoding="utf-8")

        # Must not raise.
        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        ledger = json.loads((ledger_dir / "enrichment_ledger-test.json").read_text(encoding="utf-8"))
        assert ledger["entries"] == {}

    def test_dict_ledger_with_non_dict_entries_recovers(self, tmp_path, monkeypatch):
        """Same guard, other malformed shape: top-level dict but 'entries'
        itself isn't a dict."""
        import enrich_bibliography
        # Pre-filled-attestation path (Task 2) would otherwise hit the API;
        # this test is about the malformed-ledger guard, not attestation.
        monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                            lambda *a, **k: (None, None))

        ledger_dir = tmp_path / "intermediate_files" / "json"
        ledger_dir.mkdir(parents=True)
        (ledger_dir / "enrichment_ledger-test.json").write_text(json.dumps({
            "schema_version": 1, "bib_file": "test.bib",
            "entries": ["not", "a", "dict"],
        }), encoding="utf-8")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_WITH_ABSTRACT, encoding="utf-8")

        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        ledger = json.loads((ledger_dir / "enrichment_ledger-test.json").read_text(encoding="utf-8"))
        assert ledger["entries"] == {}

    def test_researcher_written_abstract_not_attested(self, tmp_path, monkeypatch):
        """Entry already has an abstract; the API confirms nothing (no
        network in this unit test) -> pre-filled attestation (Task 2) is a
        no-op -> ledger is still written (always-write) but contains no
        entry for it, and the entry text passes through unchanged."""
        import enrich_bibliography
        monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                            lambda *a, **k: (None, None))

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_WITH_ABSTRACT, encoding="utf-8")

        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        assert bib.read_text(encoding="utf-8").strip() == SAMPLE_ENTRY_WITH_ABSTRACT.strip()
        p = self._ledger_path(tmp_path)
        assert p.exists()
        assert json.loads(p.read_text(encoding="utf-8"))["entries"] == {}

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_ledger_skipped_on_validation_failure(self, mock_resolve, tmp_path):
        """No ledger write (and no clobber of an existing one) when the bib
        write itself was aborted by pybtex validation."""
        import enrich_bibliography
        mock_resolve.return_value = ("Abstract text", "s2")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_NO_ABSTRACT, encoding="utf-8")

        with patch("pybtex.database.parse_file", side_effect=Exception("Invalid BibTeX")):
            stats = enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        assert stats.get("validation_failed") is True
        assert not self._ledger_path(tmp_path).exists()

    def test_undecodable_ledger_file_does_not_crash_enrichment(self, tmp_path, monkeypatch):
        """_update_enrichment_ledger's read guard must be as wide as
        _load_prior_ledger's: an undecodable (invalid-UTF-8) ledger file
        raises UnicodeDecodeError, which the narrower
        `except (json.JSONDecodeError, OSError)` clause does not catch --
        crashing enrichment AFTER the bib write already happened. The run
        must complete and rewrite the ledger cleanly instead."""
        import enrich_bibliography
        monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                            lambda *a, **k: (None, None))

        ledger_dir = tmp_path / "intermediate_files" / "json"
        ledger_dir.mkdir(parents=True)
        (ledger_dir / "enrichment_ledger-test.json").write_bytes(
            b'\xff\xfe\x00invalid utf-8 \x80\x81')

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_WITH_ABSTRACT, encoding="utf-8")

        # Must not raise.
        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        ledger = json.loads((ledger_dir / "enrichment_ledger-test.json").read_text(encoding="utf-8"))
        assert ledger["entries"] == {}

    @patch("enrich_bibliography.resolve_abstract_for_entry")
    def test_ledger_hash_survives_pybtex_roundtrip(self, mock_resolve, tmp_path):
        """The attestation must still verify after the SubagentStop cleaner
        rewrites the file via pybtex Writer (reflow/escaping)."""
        import enrich_bibliography
        import stamp_evidence
        from pybtex.database import parse_file
        from pybtex.database.output.bibtex import Writer

        abstract = "An abstract with special chars: 5% & #2, A_B."
        mock_resolve.return_value = (abstract, "s2")

        bib = tmp_path / "test.bib"
        bib.write_text(SAMPLE_ENTRY_NO_ABSTRACT, encoding="utf-8")

        enrich_bibliography.enrich_bibliography(bib, None, None, None, None)

        data = parse_file(str(bib), bib_format="bibtex")
        with open(bib, "w", encoding="utf-8") as f:
            Writer().write_file(data, f)

        roundtripped = stamp_evidence.parse_entry_fields(bib.read_text(encoding="utf-8"))
        ledger = json.loads(self._ledger_path(tmp_path).read_text(encoding="utf-8"))
        ent = ledger["entries"]["frankfurt1971freedom"]
        assert stamp_evidence.attest_abstract(roundtripped, ent) is True


def test_add_field_replaces_quoted_value():
    """pybtex round-trips write quoted fields; replace must not duplicate."""
    import enrich_bibliography

    entry = ('@article{k1,\n'
             '    author = "McAllister, James W.",\n'
             '    abstract_source = "semantic\\_scholar",\n'
             '    title = "T"\n'
             '}')
    out = enrich_bibliography.add_field_to_entry(entry, 'abstract_source', 's2')
    assert out.lower().count('abstract_source') == 1
    assert 'abstract_source = {s2}' in out
    assert 'semantic' not in out


def test_add_field_replace_is_backslash_safe():
    r"""Abstracts carry LaTeX; a template re.sub would eat \1 or \g."""
    import enrich_bibliography

    entry = '@article{k1,\n  abstract = {old text},\n  title = {T}\n}'
    value = r'uses \textit{emphasis} and a literal \1 sequence'
    out = enrich_bibliography.add_field_to_entry(entry, 'abstract', value)
    assert value in out


def test_add_field_replaces_braced_value_with_nested_braces():
    import enrich_bibliography

    entry = '@article{k1,\n  abstract = {outer {nested} text},\n  title = {T}\n}'
    out = enrich_bibliography.add_field_to_entry(entry, 'abstract', 'replaced')
    assert 'abstract = {replaced}' in out
    assert 'nested' not in out


def test_add_field_replaces_two_level_nested_braced_value():
    """Review finding 1 (Task 4): a value nested TWO levels deep -- e.g. a
    LaTeX emphasis command wrapping a further-nested phrase -- fails the
    old one-level-tolerant regex outright, falling through to the insert
    branch and leaving the stale field behind (a duplicate `abstract =`
    pybtex rejects). The depth-counting locator must find and replace it
    whole, regardless of nesting depth."""
    import enrich_bibliography

    entry = (
        "@article{k1,\n"
        "  abstract = {We show {\\it Kant's {a priori}} fails.},\n"
        "  title = {T}\n"
        "}"
    )
    out = enrich_bibliography.add_field_to_entry(entry, 'abstract', 'replaced')
    assert out.count('abstract =') == 1
    assert 'abstract = {replaced}' in out
    assert 'Kant' not in out
    from pybtex.database import parse_string
    parse_string(out, bib_format='bibtex')  # must not raise (no duplicate field)


def test_add_field_replace_all_occurrences_pinned():
    """Pins existing semantics: re.sub without count replaces EVERY
    occurrence of the field within the entry text. Callers rely on
    entry_text being a SINGLE entry (split_entries chunks) -- this test
    documents that invariant by showing what happens when it's violated."""
    import enrich_bibliography

    entry = ('@article{k1,\n  abstract = {first},\n  title = {T},\n'
             '  abstract = {second}\n}')
    out = enrich_bibliography.add_field_to_entry(entry, 'abstract', 'new')
    assert out.count('abstract = {new}') == 2


# =============================================================================
# Pre-filled Abstract Attestation Tests (Task 2)
# =============================================================================

def _prefilled_bib(tmp_path, abstract='Same text here.', source_field='semantic_scholar'):
    bib = tmp_path / "literature-domain-1.bib"
    bib.write_text(
        '@article{k1,\n'
        '  author = {McAllister, James W.},\n'
        '  title = {What Do Patterns Tell Us},\n'
        '  doi = {10.1007/s11229-009-9613-x},\n'
        f'  abstract = {{{abstract}}},\n'
        f'  abstract_source = {{{source_field}}},\n'
        '  keywords = {patterns, Medium}\n'
        '}\n', encoding='utf-8')
    return bib


def test_prefilled_abstract_attested_on_hash_match(tmp_path, monkeypatch):
    import enrich_bibliography

    bib = _prefilled_bib(tmp_path)
    # Fetched text differs only in whitespace -> abstract_hash-equal.
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                        lambda *a, **k: ('Same  text here.', 's2'))
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    out = bib.read_text(encoding='utf-8')
    assert stats['prefilled_attested'] == 1
    assert stats['prefilled_unverified'] == 0
    assert stats['already_had_abstract'] == 1
    assert 'abstract_source = {s2}' in out
    assert out.lower().count('abstract_source') == 1
    ledger = json.loads(
        (tmp_path / "intermediate_files" / "json"
         / "enrichment_ledger-literature-domain-1.json").read_text(encoding='utf-8'))
    rec = ledger['entries']['k1']
    assert rec['abstract_source'] == 's2'
    from stamp_evidence import abstract_hash
    assert rec['abstract_sha256'] == abstract_hash('Same text here.')


def test_prefilled_abstract_mismatch_left_unattested(tmp_path, monkeypatch):
    import enrich_bibliography

    bib = _prefilled_bib(tmp_path)
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                        lambda *a, **k: ('Entirely different abstract text.', 's2'))
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    out = bib.read_text(encoding='utf-8')
    assert stats['prefilled_attested'] == 0
    assert stats['prefilled_unverified'] == 1
    assert 'abstract_source = {semantic_scholar}' in out  # untouched
    ledger = json.loads(
        (tmp_path / "intermediate_files" / "json"
         / "enrichment_ledger-literature-domain-1.json").read_text(encoding='utf-8'))
    assert ledger['entries'] == {}  # nothing attested


def test_prefilled_abstract_fetch_failure_is_noop(tmp_path, monkeypatch):
    import enrich_bibliography

    bib = _prefilled_bib(tmp_path)
    def boom(*a, **k):
        raise RuntimeError("API down")
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry', boom)
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    assert stats['prefilled_unverified'] == 1
    assert 'abstract = {Same text here.}' in bib.read_text(encoding='utf-8')


def test_rerun_skips_already_attested_entries(tmp_path, monkeypatch):
    """Re-running enrichment on an already-enriched file must cost ZERO
    API calls for entries whose text the prior ledger already attests
    (Task 5 guidance tells researchers to re-run after adding entries)."""
    import enrich_bibliography
    from stamp_evidence import abstract_hash

    bib = _prefilled_bib(tmp_path, source_field='s2')
    ij = tmp_path / "intermediate_files" / "json"
    ij.mkdir(parents=True, exist_ok=True)
    (ij / "enrichment_ledger-literature-domain-1.json").write_text(json.dumps({
        "schema_version": 1, "bib_file": "literature-domain-1.bib",
        "entries": {"k1": {"abstract_source": "s2",
                           "abstract_sha256": abstract_hash('Same text here.')}},
    }), encoding='utf-8')
    def fail(*a, **k):
        raise AssertionError("attested entries must not be re-fetched")
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry', fail)
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    assert stats['prefilled_attested'] == 1
    ledger = json.loads(
        (ij / "enrichment_ledger-literature-domain-1.json").read_text(encoding='utf-8'))
    assert ledger['entries']['k1']['abstract_sha256'] == abstract_hash('Same text here.')


def test_source_mismatch_falls_through_to_api_check(tmp_path, monkeypatch):
    """Ledger says openalex, bib field says s2, hash matches: the fast
    path must NOT fire (field==ledger-source is part of what the barrier
    checks); the API path runs and re-normalizes the field."""
    import enrich_bibliography
    from stamp_evidence import abstract_hash

    bib = _prefilled_bib(tmp_path, source_field='s2')
    ij = tmp_path / "intermediate_files" / "json"
    ij.mkdir(parents=True, exist_ok=True)
    (ij / "enrichment_ledger-literature-domain-1.json").write_text(json.dumps({
        "schema_version": 1, "bib_file": "literature-domain-1.bib",
        "entries": {"k1": {"abstract_source": "openalex",
                           "abstract_sha256": abstract_hash('Same text here.')}},
    }), encoding='utf-8')
    calls = []
    def resolver(*a, **k):
        calls.append(1)
        return ('Same text here.', 'openalex')
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry', resolver)
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    assert calls, "API check must run on source mismatch"
    assert stats['prefilled_attested'] == 1
    assert 'abstract_source = {openalex}' in bib.read_text(encoding='utf-8')


def test_drifted_text_keeps_prior_ledger_record(tmp_path, monkeypatch):
    """Pre-filled text that matches NOTHING (drifted since attestation)
    stays unattested -- but the PRIOR ledger record must survive the
    merge, or the barrier's self-heal has nothing to heal toward."""
    import enrich_bibliography

    bib = _prefilled_bib(tmp_path, abstract='Drifted mutated text.',
                         source_field='s2')
    ij = tmp_path / "intermediate_files" / "json"
    ij.mkdir(parents=True, exist_ok=True)
    (ij / "enrichment_ledger-literature-domain-1.json").write_text(json.dumps({
        "schema_version": 1, "bib_file": "literature-domain-1.bib",
        "entries": {"k1": {"abstract_source": "s2",
                           "abstract_sha256": "a" * 64}},
    }), encoding='utf-8')
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                        lambda *a, **k: ('The true original text.', 's2'))
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    assert stats['prefilled_unverified'] == 1
    ledger = json.loads(
        (ij / "enrichment_ledger-literature-domain-1.json").read_text(encoding='utf-8'))
    assert ledger['entries']['k1']['abstract_sha256'] == "a" * 64  # preserved


def test_non_dict_ledger_value_degrades_to_api_check(tmp_path, monkeypatch):
    """A malformed ledger record (string value) must not crash the run --
    it degrades to the API path (review finding 1b)."""
    import enrich_bibliography

    bib = _prefilled_bib(tmp_path, source_field='s2')
    ij = tmp_path / "intermediate_files" / "json"
    ij.mkdir(parents=True, exist_ok=True)
    (ij / "enrichment_ledger-literature-domain-1.json").write_text(json.dumps({
        "schema_version": 1, "bib_file": "literature-domain-1.bib",
        "entries": {"k1": "garbage"},
    }), encoding='utf-8')
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                        lambda *a, **k: ('Same text here.', 's2'))
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    assert stats['prefilled_attested'] == 1  # API path attested it


def test_resolver_none_source_rejected(tmp_path, monkeypatch):
    """(text, None) from the resolver must not attest (the `not source`
    guard) -- a sourceless record would fail attest_abstract anyway."""
    import enrich_bibliography

    bib = _prefilled_bib(tmp_path)
    monkeypatch.setattr(enrich_bibliography, 'resolve_abstract_for_entry',
                        lambda *a, **k: ('Same text here.', None))
    stats = enrich_bibliography.enrich_bibliography(bib, None, '', '', '')
    assert stats['prefilled_unverified'] == 1


def test_ndpr_pass_sees_quoted_keywords(tmp_path, monkeypatch):
    """A round-tripped bib carries keywords = "..." -- the NDPR book pass
    must still detect INCOMPLETE + High there."""
    import enrich_bibliography as eb
    bib = tmp_path / "in.bib"
    bib.write_text(
        '@book{zagzebski1996virtues,\n'
        '  author = "Zagzebski, Linda",\n'
        '  title = "Virtues of the Mind",\n'
        '  year = "1996",\n'
        '  keywords = "virtue-epistemology, High, INCOMPLETE, no-abstract"\n'
        '}\n', encoding="utf-8")
    monkeypatch.setattr(eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (None, None))
    calls = []
    def fake_ndpr(title, author=None, debug=False):
        calls.append(title)
        return None, None
    monkeypatch.setattr(eb, "resolve_ndpr_abstract", fake_ndpr)
    eb.enrich_bibliography(bib, None, None, None, None)
    assert calls == ["Virtues of the Mind"]


def test_name_invalid_entries_flags_unbalanced_entry():
    from enrich_bibliography import _name_invalid_entries
    good = "@article{ok2020,\n  author = {A, B},\n  title = {T},\n  year = {2020},\n}"
    bad = "@article{broken2020,\n  author = {A, B},\n  title = {T,\n  year = {2020},\n}"
    named = _name_invalid_entries([good, bad])
    assert len(named) == 1
    key, diag = named[0]
    assert key == "broken2020"
    assert diag  # carries the exception class/message text


def test_name_invalid_entries_skips_nonentry_chunks():
    from enrich_bibliography import _name_invalid_entries
    assert _name_invalid_entries([
        "@comment{arbitrary text}",
        "@string{jphil = {J. Phil.}}",
        "@preamble{...}",
    ]) == []


def test_validation_failure_reports_offender(tmp_path, monkeypatch, capsys):
    """End-to-end: corrupt output -> warning names the offending key and
    stats carry validation_failed_keys."""
    import enrich_bibliography as eb
    bib = tmp_path / "in.bib"
    bib.write_text(
        "@article{ok2020,\n  author = {A, B},\n  title = {T},\n"
        "  year = {2020},\n}\n",
        encoding="utf-8")
    monkeypatch.setattr(eb, "resolve_abstract_for_entry",
                        lambda *a, **k: (None, None))
    # Force corruption the way production did: make the enriched text
    # brace-unbalanced.
    real = eb.add_keyword_to_entry
    monkeypatch.setattr(eb, "add_keyword_to_entry",
                        lambda text, kw: real(text, kw).replace("}", "", 1))
    stats = eb.enrich_bibliography(bib, None, None, None, None)
    assert stats.get("validation_failed") is True
    assert stats.get("validation_failed_keys") == ["ok2020"]
    err = capsys.readouterr().err
    assert "ok2020" in err
