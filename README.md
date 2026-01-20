# PhilReview

PhilReview is a multi-agent system for generating focused, insight-driven literature reviews with verified bibliographies. Designed for philosophy research proposals where analytical depth, citation integrity, and reference-manager-ready outputs matter.

## Highlights

- **6-phase workflow**: Environment → Plan → Research → Outline → Write → Assemble
- **Parallel execution**: Domain researchers and section writers run concurrently
- **Skill-based orchestration**: `/literature-review` skill coordinates specialized subagents
- **Structured API searches**: Semantic Scholar, OpenAlex, arXiv, SEP, PhilPapers, CrossRef
- **BibTeX-first**: Valid `.bib` files ready for Zotero import
- **Citation integrity**: Papers verified at search time via structured APIs
- **Resumable**: Progress tracked in `task-progress.md`
- **Context-efficient**: Per-domain search, section-by-section writing

## How It Works

The `/literature-review` skill orchestrates 6 phases, invoking specialized subagents via the Task tool:

| Phase | Subagent | Output |
|-------|----------|--------|
| 1. Environment | (skill) | Verify setup, choose mode |
| 2. Plan | `literature-review-planner` | `lit-review-plan.md` |
| 3. Research | `domain-literature-researcher` ×N (parallel) | `literature-domain-*.bib` |
| 4. Outline | `synthesis-planner` | `synthesis-outline.md` |
| 5. Write | `synthesis-writer` ×N (parallel) | `synthesis-section-*.md` |
| 6. Assemble | (skill) | `literature-review-final.md`, `literature-all.bib` |

## Quick Start

```
I need a literature review for [topic].

[Your research idea in 2-5 paragraphs]
```

See [GETTING_STARTED.md](GETTING_STARTED.md) for setup and detailed instructions.

## Output Structure

```
reviews/[topic]/
├── literature-review-final.md      # Complete review
├── literature-all.bib              # Aggregated bibliography (import to Zotero)
└── intermediate_files/
    ├── json/                       # API response files (archived)
    ├── lit-review-plan.md          # Domain decomposition
    ├── literature-domain-*.bib     # Per-domain BibTeX files
    ├── synthesis-outline.md        # Review structure
    ├── synthesis-section-*.md      # Individual sections
    └── task-progress.md            # Progress tracker
```

## Quality Standards

- No fabricated citations—only papers found via structured APIs
- Insight over coverage—key debates, recent work, concrete gaps
- Chicago author-date citations
- Balanced presentation of positions

## Development

For agent architecture: `.claude/docs/ARCHITECTURE.md`

For Claude instructions: `CLAUDE.md`

---

Inspired by [LiRA](https://arxiv.org/abs/2510.05138) multi-agent patterns.
