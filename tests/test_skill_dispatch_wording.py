"""Pins the literature-review skill's subagent-dispatch instructions.

Root cause of the run_in_background dispatch bug: recent Claude Code versions
default subagent dispatch to *background* execution, so the old instruction
"Do NOT use run_in_background" (i.e. omit it) silently produced background
dispatch. The fix mandates run_in_background: false explicitly and removes the
now-deprecated TaskOutput wait idiom. These assertions guard against
regressing the wording.
"""
from pathlib import Path

SKILL = (
    Path(__file__).parent.parent
    / "skills"
    / "literature-review"
    / "SKILL.md"
)
TEXT = SKILL.read_text(encoding="utf-8")


def test_mandates_explicit_foreground_dispatch():
    # The dispatch tool defaults to background on recent CLIs; foreground must
    # be requested explicitly, not by omission.
    assert "run_in_background: false" in TEXT


def test_does_not_use_omit_the_parameter_phrasing():
    # The old blanket "Do NOT use run_in_background" implied omitting the
    # parameter, which no longer yields foreground behaviour.
    assert "Do NOT use `run_in_background`" not in TEXT


def test_no_deprecated_taskoutput_wait_idiom():
    # TaskOutput is deprecated (Claude Code v2.1.203+) and is a background-task
    # idiom that contradicts the foreground-batched execution model.
    assert "TaskOutput" not in TEXT
