---
id: PL-31
title: Abstract corroboration budget is fixed at 180 s and strands the last domains
status: Done
assignee: []
created_date: '2026-11-17T11:16:00Z'
updated_date: '2026-11-19T13:00:00Z'
labels:
  - barrier
  - test-run
dependencies: []
type: bug
project: Accuracy
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** the abstract-corroboration pass in the evidence barrier stops at a fixed 180 s wall clock (`CORROBORATION_PASS_DEADLINE_SECONDS` in `skills/literature-review/scripts/evidence_barrier.py`), however many candidates a review has. A large review cannot fit. In a 2026-11-17 run (7 domains, 198 entries, 177 candidates, PhilLit 0.5.47) the pass corroborated 129, then 127 on a re-run, and stranded 48, then 50 entries as `corroboration_deadline`, with `transport_failed` and `probe_error` both 0. The pass probes in domain order, so the stranded entries were the last domains (manipulation and oversight). They dropped to EVIDENCE-EXISTENCE, so the writers could cite them but not say what they argue. A re-run does not help: each run starts its clock afresh and strands the same tail. SKILL.md (Phase 3 step 6, the `abstract_corroboration` paragraph) tells the orchestrator that a re-run restores the tier, which is wrong when the count repeats with zero errors.

**Evidence:** raising the constant to 360 s for one run, then restoring it, corroborated all 177 candidates (`corroboration_deadline` 0). Tiers went from ABSTRACT 127 / EXISTENCE 55 to ABSTRACT 177 / EXISTENCE 9. The pass ran at about 0.7 candidates per second.

**Scope:** make the budget scale with the candidate count (for example a per-candidate allowance with a floor), or keep corroboration results across runs so that a re-run resumes where the last one stopped. Keep the whole barrier under the 600 s Bash ceiling the skill relies on, or say what the orchestrator does when it is not. Correct the SKILL.md re-run advice to match. The consecutive-error breaker stays as it is.
<!-- SECTION:DESCRIPTION:END -->
