"""workdir.py subcommands: init, status, activate, demote, resolve, the
garbage collector and the CLI. HOME / CLAUDE_CONFIG_DIR point into tmp_path."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))
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
    w = tmp_path / "ws"
    w.mkdir()
    return w.resolve()


@pytest.fixture
def ruled(ws):
    """A workspace whose settings carry the standard allow rule."""
    (ws / ".claude").mkdir()
    (ws / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [wd.ALLOW_RULE]}}), encoding="utf-8")
    return ws


# --- init -------------------------------------------------------------------
def test_init_local(home, ruled):
    out = wd.cmd_init(ruled, "topic")
    local = wd.local_workdir(ruled, "topic")
    assert out["mode"] == "local" and "reason" not in out
    assert out["workdir"] == local.as_posix()
    assert out["destination"] == (ruled / "reviews" / "topic").as_posix()
    meta = wd.read_meta(local)
    assert meta["state"] == "active" and meta["workspace"] == wd.workspace_id(ruled)
    ptr = wd.read_pointer(ruled)
    assert ptr["form"] == "local" and ptr["review_id"] == meta["review_id"]
    assert not (ruled / "reviews" / "topic").exists()


def test_init_local_root_is_private(home, ruled):
    if os.name == "nt":
        pytest.skip("POSIX modes only")
    wd.cmd_init(ruled, "topic")
    assert (wd.local_root().stat().st_mode & 0o777) == 0o700


def test_init_without_rule_falls_back_in_place(home, ws):
    out = wd.cmd_init(ws, "topic")
    assert out["mode"] == "inplace" and out["reason"] == wd.MISSING_RULE_REASON
    assert out["workdir"] == (ws / "reviews" / "topic").as_posix()
    assert wd.read_pointer(ws) == {"form": "inplace", "name": "topic"}
    assert not wd.local_root().exists()


def test_init_unsafe_local_path_falls_back(home, ruled, monkeypatch, tmp_path):
    odd = tmp_path / "ho$me"
    odd.mkdir()
    monkeypatch.setenv("HOME", str(odd))
    out = wd.cmd_init(ruled, "topic")
    assert out["mode"] == "inplace" and "'$'" in out["reason"]


def test_init_unsafe_inplace_path_refuses(home, tmp_path):
    w = tmp_path / 'we"ird'
    w.mkdir()
    with pytest.raises(wd.Refusal, match="cannot quote"):
        wd.cmd_init(w.resolve(), "topic")


def test_init_explicit_inplace(home, ruled, monkeypatch):
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    out = wd.cmd_init(ruled, "topic")
    assert out["mode"] == "inplace" and "reason" not in out


def test_init_refuses_when_pointer_exists(home, ruled):
    wd.cmd_init(ruled, "topic")
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_init(ruled, "other")
    assert e.value.extra["active"]["name"] == "topic"


def test_init_refuses_bad_name(home, ruled):
    with pytest.raises(wd.Refusal, match="reserved"):
        wd.cmd_init(ruled, "CON")


def test_init_local_refuses_existing_destination_even_empty(home, ruled):
    (ruled / "reviews" / "topic").mkdir(parents=True)
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_init(ruled, "topic")
    assert e.value.extra["suggested_name"] == "topic-2"
    assert wd.read_pointer(ruled) is None


def test_init_local_refuses_existing_local_dir_and_skips_taken_suggestions(home, ruled):
    (ruled / "reviews" / "topic-2").mkdir(parents=True)
    wd.local_workdir(ruled, "topic").mkdir(parents=True)
    (wd.local_workdir(ruled, "topic") / "stray.txt").write_text("x", encoding="utf-8")
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_init(ruled, "topic")
    assert e.value.extra["suggested_name"] == "topic-3"


def test_suggest_name_stays_within_64_chars(home, ruled):
    name = "a" * 64
    (ruled / "reviews" / name).mkdir(parents=True)
    s = wd.suggest_name(ruled, name)
    assert len(s) <= 64 and s.endswith("-2") and wd.name_problem(s) is None


def test_init_inplace_accepts_the_services_empty_folder(home, ws, monkeypatch):
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    (ws / "reviews" / "0123456789abcdef").mkdir(parents=True)
    out = wd.cmd_init(ws, "0123456789abcdef")
    assert out["mode"] == "inplace" and "existing_review" not in out
    assert wd.read_pointer(ws) == {"form": "inplace", "name": "0123456789abcdef"}


def test_init_inplace_flags_a_finished_review(home, ws, monkeypatch):
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    (ws / "reviews" / "topic").mkdir(parents=True)
    (ws / "reviews" / "topic" / "literature-review-topic.md").write_text("x", encoding="utf-8")
    out = wd.cmd_init(ws, "topic")
    assert out["existing_review"] is True and out["suggested_name"] == "topic-2"
    assert wd.read_pointer(ws) == {"form": "inplace", "name": "topic"}


def test_init_loses_a_pointer_race_cleanly(home, ruled, monkeypatch):
    real = wd.create_pointer

    def racing(ws_, ptr):
        real(ws_, {"form": "inplace", "name": "winner"})
        real(ws_, ptr)

    monkeypatch.setattr(wd, "create_pointer", racing)
    with pytest.raises(wd.Refusal, match="first"):
        wd.cmd_init(ruled, "topic")
    assert not wd.local_workdir(ruled, "topic").exists()
    assert wd.read_pointer(ruled) == {"form": "inplace", "name": "winner"}


def test_init_checks_destination_length_on_windows(home, ruled, monkeypatch):
    dest = wd.destination(ruled, "topic")
    monkeypatch.setattr(wd, "length_problem",
                        lambda paths, windows=None: "too long" if dest in paths else None)
    with pytest.raises(wd.Refusal, match="too long"):
        wd.cmd_init(ruled, "topic")
    assert wd.read_pointer(ruled) is None


# --- garbage collection ------------------------------------------------------
def _finish(ws, name, state="published"):
    """Simulate a committed publish whose local delete failed."""
    local = wd.local_workdir(ws, name)
    meta = wd.read_meta(local)
    meta["state"] = state
    wd.write_meta(local, meta)
    dest = wd.destination(ws, name)
    (dest / "intermediate_files").mkdir(parents=True, exist_ok=True)
    wd.write_meta(dest, {"format": 1, "review_id": meta["review_id"], "name": name,
                         "state": state, "published": wd.now()})
    wd.remove_pointer(ws)
    return local


def test_next_init_collects_a_committed_leftover(home, ruled):
    wd.cmd_init(ruled, "old")
    local = _finish(ruled, "old")
    (local / "big.json").write_text("x", encoding="utf-8")
    wd.cmd_init(ruled, "new")
    assert not local.exists()


def test_collect_spares_uncommitted_and_foreign_dirs(home, ruled):
    wd.cmd_init(ruled, "keep")
    wd.remove_pointer(ruled)  # abandoned by hand: metadata still "active"
    nometa = wd.local_workdir(ruled, "nometa")
    nometa.mkdir(parents=True)
    (nometa / "f.txt").write_text("x", encoding="utf-8")
    empty = wd.local_workdir(ruled, "crashed")
    (empty / "intermediate_files").mkdir(parents=True)
    wd.collect(ruled)
    assert wd.local_workdir(ruled, "keep").exists()
    assert nometa.exists()
    assert not empty.exists()


def test_collect_requires_matching_destination_marker(home, ruled):
    wd.cmd_init(ruled, "old")
    local = _finish(ruled, "old")
    dest = wd.destination(ruled, "old")
    marker = wd.read_meta(dest)
    marker["review_id"] = "ff" * 16
    wd.write_meta(dest, marker)
    wd.collect(ruled)
    assert local.exists()


# --- status ------------------------------------------------------------------
def test_status_is_read_only(home, ruled):
    wd.cmd_init(ruled, "topic")
    before = sorted((p.as_posix(), p.stat().st_mtime_ns) for p in Path(home).rglob("*"))
    before_ws = sorted((p.as_posix(), p.stat().st_mtime_ns) for p in ruled.rglob("*"))
    wd.cmd_status(ruled)
    assert before == sorted((p.as_posix(), p.stat().st_mtime_ns) for p in Path(home).rglob("*"))
    assert before_ws == sorted((p.as_posix(), p.stat().st_mtime_ns) for p in ruled.rglob("*"))


def test_status_active_local(home, ruled):
    wd.cmd_init(ruled, "topic")
    out = wd.cmd_status(ruled)
    assert out == {"active": True, "mode": "local", "name": "topic",
                   "workdir": wd.local_workdir(ruled, "topic").as_posix(),
                   "destination": wd.destination(ruled, "topic").as_posix()}


def test_status_from_symlinked_workspace_form(home, ruled, tmp_path):
    wd.cmd_init(ruled, "topic")
    link = tmp_path / "onedrive-form"
    link.symlink_to(ruled, target_is_directory=True)
    out = wd.cmd_status(link.resolve())
    assert out["active"] and out["mode"] == "local"


def test_status_active_inplace(home, ws):
    wd.cmd_init(ws, "topic")
    out = wd.cmd_status(ws)
    assert out["mode"] == "inplace" and out["workdir"] == (ws / "reviews" / "topic").as_posix()


def test_status_committed_with_or_without_local_dir(home, ruled):
    wd.cmd_init(ruled, "topic")
    ptr = wd.read_pointer(ruled)
    local = _finish(ruled, "topic")
    wd.create_pointer(ruled, ptr)  # the crash came before the pointer removal
    assert wd.cmd_status(ruled)["committed"] is True
    wd.delete_workdir(local)
    assert wd.cmd_status(ruled)["committed"] is True


def test_status_elsewhere(home, ruled):
    wd.cmd_init(ruled, "topic")
    wd.delete_workdir(wd.local_workdir(ruled, "topic"))
    out = wd.cmd_status(ruled)
    assert out["elsewhere"] is True and out["host"]


def test_changed_hostname_does_not_block_resume(home, ruled, monkeypatch):
    wd.cmd_init(ruled, "topic")
    monkeypatch.setattr(wd.platform, "node", lambda: "other-name.local")
    assert wd.cmd_status(ruled)["mode"] == "local"


def test_status_inplace_env_meets_local_pointer(home, ruled, monkeypatch):
    wd.cmd_init(ruled, "topic")
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    with pytest.raises(wd.Refusal, match="unset PHILLIT_WORKDIR"):
        wd.cmd_status(ruled)


def test_status_lists_abandoned_and_stranded(home, ruled, tmp_path):
    wd.cmd_init(ruled, "loc")
    wd.remove_pointer(ruled)
    old = ruled / "reviews" / "old-inplace"
    old.mkdir(parents=True)
    (old / "task-progress.md").write_text("x", encoding="utf-8")
    delivered = ruled / "reviews" / "delivered"
    (delivered / "intermediate_files").mkdir(parents=True)
    (delivered / "task-progress.md").write_text("x", encoding="utf-8")
    wd.write_meta(delivered, {"format": 1, "review_id": "x", "name": "delivered", "state": "published"})
    gone_ws = tmp_path / "gone"  # a workspace that was moved away: never created here
    lost = wd.local_workdir(gone_ws, "lost")
    (lost / "intermediate_files").mkdir(parents=True)
    wd.write_meta(lost, {"format": 1, "review_id": "y", "name": "lost", "workspace": gone_ws.as_posix(),
                         "host": "h", "state": "active", "created": wd.now()})
    out = wd.cmd_status(ruled)
    assert out["active"] is False
    assert {(a["name"], a["mode"]) for a in out["abandoned"]} == {("loc", "local"), ("old-inplace", "inplace")}
    assert [s["path"] for s in out["stranded"]] == [lost.as_posix()]
    assert "ownership cannot be proven" in out["stranded"][0]["note"]


# --- activate ----------------------------------------------------------------
def test_activate_local(home, ruled):
    wd.cmd_init(ruled, "topic")
    wd.remove_pointer(ruled)
    out = wd.cmd_activate(ruled, "topic")
    assert out["mode"] == "local" and wd.read_pointer(ruled)["name"] == "topic"


def test_activate_inplace_and_clears_an_abandoned_marker(home, ws):
    d = ws / "reviews" / "topic"
    (d / "intermediate_files").mkdir(parents=True)
    (d / "task-progress.md").write_text("x", encoding="utf-8")
    wd.write_meta(d, {"format": 1, "review_id": "r", "name": "topic", "state": "abandoned"})
    out = wd.cmd_activate(ws, "topic")
    assert out["mode"] == "inplace" and not wd.meta_path(d).exists()
    assert wd.read_pointer(ws) == {"form": "inplace", "name": "topic"}


def test_activate_refuses_a_delivered_review(home, ws):
    d = ws / "reviews" / "topic"
    (d / "intermediate_files").mkdir(parents=True)
    (d / "task-progress.md").write_text("x", encoding="utf-8")
    wd.write_meta(d, {"format": 1, "review_id": "r", "name": "topic", "state": "published"})
    with pytest.raises(wd.Refusal, match="delivered"):
        wd.cmd_activate(ws, "topic")


def test_activate_refuses_when_a_pointer_exists(home, ruled):
    wd.cmd_init(ruled, "topic")
    with pytest.raises(wd.Refusal, match="already active"):
        wd.cmd_activate(ruled, "topic")


def test_activate_refuses_unknown(home, ws):
    with pytest.raises(wd.Refusal, match="no abandoned review"):
        wd.cmd_activate(ws, "nothing")


@pytest.mark.parametrize("field,value", [("workspace", "/another/workspace"), ("name", "other")])
def test_activate_local_refuses_unprovable_ownership(home, ruled, field, value):
    wd.cmd_init(ruled, "topic")
    wd.remove_pointer(ruled)
    local = wd.local_workdir(ruled, "topic")
    meta = wd.read_meta(local)
    meta[field] = value
    wd.write_meta(local, meta)
    with pytest.raises(wd.Refusal, match="ownership cannot be proven"):
        wd.cmd_activate(ruled, "topic")
    assert wd.read_pointer(ruled) is None


def test_activate_local_refuses_a_finished_review(home, ruled):
    wd.cmd_init(ruled, "topic")
    _finish(ruled, "topic")  # local metadata "published", pointer removed
    with pytest.raises(wd.Refusal, match="not an abandoned review"):
        wd.cmd_activate(ruled, "topic")
    assert wd.read_pointer(ruled) is None


def test_activate_local_under_the_inplace_pin_refuses(home, ruled, monkeypatch):
    wd.cmd_init(ruled, "topic")
    wd.remove_pointer(ruled)
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    with pytest.raises(wd.Refusal, match="unset PHILLIT_WORKDIR"):
        wd.cmd_activate(ruled, "topic")
    assert wd.read_pointer(ruled) is None


# --- demote ------------------------------------------------------------------
def test_demote_fresh_review(home, ruled):
    wd.cmd_init(ruled, "topic")
    out = wd.cmd_demote(ruled)
    assert out["mode"] == "inplace" and out["reason"] == wd.DEMOTE_REASON
    assert out["workdir"] == (ruled / "reviews" / "topic").as_posix()
    assert (ruled / "reviews" / "topic").is_dir()
    assert not wd.local_workdir(ruled, "topic").exists()
    assert wd.read_pointer(ruled) == {"form": "inplace", "name": "topic"}


def test_demote_refuses_once_work_exists(home, ruled):
    wd.cmd_init(ruled, "topic")
    (wd.local_workdir(ruled, "topic") / "task-progress.md").write_text("x", encoding="utf-8")
    with pytest.raises(wd.Refusal, match="FRESH"):
        wd.cmd_demote(ruled)


# --- resolve -----------------------------------------------------------------
def test_resolve_local_inplace_and_errors(home, ruled, ws):
    assert "error" in wd.cmd_resolve(ruled)
    wd.cmd_init(ruled, "topic")
    assert wd.cmd_resolve(ruled) == {"workdir": wd.local_workdir(ruled, "topic").as_posix()}
    wd.delete_workdir(wd.local_workdir(ruled, "topic"))
    assert "not on this machine" in wd.cmd_resolve(ruled)["error"]


# --- CLI ---------------------------------------------------------------------
def _cli(ws, *args, env_extra=None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run([sys.executable, str(SCRIPTS / "workdir.py"), *args], cwd=ws,
                          capture_output=True, text=True, encoding="utf-8", env=env)


def test_cli_init_and_status(home, ruled):
    r = _cli(ruled, "init", "topic")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["mode"] == "local"
    r = _cli(ruled, "status")
    assert json.loads(r.stdout)["active"] is True


def test_cli_refusal_exits_2_with_error(home, ruled):
    r = _cli(ruled, "init", "CON")
    assert r.returncode == 2 and "reserved" in json.loads(r.stdout)["error"]


def test_cli_invalid_mode_exits_2(home, ruled):
    r = _cli(ruled, "status", env_extra={"PHILLIT_WORKDIR": "tmp"})
    assert r.returncode == 2 and "'tmp'" in json.loads(r.stdout)["error"]


def test_cli_resolve_always_exits_0(home, ruled, tmp_path):
    r = _cli(tmp_path, "--workspace", str(ruled), "resolve", env_extra={"PHILLIT_WORKDIR": "tmp"})
    assert r.returncode == 0 and "error" in json.loads(r.stdout)


def test_cli_reads_workdir_mode_from_dotenv(home, ruled):
    (ruled / ".env").write_text("PHILLIT_WORKDIR=inplace\n", encoding="utf-8")
    r = _cli(ruled, "init", "topic", env_extra={"PHILLIT_WORKDIR": "local"})
    assert json.loads(r.stdout)["mode"] == "inplace"  # .env overrides the shell


# --- review-round hardening -------------------------------------------------
def test_init_refuses_a_linked_key_dir(home, ruled, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    wd.local_root().mkdir(parents=True)
    (wd.local_root() / wd.ws_key(ruled)).symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(wd.Refusal, match="is a link"):
        wd.cmd_init(ruled, "topic")
    assert wd.read_pointer(ruled) is None and not any(elsewhere.iterdir())


def test_init_tightens_an_existing_root_to_0700(home, ruled):
    if os.name == "nt":
        pytest.skip("POSIX modes only")
    wd.local_root().mkdir(parents=True)
    os.chmod(wd.local_root(), 0o755)
    wd.cmd_init(ruled, "topic")
    assert (wd.local_root().stat().st_mode & 0o777) == 0o700


def test_explicit_inplace_meets_local_pointer_in_every_command(home, ruled, monkeypatch):
    wd.cmd_init(ruled, "topic")
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    for call in (lambda: wd.cmd_init(ruled, "other"), lambda: wd.cmd_status(ruled),
                 lambda: wd.cmd_demote(ruled)):
        with pytest.raises(wd.Refusal, match="unset PHILLIT_WORKDIR"):
            call()
    assert "unset PHILLIT_WORKDIR" in wd.cmd_resolve(ruled)["error"]


def test_status_missing_inplace_folder_is_not_a_fresh_review(home, ws):
    wd.cmd_init(ws, "topic")
    (ws / "reviews" / "topic").rmdir()
    out = wd.cmd_status(ws)
    assert out["missing"] is True and out["mode"] == "inplace"


def test_status_flags_a_pointer_naming_a_delivered_review(home, ws):
    d = ws / "reviews" / "topic"
    (d / "intermediate_files").mkdir(parents=True)
    (d / "intermediate_files" / ".completed-review").write_text("reviews/topic\n", encoding="utf-8")
    (ws / "reviews" / ".active-review").write_text("reviews/topic\n", encoding="utf-8")
    assert wd.cmd_status(ws)["delivered"] is True


@pytest.mark.parametrize("ch", ["$", "`", '"'])
def test_status_and_activate_refuse_an_unquotable_legacy_path(home, tmp_path, ch):
    w = tmp_path / f"a{ch}b"
    (w / "reviews" / "topic").mkdir(parents=True)
    (w / "reviews" / "topic" / "task-progress.md").write_text("x", encoding="utf-8")
    w = w.resolve()
    with pytest.raises(wd.Refusal, match="cannot quote"):
        wd.cmd_activate(w, "topic")
    assert wd.read_pointer(w) is None
    (w / "reviews" / ".active-review").write_text("reviews/topic\n", encoding="utf-8")
    with pytest.raises(wd.Refusal, match="cannot quote"):
        wd.cmd_status(w)


def test_delivered_reviews_are_not_listed_as_abandoned(home, ws):
    old = ws / "reviews" / "old-delivered"  # a pre-marker delivered review
    (old / "intermediate_files").mkdir(parents=True)
    (old / "intermediate_files" / "task-progress.md").write_text("x", encoding="utf-8")
    (old / "literature-review-old-delivered.md").write_text("x", encoding="utf-8")
    assert wd.cmd_status(ws)["abandoned"] == []
    with pytest.raises(wd.Refusal, match="no abandoned review"):
        wd.cmd_activate(ws, "old-delivered")


def test_activate_losing_the_race_leaves_the_marker(home, ws, monkeypatch):
    d = ws / "reviews" / "topic"
    (d / "intermediate_files").mkdir(parents=True)
    wd.write_meta(d, {"format": 1, "review_id": None, "name": "topic", "state": "abandoned"})

    def racing(ws_, ptr):
        raise FileExistsError

    monkeypatch.setattr(wd, "create_pointer", racing)
    with pytest.raises(wd.Refusal, match="first"):
        wd.cmd_activate(ws, "topic")
    assert wd.read_meta(d)["state"] == "abandoned"


def test_demote_with_a_locked_file_changes_nothing(home, ruled, monkeypatch):
    wd.cmd_init(ruled, "topic")
    ptr = wd.read_pointer(ruled)
    monkeypatch.setattr(wd, "delete_workdir", lambda d: [d.as_posix() + "/locked"])
    with pytest.raises(wd.Refusal, match="unchanged"):
        wd.cmd_demote(ruled)
    assert wd.read_pointer(ruled) == ptr
    assert not (ruled / "reviews" / "topic").exists()


def test_uncollectable_finished_leftover_is_listed(home, ruled):
    wd.cmd_init(ruled, "topic")
    local = _finish(ruled, "topic")
    wd.meta_path(ruled / "reviews" / "topic").unlink()  # the user deleted the marker
    wd.collect(ruled)
    assert local.exists()
    stranded = wd.cmd_status(ruled)["stranded"]
    assert [s["path"] for s in stranded] == [local.as_posix()]
    assert "published copy" in stranded[0]["note"]


def test_cli_crash_is_one_json_object_exit_1(home, ruled, tmp_path):
    blocker = tmp_path / "home-is-a-file"
    blocker.write_text("x", encoding="utf-8")
    r = _cli(ruled, "init", "topic", env_extra={"HOME": str(blocker), "USERPROFILE": str(blocker)})
    assert r.returncode == 1
    assert json.loads(r.stdout)["error"].startswith("workdir.py crashed:")


def test_status_refuses_an_unquotable_missing_or_delivered_path(home, tmp_path):
    w = tmp_path / "we$ird"
    (w / "reviews").mkdir(parents=True)
    w = w.resolve()
    (w / "reviews" / ".active-review").write_text("reviews/topic\n", encoding="utf-8")
    with pytest.raises(wd.Refusal, match="cannot quote"):
        wd.cmd_status(w)  # the folder is missing: still never handed out unquotable


@pytest.mark.parametrize("command", ["init", "activate"])
def test_inplace_commands_refuse_a_linked_destination(home, ws, tmp_path, command):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "task-progress.md").write_text("x", encoding="utf-8")
    (ws / "reviews").mkdir()
    (ws / "reviews" / "topic").symlink_to(outside, target_is_directory=True)
    with pytest.raises(wd.Refusal, match="is a link"):
        if command == "init":
            wd.cmd_init(ws, "topic")  # no rule: in place
        else:
            wd.cmd_activate(ws, "topic")
    assert wd.read_pointer(ws) is None


def test_demote_refuses_a_linked_destination(home, ruled, tmp_path):
    wd.cmd_init(ruled, "topic")
    outside = tmp_path / "outside"
    outside.mkdir()
    (ruled / "reviews" / "topic").symlink_to(outside, target_is_directory=True)
    with pytest.raises(wd.Refusal, match="is a link"):
        wd.cmd_demote(ruled)
    assert wd.read_pointer(ruled)["form"] == "local"


def test_init_collects_a_finished_leftover_even_when_it_refuses(home, ruled):
    wd.cmd_init(ruled, "old")
    local = _finish(ruled, "old")
    with pytest.raises(wd.Refusal):
        wd.cmd_init(ruled, "old")  # the name is taken by the delivered review
    assert not local.exists()
