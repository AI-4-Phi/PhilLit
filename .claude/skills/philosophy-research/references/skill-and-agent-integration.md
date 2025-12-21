# SKILL.md Template and Agent Integration Details

This reference document contains:
1. Full proposed content for SKILL.md
2. Detailed agent integration workflows for domain-literature-researcher
3. Detailed agent integration workflows for citation-validator

---

## SKILL.md Template

The SKILL.md file should use this structure:

```yaml
---
name: philosophy-research
description: Search philosophy literature across SEP, PhilPapers, and Semantic Scholar. Supports paper discovery, citation traversal, and recommendations. Verifies citations via CrossRef.
---
```

### Section 1: Overview

Brief description of available capabilities and when to use this skill.

### Section 2: Search Workflow

**Phase 1: SEP (Most Authoritative)**
- `search_sep.py "{topic}"` - discover relevant SEP articles
- `fetch_sep.py {entry}` - extract structured content (preamble, sections, bibliography)
- Parse bibliography for foundational works
- Follow related entries for topic expansion

**Phase 2: PhilPapers**
- `search_philpapers.py "{topic}"` - philosophy-specific papers
- Cross-reference with SEP bibliography

**Phase 3: Extended Academic Search**
- Semantic Scholar: `s2_search.py` (broad academic search)
- OpenAlex: `search_openalex.py` (250M+ works, cross-disciplinary)
- arXiv: `search_arxiv.py` (preprints, AI ethics, recent work)

**Phase 4: Citation Traversal**
- Get references for foundational papers: `s2_citations.py --references`
- Get citing papers for forward chaining: `s2_citations.py --citations`
- Focus on influential citations with `--influential-only`
- Parse SEP bibliographies and feed to `s2_search.py` or `verify_paper.py`

**Phase 5: Expansion**
- Use `s2_recommend.py` to find related papers not connected by citations
- Provide positive seeds (relevant papers) and negative seeds (irrelevant)
- Use `fetch_sep.py --related-only` to expand via SEP connections

**Phase 6: Batch Details**
- Collect paper IDs from all phases
- Use `s2_batch.py` to efficiently fetch full metadata

### Section 3: SEP Content Access

**For SEP articles, use `fetch_sep.py` instead of WebFetch.**

`fetch_sep.py` provides structured extraction:
- Preamble (abstract/introduction)
- Individual sections by number
- Bibliography with parsed author/year/title
- Related entries for topic expansion
- Author and publication dates

**SEP workflow**:
```
search_sep.py "free will" → article URLs with entry_names
fetch_sep.py freewill --sections "preamble,1,bibliography"
  → structured JSON with sections and parsed bibliography
Parse bibliography → s2_search.py or verify_paper.py
  → find DOIs for cited works
```

### Section 4: WebFetch Usage

**Use WebFetch only when skill scripts don't provide the needed content:**

- PhilPapers entry pages for additional metadata
- Publisher pages for paper details not in S2
- DOI resolution verification (`https://doi.org/{doi}`)
- Any other web content not covered by skill scripts

**Do NOT use WebFetch for**:
- SEP articles: use `fetch_sep.py` instead (structured output)
- Paper abstracts: use `s2_search.py` or `s2_batch.py`

### Section 5: Available Scripts

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
| `search_philpapers.py` | PhilPapers search | `--limit`, `--recent` |
| `verify_paper.py` | DOI verification | `--title`, `--author`, `--year`, `--doi` |

### Section 6: Verification Requirements

- **Never fabricate citations** - only include papers found via scripts
- **Verify DOIs** via `verify_paper.py` when S2 lacks DOI
- **Omit DOI field** if verification fails (never invent)
- **Report gaps** if expected papers are not found

### Section 7: Environment Setup

```bash
export S2_API_KEY="your-semantic-scholar-key"  # Recommended
export BRAVE_API_KEY="your-brave-key"           # Required for SEP/PhilPapers discovery
export CROSSREF_MAILTO="your@email.com"         # Required for CrossRef polite pool
export OPENALEX_EMAIL="your@email.com"          # Recommended for OpenAlex polite pool
pip install requests beautifulsoup4 lxml pyalex arxiv
```

---

## Agent Integration: domain-literature-researcher

### Frontmatter Changes

```yaml
---
name: domain-literature-researcher
description: ...
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
model: sonnet
---
```

### Search Process - Detailed Phases

**Phase 1: SEP (Stanford Encyclopedia of Philosophy)**

*Most authoritative source for philosophy - start here*

1. `search_sep.py "{topic}"` - discover relevant SEP articles
2. `fetch_sep.py {entry_name} --sections "preamble,1,2,bibliography"` - extract content
3. Read preamble and key sections for domain overview
4. Parse bibliography for foundational works cited
5. `fetch_sep.py {entry_name} --related-only` - expand to related topics

**Phase 2: PhilPapers**

*Philosophy-specific academic papers*

1. `search_philpapers.py "{topic}"` - note key papers
2. Cross-reference with SEP bibliography entries
3. Identify papers not covered by SEP

**Phase 3: Extended Academic Search**

*Broader coverage and cross-disciplinary work*

1. **Semantic Scholar**: `s2_search.py "{topic}" --field Philosophy --year 2015-2025`
2. **OpenAlex**: `search_openalex.py "{topic}" --year 2015-2025` - broad coverage, cross-disciplinary
3. **arXiv**: `search_arxiv.py "{topic}" --category cs.AI --recent` - preprints, AI ethics

**Phase 4: Citation Chaining**

1. Identify foundational papers from SEP bibliography + PhilPapers + S2 search
2. `s2_citations.py {paper_id} --both --influential-only`
3. `s2_recommend.py --positive {foundational_ids}`
4. Parse SEP bibliographies and run `verify_paper.py` to get DOIs

**Phase 5: Batch Metadata**

1. Collect all paper IDs from all phases
2. `s2_batch.py --ids "{all_ids}"`
3. Use structured SEP content for writing CORE ARGUMENT notes

### When to Prioritize arXiv

- AI ethics, AI alignment, machine learning interpretability topics
- Recent/cutting-edge work not yet in journals
- Computational philosophy, formal epistemology
- Cross-disciplinary philosophy-CS research

### When to Prioritize OpenAlex

- Comprehensive literature coverage (250M+ works)
- Cross-disciplinary topics (philosophy published in non-philosophy venues)
- Finding open access versions of paywalled papers
- Papers not in Semantic Scholar or arXiv
- Author searches with affiliation information
- Citation analysis with high coverage

---

## Agent Integration: citation-validator

### Frontmatter Changes

```yaml
---
name: citation-validator
description: ...
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
model: sonnet
---
```

### Validation Methods

**Method 1: Semantic Scholar Lookup** (preferred)
- Extract DOI or title from BibTeX entry
- `s2_search.py "{title}" --limit 5` or use DOI directly
- If found: verify metadata matches (authors, year, venue)
- If S2 has the paper, it exists - high confidence

**Method 2: CrossRef Verification**
- `verify_paper.py --title "{title}" --author "{author}" --year {year}`
- Returns match confidence score (threshold 0.85)
- Confirms DOI validity

**Method 3: DOI Resolution**
- WebFetch `https://doi.org/{doi}` to verify DOI resolves
- Check metadata on landing page

**Method 4: SEP/PhilPapers Check** (for non-journal sources)
- `search_sep.py "{title}"` for SEP entries
- `search_philpapers.py "{title}"` for PhilPapers entries
- WebFetch URL to verify it resolves

**Method 5: arXiv Lookup** (for preprints)
- `search_arxiv.py --id "{arxiv_id}"` for direct arXiv ID lookup
- `search_arxiv.py --title "{title}" --author "{author}"` for title/author search
- Useful for: AI ethics papers, recent preprints, CS/philosophy cross-disciplinary work
- arXiv provides: full abstract, DOI (if published), journal_ref

**Method 6: OpenAlex Lookup** (broad coverage)
- `search_openalex.py --doi "{doi}"` for direct DOI verification
- `search_openalex.py "{title}"` for title search with year filtering
- Useful for: Papers not found in S2 or arXiv, cross-disciplinary work
- OpenAlex provides: 250M+ works, open access links, comprehensive metadata
- **Batch validation**: `search_openalex.py --doi "{doi1}" --doi "{doi2}"...` (up to 50)

### Validation Workflow

```
For each BibTeX entry:

1. If DOI present:
   a. verify_paper.py --title "..." → confirm DOI matches
   b. WebFetch doi.org/{doi} → confirm resolves

2. If arXiv ID present (e.g., "arXiv:2301.00001"):
   a. search_arxiv.py --id "2301.00001" → verify exists
   b. Check if arXiv entry has DOI (paper was published)

3. If no DOI/arXiv ID:
   a. s2_search.py "{title}" → find in Semantic Scholar
   b. If found, extract DOI from S2 response
   c. If not in S2, try search_openalex.py "{title}" → broader coverage
   d. If not in OpenAlex, try search_arxiv.py for preprints
   e. If not in arXiv, search_philpapers.py or search_sep.py

4. Compare metadata: authors, year (±1), venue

5. Decision: KEEP (verified), CORRECT (minor fixes), or REMOVE (unverified)
```

### Batch Validation (Efficiency)

For large BibTeX files:

1. Collect all DOIs from BibTeX file
2. `s2_batch.py --ids "DOI:10.xxx,DOI:10.yyy,..."` (up to 500)
3. For DOIs not found in S2, use OpenAlex batch: `Works().filter_or(doi=[...])` (up to 50)
4. Compare batch response against BibTeX metadata
5. Only use individual lookups for entries not found in batch
6. For arXiv entries, use individual lookups (no batch API)
