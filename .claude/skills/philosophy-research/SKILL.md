---
name: philosophy-research
description: Search philosophy literature across SEP, PhilPapers, Semantic Scholar, OpenAlex, and arXiv. Supports paper discovery, citation traversal, and recommendations. Verifies citations via CrossRef.
allowed-tools: Bash, Read, Write, Grep, WebFetch
---

# Philosophy Research Skill

Search and retrieve academic philosophy literature using structured APIs instead of WebSearch.

## When to Use This Skill

Use this skill when:
- Searching for philosophy papers, articles, or concepts
- Accessing SEP (Stanford Encyclopedia of Philosophy) content
- Finding citations and references for papers
- Verifying that a paper exists with correct metadata
- Building bibliographies for literature reviews

## Search Workflow

### Phase 1: SEP (Most Authoritative)

```bash
# Discover relevant SEP articles
python scripts/search_sep.py "free will"

# Extract structured content from an entry
python scripts/fetch_sep.py freewill --sections "preamble,1,2,bibliography"
python scripts/fetch_sep.py freewill --bibliography-only
```

Parse the bibliography for foundational works, then search for those papers.

### Phase 2: PhilPapers

```bash
# Philosophy-specific paper search
python scripts/search_philpapers.py "epistemic injustice"
python scripts/search_philpapers.py "virtue epistemology" --recent
```

### Phase 3: Extended Academic Search

```bash
# Semantic Scholar - broad academic search
python scripts/s2_search.py "moral responsibility" --field Philosophy --year 2015-2025

# OpenAlex - 250M+ works, cross-disciplinary
python scripts/search_openalex.py "consciousness" --year 2020-2024 --min-citations 10

# CORE - 431M+ research outputs, 46M full texts, excellent for abstracts
python scripts/search_core.py "epistemic injustice" --year 2020-2024
python scripts/search_core.py --doi "10.1111/nous.12191"
python scripts/search_core.py --title "Freedom of the Will" --author "Frankfurt"

# arXiv - preprints, AI ethics, recent work
python scripts/search_arxiv.py "AI alignment ethics" --category cs.AI --recent
```

**Note**: CORE API is rate-limited to 5 requests per 10 seconds (free tier, no API key required).

### Phase 4: Citation Traversal

```bash
# Get references and citations for a paper
python scripts/s2_citations.py PAPER_ID --both --influential-only

# Find recommendations based on seed papers
python scripts/s2_recommend.py --positive "PAPER_ID1,PAPER_ID2"
```

### Phase 5: Batch Details

```bash
# Efficiently fetch metadata for multiple papers
python scripts/s2_batch.py --ids "PAPER_ID1,PAPER_ID2,DOI:10.xxx/yyy"
```

### Phase 5.5: Abstract Resolution

After gathering papers, resolve abstracts for entries that lack them:

```bash
# Resolve abstract from multiple sources (S2 → OpenAlex → CORE)
python scripts/get_abstract.py --doi "10.1111/nous.12191"
python scripts/get_abstract.py --title "Freedom of the Will" --author "Frankfurt" --year 1971
python scripts/get_abstract.py --s2-id "abc123def"
```

Fallback chain: S2 → OpenAlex → CORE. Output includes `status`, `abstract`, and `abstract_source`.

For batch processing, use `enrich_bibliography.py` (in literature-review scripts):
```bash
python .claude/skills/literature-review/scripts/enrich_bibliography.py input.bib
```

### Phase 5.6: Encyclopedia Context Extraction (Optional)

For important papers, extract how they're discussed in authoritative philosophy encyclopedias:

```bash
# Extract SEP citation context for a specific paper
python scripts/get_sep_context.py freewill --author "Frankfurt" --year 1971
python scripts/get_sep_context.py freewill --author "Fischer" --year 1998 --coauthor "Ravizza"

# Extract IEP citation context
python scripts/get_iep_context.py freewill --author "Frankfurt" --year 1971
```

### Phase 6: Verification

```bash
# Verify a paper exists via CrossRef
python scripts/verify_paper.py --title "The Title" --author "Smith" --year 2020
python scripts/verify_paper.py --doi "10.1093/mind/fzv123"
```

## SEP Content Access

**Use `fetch_sep.py` instead of WebFetch for SEP articles.**

`fetch_sep.py` provides structured extraction:
- Preamble (abstract/introduction)
- Individual sections by number
- Bibliography with parsed author/year/title
- Author and publication dates

```bash
# Get specific sections
python scripts/fetch_sep.py compatibilism --sections "preamble,1,2"

# Get bibliography only
python scripts/fetch_sep.py freewill --bibliography-only
```

## IEP Content Access

**Use `fetch_iep.py` for Internet Encyclopedia of Philosophy articles.**

`fetch_iep.py` provides structured extraction similar to SEP:
- Preamble, individual sections, bibliography, author information

```bash
python scripts/fetch_iep.py compatibilism --sections "1,2,3"
python scripts/fetch_iep.py freewill --bibliography-only
```

**Note**: IEP has different coverage than SEP. Use both for comprehensive encyclopedia coverage.

## Available Scripts

| Script | Purpose | Key Options |
|--------|---------|-------------|
| `s2_search.py` | Paper discovery | `--bulk`, `--year`, `--field`, `--min-citations` |
| `s2_citations.py` | Citation traversal | `--references`, `--citations`, `--influential-only` |
| `s2_batch.py` | Batch paper details | `--ids`, `--file` |
| `s2_recommend.py` | Find similar papers | `--positive`, `--negative`, `--for-paper` |
| `search_openalex.py` | Broad academic search | `--year`, `--doi`, `--id`, `--cites`, `--oa-only` |
| `search_arxiv.py` | arXiv preprints | `--category`, `--author`, `--recent`, `--id` |
| `search_sep.py` | SEP discovery | `--limit`, `--all-pages` |
| `fetch_sep.py` | SEP content extraction | `--sections`, `--bibliography-only`, `--related-only` |
| `search_iep.py` | IEP discovery | `--limit`, `--all-pages` |
| `fetch_iep.py` | IEP content extraction | `--sections`, `--bibliography-only` |
| `search_philpapers.py` | PhilPapers search | `--limit`, `--recent` |
| `verify_paper.py` | DOI verification | `--title`, `--author`, `--year`, `--doi` |
| `search_core.py` | CORE API (431M papers) | `--doi`, `--title`, `--author`, `--year` |
| `get_abstract.py` | Multi-source abstract resolution | `--doi`, `--s2-id`, `--title`, `--author` |
| `get_sep_context.py` | SEP citation context extraction | `--author`, `--year`, `--coauthor` |
| `get_iep_context.py` | IEP citation context extraction | `--author`, `--year`, `--coauthor` |
| `check_setup.py` | Environment check | (no options) |

## Output Format

All scripts output JSON with consistent structure:

```json
{
  "status": "success|partial|error",
  "source": "script_name",
  "query": "search query",
  "results": [...],
  "count": 5,
  "errors": []
}
```

Exit codes: 0=success, 1=not found, 2=config error, 3=API error

## WebFetch Usage

**Use WebFetch only when scripts don't provide the needed content:**
- PhilPapers entry pages for additional metadata
- Publisher pages for paper details not in S2
- DOI resolution verification (`https://doi.org/{doi}`)

**Do NOT use WebFetch for:**
- SEP articles: use `fetch_sep.py` (structured output)
- Paper abstracts: use `s2_search.py` or `s2_batch.py`

## Verification Requirements

- **Never fabricate citations** - only include papers found via scripts
- **Verify DOIs** via `verify_paper.py` when S2 lacks DOI
- **Omit DOI field** if verification fails (never invent DOIs)
- **Report gaps** if expected papers are not found

## Environment

Required environment variables:
```bash
BRAVE_API_KEY        # Required for SEP/PhilPapers discovery
CROSSREF_MAILTO      # Required for CrossRef polite pool
S2_API_KEY           # Recommended for Semantic Scholar
OPENALEX_EMAIL       # Recommended for OpenAlex polite pool
```

Check setup with:
```bash
python scripts/check_setup.py
```
