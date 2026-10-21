#!/usr/bin/env python3
"""Name the bib files a stopping domain researcher owns, for SubagentStop.

The SubagentStop hook used to validate and clean EVERY domain bib at every
researcher's stop. With researchers running in parallel, that rewrote bibs
other researchers were still writing, and reported the change to the wrong
researcher. This helper reads the stopping researcher's own transcript and
names its files, so the hook can scope to them.

A researcher owns the union of:
  1. its assigned output, from the dispatch prompt (the first user record of
     its transcript): the `literature-domain-*.bib` named on SKILL.md's
     Phase 3 "Write output to: `[workdir]/literature-domain-N.bib`" line
     (any line with "output to/into/at/in": the orchestrator is a model and
     may not copy the template exactly), or, when no such line names one, the prompt's one domain bib if it
     names exactly one. A prompt may mention a sibling's file ("do not
     overlap with literature-domain-2.bib"); a mention is not ownership.
  2. every `.bib` it wrote with a file tool (Write, Edit, MultiEdit).
Bash commands are not read: a researcher edits its bib through Bash only by
running scripts on its own file, which (1) already names, and a Bash mention
of a sibling's bib is a read, not ownership.

Transcript: `agent_transcript_path`, then, when that is blank or cannot be
read, `<transcript_path without .jsonl>/subagents/agent-<agent_id>.jsonl`
(the layout Claude Code writes subagent transcripts in).

Usage: python researcher_bibs.py < <SubagentStop payload JSON>
Output: one JSON object on stdout, exit 0:
  {"bibs": [<basename>, ...], "assigned": [<basename>, ...]}
                                         at least one file identified;
                                         "assigned" is part 1 alone, the
                                         file the hook reports if missing
  {"bibs": [], "reason": "<why not>"}    nothing identified; the hook then
                                         falls back to every bib, visibly
"""

import json
import re
import sys
from pathlib import Path

# A whole file name: not inside `old-literature-domain-1.bib` or
# `literature-domain-1.bib.bak`; a sentence's closing period is fine.
DOMAIN_BIB = re.compile(r"(?<![A-Za-z0-9_.-])literature-domain-[A-Za-z0-9_-]+\.bib"
                        r"(?![A-Za-z0-9_-]|\.[A-Za-z0-9])", re.IGNORECASE)
OUTPUT_LINE = re.compile(r"\boutput\s+(?:to|into|at|in)\b[^\n]*", re.IGNORECASE)
FILE_TOOLS = {"Write", "Edit", "MultiEdit"}


def transcript_paths(payload: dict) -> list[Path]:
    """Where the transcript may be, in the order to try."""
    paths = []
    agent = payload.get("agent_transcript_path")
    if isinstance(agent, str) and agent:
        paths.append(Path(agent))
    main = payload.get("transcript_path")
    agent_id = payload.get("agent_id")
    if isinstance(main, str) and main.endswith(".jsonl") and isinstance(agent_id, str) and agent_id:
        derived = Path(main[: -len(".jsonl")]) / "subagents" / f"agent-{agent_id}.jsonl"
        if derived not in paths:
            paths.append(derived)
    return paths


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def assigned_bibs(prompt: str) -> set[str]:
    on_output_lines = {n for line in OUTPUT_LINE.findall(prompt)
                       for n in DOMAIN_BIB.findall(line)}
    if on_output_lines:
        return on_output_lines
    mentioned = set(DOMAIN_BIB.findall(prompt))
    return mentioned if len({n.lower() for n in mentioned}) == 1 else set()


def owned_bibs(lines) -> set[str]:
    """Basenames named by the first user record and written by file tools.
    `lines` holds transcript JSONL lines or records already parsed (dicts);
    phillit-service imports this with its own records. Unparseable lines are
    skipped: a transcript line cut mid-write must not hide the rest."""
    assigned, written = ownership(lines)
    return assigned | written


def ownership(lines) -> tuple[set[str], set[str]]:
    """(assigned by the prompt, written with a file tool), as owned_bibs."""
    assigned: set[str] = set()
    names: set[str] = set()
    seen_prompt = False
    for line in lines:
        if isinstance(line, dict):
            rec = line
        else:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
        if not isinstance(rec, dict):
            continue
        message = rec.get("message")
        if not isinstance(message, dict):
            continue
        if rec.get("type") == "user" and not seen_prompt:
            seen_prompt = True
            assigned = assigned_bibs(_text(message.get("content")))
        elif rec.get("type") == "assistant" and isinstance(message.get("content"), list):
            for block in message["content"]:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"
                        and block.get("name") in FILE_TOOLS):
                    continue
                inp = block.get("input")
                path = inp.get("file_path") if isinstance(inp, dict) else None
                if isinstance(path, str) and path.lower().endswith(".bib"):
                    names.add(re.split(r"[\\/]", path)[-1])
    return assigned, names


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError as e:
        print(json.dumps({"bibs": [], "reason": f"the hook payload was not JSON ({e})"}))
        return
    paths = transcript_paths(payload) if isinstance(payload, dict) else []
    if not paths:
        print(json.dumps({"bibs": [], "reason": "the payload names no transcript"}))
        return
    failures = []
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                assigned, written = ownership(f)
        except OSError as e:
            failures.append(f"{e.strerror}: {path}")
            continue
        if assigned or written:
            print(json.dumps({"bibs": sorted(assigned | written), "assigned": sorted(assigned)}))
            return
        failures.append(f"names no bib file: {path}")   # a later path may hold more
    print(json.dumps({"bibs": [], "reason": "no transcript identified this researcher's bib ("
                      + "; ".join(failures) + ")"}))


if __name__ == "__main__":
    main()
