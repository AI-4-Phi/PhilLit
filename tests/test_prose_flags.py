"""Every CLI flag named in boundary-crossing prose must exist in the named
script's argparse definition.

The defect class (four instances found and fixed 2026-08-07, plus the
service-filed planner `--recent`): skill/agent prose is vendored into every
user workspace, and a flag the script does not accept makes the documented
invocation exit non-zero — the planner followed the bogus `--recent`
instruction in 44 of 44 stored service plans. The service's filing
(`engine-planner-recent-flag.md`) proposed exactly this gate.

Method and known limits (deliberate 80/20 — static, hermetic, no uv spawn):

- Association is LINE-scoped (after joining backslash continuations): a flag
  is checked against the script(s) named on its own line. Flags on lines
  naming no script (e.g. pandoc/jq commands, generic prose) are not checked.
- A line naming SEVERAL scripts checks each flag against their UNION, so a
  flag valid for any named script passes. That is what let the original
  "search_arxiv.py or s2_search.py with --recent flag" slip: prefer prose
  that puts each flag adjacent to exactly one script.
- Flags are extracted from literal `add_argument("--x", ...)` calls, plus one
  repo convention: `add_output_arg(parser)` (from `output.py`) contributes
  `--output`. A new shared flag-adding helper needs a line here.
- Positional arguments and required-ness are NOT validated; only flag names.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

PROSE_FILES = sorted((REPO_ROOT / "agents").glob("*.md")) + sorted(
    (REPO_ROOT / "skills").rglob("SKILL.md")
)
SCRIPTS = {
    p.name: p
    for d in ("skills", "hooks")
    for p in (REPO_ROOT / d).rglob("*.py")
    if "__pycache__" not in p.parts
}

_SCRIPT_TOKEN = re.compile(r"[\w<>-]+\.py")
_FLAG_TOKEN = re.compile(r"(?<![\w-])(--[A-Za-z][\w-]*)")
_ADD_ARGUMENT = re.compile(r"add_argument\(([^)]*)\)")
_ARG_STRING = re.compile(r"""['"](--?[A-Za-z][\w-]*)['"]""")


def _joined_lines(path):
    """Yield (first_lineno, logical_line) with backslash continuations joined."""
    buf, start = "", 0
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not buf:
            start = lineno
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        yield start, buf + line
        buf = ""


def _argparse_flags(script_path):
    text = script_path.read_text(encoding="utf-8")
    flags = set()
    for call in _ADD_ARGUMENT.findall(text):
        flags.update(_ARG_STRING.findall(call))
    if re.search(r"\badd_output_arg\(", text):
        flags.add("--output")
    return flags


def _prose_references():
    """Yield (prose_path, lineno, script_names, prose_flags) per logical line.

    Placeholder tokens like `<script>.py` are skipped, not treated as names.
    """
    for prose in PROSE_FILES:
        for lineno, line in _joined_lines(prose):
            flags = _FLAG_TOKEN.findall(line)
            if not flags:
                continue
            names = [
                t for t in _SCRIPT_TOKEN.findall(line) if "<" not in t and ">" not in t
            ]
            if names:
                yield prose, lineno, names, flags


def test_prose_files_and_scripts_found():
    assert PROSE_FILES, "expected agent/skill prose files"
    assert len(SCRIPTS) > 30, "script index implausibly small — glob broken?"
    assert any(True for _ in _prose_references()), (
        "extraction found no script+flag lines at all — the regexes have "
        "rotted, and the flag test below would pass vacuously"
    )


def test_prose_named_scripts_exist_on_disk():
    offenders = [
        f"{prose.relative_to(REPO_ROOT)}:{lineno}: {name}"
        for prose, lineno, names, _ in _prose_references()
        for name in names
        if name not in SCRIPTS
    ]
    assert not offenders, (
        "prose names scripts that do not exist under skills/ or hooks/ "
        "(renamed script with stale prose?):\n" + "\n".join(offenders)
    )


def test_prose_flags_exist_in_named_scripts_argparse():
    offenders = []
    for prose, lineno, names, flags in _prose_references():
        known = [n for n in names if n in SCRIPTS]
        if not known:
            continue  # existence test above owns this case
        union = set().union(*(_argparse_flags(SCRIPTS[n]) for n in known))
        for flag in flags:
            if flag not in union:
                offenders.append(
                    f"{prose.relative_to(REPO_ROOT)}:{lineno}: "
                    f"{flag} not accepted by {' or '.join(known)}"
                )
    assert not offenders, (
        "prose names CLI flags the script's argparse does not define — the "
        "documented invocation would exit non-zero in a user workspace:\n"
        + "\n".join(offenders)
    )
