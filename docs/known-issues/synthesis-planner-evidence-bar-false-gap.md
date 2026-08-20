# Synthesis Planner Converts an Evidence Bar into a False "Gap in the Literature" Claim

**Observed**: 2026-08-19, downstream service, first production kimi-k3 run on
the evidence-tier engine (service review `42b029364b084b6b`; the service's
acceptance quality read found it)
**Severity**: High — produces confident false negative-existence claims in
the delivered text, the exact reader-facing harm the evidence tier was built
to prevent
**Status**: FIXED 2026-08-19 — the convention below shipped the same day the
issue was filed: `agents/synthesis-planner.md` now carries the
evidence-bar-is-never-a-claim-about-the-literature rule (verified-substitute
routing first, silent omission second, absence claims licensed only when no
relevant entry exists at ANY tier; the seeding phrase "note the gap if the
work would have been important" is gone, and barred-work losses are reported
to the orchestrator, never into review-facing content), and
`agents/synthesis-writer.md` bans unplanned negative-existence claims
(outline-licensed only — covers the observed third, writer-invented
instance). Both pinned by `tests/test_agent_definitions.py`. Reaches the
service at its next re-vendor pin.

## Summary

When every source covering a question is citation-barred (EVIDENCE-NONE),
the synthesis planner sometimes converts the bar into a claim that the
LITERATURE is silent — "a gap the reviewed literature leaves unaddressed" —
rather than routing to a verified substitute or saying nothing. In the
observed run the corpus held BOTH sides of the allegedly-open question:
`nguyen2020arts` (EVIDENCE-NONE, correctly barred) argued games-to-life
transfer, and `holowchak2007games` (EVIDENCE-ABSTRACT, abstract-attested,
fully licensed for content claims) bears directly on it — and appeared 0×
in the outline and 0× in every section. The false gap claim shipped 3× in
the final text.

## Mechanism (on the record in the artifact)

The outline annotated its own move: "nguyen2020arts omitted for evidence
reasons ... the games-to-life transfer question is flagged as an open gap."
For two other EVIDENCE-NONE areas in the same run the planner did the right
thing — routed to verified substitutes (Marx 1844 → Elster 1986; Polanyi →
Dreyfus 2004), which the writer executed correctly — so the convention is
partially learned, not absent. The low-effort writer then transcribed the
gap claim twice, stripped the disclosing parenthetical, and added a third
unplanned instance in the Conclusion.

Two aggravating notes: (a) the abstract-attested source covering the
question was dropped at PLANNING, so no downstream stage could recover it;
(b) the planner is deliberately outside the cost-override set (validated
kimi recipe parity), so it ran at default effort — this is a convention
gap, not an effort artifact, and the fix should hold for Sonnet runs too.

## Fix direction

A synthesis-planner convention with teeth: **an evidence bar is never a
claim about the literature.** When EVIDENCE-NONE sources cover a question,
either (1) a verified substitute carries the content (the pattern the
planner already applies inconsistently), or (2) the topic is omitted
silently — "the literature does not address X" may only be asserted when
the corpus actually lacks X-relevant entries at any tier. Lineage:
`incomplete-exclusion-unfollowable.md` (SHIPPED) fixed the exclusion rule
itself; this is the residual failure mode of the shipped design's
planning-stage bar. Downstream mirror:
phillit-service `docs/known-issues/synthesis-planner-evidence-bar-false-gap.md`
(the service ports the fix; its intake item is the service's roadmap
item 26).
