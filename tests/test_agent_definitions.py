"""In plugin mode, agents and skills run from the user's workspace: relative
repo paths like `../docs/conventions.md` resolve against the workspace's parent
directory, not the plugin root. Shared-doc references must use $PHILLIT_ROOT
(bridged into the session by the SessionStart bootstrap).

Review finding (2026-07-13): SKILL.md was fixed to the $PHILLIT_ROOT form
during the plugin conversion; the agent files were not.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_no_relative_docs_paths_in_agents_or_skills():
    files = list((REPO_ROOT / "agents").glob("*.md")) + list(
        (REPO_ROOT / "skills").rglob("SKILL.md")
    )
    assert files, "expected agent/skill definitions to exist"
    offenders = []
    for path in files:
        for i, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if "../docs/" in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{i}")
    assert not offenders, (
        "relative ../docs/ paths do not resolve from a plugin workspace "
        "(use $PHILLIT_ROOT/docs/...):\n" + "\n".join(offenders)
    )


def test_researcher_teaches_verify_paper_output_convention():
    """verify_paper.py owns its output file via --output;
    a researcher piping stdout to a file (or worse, `2>&1`) corrupts the
    JSON with interleaved progress logs. The agent definition must both
    show the --output invocation and explicitly forbid the redirect
    footgun. We only assert positive markers (never `"2>&1" not in text`)
    because the prohibition sentence itself quotes `2>&1`.
    """
    path = REPO_ROOT / "agents" / "domain-literature-researcher.md"
    text = path.read_text(encoding="utf-8")

    assert "verify_paper.py" in text and "--output" in text, (
        "researcher agent must show verify_paper.py invoked with --output"
    )
    assert "never redirect" in text.lower() or "do not redirect" in text.lower(), (
        "researcher agent must explicitly instruct never to redirect "
        "verify_paper.py output (e.g. `> f.json 2>&1`) instead of using --output"
    )


def test_researcher_forbids_post_enrichment_reemission():
    """A/B root cause 2 (2026-07-25): researchers re-emit the whole bib
    after enrichment, silently mutating hash-attested abstracts. The
    guidance must freeze the file, name the Write AND the Bash-workaround
    paths, and give the surgical-Edit alternative."""
    path = REPO_ROOT / "agents" / "domain-literature-researcher.md"
    text = path.read_text(encoding="utf-8")
    assert "FROZEN after enrichment" in text
    assert "Never `Write` the whole bib file again" in text
    assert "Bash file operations" in text
    assert "surgical" in text.lower()


def test_researcher_has_edit_tool_and_guidance():
    """Researchers need Edit
    for surgical changes to .bib files after enrichment. The tool must be
    listed in frontmatter and guidance must replace the stale "Edit is NOT
    available" note with new guidance about post-edit validation."""
    path = REPO_ROOT / "agents" / "domain-literature-researcher.md"
    text = path.read_text(encoding="utf-8")

    # Extract frontmatter
    lines = text.split("\n")
    tools_line = None
    for line in lines:
        if line.startswith("tools:"):
            tools_line = line
            break

    assert tools_line is not None, "could not find 'tools:' line in frontmatter"
    assert "Edit" in tools_line, "Edit tool must be in the frontmatter tools list"

    # Verify stale guidance is gone
    assert "The Edit tool is NOT available to you" not in text, (
        "stale guidance asserting Edit is unavailable must be removed"
    )

    # Verify new guidance is present
    assert "Prefer `Edit` for targeted changes" in text or "Edit` to a `.bib`" in text, (
        "new guidance about Edit post-edit validation must be present"
    )


def test_writer_tier_rules_carry_b2_edits():
    """Adjudication 2026-07-28 + decision b2 2026-08-01: CONTEXT
    attribution was followed 1 of 4 times, and EXISTENCE-tier
    over-characterization needed a title-derivable clarifier plus
    calibration examples from the adjudicated run."""
    path = REPO_ROOT / "agents" / "synthesis-writer.md"
    text = path.read_text(encoding="utf-8")
    assert "title-derivable" in text
    assert "every sentence" in text.lower()
    assert "Calibration examples" in text
    assert "Sequoiah-Grayson" in text          # CONTEXT exemplar present
    assert "announces, in its very title" in text  # EXISTENCE exemplar present
    assert "data creators" in text             # negative exemplar present

    planner_path = REPO_ROOT / "agents" / "synthesis-planner.md"
    planner_text = planner_path.read_text(encoding="utf-8")
    assert "title-derivable" in planner_text   # mirrors the writer's carve-out


def test_writer_knows_the_venue_status_rule():
    """A bare "venue_status" in text
    substring is vacuous -- it would pass even if the flag were rewritten as
    a quality signal. Pin the two phrases that make it a visibility-not-
    quality caveat with a real floor on when the field means nothing."""
    text = (REPO_ROOT / "agents" / "synthesis-writer.md").read_text(encoding="utf-8")
    assert "venue_status" in text
    assert "low-visibility" in text
    assert "visibility, not" in text
    assert "absence of the field means nothing" in text


def test_planner_knows_the_venue_status_rule():
    """The writer rule is pinned by four
    assertions and the researcher rule by two, but the planner's venue
    sentence -- added by Task 5 fix round 2 -- was pinned by nothing and
    could be deleted with a green suite. Pin the load-bearing phrases, not
    the bare field name: a "venue_status" substring alone would survive the
    directive being rewritten into a quality judgement (same vacuity the
    writer test's docstring warns about)."""
    text = (REPO_ROOT / "agents" / "synthesis-planner.md").read_text(encoding="utf-8")
    assert "venue_status" in text
    assert "low-visibility" in text
    assert "anchor of a section" in text
    assert "sole support" in text
    # The flag restricts PROMINENCE, never eligibility -- eligibility is the
    # evidence tier's job, and conflating the two would silently drop work.
    assert "still outline-eligible" in text


def test_researcher_told_not_to_write_any_derived_field():
    """The ban must cover EVERY barrier-owned field a researcher could
    plausibly hand-write, not just venue_status.

    The prompt banned hand-writing `venue_status` while saying nothing
    about `year_suffix` --
    even though the barrier owns both, re-derives both every run, and a
    hand-written `year_suffix` is the more dangerous of the two: one the
    stripper cannot reach can make a collision group look structurally
    complete and cost a cited work. `same_work_group` joined the owned set
    with the reprint annotation and takes the same ban: a hand-written one
    would tell the writer to collapse two genuinely distinct works.
    """
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    assert ("Never write a `venue_status`, `year_suffix`, or "
            "`same_work_group` field yourself") in text
    # And the reason, not just the prohibition -- a bare ban invites a
    # researcher to treat it as style rather than correctness.
    assert "re-derives them from scratch on every run" in text


def test_writer_knows_the_year_suffix_rule():
    """A bare "year_suffix" substring is vacuous -- the venue-vetting review
    caught
    this exact pattern for venue_status (see test_writer_knows_the_venue_
    status_rule below). Pin the load-bearing phrases so the test fails if the
    citation directive itself were stripped out, not just if the field name
    disappeared."""
    text = (REPO_ROOT / "agents" / "synthesis-writer.md").read_text(encoding="utf-8")
    assert "year_suffix" in text
    assert "the letter is part of the citation" in text
    assert "never invent one" in text
    # The old "the renderer cannot emit yet" caveat must be gone.
    assert "cannot emit yet" not in text


def test_writer_and_planner_know_the_same_work_group_rule():
    """A bare "same_work_group" substring is vacuous, the same vacuity the
    venue_status and year_suffix pins warn about. Pin the load-bearing
    directive on both sides: the field's whole purpose is that the members
    are ONE work, so a rewrite that lost "one work" while keeping the field
    name would leave the Reiman defect exactly where it was."""
    writer = (REPO_ROOT / "agents" / "synthesis-writer.md").read_text(
        encoding="utf-8")
    assert "same_work_group" in writer
    assert "treat them as ONE work" in writer
    assert "the work ONCE" in writer
    # The escape hatch stays available -- the annotation is advisory, and a
    # writer that inspects and finds two real works must be able to cite both.
    assert "genuinely distinct" in writer

    planner = (REPO_ROOT / "agents" / "synthesis-planner.md").read_text(
        encoding="utf-8")
    assert "same_work_group" in planner
    assert "single position, never as two" in planner


def test_conventions_has_no_stale_suffix_caveat():
    text = (REPO_ROOT / "docs" / "conventions.md").read_text(encoding="utf-8")
    assert "year_suffix" in text
    for stale in ("does not yet emit", "cannot emit yet", "not yet emit"):
        assert stale not in text, f"stale renderer caveat still present: {stale}"


def test_planner_never_converts_evidence_bar_into_gap_claim():
    """Observed in production (2026-08-19): the planner converted
    EVIDENCE-NONE bars into
    "a gap the reviewed literature leaves unaddressed" while an
    abstract-attested source bearing on the same question sat unused in the
    corpus; the claim shipped 3x in the final text. The old prose seeded it:
    "note the gap if the work would have been important". Pin the
    replacement convention's load-bearing phrases (a bare "gap" substring
    would be vacuous), and pin the seeding phrase OUT."""
    text = (REPO_ROOT / "agents" / "synthesis-planner.md").read_text(
        encoding="utf-8")
    assert "never a claim about the literature" in text
    assert "verified substitute" in text
    assert "omit the topic silently" in text
    # The permission floor for a genuine absence claim: no relevant entry
    # at ANY tier -- not "no citable entry".
    assert "at any tier" in text
    # The seeding phrase must be gone.
    assert "note the gap if the work would have been important" not in text


def test_writer_never_asserts_unplanned_literature_gap():
    """Same production run: the writer transcribed the planned gap claim
    twice, stripped the disclosing parenthetical, and ADDED a third
    unplanned instance in the Conclusion. The planner convention cannot
    reach that third instance -- pin a writer-side guard that makes
    negative-existence claims outline-licensed only."""
    text = (REPO_ROOT / "agents" / "synthesis-writer.md").read_text(
        encoding="utf-8")
    assert "only where the outline explicitly plans" in text
    assert "not evidence of absence" in text


def test_researcher_carve_out_names_every_primary_excluded_host():
    """Prose-vs-policy pin (the encyclopedia-host exclusion shipped with
    manual verification only): the
    researcher's carve-out block must name each of the four primary excluded
    hosts literally, not just gesture at "encyclopedia hosts". A rename or a
    dropped host in web_evidence.EXCLUDED_HOST_HINTS with no matching prose
    update must fail this, and vice versa if the prose silently drops one.
    The two SEP mirror hostnames are deliberately NOT required literally --
    the prose covers them generically via "or its mirrors"."""
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    for host in ("plato.stanford.edu", "iep.utm.edu", "ndpr.nd.edu",
                 "philpapers.org"):
        assert host in text, f"researcher prose does not name {host}"
    assert "mirrors" in text


def _section(text, start_heading, end_heading):
    """The prose between two Markdown headings, both anchored at line start."""
    pattern = (r"(?ms)^" + re.escape(start_heading) + r".*?(?=^" + re.escape(end_heading) + r")")
    m = re.search(pattern, text)
    assert m, f"section {start_heading!r} not found before {end_heading!r}"
    return m.group(0)


def test_researcher_prose_makes_citation_chaining_required():
    """Stage 4 was skipped silently in 18 of 33 local domains and 6 of 6
    service domains (2026-09-03 measurement): nothing said it must run.
    Pin the heading marker, the per-domain rule, the narrow documented
    skip, and the checklist row."""
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    assert "### Stage 4: Citation Chaining (REQUIRED)" in text
    stage4 = _section(text, "### Stage 4: Citation Chaining (REQUIRED)", "### Stage 5: Metadata Enrichment & Verification")
    assert "Stage 4 runs in every domain" in stage4
    assert "Stage 4 skipped: no resolvable seeds (S2 status:" in stage4
    assert "Exactly one" in stage4  # the one-seed case has an action
    # ...and it carries the inventory count, because the one-seed case is the
    # one an undercounted inventory lands you in wrongly. Detection, not
    # enforcement: `<N>` is still self-reported, but a bare "one seed
    # available" leaves an undercount invisible in the deliverable.
    assert "Stage 4: one seed available (candidates inspected: <N>)" in stage4
    # A chaining run that errored is not a skip: it has its own evidenced line.
    assert "Stage 4 attempted: chaining incomplete" in stage4
    checklist = _section(text, "## Before Submitting — Quality Checklist", "## Error Checking")
    assert "Stage 4 ran" in checklist
    # The status example must model every stage, not a subset.
    status = _section(text, "## Status Updates", "## Search Process")
    m = re.search(r"```\n(.*?)```", status, re.S)
    assert m, "status section has no fenced example block"
    example = m.group(1)
    for stage in ("Stage 1", "Stage 2", "Stage 3", "Stage 4", "Stage 5"):
        assert stage in example, f"status example omits {stage}"
    # Enrichment reports its own result line, like every other stage.
    assert "✓ Stage 5.5:" in example


def test_researcher_prose_budgets_calls_and_forbids_probing():
    """2026-09-03 measurement: 16 no-script Bash calls per domain, every
    domain opening with an `echo PHILLIT_ROOT; mkdir; ls` probe the prose
    itself invited. Pin the replacements, scoped to their sections."""
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    assert "Do NOT probe it" in text
    batching = _section(text, "## One Bash Call Per Stage (REQUIRED)", "## BibTeX File Structure")
    assert "Budget per domain" in batching
    assert "| Stage 4 |" in batching
    assert "| Stage 6 web fetch |" in batching  # the fetch is mandatory for citability
    # The no-script rule is an instruction, not a description of the budget.
    assert "Do not make Bash calls that run no script" in batching
    assert "as many rounds as the results warrant" in batching
    # Dropped 2026-09-04: two validation runs on the shipped prose left split
    # follow-up rounds at baseline (3/15, 4/21 vs 2/20) while every other bar
    # cleared, so the "one follow-up call per round" rule was inert noise.
    assert "one follow-up call per round" not in text
    assert "not budgeted" in batching
    assert "Marked INCOMPLETE" in text  # prose reads the conditional summary line
    assert "valid-empty slug-file call" in batching  # the one exempt standalone call
    assert "result JSON" in batching  # pokes named as out of budget
    # The slug file rides the Stage 1 fetch call, and the valid-empty rule survives.
    stage1 = _section(text, "### Stage 1: SEP & IEP (Most Authoritative)", "### Stage 2: PhilPapers")
    fetch_block = [b for b in re.findall(r"```bash\n(.*?)```", stage1, re.S) if "fetch_sep.py" in b]
    assert len(fetch_block) == 1 and "encyclopedia_entries-domain-N.json" in fetch_block[0]
    assert '{"sep_entries": [], "iep_entries": []}' in stage1
    # The valid-empty case is a runnable block, not a `...` schematic, and it
    # spells out the concrete N so nobody writes a literal `domain-N` file.
    assert "encyclopedia_entries-domain-3.json" in stage1
    # Stage 5's DOI-search fallback writes a namespaced verify file; no bash
    # example may still show the collision-prone bare form. (The anti-pattern
    # is named in the CRITICAL prose on purpose, so scope this to the blocks.)
    assert "verify_<domain>_<citekey>.json" in text
    for block in re.findall(r"```bash\n(.*?)```", text, re.S):
        assert "verify_<citekey>.json" not in block, "a bash example still writes a bare verify file"
    # Stage 6's --stdin example actually pipes the text the prose says to pipe.
    assert "PAGE_TEXT" in text
    # The orchestrator always assigns literature-domain-N.bib (SKILL.md Phase 3).
    assert "literature-domain-compatibilism" not in text
    # Stage 3's worked example still chains all four searches in one block.
    stage3 = _section(text, "### Stage 3: Extended Academic Search", "### Consuming results without re-reading them")
    m = re.search(r"```bash\n(.*?)```", stage3, re.S)
    assert m, "Stage 3 has no fenced bash block"
    block = m.group(1)
    assert "No `python3 -c`" in stage3  # the read-once clause sits in Stage 3's own paragraph
    for script in ("s2_search.py", "search_openalex.py", "search_core.py", "search_arxiv.py"):
        assert script in block
    # Task 4's DOI-safe chain filenames and its batching sentence stay pinned.
    assert "cites_<domain>_{paper_id" not in text
    assert "cites_<domain>_seed1.json" in text
    assert "Separate is not optional: Stage 4 runs in every domain." in batching
    # The Stage 5.5 grep instruction is gone; the summary names the keys.
    stage55 = _section(text, "### Stage 5.5: Abstract Resolution", "### Stage 6: Web Search Fallback (When Needed)")
    assert "grep -c INCOMPLETE" not in stage55
    assert "INCOMPLETE entries:" in stage55


def test_stage4_skip_is_keyed_on_seeds_the_agent_holds():
    """Stage 4's case list partitioned the space only while an unenforced
    data assertion held: case 3 licensed a skip for "no usable seed" and
    then forbade "a skip while Stage 3's S2 search returned a hit". Those
    are exhaustive iff every hit carries an ID, and `s2_formatters.
    format_paper` writes `paper.get("paperId")` — a `null` is expressible,
    and in that state no case applied, in a REQUIRED stage. Pin the guard
    as a decision procedure over what the agent HOLDS."""
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    stage4 = _section(text, "### Stage 4: Citation Chaining (REQUIRED)",
                      "### Stage 5: Metadata Enrichment & Verification")
    # Assert on reflow-independent text: a Markdown re-wrap must not fail a
    # test whose subject is the guard's content.
    flat = " ".join(stage4.split())
    # License and deterrent are keyed on the same verb over the same object,
    # so they are exact complements: no gap and no overlap to rationalize.
    assert "no candidate you HOLD carries a Semantic Scholar paper ID or a DOI" in flat
    assert "Judge that on your holdings, not on what Stage 3 returned" in flat
    assert "`null` hands you no seed" in flat
    assert ("a skip while you hold any candidate carrying a Semantic Scholar "
            "paper ID or a DOI") in flat
    # Holdings must be enumerated before the case applies, or `<N>` evidences
    # nothing: a model may not inspect one file and call the domain seedless.
    # The inventory must precede ALL THREE cases, not just the zero case: an
    # agent holding one S2 id plus an uninspected DOI-bearing SEP entry would
    # otherwise pick "exactly one seed" and never trigger the mandate.
    assert "Before you pick a case, inventory your holdings" in flat
    assert "not the S2 hits alone" in flat
    assert "A Stage 1 bibliography entry can carry a DOI" in flat
    # Distinct WORKS, or two records of one paper count as two seeds.
    assert "Count DISTINCT WORKS: two records of the same paper are one" in flat
    # The inventory sits ahead of the case list in the section, not inside it.
    assert flat.index("inventory your holdings") < flat.index("Two or more usable seeds")
    # "Most foundational" ranks seeds; it must not gate them, or an ID-bearing
    # candidate judged tangential re-opens the no-case-applies state.
    assert "RANKS your usable seeds, it does not gate" in flat
    # ...and it names the ID KIND: a bare "an ID" re-licenses an
    # OpenAlex-only candidate the no-seed clause calls unusable.
    assert ("any candidate you hold with a Semantic Scholar paper ID or a DOI "
            "can serve as a seed") in flat
    assert "with an ID or a DOI" not in flat
    # The retired clause must not come back: it is the data assertion itself.
    assert "skip while Stage 3's S2" not in flat
    # The emitted NOTABLE_GAPS line keeps its shape (the checklist reads it).
    assert "Stage 4 skipped: no resolvable seeds (S2 status:" in stage4


def test_stage1_double_fetch_failure_has_an_evidenced_record():
    """Stage 1 gave a failed fetch one re-run and said nothing about the
    second failure — the one required-stage failure with no evidenced
    record, while Stage 4 mandates a line for exactly this class. The
    researcher then works Stages 1-4 without the encyclopedia text it was
    told it needs, and the deliverable does not say so."""
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    stage1 = _section(text, "### Stage 1: SEP & IEP (Most Authoritative)",
                      "### Stage 2: PhilPapers")
    flat = " ".join(stage1.split())
    assert "Stage 1 fetch failed: <slug> (status:" in flat
    assert "NOTABLE_GAPS" in flat
    # The slug stays listed: the barrier re-fetches it independently.
    assert "keep the slug listed" in flat
    # The status must be the FAILED SLUG's own: Stage 1's tail globs, so it can
    # print a sibling slug's "ok", and a model told to fill a placeholder from
    # an absent source may invent one. Both are licensed away explicitly.
    # Three licensed values, so "no status file" is never written of a file
    # that exists but carries no status line.
    assert "that slug's own status value" in flat
    assert "no status line in that slug's file" in flat
    assert "no status file" in flat
    assert "The tail globs" in flat
    assert "never copy one that is not for this slug" in flat
    assert "never infer or guess a status" in flat
    # And the checklist carries the row, as Stage 4's evidenced line does.
    checklist = _section(text, "## Before Submitting — Quality Checklist",
                         "## Error Checking")
    assert "Stage 1 fetch failed: …" in checklist


def test_every_researcher_json_path_goes_through_json_dir():
    """`36fa390` gave the stages a `JSON_DIR`; Stage 5's verification block
    and the canonical prologue that teaches the convention kept writing the
    long path. A file that teaches a convention and then departs from it in
    the stage issuing the most calls leaves a researcher two forms to
    pattern-match. One form only."""
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    # Whole-FILE scan, not just the bash fences: the original finding named
    # two offenders, and the second was the `--output` CRITICAL blockquote --
    # prose, the most-quoted line in the stage. A fence-only scan would pass
    # green on a regression there.
    # Match any PATH-LIKE use -- a `/` after the directory, or any shell
    # expansion of the review dir before it -- so `${REVIEW_DIR}/...`,
    # `"$REVIEW_DIR"/...` and an absolute path cannot slip past one spelling.
    # Bare prose naming the directory (no trailing `/`, no expansion) is fine.
    path_like = re.compile(
        r"intermediate_files/json/[\w.$*<{]")
    for i, line in enumerate(text.splitlines(), 1):
        if not path_like.search(line):
            continue
        assert "JSON_DIR=" in line, (
            f"line {i} writes a json path outside $JSON_DIR: {line!r}")
    # Stage 5's verification writes through JSON_DIR, and defines it first.
    stage5 = _section(text, "### Stage 5: Metadata Enrichment & Verification",
                      "### Stage 5.5: Abstract Resolution")
    verify_block = [b for b in re.findall(r"```bash\n(.*?)```", stage5, re.S)
                    if "--doi" in b]
    assert len(verify_block) == 1, "Stage 5 has no single DOI verification block"
    assert 'JSON_DIR="$REVIEW_DIR/intermediate_files/json"' in verify_block[0]
    assert 'mkdir -p "$JSON_DIR"' in verify_block[0]
    assert "$JSON_DIR/verify_<domain>_<citekey1>.json" in verify_block[0]
