#!/usr/bin/env python3
"""Build the review PDF with pandoc + lualatex, never silently losing characters.

pandoc's default font (Latin Modern) has no Greek, so a review that reports
"β = 0.4" lost every β while the step still said "Converted to PDF" (PL-38).
This tries wide-coverage fonts in order, keeps the first build that reports
no "Missing character", and otherwise keeps the build with the fewest losses
and names the lost characters (by codepoint; "unparsed" for a warning in an
unknown shape).

Usage: build_pdf.py <review.md> <review.pdf>
Prints `Converted to PDF: <name>` on success, plus one
`WARN pdf-missing-characters: ...` line when characters were still lost.
Exit 0 when a PDF was built, 1 when every build failed, 2 on bad usage.
"""
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

# Fonts TeX Live ships (stix2-otf, libertinus-fonts, dejavu) and that common
# systems carry; None is pandoc's default, the last resort. A font that is not
# installed fails its build in about a second, so there is no preflight: the
# build itself is the availability test, through lualatex's own resolver.
CANDIDATE_FONTS = ("STIX Two Text", "Libertinus Serif", "DejaVu Serif", "Noto Serif", None)
BUILD_TIMEOUT = 600  # seconds per build

# pandoc relays lualatex's warning as
# "[WARNING] Missing character: There is no β (U+03B2) (U+03B2) in font ..."
_MISSING_RE = re.compile(r"Missing character: There is no (.+?) \((U\+[0-9A-F]{4,6})\)")
_ANY_MISSING_RE = re.compile(r"Missing character", re.IGNORECASE)


def parse_missing(output: str) -> Counter:
    """Count lost characters by (char, codepoint) from pandoc's output.

    A "Missing character" line in another shape (no codepoint) still counts,
    as ("?", "unparsed"): a build that reports a loss is never clean.
    """
    missing = Counter()
    for line in output.splitlines():
        if not _ANY_MISSING_RE.search(line):
            continue
        m = _MISSING_RE.search(line)
        missing[(m.group(1), m.group(2)) if m else ("?", "unparsed")] += 1
    return missing


def pandoc_command(md: Path, pdf: Path, font):
    cmd = ["pandoc", str(md), "--from", "markdown", "--pdf-engine=lualatex",
           "-V", "geometry:margin=1in", "-V", "fontsize=11pt", "--output", str(pdf)]
    if font:
        cmd += ["-V", f"mainfont={font}"]
    return cmd


def run_pandoc(cmd):
    """(returncode, stdout + stderr); a pandoc that cannot start or hangs is a failed build."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=BUILD_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"{type(e).__name__}: {e}"
    return r.returncode, r.stdout + r.stderr


def build(md: Path, pdf: Path, fonts=CANDIDATE_FONTS, run=run_pandoc):
    """Return (font, missing Counter) of the kept build, or None if every build failed."""
    best = None  # (n_missing, font, missing, candidate path)
    with tempfile.TemporaryDirectory(prefix=".pdf-build-", dir=pdf.parent) as tmpdir:
        for i, font in enumerate(fonts):
            cand = Path(tmpdir) / f"try{i}.pdf"
            rc, out = run(pandoc_command(md, cand, font))
            if rc != 0 or not cand.exists():
                continue
            missing = parse_missing(out)
            n = sum(missing.values())
            if best is None or n < best[0]:
                best = (n, font, missing, cand)
            if n == 0:
                break
        if best is None:
            return None
        try:
            best[3].replace(pdf)
        except OSError as e:  # e.g. the old PDF is open in a viewer on Windows
            print(f"PDF build: could not write {pdf.name} ({type(e).__name__})")
            return None
    return best[1], best[2]


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Usage: build_pdf.py <review.md> <review.pdf>", file=sys.stderr)
        return 2
    md, pdf = Path(args[0]), Path(args[1])
    result = build(md, pdf)
    if result is None:
        print("PDF build failed with every font; no PDF written")
        return 1
    font, missing = result
    print(f"Converted to PDF: {pdf.name} (font: {font or 'pandoc default'})")
    if missing:
        # Codepoints only: the characters themselves may not encode on a
        # Windows cp1252 console.
        lost = ", ".join(f"{cp} x{n}" for (_, cp), n in sorted(missing.items(), key=lambda kv: kv[0][1]))
        print(f"WARN pdf-missing-characters: the PDF lacks {lost}; none of the fonts tried has them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
