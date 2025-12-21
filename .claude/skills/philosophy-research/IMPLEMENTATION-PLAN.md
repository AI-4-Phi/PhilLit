# Philosophy Research Skill - Implementation Plan

**Status**: Planning complete, ready for implementation
**Last updated**: 2025-12-21 (Added OpenAlex)

## Objective

Replace `WebSearch` in `domain-literature-researcher` and `citation-validator` agents with a Claude Skill that searches academic sources via APIs, reducing costs while maintaining citation quality.

## Architecture Decision

**Approach**: Claude Skill (not MCP)
**Rationale**: Simpler to implement, sufficient for this use case, skills can be used by subagents via `skills:` frontmatter.

## File Structure

```
.claude/skills/philosophy-research/
├── SKILL.md                    # Skill definition
├── scripts/
│   ├── s2_search.py            # Semantic Scholar search (relevance + bulk)
│   ├── s2_citations.py         # Citation traversal (references + citations)
│   ├── s2_batch.py             # Batch paper details
│   ├── s2_recommend.py         # Paper recommendations
│   ├── search_arxiv.py         # arXiv preprint search
│   ├── search_openalex.py      # OpenAlex broad academic search
│   ├── search_sep.py           # SEP discovery via Brave API
│   ├── fetch_sep.py            # SEP content extraction via BeautifulSoup
│   ├── search_philpapers.py    # PhilPapers via Brave API
│   ├── verify_paper.py         # CrossRef API
│   └── requirements.txt
└── references/
    ├── philpapers-categories.txt
    └── philosophy-journals.txt
```

## Search Sources

| Source | Method | Auth Required | Rate Limit | Notes |
|--------|--------|---------------|------------|-------|
| Semantic Scholar | Direct API | Optional (recommended) | 1 req/sec | Primary paper source, citations, recommendations |
| OpenAlex | pyalex library | None (email recommended) | 10 req/sec | Broad academic coverage, 250M+ works, open access |
| arXiv | arxiv.py library | None | 3 sec delay | Preprints, recent work, full abstracts |
| SEP (discovery) | Brave API + `site:plato.stanford.edu` | BRAVE_API_KEY | 1/sec free | Find relevant articles |
| SEP (content) | requests + BeautifulSoup | None | Polite (1/sec) | Extract structured content, bibliography |
| PhilPapers | Brave API + `site:philpapers.org` | BRAVE_API_KEY | 1/sec free | Philosophy-specific papers |
| CrossRef | Direct API | None (polite pool) | 50/sec | DOI verification |

---

## Semantic Scholar API — Detailed Specification

**Base URL**: `https://api.semanticscholar.org`

### Authentication

- **Without API key**: Shares rate limit with all unauthenticated users (unreliable)
- **With API key**: Guaranteed 1 request/second across all endpoints
- **Header**: `x-api-key: {S2_API_KEY}`
- **Obtain key**: https://www.semanticscholar.org/product/api#api-key

### Rate Limiting Strategy

All scripts MUST implement:

```python
import time
import random

class S2RateLimiter:
    """Enforces 1 req/sec with exponential backoff on 429 errors."""

    def __init__(self):
        self.last_request = 0
        self.min_interval = 1.1  # Slightly over 1 sec for safety

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()

    def backoff(self, attempt: int, max_attempts: int = 5) -> bool:
        """Exponential backoff. Returns False if max attempts exceeded."""
        if attempt >= max_attempts:
            return False
        delay = (2 ** attempt) + random.uniform(0, 1)
        time.sleep(delay)
        return True
```

### Endpoints Used

#### 1. Paper Relevance Search
- **Path**: `GET /graph/v1/paper/search`
- **Use**: Ranked search results for discovery
- **Params**:
  - `query` (required): Plain text, no special syntax
  - `fields`: Comma-separated (see Fields section)
  - `offset`, `limit`: Pagination (limit ≤ 100)
  - `year`: Filter by year or range (e.g., `2020-2024`)
  - `fieldsOfStudy`: Filter by discipline (e.g., `Philosophy`)
  - `minCitationCount`: Filter by citation threshold
- **Response**: `{total, offset, next, data: [papers]}`

#### 2. Paper Bulk Search
- **Path**: `GET /graph/v1/paper/search/bulk`
- **Use**: Large-scale retrieval (up to 1,000 per request)
- **Params**:
  - `query`: Supports boolean operators (`+`, `|`, `-`, `"`, `*`, `~`)
  - `token`: Continuation token for pagination
  - `sort`: `paperId`, `publicationDate`, or `citationCount`
  - Same filters as relevance search
- **Response**: `{total, token, data: [papers]}`
- **Note**: No relevance ranking; use for comprehensive collection

#### 3. Paper Details (Single)
- **Path**: `GET /graph/v1/paper/{paper_id}`
- **Paper ID formats**: SHA, `CorpusId:123`, `DOI:10.xxx`, `ARXIV:xxx`, `URL:https://...`
- **Params**: `fields`
- **Use**: Detailed info for known paper

#### 4. Paper Batch
- **Path**: `POST /graph/v1/paper/batch`
- **Use**: Get details for multiple papers at once (up to 500)
- **Body**: `{"ids": ["DOI:10.xxx", "CorpusId:123", ...]}`
- **Params**: `fields` (as query param)
- **Limits**: 500 IDs, 10 MB response, 9,999 citations max
- **CRITICAL**: Use this instead of repeated single-paper calls

#### 5. Paper Citations
- **Path**: `GET /graph/v1/paper/{paper_id}/citations`
- **Use**: Find papers that cite a given paper (forward traversal)
- **Params**:
  - `offset`, `limit`: Pagination (limit ≤ 1,000)
  - `fields`: Include `contexts`, `isInfluential`, `citingPaper.title`, etc.
- **Response**: `{data: [{contexts, isInfluential, citingPaper: {...}}]}`

#### 6. Paper References
- **Path**: `GET /graph/v1/paper/{paper_id}/references`
- **Use**: Find papers cited by a given paper (backward traversal)
- **Params**: Same as citations
- **Response**: `{data: [{contexts, isInfluential, citedPaper: {...}}]}`

#### 7. Recommendations (Batch)
- **Base**: `https://api.semanticscholar.org/recommendations/v1`
- **Path**: `POST /papers/`
- **Use**: Find similar papers based on positive/negative examples
- **Body**:
  ```json
  {
    "positivePaperIds": ["DOI:10.xxx", "CorpusId:123"],
    "negativePaperIds": ["DOI:10.yyy"]
  }
  ```
- **Params**: `limit` (max 500), `fields`
- **Use case**: Expand bibliography from seed papers

#### 8. Recommendations (Single Paper)
- **Path**: `GET /papers/forpaper/{paper_id}`
- **Params**:
  - `from`: `recent` (default) or `all-cs`
  - `limit` (max 500), `fields`
- **Use case**: Quick expansion from one foundational paper

### Fields Parameter — Best Practices

**Only request fields you need** — extra fields slow responses.

**Recommended fields for literature research**:
```
paperId,title,authors,year,abstract,citationCount,externalIds,url,publicationTypes,journal
```

**For citation traversal, add**:
```
contexts,isInfluential
```

**Nested field syntax** (for batch/detail):
```
authors.name,authors.authorId,citations.title,references.title
```

**Available fields** (partial list):
- Paper: `paperId`, `title`, `abstract`, `year`, `citationCount`, `referenceCount`, `influentialCitationCount`, `publicationDate`, `venue`, `journal`, `publicationTypes`, `externalIds`, `url`, `openAccessPdf`
- Authors: `authorId`, `name`, `url`, `paperCount`, `citationCount`, `hIndex`
- Citation context: `contexts`, `intents`, `isInfluential`

### Citation Traversal Workflow

For Phase 3 (Citation Chaining) in the domain-literature-researcher:

```
1. Start with foundational paper(s) identified in Phase 1
2. GET /paper/{id}/references → Find sources the paper builds on
3. GET /paper/{id}/citations → Find papers that build on it
4. Filter by isInfluential=true for high-signal connections
5. Use recommendations to find topically related papers missed by citations
6. Batch-fetch details for all discovered papers
```

---

## arXiv API — Detailed Specification

**Base URL**: `http://export.arxiv.org/api/query`

**Python Library**: `arxiv` (recommended over raw API)

### Why arXiv for Philosophy Research?

- **Preprints**: Access to latest work before journal publication
- **Full abstracts**: Complete abstracts for all papers
- **Free and open**: No authentication required
- **Philosophy coverage**: Categories like `phil.*` (philosophy of science, logic, etc.)
- **Cross-disciplinary**: AI ethics papers often on arXiv before journals

### Installation

```bash
pip install arxiv
```

### Core Components (arxiv.py)

**Client**: Manages API connections with rate limiting
```python
import arxiv

client = arxiv.Client(
    page_size=100,      # Results per request (max 1000)
    delay_seconds=3,    # Required delay between requests
    num_retries=3       # Retry failed requests
)
```

**Search**: Defines query parameters
```python
search = arxiv.Search(
    query="au:Frankfurt AND ti:free will",
    max_results=50,
    sort_by=arxiv.SortCriterion.SubmittedDate,
    sort_order=arxiv.SortOrder.Descending
)
```

**Result**: Paper metadata
- `entry_id`: arXiv URL (e.g., `http://arxiv.org/abs/2301.00001v1`)
- `title`: Paper title
- `authors`: List of author objects
- `summary`: Full abstract
- `published`: Initial submission date
- `updated`: Latest version date
- `primary_category`: Main arXiv category
- `categories`: All categories
- `doi`: DOI if available
- `journal_ref`: Journal reference if published
- `pdf_url`: Direct PDF link

### Query Syntax

**Field Prefixes**:
- `ti:` — Title
- `au:` — Author
- `abs:` — Abstract
- `cat:` — Category
- `all:` — All fields

**Boolean Operators**:
- `AND`, `OR`, `ANDNOT`

**Examples**:
```
au:Chalmers AND ti:consciousness
cat:cs.AI AND ti:ethics
all:epistemic AND all:injustice
ti:"free will" AND au:Frankfurt
```

**Date Filtering**:
```
submittedDate:[202301010000 TO 202401010000]
```

### Relevant Categories for Philosophy

| Category | Description |
|----------|-------------|
| `cs.AI` | Artificial Intelligence (AI ethics, alignment) |
| `cs.CY` | Computers and Society (tech ethics) |
| `cs.LG` | Machine Learning (interpretability, fairness) |
| `stat.ML` | Machine Learning (statistical) |
| `q-bio.NC` | Neurons and Cognition |
| `physics.hist-ph` | History and Philosophy of Physics |

**Note**: Pure philosophy papers are less common on arXiv, but AI ethics, philosophy of mind (computational), and formal epistemology are well-represented.

### Rate Limiting

**Required**: 3-second delay between API calls

```python
class ArxivRateLimiter:
    """Enforces 3-second delay per arXiv guidelines."""

    def __init__(self):
        self.last_request = 0
        self.min_interval = 3.0  # arXiv requires 3 sec delay

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()
```

**Note**: The `arxiv.Client` handles this automatically with `delay_seconds=3`.

### Pagination

- Default: 10 results per request
- Maximum: 2000 results per request
- Total cap: 30,000 results per query
- Use `start` parameter for pagination

### Verification Use Case

arXiv can verify papers by:
1. **arXiv ID lookup**: Direct lookup with `id_list`
2. **Title/author search**: Find matching papers
3. **DOI cross-reference**: Many arXiv papers have DOIs

```python
# Verify by arXiv ID
search = arxiv.Search(id_list=["2301.00001"])
paper = next(client.results(search))

# Verify by title/author
search = arxiv.Search(
    query='ti:"Attention Is All You Need" AND au:Vaswani',
    max_results=5
)
```

---

## OpenAlex API — Detailed Specification

**Base URL**: `https://api.openalex.org`

**Python Library**: `pyalex` (recommended over raw API)

### Why OpenAlex for Philosophy Research?

- **Massive coverage**: 250M+ works, far larger than Semantic Scholar
- **Open and free**: No authentication required, generous rate limits
- **Rich metadata**: Abstracts, citations, open access status, topics
- **Cross-disciplinary**: Excellent for philosophy papers published in non-philosophy venues
- **Citation analysis**: Both incoming and outgoing citations
- **DOI/ROR/ORCID linking**: Strong identifier coverage

### Installation

```bash
pip install pyalex
```

### Configuration

**Polite Pool Access** (recommended for consistent response times):
```python
import pyalex
pyalex.config.email = "your@email.com"  # Highly recommended
```

**Retry Settings**:
```python
from pyalex import config
config.max_retries = 3
config.retry_backoff_factor = 0.1
config.retry_http_codes = [429, 500, 503]
```

### Rate Limits

| Limit | Value |
|-------|-------|
| Daily maximum | 100,000 calls |
| Per-second maximum | 10 requests |
| Polite pool benefit | More consistent response times |

**429 Response**: Exceeding limits returns 429 error. Implement exponential backoff.

### Core Entities

OpenAlex provides seven entity types:

| Entity | Class | Use Case |
|--------|-------|----------|
| Works | `Works()` | Papers, articles, books |
| Authors | `Authors()` | Researcher profiles |
| Sources | `Sources()` | Journals, repositories |
| Institutions | `Institutions()` | Universities, organizations |
| Topics | `Topics()` | Subject classifications |
| Publishers | `Publishers()` | Publishing organizations |
| Funders | `Funders()` | Funding bodies |

### Works Search Methods

**Text Search** (full-text across title, abstract):
```python
from pyalex import Works

results = Works().search("free will compatibilism").get()
```

**Field-Specific Search**:
```python
Works().search_filter(title="free will").get()
Works().search_filter(display_name="Frankfurt").get()  # For authors
```

**Single Entity Retrieval**:
```python
Works()["W2741809807"]           # By OpenAlex ID
Works()["doi:10.2307/2024717"]   # By DOI
```

### Filtering

**Basic Filters**:
```python
Works().filter(
    publication_year=2020,
    is_oa=True,
    type="journal-article"
).get()
```

**Nested Attribute Filters**:
```python
Works().filter(
    authorships={"institutions": {"ror": "04pp8hn57"}}
).get()
```

**Multiple Values (max 100 items)**:
```python
Works().filter_or(
    doi=["10.1016/...", "10.1002/..."]
).get()
```

**Logical Operators**:
- Inequality: `Works().filter(works_count=">1000")`
- Negation: `Works().filter(country_code="!us")`
- OR within field: `Works().filter(institutions={"country_code": "fr|gb"})`
- AND: Chain multiple `.filter()` calls

### Useful Filters for Philosophy Research

| Filter | Example | Use Case |
|--------|---------|----------|
| `publication_year` | `2020` or `"2020-2024"` | Date range |
| `is_oa` | `True` | Open access only |
| `type` | `"journal-article"` | Work type |
| `has_doi` | `True` | Only DOI works |
| `cites` | `"W2741809807"` | Papers citing a work |
| `cited_by_count` | `">50"` | Citation threshold |
| `authorships.author.id` | `"A123"` | By author |
| `primary_topic.field.id` | `"fields/31"` | Philosophy field |

### Citation Analysis

**Papers citing a work** (incoming citations):
```python
Works().filter(cites="W2741809807").get()
```

**Papers cited by a work** (outgoing references):
```python
work = Works()["W2741809807"]
referenced_ids = work.get("referenced_works", [])
Works()[referenced_ids]  # Batch lookup
```

### Pagination

**Cursor Paging** (default, recommended):
```python
pager = Works().search("epistemology").paginate(per_page=200)
for page in pager:
    for work in page:
        process(work)
```

**Limits**:
- Default: 25 results per page
- Maximum: 200 per page
- Total via cursor: unlimited (use `n_max=None`)
- Total via basic paging: 10,000 results

### Abstract Access

Abstracts are generated on-the-fly from inverted indices:
```python
work = Works()["W3128349626"]
abstract = work.get("abstract")  # Plaintext abstract
```

### Autocomplete

For entity discovery and suggestions:
```python
from pyalex import autocomplete

# Global autocomplete
autocomplete("frankfurt philosophy")

# Entity-specific
Works().autocomplete("free will")
Authors().autocomplete("Harry Frankfurt")
```

### Sampling

For random subsets:
```python
Works().sample(100, seed=42).get()
Works().filter(publication_year=2023).sample(50).get()
```

### Field Selection

Limit returned fields for faster responses:
```python
Works().filter(publication_year=2020).select(
    ["id", "doi", "title", "authorships", "cited_by_count", "abstract_inverted_index"]
).get()
```

### Open Access Information

```python
work = Works()["W2741809807"]
oa_info = work.get("open_access")
# Returns: {'is_oa': True, 'oa_status': 'gold', 'oa_url': '...'}
```

### Batch Operations

Use OR syntax for efficient batching (up to 50 items):
```python
Works().filter_or(
    doi=["10.xxx/1", "10.xxx/2", "10.xxx/3", ...]  # up to 50
).get()
```

### Rate Limiting Strategy

```python
import time

class OpenAlexRateLimiter:
    """Enforces 10 req/sec with exponential backoff on 429 errors."""

    def __init__(self):
        self.last_request = 0
        self.min_interval = 0.11  # Slightly over 0.1 sec for safety

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()

    def backoff(self, attempt: int, max_attempts: int = 5) -> bool:
        """Exponential backoff. Returns False if max attempts exceeded."""
        if attempt >= max_attempts:
            return False
        delay = (2 ** attempt) + random.uniform(0, 1)
        time.sleep(delay)
        return True
```

**Note**: pyalex handles retries automatically with `config.max_retries`.

### Key Response Fields for Works

| Field | Description | Notes |
|-------|-------------|-------|
| `id` | OpenAlex ID | Format: `W1234567890` |
| `doi` | DOI | Full URL or bare DOI |
| `title` | Title | String |
| `authorships` | Author list | Includes names, IDs, affiliations |
| `publication_year` | Year | Integer |
| `publication_date` | Full date | YYYY-MM-DD |
| `abstract_inverted_index` | Abstract data | Use `.get("abstract")` for text |
| `cited_by_count` | Citation count | Integer |
| `referenced_works` | Outgoing citations | List of OpenAlex IDs |
| `primary_topic` | Main topic | Includes field, subfield |
| `type` | Work type | journal-article, book, etc. |
| `open_access` | OA status | is_oa, oa_status, oa_url |
| `primary_location` | Publication venue | Journal/source info |

### Verification Use Case

OpenAlex can verify papers by:
1. **DOI lookup**: `Works()["doi:10.xxx"]`
2. **Title search**: `Works().search_filter(title="...").get()`
3. **OpenAlex ID**: `Works()["W1234567890"]`

```python
# Verify by DOI
try:
    work = Works()[f"doi:{doi}"]
    verified = True
except:
    verified = False

# Verify by title + author
results = Works().search_filter(title="Freedom of the Will").filter(
    publication_year="1970-1972"
).get()
```

---

## CrossRef API — Detailed Specification

**Base URL**: `https://api.crossref.org`

### Authentication & Polite Pool

- **No authentication required** for basic access
- **Polite pool access**: Add `mailto` parameter for higher rate limits
  ```
  ?mailto=your-email@example.com
  ```
- **Rate limit headers**: Check response headers to adapt request rate
  - `X-Rate-Limit-Limit`: Requests allowed per interval
  - `X-Rate-Limit-Interval`: Time interval (e.g., `1s`)

### Endpoints Used

#### 1. Direct DOI Lookup (Preferred for Verification)
- **Path**: `GET /works/{doi}`
- **Use**: Verify a known DOI exists and get its metadata
- **Response**:
  - 200 + metadata if DOI exists
  - 404 if DOI doesn't exist (definitive verification)
- **Example**: `GET /works/10.2307/2024717`
- **CRITICAL**: Use this instead of searching when DOI is already known

#### 2. Bibliographic Search
- **Path**: `GET /works`
- **Use**: Find DOI when only title/author known
- **Query Parameters**:
  - `query.bibliographic`: Searches titles, authors, ISSNs, years (replaces deprecated `query.title`)
  - `query.author`: Search author names specifically
  - `query.container-title`: Search journal/book titles
  - Multiple query params are ANDed together
- **Control Parameters**:
  - `rows`: Results per page (default 20, max 1000)
  - `offset`: Pagination offset (max 10,000)
  - `select`: Limit returned fields (improves speed)
  - `sort`: Order by `score`, `published`, `deposited`, `relevance`
  - `order`: `asc` or `desc`
- **Response**: Includes `score` field for relevance ranking

### Query Parameter Details

**`query.bibliographic`** (recommended):
- Searches across: titles, authors, ISSNs, publication years
- Better than deprecated `query.title` which only searched titles
- Words are ORed within the field

**Combining queries for precision**:
```
?query.bibliographic=Freedom+Will+Person&query.author=Frankfurt&mailto=...
```
- Multiple query fields are ANDed together
- More precise than single-field search

### Filters for Verification

Use filters to narrow results:
```
?filter=type:journal-article,from-pub-date:1970,until-pub-date:1972
```

**Useful filters**:
- `type`: `journal-article`, `book`, `book-chapter`, `proceedings-article`
- `from-pub-date` / `until-pub-date`: Year range (format: YYYY, YYYY-MM, or YYYY-MM-DD)
- `has-references`: Only items with reference lists
- `container-title`: Exact journal name match

### Field Selection

Use `select` to limit returned fields and improve response time:
```
?select=DOI,title,author,published,container-title,score,type
```

**Recommended fields for verification**:
- `DOI`: The DOI
- `title`: Array of titles
- `author`: Array of author objects with `given`, `family`
- `published`: Publication date
- `container-title`: Journal/book title
- `publisher`: Publisher name
- `score`: Relevance score (only present when querying)
- `type`: Work type

### Scoring & Matching

**Relevance score**:
- Results include `score` field when using query parameters
- Higher score = better match
- Sort by `sort=score&order=desc` to get best match first
- Use score threshold (e.g., > 50) instead of custom fuzzy matching

**Matching strategy**:
1. Get top 5 results sorted by score
2. Check if top result score exceeds threshold
3. Verify author name and year match within tolerance
4. Accept if all criteria pass

### Rate Limiting Strategy

```python
import time

class CrossRefRateLimiter:
    """Adaptive rate limiting based on response headers."""

    def __init__(self, mailto: str):
        self.mailto = mailto
        self.limit = 50  # Default conservative estimate
        self.interval = 1.0
        self.last_request = 0

    def update_from_headers(self, headers: dict):
        """Update limits from X-Rate-Limit-* headers."""
        if 'X-Rate-Limit-Limit' in headers:
            self.limit = int(headers['X-Rate-Limit-Limit'])
        if 'X-Rate-Limit-Interval' in headers:
            # Parse interval like "1s" or "1000ms"
            interval_str = headers['X-Rate-Limit-Interval']
            if interval_str.endswith('s'):
                self.interval = float(interval_str[:-1])
            elif interval_str.endswith('ms'):
                self.interval = float(interval_str[:-2]) / 1000

    def wait(self):
        """Wait to respect rate limit."""
        min_interval = self.interval / self.limit
        elapsed = time.time() - self.last_request
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request = time.time()
```

### Verification Workflow

```
verify_paper(title, author=None, year=None, doi=None):

1. If DOI provided:
   GET /works/{doi}?mailto=...&select=DOI,title,author,published,container-title
   → If 200: Compare metadata, return verified result
   → If 404: DOI is invalid, continue to search

2. If no DOI (or DOI lookup failed):
   Build query:
   - query.bibliographic={title}
   - query.author={author} (if provided)
   - filter=from-pub-date:{year-1},until-pub-date:{year+1} (if year provided)
   - rows=5
   - sort=score&order=desc
   - select=DOI,title,author,published,container-title,score
   - mailto=...

   GET /works?{query}
   → Check top result:
     - score > 50 (threshold)
     - Author family name matches (fuzzy)
     - Year within ±1
   → If match: Return DOI and metadata
   → If no match: Return not found (exit 1)

3. NEVER fabricate a DOI or metadata
```

---

## Brave Search API — Detailed Specification

**Base URL**: `https://api.search.brave.com/res/v1/web/search`

### Authentication

- **Header**: `X-Subscription-Token: {BRAVE_API_KEY}`
- **Obtain key**: https://api-dashboard.search.brave.com

### Pricing & Rate Limits

| Tier | Rate Limit | Monthly Quota | Price |
|------|------------|---------------|-------|
| Free AI | 1 req/sec | 2,000 queries | $0 |
| Base AI | 20 req/sec | 20M queries | $5/1000 |
| Pro AI | 50 req/sec | Unlimited | $9/1000 |

**Note**: Free tier requires credit card for identity verification but no charges.

### Query Parameters

#### Required
- `q` (string): Search query, max 400 characters, 50 words
  - Use `site:domain.com` operator for site-specific search

#### Result Control
- `count` (int): Results per page, max 20
- `offset` (int): Pagination, **max 9** (limits total to 200 results)
- `result_filter` (string): Comma-separated types to include
  - Values: `web`, `news`, `videos`, `discussions`, `faq`, `infobox`
  - Use `web` only for academic searches

#### Date Filtering
- `freshness` (string): Filter by recency
  - `pd`: Past 24 hours
  - `pw`: Past week
  - `pm`: Past month
  - `py`: Past year
  - `YYYY-MM-DDtoYYYY-MM-DD`: Custom date range

#### Quality Options
- `spellcheck` (bool): Enable query correction, default true
- `text_decorations` (bool): Include highlight markers, default true
  - Set `false` for clean text output
- `extra_snippets` (bool): Return up to 5 additional excerpts per result

#### Localization
- `country` (string): 2-char country code (e.g., `US`)
- `search_lang` (string): Preferred language (e.g., `en`)

### Response Structure

```json
{
  "type": "search",
  "query": {
    "original": "site:plato.stanford.edu free will",
    "altered": "..."
  },
  "web": {
    "results": [
      {
        "title": "Free Will - Stanford Encyclopedia of Philosophy",
        "url": "https://plato.stanford.edu/entries/freewill/",
        "description": "Main snippet text...",
        "page_age": "2023-05-15T00:00:00",
        "extra_snippets": ["Additional context 1", "Additional context 2"],
        "meta_url": {
          "scheme": "https",
          "hostname": "plato.stanford.edu",
          "path": "/entries/freewill/"
        },
        "article": {
          "author": "Timothy O'Connor",
          "date": "2023-05-15",
          "publisher": "Stanford Encyclopedia of Philosophy"
        }
      }
    ]
  }
}
```

### Key Response Fields

| Field | Description | Use Case |
|-------|-------------|----------|
| `title` | Page title | Entry name |
| `url` | Full URL | For WebFetch |
| `description` | Main snippet | Quick summary |
| `page_age` | Publication/update date | Recency check |
| `extra_snippets` | Additional excerpts | More context |
| `article.author` | Author name (when available) | Attribution |
| `article.date` | Article date (when available) | Dating |

### Pagination Limits

**Critical**: Maximum offset is 9
- Each page: up to 20 results
- Maximum retrievable: 10 pages × 20 = **200 results total**
- For comprehensive coverage, use multiple query variations

### Rate Limiting Strategy

```python
import time

class BraveRateLimiter:
    """Enforces 1 req/sec for free tier."""

    def __init__(self):
        self.last_request = 0
        self.min_interval = 1.1  # Slightly over 1 sec for safety

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()
```

### Site-Specific Search Patterns

**SEP Search**:
```
q=site:plato.stanford.edu {query}
count=20
extra_snippets=true
text_decorations=false
result_filter=web
```

**PhilPapers Search**:
```
q=site:philpapers.org {query}
count=20
extra_snippets=true
text_decorations=false
result_filter=web
freshness=py  # Optional: focus on recent entries
```

### Error Handling

- **429 Too Many Requests**: Rate limit exceeded, implement backoff
- **401 Unauthorized**: Invalid or missing API key
- **400 Bad Request**: Invalid query parameters

---

## SEP Content Extraction — BeautifulSoup Specification

**Purpose**: Extract structured content from SEP articles without API costs.

**Why BeautifulSoup instead of WebFetch?**
- SEP articles have consistent, predictable HTML structure
- Can extract specific sections, bibliography, related entries
- Bibliography parsing enables citation chaining
- No API costs (SEP is freely accessible)
- More structured output than raw text

### SEP Article Structure

All SEP articles follow this HTML pattern:

```html
<div id="preamble">...</div>           <!-- Abstract/introduction -->
<div id="main-text">
  <div id="toc">...</div>              <!-- Table of contents -->
  <h2 id="Sec1">1. Section Title</h2>
  <p>Content...</p>
  <h3 id="Sec1.1">1.1 Subsection</h3>
  ...
</div>
<div id="bibliography">
  <h2>Bibliography</h2>
  <ul>
    <li>Anscombe, G.E.M., 1957, <em>Intention</em>, Oxford: Blackwell.</li>
    ...
  </ul>
</div>
<div id="related-entries">
  <h2>Related Entries</h2>
  <p><a href="/entries/action/">action</a> | <a href="/entries/agency/">agency</a> | ...</p>
</div>
<div id="academic-tools">...</div>      <!-- Author info, dates -->
```

### Key Extraction Targets

| Element | Selector | Use Case |
|---------|----------|----------|
| Preamble | `#preamble` | Quick article summary |
| Sections | `h2[id^="Sec"], h3[id^="Sec"]` | Structured content |
| Bibliography | `#bibliography ul li` | Cited works → citation chaining |
| Related entries | `#related-entries a` | Topic expansion |
| Author | `.author-name` or parse academic-tools | Attribution |
| Dates | `#publication-date`, `#modified-date` | Recency |

### Parsing Strategy

```python
from bs4 import BeautifulSoup
import requests

def fetch_sep_article(entry_name: str) -> dict:
    """Fetch and parse SEP article."""
    url = f"https://plato.stanford.edu/entries/{entry_name}/"
    response = requests.get(url, headers={"User-Agent": "PhiloResearchBot/1.0"})
    soup = BeautifulSoup(response.text, 'lxml')

    return {
        "url": url,
        "title": soup.find("h1").get_text(strip=True),
        "preamble": extract_preamble(soup),
        "toc": extract_toc(soup),
        "sections": extract_sections(soup),
        "bibliography": extract_bibliography(soup),
        "related_entries": extract_related(soup),
        "metadata": extract_metadata(soup)
    }

def extract_bibliography(soup) -> list:
    """Extract bibliography entries for citation chaining."""
    bib_section = soup.find("div", id="bibliography")
    if not bib_section:
        return []
    entries = []
    for li in bib_section.find_all("li"):
        entries.append({
            "text": li.get_text(strip=True),
            "html": str(li)  # Preserve italics for title extraction
        })
    return entries
```

### Rate Limiting

Even though SEP is free, be polite:

```python
class SEPRateLimiter:
    """Polite rate limiting for SEP requests."""

    def __init__(self):
        self.last_request = 0
        self.min_interval = 1.0  # 1 request per second

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()
```

### SEP Workflow Integration

```
Phase 1: Discovery (Brave API)
  search_sep.py "free will" → [article URLs]

Phase 2: Content Extraction (BeautifulSoup)
  fetch_sep.py freewill → structured JSON with sections, bibliography

Phase 3: Citation Chaining
  Parse bibliography entries → s2_search.py or verify_paper.py
  → Find DOIs for works cited in SEP article

Phase 4: Topic Expansion
  Extract related_entries → fetch additional SEP articles
```

---

## Script Specifications

### s2_search.py
```python
# Semantic Scholar paper search with relevance ranking or bulk retrieval

# Usage:
#   python s2_search.py "free will compatibilism" --limit 20
#   python s2_search.py "moral responsibility" --bulk --year 2020-2024
#   python s2_search.py "Frankfurt cases" --field Philosophy --min-citations 10

# Input:
#   query: Search string
#   --bulk: Use bulk search (no ranking, up to 1000 results)
#   --limit N: Number of results (default 20, max 100 for relevance, 1000 for bulk)
#   --year YYYY or YYYY-YYYY: Year filter
#   --field FIELD: Field of study filter (e.g., Philosophy)
#   --min-citations N: Minimum citation count

# Output: JSON array
# [
#   {
#     "paperId": "...",
#     "title": "...",
#     "authors": [{"name": "...", "authorId": "..."}],
#     "year": 2021,
#     "abstract": "...",
#     "citationCount": 45,
#     "doi": "10.xxx/...",  # extracted from externalIds
#     "url": "https://semanticscholar.org/paper/..."
#   }
# ]

# Implements: Rate limiting (1 req/sec), exponential backoff on 429
```

### s2_citations.py
```python
# Traverse citations and references for a paper

# Usage:
#   python s2_citations.py DOI:10.1111/j.1933-1592.2004.tb00342.x --references
#   python s2_citations.py CorpusId:12345 --citations --influential-only
#   python s2_citations.py "URL:https://arxiv.org/abs/..." --both

# Input:
#   paper_id: Paper identifier (DOI:, CorpusId:, ARXIV:, URL:, or SHA)
#   --references: Get papers this paper cites
#   --citations: Get papers that cite this paper
#   --both: Get both directions
#   --influential-only: Filter to influential citations only
#   --limit N: Max results per direction (default 100, max 1000)

# Output: JSON object
# {
#   "paper": {"paperId": "...", "title": "..."},
#   "references": [...],  # if requested
#   "citations": [...]    # if requested
# }

# Implements: Rate limiting, exponential backoff
```

### s2_batch.py
```python
# Batch fetch paper details for multiple IDs

# Usage:
#   python s2_batch.py --ids "DOI:10.xxx,CorpusId:123,DOI:10.yyy"
#   python s2_batch.py --file paper_ids.txt

# Input:
#   --ids: Comma-separated paper IDs
#   --file: File with one paper ID per line
#   --fields: Override default fields

# Output: JSON array of paper objects

# Limits: Max 500 IDs per call
# Implements: Rate limiting, exponential backoff
```

### s2_recommend.py
```python
# Get paper recommendations based on seed papers

# Usage:
#   python s2_recommend.py --positive "DOI:10.xxx,DOI:10.yyy"
#   python s2_recommend.py --positive "DOI:10.xxx" --negative "DOI:10.zzz" --limit 50
#   python s2_recommend.py --for-paper DOI:10.xxx

# Input:
#   --positive: Comma-separated IDs of papers to find similar to
#   --negative: Comma-separated IDs of papers to avoid similarity to
#   --for-paper: Single paper ID for single-paper recommendations
#   --limit N: Number of recommendations (default 100, max 500)

# Output: JSON array of recommended papers

# Implements: Rate limiting, exponential backoff
```

### search_arxiv.py
```python
# Search arXiv for preprints and recent papers

# Usage:
#   python search_arxiv.py "free will consciousness"
#   python search_arxiv.py "AI ethics" --category cs.AI --limit 50
#   python search_arxiv.py "epistemic injustice" --recent
#   python search_arxiv.py --id "2301.00001"
#   python search_arxiv.py --author "Chalmers" --title "consciousness"

# Input:
#   query: Search terms (searches all fields by default)
#   --author NAME: Filter by author name (au: prefix)
#   --title TERMS: Filter by title (ti: prefix)
#   --abstract TERMS: Filter by abstract (abs: prefix)
#   --category CAT: Filter by arXiv category (e.g., cs.AI, cs.CY, physics.hist-ph)
#   --id ID: Lookup specific arXiv ID (e.g., 2301.00001)
#   --limit N: Max results (default 20, max 2000)
#   --recent: Sort by submission date (most recent first)
#   --year YYYY: Filter to specific year
#   --year-from YYYY: Filter from year onwards

# Output: JSON array
# [
#   {
#     "arxiv_id": "2301.00001",
#     "title": "Paper Title",
#     "authors": ["First Author", "Second Author"],
#     "abstract": "Full abstract text...",
#     "published": "2023-01-15",
#     "updated": "2023-02-20",
#     "primary_category": "cs.AI",
#     "categories": ["cs.AI", "cs.CY"],
#     "doi": "10.xxxx/xxxxx",       # if available
#     "journal_ref": "Nature 2023", # if published
#     "pdf_url": "https://arxiv.org/pdf/2301.00001.pdf",
#     "url": "https://arxiv.org/abs/2301.00001"
#   }
# ]

# Implements: 3-second delay between requests (arXiv requirement)
# Uses: arxiv.py library for robust API handling
# Note: Best for AI ethics, computational philosophy, formal epistemology
```

### search_openalex.py
```python
# Search OpenAlex for broad academic paper discovery and verification

# Usage:
#   python search_openalex.py "free will compatibilism"
#   python search_openalex.py "moral responsibility" --year 2020-2024 --limit 50
#   python search_openalex.py --doi "10.2307/2024717"
#   python search_openalex.py --id "W2741809807"
#   python search_openalex.py "epistemic injustice" --oa-only --min-citations 10
#   python search_openalex.py --cites "W2741809807" --limit 100
#   python search_openalex.py "Frankfurt" --author --limit 20

# Input:
#   query: Search terms (searches title and abstract)
#   --doi DOI: Direct lookup by DOI (returns single paper)
#   --id OPENALEX_ID: Direct lookup by OpenAlex ID (e.g., W2741809807)
#   --author: Search for authors instead of works
#   --cites OPENALEX_ID: Find papers citing a specific work
#   --refs OPENALEX_ID: Find papers referenced by a work
#   --year YYYY or YYYY-YYYY: Filter by publication year or range
#   --limit N: Max results (default 25, max 200 per page)
#   --oa-only: Only open access papers
#   --min-citations N: Minimum citation count
#   --type TYPE: Filter by work type (journal-article, book, book-chapter, etc.)
#   --select FIELDS: Comma-separated fields to return (for efficiency)
#   --sample N: Random sample of N papers (for exploratory search)

# Output: JSON array (or single object for --doi/--id)
# [
#   {
#     "openalex_id": "W2741809807",
#     "doi": "10.2307/2024717",
#     "title": "Freedom of the Will and the Concept of a Person",
#     "authors": [
#       {
#         "name": "Harry G. Frankfurt",
#         "openalex_id": "A5027479191",
#         "orcid": "0000-0001-2345-6789",  # if available
#         "institutions": ["Princeton University"]
#       }
#     ],
#     "publication_year": 1971,
#     "publication_date": "1971-01-01",
#     "abstract": "Full abstract text...",  # Generated from inverted index
#     "cited_by_count": 3500,
#     "type": "journal-article",
#     "source": {
#       "name": "The Journal of Philosophy",
#       "issn": "0022-362X",
#       "type": "journal"
#     },
#     "open_access": {
#       "is_oa": true,
#       "oa_status": "gold",
#       "oa_url": "https://..."
#     },
#     "referenced_works_count": 15,
#     "topics": ["Free Will", "Moral Responsibility"],
#     "url": "https://openalex.org/W2741809807"
#   }
# ]

# Author search output (--author):
# [
#   {
#     "openalex_id": "A5027479191",
#     "name": "Harry G. Frankfurt",
#     "orcid": "0000-0001-2345-6789",
#     "works_count": 47,
#     "cited_by_count": 12500,
#     "affiliations": ["Princeton University"],
#     "url": "https://openalex.org/A5027479191"
#   }
# ]

# Implements: pyalex library with polite pool (config.email)
# Rate limiting: 10 req/sec, automatic retries on 429
# Note: Larger database than Semantic Scholar, good for comprehensive coverage
```

### search_sep.py
```python
# DISCOVERY: Find relevant SEP articles via Brave API
# For content extraction, use fetch_sep.py instead

# Usage:
#   python search_sep.py "free will"
#   python search_sep.py "compatibilism determinism" --limit 10
#   python search_sep.py "moral responsibility" --all-pages

# Input:
#   query: Search terms
#   --limit N: Max results (default 20, max 200)
#   --all-pages: Fetch all available pages (up to 200 results)
#   --extra-snippets: Include additional excerpts

# Output: JSON array
# [
#   {
#     "title": "Free Will - Stanford Encyclopedia of Philosophy",
#     "url": "https://plato.stanford.edu/entries/freewill/",
#     "entry_name": "freewill",  # Extracted for use with fetch_sep.py
#     "snippet": "Main description text...",
#     "extra_snippets": ["...", "..."],  # if --extra-snippets
#     "page_age": "2023-05-15",           # when available
#     "author": "Timothy O'Connor"        # when available
#   }
# ]

# API params used:
#   q=site:plato.stanford.edu {query}
#   count=20
#   offset=0..9 (for pagination)
#   extra_snippets=true (if requested)
#   text_decorations=false
#   result_filter=web

# Implements: Rate limiting (1 req/sec), exponential backoff on 429
# Note: Max 200 results due to offset limit of 9
# Typical workflow: search_sep.py → fetch_sep.py for full content
```

### fetch_sep.py
```python
# EXTRACTION: Fetch and parse SEP article content via BeautifulSoup
# Use after search_sep.py to get structured content

# Usage:
#   python fetch_sep.py freewill
#   python fetch_sep.py https://plato.stanford.edu/entries/freewill/
#   python fetch_sep.py freewill --sections "preamble,1,2,bibliography"
#   python fetch_sep.py freewill --bibliography-only
#   python fetch_sep.py freewill --related-only

# Input:
#   entry: Entry name (e.g., "freewill") or full URL
#   --sections LIST: Comma-separated sections to extract (default: all)
#     Special values: "preamble", "bibliography", "related", "toc"
#     Section numbers: "1", "2.1", "3.2.1", etc.
#   --bibliography-only: Only extract bibliography (for citation chaining)
#   --related-only: Only extract related entries (for topic expansion)
#   --include-html: Include raw HTML in addition to text

# Output: JSON object
# {
#   "url": "https://plato.stanford.edu/entries/freewill/",
#   "entry_name": "freewill",
#   "title": "Free Will",
#   "author": "Timothy O'Connor",
#   "first_published": "2002-01-07",
#   "last_updated": "2024-03-15",
#   "preamble": "Free will is a philosophical concept referring to...",
#   "toc": [
#     {"id": "1", "title": "Introduction", "level": 1},
#     {"id": "1.1", "title": "The Concept of Free Will", "level": 2},
#     {"id": "2", "title": "The Powers of Agency", "level": 1},
#     ...
#   ],
#   "sections": {
#     "1": {
#       "id": "1",
#       "title": "Introduction",
#       "content": "Section text content..."
#     },
#     "1.1": {
#       "id": "1.1",
#       "title": "The Concept of Free Will",
#       "content": "Subsection text content..."
#     },
#     ...
#   },
#   "bibliography": [
#     {
#       "text": "Anscombe, G.E.M., 1957, Intention, Oxford: Blackwell.",
#       "parsed": {  # Best-effort parsing
#         "authors": ["Anscombe, G.E.M."],
#         "year": "1957",
#         "title": "Intention",
#         "publisher": "Oxford: Blackwell"
#       }
#     },
#     ...
#   ],
#   "related_entries": [
#     {"title": "action", "url": "/entries/action/", "entry_name": "action"},
#     {"title": "compatibilism", "url": "/entries/compatibilism/", "entry_name": "compatibilism"},
#     ...
#   ]
# }

# With --bibliography-only:
# {
#   "url": "...",
#   "entry_name": "freewill",
#   "bibliography": [...]
# }

# Implements: Polite rate limiting (1 req/sec)
# Dependencies: requests, beautifulsoup4, lxml
```

### search_philpapers.py
```python
# Search PhilPapers via Brave API

# Usage:
#   python search_philpapers.py "epistemic injustice"
#   python search_philpapers.py "virtue epistemology" --limit 40
#   python search_philpapers.py "phenomenal consciousness" --recent

# Input:
#   query: Search terms
#   --limit N: Max results (default 20, max 200)
#   --all-pages: Fetch all available pages (up to 200 results)
#   --recent: Filter to past year only (freshness=py)
#   --extra-snippets: Include additional excerpts

# Output: JSON array
# [
#   {
#     "title": "Epistemic Injustice: Power and the Ethics of Knowing",
#     "url": "https://philpapers.org/rec/FRIEIP",
#     "snippet": "Description text...",
#     "extra_snippets": ["...", "..."],  # if --extra-snippets
#     "page_age": "2023-01-15",           # when available
#     "authors": ["Miranda Fricker"]      # parsed from title/snippet when possible
#   }
# ]

# API params used:
#   q=site:philpapers.org {query}
#   count=20
#   offset=0..9 (for pagination)
#   freshness=py (if --recent)
#   extra_snippets=true (if requested)
#   text_decorations=false
#   result_filter=web

# Implements: Rate limiting (1 req/sec), exponential backoff on 429
# Note: Max 200 results due to offset limit of 9
```

### verify_paper.py
```python
# Verify paper existence and retrieve/validate DOI via CrossRef

# Usage:
#   python verify_paper.py --title "Freedom of the Will and the Concept of a Person"
#   python verify_paper.py --title "..." --author "Frankfurt" --year 1971
#   python verify_paper.py --doi "10.2307/2024717"
#   python verify_paper.py --doi "10.2307/2024717" --title "..." --verify-metadata

# Input:
#   --title "...": Paper title (required unless --doi provided)
#   --author "...": Author family name (optional, improves matching)
#   --year YYYY: Publication year (optional, filters results ±1 year)
#   --doi "...": DOI to verify directly (skips search)
#   --verify-metadata: When using --doi, also verify title/author match
#   --mailto "...": Email for polite pool (default: uses CROSSREF_MAILTO env var)

# Output: JSON object
# {
#   "verified": true,
#   "doi": "10.2307/2024717",
#   "title": "Freedom of the Will and the Concept of a Person",
#   "authors": [{"given": "Harry G.", "family": "Frankfurt"}],
#   "year": 1971,
#   "container_title": "The Journal of Philosophy",
#   "publisher": "Journal of Philosophy, Inc.",
#   "type": "journal-article",
#   "score": 142.5,  # Only present for search results
#   "method": "doi_lookup" | "bibliographic_search"
# }

# On failure:
# {
#   "verified": false,
#   "error": "Paper not found in CrossRef",
#   "query": {"title": "...", "author": "...", "year": ...}
# }
# Exit code 1

# Workflow:
# 1. If --doi provided: Direct lookup via GET /works/{doi}
# 2. Else: Search via GET /works?query.bibliographic=...&query.author=...
# 3. Validate: score > 50, author match, year ±1
# 4. Return verified metadata or exit 1

# CRITICAL: Exit 1 and print error JSON if not found—NEVER fabricate
# Implements: Adaptive rate limiting via X-Rate-Limit-* headers
```

### requirements.txt
```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
arxiv>=2.0.0
pyalex>=0.14
```

**Dependency notes**:
- `requests`: HTTP client for all API calls and SEP fetching
- `beautifulsoup4`: HTML parsing for SEP content extraction
- `lxml`: Fast HTML parser backend for BeautifulSoup (recommended over html.parser)
- `arxiv`: Python wrapper for arXiv API with built-in rate limiting
- `pyalex`: Python wrapper for OpenAlex API with polite pool and retry handling

---

## SKILL.md Structure

```yaml
---
name: philosophy-research
description: Search philosophy literature across SEP, PhilPapers, and Semantic Scholar. Supports paper discovery, citation traversal, and recommendations. Verifies citations via CrossRef.
---
```

**Body sections**:

### 1. Overview
Brief description of available capabilities and when to use this skill.

### 2. Search Workflow

**Phase 1: SEP (Most Authoritative)**
- `search_sep.py "{topic}"` → discover relevant SEP articles
- `fetch_sep.py {entry}` → extract structured content (preamble, sections, bibliography)
- Parse bibliography for foundational works
- Follow related entries for topic expansion

**Phase 2: PhilPapers**
- `search_philpapers.py "{topic}"` → philosophy-specific papers
- Cross-reference with SEP bibliography

**Phase 3: Extended Academic Search**
- Semantic Scholar → `s2_search.py` (broad academic search)
- OpenAlex → `search_openalex.py` (250M+ works, cross-disciplinary)
- arXiv → `search_arxiv.py` (preprints, AI ethics, recent work)

**Phase 4: Citation Traversal**
- Get references for foundational papers → `s2_citations.py --references`
- Get citing papers for forward chaining → `s2_citations.py --citations`
- Focus on influential citations with `--influential-only`
- Parse SEP bibliographies → feed to `s2_search.py` or `verify_paper.py`

**Phase 5: Expansion**
- Use `s2_recommend.py` to find related papers not connected by citations
- Provide positive seeds (relevant papers) and negative seeds (irrelevant)
- Use `fetch_sep.py --related-only` to expand via SEP connections

**Phase 6: Batch Details**
- Collect paper IDs from all phases
- Use `s2_batch.py` to efficiently fetch full metadata

### 3. SEP Content Access

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

### 4. WebFetch Usage

**Use WebFetch only when skill scripts don't provide the needed content:**

- PhilPapers entry pages for additional metadata
- Publisher pages for paper details not in S2
- DOI resolution verification (`https://doi.org/{doi}`)
- Any other web content not covered by skill scripts

**Do NOT use WebFetch for**:
- SEP articles → use `fetch_sep.py` instead (structured output)
- Paper abstracts → use `s2_search.py` or `s2_batch.py`

### 5. Available Scripts

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

### 6. Verification Requirements

- **Never fabricate citations** — only include papers found via scripts
- **Verify DOIs** via `verify_paper.py` when S2 lacks DOI
- **Omit DOI field** if verification fails (never invent)
- **Report gaps** if expected papers are not found

### 7. Environment Setup

```bash
export S2_API_KEY="your-semantic-scholar-key"  # Recommended
export BRAVE_API_KEY="your-brave-key"           # Required for SEP/PhilPapers discovery
export CROSSREF_MAILTO="your@email.com"         # Required for CrossRef polite pool
export OPENALEX_EMAIL="your@email.com"          # Recommended for OpenAlex polite pool
pip install requests beautifulsoup4 lxml pyalex arxiv
```

---

## Agent Integration

### 1. domain-literature-researcher

Modify `domain-literature-researcher.md`:

```yaml
# Change frontmatter
---
name: domain-literature-researcher
description: ...
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
model: sonnet
---
```

Update search process instructions to use skill scripts:

**Phase 1: SEP (Stanford Encyclopedia of Philosophy)**
*Most authoritative source for philosophy — start here*
1. `search_sep.py "{topic}"` → discover relevant SEP articles
2. `fetch_sep.py {entry_name} --sections "preamble,1,2,bibliography"` → extract content
3. Read preamble and key sections for domain overview
4. Parse bibliography for foundational works cited
5. `fetch_sep.py {entry_name} --related-only` → expand to related topics

**Phase 2: PhilPapers**
*Philosophy-specific academic papers*
1. `search_philpapers.py "{topic}"` → note key papers
2. Cross-reference with SEP bibliography entries
3. Identify papers not covered by SEP

**Phase 3: Extended Academic Search**
*Broader coverage and cross-disciplinary work*
1. **Semantic Scholar**: `s2_search.py "{topic}" --field Philosophy --year 2015-2025`
2. **OpenAlex**: `search_openalex.py "{topic}" --year 2015-2025` → broad coverage, cross-disciplinary
3. **arXiv**: `search_arxiv.py "{topic}" --category cs.AI --recent` → preprints, AI ethics

**Phase 4: Citation Chaining**
1. Identify foundational papers from SEP bibliography + PhilPapers + S2 search
2. `s2_citations.py {paper_id} --both --influential-only`
3. `s2_recommend.py --positive {foundational_ids}`
4. Parse SEP bibliographies → `verify_paper.py` → get DOIs

**Phase 5: Batch Metadata**
1. Collect all paper IDs from all phases
2. `s2_batch.py --ids "{all_ids}"`
3. Use structured SEP content for writing CORE ARGUMENT notes

**When to prioritize arXiv**:
- AI ethics, AI alignment, machine learning interpretability topics
- Recent/cutting-edge work not yet in journals
- Computational philosophy, formal epistemology
- Cross-disciplinary philosophy-CS research

**When to prioritize OpenAlex**:
- Comprehensive literature coverage (250M+ works)
- Cross-disciplinary topics (philosophy published in non-philosophy venues)
- Finding open access versions of paywalled papers
- Papers not in Semantic Scholar or arXiv
- Author searches with affiliation information
- Citation analysis with high coverage

### 2. citation-validator

Modify `citation-validator.md`:

```yaml
# Change frontmatter
---
name: citation-validator
description: ...
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
model: sonnet
---
```

Update validation workflow to use skill scripts:

**Validation Method 1: Semantic Scholar Lookup** (preferred)
- Extract DOI or title from BibTeX entry
- `s2_search.py "{title}" --limit 5` or use DOI directly
- If found: verify metadata matches (authors, year, venue)
- If S2 has the paper, it exists — high confidence

**Validation Method 2: CrossRef Verification**
- `verify_paper.py --title "{title}" --author "{author}" --year {year}`
- Returns match confidence score (threshold 0.85)
- Confirms DOI validity

**Validation Method 3: DOI Resolution**
- WebFetch `https://doi.org/{doi}` to verify DOI resolves
- Check metadata on landing page

**Validation Method 4: SEP/PhilPapers Check** (for non-journal sources)
- `search_sep.py "{title}"` for SEP entries
- `search_philpapers.py "{title}"` for PhilPapers entries
- WebFetch URL to verify it resolves

**Validation Method 5: arXiv Lookup** (for preprints)
- `search_arxiv.py --id "{arxiv_id}"` for direct arXiv ID lookup
- `search_arxiv.py --title "{title}" --author "{author}"` for title/author search
- Useful for: AI ethics papers, recent preprints, CS/philosophy cross-disciplinary work
- arXiv provides: full abstract, DOI (if published), journal_ref

**Validation Method 6: OpenAlex Lookup** (broad coverage)
- `search_openalex.py --doi "{doi}"` for direct DOI verification
- `search_openalex.py "{title}"` for title search with year filtering
- Useful for: Papers not found in S2 or arXiv, cross-disciplinary work
- OpenAlex provides: 250M+ works, open access links, comprehensive metadata
- **Batch validation**: `search_openalex.py --doi "{doi1}" --doi "{doi2}"...` (up to 50)

**Updated Validation Workflow**:
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

**Batch Validation** (efficiency):
- Collect all DOIs from BibTeX file
- `s2_batch.py --ids "DOI:10.xxx,DOI:10.yyy,..."` (up to 500)
- For DOIs not found in S2, use OpenAlex batch: `Works().filter_or(doi=[...])` (up to 50)
- Compare batch response against BibTeX metadata
- Only use individual lookups for entries not found in batch
- For arXiv entries, use individual lookups (no batch API)

---

## Implementation Order

1. **Rate limiter module** — shared utility for S2, Brave, SEP, CrossRef, arXiv, OpenAlex
2. `verify_paper.py` — foundation for accuracy (CrossRef)
3. `s2_search.py` — primary paper discovery
4. `s2_citations.py` — citation traversal
5. `s2_batch.py` — efficient batch retrieval
6. `s2_recommend.py` — expansion via recommendations
7. `search_openalex.py` — broad academic search (pyalex)
8. `search_arxiv.py` — arXiv preprint search (arxiv.py)
9. `search_sep.py` — SEP discovery (Brave API)
10. `fetch_sep.py` — SEP content extraction (BeautifulSoup)
11. `search_philpapers.py` — PhilPapers search (Brave API)
12. `SKILL.md` — documentation
13. Test all scripts
14. Update `domain-literature-researcher.md`
15. Update `citation-validator.md`

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
- [ ] S2 rate limiter enforces 1 req/sec with exponential backoff

### CrossRef Scripts
- [ ] `verify_paper.py --doi 10.2307/2024717` returns verified Frankfurt (1971) metadata
- [ ] `verify_paper.py --title "..." --author Frankfurt` finds DOI via bibliographic search
- [ ] `verify_paper.py` returns exit code 1 for non-existent papers (never fabricates)
- [ ] CrossRef rate limiter adapts to `X-Rate-Limit-*` headers

### arXiv Scripts
- [ ] `search_arxiv.py "AI ethics"` returns papers with abstracts and metadata
- [ ] `search_arxiv.py --id "2301.00001"` returns specific paper by arXiv ID
- [ ] `search_arxiv.py --category cs.AI --recent` filters by category and sorts by date
- [ ] `search_arxiv.py --author "Chalmers" --title "consciousness"` uses field queries
- [ ] arXiv rate limiter enforces 3 sec delay between requests
- [ ] Output includes: arxiv_id, title, authors, abstract, doi (if available), pdf_url

### OpenAlex Scripts
- [ ] `search_openalex.py "free will"` returns papers with abstracts and DOIs
- [ ] `search_openalex.py --doi "10.2307/2024717"` returns verified Frankfurt (1971) metadata
- [ ] `search_openalex.py --id "W2741809807"` returns paper by OpenAlex ID
- [ ] `search_openalex.py --cites "W2741809807"` returns papers citing a work
- [ ] `search_openalex.py --year 2020-2024` filters by publication year range
- [ ] `search_openalex.py --oa-only` filters to open access papers only
- [ ] `search_openalex.py --author "Frankfurt"` searches for authors
- [ ] pyalex polite pool configured with OPENALEX_EMAIL
- [ ] Rate limiter enforces 10 req/sec with exponential backoff on 429
- [ ] Output includes: openalex_id, doi, title, authors, abstract, cited_by_count, open_access

### Brave Search Scripts
- [ ] `search_sep.py "free will"` returns SEP article URLs with snippets
- [ ] `search_sep.py` extracts `entry_name` for use with `fetch_sep.py`
- [ ] `search_philpapers.py "epistemic injustice"` returns PhilPapers URLs
- [ ] `search_philpapers.py --recent` filters to past year
- [ ] `search_sep.py --all-pages` paginates correctly (max 200 results)
- [ ] Brave rate limiter enforces 1 req/sec with backoff on 429

### SEP Content Extraction
- [ ] `fetch_sep.py freewill` returns structured JSON with all sections
- [ ] `fetch_sep.py freewill --sections "preamble,1,bibliography"` extracts specific sections
- [ ] `fetch_sep.py freewill --bibliography-only` extracts bibliography entries
- [ ] Bibliography parsing extracts author, year, title from entries
- [ ] `fetch_sep.py` extracts related entries with entry_names
- [ ] SEP rate limiter enforces polite 1 req/sec
- [ ] Workflow: `search_sep.py` → `fetch_sep.py` → bibliography → `s2_search.py`

### General
- [ ] All scripts return valid JSON
- [ ] `domain-literature-researcher` can complete a search without WebSearch
- [ ] `domain-literature-researcher` uses `fetch_sep.py` for SEP content (not WebFetch)
- [ ] `domain-literature-researcher` uses `search_arxiv.py` for AI ethics/preprints
- [ ] `domain-literature-researcher` uses `search_openalex.py` for broad academic coverage
- [ ] `citation-validator` can validate entries without WebSearch
- [ ] `citation-validator` can validate arXiv entries via `search_arxiv.py --id`
- [ ] `citation-validator` can validate via OpenAlex when S2 fails via `search_openalex.py`
- [ ] `citation-validator` batch validates DOIs efficiently via `s2_batch.py`
- [ ] No fabricated citations possible
