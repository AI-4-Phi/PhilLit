# `task-progress.md` Written at Repo Root, Resumed from `reviews/`

**Observed**: 2026-06-19, during permissions investigation
**Severity**: Low (no data loss; caused a stray permission prompt, since worked around)
**Status**: Resolved 2026-06-24 — see "Resolution" below

## Summary

The `literature-review` skill writes its progress tracker, `task-progress.md`, to the **repo root**, but the skill's resume logic **scans `reviews/*/task-progress.md`** to locate an interrupted review. The write location and the resume location disagree.

## Root Cause

`SKILL.md:17` instructs:

> At workflow start, create `task-progress.md` in the working directory:

This runs at the very start of the workflow — **before** Phase 2 establishes the per-review subdirectory `reviews/[project-short-name]/`. With no review directory yet, "the working directory" resolves to the repo root, so the tracker is created at `./task-progress.md`.

Meanwhile, the resume/orphan-detection logic expects it inside the review folder:

> `SKILL.md:107`: (If you suspect an orphaned review from a previous interruption, scan `reviews/*/task-progress.md` to locate it.)

## Consequences

1. **Permission prompt** — the root-level write was not covered by the `Write(reviews/**)` allow rule, so it triggered a prompt. Worked around on 2026-06-19 by adding `Write(task-progress.md)` / `Edit(task-progress.md)` to `.claude/settings.json`.
2. **Resume can miss interrupted reviews** — a tracker left at the repo root is not found by a `reviews/*/task-progress.md` scan, so an orphaned review may not be detected on resume.
3. **Root-directory clutter** — a stray `task-progress.md` accumulates at the project root rather than living with the review it describes.

## Proposed Fix

Make the tracker live inside the review folder, consistent with the resume scan:

- Determine `reviews/[project-short-name]/` **first** (or as the first step once the topic is known), then create `reviews/[project-short-name]/task-progress.md` there.
- Update `SKILL.md:17` to name the in-review path explicitly instead of "the working directory."
- Once the tracker is always under `reviews/`, the `Write(task-progress.md)` / `Edit(task-progress.md)` rules added as the workaround become redundant and can be removed (the path is already covered by `Write(reviews/**)` / `Edit(reviews/**)`).

## Notes

The chicken-and-egg wrinkle: the review directory name is derived during Phase 2, but the tracker is meant to exist from "workflow start." The fix needs to either (a) move tracker creation to just after the review directory is named, accepting that the first moments of Phase 1/2 run untracked, or (b) establish the review directory earlier in the flow.

## Resolution

Fixed via option (a). The review directory is established in Phase 1, step 7 (`mkdir -p reviews/[project-short-name]`), so tracker creation was moved to run immediately after:

- `SKILL.md` "Critical: Task List Management" now instructs creating the tracker at `reviews/[project-short-name]/task-progress.md` once the review directory exists, and notes that the first setup steps of Phase 1 (environment check, resume detection, mode choice) run untracked.
- `SKILL.md` Phase 1, step 7 now explicitly creates the tracker right after writing the `.active-review` pointer.
- The workaround `Write(task-progress.md)` / `Edit(task-progress.md)` rules were removed from `.claude/settings.json`; the path is now covered by the existing `Write(reviews/**)` / `Edit(reviews/**)` rules.

The resume scan (`reviews/*/task-progress.md`) and `ARCHITECTURE.md` already assumed the in-review location, so they needed no change. Do not re-add the root-level permission rules — they are redundant under the corrected write location.
