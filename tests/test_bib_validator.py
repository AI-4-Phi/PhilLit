"""Tests for bib_validator.py - BibTeX validation hook.

Tests the SubagentStop hook that validates .bib files for:
1. UTF-8 encoding
2. No LaTeX diacritic escapes
3. Valid BibTeX syntax
4. No duplicate keys
5. Required fields per entry type
6. No BibLaTeX fields
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Add hooks directory to path
HOOKS_DIR = Path(__file__).parent.parent / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from bib_validator import (
    check_utf8_encoding,
    check_latex_escapes,
    check_duplicate_fields,
    check_duplicate_keys,
    check_bibtex_syntax,
    check_required_fields,
    check_biblatex_fields,
    validate_bib,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def valid_article():
    """Complete, valid @article entry."""
    return """@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {Journal of Philosophy},
  year = {1971},
  volume = {68},
  pages = {5--20},
  doi = {10.2307/2024717},
  note = {CORE ARGUMENT: Examines free will and moral responsibility.}
}"""


@pytest.fixture
def valid_book():
    """Complete, valid @book entry with author."""
    return """@book{rawls1971theory,
  author = {Rawls, John},
  title = {A Theory of Justice},
  publisher = {Harvard University Press},
  year = {1971}
}"""


@pytest.fixture
def valid_book_editor():
    """Complete, valid @book entry with editor (no author)."""
    return """@book{mele2006freewill,
  editor = {Mele, Alfred R.},
  title = {Free Will and Luck},
  publisher = {Oxford University Press},
  year = {2006}
}"""


@pytest.fixture
def valid_inproceedings():
    """Complete, valid @inproceedings entry."""
    return """@inproceedings{smith2020ai,
  author = {Smith, Jane},
  title = {AI and Philosophy},
  booktitle = {Proceedings of PhilAI 2020},
  year = {2020}
}"""


@pytest.fixture
def valid_incollection():
    """Complete, valid @incollection entry."""
    return """@incollection{wolf1990freedom,
  author = {Wolf, Susan},
  title = {Freedom Within Reason},
  booktitle = {The Oxford Handbook of Free Will},
  publisher = {Oxford University Press},
  year = {1990},
  pages = {100--120}
}"""


@pytest.fixture
def utf8_content():
    """Valid UTF-8 content with international characters."""
    return """@article{muller2020ethics,
  author = {Müller, Hans-Georg and García, María and Søren, Kierkegaard},
  title = {Éthique et Philosophie: Une Réflexion},
  journal = {Revue Philosophique},
  year = {2020}
}"""


@pytest.fixture
def latex_escape_content():
    """Content with LaTeX diacritic escapes (should fail)."""
    return """@article{test2020,
  author = {M\\\"uller, Hans and Garc\\'ia, Mar\\'ia},
  title = {Test Paper},
  journal = {Test Journal},
  year = {2020}
}"""


@pytest.fixture
def duplicate_keys_content():
    """Content with duplicate citation keys."""
    return """@article{same2020key,
  author = {First, Author},
  title = {First Paper},
  journal = {Journal One},
  year = {2020}
}

@article{same2020key,
  author = {Second, Author},
  title = {Second Paper},
  journal = {Journal Two},
  year = {2021}
}"""


@pytest.fixture
def syntax_error_content():
    """Content with BibTeX syntax error (missing closing brace)."""
    return """@article{test2020,
  author = {Test, Author},
  title = {Test Paper},
  journal = {Test Journal},
  year = {2020
}"""


@pytest.fixture
def missing_fields_article():
    """Article missing required fields (journal, year)."""
    return """@article{incomplete2020,
  author = {Test, Author},
  title = {Incomplete Paper}
}"""


@pytest.fixture
def missing_author_book():
    """Book missing both author and editor."""
    return """@book{noauthor2020,
  title = {Book Without Author},
  publisher = {Some Publisher},
  year = {2020}
}"""


@pytest.fixture
def biblatex_fields_content():
    """Content with BibLaTeX-specific fields."""
    return """@article{biblatex2020,
  author = {Test, Author},
  title = {BibLaTeX Paper},
  journaltitle = {Test Journal},
  date = {2020},
  location = {New York}
}"""


@pytest.fixture
def comment_block():
    """BibTeX @comment block (domain metadata)."""
    return """@comment{
====================================================================
DOMAIN: Test Domain
SEARCH_DATE: 2024-01-01
PAPERS_FOUND: 5 total (High: 2, Medium: 2, Low: 1)
====================================================================
}"""


# =============================================================================
# Tests for check_utf8_encoding
# =============================================================================

class TestCheckUtf8Encoding:
    """Tests for UTF-8 encoding validation."""

    def test_valid_utf8(self, tmp_path, utf8_content):
        """Should pass for valid UTF-8 file."""
        bib_file = tmp_path / "valid.bib"
        bib_file.write_text(utf8_content, encoding='utf-8')

        errors = check_utf8_encoding(bib_file)
        assert errors == []

    def test_valid_ascii(self, tmp_path, valid_article):
        """Should pass for ASCII content (subset of UTF-8)."""
        bib_file = tmp_path / "ascii.bib"
        bib_file.write_text(valid_article, encoding='utf-8')

        errors = check_utf8_encoding(bib_file)
        assert errors == []

    def test_invalid_utf8(self, tmp_path):
        """Should fail for invalid UTF-8 encoding."""
        bib_file = tmp_path / "invalid.bib"
        # Write Latin-1 encoded content that's invalid UTF-8
        bib_file.write_bytes(b"@article{test,\n  author = {M\xfcller}\n}")

        errors = check_utf8_encoding(bib_file)
        assert len(errors) == 1
        assert "Invalid UTF-8" in errors[0]


# =============================================================================
# Tests for check_latex_escapes
# =============================================================================

class TestCheckLatexEscapes:
    """Tests for LaTeX diacritic escape detection."""

    def test_clean_content(self, tmp_path, utf8_content):
        """Should pass for content without LaTeX escapes."""
        bib_file = tmp_path / "clean.bib"
        bib_file.write_text(utf8_content, encoding='utf-8')

        errors = check_latex_escapes(bib_file, utf8_content)
        assert errors == []

    def test_umlaut_escape(self, tmp_path):
        """Should detect umlaut LaTeX escapes."""
        content = '@article{test,\n  author = {M\\"uller}\n}'
        bib_file = tmp_path / "umlaut.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_latex_escapes(bib_file, content)
        assert len(errors) >= 1
        assert any('ü' in e or 'replace' in e.lower() for e in errors)

    def test_acute_escape(self, tmp_path):
        """Should detect acute accent LaTeX escapes."""
        content = "@article{test,\n  author = {Garc\\'ia}\n}"
        bib_file = tmp_path / "acute.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_latex_escapes(bib_file, content)
        assert len(errors) >= 1
        assert any('í' in e or 'replace' in e.lower() for e in errors)

    def test_grave_escape(self, tmp_path):
        """Should detect grave accent LaTeX escapes."""
        # Use raw string with proper BibTeX format: {\`e} for è
        content = r"@article{test," + "\n" + r"  title = {caf{\`e}}" + "\n" + "}"
        bib_file = tmp_path / "grave.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_latex_escapes(bib_file, content)
        assert len(errors) >= 1
        assert any('è' in e or 'replace' in e.lower() for e in errors)

    def test_tilde_escape(self, tmp_path):
        """Should detect tilde LaTeX escapes."""
        content = "@article{test,\n  author = {Espa\\~na}\n}"
        bib_file = tmp_path / "tilde.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_latex_escapes(bib_file, content)
        assert len(errors) >= 1

    def test_eszett_escape(self, tmp_path):
        """Should detect eszett (\\ss) LaTeX escape."""
        content = "@article{test,\n  author = {Stra{\\ss}e}\n}"
        bib_file = tmp_path / "eszett.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_latex_escapes(bib_file, content)
        assert len(errors) >= 1
        assert any('ß' in e or 'replace' in e.lower() for e in errors)

    def test_braced_escape(self, tmp_path):
        """Should detect braced LaTeX escapes like {\\"a}."""
        content = '@article{test,\n  author = {{\\\"a}rger}\n}'
        bib_file = tmp_path / "braced.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_latex_escapes(bib_file, content)
        assert len(errors) >= 1


# =============================================================================
# Tests for check_duplicate_keys
# =============================================================================

class TestCheckDuplicateKeys:
    """Tests for duplicate citation key detection."""

    def test_no_duplicates(self, valid_article, valid_book):
        """Should pass when no duplicate keys."""
        content = valid_article + "\n\n" + valid_book
        errors = check_duplicate_keys(content)
        assert errors == []

    def test_single_duplicate(self, duplicate_keys_content):
        """Should detect single duplicate key."""
        errors = check_duplicate_keys(duplicate_keys_content)
        assert len(errors) == 1
        assert "same2020key" in errors[0]
        assert "duplicate" in errors[0].lower()

    def test_multiple_duplicates(self):
        """Should detect multiple different duplicate keys."""
        content = """@article{dup1, title = {A}}
@article{dup2, title = {B}}
@article{dup1, title = {C}}
@article{dup2, title = {D}}"""

        errors = check_duplicate_keys(content)
        assert len(errors) == 2
        assert any("dup1" in e for e in errors)
        assert any("dup2" in e for e in errors)

    def test_comment_ignored(self, comment_block, valid_article):
        """Should ignore @comment blocks (not treat as duplicate)."""
        content = comment_block + "\n\n" + valid_article
        errors = check_duplicate_keys(content)
        assert errors == []

    def test_case_sensitive(self):
        """Keys should be case-sensitive (Test2020 != test2020)."""
        content = """@article{Test2020, title = {A}}
@article{test2020, title = {B}}"""

        errors = check_duplicate_keys(content)
        assert errors == []  # Different keys


# =============================================================================
# Tests for check_duplicate_fields
# =============================================================================

class TestCheckDuplicateFields:
    """Tests for duplicate field name detection within entries."""

    def test_no_duplicates(self, valid_article):
        """Should pass when no duplicate fields."""
        errors = check_duplicate_fields(valid_article)
        assert errors == []

    def test_duplicate_note_arxiv_pattern(self):
        """Should detect the arXiv double-note anti-pattern."""
        content = """@misc{author2023paper,
  author = {Author, Test},
  title = {Test Paper},
  year = {2023},
  note = {arXiv:2304.01481},
  howpublished = {arXiv preprint},
  note = {CORE ARGUMENT: This paper argues something important.},
  keywords = {ai-ethics, preprint, Medium}
}"""
        errors = check_duplicate_fields(content)
        assert len(errors) == 1
        assert "note" in errors[0]
        assert "author2023paper" in errors[0]

    def test_multiple_entries_mixed(self):
        """Should detect duplicates in one entry but not another."""
        content = """@article{clean2020,
  author = {Clean, Author},
  title = {Clean Paper},
  journal = {Good Journal},
  year = {2020}
}

@misc{dirty2023,
  author = {Dirty, Author},
  title = {Dirty Paper},
  year = {2023},
  note = {arXiv:1234.5678},
  note = {This paper does stuff.}
}"""
        errors = check_duplicate_fields(content)
        assert len(errors) == 1
        assert "dirty2023" in errors[0]

    def test_comment_ignored(self):
        """Should ignore @comment blocks entirely."""
        content = """@comment{
  note = {some note},
  note = {another note}
}

@article{real2020,
  author = {Real, Author},
  title = {Real Paper},
  journal = {Journal},
  year = {2020}
}"""
        errors = check_duplicate_fields(content)
        assert errors == []

    def test_line_numbers_in_error(self):
        """Should include line numbers in error message."""
        content = """@misc{test2023,
  author = {Test, Author},
  title = {Test},
  year = {2023},
  note = {First note},
  note = {Second note}
}"""
        errors = check_duplicate_fields(content)
        assert len(errors) == 1
        assert "line 5" in errors[0]  # first note
        assert "line 6" in errors[0]  # duplicate note

    def test_validate_bib_integration(self, tmp_path):
        """check_duplicate_fields should be called from validate_bib()."""
        content = """@misc{test2023,
  author = {Test, Author},
  title = {Test},
  year = {2023},
  note = {First},
  note = {Second}
}"""
        bib_file = tmp_path / "dup_fields.bib"
        bib_file.write_text(content, encoding='utf-8')

        result = validate_bib(bib_file)
        assert result["valid"] is False
        assert any("duplicate field" in e.lower() for e in result["errors"])

    def test_multiline_value_no_false_positive(self):
        """Should NOT flag 'word = text' inside multi-line field values."""
        content = """@article{test2023,
  author = {Test, Author},
  title = {Test Paper},
  journal = {Test Journal},
  year = {2023},
  note = {This paper discusses how
  title = something they changed in the field.
  The utility = 0.5 result is interesting.}
}"""
        errors = check_duplicate_fields(content)
        assert errors == [], f"Got false positives: {errors}"

    def test_unindented_fields_detected(self):
        """Should detect duplicate fields even without indentation."""
        content = """@article{test2023,
author = {Test, Author},
title = {Test},
journal = {J},
year = {2023},
note = {First},
note = {Second}
}"""
        errors = check_duplicate_fields(content)
        assert len(errors) == 1
        assert "note" in errors[0]


# =============================================================================
# Tests for check_bibtex_syntax
# =============================================================================

class TestCheckBibtexSyntax:
    """Tests for BibTeX syntax validation."""

    def test_valid_syntax(self, tmp_path, valid_article):
        """Should pass for valid BibTeX syntax."""
        bib_file = tmp_path / "valid.bib"
        bib_file.write_text(valid_article, encoding='utf-8')

        errors = check_bibtex_syntax(bib_file)
        assert errors == []

    def test_missing_closing_brace(self, tmp_path, syntax_error_content):
        """Should detect missing closing brace."""
        bib_file = tmp_path / "syntax.bib"
        bib_file.write_text(syntax_error_content, encoding='utf-8')

        errors = check_bibtex_syntax(bib_file)
        assert len(errors) >= 1
        assert any("syntax" in e.lower() or "error" in e.lower() for e in errors)

    def test_unclosed_quote(self, tmp_path):
        """Should detect unclosed quote in field value."""
        content = '@article{test,\n  title = "Unclosed quote\n}'
        bib_file = tmp_path / "quote.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_bibtex_syntax(bib_file)
        assert len(errors) >= 1

    def test_empty_file(self, tmp_path):
        """Should handle empty file gracefully."""
        bib_file = tmp_path / "empty.bib"
        bib_file.write_text("", encoding='utf-8')

        errors = check_bibtex_syntax(bib_file)
        assert errors == []  # Empty file is technically valid


# =============================================================================
# Tests for check_required_fields
# =============================================================================

class TestCheckRequiredFields:
    """Tests for required field validation."""

    def test_complete_article(self, tmp_path, valid_article):
        """Should pass for complete @article."""
        bib_file = tmp_path / "article.bib"
        bib_file.write_text(valid_article, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert errors == []

    def test_complete_book_with_author(self, tmp_path, valid_book):
        """Should pass for @book with author."""
        bib_file = tmp_path / "book.bib"
        bib_file.write_text(valid_book, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert errors == []

    def test_complete_book_with_editor(self, tmp_path, valid_book_editor):
        """Should pass for @book with editor (no author)."""
        bib_file = tmp_path / "book_editor.bib"
        bib_file.write_text(valid_book_editor, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert errors == []

    def test_complete_inproceedings(self, tmp_path, valid_inproceedings):
        """Should pass for complete @inproceedings."""
        bib_file = tmp_path / "inproceedings.bib"
        bib_file.write_text(valid_inproceedings, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert errors == []

    def test_complete_incollection(self, tmp_path, valid_incollection):
        """Should pass for complete @incollection."""
        bib_file = tmp_path / "incollection.bib"
        bib_file.write_text(valid_incollection, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert errors == []

    def test_missing_journal(self, tmp_path, missing_fields_article):
        """Should detect missing journal field in @article."""
        bib_file = tmp_path / "missing.bib"
        bib_file.write_text(missing_fields_article, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert any("journal" in e.lower() for e in errors)

    def test_missing_year(self, tmp_path, missing_fields_article):
        """Should detect missing year field in @article."""
        bib_file = tmp_path / "missing.bib"
        bib_file.write_text(missing_fields_article, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert any("year" in e.lower() for e in errors)

    def test_book_missing_author_and_editor(self, tmp_path, missing_author_book):
        """Should detect @book missing both author and editor."""
        bib_file = tmp_path / "noauthor.bib"
        bib_file.write_text(missing_author_book, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert len(errors) >= 1
        assert any("author" in e.lower() or "editor" in e.lower() for e in errors)

    def test_unknown_entry_type_ignored(self, tmp_path):
        """Should ignore unknown entry types."""
        content = """@unknown{test2020,
  title = {Unknown Type}
}"""
        bib_file = tmp_path / "unknown.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_required_fields(bib_file)
        assert errors == []  # Unknown types have no required fields


# =============================================================================
# Tests for check_biblatex_fields
# =============================================================================

class TestCheckBiblatexFields:
    """Tests for BibLaTeX field detection."""

    def test_clean_bibtex(self, tmp_path, valid_article):
        """Should pass for standard BibTeX fields."""
        bib_file = tmp_path / "bibtex.bib"
        bib_file.write_text(valid_article, encoding='utf-8')

        errors = check_biblatex_fields(bib_file)
        assert errors == []

    def test_journaltitle_field(self, tmp_path):
        """Should detect 'journaltitle' (BibLaTeX) instead of 'journal'."""
        content = """@article{test2020,
  author = {Test, Author},
  title = {Test Paper},
  journaltitle = {Test Journal},
  year = {2020}
}"""
        bib_file = tmp_path / "journaltitle.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_biblatex_fields(bib_file)
        assert len(errors) >= 1
        assert any("journaltitle" in e.lower() and "journal" in e.lower() for e in errors)

    def test_date_field(self, tmp_path):
        """Should detect 'date' (BibLaTeX) instead of 'year'."""
        content = """@article{test2020,
  author = {Test, Author},
  title = {Test Paper},
  journal = {Test Journal},
  date = {2020-01-15}
}"""
        bib_file = tmp_path / "date.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_biblatex_fields(bib_file)
        assert len(errors) >= 1
        assert any("date" in e.lower() and "year" in e.lower() for e in errors)

    def test_location_field(self, tmp_path):
        """Should detect 'location' (BibLaTeX) instead of 'address'."""
        content = """@book{test2020,
  author = {Test, Author},
  title = {Test Book},
  publisher = {Test Publisher},
  year = {2020},
  location = {New York}
}"""
        bib_file = tmp_path / "location.bib"
        bib_file.write_text(content, encoding='utf-8')

        errors = check_biblatex_fields(bib_file)
        assert len(errors) >= 1
        assert any("location" in e.lower() and "address" in e.lower() for e in errors)


# =============================================================================
# Tests for validate_bib (full validation pipeline)
# =============================================================================

class TestValidateBib:
    """Tests for the full validation pipeline."""

    def test_valid_file(self, tmp_path, valid_article):
        """Should return valid=True for correct file."""
        bib_file = tmp_path / "valid.bib"
        bib_file.write_text(valid_article, encoding='utf-8')

        result = validate_bib(bib_file)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_file_not_found(self, tmp_path):
        """Should return valid=False for nonexistent file."""
        nonexistent = tmp_path / "nonexistent.bib"

        result = validate_bib(nonexistent)
        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "not found" in result["errors"][0].lower()

    def test_multiple_errors(self, tmp_path):
        """Should collect errors from multiple checks."""
        # Content with duplicate keys and BibLaTeX field
        content = """@article{dup2020,
  author = {Test, Author},
  title = {First Paper},
  journaltitle = {Test Journal},
  year = {2020}
}

@article{dup2020,
  author = {Other, Author},
  title = {Second Paper},
  journal = {Another Journal},
  year = {2021}
}"""
        bib_file = tmp_path / "multiple.bib"
        bib_file.write_text(content, encoding='utf-8')

        result = validate_bib(bib_file)
        assert result["valid"] is False
        assert len(result["errors"]) >= 2  # At least duplicate + biblatex

    def test_utf8_error_stops_early(self, tmp_path):
        """Should stop early if UTF-8 validation fails."""
        bib_file = tmp_path / "invalid_encoding.bib"
        # Write invalid UTF-8 bytes
        bib_file.write_bytes(b"@article{test,\n  author = {M\xfcller}\n}")

        result = validate_bib(bib_file)
        assert result["valid"] is False
        assert len(result["errors"]) == 1  # Only UTF-8 error, stops early

    def test_syntax_error_skips_field_checks(self, tmp_path, syntax_error_content):
        """Should skip field checks if syntax is invalid."""
        bib_file = tmp_path / "syntax.bib"
        bib_file.write_text(syntax_error_content, encoding='utf-8')

        result = validate_bib(bib_file)
        assert result["valid"] is False
        # Should have syntax error but not required field errors
        assert any("syntax" in e.lower() for e in result["errors"])


# =============================================================================
# Tests for CLI (main function)
# =============================================================================

class TestCLI:
    """Tests for command-line interface."""

    def test_missing_args(self):
        """Should exit with code 2 when no path argument."""
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "bib_validator.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Usage:" in result.stdout

    def test_valid_file_exit_0(self, tmp_path, valid_article):
        """Should exit with code 0 for valid file."""
        bib_file = tmp_path / "valid.bib"
        bib_file.write_text(valid_article, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "bib_validator.py"), str(bib_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert '"valid": true' in result.stdout

    def test_invalid_file_exit_1(self, tmp_path, syntax_error_content):
        """Should exit with code 1 for invalid file."""
        bib_file = tmp_path / "invalid.bib"
        bib_file.write_text(syntax_error_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "bib_validator.py"), str(bib_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert '"valid": false' in result.stdout

    def test_nonexistent_file_exit_1(self, tmp_path):
        """Should exit with code 1 for nonexistent file."""
        nonexistent = tmp_path / "nonexistent.bib"

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "bib_validator.py"), str(nonexistent)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stdout.lower()

    def test_json_output(self, tmp_path, valid_article):
        """Should output valid JSON."""
        import json

        bib_file = tmp_path / "valid.bib"
        bib_file.write_text(valid_article, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "bib_validator.py"), str(bib_file)],
            capture_output=True,
            text=True,
        )

        # Should parse as valid JSON
        output = json.loads(result.stdout)
        assert "valid" in output
        assert "errors" in output
