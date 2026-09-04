"""Locate fields in raw BibTeX text: the one owner of that job.

The barrier pipeline edits bibliographies as TEXT -- it splices, strips and
re-stamps individual fields inside chunks it otherwise leaves byte-for-byte
alone -- so it needs to know where a field's value starts and ends without
re-serialising the entry. pybtex cannot give it that: a parse loses the
spans, moves author/editor into `.persons`, rewrites a single-braced
corporate author as a person name on output, and rejects a chunk outright
on a duplicate field, where a lenient reader should still return the rest.
pybtex stays the STRICT gate (the barrier validates every domain bib with it
before doing anything else, SubagentStop re-validates, `_derived_field_took`
re-parses a spliced chunk); this module is the lenient reader beside it.
Every field VALUE read, edited or stripped in this directory is located
here. Outside it, by design: the barrier's `\\b<name>\\s*=` presence counters
(they count assignments in a splice check, not bound values), dedupe_bib's
line-based duplicate-field warning, and dedupe_bib's field remover's one
textual check: a `name =` in the tail past where `scan` says trust ended.

The reader it replaced was a regex whose value alternation admitted a brace
group containing no braces -- ONE level of nesting. The standard LaTeX accent
form nests two (`Mendon{\\c{c}}a`, `Garc{\\'{i}}a`), so any field carrying it
failed to match and was dropped from the parse: absent, not mangled, not
flagged. Two consumers degraded together from the same dict -- the barrier's
same-work grouping produced no key, and the Chicago a/b pass reached its
fallback key with an empty surname axis. Census over 8,894 delivered
entries: 39 fields dropped -- 22 authors and 11 titles (the 33 entries that
lost their same-work key, all with accented names), 2 journals, and 4 BARE
values (`year = 2016,`, valid BibTeX, which the regex also skipped)
(docs/known-issues/field-parse-divergence-measurement-2026-09-02/). Depth
counting has no wall to move: it tracks a counter instead of matching a fixed
shape.

Grammar read here (BibTeX's, minus macro expansion):

    field  := name '=' value
    value  := piece ('#' piece)*
    piece  := '{' balanced '}' | '"' quoted '"' | bare
    bare   := run of characters outside whitespace and  " # % ' ( ) , = { }

Inside a quoted piece, braces balance and a `"` at brace depth zero closes it.
Concatenated pieces are joined; a bare macro name is returned as its own
text, since no @string table is read. Nothing is unescaped or normalised.

Scanning is STRUCTURAL: a field is recognised only inside an entry and at
its top level -- never inside a value, never in a skipped block, never in
the commentary between entries -- so text shaped like `year = {1999}` inside
an abstract, or in a note after the entry, is not a field, which the regex
got wrong on both counts. (A repeated name keeps the last value.) A bare
value is a macro identifier, so a `#` inside one is BibTeX's concatenation
operator, not text -- a bare URL with a fragment reads wrong, but the engine
never writes bare values, and an undefined one fails the barrier's pybtex
validation before any decision reads it. On a piece that opens and never
closes the scan stops and returns what it has read: fail lenient, never
loud, because the strict gate is pybtex's.

There is NO `%` handling, and the reason it costs nothing is worth stating
precisely, because external reviewers keep reasoning about it and keep
arriving at a false premise. **`%` has no line-comment semantics in the
BibTeX data syntax pybtex implements.** It is not that a comment is handled
leniently here; there is no `%` comment to handle. The convention only looks
like one because text outside an entry is skipped until the next `@` -- which
this scanner does structurally (above) and pybtex does too. Two consequences
that surprise people: a `%` does NOT comment an entry out (pybtex parses
`% @article{old, ...}` as the entry `old`, and so does this scanner -- they
AGREE), and a comment-aware reader would be the one diverging from the strict
gate.

Rather than enumerate positions, the property measured over 21 `%` placements
-- in values (braced, quoted, escaped `50\\%`), at top level, in `@comment`
payloads carrying braces or an `@`, in `@preamble`, in `@string`, at field
position, between a field name and its `=`, after the `=`, swallowing an
entry's closing brace, in the entry key, in the entry type, in a bare value,
around `#` concatenation, and in the parenthesised entry form:

    Of those placements, every one pybtex ACCEPTED this scanner read the same
    way; the disagreements are all on text pybtex REFUSES.

Read the scope literally: that is a statement about `%` placement, NOT about
scanner/pybtex equivalence in general, which is FALSE and deliberately so.
Two intentional differences on text pybtex accepts, both documented above and
neither involving `%`: no @string table is read, so a defined macro comes back
as its own bare text where pybtex substitutes the expansion
(`@string{x = "Expanded"}` + `title = x` gives `x` here and `Expanded` there,
and macro `#` concatenation likewise); and pybtex moves author/editor out of
`Entry.fields` into `.persons` where this reports them as the text fields they
are. A general equivalence claim here was an overclaim, caught in review; the
sentence above is the one the measurement supports.

The scan of REFUSED text is meaningless -- it may read a comment word as a
field name, or stop early -- and that is harmless only because of a CALL-ORDER
property, not a property of this module: `validate_bib_write` parses through
this same pybtex, and the barrier's `_parseable_bib` marks an unparseable
domain bib `malformed` and drops it before any field is scanned. If that
ordering ever changes, this paragraph stops being true, which is why
`test_unparseable_bib_is_never_field_scanned` SPIES on the scanner rather
than checking outputs -- asserting the final report cannot tell "never
scanned" apart from "scanned, then discarded" -- with a sibling test proving
the spy is not vacuous.

`test_percent_at_field_position_is_refused_by_the_strict_gate` pins the
refusal half; the agreement half is pinned beside it. If a pybtex release
adds `%` comment semantics, both go loud, which is the point.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, NamedTuple

# Characters BibTeX excludes from identifiers (field and macro names).
_NAME_RE = re.compile(r"""[^\s"#%'(),={}]+""")
# Both entry delimiters, whitespace tolerated around the key: this only
# steps OVER a header, it never identifies an entry (stamp_evidence.
# entry_header does that, more strictly). The three non-entry block types
# are excluded by name so `@comment{TODO, ...}` is skipped whole rather than
# read as an entry whose fields then leak into the parse.
_HEADER_RE = re.compile(
    r"@(?!(?:comment|string|preamble)\b)\w+\s*([{(])\s*[^,\s]+\s*,",
    re.IGNORECASE)
_CLOSER = {"{": "}", "(": ")"}
_WS_RE = re.compile(r"\s*")


@dataclass(frozen=True)
class Field:
    """One field as it sits in the text.

    `text[value_start:value_end]` is the raw value with its delimiters (for a
    concatenation, from the first piece's opening delimiter to the last
    piece's closing one); `value` is the same span with delimiters removed
    and pieces joined, NOT stripped. `name` keeps the case it was written in.
    """
    name: str
    name_start: int
    value_start: int
    value_end: int
    value: str


def _ws(text: str, i: int) -> int:
    return _WS_RE.match(text, i).end()


def _balanced_end(text: str, i: int) -> int | None:
    """Index just past the `}` closing the group opened at `text[i] == '{'`."""
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
    return None


def _quoted_end(text: str, i: int) -> int | None:
    """Index just past the `"` closing the string opened at `text[i] == '"'`.
    Braces balance inside, and a `"` only closes at brace depth zero. A stray
    `}` (depth would go negative) is treated as text, so `"see } below"`
    still closes. If the braces never balance at all (`"a } b { c"`), fall
    back to the next `"`, as the old reader did, rather than end the scan;
    pybtex rejects such a value anyway."""
    depth = 0
    for j in range(i + 1, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif c == '"' and depth == 0:
            return j + 1
    end = text.find('"', i + 1)
    return None if end == -1 else end + 1


def _paren_block_end(text: str, i: int) -> int | None:
    """Index just past the `)` closing a `@word(...)` block opened at
    `text[i] == '('`: a `)` counts only outside braces and quotes."""
    depth = 0
    in_quote = False
    for j in range(i + 1, len(text)):
        c = text[j]
        if in_quote:
            if c == "{":
                depth += 1
            elif c == "}":
                depth = max(0, depth - 1)
            elif c == '"' and depth == 0:
                in_quote = False
        elif c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif c == '"' and depth == 0:
            in_quote = True
        elif c == ")" and depth == 0:
            return j + 1
    return None


class _Unbounded(Exception):
    """A `{` or `"` piece opened and the text ended before it closed. Nothing
    after it can be trusted, so the scan ends (fields already read stand)."""


def _read_piece(text: str, i: int) -> tuple[str, int] | None:
    """(piece content, index just past its closing delimiter); None if no
    piece starts at `i`; raises _Unbounded if one starts and never closes."""
    if i >= len(text):
        return None
    c = text[i]
    if c == "{":
        end = _balanced_end(text, i)
    elif c == '"':
        end = _quoted_end(text, i)
    else:
        m = _NAME_RE.match(text, i)
        return None if not m else (m.group(), m.end())
    if end is None:
        raise _Unbounded
    return text[i + 1:end - 1], end


def _read_value(text: str, i: int) -> tuple[str, int] | None:
    """(joined value, index just past the last piece), or None if no piece
    starts at `i` (`note = ,`). A `#` followed by something that is not a
    piece (`{2020} #,`) is dropped and the value ends at the last piece read
    -- malformed, but what was read is complete, and abandoning the entry
    would lose it. A piece that opens and never closes, first or later,
    raises _Unbounded."""
    first = _read_piece(text, i)
    if first is None:
        return None
    pieces, end = [first[0]], first[1]
    while True:
        j = _ws(text, end)
        if j >= len(text) or text[j] != "#":
            return "".join(pieces), end
        nxt = _read_piece(text, _ws(text, j + 1))
        if nxt is None:
            return "".join(pieces), end
        pieces.append(nxt[0])
        end = nxt[1]


def _scan(text: str, stop: list, unreadable: list) -> Iterator[Field]:
    """Body of iter_fields. When the scan ends early -- on a value that never
    closes, or on a skipped `@word{` block that never closes -- the index
    where trust ended (the field's NAME, or the block's `@`) is appended to
    `stop`. An assignment skipped for having no readable value (`note = ,`)
    is appended to `unreadable` as (name, name index)."""
    n = len(text)
    i = 0
    close = None  # the delimiter that ends the entry being read, if any
    while i < n:
        if close is None:
            i = text.find("@", i)
            if i == -1:
                return
        c = text[i]
        if c == "@":
            m = _HEADER_RE.match(text, i)
            if m:
                close = _CLOSER[m.group(1)]
                i = m.end()
                continue
            m = _NAME_RE.match(text, i + 1)
            j = _ws(text, m.end()) if m else i + 1
            if j < n and text[j] == "{":
                end = _balanced_end(text, j)
                if end is None:
                    stop.append(i)
                    return
                i = end
                continue
            if j < n and text[j] == "(":
                end = _paren_block_end(text, j)
                if end is None:
                    # Never closed: keep reading leniently, but mark that
                    # trust ended here for callers that must not guess.
                    stop.append(i)
                    i = j + 1
                else:
                    i = end
                continue
            i = j
            continue
        if c == close:
            close = None
            i += 1
            continue
        if c.isspace() or c in ",}":
            i += 1
            continue
        m = _NAME_RE.match(text, i)
        if not m:
            i += 1
            continue
        j = _ws(text, m.end())
        if j >= n or text[j] != "=":
            i = m.end()
            continue
        value_start = _ws(text, j + 1)
        try:
            read = _read_value(text, value_start)
        except _Unbounded:
            stop.append(m.start())
            return
        if read is None:
            unreadable.append((m.group(), m.start()))
            i = value_start  # no value at all (`note = ,`): drop it, go on
            continue
        value, value_end = read
        yield Field(m.group(), m.start(), value_start, value_end, value)
        i = value_end


def iter_fields(text: str) -> Iterator[Field]:
    """Every field in `text`, in order -- across entries if there are several.

    Fields are read only INSIDE an entry: from its `@type{key,` (or
    `@type(key,`) header to the delimiter that closes it. Text outside
    entries is commentary, as BibTeX treats it, and is skipped -- so are a
    `@comment`, `@string` or `@preamble` block and any other `@word{...}` /
    `@word(...)` block. Inside an entry, a token that is not followed by `=`
    is skipped, and so is an assignment with no value at all (`note = ,`).
    Only a piece that OPENS with `{` or `"` and never closes -- first or
    after a `#` -- or an unclosed skipped `@word{` block ends the scan;
    everything read before it is returned. This iterator hides WHERE it
    stopped; a caller that must tell "absent" from "unreadable" uses scan().
    """
    yield from _scan(text, [], [])


class Scan(NamedTuple):
    """What a full scan saw: the fields; `stop`, the index from which the
    text could no longer be trusted (an unclosed value's name, or an
    unclosed skipped `@word{` / `@word(` block's `@` -- after an unclosed
    `(` block the scan keeps reading leniently, so fields may follow it),
    None if trust held to the end; and the assignments skipped for having
    no readable value, as (name, index)."""
    fields: list[Field]
    stop: int | None
    unreadable: list[tuple[str, int]]


def scan(text: str) -> Scan:
    """For callers that must distinguish a field that is ABSENT from one that
    is present but unreadable -- past the point the text stops being
    trustworthy, or written with no value at all."""
    stop: list = []
    unreadable: list = []
    fields = list(_scan(text, stop, unreadable))
    return Scan(fields, stop[0] if stop else None, unreadable)


def parse_entry_fields(entry_text: str) -> dict:
    """Field name (lowercased) -> value (stripped). A repeated name keeps the
    last value, as the regex reader did; pybtex rejects such an entry at the
    barrier's validation, so this only ever governs text no decision reads."""
    return {f.name.lower(): f.value.strip() for f in iter_fields(entry_text)}


# Whitespace only, so the comma may sit on the next line.
_TRAILING_COMMA_RE = re.compile(r"\s*,")


def remove_field(text: str, field: Field) -> str:
    """`text` with `field` cut out: the field, its trailing comma (even on
    the next line), and -- when it had a line to itself -- that line's
    leading whitespace and newline.
    A field sharing a line loses only itself. The comma of the field BEFORE
    it is left alone: BibTeX accepts a trailing comma before the closing
    brace, so the result stays parseable either way."""
    start = field.name_start
    while start > 0 and text[start - 1] in " \t":
        start -= 1
    if start > 0 and text[start - 1] == "\n":
        start -= 1
        if start > 0 and text[start - 1] == "\r":
            start -= 1
    end = field.value_end
    m = _TRAILING_COMMA_RE.match(text, end)
    if m:
        end = m.end()
    return text[:start] + text[end:]
