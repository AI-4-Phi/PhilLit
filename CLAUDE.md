Repository to (a) author academic literature reviews using agent orchestration, and (b) improve these agents.

# Mode

**Production mode** (default): When the user asks for a literature review, invoke the `/literature-review` skill to begin the 6-phase workflow.

**Development mode**: Only if user explicitly asks to develop, improve, or test agents/skills. Work on definitions in `.claude/agents/` and `.claude/skills/`.

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
- `.claude/skills/literature-review/` — Main orchestration skill for the 6-phase workflow.
- `.claude/skills/philosophy-research/` — Structured API search scripts (Semantic Scholar, OpenAlex, arXiv, SEP, PhilPapers, CrossRef).
- `.claude/agents/` — Specialized subagent definitions invoked by the literature-review skill.
- `.claude/docs/` — Shared specifications (conventions.md, ARCHITECTURE.md).
- `tests/` — pytest tests for API scripts and hooks.

# Typical Usage: Literature Review

When asked to perform a new literature review:
1. Invoke the `/literature-review` skill to begin the 6-phase workflow
2. The skill creates a new directory in `reviews/` with an informative short name (e.g., `reviews/epistemic-autonomy-ai/`)
3. The skill coordinates specialized subagents via the Task tool to complete all phases

# Workflow Architecture

**`/literature-review` skill** — Main entry point. Runs in main conversation with Task tool access. Coordinates the 6-phase workflow:
- Phase 1: Verify environment and determine execution mode
- Phase 2: Task tool invokes `literature-review-planner` — Decomposes research idea into domains
- Phase 3: Task tool invokes `domain-literature-researcher` ×N (parallel) — Uses `philosophy-research` skill for API searches; outputs BibTeX files
- Phase 4: Task tool invokes `synthesis-planner` — Reads BibTeX files; designs outline emphasizing debates and gaps
- Phase 5: Task tool invokes `synthesis-writer` ×N (parallel) — Writes sections using relevant BibTeX subsets
- Phase 6: Assemble final review files and move intermediate files

**Specialized subagents** (invoked via Task tool, cannot spawn other subagents):
- `literature-review-planner` — Decomposes research idea into domains and search strategies
- `domain-literature-researcher` — Searches academic sources, produces BibTeX with rich annotations
- `synthesis-planner` — Designs tight outline from collected literature
- `synthesis-writer` — Writes individual sections of the review

# Development

For agent architecture and design patterns, see `.claude/docs/ARCHITECTURE.md`.

## Testing

Run tests with: `pytest tests/`

## Principles

- **Keep the repository lean** — Do not keep files only for reference if the functionality is already documented elsewhere (e.g., in `pyproject.toml`). Remove deprecated files rather than marking them as such.
- **Single source of truth** — Dependencies in `pyproject.toml`, agent definitions in `.claude/agents/`, skill definitions in `.claude/skills/`. Avoid duplicating information across files.
- **Simple and concise** — Prefer simple solutions. Keep agent/skill instructions brief and effective. Avoid verbosity.
- **Verify assumptions empirically** — Test bash patterns and environment behavior in actual subagent context before codifying. Don't assume documentation is accurate.
- **Cross-platform** — Implementations must work in Claude Code Cloud, Linux, macOS. Use forward slashes in paths.

## Adding Python Dependencies

When adding a new Python package import, update these files:

1. **`pyproject.toml`** — Add the package to `dependencies` list
2. **`uv.lock`** — Regenerate with `uv lock`
3. **`.claude/hooks/setup-environment.sh`** — Add `check_package` call if the package is required for agents/skills to function
4. **`.claude/skills/philosophy-research/scripts/check_setup.py`** — Add to `required_packages` dict only if the package is specifically for the philosophy-research skill
