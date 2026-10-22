"""Full texts never enter git: PDFs are the user's copies (Zotero, a PDF
folder, a file handed over) and must stay local, also inside the example
reviews that `.gitignore` otherwise negates back in."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs a git checkout")


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8")


def test_no_tracked_path_is_a_full_text():
    r = _git("ls-files")
    assert r.returncode == 0
    assert [p for p in r.stdout.splitlines() if "/intermediate_files/fulltext/" in p] == []


@pytest.mark.parametrize("review", ["moral-value-diy", "some-local-review"])
def test_a_full_text_is_ignored_even_in_an_example_review(review):
    path = f"reviews/{review}/intermediate_files/fulltext/doi-10.1_x-abc123def456.pdf"
    r = _git("check-ignore", "-q", "--no-index", path)
    assert r.returncode == 0, path


def test_the_example_review_itself_stays_tracked():
    r = _git("check-ignore", "-q", "--no-index",
             "reviews/moral-value-diy/intermediate_files/json/evidence_report.json")
    assert r.returncode == 1
