"""workdir.py publish: every branch of the state machine, and the ownership
safety guarantee (a bad pointer never reaches a copy or a delete)."""
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
    w = tmp_path / "ws"
    (w / ".claude").mkdir(parents=True)
    (w / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [wd.ALLOW_RULE]}}), encoding="utf-8")
    return w.resolve()


@pytest.fixture
def plain(tmp_path):
    """A workspace WITHOUT the allow rule: reviews run in place."""
    w = tmp_path / "plain-ws"
    w.mkdir()
    return w.resolve()


def _review(ws, name="topic"):
    wd.cmd_init(ws, name)
    local = wd.local_workdir(ws, name)
    (local / f"literature-review-{name}.md").write_text("# Review\n", encoding="utf-8")
    (local / f"literature-{name}.bib").write_text("@misc{a, title={A}}\n", encoding="utf-8")
    (local / "intermediate_files" / "json").mkdir()
    (local / "intermediate_files" / "json" / "s2_d1.json").write_text("{}", encoding="utf-8")
    return local


def _snapshot(*roots):
    return sorted((p.as_posix(), p.read_bytes() if p.is_file() else None)
                  for r in roots if r.exists() for p in r.rglob("*"))


def test_publish_fresh(home, ws):
    local = _review(ws)
    out = wd.cmd_publish(ws, abandon=False)
    dest = ws / "reviews" / "topic"
    assert out["state"] == "published" and out["files"] == 3
    assert (dest / "literature-review-topic.md").read_text(encoding="utf-8") == "# Review\n"
    assert (dest / "intermediate_files" / "json" / "s2_d1.json").is_file()
    marker = json.loads(wd.meta_path(dest).read_text(encoding="utf-8"))
    assert set(marker) == {"format", "review_id", "name", "state", "published"}
    assert marker["state"] == "published"
    assert wd.read_pointer(ws) is None
    assert not local.exists()


def test_destination_marker_holds_no_host_and_no_path(home, ws):
    _review(ws)
    wd.cmd_publish(ws, abandon=False)
    text = wd.meta_path(ws / "reviews" / "topic").read_text(encoding="utf-8")
    assert set(json.loads(text)) == {"format", "review_id", "name", "state", "published"}
    assert str(home) not in text and ws.as_posix() not in text


def test_publish_abandon_local(home, ws):
    _review(ws)
    out = wd.cmd_publish(ws, abandon=True)
    assert out["state"] == "abandoned"
    assert json.loads(wd.meta_path(ws / "reviews" / "topic").read_text(encoding="utf-8"))["state"] == "abandoned"
    # an abandoned local review is resumable in place afterwards
    (ws / "reviews" / "topic" / "task-progress.md").write_text("x", encoding="utf-8")
    assert wd.cmd_activate(ws, "topic")["mode"] == "inplace"


def test_publish_inplace_archives_the_pointer(home, tmp_path):
    w = tmp_path / "plain"
    w.mkdir()
    wd.cmd_init(w.resolve(), "topic")  # no rule: in place
    out = wd.cmd_publish(w.resolve(), abandon=False)
    assert out == {"mode": "inplace", "state": "published",
                   "published_to": (w.resolve() / "reviews" / "topic").as_posix()}
    assert (w / "reviews" / "topic" / "intermediate_files" / ".completed-review").read_text(
        encoding="utf-8") == "reviews/topic\n"
    assert not (w / "reviews" / ".active-review").exists()


def test_publish_inplace_abandon_keeps_the_review_in_place(home, tmp_path):
    w = (tmp_path / "plain")
    w.mkdir()
    wd.cmd_init(w.resolve(), "topic")
    wd.cmd_publish(w.resolve(), abandon=True)
    assert not (w / "reviews" / ".active-review").exists()
    assert (w / "reviews" / "topic").is_dir()


def test_publish_without_pointer_names_activate(home, ws):
    with pytest.raises(wd.Refusal, match="activate"):
        wd.cmd_publish(ws, abandon=False)


def test_interrupted_copy_rerun_completes(home, ws, monkeypatch):
    local = _review(ws)
    real = wd._copy_file
    calls = {"n": 0}

    def dying(src, dst):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("disk went away")
        real(src, dst)

    monkeypatch.setattr(wd, "_copy_file", dying)
    with pytest.raises(OSError):
        wd.cmd_publish(ws, abandon=False)
    assert wd.read_pointer(ws) is not None and local.exists()
    monkeypatch.setattr(wd, "_copy_file", real)
    assert wd.cmd_publish(ws, abandon=False)["state"] == "published"
    assert not local.exists()


def test_source_is_authoritative_over_a_stale_partial_copy(home, ws):
    local = _review(ws)
    dest = ws / "reviews" / "topic"
    (dest / "intermediate_files").mkdir(parents=True)
    wd._copy_file(wd.meta_path(local), wd.meta_path(dest))
    (dest / "literature-review-topic.md").write_text("stale", encoding="utf-8")
    wd.cmd_publish(ws, abandon=False)
    assert (dest / "literature-review-topic.md").read_text(encoding="utf-8") == "# Review\n"


def test_publish_refuses_when_destination_has_extra_files(home, ws):
    local = _review(ws)
    dest = ws / "reviews" / "topic"
    (dest / "intermediate_files").mkdir(parents=True)
    wd._copy_file(wd.meta_path(local), wd.meta_path(dest))
    (dest / "unexpected.txt").write_text("x", encoding="utf-8")
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_publish(ws, abandon=False)
    assert e.value.extra["extra"] == ["unexpected.txt"]
    assert wd.read_pointer(ws) is not None and local.exists()


def test_publish_refuses_a_foreign_destination(home, ws):
    _review(ws)
    dest = ws / "reviews" / "topic"
    dest.mkdir(parents=True)
    (dest / "someone-elses.md").write_text("x", encoding="utf-8")
    before = _snapshot(dest, wd.local_root())
    with pytest.raises(wd.Refusal, match="not this review"):
        wd.cmd_publish(ws, abandon=False)
    assert _snapshot(dest, wd.local_root()) == before


@pytest.mark.parametrize("stage", ["intact", "half-deleted", "gone"])
def test_crash_after_commit_recovers(home, ws, stage):
    local = _review(ws)
    ptr = wd.read_pointer(ws)
    real_remove = wd.remove_pointer
    wd.remove_pointer = lambda w: (_ for _ in ()).throw(OSError("crash"))
    try:
        with pytest.raises(OSError):
            wd.cmd_publish(ws, abandon=False)
    finally:
        wd.remove_pointer = real_remove
    assert wd.cmd_status(ws)["committed"] is True
    if stage == "half-deleted":
        (local / "literature-topic.bib").unlink()
    elif stage == "gone":
        wd.delete_workdir(local)
    out = wd.cmd_publish(ws, abandon=False)
    assert out["state"] == "published"
    assert wd.read_pointer(ws) is None and not local.exists()
    assert ptr["review_id"] == json.loads(wd.meta_path(ws / "reviews" / "topic").read_text(encoding="utf-8"))["review_id"]


def test_recovery_refuses_a_working_dir_edited_after_commit(home, ws):
    local = _review(ws)
    real_remove = wd.remove_pointer
    wd.remove_pointer = lambda w: (_ for _ in ()).throw(OSError("crash"))
    try:
        with pytest.raises(OSError):
            wd.cmd_publish(ws, abandon=False)
    finally:
        wd.remove_pointer = real_remove
    (local / "literature-review-topic.md").write_text("# edited later\n", encoding="utf-8")
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_publish(ws, abandon=False)
    assert e.value.extra["differing"] == ["literature-review-topic.md"]
    assert local.exists()


def test_failed_delete_is_reported_then_collected(home, ws, monkeypatch):
    local = _review(ws)
    real = wd.delete_workdir
    monkeypatch.setattr(wd, "delete_workdir", lambda d: [d.as_posix() + "/locked.json"])
    out = wd.cmd_publish(ws, abandon=False)
    assert out["state"] == "published" and out["leftover"]
    assert wd.read_meta(local)["state"] == "published"
    monkeypatch.setattr(wd, "delete_workdir", real)
    wd.cmd_init(ws, "next")
    assert not local.exists()


# --- ownership safety: nothing copied, nothing deleted -----------------------
def _write_raw_pointer(ws, **fields):
    ptr = wd.read_pointer(ws)
    wd.remove_pointer(ws)
    data = {"format": 1, "mode": "local", "review_id": ptr["review_id"], "name": ptr["name"],
            "host": ptr["host"], "workdir": ptr["workdir"], **fields}
    (ws / "reviews" / ".active-review").write_text(json.dumps(data) + "\n", encoding="utf-8")


@pytest.mark.parametrize("workdir_of", [
    lambda home, ws: str(home),
    lambda home, ws: wd.local_root().as_posix(),
    lambda home, ws: (wd.local_root() / wd.ws_key(ws)).as_posix(),
    lambda home, ws: (wd.local_root() / wd.ws_key(ws) / "topic" / "deeper").as_posix(),
    lambda home, ws: (wd.local_root() / wd.ws_key(ws) / ".." / wd.ws_key(ws) / "topic").as_posix(),
    lambda home, ws: "C:/Users/me/.local/state/phillit/reviews/" + wd.ws_key(ws) + "/topic",
])
def test_publish_refuses_foreign_machine_pointer(home, ws, workdir_of):
    local = _review(ws)
    _write_raw_pointer(ws, workdir=workdir_of(home, ws))
    before = _snapshot(home, ws)
    with pytest.raises(wd.Refusal):
        wd.cmd_publish(ws, abandon=False)
    assert _snapshot(home, ws) == before
    assert local.exists()


def test_publish_refuses_a_symlinked_working_dir(home, ws, tmp_path):
    local = _review(ws)
    real = tmp_path / "elsewhere"
    local.rename(real)
    local.symlink_to(real, target_is_directory=True)
    with pytest.raises(wd.Refusal, match="is a link"):
        wd.cmd_publish(ws, abandon=False)
    assert (real / "literature-review-topic.md").is_file()


def test_publish_refuses_a_symlink_inside(home, ws, tmp_path):
    local = _review(ws)
    secret = tmp_path / "secret.txt"
    secret.write_text("s", encoding="utf-8")
    (local / "leak.txt").symlink_to(secret)
    with pytest.raises(wd.Refusal, match="is a link"):
        wd.cmd_publish(ws, abandon=False)
    assert not (ws / "reviews" / "topic").exists()


@pytest.mark.parametrize("field,value", [("review_id", "ee" * 16), ("workspace", "/another/workspace")])
def test_publish_refuses_mismatched_metadata(home, ws, field, value):
    local = _review(ws)
    meta = wd.read_meta(local)
    meta[field] = value
    wd.write_meta(local, meta)
    with pytest.raises(wd.Refusal):
        wd.cmd_publish(ws, abandon=False)
    assert local.exists() and not (ws / "reviews" / "topic").exists()


def test_publish_inplace_env_meets_local_pointer(home, ws, monkeypatch):
    _review(ws)
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    with pytest.raises(wd.Refusal, match="unset PHILLIT_WORKDIR"):
        wd.cmd_publish(ws, abandon=False)


def test_publish_refuses_a_file_created_during_the_copy(home, ws, monkeypatch):
    local = _review(ws)
    real = wd._copy_file
    done = {"late": False}

    def copy_then_write(src, dst):
        real(src, dst)
        if not done["late"]:
            done["late"] = True
            (local / "late.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(wd, "_copy_file", copy_then_write)
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_publish(ws, abandon=False)
    assert "late.json" in e.value.extra["changed_during_copy"]
    assert wd.read_pointer(ws) is not None and local.exists()
    assert wd.committed(ws, wd.read_pointer(ws)) is None


def test_publish_refuses_a_source_edited_after_its_copy(home, ws, monkeypatch):
    local = _review(ws)
    real = wd._copy_file

    def copy_then_edit(src, dst):
        real(src, dst)
        if src.name == "literature-review-topic.md":
            src.write_text("# edited mid-copy\n", encoding="utf-8")

    monkeypatch.setattr(wd, "_copy_file", copy_then_edit)
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_publish(ws, abandon=False)
    assert e.value.extra["changed_during_copy"] == ["literature-review-topic.md"]


def test_inplace_publish_refuses_a_linked_intermediate_files(home, tmp_path):
    w = (tmp_path / "plain")
    w.mkdir()
    w = w.resolve()
    wd.cmd_init(w, "topic")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / ".completed-review").write_text("keep", encoding="utf-8")
    (w / "reviews" / "topic" / "intermediate_files").symlink_to(outside, target_is_directory=True)
    with pytest.raises(wd.Refusal, match="is a link"):
        wd.cmd_publish(w, abandon=False)
    assert (outside / ".completed-review").read_text(encoding="utf-8") == "keep"
    assert wd.read_pointer(w) is not None


def test_finish_never_writes_a_partial_metadata_record(home, ws, monkeypatch):
    local = _review(ws)
    dest = wd.destination(ws, "topic")
    (dest / "intermediate_files").mkdir(parents=True)
    real_read = wd.read_meta
    monkeypatch.setattr(wd, "read_meta", lambda d: None if d == local else real_read(d))
    monkeypatch.setattr(wd, "delete_workdir", lambda d: [d.as_posix()])  # the delete fails too
    wd._finish(ws, local, "published", dest)
    raw = json.loads(wd.meta_path(local).read_text(encoding="utf-8"))
    assert raw["state"] == "active" and raw["name"] == "topic"


# --- abandon, from the review-round hardening -------------------------------
def test_review_abandoned_after_cleanup_stays_resumable(home, ws):
    wd.cmd_init(ws, "topic")
    local = wd.local_workdir(ws, "topic")
    (local / "intermediate_files" / "task-progress.md").write_text("x", encoding="utf-8")
    wd.cmd_publish(ws, abandon=True)
    listed = wd.cmd_status(ws)["abandoned"]
    assert {"name": "topic", "mode": "inplace",
            "workdir": (ws / "reviews" / "topic").as_posix()} in listed
    assert wd.cmd_activate(ws, "topic")["mode"] == "inplace"
    assert not wd.meta_path(ws / "reviews" / "topic").exists()


def test_inplace_abandon_marks_an_unfinished_review_only(home, plain):
    wd.cmd_init(plain, "topic")
    wd.cmd_publish(plain, abandon=True)
    assert wd.read_meta(plain / "reviews" / "topic")["state"] == "abandoned"
    assert [a["name"] for a in wd.cmd_status(plain)["abandoned"]] == ["topic"]


def test_existing_review_guard_leaves_the_delivered_review_untouched(home, plain, monkeypatch):
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    d = plain / "reviews" / "topic"
    d.mkdir(parents=True)
    (d / "literature-review-topic.md").write_text("delivered", encoding="utf-8")
    before = sorted(p.as_posix() for p in d.rglob("*"))
    assert wd.cmd_init(plain, "topic")["existing_review"] is True
    wd.cmd_publish(plain, abandon=True)  # what SKILL.md's guard runs
    assert sorted(p.as_posix() for p in d.rglob("*")) == before
    assert wd.read_pointer(plain) is None


def test_committed_review_with_an_unprovable_local_folder_completes(home, ws):
    local = _review(ws)
    real_remove = wd.remove_pointer
    wd.remove_pointer = lambda w: (_ for _ in ()).throw(OSError("crash"))
    try:
        with pytest.raises(OSError):
            wd.cmd_publish(ws, abandon=False)
    finally:
        wd.remove_pointer = real_remove
    wd.meta_path(local).unlink()  # a user "cleaned up" the local folder's metadata
    out = wd.cmd_publish(ws, abandon=False)
    assert out["state"] == "published" and wd.read_pointer(ws) is None
    assert local.exists() and "ownership cannot be proven" in out["leftover"][0]
    assert [s["path"] for s in wd.cmd_status(ws)["stranded"]] == [local.as_posix()]


def test_a_stale_metadata_temp_is_never_published(home, ws):
    local = _review(ws)
    (local / "intermediate_files" / ".phillit-review.json.4182.tmp").write_text("{}", encoding="utf-8")
    wd.cmd_publish(ws, abandon=False)
    assert not (ws / "reviews" / "topic" / "intermediate_files" / ".phillit-review.json.4182.tmp").exists()


def test_a_failed_delete_is_reported_once(home, ws, monkeypatch):
    local = _review(ws)
    monkeypatch.setattr(wd, "delete_workdir", lambda d: [d.as_posix() + "/locked.json"])
    out = wd.cmd_publish(ws, abandon=False)
    assert out["leftover"] == [local.as_posix() + "/locked.json"]


def test_a_read_only_file_never_wedges_publish(home, ws, monkeypatch):
    local = _review(ws)
    ro = local / "literature-topic.bib"
    ro.chmod(0o444)
    real = wd._copy_file

    def dying(src, dst):
        real(src, dst)
        if src == ro:
            raise OSError("crash right after the read-only file was copied")

    monkeypatch.setattr(wd, "_copy_file", dying)
    with pytest.raises(OSError):
        wd.cmd_publish(ws, abandon=False)
    monkeypatch.setattr(wd, "_copy_file", real)
    assert wd.cmd_publish(ws, abandon=False)["state"] == "published"
    assert (ws / "reviews" / "topic" / "literature-topic.bib").read_text(encoding="utf-8") == "@misc{a, title={A}}\n"
    assert not local.exists()


def test_a_crash_inside_the_metadata_copy_is_not_a_foreign_destination(home, ws, monkeypatch):
    local = _review(ws)
    real = wd._copy_file

    def dying(src, dst):
        if src.name == ".phillit-review.json":
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text('{"format": 1, "rev', encoding="utf-8")  # a torn copy
            raise OSError("killed mid-copy")
        real(src, dst)

    monkeypatch.setattr(wd, "_copy_file", dying)
    with pytest.raises(OSError):
        wd.cmd_publish(ws, abandon=False)
    monkeypatch.setattr(wd, "_copy_file", real)
    assert wd.cmd_publish(ws, abandon=False)["state"] == "published"
    assert not local.exists()
    assert not list((ws / "reviews" / "topic" / "intermediate_files").glob("*.tmp"))


def test_a_crashed_commit_leaves_no_temp_in_the_delivered_review(home, ws, monkeypatch):
    _review(ws)
    real = wd.write_meta

    def dying(workdir, data):
        if workdir == wd.destination(ws, "topic") and data.get("state") == "published":
            wd.meta_path(workdir).with_name(".phillit-review.json.99999.tmp").write_text("{}", encoding="utf-8")
            raise OSError("killed before os.replace")
        real(workdir, data)

    monkeypatch.setattr(wd, "write_meta", dying)
    with pytest.raises(OSError):
        wd.cmd_publish(ws, abandon=False)
    monkeypatch.setattr(wd, "write_meta", real)
    assert wd.cmd_publish(ws, abandon=False)["state"] == "published"
    assert not list((ws / "reviews" / "topic" / "intermediate_files").glob("*.tmp"))


def test_recovery_refuses_a_file_added_after_the_commit(home, ws):
    local = _review(ws)
    real_remove = wd.remove_pointer
    wd.remove_pointer = lambda w: (_ for _ in ()).throw(OSError("crash"))
    try:
        with pytest.raises(OSError):
            wd.cmd_publish(ws, abandon=False)
    finally:
        wd.remove_pointer = real_remove
    (local / "added-later.md").write_text("new", encoding="utf-8")
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_publish(ws, abandon=False)
    assert e.value.extra["differing"] == ["added-later.md"]
    assert local.exists()


def test_inplace_publish_refuses_a_missing_folder(home, plain):
    wd.cmd_init(plain, "topic")
    (plain / "reviews" / "topic").rmdir()
    with pytest.raises(wd.Refusal, match="nothing to publish"):
        wd.cmd_publish(plain, abandon=False)
    assert wd.read_pointer(plain) is not None


def test_inplace_abandon_never_marks_a_delivered_folder(home, plain):
    d = plain / "reviews" / "topic"
    (d / "intermediate_files").mkdir(parents=True)
    (d / "intermediate_files" / ".completed-review").write_text("reviews/topic\n", encoding="utf-8")
    (plain / "reviews" / ".active-review").write_text("reviews/topic\n", encoding="utf-8")
    wd.cmd_publish(plain, abandon=True)
    assert not wd.meta_path(d).exists() and wd.read_pointer(plain) is None


def test_activate_after_an_abandon_whose_delete_failed_resumes_in_place(home, ws, monkeypatch):
    local = _review(ws)
    real = wd.delete_workdir
    monkeypatch.setattr(wd, "delete_workdir", lambda d: [d.as_posix() + "/locked"])
    wd.cmd_publish(ws, abandon=True)
    monkeypatch.setattr(wd, "delete_workdir", real)
    (ws / "reviews" / "topic" / "task-progress.md").write_text("x", encoding="utf-8")
    assert wd.cmd_activate(ws, "topic")["mode"] == "inplace"
    assert not local.exists()
