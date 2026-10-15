"""workdir.py revise: a NEW review seeded from a delivered one. The delivered
folder is read-only throughout, and a revision publishes like any review."""
import json
import os
import stat
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
    """A workspace WITH the allow rule: reviews run in the local folder."""
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


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as e:  # Windows without Developer Mode or elevation
        pytest.skip(f"symlinks need privileges here: {e}")


def _fill(d: Path, name: str) -> None:
    """The files a finished Phase 6 leaves in a working directory."""
    files = {
        f"literature-review-{name}.md": "---\ntitle: A Review\n---\n\n## Introduction\n",
        f"literature-review-{name}.docx": "docx bytes",
        f"literature-review-{name}.pdf": "pdf bytes",
        f"literature-{name}.bib": "@misc{a, title={A}}\n",
        f"literature-{name}-annotated.bib": "@misc{a, title={A}, note={n}}\n",
        f"research-notes-{name}.md": "# Notes\n",
        f"intermediate_files/literature-{name}-merged.bib": "@misc{a, title={A}}\n",
        "intermediate_files/lit-review-plan.md": "# Plan\n",
        "intermediate_files/task-progress.md": "- [x] Phase 6\n",
        "intermediate_files/synthesis-section-1.md": "## S1\n",
        "intermediate_files/json/evidence_report.json": '{"status": "complete"}',
    }
    for rel, text in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text, encoding="utf-8")


def _delivered_local(ws, name="topic"):
    wd.cmd_init(ws, name)
    _fill(wd.local_workdir(ws, name), name)
    assert wd.cmd_publish(ws, abandon=False)["state"] == "published"
    return ws / "reviews" / name


def _delivered_inplace(ws, name="topic"):
    assert wd.cmd_init(ws, name)["mode"] == "inplace"
    _fill(ws / "reviews" / name, name)
    wd.cmd_publish(ws, abandon=False)
    assert (ws / "reviews" / name / wd.COMPLETED_REL).is_file()
    return ws / "reviews" / name


def _snapshot(root: Path):
    """Every path under root with its bytes and mode: a chmod is a change."""
    return sorted((p.relative_to(root).as_posix(), p.read_bytes() if p.is_file() else None,
                   p.lstat().st_mode) for p in root.rglob("*"))


def _rel_files(root: Path):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


EXPECTED_NEW = [
    "intermediate_files/json/evidence_report.json",
    "intermediate_files/lit-review-plan.md",
    "intermediate_files/literature-topic-r2-merged.bib",
    "intermediate_files/synthesis-section-1.md",
    "intermediate_files/task-progress.md",
    "literature-review-topic-r2.md",
    "literature-topic-r2-annotated.bib",
    "literature-topic-r2.bib",
    "research-notes-topic-r2.md",
]


# --- the local round trip ---------------------------------------------------
def test_revise_local_seeds_a_new_active_review(home, ws):
    src = _delivered_local(ws)
    before = _snapshot(src)
    out = wd.cmd_revise(ws, "topic")
    new = wd.local_workdir(ws, "topic-r2")
    assert out["mode"] == "local" and out["name"] == "topic-r2"
    assert out["workdir"] == new.as_posix()
    assert out["destination"] == (ws / "reviews" / "topic-r2").as_posix()
    assert out["revised_from"] == "topic" and out["files"] == len(EXPECTED_NEW)
    assert "carried" not in out
    # the new review's own metadata, no old marker, no docx/pdf
    assert [f for f in _rel_files(new) if f != wd.META_REL.as_posix()] == EXPECTED_NEW
    meta = wd.read_meta(new)
    assert meta["name"] == "topic-r2" and meta["state"] == "active"
    assert meta["revised_from"] == "topic"
    assert meta["review_id"] != wd.read_meta(src)["review_id"]
    # contents unchanged, the title included
    assert ((new / "literature-review-topic-r2.md").read_bytes()
            == (src / "literature-review-topic.md").read_bytes())
    assert ((new / "intermediate_files" / "literature-topic-r2-merged.bib").read_bytes()
            == (src / "intermediate_files" / "literature-topic-merged.bib").read_bytes())
    # an ordinary active review
    assert wd.cmd_status(ws) == {"active": True, "mode": "local", "name": "topic-r2",
                                 "workdir": new.as_posix(),
                                 "destination": (ws / "reviews" / "topic-r2").as_posix()}
    assert wd.cmd_resolve(ws) == {"workdir": new.as_posix()}
    assert _snapshot(src) == before


def test_revise_then_publish_delivers_a_new_review_and_never_touches_the_source(home, ws):
    src = _delivered_local(ws)
    before = _snapshot(src)
    new = Path(wd.cmd_revise(ws, "topic")["workdir"])
    (new / "literature-review-topic-r2.md").write_text("# Revised\n", encoding="utf-8")
    out = wd.cmd_publish(ws, abandon=False)
    dest = ws / "reviews" / "topic-r2"
    assert out["state"] == "published" and out["published_to"] == dest.as_posix()
    assert (dest / "literature-review-topic-r2.md").read_text(encoding="utf-8") == "# Revised\n"
    marker = wd.read_meta(dest)
    assert marker["state"] == "published" and marker["name"] == "topic-r2"
    assert wd.read_pointer(ws) is None and not new.exists()
    assert _snapshot(src) == before


# --- in place -------------------------------------------------------------------
def test_revise_inplace_round_trip(home, plain):
    src = _delivered_inplace(plain)
    before = _snapshot(src)
    out = wd.cmd_revise(plain, "topic")
    new = plain / "reviews" / "topic-r2"
    assert out["mode"] == "inplace" and out["reason"] == wd.MISSING_RULE_REASON
    assert out["workdir"] == out["destination"] == new.as_posix()
    assert out["revised_from"] == "topic"
    assert _rel_files(new) == EXPECTED_NEW  # no .completed-review, no metadata file
    assert wd.read_pointer(plain) == {"form": "inplace", "name": "topic-r2"}
    assert wd.cmd_status(plain)["workdir"] == new.as_posix()
    (new / "literature-review-topic-r2.md").write_text("# Revised\n", encoding="utf-8")
    wd.cmd_publish(plain, abandon=False)
    assert (new / wd.COMPLETED_REL).read_text(encoding="utf-8") == "reviews/topic-r2\n"
    assert _snapshot(src) == before


def test_revise_a_locally_published_review_in_place(home, ws, monkeypatch):
    src = _delivered_local(ws)
    before = _snapshot(src)
    monkeypatch.setenv("PHILLIT_WORKDIR", "inplace")
    out = wd.cmd_revise(ws, "topic")
    new = ws / "reviews" / "topic-r2"
    assert out["mode"] == "inplace" and "reason" not in out
    assert _rel_files(new) == EXPECTED_NEW  # the source's published marker is not carried
    assert _snapshot(src) == before


# --- naming -------------------------------------------------------------------------
def test_default_names_count_up_and_a_revision_of_a_revision_stays_flat(home, ws):
    _delivered_local(ws)
    assert wd.cmd_revise(ws, "topic")["name"] == "topic-r2"
    wd.cmd_publish(ws, abandon=False)
    assert wd.cmd_revise(ws, "topic")["name"] == "topic-r3"
    wd.cmd_publish(ws, abandon=False)
    out = wd.cmd_revise(ws, "topic-r2")  # strips -r2: never topic-r2-r2
    assert out["name"] == "topic-r4" and out["revised_from"] == "topic-r2"
    assert (Path(out["workdir"]) / "literature-review-topic-r4.md").is_file()


def test_revise_as_names_the_new_review(home, ws):
    _delivered_local(ws)
    out = wd.cmd_revise(ws, "topic", "topic-new-evidence")
    assert out["name"] == "topic-new-evidence"
    assert (Path(out["workdir"]) / "literature-topic-new-evidence-annotated.bib").is_file()


def test_revise_as_taken_refuses_with_a_suggestion(home, ws):
    src = _delivered_local(ws)
    (ws / "reviews" / "other").mkdir()
    before = _snapshot(src)
    with pytest.raises(wd.Refusal, match="taken") as e:
        wd.cmd_revise(ws, "topic", "other")
    assert e.value.extra["suggested_name"] == "other-2"
    with pytest.raises(wd.Refusal, match="taken"):
        wd.cmd_revise(ws, "topic", "topic")  # the source's own name
    assert wd.read_pointer(ws) is None and _snapshot(src) == before


def test_revise_as_taken_by_a_local_folder_refuses(home, ws):
    _delivered_local(ws)
    wd.local_workdir(ws, "other").mkdir(parents=True)
    with pytest.raises(wd.Refusal, match="taken"):
        wd.cmd_revise(ws, "topic", "other")


def test_revise_as_bad_name_refuses(home, ws):
    _delivered_local(ws)
    with pytest.raises(wd.Refusal, match="reserved"):
        wd.cmd_revise(ws, "topic", "CON")
    assert wd.read_pointer(ws) is None


# --- refusals: the source -----------------------------------------------------------
def test_revise_refuses_a_missing_source(home, ws):
    with pytest.raises(wd.Refusal, match="no review named"):
        wd.cmd_revise(ws, "topic")


def test_revise_refuses_a_folder_without_a_delivery_marker(home, ws):
    d = ws / "reviews" / "topic"
    _fill(d, "topic")  # a final review file, but no marker: not provably delivered
    with pytest.raises(wd.Refusal, match="not a delivered review"):
        wd.cmd_revise(ws, "topic")
    assert wd.read_pointer(ws) is None


def test_revise_refuses_an_abandoned_review_and_names_activate(home, ws):
    wd.cmd_init(ws, "topic")
    (wd.local_workdir(ws, "topic") / "task-progress.md").write_text("x", encoding="utf-8")
    wd.cmd_publish(ws, abandon=True)
    with pytest.raises(wd.Refusal, match="activate"):
        wd.cmd_revise(ws, "topic")


def test_revise_refuses_a_delivered_review_without_its_final_file(home, ws):
    src = _delivered_local(ws)
    (src / "literature-review-topic.md").unlink()
    with pytest.raises(wd.Refusal, match="literature-review-topic.md"):
        wd.cmd_revise(ws, "topic")
    assert wd.read_pointer(ws) is None


def test_revise_refuses_a_delivered_review_without_its_track_record(home, ws):
    src = _delivered_local(ws)
    (src / "literature-topic.bib").unlink()
    with pytest.raises(wd.Refusal, match="literature-topic.bib"):
        wd.cmd_revise(ws, "topic")
    assert wd.read_pointer(ws) is None


def test_revise_refuses_a_linked_source(home, ws, tmp_path):
    real = _delivered_local(ws, "real")
    _symlink(ws / "reviews" / "topic", real)
    with pytest.raises(wd.Refusal, match="link"):
        wd.cmd_revise(ws, "topic")


def test_revise_refuses_a_link_inside_the_source_before_creating_anything(home, ws, tmp_path):
    src = _delivered_local(ws)
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    _symlink(src / "intermediate_files" / "planted.txt", outside)
    with pytest.raises(wd.Refusal, match="link"):
        wd.cmd_revise(ws, "topic")
    assert wd.read_pointer(ws) is None
    assert not wd.local_workdir(ws, "topic-r2").exists()


# --- refusals: an active review -------------------------------------------------------
def test_revise_refuses_while_a_review_is_active(home, ws):
    _delivered_local(ws)
    wd.cmd_init(ws, "busy")
    with pytest.raises(wd.Refusal, match="already active") as e:
        wd.cmd_revise(ws, "topic")
    assert e.value.extra["active"]["name"] == "busy"
    assert not wd.local_workdir(ws, "topic-r2").exists()


# --- what is copied ---------------------------------------------------------------------
def test_unexpected_top_level_files_are_carried_into_intermediate_files(home, ws):
    src = _delivered_local(ws)
    # a stale duplicate tracker (seen in real delivered reviews), a user's own
    # file, an export pandoc did not make, a folder, and OS clutter
    (src / "task-progress.md").write_text("stale tracker\n", encoding="utf-8")
    (src / "my-notes.txt").write_text("mine\n", encoding="utf-8")
    (src / "literature-review-topic.html").write_text("<html/>", encoding="utf-8")
    (src / "extra").mkdir()
    (src / "extra" / "a.txt").write_text("a", encoding="utf-8")
    (src / ".DS_Store").write_bytes(b"\0")
    (src / "intermediate_files" / ".DS_Store").write_bytes(b"\0")
    before = _snapshot(src)
    out = wd.cmd_revise(ws, "topic")
    new = Path(out["workdir"])
    carried = "intermediate_files/carried-from-topic"
    assert out["carried"] == ["extra/a.txt", "literature-review-topic.html", "my-notes.txt",
                              "task-progress.md"]
    files = _rel_files(new)
    for rel in out["carried"]:
        assert f"{carried}/{rel}" in files
    assert (new / "intermediate_files" / "task-progress.md").read_text(
        encoding="utf-8") == "- [x] Phase 6\n"  # never overwritten by the stale copy
    assert not any(Path(f).name == ".DS_Store" for f in files)
    assert "task-progress.md" not in files and "literature-review-topic.html" not in files
    assert _snapshot(src) == before


def test_copies_are_writable_even_when_the_source_is_read_only(home, ws):
    if os.name == "nt":
        pytest.skip("POSIX modes only")
    src = _delivered_local(ws)
    md = src / "literature-review-topic.md"
    os.chmod(md, stat.S_IRUSR)
    before = _snapshot(src)
    new = Path(wd.cmd_revise(ws, "topic")["workdir"])
    assert os.access(new / "literature-review-topic-r2.md", os.W_OK)
    assert _snapshot(src) == before


# --- failure midway -----------------------------------------------------------------------
def _fail_on_third_copy(monkeypatch):
    real = wd._copy_content
    calls = []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) == 3:
            raise OSError(28, "No space left on device")
        real(src, dst)
    monkeypatch.setattr(wd, "_copy_content", flaky)
    return real


def test_a_failed_copy_removes_the_half_made_local_review(home, ws, monkeypatch):
    src = _delivered_local(ws)
    before = _snapshot(src)
    real = _fail_on_third_copy(monkeypatch)
    with pytest.raises(wd.Refusal, match="No space left") as e:
        wd.cmd_revise(ws, "topic")
    assert "unchanged" in str(e.value)
    assert wd.read_pointer(ws) is None
    assert not wd.local_workdir(ws, "topic-r2").exists()
    assert _snapshot(src) == before
    monkeypatch.setattr(wd, "_copy_content", real)
    assert wd.cmd_revise(ws, "topic")["name"] == "topic-r2"  # nothing was left behind


def test_a_failed_copy_removes_the_half_made_inplace_review(home, plain, monkeypatch):
    src = _delivered_inplace(plain)
    before = _snapshot(src)
    _fail_on_third_copy(monkeypatch)
    with pytest.raises(wd.Refusal, match="No space left"):
        wd.cmd_revise(plain, "topic")
    assert wd.read_pointer(plain) is None
    assert not (plain / "reviews" / "topic-r2").exists()
    assert _snapshot(src) == before


def test_a_source_that_changes_during_the_copy_refuses_and_cleans_up(home, ws, monkeypatch):
    src = _delivered_local(ws)
    real = wd._copy_content

    def racing(s, d):
        real(s, d)
        if s.name == "research-notes-topic.md":
            (src / "literature-topic.bib").write_text("changed\n", encoding="utf-8")
    monkeypatch.setattr(wd, "_copy_content", racing)
    with pytest.raises(wd.Refusal, match="changed"):
        wd.cmd_revise(ws, "topic")
    assert wd.read_pointer(ws) is None
    assert not wd.local_workdir(ws, "topic-r2").exists()


def test_a_cleanup_that_leaves_files_is_never_offered_for_resume(home, ws, monkeypatch):
    _delivered_local(ws)
    _fail_on_third_copy(monkeypatch)
    monkeypatch.setattr(wd, "delete_workdir", lambda d: [d.as_posix() + "/locked"])
    with pytest.raises(wd.Refusal) as e:
        wd.cmd_revise(ws, "topic")
    assert e.value.extra["leftover"]
    assert wd.read_pointer(ws) is None
    assert wd.read_meta(wd.local_workdir(ws, "topic-r2"))["state"] == "abandoned"
    assert wd.list_abandoned(ws) == []


# --- CLI -----------------------------------------------------------------------------------
def _cli(ws, *args, env_extra=None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run([sys.executable, str(SCRIPTS / "workdir.py"), *args], cwd=ws,
                          capture_output=True, text=True, encoding="utf-8", env=env)


def test_cli_revise(home, ws):
    _delivered_local(ws)
    r = _cli(ws, "revise", "topic", "--as", "topic-v2")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["name"] == "topic-v2" and out["revised_from"] == "topic"
    r = _cli(ws, "revise", "topic")
    assert r.returncode == 2 and "already active" in json.loads(r.stdout)["error"]


def test_the_cleanup_never_deletes_the_source(home, plain, monkeypatch):
    # an init that (by some future bug) hands back the delivered folder as
    # the new workdir: the guard fires, and its cleanup must not delete it
    src = _delivered_inplace(plain)
    before = _snapshot(src)

    def bad_init(workspace, name):
        return {"mode": "inplace", "name": name, "workdir": src.as_posix(),
                "destination": src.as_posix()}
    monkeypatch.setattr(wd, "cmd_init", bad_init)
    with pytest.raises(wd.Refusal, match="delivered"):
        wd.cmd_revise(plain, "topic")
    assert _snapshot(src) == before
