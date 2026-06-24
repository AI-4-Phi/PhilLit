import json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_plugin_json_has_required_fields():
    m = _load(".claude-plugin/plugin.json")
    assert m["name"] == "phillit"
    assert m["version"] == "0.1.0"
    assert m["description"]


def test_marketplace_lists_one_plugin_sourced_at_repo_root():
    mk = _load(".claude-plugin/marketplace.json")
    assert mk["name"] == "phillit"
    assert len(mk["plugins"]) == 1
    plugin = mk["plugins"][0]
    assert plugin["name"] == "phillit"
    assert plugin["source"] == "."
    assert plugin["version"] == "0.1.0"
