"""Chicago letters end-to-end: a letter assigned at the barrier must survive
every
Phase 6 stage and come out in the rendered References.

`year_suffix` in dedupe_bib._KNOWN_FIELDS proves nothing on its own: the
letter has to survive a merge, an attestation-aware re-stamp, a pybtex
round-trip in the renderer, the sanitizer, and it has to be the token the
linter and the evidence checker actually see. The only thing that proves
that is running the real Phase 6 command sequence through the real
command-line entry points, which is what this module does.

Stage order follows skills/literature-review/SKILL.md Phase 6 verbatim --
dedupe -> generate -> lint -> check_evidence -> sanitize -- including
dedupe's `--evidence-report` argument, because the attestation-aware
re-stamp pass rewrites every surviving entry's text and is therefore one of
the carriers under test. (Steps 1-2 of Phase 6, assemble_review and
normalize_headings, are out of scope: they never touch a .bib.)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS = (Path(__file__).resolve().parent.parent / "skills"
           / "literature-review" / "scripts")

# menary2010cognitive and menaryCogIntegration are deliberately the SAME work
# (shared DOI 10.7551/mitpress/1.001) reached through two domains, so the
# barrier has to give both copies the same letter and dedupe has to fold them
# into one entry before the renderer sees them. Do not "simplify" this by
# feeding the un-deduped domain bibs straight to generate_bibliography.py:
# generate_bibliography._resolve_collisions runs BEFORE that script's own
# dedup pass, so its suffix filter refuses to act on any collision group whose
# members are not pairwise-distinct works (_members_are_distinct_works). Feed
# it duplicates and it correctly falls through to keep-all -- a state the real
# pipeline never produces, which would look like a bug in the filter. The
# dedupe-before-generate ordering is exactly what this test exists to pin.
DOMAIN_1 = """@incollection{menary2010cognitive,
  author = {Menary, Richard},
  title = {Cognitive Integration and the Extended Mind},
  booktitle = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/1.001},
  year = {2010},
  keywords = {mind, High}
}

@book{menary2010extended,
  author = {Menary, Richard},
  title = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/2.002},
  year = {2010},
  keywords = {mind, High}
}"""

DOMAIN_2 = """@incollection{menaryCogIntegration,
  author = {Menary, Richard},
  title = {Cognitive Integration and the Extended Mind},
  booktitle = {The Extended Mind},
  publisher = {MIT Press},
  doi = {10.7551/mitpress/1.001},
  year = {2010},
  keywords = {mind, Medium}
}"""

# Two citation forms, and BOTH are load-bearing -- do not drop either.
#
# "Menary (2010a; 2010b)" is the compact continuation form that
# generate_bibliography._citation_instances parses. It is
# invisible to lint_md.extract_citations: _NARRATIVE_CITE_RE needs the
# closing paren right after the year, and _PAREN_CITE_RE needs a surname
# INSIDE the parenthesis, so "(2010a; 2010b)" matches neither. With only that
# sentence the linter extracts ZERO citations and every lint assertion below
# passes vacuously.
#
# "(Menary 2010b)" is the parenthetical form lint_md DOES parse, so it is what
# makes the linter's suffix check actually run against the rendered
# References -- delete it and the lint stage below asserts nothing. It also
# puts the second citation shape through check_evidence.find_cites, whose two
# arms handle the two forms differently.
PROSE = """# Review

## Section 1: Integration

Menary (2010a; 2010b) develops two distinct treatments of the same theme.

The extended-mind volume is the second of these (Menary 2010b).
"""

SHARED_DOI = "10.7551/mitpress/1.001"


def _run(cwd, *args):
    """Run a bundled script as a subprocess, with cwd OUTSIDE the repo tree.

    cwd is always the tmp_path review dir, never pytest's cwd (the repo
    root). evidence_barrier.main() calls
    load_dotenv(find_dotenv(usecwd=True), override=True), which walks UP
    from the subprocess's cwd for a .env and OVERRIDES the inherited
    environment with what it finds -- including a real OPENALEX_API_KEY that
    tests/conftest.py::_no_ambient_openalex_key already stripped. A repo-root
    .env is exactly what .env.example and /phillit:setup tell developers to
    create, so running from the repo root would make this test spend real,
    metered OpenAlex budget on a developer machine, silently, because
    venue-vetting failures never fail a test. See that fixture's docstring
    (it documents both halves of the fix) and the identically-motivated
    _run() in tests/test_evidence_barrier.py.

    Note also that conftest's isolated_phillit_dirs fixture monkeypatches
    in-process modules and so does NOT reach a subprocess: a subprocess still
    sees the real ~/.cache/phillit. Nothing here writes there, because
    venue vetting is the only cache user on this path and it never runs (no
    key, and no fixture entry carries a `journal` field, so it is handed an
    empty venue list).

    The returncode is asserted here rather than at the call sites: a stage
    that crashed would otherwise leave its output file untouched and let the
    NEXT stage's assertions describe the failure, or pass vacuously.
    """
    r = subprocess.run([sys.executable, *[str(a) for a in args]],
                       capture_output=True, text=True, cwd=str(cwd))
    assert r.returncode == 0, (
        f"{Path(str(args[0])).name} exited {r.returncode}\n"
        f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}")
    return r


def _entry_chunk(bib_text, key):
    """The single entry chunk for `key`. Asserts it occurs exactly once."""
    chunks = [c for c in bib_text.split("\n@") if key in c]
    assert len(chunks) == 1, f"expected exactly one {key} entry, got {len(chunks)}"
    return chunks[0]


def _suffix_of(bib_text, key):
    """The Chicago letter stamped on `key`, or "" if it carries none.

    Chunk first, then search -- the shape tests/test_evidence_barrier.py
    already uses. Splitting the WHOLE file on "year_suffix = {" and indexing
    the second piece silently reads a different entry's letter as soon as an
    earlier entry carries one.
    """
    m = re.search(r'year_suffix\s*=\s*[{"]([^}"]*)[}"]', _entry_chunk(bib_text, key))
    return m.group(1) if m else ""


def _entry_count(bib_text):
    return len(re.findall(r"(?m)^@\w+\s*\{", bib_text))


def _scaffold(tmp_path):
    """A two-domain review dir in the shape the barrier expects."""
    rd = tmp_path / "review"
    ij = rd / "intermediate_files" / "json"
    ij.mkdir(parents=True)
    (rd / "literature-domain-1.bib").write_text(DOMAIN_1, encoding="utf-8")
    (rd / "literature-domain-2.bib").write_text(DOMAIN_2, encoding="utf-8")
    for i in (1, 2):
        name = f"literature-domain-{i}.bib"
        stem = name.replace(".bib", ".json")
        (ij / f"cleaning_ledger-{stem}").write_text(
            json.dumps({"schema_version": 1, "bib_file": name,
                        "breaker_tripped": False, "entries": {}}),
            encoding="utf-8")
        (ij / f"enrichment_ledger-{stem}").write_text(
            json.dumps({"schema_version": 1, "bib_file": name, "entries": {}}),
            encoding="utf-8")
        (ij / f"encyclopedia_entries-domain-{i}.json").write_text(
            '{"sep_entries": [], "iep_entries": []}', encoding="utf-8")
    return rd


def test_letter_survives_the_whole_phase_6_chain(tmp_path):
    rd = _scaffold(tmp_path)

    # --- Phase 3->4 barrier: assign and stamp the letters -------------------
    _run(rd, SCRIPTS / "evidence_barrier.py", rd, "--domains", "2")

    d1 = (rd / "literature-domain-1.bib").read_text(encoding="utf-8")
    d2 = (rd / "literature-domain-2.bib").read_text(encoding="utf-8")
    assert "year_suffix = {a}" in d1 and "year_suffix = {b}" in d1
    # The same work reached through two domains carries the SAME letter --
    # a writer in domain 2 must not cite "2010b" for what domain 1 calls
    # "2010a".
    assert _suffix_of(d1, "menary2010cognitive") == _suffix_of(d2, "menaryCogIntegration")
    assert {_suffix_of(d1, "menary2010cognitive"),
            _suffix_of(d1, "menary2010extended")} == {"a", "b"}
    # `year` itself is never rewritten: the \\d{4} guards in check_evidence.py
    # and resolve_context.py reject "2010a".
    assert "year = {2010}" in d1 and "2010a" not in d1

    md = rd / "literature-review-x.md"
    md.write_text(PROSE, encoding="utf-8")
    merged = rd / "literature-x.bib"
    report = rd / "intermediate_files" / "json" / "evidence_report.json"

    # --- Phase 6 step 3: dedupe (with the re-stamp pass in the path) --------
    _run(rd, SCRIPTS / "dedupe_bib.py", merged, "--evidence-report", report,
         rd / "literature-domain-1.bib", rd / "literature-domain-2.bib")
    merged_text = merged.read_text(encoding="utf-8")
    # The ordering guarantee, made explicit rather than incidental: the two
    # copies of the shared-DOI work MUST be one entry before the renderer
    # runs, or generate_bibliography's suffix filter disables itself on a
    # non-distinct group (see the DOMAIN_1/DOMAIN_2 comment above). A future
    # change that reorders the pipeline fails here, with a clear message.
    assert merged_text.count(SHARED_DOI) == 1
    assert _entry_count(merged_text) == 2
    letter_cog = _suffix_of(merged_text, "menary2010cognitive")
    letter_book = _suffix_of(merged_text, "menary2010extended")
    assert {letter_cog, letter_book} == {"a", "b"}

    # --- Phase 6 step 4: render the References ------------------------------
    _run(rd, SCRIPTS / "generate_bibliography.py", md, merged)
    rendered = md.read_text(encoding="utf-8")
    assert "2010a." in rendered and "2010b." in rendered
    # Bind each letter to the RIGHT work, not merely to some reference line:
    # a renderer that emitted both letters but swapped them would satisfy the
    # bare substring check above.
    refs = rendered.split("## References", 1)[1].splitlines()
    cog_line = [ln for ln in refs if "Cognitive Integration" in ln]
    book_line = [ln for ln in refs if "Menary" in ln and "Cognitive Integration" not in ln]
    assert len(cog_line) == 1 and len(book_line) == 1, rendered
    assert f"2010{letter_cog}." in cog_line[0]
    assert f"2010{letter_book}." in book_line[0]

    # --- Phase 6 step 5: lint ------------------------------------------------
    lint = _run(rd, SCRIPTS / "lint_md.py", md)
    assert "does not resolve" not in lint.stdout, lint.stdout
    assert "carries the suffix" not in lint.stdout, lint.stdout

    # Positive control for the two assertions above. They are "absence of a
    # message" checks, which a linter that extracted no citations at all
    # would also satisfy; this proves the suffix check really is running
    # against THIS rendered References. Same file, one letter changed to one
    # nothing in References carries.
    assert "(Menary 2010b)" in rendered
    probe = rd / "lint-probe.md"
    probe.write_text(rendered.replace("(Menary 2010b)", "(Menary 2010c)"),
                     encoding="utf-8")
    probe_lint = _run(rd, SCRIPTS / "lint_md.py", probe)   # WARN, never ERROR
    assert "carries the suffix" in probe_lint.stdout
    assert "2010c" in probe_lint.stdout

    # --- Phase 6 step 6: evidence telemetry ---------------------------------
    check = _run(rd, SCRIPTS / "check_evidence.py", md, merged)
    cited = {ln.split(": ", 1)[1] for ln in check.stdout.splitlines()
             if ln.startswith("CHECK none-cited: ")}
    # Both lettered works resolve against the lettered prose. Strict
    # suffix matching that failed to bind the second work would report it as
    # uncited -- false telemetry manufactured by this feature.
    assert cited == {"menary2010cognitive", "menary2010extended"}
    summary = json.loads(check.stdout.rsplit("CHECK-SUMMARY: ", 1)[1])
    assert summary["none_cited"] == 2

    # --- Phase 6 step 7: sanitize the delivered bib -------------------------
    _run(rd, SCRIPTS / "sanitize_bib.py", merged)
    sanitized = merged.read_text(encoding="utf-8")
    assert "EVIDENCE-" not in sanitized          # the sanitizer did its own job
    assert _suffix_of(sanitized, "menary2010cognitive") == letter_cog
    assert _suffix_of(sanitized, "menary2010extended") == letter_book
