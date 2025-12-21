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

**Key Design Decisions**:
- Scripts output JSON; agents handle BibTeX conversion
- File-based rate limiting shared across scripts
- Graceful failure with partial results on API errors

---

## File Structure

```
.claude/skills/philosophy-research/
├── SKILL.md                    # Skill definition (includes JSON→BibTeX mapping)
├── scripts/
│   ├── rate_limiter.py         # Shared file-based rate limiter module
│   ├── check_setup.py          # Environment verification script
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
    ├── api-specifications.md
    ├── script-specifications.md
    ├── skill-and-agent-integration.md
    ├── philpapers-categories.txt
    └── philosophy-journals.txt
```

---

## Standard Output Schema

**CRITICAL**: All scripts MUST follow this output schema for consistency. Agents depend on this structure.

### Success Response

```json
{
  "status": "success",
  "source": "semantic_scholar",
  "query": "free will compatibilism",
  "results": [
    {
      "paperId": "abc123",
      "title": "Freedom of the Will and the Concept of a Person",
      "authors": [{"name": "Harry G. Frankfurt", "authorId": "12345"}],
      "year": 1971,
      "abstract": "What philosophers have lately...",
      "doi": "10.2307/2024717",
      "citationCount": 3500,
      "url": "https://semanticscholar.org/paper/abc123"
    }
  ],
  "count": 1,
  "errors": []
}
```

### Partial Failure Response

When some results retrieved but errors occurred (e.g., rate limit hit mid-pagination):

```json
{
  "status": "partial",
  "source": "semantic_scholar",
  "query": "free will compatibilism",
  "results": [...],
  "count": 8,
  "errors": [
    {
      "type": "rate_limit",
      "message": "429 error after 3 retries on page 2",
      "recoverable": true
    }
  ],
  "warning": "Retrieved 8 of expected ~20 results. Retry later for complete results."
}
```

### Complete Failure Response

```json
{
  "status": "error",
  "source": "semantic_scholar",
  "query": "free will compatibilism",
  "results": [],
  "count": 0,
  "errors": [
    {
      "type": "config_error",
      "message": "S2_API_KEY environment variable not set",
      "recoverable": false
    }
  ]
}
```

### Exit Codes

| Code | Meaning | When to Use |
|------|---------|-------------|
| 0 | Success or partial success | Results available (check `status` field) |
| 1 | No results found | Query returned empty; paper doesn't exist |
| 2 | Configuration error | Missing API key, invalid arguments |
| 3 | Unrecoverable API error | API down, authentication failed |

### Implementation Pattern

Every script must:

```python
import json
import sys

def output_success(source, query, results):
    print(json.dumps({
        "status": "success",
        "source": source,
        "query": query,
        "results": results,
        "count": len(results),
        "errors": []
    }, indent=2))
    sys.exit(0)

def output_partial(source, query, results, errors, warning):
    print(json.dumps({
        "status": "partial",
        "source": source,
        "query": query,
        "results": results,
        "count": len(results),
        "errors": errors,
        "warning": warning
    }, indent=2))
    sys.exit(0)  # Exit 0 because partial results are usable

def output_error(source, query, errors):
    print(json.dumps({
        "status": "error",
        "source": source,
        "query": query,
        "results": [],
        "count": 0,
        "errors": errors
    }, indent=2))
    sys.exit(1 if errors[0].get("type") == "not_found" else 2)
```

---

## File-Based Rate Limiter

**CRITICAL**: All scripts MUST use this shared rate limiter to prevent API bans when agents call multiple scripts in sequence.

### Implementation: `rate_limiter.py`

```python
"""
Shared file-based rate limiter for cross-script coordination.

Usage:
    from rate_limiter import RateLimiter

    limiter = RateLimiter("semantic_scholar", min_interval=1.1)
    limiter.wait()  # Blocks until safe to make request
    response = requests.get(...)
    limiter.record()  # Record successful request
"""

import time
import fcntl
import os
from pathlib import Path

class RateLimiter:
    """
    File-based rate limiter that coordinates across script invocations.
    Uses file locking to prevent race conditions.
    """

    # Lock file directory - use /tmp for cross-session persistence
    LOCK_DIR = Path("/tmp/philosophy_research_ratelimits")

    def __init__(self, api_name: str, min_interval: float):
        """
        Args:
            api_name: Identifier for the API (e.g., "semantic_scholar", "brave")
            min_interval: Minimum seconds between requests
        """
        self.api_name = api_name
        self.min_interval = min_interval
        self.LOCK_DIR.mkdir(exist_ok=True)
        self.lock_file = self.LOCK_DIR / f".ratelimit_{api_name}.lock"

    def wait(self):
        """Block until it's safe to make a request. Call BEFORE each API request."""
        with open(self.lock_file, 'a+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                content = f.read().strip()
                last_request = float(content) if content else 0
            except ValueError:
                last_request = 0

            elapsed = time.time() - last_request
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)

            fcntl.flock(f, fcntl.LOCK_UN)

    def record(self):
        """Record that a request was made. Call AFTER each successful API request."""
        with open(self.lock_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(str(time.time()))
            fcntl.flock(f, fcntl.LOCK_UN)

    def wait_and_record(self):
        """Convenience method: wait, then record. Use when you don't need to check response."""
        self.wait()
        self.record()


class ExponentialBackoff:
    """
    Exponential backoff for retry logic.

    Usage:
        backoff = ExponentialBackoff()
        for attempt in range(backoff.max_attempts):
            response = requests.get(...)
            if response.status_code == 429:
                if not backoff.wait(attempt):
                    break  # Max attempts exceeded
                continue
            break
    """

    def __init__(self, max_attempts: int = 5, base_delay: float = 1.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    def wait(self, attempt: int) -> bool:
        """
        Wait with exponential backoff.

        Returns:
            True if should retry, False if max attempts exceeded
        """
        if attempt >= self.max_attempts - 1:
            return False

        import random
        delay = (2 ** attempt) * self.base_delay + random.uniform(0, 1)
        time.sleep(delay)
        return True


# Pre-configured limiters for each API
LIMITERS = {
    "semantic_scholar": lambda: RateLimiter("semantic_scholar", 1.1),
    "brave": lambda: RateLimiter("brave", 1.1),
    "crossref": lambda: RateLimiter("crossref", 0.02),  # 50/sec, but be conservative
    "openalex": lambda: RateLimiter("openalex", 0.11),   # 10/sec
    "arxiv": lambda: RateLimiter("arxiv", 3.0),
    "sep_fetch": lambda: RateLimiter("sep_fetch", 1.0),
}

def get_limiter(api_name: str) -> RateLimiter:
    """Get a pre-configured rate limiter for the specified API."""
    if api_name not in LIMITERS:
        raise ValueError(f"Unknown API: {api_name}. Valid options: {list(LIMITERS.keys())}")
    return LIMITERS[api_name]()
```

### Lock Files Created

| API | Lock File | Interval |
|-----|-----------|----------|
| Semantic Scholar | `/tmp/philosophy_research_ratelimits/.ratelimit_semantic_scholar.lock` | 1.1s |
| Brave | `/tmp/philosophy_research_ratelimits/.ratelimit_brave.lock` | 1.1s |
| CrossRef | `/tmp/philosophy_research_ratelimits/.ratelimit_crossref.lock` | 0.02s |
| OpenAlex | `/tmp/philosophy_research_ratelimits/.ratelimit_openalex.lock` | 0.11s |
| arXiv | `/tmp/philosophy_research_ratelimits/.ratelimit_arxiv.lock` | 3.0s |
| SEP Fetch | `/tmp/philosophy_research_ratelimits/.ratelimit_sep_fetch.lock` | 1.0s |

---

## JSON to BibTeX Conversion

**CRITICAL**: Agents handle BibTeX conversion. This section defines the exact field mappings agents must use.

### Field Mapping Table

| Source | JSON Field | BibTeX Field | Transformation |
|--------|------------|--------------|----------------|
| **All** | `title` | `title` | Wrap in `{...}` to preserve capitalization |
| **All** | `year` / `publication_year` | `year` | Integer as string |
| **All** | `doi` | `doi` | Strip `https://doi.org/` prefix if present |
| **All** | `abstract` | *(use in note field)* | For CORE ARGUMENT section |
| **S2** | `authors[].name` | `author` | Join with ` and ` |
| **S2** | `journal.name` or `venue` | `journal` | Use for @article |
| **S2** | `paperId` | *(use in citation key)* | Not a BibTeX field |
| **S2** | `url` | `url` | Optional |
| **OpenAlex** | `authorships[].author.display_name` | `author` | Join with ` and ` |
| **OpenAlex** | `primary_location.source.display_name` | `journal` | Use for @article |
| **OpenAlex** | `id` | *(use in citation key)* | Strip `https://openalex.org/` |
| **arXiv** | `authors[]` | `author` | Join with ` and ` (already strings) |
| **arXiv** | `primary_category` | `keywords` | Optional |
| **arXiv** | `arxiv_id` | `eprint` | For @misc or @article |
| **arXiv** | `journal_ref` | `journal` | If published |

### Entry Type Selection

Agents MUST select BibTeX entry type based on these rules:

```
IF source is SEP:
    → @misc with howpublished = {Stanford Encyclopedia of Philosophy}

ELSE IF json.type == "book" OR json.publicationTypes contains "Book":
    → @book

ELSE IF json.type == "book-chapter" OR json.publicationTypes contains "BookChapter":
    → @incollection (requires booktitle field)

ELSE IF json.venue contains "Conference" OR json.publicationTypes contains "Conference":
    → @inproceedings (use venue as booktitle)

ELSE IF json.journal exists OR json.venue exists:
    → @article

ELSE IF json.arxiv_id exists AND json.journal_ref is empty:
    → @misc with note = {arXiv preprint}

ELSE:
    → @misc
```

### Citation Key Generation

Format: `{firstAuthorLastName}{year}{firstTitleWord}`

```python
def generate_citation_key(authors, year, title):
    """
    Generate BibTeX citation key.

    Examples:
        frankfurt1971freedom
        chalmers1996conscious
        vaswani2017attention
    """
    # Extract first author's last name
    if not authors:
        first_author = "unknown"
    else:
        # Handle "Last, First" or "First Last" formats
        name = authors[0] if isinstance(authors[0], str) else authors[0].get("name", "unknown")
        if "," in name:
            first_author = name.split(",")[0].strip()
        else:
            first_author = name.split()[-1] if name.split() else "unknown"

    # Clean and lowercase
    first_author = ''.join(c for c in first_author if c.isalnum()).lower()

    # Get first significant word from title (skip articles)
    skip_words = {'a', 'an', 'the', 'on', 'in', 'of', 'for', 'to'}
    title_words = title.lower().split()
    first_word = "untitled"
    for word in title_words:
        clean_word = ''.join(c for c in word if c.isalnum())
        if clean_word and clean_word not in skip_words:
            first_word = clean_word
            break

    return f"{first_author}{year}{first_word}"
```

### Author Name Formatting

BibTeX requires authors separated by ` and `:

```python
def format_authors_bibtex(authors_list):
    """
    Convert author list to BibTeX format.

    Input formats handled:
        - ["Harry G. Frankfurt", "John Smith"]  # arXiv style
        - [{"name": "Harry G. Frankfurt"}, ...]  # S2 style
        - [{"author": {"display_name": "..."}}]  # OpenAlex style

    Output: "Frankfurt, Harry G. and Smith, John"
    """
    names = []
    for author in authors_list:
        if isinstance(author, str):
            name = author
        elif isinstance(author, dict):
            # S2 format
            if "name" in author:
                name = author["name"]
            # OpenAlex format
            elif "author" in author and "display_name" in author["author"]:
                name = author["author"]["display_name"]
            else:
                continue
        else:
            continue

        # Convert "First Last" to "Last, First" if needed
        parts = name.split()
        if len(parts) >= 2 and "," not in name:
            name = f"{parts[-1]}, {' '.join(parts[:-1])}"

        names.append(name)

    return " and ".join(names)
```

### Complete BibTeX Generation Example

```python
def json_to_bibtex(paper, source, note_content):
    """
    Convert JSON paper object to BibTeX entry.

    Args:
        paper: JSON object from any search script
        source: "s2", "openalex", "arxiv", "sep"
        note_content: Pre-formatted note with CORE ARGUMENT, RELEVANCE, POSITION

    Returns:
        Complete BibTeX entry as string
    """
    # Extract fields based on source
    if source == "s2":
        authors = [a.get("name", "") for a in paper.get("authors", [])]
        year = paper.get("year", "")
        title = paper.get("title", "")
        doi = paper.get("doi", "")
        journal = paper.get("journal", {}).get("name") or paper.get("venue", "")

    elif source == "openalex":
        authors = [a["author"]["display_name"] for a in paper.get("authorships", []) if "author" in a]
        year = paper.get("publication_year", "")
        title = paper.get("title", "")
        doi = paper.get("doi", "").replace("https://doi.org/", "")
        journal = paper.get("primary_location", {}).get("source", {}).get("display_name", "")

    elif source == "arxiv":
        authors = paper.get("authors", [])
        year = paper.get("published", "")[:4] if paper.get("published") else ""
        title = paper.get("title", "")
        doi = paper.get("doi", "")
        journal = paper.get("journal_ref", "")

    elif source == "sep":
        authors = [paper.get("author", "")]
        year = paper.get("last_updated", "")[:4] if paper.get("last_updated") else ""
        title = paper.get("title", "")
        doi = ""
        journal = ""

    # Generate citation key
    key = generate_citation_key(authors, year, title)

    # Determine entry type
    entry_type = determine_entry_type(paper, source)

    # Format authors
    author_str = format_authors_bibtex(authors) if authors else ""

    # Build entry
    lines = [f"@{entry_type}{{{key},"]
    if author_str:
        lines.append(f'  author = {{{author_str}}},')
    lines.append(f'  title = {{{{{title}}}}},')  # Double braces to preserve caps
    if year:
        lines.append(f'  year = {{{year}}},')
    if journal and entry_type == "article":
        lines.append(f'  journal = {{{journal}}},')
    if doi:
        lines.append(f'  doi = {{{doi}}},')
    if note_content:
        lines.append(f'  note = {{{note_content}}},')
    lines.append(f'  keywords = {{Medium}}')  # Default importance
    lines.append('}')

    return '\n'.join(lines)
```

---

## SEP Bibliography Parsing

**IMPORTANT**: SEP bibliographies have highly variable formats. Parsing is BEST-EFFORT with raw text always preserved.

### Output Format

```json
{
  "bibliography": [
    {
      "raw": "Anscombe, G.E.M., 1957, Intention, Oxford: Blackwell.",
      "parsed": {
        "authors": ["Anscombe, G.E.M."],
        "year": "1957",
        "title": "Intention",
        "publisher": "Oxford: Blackwell"
      },
      "confidence": "high"
    },
    {
      "raw": "Kane, Robert (ed.), 2002, The Oxford Handbook of Free Will, Oxford: Oxford University Press.",
      "parsed": {
        "authors": ["Kane, Robert"],
        "year": "2002",
        "title": "The Oxford Handbook of Free Will",
        "publisher": "Oxford: Oxford University Press",
        "is_edited": true
      },
      "confidence": "high"
    },
    {
      "raw": "For more on this topic, see the entry on action.",
      "parsed": null,
      "confidence": "unparseable"
    },
    {
      "raw": "Smith, J. and Jones, K., forthcoming, 'New Work', Journal TBD.",
      "parsed": {
        "authors": ["Smith, J.", "Jones, K."],
        "year": "forthcoming",
        "title": "New Work"
      },
      "confidence": "low"
    }
  ]
}
```

### Confidence Levels

| Level | Meaning | Agent Action |
|-------|---------|--------------|
| `high` | All key fields extracted reliably | Use parsed data |
| `medium` | Some fields extracted, others uncertain | Use parsed data, verify via CrossRef |
| `low` | Partial extraction, may have errors | Prefer raw text, attempt CrossRef lookup |
| `unparseable` | Not a bibliographic reference | Skip this entry |

### Parsing Strategy

```python
import re

def parse_sep_bibliography_entry(raw_text):
    """
    Attempt to parse SEP bibliography entry.
    Returns (parsed_dict, confidence).
    """
    # Skip non-reference entries
    skip_patterns = [
        r'^See the entry',
        r'^For more on',
        r'^Also see',
        r'^\[.*\]$',  # Just a bracketed note
    ]
    for pattern in skip_patterns:
        if re.match(pattern, raw_text, re.IGNORECASE):
            return None, "unparseable"

    # Common SEP format: "Author, Year, Title, Publisher."
    # Pattern: Name(s), YYYY, Title, Location: Publisher.
    standard_pattern = r'^([^,]+(?:,\s*[^,]+)*),\s*(\d{4}|forthcoming),\s*["\']?([^"\']+?)["\']?,\s*(.+)\.$'

    match = re.match(standard_pattern, raw_text)
    if match:
        authors_str, year, title, publisher = match.groups()

        # Split authors on " and "
        authors = [a.strip() for a in re.split(r'\s+and\s+', authors_str)]

        # Check for (ed.) or (eds.)
        is_edited = bool(re.search(r'\(eds?\.?\)', authors_str, re.IGNORECASE))

        parsed = {
            "authors": authors,
            "year": year,
            "title": title.strip("'\""),
            "publisher": publisher.strip()
        }
        if is_edited:
            parsed["is_edited"] = True

        return parsed, "high"

    # Try to extract at least author and year
    partial_pattern = r'^([^,]+),\s*(\d{4})'
    match = re.match(partial_pattern, raw_text)
    if match:
        authors_str, year = match.groups()
        return {
            "authors": [authors_str.strip()],
            "year": year,
            "title": raw_text  # Fall back to raw
        }, "low"

    # Could not parse
    return None, "unparseable"
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
| `rate_limiter.py` | Shared rate limiting module | *(imported, not called directly)* |
| `check_setup.py` | Verify environment configuration | `--verbose` |
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
description: Search philosophy literature across SEP, PhilPapers, Semantic Scholar, OpenAlex, arXiv. Supports paper discovery, citation traversal, and recommendations. Verifies citations via CrossRef.
---
```

**Sections to include**:
1. Overview
2. Script Invocation (with full paths)
3. Search Workflow (phases 1-6)
4. SEP Content Access
5. JSON to BibTeX Conversion (field mappings)
6. Available Scripts table
7. Error Handling
8. Environment Setup

**Details**: See [`references/skill-and-agent-integration.md`](references/skill-and-agent-integration.md) for full template content.

---

## Agent Integration

### domain-literature-researcher

**Scope of changes**: ~60% rewrite of instructions. Major additions for JSON→BibTeX conversion.

**Frontmatter changes**:
```yaml
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
```

**Key instruction changes**:

1. **Remove** all references to WebSearch
2. **Add** script invocation patterns:
   ```bash
   python .claude/skills/philosophy-research/scripts/search_sep.py "free will"
   ```
3. **Add** JSON→BibTeX conversion logic (from this plan)
4. **Add** error handling for partial results
5. **Update** search phases to use skill scripts

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

**New section to add: "Converting JSON Results to BibTeX"**

```markdown
## Converting JSON Results to BibTeX

After calling search scripts, convert JSON results to BibTeX entries:

1. Parse the JSON response (check `status` field first)
2. For each paper in `results`:
   a. Determine entry type (@article, @book, @misc, etc.)
   b. Generate citation key: `{authorLastName}{year}{firstTitleWord}`
   c. Format author names: "Last, First and Last2, First2"
   d. Map fields according to source (S2, OpenAlex, arXiv)
   e. Write note field with CORE ARGUMENT, RELEVANCE, POSITION
3. Handle partial failures gracefully (use papers that were retrieved)
4. If `status` is "error", report the issue and continue with other sources

[Include field mapping table from this plan]
```

**Details**: See [`references/skill-and-agent-integration.md`](references/skill-and-agent-integration.md) for full phase descriptions.

### citation-validator

**Scope of changes**: ~50% rewrite of instructions. Major changes to validation workflow.

**Frontmatter changes**:
```yaml
tools: WebFetch, Read, Write, Grep, Bash  # REMOVE WebSearch
skills: philosophy-research               # ADD skill
```

**Key instruction changes**:

1. **Remove** WebSearch mandate
2. **Replace** Google Scholar searches with script calls
3. **Add** fallback chain logic
4. **Add** handling for partial failure responses

**Validation workflow**:
```
1. If DOI present:
   → verify_paper.py --doi → confirm matches
   → WebFetch doi.org/{doi} → confirm resolves

2. If arXiv ID present:
   → search_arxiv.py --id → verify exists

3. If no DOI/arXiv:
   → s2_search.py → find in S2
   → If not found OR status="error": search_openalex.py → broader coverage
   → If not found: search_arxiv.py → preprints
   → If not found: search_philpapers.py / search_sep.py

4. Check response status:
   → If "success": compare metadata
   → If "partial": use available results, note warning
   → If "error": try next source in fallback chain

5. Compare metadata: authors, year (±1), venue

6. Decision: KEEP / CORRECT / REMOVE
```

**Batch validation**:
- `s2_batch.py --ids "DOI:..."` (up to 500)
- OpenAlex batch for DOIs not in S2 (up to 50)

**Details**: See [`references/skill-and-agent-integration.md`](references/skill-and-agent-integration.md) for all 6 validation methods and full workflow.

---

## Implementation Order

**IMPORTANT FOR IMPLEMENTER**: Follow this order exactly. Each step depends on previous steps. Test each script before proceeding.

| Step | Task | Dependency | Acceptance Criteria |
|------|------|------------|---------------------|
| 1 | `rate_limiter.py` | None | Creates lock files, blocks correctly between calls |
| 2 | `check_setup.py` | rate_limiter.py | Reports status of all API keys and dependencies |
| 3 | `verify_paper.py` | rate_limiter.py | CrossRef lookup works; graceful failure on not found |
| 4 | `s2_search.py` | rate_limiter.py | Returns JSON with papers; handles 429 gracefully |
| 5 | `s2_citations.py` | rate_limiter.py | Returns references and citations; respects rate limit |
| 6 | `s2_batch.py` | rate_limiter.py | Handles up to 500 IDs; partial results on failure |
| 7 | `s2_recommend.py` | rate_limiter.py | Returns recommendations based on seed papers |
| 8 | `search_openalex.py` | rate_limiter.py | Returns papers with abstracts; handles missing email gracefully |
| 9 | `search_arxiv.py` | rate_limiter.py | Returns preprints; 3-second delay enforced |
| 10 | `search_sep.py` | rate_limiter.py | Returns SEP article URLs with entry_names |
| 11 | `fetch_sep.py` | rate_limiter.py | Extracts structured content; bibliography parsing is best-effort |
| 12 | `search_philpapers.py` | rate_limiter.py | Returns PhilPapers URLs |
| 13 | `SKILL.md` | All scripts | Complete documentation with field mappings |
| 14 | Manual testing | All scripts | User verifies all scripts work in real scenarios |
| 15 | Update `domain-literature-researcher.md` | SKILL.md | ~60% rewrite with JSON→BibTeX conversion |
| 16 | Update `citation-validator.md` | SKILL.md | ~50% rewrite with new validation workflow |
| 17 | Integration test | Updated agents | Run full literature review with new skill |

---

## Environment Setup

### Required Environment Variables

```bash
# Required
export BRAVE_API_KEY="your-key-here"     # Required for SEP/PhilPapers discovery
export CROSSREF_MAILTO="your@email.com"  # Required for CrossRef polite pool

# Recommended
export S2_API_KEY="your-key-here"        # Semantic Scholar (improves reliability)
export OPENALEX_EMAIL="your@email.com"   # OpenAlex polite pool (improves rate limits)
```

### Dependencies

```bash
pip install requests beautifulsoup4 lxml pyalex arxiv
```

### Verification

Run `check_setup.py` to verify configuration:

```bash
python .claude/skills/philosophy-research/scripts/check_setup.py --verbose
```

Expected output:
```
Environment Check Results
=========================
[OK] BRAVE_API_KEY: Set
[OK] CROSSREF_MAILTO: Set
[OK] S2_API_KEY: Set (recommended)
[OK] OPENALEX_EMAIL: Set (recommended)

Dependencies Check
==================
[OK] requests: 2.31.0
[OK] beautifulsoup4: 4.12.0
[OK] lxml: 5.0.0
[OK] pyalex: 0.14
[OK] arxiv: 2.0.0

API Connectivity Check
======================
[OK] Semantic Scholar: Responding (authenticated)
[OK] CrossRef: Responding (polite pool)
[OK] OpenAlex: Responding (polite pool)
[OK] Brave: Responding
[OK] arXiv: Responding

All checks passed. Ready to use philosophy-research skill.
```

---

## Success Criteria

### Setup Verification
- [ ] `check_setup.py` reports all required env vars set
- [ ] `check_setup.py` verifies all APIs are reachable
- [ ] Rate limiter creates lock files in `/tmp/philosophy_research_ratelimits/`

### Rate Limiter
- [ ] File-based locking prevents concurrent writes
- [ ] Cross-script rate limiting works (call s2_search.py twice rapidly; second waits)
- [ ] Exponential backoff retries on 429

### Standard Output Schema
- [ ] All scripts output valid JSON matching schema
- [ ] `status` field always present ("success", "partial", "error")
- [ ] `errors` array provides actionable information
- [ ] Exit codes follow specification (0, 1, 2, 3)

### Semantic Scholar Scripts
- [ ] `s2_search.py` returns papers with abstracts and DOIs
- [ ] `s2_citations.py` traverses references and citations
- [ ] `s2_batch.py` handles up to 500 IDs
- [ ] `s2_recommend.py` returns relevant recommendations
- [ ] All return partial results on rate limit errors

### CrossRef Scripts
- [ ] `verify_paper.py --doi 10.2307/2024717` returns verified metadata
- [ ] `verify_paper.py --title "..." --author Frankfurt` finds DOI
- [ ] `verify_paper.py` returns exit code 1 for non-existent papers
- [ ] Graceful failure message when paper not found

### arXiv Scripts
- [ ] `search_arxiv.py "AI ethics"` returns papers with abstracts
- [ ] `search_arxiv.py --id "2301.00001"` returns specific paper
- [ ] `search_arxiv.py --category cs.AI --recent` filters correctly
- [ ] 3-second delay enforced via shared rate limiter

### OpenAlex Scripts
- [ ] `search_openalex.py "free will"` returns papers with abstracts
- [ ] `search_openalex.py --doi "..."` returns verified metadata
- [ ] `search_openalex.py --cites "W..."` returns citing papers
- [ ] Works without OPENALEX_EMAIL (with warning in output)

### Brave Search Scripts
- [ ] `search_sep.py "free will"` returns SEP article URLs
- [ ] `search_sep.py` extracts `entry_name` for `fetch_sep.py`
- [ ] `search_philpapers.py "..."` returns PhilPapers URLs
- [ ] Clear error when BRAVE_API_KEY not set

### SEP Content Extraction
- [ ] `fetch_sep.py freewill` returns structured JSON
- [ ] `fetch_sep.py freewill --bibliography-only` extracts bibliography
- [ ] Bibliography entries have `raw` field (always) and `parsed` field (when possible)
- [ ] `confidence` field indicates parsing reliability
- [ ] `fetch_sep.py` extracts related entries

### Agent Integration
- [ ] `domain-literature-researcher.md` updated with JSON→BibTeX conversion
- [ ] `citation-validator.md` updated with new validation workflow
- [ ] Both agents work without WebSearch
- [ ] Agents handle partial failure responses gracefully

### General
- [ ] All scripts return valid JSON matching Standard Output Schema
- [ ] No fabricated citations possible (scripts only return what APIs return)
- [ ] Agents produce valid BibTeX from JSON results
- [ ] Full literature review completes successfully with new skill

---

## Troubleshooting Guide

### Common Issues

**"BRAVE_API_KEY not set" error**
- Solution: `export BRAVE_API_KEY="your-key"` in shell
- Get key at: https://api-dashboard.search.brave.com

**Rate limit errors despite limiter**
- Check: Are lock files being created in `/tmp/philosophy_research_ratelimits/`?
- Check: Is another process clearing /tmp?
- Solution: Increase `min_interval` slightly

**SEP bibliography parsing returning mostly "unparseable"**
- This is expected for some entries (cross-references, notes)
- Check: Are actual references getting `parsed` data?
- The `raw` field is always available as fallback

**OpenAlex returning fewer results than expected**
- Check: Is OPENALEX_EMAIL set? (affects rate limiting)
- Some queries legitimately have few results
- Try broader search terms

**arXiv very slow**
- Expected: 3-second delay between requests is required by arXiv
- For batch lookups, this is unavoidable

### Debug Mode

Add `--debug` flag to any script for verbose output:

```bash
python .claude/skills/philosophy-research/scripts/s2_search.py "free will" --debug
```

This will print:
- Rate limiter wait times
- API request/response details
- Parsing steps
