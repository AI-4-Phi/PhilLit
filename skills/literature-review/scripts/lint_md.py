#!/usr/bin/env python3
"""
Minimal markdown linter for Claude Code.
Checks markdown files against specific pymarkdownlnt rules.
"""
import re
import subprocess
import sys
from pathlib import Path

# Rule explanations for helpful error messages
RULE_EXPLANATIONS = {
    "MD001": "Heading levels should increment by one (don't skip from # to ###)",
    "MD003": "Heading style should be consistent (use ATX style: # Heading)",
    "MD004": "Unordered list style should be consistent (use - for bullets)",
    "MD005": "List items should have consistent indentation",
    "MD007": "Unordered list indentation should be consistent (2 spaces per level)",
    "MD018": "ATX headings need a space after the hash (# Heading, not #Heading)",
    "MD019": "ATX headings should have only one space after hash",
    "MD020": "Closed ATX headings need space inside (# Heading #)",
    "MD021": "Closed ATX headings should have only one space inside",
    "MD022": "Headings need blank lines above and below",
    "MD023": "Headings must start at the beginning of the line",
    "MD028": "Blockquotes should not have blank lines inside",
    "MD029": "Ordered list prefixes should be consistent",
    "MD031": "Fenced code blocks need blank lines above and below",
    "MD032": "Lists need blank lines above and below",
    "MD037": "Emphasis markers should not have spaces inside (*text*, not * text *)",
    "MD056": "Table rows should have consistent column count",
    "MD058": "Tables need blank lines above and below",
}

# Extensions to enable (front-matter handles YAML frontmatter in literature reviews)
ENABLED_EXTENSIONS = ["front-matter"]

# Rules enabled by default in pymarkdownlnt that we want to disable
# (not relevant for literature reviews - e.g., line length, trailing spaces)
DISABLED_RULES = [
    "MD009",  # No trailing spaces
    "MD010",  # No hard tabs
    "MD011",  # No reversed links
    "MD012",  # No multiple blanks
    "MD013",  # Line length
    "MD014",  # Commands show output
    "MD024",  # No duplicate heading
    "MD025",  # Single title/h1
    "MD026",  # No trailing punctuation in heading
    "MD027",  # Multiple spaces after blockquote
    "MD030",  # Spaces after list markers
    "MD033",  # No inline HTML
    "MD034",  # No bare URLs
    "MD035",  # Horizontal rule style
    "MD036",  # No emphasis as heading
    "MD038",  # Spaces inside code span
    "MD039",  # Spaces inside link text
    "MD040",  # Fenced code language
    "MD041",  # First line heading
    "MD042",  # No empty links
    "MD043",  # Required heading structure
    "MD044",  # Proper names capitalization
    "MD045",  # Images should have alt text
    "MD046",  # Code block style
    "MD047",  # Files should end with newline
    "MD048",  # Code fence style
]


def lint_markdown(filepath: str) -> int:
    """Lint a markdown file and output errors with explanations."""
    disabled_str = ",".join(DISABLED_RULES)
    extensions_str = ",".join(ENABLED_EXTENSIONS)

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pymarkdown",
                "--enable-extensions", extensions_str,
                "--disable-rules", disabled_str,
                "scan", filepath
            ],
            capture_output=True,
            text=True,
        )

        # Process output to add explanations
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                print(line)
                # Extract rule code from pymarkdown output format: "file:line:col: MDXXX: message"
                match = re.search(r': (MD\d{3}):', line)
                if match:
                    code = match.group(1)
                    if code in RULE_EXPLANATIONS:
                        print(f"  -> Fix: {RULE_EXPLANATIONS[code]}")

        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        return result.returncode

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# --- Prose-quality heuristics (roadmap item 13, B5) -------------------------
# WARN-level advisory checks surfaced at Phase 6. They NEVER affect the exit
# code: false positives cost nothing, so the patterns stay simple and err
# toward noticing rather than silence.

# Annotation phrases that leak into citation parentheses (item 13 §4.2): a
# citation parenthesis carrying any of these is an improvised process note
# that loses its margin-apparatus anchor at render.
_ANNOTATION_PHRASES = (
    "non-peer-reviewed",
    "working paper",
    "classic text",
    "cited via",
    # "primary policy source" observed verbatim in the 2026-07-17 production
    # artifact ("(Article 36 2013; a non-peer-reviewed primary policy source)")
    # — an evidence-grounded phrase, not an invention.
    "primary policy source",
)

# A parenthesis and its (non-nested) contents.
_PAREN_RE = re.compile(r"\(([^()]*)\)")

# In-prose "Section 3" / "Section 3.3" cross-reference tokens. Display-time
# renumbering makes these off-by-one; cross-reference by title instead.
_INPROSE_SECTION_RE = re.compile(r"\bSection\s+\d+(?:\.\d+)?\b")

# An H2 heading ending in a parenthesized Title-Case meta-label, e.g.
# "## Section 1: Foo (Core Analytical Section)". Requires >=2 Title-Case
# words so "(2020-2025)" and single ordinary words do not match.
_H2_META_LABEL_RE = re.compile(
    r"^\s*##\s+.*\(([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+)\)\s*$"
)


def check_prose_quality(text: str) -> list[str]:
    """Return WARN-level advisories about prose-quality issues (item 13 §4.2).

    Heuristic, WARN-only — the caller must never let these affect the exit
    code. Detects: (1) citation parentheses carrying process annotations,
    (2) in-prose "Section N(.M)" cross-references, (3) H2 headings ending in a
    parenthesized Title-Case meta-label. Fenced code blocks and heading lines
    are exempt from the prose checks.
    """
    warnings: list[str] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if stripped.startswith("#"):
            m = _H2_META_LABEL_RE.match(line)
            if m:
                warnings.append(
                    f"line {lineno}: H2 heading ends in a parenthesized "
                    f"meta-label '({m.group(1)})' - section titles should be "
                    f"reader-facing (WARN)"
                )
            # Headings are exempt from the prose checks below.
            continue

        for content in _PAREN_RE.findall(line):
            low = content.lower()
            for phrase in _ANNOTATION_PHRASES:
                if phrase in low:
                    warnings.append(
                        f"line {lineno}: citation parenthesis contains the "
                        f"annotation '{phrase}' - put source qualifiers in "
                        f"prose, outside the parenthesis (WARN)"
                    )
                    break

        for m in _INPROSE_SECTION_RE.finditer(line):
            warnings.append(
                f"line {lineno}: in-prose cross-reference '{m.group(0)}' - "
                f"cross-reference sections by title, not number (display "
                f"renumbering makes numbers off-by-one) (WARN)"
            )
    return warnings


# --- Every-citation-resolves check (ROADMAP item 3 B) ------------------------
# ERROR-level: a cited work missing from the rendered References is the one
# defect a reader cannot detect and the pipeline used to swallow silently
# (observed: an anchor study cited seven times, absent from References).

# A citation year: 1600s-2000s (philosophy cites Kant 1785 - review 4b)
# plus an optional Chicago a/b suffix; a reprint form YEAR/YEAR resolves on
# either year.
_YEAR = r"(?:1[6-9]|20)\d{2}[a-z]?"
# A surname token: capitalized, may carry diacritics, hyphens, apostrophes.
_SURNAME = r"[A-ZÀ-Þ][\w'’À-ÿ-]+"
# Parenthetical citation: surname tokens (with "and"/"&"/commas/"et al."),
# then the year (optionally YEAR/YEAR). The trailing lookahead deliberately
# skips prose year-ranges ("Smith 2020-2025" is not a citation - pinned by
# test_surnamed_year_range_not_extracted).
_PAREN_CITE_RE = re.compile(
    r"((?:" + _SURNAME + r")(?:(?:,?\s+(?:and|&)\s+|,\s+)" + _SURNAME +
    r")*(?:\s+et al\.?)?),?\s+(" + _YEAR + r")(?:/(" + _YEAR + r"))?"
    r"(?!\s*[-–]\s*\d)"
)
# Narrative citation: Surname('s) (Year) / Surname et al. (Year).
_NARRATIVE_CITE_RE = re.compile(
    r"(" + _SURNAME + r")(?:'s|’s|')?(?:\s+et al\.?)?\s+\((" + _YEAR +
    r")(?:/(" + _YEAR + r"))?\)"
)

# Transliteration variants generated on BOTH sides of the comparison, so
# body "Fraenken" meets References "Fränken" (ä -> a AND ä -> ae).
_TRANSLIT = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "å": "aa", "ø": "oe", "æ": "ae",
}


def _fold_variants(s: str) -> set[str]:
    """Lowercased ASCII variants of a name: NFKD-stripped and
    transliteration-expanded. Curly apostrophes unify with straight ones
    (review 4f); empty variants are dropped (an empty needle would match
    everything - review 4g)."""
    import unicodedata
    low = s.lower().replace("’", "'")
    nfkd = unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode()
    translit = low
    for ch, rep in _TRANSLIT.items():
        translit = translit.replace(ch, rep)
    translit = unicodedata.normalize("NFKD", translit).encode(
        "ascii", "ignore").decode()
    return {v for v in (nfkd, translit) if v}


def _clean_tokens(tokens: list[str]) -> list[str]:
    """Strip a trailing possessive ('s / ’s / bare ') - the _SURNAME char
    class includes apostrophes (O'Neill), so "Nussbaum's" and "Chalmers'"
    are captured whole (review 4f)."""
    return [re.sub(r"[’']s?$", "", t) for t in tokens]


def extract_citations(body: str) -> list[tuple[int, str, list[str], list[str]]]:
    """(lineno, raw, surname_tokens, years) for each author-year citation in
    the body. `years` holds one year, or two for the reprint form 1930/2002.
    Fenced code blocks and heading lines are skipped. finditer catches every
    citation in a parenthesis, including comma-separated multi-cites
    "(Smith 2020, Jones 2021)" (review 4d)."""
    out = []
    in_fence = False
    for lineno, line in enumerate(body.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or stripped.startswith("#"):
            continue
        for content in _PAREN_RE.findall(line):
            for m in _PAREN_CITE_RE.finditer(content):
                tokens = _clean_tokens(re.findall(_SURNAME, m.group(1)))
                years = [y for y in (m.group(2), m.group(3)) if y]
                out.append((lineno, m.group(0).strip(), tokens, years))
        for m in _NARRATIVE_CITE_RE.finditer(line):
            years = [y for y in (m.group(2), m.group(3)) if y]
            out.append((lineno, m.group(0), _clean_tokens([m.group(1)]),
                        years))
    return out


def _find_refs_heading(text: str) -> tuple[int, int] | None:
    """(start, end) char offsets of the real ## References heading line -
    fence-aware, so a heading inside a code block never splits the file
    (review 6.1). The LAST real heading wins (References is a tail section)."""
    offset = 0
    in_fence = False
    found = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        elif not in_fence and re.match(r"^## References\s*$", line):
            found = (offset, offset + len(line))
        offset += len(line)
    return found


def check_citations(text: str) -> tuple[list[str], bool]:
    """Verify every in-text author-year citation resolves to a References
    entry. Returns (errors, checked); checked=False when the file has no
    ## References section (draft - nothing to resolve against).

    Resolution is deliberately MORE tolerant than the generator's matching
    (transliteration variants, either reprint year, suffix-tolerant) but
    word-boundary-strict on the surname: a substring test would let "he"
    resolve against "the" and blind the check for short surnames (review 4a).
    """
    span = _find_refs_heading(text)
    if span is None:
        return [], False
    body, refs = text[:span[0]], text[span[1]:]
    ref_lines = [ln for ln in refs.splitlines() if ln.strip()]
    folded_lines = [_fold_variants(ln) for ln in ref_lines]
    errors = []
    for lineno, raw, tokens, years in extract_citations(body):
        base_years = [y.rstrip("abcdefghijklmnopqrstuvwxyz") for y in years]
        resolved = False
        for ln, line_variants in zip(ref_lines, folded_lines):
            if not any(y in ln for y in base_years):
                continue
            for tok in tokens:
                for tv in _fold_variants(tok):
                    pat = re.compile(r"\b" + re.escape(tv) + r"\b")
                    if any(pat.search(lv) for lv in line_variants):
                        resolved = True
                        break
                if resolved:
                    break
            if resolved:
                break
        if not resolved:
            # cp1252-safe: the citation text is exactly where non-ASCII
            # lives; the error path must never crash the linter (review 6).
            raw_ascii = raw.encode("ascii", "backslashreplace").decode("ascii")
            errors.append(
                f"line {lineno}: citation '{raw_ascii}' does not resolve to "
                f"any References entry (ERROR)")
    return errors, True


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: python lint_md.py <markdown_file>", file=sys.stderr)
        return 1

    filepath = args[0]
    rc = lint_markdown(filepath)

    # Prose-quality advisories (item 13 §4.2): WARN-only — printed for the
    # orchestrator to see at Phase 6, never affecting the exit code.
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except OSError:
        # An unreadable file is a distinct condition from "no ## References
        # section yet" - conflating the two into the same "skipped" message
        # made a read failure look like an ordinary draft-stage skip. Skip
        # both the prose-quality and citation checks (there is no text to
        # check) and say so explicitly; the exit code still comes from
        # lint_markdown() above, unaffected by this read attempt.
        print("citation-check: file unreadable; skipped")
        return rc

    for warning in check_prose_quality(text):
        print(f"WARN prose-quality: {warning}")

    citation_errors, checked = check_citations(text)
    if not checked:
        print("citation-check: no ## References section; skipped")
    for err in citation_errors:
        print(f"ERROR unresolved-citation: {err}")
    if citation_errors:
        rc = rc or 1

    return rc


if __name__ == "__main__":
    sys.exit(main())
