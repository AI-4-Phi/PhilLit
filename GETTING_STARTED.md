# Getting Started

## Prerequisites

You need [Claude Code](https://claude.ai/code) installed and configured.

## Environment Setup

The literature search scripts require API keys. Set these environment variables:

```bash
# Required
export BRAVE_API_KEY="your-key"      # For SEP/PhilPapers discovery
export CROSSREF_MAILTO="your@email"  # For CrossRef polite pool

# Recommended (improves rate limits)
export S2_API_KEY="your-key"         # Semantic Scholar
export OPENALEX_EMAIL="your@email"   # OpenAlex polite pool
```

**Get API keys:**
- Brave Search: https://brave.com/search/api/
- Semantic Scholar: https://www.semanticscholar.org/product/api

Verify your setup:
```bash
python .claude/skills/philosophy-research/scripts/check_setup.py
```

## Your First Review

1. Start Claude Code in this repository
2. Provide your research idea:

```
I need a state-of-the-art literature review for my research on [topic].

[2-5 paragraph description of your research idea]

Target: [word count, e.g., 3000-4000 words]
Audience: [e.g., grant reviewers, journal editors]
```

3. The orchestrator runs 4 phases automatically:
   - **Plan**: Decomposes into searchable domains
   - **Research**: Produces annotated BibTeX files
   - **Synthesize**: Designs outline, then writes sections
   - **Assemble**: Combines sections into final review

4. All outputs are saved to `reviews/[your-topic]/`

## Output Files

After completion, you'll have:

| File | Description |
|------|-------------|
| `lit-review-plan.md` | Domain decomposition and search strategy |
| `literature-domain-*.bib` | BibTeX files per domain (import to Zotero) |
| `synthesis-outline.md` | Review structure and citation selection |
| `literature-review-final.md` | The complete literature review |
| `task-progress.md` | Progress tracker (enables resume) |

## Importing to Zotero

Import the `.bib` files directly into Zotero:
1. File → Import...
2. Select `literature-domain-*.bib` files
3. The `note` fields contain paper summaries and relevance notes

## Resuming an Interrupted Review

If a review is interrupted, resume with:
```
Resume the literature review from task-progress.md in reviews/[your-topic]/
```

The orchestrator detects the last completed phase and continues.

## Execution Modes

**Autopilot** (default): Runs all phases automatically.

**Human-in-the-loop**: Add checkpoints for review:
```
Run the literature review with approval checkpoints after each phase.
```

## Tips

- Be specific about your research question and target audience
- Specify domains to include/exclude if you have preferences
- For interdisciplinary topics, note which non-philosophy sources matter
- Request "focused" (15-20 citations) vs "comprehensive" (25-35 citations) scope
