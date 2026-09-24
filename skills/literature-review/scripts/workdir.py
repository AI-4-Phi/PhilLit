#!/usr/bin/env python3
"""The one owner of a review's working directory.

A plugin review works in a per-user local folder outside the workspace,
`~/.local/state/phillit/reviews/<ws-key>/<name>/`, and is copied into the
workspace's `reviews/<name>/` once, by `publish`, when it is finished or
abandoned. A sync engine (OneDrive, iCloud) then sees one burst of new files
instead of hours of rewrites. `PHILLIT_WORKDIR=inplace` keeps the old
behaviour, where the review works in `reviews/<name>/` itself;
phillit-service pins it.

This module is the only code that decides the mode, resolves the working
directory or touches the pointer `reviews/.active-review`. The SubagentStop
hook calls `resolve` instead of parsing the pointer. Every subcommand prints
one JSON object on stdout: exit 2 on a refusal, exit 1 on a crash (still one
JSON object, `{"error": "workdir.py crashed: ..."}`); a `resolve` refusal
exits 0, so only a crash reads as a crash to the hook.

The location is fixed (`XDG_STATE_HOME` is ignored), so one permission-rule
string works on every machine. `ws-key` only NAMES a folder: ownership is
proven by the metadata file `intermediate_files/.phillit-review.json`, never
by the key. Nothing is copied or deleted unless ownership is proven, and every
deletion removes the metadata file LAST, so an interrupted delete always
leaves a folder that still says what it is. A link (symlink, or any Windows
reparse point) at the key or review level, or inside a tree, refuses; the
root itself may be a link, since dotfile managers link `~/.local`, and every
deletion stays inside `<root>/<key>/<name>`.

Design and rationale: docs/ARCHITECTURE.md, "Working directory".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "philosophy-research" / "scripts"))
from output import dumps  # noqa: E402

sys.path.pop(0)

FORMAT = 1
POINTER_REL = Path("reviews") / ".active-review"
META_REL = Path("intermediate_files") / ".phillit-review.json"
COMPLETED_REL = Path("intermediate_files") / ".completed-review"
# /phillit:setup merges exactly this string (PHILLIT_RULES in
# skills/setup/scripts/setup_workspace.py); tests pin the two equal.
ALLOW_RULE = "Edit(~/.local/state/phillit/reviews/**)"
MODES = ("local", "inplace")
FINAL_STATES = ("published", "abandoned")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RESERVED = frozenset({"CON", "PRN", "AUX", "NUL"}
                     | {f"COM{i}" for i in range(1, 10)}
                     | {f"LPT{i}" for i in range(1, 10)})
# Unsafe inside a double-quoted Bash string; `!` is safe because
# non-interactive Bash does no history expansion. NAME_RE keeps every one of
# these out of a review name, so only HOME and the workspace path can carry
# one: relaxing NAME_RE would reopen that.
UNSAFE_CHARS = ("$", "`", '"', "\\", "\n")
WINDOWS_PATH_LIMIT = 250
DEEP_FILE_HEADROOM = 120  # intermediate_files/json/verify_<domain>_<citekey>.json
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
MISSING_RULE_REASON = (
    "the standard PhilLit allow rule for the local work folder was not found; "
    "re-run /phillit:setup to move review work off this folder")
DEMOTE_REASON = "the Write tool was denied in the local work folder"
INPLACE_MEETS_LOCAL = (
    "PHILLIT_WORKDIR=inplace, but the active review works in the local folder; "
    "unset PHILLIT_WORKDIR to resume it")
STRANDED_NOTE = "ownership cannot be proven; move or delete it by hand"
UNCOLLECTED_NOTE = ("finished, but its published copy in reviews/ is missing or "
                    "differs; move or delete it by hand")


class Refusal(Exception):
    """A refusal: printed as {"error": <message>, **extra}, exit 2."""

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.extra = extra


# --- location ---------------------------------------------------------------

def local_root() -> Path:
    return Path.home() / ".local" / "state" / "phillit" / "reviews"


def workspace_id(workspace: Path) -> str:
    return workspace.resolve().as_posix()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def ws_key(workspace: Path) -> str:
    """Basename slug (20 chars) + 16 hex of sha256(RESOLVED path): both path
    forms of one workspace map to one key; two workspaces never share one."""
    resolved = workspace.resolve()
    base = _slug(resolved.name)[:20].strip("-") or "workspace"
    digest = hashlib.sha256(resolved.as_posix().encode("utf-8")).hexdigest()[:16]
    return f"{base}-{digest}"


def local_workdir(workspace: Path, name: str) -> Path:
    return local_root() / ws_key(workspace) / name


def destination(workspace: Path, name: str) -> Path:
    return workspace / "reviews" / name


# --- mode and rule ----------------------------------------------------------

def requested_mode() -> str | None:
    """PHILLIT_WORKDIR, read per call (main() loads .env first). None = unset."""
    value = os.environ.get("PHILLIT_WORKDIR", "").strip()
    if not value:
        return None
    if value not in MODES:
        raise Refusal(f"PHILLIT_WORKDIR={value!r} is not one of: local, inplace")
    return value


def settings_files(workspace: Path) -> list[Path]:
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    user_dir = Path(config).expanduser() if config else Path.home() / ".claude"
    return [workspace / ".claude" / "settings.json",
            workspace / ".claude" / "settings.local.json",
            user_dir / "settings.json"]


def allow_rule_present(workspace: Path) -> bool:
    """Exact-string presence of ALLOW_RULE. Presence is not proof the rule is
    effective; SKILL.md's Phase 1 tracker Write is the empirical test."""
    for path in settings_files(workspace):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        perms = data.get("permissions") if isinstance(data, dict) else None
        allow = perms.get("allow") if isinstance(perms, dict) else None
        if isinstance(allow, str):
            allow = [allow]
        if isinstance(allow, list) and ALLOW_RULE in allow:
            return True
    return False


# --- names and paths ---------------------------------------------------------

def name_problem(name: str) -> str | None:
    if not NAME_RE.match(name):
        return (f"review name {name!r} must be 1-64 letters, digits, '.', '_' "
                "or '-', starting with a letter or digit")
    if name.endswith("."):
        return f"review name {name!r} must not end with '.'"
    if name.split(".")[0].upper() in RESERVED:
        return f"review name {name!r} is a reserved device name on Windows"
    return None


def unsafe_char(path: Path) -> str | None:
    text = path.as_posix()
    return next((ch for ch in UNSAFE_CHARS if ch in text), None)


def _require_quotable(workdir: Path) -> None:
    """Every path handed to the orchestrator is pasted into a double-quoted
    shell string (REVIEW_DIR="[workdir]"): refuse one that cannot be."""
    ch = unsafe_char(workdir)
    if ch is not None:
        raise Refusal(f"the review folder path {workdir.as_posix()!r} contains {ch!r}, "
                      "which the review's shell commands cannot quote safely; use a "
                      "workspace path without it")


def length_problem(paths: list[Path], windows: bool | None = None) -> str | None:
    if windows is None:
        windows = os.name == "nt"
    if not windows:
        return None
    for p in paths:
        if len(p.as_posix()) + DEEP_FILE_HEADROOM >= WINDOWS_PATH_LIMIT:
            return (f"{p.as_posix()} is too long for Windows once the review's "
                    "deepest files are added; choose a shorter review name")
    return None


# --- pointer ------------------------------------------------------------------

def read_pointer(workspace: Path) -> dict | None:
    """The pointer, recognised LEXICALLY: `{`-prefixed JSON is local,
    `reviews/<name>` is in place. Never Path.is_absolute(), which calls a
    Windows `C:/...` path relative on macOS."""
    path = workspace / POINTER_REL
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise Refusal(f"cannot read {POINTER_REL.as_posix()}: {e}")
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        ok = (isinstance(data, dict) and data.get("format") == FORMAT
              and data.get("mode") == "local"
              and all(isinstance(data.get(k), str) and data[k]
                      for k in ("review_id", "name", "workdir"))
              and isinstance(data.get("host"), str)
              and name_problem(data["name"]) is None)
        if not ok:
            raise Refusal(f"{POINTER_REL.as_posix()} is not a valid local-review pointer",
                          pointer=text[:200])
        return {"form": "local", **{k: data[k] for k in ("review_id", "name", "host", "workdir")}}
    if text.startswith("reviews/") and "\n" not in text:
        name = text[len("reviews/"):].rstrip("/")
        if name and "/" not in name and "\\" not in name and name not in (".", ".."):
            return {"form": "inplace", "name": name}
    raise Refusal(f"{POINTER_REL.as_posix()} holds neither pointer form", pointer=text[:200])


def current_pointer(workspace: Path) -> dict | None:
    """read_pointer plus the one mode-compatibility rule every command obeys:
    an explicit PHILLIT_WORKDIR=inplace meeting a local pointer is an error,
    so the service's pin can never act on a local review."""
    ptr = read_pointer(workspace)
    if ptr is not None and ptr["form"] == "local" and requested_mode() == "inplace":
        raise Refusal(INPLACE_MEETS_LOCAL)
    return ptr


def _pointer_text(ptr: dict) -> str:
    if ptr["form"] == "inplace":
        return f"reviews/{ptr['name']}\n"
    return json.dumps({"format": FORMAT, "mode": "local", "review_id": ptr["review_id"],
                       "name": ptr["name"], "host": ptr["host"],
                       "workdir": ptr["workdir"]}) + "\n"


def create_pointer(workspace: Path, ptr: dict) -> None:
    """Exclusive create (O_EXCL): of two racing commands, exactly one wins;
    the loser gets FileExistsError."""
    path = workspace / POINTER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
    with os.fdopen(fd, "wb") as f:
        f.write(_pointer_text(ptr).encode("utf-8"))


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def replace_pointer(workspace: Path, ptr: dict) -> None:
    _atomic_write_text(workspace / POINTER_REL, _pointer_text(ptr))


def remove_pointer(workspace: Path) -> None:
    (workspace / POINTER_REL).unlink(missing_ok=True)


# --- metadata -------------------------------------------------------------------

def meta_path(workdir: Path) -> Path:
    return workdir / META_REL


def read_meta(workdir: Path) -> dict | None:
    try:
        data = json.loads(meta_path(workdir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("format") == FORMAT else None


def write_meta(workdir: Path, data: dict) -> None:
    _atomic_write_text(meta_path(workdir), json.dumps(data, indent=2) + "\n")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- trees ------------------------------------------------------------------------

def _is_link(p: Path) -> bool:
    """A symlink, or on Windows any reparse point: a junction included, which
    os.path.isjunction reports only from Python 3.12 on."""
    try:
        st = os.lstat(p)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


def _stale_meta_temp(rel: Path) -> bool:
    """A metadata temp file left by a crash inside _atomic_write_text: never
    review content, so never copied, counted or verified."""
    return (rel.parent == META_REL.parent and rel.name.startswith(META_REL.name + ".")
            and rel.name.endswith(".tmp"))


def tree_files(root: Path) -> list[Path]:
    """Every regular file under root, relative, walked with lstat. A link or
    special file (FIFO, socket) refuses, so a link planted in a tree can
    never redirect a copy or a delete. Stale metadata temps are skipped."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            if _is_link(p):
                raise Refusal(f"{p.as_posix()} is a link; refusing to copy or delete through it")
            if name in filenames and not stat.S_ISREG(os.lstat(p).st_mode):
                raise Refusal(f"{p.as_posix()} is not a regular file; refusing to copy it")
            if name in filenames and not _stale_meta_temp(p.relative_to(root)):
                files.append(p.relative_to(root))
    return sorted(files)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def same_file(a: Path, b: Path) -> bool:
    return (b.is_file() and a.stat().st_size == b.stat().st_size
            and file_sha256(a) == file_sha256(b))


def manifest(root: Path, files: list[Path]) -> dict[str, tuple[int, str]]:
    """{relative POSIX path: (size, sha256)}, the metadata file aside."""
    return {rel.as_posix(): ((root / rel).stat().st_size, file_sha256(root / rel))
            for rel in files if rel != META_REL}


def holds_no_files(d: Path) -> bool:
    for dirpath, dirnames, filenames in os.walk(d, followlinks=False):
        if filenames or any(_is_link(Path(dirpath) / n) for n in dirnames):
            return False
    return True


def delete_workdir(workdir: Path) -> list[str]:
    """Delete a working directory from Python (no `rm` prompt): contents
    first, then the metadata file, then the empty folders. A link is removed
    itself, never walked and never chmod-ed (a chmod follows the link).
    Returns what could not be deleted; when anything is left, the metadata
    file stays too."""
    if _is_link(workdir):
        return [workdir.as_posix()]
    leftover: list[str] = []
    meta = meta_path(workdir)

    def _rm_link(p: Path) -> None:
        try:
            if os.name == "nt" and os.path.isdir(p):
                os.rmdir(p)  # a junction or directory symlink on Windows
            else:
                os.unlink(p)
        except FileNotFoundError:
            pass
        except OSError:
            leftover.append(p.as_posix())

    def _rm(p: Path, is_dir: bool) -> None:
        op = os.rmdir if is_dir else os.unlink
        try:
            op(p)
        except FileNotFoundError:
            pass
        except OSError:
            try:  # a read-only file on Windows
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD | (stat.S_IEXEC if is_dir else 0))
                op(p)
            except OSError:
                leftover.append(p.as_posix())

    for dirpath, dirnames, filenames in os.walk(workdir, topdown=False, followlinks=False):
        d = Path(dirpath)
        for name in filenames:
            p = d / name
            if _is_link(p):
                _rm_link(p)
            elif p != meta:
                _rm(p, False)
        for name in dirnames:
            p = d / name
            if _is_link(p):
                _rm_link(p)
            elif p != meta.parent:
                _rm(p, True)
    if leftover:
        return leftover
    _rm(meta, False)
    _rm(meta.parent, True)
    _rm(workdir, True)
    return leftover


# --- ownership ----------------------------------------------------------------------

def locate(workspace: Path, ptr: dict) -> tuple[Path | None, str | None]:
    """A local pointer's working directory, with ownership PROVEN:
    (workdir, None). (None, "elsewhere") when the pointer names a path this
    machine would not use (another machine, a crafted pointer);
    (None, "missing") when the path is right but absent. A folder that exists
    at the right place but fails a check raises Refusal: nothing may act on it."""
    expected = local_workdir(workspace, ptr["name"])
    if ptr["workdir"] != expected.as_posix():
        return None, "elsewhere"
    if not os.path.lexists(expected):
        return None, "missing"
    for p in (expected, expected.parent):
        if _is_link(p):
            raise Refusal(f"{p.as_posix()} is a link; ownership cannot be proven")
    meta = read_meta(expected)
    if meta is None:
        raise Refusal(f"{expected.as_posix()} has no readable {META_REL.as_posix()}; "
                      "ownership cannot be proven")
    if meta.get("review_id") != ptr["review_id"] or meta.get("name") != ptr["name"]:
        raise Refusal(f"{expected.as_posix()} belongs to another review")
    if meta.get("workspace") != workspace_id(workspace):
        raise Refusal(f"{expected.as_posix()} belongs to another workspace "
                      f"({meta.get('workspace')})")
    return expected, None


def committed(workspace: Path, ptr: dict) -> dict | None:
    """The destination's marker when it commits THIS review, else None."""
    marker = read_meta(destination(workspace, ptr["name"]))
    if (marker and marker.get("review_id") == ptr["review_id"]
            and marker.get("state") in FINAL_STATES):
        return marker
    return None


