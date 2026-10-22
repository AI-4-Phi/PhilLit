"""The PDF fixture helper must give pypdf back the lines it was given, in order.

Page-map and identity tests read the first and last lines of a page and the
first characters of a page; they prove nothing unless this holds.
"""

import io
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).parent))
from pdf_fixtures import make_pdf  # noqa: E402


def _pages(data):
    return [p.extract_text() for p in PdfReader(io.BytesIO(data)).pages]


def test_lines_come_back_in_order_one_per_line():
    pages = [["Journal of Ethics 12", "A Title Here", "Body line (with parens)", "899"],
             ["900", "Second page body", "more text", "Smith"]]
    got = _pages(make_pdf(pages))
    assert [g.splitlines() for g in got] == pages


def test_encrypted_pdf_is_encrypted():
    reader = PdfReader(io.BytesIO(make_pdf([["x"]], encrypt=True)))
    assert reader.is_encrypted
