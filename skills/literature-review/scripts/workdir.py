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
about the review exits 0, while a configuration error (ConfigError) exits 1,
so the hook fails closed on it as on a crash.

The location is fixed (`XDG_STATE_HOME` is ignored), so one permission-rule
string works on every machine. `ws-key` only NAMES a folder: ownership is
proven by the metadata file `intermediate_files/.phillit-review.json`, never
by the key. Nothing is copied or deleted unless ownership is proven, and every
deletion removes the metadata file LAST, so an interrupted delete always
leaves a folder that still says what it is. A link (a symlink, or on Windows
a junction or other name-surrogate reparse point; a cloud-files placeholder
is not one) at the key or review level, or inside a tree, refuses; the root
itself may be a link, since dotfile managers link `~/.local`, and every
deletion stays inside `<root>/<key>/<name>`.

Decided, do not reopen:
- The location is fixed: one rule string then works on every machine.
- A local name clash refuses: publish must prove its destination, and a
  delivered review is never changed.
- The local copy is deleted at publish: kept until the next init, it would
  stay a hidden copy forever in a workspace that starts no other review.
- In-place `init` accepts an existing finished destination only under an
  explicit `PHILLIT_WORKDIR=inplace` (the service's pin); the automatic
  fallback refuses it, since a delivered review is never changed.
- A linked root is accepted: dotfile managers link `~/.local`.
- A configuration error fails the SubagentStop hook closed; a review-state
  error warns and allows (ROADMAP: "The SubagentStop gate fails open
  silently when the review cannot be resolved").

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
_NAME_SURROGATE = 0x20000000  # IO_REPARSE_TAG_NAME_SURROGATE bit: symlinks, junctions
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
ALREADY_PUBLISHED_NOTE = ("already published to reviews/; an interrupted publish left this "
                          "copy; delete it by hand")
DETACH_HINT = " (to detach it, delete reviews/.active-review by hand)"


class Refusal(Exception):
    """A refusal: printed as {"error": <message>, **extra}, exit 2."""

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.extra = extra


class ConfigError(Refusal):
    """A configuration error: a bad PHILLIT_WORKDIR, or the inplace pin
    meeting a local review. `resolve` reports it as a CRASH (exit 1), so the
    SubagentStop gate fails closed instead of silently skipping validation
    for a review whose files are here. Every other command treats it as an
    ordinary refusal (exit 2)."""


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
        raise ConfigError(f"PHILLIT_WORKDIR={value!r} is not one of: local, inplace")
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
        raise Refusal(f"cannot read {POINTER_REL.as_posix()}: {e}{DETACH_HINT}")
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
            raise Refusal(f"{POINTER_REL.as_posix()} is not a valid local-review pointer"
                          f"{DETACH_HINT}", pointer=text[:200])
        return {"form": "local", **{k: data[k] for k in ("review_id", "name", "host", "workdir")}}
    if text.startswith("reviews/") and "\n" not in text:
        name = text[len("reviews/"):].rstrip("/")
        if name and "/" not in name and "\\" not in name and name not in (".", ".."):
            return {"form": "inplace", "name": name}
    raise Refusal(f"{POINTER_REL.as_posix()} holds neither pointer form{DETACH_HINT}",
                  pointer=text[:200])


def current_pointer(workspace: Path) -> dict | None:
    """read_pointer plus the one mode-compatibility rule every command obeys:
    an explicit PHILLIT_WORKDIR=inplace meeting a local pointer is an error,
    so the service's pin can never act on a local review."""
    ptr = read_pointer(workspace)
    if ptr is not None and ptr["form"] == "local" and requested_mode() == "inplace":
        raise ConfigError(INPLACE_MEETS_LOCAL)
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
    _make_writable(path)
    os.replace(tmp, path)


def replace_pointer(workspace: Path, ptr: dict) -> None:
    _atomic_write_text(workspace / POINTER_REL, _pointer_text(ptr))


def remove_pointer(workspace: Path) -> None:
    _make_writable(workspace / POINTER_REL)
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
    """A symlink, or on Windows a name-surrogate reparse point (a junction or
    symlink; os.path.isjunction exists only from Python 3.12). A cloud-files
    placeholder (OneDrive Files On-Demand) is a reparse point too, but it
    does not redirect a walk, so it is not a link."""
    try:
        st = os.lstat(p)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    if getattr(st, "st_file_attributes", 0) & _REPARSE_POINT:
        return bool(getattr(st, "st_reparse_tag", 0) & _NAME_SURROGATE)
    return False


def _make_writable(path: Path) -> None:
    """Clear a read-only mode/attribute on a file PhilLit is about to replace
    or remove (Windows refuses both on a read-only file)."""
    try:
        if os.path.lexists(path) and not _is_link(path) and not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass


# Files a file manager or sync client drops into any folder it shows: never
# review content, so a destination holding only these holds nothing.
_OS_CLUTTER = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


def _is_clutter(rel: Path) -> bool:
    return rel.name in _OS_CLUTTER or rel.name.startswith("._")


def _stale_meta_temp(rel: Path) -> bool:
    """A metadata temp file left by a crash inside _atomic_write_text: never
    review content, so never copied, counted or verified."""
    return (rel.parent == META_REL.parent and rel.name.startswith(META_REL.name + ".")
            and rel.name.endswith(".tmp"))


def _walk_error(e: OSError) -> None:
    """os.walk's onerror: a folder the walk cannot list must never read as
    empty, or a copy would miss files and a delete would follow them."""
    where = Path(e.filename).as_posix() if e.filename else "a folder"
    raise Refusal(f"cannot list {where}: {e.strerror}; refusing to copy or "
                  "delete what cannot be seen")


def tree_files(root: Path) -> list[Path]:
    """Every regular file under root, relative, walked with lstat. A link or
    special file (FIFO, socket) refuses, so a link planted in a tree can
    never redirect a copy or a delete. Stale metadata temps are skipped.
    A folder it cannot list refuses too."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=_walk_error, followlinks=False):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            if _is_link(p):
                raise Refusal(f"{p.as_posix()} is a link; refusing to copy or delete through it")
            try:
                mode = os.lstat(p).st_mode
            except OSError as e:  # a folder that lists but cannot be searched
                raise Refusal(f"cannot inspect {p.as_posix()}: {e.strerror}; refusing to copy "
                              "or delete what cannot be seen")
            if name in filenames and not stat.S_ISREG(mode):
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
    """True only when d provably holds no files: a folder the walk cannot
    list counts as holding some (fail closed; it is never collected). A
    stale metadata temp (a crashed write) is not a file here; a link is."""
    try:
        for dirpath, dirnames, filenames in os.walk(d, onerror=_walk_error, followlinks=False):
            here = Path(dirpath)
            if (any(_is_link(here / n) or not _stale_meta_temp((here / n).relative_to(d))
                    for n in filenames)
                    or any(_is_link(here / n) for n in dirnames)):
                return False
    except Refusal:
        return False
    return True


def delete_workdir(workdir: Path) -> list[str]:
    """Delete a working directory from Python (no `rm` prompt): contents
    first, then the metadata file, then the empty folders. A link is removed
    itself, never walked and never chmod-ed (a chmod follows the link).
    Returns what could not be deleted; when anything is left, the metadata
    file stays too. A folder the walk cannot list is left over as well, so
    an unseen file never outlives the metadata that says what it is."""
    if _is_link(workdir):
        return [workdir.as_posix()]
    leftover: list[str] = []
    meta = meta_path(workdir)

    def _unlistable(e: OSError) -> None:
        # Only the working directory itself vanishing (a racing delete) hides
        # nothing; any other missing path (on Windows, a too-long one reads
        # as missing) is left over and keeps the metadata file.
        if isinstance(e, FileNotFoundError) and e.filename and Path(e.filename) == workdir:
            return
        leftover.append(Path(e.filename).as_posix() if e.filename else workdir.as_posix())

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

    for dirpath, dirnames, filenames in os.walk(workdir, topdown=False, onerror=_unlistable,
                                                followlinks=False):
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
        return list(dict.fromkeys(leftover))  # a walk error and its rmdir name one path
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


def _published_copy(workspace: Path, d: Path, meta: dict) -> bool:
    """reviews/<d.name>/ commits the review d holds (same review_id, a final
    state): d is a copy an interrupted publish left behind."""
    marker = read_meta(destination(workspace, d.name))
    return bool(marker and isinstance(meta.get("review_id"), str)
                and marker.get("review_id") == meta["review_id"]
                and marker.get("state") in FINAL_STATES)


def _holds_only_clutter(d: Path) -> bool:
    """Every entry of d is an OS clutter FILE (no entries counts): no
    folder, no link, nothing else. A folder that cannot be listed holds
    something."""
    try:
        return all(not _is_link(p) and p.is_file() and _is_clutter(p) for p in d.iterdir())
    except OSError:
        return False


def _demote_interrupted(dest: Path) -> bool:
    """reviews/<name>/ exists and holds nothing but OS clutter: with the
    local folder gone, that is exactly what a demote crash leaves (it creates
    the folder empty, then deletes the local one). A subfolder, such as the
    intermediate_files/ a publish crashing in step 1 leaves, disqualifies."""
    return dest.is_dir() and not _is_link(dest) and _holds_only_clutter(dest)


# --- garbage collection -------------------------------------------------------

def _subdirs(d: Path, follow_top_link: bool = False) -> list[Path]:
    """The non-link subdirectories of d, sorted; [] when d is missing, a
    link (unless follow_top_link: the root itself may be a link), or
    unreadable. An in-place review never needs the local root, so a sandbox
    that denies $HOME must not crash it; an unreadable folder is never
    deleted either, only left out."""
    try:
        if (not follow_top_link and _is_link(d)) or not d.is_dir():
            return []
        return sorted(p for p in d.iterdir() if p.is_dir() and not _is_link(p))
    except OSError:
        return []


def _collectable(workspace: Path, d: Path, meta: dict) -> bool:
    """A finished local folder whose published copy carries the same
    review_id and state, and holds every file the folder still holds with
    the same size and sha256: safe to delete. A file missing from the folder
    is a partial delete and loses nothing. A folder the walk refuses (a
    link, an unlistable folder) or a file that cannot be read is never
    collectable."""
    if not (meta.get("state") in FINAL_STATES and meta.get("name") == d.name
            and meta.get("workspace") == workspace_id(workspace)):
        return False
    dest = destination(workspace, d.name)
    marker = read_meta(dest)
    if not (marker and marker.get("review_id") == meta.get("review_id")
            and marker.get("state") == meta.get("state")):
        return False
    try:
        return all(same_file(d / rel, dest / rel) for rel in tree_files(d) if rel != META_REL)
    except (Refusal, OSError):
        return False


def collect(workspace: Path) -> list[str]:
    """Delete THIS workspace's finished leftovers under its ws-key (see
    _collectable), and folders holding no files at all (an init that crashed
    before its metadata write). A non-empty folder without metadata is never
    deleted; status lists it. Returns what could not be deleted."""
    keydir = local_root() / ws_key(workspace)
    leftover: list[str] = []
    for d in _subdirs(keydir):
        meta = read_meta(d)
        if meta is None:
            if holds_no_files(d):
                leftover += delete_workdir(d)
        elif _collectable(workspace, d, meta):
            leftover += delete_workdir(d)
    try:
        keydir.rmdir()  # only when empty
    except OSError:
        pass
    return leftover


# --- listings -------------------------------------------------------------------

def list_abandoned(workspace: Path) -> list[dict]:
    out = []
    for d in _subdirs(local_root() / ws_key(workspace)):
        meta = read_meta(d)
        if (meta and meta.get("state") == "active" and meta.get("name") == d.name
                and meta.get("workspace") == workspace_id(workspace)
                and not _published_copy(workspace, d, meta)):
            out.append({"name": d.name, "mode": "local", "workdir": d.as_posix()})
    reviews = workspace / "reviews"
    if reviews.is_dir():
        for d in sorted(p for p in reviews.iterdir() if p.is_dir() and not _is_link(p)):
            if _abandoned_in_place(d):
                out.append({"name": d.name, "mode": "inplace", "workdir": d.as_posix()})
    return out


def _abandoned_in_place(d: Path) -> bool:
    """An in-workspace review that can be resumed: its marker says
    `abandoned` (set by publish --abandon in either mode, so it holds after
    Phase 6 moved the tracker), or it still has a top-level tracker and no
    marker saying `published`. A delivered review (a `published` marker, or
    `.completed-review` in place) is never offered."""
    if (d / COMPLETED_REL).exists():
        return False  # delivered in place: its pointer was archived by publish
    marker = read_meta(d)
    if marker is not None and marker.get("name") != d.name:
        return False  # a marker for another review: never offered, never removed
    if marker and marker.get("state") == "published":
        return False
    if marker and marker.get("state") == "abandoned":
        return True
    return (d / "task-progress.md").is_file()


def _unsynced(dest: Path, files) -> list[str]:
    """The entries of an abandoned marker's manifest that dest does not hold
    yet as a regular file with the same size and sha256 (a sync still
    delivering them). No manifest (or an unreadable one): nothing to check."""
    if not isinstance(files, dict):
        return []
    out = []
    for rel, expected in sorted(files.items()):
        if _is_clutter(Path(rel)):
            continue  # never review content; an old marker may still list it
        p = dest / rel
        try:
            ok = (p.is_file() and not _is_link(p)
                  and list(expected) == [p.stat().st_size, file_sha256(p)])
        except (OSError, TypeError):
            ok = False
        if not ok:
            out.append(rel)
    return out


def list_stranded(workspace: Path) -> list[dict]:
    """For information only (listing needs no ownership proof; deletion
    does): folders under OTHER keys whose workspace no longer exists,
    non-empty folders without metadata anywhere, this workspace's finished
    folders that collection cannot collect, and its active folders whose
    review is already published (an interrupted publish's copy)."""
    out = []
    own = ws_key(workspace)
    for keydir in _subdirs(local_root(), follow_top_link=True):
        for d in _subdirs(keydir):
            meta = read_meta(d)
            if meta is None:
                if not holds_no_files(d):
                    out.append({"path": d.as_posix(), "note": STRANDED_NOTE})
            elif keydir.name != own:
                ws = meta.get("workspace")
                if isinstance(ws, str) and not Path(ws).exists():
                    out.append({"path": d.as_posix(), "note": STRANDED_NOTE})
            elif meta.get("state") in FINAL_STATES and not _collectable(workspace, d, meta):
                out.append({"path": d.as_posix(), "note": UNCOLLECTED_NOTE})
            elif meta.get("state") == "active" and _published_copy(workspace, d, meta):
                out.append({"path": d.as_posix(), "note": ALREADY_PUBLISHED_NOTE})
    return out


# --- commands ---------------------------------------------------------------------

def _describe(ptr: dict) -> dict:
    return {k: v for k, v in ptr.items() if k != "form"} | {"mode": ptr["form"]}


def _refuse_linked_destination(dest: Path) -> None:
    """An in-place review writes into reviews/<name>/ for hours and publish
    refuses a linked one, so refuse it up front rather than at the end."""
    for p in (dest, dest / "intermediate_files"):
        if _is_link(p):
            raise Refusal(f"{p.as_posix()} is a link; a review cannot work through it")


def _active(mode: str, name: str, workdir: Path, workspace: Path) -> dict:
    _require_quotable(workdir)
    return {"active": True, "mode": mode, "name": name, "workdir": workdir.as_posix(),
            "destination": destination(workspace, name).as_posix()}


def suggest_name(workspace: Path, name: str) -> str | None:
    for n in range(2, 1000):
        suffix = f"-{n}"
        candidate = name[:64 - len(suffix)].rstrip(".") + suffix
        if name_problem(candidate):
            continue
        if not (os.path.lexists(destination(workspace, candidate))
                or os.path.lexists(local_workdir(workspace, candidate))):
            return candidate
    return None


def cmd_init(workspace: Path, name: str) -> dict:
    ptr = current_pointer(workspace)
    if ptr is not None:
        raise Refusal("a review is already active: resume it, or abandon it first with "
                      "`workdir.py publish --abandon`", active=_describe(ptr))
    problem = name_problem(name)
    if problem:
        raise Refusal(problem)
    mode, reason = requested_mode() or "local", None
    dest, local = destination(workspace, name), local_workdir(workspace, name)
    if mode == "local":
        if not allow_rule_present(workspace):
            mode, reason = "inplace", MISSING_RULE_REASON
        elif (ch := unsafe_char(local)) is not None:
            mode, reason = "inplace", (f"the local work folder path contains {ch!r}, which "
                                       "the review's shell commands cannot quote safely")
    workdir = local if mode == "local" else dest
    _require_quotable(workdir)
    problem = length_problem([local, dest] if mode == "local" else [dest])
    if problem:
        raise Refusal(problem)
    leftover = collect(workspace)  # before the clash check: a finished leftover never blocks
    existing_review = False
    if mode == "local":
        if _is_link(local.parent):
            raise Refusal(f"{local.parent.as_posix()} is a link; ownership could never be "
                          "proven there. Remove the link and run init again")
        taken = [p for p in (dest, local) if os.path.lexists(p)]
        if taken:
            raise Refusal(f"the name {name!r} is taken: {taken[0].as_posix()} exists",
                          suggested_name=suggest_name(workspace, name))
    else:
        _refuse_linked_destination(dest)
        existing_review = (dest / f"literature-review-{name}.md").exists()
        if existing_review and requested_mode() != "inplace":
            # init fell back to in place by itself (no rule, unsafe path):
            # only the service's explicit pin accepts a finished destination
            raise Refusal(f"a completed review occupies reviews/{name}/, and a delivered "
                          "review is never changed; choose another name",
                          suggested_name=suggest_name(workspace, name))
    if mode == "local":
        root = local_root()
        root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt" and not _is_link(root):
            os.chmod(root, 0o700)  # every init: review drafts and API results live here
        local.parent.mkdir(exist_ok=True)
        try:
            local.mkdir()  # no exist_ok: a racing init fails instead of sharing
        except FileExistsError:
            raise Refusal(f"{local.as_posix()} appeared while init ran",
                          suggested_name=suggest_name(workspace, name))
        (local / "intermediate_files").mkdir()
        review_id, host = uuid.uuid4().hex, platform.node()
        write_meta(local, {"format": FORMAT, "review_id": review_id, "name": name,
                           "workspace": workspace_id(workspace), "host": host,
                           "state": "active", "created": now()})
        new_ptr = {"form": "local", "review_id": review_id, "name": name, "host": host,
                   "workdir": local.as_posix()}
    else:
        dest.mkdir(parents=True, exist_ok=True)  # the service pre-creates it
        new_ptr = {"form": "inplace", "name": name}
    try:
        create_pointer(workspace, new_ptr)
    except FileExistsError:
        if mode == "local":
            delete_workdir(local)
        raise Refusal("another init created the pointer first; a review is already active")
    out = {"mode": mode, "name": name, "workdir": workdir.as_posix(),
           "destination": dest.as_posix()}
    if reason:
        out["reason"] = reason
    if existing_review:
        out["existing_review"] = True
        out["suggested_name"] = suggest_name(workspace, name)
    if leftover:
        out["leftover"] = leftover
    return out


def cmd_status(workspace: Path) -> dict:
    """READ-ONLY: reports; never deletes or writes."""
    ptr = current_pointer(workspace)
    if ptr is None:
        return {"active": False, "abandoned": list_abandoned(workspace),
                "stranded": list_stranded(workspace)}
    name = ptr["name"]
    dest = destination(workspace, name)
    if ptr["form"] == "inplace":
        _require_quotable(dest)
        if not dest.is_dir():
            # init creates the folder before the pointer, so this is loss or
            # sync lag, never "created but not started"
            return {"active": True, "missing": True, "mode": "inplace", "name": name,
                    "workdir": dest.as_posix()}
        marker = read_meta(dest)
        if (dest / COMPLETED_REL).exists() or (marker is not None and marker.get("state") == "published"):
            # an init whose completed-review guard was interrupted, or a
            # folder a local publish delivered
            return {"active": True, "delivered": True, "mode": "inplace", "name": name,
                    "workdir": dest.as_posix()}
        return _active("inplace", name, dest, workspace)
    marker = committed(workspace, ptr)
    if marker:
        return {"active": True, "committed": True, "mode": "local", "name": name,
                "state": marker["state"], "destination": dest.as_posix()}
    try:
        workdir, where = locate(workspace, ptr)
    except Refusal as e:  # the folder is here, but nothing may act on it
        return {"active": True, "unproven": True, "mode": "local", "name": name,
                "host": ptr["host"], "workdir": ptr["workdir"], "error": str(e)}
    if workdir is not None:
        return _active("local", name, workdir, workspace)
    if where == "missing" and _demote_interrupted(dest):
        _require_quotable(dest)
        return {"active": True, "interrupted_demote": True, "mode": "local", "name": name,
                "workdir": dest.as_posix()}
    return {"active": True, "elsewhere": True, "mode": "local", "name": name,
            "host": ptr["host"], "workdir": ptr["workdir"],
            "workdir_exists": os.path.lexists(ptr["workdir"])}


def cmd_activate(workspace: Path, name: str) -> dict:
    ptr = current_pointer(workspace)
    if ptr is not None:
        raise Refusal("a review is already active; activate needs no pointer",
                      active=_describe(ptr))
    collect(workspace)  # a finished local leftover must not shadow the published copy
    clear_marker = None
    if name_problem(name) is None and os.path.lexists(local := local_workdir(workspace, name)):
        if requested_mode() == "inplace":
            raise ConfigError(INPLACE_MEETS_LOCAL)
        meta = read_meta(local)
        if (_is_link(local) or _is_link(local.parent) or meta is None
                or meta.get("name") != name or not isinstance(meta.get("review_id"), str)
                or meta.get("workspace") != workspace_id(workspace)):
            raise Refusal(f"{local.as_posix()}: ownership cannot be proven")
        if meta.get("state") != "active":
            raise Refusal(f"{local.as_posix()} is already {meta.get('state')} but could not be "
                          "collected (its copy in reviews/ is missing or differs, or a file "
                          "is locked); move or delete it by hand, then run activate again")
        new_ptr = {"form": "local", "review_id": meta["review_id"], "name": name,
                   "host": platform.node(), "workdir": local.as_posix()}
        mode, workdir = "local", local
    else:
        if "/" in name or "\\" in name or name in ("", ".", ".."):
            raise Refusal(f"review name {name!r} is not a folder name")
        dest = destination(workspace, name)
        marker = read_meta(dest)
        if marker and marker.get("state") == "published":
            raise Refusal(f"{dest.as_posix()} is a delivered review; it is never resumed")
        if not (dest.is_dir() and _abandoned_in_place(dest)):
            raise Refusal(f"no abandoned review named {name!r} in this workspace")
        _refuse_linked_destination(dest)
        if marker and marker.get("state") == "abandoned":
            missing = _unsynced(dest, marker.get("files"))
            if missing:
                raise Refusal(f"reviews/{name}/ is not complete yet (still syncing?): "
                              f"{len(missing)} files missing or different; try again when "
                              "sync has finished. If you changed those files yourself, this "
                              "check cannot tell your edits from sync lag: restore them, or "
                              "copy the folder elsewhere by hand", missing=missing)
            clear_marker = meta_path(dest)
        new_ptr, mode, workdir = {"form": "inplace", "name": name}, "inplace", dest
    _require_quotable(workdir)
    try:
        create_pointer(workspace, new_ptr)  # win the race BEFORE changing anything
    except FileExistsError:
        raise Refusal("another command created the pointer first")
    out = _active(mode, name, workdir, workspace)
    if clear_marker is not None:  # an ordinary in-place review from now on
        _make_writable(clear_marker)
        try:
            clear_marker.unlink(missing_ok=True)
        except OSError as e:  # the pointer is written; a stale marker is harmless
            out["warning"] = (f"could not remove the abandoned marker "
                              f"{clear_marker.as_posix()}: {e.strerror}")
    return out


def cmd_demote(workspace: Path) -> dict:
    """Turn a FRESH local review (nothing but its metadata) into an in-place
    one: Phase 1's tracker Write was denied in the local folder. The empty
    reviews/<name>/ is created first and the local folder deleted BEFORE the
    pointer changes, so a failed delete leaves the review exactly as it was,
    and a crash after the delete leaves the state status reports as
    `interrupted_demote`, which demote then finishes."""
    ptr = current_pointer(workspace)
    if ptr is None or ptr["form"] != "local":
        raise Refusal("demote needs an active local review")
    dest = destination(workspace, ptr["name"])
    workdir, where = locate(workspace, ptr)
    if workdir is None and not (where == "missing" and _demote_interrupted(dest)):
        raise Refusal("the review's working files are not on this machine")
    _refuse_linked_destination(dest)
    _require_quotable(dest)
    if workdir is not None:
        files = tree_files(workdir)
        if files != [META_REL]:
            raise Refusal("demote only moves a FRESH review; the working directory already "
                          "holds files", files=[f.as_posix() for f in files[:20]])
        if dest.exists() and not _holds_only_clutter(dest):
            raise Refusal(f"{dest.as_posix()} already holds files")
        created = not dest.exists()
        dest.mkdir(parents=True, exist_ok=True)
        leftover = delete_workdir(workdir)
        if leftover:
            if created:
                try:
                    dest.rmdir()
                except OSError:
                    pass
            raise Refusal("could not remove the local work folder; the review is unchanged",
                          leftover=leftover)
        try:
            workdir.parent.rmdir()
        except OSError:
            pass
    replace_pointer(workspace, {"form": "inplace", "name": ptr["name"]})
    return {"mode": "inplace", "name": ptr["name"], "workdir": dest.as_posix(),
            "destination": dest.as_posix(), "reason": DEMOTE_REASON}


def cmd_resolve(workspace: Path) -> dict:
    """For the SubagentStop hook: {workdir} with ownership proven, else
    {error}. main() prints it and exits 0 either way, except for a
    configuration error, which exits 1 like a crash."""
    try:
        ptr = current_pointer(workspace)
        if ptr is None:
            return {"error": "no active review"}
        if ptr["form"] == "inplace":
            d = destination(workspace, ptr["name"])
            return {"workdir": d.as_posix()} if d.is_dir() else {"error": f"{d.as_posix()} does not exist"}
        workdir, _ = locate(workspace, ptr)
        if workdir is None:
            return {"error": "the review's working files are not on this machine "
                             f"(last worked on {ptr['host'] or 'an unnamed host'})"}
        return {"workdir": workdir.as_posix()}
    except ConfigError:
        raise  # main() prints it and exits 1: the hook's fail-closed crash branch
    except Refusal as e:
        return {"error": str(e)}


# --- publish ------------------------------------------------------------------------

def _copy_file(src: Path, dst: Path) -> None:
    """Copy src over dst, fsync it, then copy its metadata (mode included).
    copyfile first and copystat LAST: copy2 would make a read-only source's
    copy read-only before the fsync could open it for writing, and every
    re-run would then fail writing over that read-only copy."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(dst) and not os.access(dst, os.W_OK):
        os.chmod(dst, stat.S_IREAD | stat.S_IWRITE)  # a read-only copy from an earlier attempt
    shutil.copyfile(src, dst)
    with open(dst, "rb+") as f:  # a write handle: Windows fsync needs one
        os.fsync(f.fileno())
    shutil.copystat(src, dst)


def _copy_file_atomically(src: Path, dst: Path) -> None:
    """_copy_file through a temp name and os.replace, for the metadata file:
    a crash mid-copy leaves nothing half-written at dst, only a temp name
    every tree walk skips."""
    tmp = dst.with_name(f"{dst.name}.{os.getpid()}.tmp")
    _copy_file(src, tmp)
    os.replace(tmp, dst)


def _sweep_stale_meta_temps(root: Path) -> None:
    """Remove metadata temps a crash left in root's intermediate_files/."""
    for p in (root / META_REL.parent).glob(META_REL.name + ".*.tmp"):
        try:
            os.unlink(p)
        except OSError:
            pass


def _finish(workspace: Path, workdir: Path | None, state: str, dest: Path) -> dict:
    """Steps 5-7: mark the local metadata, remove the pointer, delete the
    local copy (metadata last). A failed delete never fails the publish: the
    leftover carries final-state metadata, and the next init or publish
    collects it."""
    leftover: list[str] = []
    if workdir is not None:
        meta = read_meta(workdir)
        if meta is not None:  # never write a partial record over an unreadable one
            meta["state"] = state
            write_meta(workdir, meta)
    remove_pointer(workspace)
    if workdir is not None:
        leftover += delete_workdir(workdir)
        try:
            workdir.parent.rmdir()
        except OSError:
            pass
    leftover += [p for p in collect(workspace) if p not in leftover]
    out = {"mode": "local", "state": state, "published_to": dest.as_posix()}
    try:
        files = [f for f in tree_files(dest) if f != META_REL]
        out.update(files=len(files), bytes=sum((dest / f).stat().st_size for f in files))
    except Refusal:
        pass  # a link someone put into the delivered review; the counts are cosmetic
    if leftover:
        out["leftover"] = leftover
    return out


def _finish_committed(workspace: Path, ptr: dict, dest: Path, marker: dict) -> dict:
    """Branch 1, recovery after a crash anywhere past the commit: never copy
    again. The working directory, if still here, must match the destination
    for every file it still holds; a mismatch means it changed after the
    commit, and nothing is deleted. A file missing from it is a partial
    delete and loses nothing: the destination has it."""
    expected = local_workdir(workspace, ptr["name"])
    workdir, unproven = None, []
    if ptr["workdir"] == expected.as_posix() and os.path.lexists(expected):
        if (expected.is_dir() and not _is_link(expected) and not _is_link(expected.parent)
                and holds_no_files(expected)):
            delete_workdir(expected)  # only empty folders were left; they hold nothing
        else:
            try:
                workdir, _ = locate(workspace, ptr)
            except Refusal as e:
                # The destination marker already proves the delivery, so the
                # publish completes; the unprovable folder is left untouched
                # and reported (status lists it as stranded).
                unproven = [str(e)]
    differing = []
    if workdir is not None:
        try:
            differing = [rel.as_posix() for rel in tree_files(workdir)
                         if rel != META_REL and not same_file(workdir / rel, dest / rel)]
        except (Refusal, OSError) as e:
            # A folder that cannot be compared is left as it is, unmarked and
            # undeleted, like an unprovable one; the delivery still stands.
            workdir, unproven = None, [str(e)]
        if differing:
            w, n = workdir.as_posix(), ptr["name"]
            raise Refusal(f"the working directory {w} and the published copy in reviews/{n}/ "
                          "differ in these files; nothing was deleted. The review is already "
                          f"delivered: if reviews/{n}/ is what you want, delete {w} and "
                          "reviews/.active-review by hand; otherwise copy those files from "
                          f"{w} into reviews/{n}/ and run publish again", differing=differing)
    out = _finish(workspace, workdir, marker["state"], dest)
    if unproven:
        out["unproven"] = unproven
    return out


def _copy_commit(workspace: Path, ptr: dict, workdir: Path, dest: Path, state: str) -> dict:
    """Branch 3: fresh, or an interrupted copy of this review. PRECONDITION
    (SKILL.md, prose): nothing is still writing the tree. The before/after
    manifests catch a write that lands during the copy; one that lands
    between the final check and the commit is the precondition's alone."""
    if _is_link(dest):  # a linked reviews/ is the user's layout; no delete touches it
        raise Refusal(f"{dest.as_posix()} is a link; refusing to copy into it")
    src_files = tree_files(workdir)
    before = manifest(workdir, src_files)
    if os.path.lexists(dest):
        tree_files(dest)  # a partial copy must hold no planted link either
    # 1. metadata FIRST: a partial destination is provably this review's
    _copy_file_atomically(workdir / META_REL, dest / META_REL)
    # 2. the rest; the source is authoritative
    for rel in src_files:
        if rel != META_REL:
            _copy_file(workdir / rel, dest / rel)
    # 2b. The source is authoritative: remove what only the (uncommitted,
    # provably ours) destination holds, such as a file the source renamed
    # away or a .DS_Store a file manager added. Branch 3 runs only on an
    # absent, empty or own-marker destination, and step 1 just wrote ours.
    src_set = set(src_files)
    for rel in tree_files(dest):
        if rel not in src_set:
            _make_writable(dest / rel)  # a read-only source's copy keeps its mode
            try:
                (dest / rel).unlink()
            except OSError as e:
                raise Refusal(f"could not remove {rel.as_posix()} from the half-published copy "
                              f"in {dest.as_posix()}: {e.strerror}; nothing was committed; "
                              "run publish again")
    # 3. verify: the source did not change, and the copy equals it exactly
    after = manifest(workdir, tree_files(workdir))
    copied = manifest(dest, tree_files(dest))
    if not before == after == copied:
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        mismatched = sorted(k for k in after if copied.get(k) != after[k])
        extra = sorted(set(copied) - set(after))
        raise Refusal("the copy does not match the working directory; nothing was "
                      "committed (was something still writing?)",
                      changed_during_copy=changed, mismatched=mismatched, extra=extra)
    # 4. commit: the reduced marker carries no host and no path. An abandoned
    # one carries the manifest, so activate can tell a half-synced copy.
    marker = {"format": FORMAT, "review_id": ptr["review_id"], "name": ptr["name"],
              "state": state, "published": now()}
    if state == "abandoned":
        marker["files"] = {k: list(v) for k, v in after.items() if not _is_clutter(Path(k))}
    write_meta(dest, marker)
    _sweep_stale_meta_temps(dest)
    return _finish(workspace, workdir, state, dest)


def _publish_inplace(workspace: Path, ptr: dict, state: str) -> dict:
    dest = destination(workspace, ptr["name"])
    for p in (dest, dest / "intermediate_files"):
        if _is_link(p):
            raise Refusal(f"{p.as_posix()} is a link; refusing to write through it")
    if state == "abandoned":
        # The reduced marker keeps an unfinished review discoverable even
        # after its tracker moves; activate removes it again. Never on a
        # delivered review (final file or .completed-review present): the
        # init guard for an existing review runs --abandon on one, and a
        # delivered review is never changed.
        if (dest.is_dir() and not (dest / f"literature-review-{ptr['name']}.md").exists()
                and not (dest / COMPLETED_REL).exists()
                and not ((m := read_meta(dest)) is not None and m.get("state") == "published")):
            (dest / "intermediate_files").mkdir(exist_ok=True)
            marker = {"format": FORMAT, "review_id": None, "name": ptr["name"],
                      "state": "abandoned", "published": now()}
            try:  # the manifest lets activate tell a half-synced copy
                marker["files"] = {k: list(v) for k, v in manifest(dest, tree_files(dest)).items()
                                   if not _is_clutter(Path(k))}
            except (Refusal, OSError):
                pass  # a link or an unreadable file: no manifest, activate cannot verify
            write_meta(dest, marker)
        remove_pointer(workspace)
    else:
        if not dest.is_dir():
            raise Refusal(f"{dest.as_posix()} does not exist; there is nothing to publish")
        marker = read_meta(dest)
        if marker is not None and marker.get("state") == "published":
            raise Refusal(f"{dest.as_posix()} is a delivered review (its marker says published) "
                          "and is never published again; run `workdir.py publish --abandon` to "
                          "clear the pointer")
        (dest / "intermediate_files").mkdir(exist_ok=True)
        _make_writable(dest / COMPLETED_REL)
        os.replace(workspace / POINTER_REL, dest / COMPLETED_REL)
    return {"mode": "inplace", "state": state, "published_to": dest.as_posix()}


def cmd_publish(workspace: Path, abandon: bool) -> dict:
    """Phase 6's last step (and, with --abandon, how an unfinished review is
    set aside). The first matching branch runs: already committed ->
    recovery; destination foreign -> refuse; otherwise copy, verify, commit."""
    ptr = current_pointer(workspace)
    if ptr is None:
        raise Refusal("no active review; if its pointer was deleted, run "
                      "`workdir.py activate <name>`, then publish again")
    state = "abandoned" if abandon else "published"
    if ptr["form"] == "inplace":
        return _publish_inplace(workspace, ptr, state)
    dest = destination(workspace, ptr["name"])
    marker = committed(workspace, ptr)
    if marker:
        return _finish_committed(workspace, ptr, dest, marker)
    if os.path.lexists(dest):
        existing = read_meta(dest)
        # A destination holding no files is what a crash inside step 1 leaves
        # (an empty intermediate_files/, or a temp every walk skips): nothing
        # there to protect, and OS clutter (.DS_Store) is not a file either.
        # A READABLE marker naming another review always refuses, and a
        # folder the walk cannot list refuses (tree_files).
        foreign = (existing.get("review_id") != ptr["review_id"] if existing is not None
                   else not (dest.is_dir() and not _is_link(dest)
                             and all(_is_clutter(r) for r in tree_files(dest))))
        if foreign:
            raise Refusal(f"{dest.as_posix()} already exists and is not this review's; "
                          "nothing was copied. To set this review aside, delete "
                          "reviews/.active-review by hand: its files stay in the local work "
                          f"folder and are listed as abandoned. The folder at {dest.as_posix()} "
                          "belongs to someone else: move or rename it before publishing under "
                          "this name", destination=dest.as_posix())
    workdir, where = locate(workspace, ptr)
    if workdir is None:
        raise Refusal("the review's working files are not on this machine "
                      f"({where}); nothing was copied")
    return _copy_commit(workspace, ptr, workdir, dest, state)


# --- CLI ------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """--workspace does not move .env discovery; a caller passing it runs
    from the workspace (the hook cd's there)."""
    load_dotenv(find_dotenv(usecwd=True), override=True)
    parser = argparse.ArgumentParser(
        description="Owner of the review working directory (see the module docstring).")
    parser.add_argument("--workspace", type=Path, default=None,
                        help="the PhilLit workspace (default: the current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create a new review and its pointer").add_argument("name")
    sub.add_parser("status", help="report the active or abandoned reviews (read-only)")
    sub.add_parser("activate", help="re-attach an abandoned review").add_argument("name")
    sub.add_parser("demote", help="turn a fresh local review into an in-place one")
    p = sub.add_parser("publish", help="copy the review into reviews/<name>/ and clear the pointer")
    p.add_argument("--abandon", action="store_true", help="set an unfinished review aside")
    sub.add_parser("resolve", help="print the active working directory (for hooks; exits 0)")
    args = parser.parse_args(argv)
    try:
        workspace = (args.workspace or Path.cwd()).resolve()
        requested_mode()  # a bad value is an error for every subcommand
        if args.command == "init":
            result = cmd_init(workspace, args.name)
        elif args.command == "status":
            result = cmd_status(workspace)
        elif args.command == "activate":
            result = cmd_activate(workspace, args.name)
        elif args.command == "demote":
            result = cmd_demote(workspace)
        elif args.command == "publish":
            result = cmd_publish(workspace, args.abandon)
        else:
            result = cmd_resolve(workspace)
    except Refusal as e:
        if args.command == "resolve":
            print(dumps({"error": str(e)}))
            return 1 if isinstance(e, ConfigError) else 0
        print(dumps({"error": str(e), **e.extra}))
        return 2
    except Exception as e:  # still one JSON object; exit 1 reads as a crash
        print(dumps({"error": f"workdir.py crashed: {type(e).__name__}: {e}"}))
        return 1
    print(dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
