# Getting Started

## Prerequisites

1. **[Claude Code](https://claude.ai/code)** installed and configured
2. **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager
3. **Python 3.9+**

### Install uv

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Or via package managers:
```bash
# macOS
brew install uv

# pipx
pipx install uv
```

## Environment Setup

### Automatic Setup (Recommended)

The Python environment is **automatically configured** when you start Claude Code in this repository:

1. Clone this repository
2. Start Claude Code: `claude-code` or open in your IDE
3. The SessionStart hook automatically:
   - Creates a virtual environment (`.venv/`)
   - Installs all dependencies from `pyproject.toml`
   - Activates the environment

Setup runs silently on success. If there's an error (e.g., `uv` not installed, missing packages), Claude will be notified and can help you resolve it.

### Manual Setup (Optional)

If you want to set up manually:

```bash
# Sync environment (creates .venv and installs dependencies)
uv sync

# Activate it
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows
```

### API Keys

The literature search scripts require API keys. Either set these as shell environment variables manually or the create a `.env` file in the project root:

```bash
cp .env.example .env
# Edit .env with your values
```

The `.env` file should contain:

```bash
# Required
BRAVE_API_KEY=your-key        # For SEP/PhilPapers discovery
CROSSREF_MAILTO=your@email    # For CrossRef polite pool

# Recommended (improves rate limits)
S2_API_KEY=your-key           # Semantic Scholar
OPENALEX_EMAIL=your@email     # OpenAlex polite pool
```

Variables in `.env` take priority over your shell environment and are automatically loaded when Claude Code starts.

**Get API keys:**
- Brave Search: https://brave.com/search/api/
- Semantic Scholar: https://www.semanticscholar.org/product/api

**Verify your setup:**
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

3. The `/literature-review` skill coordinates 6 phases automatically:
   - **Phase 1**: Verify environment and choose execution mode
   - **Phase 2**: Decompose into searchable domains
   - **Phase 3**: Research each domain, produce annotated BibTeX files
   - **Phase 4**: Design synthesis outline
   - **Phase 5**: Write review sections
   - **Phase 6**: Assemble final review and aggregate bibliography

4. All outputs are saved to `reviews/[your-topic]/`

## Output Files

After completion, you'll have:

| File | Description |
|------|-------------|
| `literature-review-final.md` | The complete literature review |
| `literature-all.bib` | Aggregated bibliography (import to Zotero) |
| `intermediate_files/` | Workflow artifacts (plan, per-domain BibTeX, sections, progress tracker) |

## Importing to Zotero

Import the aggregated bibliography into Zotero:
1. File → Import...
2. Select `literature-all.bib` (or individual `literature-domain-*.bib` files from `intermediate_files/`)
3. The `note` fields contain paper summaries and relevance notes

## Resuming an Interrupted Review

If a review is interrupted, resume with:
```
Resume the literature review from task-progress.md in reviews/[your-topic]/
```

The skill detects the last completed phase and continues from there.

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
