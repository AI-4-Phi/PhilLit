"""The `@comment` block grammar of raw BibTeX text - the one owner.

Not a hook. A `re`-only leaf so that `bib_validator`, `metadata_cleaner` and
`dedupe_bib` decide "is this a block to carry" and "would a rewrite lose
text" the same way. The pybtex facts that drive it (all measured 2026-09-10):

- The comment COMMAND is `@comment`, in any case, optionally followed by
  whitespace, then `{` or `(`. An entry TYPE that merely begins with
  "comment" (`@commentary{k1, ...}`) is an ordinary entry; a
  `startswith("@comment")` test carried one over as a comment block AND
  rendered it as an entry, so the rewritten file no longer parsed.
- A comment BODY runs to the NEXT `@`, whatever the braces say - a `}` in
  the overview does not close it, an extra `{` does not keep it open. So a
  braced `@word{...}` inside a `@comment{}` block is parsed as a second
  entry, and the rest of the block - the overview tail the synthesis planner
  reads - is silently dropped; a rewrite through pybtex makes that loss
  permanent. A bare `@word` (no brace) in a body is refused by pybtex
  outright, so it already fails syntax validation; `comment_body_intrusions`
  reports it too, naming the cause. `%` means nothing to pybtex anywhere (a
  `% @word` line in a body is refused like any bare `@`). A UTF-8 BOM is
  skipped like any text before the first `@`. Braces are structural even
  after a backslash, as in BibTeX; in a `(`-delimited command a paren
  inside braces or a `"`-quoted value is literal.
- `@string` and `@preamble` are dropped by pybtex's Writer exactly as
  `@comment` is, so the cleaner carries all three verbatim
  (`is_verbatim_block`, the one test for "is this chunk a block to carry",
  which dedupe binds too); a `@string` macro is expanded into the rendered
  entries and the declaration rides along unused.

Every splitter here chunks a file at a COLUMN-0 `@` (`re.split(r"\\n(?=@)")`),
so that is what "line start" means throughout - and it is the one residual:
a field VALUE whose line starts at column 0 with `@word{` is a chunk to
every tool (carried out as a block, or read as an entry whose tail is then
stray) while pybtex parses the entry whole; zero incidence, not guarded,
and its report reads as stray text rather than naming the cause. A rewrite
keeps exactly two things: verbatim chunks whole (moved ahead of the
entries, as they always were), and the entries pybtex parsed, re-rendered.
Everything else is dropped without a word - a `%%` divider between
entries, a doubled `}`, the tail of a block a column-0 `@` ended. Downstream
agents read a domain bib as TEXT, so all of that is content to them
whatever pybtex thinks; `stray_text` accounts for it, and refusing a
metadata rewrite until it is moved or deleted is the price of never losing
it silently. An `@` command that does not start its line (indented, or
concatenated after another command) is reported the same way for a
different reason: pybtex reads it, no splitter here does. Measured over 335
local bibs (558 blocks): 10 spots in 5 files of 3 reviews - `%%` section
dividers, a doubled `}`, a bare `@comment only` in a block - all text the
rewrite was already dropping.
"""
import re
from typing import NamedTuple

# A UTF-8 BOM (which `\s` does not match) is leading whitespace here.
_VERBATIM_RE = re.compile(r"[\s﻿]*@(comment|string|preamble)\s*([{(])", re.IGNORECASE)
_NEXT_CHUNK_RE = re.compile(r"\n(?=@)")
# `\w+` for the type name is the header grammar every other tool here uses
# (bib_fields, dedupe, the validator); pybtex would also accept `@my-type{`,
# which therefore surfaces as stray text rather than being dropped by dedupe.
_CHUNK_HEADER_RE = re.compile(r"[\s﻿]*@\w+\s*([{(])")
# BibTeX identifier characters (same alphabet as bib_fields._NAME_RE, minus
# `@` so that `@@foo` is two intrusions); may match empty, for a lone `@`.
_WORD_RE = re.compile(r"""[^\s"#%'(),={}@]*""")
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


def _line(text: str, at: int) -> int:
    return text.count("\n", 0, at) + 1


def _balanced_end(text: str, start: int, opener: str) -> int | None:
    """Index just past the delimiter that balances `text[start]` (== opener),
    or None if the text ends first. Braces are always structural (BibTeX
    counts every one, backslash or not). For a `(`-delimited command a
    paren counts only outside braces and outside a `"`-quoted value, where
    BibTeX reads it as literal text."""
    if opener == "{":
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        return None
    braces = parens = 0
    quoted = False
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            braces += 1
        elif c == "}":
            braces -= 1
        elif braces == 0:
            if c == '"':
                quoted = not quoted
            elif not quoted:
                if c == "(":
                    parens += 1
                elif c == ")":
                    parens -= 1
                    if parens == 0:
                        return i + 1
    return None


class Intrusion(NamedTuple):
    """An `@` inside a verbatim chunk, after its command: pybtex ends the
    block there."""
    open_line: int  # 1-based line of the block's `@comment{`
    line: int       # 1-based line of the intruding `@`
    word: str       # the identifier after it ("" for a lone `@`)
    offset: int     # index of the `@` in the text
    block: str = "comment"  # the command that opened the chunk

    def describe(self) -> str:
        return (f"line {self.line}: `@{self.word}` inside the @{self.block} block opened on "
                f"line {self.open_line} - BibTeX ends the block at that `@` and reads on "
                f"from there as a new command (a braced `@word{{...}}` becomes an entry "
                f"and the rest of the block is dropped; a bare `@word` is a syntax "
                f"error; a nested `@comment{{` starts a second block); remove the `@` "
                f"or move the text out of the block")


def comment_body_intrusions(text: str) -> list[Intrusion]:
    """Every `@` inside a verbatim chunk after the command that opens it, in
    order. This is pybtex's own rule - a comment runs to the next `@`,
    braces notwithstanding - so nothing here depends on the block's braces
    balancing. A column-0 `@` inside a block is a chunk of its own to every
    tool here and an entry to pybtex, so it is not an intrusion: whatever
    pybtex drops after it is `stray_text`'s to report, which names it."""
    hits = []
    for offset, chunk in _chunks(text):
        m = _VERBATIM_RE.match(chunk)
        if not m:
            continue
        open_line = _line(text, offset + m.start(1) - 1)
        block = m.group(1).lower()
        i = m.end()
        while i < len(chunk):
            if chunk[i] == "@":
                word = _WORD_RE.match(chunk, i + 1).group()
                hits.append(Intrusion(open_line, _line(text, offset + i), word, offset + i, block))
            i += 1
    return hits


class Stray(NamedTuple):
    """Text the column-0 tools do not account for: outside every verbatim
    chunk and outside the entry its chunk opens."""
    line: int      # 1-based line where the run of text begins
    snippet: str   # that line's text, trimmed
    offset: int    # index in the text where the run begins
    # (block open line, intruder line, intruder word) when the chunk right
    # before this one is a verbatim block that never balanced - the `@` that
    # opens this chunk is what ended the block for pybtex.
    after: tuple[int, int, str] | None = None

    def describe(self) -> str:
        if self.snippet.startswith("@"):
            return (f"line {self.line}: {self.snippet!r} - an `@` command must start at the "
                    f"beginning of its line: every tool here reads the file in column-0 "
                    f"chunks, so dedupe and evidence stamping would fold this one into the "
                    f"entry before it, and a comment there would not survive a metadata "
                    f"rewrite; move it to the start of a line")
        cause = ""
        if self.after:
            open_line, at_line, word = self.after
            cause = (f" - the `@{word}` on line {at_line} ended the @comment block opened on "
                     f"line {open_line} (BibTeX ends a comment at the next `@`, braces "
                     f"notwithstanding), so this text is outside it")
        return (f"line {self.line}: text outside any entry or @comment block, which a "
                f"metadata rewrite drops: {self.snippet!r}{cause}; move it into the "
                f"@comment block or delete it")


def stray_text(text: str) -> list[Stray]:
    """The runs of non-whitespace text that neither sit in a verbatim chunk
    nor inside the entry their chunk opens, one report per chunk. A chunk
    with no `@type{` header at all (text before the first command) is
    reported whole; an entry chunk whose entry never balances is treated as
    all entry (pybtex will refuse it anyway). A run that begins with `@` is
    a command that does not start its line - indented, or concatenated after
    another command - which pybtex reads and no splitter here does."""
    strays = []
    open_block = None  # (open line, ...) of an unbalanced verbatim chunk just seen
    for offset, chunk in _chunks(text):
        m = _VERBATIM_RE.match(chunk)
        if m:
            balanced = _balanced_end(chunk, m.end() - 1, m.group(2)) is not None
            open_block = None if balanced else _line(text, offset + m.start(1) - 1)
            continue
        header = _CHUNK_HEADER_RE.match(chunk)
        if header:
            end = _balanced_end(chunk, header.end() - 1, header.group(1))
            if end is None:
                open_block = None
                continue
        else:
            end = 0
        tail = chunk[end:]
        stripped = tail.lstrip()
        if stripped:
            at = offset + end + (len(tail) - len(stripped))
            after = None
            if open_block is not None and header:
                at_word = _WORD_RE.match(chunk, header.start() + len(header.group()) - len(header.group().lstrip()) + 1)
                after = (open_block, _line(text, offset), at_word.group() if at_word else "")
            strays.append(Stray(_line(text, at), stripped.splitlines()[0].strip()[:80], at, after))
        open_block = None
    return strays


def comment_defects(text: str) -> list[str]:
    """Every reason a rewrite of `text` would not carry it whole, as
    researcher-facing messages in source order: the intrusions into
    verbatim chunks and the stray text. The validator's check 4c and the
    cleaner's preflight are the same list."""
    found = [(hit.offset, hit.describe()) for hit in comment_body_intrusions(text)]
    found += [(stray.offset, stray.describe()) for stray in stray_text(text)]
    return [msg for _, msg in sorted(found, key=lambda pair: pair[0])]
