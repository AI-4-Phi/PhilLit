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
