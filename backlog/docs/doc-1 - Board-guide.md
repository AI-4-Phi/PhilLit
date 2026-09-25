---
id: doc-1
title: Board guide
type: guide
created_date: '2026-09-25 19:18'
updated_date: '2026-09-25 19:23'
---
PhilLit's work queue, holding open engineering work only. There is one card per open item, and the card is the only place that item's scope and status live. Every placement, order and "decided" on this board is a working assumption, revisable on Johannes's word.

## Reading a card

- **Title**: the work, named so it reads without the ID.
- **Project badge**: *why* the work matters, meaning which of PhilLit's aims it serves:
  - `Accuracy`: only verified papers are cited, on evidence that supports the claim, and no accuracy gate passes silently. This is objective 1 in CLAUDE.md.
  - `Delivery`: the user receives the whole review, with every promised file and every domain and section.
  - `Safety`: PhilLit never harms the user's machine or changes the user's own files, delivered reviews included.
  - `Consistency`: docs and prompts agree with each other and with the code. The agents are models, and they follow whatever they read.
  - `Platform`: PhilLit works in Claude Code Cloud, Linux, macOS and Windows.
- **Type**: what kind of work it is:
  - `bug`: shipped behaviour is wrong;
  - `guard`: a check nothing enforces yet, with no incident so far;
  - `feature`: a new capability;
  - `docs`: documentation or prompt wording;
  - `decision`: a ruling, then a small change;
  - `verify`: it needs a real machine to check.
- **Labels** (area): `barrier`, `hooks`, `agents`, `notes` (the research notes and the delivery split) and `workdir`. `test-run` marks work that a headless review run must validate. Runs share the 5-hour usage window, so batch the `test-run` cards into one run.
- **Body**: opens with **Why:** in plain words, then the scope, evidence and binding constraints, in the present tense. A card waiting on Johannes ends with **Decision needed:** and the options.

## Columns

- **Later**: parked on purpose. Never propose a Later card as a next step. Each card says what would bring it forward.
- **To Do**: the queue, in working order, top first. Cards with equal ordinals are peers: batch them into one release, so that phillit-service re-pins once.
- **In Progress**: being worked on now.
- **Needs Johannes**: waiting on his ruling. Each card names the decision and its options. Once he rules, the card moves to To Do, or to Done when the ruling itself closes it.
- **Done**: shipped. At a session wrap-up, clear Done cards last updated more than about two weeks ago off the board: `backlog task complete PL-n` moves each into `backlog/completed/`. The git log is the history.

## Fields

- **Order**: `ordinal` sets a card's place in its column, lowest first, so the top of To Do is next up. Leave gaps so a card can slot in between.
- **No priority.** A priority badge shares the card's top row with the ID, type and project, and with it the project badge truncates. Order is the ordinal alone.
- **Dependencies**: `--depends-on PL-n` marks a hard block. A blocked card keeps its place but is skipped until its dependency is Done.

## What does not go on a card

- A decision that is still binding belongs in CLAUDE.md or in the module that owns it. An accepted residual belongs in the function it describes, so that a recurrence is recognized where it would be read.
- Design sketches live in `docs/ideas/`. A card points at the sketch; it does not copy it.
- phillit-service tracks its own engine state: which PhilLit pin is vendored, what is deployed, and the service-side ports each pin needs. See its `docs/roadmap.md` (the engine-ports intake item) and `docs/engine-provenance.md`. Do not copy that state here: every copied fact went stale.
- Candidates that were checked and deliberately not filed are in doc-2, so that they are not found again.

## Conventions

- Refer to a card by ID and name ("PL-5, the abstract usability screen"), never by ID alone.
- New open work gets a card, never a list in a doc. Move a card as its work moves.
- Docs and code comments may point at an open card. When the card ships, find the pointers with `git grep PL-n` and rewrite each to state the fact.
- The board is ordinary files under `backlog/`. Commit them by explicit path, like any other file, and run `backlog doctor` after bulk changes.
- Edit cards through `backlog task edit` or the web UI. A hand edit must stay between the `SECTION:DESCRIPTION` markers and keep the frontmatter valid. A hand-edited `title:` leaves the filename slug stale; `git mv` the file.

## Commands (from the repo root)

- **Web UI**: `backlog browser`, then open http://127.0.0.1:6422. Ctrl+C stops it. Five columns fit a laptop screen only with the sidebar collapsed.
  - It listens on 127.0.0.1 only. From another machine, connect with `ssh -L 6422:127.0.0.1:6422 <host>`, run `backlog browser` in the repo in that session, and open the same URL locally.
- `backlog task list --plain`; `backlog task view PL-1 --plain`
- `backlog task edit PL-1 -s "In Progress"`
- `backlog task create "Title" -s "To Do" --type bug --project Accuracy -l barrier --ordinal 3500 --no-dod-defaults -a "" -d "..."`
- To create cards in bulk, drive `backlog task create` from Python with an argument list, never with shell strings.
