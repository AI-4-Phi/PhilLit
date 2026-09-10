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
  entries and the declaration rides along unused. The next-`@` rule is the
  comment's ALONE: a `@string` value and a `@preamble` are read whole,
  braces or quotes deciding their extent, so `@string{j = "Journal @
  Large"}` is valid and nothing here loses it - and an UNCLOSED one is a
  syntax error at end of file - or, closed by a later `}`, it SWALLOWS the
  entries between (`@string{j = {x` + an entry + `}}` parses to zero
  entries, so the rewrite would drop them while dedupe still reads them),
  which is why an unbalanced `@string`/`@preamble` chunk is reported. Only
  `@comment` chunks are scanned for intrusions, and only an unbalanced
  `@comment` attributes the stray text that follows it. An ENTRY-shaped
  command after a closed `@string`/`@preamble` in the same chunk is a
  misplaced command (pybtex reads it; the tools carry it as block text, so
  the cleaner would render it twice and dedupe gives it no identity); a
  further verbatim command there is carried whole and is not reported, and
  a bare `@` in trailing words is pybtex's own syntax error, not ours.
- A UTF-8 BOM, or indentation, before the FIRST command: pybtex skips it,
  dedupe matches its header regex against the raw chunk and DROPS that
  entry (measured 2026-09-10), so it is reported as a misplaced command. A
  BOM before a verbatim block is tolerated by `is_verbatim_block` (dedupe's
  own predicate), so the block is carried and nothing is lost.

Every splitter here chunks a file at a COLUMN-0 `@` (`re.split(r"\\n(?=@)")`),
so that is what "line start" means throughout. What the tools then read as
an ENTRY is the header `@type{key,` at column 0 - `\\w+` type, `{`, a key
with no whitespace, then `,` - because that is the grammar dedupe (which DROPS a chunk
without it, with only a stderr warning), evidence stamping (which MISSES an
entry with a space before its key) and the field scanner share; pybtex is
wider (a hyphenated type, a `(`-delimited entry, a zero-field `@type{key}`
with no comma, a space after the type or before the key), so a
column-0 command without that header is reported by name here rather than
taught to every tool: `stray_text` reads it as a header defect, never as a
command out of position. Zero such headers over 9,579 chunks in 335 local
bibs. A rewrite keeps exactly two things: verbatim chunks whole (moved
ahead of the entries, as they always were), and the entries pybtex parsed,
re-rendered. Everything else is dropped without a word - a `%%` divider
between entries, a doubled `}`, the tail of a block a column-0 `@` ended.
Downstream agents read a domain bib as TEXT, so all of that is content to
them whatever pybtex thinks; `stray_text` accounts for it, and refusing a
metadata rewrite until it is moved or deleted is the price of never losing
it silently. An `@` command that does not start its line (indented, or
concatenated after another command) is reported for a different reason:
pybtex reads it, no splitter here does, so dedupe and evidence stamping
fold it into the entry before it - misattribution rather than loss for an
entry (no identity of its own, no year check, no stamp), loss for a comment
the rewrite then drops. Measured over 335 local bibs (558 blocks): 10 spots
in 5 files of 3 reviews - `%%` section dividers, a doubled `}`, a bare
`@comment only` in a block - all text the rewrite was already dropping.

The one residual is a field VALUE whose line starts at column 0 with
`@word{`: a chunk to every tool (carried out as a block, or read as an
entry whose tail is then stray) while pybtex parses the entry whole; zero
incidence, not guarded, and its report reads as stray text rather than
naming the cause.
"""
import re
from typing import NamedTuple

# A UTF-8 BOM (which `\s` does not match) is leading whitespace here.
_VERBATIM_RE = re.compile(r"[\s\ufeff]*@(comment|string|preamble)\s*([{(])", re.IGNORECASE)
_NEXT_CHUNK_RE = re.compile(r"\n(?=@)")
# The entry header every tool here reads (the intersection of dedupe's
# `@(\w+)\{([^,]+),`, stamp_evidence's `@(\w+)\s*\{([^,\s]+)\s*,` and
# bib_fields' `_HEADER_RE`): a chunk pybtex reads as an entry but this does
# not match is a header defect to report, since dedupe drops it. Anchored
# at the chunk's first character on purpose: dedupe matches the raw chunk,
# so a BOM or indentation before the FIRST entry of a file drops that entry
# (measured 2026-09-10) - that is a misplaced command, not a header.
_ENTRY_HEADER_RE = re.compile(r"@\w+(\{)[^,\s]+\s*,")
_LEAD_RE = re.compile(r"[\s\ufeff]*")
# A command as pybtex reads one: `@`, an identifier, `{` or `(`. A run that
# opens with `@` but is not command-shaped (`@ 3pm`, `foo@bar.org`) is
# either stray text or pybtex's own syntax error, never a misplaced command.
_COMMAND_RE = re.compile(r"""@([^\s"#%'(),={}@]+)\s*([{(])""")
_VERBATIM_WORDS = frozenset({"comment", "string", "preamble"})
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
    """An `@` inside a `@comment` chunk, after its command: pybtex ends the
    block there. Comment blocks only - a `@string` value or a `@preamble`
    is read whole, so an `@` inside one is ordinary text."""
    open_line: int  # 1-based line of the block's `@comment{`
    line: int       # 1-based line of the intruding `@`
    word: str       # the identifier after it ("" for a lone `@`)
    offset: int     # index of the `@` in the text

    def describe(self) -> str:
        return (f"line {self.line}: `@{self.word}` inside the @comment block opened on "
                f"line {self.open_line} - BibTeX ends the block at the first such `@` and reads on "
                f"from there as a new command (a braced `@word{{...}}` becomes an entry "
                f"and the rest of the block is dropped; a bare `@word` is a syntax "
                f"error; a nested `@comment{{` starts a second block); remove the `@` "
                f"or move the text out of the block")


def comment_body_intrusions(text: str) -> list[Intrusion]:
    """Every `@` inside a `@comment` chunk after the command that opens it,
    in order. This is pybtex's own rule - a comment runs to the next `@`,
    braces notwithstanding - so nothing here depends on the block's braces
    balancing. It is the comment's rule alone: `@string` and `@preamble`
    chunks are read whole by pybtex and are not scanned. A column-0 `@`
    inside a block is a chunk of its own to every tool here and an entry to
    pybtex, so it is not an intrusion: whatever pybtex drops after it is
    `stray_text`'s to report, which names it."""
    hits = []
    for offset, chunk in _chunks(text):
        m = _VERBATIM_RE.match(chunk)
        if not m or m.group(1).lower() != "comment":
            continue
        open_line = _line(text, offset + m.start(1) - 1)
        i = m.end()
        while i < len(chunk):
            if chunk[i] == "@":
                word = _WORD_RE.match(chunk, i + 1).group()
                hits.append(Intrusion(open_line, _line(text, offset + i), word, offset + i))
            i += 1
    return hits


class Stray(NamedTuple):
    """Text the column-0 tools do not account for: outside every verbatim
    chunk and outside the entry its chunk opens."""
    line: int      # 1-based line where the run of text begins
    snippet: str   # that line's text, trimmed
    offset: int    # index in the text where the run begins
    # "text": a run outside every block and entry; "misplaced": a command
    # that does not start its line; "header": a column-0 command whose
    # header no tool here reads as an entry; "unclosed": a @string or
    # @preamble that never balances within its chunk.
    kind: str = "text"
    # (block open line, intruder line, intruder word) when the chunk right
    # before this one is a `@comment` block that never balanced - the `@`
    # that opens this chunk is what ended the block for pybtex.
    after: tuple[int, int, str] | None = None
    bom: bool = False  # a UTF-8 BOM is what put the command off column 0

    def describe(self) -> str:
        if self.kind == "misplaced":
            remedy = ("remove the byte-order mark and any indentation before it" if self.bom
                      else "move it to the start of a line")
            if self.after:
                open_line, at_line, word = self.after
                remedy = (f"it also sits where BibTeX ends the @comment opened on line "
                          f"{open_line} (a comment runs to the next `@`): remove the `@` if "
                          f"this is comment text, or {remedy} if it is an entry")
            return (f"line {self.line}: {self.snippet!r} - an `@` command must start at the "
                    f"beginning of its line: every tool here reads the file in column-0 "
                    f"chunks, so this one is carried inside the chunk before it - an entry "
                    f"there has no identity of its own in dedupe or evidence stamping (and "
                    f"inside a carried @string/@preamble chunk the cleaner would render it a "
                    f"second time), a comment there would not survive a metadata rewrite - "
                    f"or dropped when it is the first chunk; {remedy}")
        if self.kind == "header":
            remedy = "rewrite the header"
            if self.after:
                open_line, at_line, word = self.after
                remedy = (f"and the `@{word}` on line {at_line} is where BibTeX ends the "
                          f"@comment block opened on line {open_line} (a comment runs to the "
                          f"next `@`): remove the `@` if this is comment text, or rewrite the "
                          f"header if it is an entry")
            return (f"line {self.line}: {self.snippet!r} - an entry header must read "
                    f"`@type{{key,`: a word type, `{{`, the key and `,`, with no space after "
                    f"the type or before the key. That is the one header dedupe, evidence "
                    f"stamping and the field scanner all read; outside it dedupe drops the "
                    f"chunk with only a warning (a `(`-delimited entry, a hyphenated type, a "
                    f"key with no `,` after it, a space before `{{`) or evidence stamping "
                    f"misses it (a space before the key); {remedy}")
        if self.kind == "unclosed":
            return (f"line {self.line}: {self.snippet!r} - this block never closes within "
                    f"its chunk: BibTeX reads the entries that follow as part of its value "
                    f"until a later closer (they vanish from the parse and from a metadata "
                    f"rewrite, while dedupe still reads them as entries) or fails at end of "
                    f"file; close it")
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
    with no `@type{key,` header (text before the first command) is reported
    whole - as a header defect when it opens with `@` at column 0, since
    that is a command dedupe would drop; an entry chunk whose entry never
    balances is treated as all entry (pybtex will refuse it anyway). A
    command-shaped run (`@word{` or `@word(`) anywhere else - after an
    entry, after a closed `@string`/`@preamble`, or after indentation or a
    BOM at the top of the file - is a command that does not start its line,
    which pybtex reads and no splitter here does (dedupe drops a first
    entry so placed); a `@` that is not command-shaped is plain stray text.
    A `@string`/`@preamble` that never balances is reported as such."""
    strays = []
    open_block = None  # open line of an unbalanced `@comment` chunk just seen
    for offset, chunk in _chunks(text):
        m = _VERBATIM_RE.match(chunk)
        if m:
            end = _balanced_end(chunk, m.end() - 1, m.group(2))
            open_at = offset + m.start(1) - 1
            if m.group(1).lower() == "comment":
                # Only a comment runs to the next `@` (any `@` after the
                # command is the intrusion scan's); an unbalanced one ends
                # at the next chunk's `@`, which attributes its stray tail.
                open_block = _line(text, open_at) if end is None else None
                continue
            open_block = None
            if end is None:
                # pybtex reads on into the following entries as the value
                # (or fails at end of file); the column-0 tools read them
                # as entries. Reported, since a later `}` can close it.
                snippet = chunk[m.start(1) - 1:].splitlines()[0].strip()[:80]
                strays.append(Stray(_line(text, open_at), snippet, open_at, "unclosed"))
                continue
            # After the closer pybtex skips plain words (carried with the
            # chunk, nothing lost) and reads commands. A further verbatim
            # command is carried too; an entry-shaped one is read by pybtex
            # and by no splitter here - the cleaner would render it twice.
            pos = end
            comment_line = None  # a @comment passed in this tail: the entry after it may be its prose
            while (c := _COMMAND_RE.search(chunk, pos)) is not None:
                word = c.group(1).lower()
                at = offset + c.start()
                snippet = chunk[c.start():].splitlines()[0].strip()[:80]
                if word == "comment":
                    comment_line = _line(text, at)
                    pos = c.end()  # runs to the next `@`, whatever follows
                    continue
                if word in _VERBATIM_WORDS:
                    nxt = _balanced_end(chunk, c.end() - 1, c.group(2))
                    if nxt is None:
                        # The same swallowing hazard as a primary one.
                        strays.append(Stray(_line(text, at), snippet, at, "unclosed"))
                        break
                    pos = nxt
                    continue
                after = (comment_line, _line(text, at), word) if comment_line else None
                strays.append(Stray(_line(text, at), snippet, at, "misplaced", after))
                break
            continue
        header = _ENTRY_HEADER_RE.match(chunk)
        if header:
            end = _balanced_end(chunk, header.start(1), "{")
            if end is None:
                open_block = None
                continue
        else:
            end = 0
        tail = chunk[end:]
        lead = _LEAD_RE.match(tail).end()  # whitespace or a BOM, which lstrip keeps
        stripped = tail[lead:]
        if stripped:
            at = offset + end + lead
            kind = "text"
            if _COMMAND_RE.match(stripped):
                # After an entry, or after whitespace/BOM at the top of the
                # file: not at column 0. At column 0 with no header: the
                # header is what dedupe cannot read.
                kind = "misplaced" if header or lead else "header"
            after = None
            if open_block is not None and kind != "misplaced":
                # This chunk's column-0 `@` ended the unbalanced comment.
                at_word = _WORD_RE.match(chunk, chunk.index("@") + 1)
                after = (open_block, _line(text, offset), at_word.group())
            strays.append(Stray(_line(text, at), stripped.splitlines()[0].strip()[:80], at,
                                kind, after, "\ufeff" in tail[:lead]))
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
