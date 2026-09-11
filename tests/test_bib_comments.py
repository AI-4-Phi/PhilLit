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


E = "@article{k1,\n  title = {x},\n  year = {2000}\n}\n"


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

    def test_string_and_preamble_bodies_may_hold_an_at(self):
        # pybtex reads a @string value and a @preamble whole, braces or
        # quotes deciding their extent; only a @comment runs to the next `@`.
        # Reporting these blocked the cleaner (and a service SubagentStop)
        # on a valid file with a false diagnosis.
        for block in ('@string{j = "Journal @ Large"}', "@string{j = {Journal @ Large}}",
                      '@preamble{"mail: foo@bar"}', "@PREAMBLE( {\\href{mailto:a@b}} )"):
            assert comment_body_intrusions(block + "\n" + E) == [], block
            assert comment_defects(block + "\n" + E) == [], block

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
                "@comment{\nsecond\n@misc{k2, title={y}}\n}\n")
        assert comment_body_intrusions(text) == []
        [msg] = comment_defects(text)
        assert "line 8" in msg and "`@misc` on line 7" in msg and "opened on line 5" in msg


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

    def test_a_header_no_tool_reads_is_reported_as_such(self):
        # pybtex accepts all of these; the intersection header `@type{key,`
        # shared by dedupe, evidence stamping and the field scanner does not
        # match any, so at least one tool drops or misses it (dedupe, with
        # only a stderr warning, all but the space-before-key form, which
        # dedupe reads and evidence stamping misses). The
        # report names the header rule, not the column-0 rule (the command
        # DOES start its line), and the paren form is rejected here rather
        # than taught to every tool (zero incidence over 335 local bibs).
        for bad in ("@article(k2,\n  title = {x}\n)\n",
                    "@my-type{k2, title={t}, year={2000}}\n",
                    "@commentary{k2}\n",
                    "@article {k2, title={t}}\n",
                    "@article{ k2, title={t}}\n"):
            [stray] = stray_text(bad + E)
            assert stray.line == 1 and stray.snippet == bad.splitlines()[0], bad
            [msg] = comment_defects(bad + E)
            assert "`@type{key,`" in msg and "dedupe drops the chunk" in msg, msg
            assert "start at the beginning of its line" not in msg, msg
            assert "no space after the type or before the key" in msg, msg
        # The same header at column 0 in a well-formed file is an entry.
        assert stray_text("@commentary{k2,}\n" + E) == []
        assert stray_text("@Article{k2 ,\n  title = {x}\n}\n" + E) == []

    def test_defect_message_names_the_line_and_the_text(self):
        [msg] = comment_defects(E + "%% ---- divider ----\n" + E.replace("k1", "k2"))
        assert "line 5" in msg and "%% ---- divider ----" in msg
        assert "outside" in msg


class TestReviewRoundFour:
    """Final-design review: lexical context for paren-delimited commands, a
    BOM, late-balance reporting, and same-line ordering."""

    def test_paren_entry_is_one_header_report_whatever_its_body_holds(self):
        # The `(`-form body is never scanned as an entry span any more, so a
        # literal paren inside it changes nothing about the report.
        for text in ("@article(k1,\n  title = {A ) char},\n  year = {2000}\n)\n" + E,
                     '@article(k1,\n  title = "A ) char",\n  year = {2000}\n)\n' + E):
            [stray] = stray_text(text)
            assert stray.line == 1 and "`@type{key,`" in stray.describe()

    def test_paren_comment_block_balances_at_its_real_closer(self):
        # A `)` inside braces is literal; the block ends at the outer `)`.
        [hit] = comment_body_intrusions("@comment( see {a ) b} @x{k} )\n" + E)
        assert hit.word == "x"

    def test_bom_is_leading_whitespace_to_the_block_grammar_only(self):
        # Before a verbatim block a BOM is harmless: is_verbatim_block (which
        # dedupe binds) tolerates it and the chunk is carried whole. Before
        # the FIRST ENTRY it is not: dedupe matches `@type{key,` against the
        # raw chunk and drops that entry (measured 2026-09-10), so it is
        # reported as a command off the start of its line, naming the BOM.
        bom = "\ufeff"
        assert is_verbatim_block(bom + "@comment{x}")
        assert stray_text(bom + "@comment{x}\n" + E) == []
        [hit] = comment_body_intrusions(bom + "@comment{ a @x{k} }\n" + E)
        assert hit.word == "x"
        [stray] = stray_text(bom + E)
        assert (stray.line, stray.kind, stray.snippet) == (1, "misplaced", "@article{k1,")
        assert "byte-order mark" in stray.describe()
        assert [s.kind for s in stray_text(bom + "@my-type{k1, title={x}}\n" + E)] == ["misplaced", "header"]

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

    def test_command_after_a_closed_string_or_preamble_is_misplaced(self):
        # pybtex reads the entry (measured 2026-09-10); every tool here sees
        # one @string chunk and carries it whole, so the entry gets no
        # identity in dedupe and the cleaner would render it twice. The
        # first cut of the comment-only rule went silent here; the old scan
        # had reported it, with the wrong diagnosis.
        [stray] = stray_text('@string{j = "x"} ' + E)
        assert (stray.line, stray.kind, stray.snippet) == (1, "misplaced", "@article{k1,")
        [msg] = comment_defects('@preamble{"x"}\n  @article{k2, title={y}}\n' + E)
        assert "line 2" in msg and "start at the beginning of its line" in msg
        # Plain words after the closer are ignored by pybtex and carried
        # with the chunk: nothing is lost, nothing is reported.
        assert stray_text('@string{jp = "J Phil"} trailing words\n' + E) == []

    def test_an_indented_first_entry_is_a_misplaced_command(self):
        # dedupe drops it (measured 2026-09-10): its header regex runs on the
        # raw chunk, indentation included. Nothing is before it to fold into.
        [stray] = stray_text("  " + E + E.replace("k1", "k2"))
        assert (stray.line, stray.kind) == (1, "misplaced")
        msg = stray.describe()
        assert "dropped with that chunk" in msg and "move it to the start" in msg
        assert "byte-order mark" not in msg  # the BOM remedy is for a BOM

    def test_unclosed_string_or_preamble_is_reported_and_attributes_nothing(self):
        # Only a @comment runs to the next `@`, so the stray `}` after k1 is a
        # plain typo with no claim that the `@article` ended a block. The
        # unclosed block itself IS reported: pybtex refuses the quoted form
        # at end of file (TokenRequired), but a brace form closed by a later
        # `}}` parses to ZERO entries (measured 2026-09-10) - the entry is
        # swallowed into the value, gone from a rewrite, kept by dedupe.
        for opener in ('@string{j = "x"\n', '@preamble{"x"\n'):
            [msg] = comment_defects(opener + E + "}\n")
            assert "line 1" in msg and "does not close within its chunk" in msg, msg
            assert "ended the" not in msg
        [msg] = comment_defects("@string{j = {x\n" + E + "}}\n")
        assert "through line 6" in msg and "vanish" in msg
        # Everything BibTeX reads as the value - the swallowed entry, the
        # late `}}` closer - is covered by that one report, not reported as
        # stray text to delete.
        [msg] = comment_defects("@string{j = {x\n" + E + "%% divider\n" + E.replace("k1", "k2"))
        assert "never closes" in msg and "end of file" in msg  # and nothing after it is advised

    def test_only_an_entry_shaped_command_after_a_closed_string_is_misplaced(self):
        # pybtex reads a second @string, a @comment and an entry after the
        # closer (measured 2026-09-10); the tools carry the whole chunk. A
        # verbatim command there loses nothing, so it is not reported; an
        # entry there is the duplication hazard. `foo@bar.org` in trailing
        # words is pybtex's own syntax error (TokenRequired), not a command.
        assert stray_text('@string{j = "x"}@string{k = "y"}\n' + E) == []
        assert stray_text('@string{j = "x"} @comment{ overview }\n' + E) == []
        assert stray_text('@string{j = "x"} see foo@bar.org for more\n' + E) == []
        [stray] = stray_text('@string{j = "x"}@string{k = "y"} @article{k2, title={t}}\n' + E)
        assert (stray.kind, stray.snippet) == ("misplaced", "@article{k2, title={t}}")
        [stray] = stray_text('@string{j = "x"} @comment{ ov } @misc{k2, title={t}}\n' + E)
        assert (stray.kind, stray.snippet) == ("misplaced", "@misc{k2, title={t}}")
        # Paren-form blocks balance at their real closer: a paren inside a
        # quoted value is literal (pybtex reads the entry after each).
        [stray] = stray_text('@string(j = "a ) b") ' + E)
        assert stray.kind == "misplaced"
        [stray] = stray_text('@preamble("a ( b") ' + E)
        assert stray.kind == "misplaced"

    def test_unclosed_secondary_string_in_a_tail_is_reported(self):
        # Round-three shape: the first string balances, the second never
        # does, and a later `}}}` in a comment closes it for pybtex, which
        # then parses ZERO entries - k2 is swallowed. Silent before.
        text = ('@string{j="x"} @string{k={y\n' + E.replace("k1", "k2") + "@comment{x}}}\n")
        [stray] = stray_text(text)
        assert (stray.line, stray.kind, stray.snippet) == (1, "unclosed", '@string{k={y')
        assert stray.closes == 6

    def test_entry_after_a_comment_in_a_string_tail_names_the_comment(self):
        # `@misc` ends the trailing @comment for pybtex (read as an entry);
        # if it was comment prose the fix is to drop the `@`, not to move it.
        [msg] = comment_defects('@string{j="x"} @comment{ a @misc{k2, title={t}} }\n' + E)
        assert "start at the beginning of its line" in msg
        assert "ends the @comment opened on line 1" in msg and "if this is comment text remove the `@`" in msg

    def test_invisible_lead_characters_name_both_in_the_remedy(self):
        for lead in ("\ufeff  ", "\u200b", " \u2060"):
            [stray] = stray_text(lead + E)
            assert stray.kind == "misplaced", lead
            assert "invisible character" in stray.describe() and "any indentation" in stray.describe()

    def test_non_command_text_after_an_unbalanced_comment_is_attributed(self):
        [msg] = comment_defects("@comment{\noverview {\n@ 3pm notes\n" + E)
        assert "'@ 3pm notes'" in msg and "ended the @comment block opened on line 1" in msg

    def test_off_column_and_unreadable_header_are_both_reported_at_once(self):
        # Service pin review of 0.5.20: a BOM/indent AND a bad header on one
        # first entry earned two blocking cycles; now both are said at once.
        for text in ("\ufeff@article(k1, title={x})\n" + E, "  @my-type{k1, title={x}}\n" + E):
            kinds = [s.kind for s in stray_text(text)]
            assert kinds == ["misplaced", "header"], text
        [stray] = stray_text("  " + E)  # readable once at column 0: one report
        assert stray.kind == "misplaced"
        # A block behind a lead is carried (dedupe's own predicate tolerates
        # whitespace, a BOM and zero-width characters alike): no report.
        assert stray_text("  @comment{done}\n" + E) == []
        assert stray_text("\u200b@comment{done}\n" + E) == []
        # The same two-at-once rule in an entry's tail and in a string's tail.
        assert [s.kind for s in stray_text(E.rstrip("\n") + " @my-type{k2, title={t}}\n")] == ["misplaced", "header"]
        assert [s.kind for s in stray_text(E.rstrip("\n") + " @misc{k2, title={t}}\n")] == ["misplaced"]
        assert [s.kind for s in stray_text('@string{j="x"} @my-type{k2, title={t}}\n' + E)] == ["misplaced", "header"]

    def test_a_string_value_continuing_past_a_column_zero_at_names_the_cut(self):
        # pybtex reads `@string{j = "Journal\n@ Large"}` whole (measured
        # 2026-09-10); the chunker cuts it at the column-0 `@`, so no tool
        # here carries it whole and blocking is right - but the remedy is to
        # move that `@`, not to "close" a block that does close.
        [msg] = comment_defects('@string{j = "Journal\n@ Large"}\n' + E)
        assert "does not close within its chunk" in msg and "through line 2" in msg
        assert "move that line-start `@` off column 0" in msg
        # The value's tail chunk is NOT reported on its own: "delete it" would
        # be the wrong fix for text BibTeX reads as the value.

    def test_entry_after_a_closed_comment_gets_the_dual_remedy(self):
        # `@comment{ done } @misc{k2,...}`: pybtex reads k2 as an entry
        # (measured). Whether the `}` closed the intended block or not is the
        # author's intent, so the report offers both fixes and no longer
        # claims a tail is dropped when the block had closed.
        [msg] = comment_defects("@comment{ done } @misc{k2, title={t}}\n" + E)
        assert "if this is comment text remove the `@`" in msg and "left behind as stray text" in msg
        assert "if it is an entry, move the command to the start of its own line" in msg
        assert "the rest of the block is dropped" not in msg

    def test_only_the_first_intruder_is_said_to_end_the_block(self):
        first, second = comment_body_intrusions(
            "@comment{a @misc{k2, title={x}} @article{k3, title={y}}}\n" + E)
        assert first.first and not second.first
        assert "ends the block at this `@`" in first.describe()
        # The second says only what is certain: BibTeX left the comment at
        # the first `@`; how it reads this one depends on that fix.
        assert "fix that first `@`" in second.describe() and "becomes an entry" not in second.describe()

    def test_boundary_chunk_of_an_unclosed_block_is_scanned_past_the_closer(self):
        # Service pin review of 0.5.21: the chunk holding the closer was
        # skipped WHOLE, so an entry after the closer on that line went
        # unreported while dedupe drops that chunk (no header). pybtex reads
        # k2 (measured). Now the remainder after the closer is a string's
        # tail: k2 is a misplaced command, said in the same cycle.
        text = ('@string{j = "Journal\n@ Large"} @article{k2,\n  title = {T}, year = {2001}\n}\n' + E)
        unclosed, misplaced = stray_text(text)
        assert (unclosed.kind, unclosed.line, unclosed.closes) == ("unclosed", 1, 2)
        assert (misplaced.kind, misplaced.offset) == ("misplaced", text.index("@article{k2"))
        # Plain words after the closer are still nothing.
        [stray] = stray_text('@string{j = "Journal\n@ Large"} see above\n' + E)
        assert stray.kind == "unclosed"

    def test_invisible_lead_before_a_block_is_the_bom_rule(self):
        # One lead class for both regexes (the service noted the drift): a
        # zero-width character before a block is tolerated like a BOM - the
        # chunk is carried by dedupe's own predicate, its tail and closure
        # are judged as a block's, and its body is the intrusion scan's.
        assert is_verbatim_block("\u200b@comment{x}") and is_verbatim_block("\u2060 @string{j = \"x\"}")
        [stray] = stray_text('\u200b@string{j="J"} @article{k2, title={t}}\n' + E)
        assert (stray.kind, stray.snippet) == ("misplaced", "@article{k2, title={t}}")
        [stray] = stray_text("\u200b@string{j = {x\n" + E + "}}\n")
        assert stray.kind == "unclosed"
        assert stray_text("\u200b@comment{ a @x{k} }\n" + E) == []
        [hit] = comment_body_intrusions("\u200b@comment{ a @x{k} }\n" + E)
        assert hit.word == "x"

    def test_intrusion_scan_honours_an_unclosed_blocks_value_span(self):
        # Service pin review of 0.5.22: pybtex reads ['k1'] - the braced
        # value holds the literal `@comment{a @x{k}}` and closes at `}}`.
        # The `@x` was a false intrusion whose remedy would corrupt the
        # value; the unclosed report is the one report.
        swallowed = "@string{j = {x\n@comment{a @x{k}}\n}}\n" + E
        assert comment_body_intrusions(swallowed) == []
        [msg] = comment_defects(swallowed)
        assert "does not close within its chunk" in msg and "through line 3" in msg
        [msg] = comment_defects("@string{j = {x\n@comment{a @x{k}}\n" + E)  # never closes
        assert "never closes" in msg
        # A boundary chunk holding value text before the closer AND a real
        # comment after it (service round 2, pybtex reads ['k2', 'k1']): the
        # `@x` before the closer is value text (no report), the `@y` that
        # ends the trailing comment is reported once, by the tail scan, with
        # the comment's attribution and the dual remedy.
        text = ("@string{j = {x\n@comment{ a } @x{k} }} @comment{b @y{k2, title={t}}}\n" + E)
        assert comment_body_intrusions(text) == []
        unclosed, at_y = stray_text(text)
        assert (unclosed.kind, unclosed.closes) == ("unclosed", 2)
        assert (at_y.kind, at_y.snippet, at_y.after) == ("misplaced", "@y{k2, title={t}}}", (2, 2, "y"))
        assert "ends the @comment opened on line 2" in at_y.describe()
        # An unclosed @string in a COMMENT chunk's tail (pybtex ends the
        # comment at `@string` and reads the string; ['k1'], measured): the
        # intrusion scan reports the `@string` (true - move it to its own
        # line) and the string's unclosed span still bounds the swallowed
        # `@comment{a @x{k}}` line, so `@x` is not a second, false intrusion.
        text = "@comment{done} @string{j = {x\n@comment{a @x{k}}\n}}\n" + E
        assert [(h.line, h.word) for h in comment_body_intrusions(text)] == [(1, "string")]
        [unclosed] = stray_text(text)
        assert (unclosed.kind, unclosed.closes) == ("unclosed", 3)
        # A comment AFTER the closer is a comment again.
        unclosed, intrusion = comment_defects(
            "@string{j = {x\n@article{k0, title={t}}\n}}\n@comment{a @x{k}}\n" + E)
        assert "through line 3" in unclosed and "`@x`" in intrusion

    def test_a_column_zero_at_that_is_not_a_command_is_stray_text(self):
        # `@ 3pm notes` is pybtex's syntax error and text to delete, not a
        # header to rewrite.
        [stray] = stray_text("@ 3pm notes\n" + E)
        assert stray.kind == "text"

    def test_header_defect_after_an_unbalanced_comment_names_the_comment(self):
        # The column-0 `@commentary{k1}` ends the unbalanced block for pybtex
        # and is no entry to dedupe. Told only to rewrite the header, an
        # agent would make a phantom entry out of comment prose; the report
        # names the block so the `@` can be removed instead.
        [msg] = comment_defects("@comment{\noverview {\n@commentary{k1}\n}\n" + E)
        assert "line 3" in msg and "`@type{key,`" in msg
        assert "opened on line 1" in msg and "if this is comment text remove the `@`" in msg
        assert msg.endswith("if it is an entry, rewrite the header")  # the two remedies are alternatives

    def test_attribution_reaches_only_the_chunk_right_after_the_block(self):
        text = ("@comment{\noverview { unmatched\n}\n" + E
                + E.replace("k1", "k2") + "}\n")
        [msg] = comment_defects(text)
        assert "'}'" in msg and "ended the" not in msg
