"""split_delivery: the three Phase 6 deliverables (docs/ROADMAP.md, delivery item)."""
import sys
from pathlib import Path

import pytest
from pybtex.database import parse_string

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(SCRIPTS))
import fault_lines as fl  # noqa: E402
import split_delivery as sd  # noqa: E402

DEFS = {"FL1.1": "One principle or three?", "FL1.4": "Continuity or rupture with the classical tradition?"}

ENTRY = """@article{waldron2020separation,
  same_work_group = {waldron2013separation, waldron2020separation},
  abstract_source = {s2},
  abstract = {The rationale of the separation of powers.},
  author = {Waldron, Jeremy},
  title = {Separation of powers in thought and practice?},
  journal = {Revista de Direito Administrativo},
  year = {2020},
  year_suffix = {a},
  url = {https://example.org/w},
  urldate = {2026-09-10},
  venue_status = {low-visibility},
  iep_context = {An IEP passage.},
  doi = {10.12660/rda.v279.2020.82914},
  note = {
  CORE ARGUMENT: the thesis on which FL1.1 turns.

  POSITION: disaggregation; see FL1.1, FL1.4.
  },
  keywords = {separation-of-powers, XCONST, FLOW, High-modernism, FL1.1, FL1.4, AI-RELEVANT, NO-DOI, INCOMPLETE, High, EVIDENCE-ABSTRACT, METADATA\\_CLEANED: journal}
}
"""


def _entries(text):
    return parse_string(text, "bibtex").entries


def test_annotated_keywords_keep_topics_and_drop_every_verdict():
    kw = ("separation-of-powers, XCONST, FLOW, High-modernism, FL1.1, AI-RELEVANT, "
          "ROUTING-DISPUTE, NO-DOI, Medium, INCOMPLETE, no-abstract, EVIDENCE-NONE, "
          "METADATA\\_CLEANED: journal")
    assert sd.annotated_keywords(kw) == "separation-of-powers, XCONST, FLOW, High-modernism"


def test_track_keywords_keep_verdicts_and_drop_only_phase3_tokens():
    kw = "a-topic, FL1.1, AI-RELEVANT, INCOMPLETE, no-abstract, High, EVIDENCE-NONE, METADATA\\_CLEANED: journal"
    assert sd.track_keywords(kw) == "a-topic, FL1.1, AI-RELEVANT, High, EVIDENCE-NONE, METADATA\\_CLEANED: journal"


def test_track_record_drops_notes_and_keeps_every_verdict():
    out = sd.track_record_entry(ENTRY)
    e = _entries(out)["waldron2020separation"].fields
    assert "note" not in e and "CORE ARGUMENT" not in out
    for kept in ("same_work_group", "abstract_source", "year_suffix", "venue_status",
                 "urldate", "iep_context"):
        assert kept in e
    kw = e["keywords"]
    for token in ("FL1.1", "AI-RELEVANT", "EVIDENCE-ABSTRACT", "METADATA\\_CLEANED: journal"):
        assert token in kw
    assert ", High," in kw and "INCOMPLETE" not in kw


def test_annotated_substitutes_notes_strips_verdicts_and_the_eight_engine_fields():
    out = sd.annotated_entry(ENTRY, DEFS)
    e = _entries(out)["waldron2020separation"].fields
    assert "the “one principle or three?” fault line turns" in e["note"]
    assert not fl.tags_in(out)
    assert e["keywords"] == "separation-of-powers, XCONST, FLOW, High-modernism"
    for gone in ("same_work_group", "abstract_source", "year_suffix", "venue_status", "urldate"):
        assert gone not in e
    assert e["iep_context"] == "An IEP passage."          # not one of the eight (decided)
    assert e["url"] == "https://example.org/w" and e["abstract"].startswith("The rationale")


def test_a_quoted_note_is_substituted_and_re_emitted_braced():
    entry = '@book{k1,\n  title = {T},\n  year = {2020},\n  note = "POSITION: see FL1.1.",\n}\n'
    out = sd.annotated_entry(entry, DEFS)
    assert 'note = {POSITION: see the “one principle or three?” fault line.}' in out
    assert "k1" in _entries(out)


def test_a_keywords_field_that_empties_is_removed():
    entry = "@book{k1,\n  title = {T},\n  year = {2020},\n  keywords = {FL1.1, High, EVIDENCE-EXISTENCE}\n}\n"
    out = sd.annotated_entry(entry, DEFS)
    assert "keywords" not in out and "k1" in _entries(out)
    only_phase3 = "@book{k2,\n  title = {T},\n  year = {2020},\n  keywords = {INCOMPLETE}\n}\n"
    assert "keywords" not in sd.track_record_entry(only_phase3)


def test_undefined_tags_in_note_and_keywords_are_all_named():
    entry = "@book{k1,\n  title = {T},\n  year = {2020},\n  note = {see FL7.7},\n  keywords = {x, FL8.8}\n}\n"
    with pytest.raises(fl.UndefinedFaultLine) as exc:
        sd.annotated_entry(entry, DEFS)
    assert exc.value.tags == ["FL7.7", "FL8.8"]


def test_an_entry_without_notes_or_keywords_passes_through():
    entry = "@book{k1,\n  title = {T},\n  year = {2020}\n}\n"
    assert sd.track_record_entry(entry) == entry
    assert sd.annotated_entry(entry, DEFS) == entry
