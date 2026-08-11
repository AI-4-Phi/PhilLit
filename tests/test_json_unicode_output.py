"""No `\\uXXXX` escapes in the JSON researchers read.

Agents copy venue and author names out of search-result JSON as TEXT rather
than parsing it, so `ensure_ascii=True` (Python's default) puts a literal
`O\\u00f1ati Socio-legal Series` into a delivered .bib, where it is neither
valid BibTeX nor readable prose. Three such escapes reached the tracked,
publicly linked example reviews before this was fixed.

The Windows half matters as much as the escape half: stdout must be put into
UTF-8 before real characters are printed, or a cp1252 console raises
UnicodeEncodeError and the search dies instead of the name being mangled.
"""
import io
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "philosophy-research" / "scripts"))

import output  # noqa: E402


ACCENTED = {"status": "success", "results": [{"journal": "Oñati Socio-legal Series",
                                              "author": "Medina, José"}]}


def test_output_file_is_written_without_escapes(tmp_path):
    path = tmp_path / "out.json"
    assert output._write_output_file(ACCENTED, str(path), "test") is True
    raw = path.read_text(encoding="utf-8")
    assert "\\u" not in raw
    assert "José" in raw


def test_output_file_still_round_trips_as_json(tmp_path):
    path = tmp_path / "out.json"
    output._write_output_file(ACCENTED, str(path), "test")
    assert json.loads(path.read_text(encoding="utf-8")) == ACCENTED


def test_dumps_emits_real_characters_when_stdout_is_utf8(monkeypatch):
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", stream)
    assert "\\u" not in output.dumps(ACCENTED)


def test_dumps_falls_back_to_escapes_when_stdout_cannot_encode(monkeypatch):
    """A cp1252 console that refuses reconfiguration must get ASCII, not a
    UnicodeEncodeError -- a mangled name beats a crashed search."""
    class Cp1252NoReconfigure:
        encoding = "cp1252"
        def write(self, _):      # pragma: no cover - never called here
            raise AssertionError("test should not write")

    monkeypatch.setattr(sys, "stdout", Cp1252NoReconfigure())
    assert "\\u00e9" in output.dumps(ACCENTED)


def test_dumps_reconfigures_a_cp1252_stdout_that_allows_it(monkeypatch):
    calls = {}

    class Reconfigurable:
        encoding = "cp1252"
        def reconfigure(self, encoding=None):
            calls["encoding"] = encoding
            self.encoding = encoding

    monkeypatch.setattr(sys, "stdout", Reconfigurable())
    assert "\\u" not in output.dumps(ACCENTED)
    assert calls["encoding"] == "utf-8"


# The three reviews negated in .gitignore -- the only ones that ship. Scoped
# deliberately: delivered reviews are never retro-fixed (wrong-years audit,
# Johannes 2026-08-05) and the sole exception is the public examples, so
# asserting over every local review would demand fixes the doctrine forbids.
TRACKED_EXAMPLES = ("extended-mind-cognitive-offloading",
                    "metaphilosophy-literature-reviews",
                    "moral-value-diy")


@pytest.mark.parametrize("name", TRACKED_EXAMPLES)
def test_no_escapes_survive_in_the_tracked_example_bibliographies(name):
    """These are linked from the README, so an escape there is user-visible."""
    bib = REPO / "reviews" / name / "literature-all.bib"
    if not bib.is_file():
        pytest.skip(f"{name} not present in this checkout")
    text = bib.read_text(encoding="utf-8")
    assert "\\u00" not in text and "\\u3c" not in text, f"{name} carries escapes"
