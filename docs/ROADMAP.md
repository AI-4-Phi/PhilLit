# PhilLit Roadmap

**Open engineering work only.** Design sketches live in `docs/ideas/`;
`docs/known-issues/` holds only measurement scripts and their data, kept as the
reproduction path for decisions this file says to re-measure. Shipped work is
deleted from this file rather than marked done — the git log is the history. A
decision that is still binding belongs in `CLAUDE.md` or the module that owns
it, never here; an accepted residual belongs in the function it describes, so
that a recurrence is recognized where it would be read.

## Queue

The five entries below were read in `phillit-service` while adopting the
v0.5.9–v0.5.13 mirror, against this repo's tree at `191bde5`. None is
actionable from there — `engine/` is a mirror and a local edit is reverted by
the next re-vendor — and none blocked that mirror, which shipped and deployed
on 2026-09-04.

**`rc_surname` and `first_author_surname` are the same three tokens in two
files, and one of them says so in a docstring.** `check_evidence.rc_surname`
and `resolve_context.first_author_surname` both are, byte for byte,
`first_author_name(author_field).split(",")[0].strip()`, and `rc_surname`'s
docstring asserts the agreement in prose: "First author's surname as
resolve_context.first_author_surname computes it". That is the shape
`f0440fa`–`05efb94` spent five versions removing everywhere else, and
`CLAUDE.md` states the rule it breaks: "Sites keep their historic names as
**aliases to the shared objects** … never re-add a local copy." **The fix has
no cost**: both files already carry `from bib_identity import
first_author_name`, so the shared owner is one line each. Note what the owner
is NOT — `bib_identity.first_author_surname` returns pybtex prelast+last
(identity text, braces kept), while these two return the part before the first
comma (prose-matching text, and deliberately so: a comma or a brace in the
result defeats `find_cites` and the SEP passage match). Those are two rules,
and the second one currently has no owner.

**Stage 4's case list is exhaustive only while an unenforced data assertion
holds, and the stage is REQUIRED.** Case 3 licenses a skip for "no usable seed
… (rare — every Stage 3 S2 hit carries an ID; valid even if S2 errored)" and
then closes with "a skip while Stage 3's S2 search returned a hit [leaves the
domain incomplete]". Those two clauses partition the space correctly **iff**
every hit carries an ID. The script does not enforce that:
`s2_formatters.format_paper` writes `"paperId": paper.get("paperId")`, so a
paper object S2 returns without one formats to `"paperId": null` and the agent
genuinely holds no ID for a hit. In that state no case applies — no usable seed,
and the skip its own guard forbids — in a stage that runs in every domain,
seven concurrently. Not an observed failure; the reading is that the guard is
written as a claim about data where it wants to be a decision procedure, and
the one-clause fix is to key case 3 on what the agent HOLDS ("if no candidate
yields an ID or a DOI, that is a valid skip whatever Stage 3 returned — record
what you inspected") rather than on what Stage 3 returned.

**Stage 1's failed re-fetch is the one required-stage failure with no evidenced
record, and Stage 4 is the argument that it should have one.** "A fetch that
fails on your side still gets one re-run: you need its text and bibliography
for Stages 1–4." If the re-run also fails, nothing is said. The review is not
broken — the barrier re-fetches every listed slug itself — so what actually
happens is that the researcher works through Stages 1–4 without the
encyclopedia text it was told it needs, and nothing in the deliverable records
that it did. Stage 4 requires an evidenced `Stage 4 attempted: chaining
incomplete (…)` line for exactly this class of failure, and Stage 1's
equivalent would cost one sentence.

**Stage 5's verification block is the one file-writing block `36fa390` did not
convert to `JSON_DIR`.** It still writes `"$REVIEW_DIR/intermediate_files/json/
verify_<domain>_<citekey>.json"` and does its own `mkdir -p` on the long path,
as does the `--output` blockquote below it — while the "Other verification
tools" block immediately after it, and Stages 1, 3 and 4, all define and use
`JSON_DIR`. Functionally equivalent; the cost is that the file teaches a
convention and then departs from it in the stage that issues the most calls, so
a researcher pattern-matching its neighbours has two forms to choose from.

**`bib_fields`' docstring states the grammar it owns and does not mention `%`.**
It excludes `%` from `_NAME_RE` and from `bare`, but never says the scanner has
no comment handling — that a `%` inside an entry is not a comment and does not
run to end of line. Nothing downstream is at risk: pybtex rejects `%` inside an
entry in every form tested, including a bare `% note` with no brace, so the one
construct where the scanner and the regexes it replaced differ is exactly the
text `validate_bib_write` refuses and the barrier's own parse excludes. The
measured cost is reviewer time, which is why it is worth a clause: two
independent external reviewers of the service's mirror both filed the same
finding — a `%` carrying an entry's closing brace truncating the scan — and
both were reasoning from this docstring.

**Checked while filing the above, and NOT filed.** Recorded so they are not
re-found; each was a live candidate that did not survive reading the file.
(1) The budget's `Stage 5.5 enrichment | 1 (2 if you added entries after it)`
does NOT contradict "the bib file is FROZEN after enrichment" — FROZEN's own
bullet sanctions "adding a missed entry" by surgical `Edit`. Two independent
reviewers called it a contradiction, which is a readability datum rather than a
defect, and worth knowing given the audience is a model. (2) Case 3's
`<status from the Stage 3 tail>` is not undefined when a source fails: the
error-handling paragraph says Stage 3's tail names each expected file
explicitly, so a missing one prints a `grep: … No such file` line. (Stage 1 and
Stage 4's tails glob, which is the case that IS absent — but neither is quoted
by case 3.) (3) Stage 5.5 does carry a failure path: "a FAILED run — network
error, crash — does not count: re-run it". (4) The budget's
`Stage 5 verification | 1 per ~6 DOIs` is keyed on DOIs while Stage 5's work is
keyed on papers, so the DOI-less fallback's calls are uncounted — real, but the
table is explicitly approximate ("About ten calls") and says what it caps
("ceremony"), so it does not carry the risk of a skipped mandated call.
