# Script Specifications Reference

Detailed specifications for all scripts in the philosophy-research skill.

---

## s2_search.py

Semantic Scholar paper search with relevance ranking or bulk retrieval.

### Usage

```bash
python s2_search.py "free will compatibilism" --limit 20
python s2_search.py "moral responsibility" --bulk --year 2020-2024
python s2_search.py "Frankfurt cases" --field Philosophy --min-citations 10
```

### Input

| Argument | Description |
|----------|-------------|
| `query` | Search string (required) |
| `--bulk` | Use bulk search (no ranking, up to 1000 results) |
| `--limit N` | Number of results (default 20, max 100 for relevance, 1000 for bulk) |
| `--year YYYY` or `YYYY-YYYY` | Year filter |
| `--field FIELD` | Field of study filter (e.g., Philosophy) |
| `--min-citations N` | Minimum citation count |

### Output

JSON array:
```json
[
  {
    "paperId": "...",
    "title": "...",
    "authors": [{"name": "...", "authorId": "..."}],
    "year": 2021,
    "abstract": "...",
    "citationCount": 45,
    "doi": "10.xxx/...",
    "url": "https://semanticscholar.org/paper/..."
  }
]
```

### Implementation Notes

- Implements rate limiting (1 req/sec)
- Exponential backoff on 429 errors
- DOI extracted from externalIds field

---

## s2_citations.py

Traverse citations and references for a paper.

### Usage

```bash
python s2_citations.py DOI:10.1111/j.1933-1592.2004.tb00342.x --references
python s2_citations.py CorpusId:12345 --citations --influential-only
python s2_citations.py "URL:https://arxiv.org/abs/..." --both
```

### Input

| Argument | Description |
|----------|-------------|
| `paper_id` | Paper identifier (DOI:, CorpusId:, ARXIV:, URL:, or SHA) |
| `--references` | Get papers this paper cites |
| `--citations` | Get papers that cite this paper |
| `--both` | Get both directions |
| `--influential-only` | Filter to influential citations only |
| `--limit N` | Max results per direction (default 100, max 1000) |

### Output

JSON object:
```json
{
  "paper": {"paperId": "...", "title": "..."},
  "references": [...],
  "citations": [...]
}
```

### Implementation Notes

- Implements rate limiting
- Exponential backoff on errors

---

## s2_batch.py

Batch fetch paper details for multiple IDs.

### Usage

```bash
python s2_batch.py --ids "DOI:10.xxx,CorpusId:123,DOI:10.yyy"
python s2_batch.py --file paper_ids.txt
```

### Input

| Argument | Description |
|----------|-------------|
| `--ids` | Comma-separated paper IDs |
| `--file` | File with one paper ID per line |
| `--fields` | Override default fields |

### Output

JSON array of paper objects.

### Implementation Notes

- Max 500 IDs per call
- Implements rate limiting
- Exponential backoff on errors

---

## s2_recommend.py

Get paper recommendations based on seed papers.

### Usage

```bash
python s2_recommend.py --positive "DOI:10.xxx,DOI:10.yyy"
python s2_recommend.py --positive "DOI:10.xxx" --negative "DOI:10.zzz" --limit 50
python s2_recommend.py --for-paper DOI:10.xxx
```

### Input

| Argument | Description |
|----------|-------------|
| `--positive` | Comma-separated IDs of papers to find similar to |
| `--negative` | Comma-separated IDs of papers to avoid similarity to |
| `--for-paper` | Single paper ID for single-paper recommendations |
| `--limit N` | Number of recommendations (default 100, max 500) |

### Output

JSON array of recommended papers.

### Implementation Notes

- Implements rate limiting
- Exponential backoff on errors

---

## search_arxiv.py

Search arXiv for preprints and recent papers.

### Usage

```bash
python search_arxiv.py "free will consciousness"
python search_arxiv.py "AI ethics" --category cs.AI --limit 50
python search_arxiv.py "epistemic injustice" --recent
python search_arxiv.py --id "2301.00001"
python search_arxiv.py --author "Chalmers" --title "consciousness"
```

### Input

| Argument | Description |
|----------|-------------|
| `query` | Search terms (searches all fields by default) |
| `--author NAME` | Filter by author name (au: prefix) |
| `--title TERMS` | Filter by title (ti: prefix) |
| `--abstract TERMS` | Filter by abstract (abs: prefix) |
| `--category CAT` | Filter by arXiv category (e.g., cs.AI, cs.CY, physics.hist-ph) |
| `--id ID` | Lookup specific arXiv ID (e.g., 2301.00001) |
| `--limit N` | Max results (default 20, max 2000) |
| `--recent` | Sort by submission date (most recent first) |
| `--year YYYY` | Filter to specific year |
| `--year-from YYYY` | Filter from year onwards |

### Output

JSON array:
```json
[
  {
    "arxiv_id": "2301.00001",
    "title": "Paper Title",
    "authors": ["First Author", "Second Author"],
    "abstract": "Full abstract text...",
    "published": "2023-01-15",
    "updated": "2023-02-20",
    "primary_category": "cs.AI",
    "categories": ["cs.AI", "cs.CY"],
    "doi": "10.xxxx/xxxxx",
    "journal_ref": "Nature 2023",
    "pdf_url": "https://arxiv.org/pdf/2301.00001.pdf",
    "url": "https://arxiv.org/abs/2301.00001"
  }
]
```

### Implementation Notes

- 3-second delay between requests (arXiv requirement)
- Uses arxiv.py library for robust API handling
- Best for AI ethics, computational philosophy, formal epistemology

---

## search_openalex.py

Search OpenAlex for broad academic paper discovery and verification.

### Usage

```bash
python search_openalex.py "free will compatibilism"
python search_openalex.py "moral responsibility" --year 2020-2024 --limit 50
python search_openalex.py --doi "10.2307/2024717"
python search_openalex.py --id "W2741809807"
python search_openalex.py "epistemic injustice" --oa-only --min-citations 10
python search_openalex.py --cites "W2741809807" --limit 100
python search_openalex.py "Frankfurt" --author --limit 20
```

### Input

| Argument | Description |
|----------|-------------|
| `query` | Search terms (searches title and abstract) |
| `--doi DOI` | Direct lookup by DOI (returns single paper) |
| `--id OPENALEX_ID` | Direct lookup by OpenAlex ID (e.g., W2741809807) |
| `--author` | Search for authors instead of works |
| `--cites OPENALEX_ID` | Find papers citing a specific work |
| `--refs OPENALEX_ID` | Find papers referenced by a work |
| `--year YYYY` or `YYYY-YYYY` | Filter by publication year or range |
| `--limit N` | Max results (default 25, max 200 per page) |
| `--oa-only` | Only open access papers |
| `--min-citations N` | Minimum citation count |
| `--type TYPE` | Filter by work type (journal-article, book, book-chapter, etc.) |
| `--select FIELDS` | Comma-separated fields to return (for efficiency) |
| `--sample N` | Random sample of N papers (for exploratory search) |

### Output (Works)

JSON array (or single object for --doi/--id):
```json
[
  {
    "openalex_id": "W2741809807",
    "doi": "10.2307/2024717",
    "title": "Freedom of the Will and the Concept of a Person",
    "authors": [
      {
        "name": "Harry G. Frankfurt",
        "openalex_id": "A5027479191",
        "orcid": "0000-0001-2345-6789",
        "institutions": ["Princeton University"]
      }
    ],
    "publication_year": 1971,
    "publication_date": "1971-01-01",
    "abstract": "Full abstract text...",
    "cited_by_count": 3500,
    "type": "journal-article",
    "source": {
      "name": "The Journal of Philosophy",
      "issn": "0022-362X",
      "type": "journal"
    },
    "open_access": {
      "is_oa": true,
      "oa_status": "gold",
      "oa_url": "https://..."
    },
    "referenced_works_count": 15,
    "topics": ["Free Will", "Moral Responsibility"],
    "url": "https://openalex.org/W2741809807"
  }
]
```

### Output (Authors with --author)

```json
[
  {
    "openalex_id": "A5027479191",
    "name": "Harry G. Frankfurt",
    "orcid": "0000-0001-2345-6789",
    "works_count": 47,
    "cited_by_count": 12500,
    "affiliations": ["Princeton University"],
    "url": "https://openalex.org/A5027479191"
  }
]
```

### Implementation Notes

- Uses pyalex library with polite pool (config.email)
- Rate limiting: 10 req/sec, automatic retries on 429
- Larger database than Semantic Scholar, good for comprehensive coverage

---

## search_sep.py

**DISCOVERY**: Find relevant SEP articles via Brave API.

For content extraction, use `fetch_sep.py` instead.

### Usage

```bash
python search_sep.py "free will"
python search_sep.py "compatibilism determinism" --limit 10
python search_sep.py "moral responsibility" --all-pages
```

### Input

| Argument | Description |
|----------|-------------|
| `query` | Search terms |
| `--limit N` | Max results (default 20, max 200) |
| `--all-pages` | Fetch all available pages (up to 200 results) |
| `--extra-snippets` | Include additional excerpts |

### Output

JSON array:
```json
[
  {
    "title": "Free Will - Stanford Encyclopedia of Philosophy",
    "url": "https://plato.stanford.edu/entries/freewill/",
    "entry_name": "freewill",
    "snippet": "Main description text...",
    "extra_snippets": ["...", "..."],
    "page_age": "2023-05-15",
    "author": "Timothy O'Connor"
  }
]
```

### API Parameters Used

```
q=site:plato.stanford.edu {query}
count=20
offset=0..9 (for pagination)
extra_snippets=true (if requested)
text_decorations=false
result_filter=web
```

### Implementation Notes

- Rate limiting (1 req/sec)
- Exponential backoff on 429
- Max 200 results due to offset limit of 9
- Typical workflow: `search_sep.py` -> `fetch_sep.py` for full content

---

## fetch_sep.py

**EXTRACTION**: Fetch and parse SEP article content via BeautifulSoup.

Use after `search_sep.py` to get structured content.

### Usage

```bash
python fetch_sep.py freewill
python fetch_sep.py https://plato.stanford.edu/entries/freewill/
python fetch_sep.py freewill --sections "preamble,1,2,bibliography"
python fetch_sep.py freewill --bibliography-only
python fetch_sep.py freewill --related-only
```

### Input

| Argument | Description |
|----------|-------------|
| `entry` | Entry name (e.g., "freewill") or full URL |
| `--sections LIST` | Comma-separated sections to extract (default: all). Special values: "preamble", "bibliography", "related", "toc". Section numbers: "1", "2.1", "3.2.1", etc. |
| `--bibliography-only` | Only extract bibliography (for citation chaining) |
| `--related-only` | Only extract related entries (for topic expansion) |
| `--include-html` | Include raw HTML in addition to text |

### Output (Full)

```json
{
  "url": "https://plato.stanford.edu/entries/freewill/",
  "entry_name": "freewill",
  "title": "Free Will",
  "author": "Timothy O'Connor",
  "first_published": "2002-01-07",
  "last_updated": "2024-03-15",
  "preamble": "Free will is a philosophical concept referring to...",
  "toc": [
    {"id": "1", "title": "Introduction", "level": 1},
    {"id": "1.1", "title": "The Concept of Free Will", "level": 2},
    {"id": "2", "title": "The Powers of Agency", "level": 1}
  ],
  "sections": {
    "1": {
      "id": "1",
      "title": "Introduction",
      "content": "Section text content..."
    },
    "1.1": {
      "id": "1.1",
      "title": "The Concept of Free Will",
      "content": "Subsection text content..."
    }
  },
  "bibliography": [
    {
      "text": "Anscombe, G.E.M., 1957, Intention, Oxford: Blackwell.",
      "parsed": {
        "authors": ["Anscombe, G.E.M."],
        "year": "1957",
        "title": "Intention",
        "publisher": "Oxford: Blackwell"
      }
    }
  ],
  "related_entries": [
    {"title": "action", "url": "/entries/action/", "entry_name": "action"},
    {"title": "compatibilism", "url": "/entries/compatibilism/", "entry_name": "compatibilism"}
  ]
}
```

### Output (--bibliography-only)

```json
{
  "url": "...",
  "entry_name": "freewill",
  "bibliography": [...]
}
```

### Implementation Notes

- Polite rate limiting (1 req/sec)
- Dependencies: requests, beautifulsoup4, lxml

---

## search_philpapers.py

Search PhilPapers via Brave API.

### Usage

```bash
python search_philpapers.py "epistemic injustice"
python search_philpapers.py "virtue epistemology" --limit 40
python search_philpapers.py "phenomenal consciousness" --recent
```

### Input

| Argument | Description |
|----------|-------------|
| `query` | Search terms |
| `--limit N` | Max results (default 20, max 200) |
| `--all-pages` | Fetch all available pages (up to 200 results) |
| `--recent` | Filter to past year only (freshness=py) |
| `--extra-snippets` | Include additional excerpts |

### Output

JSON array:
```json
[
  {
    "title": "Epistemic Injustice: Power and the Ethics of Knowing",
    "url": "https://philpapers.org/rec/FRIEIP",
    "snippet": "Description text...",
    "extra_snippets": ["...", "..."],
    "page_age": "2023-01-15",
    "authors": ["Miranda Fricker"]
  }
]
```

### API Parameters Used

```
q=site:philpapers.org {query}
count=20
offset=0..9 (for pagination)
freshness=py (if --recent)
extra_snippets=true (if requested)
text_decorations=false
result_filter=web
```

### Implementation Notes

- Rate limiting (1 req/sec)
- Exponential backoff on 429
- Max 200 results due to offset limit of 9

---

## verify_paper.py

Verify paper existence and retrieve/validate DOI via CrossRef.

### Usage

```bash
python verify_paper.py --title "Freedom of the Will and the Concept of a Person"
python verify_paper.py --title "..." --author "Frankfurt" --year 1971
python verify_paper.py --doi "10.2307/2024717"
python verify_paper.py --doi "10.2307/2024717" --title "..." --verify-metadata
```

### Input

| Argument | Description |
|----------|-------------|
| `--title "..."` | Paper title (required unless --doi provided) |
| `--author "..."` | Author family name (optional, improves matching) |
| `--year YYYY` | Publication year (optional, filters results +/-1 year) |
| `--doi "..."` | DOI to verify directly (skips search) |
| `--verify-metadata` | When using --doi, also verify title/author match |
| `--mailto "..."` | Email for polite pool (default: uses CROSSREF_MAILTO env var) |

### Output (Success)

```json
{
  "verified": true,
  "doi": "10.2307/2024717",
  "title": "Freedom of the Will and the Concept of a Person",
  "authors": [{"given": "Harry G.", "family": "Frankfurt"}],
  "year": 1971,
  "container_title": "The Journal of Philosophy",
  "publisher": "Journal of Philosophy, Inc.",
  "type": "journal-article",
  "score": 142.5,
  "method": "doi_lookup"
}
```

### Output (Failure)

```json
{
  "verified": false,
  "error": "Paper not found in CrossRef",
  "query": {"title": "...", "author": "...", "year": ...}
}
```
Exit code 1.

### Workflow

1. If `--doi` provided: Direct lookup via `GET /works/{doi}`
2. Else: Search via `GET /works?query.bibliographic=...&query.author=...`
3. Validate: score > 50, author match, year +/-1
4. Return verified metadata or exit 1

### Implementation Notes

- **CRITICAL**: Exit 1 and print error JSON if not found - NEVER fabricate
- Adaptive rate limiting via X-Rate-Limit-* headers

---

## requirements.txt

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
arxiv>=2.0.0
pyalex>=0.14
```

### Dependency Notes

| Package | Purpose |
|---------|---------|
| `requests` | HTTP client for all API calls and SEP fetching |
| `beautifulsoup4` | HTML parsing for SEP content extraction |
| `lxml` | Fast HTML parser backend for BeautifulSoup (recommended over html.parser) |
| `arxiv` | Python wrapper for arXiv API with built-in rate limiting |
| `pyalex` | Python wrapper for OpenAlex API with polite pool and retry handling |
