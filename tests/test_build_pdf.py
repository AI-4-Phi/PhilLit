"""PL-38: the PDF build must not silently lose characters the font lacks."""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"))
import build_pdf as bp  # noqa: E402

WARN_BETA = ("[WARNING] Missing character: There is no β (U+03B2) (U+03B2) "
             "in font [lmroman10-regular]:+tlig;!\n")


def test_parse_missing_counts_by_codepoint():
    got = bp.parse_missing(WARN_BETA * 3 + "[WARNING] Missing character: There is no 中 (U+4E2D) (U+4E2D) in font x\n")
    assert got == {("β", "U+03B2"): 3, ("中", "U+4E2D"): 1}
    assert bp.parse_missing("[WARNING] unrelated\n") == {}


def _fake_run(outcomes):
    """outcomes: font -> (rc, stderr). Writes the --output file on rc 0."""
    calls = []

    def run(cmd):
        font = next((c.split("=", 1)[1] for c in cmd if c.startswith("mainfont=")), None)
        calls.append(font)
        rc, err = outcomes[font]
        if rc == 0:
            Path(cmd[cmd.index("--output") + 1]).write_text(f"pdf by {font}", encoding="utf-8")
        return rc, err
    return run, calls


def test_first_clean_font_wins_and_later_fonts_are_not_tried(tmp_path):
    run, calls = _fake_run({"A": (0, WARN_BETA), "B": (0, ""), "C": (0, "")})
    pdf = tmp_path / "r.pdf"
    font, missing = bp.build(tmp_path / "r.md", pdf, fonts=("A", "B", "C", None), run=run)
    assert (font, missing) == ("B", {})
    assert calls == ["A", "B"]
    assert pdf.read_text(encoding="utf-8") == "pdf by B"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["r.pdf"]   # no temp dir left


def test_a_font_that_fails_to_build_falls_through_to_the_default(tmp_path):
    run, calls = _fake_run({"A": (43, "! Package fontspec Error: The font cannot be found."),
                            None: (0, WARN_BETA)})
    font, missing = bp.build(tmp_path / "r.md", tmp_path / "r.pdf", fonts=("A", None), run=run)
    assert font is None and sum(missing.values()) == 1
    assert calls == ["A", None]


def test_unparsed_missing_character_is_not_clean():
    got = bp.parse_missing("Missing character: There is no x in font foo!\n")
    assert got == {("?", "unparsed"): 1}


def test_pandoc_that_cannot_start_is_a_failed_build(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("pandoc")
    monkeypatch.setattr(bp.subprocess, "run", boom)
    assert bp.run_pandoc(["pandoc"])[0] == 1
    assert bp.build(tmp_path / "r.md", tmp_path / "r.pdf", fonts=(None,)) is None


def test_keeps_the_build_with_fewest_losses(tmp_path):
    run, _ = _fake_run({"A": (0, WARN_BETA * 5), "B": (0, WARN_BETA), None: (0, WARN_BETA * 9)})
    pdf = tmp_path / "r.pdf"
    font, missing = bp.build(tmp_path / "r.md", pdf, fonts=("A", "B", None), run=run)
    assert font == "B" and pdf.read_text(encoding="utf-8") == "pdf by B"


def test_failed_builds_fall_through_and_all_failed_is_none(tmp_path):
    run, _ = _fake_run({"A": (43, "! LaTeX Error"), None: (0, "")})
    assert bp.build(tmp_path / "r.md", tmp_path / "r.pdf", fonts=("A", None), run=run)[0] is None
    run, _ = _fake_run({"A": (43, "x"), None: (43, "x")})
    assert bp.build(tmp_path / "r.md", tmp_path / "s.pdf", fonts=("A", None), run=run) is None
    assert not (tmp_path / "s.pdf").exists()


def test_main_names_lost_codepoints_in_ascii(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bp, "build", lambda md, pdf: (None, bp.parse_missing(WARN_BETA * 2)))
    assert bp.main([str(tmp_path / "r.md"), str(tmp_path / "r.pdf")]) == 0
    out = capsys.readouterr().out
    assert "Converted to PDF: r.pdf" in out
    assert "WARN pdf-missing-characters" in out and "U+03B2 x2" in out
    out.encode("ascii")


@pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("lualatex")),
                    reason="needs pandoc and lualatex")
def test_real_build_keeps_greek(tmp_path):
    md = tmp_path / "r.md"
    md.write_text("# T\n\nThe coefficient β = 0.4.\n", encoding="utf-8")
    font, missing = bp.build(md, tmp_path / "r.pdf")
    assert (tmp_path / "r.pdf").stat().st_size > 1000
    if font is not None:            # a wide-coverage font was installed
        assert missing == {}
