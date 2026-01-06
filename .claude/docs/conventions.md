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

**@article**: author, title, journal, year, volume, pages
- Optional: number, doi

**@book**: author, title, publisher, year
- Optional: address, doi, edition

**@incollection**: author, title, booktitle, publisher, year, pages
- Optional: editor, address

### DOI Field

- Only include verified DOIs from publisher sites or CrossRef
- Format: `doi = {10.XXXX/xxxxx}` (no URL prefix)
- If DOI unavailable, omit the field — never fabricate

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
- UTF-8 encoding check
- BibTeX syntax validation
- No LaTeX commands for special characters

See `.claude/settings.json` for hook configuration.
