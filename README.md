# Philo-SOTA

Multi-agent system for generating focused, insight-driven state-of-the-art literature reviews with verified bibliographies. Designed for research proposals where analytical depth, citation integrity, and reference-manager-ready outputs matter.

## Highlights

- **4-phase workflow**: Plan → Research (parallel) → Synthesize → Assemble
- **Structured API searches**: Semantic Scholar, OpenAlex, arXiv, SEP, PhilPapers, CrossRef
- **BibTeX-first**: Valid `.bib` files ready for Zotero import
- **Citation integrity**: Papers verified at search time via structured APIs
- **Resumable**: Progress tracked in `task-progress.md`
- **Context-efficient**: Parallel domain search, section-by-section writing

## How It Works

| Phase | Agent | Output |
|-------|-------|--------|
| 1. Plan | `@literature-review-planner` | `lit-review-plan.md` |
| 2. Research | `@domain-literature-researcher` (parallel) | `literature-domain-*.bib` |
| 3. Synthesize | `@synthesis-planner` → `@synthesis-writer` | `synthesis-outline.md`, section files |
| 4. Assemble | `@research-proposal-orchestrator` | `literature-review-final.md` |

**Optional**: `@sota-review-editor` (polish), `@novelty-assessor` (strategic assessment)

## Quick Start

```
I need a state-of-the-art literature review for [topic].

[Your research idea in 2-5 paragraphs]

Target: 3000-4000 words
Audience: Grant reviewers
```

See [GETTING_STARTED.md](GETTING_STARTED.md) for setup and detailed instructions.

## Output Structure

```
reviews/[topic]/
├── lit-review-plan.md              # Domain decomposition
├── literature-domain-*.bib         # BibTeX files (import to Zotero)
├── synthesis-outline.md            # Review structure
├── synthesis-section-*.md          # Individual sections
├── literature-review-final.md      # Complete review
└── task-progress.md                # Progress tracker
```

## Quality Standards

- No fabricated citations—only papers found via structured APIs
- Insight over coverage—key debates, recent work, concrete gaps
- Chicago author-date citations
- Balanced presentation of positions

## Development

For agent architecture: `.claude/agents/ARCHITECTURE.md`

For Claude instructions: `CLAUDE.md`

---

Inspired by [LiRA](https://arxiv.org/abs/2510.05138) multi-agent patterns.
