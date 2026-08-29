"""In plugin mode, agents and skills run from the user's workspace: relative
repo paths like `../docs/conventions.md` resolve against the workspace's parent
directory, not the plugin root. Shared-doc references must use $PHILLIT_ROOT
(bridged into the session by the SessionStart bootstrap).

Review finding (2026-07-13): SKILL.md was fixed to the $PHILLIT_ROOT form
during the plugin conversion; the agent files were not.
"""

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


def test_researcher_told_not_to_write_either_derived_field():
    """The ban must cover BOTH barrier-owned fields, not just venue_status.

    The prompt banned hand-writing `venue_status` while saying nothing
    about `year_suffix` --
    even though the barrier owns both, re-derives both every run, and a
    hand-written `year_suffix` is the more dangerous of the two: one the
    stripper cannot reach can make a collision group look structurally
    complete and cost a cited work.
    """
    text = (REPO_ROOT / "agents" / "domain-literature-researcher.md").read_text(
        encoding="utf-8")
    assert "Never write a `venue_status` or `year_suffix` field yourself" in text
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
