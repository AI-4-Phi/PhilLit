# Philosophy Research Skill - Implementation Plan

**Status**: Planning complete, ready for implementation
**Last updated**: 2025-12-21

## Objective

Replace `WebSearch` in `domain-literature-researcher` and `citation-validator` agents with a Claude Skill that searches academic sources via APIs, reducing costs while maintaining citation quality.

## Reference Documents

| Document | Contents |
|----------|----------|
| [`references/api-specifications.md`](references/api-specifications.md) | Detailed API docs for S2, OpenAlex, arXiv, CrossRef, Brave, SEP |
| [`references/script-specifications.md`](references/script-specifications.md) | Full script specs with usage, input/output, implementation notes |
| [`references/skill-and-agent-integration.md`](references/skill-and-agent-integration.md) | SKILL.md template, agent workflow details, validation methods |

---

## Architecture Decision

**Approach**: Claude Skill (not MCP)
**Rationale**: Simpler to implement, sufficient for this use case, skills can be used by subagents via `skills:` frontmatter.

---

## File Structure

```
.claude/skills/philosophy-research/
├── SKILL.md                    # Skill definition
├── scripts/
│   ├── s2_search.py            # Semantic Scholar search
│   ├── s2_citations.py         # Citation traversal
│   ├── s2_batch.py             # Batch paper details
│   ├── s2_recommend.py         # Paper recommendations
│   ├── search_openalex.py      # OpenAlex broad academic search
│   ├── search_arxiv.py         # arXiv preprint search
│   ├── search_sep.py           # SEP discovery via Brave API
│   ├── fetch_sep.py            # SEP content extraction
│   ├── search_philpapers.py    # PhilPapers via Brave API
│   ├── verify_paper.py         # CrossRef verification
│   └── requirements.txt
└── references/
    ├── api-specifications.md          # Detailed API documentation
    ├── script-specifications.md       # Detailed script specs
    ├── skill-and-agent-integration.md # SKILL.md template, agent workflows
    ├── philpapers-categories.txt
    └── philosophy-journals.txt
```

---

## Search Sources

| Source | Method | Rate Limit | Use Case |
|--------|--------|------------|----------|
| SEP | Brave API + BeautifulSoup | 1/sec | Most authoritative; start here |
| PhilPapers | Brave API | 1/sec | Philosophy-specific papers |
| Semantic Scholar | Direct API | 1/sec | Primary paper source, citations |
| OpenAlex | pyalex library | 10/sec | Broad coverage (250M+ works) |
| arXiv | arxiv.py library | 3 sec delay | Preprints, AI ethics |
| CrossRef | Direct API | 50/sec | DOI verification |

**Details**: See [`references/api-specifications.md`](references/api-specifications.md)

---

## Scripts Summary

| Script | Purpose | Key Options |
|--------|---------|-------------|
| `s2_search.py` | Paper discovery | `--bulk`, `--year`, `--field` |
| `s2_citations.py` | Citation traversal | `--references`, `--citations`, `--influential-only` |
| `s2_batch.py` | Batch paper details | `--ids`, `--file` |
| `s2_recommend.py` | Find similar papers | `--positive`, `--negative` |
| `search_openalex.py` | Broad academic search | `--doi`, `--cites`, `--oa-only` |
| `search_arxiv.py` | arXiv preprints | `--category`, `--recent`, `--id` |
| `search_sep.py` | SEP discovery | `--limit`, `--all-pages` |
| `fetch_sep.py` | SEP content extraction | `--sections`, `--bibliography-only` |
| `search_philpapers.py` | PhilPapers search | `--limit`, `--recent` |
| `verify_paper.py` | DOI verification | `--title`, `--author`, `--doi` |

**Details**: See [`references/script-specifications.md`](references/script-specifications.md)

---

## SKILL.md Structure

```yaml
---
name: philosophy-research
description: Search philosophy literature across SEP, PhilPapers, and Semantic Scholar. Supports paper discovery, citation traversal, and recommendations. Verifies citations via CrossRef.
---
```

**Sections to include**:
1. Overview
2. Search Workflow (phases 1-6)
3. SEP Content Access
4. WebFetch Usage guidelines
5. Available Scripts table
6. Verification Requirements
7. Environment Setup

**Details**: See [`references/skill-and-agent-integration.md`](references/skill-and-agent-integration.md) for full template content.

---

## Agent Integration

### domain-literature-researcher

**Frontmatter changes**:
```yaml
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
```

**Search phases**:

| Phase | Source | Action |
|-------|--------|--------|
| 1 | SEP | `search_sep.py` → `fetch_sep.py` (preamble, bibliography, related) |
| 2 | PhilPapers | `search_philpapers.py` → cross-reference with SEP |
| 3 | Extended | S2, OpenAlex, arXiv for broader coverage |
| 4 | Citations | `s2_citations.py --both --influential-only` |
| 5 | Metadata | `s2_batch.py` for all collected IDs |

**When to prioritize specific sources**:
- **arXiv**: AI ethics, computational philosophy, recent preprints
- **OpenAlex**: Cross-disciplinary, open access, papers not in S2

**Details**: See [`references/skill-and-agent-integration.md`](references/skill-and-agent-integration.md) for full phase descriptions.

### citation-validator

**Frontmatter changes**:
```yaml
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
```

**Validation workflow**:
```
1. If DOI present:
   → verify_paper.py --doi → confirm matches
   → WebFetch doi.org/{doi} → confirm resolves

2. If arXiv ID present:
   → search_arxiv.py --id → verify exists

3. If no DOI/arXiv:
   → s2_search.py → find in S2
   → If not found: search_openalex.py → broader coverage
   → If not found: search_arxiv.py → preprints
   → If not found: search_philpapers.py / search_sep.py

4. Compare metadata: authors, year (±1), venue

5. Decision: KEEP / CORRECT / REMOVE
```

**Batch validation**:
- `s2_batch.py --ids "DOI:..."` (up to 500)
- OpenAlex batch for DOIs not in S2 (up to 50)

**Details**: See [`references/skill-and-agent-integration.md`](references/skill-and-agent-integration.md) for all 6 validation methods and full workflow.

---

## Implementation Order

| Step | Script/Task | Dependency |
|------|-------------|------------|
| 1 | Rate limiter module | None |
| 2 | `verify_paper.py` | Rate limiter |
| 3 | `s2_search.py` | Rate limiter |
| 4 | `s2_citations.py` | Rate limiter |
| 5 | `s2_batch.py` | Rate limiter |
| 6 | `s2_recommend.py` | Rate limiter |
| 7 | `search_openalex.py` | Rate limiter |
| 8 | `search_arxiv.py` | Rate limiter |
| 9 | `search_sep.py` | Rate limiter |
| 10 | `fetch_sep.py` | None |
| 11 | `search_philpapers.py` | Rate limiter |
| 12 | `SKILL.md` | All scripts |
| 13 | Test all scripts | All scripts |
| 14 | Update `domain-literature-researcher.md` | SKILL.md |
| 15 | Update `citation-validator.md` | SKILL.md |

---

## Environment Setup

```bash
export S2_API_KEY="your-key-here"        # Semantic Scholar (recommended)
export BRAVE_API_KEY="your-key-here"     # Required for SEP/PhilPapers
export CROSSREF_MAILTO="your@email.com"  # Required for CrossRef polite pool
export OPENALEX_EMAIL="your@email.com"   # Recommended for OpenAlex polite pool
pip install requests beautifulsoup4 lxml pyalex arxiv
```

---

## Success Criteria

### Semantic Scholar Scripts
- [ ] `s2_search.py` returns papers with abstracts and DOIs
- [ ] `s2_citations.py` traverses references and citations
- [ ] `s2_batch.py` handles up to 500 IDs
- [ ] `s2_recommend.py` returns relevant recommendations
- [ ] Rate limiter enforces 1 req/sec with exponential backoff

### CrossRef Scripts
- [ ] `verify_paper.py --doi 10.2307/2024717` returns verified metadata
- [ ] `verify_paper.py --title "..." --author Frankfurt` finds DOI
- [ ] `verify_paper.py` returns exit code 1 for non-existent papers
- [ ] Rate limiter adapts to `X-Rate-Limit-*` headers

### arXiv Scripts
- [ ] `search_arxiv.py "AI ethics"` returns papers with abstracts
- [ ] `search_arxiv.py --id "2301.00001"` returns specific paper
- [ ] `search_arxiv.py --category cs.AI --recent` filters correctly
- [ ] Rate limiter enforces 3 sec delay

### OpenAlex Scripts
- [ ] `search_openalex.py "free will"` returns papers with abstracts
- [ ] `search_openalex.py --doi "..."` returns verified metadata
- [ ] `search_openalex.py --cites "W..."` returns citing papers
- [ ] Rate limiter enforces 10 req/sec

### Brave Search Scripts
- [ ] `search_sep.py "free will"` returns SEP article URLs
- [ ] `search_sep.py` extracts `entry_name` for `fetch_sep.py`
- [ ] `search_philpapers.py "..."` returns PhilPapers URLs
- [ ] Rate limiter enforces 1 req/sec

### SEP Content Extraction
- [ ] `fetch_sep.py freewill` returns structured JSON
- [ ] `fetch_sep.py freewill --bibliography-only` extracts bibliography
- [ ] Bibliography parsing extracts author, year, title
- [ ] `fetch_sep.py` extracts related entries

### General
- [ ] All scripts return valid JSON
- [ ] Agents complete searches without WebSearch
- [ ] Agents use `fetch_sep.py` for SEP content (not WebFetch)
- [ ] Citation validator uses fallback chain (S2 → OpenAlex → arXiv)
- [ ] No fabricated citations possible
