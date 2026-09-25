---
id: doc-1
title: Board guide
type: guide
created_date: '2026-09-25 19:18'
updated_date: '2026-09-25 19:23'
---
PhilLit's work queue, holding open engineering work only. There is one card per open item, and the card is the only place that item's status, open questions and next step live; design detail lives in the documents it cites. Every placement, order and "decided" on this board is a working assumption, revisable on Johannes's word.

## Reading a card

- **Title**: the work, named so it reads without the ID.
- **Project badge**: *why* the work matters, meaning the outcome at stake. These are not CLAUDE.md's four objectives one to one; add a value (say, `Coverage` or `Rigor`) to `projects` in `backlog/config.yml` when a card needs one:
  - `Accuracy`: only verified papers are cited, on evidence that supports the claim, and no accuracy gate passes silently. This is objective 1 in CLAUDE.md.
  - `Delivery`: the user receives the whole review, with every promised file and every domain and section.
  - `Safety`: PhilLit never harms the user's machine or changes the user's own files, delivered reviews included.
  - `Consistency`: docs and prompts agree with each other and with the code. The agents are models, and they follow whatever they read.
  - `Platform`: PhilLit works in Claude Code Cloud, Linux, macOS and Windows.
- **Type**: what kind of work it is:
  - `bug`: shipped code behaves wrongly;
  - `guard`: a check nothing enforces yet, with no incident so far;
  - `feature`: a new capability;
  - `docs`: documentation or prompt wording;
  - `decision`: the ruling is the main work, and the change after it is small;
  - `verify`: it needs a real machine to check.
- **Labels**: optional area labels for recurring subsystems: `barrier`, `hooks`, `agents`, `notes` (the research notes and the delivery split) and `workdir`. A card may carry none. `test-run` marks work that a headless review run must validate. Runs share the account's usage window (CLAUDE.md, Headless review runs), so batch the `test-run` cards into one run.
- **Body**: opens with **Why:** in plain words, then the scope, evidence and binding constraints, in the present tense. A card waiting on Johannes ends with **Decision needed:** and the options. Such a card sits in Needs Johannes whatever its type.

## Columns

- **Later**: parked on purpose. Each card says what would bring it forward. Never propose a Later card as a next step unless that trigger has fired; when it has, say so.
- **To Do**: the queue, in working order, top first. Cards with equal ordinals are peers: batch them into one release, so that phillit-service re-pins once.
- **In Progress**: being worked on now.
- **Needs Johannes**: waiting on his ruling. Each card names the decision and its options. Once he rules, the card moves to To Do, or to Done when the ruling itself closes it.
- **Done**: shipped. At a session wrap-up, take Done cards off the board with `backlog task complete PL-n`, which files each in `backlog/completed/`. Keep them there. backlog numbers a new card as the highest ID in `tasks/` and `completed/` plus one, so deleting the highest card (`git rm`) or archiving it (`backlog task archive`) makes the next card reuse an ID that code comments and commits already cite. `completed/` is that ID register and never part of the queue; the git log is the history.

## Fields

- **Order**: `ordinal` sets a card's place in its column, lowest first, so the top of To Do is next up. Leave gaps so a card can slot in between.
- **No priority.** A priority badge shares the card's top row with the ID, type and project, and with it the project badge truncates. Order is the ordinal alone.
- **Dependencies**: `--depends-on PL-n` marks a hard block. A blocked card keeps its place but is skipped until its dependency is Done.

## What does not go on a card

- A decision that is still binding belongs in CLAUDE.md or in the module that owns it. An accepted residual belongs in the function it describes, so that a recurrence is recognized where it would be read.
- Design sketches live in `docs/ideas/`. A card points at the sketch; it does not copy it.
- phillit-service tracks its own engine state: which PhilLit pin is vendored, what is deployed, and the service-side ports each pin needs. See its own board, `phillit-service/backlog/`, where PS-26 (engine ports from PhilLit: standing intake) is the intake, and its `docs/engine-provenance.md` for the pins and run records. Do not copy that state here: every copied fact went stale.
- Candidates that were checked and deliberately not filed are in doc-2, so that they are not found again.

## Conventions

- Refer to a card by ID and name ("PL-n, <its short name>"), never by ID alone.
- New open work gets a card, never a list in a doc. Move a card as its work moves.
- Docs and code comments may point at an open card. When the card ships, find the pointers with `git grep PL-n` and rewrite each to state the fact.
- The board is ordinary files under `backlog/`. Commit them by explicit path, like any other file, and run `backlog doctor` after bulk changes.
- Edit cards through `backlog task edit` or the web UI. A hand edit to a description stays between the `SECTION:DESCRIPTION` markers, and a frontmatter edit must keep the YAML valid. A changed title, whether hand-edited or set with `--title`, leaves the filename slug stale; `git mv` the file.

## Commands (from the repo root)

These need the `backlog` CLI (Homebrew `backlog-md` or npm `backlog.md`); the board was set up with 1.52.0.

- **Web UI**: `backlog browser`, then open http://127.0.0.1:6422. Ctrl+C stops it. Five columns fit a laptop screen only with the sidebar collapsed.
  - It listens on 127.0.0.1 only. From another machine, connect with `ssh -L 6422:127.0.0.1:6422 <host>`, run `backlog browser` in the repo in that session, and open the same URL locally.
- `backlog task list --plain`; `backlog task view PL-n --plain`
- `backlog task edit PL-n -s "In Progress"`
- `backlog task create "Title" -s "To Do" --type bug --project Accuracy -l barrier --ordinal 3500 --no-dod-defaults -a "" -d "..."`
- To create cards in bulk, drive `backlog task create` from Python with an argument list, never with shell strings.
