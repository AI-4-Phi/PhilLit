"""fulltext.py: extraction, the measured identity rules, page maps, the text
format, store slugs and records, and the quote matcher (spec sections 4, 5, 9).
"""
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

import fulltext as ft  # noqa: E402
from pdf_fixtures import make_pdf  # noqa: E402

FILLER = "This sentence is ordinary body text that pads the page to a realistic length."


def body(n=4):
    return [FILLER] * n


# ---------------------------------------------------------------------------
# extract_pages
# ---------------------------------------------------------------------------

class TestExtract:
    def test_pages_come_back_in_order(self):
        pages = ft.extract_pages(make_pdf([["First page"] + body(), ["Second page"] + body()]))
        assert len(pages) == 2
        assert pages[0].splitlines()[0] == "First page"
        assert pages[1].splitlines()[0] == "Second page"

    def test_encrypted_with_a_password_fails(self):
        with pytest.raises(ft.FulltextError) as e:
            ft.extract_pages(make_pdf([body()], encrypt=True))
        assert e.value.reason == "encrypted"

    def test_encrypted_with_empty_user_password_is_read(self):
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf([body()]))))
        w.encrypt(user_password="", owner_password="owner")
        buf = io.BytesIO()
        w.write(buf)
        pages = ft.extract_pages(buf.getvalue())
        assert FILLER in pages[0]

    def test_too_little_text_is_no_text(self):
        with pytest.raises(ft.FulltextError) as e:
            ft.extract_pages(make_pdf([["short"]]))
        assert e.value.reason == "no-text"

    def test_mostly_unprintable_text_is_unreadable(self):
        with pytest.raises(ft.FulltextError) as e:
            ft.extract_pages(make_pdf([["\x01\x02\x03\x04" * 80]]))
        assert e.value.reason == "unreadable"

    def test_not_a_pdf_is_parse(self):
        with pytest.raises(ft.FulltextError) as e:
            ft.extract_pages(b"<html>not a pdf</html>" * 50)
        assert e.value.reason == "parse"

    def test_over_cap_is_too_large(self, monkeypatch):
        data = make_pdf([body()])
        monkeypatch.setattr(ft, "MAX_PDF_BYTES", len(data) - 1)
        with pytest.raises(ft.FulltextError) as e:
            ft.extract_pages(data)
        assert e.value.reason == "too-large"

    def test_aes_without_cryptography_is_encrypted(self, monkeypatch):
        # An owner-password-only AES PDF: pypdf opens it but raises
        # DependencyError on the streams when `cryptography` is absent
        # (checked with a qpdf-built AES-256 file).
        import pypdf
        from pypdf.errors import DependencyError

        class Page:
            def extract_text(self):
                raise DependencyError("cryptography>=3.1 is required for AES algorithm")

        class Reader:
            is_encrypted = True
            pages = [Page()]

            def __init__(self, stream):
                pass

            def decrypt(self, password):
                return 2

        monkeypatch.setattr(pypdf, "PdfReader", Reader)
        with pytest.raises(ft.FulltextError) as e:
            ft.extract_pages(b"%PDF-1.7 aes")
        assert e.value.reason == "encrypted"

    def test_reuses_fetch_web_printable_floor(self):
        sys.path.insert(0, str(ROOT / "skills" / "philosophy-research" / "scripts"))
        import fetch_web
        assert ft.MIN_PRINTABLE_RATIO is fetch_web.MIN_PRINTABLE_RATIO
        assert ft._printable_ratio is fetch_web._printable_ratio


# ---------------------------------------------------------------------------
# identity_ok
# ---------------------------------------------------------------------------

DOI = "10.1111/phc3.12345"
TITLE = "Justified Harm and the Ethics of Defensive Action in War"
DOI_WORK = {"doi": DOI, "title": TITLE, "surname": "Gardner", "year": "2019"}


def page(*lines):
    return "\n".join(lines)


class TestIdentityDoi:
    def test_doi_in_page_three(self):
        pages = [page(*body()), page(*body()), page("doi: 10.1111/PHC3.12345", *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (True, "doi")

    def test_doi_prefix_forms_normalized(self):
        work = dict(DOI_WORK, doi="https://doi.org/10.1111/PHC3.12345")
        assert ft.identity_ok([page(DOI, *body())], work) == (True, "doi")

    def test_doi_must_be_whole_not_the_start_of_a_longer_one(self):
        for longer in ("10.1111/phc3.123456", "10.1111/phc3.12345.x", "10.1111/phc3.12345/abc"):
            assert ft.identity_ok([page(longer, *body())], DOI_WORK) == (False, "other_doi_page1")

    def test_doi_followed_by_a_sentence_period_still_counts(self):
        assert ft.identity_ok([page(f"See {DOI}.", *body())], DOI_WORK) == (True, "doi")

    def test_doi_only_counts_in_pages_1_to_3(self):
        pages = [page(*body())] * 3 + [page(DOI)]
        assert ft.identity_ok(pages, DOI_WORK) == (False, "no_match")

    def test_title_fallback_phrase_and_surname(self):
        pages = [page("Justified harm and the ethics of", "defensive action in war, and more"),
                 page("John Gardner", *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (True, "title")

    def test_title_fallback_needs_the_surname(self):
        pages = [page(TITLE, *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (False, "no_match")

    def test_title_fallback_needs_the_phrase_in_order(self):
        pages = [page("Defensive action in war and justified harm", "Gardner", *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (False, "no_match")

    def test_surname_must_be_a_whole_word(self):
        pages = [page(TITLE, "Gardnerson", *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (False, "no_match")

    def test_other_doi_on_page_one_rejects_the_title_fallback(self):
        pages = [page(TITLE, "Gardner", "https://doi.org/10.1007/s11098-020-01234-5", *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (False, "other_doi_page1")

    def test_citing_paper_from_the_same_journal_rejected(self):
        # Shares the first 12 DOI characters ("10.1111/phc3"): the full
        # comparison is what rejects it (idbar_nxn_fullguard.py).
        pages = [page("A Reply to Critics", "Smith", "DOI: 10.1111/phc3.12999",
                      f"Gardner's '{TITLE}' argues that...", *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (False, "other_doi_page1")

    def test_own_doi_with_trailing_punctuation_on_page_one_is_not_other(self):
        # Page 1 carries the DOI, so the DOI string accepts first; the guard
        # strips trailing .,;) before comparing.
        pages = [page(TITLE, "Gardner", f"(doi:{DOI}).", *body())]
        assert ft.identity_ok(pages, DOI_WORK) == (True, "doi")

    def test_other_doi_off_page_one_does_not_block(self):
        pages = [page(TITLE, "Gardner", *body()), page("10.1007/s11098-020-01234-5")]
        assert ft.identity_ok(pages, DOI_WORK) == (True, "title")

    def test_doi_work_does_not_fall_back_to_rule_a(self):
        # Phrase + surname on page 4 only: rule A (pages 1-5) would accept,
        # the DOI rule (pages 1-3) does not.
        pages = [page(*body())] * 3 + [page(TITLE, "Gardner")]
        assert ft.identity_ok(pages, DOI_WORK) == (False, "no_match")

    def test_doi_rule_phrase_is_not_cut_at_the_subtitle(self):
        work = dict(DOI_WORK, title="Moral Luck: Essays on Responsibility and Chance Today")
        pages = [page("Moral Luck", "Gardner", *body())]
        assert ft.identity_ok(pages, work) == (False, "no_match")
        pages = [page("Moral luck essays on responsibility and chance", "Gardner", *body())]
        assert ft.identity_ok(pages, work) == (True, "title")

    def test_empty_surname_rejects(self):
        pages = [page(TITLE, *body())]
        assert ft.identity_ok(pages, dict(DOI_WORK, surname="")) == (False, "empty_identity")


NODOI = {"doi": None, "title": "Moral Luck: Philosophical Papers 1973-1980",
         "surname": "Williams", "year": "1981"}


class TestIdentityRuleA:
    def test_phrase_cut_at_subtitle_at_head_of_page(self):
        pages = [page("Cambridge University Press"),
                 page("Moral Luck", "Bernard Williams", *body())]
        assert ft.identity_ok(pages, NODOI) == (True, "title_head")

    def test_phrase_cut_needs_two_words(self):
        assert ft.title_phrase_cut("Freedom: A Study of the Will") == "freedom a study of the will"
        assert ft.title_phrase_cut("Moral Luck: Papers") == "moral luck"
        assert ft.title_phrase_cut("Why Not? Socialism Today") == "why not"

    def test_phrase_must_start_within_600_folded_chars(self):
        # A citing document: the title sits in its references, deep in the page.
        long_body = [FILLER] * 12
        pages = [page(*long_body, "Williams, B. Moral Luck. Cambridge, 1981.")]
        assert ft.identity_ok(pages, NODOI) == (False, "no_match")

    def test_boundary_599_vs_600(self):
        lead = "x" * 598   # fold keeps it; "x"*598 + " " puts the phrase at 599
        ok = [page(lead + " moral luck williams")]
        assert ft.fold(ok[0]).find("moral luck") == 599
        assert ft.identity_ok(ok, NODOI)[0] is True
        bad = [page("x" * 599 + " moral luck williams")]
        assert ft.fold(bad[0]).find("moral luck") == 600
        assert ft.identity_ok(bad, NODOI)[0] is False

    def test_surname_must_be_on_the_same_page(self):
        pages = [page("Moral Luck", *body()), page("Bernard Williams", *body())]
        assert ft.identity_ok(pages, NODOI) == (False, "no_match")

    def test_only_pages_1_to_5(self):
        pages = [page(*body())] * 5 + [page("Moral Luck", "Williams")]
        assert ft.identity_ok(pages, NODOI) == (False, "no_match")
        pages = [page(*body())] * 4 + [page("Moral Luck", "Williams")]
        assert ft.identity_ok(pages, NODOI) == (True, "title_head")

    def test_empty_title_rejects(self):
        assert ft.identity_ok([page("Williams")], dict(NODOI, title="")) == (False, "empty_identity")


# ---------------------------------------------------------------------------
# confirm_pages
# ---------------------------------------------------------------------------

def numbered(printed, n_body=4, where="footer"):
    lines = body(n_body)
    if printed is None:
        return page(*lines)
    return page(*(lines + [str(printed)] if where == "footer" else [str(printed)] + lines))


class TestConfirmPages:
    def test_range_start_matches_footers(self):
        pages = [numbered(p) for p in range(899, 905)]
        pm = ft.confirm_pages(pages, "899--904")
        assert pm.numbers == (899, 900, 901, 902, 903, 904)

    def test_through_real_pdf_extraction(self):
        data = make_pdf([body() + [str(p)] for p in range(899, 903)])
        pm = ft.confirm_pages(ft.extract_pages(data), "899-902")
        assert pm.numbers == (899, 900, 901, 902)

    def test_front_matter_cover_page(self):
        pages = [page("Downloaded from a repository", *body())] + [numbered(p) for p in range(45, 50)]
        pm = ft.confirm_pages(pages, "45-49")
        assert pm.numbers == (None, 45, 46, 47, 48, 49)

    def test_start_beyond_the_first_six_indices_confirms_nothing(self):
        pages = [page(*body())] * 6 + [numbered(p) for p in range(10, 20)]
        assert ft.confirm_pages(pages, "10-19") is None

    def test_unnumbered_page_inside_gets_none(self):
        pages = [numbered(p) if p != 902 else numbered(None) for p in range(899, 905)]
        pm = ft.confirm_pages(pages, "899-904")
        assert pm.numbers == (899, 900, 901, None, 903, 904)

    def test_page_inserted_mid_document_shifts_no_number(self):
        # An inserted unnumbered page shifts the tail: the tail's printed
        # numbers no longer equal index + c, so it gets no number, never a
        # wrong one.
        pages = [numbered(p) for p in (899, 900, 901, 902)] + [numbered(None), numbered(903)]
        pm = ft.confirm_pages(pages, "899-904")
        assert pm.numbers == (899, 900, 901, 902, None, None)

    def test_dissenting_page_gets_none(self):
        pages = [numbered(p) for p in range(899, 905)]
        pages[3] = numbered(2019)   # a year in the footer, not the page
        pm = ft.confirm_pages(pages, "899-904")
        assert pm.numbers[3] is None and pm.numbers[2] == 901

    def test_below_sixty_percent_is_none(self):
        pages = [numbered(899), numbered(900)] + [numbered(None)] * 4
        assert ft.confirm_pages(pages, "899-904") is None

    def test_fewer_than_three_pages_is_none(self):
        assert ft.confirm_pages([numbered(5), numbered(6)], "5-6") is None

    def test_other_version_pages_disagree(self):
        # An online-first or preprint copy printed from 1; the bib says 899.
        pages = [numbered(p) for p in range(1, 7)]
        assert ft.confirm_pages(pages, "899-904") is None

    def test_article_number_with_printing_from_one(self):
        pages = [numbered(p) for p in range(1, 7)]
        assert ft.confirm_pages(pages, "e12345").numbers == (1, 2, 3, 4, 5, 6)
        assert ft.confirm_pages(pages, "102345").numbers == (1, 2, 3, 4, 5, 6)
        assert ft.confirm_pages(pages, "e1234").numbers == (1, 2, 3, 4, 5, 6)

    def test_short_no_range_value_is_a_one_page_item(self):
        # "7" (a one-page item) vs a preprint printed from 1: confirms nothing.
        pages = [numbered(p) for p in range(1, 7)]
        assert ft.confirm_pages(pages, "7") is None
        assert ft.confirm_pages(pages, "1234") is None
        assert ft.confirm_pages(pages, "e123") is None

    def test_no_pages_field_is_none(self):
        pages = [numbered(p) for p in range(1, 7)]
        assert ft.confirm_pages(pages, "") is None
        assert ft.confirm_pages(pages, None) is None

    def test_header_numbers_count(self):
        pages = [numbered(p, where="header") for p in range(20, 26)]
        assert ft.confirm_pages(pages, "20-25").numbers == tuple(range(20, 26))

    def test_numbers_in_the_middle_do_not_vote(self):
        pages = [page(*(body(4) + [str(p)] + body(4))) for p in range(20, 26)]
        assert ft.confirm_pages(pages, "20-25") is None

    def test_page_maps_compare_by_numbers(self):
        assert ft.PageMap((1, None)) == ft.PageMap((1, None))
        assert ft.PageMap((1, None)) != ft.PageMap((1, 2))


# ---------------------------------------------------------------------------
# render_text and the text helpers
# ---------------------------------------------------------------------------

class TestRender:
    def test_markers_page_and_one_based_sheet(self):
        text = ft.render_text(["cover", "alpha", "beta"], ft.PageMap((None, 12, 13)))
        assert text == "[[sheet 1]]\ncover\n[[page 12]]\nalpha\n[[page 13]]\nbeta\n"

    def test_no_page_map_is_all_sheets(self):
        assert ft.render_text(["a", "b"], None) == "[[sheet 1]]\na\n[[sheet 2]]\nb\n"

    def test_extracted_marker_lines_are_escaped(self):
        text = ft.render_text(["[[page 5]] forged\n  [[sheet 2]]\nok [[x]]"], None)
        assert ft.MARKER_RE.findall(text) == [("sheet", "1")]
        assert "[ [page 5]] forged" in text and "  [ [sheet 2]]" in text and "ok [[x]]" in text

    def test_fullwidth_brackets_cannot_forge_a_marker(self):
        text = ft.render_text(["［［page 9］］"], None)
        assert ft.MARKER_RE.findall(text) == [("sheet", "1")]

    def test_hyphenation_joined_only_before_lowercase(self):
        text = ft.render_text(["philo- \nsophy and non-\nEuropean and 1990-\nnow"], None)
        assert "philosophy" in text
        assert "non-\nEuropean" in text
        assert "1990-\nnow" in text

    def test_ligatures_normalized(self):
        assert "find the flow" in ft.render_text(["ﬁnd the ﬂow"], None)

    def test_carriage_returns_become_newlines(self):
        assert "\r" not in ft.render_text(["a\r\nb\rc"], None)

    def test_page_map_length_mismatch(self):
        with pytest.raises(ValueError):
            ft.render_text(["a", "b"], ft.PageMap((1,)))

    def test_page_map_from_text_round_trip(self):
        pm = ft.PageMap((None, 12, None, 14))
        text = ft.render_text(["a", "b", "c", "d"], pm)
        assert ft.page_map_from_text(text) == pm
        assert ft.page_map_from_text(ft.render_text(["a"], None)) is None


class TestTextHash:
    def test_hash_is_sha256_of_utf8(self):
        assert ft.text_sha256("é\n") == hashlib.sha256("é\n".encode("utf-8")).hexdigest()

    def test_hash_stable_through_crlf_round_trip(self, tmp_path):
        text = ft.render_text(["Café one\nline two", "page two"], ft.PageMap((3, 4)))
        p = tmp_path / "x.txt"
        with open(p, "w", encoding="utf-8", newline="\r\n") as f:   # a Windows checkout
            f.write(text)
        assert b"\r\n" in p.read_bytes()
        assert ft.file_text_sha256(p) == ft.text_sha256(text)

    def test_atomic_write_leaves_no_tmp_and_uses_lf(self, tmp_path):
        p = tmp_path / "s.txt"
        ft.write_text_atomic(p, "a\nb\n")
        assert p.read_bytes() == b"a\nb\n"
        assert not (tmp_path / "s.txt.tmp").exists()
        assert ft.read_text(p) == "a\nb\n"


# ---------------------------------------------------------------------------
# slugs, canonical identity, path budget
# ---------------------------------------------------------------------------

class TestSlug:
    def test_doi_punctuation_pair_differs(self):
        a = ft.slug_for({"doi": "10.1/a+b"})
        b = ft.slug_for({"doi": "10.1/a_b"})
        assert a.startswith("doi-10.1_a_b-") and b.startswith("doi-10.1_a_b-")
        assert a != b

    def test_shared_title_words_differ(self):
        a = ft.slug_for({"doi": None, "title": "Moral Luck and Agency", "surname": "Williams", "year": "1981"})
        b = ft.slug_for({"doi": None, "title": "Moral Luck Revisited", "surname": "Williams", "year": "1981"})
        assert a.startswith("t-williams-1981-moral-luck-") and b.startswith("t-williams-1981-moral-luck-")
        assert a != b

    def test_hash_is_of_the_canonical_identity(self):
        ident = {"doi": "https://doi.org/10.1/ABC"}
        assert ft.canonical_identity(ident) == "doi:10.1/abc"
        h = hashlib.sha256(b"doi:10.1/abc").hexdigest()[:12]
        assert ft.slug_for(ident) == f"doi-10.1_abc-{h}"

    def test_no_doi_canonical_form(self):
        ident = {"doi": "", "title": "Moral Luck: Papers", "surname": "Van Fraassen", "year": 1981}
        assert ft.canonical_identity(ident) == "t:moral luck papers|van fraassen|1981"
        assert ft.slug_for(ident).startswith("t-van_fraassen-1981-moral-luck-")

    def test_no_doi_needs_title_surname_year(self):
        with pytest.raises(ValueError):
            ft.canonical_identity({"doi": None, "title": "X", "surname": "", "year": "2000"})

    def test_long_values_cut_to_64_keeping_the_hash(self):
        d = ft.slug_for({"doi": "10.1234/" + "abcdefghij" * 20})
        t = ft.slug_for({"doi": None, "title": "Supercalifragilisticexpialidocious " * 4,
                         "surname": "Wolfeschlegelsteinhausenbergerdorff", "year": "2001"})
        for s in (d, t):
            assert len(s) <= 64
            assert ft.SLUG_RE.match(s)
        canon = ft.canonical_identity({"doi": "10.1234/" + "abcdefghij" * 20})
        assert d.endswith(hashlib.sha256(canon.encode()).hexdigest()[:12])

    def test_trailing_dot_stripped(self):
        # The readable part is cut at 51 characters ("doi-" + 47); put a dot
        # at the cut.
        doi = "10.1234/" + "a" * 38 + "." + "b" * 20
        readable = ("doi-" + doi)[:51]
        assert readable.endswith(".")
        s = ft.slug_for({"doi": doi})
        assert not s[:-13].endswith(".")
        assert ft.slug_for({"doi": "10.1/abc."}).startswith("doi-10.1_abc-")

    def test_path_budget_boundary(self):
        fixed = len("/intermediate_files/fulltext/") + 64 + len(".json.tmp")
        ok = "/" + "w" * (ft.WINDOWS_PATH_LIMIT - fixed - 1)
        assert len(ok) + fixed == ft.WINDOWS_PATH_LIMIT
        assert ft.path_budget_ok(ok) is True
        assert ft.path_budget_ok(ok + "w") is False

    def test_window_limit_is_workdirs(self):
        import workdir
        assert ft.WINDOWS_PATH_LIMIT == workdir.WINDOWS_PATH_LIMIT


# ---------------------------------------------------------------------------
# validate_record
# ---------------------------------------------------------------------------

def write_record(d: Path, identity, pdf=b"%PDF-1.4 fake", **over):
    stem = ft.slug_for(identity)
    (d / f"{stem}.pdf").write_bytes(pdf)
    side = {"schema": 1, "slug": stem, "identity": identity, "source": "user",
            "source_ref": "/tmp/x.pdf", "license": None,
            "pdf_sha256": hashlib.sha256(pdf).hexdigest(), "acquired_at": "2026-10-22T00:00:00+00:00"}
    side.update(over)
    (d / f"{stem}.json").write_text(json.dumps(side), encoding="utf-8")
    return stem


IDENT = {"doi": "10.1/abc", "title": "T", "surname": "S", "year": "2000"}


class TestValidateRecord:
    def test_valid(self, tmp_path):
        stem = write_record(tmp_path, IDENT)
        rec = ft.validate_record(tmp_path, stem)
        assert isinstance(rec, ft.Record)
        assert rec.pdf_path == tmp_path / f"{stem}.pdf"
        assert rec.txt_path == tmp_path / f"{stem}.txt"
        assert rec.identity["doi"] == "10.1/abc"

    def test_bad_slug_grammar_never_touches_the_path(self, tmp_path):
        assert ft.validate_record(tmp_path, "../etc/passwd") == "bad_slug"
        assert ft.validate_record(tmp_path, "doi-x") == "bad_slug"

    def test_sidecar_slug_differs_from_stem(self, tmp_path):
        stem = write_record(tmp_path, IDENT, slug="doi-10.1_abd-000000000000")
        assert ft.validate_record(tmp_path, stem) == "bad_slug"

    def test_identity_edited_after_acquisition(self, tmp_path):
        stem = write_record(tmp_path, IDENT)
        side = json.loads((tmp_path / f"{stem}.json").read_text(encoding="utf-8"))
        side["identity"]["doi"] = "10.1/other"
        (tmp_path / f"{stem}.json").write_text(json.dumps(side), encoding="utf-8")
        assert ft.validate_record(tmp_path, stem) == "bad_slug"

    def test_sidecar_missing_or_broken(self, tmp_path):
        stem = ft.slug_for(IDENT)
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"
        (tmp_path / f"{stem}.json").write_text("{not json", encoding="utf-8")
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"

    def test_wrong_schema_or_missing_key(self, tmp_path):
        stem = write_record(tmp_path, IDENT, schema=2)
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"
        write_record(tmp_path, IDENT, schema=True)
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"
        write_record(tmp_path, IDENT)
        side = json.loads((tmp_path / f"{stem}.json").read_text(encoding="utf-8"))
        del side["acquired_at"]
        (tmp_path / f"{stem}.json").write_text(json.dumps(side), encoding="utf-8")
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"

    def test_doi_only_identity_is_valid(self, tmp_path):
        ident = {"doi": "10.1/abc", "title": None, "surname": None, "year": None}
        stem = write_record(tmp_path, ident)
        assert stem == ft.slug_for(IDENT)
        assert isinstance(ft.validate_record(tmp_path, stem), ft.Record)

    def test_no_doi_identity_needs_title_surname_year(self, tmp_path):
        good = {"doi": None, "title": "Moral Luck", "surname": "Williams", "year": "1981"}
        stem = write_record(tmp_path, good)
        assert isinstance(ft.validate_record(tmp_path, stem), ft.Record)
        side = json.loads((tmp_path / f"{stem}.json").read_text(encoding="utf-8"))
        side["identity"]["year"] = None
        (tmp_path / f"{stem}.json").write_text(json.dumps(side), encoding="utf-8")
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"

    @pytest.mark.parametrize("field,value", [
        ("schema", "1"), ("schema", None), ("schema", 1.0), ("schema", [1]),
        ("slug", None), ("slug", 7), ("slug", ["x"]), ("slug", {}),
        ("identity", None), ("identity", []), ("identity", "x"),
        ("source", []), ("source", {}), ("source", None), ("source", 3), ("source", "web"),
        ("source_ref", []), ("source_ref", 5), ("source_ref", True),
        ("license", []), ("license", {}), ("license", 4),
        ("pdf_sha256", None), ("pdf_sha256", []), ("pdf_sha256", 12), ("pdf_sha256", "ABC"),
        ("acquired_at", None), ("acquired_at", []), ("acquired_at", 20261022),
    ])
    def test_malformed_field_is_sidecar_unreadable(self, tmp_path, field, value):
        stem = write_record(tmp_path, IDENT)
        side = json.loads((tmp_path / f"{stem}.json").read_text(encoding="utf-8"))
        side[field] = value
        (tmp_path / f"{stem}.json").write_text(json.dumps(side), encoding="utf-8")
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"

    @pytest.mark.parametrize("key,value", [
        ("doi", []), ("doi", 10), ("doi", {}),
        ("title", []), ("title", 3), ("surname", {}), ("surname", 1),
        ("year", []), ("year", True), ("year", {}), ("year", 1.5),
    ])
    def test_malformed_identity_value_is_sidecar_unreadable(self, tmp_path, key, value):
        stem = write_record(tmp_path, IDENT)
        side = json.loads((tmp_path / f"{stem}.json").read_text(encoding="utf-8"))
        side["identity"][key] = value
        (tmp_path / f"{stem}.json").write_text(json.dumps(side), encoding="utf-8")
        assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"

    def test_non_object_json_is_sidecar_unreadable(self, tmp_path):
        stem = ft.slug_for(IDENT)
        for raw in ("[]", "null", "3", '"x"', "[" * 100000):
            (tmp_path / f"{stem}.json").write_text(raw, encoding="utf-8")
            assert ft.validate_record(tmp_path, stem) == "sidecar_unreadable"

    def test_pdf_missing(self, tmp_path):
        stem = write_record(tmp_path, IDENT)
        (tmp_path / f"{stem}.pdf").unlink()
        assert ft.validate_record(tmp_path, stem) == "pdf_missing"

    def test_pdf_hash_mismatch(self, tmp_path):
        stem = write_record(tmp_path, IDENT)
        (tmp_path / f"{stem}.pdf").write_bytes(b"%PDF-1.4 tampered")
        assert ft.validate_record(tmp_path, stem) == "pdf_hash_mismatch"


# ---------------------------------------------------------------------------
# locate_quote and span_pages
# ---------------------------------------------------------------------------

def rendered(pages, numbers=None):
    return ft.render_text(pages, ft.PageMap(tuple(numbers)) if numbers else None)


SRC = ["The problem of justified harm is distinct from\nthe problem of justified action, "
       "as the argument shows.",
       "a second page where the argument continues with “scare quotes” and Smith’s view."]


class TestLocateQuote:
    def test_offsets_point_into_rendered_text(self):
        text = rendered(SRC)
        spans = ft.locate_quote("justified harm is distinct", text)
        (a, b), = spans
        assert text[a:b] == "justified harm is distinct"

    def test_whitespace_and_line_breaks_collapsed(self):
        text = rendered(SRC)
        (a, b), = ft.locate_quote("distinct from the problem", text)
        assert text[a:b] == "distinct from\nthe problem"

    def test_not_in_text(self):
        assert ft.locate_quote("justified harm is identical", rendered(SRC)) is None

    def test_first_character_case_free_rest_kept(self):
        text = rendered(SRC)
        assert ft.locate_quote("Problem of justified harm", text) is not None
        assert ft.locate_quote("problem of Justified harm", text) is None

    def test_page_spanning_quote(self):
        text = rendered(SRC, [899, 900])
        spans = ft.locate_quote("as the argument shows. a second page where", text)
        assert spans is not None
        assert ft.span_pages(text, spans) == [("page", 899), ("page", 900)]

    def test_span_pages_single_page_and_sheet(self):
        text = rendered(["cover blurb text here"] + SRC, [None, 899, 900])
        assert ft.span_pages(text, ft.locate_quote("scare quotes", text)) == [("page", 900)]
        assert ft.span_pages(text, ft.locate_quote("cover blurb text", text)) == [("sheet", 1)]

    def test_curly_and_straight_quotes_unified(self):
        text = rendered(SRC)
        assert ft.locate_quote("with \"scare quotes\" and Smith's view", text) is not None
        assert ft.locate_quote("with 'scare quotes' and Smith’s view", text) is not None

    def test_dash_family_unified(self):
        text = rendered(["the view — so called — is wrong"])
        assert ft.locate_quote("the view - so called - is wrong", text) is not None

    def test_line_broken_compound_matches(self):
        # Rendered "self-\nknowledge" is joined to "selfknowledge"; the quote's
        # hyphen between letters is dropped too.
        text = rendered(["a theory of self-\nknowledge and non-\nEuropean thought"])
        assert "selfknowledge" in text
        assert ft.locate_quote("theory of self-knowledge", text) is not None
        assert ft.locate_quote("and non-European thought", text) is not None

    def test_ligature_and_decomposed_accent(self):
        text = rendered(["we ﬁnd that Café society"])
        assert ft.locate_quote("we find that Café society", text) is not None

    def test_bracket_letter_replaces_the_source_letter(self):
        text = rendered(SRC)
        (a, b), = ft.locate_quote("[T]he problem of justified action", text)
        assert text[a:b] == "the problem of justified action"
        assert ft.locate_quote("the problem of justified harm [I]s distinct", text) is not None

    def test_bracket_letter_never_inserts(self):
        text = rendered(["and he said that it was so"])
        assert ft.locate_quote("[T]he said that", text) is None

    def test_bracket_word_fails_as_bracket(self):
        with pytest.raises(ft.QuoteBracketError):
            ft.locate_quote("[Not] distinct from", rendered(SRC))
        with pytest.raises(ft.QuoteBracketError):
            ft.locate_quote("justified harm ] distinct", rendered(SRC))

    def test_ellipsis_parts_in_order(self):
        text = rendered(SRC)
        for e in ("...", ". . .", "…"):
            spans = ft.locate_quote(f"problem of justified harm {e} as the argument shows", text)
            assert spans is not None and len(spans) == 2
            assert spans[0][1] <= spans[1][0]
        assert ft.locate_quote("as the argument shows ... problem of justified harm", text) is None

    def test_bracketed_ellipsis_is_an_ellipsis(self):
        text = rendered(SRC)
        for e in ("[...]", "[\u2026]", "[. . .]"):
            spans = ft.locate_quote(f"problem of justified harm {e} as the argument shows", text)
            assert spans is not None and len(spans) == 2

    def test_source_brackets_quoted_literally_pass(self):
        text = rendered(["the point, as argued in [1] above, is an objection to it"])
        assert ft.locate_quote("as argued in [1] above", text) is not None
        with pytest.raises(ft.QuoteBracketError):
            ft.locate_quote("[Not] an objection", text)
        with pytest.raises(ft.QuoteBracketError):
            ft.locate_quote("as argued in [2] above", text)

    def test_ellipsis_part_needs_three_words(self):
        with pytest.raises(ft.QuoteEllipsisError):
            ft.locate_quote("problem of justified harm ... the argument", rendered(SRC))

    def test_form_errors_share_a_base_with_reasons(self):
        for quote, reason in (("[Not] distinct from", "bracket"),
                              ("problem of justified harm ... the argument", "ellipsis")):
            with pytest.raises(ft.QuoteFormError) as e:
                ft.locate_quote(quote, rendered(SRC))
            assert e.value.reason == reason

    def test_leading_and_trailing_ellipsis(self):
        text = rendered(SRC)
        assert ft.locate_quote("... the problem of justified action ...", text) is not None

    def test_ellipsis_window(self):
        far = ["alpha beta gamma delta " + "filler " * 400 + "epsilon zeta eta theta"]
        text = rendered(far)
        assert ft.locate_quote("alpha beta gamma ... epsilon zeta eta", text) is None
        near = ["alpha beta gamma delta " + "filler " * 100 + "epsilon zeta eta theta"]
        assert ft.locate_quote("alpha beta gamma ... epsilon zeta eta", rendered(near)) is not None

    def test_trailing_period_or_comma_inside_the_quote(self):
        text = rendered(SRC)
        assert ft.locate_quote("justified harm is distinct.", text) is not None
        assert ft.locate_quote("justified harm is distinct,", text) is not None

    def test_marker_text_does_not_match(self):
        text = rendered(SRC, [899, 900])
        assert ft.locate_quote("page 900", text) is None

    def test_cover_page_of_a_confirmed_pdf_not_quotable(self):
        pages = ["A brilliant book, says the blurb on the cover"] + SRC
        pm = ft.PageMap((None, 899, 900))
        text = ft.render_text(pages, pm)
        assert ft.locate_quote("brilliant book, says the blurb", text, pm) is None
        assert ft.locate_quote("brilliant book, says the blurb", text, None) is not None
        assert ft.locate_quote("problem of justified harm", text, pm) is not None

    def test_trailing_appended_material_not_quotable(self):
        pages = SRC + ["an appended advertisement for other books"]
        pm = ft.PageMap((899, 900, None))
        text = ft.render_text(pages, pm)
        assert ft.locate_quote("appended advertisement for", text, pm) is None
        assert ft.locate_quote("appended advertisement for", text, ft.page_map_from_text(text)) is None

    def test_unconfirmed_page_between_confirmed_ones_is_quotable(self):
        pages = SRC[:1] + ["a full page figure caption here"] + SRC[1:]
        pm = ft.PageMap((899, None, 901))
        text = ft.render_text(pages, pm)
        spans = ft.locate_quote("full page figure caption", text, pm)
        assert ft.span_pages(text, spans) == [("sheet", 2)]

    def test_quote_across_a_footer_number_line(self):
        pm = ft.PageMap((899, 900))
        text = ft.render_text(["body of the page ends with these\nfinal words of it\n899",
                               "- 900 -\nand the next page goes on here\nmore body"], pm)
        spans = ft.locate_quote("final words of it and the next page goes on", text, pm)
        assert spans is not None
        assert ft.span_pages(text, spans) == [("page", 899), ("page", 900)]

    def test_quote_across_a_running_head(self):
        head = "Journal of Applied Philosophy Vol. 12"
        pages = [f"{head}\nopening body text\nthe argument runs on to",
                 f"{head}\nthe very next page here\nmiddle body",
                 f"{head}\nthird page body text\nend"]
        text = ft.render_text(pages, None)
        assert ft.locate_quote("the argument runs on to the very next page", text) is not None

    def test_page_number_inside_a_long_edge_line_is_not_furniture(self):
        pm = ft.PageMap((899, 900))
        long_line = "the court cited 899 earlier cases in a ruling that ran to many words here"
        text = ft.render_text([f"body before\n{long_line}\nlast words here", "next page"], pm)
        assert ft.locate_quote("body before last words here", text, pm) is None

    def test_body_line_with_a_number_is_not_skipped(self):
        pm = ft.PageMap((899, 900))
        text = ft.render_text(["the page ends with these words",
                               "In 1999 the court ruled\nthat the claim was void\nmore\nbody\ntext\nhere\nend"], pm)
        assert ft.locate_quote("ends with these words that the claim was void", text, pm) is None
        assert ft.locate_quote("ends with these words In 1999 the court ruled", text, pm) is not None
        # A middle (non-edge) digits-only line is body, never furniture.
        text2 = ft.render_text(["a\nb\nc\nthe sum is\n42\nexactly so\nd\ne\nf"], None)
        assert ft.locate_quote("the sum is exactly so", text2) is None

    def test_furniture_inside_a_page_is_never_skipped(self):
        # "not" repeats as an edge line on 3 pages (rule c) and "42" is
        # digits-only (rule a), but neither sits at a page break.
        pages = [f"Consent is\n{mid}\nrequired" for mid in ("not", "not", "not")]
        text = ft.render_text(pages, None)
        assert ft.locate_quote("Consent is required", text) is None
        text = ft.render_text(["Consent is\n42\nrequired"], None)
        assert ft.locate_quote("Consent is required", text) is None

    def test_body_line_with_the_page_number_is_not_spliced_out(self):
        pm = ft.PageMap((1847, 1848))
        for first in ("As 1848 revolutions swept Europe, Marx",
                      "As revolutions swept Europe in 1848 and 1849, Marx and his allies wrote"):
            text = ft.render_text(["the old order held firm until",
                                   f"{first}\nwrote the manifesto\nmore body"], pm)
            assert ft.locate_quote("held firm until wrote the manifesto", text, pm) is None
        text = ft.render_text(["the old order held firm until",
                               "body\nAs 1848 revolutions swept Europe, Marx\nwrote the manifesto\nx\ny\nz"], pm)
        assert ft.locate_quote("Europe, Marx wrote", text, pm) is not None
        assert ft.locate_quote("body wrote the manifesto", text, pm) is None

    def test_running_head_with_number_at_break(self):
        pm = ft.PageMap((899, 900))
        text = ft.render_text(["the claim is that\n899 Journal of Ethics",
                               "Journal of Ethics 900\nharm differs from action\nbody"], pm)
        assert ft.locate_quote("the claim is that harm differs from action", text, pm) is not None

    def test_all_occurrences(self):
        text = rendered(["the same words here", "and the same words here again"])
        found = ft.locate_quote_all("the same words here", text)
        assert len(found) == 2
        assert ft.span_pages(text, found[1]) == [("sheet", 2)]

    def test_page_map_must_match_markers(self):
        text = rendered(SRC, [899, 900])
        with pytest.raises(ValueError):
            ft.locate_quote("problem", text, ft.PageMap((899, 900, 901)))


# ---------------------------------------------------------------------------
# A real PDF, and loading by path
# ---------------------------------------------------------------------------

REAL_PDF = ROOT / "reviews" / "extended-mind-cognitive-offloading" / "cognitive-offloading-review.pdf"


def test_real_tracked_pdf():
    pages = ft.extract_pages(REAL_PDF.read_bytes())
    assert len(pages) == 25
    assert all(p.strip() for p in pages)
    assert "Extended Mind" in pages[0]
    # Its pages carry no printed numbers: nothing confirms, every page is a sheet.
    assert ft.confirm_pages(pages, "1-25") is None
    text = ft.render_text(pages, None)
    assert [k for k, _ in ft.MARKER_RE.findall(text)] == ["sheet"] * 25


def test_loads_by_path_without_pythonpath(tmp_path):
    code = (
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('m', {str(SCRIPTS / 'fulltext.py')!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "print(m.slug_for({'doi': '10.1/x'})[:10], m.WINDOWS_PATH_LIMIT)"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True,
                       text=True, env={**os.environ, "PYTHONPATH": ""})
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["doi-10.1_x", "250"]


class TestEntryIdentity:
    FIELDS = {"title": "{Justified} Harm: A Study", "author": "Gardner, John and Doe, Jane",
              "year": "2019a", "doi": "https://doi.org/10.1/ABC"}

    def test_shape_round_trips_through_json(self):
        import json
        ident = ft.entry_identity(self.FIELDS)
        assert ident["doi"] == "10.1/abc" and ident["year"] == "2019"
        assert isinstance(ident["work_key"], list)
        assert ft.identity_matches(json.loads(json.dumps(ident)), self.FIELDS)

    def test_any_part_changing_breaks_the_match(self):
        ident = ft.entry_identity(self.FIELDS)
        for change in ({"doi": "10.1/abd"}, {"doi": ""}, {"year": "2020"},
                       {"title": "Another Title"}, {"author": "Smith, John"}):
            assert not ft.identity_matches(ident, dict(self.FIELDS, **change))

    def test_doi_absent_on_both_sides_matches(self):
        fields = {k: v for k, v in self.FIELDS.items() if k != "doi"}
        assert ft.identity_matches(ft.entry_identity(fields), fields)

    def test_no_work_key_never_matches(self):
        fields = {"year": "2019"}
        assert not ft.identity_matches(ft.entry_identity(fields), fields)
        assert not ft.identity_matches(None, self.FIELDS)


def test_identity_ok_decodes_latex_in_raw_bib_values():
    work = {"doi": None, "title": "{\\\"U}ber die {Grundlagen}: Studien", "surname": "M{\\\"u}ller", "year": "1990"}
    pages = ["Über die Grundlagen\nHans Müller\n" + "body text " * 30]
    assert ft.identity_ok(pages, work) == (True, "title_head")
