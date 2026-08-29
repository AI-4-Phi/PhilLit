"""Tests for hooks/block_ledger_write.py — the PreToolUse gate that refuses
tool-writes to the evidence-tier attestation ledgers.

The gate must DENY exactly when ``tool_input.file_path``'s basename is one of
the two filenames ``evidence_barrier._load_ledger`` opens
(``enrichment_ledger-*.json`` / ``cleaning_ledger-*.json``), and allow
everything else — including a *content* mention of the needle, a
similarly-named user file, a missing field, and unparseable input (fail open,
PreToolUse plumbing policy).
"""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "block_ledger_write.py"


def _run(payload):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _is_deny(out):
    return out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def _write(file_path, content="{}"):
    return {"tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content}}


class TestDenies:
    def test_enrichment_ledger_denied(self):
        out = _run(_write(
            "reviews/x/intermediate_files/json/enrichment_ledger-literature-domain-1.json"))
        assert _is_deny(out)

    def test_cleaning_ledger_denied(self):
        out = _run(_write(
            "reviews/x/intermediate_files/json/cleaning_ledger-literature-domain-3.json"))
        assert _is_deny(out)

    def test_absolute_path_denied(self):
        out = _run(_write(
            "/Users/me/ws/reviews/x/intermediate_files/json/enrichment_ledger-b.json"))
        assert _is_deny(out)

    def test_windows_separators_denied(self):
        # Claude Code reports native paths; Git Bash on Windows is a supported
        # platform (CLAUDE.md, Cross-Platform), so a backslash path must not
        # slip past basename extraction.
        out = _run(_write(
            r"C:\ws\reviews\x\intermediate_files\json\cleaning_ledger-b.json"))
        assert _is_deny(out)

    def test_case_variant_denied(self):
        # macOS/Windows filesystems are case-insensitive, so this names the
        # same file. The fast_gate needle had the matching gap (see
        # tests/test_fast_gate.py); the gate itself must not add a second one.
        out = _run(_write("json/ENRICHMENT_LEDGER-literature-domain-1.JSON"))
        assert _is_deny(out)

    def test_edit_tool_denied_too(self):
        # Blocking requires PreToolUse on BOTH Write and Edit; the gate itself
        # is tool-agnostic and keys only on file_path.
        out = _run({"tool_name": "Edit",
                    "tool_input": {"file_path": "json/enrichment_ledger-b.json",
                                   "old_string": "a", "new_string": "b"}})
        assert _is_deny(out)

    def test_denial_reason_names_the_owning_scripts(self):
        out = _run(_write("json/enrichment_ledger-b.json"))
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "enrichment_ledger-b.json" in reason
        assert "enrich_bibliography.py" in reason
        # The reason must say what to do instead, not merely refuse.
        assert "re-run" in reason.lower() or "git" in reason.lower()


class TestAllows:
    def test_bib_write_allowed(self):
        assert _run(_write("reviews/x/literature-domain-1.bib")) == {}

    def test_sibling_api_json_allowed(self):
        # The needle hits the whole stdin blob, so ordinary search-result
        # writes in the same directory reach this gate and must pass.
        assert _run(_write(
            "reviews/x/intermediate_files/json/s2_search_results.json")) == {}

    def test_user_file_with_ledger_in_name_allowed(self):
        # Narrow matching on purpose: only the two prefixes the barrier reads.
        assert _run(_write("notes/my_ledger-thoughts.json")) == {}
        assert _run(_write("json/ledger-domain-1.json")) == {}
        assert _run(_write("json/enrichment_ledger.json")) == {}  # no "-<stem>"

    def test_ledger_mentioned_only_in_content_allowed(self):
        # fast_gate's needle is an over-approximation: a Write whose *content*
        # discusses the ledger must not be blocked on that basis.
        out = _run(_write("docs/notes.md",
                          content="see enrichment_ledger-b.json for details"))
        assert out == {}

    def test_non_json_ledger_name_allowed(self):
        assert _run(_write("json/enrichment_ledger-b.txt")) == {}


class TestFailureDirection:
    """This is an ACCURACY gate, so it fails closed and never silently
    (CLAUDE.md gate-failure policy). An earlier draft advertised "fail open
    but loud" while actually failing
    open *silently* — hooks.json's `|| echo` fallback fires only on a nonzero
    exit (a uv/process failure), never on a parse failure."""

    def test_malformed_stdin_denies_with_a_reason(self):
        out = _run("not json at all")
        assert _is_deny(out)
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "could not evaluate" in reason

    def test_empty_stdin_denies(self):
        assert _is_deny(_run(""))

    def test_non_dict_payload_without_a_ledger_name_allows(self):
        # A parseable non-dict is a non-candidate shape, not a gate failure.
        assert _run("[1, 2, 3]") == {}

    def test_schema_change_hiding_a_ledger_write_denies(self):
        # If the payload shape changes so file_path can't be found, a real
        # ledger write must not sail through: the raw-text backstop catches it.
        assert _is_deny(_run({"tool_name": "Write",
                              "params": {"path": "json/enrichment_ledger-b.json"}}))

    def test_missing_file_path_without_a_ledger_name_allows(self):
        assert _run({"tool_name": "Write", "tool_input": {"content": "x"}}) == {}

    def test_non_string_file_path_allows(self):
        assert _run({"tool_name": "Write",
                     "tool_input": {"file_path": 42}}) == {}

    def test_blank_file_path_allows(self):
        assert _run(_write("   ")) == {}


class TestUnitPredicate:
    """is_ledger_path is the whole decision surface — pin it directly too."""

    @staticmethod
    def _pred():
        sys.path.insert(0, str(HOOK.parent))
        try:
            from block_ledger_write import is_ledger_path
        finally:
            sys.path.pop(0)
        return is_ledger_path

    def test_matches_both_kinds_case_insensitively(self):
        pred = self._pred()
        assert pred("Enrichment_Ledger-B.JSON")
        assert pred("CLEANING_LEDGER-b.json")

    def test_trailing_separator_is_not_an_evasion(self):
        # The rstrip is deliberate: a trailing separator makes the path
        # malformed as a write target, and treating it as "not a ledger" would
        # be a one-character bypass. Fail toward blocking.
        pred = self._pred()
        assert pred("json/enrichment_ledger-b.json/")

    def test_rejects_empty_and_non_string(self):
        pred = self._pred()
        assert not pred("")
        assert not pred(None)
