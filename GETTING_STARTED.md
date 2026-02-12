# Getting Started

This guide covers setup for both local development and Claude's cloud environment.

## Quick Start: Claude Code Cloud

If you're using [Claude Code Cloud](https://docs.anthropic.com/en/docs/claude-code/cloud) (the sandboxed environment available through claude.ai or the Claude apps):

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
2. Remove `.env` from `.gitignore` in your fork
3. Create and commit your `.env` file with API keys
4. Use your private fork with Claude Code

---

## Local Setup

### Prerequisites

1. **[Claude Code CLI](https://claude.ai/code)** installed and configured
2. **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager
3. **Python 3.9+**

Clone this repository 

```bash
git clone https://github.com/AI-4-Phi/PhilReview.git
```
### Environment Setup

The Python environment is **automatically configured** when you start Claude Code in this repository.

### API Keys

The literature search scripts require API keys. Create a `.env` file in the project root with the variables listed below. Variables in `.env` take priority over your shell environment and are automatically loaded when Claude Code starts.

**Required:**
- **BRAVE_API_KEY**: Get one at https://brave.com/search/api/
- **CROSSREF_MAILTO**: Your email address (no signup required; used for CrossRef's polite pool)

**Recommended:**
- **S2_API_KEY**: Get one at https://www.semanticscholar.org/product/api (improves rate limits)
- **OPENALEX_EMAIL**: Your email address (no signup required; enables polite pool access)

**Verify your setup:**
```bash
python .claude/skills/philosophy-research/scripts/check_setup.py
```

## Your First Review

1. Start Claude Code in the project directory and select **Sonnet** as the model:
   ```bash
   cd PhilReview
   claude
   ```
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
| `literature-review-final.docx` | DOCX version (if pandoc is installed) |
| `literature-all.bib` | Aggregated bibliography (BibTeX) |
| `intermediate_files/` | Workflow artifacts (plan, per-domain BibTeX, sections, progress tracker) |

## Using the Bibliography

The `.bib` files are standard BibTeX and can be:
- Imported into reference managers (Zotero, BibDesk, Mendeley, etc.)
- Used with pandoc or LaTeX for formatted citations

**Tip:** The `.bib` files contain substantial metadata beyond what reference managers display — paper summaries, relevance assessments, importance ratings, and abstract sources are stored in BibTeX comments and `note`/`keywords` fields. Open the files in a text editor to access this information.

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
