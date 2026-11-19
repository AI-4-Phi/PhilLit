"""The pyproject exclude-newer pin must exist and match the lock (PL-41).

A user-level or environment exclude-newer otherwise changes uv's resolution
options, and `uv run --locked` in bin/phillit-run refuses the lock.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _pin(text: str, table: str):
    m = re.search(rf"^\[{re.escape(table)}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    assert m, f"no [{table}] table"
    v = re.search(r'^exclude-newer\s*=\s*"([^"]+)"', m.group(1), re.M)
    assert v, f"no exclude-newer in [{table}]"
    return v.group(1)


def test_pyproject_pin_matches_lock():
    pin = _pin((ROOT / "pyproject.toml").read_text(encoding="utf-8"), "tool.uv")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", pin), "use a fixed RFC 3339 date, not a span"
    assert _pin((ROOT / "uv.lock").read_text(encoding="utf-8"), "options") == pin


def test_wrapper_drops_environment_exclude_newer():
    wrapper = (ROOT / "bin" / "phillit-run").read_text(encoding="utf-8")
    assert "-u UV_EXCLUDE_NEWER " in wrapper and "-u UV_EXCLUDE_NEWER_PACKAGE" in wrapper
