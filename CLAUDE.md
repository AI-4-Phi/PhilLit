Repository to (a) author academic literature reviews using agent orchestration, and (b) improve these agents.

# Mode

**Production mode** (default): Assume user wants a literature review. Invoke `@research-proposal-orchestrator` immediately.

**Development mode**: Only if user explicitly asks to develop, improve, or test agents. Work on agent definitions in `.claude/agents/`.

# Objectives

**Priority order for literature reviews** (and agent development):

1. **Accurate** — Only cite verified papers; never fabricate references
2. **Comprehensive** — Cover all major positions and key debates
3. **Rigorous and concise** — Analytical depth, tight prose, specific gaps
4. **Reproducible** — Structured workflow, BibTeX files importable to Zotero

**NOT priorities**:
- ❌ Speed — Quality over fast completion
- ❌ Context efficiency — Use full context as needed; don't optimize for token savings

# File Structure

- `reviews/` — All existing and new literature reviews. Each review has its own subdirectory with an informative short name.
- `.claude/agents/` — Agent definitions for the literature review pipeline.
  - `ARCHITECTURE.md` — Design patterns and multi-file-then-assemble workflow.
  - `conventions.md` — Shared specifications (BibTeX format, citation style).
- `.claude/skills/philosophy-research/` — Structured API search scripts (Semantic Scholar, OpenAlex, arXiv, SEP, PhilPapers, CrossRef).

# Typical Usage: Literature Review

When asked to perform a new literature review:
1. Create a new directory in `reviews/` with an informative short name (e.g., `reviews/epistemic-autonomy-ai/`)
2. This new directory becomes the working folder for the review — save all files pertaining to this review there
3. Use the `research-proposal-orchestrator` agent to coordinate the review process

**Default agent:** `@research-proposal-orchestrator` (see Mode section above).

# Agents

**Core workflow (4 phases):**
- `@research-proposal-orchestrator` — Coordinates all phases, tracks progress, assembles outputs. **Default entry point.**
- `@literature-review-planner` — Decomposes research idea into domains and search strategies.
- `@domain-literature-researcher` — Uses `philosophy-research` skill for structured API searches; outputs valid BibTeX files.
- `@synthesis-planner` — Reads BibTeX files; designs tight outline emphasizing debates and gaps.
- `@synthesis-writer` — Writes sections one-by-one using relevant BibTeX subsets.

**Optional:**
- `@citation-validator` — Validates external BibTeX files (not needed for in-workflow use; APIs verify at search time).
- `@sota-review-editor` — Reviews draft for structure, clarity, and citation practice.
- `@novelty-assessor` — Produces executive assessment of novelty and positioning.

# Development

For agent architecture and design patterns, see `.claude/agents/ARCHITECTURE.md`.

Reference documentation:
- **Claude Agent Development Documentation** `https://code.claude.com/docs/en/sub-agents`
- **Claude Agents Best Practices** `https://www.anthropic.com/engineering/building-effective-agents`
- **Claude Skills Documentation** `https://code.claude.com/docs/en/skills`
- **Claude MCP Server Use Documentation** `https://code.claude.com/docs/en/mcp`

