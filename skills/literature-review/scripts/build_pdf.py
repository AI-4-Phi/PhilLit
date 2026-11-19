#!/usr/bin/env python3
"""Build the review PDF with pandoc + lualatex, never silently losing characters.

pandoc's default font (Latin Modern) has no Greek, so a review that reports
"β = 0.4" lost every β while the step still said "Converted to PDF" (PL-38).
This tries wide-coverage fonts in order, keeps the first build that lualatex
reports no "Missing character" for, and otherwise keeps the build with the
fewest losses and names the lost characters.

Usage: build_pdf.py <review.md> <review.pdf>
Prints `Converted to PDF: <name>` on success, plus one
`WARN pdf-missing-characters: ...` line when characters were still lost.
Exit 0 when a PDF was built, 1 when every build failed, 2 on bad usage.
"""
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Fonts TeX Live ships (stix2-otf, libertinus-fonts, dejavu) and that common
# systems carry; None is pandoc's default, the last resort.
CANDIDATE_FONTS = ("STIX Two Text", "Libertinus Serif", "DejaVu Serif", "Noto Serif", None)

# pandoc relays lualatex's warning as
# "[WARNING] Missing character: There is no β (U+03B2) (U+03B2) in font ..."
_MISSING_RE = re.compile(r"Missing character: There is no (.+?) \((U\+[0-9A-F]{4,6})\)")


def parse_missing(stderr: str) -> Counter:
    """Count lost characters by (char, codepoint) from pandoc's stderr."""
    return Counter((m.group(1), m.group(2)) for m in _MISSING_RE.finditer(stderr))


def font_available(name: str) -> bool:
    """Ask luaotfload (the font resolver lualatex itself uses) whether `name` exists."""
    tool = shutil.which("luaotfload-tool")
    if tool is None:
        return False
    try:
        r = subprocess.run([tool, f"--find={name}"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and "found!" in (r.stdout + r.stderr)


def pandoc_command(md: Path, pdf: Path, font):
    cmd = ["pandoc", str(md), "--from", "markdown", "--pdf-engine=lualatex",
           "-V", "geometry:margin=1in", "-V", "fontsize=11pt", "--output", str(pdf)]
    if font:
        cmd += ["-V", f"mainfont={font}"]
    return cmd


def run_pandoc(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stderr


def build(md: Path, pdf: Path, fonts=CANDIDATE_FONTS, available=font_available, run=run_pandoc):
    """Return (font, missing Counter) of the kept build, or None if every build failed."""
    best = None  # (n_missing, font, missing, tmp path)
    tmps = []
    try:
        for i, font in enumerate(fonts):
            if font is not None and not available(font):
                continue
            tmp = pdf.with_name(f"{pdf.stem}.try{i}{pdf.suffix}")
            tmps.append(tmp)
            rc, err = run(pandoc_command(md, tmp, font))
            if rc != 0 or not tmp.exists():
                continue
            missing = parse_missing(err)
            n = sum(missing.values())
            if best is None or n < best[0]:
                best = (n, font, missing, tmp)
            if n == 0:
                break
        if best is None:
            return None
        best[3].replace(pdf)
        return best[1], best[2]
    finally:
        for t in tmps:
            if t.exists():
                t.unlink()


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
        print(f"WARN pdf-missing-characters: the PDF lacks {lost}; no installed font has them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
