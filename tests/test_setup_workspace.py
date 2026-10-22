import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "setup" / "scripts"))
import setup_workspace as sw  # noqa: E402

RULES = sw.PHILLIT_RULES


def test_merge_into_empty_adds_all_rules():
    merged = sw.merge_permissions({}, RULES)
    assert "Bash" in merged["allow"]
    assert "Skill(phillit:literature-review)" in merged["allow"]
    assert "Bash(sudo *)" in merged["deny"]
    assert "Bash(rm *)" in merged["ask"]
    assert merged["defaultMode"] == "default"


def test_ledger_write_denied_and_ordered_before_the_reviews_allow():
    # The evidence-tier ledgers are the attestation authority, so a
    # hand-written record must not be possible through a file tool. Note the
    # allow rule Edit(reviews/**) positively permits the ledger path, so this
    # only works because deny is evaluated before allow.
    merged = sw.merge_permissions({}, RULES)
    assert "Edit(**/enrichment_ledger-*.json)" in merged["deny"]
    assert "Edit(**/cleaning_ledger-*.json)" in merged["deny"]
    assert "Edit(reviews/**)" in merged["allow"]
    # Belt-and-braces only: hooks/block_ledger_write.py is the mechanism that
    # covers workspaces which have not re-run /phillit:setup, so the rule must
    # never be the sole protection.
    hook = Path(sw.__file__).parent.parent.parent.parent / "hooks" / "block_ledger_write.py"
    assert hook.is_file()


def test_rules_carry_no_dead_file_permission_patterns():
    # Claude Code matches file permission checks against Edit(path) rules only;
    # Write(path)/NotebookEdit(path)/MultiEdit(path) rules are never consulted and
    # trigger a startup warning in every workspace (verified in CLI 2.1.210).
    for rule in RULES["allow"] + RULES["deny"] + RULES["ask"]:
        assert not rule.startswith(("Write(", "NotebookEdit(", "MultiEdit(", "Glob(")), rule
    assert "Edit(reviews/**)" in RULES["allow"]


def test_merge_strips_phillits_own_obsolete_rules():
    # A workspace set up by an older PhilLit carries Write(reviews/**); a re-run
    # of setup must remove it, or the startup warning never goes away.
    existing = {"allow": ["Read", "Write(reviews/**)", "Edit(reviews/**)"]}
    merged = sw.merge_permissions(existing, RULES)
    assert "Write(reviews/**)" not in merged["allow"]
    assert "Edit(reviews/**)" in merged["allow"]


def test_merge_keeps_user_authored_write_rules():
    # Only rules PhilLit itself shipped are stripped — a user's own dead rule is
    # their call (Claude Code warns them directly).
    existing = {"allow": ["Write(drafts/**)"]}
    merged = sw.merge_permissions(existing, RULES)
    assert "Write(drafts/**)" in merged["allow"]


def test_rerun_on_stale_workspace_is_idempotent(tmp_path):
    # First re-run migrates the stale rule away; a second re-run changes nothing
    # (and therefore must not rewrite the file or touch the backup).
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"; (ws / ".claude").mkdir(parents=True)
    stale = {"permissions": dict(RULES, allow=["Write(reviews/**)"] + RULES["allow"])}
    (ws / ".claude" / "settings.json").write_text(json.dumps(stale), encoding="utf-8")

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)
    migrated = (ws / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "Write(reviews/**)" not in migrated

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)
    assert (ws / ".claude" / "settings.json").read_text(encoding="utf-8") == migrated


def test_merge_dedupes_and_preserves_existing_order():
    existing = {"allow": ["Read", "Bash"], "defaultMode": "acceptEdits"}
    merged = sw.merge_permissions(existing, RULES)
    assert merged["allow"][:2] == ["Read", "Bash"]      # existing order kept
    assert merged["allow"].count("Bash") == 1            # no duplicate
    assert merged["defaultMode"] == "acceptEdits"        # user's value preserved


def test_merge_tolerates_string_valued_rule_list():
    # A hand-edited settings.json may hold "allow": "Bash" (a bare string);
    # list("Bash") would explode it into single characters.
    existing = {"allow": "Bash", "deny": "Bash(sudo *)", "ask": None}
    merged = sw.merge_permissions(existing, RULES)
    assert merged["allow"][0] == "Bash"
    assert "B" not in merged["allow"]
    assert merged["deny"][0] == "Bash(sudo *)"
    assert merged["deny"].count("Bash(sudo *)") == 1
    assert merged["ask"] == RULES["ask"]


def test_apply_creates_marker_and_scaffolds_env(tmp_path, monkeypatch):
    monkeypatch.delenv("S2_API_KEY", raising=False)
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("S2_API_KEY=\n", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)

    assert (ws / ".phillit").is_dir()
    assert (ws / ".env").read_text(encoding="utf-8") == "# S2_API_KEY=\n"
    settings = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Bash" in settings["permissions"]["allow"]


def test_scaffold_env_never_copies_env_values(tmp_path, monkeypatch):
    # Keys already set in the environment must not be duplicated into .env:
    # the file may live in a synced or committed folder, and (override=True)
    # a copied value would shadow later key rotations in the environment.
    monkeypatch.setenv("BRAVE_API_KEY", "brave-123")
    monkeypatch.setenv("CROSSREF_MAILTO", "user@example.edu")
    monkeypatch.delenv("S2_API_KEY", raising=False)
    example = tmp_path / ".env.example"
    example.write_text(
        "# Brave key\nBRAVE_API_KEY=\nCROSSREF_MAILTO=\nS2_API_KEY=\n", encoding="utf-8")
    env_path = tmp_path / ".env"

    inherited = sw.scaffold_env(example, env_path)

    assert inherited == ["BRAVE_API_KEY", "CROSSREF_MAILTO"]
    content = env_path.read_text(encoding="utf-8")
    assert "brave-123" not in content        # secret never written to disk
    assert "user@example.edu" not in content
    assert "# S2_API_KEY=" in content        # unset key kept as a fill-in slot
    assert "# Brave key" in content          # comments preserved


def test_scaffolded_env_never_clobbers_environment_values(tmp_path, monkeypatch):
    # Every script loads .env with override=True, so any active `KEY=` line —
    # for an env-set key OR one exported later — would wipe the real value
    # to "". A freshly scaffolded .env must therefore define no keys at all.
    from dotenv import dotenv_values

    monkeypatch.setenv("BRAVE_API_KEY", "brave-123")
    monkeypatch.delenv("S2_API_KEY", raising=False)
    example = tmp_path / ".env.example"
    example.write_text("BRAVE_API_KEY=\nS2_API_KEY=\n", encoding="utf-8")
    env_path = tmp_path / ".env"

    sw.scaffold_env(example, env_path)

    assert dotenv_values(env_path) == {}


def test_scaffold_env_comments_out_empty_lines_of_missing_keys(tmp_path, monkeypatch):
    # A key missing from the environment must not stay as an active empty
    # `KEY=` line: if the user exports it later, that line would clobber it.
    # Lines for keys PhilLit does not own pass through untouched.
    monkeypatch.delenv("S2_API_KEY", raising=False)
    example = tmp_path / ".env.example"
    example.write_text("S2_API_KEY=\nMY_OWN_VAR=keepme\n", encoding="utf-8")
    env_path = tmp_path / ".env"

    sw.scaffold_env(example, env_path)

    content = env_path.read_text(encoding="utf-8")
    assert "# S2_API_KEY=" in content
    assert "\nS2_API_KEY=" not in "\n" + content.replace("# S2_API_KEY=", "")
    assert "MY_OWN_VAR=keepme" in content


def test_scaffold_env_handles_commented_example_keys(tmp_path, monkeypatch):
    # .env.example ships keys pre-commented (`# KEY=`). Env-set keys still get
    # the explanatory note and count as inherited; missing keys pass through.
    monkeypatch.setenv("BRAVE_API_KEY", "brave-123")
    monkeypatch.delenv("S2_API_KEY", raising=False)
    example = tmp_path / ".env.example"
    example.write_text("# BRAVE_API_KEY=\n# S2_API_KEY=\n", encoding="utf-8")
    env_path = tmp_path / ".env"

    inherited = sw.scaffold_env(example, env_path)

    assert inherited == ["BRAVE_API_KEY"]
    content = env_path.read_text(encoding="utf-8")
    assert "BRAVE_API_KEY is read from your environment" in content
    assert "brave-123" not in content
    assert "# S2_API_KEY=" in content


def test_shipped_env_example_defines_no_keys():
    # The template itself must never carry active KEY= lines: users copying it
    # by hand would inherit the override-to-"" trap the scaffold avoids.
    from dotenv import dotenv_values

    example = Path(__file__).parent.parent / ".env.example"
    assert dotenv_values(example) == {}


def test_apply_skips_env_when_environment_complete(tmp_path, monkeypatch):
    # With every key already in the environment there is nothing to collect,
    # so no .env is created at all — the environment stays authoritative.
    for key in sw.ENV_KEYS:
        monkeypatch.setenv(key, "some-value")
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text(
        "".join(f"{k}=\n" for k in sw.ENV_KEYS), encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)

    assert not (ws / ".env").exists()
    assert (ws / ".phillit").is_dir()        # rest of setup still runs
    assert (ws / ".claude" / "settings.json").exists()


def test_apply_never_overwrites_existing_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "brave-123")
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("BRAVE_API_KEY=\n", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / ".env").write_text("BRAVE_API_KEY=my-own-key\n", encoding="utf-8")

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)

    assert (ws / ".env").read_text(encoding="utf-8") == "BRAVE_API_KEY=my-own-key\n"


def test_apply_merges_and_backs_up_existing_settings(tmp_path):
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"; (ws / ".claude").mkdir(parents=True)
    (ws / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Read"]}}), encoding="utf-8")

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)

    assert (ws / ".claude" / "settings.json.bak").exists()      # backup made
    settings = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Read" in settings["permissions"]["allow"]
    assert "Bash" in settings["permissions"]["allow"]


def test_rerun_preserves_pristine_backup(tmp_path):
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"; (ws / ".claude").mkdir(parents=True)
    pristine = json.dumps({"permissions": {"allow": ["Read"]}})
    (ws / ".claude" / "settings.json").write_text(pristine, encoding="utf-8")

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)
    bak = ws / ".claude" / "settings.json.bak"
    assert bak.read_text(encoding="utf-8") == pristine

    # Re-running setup must not overwrite the pristine pre-PhilLit backup
    # with the already-merged settings.
    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)
    assert bak.read_text(encoding="utf-8") == pristine


def test_rerun_after_fresh_install_creates_no_backup(tmp_path):
    # No settings.json existed before setup: the pristine state is absence-of-file.
    # A re-run must not back up PhilLit's own merged output as if it were pristine.
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)
    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)

    assert not (ws / ".claude" / "settings.json.bak").exists()
    settings = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Bash" in settings["permissions"]["allow"]


def test_non_dict_permissions_fails_closed(tmp_path):
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"; (ws / ".claude").mkdir(parents=True)
    bad = ws / ".claude" / "settings.json"
    original = json.dumps({"permissions": None})
    bad.write_text(original, encoding="utf-8")

    rc = sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)

    assert rc == 2                                       # clean error, no traceback
    assert bad.read_text(encoding="utf-8") == original   # untouched
    assert not (ws / ".phillit").exists()                # nothing else written either


def test_malformed_settings_fails_closed(tmp_path):
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"; (ws / ".claude").mkdir(parents=True)
    bad = ws / ".claude" / "settings.json"
    bad.write_text("{ not valid json", encoding="utf-8")

    rc = sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)
    assert rc == 2                                              # error
    assert bad.read_text(encoding="utf-8") == "{ not valid json"  # untouched


def test_dry_run_writes_nothing(tmp_path):
    plugin_root = tmp_path / "plugin"; plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=True)

    assert not (ws / ".phillit").exists()
    assert not (ws / ".claude").exists()
    assert not (ws / ".env").exists()


sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"))
import workdir  # noqa: E402

LOCAL_ALLOW = "Edit(~/.local/state/phillit/reviews/**)"
LOCAL_DENY = ["Edit(~/.local/state/phillit/reviews/**/enrichment_ledger-*.json)",
              "Edit(~/.local/state/phillit/reviews/**/cleaning_ledger-*.json)"]


def test_rules_allow_the_local_work_folder_and_match_workdir():
    assert LOCAL_ALLOW in RULES["allow"]
    assert workdir.ALLOW_RULE == LOCAL_ALLOW  # workdir.py detects exactly this string


def test_rules_deny_ledgers_in_the_local_work_folder():
    # REQUIRED, not redundant: Edit(**/x) is anchored to the project, so it does
    # not reach ~/.local/... (probed on Claude Code 2.1.282).
    for rule in LOCAL_DENY:
        assert rule in RULES["deny"]


def test_local_rules_merge_idempotently(tmp_path):
    once = sw.merge_permissions({}, RULES)
    twice = sw.merge_permissions(once, RULES)
    assert once == twice
    assert once["allow"].count(LOCAL_ALLOW) == 1


# --- optional full-text sources: --probe-zotero / --check-pdf-dir -------------

import io  # noqa: E402
import urllib.error  # noqa: E402


class _FakeResp:
    def __init__(self, body: bytes, status: int = 200):
        self._body, self.status = body, status

    def read(self, n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_opener(result):
    class _Opener:
        def open(self, req, timeout=None):
            self.timeout = timeout
            if isinstance(result, BaseException):
                raise result
            return result

    return _Opener()


def _patch_opener(monkeypatch, result):
    opener = _fake_opener(result)
    monkeypatch.setattr(sw.urllib.request, "build_opener", lambda *a, **k: opener)
    return opener


def test_probe_zotero_ok(monkeypatch):
    opener = _patch_opener(monkeypatch, _FakeResp(b"[]"))
    assert sw.probe_zotero()["zotero"] == "ok"
    assert opener.timeout == 5


def test_probe_zotero_nothing_listening(monkeypatch):
    _patch_opener(monkeypatch, urllib.error.URLError(ConnectionRefusedError()))
    out = sw.probe_zotero()
    assert out["zotero"] == "unavailable" and "ConnectionRefusedError" in out["detail"]


def test_probe_zotero_timeout_and_garbage(monkeypatch):
    _patch_opener(monkeypatch, TimeoutError("timed out"))
    assert sw.probe_zotero()["zotero"] == "unavailable"
    _patch_opener(monkeypatch, _FakeResp(b"<html>not zotero</html>"))
    assert sw.probe_zotero()["zotero"] == "unavailable"
    _patch_opener(monkeypatch, _FakeResp(b'{"not": "a list"}'))
    assert sw.probe_zotero()["zotero"] == "unavailable"
    import http.client
    _patch_opener(monkeypatch, http.client.BadStatusLine("x"))
    assert sw.probe_zotero()["zotero"] == "unavailable"


def test_probe_zotero_api_switched_off_is_403(monkeypatch):
    err = urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b""))
    _patch_opener(monkeypatch, err)
    out = sw.probe_zotero()
    assert out["zotero"] == "unavailable" and "switched off" in out["detail"]


def test_probe_zotero_redirect_is_not_followed(monkeypatch):
    # The real opener, a local server answering 302: the redirect must surface
    # as unavailable, and the redirect target must never be requested.
    import http.server
    import threading

    hits = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if self.path.startswith("/api"):
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        out = sw.probe_zotero(url=f"http://127.0.0.1:{srv.server_port}/api/users/0/items?limit=1")
    finally:
        srv.shutdown()
        srv.server_close()
    assert out["zotero"] == "unavailable"
    assert hits == ["/api/users/0/items?limit=1"]


def test_probe_zotero_real_closed_port_does_not_crash():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    out = sw.probe_zotero(url=f"http://127.0.0.1:{port}/api/users/0/items?limit=1", timeout=2)
    assert out["zotero"] == "unavailable"


def test_check_pdf_dir_counts_recursively_case_insensitively(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-")
    (tmp_path / "B.PDF").write_bytes(b"%PDF-")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sub" / "deep").mkdir(parents=True)
    (tmp_path / "sub" / "deep" / "c.Pdf").write_bytes(b"%PDF-")
    out = sw.check_pdf_dir(str(tmp_path))
    assert (out["exists"], out["is_dir"], out["pdf_count"]) == (True, True, 3)
    assert "\\" not in out["path"] and out["path"].endswith(tmp_path.name)


def test_check_pdf_dir_strips_quotes_and_expands_home(tmp_path, monkeypatch):
    (tmp_path / "Papers").mkdir()
    (tmp_path / "Papers" / "a.pdf").write_bytes(b"%PDF-")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for raw in ('"~/Papers"', "'~/Papers'", '  "~/Papers"  '):
        out = sw.check_pdf_dir(raw)
        assert out["is_dir"] and out["pdf_count"] == 1, raw
        assert out["path"] == str(tmp_path / "Papers").replace("\\", "/")


def test_check_pdf_dir_missing_file_and_empty(tmp_path):
    out = sw.check_pdf_dir(str(tmp_path / "nope"))
    assert (out["exists"], out["is_dir"], out["pdf_count"]) == (False, False, 0)
    f = tmp_path / "file.pdf"
    f.write_bytes(b"%PDF-")
    out = sw.check_pdf_dir(str(f))
    assert (out["exists"], out["is_dir"], out["pdf_count"]) == (True, False, 0)
    out = sw.check_pdf_dir("")
    assert (out["exists"], out["is_dir"]) == (False, False)
    assert sw.check_pdf_dir(str(tmp_path))["pdf_count"] == 1


def test_check_pdf_dir_skips_symlinks(tmp_path):
    import pytest
    real = tmp_path / "real"
    real.mkdir()
    (real / "a.pdf").write_bytes(b"%PDF-")
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "link.pdf").symlink_to(real / "a.pdf")
        (root / "linkdir").symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    (root / "own.pdf").write_bytes(b"%PDF-")
    assert sw.check_pdf_dir(str(root))["pdf_count"] == 1


def test_check_pdf_dir_stops_at_the_file_limit(tmp_path):
    for i in range(7):
        (tmp_path / f"{i}.pdf").write_bytes(b"%PDF-")
    out = sw.check_pdf_dir(str(tmp_path), limit=5)
    assert out["truncated"] is True and out["pdf_count"] == 5
    assert sw.check_pdf_dir(str(tmp_path), limit=7)["truncated"] is False


def _run_main(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", ["setup_workspace.py"] + argv)
    rc = sw.main()
    return rc, capsys.readouterr().out


def test_cli_check_pdf_dir_prints_one_json_object_without_plugin_root(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-")
    rc, out = _run_main(monkeypatch, capsys, ["--check-pdf-dir", str(tmp_path)])
    assert rc == 0
    assert out.count("\n") == 1 and json.loads(out)["pdf_count"] == 1
    assert out.isascii()


def test_cli_probe_zotero_prints_one_json_object_and_touches_nothing(tmp_path, monkeypatch, capsys):
    _patch_opener(monkeypatch, urllib.error.URLError(ConnectionRefusedError()))
    monkeypatch.chdir(tmp_path)
    rc, out = _run_main(monkeypatch, capsys, ["--probe-zotero"])
    assert rc == 0
    assert json.loads(out)["zotero"] == "unavailable"
    assert list(tmp_path.iterdir()) == []


def test_cli_nonascii_path_stays_ascii_on_stdout(tmp_path, monkeypatch, capsys):
    d = tmp_path / "Bücher"
    d.mkdir()
    rc, out = _run_main(monkeypatch, capsys, ["--check-pdf-dir", str(d)])
    assert rc == 0 and out.isascii() and json.loads(out)["is_dir"] is True


def test_cli_apply_still_requires_plugin_root(monkeypatch, capsys):
    import pytest
    monkeypatch.setattr(sys, "argv", ["setup_workspace.py"])
    with pytest.raises(SystemExit) as e:
        sw.main()
    assert e.value.code == 2


def test_cli_probe_flags_do_not_combine_with_apply_flags(tmp_path, monkeypatch):
    import pytest
    for argv in (["--probe-zotero", "--check-pdf-dir", str(tmp_path)],
                 ["--probe-zotero", "--dry-run"],
                 ["--check-pdf-dir", str(tmp_path), "--plugin-root", str(tmp_path)]):
        monkeypatch.setattr(sys, "argv", ["setup_workspace.py"] + argv)
        with pytest.raises(SystemExit) as e:
            sw.main()
        assert e.value.code == 2


def test_new_env_keys_pass_through_the_scaffold_as_comments(tmp_path, monkeypatch):
    # The two consent keys are not API keys: the scaffold must keep them
    # commented (an active empty line would be an override trap, and an
    # unwritten key must mean "no consent").
    for k in sw.ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    plugin_root = Path(sw.__file__).parent.parent.parent.parent
    ws = tmp_path / "ws"
    ws.mkdir()
    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)
    from dotenv import dotenv_values
    text = (ws / ".env").read_text(encoding="utf-8")
    assert "# PHILLIT_ZOTERO=" in text and "# PHILLIT_PDF_DIR=" in text
    assert dotenv_values(ws / ".env") == {}
    assert "PHILLIT_FULLTEXT_LICENSED_ONLY" not in (plugin_root / ".env.example").read_text(encoding="utf-8")


def test_skill_documents_both_consent_questions_and_the_flags():
    skill = (Path(sw.__file__).parent.parent / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("--probe-zotero", "--check-pdf-dir", "PHILLIT_ZOTERO=on", "PHILLIT_PDF_DIR",
                   "Allow other applications on this computer to communicate with Zotero"):
        assert needle in skill, needle
