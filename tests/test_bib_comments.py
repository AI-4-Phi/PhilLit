"""Tests for hooks/bib_comments.py - the @comment block grammar.

Two facts about pybtex drive this module (measured 2026-09-10):
- a `@comment` body runs to the NEXT `@`, whatever the braces say, so a
  braced `@word{...}` inside a comment block is parsed as a second entry
  and the rest of the block is silently dropped;
- an entry TYPE that merely begins with "comment" (`@commentary{k1, ...}`)
  is an ordinary entry, which a `startswith("@comment")` test mistook for a
  comment block.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from bib_comments import (  # noqa: E402
    comment_body_intrusions,
    comment_defects,
    is_verbatim_block,
    stray_text,
)


class TestIsVerbatimBlock:
    def test_brace_and_paren_openers_in_any_case_with_leading_whitespace(self):
        assert is_verbatim_block("@comment{\nDOMAIN: 1\n}")
        assert is_verbatim_block("@COMMENT {overview}")
        assert is_verbatim_block("@comment(overview)")
        assert is_verbatim_block("\n  @Comment{x}")

    def test_an_entry_type_that_starts_with_comment_is_not_a_comment(self):
        assert not is_verbatim_block("@commentary{k1, title={x}, year={2000}}")
        assert not is_verbatim_block("@commentary{k1}")
        assert not is_verbatim_block("@article{k1, title={x}}")
        assert not is_verbatim_block("DOMAIN: text with @comment{ later}")


class TestCommentBodyIntrusions:
    def test_clean_block_reports_nothing(self):
        text = ("@comment{\n====\nDOMAIN: 1 - Test\nDOMAIN_OVERVIEW: fine\n====\n}\n\n"
                "@article{k1,\n  title = {x},\n  year = {2000}\n}\n")
        assert comment_body_intrusions(text) == []

    def test_line_start_entry_inside_a_block_is_stray_text_attributed_to_it(self):
        # A column-0 `@misc` is its own chunk to every tool here and an entry
        # to pybtex, so it is not an intrusion; what pybtex drops is the tail
        # after it, reported as stray text that names the `@` which ended
        # the block.
        text = ("@comment{\nDOMAIN_OVERVIEW: blah\n"
                "@misc{k2, title={y}, year={2001}}\n"
                "NOTABLE_GAPS: this tail is what pybtex drops\n}\n\n"
                "@article{k1,\n  title = {x},\n  year = {2000}\n}\n")
        assert comment_body_intrusions(text) == []
        [stray] = stray_text(text)
        assert (stray.line, stray.snippet) == (4, "NOTABLE_GAPS: this tail is what pybtex drops")
        [msg] = comment_defects(text)
        assert "line 4" in msg and "NOTABLE_GAPS" in msg
        assert "`@misc` on line 3" in msg and "opened on line 1" in msg

    def test_mid_line_braced_word_inside_a_closed_block(self):
        text = "@comment{overview @x{k1} tail}\n@article{k1,\n  title = {x}\n}\n"
        [hit] = comment_body_intrusions(text)
        assert (hit.open_line, hit.line, hit.word) == (1, 1, "x")

    def test_bare_at_is_reported_with_the_following_word(self):
        # pybtex refuses this shape outright; the error still names the cause.
        text = "@comment{ see @smith2020 for more }\n@article{k1,\n  title = {x}\n}\n"
        [hit] = comment_body_intrusions(text)
        assert hit.word == "smith2020"

    def test_unclosed_block_is_not_judged(self):
        # An extra `{` in the overview means the block never balances; pybtex
        # ends it at the next `@` and the cleaner carries it as is (pinned by
        # TestRewriteFidelity). Whether the following `@article` is "inside"
        # is undecidable from the text, so nothing is reported.
        text = ("@comment{\nDOMAIN_OVERVIEW: an overview with an unbalanced { brace\n}\n\n"
                "@article{k1,\n  title = {x}\n}\n")
        assert comment_body_intrusions(text) == []

    def test_a_commentary_entry_is_not_an_opener(self):
        text = "@commentary{k1, title={x}}\n@misc{k2, title={y}}\n"
        assert comment_body_intrusions(text) == []

    def test_only_line_start_openers_count(self):
        # A field VALUE mentioning @comment{ mid-line is not a block.
        text = "@article{k1,\n  note = {see @comment{ } and @misc{k2}},\n  title = {x}\n}\n"
        assert comment_body_intrusions(text) == []

    def test_second_block_reports_its_own_lines(self):
        text = ("@comment{first, clean}\n"
                "@article{k1,\n  title = {x}\n}\n"
                "@comment{\nsecond\n@misc{k2}\n}\n")
        assert comment_body_intrusions(text) == []
        [msg] = comment_defects(text)
        assert "line 8" in msg and "`@misc` on line 7" in msg and "opened on line 5" in msg


E = "@article{k1,\n  title = {x},\n  year = {2000}\n}\n"


class TestReviewRoundTwo:
    """Shapes two external reviews raised against the first cut."""

    def test_paren_form_block_is_handled_like_the_brace_form(self):
        text = "@comment(\noverview\n@misc{k2, title={y}, year={2001}}\ntail\n)\n" + E
        assert comment_body_intrusions(text) == []
        [msg] = comment_defects(text)
        assert "'tail'" in msg and "`@misc` on line 3" in msg and "opened on line 1" in msg

    def test_indented_line_start_opener_is_not_a_block(self):
        # The chunker splits only at a column-0 `@`; an indented `@comment{`
        # is a field-value continuation line, not a block, so an `@` after
        # it is not an intrusion. The two halves of the grammar must agree.
        text = ("@article{k1,\n  note = {long value continued\n"
                "  @comment{see @x} more},\n  title = {x}\n}\n")
        assert comment_body_intrusions(text) == []

    def test_unclosed_block_intruder_is_caught_as_stray_text(self):
        # An extra `{` keeps the block from ever closing; pybtex still ends
        # it at `@misc`, parses k2, and drops "lost tail" - and the rewrite
        # would make that permanent. Whether `@misc` was "inside" is
        # undecidable from the text, so the intrusion scan stays silent; the
        # text pybtex drops is what gets reported.
        text = ("@comment{\noverview with unmatched {\n"
                "@misc{k2, title={y}, year={2001}}\nlost tail\n}\n")
        assert comment_body_intrusions(text) == []
        [stray] = stray_text(text)
        assert (stray.line, stray.snippet) == (4, "lost tail")
        [msg] = comment_defects(text)
        assert "line 4" in msg and "lost tail" in msg

    def test_unclosed_block_followed_by_entries_is_clean_but_a_divider_is_stray(self):
        text = "@comment{\noverview {oops\n}\n" + E + E.replace("k1", "k2")
        assert comment_defects(text) == []
        with_divider = "@comment{\noverview {oops\n}\n" + E + "%% divider\n" + E.replace("k1", "k2")
        assert comment_body_intrusions(with_divider) == []
        [stray] = stray_text(with_divider)
        assert (stray.line, stray.snippet) == (8, "%% divider")

    def test_column_zero_nested_comment_is_its_own_chunk(self):
        # pybtex ends the outer block at the inner `@comment` and reads a
        # second comment; both chunks are carried whole, nothing is lost, so
        # only the mid-line `@x` inside the second chunk is an intrusion.
        text = "@comment{ a\n@comment{ b @x{k} }\n c }\n" + E
        hits = comment_body_intrusions(text)
        assert [(h.open_line, h.line, h.word) for h in hits] == [(2, 2, "x")]

    def test_early_closing_brace_hides_nothing(self):
        # Braces mean nothing to pybtex's comment: the block runs to the next
        # `@`, so a `}` in the overview cannot put a later `@misc` outside it.
        [hit] = comment_body_intrusions("@comment{overview } and @misc{fake, title={x}} more }\n" + E)
        assert (hit.line, hit.word) == (1, "misc")

    def test_a_double_at_reports_two_intrusions(self):
        hits = comment_body_intrusions("@comment{ a @@foo }\n" + E)
        assert [h.word for h in hits] == ["", "foo"]

    def test_verbatim_blocks_are_the_three_commands_pybtex_drops(self):
        assert is_verbatim_block("@comment{x}")
        assert is_verbatim_block('@string{jp = "J Phil"}')
        assert is_verbatim_block("@PREAMBLE{\\newcommand{\\x}{y}}")
        assert not is_verbatim_block("@stringent{k1, title={x}}")
        assert not is_verbatim_block("@article{k1, title={x}}")

    def test_indented_commands_after_an_entry_are_misplaced_commands(self):
        # pybtex reads them (a comment; an entry); no splitter here does, so
        # dedupe and evidence stamping fold them into the entry before them
        # and a rewrite drops the comment. The message names the real reason
        # - the command's position - not a loss the rewrite may not cause.
        text = E + "  @comment{ indented }\n" + E.replace("k1", "k2") + "\t@COMMENT (also)\n"
        assert [(s.line, s.snippet) for s in stray_text(text)] == [
            (5, "@comment{ indented }"), (10, "@COMMENT (also)")]
        assert stray_text("@comment{ ok }\n" + E) == []
        [msg] = comment_defects(E + "  @commentary{k3, title={t}}\n")
        assert "line 5" in msg and "start at the beginning of its line" in msg
        assert "drops" not in msg


class TestStrayText:
    """The accounting rule: every non-whitespace character of a bib must sit
    inside a verbatim block or inside an entry, because the metadata rewrite
    keeps nothing else - and downstream agents read the file as TEXT, so a
    `%`-line or a stray brace is content to them whatever pybtex thinks."""

    def test_indented_opener_inside_a_field_value_is_not_stray(self):
        # A continuation line of a braced value that happens to start with
        # `@comment{`: pybtex keeps it as field text and the Writer renders
        # it, so refusing would block cleaning of a valid file.
        text = ("@article{k1,\n  note = {long value continued\n"
                "  @comment{this is field text}\n  more},\n  title = {x}\n}\n")
        assert comment_defects(text) == []

    def test_text_before_the_first_command_is_stray(self):
        [stray] = stray_text("Notes to self\n" + E)
        assert (stray.line, stray.snippet) == (1, "Notes to self")

    def test_doubled_closer_after_an_entry_is_stray(self):
        text = E + "}\n" + E.replace("k1", "k2")
        [stray] = stray_text(text)
        assert (stray.line, stray.snippet) == (5, "}")

    def test_early_closed_block_tail_in_the_next_chunk_is_stray(self):
        # The overview's own `}` closes the block early for the scan; pybtex
        # ends the block at `@misc` and skips NOTABLE_GAPS; the chunker puts
        # NOTABLE_GAPS in the @misc chunk, which the rewrite does not carry.
        text = ("@comment{\noverview with an early } brace\n"
                "@misc{k2, title={y}}\nNOTABLE_GAPS: lost\n}\n" + E)
        assert comment_body_intrusions(text) == []
        [stray] = stray_text(text)
        assert (stray.line, stray.snippet) == (4, "NOTABLE_GAPS: lost")

    def test_verbatim_chunk_contents_are_never_stray(self):
        # Whatever follows a block on its own chunk is carried with it.
        assert stray_text("@comment{ a } junk after the block\n" + E) == []
        assert stray_text('@string{jp = "J Phil"} trailing\n' + E) == []
        assert stray_text("@comment{\nan overview with an unbalanced { brace\n}\n\n" + E) == []

    def test_one_report_per_chunk_tail_at_its_first_line(self):
        text = E + "\n}\nmore\nlines\n" + E.replace("k1", "k2")
        [stray] = stray_text(text)
        assert (stray.line, stray.snippet) == (6, "}")

    def test_paren_entry_span_is_honoured(self):
        text = "@article(k1,\n  title = {x}\n)\n" + E
        assert stray_text(text) == []

    def test_defect_message_names_the_line_and_the_text(self):
        [msg] = comment_defects(E + "%% ---- divider ----\n" + E.replace("k1", "k2"))
        assert "line 5" in msg and "%% ---- divider ----" in msg
        assert "outside" in msg


class TestReviewRoundFour:
    """Final-design review: lexical context for paren-delimited commands, a
    BOM, late-balance reporting, and same-line ordering."""

    def test_paren_entry_with_a_literal_paren_inside_a_value_is_not_stray(self):
        assert stray_text("@article(k1,\n  title = {A ) char},\n  year = {2000}\n)\n" + E) == []
        assert stray_text('@article(k1,\n  title = "A ) char",\n  year = {2000}\n)\n' + E) == []

    def test_paren_comment_block_balances_at_its_real_closer(self):
        # A `)` inside braces is literal; the block ends at the outer `)`.
        [hit] = comment_body_intrusions("@comment( see {a ) b} @x{k} )\n" + E)
        assert hit.word == "x"

    def test_bom_is_leading_whitespace_to_the_grammar(self):
        bom = "﻿"
        assert is_verbatim_block(bom + "@comment{x}")
        assert stray_text(bom + "@comment{x}\n" + E) == []
        assert stray_text(bom + E) == []
        [hit] = comment_body_intrusions(bom + "@comment{ a @x{k} }\n" + E)
        assert hit.word == "x"

    def test_unbalanced_block_then_entry_then_stray_closer_reports_only_the_closer(self):
        # Braces do not decide a block's extent, so the entry after an
        # unbalanced block is never an intrusion; the stray `}` after it is
        # the one thing to remove and the one thing reported.
        text = "@comment{\noverview { unmatched\n}\n" + E + "}\n" + E.replace("k1", "k2")
        [msg] = comment_defects(text)
        assert "'}'" in msg and "line 8" in msg

    def test_same_line_defects_keep_source_order(self):
        msgs = comment_defects("@comment{ a @z{1} @a{2} }\n" + E)
        assert [m.split("`")[1] for m in msgs] == ["@z", "@a"]


class TestReviewRoundFive:
    def test_concatenated_commands_on_one_line_are_misplaced_commands(self):
        [msg] = comment_defects("@article{k1,\n  title = {x}\n}@misc{k2, title={y}}\n")
        assert "line 3" in msg and "start at the beginning of its line" in msg

    def test_stray_after_a_balanced_block_carries_no_attribution(self):
        # The block closed on its own line; the `}` after k1 is a plain typo.
        [msg] = comment_defects("@comment{ ok }\n" + E + "}\n")
        assert "ended the" not in msg and "'}'" in msg

    def test_attribution_reaches_only_the_chunk_right_after_the_block(self):
        text = ("@comment{\noverview { unmatched\n}\n" + E
                + E.replace("k1", "k2") + "}\n")
        [msg] = comment_defects(text)
        assert "'}'" in msg and "ended the" not in msg
