"""The `@comment` block grammar of raw BibTeX text - the one owner.

Not a hook. A `re`-only leaf so that `bib_validator`, `metadata_cleaner` and
`dedupe_bib` decide "is this a block to carry" and "would a rewrite lose
text" the same way. The pybtex facts that drive it (all measured 2026-09-10):

- The comment COMMAND is `@comment`, in any case, optionally followed by
  whitespace, then `{` or `(`. An entry TYPE that merely begins with
  "comment" (`@commentary{k1, ...}`) is an ordinary entry; a
  `startswith("@comment")` test carried one over as a comment block AND
  rendered it as an entry, so the rewritten file no longer parsed.
- A comment BODY runs to the NEXT `@`, whatever the braces say. So a braced
  `@word{...}` inside a `@comment{}` block is parsed as a second entry, and
  the rest of the block - the overview tail the synthesis planner reads -
  is silently dropped; a rewrite through pybtex makes that loss permanent.
  A bare `@word` (no brace) in a body is refused by pybtex outright, so it
  already fails syntax validation; `comment_body_intrusions` reports it too,
  naming the cause. `%` means nothing to pybtex anywhere (a `% @word` line
  in a body is refused like any bare `@`), and braces are structural even
  after a backslash, as in BibTeX itself.
- `@string` and `@preamble` are dropped by pybtex's Writer exactly as
  `@comment` is, so the cleaner carries all three verbatim
  (`is_verbatim_block`, the one test for "is this chunk a block to carry",
  which dedupe binds too); a `@string` macro is expanded into the rendered
  entries and the declaration rides along unused.

Every splitter here chunks a file at a COLUMN-0 `@` (`re.split(r"\\n(?=@)")`),
so that is what "line start" means throughout. A rewrite keeps exactly two
things: verbatim chunks whole, and the entries pybtex parsed, re-rendered.
Everything else is dropped without a word - a `%%` divider between entries,
a doubled `}`, an indented `@comment{` (a comment to pybtex, a chunk to no
splitter), the tail of a block pybtex ended early. Downstream agents read a
domain bib as TEXT, so all of that is content to them whatever pybtex
thinks; `stray_text` accounts for it, and refusing a metadata rewrite until
it is moved or deleted is the price of never losing it silently. Measured
over 335 local bibs: 3 bibs carry such text (`%%` dividers in one, a
doubled `}` in one, a bare `@comment only` in a block in one).
"""
import re
from typing import NamedTuple

_VERBATIM_RE = re.compile(r"\s*@(?:comment|string|preamble)\s*[{(]", re.IGNORECASE)
_BLOCK_OPENER_RE = re.compile(r"^@comment\s*([{(])", re.IGNORECASE | re.MULTILINE)
_NEXT_CHUNK_RE = re.compile(r"\n(?=@)")
_CHUNK_HEADER_RE = re.compile(r"\s*@\w+\s*([{(])")
# BibTeX identifier characters (same alphabet as bib_fields._NAME_RE); may
# match empty, for a lone `@`.
_WORD_RE = re.compile(r"""[^\s"#%'(),={}]*""")
_CLOSER = {"{": "}", "(": ")"}


def is_verbatim_block(chunk: str) -> bool:
    """True if `chunk` - a `\\n(?=@)`-split piece of a bib file - opens a
    block to carry verbatim because pybtex's Writer drops it: `@comment`,
    `@string` or `@preamble`. Leading whitespace is tolerated (the first
    chunk); an entry type that merely begins with one of the words is not."""
    return _VERBATIM_RE.match(chunk) is not None


def _chunks(text: str):
    """(offset, chunk) for every `\\n(?=@)`-split chunk of `text`."""
    bounds = [0] + [m.start() + 1 for m in _NEXT_CHUNK_RE.finditer(text)] + [len(text)]
    for start, stop in zip(bounds, bounds[1:]):
        yield start, text[start:stop]


def _balanced_end(text: str, start: int, opener: str) -> int | None:
    """Index just past the delimiter that balances `text[start]` (== opener),
    or None if the text ends first."""
    closer = _CLOSER[opener]
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i + 1
    return None


class Intrusion(NamedTuple):
    """An `@` inside a brace-closed `@comment` block."""
    open_line: int  # 1-based line of the block's `@comment{`
    line: int       # 1-based line of the intruding `@`
    word: str       # the identifier after it ("" for a lone `@`)

    def describe(self) -> str:
        return (f"line {self.line}: `@{self.word}` inside the @comment block opened on "
                f"line {self.open_line} - BibTeX ends the block at that `@` and reads on "
                f"from there as a new command (a braced `@word{{...}}` becomes an entry "
                f"and the rest of the block is dropped; a bare `@word` is a syntax "
                f"error; a nested `@comment{{` starts a second block); remove the `@` "
                f"or move the text out of the block")


def comment_body_intrusions(text: str) -> list[Intrusion]:
    """Every `@` inside a column-0 `@comment{...}` / `@comment(...)` block
    whose opening delimiter is balanced, in order, each once.

    Inside a balanced block the researcher's intended extent is known, so
    every `@` there breaks the spec's ban - it ends the block for pybtex
    and, braced, promotes what follows to an entry, even when no text is
    lost. A block that never balances (an extra `{` in the overview; pybtex
    still ends it at the next `@`, and the cleaner carries it as is) is not
    judged: whether the `@` that follows is "inside" is undecidable from the
    text, and whatever pybtex would drop there is `stray_text`'s to report.
    A stray `}` after the entry that follows an unbalanced block can make
    the block balance late and put that entry inside it; `stray_text`
    reports the brace alongside.
    """
    hits: dict[int, Intrusion] = {}
    for m in _BLOCK_OPENER_RE.finditer(text):
        end = _balanced_end(text, m.end() - 1, m.group(1))
        if end is None:
            continue
        open_line = text.count("\n", 0, m.start()) + 1
        for i in range(m.end(), end):
            if text[i] == "@":
                word = _WORD_RE.match(text, i + 1).group()
                hits.setdefault(i, Intrusion(open_line, text.count("\n", 0, i) + 1, word))
    return [hits[pos] for pos in sorted(hits)]


class Stray(NamedTuple):
    """Text a metadata rewrite would drop: outside every verbatim chunk and
    outside the entry its chunk opens."""
    line: int      # 1-based line where the run of text begins
    snippet: str   # that line's text, trimmed

    def describe(self) -> str:
        return (f"line {self.line}: text outside any entry or @comment block, which a "
                f"metadata rewrite drops: {self.snippet!r} - move it into the @comment "
                f"block or delete it (every `@` command starts at the beginning of its "
                f"line)")


def stray_text(text: str) -> list[Stray]:
    """The runs of non-whitespace text that neither sit in a verbatim chunk
    nor inside the entry their chunk opens, one report per chunk. A chunk
    with no `@type{` header at all (text before the first command) is
    reported whole; an entry chunk whose entry never balances is treated as
    all entry (pybtex will refuse it anyway)."""
    strays = []
    for offset, chunk in _chunks(text):
        if is_verbatim_block(chunk):
            continue
        header = _CHUNK_HEADER_RE.match(chunk)
        if header:
            end = _balanced_end(chunk, header.end() - 1, header.group(1))
            if end is None:
                continue
        else:
            end = 0
        tail = chunk[end:]
        stripped = tail.lstrip()
        if not stripped:
            continue
        at = offset + end + (len(tail) - len(stripped))
        line = text.count("\n", 0, at) + 1
        strays.append(Stray(line, stripped.splitlines()[0].strip()[:80]))
    return strays


def _balanced_block_line_spans(text: str) -> list[tuple[int, int]]:
    """(first line, last line) of every column-0 comment block that balances."""
    spans = []
    for m in _BLOCK_OPENER_RE.finditer(text):
        end = _balanced_end(text, m.end() - 1, m.group(1))
        if end is not None:
            spans.append((text.count("\n", 0, m.start()) + 1, text.count("\n", 0, end) + 1))
    return spans


def comment_defects(text: str) -> list[str]:
    """Every reason a rewrite of `text` would not carry it whole, as
    researcher-facing messages in line order: the intrusions into balanced
    blocks and the stray text. Stray text that lies inside a balanced block
    is the tail an intrusion there already accounts for, so it is not
    reported twice. The validator's check 4c and the cleaner's preflight are
    the same list."""
    spans = _balanced_block_line_spans(text)
    found = [(hit.line, hit.describe()) for hit in comment_body_intrusions(text)]
    found += [(stray.line, stray.describe()) for stray in stray_text(text)
              if not any(first <= stray.line <= last for first, last in spans)]
    return [msg for _, msg in sorted(found)]
