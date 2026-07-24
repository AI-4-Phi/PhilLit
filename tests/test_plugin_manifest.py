import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_plugin_json_has_required_fields():
    m = _load(".claude-plugin/plugin.json")
    assert m["name"] == "phillit"
    # Shape only, not a pinned value: the version bumps with every release.
    assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"])
    assert m["description"]


def test_no_legacy_in_repo_marketplace():
    # Installs go through the external ai4phi marketplace (AI-4-Phi/plugins).
    # A marketplace.json here would re-register this repo as its own marketplace
    # and reopen the duplicate-version stale-value trap.
    assert not (ROOT / ".claude-plugin" / "marketplace.json").exists()
