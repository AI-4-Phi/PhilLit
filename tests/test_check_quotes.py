"""check_quotes.py: the Phase 6 quotation gate for EVIDENCE-FULLTEXT works
(spec section 9). Fixtures are built in tmp_path: real PDF bytes through
pypdf extraction, page confirmation and the renderer, a merged bib, a barrier
report with attestation blobs, and a review."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
CHECKER = SCRIPTS / "check_quotes.py"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

import check_quotes as cq  # noqa: E402
import fulltext as ft  # noqa: E402
import stamp_evidence as se  # noqa: E402
from pdf_fixtures import make_pdf  # noqa: E402

CAP_SENTENCE = ("Equal consideration of interests is a basic moral principle that "
                "extends beyond our own species and asks us to weigh like interests alike.")

# Page 45 carries its number as a header and the others as footers, so
# nothing stands between the last line of page 45 and the first of page 46.
# The layout with a real footer at that break (the fold skips page
# furniture) is test_quote_across_a_real_footer.
PAGES = [
    ["45",
     "The capacity for suffering is the vital characteristic",
     "that gives a being the right to equal consideration.",
     "If a being suffers there can be no moral justification",
     "for refusing to take that suffering into consideration."],
    ["No matter what the nature of the being, the principle",
     "of equality requires that its suffering be counted equally",
     "with the like suffering of any other being whatsoever.",
     "The limit of sentience is the only defensible boundary.",
     "46"],
    [CAP_SENTENCE, CAP_SENTENCE, CAP_SENTENCE, CAP_SENTENCE, "47"],
    [CAP_SENTENCE, CAP_SENTENCE, CAP_SENTENCE, CAP_SENTENCE, "48"],
]


def rendered_text(confirm=True):
    pages = ft.extract_pages(make_pdf(PAGES))
    pm = ft.confirm_pages(pages, "45--48") if confirm else None
    if confirm:
        assert pm is not None and pm.numbers == (45, 46, 47, 48)
    return ft.render_text(pages, pm)


def bib_entry(key, *, year, doi=None, tier="EVIDENCE-FULLTEXT", slug=None, title="Animal Liberation",
              author="Singer, Peter", abstract=None):
    lines = [f"@book{{{key},", f"  author = {{{author}}},", f"  title = {{{title}}},",
             f"  year = {{{year}}},"]
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    if abstract:
        lines.append(f"  abstract = {{{abstract}}},")
    if slug:
        lines.append(f"  fulltext_file = {{{ft.STORE_REL}/{slug}.txt}},")
    lines.append(f"  keywords = {{topic, High, {tier}}}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def fields_of(entry_text):
    return se.parse_entry_fields(entry_text)


class Fix:
    """A workdir with texts, a merged bib, a report and a review."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.workdir = tmp_path / "work"
        self.store = self.workdir / ft.STORE_REL
        self.store.mkdir(parents=True)
        self.entries = []
        self.report = {"schema_version": 2, "attestations": {}}

    def add_fulltext(self, key, *, year, doi=None, text=None, bib="literature-domain-1.bib",
                     tier="EVIDENCE-FULLTEXT", title="Animal Liberation", author="Singer, Peter",
                     write_blob=True, abstract=None):
        identity = {"doi": doi, "title": title, "surname": author.split(",")[0], "year": year}
        slug = ft.slug_for(identity)
        text = rendered_text() if text is None else text
        ft.write_text_atomic(self.store / f"{slug}.txt", text)
        entry = bib_entry(key, year=year, doi=doi, tier=tier, slug=slug, title=title, author=author,
                          abstract=abstract)
        self.entries.append(entry)
        if write_blob:
            self.add_blob(bib, key, slug, text, entry)
        return slug, text, entry

    def add_blob(self, bib, key, slug, text, entry):
        self.report["attestations"].setdefault(bib, {})[key] = {
            "abstract_attested": False, "web_gate_passed": False,
            "fulltext_verified": True, "fulltext_slug": slug,
            "fulltext_text_sha256": ft.text_sha256(text),
            "fulltext_identity": ft.entry_identity(fields_of(entry)),
        }

    def add_entry(self, entry):
        self.entries.append(entry)

    def run(self, review, capsys):
        md = self.tmp / "review.md"
        md.write_text(review, encoding="utf-8")
        bib = self.tmp / "merged.bib"
        bib.write_text("\n".join(self.entries), encoding="utf-8")
        rep = self.tmp / "report.json"
        rep.write_text(json.dumps(self.report), encoding="utf-8")
        code = cq.main([str(md), str(bib), "--workdir", str(self.workdir),
                        "--evidence-report", str(rep)])
        out = capsys.readouterr().out.splitlines()
        assert out[-1].startswith("QUOTES-SUMMARY: ")
        summary = json.loads(out[-1][len("QUOTES-SUMMARY: "):])
        return code, out[:-1], summary


@pytest.fixture
def fx(tmp_path):
    f = Fix(tmp_path)
    f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975")
    f.add_entry(bib_entry("regan1983", year="1983", tier="EVIDENCE-EXISTENCE",
                          title="The Case for Animal Rights", author="Regan, Tom"))
    return f


def doc(body):
    return "# Review\n\n## Section\n\n" + body + "\n\n## References\n\nSinger, Peter. 1975. \"Totally invented words here.\"\n"


# ---------------------------------------------------------------------------
# Verbatim
# ---------------------------------------------------------------------------

class TestVerbatim:
    def test_pass(self, fx, capsys):
        code, lines, s = fx.run(doc(
            'Singer (1975) holds that "the capacity for suffering is the vital characteristic".'), capsys)
        assert (code, lines) == (0, [])
        assert s["fulltext_attributed"] == 1

    def test_fail(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'Singer (1975) holds that "the capacity for pain is the vital characteristic".'), capsys)
        assert code == 1
        assert lines == ['FAIL verbatim: singer1975: "the capacity for pain is the vital characteristic" [line 5]']

    def test_quote_across_a_page_break(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'Singer (1975, 45-46) writes "to take that suffering into consideration. '
            'No matter what the nature of the being".'), capsys)
        assert (code, lines) == (0, [])

    def test_quote_across_a_real_footer(self, tmp_path, capsys):
        pages = [PAGES[0][1:] + ["45"], PAGES[1], PAGES[2], PAGES[3]]
        extracted = ft.extract_pages(make_pdf(pages))
        pm = ft.confirm_pages(extracted, "45--48")
        assert pm is not None and pm.numbers == (45, 46, 47, 48)
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975",
                       text=ft.render_text(extracted, pm))
        code, lines, _ = f.run(doc(
            'Singer (1975, 45-46) writes "to take that suffering into consideration. '
            'No matter what the nature of the being".'), capsys)
        assert (code, lines) == (0, [])

    def test_two_word_span_checked(self, fx, capsys):
        ok = fx.run(doc('It is "the vital characteristic" (Singer 1975).'), capsys)
        assert ok[0] == 0
        code, lines, _ = fx.run(doc('It is "vital feature" (Singer 1975).'), capsys)
        assert code == 1 and lines[0].startswith("FAIL verbatim: singer1975")

    def test_one_word_scare_quote_ignored(self, fx, capsys):
        code, lines, s = fx.run(doc('The "boundary" is drawn (Singer 1975).'), capsys)
        assert (code, lines, s["spans"]) == (0, [], 0)

    def test_bracketed_capital_passes_and_other_brackets_fail(self, fx, capsys):
        ok = fx.run(doc('"[N]o matter what the nature of the being" (Singer 1975).'), capsys)
        assert ok[0] == 0
        code, lines, s = fx.run(doc('"[Not] matter what the nature of the being" (Singer 1975).'), capsys)
        assert code == 1 and lines[0].startswith("FAIL bracket: singer1975")
        assert s["fail_bracket"] == 1

    def test_short_ellipsis_part_fails(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            '"the capacity for suffering ... vital characteristic" (Singer 1975).'), capsys)
        assert code == 1 and lines[0].startswith("FAIL ellipsis: singer1975")

    def test_curly_quotes_and_emphasis(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'Singer (1975) puts it plainly: “the *vital* characteristic”.'), capsys)
        assert (code, lines) == (0, [])

    def test_abstract_of_an_abstract_entry_licenses(self, fx, capsys):
        fx.add_entry(bib_entry("regan1984", year="1984", tier="EVIDENCE-ABSTRACT",
                               title="Rights", author="Regan, Tom",
                               abstract="Animals are subjects-of-a-life with inherent value."))
        code, lines, _ = fx.run(doc(
            'Animals are "subjects-of-a-life with inherent value" (Regan 1984; Singer 1975).'), capsys)
        assert (code, lines) == (0, [])

    def test_headings_code_and_references_skipped(self, fx, capsys):
        md = ('# "A heading with quoted words" (Singer 1975)\n\n'
              'Text with `"code span words here"` (Singer 1975).\n\n'
              '```\n"fenced quote words here" (Singer 1975)\n```\n\n'
              '## References\n\nSinger, Peter. 1975. "Not in the text at all." Publisher.\n')
        code, lines, s = fx.run(md, capsys)
        assert (code, lines, s["spans"]) == (0, [], 0)


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

    def test_unclosed_quote_fails(self, fx, capsys):
        code, lines, s = fx.run(doc(
            'Some say "this is never closed (Singer 1975). Singer\'s view stands.'), capsys)
        assert code == 1
        assert lines == ['FAIL unclosed-quote: "this is never closed (Singer 1975). Singer\'s view stands." [line 5]']
        assert s["fail_unclosed_quote"] == 1

    def test_quote_across_paragraphs_fails_unclosed(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'Singer (1975) writes \u201cthe capacity for suffering\n\nis the vital characteristic\u201d.'), capsys)
        assert code == 1 and [ln.split(":")[0] for ln in lines] == ["FAIL unclosed-quote"]

    def test_frontmatter_and_html_comments_masked(self, fx, capsys):
        md = ('---\ntitle: "Animal Liberation and Other Wholly Invented Words"\n---\n\n'
              + doc('<!-- "an invented quoted comment here" (Singer 1975) -->\n\nPlain prose (Singer 1975).'))
        code, lines, s = fx.run(md, capsys)
        assert (code, lines, s["spans"], s["titles_skipped"]) == (0, [], 0, 0)

    def test_literal_asterisk_survives(self, fx, capsys):
        code, lines, _ = fx.run(doc('"the vital * characteristic" (Singer 1975).'), capsys)
        assert code == 1 and lines[0].startswith("FAIL verbatim: singer1975")


class TestAttribution:
    def test_first_citation_in_a_multi_cite(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'One view is that "the vital characteristic" matters (Singer 1975; Regan 1983).'), capsys)
        assert (code, lines) == (0, [])

    def test_second_citation_in_a_multi_cite(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'One view is that "a wholly invented phrase" matters (Regan 1983; Singer 1975).'), capsys)
        assert code == 1
        assert lines == ['FAIL verbatim: regan1983, singer1975: "a wholly invented phrase" [line 5]']

    def test_next_sentence_citation(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'Some say "a wholly invented phrase here." That is how Singer (1975) puts it.'), capsys)
        assert code == 1 and lines[0].startswith("FAIL verbatim: singer1975")

    def test_abbreviation_does_not_split_the_sentence(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'Some say "a wholly invented phrase here" (cf. Singer et al. 1975, 45).'), capsys)
        assert code == 1 and lines[0].startswith("FAIL verbatim: singer1975")

    def test_period_inside_the_quote_then_citation(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'Some say "a wholly invented phrase here." (Singer 1975). Regan (1983) disagrees.'), capsys)
        assert code == 1 and lines[0].startswith("FAIL verbatim: singer1975:")

    def test_initial_does_not_split_the_sentence(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'As P. Singer (1975) says, "a wholly invented phrase here".'), capsys)
        assert code == 1 and lines[0].startswith("FAIL verbatim: singer1975:")

    def test_quoted_title_excluded(self, fx, capsys):
        code, lines, s = fx.run(doc(
            'Singer\'s "Animal Liberation" (Singer 1975) changed the debate.'), capsys)
        assert (code, lines) == (0, [])
        assert s["titles_skipped"] == 1

    def test_quoted_title_with_next_sentence_citation_excluded(self, fx, capsys):
        code, lines, s = fx.run(doc(
            'Consider "Animal Liberation" first. Singer (1975) wrote it.'), capsys)
        assert (code, lines, s["titles_skipped"]) == (0, [], 1)

    def test_editor_only_entry_resolves(self, fx, capsys):
        fx.add_entry("@book{korsgaard1986,\n  editor = {Korsgaard, Christine},\n"
                     "  title = {An Edited Volume},\n  year = {1986},\n"
                     "  keywords = {EVIDENCE-EXISTENCE}\n}\n")
        code, lines, _ = fx.run(doc('Some say "this phrase has four words" (Korsgaard 1986).'), capsys)
        assert (code, lines) == (0, [])   # attributed, so no WARN uncited

    def test_title_of_an_uncited_work_is_not_excluded(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'The book "Animal Liberation" is cited here (Regan 1983).'), capsys)
        assert (code, lines) == (0, [])   # not FULLTEXT-attributed: no check

    def test_uncited_warn(self, fx, capsys):
        code, lines, s = fx.run(doc(
            'Some say "this phrase has four words" and others disagree.\n\nNew paragraph (Singer 1975).'), capsys)
        assert code == 0
        assert lines == ['WARN uncited: "this phrase has four words" [line 5]']
        assert s["warn_uncited"] == 1

    def test_three_word_uncited_not_warned(self, fx, capsys):
        code, lines, _ = fx.run(doc('Some say "only three words" loosely.'), capsys)
        assert (code, lines) == (0, [])


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

class TestPages:
    def test_right_page(self, fx, capsys):
        code, lines, _ = fx.run(doc('"The limit of sentience" is decisive (Singer 1975, 46).'), capsys)
        assert (code, lines) == (0, [])

    def test_wrong_page_is_fix_not_fail(self, fx, capsys):
        code, lines, s = fx.run(doc('"The limit of sentience" is decisive (Singer 1975, 47).'), capsys)
        assert code == 0
        assert lines[0].startswith('FIX page: singer1975: drop or correct the locator "47" (quote on: page 46)')
        assert s["fix_page"] == 1

    def test_page_prefix_and_narrative_form(self, fx, capsys):
        code, lines, _ = fx.run(doc('Singer (1975, p. 46) says "the limit of sentience".'), capsys)
        assert (code, lines) == (0, [])

    def test_spanning_quote_either_page_or_the_range(self, fx, capsys):
        quote = '"take that suffering into consideration. No matter what the nature"'
        for loc in ("45", "46", "45-46", "44-45"):
            code, lines, _ = fx.run(doc(f"He writes {quote} (Singer 1975, {loc})."), capsys)
            assert (code, lines) == (0, []), loc
        code, lines, _ = fx.run(doc(f"He writes {quote} (Singer 1975, 47-48)."), capsys)
        assert lines[0].startswith("FIX page: singer1975")

    def test_trailing_page_parenthesis(self, fx, capsys):
        code, lines, _ = fx.run(doc('Singer (1975) writes "the limit of sentience" (48).'), capsys)
        assert lines[0].startswith('FIX page: singer1975: drop or correct the locator "48"')

    def test_chapter_locator_and_second_year_not_pages(self, fx, capsys):
        fx.add_fulltext("singer1990", year="1990", text=rendered_text())
        code, lines, _ = fx.run(doc(
            '"The limit of sentience" (Singer 1975, ch. 1). Also "the vital characteristic" (Singer 1975, 1990).'),
            capsys)
        assert (code, lines) == (0, [])

    def test_locator_on_an_unconfirmed_text_is_fix(self, tmp_path, capsys):
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975", text=rendered_text(confirm=False))
        code, lines, _ = f.run(doc('"The limit of sentience" (Singer 1975, 46).'), capsys)
        assert code == 0
        assert lines[0].startswith('FIX page: singer1975: drop or correct the locator "46" (quote on: sheet 2)')
        code, lines, _ = f.run(doc('"The limit of sentience" (Singer 1975).'), capsys)
        assert (code, lines) == (0, [])


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------

class TestLocatorForms:
    QUOTE = '"The limit of sentience" is decisive'

    @pytest.mark.parametrize("loc", ["46 n. 3", "46n3", "46ff.", "46f.", "pp. 45-46", "ch. 2",
                                     "46, emphasis added", "1990"])
    def test_readable_and_confirmed(self, fx, capsys, loc):
        code, lines, _ = fx.run(doc(f"{self.QUOTE} (Singer 1975, {loc})."), capsys)
        assert (code, lines) == (0, []), loc

    def test_each_listed_page_checked(self, fx, capsys):
        code, lines, s = fx.run(doc(f"{self.QUOTE} (Singer 1975, 46, 47)."), capsys)
        assert code == 0 and s["fix_page"] == 1
        assert lines[0].startswith('FIX page: singer1975: drop or correct the locator "47"')

    def test_unrecognized_locator_is_fix(self, fx, capsys):
        code, lines, _ = fx.run(doc(f"{self.QUOTE} (Singer 1975, 46 et seq.)."), capsys)
        assert lines[0].startswith('FIX page: singer1975: unrecognized locator "46 et seq."')

    def test_roman_locator_is_fix_drop_it(self, fx, capsys):
        code, lines, _ = fx.run(doc(f"{self.QUOTE} (Singer 1975, xii)."), capsys)
        assert lines[0].startswith('FIX page: singer1975: roman locator "xii" names no confirmed page: drop it')

    def test_prose_after_a_narrative_year_is_not_a_locator(self, fx, capsys):
        code, lines, _ = fx.run(doc(
            'In Singer 1975, 46 readers found "the limit of sentience" decisive.'), capsys)
        assert (code, lines) == (0, [])

    def test_year_like_number_is_a_page_when_the_text_has_that_page(self, tmp_path, capsys):
        pages = [[str(n)] + PAGES[1][:-1] if i == 0 else PAGES[min(i + 1, 3)][:-1] + [str(n)]
                 for i, n in enumerate(range(1999, 2003))]
        extracted = ft.extract_pages(make_pdf(pages))
        pm = ft.confirm_pages(extracted, "1999--2002")
        assert pm is not None and pm.numbers == (1999, 2000, 2001, 2002)
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975", text=ft.render_text(extracted, pm))
        ok = f.run(doc(f"{self.QUOTE} (Singer 1975, 1999)."), capsys)
        assert ok[:2] == (0, [])
        code, lines, _ = f.run(doc(f"{self.QUOTE} (Singer 1975, 2001)."), capsys)
        assert lines[0].startswith('FIX page: singer1975: drop or correct the locator "2001" (quote on: page 1999)')
        code, lines, _ = f.run(doc(f"{self.QUOTE} (Singer 1975, 1985)."), capsys)
        assert (code, lines) == (0, [])   # no such page: a second year


def words(n):
    """n words of the repeated cap sentence (it repeats, so any window matches)."""
    w = CAP_SENTENCE.split() * 4
    return " ".join(w[:n])


class TestCaps:
    def test_span_above_40_words(self, fx, capsys):
        code, lines, s = fx.run(doc(f'"{words(41)}" (Singer 1975).'), capsys)
        assert code == 0
        assert lines[0].startswith("WARN cap: singer1975: 41 words in one quotation (cap 40)")
        ok = fx.run(doc(f'"{words(40)}" (Singer 1975).'), capsys)
        assert ok[1] == []

    def test_per_work_across_two_keys_and_two_slugs(self, tmp_path, capsys):
        f = Fix(tmp_path)
        slug_a, _, _ = f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975")
        slug_b, _, _ = f.add_fulltext("singer1990", year="1990")   # a reprint, no DOI
        assert slug_a != slug_b
        body = " ".join([f'One "{words(40)}" (Singer 1975).', f'Two "{words(40)}" (Singer 1975).',
                         f'Three "{words(38)}" (Singer 1990).', f'Four "{words(36)}" (Singer 1990).'])
        code, lines, s = f.run(doc(body), capsys)
        assert code == 0
        assert lines == ["WARN cap: singer1975, singer1990: 154 words quoted from this work (cap 150)"]
        assert s["warn_cap"] == 1

    def test_different_works_do_not_pool(self, tmp_path, capsys):
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975")
        f.add_fulltext("singer1990", year="1990", title="Practical Ethics")
        body = " ".join([f'One "{words(40)}" (Singer 1975).', f'Two "{words(40)}" (Singer 1975).',
                         f'Three "{words(38)}" (Singer 1990).', f'Four "{words(36)}" (Singer 1990).'])
        code, lines, _ = f.run(doc(body), capsys)
        assert (code, lines) == (0, [])


# ---------------------------------------------------------------------------
# Licence
# ---------------------------------------------------------------------------

QUOTE = 'Singer (1975) holds that "the capacity for suffering is the vital characteristic".'


class TestLicence:
    def test_demoted_entry(self, tmp_path, capsys):
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975", tier="EVIDENCE-ABSTRACT")
        code, lines, s = f.run(doc(QUOTE), capsys)
        assert code == 1
        assert lines == ['FAIL licence-lost: singer1975 (not EVIDENCE-FULLTEXT now (EVIDENCE-ABSTRACT)): '
                         '"the capacity for suffering is the vital characteristic" [line 5]']
        assert s["fail_licence_lost"] == 1 and s["fail_verbatim"] == 0

    def test_demoted_to_abstract_passes_when_its_abstract_holds_the_quote(self, tmp_path, capsys):
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975", tier="EVIDENCE-ABSTRACT",
                       abstract="He argues that the capacity for suffering is the vital characteristic.")
        code, lines, s = f.run(doc(QUOTE), capsys)
        assert (code, lines, s["fail_licence_lost"]) == (0, [], 0)

    def test_demoted_to_abstract_fails_when_only_the_full_text_holds_it(self, tmp_path, capsys):
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975", tier="EVIDENCE-ABSTRACT",
                       abstract="An argument for equal consideration of animals.")
        code, lines, _ = f.run(doc(QUOTE), capsys)
        assert code == 1
        assert [ln.split(":")[0] for ln in lines] == ["FAIL licence-lost", "FAIL verbatim"]

    def test_fulltext_stamp_with_failed_hash_gets_no_abstract_fallback(self, tmp_path, capsys):
        f = Fix(tmp_path)
        f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975",
                       abstract="He argues that the capacity for suffering is the vital characteristic.")
        p = next(f.store.glob("*.txt"))
        p.write_text(ft.read_text(p) + "appended\n", encoding="utf-8")
        code, lines, _ = f.run(doc(QUOTE), capsys)
        assert code == 1 and lines[0].startswith("FAIL licence-lost: singer1975 (text hash differs)")

    def test_missing_text(self, fx, capsys):
        for p in fx.store.glob("*.txt"):
            p.unlink()
        code, lines, _ = fx.run(doc(QUOTE), capsys)
        assert code == 1 and lines[0].startswith("FAIL licence-lost: singer1975 (text missing)")

    def test_tampered_text(self, fx, capsys):
        p = next(fx.store.glob("*.txt"))
        p.write_text(ft.read_text(p) + "appended\n", encoding="utf-8")
        code, lines, _ = fx.run(doc(QUOTE), capsys)
        assert code == 1 and lines[0].startswith("FAIL licence-lost: singer1975 (text hash differs)")

    def test_unreadable_text_is_a_licence_fail_not_a_crash(self, fx, capsys):
        p = next(fx.store.glob("*.txt"))
        p.write_bytes(b"\xff\xfe\xfa not utf-8")
        code, lines, _ = fx.run(doc(QUOTE), capsys)
        assert code == 1 and lines[0].startswith("FAIL licence-lost: singer1975 (text unreadable)")

    def test_identity_changed_since_the_barrier(self, tmp_path, capsys):
        f = Fix(tmp_path)
        slug, text, entry = f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975")
        f.entries = [entry.replace("year = {1975}", "year = {1976}").replace("(1975)", "")]
        code, lines, _ = f.run(doc(QUOTE.replace("1975", "1976")), capsys)
        assert code == 1 and lines[0].startswith("FAIL licence-lost: singer1975 (no authorizing attestation)")

    def test_same_key_in_two_domains_only_the_matching_blob_authorizes(self, tmp_path, capsys):
        f = Fix(tmp_path)
        # Domain 1's singer1975 is a different work (other DOI, other slug);
        # its blob comes FIRST in the report.
        other_slug, other_text, other_entry = f.add_fulltext(
            "singer1975", year="1975", doi="10.1000/other", bib="literature-domain-1.bib")
        f.entries = []
        slug, text, entry = f.add_fulltext("singer1975", year="1975", doi="10.1000/al.1975",
                                           bib="literature-domain-2.bib")
        assert list(f.report["attestations"]) == ["literature-domain-1.bib", "literature-domain-2.bib"]
        code, lines, _ = f.run(doc(QUOTE), capsys)
        assert (code, lines) == (0, [])
        # Without domain 2's blob, domain 1's never authorizes the merged entry.
        del f.report["attestations"]["literature-domain-2.bib"]
        code, lines, _ = f.run(doc(QUOTE), capsys)
        assert code == 1 and lines[0].startswith("FAIL licence-lost: singer1975 (no authorizing attestation)")

    def test_blob_not_verified(self, fx, capsys):
        for blobs in fx.report["attestations"].values():
            for b in blobs.values():
                b["fulltext_verified"] = "true"   # truthy is not True
        code, lines, _ = fx.run(doc(QUOTE), capsys)
        assert code == 1 and "(no authorizing attestation)" in lines[0]

    def test_malformed_fulltext_file(self, fx, capsys):
        fx.entries[0] = fx.entries[0].replace(ft.STORE_REL + "/", "../../")
        code, lines, _ = fx.run(doc(QUOTE), capsys)
        assert code == 1 and "(malformed fulltext_file)" in lines[0]

    def test_unquoted_watched_work_is_fine(self, fx, capsys):
        for p in fx.store.glob("*.txt"):
            p.unlink()
        code, lines, _ = fx.run(doc("Singer (1975) argues for equal consideration."), capsys)
        assert (code, lines) == (0, [])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(args, cwd):
    return subprocess.run([sys.executable, str(CHECKER), *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", env={**os.environ, "PYTHONPATH": ""})


class TestCli:
    def test_by_path_exit_codes_and_ascii_output(self, fx, tmp_path, capsys):
        fx.run(doc('Singer (1975) holds that "the capacity for pain — is the vital characteristic".'), capsys)
        args = [str(tmp_path / "review.md"), str(tmp_path / "merged.bib"), "--workdir", str(fx.workdir),
                "--evidence-report", str(tmp_path / "report.json")]
        r = _cli(args, tmp_path)
        assert r.returncode == 1, r.stderr
        assert r.stdout.isascii()
        assert r.stdout.splitlines()[0].startswith("FAIL verbatim: singer1975")
        assert r.stdout.splitlines()[-1].startswith("QUOTES-SUMMARY: {")

    def test_unreadable_report_exits_2(self, fx, tmp_path, capsys):
        fx.run(doc(QUOTE), capsys)
        (tmp_path / "report.json").write_text("{not json", encoding="utf-8")
        args = [str(tmp_path / "review.md"), str(tmp_path / "merged.bib"), "--workdir", str(fx.workdir),
                "--evidence-report", str(tmp_path / "report.json")]
        r = _cli(args, tmp_path)
        assert r.returncode == 2
        assert r.stdout == "" and len(r.stderr.strip().splitlines()) == 1

    def test_missing_inputs_and_usage_exit_2(self, tmp_path):
        r = _cli([str(tmp_path / "nope.md"), str(tmp_path / "nope.bib"), "--workdir", str(tmp_path),
                  "--evidence-report", str(tmp_path / "nope.json")], tmp_path)
        assert r.returncode == 2 and len(r.stderr.strip().splitlines()) == 1
        assert _cli(["only-one-arg"], tmp_path).returncode == 2

    def test_crash_exits_2(self, fx, tmp_path, capsys, monkeypatch):
        fx.run(doc(QUOTE), capsys)

        def boom(*a, **k):
            raise RuntimeError("boom")
        monkeypatch.setattr(cq, "run", boom)
        code = cq.main([str(tmp_path / "review.md"), str(tmp_path / "merged.bib"), "--workdir",
                        str(fx.workdir), "--evidence-report", str(tmp_path / "report.json")])
        err = capsys.readouterr().err
        assert code == 2 and "crashed: RuntimeError: boom" in err and len(err.strip().splitlines()) == 1
