"""Tests for hooks/researcher_bibs.py: which bibs a stopping researcher owns."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
from researcher_bibs import owned_bibs, transcript_paths  # noqa: E402

SCRIPT = Path(__file__).parent.parent / "hooks" / "researcher_bibs.py"


def user(content):
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}})


def tool(name, **inp):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t", "name": name, "input": inp}]}})


def test_prompt_names_the_researchers_bib():
    assert owned_bibs([user("Write output to: `/w/r/literature-domain-3.bib`")]) == {
        "literature-domain-3.bib"}


def test_prompt_as_a_list_of_text_blocks():
    assert owned_bibs([user([{"type": "text", "text": "out: literature-domain-2.bib"}])]) == {
        "literature-domain-2.bib"}


def test_only_the_first_user_record_is_the_prompt():
    # A later user record (a tool result, a resumed instruction) may name a
    # sibling's bib; it does not make the sibling's file this researcher's.
    lines = [user("Write output to: literature-domain-1.bib"),
             user("see literature-domain-2.bib for overlap")]
    assert owned_bibs(lines) == {"literature-domain-1.bib"}


def test_file_tool_writes_are_owned_and_bash_mentions_are_not():
    lines = [user("Write output to: literature-domain-1.bib"),
             tool("Edit", file_path="C:\\w\\literature-domain-4.bib"),
             tool("Write", file_path="/w/notes.md"),
             tool("Bash", command="cat /w/literature-domain-5.bib"),
             tool("Read", file_path="/w/literature-domain-6.bib")]
    assert owned_bibs(lines) == {"literature-domain-1.bib", "literature-domain-4.bib"}


def test_unparseable_and_odd_lines_are_skipped():
    lines = ["{not json", "[]", json.dumps({"type": "user"}),
             user("Write output to: literature-domain-1.bib"), '{"type": "assistant", "message": 3}']
    assert owned_bibs(lines) == {"literature-domain-1.bib"}


def test_a_glob_is_not_a_name():
    assert owned_bibs([user("never touch literature-domain-*.bib")]) == set()


def test_transcript_paths_try_the_agent_transcript_then_the_derived_one():
    assert transcript_paths({"agent_transcript_path": "/a.jsonl", "transcript_path": "/p/s1.jsonl",
                             "agent_id": "a9"}) == [Path("/a.jsonl"),
                                                    Path("/p/s1/subagents/agent-a9.jsonl")]
    assert transcript_paths({"agent_transcript_path": "", "transcript_path": "/p/s1.jsonl",
                             "agent_id": "a9"}) == [Path("/p/s1/subagents/agent-a9.jsonl")]


def test_transcript_paths_empty_without_enough_to_go_on():
    assert transcript_paths({"transcript_path": "/p/s1.jsonl"}) == []
    assert transcript_paths({}) == []


def test_cli_falls_through_to_the_derived_transcript(tmp_path):
    sub = tmp_path / "s1" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-a9.jsonl").write_text(user("Write output to: literature-domain-7.bib") + "\n",
                                        encoding="utf-8")
    out = _cli(json.dumps({"agent_transcript_path": str(tmp_path / "gone.jsonl"),
                           "transcript_path": str(tmp_path / "s1.jsonl"), "agent_id": "a9"}))
    assert out == {"bibs": ["literature-domain-7.bib"], "assigned": ["literature-domain-7.bib"]}


def _cli(stdin: str) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_cli_reports_a_reason_for_every_empty_answer(tmp_path):
    assert _cli("not json")["bibs"] == []
    assert "no transcript" in _cli("{}")["reason"]
    assert "No such file" in _cli(json.dumps({"agent_transcript_path": str(tmp_path / "x")}))["reason"]
    t = tmp_path / "t.jsonl"
    t.write_text(user("no bib here") + "\n", encoding="utf-8")
    assert "names no bib file" in _cli(json.dumps({"agent_transcript_path": str(t)}))["reason"]


def test_cli_lists_owned_bibs_sorted(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(user("Write output to: literature-domain-2.bib") + "\n"
                 + tool("Write", file_path="/w/literature-domain-1.bib") + "\n", encoding="utf-8")
    assert _cli(json.dumps({"agent_transcript_path": str(t)})) == {
        "bibs": ["literature-domain-1.bib", "literature-domain-2.bib"],
        "assigned": ["literature-domain-2.bib"]}


def test_a_sibling_mentioned_in_the_prompt_is_not_owned():
    prompt = ("Do not overlap with literature-domain-2.bib.\n"
              "Write output to: `/w/literature-domain-1.bib`")
    assert owned_bibs([user(prompt)]) == {"literature-domain-1.bib"}


def test_without_an_output_line_only_a_single_mention_counts():
    assert owned_bibs([user("your file is literature-domain-4.bib")]) == {"literature-domain-4.bib"}
    assert owned_bibs([user("literature-domain-4.bib or literature-domain-5.bib")]) == set()


def test_a_name_inside_a_longer_file_name_is_not_a_name():
    assert owned_bibs([user("Write output to: literature-domain-2.bib.bak")]) == set()
    assert owned_bibs([user("Write output to: old-literature-domain-2.bib")]) == set()
    assert owned_bibs([user("Write output to: `literature-domain-2.bib`.")]) == {
        "literature-domain-2.bib"}


def test_a_tool_input_that_is_not_an_object_is_skipped():
    bad = json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "input": "literature-domain-9.bib"}]}})
    assert owned_bibs([user("Write output to: literature-domain-1.bib"), bad]) == {
        "literature-domain-1.bib"}


def test_parsed_records_are_accepted_too():
    records = [json.loads(user("Write output to: literature-domain-1.bib")),
               json.loads(tool("Edit", file_path="/w/literature-domain-1.bib"))]
    assert owned_bibs(records) == {"literature-domain-1.bib"}


def test_output_line_variants_assign():
    for prompt in ("Write your output to /w/literature-domain-3.bib",
                   "Put the output into literature-domain-3.bib",
                   "WRITE OUTPUT TO: literature-domain-3.bib"):
        assert owned_bibs([user("Avoid literature-domain-9.bib.\n" + prompt)]) == {
            "literature-domain-3.bib"}, prompt


def test_cli_moves_on_when_the_first_transcript_names_nothing(tmp_path):
    first = tmp_path / "empty.jsonl"
    first.write_text("", encoding="utf-8")
    sub = tmp_path / "s1" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-a9.jsonl").write_text(user("Write output to: literature-domain-5.bib") + "\n",
                                        encoding="utf-8")
    out = _cli(json.dumps({"agent_transcript_path": str(first),
                           "transcript_path": str(tmp_path / "s1.jsonl"), "agent_id": "a9"}))
    assert out["bibs"] == ["literature-domain-5.bib"]
