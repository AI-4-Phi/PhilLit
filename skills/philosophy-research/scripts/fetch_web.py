#!/usr/bin/env python3
"""Fetch a web source and write a research-time capture the barrier can gate on.

Usage:
  bash "$PHILLIT_ROOT/bin/phillit-run" skills/philosophy-research/scripts/fetch_web.py \
      --url https://example.org/post --citekey smith2024post --review-dir "$REVIEW_DIR"

  # JS-rendered or bot-blocking hosts: read the page with WebFetch, then pipe it
  cat page.txt | bash "$PHILLIT_ROOT/bin/phillit-run" skills/philosophy-research/scripts/fetch_web.py \
      --stdin --url https://example.org/post --citekey smith2024post --review-dir "$REVIEW_DIR"

The capture is EVIDENCE that content was fetched, not writer input: the note is
written from the page, and the barrier reads the capture only to check that the
fetch happened and that the note's spans really occur in it.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import output  # noqa: E402
from rate_limiter import user_agent  # noqa: E402

MAX_BYTES = 20 * 1024 * 1024
TIMEOUT = 15
MAX_REDIRECTS = 5
# CID-font mojibake floor: extracted "text" that is mostly unprintable is not
# text. Loose on purpose -- it only has to catch garbage, not judge quality.
MIN_PRINTABLE_RATIO = 0.7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def extract_html(html: str) -> tuple[str, str]:
    """(title, text). `<title>` first, then `<h1>`; scripts and styles dropped
    so their source never counts toward the barrier's length floor."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.h1:
        title = soup.h1.get_text(" ", strip=True)
    return title, soup.get_text(" ", strip=True)


def extract_pdf(data: bytes) -> tuple[str, str]:
    """(title, text) from PDF bytes. Raises on an encrypted file."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ValueError("pdf-encrypted")
    meta = reader.metadata or {}
    title = meta.get("/Title") or ""
    text = " ".join((page.extract_text() or "") for page in reader.pages)
    return str(title).strip(), text.strip()


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    ok = sum(1 for c in text if c.isprintable() or c.isspace())
    return ok / len(text)


def build_record_from_response(url, final_url, status, content_type, body) -> dict:
    """A capture record from fetched bytes, or an error record.

    Every failure direction here is toward NO PROMOTION and is recorded, never
    silent: an over-cap body, an encrypted PDF, a scanned PDF with no text, and
    CID-font mojibake all become error records rather than thin captures that
    might scrape past the barrier's length floor.
    """
    base = {"url": url, "final_url": final_url, "retrieved_at": _now(),
            "http_status": status, "content_type": content_type,
            "provenance": "script"}
    if len(body) > MAX_BYTES:
        return {**base, "error": f"response-too-large:{len(body)}"}
    is_pdf = ("application/pdf" in (content_type or "").lower()
              or body[:5] == b"%PDF-")
    try:
        if is_pdf:
            title, text = extract_pdf(body)
            if not text:
                return {**base, "error": "pdf-no-text"}
            if _printable_ratio(text) < MIN_PRINTABLE_RATIO:
                return {**base, "error": "pdf-unreadable-text"}
        else:
            title, text = extract_html(body.decode("utf-8", errors="replace"))
    except Exception as exc:
        return {**base, "error": f"extract-failed:{exc}"}
    return {**base, "title": title, "text": text}


def build_stdin_record(url: str, text: str) -> dict:
    """An agent-provided capture. `provenance: "agent"` is load-bearing: it
    skips the status check (there is no HTTP status) and it marks the design's
    residual trust assumption, since WebFetch output is a model-mediated
    rendering of the page rather than the page."""
    return {"url": url, "final_url": url, "retrieved_at": _now(),
            "http_status": None, "content_type": None, "title": "",
            "provenance": "agent", "text": text}


def write_capture(out_dir, citekey: str, record: dict) -> str:
    """Atomic write. Returns "written" or "kept_existing".

    The never-clobber rule: a failure record must not overwrite a good capture,
    or a re-run during an outage would flip a citable entry back to
    EVIDENCE-NONE on the next barrier pass. A successful re-fetch does
    overwrite.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{citekey}.json"
    if record.get("error") and path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and not existing.get("error"):
                return "kept_existing"
        except (OSError, ValueError):
            pass
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(str(tmp), str(path))
    return "written"


def fetch(url: str) -> dict:
    """GET the URL and build a capture record."""
    # Scheme allow-list. The barrier's extractor only yields http(s), but --url
    # takes a string verbatim and `file:///` should never reach requests.
    # Residual, accepted and stated: redirect TARGETS are unrestricted, so a
    # malicious page can still bounce this into the LAN. The URL supplier is
    # the researcher agent on the owner's own machine, so DNS-level private-IP
    # blocking is out of proportion here.
    if not str(url).lower().startswith(("http://", "https://")):
        return {"url": url, "final_url": None, "retrieved_at": _now(),
                "http_status": None, "content_type": None,
                "provenance": "script", "error": "unsupported-scheme"}
    session = requests.Session()
    session.max_redirects = MAX_REDIRECTS
    # stream=True so the cap is enforced BEFORE the bytes are in memory: a
    # non-streamed get() has already downloaded a 5 GB body by the time any
    # len() check runs, which is a memory problem rather than an error record.
    resp = session.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True,
                       headers={"User-Agent": user_agent()})
    ctype = resp.headers.get("Content-Type", "")
    declared = resp.headers.get("Content-Length")
    over = {"url": url, "final_url": resp.url, "retrieved_at": _now(),
            "http_status": resp.status_code, "content_type": ctype,
            "provenance": "script"}
    if declared and str(declared).isdigit() and int(declared) > MAX_BYTES:
        resp.close()
        return {**over, "error": f"response-too-large:{declared}"}
    chunks, total = [], 0
    for chunk in resp.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > MAX_BYTES:       # a lying or absent Content-Length
            resp.close()
            return {**over, "error": f"response-too-large:{total}"}
        chunks.append(chunk)
    return build_record_from_response(
        url=url, final_url=resp.url, status=resp.status_code,
        content_type=ctype, body=b"".join(chunks))


def main() -> int:
    load_dotenv(find_dotenv(usecwd=True), override=True)
    ap = argparse.ArgumentParser(
        description="Fetch a web source and write a research-time capture")
    ap.add_argument("--url", required=True, help="The source URL")
    ap.add_argument("--citekey", required=True,
                    help="BibTeX key the capture belongs to")
    ap.add_argument("--review-dir", default=".",
                    help="Review directory (default: cwd)")
    ap.add_argument("--stdin", action="store_true",
                    help="Read page text from stdin instead of fetching")
    args = ap.parse_args()

    if args.stdin:
        record = build_stdin_record(args.url, sys.stdin.read())
    else:
        try:
            record = fetch(args.url)
        except Exception as exc:
            record = {"url": args.url, "final_url": None, "retrieved_at": _now(),
                      "http_status": None, "content_type": None,
                      "provenance": "script", "error": f"fetch-failed:{exc}"}

    out_dir = Path(args.review_dir) / "intermediate_files" / "web_captures"
    outcome = write_capture(out_dir, args.citekey, record)
    # output.dumps, not a hand-picked ensure_ascii: this summary echoes the
    # page's own title, i.e. arbitrary web text. The helper prints real
    # characters where stdout can encode them and falls back to escapes where
    # it cannot, which is the whole point of dc606de.
    print(output.dumps({
        "status": "error" if record.get("error") else "success",
        "citekey": args.citekey,
        "outcome": outcome,
        "error": record.get("error"),
        "chars": len(record.get("text") or ""),
        "title": record.get("title") or "",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
