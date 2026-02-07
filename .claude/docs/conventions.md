# Shared Format Conventions

Specifications shared across literature review agents. Reference this file for format standards.

---

## UTF-8 Encoding

**All output files MUST use UTF-8 encoding.**

Requirements:
- Preserve diacritics in author names exactly (e.g., Kästner, Müller, García)
- Use proper special characters: ä ö ü é è ñ ç etc.
- Use typographic characters: em-dash (—), en-dash (–), curly quotes (" " ' ')
- Never convert special characters to ASCII approximations
- Never use LaTeX commands for special characters

**Verification**: Run `file [filename]` — should show "UTF-8 Unicode text"

---

## BibTeX Format Specification

### Entry Types

| Type | Use For |
|------|---------|
| `@article` | Journal articles |
| `@book` | Books |
| `@incollection` | Book chapters |
| `@inproceedings` | Conference papers |
| `@phdthesis` | Dissertations |
| `@misc` | SEP entries, online resources |

### Citation Keys

Format: `authorYYYYkeyword`

Examples: `frankfurt1971freedom`, `fischerravizza1998responsibility`

### Author Names

Format: `Last, First Middle and Last2, First2`

```bibtex
author = {Frankfurt, Harry G.}
author = {Fischer, John Martin and Ravizza, Mark}
author = {Smith, John and Jones, Mary and Brown, David}
```

### Required Fields by Entry Type

**@article**: author, title, journal, year
- Include volume, pages only if API provides them
- Optional: number, doi
- Note: If API doesn't provide journal/venue, use `@misc` instead

**@book**: author, title, publisher, year
- Optional: address, doi, edition

**@incollection**: author, title, booktitle, publisher, year
- Include pages only if API provides them
- Optional: editor, address

**@misc**: author, title, year, howpublished OR url
- Use for papers with no venue info, web sources, preprints

### DOI Field

- Only include verified DOIs from publisher sites or CrossRef
- Format: `doi = {10.XXXX/xxxxx}` (no URL prefix)
- If DOI unavailable, omit the field — never fabricate

### Field Grounding — CRITICAL

**ALL bibliographic fields must come ONLY from API/tool output.**

This prevents hallucination of any metadata. The rule applies to EVERY field, not just journal names.

**Metadata source priority** (for papers with DOIs):
1. **CrossRef** (via `verify_paper.py --doi`) — authoritative source for publication metadata
2. **S2/OpenAlex/arXiv** — fallback if CrossRef unavailable

| Field | Preferred Source | Fallback Source | If Missing Everywhere |
|-------|-----------------|-----------------|----------------------|
| `author` | Any API | — | Required — don't include paper |
| `title` | Any API | — | Required — don't include paper |
| `year` | Any API | — | Required — don't include paper |
| `journal`/`booktitle` | CrossRef `container_title` | S2 `venue`, OpenAlex `source.name` | **Omit field entirely** |
| `volume` | CrossRef | S2/OpenAlex | **Omit field entirely** |
| `number` (issue) | CrossRef `issue` | S2/OpenAlex | **Omit field entirely** |
| `pages` | CrossRef `page` | S2/OpenAlex | **Omit field entirely** |
| `publisher` | CrossRef | S2/OpenAlex | **Omit field entirely** |
| `editor` | API output | — | **Omit field entirely** |
| `doi` | Any API or verify_paper.py | — | **Omit field entirely** |

**Never fill in missing fields from model knowledge** — even if you "recognize" the paper. This applies to ALL fields. A BibTeX entry with missing fields is preferable to one with hallucinated data.

If no venue information is available from any source, use `@misc` entry type instead of `@article`.

### Keywords Field

Format: `topic-tag, position-tag, Importance-level`

Importance levels:
- `High` — Core paper, must cite
- `Medium` — Important context
- `Low` — Peripheral but relevant

Example: `keywords = {compatibilism, free-will, High}`

---

## Chicago Citation Style (Author-Date)

### In-Text Citations

| Situation | Format | Example |
|-----------|--------|---------|
| Single author | (Author Year) | (Frankfurt 1971) |
| Two authors | (Author and Author Year) | (Fischer and Ravizza 1998) |
| Three+ authors | (Author et al. Year) | (Smith et al. 2020) |
| Multiple citations | (Author Year; Author Year) | (Frankfurt 1971; Dennett 1984) |
| With page numbers | (Author Year, pages) | (Fischer and Ravizza 1998, 31-45) |
| Author as subject | Author (Year) argues... | Frankfurt (1971) argues... |

### Bibliography Format

**Journal Article**:
```
Frankfurt, Harry G. 1971. "Freedom of the Will and the Concept of a Person." The Journal of Philosophy 68 (1): 5–20. https://doi.org/10.2307/2024717.
```

**Book**:
```
Fischer, John Martin, and Mark Ravizza. 1998. Responsibility and Control: A Theory of Moral Responsibility. Cambridge: Cambridge University Press.
```

**Book Chapter**:
```
Nelkin, Dana Kay. 2011. "Freedom and Responsibility." In The Oxford Handbook of Free Will, edited by Robert Kane, 425–453. Oxford: Oxford University Press.
```

---

## Automated Validation

The `SubagentStop` hook automatically validates BibTeX files written by `domain-literature-researcher`:

### 1. BibTeX Syntax Validation (`bib_validator.py`)
- UTF-8 encoding check
- BibTeX syntax validation
- No LaTeX commands for special characters
- No duplicate citation keys
- Required fields present per entry type
- No BibLaTeX fields

### 2. Metadata Provenance Validation (`metadata_validator.py`)

**Purpose**: Prevents LLM hallucination of bibliographic metadata by validating that field values exist in API output.

**Validated fields** (must exist in JSON API output):
- `journal` / `booktitle`
- `volume`
- `number` / `issue`
- `pages`
- `publisher`
- `year`
- `doi`

**Exempt fields** (LLM-generated, not validated):
- `note` (annotations)
- `keywords`
- `howpublished`
- `url`
- `abstract`

**How it works**:
1. Scans `intermediate_files/json/` for API output files (S2, OpenAlex, CrossRef, arXiv, PhilPapers)
2. Builds an index of all metadata values from API responses
3. Validates each BibTeX entry's fields against this index
4. Blocks the subagent if any field value is not found in API output

**Value normalization**: The validator normalizes values for comparison:
- Pages: `"163 - 188"` matches `"163--188"` (handles space/dash variations)
- Journals: case-insensitive, strips "The" prefix
- DOIs: strips URL prefixes

**Error messages**: When validation fails, the validator reports:
- Which entry has the problem
- Which field contains the unverifiable value
- What values the API actually contains
- Action to take (remove field or use API value)

See `.claude/settings.json` for hook configuration.
