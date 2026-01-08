# Getting Started

This guide covers setup for both local development and Claude's cloud environment.

## Quick Start: Claude Cloud Environment

If you're using Claude Code in the cloud (via claude.ai, the Claude desktop app, or the Claude mobile app):

1. **Fork this repository** (optional but recommended for persistence)
2. **Open in Claude Code** via the GitHub integration
3. **Provide your API keys** by pasting them in the chat:

Tell Claude:
```
Please create a .env file with these keys:

BRAVE_API_KEY=your-brave-api-key
CROSSREF_MAILTO=your@email.com
S2_API_KEY=your-semantic-scholar-key
OPENALEX_EMAIL=your@email.com
```

**Note:**
- The environment is ephemeral—`.env` files are not persisted between sessions
- You'll need to provide API keys at the start of each new session

**Alternative: Persistent keys via private fork**
1. Fork this repo and make it private
2. Add `.env` to your fork (it's already in `.gitignore`)
3. Use your private fork with Claude Code

---

## Local Setup

### Prerequisites

1. **[Claude Code CLI](https://claude.ai/code)** installed and configured
2. **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager
3. **Python 3.9+**

Clone this repository 

```bash
git clone https://github.com/marco2meyer/philo-sota.git
```
### Environment Setup

The Python environment is **automatically configured** when you start Claude Code in this repository.

### API Keys

The literature search scripts require API keys. Create a `.env` file in the project root:

```bash
cp .env.example .env
# Edit .env with your values
```

See `.env.example` for required and recommended variables. Variables in `.env` take priority over your shell environment and are automatically loaded when Claude Code starts.

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
I need a literature review for my research on [topic].

[1-3 paragraph description of your research idea]
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

Then use [Zotero's function `Find Full Text`](https://guides.library.oregonstate.edu/zotero/fulltextresolver) to download PDFs.

## Resuming an Interrupted Review

If a review is interrupted, resume with:
```
Resume the literature review from task-progress.md in reviews/[your-topic]/
```

The skill detects the last completed phase and continues from there.

## Tips

- Be specific about your research question and target audience
- Specify domains to include/exclude if you have preferences
- For interdisciplinary topics, note which non-philosophy sources matter
- Request "focused" (15-20 citations) vs "comprehensive" (25-35 citations) scope
