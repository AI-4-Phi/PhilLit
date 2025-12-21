# API Specifications Reference

Detailed API documentation for all data sources used by the philosophy-research skill.

---

## Semantic Scholar API

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

### Endpoints

#### 1. Paper Relevance Search
- **Path**: `GET /graph/v1/paper/search`
- **Use**: Ranked search results for discovery
- **Params**:
  - `query` (required): Plain text, no special syntax
  - `fields`: Comma-separated (see Fields section)
  - `offset`, `limit`: Pagination (limit <= 100)
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
  - `offset`, `limit`: Pagination (limit <= 1,000)
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

### Fields Parameter

**Only request fields you need** - extra fields slow responses.

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

```
1. Start with foundational paper(s) identified in Phase 1
2. GET /paper/{id}/references -> Find sources the paper builds on
3. GET /paper/{id}/citations -> Find papers that build on it
4. Filter by isInfluential=true for high-signal connections
5. Use recommendations to find topically related papers missed by citations
6. Batch-fetch details for all discovered papers
```

---

## arXiv API

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

**Result fields**:
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
- `ti:` - Title
- `au:` - Author
- `abs:` - Abstract
- `cat:` - Category
- `all:` - All fields

**Boolean Operators**: `AND`, `OR`, `ANDNOT`

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

## OpenAlex API

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

## CrossRef API

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

### Endpoints

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
   -> If 200: Compare metadata, return verified result
   -> If 404: DOI is invalid, continue to search

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
   -> Check top result:
     - score > 50 (threshold)
     - Author family name matches (fuzzy)
     - Year within +/-1
   -> If match: Return DOI and metadata
   -> If no match: Return not found (exit 1)

3. NEVER fabricate a DOI or metadata
```

---

## Brave Search API

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
- Maximum retrievable: 10 pages x 20 = **200 results total**
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

## SEP Content Extraction (BeautifulSoup)

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
| Bibliography | `#bibliography ul li` | Cited works -> citation chaining |
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
  search_sep.py "free will" -> [article URLs]

Phase 2: Content Extraction (BeautifulSoup)
  fetch_sep.py freewill -> structured JSON with sections, bibliography

Phase 3: Citation Chaining
  Parse bibliography entries -> s2_search.py or verify_paper.py
  -> Find DOIs for works cited in SEP article

Phase 4: Topic Expansion
  Extract related_entries -> fetch additional SEP articles
```
