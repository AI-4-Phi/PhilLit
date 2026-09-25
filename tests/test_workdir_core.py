"""Unit tests for workdir.py's foundation: location, mode, rule detection,
names, the two pointer forms, metadata and ownership. HOME and
CLAUDE_CONFIG_DIR point into tmp_path, so nothing touches the real ~."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"))
import workdir as wd  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(h / ".claude"))
    monkeypatch.delenv("PHILLIT_WORKDIR", raising=False)
    return h


@pytest.fixture
def ws(tmp_path):
    w = tmp_path / "My Workspace"
    w.mkdir()
    return w.resolve()


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as e:  # Windows without Developer Mode or elevation
        pytest.skip(f"symlinks need privileges here: {e}")


def test_local_root_is_fixed_under_home(home):
    assert wd.local_root() == home / ".local" / "state" / "phillit" / "reviews"


def test_local_root_ignores_xdg_state_home(home, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    assert wd.local_root() == home / ".local" / "state" / "phillit" / "reviews"


def test_ws_key_is_slug_plus_hash(ws):
    key = wd.ws_key(ws)
    base, digest = key.rsplit("-", 1)
    assert base == "my-workspace"
    assert len(digest) == 16 and all(c in "0123456789abcdef" for c in digest)


def test_ws_key_slug_is_cut_to_20_chars(tmp_path):
    w = tmp_path / ("A" * 40)
    w.mkdir()
    assert len(wd.ws_key(w).rsplit("-", 1)[0]) <= 20


def test_ws_key_same_for_symlinked_path(ws, tmp_path):
    link = tmp_path / "link-to-ws"
    _symlink(link, ws)
    assert wd.ws_key(link) == wd.ws_key(ws)
    assert wd.workspace_id(link) == wd.workspace_id(ws)


def test_ws_key_differs_for_two_workspaces(tmp_path):
    a, b = tmp_path / "a" / "ws", tmp_path / "b" / "ws"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    assert wd.ws_key(a) != wd.ws_key(b)


def test_local_workdir_keeps_a_reviews_segment(home, ws):
    p = wd.local_workdir(ws, "topic")
    assert "reviews" in p.parts and p.name == "topic"
    assert p.parent.parent == wd.local_root()


@pytest.mark.parametrize("value,expected", [(None, None), ("", None), ("local", "local"), ("inplace", "inplace")])
def test_requested_mode(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("PHILLIT_WORKDIR", raising=False)
    else:
        monkeypatch.setenv("PHILLIT_WORKDIR", value)
    assert wd.requested_mode() == expected


def test_requested_mode_rejects_other_values(monkeypatch):
    monkeypatch.setenv("PHILLIT_WORKDIR", "tmp")
    with pytest.raises(wd.ConfigError, match="'tmp'"):
        wd.requested_mode()


def _settings(path: Path, allow):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"permissions": {"allow": allow}}), encoding="utf-8")


@pytest.mark.parametrize("where", ["settings.json", "settings.local.json"])
def test_rule_found_in_workspace_settings(home, ws, where):
    assert not wd.allow_rule_present(ws)
    _settings(ws / ".claude" / where, ["Bash", wd.ALLOW_RULE])
    assert wd.allow_rule_present(ws)


def test_rule_found_in_claude_config_dir(home, ws, monkeypatch, tmp_path):
    work = tmp_path / "claude-work"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(work))
    _settings(work / "settings.json", [wd.ALLOW_RULE])
    assert wd.allow_rule_present(ws)


def test_rule_found_in_home_claude_when_config_dir_unset(home, ws, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    _settings(home / ".claude" / "settings.json", [wd.ALLOW_RULE])
    assert wd.allow_rule_present(ws)


def test_rule_detection_is_exact_string_and_tolerates_bad_files(home, ws):
    _settings(ws / ".claude" / "settings.json", ["Edit(~/.local/state/phillit/**)"])
    (ws / ".claude" / "settings.local.json").write_text("{not json", encoding="utf-8")
    assert not wd.allow_rule_present(ws)
    _settings(ws / ".claude" / "settings.json", wd.ALLOW_RULE)  # a bare string, hand-edited
    assert wd.allow_rule_present(ws)


@pytest.mark.parametrize("name", ["topic", "a", "epistemic-autonomy-ai", "v1.2_x", "0123456789abcdef", "A" * 64])
def test_valid_names(name):
    assert wd.name_problem(name) is None


@pytest.mark.parametrize("name", ["", "-x", ".x", "a/b", "a b", "x.", "A" * 65, "CON", "nul", "Com1.txt", "LPT9", "a$b"])
def test_invalid_names(name):
    assert wd.name_problem(name) is not None


@pytest.mark.parametrize("ch", ["$", "`", '"', "\\", "\n"])
def test_unsafe_char_detected(ch):
    assert wd.unsafe_char(Path(f"/Users/a{ch}b/x")) == ch


def test_bang_is_safe():
    assert wd.unsafe_char(Path("/Users/a!b/x")) is None


def test_length_problem_only_on_windows(tmp_path):
    long = Path("C:/Users/" + "x" * 140)
    assert wd.length_problem([long], windows=False) is None
    assert "too long" in wd.length_problem([long], windows=True)
    assert wd.length_problem([Path("C:/Users/x/reviews/topic")], windows=True) is None


def test_pointer_absent(ws):
    assert wd.read_pointer(ws) is None


def test_legacy_inplace_pointer(ws):
    (ws / "reviews").mkdir()
    (ws / "reviews" / ".active-review").write_text("reviews/old-review\n", encoding="utf-8")
    assert wd.read_pointer(ws) == {"form": "inplace", "name": "old-review"}


def test_inplace_pointer_crlf_and_trailing_slash(ws):
    (ws / "reviews").mkdir()
    (ws / "reviews" / ".active-review").write_bytes(b"reviews/old-review/\r\n")
    assert wd.read_pointer(ws) == {"form": "inplace", "name": "old-review"}


def _local_ptr(name="topic", workdir="/x/y", review_id="ab" * 16, host="dove"):
    return {"form": "local", "review_id": review_id, "name": name, "host": host, "workdir": workdir}


def test_local_pointer_round_trip(ws):
    ptr = _local_ptr()
    wd.create_pointer(ws, ptr)
    assert wd.read_pointer(ws) == ptr
    line = (ws / "reviews" / ".active-review").read_text(encoding="utf-8")
    assert line.count("\n") == 1 and json.loads(line)["mode"] == "local"


def test_create_pointer_is_exclusive(ws):
    wd.create_pointer(ws, _local_ptr())
    with pytest.raises(FileExistsError):
        wd.create_pointer(ws, _local_ptr(name="other"))


def test_replace_and_remove_pointer(ws):
    wd.create_pointer(ws, _local_ptr())
    wd.replace_pointer(ws, {"form": "inplace", "name": "topic"})
    assert wd.read_pointer(ws) == {"form": "inplace", "name": "topic"}
    wd.remove_pointer(ws)
    wd.remove_pointer(ws)  # idempotent
    assert wd.read_pointer(ws) is None


@pytest.mark.parametrize("text", ["garbage", "reviews/", "reviews/a/b", "reviews/..", '{"format": 1}',
                                  '{"format": 1, "mode": "local", "review_id": "x", "name": "../etc", "host": "h", "workdir": "/w"}'])


def test_bad_pointers_refuse(ws, text):
    (ws / "reviews").mkdir()
    (ws / "reviews" / ".active-review").write_text(text, encoding="utf-8")
    with pytest.raises(wd.Refusal, match=r"\(to detach it, delete reviews/\.active-review by hand\)$"):
        wd.read_pointer(ws)


def test_meta_round_trip_and_atomic(tmp_path):
    d = tmp_path / "review"
    (d / "intermediate_files").mkdir(parents=True)
    wd.write_meta(d, {"format": 1, "state": "active"})
    assert wd.read_meta(d) == {"format": 1, "state": "active"}
    assert [p.name for p in (d / "intermediate_files").iterdir()] == [".phillit-review.json"]


def test_read_meta_rejects_wrong_format(tmp_path):
    d = tmp_path / "review"
    (d / "intermediate_files").mkdir(parents=True)
    wd.meta_path(d).write_text('{"format": 2}', encoding="utf-8")
    assert wd.read_meta(d) is None


def test_tree_files_refuses_symlink(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    (d / "a.txt").write_text("a", encoding="utf-8")
    assert wd.tree_files(d) == [Path("a.txt")]
    _symlink(d / "link", tmp_path)
    with pytest.raises(wd.Refusal, match="is a link"):
        wd.tree_files(d)


def test_tree_files_refuses_fifo(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("no FIFOs on this platform")
    d = tmp_path / "t"
    d.mkdir()
    os.mkfifo(d / "pipe")
    with pytest.raises(wd.Refusal, match="regular file"):
        wd.tree_files(d)


def _review_tree(d: Path) -> None:
    (d / "intermediate_files" / "json").mkdir(parents=True)
    (d / "a.md").write_text("a", encoding="utf-8")
    (d / "intermediate_files" / "json" / "x.json").write_text("{}", encoding="utf-8")
    wd.write_meta(d, {"format": 1, "state": "published"})


def test_delete_workdir_removes_everything(tmp_path):
    d = tmp_path / "review"
    _review_tree(d)
    assert wd.delete_workdir(d) == []
    assert not d.exists()


def test_interrupted_delete_leaves_the_metadata_file(tmp_path, monkeypatch):
    d = tmp_path / "review"
    _review_tree(d)
    real_unlink = os.unlink

    def flaky_unlink(p, *a, **k):
        if str(p).endswith("x.json"):
            raise PermissionError("locked")
        return real_unlink(p, *a, **k)

    monkeypatch.setattr(os, "unlink", flaky_unlink)
    monkeypatch.setattr(os, "chmod", lambda *a, **k: None)
    leftover = wd.delete_workdir(d)
    assert any(p.endswith("x.json") for p in leftover)
    assert wd.meta_path(d).is_file()  # still says what it is


def test_delete_workdir_keeps_the_metadata_when_a_folder_cannot_be_listed(tmp_path):
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("POSIX permission bits, as a non-root user")
    d = tmp_path / "review"
    _review_tree(d)
    (d / "intermediate_files" / "notes.md").write_text("n", encoding="utf-8")
    (d / "intermediate_files").chmod(0o300)  # write+search, no read: the walk cannot list it
    try:
        leftover = wd.delete_workdir(d)
    finally:
        (d / "intermediate_files").chmod(0o755)
    assert (d / "intermediate_files").as_posix() in leftover
    assert wd.meta_path(d).is_file()  # still says what it is


def test_delete_workdir_of_a_vanished_folder_leaves_nothing(tmp_path):
    assert wd.delete_workdir(tmp_path / "gone") == []  # nothing unseen: nothing left over


def test_delete_workdir_unlinks_a_planted_dir_link_without_following(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    d = tmp_path / "review"
    _review_tree(d)
    _symlink(d / "sneaky", outside)
    assert wd.delete_workdir(d) == []
    assert (outside / "keep.txt").is_file()


def test_holds_no_files(tmp_path):
    d = tmp_path / "d"
    (d / "intermediate_files").mkdir(parents=True)
    assert wd.holds_no_files(d)
    (d / "intermediate_files" / "f").write_text("x", encoding="utf-8")
    assert not wd.holds_no_files(d)


def _owned_review(ws: Path, name="topic") -> dict:
    d = wd.local_workdir(ws, name)
    (d / "intermediate_files").mkdir(parents=True)
    rid = "cd" * 16
    wd.write_meta(d, {"format": 1, "review_id": rid, "name": name, "workspace": wd.workspace_id(ws),
                      "host": "dove", "state": "active", "created": wd.now()})
    return {"form": "local", "review_id": rid, "name": name, "host": "dove", "workdir": d.as_posix()}


def test_locate_proves_ownership(home, ws):
    ptr = _owned_review(ws)
    assert wd.locate(ws, ptr) == (wd.local_workdir(ws, "topic"), None)


def test_locate_missing_and_elsewhere(home, ws):
    ptr = _owned_review(ws)
    wd.delete_workdir(wd.local_workdir(ws, "topic"))
    assert wd.locate(ws, ptr) == (None, "missing")
    assert wd.locate(ws, {**ptr, "workdir": "/Users/other/.local/state/phillit/reviews/k/topic"}) == (None, "elsewhere")


def test_windows_pointer_read_on_posix_is_elsewhere(home, ws):
    ptr = _owned_review(ws)
    win = {**ptr, "workdir": "C:/Users/me/.local/state/phillit/reviews/" + wd.ws_key(ws) + "/topic"}
    assert wd.locate(ws, win) == (None, "elsewhere")


@pytest.mark.parametrize("field,value", [("review_id", "ee" * 16), ("name", "other"), ("workspace", "/elsewhere")])
def test_locate_refuses_mismatched_metadata(home, ws, field, value):
    ptr = _owned_review(ws)
    d = wd.local_workdir(ws, "topic")
    meta = wd.read_meta(d)
    meta[field] = value
    wd.write_meta(d, meta)
    with pytest.raises(wd.Refusal):
        wd.locate(ws, ptr)


def test_locate_refuses_symlinked_workdir(home, ws, tmp_path):
    ptr = _owned_review(ws)
    d = wd.local_workdir(ws, "topic")
    real = tmp_path / "real"
    d.rename(real)
    _symlink(d, real)
    with pytest.raises(wd.Refusal, match="is a link"):
        wd.locate(ws, ptr)


def test_committed_reads_the_destination_marker(home, ws):
    ptr = _owned_review(ws)
    dest = wd.destination(ws, "topic")
    (dest / "intermediate_files").mkdir(parents=True)
    assert wd.committed(ws, ptr) is None
    wd.write_meta(dest, {"format": 1, "review_id": ptr["review_id"], "name": "topic", "state": "active"})
    assert wd.committed(ws, ptr) is None
    wd.write_meta(dest, {"format": 1, "review_id": ptr["review_id"], "name": "topic", "state": "published"})
    assert wd.committed(ws, ptr)["state"] == "published"


@pytest.mark.parametrize("tag,is_link", [
    (0xA0000003, True),    # IO_REPARSE_TAG_MOUNT_POINT: a junction
    (0xA000000C, True),    # IO_REPARSE_TAG_SYMLINK
    (0x9000601A, False)])  # a cloud-files tag: a OneDrive Files On-Demand placeholder
def test_is_link_counts_only_name_surrogate_reparse_points(monkeypatch, tmp_path, tag, is_link):
    # A junction on Python < 3.12 is not S_ISLNK; the reparse attribute is
    # the signal, and the tag's name-surrogate bit says it redirects a walk.
    import types
    d = tmp_path / "j"
    d.mkdir()
    real_lstat = os.lstat

    def fake_lstat(p, *a, **k):
        st = real_lstat(p, *a, **k)
        if Path(p) == d:
            return types.SimpleNamespace(st_mode=st.st_mode, st_file_attributes=0x400,
                                         st_reparse_tag=tag)
        return st

    monkeypatch.setattr(os, "lstat", fake_lstat)
    assert wd._is_link(d) is is_link
    assert not wd._is_link(tmp_path)


def test_manifest_skips_the_metadata_file(tmp_path):
    d = tmp_path / "r"
    _review_tree(d)
    m = wd.manifest(d, wd.tree_files(d))
    assert set(m) == {"a.md", "intermediate_files/json/x.json"}
    assert m["a.md"][0] == 1


_POSIX_PERMS = pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="POSIX permission bits, as a non-root user")


@_POSIX_PERMS
def test_make_writable_clears_a_read_only_file(tmp_path):
    f = tmp_path / "ro.txt"
    f.write_text("x", encoding="utf-8")
    f.chmod(0o444)
    wd._make_writable(f)
    assert os.access(f, os.W_OK)
    wd._make_writable(tmp_path / "absent")  # a missing target is fine


@_POSIX_PERMS
def test_tree_files_refuses_a_folder_it_cannot_search(tmp_path):
    d = tmp_path / "t"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "f.txt").write_text("x", encoding="utf-8")
    (d / "sub").chmod(0o600)  # readable, not searchable: names list, lstat fails
    try:
        with pytest.raises(wd.Refusal, match="cannot inspect .*refusing to copy or delete"):
            wd.tree_files(d)
    finally:
        (d / "sub").chmod(0o755)


def test_walk_errors_print_posix_paths(monkeypatch):
    from pathlib import PureWindowsPath
    monkeypatch.setattr(wd, "Path", PureWindowsPath)  # as on Windows
    with pytest.raises(wd.Refusal, match="^cannot list C:/Users/me/x: Access is denied"):
        wd._walk_error(PermissionError(13, "Access is denied", "C:\\Users\\me\\x"))


def test_holds_no_files_fails_closed_on_an_unlistable_folder(tmp_path):
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("POSIX permission bits, as a non-root user")
    d = tmp_path / "d"
    (d / "sub").mkdir(parents=True)
    (d / "sub").chmod(0o000)
    try:
        assert wd.holds_no_files(d) is False
        with pytest.raises(wd.Refusal, match="cannot list"):
            wd.tree_files(d)
    finally:
        (d / "sub").chmod(0o755)
