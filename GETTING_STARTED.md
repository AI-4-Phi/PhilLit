# Getting Started

PhilLit runs inside [Claude Code](https://docs.anthropic.com/en/docs/claude-code). There are three ways to use Claude Code — the local CLI, the Desktop app, and the Cloud environment — and they differ in how they handle network access, which matters because PhilLit calls a dozen external APIs during a review.

| Environment | Network access | Status |
|---|---|---|
| **CLI** (terminal) | Unrestricted | Fully supported |
| **Desktop app** | Unrestricted (runs locally) | Fully supported |
| **Cloud** (claude.ai) | Sandboxed — external APIs blocked by default | Not yet supported |

## Why Cloud doesn't work yet

Claude Code Cloud runs in a sandboxed VM where outbound network requests are restricted to a default allowlist (package registries, GitHub). PhilLit's search scripts call 12 external APIs via Python/Bash — these are blocked by the sandbox. There is currently no way for users to add custom domains to the cloud allowlist. We are tracking this and will update the guide when cloud support becomes viable.

---

## Local Setup (CLI or Desktop)

### Prerequisites

1. **[Claude Code](https://claude.ai/code)** — the CLI or [Desktop app](https://claude.ai/download)
2. **[uv](https://github.com/astral-sh/uv)** — fast Python package manager
3. **Python 3.9+**

### Clone and enter the repository

```bash
git clone https://github.com/AI-4-Phi/PhilLit.git
cd PhilLit
```

### Environment Setup

The Python environment is **automatically configured** when you start Claude Code in this repository. The startup hook creates a virtual environment, installs dependencies, and sets environment variables.

### API Keys

PhilLit searches academic databases using external APIs. Create a `.env` file in the project root with the variables listed below. Variables in `.env` take priority over your shell environment and are available to all processes including subagents.

**Required:**
- **BRAVE_API_KEY**: Get one at https://brave.com/search/api/ (free tier available)
- **CROSSREF_MAILTO**: Your email address (no signup required; used for CrossRef's polite pool)

**Recommended:**
- **S2_API_KEY**: Get one at https://www.semanticscholar.org/product/api (free; improves rate limits from 1 to 10 requests/sec)
- **OPENALEX_EMAIL**: Your email address (no signup required; enables polite pool access)

Example `.env` file:
```
BRAVE_API_KEY=your-brave-api-key
CROSSREF_MAILTO=your@email.com
S2_API_KEY=your-semantic-scholar-key
OPENALEX_EMAIL=your@email.com
```

**Verify your setup** (optional — Claude Code will run this before any review):
```bash
# Unix (macOS/Linux):
.venv/bin/python .claude/skills/philosophy-research/scripts/check_setup.py

# Windows (Git Bash):
.venv/Scripts/python .claude/skills/philosophy-research/scripts/check_setup.py
```

---

## Your First Review

1. Start Claude Code *in the project directory* (`PhilLit/`).
   ```bash
   cd PhilLit
   claude
   ```
   Select **Sonnet** as the model (type `/model`) to save on API costs.

2. Tell Claude what literature review you need:

```
I need a literature review for my research on [topic].

[1-3 paragraph description of the topic]
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
| `literature-review-[topic].md` | The complete literature review |
| `literature-review-[topic].docx` | DOCX version (if pandoc is installed) |
| `literature-[topic].bib` | Aggregated bibliography (BibTeX) |
| `intermediate_files/` | Workflow artifacts (plan, per-domain BibTeX, sections, progress tracker) |

## Using the Bibliography

The `.bib` files are standard BibTeX and can be:
- Imported into reference managers (Zotero, BibDesk, Mendeley, etc.)
- Used with pandoc or LaTeX for formatted citations

**Tip:** The `.bib` files contain substantial metadata beyond what reference managers display — paper summaries, relevance assessments, importance ratings, and abstract sources are stored in BibTeX comments and `note`/`keywords` fields. Open the files in a text editor to access this information.

## Resuming an Interrupted Review

If a review is interrupted, resume with:
```
Continue the review
```

Claude should find the incomplete review, detect the last completed phase and continue from there.

You can also be more specific:
```
Resume the literature review from task-progress.md in reviews/[your-topic]/
```

## Tips

- Mention that you would like a "literature review." Otherwise Claude will try to help you with your request without invoking the skill that orchestrates the literature review process of PhilLit
- Specify domains to include/exclude if you have preferences
- For interdisciplinary topics, note which non-philosophy sources matter
