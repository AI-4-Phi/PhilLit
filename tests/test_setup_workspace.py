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


def test_merge_dedupes_and_preserves_existing_order():
    existing = {"allow": ["Read", "Bash"], "defaultMode": "acceptEdits"}
    merged = sw.merge_permissions(existing, RULES)
    assert merged["allow"][:2] == ["Read", "Bash"]      # existing order kept
    assert merged["allow"].count("Bash") == 1            # no duplicate
    assert merged["defaultMode"] == "acceptEdits"        # user's value preserved


def test_apply_creates_marker_and_scaffolds_env(tmp_path, monkeypatch):
    monkeypatch.delenv("S2_API_KEY", raising=False)
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / ".env.example").write_text("S2_API_KEY=\n", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()

    sw.apply(workspace=ws, plugin_root=plugin_root, dry_run=False)

    assert (ws / ".phillit").is_dir()
    assert (ws / ".env").read_text(encoding="utf-8") == "S2_API_KEY=\n"
    settings = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Bash" in settings["permissions"]["allow"]


def test_scaffold_env_prefills_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "brave-123")
    monkeypatch.setenv("CROSSREF_MAILTO", "user@example.edu")
    monkeypatch.delenv("S2_API_KEY", raising=False)
    example = tmp_path / ".env.example"
    example.write_text(
        "# Brave key\nBRAVE_API_KEY=\nCROSSREF_MAILTO=\nS2_API_KEY=\n", encoding="utf-8")
    env_path = tmp_path / ".env"

    filled = sw.scaffold_env(example, env_path)

    assert filled == ["BRAVE_API_KEY", "CROSSREF_MAILTO"]
    content = env_path.read_text(encoding="utf-8")
    assert "BRAVE_API_KEY=brave-123" in content
    assert "CROSSREF_MAILTO=user@example.edu" in content
    assert "S2_API_KEY=\n" in content        # unset key left blank
    assert "# Brave key" in content          # comments preserved


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
