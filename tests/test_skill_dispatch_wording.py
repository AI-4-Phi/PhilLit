"""Pins the literature-review skill's subagent-dispatch instructions.

History, because the wording has flipped twice with the CLI:
- Older Claude Code exposed `run_in_background` on the dispatch tool (then
  `Task`) and defaulted it to background from v2.1.198, so omitting it
  silently orphaned review agents. The fix then was "pass
  run_in_background: false explicitly".
- Claude Code 2.1.267 (measured 2026-09-10) exposes NO such parameter on
  `Agent`: every dispatch returns "Async agent launched" immediately and
  results arrive as `<task-notification>` events, several per agent. An
  orchestrator told to expect blocking calls read the immediate return as
  failure territory and split one batch into two round trips.

So the skill must be harness-neutral: pass the flag only where the tool
lists it, never invent a parameter, treat an immediate return as success,
wait for every agent's completion, and treat a repeat notification as a
no-op. These assertions guard that wording.
"""
from pathlib import Path

SKILL = (
    Path(__file__).parent.parent
    / "skills"
    / "literature-review"
    / "SKILL.md"
)
TEXT = SKILL.read_text(encoding="utf-8")


def test_flag_is_conditional_on_the_tool_listing_it():
    # Foreground is requested where the parameter exists - and only there.
    assert "run_in_background: false" in TEXT
    assert "only if the tool's parameter list includes it" in TEXT
    assert "never add a parameter the tool does not list" in TEXT


def test_no_blocking_claim():
    # The old text asserted every call "block[s] until every agent finishes";
    # on current CLIs that is false and misleads the orchestrator.
    assert "block until every agent finishes" not in TEXT
    assert "the call blocks until the agent finishes" not in TEXT
    assert "there is no separate wait step" not in TEXT


def test_immediate_return_is_success_and_repeats_are_noops():
    assert "never re-dispatch" in TEXT
    assert "task-notification" in TEXT
    # One agent can notify more than once; a repeat is recognised by task id.
    assert "more than once" in TEXT
    assert "<task-id>" in TEXT


def test_waiting_is_operationalised():
    # In the notification model "wait" means ending the turn, not polling -
    # and the expected output files are the backstop for "everyone is done".
    assert "end your turn" in TEXT
    assert "confirm every expected output file" in TEXT
    # A non-completed status is a failure to handle, not a repeat.
    assert "any status other than `completed`" in TEXT


def test_dispatch_steps_proactively_mandate_foreground():
    # Both parallel-dispatch steps (Phase 3 researchers, Phase 5 writers)
    # still carry the terse imperative at the point of dispatch, now in its
    # harness-neutral form.
    assert TEXT.count("foreground, never background") >= 2


def test_does_not_use_omit_the_parameter_phrasing():
    # The old blanket "Do NOT use run_in_background" implied omitting the
    # parameter on CLIs where omission meant background.
    assert "Do NOT use `run_in_background`" not in TEXT


def test_no_deprecated_taskoutput_wait_idiom():
    # TaskOutput is deprecated (Claude Code v2.1.203+); completion arrives as
    # notifications, not by polling.
    assert "TaskOutput" not in TEXT
