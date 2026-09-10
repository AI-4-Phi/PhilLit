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
import re
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
    # An immediate acknowledgement is acceptance of the dispatch - not
    # "success", which would collide with rule 3's inline-error remedy.
    assert "means the dispatch was accepted" in TEXT
    assert "is success, not failure" not in TEXT
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


def test_rule_count_matches_the_bullets_that_follow():
    # "the same N rules hold:" is followed by exactly N bullets - a miscount
    # reads as a dropped rule to the orchestrator.
    m = re.search(r"the same (\w+) rules hold:\n((?:- .*(?:\n|$))+)", TEXT)
    assert m, "rule-count sentence missing"
    words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    stated = words.get(m.group(1)) or int(m.group(1))
    bullets = [l for l in m.group(2).splitlines() if l.startswith("- ")]
    assert stated == len(bullets)


def _sentence_around(text, start, end):
    # The sentence holding text[start:end]: back to the previous sentence
    # end (". ", ".\n") or bullet start, forward to the next sentence end.
    # A bare newline is not a boundary, so a reflowed sentence stays whole.
    lo = max(text.rfind(". ", 0, start), text.rfind(".\n", 0, start),
             text.rfind("\n- ", 0, start)) + 1
    ends = [i for i in (text.find(". ", end), text.find(".\n", end)) if i != -1]
    hi = min(ends) + 1 if ends else len(text)
    return text[lo:hi]


def test_end_turn_is_fenced_to_the_notification_model():
    # In an SDK session every dispatch returns inline and nothing re-prompts
    # the orchestrator after its turn ends; an unfenced "end your turn" at a
    # phase boundary ends the review. So: the inline converse is stated, the
    # imperative names the "Async agent launched" return it applies to, and
    # every "end ... turn" in the skill either names the notification model
    # or is negated.
    assert "If a call returned the agent's result inline, that agent is complete" in TEXT
    assert "continue in this same turn" in TEXT
    assert "never end your turn to wait for a notification that will not come" in TEXT
    # The fence is the CRITERION (no result came back), with the observed
    # acknowledgement only as its example - a harness may word the ack
    # differently and must still fall on the right side.
    assert "returned an acknowledgement without the agent's result" in TEXT
    assert "Async agent launched" in TEXT
    assert "end your turn only to let" in TEXT
    # An inline call that errored or came back empty also "has no result";
    # it must read as a failure to handle, never as a launch to wait for.
    assert "An inline error or an empty return" in TEXT
    # The classification is operational, not a string match: a return that
    # carries the agent's report IS the result.
    assert "carries the agent's report or a completion or failure status" in TEXT
    assert "a status that reports failure is that agent's failure" in TEXT
    # An acknowledgement without a task id still has to be matched to its
    # notification somehow: by the output file it names.
    assert "match its notification by the output file" in TEXT
    # The missing-file backstop names its remedy in both models.
    assert "re-dispatch that one agent, in either model" in TEXT
    hits = list(re.finditer(r"end(?:ing)? (?:your|the) turn", TEXT, re.IGNORECASE))
    assert hits
    for m in hits:
        sentence = _sentence_around(TEXT, m.start(), m.end())
        # A governing negation right before the verb, or an adjacent "only":
        # "End your turn and let the notifications arrive." must NOT pass.
        assert re.search(r"\b(?:never|not|nor)\s+end(?:ing)? (?:your|the) turn"
                         r"|end(?:ing)? (?:your|the) turn only\b", sentence, re.IGNORECASE), sentence
