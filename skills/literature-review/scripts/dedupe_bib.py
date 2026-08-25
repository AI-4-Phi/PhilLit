#!/usr/bin/env python3
"""Deduplicate BibTeX entries by citation key and DOI, keeping highest importance.

Also handles:
- Preferring entries with abstract over entries without
- Preserving abstract_source field
- Removing INCOMPLETE flag when merged entry has abstract
"""

import argparse
import json
import re
import sys
from pathlib import Path

from pybtex.database import parse_string

# Import identity/matching helpers from bib_identity (single source of truth)
_hook_dir = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(_hook_dir))
from bib_identity import fallback_key, normalize_doi, title_key  # noqa: E402,F401
from metadata_cleaner import marker_removed_fields  # noqa: E402

sys.path.pop(0)

# Alias, not a copy - pinned by tests/test_dedupe_bib.py.
_normalize_title = title_key

IMPORTANCE_ORDER = {'High': 3, 'Medium': 2, 'Low': 1}


def check_intra_entry_duplicates(content: str) -> list[str]:
    """Warn about duplicate field names within BibTeX entries.

    Lightweight safety-net check for Phase 6 aggregation. Does not crash or
    fix — just prints warnings so operators notice if upstream validation
    was bypassed.

    Uses brace-depth tracking to avoid false positives from multi-line field
    values that happen to contain 'word = text' patterns.

    Returns list of warning strings (empty if clean).
    """
    warnings = []
    lines = content.split('\n')

    current_key = None
    fields_seen: dict[str, int] = {}
    brace_depth = 0
    in_comment = False

    for line_num, line in enumerate(lines, 1):
        entry_match = re.match(r'@(\w+)\{', line, re.IGNORECASE)
        if entry_match and brace_depth == 0:
            entry_type = entry_match.group(1).lower()
            if entry_type == 'comment':
                in_comment = True
                brace_depth += line.count('{') - line.count('}')
                continue
            rest = line[entry_match.end():]
            key_match = re.match(r'([^,]+),', rest)
            if key_match:
                current_key = key_match.group(1).strip()
                fields_seen = {}
                brace_depth = line.count('{') - line.count('}')
            continue

        if in_comment:
            brace_depth += line.count('{') - line.count('}')
            if brace_depth <= 0:
                in_comment = False
                brace_depth = 0
            continue

        if current_key is None:
            continue

        if brace_depth == 1:
            field_match = re.match(r'\s*(\w+)\s*=\s*', line)
            if field_match:
                field_name = field_match.group(1).lower()
                if field_name in fields_seen:
                    msg = (
                        f"  [WARN] '{current_key}': duplicate field '{field_name}' "
                        f"(lines {fields_seen[field_name]} and {line_num})"
                    )
                    warnings.append(msg)
                    print(msg)
                else:
                    fields_seen[field_name] = line_num

        brace_depth += line.count('{') - line.count('}')

        if brace_depth <= 0:
            current_key = None
            fields_seen = {}
            brace_depth = 0

    return warnings


def _field_value_re(field: str) -> re.Pattern:
    """Regex matching `field = {value}` OR `field = "value"` (pybtex Writer
    emits quoted on round-trip). Group 'braced' or 'quoted' carries the value.
    The \\b prefix stops `keywords` matching inside e.g. `otherkeywords`."""
    return re.compile(
        r'\b' + field + r'\s*=\s*(?:\{(?P<braced>(?:[^{}]|\{[^{}]*\})*)\}'
                        r'|"(?P<quoted>[^"]*)")',
        re.IGNORECASE | re.DOTALL,
    )


_KEYWORDS_RE = _field_value_re("keywords")
_ABSTRACT_RE = _field_value_re("abstract")
_YEAR_SUFFIX_RE = _field_value_re("year_suffix")


def _extract_keywords_value(entry: str) -> str:
    """Extract the value of the keywords field from a BibTeX entry."""
    m = _KEYWORDS_RE.search(entry)
    if not m:
        return ''
    return m.group('braced') if m.group('braced') is not None else m.group('quoted')


def _extract_year_suffix_value(entry: str) -> str:
    """Extract the value of the year_suffix field from a BibTeX entry, or
    '' if the entry carries none."""
    m = _YEAR_SUFFIX_RE.search(entry)
    if not m:
        return ''
    value = m.group('braced') if m.group('braced') is not None else m.group('quoted')
    return value.strip()


def _entry_key(entry_text: str) -> str:
    """Citation key parsed from a raw entry's opening line, or '' if
    unparseable. Diagnostic use only (the [SUFFIX] conflict message).

    Deliberately NOT folded onto stamp_evidence.entry_header, the shared
    version: that one keys on `[^,\\s]+`, so it rejects a whitespace-bearing
    key this one accepts, and adopting it would add a cross-module import
    to dedupe_bib for a message string. The divergence costs at most a
    degraded conflict message ("'' and 'smith2020thin'"), never a merge
    decision."""
    m = re.match(r'@\w+\{([^,]+),', entry_text)
    return m.group(1).strip() if m else ''


def _rewrite_keywords(entry: str, transform) -> str:
    """Apply `transform(value) -> value` to the keywords field's value,
    preserving its original delimiter form (braces or quotes)."""
    def _sub(m: re.Match) -> str:
        braced = m.group('braced')
        value = braced if braced is not None else m.group('quoted')
        new = transform(value)
        if braced is not None:
            return f"keywords = {{{new}}}"
        return f'keywords = "{new}"'
    return _KEYWORDS_RE.sub(_sub, entry, count=1)


def parse_importance(entry: str) -> str:
    """Extract importance level from keywords field."""
    keywords = _extract_keywords_value(entry)
    for level in ['High', 'Medium', 'Low']:
        if level in keywords:
            return level
    return 'Low'


def upgrade_importance(entry: str, new_importance: str) -> str:
    """Replace importance level in keywords field."""
    current = parse_importance(entry)
    if current == new_importance:
        return entry
    def _swap(value: str) -> str:
        for level in ['High', 'Medium', 'Low']:
            if level in value:
                return value.replace(level, new_importance, 1)
        return value
    return _rewrite_keywords(entry, _swap)


def extract_doi(entry: str) -> str | None:
    """Extract and normalize DOI from a BibTeX entry.

    Normalization is bib_identity.normalize_doi, shared with metadata_cleaner,
    generate_bibliography and stamp_evidence (ROADMAP item 4) - an inline
    prefix list here used to miss `doi:` and bare `doi.org/`, so the same DOI
    keyed two different ways across the pipeline.
    """
    match = re.search(r'doi\s*=\s*[{"]([^}"]+)["}]', entry, re.IGNORECASE)
    if not match:
        return None
    return normalize_doi(match.group(1))


def has_abstract(entry: str) -> bool:
    """Check if entry has a non-empty abstract field."""
    match = _ABSTRACT_RE.search(entry)
    if match:
        value = match.group('braced') if match.group('braced') is not None else match.group('quoted')
        abstract_content = value.strip()
        return len(abstract_content) > 10  # Filter out trivial abstracts
    return False


def has_incomplete_flag(entry: str) -> bool:
    """Check if entry has INCOMPLETE in keywords."""
    keywords = _extract_keywords_value(entry)
    return 'INCOMPLETE' in keywords


def remove_incomplete_flag(entry: str) -> str:
    """Remove INCOMPLETE and no-abstract flags from keywords field only."""
    def _strip_tokens(value: str) -> str:
        value = re.sub(r',?\s*INCOMPLETE\s*,?', ',', value)
        value = re.sub(r',?\s*no-abstract\s*,?', ',', value)
        value = re.sub(r',\s*,', ',', value)
        return value.strip(', ')
    return _rewrite_keywords(entry, _strip_tokens)


def merge_entries(entry1: str, entry2: str) -> tuple[str, str, int]:
    """
    Merge duplicate entries, preferring one with abstract and higher importance.

    Priority:
    1. Entry with abstract (if only one has it)
    2. Entry with higher importance (if both have or lack abstract)

    Returns:
        Tuple of (merged_entry, merge_reason, winner) where winner is 1 or 2.
    """
    has_abstract_1 = has_abstract(entry1)
    has_abstract_2 = has_abstract(entry2)
    importance_1 = parse_importance(entry1)
    importance_2 = parse_importance(entry2)

    reason = ""
    winner = 1

    if has_abstract_2 and not has_abstract_1:
        base = entry2
        winner = 2
        reason = "preferred entry with abstract"
        if IMPORTANCE_ORDER.get(importance_1, 0) > IMPORTANCE_ORDER.get(importance_2, 0):
            base = upgrade_importance(base, importance_1)
            reason += f", upgraded to {importance_1}"
    elif has_abstract_1 and not has_abstract_2:
        base = entry1
        winner = 1
        reason = "kept entry with abstract"
        if IMPORTANCE_ORDER.get(importance_2, 0) > IMPORTANCE_ORDER.get(importance_1, 0):
            base = upgrade_importance(base, importance_2)
            reason += f", upgraded to {importance_2}"
    else:
        # Both have abstract or neither has it — use importance
        if IMPORTANCE_ORDER.get(importance_2, 0) > IMPORTANCE_ORDER.get(importance_1, 0):
            base = entry2
            winner = 2
            reason = f"upgraded importance to {importance_2}"
        else:
            base = entry1
            winner = 1
            reason = f"kept existing ({importance_1})"

    # Item 3 A: a field the LOSER's cleaner verdict removed must not ship
    # via the winner's unchecked copy - strip it and record the verdict.
    # Deliberate decision (strip-always, review "Important" finding): the
    # loser's positive evidence of unverifiability outweighs the winner's
    # silence - entry text cannot distinguish "cleaned, field survived
    # verified" from "never cleaned" (a marker exists only when changes were
    # made), and a marker records field NAMES only. Rendered References
    # degrade gracefully without these fields (item-13 A7 handles a missing
    # booktitle).
    loser = entry2 if winner == 1 else entry1
    loser_removed = set(marker_removed_fields(_extract_keywords_value(loser)))
    if loser_removed:
        base, failed = _remove_fields_text(base, loser_removed)
        if failed:
            print("  [DEDUPE] warning: could not strip cleaner-flagged "
                  + ", ".join(sorted(failed))
                  + " (malformed entry); the field ships UNVETTED",
                  file=sys.stderr)
        applied = loser_removed - failed
        if applied:
            base = _fold_removals_into_marker(base, applied)
            reason += f", dropped cleaner-flagged {', '.join(sorted(applied))}"

    # Remove INCOMPLETE flag if merged entry has abstract
    if has_abstract(base) and has_incomplete_flag(base):
        base = remove_incomplete_flag(base)
        reason += ", removed INCOMPLETE flag"

    # Item 3 F: carry the Chicago letter forward. Unlike venue_status,
    # losing year_suffix here means the rendered References stops matching
    # prose that already cites the lettered form ("2010a"). Every duplicate
    # copy normally carries the same letter (the barrier assigns it once,
    # over the union of every domain bib), but a per-entry stamping
    # failure, a legacy/hand-edited bib, an entry added after the barrier,
    # or an identity disagreement between the barrier and dedupe can break
    # that. Read the winner's suffix from `base` (not the raw winner text):
    # base is what actually ships, and a prior step in this function (the
    # loser-flagged-field strip above) could in principle have already
    # removed it. Resolved pairwise so a merge CHAIN (3+ domain copies
    # folded in one pair at a time) composes correctly: `base` already
    # carries whatever an earlier step in the chain decided, so a later
    # disagreement is caught against that, not silently overwritten. WHICH
    # letter survives such a chain does depend on merge order (i.e. on the
    # literature-domain-*.bib glob order) - measured over all six orderings
    # of a 3-copy disagreement; the conflict is reported in every one of
    # them, so the ambiguity is never silent.
    loser_text = entry2 if winner == 1 else entry1
    winner_suffix = _extract_year_suffix_value(base)
    loser_suffix = _extract_year_suffix_value(loser_text)
    if winner_suffix and loser_suffix and winner_suffix != loser_suffix:
        winner_key = _entry_key(entry1 if winner == 1 else entry2)
        loser_key = _entry_key(loser_text)
        print(
            f"  [SUFFIX] conflict: '{winner_key}' and '{loser_key}' carry "
            f"'{winner_suffix}' and '{loser_suffix}' - keeping "
            f"'{winner_suffix}', not picking one",
            file=sys.stderr)
    elif not winner_suffix and loser_suffix:
        # No `blocked` guard here, unlike _union_substantive_fields_text
        # beside it: "year_suffix" is outside metadata_cleaner's
        # CLEANABLE_FIELDS, and the cleaner only ever removes a field in
        # that set, so no cleaner verdict can name it and this copy-up
        # cannot resurrect a removed field. Extending CLEANABLE_FIELDS to
        # cover year_suffix would make that guard necessary here.
        base = _insert_field_text(base, "year_suffix", loser_suffix)
        reason += f", copied year_suffix '{loser_suffix}' from loser"

    return base, reason, winner


# Substantive fields a survivor UNIONs in from a loser (spec v2.1 / ADV-A0).
# Keep byte-identical to generate_bibliography._SUBSTANTIVE_FIELDS (the two
# scripts do not import each other by design; pinned by
# tests/test_dedupe_bib.py::TestSubstantiveFieldsIncludeContext).
_SUBSTANTIVE_FIELDS = (
    "journal", "booktitle", "volume", "number", "pages",
    "publisher", "doi", "url", "abstract", "sep_context", "iep_context",
)


def _absorb(merged_from: dict, survivor_id: tuple, loser_id: tuple) -> None:
    """Transfer the loser's accumulated contributors to the survivor,
    transitively: everything the loser had absorbed now belongs to the
    survivor, plus the loser itself. Entry ids are (bib_filename, key)."""
    if loser_id == survivor_id:
        return
    absorbed = merged_from.pop(loser_id, set())
    merged_from.setdefault(survivor_id, set())
    merged_from[survivor_id] |= absorbed | {loser_id}


def _entry_fields(entry_text: str) -> dict:
    """Parse an entry's fields with pybtex (robust to quoted values and nested
    braces). Returns a lowercase-keyed field->value dict, or {} on parse
    failure."""
    try:
        db = parse_string(entry_text, "bibtex")
    except Exception:
        return {}
    for _key, entry in db.entries.items():
        return {name.lower(): val for name, val in entry.fields.items()}
    return {}


# Known field names for _remove_fields_text's over-greedy guard: any of
# these (other than the field being removed) whose assignment disappears
# across a removal means the scan ate into a neighbor - malformed input,
# not a safe strip.
_KNOWN_FIELDS = set(_SUBSTANTIVE_FIELDS) | {
    "author", "title", "year", "editor", "keywords",
    "note", "howpublished", "school", "address",
    # Item 3 D: barrier-stamped venue flag. Known to the over-greedy guard,
    # deliberately NOT substantive: _SUBSTANTIVE_FIELDS drives
    # _union_substantive_fields_text's loser->winner field copy with no
    # coupling to which field justifies which, so listing venue_status here
    # would let a flagged loser's verdict travel onto a survivor whose
    # journal is a different venue entirely (merge_entries picks the winner
    # on abstract-presence and importance, never on _SUBSTANTIVE_FIELDS).
    "venue_status",
    # Item 3 F: barrier-stamped Chicago letter. Known to the over-greedy
    # guard for the same reason as venue_status, but deliberately NOT
    # substantive for the OPPOSITE reason: venue_status's job is done once
    # the writers have read the domain bibs, so losing it in a merge costs
    # nothing; losing year_suffix breaks a rendered References that prose
    # already cites by letter (e.g. "2010a"). Rather than the
    # union-into-a-different-identity risk _SUBSTANTIVE_FIELDS exists to
    # avoid, merge_entries below carries it forward with its own explicit
    # policy (unanimous -> keep; winner missing, loser has it -> copy up;
    # they disagree -> warn and change nothing).
    "year_suffix",
}


def _assignment_start_re(field: str) -> re.Pattern:
    """Locate `field`'s assignment start (`field = `), case-insensitive,
    word-bounded so e.g. `author` doesn't match inside `coauthor`. Shared by
    `_remove_fields_text`'s scan and its over-greedy post-condition guard."""
    return re.compile(r'\b' + re.escape(field) + r'\s*=\s*', re.IGNORECASE)


def _remove_fields_text(entry_text: str, fields: set[str]) -> tuple[str, set[str]]:
    """Surgically remove `fields` from a raw BibTeX entry via brace/quote-depth
    scanning of the text itself - no pybtex round-trip. A full parse +
    reserialize reinterprets a single-braced corporate author
    (`author = {National Research Council}`) as a person name and rewrites it
    on output (`author = "Council, National Research"`) - the first place
    this file WRITES a reinterpreted name back into shipped text (ROADMAP
    item 3 A review finding 1). The scanner never touches any field but the
    one it is removing.

    Returns (new_text, failed): `failed` is the subset of `fields` whose
    assignment IS present but could not be safely removed - a truncated/
    unbalanced value, or a scan whose removal span would have swallowed a
    neighboring field's assignment (checked by a post-condition guard, since
    a regex miss on malformed input must never masquerade as a successful
    strip - review finding 2). A field entirely absent from the entry is not
    a failure; it is simply skipped (nothing ships either way)."""
    out = entry_text
    failed: set[str] = set()
    for f in fields:
        m = _assignment_start_re(f).search(out)
        if not m:
            continue  # not present - nothing to remove, not a failure
        val_start = m.end()
        if val_start >= len(out):
            failed.add(f)
            continue
        ch = out[val_start]
        if ch == '{':
            depth = 0
            value_end = None
            for i in range(val_start, len(out)):
                if out[i] == '{':
                    depth += 1
                elif out[i] == '}':
                    depth -= 1
                    if depth == 0:
                        value_end = i + 1
                        break
            if value_end is None:
                failed.add(f)
                continue
        elif ch == '"':
            close = out.find('"', val_start + 1)
            if close == -1:
                failed.add(f)
                continue
            value_end = close + 1
        else:
            comma = out.find(',', val_start)
            newline = out.find('\n', val_start)
            ends = [e for e in (comma, newline) if e != -1]
            value_end = min(ends) if ends else len(out)

        removal_start = m.start()
        # Consume leading line indentation (spaces/tabs immediately preceded
        # by a newline) so no blank indented line is left behind.
        j = removal_start
        while j > 0 and out[j - 1] in ' \t':
            j -= 1
        if j > 0 and out[j - 1] == '\n':
            removal_start = j

        trailing = re.match(r'\s*,?', out[value_end:])
        removal_end = value_end + trailing.end()

        candidate = out[:removal_start] + out[removal_end:]

        # Post-condition guard: removing `f` must not disturb any OTHER
        # known field's assignment. If one disappeared, the scan was
        # over-greedy on malformed input (e.g. an unclosed brace consumed a
        # neighboring field) - treat as a failure and keep the pre-removal
        # text.
        known_others = _KNOWN_FIELDS - {f.lower()}
        before = {k for k in known_others if _assignment_start_re(k).search(out)}
        after = {k for k in before if _assignment_start_re(k).search(candidate)}
        if before - after:
            failed.add(f)
            continue

        # Same guard, aimed at `f` itself (ROADMAP item 3 review C1): the
        # scan above locates the FIRST `f = ` in the whole entry text, which
        # can be a field-name-shaped substring inside a DIFFERENT field's
        # value (e.g. `abstract = {We discuss pages = 12, and more.}` with
        # flagged field `pages`) rather than the real assignment. The
        # `known_others` check above can't see this - it deliberately
        # excludes `f` itself. If an `f = ` assignment is still findable
        # after the removal, either the removed span was the fake one (the
        # real field survives untouched, but so does the fake text we
        # thought we deleted alongside a mangled neighbor - ambiguous) or a
        # genuine second occurrence remains (also ambiguous). Neither is a
        # safe silent success; report the field failed and keep the
        # pre-removal text so nothing ships mangled or half-stripped.
        if _assignment_start_re(f).search(candidate):
            failed.add(f)
            continue

        out = candidate
    return out.strip(), failed


def _fold_removals_into_marker(entry_text: str, removed: set[str]) -> str:
    """Extend the entry's METADATA_CLEANED marker with `removed` names so the
    verdict travels with the merged entry. Creates the marker (and a keywords
    field) when absent."""
    if not removed:
        return entry_text
    current = _extract_keywords_value(entry_text)
    already = marker_removed_fields(current)
    to_add = sorted(set(removed) - set(already))
    if not to_add:
        return entry_text
    if "METADATA" in current and "_CLEANED" in current.replace("\\", ""):
        # Append names to the existing marker's change list (marker is
        # always the keywords tail - _MARKER_RE contract).
        new_value = current.rstrip() + ", " + ", ".join(to_add)
        return _rewrite_keywords(entry_text, lambda _v: new_value)
    marker = "METADATA_CLEANED: " + ", ".join(to_add)
    if current:
        return _rewrite_keywords(
            entry_text, lambda v: v.rstrip().rstrip(",") + ", " + marker)
    # No keywords field at all: insert one.
    return _insert_field_text(entry_text, "keywords", marker)


def _fallback_key(entry_text: str) -> tuple[str, str, str] | None:
    """Title-axis dedup key: (normalized_title, year, first-author surname).

    Parsed with pybtex so quoted values (title = "...") and nested braces
    ({The {AI} Problem}) are handled — the regex extractors elsewhere in this
    file are brace-only and non-nested. The key itself is built by
    bib_identity.fallback_key, which generate_bibliography also uses
    (ROADMAP item 4).
    """
    try:
        db = parse_string(entry_text, "bibtex")
    except Exception:
        return None
    entry = None
    for _key, e in db.entries.items():
        entry = e
        break
    if entry is None:
        return None
    persons = entry.persons.get("author", []) or entry.persons.get("editor", [])
    surname = ""
    if persons:
        surname = " ".join(persons[0].prelast_names + persons[0].last_names)
    return fallback_key(
        entry.fields.get("title", "") or "",
        entry.fields.get("year", "") or "",
        surname,
    )


def _insert_field_text(entry_text: str, field: str, value: str) -> str:
    """Insert `field = {value},` immediately after the entry's opening line
    (`@type{key,`). The opening line is never inside a field value, so a
    multi-line value can't swallow the insertion."""
    lines = entry_text.split("\n")
    for i, line in enumerate(lines):
        if re.match(r'\s*@\w+\s*\{', line):
            indent = "  "
            for j in range(i + 1, len(lines)):
                body = lines[j].strip()
                if body and not body.startswith("}"):
                    m = re.match(r'^(\s*)', lines[j])
                    if m and m.group(1):
                        indent = m.group(1)
                    break
            stripped = lines[i].rstrip()
            if not stripped.endswith(","):
                stripped += ","
            lines[i] = stripped
            lines.insert(i + 1, f"{indent}{field} = {{{value}}},")
            return "\n".join(lines)
    return entry_text


def _union_substantive_fields_text(winner_text: str, loser_text: str) -> str:
    """Union the loser's substantive fields into the winner's text (spec v2.1 /
    ADV-A0): insert every field in _SUBSTANTIVE_FIELDS the loser has and the
    winner lacks. Field extraction uses pybtex so quoted/nested-brace values
    are handled."""
    winner_fields = _entry_fields(winner_text)
    loser_fields = _entry_fields(loser_text)
    blocked = set(marker_removed_fields(_extract_keywords_value(winner_text))) \
        | set(marker_removed_fields(_extract_keywords_value(loser_text)))
    out = winner_text
    for f in _SUBSTANTIVE_FIELDS:
        if f in blocked:
            continue
        w = (winner_fields.get(f) or "").strip()
        l = (loser_fields.get(f) or "").strip()
        if not w and l:
            out = _insert_field_text(out, f, loser_fields[f])
            winner_fields[f] = loser_fields[f]
    return out


def dedupe_by_title_key(
    seen: dict[str, str],
    origin: dict[str, tuple] | None = None,
    merged_from: dict[tuple, set] | None = None,
) -> list[str]:
    """Third dedup pass: catch same-work duplicates that share no DOI, keyed on
    (normalized_title, year, first-author surname). Winner via merge_entries()
    (abstract-preference, then importance); the survivor then UNIONs in any
    substantive field the loser had and it lacked (spec v2.1 / ADV-A0 —
    merge_entries alone is winner-take-all). DOI identity is tracked per GROUP:
    a merge is refused when the two groups' non-empty DOI sets differ.
    Mutates `seen` in place; returns removed keys.

    When `origin`/`merged_from` are given (see deduplicate_bib), contributor
    tracking is maintained across merges: the removed key's provenance is
    absorbed transitively into the survivor's.
    """
    seen_titles: dict[tuple, str] = {}
    group_dois: dict[str, set] = {}
    title_dupes: list[str] = []
    for key, entry in list(seen.items()):
        if key not in seen:  # already removed as a loser earlier this pass
            continue
        fkey = _fallback_key(entry)
        if fkey is None:
            continue
        doi = extract_doi(entry)
        new_dois = {doi} if doi else set()
        if fkey in seen_titles:
            existing_key = seen_titles[fkey]
            existing_dois = group_dois.get(existing_key, set())
            # Distinct non-empty DOI sets => genuinely different works; keep both.
            if new_dois and existing_dois and new_dois != existing_dois:
                continue
            merged, reason, winner = merge_entries(seen[existing_key], entry)
            merged_dois = existing_dois | new_dois
            if winner == 2:
                # New entry (key) won; union the loser's (existing) fields in.
                merged = _union_substantive_fields_text(merged, seen[existing_key])
                print(f"  [DEDUPE-TITLE] '{key}' and '{existing_key}' share title-key - keeping '{key}' ({reason})")
                del seen[existing_key]
                seen[key] = merged
                seen_titles[fkey] = key
                group_dois.pop(existing_key, None)
                group_dois[key] = merged_dois
                title_dupes.append(existing_key)
                if origin is not None and merged_from is not None:
                    _absorb(merged_from, origin[key], origin.pop(existing_key))
            else:
                # Existing entry won; union the loser's (new) fields in.
                merged = _union_substantive_fields_text(merged, entry)
                print(f"  [DEDUPE-TITLE] '{key}' and '{existing_key}' share title-key - keeping '{existing_key}' ({reason})")
                seen[existing_key] = merged
                del seen[key]
                group_dois[existing_key] = merged_dois
                title_dupes.append(key)
                if origin is not None and merged_from is not None:
                    _absorb(merged_from, origin[existing_key], origin.pop(key))
        else:
            seen_titles[fkey] = key
            group_dois[key] = new_dois
    return title_dupes


def deduplicate_bib(
    input_files: list[Path],
    output_file: Path,
    evidence_report: Path | None = None,
) -> list[str]:
    """
    Deduplicate BibTeX entries across files.

    When merging duplicates:
    - Prefers entry with abstract over entry without
    - Upgrades importance to highest among duplicates
    - Removes INCOMPLETE flag if merged entry has abstract
    - Second pass catches same paper with different keys via DOI
    - Third pass catches same paper with no shared DOI via title/year/author

    When `evidence_report` is given, every surviving entry's EVIDENCE-* token
    is re-stamped from the report's attestations, re-verified against the
    MERGED field values (see restamp_merged).

    Returns list of duplicate keys that were removed.
    """
    seen: dict[str, str] = {}  # key -> entry_text
    comments: list[str] = []
    duplicates: list[str] = []
    # Contributor tracking for the attestation-aware re-stamp. An entry's
    # identity is (source_bib_filename, key) — citation keys are only unique
    # within one file (shared contract). `origin` maps each current seen-key
    # to the identity of the entry occupying it; `merged_from` maps a
    # surviving identity to every identity absorbed into it (transitive).
    origin: dict[str, tuple] = {}
    merged_from: dict[tuple, set] = {}

    for bib_file in input_files:
        content = bib_file.read_text(encoding='utf-8')

        # Safety-net: warn about duplicate fields within entries
        check_intra_entry_duplicates(content)

        # Split into entries (handles @comment, @article, @book, etc.)
        entries = re.split(r'\n(?=@)', content)

        for entry in entries:
            if not entry.strip():
                continue

            # Extract citation key
            match = re.match(r'@(\w+)\{([^,]+),', entry)
            if not match:
                if entry.strip().startswith('@comment'):
                    comments.append(entry)
                continue

            entry_type = match.group(1).lower()
            key = match.group(2).strip()

            if entry_type == 'comment':
                comments.append(entry)
                continue

            if key in seen:
                duplicates.append(key)
                merged, reason, winner = merge_entries(seen[key], entry)
                incoming_id = (bib_file.name, key)
                if winner == 2:
                    survivor_id, loser_id = incoming_id, origin[key]
                else:
                    survivor_id, loser_id = origin[key], incoming_id
                origin[key] = survivor_id
                _absorb(merged_from, survivor_id, loser_id)
                seen[key] = merged
                print(f"  [DEDUPE] Duplicate '{key}' - {reason}")
            else:
                seen[key] = entry
                origin[key] = (bib_file.name, key)

    # Second pass: DOI-based deduplication (catches same paper with different keys)
    seen_dois: dict[str, str] = {}  # normalized_doi -> key
    doi_dupes: list[str] = []
    for key, entry in list(seen.items()):
        doi = extract_doi(entry)
        if doi is None:
            continue
        if doi in seen_dois:
            existing_key = seen_dois[doi]
            existing_entry = seen[existing_key]
            merged, reason, winner = merge_entries(existing_entry, entry)
            if winner == 2:
                # New entry won — replace
                print(f"  [DEDUPE-DOI] '{key}' and '{existing_key}' share DOI {doi} - keeping '{key}' ({reason})")
                del seen[existing_key]
                seen[key] = merged
                seen_dois[doi] = key
                doi_dupes.append(existing_key)
                _absorb(merged_from, origin[key], origin.pop(existing_key))
            else:
                # Existing entry won
                print(f"  [DEDUPE-DOI] '{key}' and '{existing_key}' share DOI {doi} - keeping '{existing_key}' ({reason})")
                seen[existing_key] = merged
                del seen[key]
                doi_dupes.append(key)
                _absorb(merged_from, origin[existing_key], origin.pop(key))
        else:
            seen_dois[doi] = key

    duplicates.extend(doi_dupes)

    # Third pass: title-key deduplication (catches the same work with no shared
    # DOI — e.g. after a cleaner stripped DOIs from both copies).
    title_dupes = dedupe_by_title_key(seen, origin, merged_from)
    duplicates.extend(title_dupes)

    # Attestation-aware re-stamp of the merged entries (before writing).
    if evidence_report is not None:
        restamp_merged(seen, origin, merged_from, evidence_report)

    # Write output
    with output_file.open('w', encoding='utf-8') as f:
        for comment in comments:
            f.write(comment.rstrip())
            f.write('\n\n')

        for key, entry in seen.items():
            f.write(entry.rstrip())
            f.write('\n\n')

    return duplicates


def restamp_merged(
    seen: dict[str, str],
    origin: dict[str, tuple],
    merged_from: dict[tuple, set],
    report_path: Path,
) -> None:
    """Re-stamp every surviving entry's EVIDENCE-* token after dedup.

    For each entry, take the highest tier computable over the MERGED fields
    under any contributing (bib_file, key)'s attestation — where each
    attestation is first RE-VERIFIED against the merged values (spec §9,
    hardened): a bare boolean from one contributor must never authorize
    another contributor's (possibly fabricated) field value. Abstract and
    context attestations re-check the value hash; the identifier attestation
    is value-bound inside compute_tier. Every failure path demotes (an entry
    whose attestation no longer matches computes EVIDENCE-NONE).
    """
    script_dir = str(Path(__file__).parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import stamp_evidence as se
    import web_evidence as wv

    # The supported pipeline puts the report at
    # <review_dir>/intermediate_files/json/evidence_report.json, which is how
    # the captures directory (a sibling under intermediate_files/) is found
    # for the web re-check below. Underivable -> the re-check degrades to the
    # URL-only binding, never to a crash.
    review_dir = next(
        (p.parent for p in Path(report_path).resolve().parents
         if p.name == "intermediate_files"),
        None,
    )
    capture_cache: dict = {}

    def _capture(citekey):
        if citekey not in capture_cache:
            capture_cache[citekey] = (
                wv.load_capture(review_dir, citekey)
                if review_dir is not None else None)
        return capture_cache[citekey]

    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(
            f"[DEDUPE] warning: evidence report unreadable at {report_path}; "
            "all entries re-stamp EVIDENCE-NONE",
            file=sys.stderr,
        )
        report = {}
    if not isinstance(report, dict):
        report = {}
    atts = report.get("attestations", {})
    if not isinstance(atts, dict):
        atts = {}
    # REPORT VINTAGE, not report provenance. `abstract_attested` means
    # "corroborated by a live fetch" only from schema_version 2 on (item
    # 15); in a version-1 report it means "the enrichment ledger matched",
    # which is precisely what the gate stopped accepting. Carrying such a
    # flag across a Phase-6-only re-run would re-grant EVIDENCE-ABSTRACT on
    # ledger equality alone -- the same shape as the pre-exclusion
    # web_gate_passed blob the excluded_host re-check below refuses, and
    # fail-closed for the same reason. `isinstance(True, int)` is True but
    # `True >= 2` is not, so a bool cannot pass; a string cannot either.
    version = report.get("schema_version")
    abstract_vintage_ok = isinstance(version, int) and version >= 2

    def _blob(entry_id):
        """Attestation dict for (bib_file, key), or None. Malformed report
        structure (non-dict at either level) reads as no attestation —
        demote-only, never a crash."""
        bib_file, key = entry_id
        inner = atts.get(bib_file)
        if not isinstance(inner, dict):
            return None
        blob = inner.get(key)
        return blob if isinstance(blob, dict) else None

    def _reverified_att(blob, fields, contrib_key):
        """Rebuild an EntryAttestation valid for the MERGED fields."""
        if not blob:
            return se.EntryAttestation()
        # Conjoins the barrier's own boolean, exactly like the context and
        # web re-verifications below -- the hash re-check alone is NOT
        # equivalent to it. Ledger equality stopped being attestation when
        # the barrier put a live corroboration fetch in front of the ABSTRACT
        # tier (item 15): recomputing from source+hash here would hand
        # EVIDENCE-ABSTRACT straight back to every entry the gate refused,
        # in the delivered bibliography. The hash re-check still has to run
        # on top, for its original reason: one contributor's boolean must
        # never authorize another contributor's text.
        abstract_ok = (
            abstract_vintage_ok
            and bool(blob.get("abstract_attested"))
            and se.attest_abstract(fields, {
                "abstract_source": blob.get("abstract_source"),
                "abstract_sha256": blob.get("abstract_sha256"),
            }))
        cf = blob.get("context_field")
        context_ok = bool(
            blob.get("context_written") and cf and fields.get(cf)
            and se.abstract_hash(fields[cf]) == blob.get("context_sha256")
        )
        # The web gate is VALUE-BOUND here, like the abstract and context
        # hashes above and for the same reason: a bare boolean from one
        # contributor must never authorize another contributor's URL. Without
        # this re-verification the flag could not be carried across the merge at
        # all -- and without carrying it, EVERY web entry re-stamps
        # EVIDENCE-NONE here, silently making a cited source uncitable in
        # Phase 6 after the writer already cited it. The excluded_host check
        # closes a third grant site: a Phase-6-only re-run against a
        # PRE-exclusion evidence_report.json can carry a blob with
        # web_gate_passed True for a now-excluded host (e.g. SEP); that must
        # not re-stamp EVIDENCE-WEB just because the URL matches.
        web_url = blob.get("web_url")
        web_ok = bool(
            blob.get("web_gate_passed") and web_url
            and wv.normalize_url(wv.extract_url(fields) or "") == web_url
            and not wv.excluded_host(web_url)
        )
        # URL equality alone cannot re-bind the gate to MERGED content: a
        # merge can pair this contributor's attestation with the OTHER
        # contributor's web_span (same normalized URL -- the population the
        # duplicate-across-domains dedupe exists for), shipping spans never
        # containment-checked against any capture. So when the contributor's
        # capture is on disk, re-run the full capture check over the merged
        # values (pure string work, no network -- existence was probed at the
        # barrier). A missing capture degrades to the URL-only binding above:
        # absence can never promote anything the barrier did not already
        # pass, and legacy invocations without the intermediate_files layout
        # keep their behavior. An error-record capture fails check_capture,
        # which is correct: fetch_web never overwrites a good capture with a
        # failure record, so error + gate-passed blob is an inconsistency.
        if web_ok:
            capture = _capture(contrib_key)
            if capture is not None:
                if (wv.excluded_host(capture.get("url") or "")
                        or wv.excluded_host(capture.get("final_url") or "")):
                    web_ok = False
                else:
                    web_ok, _ = wv.check_capture(
                        capture, wv.extract_url(fields) or "",
                        fields.get("title") or "",
                        fields.get("web_span") or "")
        return se.EntryAttestation(
            abstract_attested=abstract_ok,
            context_written=context_ok,
            api_matched=bool(blob.get("api_matched")),
            verified_identifier=blob.get("verified_identifier"),
            verified_identifier_value=blob.get("verified_identifier_value"),
            breaker_tripped=bool(blob.get("breaker_tripped")),
            web_gate_passed=web_ok,
        )

    for key, entry in seen.items():
        header = se.entry_header(entry)
        if not header:
            continue
        etype, _ = header
        fields = se.parse_entry_fields(entry)
        me = origin[key]
        contributing = {me} | merged_from.get(me, set())
        best = max(
            (se.compute_tier(etype, fields,
                             _reverified_att(_blob(c), fields, c[1]))
             for c in contributing),
            key=lambda t: se.TIER_RANK[t],
        )
        seen[key] = se.stamp_entry_text(entry, best)


def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate BibTeX entries across files.",
    )
    parser.add_argument("output", type=Path, help="output .bib file")
    parser.add_argument("inputs", nargs="+", type=Path, help="input .bib files")
    parser.add_argument(
        "--evidence-report", type=Path, default=None,
        help="evidence_report.json for attestation-aware tier re-stamping",
    )
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        if exc.code not in (0, None):  # keep --help exiting 0
            print("Usage: dedupe_bib.py output.bib input1.bib [input2.bib ...] [--evidence-report report.json]")
            sys.exit(1)
        raise

    # Validate input files exist
    for f in args.inputs:
        if not f.exists():
            print(f"Error: Input file not found: {f}")
            sys.exit(1)

    if args.evidence_report is None:
        print("[DEDUPE] warning: no --evidence-report; tier tokens not re-stamped",
              file=sys.stderr)

    duplicates = deduplicate_bib(args.inputs, args.output,
                                 evidence_report=args.evidence_report)

    if duplicates:
        print(f"\n  Removed {len(duplicates)} duplicate entries")
    else:
        print("\n  No duplicates found")


if __name__ == '__main__':
    main()
