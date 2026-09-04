"""bib_fields.py -- the depth-counting scanner behind every shared read of a field in raw BibTeX text.

The regex it replaced tolerated exactly ONE level of brace nesting inside a
value, so the standard LaTeX accent form (`Mendon{\\c{c}}a`) made the field
vanish from the parse: absent, not mangled, not flagged. Census over 8,894
delivered entries: 39 fields dropped -- 22 authors and 11 titles (33 entries,
all with accented names, that lost their same-work key), 2 journals, and 4
bare values (`year = 2016,`, valid BibTeX, a second silent-drop class the
roadmap item did not name)
(docs/known-issues/field-parse-divergence-measurement-2026-09-02/).
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import bib_fields  # noqa: E402
from bib_fields import iter_fields, parse_entry_fields  # noqa: E402


ACCENTED = r"""@article{mendonca2022more,
  author = {Mendon{\c{c}}a, Ricardo F. and Ercan, Selen and Asenbaum, Hans},
  title = {More than Words: A Multidimensional Approach to Deliberative Democracy},
  journal = {Political Studies},
  year = {2022}
}"""


class TestNestedBraces:
    def test_two_level_nested_author_is_parsed(self):
        fields = parse_entry_fields(ACCENTED)
        assert fields["author"] == (
            r"Mendon{\c{c}}a, Ricardo F. and Ercan, Selen and Asenbaum, Hans")

    def test_two_level_nested_title_is_parsed(self):
        entry = (r"@article{k," "\n"
                 r"  title = {A Reply to {D{\'i}az Le{\'o}n}, {Saul}, and {Sider}}," "\n"
                 r"  year = {2018}" "\n}")
        assert parse_entry_fields(entry)["title"] == (
            r"A Reply to {D{\'i}az Le{\'o}n}, {Saul}, and {Sider}")

    def test_one_level_nested_still_parses(self):
        entry = "@article{k,\n  title = {On the {K}alon},\n  year = {2020}\n}"
        assert parse_entry_fields(entry)["title"] == "On the {K}alon"

    def test_three_level_nesting_is_not_a_new_wall(self):
        entry = r"@book{k, title = {\textit{{T}he {P}rivatized {S}tate {\'{e}}}} }"
        assert parse_entry_fields(entry)["title"] == (
            r"\textit{{T}he {P}rivatized {S}tate {\'{e}}}")

    def test_neighbouring_fields_survive_a_nested_one(self):
        fields = parse_entry_fields(ACCENTED)
        assert fields["journal"] == "Political Studies"
        assert fields["year"] == "2022"


class TestValueForms:
    def test_bare_number_value_is_parsed(self):
        entry = "@article{k,\n  year = 2016,\n  title = {T}\n}"
        assert parse_entry_fields(entry)["year"] == "2016"

    def test_bare_macro_value_is_kept_as_its_name(self):
        # No macro expansion: the parser has no @string table, and every
        # caller wants the raw text of the entry, not a rendered value.
        entry = "@article{k,\n  month = jan,\n  year = {2016}\n}"
        assert parse_entry_fields(entry)["month"] == "jan"

    def test_quoted_value_is_parsed(self):
        # pybtex's Writer emits quoted values on round-trip.
        entry = '@article{k,\n  title = "The Title",\n  year = "2016"\n}'
        fields = parse_entry_fields(entry)
        assert fields["title"] == "The Title"
        assert fields["year"] == "2016"

    def test_quoted_value_with_inner_braces_and_quote(self):
        # In BibTeX a brace group inside a quoted value protects a `"`.
        entry = '@article{k,\n  journal = "The {"Q"} Review",\n  year = {2016}\n}'
        fields = parse_entry_fields(entry)
        assert fields["journal"] == 'The {"Q"} Review'
        assert fields["year"] == "2016"

    def test_hash_concatenation_joins_pieces(self):
        entry = '@article{k,\n  title = "A" # " B" # {C},\n  year = {2016}\n}'
        fields = parse_entry_fields(entry)
        assert fields["title"] == "A BC"
        assert fields["year"] == "2016"

    def test_names_are_lowercased_and_values_stripped(self):
        entry = "@article{k,\n  Title = {  Spaced  },\n  YEAR = { 2016 }\n}"
        fields = parse_entry_fields(entry)
        assert fields == {"title": "Spaced", "year": "2016"}

    def test_last_duplicate_wins(self):
        # Pins the dict-overwrite behaviour the regex parser had; pybtex
        # rejects such an entry outright, and the write hook stops it landing,
        # so this only ever governs a read of text that never shipped.
        entry = "@article{k,\n  year = {2015},\n  year = {2016}\n}"
        assert parse_entry_fields(entry)["year"] == "2016"


class TestStructure:
    def test_field_shaped_text_inside_a_value_is_not_a_field(self):
        # The regex found `name = {value}` ANYWHERE, including inside an
        # abstract; the scanner only recognises a field at field position.
        entry = ("@article{k,\n"
                 "  abstract = {We set year = {1999} as the baseline.},\n"
                 "  year = {2020}\n}")
        fields = parse_entry_fields(entry)
        assert fields["year"] == "2020"
        assert fields["abstract"] == "We set year = {1999} as the baseline."

    def test_prose_outside_entries_is_not_read(self):
        # BibTeX treats text outside `@...` commands as commentary and pybtex
        # ignores it; a scanner that read it would let `year = {1999}` in a
        # trailing note override the real year by last-wins.
        text = "@article{k,\n  year = {2020}\n}\n\nReminder: year = {1999}\n"
        assert parse_entry_fields(text) == {"year": "2020"}

    def test_text_without_any_entry_yields_nothing(self):
        assert parse_entry_fields("year = {2020}") == {}

    def test_comment_block_is_skipped(self):
        text = ("@comment{ year = {1999} }\n"
                "@article{k,\n  year = {2020}\n}")
        assert parse_entry_fields(text)["year"] == "2020"

    def test_whole_file_with_two_entries_yields_both_entries_fields(self):
        # Callers occasionally hand over a whole (single-entry) file rather
        # than a chunk; the scanner reads past an entry's closing brace.
        text = ("@article{a,\n  title = {First}\n}\n\n"
                "@book{b,\n  publisher = {Second}\n}\n")
        fields = parse_entry_fields(text)
        assert fields["title"] == "First"
        assert fields["publisher"] == "Second"

    def test_header_with_space_after_brace_is_stepped_over(self):
        # enrich_bibliography's header regex accepted `@article{ key,`; the
        # scanner must not treat such an entry as an opaque block to skip.
        entry = "@article{ key,\n  year = {2020}\n}"
        assert parse_entry_fields(entry)["year"] == "2020"

    def test_parenthesis_header_form_is_stepped_over(self):
        # BibTeX's alternative delimiter, which pybtex accepts.
        entry = "@article(key,\n  year = {2020}\n)"
        assert parse_entry_fields(entry)["year"] == "2020"

    def test_token_without_equals_is_skipped(self):
        entry = "@article{k,\n  stray\n  year = {2020}\n}"
        assert parse_entry_fields(entry)["year"] == "2020"

    def test_unbounded_value_keeps_earlier_fields_and_never_raises(self):
        # Fail lenient, never loud: an unbalanced value ends the scan, and
        # the fields already read are returned. pybtex is the strict gate
        # (bib_validator / _derived_field_took), not this reader.
        entry = "@article{k,\n  year = {2020},\n  title = {Unbalanced {brace\n}"
        fields = parse_entry_fields(entry)
        assert fields["year"] == "2020"
        assert "title" not in fields

    def test_dangling_hash_ends_the_value_and_keeps_scanning(self):
        # `year = {2020} #,` is malformed (pybtex rejects it too), but the
        # piece already read is a complete value: keep it, drop the stray
        # `#`, and go on to the next field rather than abandon the entry.
        entry = "@article{k,\n  year = {2020} #,\n  title = {T}\n}"
        fields = parse_entry_fields(entry)
        assert fields["year"] == "2020"
        assert fields["title"] == "T"

    def test_empty_assignment_is_skipped_and_later_fields_kept(self):
        # `note = ,` has no value at all. The old regex dropped only `note`;
        # a scanner that stopped here would lose author and year -- the very
        # failure this module exists to remove, for a different input.
        entry = (r"@article{k," "\n  note = ,\n"
                 r"  author = {Garc{\'{i}}a, I.}," "\n  year = {2020}\n}")
        fields = parse_entry_fields(entry)
        assert "note" not in fields
        assert fields["author"] == r"Garc{\'{i}}a, I."
        assert fields["year"] == "2020"

    def test_unmatched_close_brace_inside_quotes_does_not_swallow_the_entry(self):
        entry = '@article{k,\n  title = "see } below",\n  year = {2020}\n}'
        fields = parse_entry_fields(entry)
        assert fields["title"] == "see } below"
        assert fields["year"] == "2020"

    def test_unbalanced_braces_inside_quotes_fall_back_to_the_next_quote(self):
        # `"a } b { c"` never balances, so brace-aware closing fails; rather
        # than end the scan (losing year), close at the next `"` as the old
        # reader did. pybtex rejects the input anyway.
        entry = '@article{k,\n  title = "a } b { c",\n  year = {2020}\n}'
        fields = parse_entry_fields(entry)
        assert fields["title"] == "a } b { c"
        assert fields["year"] == "2020"

    def test_unclosed_paren_block_is_scanned_rather_than_swallowing_the_file(self):
        text = "@string(x = {y}\n@article{k,\n  year = {2020}\n}"
        assert parse_entry_fields(text)["year"] == "2020"

    def test_comment_block_with_a_comma_is_still_skipped(self):
        # `@comment{TODO, ...}` looks like an entry header to a type-blind
        # regex; its contents must not leak in as fields (last-wins would
        # let a trailing comment override the real year).
        text = ("@article{k,\n  year = {2020}\n}\n"
                "@comment{TODO, fix year = {1999}}\n")
        assert parse_entry_fields(text)["year"] == "2020"

    def test_string_and_preamble_blocks_are_skipped(self):
        text = ('@string{jphil = "J. Phil."}\n@preamble{"\\newcommand{\\x}{y}"}\n'
                "@article{k,\n  journal = jphil,\n  year = {2020}\n}")
        fields = parse_entry_fields(text)
        assert fields == {"journal": "jphil", "year": "2020"}

    def test_crlf_line_endings(self):
        entry = "@article{k,\r\n  year = {2020},\r\n  title = {T}\r\n}\r\n"
        assert parse_entry_fields(entry) == {"year": "2020", "title": "T"}

    def test_hash_inside_a_bare_value_is_concatenation(self):
        # Pinned, not endorsed: a bare value is a macro identifier, and `#`
        # is BibTeX's concatenation operator, so a bare URL with a fragment
        # reads as two macros joined. The engine never writes a bare value;
        # one only arrives agent- or hand-written, and unless the agent also
        # defined the macros pybtex rejects it (UndefinedMacro) at the
        # barrier's own validation.
        entry = "@misc{k,\n  url = https://ex.org/a#frag,\n  year = {2020}\n}"
        assert parse_entry_fields(entry)["url"] == "https://ex.org/afrag"

    def test_hyphenated_field_name_is_read_whole(self):
        # `\w+` matched `title` inside `short-title`, filing the value under
        # the wrong key; BibTeX identifiers may contain `-`.
        entry = "@article{k,\n  short-title = {S},\n  title = {T}\n}"
        fields = parse_entry_fields(entry)
        assert fields["short-title"] == "S"
        assert fields["title"] == "T"

    def test_parenthesised_string_block_is_skipped(self):
        text = '@string(jphil = "J. (Phil.)")\n@article{k,\n  year = {2020}\n}'
        assert parse_entry_fields(text) == {"year": "2020"}

    def test_bare_value_at_end_of_text(self):
        assert parse_entry_fields("@article{k,\n  year = 2016")["year"] == "2016"

    def test_unclosed_later_piece_ends_the_scan_too(self):
        # `{A} # {oops,` -- the second piece opens and never closes (the
        # text ends before any brace balances it). Nothing after it is
        # trustworthy: the `year` inside the abandoned piece is not a field
        # and must not be read as one, any more than for an unclosed FIRST
        # piece.
        entry = "@article{k,\n  note = {N},\n  title = {A} # {oops,\n  year = {2020},"
        fields = parse_entry_fields(entry)
        assert fields == {"note": "N"}

    def test_empty_text_gives_empty_dict(self):
        assert parse_entry_fields("") == {}


class TestSpans:
    def test_span_covers_the_raw_delimited_value(self):
        f = [f for f in iter_fields(ACCENTED) if f.name == "author"][0]
        assert ACCENTED[f.value_start:f.value_end] == (
            r"{Mendon{\c{c}}a, Ricardo F. and Ercan, Selen and Asenbaum, Hans}")
        assert ACCENTED[f.name_start:f.name_start + len("author")] == "author"

    def test_span_of_a_concatenated_value_runs_to_the_last_piece(self):
        entry = '@article{k,\n  title = "A" # {B},\n  year = 2016\n}'
        fields = {f.name: f for f in iter_fields(entry)}
        assert entry[fields["title"].value_start:fields["title"].value_end] == '"A" # {B}'
        assert entry[fields["year"].value_start:fields["year"].value_end] == "2016"

    def test_quoted_value_span_covers_the_quotes(self):
        # stamp_entry_text splices on this span; a boundary off by one here
        # leaves a stray quote in a delivered bib.
        entry = '@article{k,\n  keywords = "tag, High",\n  year = "2020"\n}'
        f = next(iter_fields(entry))
        assert entry[f.value_start:f.value_end] == '"tag, High"'
        assert f.value == "tag, High"

    def test_field_value_is_unstripped_on_the_span_object(self):
        entry = "@article{k,\n  title = { Spaced },\n}"
        f = next(iter_fields(entry))
        assert f.value == " Spaced "
        assert f.name == "title"


class TestScan:
    """scan() tells a caller where the text stopped being trustworthy and
    which assignments it had to skip -- what a remover needs to distinguish
    "absent" from "present but unreadable"."""

    def test_stop_is_none_when_everything_was_read(self):
        from bib_fields import scan
        fields, stop, unreadable = scan("@article{k,\n  year = {2020}\n}")
        assert [f.name for f in fields] == ["year"]
        assert stop is None and unreadable == []

    def test_stop_is_the_name_index_of_the_unclosed_field(self):
        from bib_fields import scan
        text = "@article{k,\n  year = {2020},\n  note = {open\n  title = {T}\n"
        fields, stop, _ = scan(text)
        assert [f.name for f in fields] == ["year"]
        assert text[stop:stop + 4] == "note"

    def test_an_unclosed_skipped_block_also_sets_stop(self):
        # `@comment{` that never closes: the scan returned early, and a
        # caller must not read "stop is None" as "read to the end".
        from bib_fields import scan
        text = "@comment{open\n@article{k,\n  year = {2020}\n}"
        fields, stop, _ = scan(text)
        assert fields == [] and stop == 0

    def test_an_unclosed_paren_block_marks_trust_but_scanning_continues(self):
        # `@comment(open` never closes: fields after it are still read (a
        # lenient reader), but `stop` says trust ended at the `@`, so a
        # caller that must not guess can refuse everything past it.
        from bib_fields import scan
        text = "@comment(open\n@article{k,\n  year = {2020}\n}"
        fields, stop, _ = scan(text)
        assert [f.name for f in fields] == ["year"]
        assert stop == 0

    def test_unreadable_assignments_are_reported_by_name_and_index(self):
        from bib_fields import scan
        text = "@article{k,\n  note = ,\n  year = {2020}\n}"
        fields, stop, unreadable = scan(text)
        assert [f.name for f in fields] == ["year"] and stop is None
        assert [(n, text[i:i + 4]) for n, i in unreadable] == [("note", "note")]


class TestRemoveField:
    """The edit primitive editors share: cut a field out of the text with its
    own line and its trailing comma, and nothing else."""

    def test_removes_the_line_and_trailing_comma(self):
        from bib_fields import remove_field
        entry = "@article{k,\n  keywords = {on {K}alon},\n  title = {T}\n}"
        f = next(x for x in iter_fields(entry) if x.name == "keywords")
        assert remove_field(entry, f) == "@article{k,\n  title = {T}\n}"

    def test_last_field_without_comma_leaves_a_parseable_entry(self):
        from bib_fields import remove_field
        from pybtex.database import parse_string
        entry = "@article{k,\n  title = {T},\n  keywords = {on {K}alon}\n}"
        f = next(x for x in iter_fields(entry) if x.name == "keywords")
        out = remove_field(entry, f)
        assert "keywords" not in out and "title = {T}" in out
        parse_string(out, "bibtex")

    def test_field_sharing_a_line_loses_only_itself(self):
        from bib_fields import remove_field
        entry = "@article{k, keywords = {x}, title = {T}}"
        f = next(x for x in iter_fields(entry) if x.name == "keywords")
        assert remove_field(entry, f) == "@article{k, title = {T}}"

    def test_comma_on_the_next_line_goes_with_the_field(self):
        from bib_fields import remove_field
        from pybtex.database import parse_string
        entry = "@article{k,\n  title = {T},\n  keywords = {x}\n  ,\n  year = {2020}\n}"
        f = next(x for x in iter_fields(entry) if x.name == "keywords")
        out = remove_field(entry, f)
        assert out == "@article{k,\n  title = {T},\n  year = {2020}\n}"
        parse_string(out, "bibtex")

    def test_crlf_line_is_removed_whole(self):
        from bib_fields import remove_field
        entry = "@article{k,\r\n  keywords = {x},\r\n  title = {T}\r\n}"
        f = next(x for x in iter_fields(entry) if x.name == "keywords")
        assert remove_field(entry, f) == "@article{k,\r\n  title = {T}\r\n}"


def test_module_has_no_one_level_brace_regex():
    """The wall this module exists to remove must not creep back in as a
    'good enough' shortcut; depth counting, not a character class."""
    src = Path(bib_fields.__file__).read_text(encoding="utf-8")
    assert r"[^{}]*\}" not in src


class TestPercentIsNotAComment:
    """The docstring's `%` clause, as a contract. The scanner has no comment
    handling; what that costs splits by POSITION. Pinned because two
    independent external reviewers of the service's mirror both filed the
    same finding from this module's earlier silence -- a `%` carrying an
    entry's closing brace truncating the scan."""

    def _pybtex_fields(self, text):
        """What the STRICT gate makes of the same text, or None if it refuses."""
        import io

        from pybtex.database.input.bibtex import Parser
        try:
            db = Parser().parse_stream(io.StringIO(text))
        except Exception:
            return None
        return {k: dict(e.fields) for k, e in db.entries.items()}

    def test_percent_inside_a_value_is_an_ordinary_character(self):
        for text in ('@article{k, title = {A % B}, year = {2020}}',
                     '@article{k, title = "A % B", year = {2020}}'):
            assert parse_entry_fields(text)["title"] == "A % B"
            # And the strict gate reads it the same way, so the scan is right.
            assert self._pybtex_fields(text)["k"]["title"] == "A % B"

    def test_percent_at_field_position_is_refused_by_the_strict_gate(self):
        # Every form where a comment-aware reader would differ from this one.
        for text in ('@article{k, title = {A}, % note\n year = {2020}}',
                     '@article{k, title = {A}, year = {2020} % }\n',
                     '@article{k, % title = {A}\n year = {2020}}'):
            assert self._pybtex_fields(text) is None, (
                f"pybtex now accepts {text!r}: the docstring's claim that the "
                "scanner's comment-blindness is unreachable no longer holds")

    def test_the_scanner_still_reads_such_text_leniently(self):
        # Not a promise about the values -- only that it fails lenient, never
        # loud, because nothing downstream sees a chunk pybtex refused.
        fields = parse_entry_fields('@article{k, title = {A}, year = {2020} % }\n')
        assert fields == {"title": "A", "year": "2020"}
