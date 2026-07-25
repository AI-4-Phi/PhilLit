"""Tests for check_evidence.py (Phase 6 telemetry) and sanitize_bib.py
(delivered-bib sanitizer)."""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
CHECKER = SCRIPTS_DIR / "check_evidence.py"
SANITIZER = SCRIPTS_DIR / "sanitize_bib.py"

BIB = """@book{kuhn1962structure,
  author = {Kuhn, Thomas S.},
  title = {The Structure of Scientific Revolutions},
  year = {1962},
  keywords = {ps, High, EVIDENCE-EXISTENCE}
}

@misc{blog2024,
  author = {Blogger, Bea},
  title = {A Post},
  year = {2024},
  keywords = {EVIDENCE-NONE}
}

@article{ok2020,
  author = {Fine, Frank},
  title = {Good Paper},
  year = {2020},
  keywords = {EVIDENCE-ABSTRACT}
}

@article{ghost2019,
  author = {Ghost, Gia},
  title = {Unstamped},
  year = {2019},
  keywords = {tag}
}"""

BIB_NO_AUTHOR = BIB + """

@article{noauthor2021,
  title = {No Author Here},
  year = {2021},
  keywords = {EVIDENCE-NONE}
}"""

BIB_LI = """@article{li2020lit,
  author = {Li, Wei},
  title = {A Paper},
  year = {2020},
  keywords = {tag}
}"""


def _run(tmp_path, md_text, bib_text=BIB):
    (tmp_path / "r.md").write_text(md_text, encoding="utf-8")
    (tmp_path / "b.bib").write_text(bib_text, encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECKER),
                           str(tmp_path / "r.md"), str(tmp_path / "b.bib")],
                          capture_output=True, text=True)


def test_reporting_verb_on_existence_flagged(tmp_path):
    r = _run(tmp_path, "Kuhn (1962) argues that paradigms shift.")
    assert "CHECK reporting-verb: kuhn1962structure" in r.stdout
    assert r.returncode == 0  # telemetry, not enforcement


def test_existence_coverage_claim_not_flagged(tmp_path):
    r = _run(tmp_path, "This has been studied historically (Kuhn 1962).")
    assert "reporting-verb" not in r.stdout


def test_none_cited_flagged(tmp_path):
    r = _run(tmp_path, "As noted online (Blogger 2024).")
    assert "CHECK none-cited: blog2024" in r.stdout


def test_abstract_tier_with_verb_ok(tmp_path):
    r = _run(tmp_path, "Fine (2020) argues convincingly.")
    assert "reporting-verb" not in r.stdout


def test_unstamped_cited_flagged(tmp_path):
    r = _run(tmp_path, "See Ghost (2019).")
    assert "CHECK unstamped-cited: ghost2019" in r.stdout


def test_known_false_positive_documented(tmp_path):
    # verb belongs to a different clause in the same sentence -- accepted FP
    r = _run(tmp_path, "While Smith argues X, the field grew (Kuhn 1962).")
    assert "CHECK reporting-verb: kuhn1962structure" in r.stdout  # documented limitation


def test_summary_line_present(tmp_path):
    r = _run(tmp_path, "Kuhn (1962) argues that paradigms shift.")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert lines[-1].startswith("CHECK-SUMMARY: ")


def test_no_author_entry_skipped(tmp_path):
    r = _run(tmp_path, "Some prose mentioning nobody in particular.",
             bib_text=BIB_NO_AUTHOR)
    assert r.returncode == 0
    assert "noauthor2021" not in r.stdout


def test_surname_does_not_match_inside_word(tmp_path):
    r = _run(tmp_path, "The literature (2020) on this topic is thin.",
             bib_text=BIB_LI)
    assert "li2020lit" not in r.stdout


def test_sanitizer_strips_all_tokens(tmp_path):
    bib = tmp_path / "b.bib"
    bib.write_text(BIB, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SANITIZER), str(bib)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    content = bib.read_text(encoding="utf-8")
    assert "EVIDENCE-" not in content        # the delivered-artifact invariant
    assert "ps, High" in content             # other keywords intact
