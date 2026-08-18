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

**Determining entry type from CrossRef**: When `verify_paper.py` returns a `suggested_bibtex_type` field, **use it**. CrossRef knows whether a DOI is a journal article or a book chapter. Common mapping:
- CrossRef `journal-article` → `@article` (use `container_title` as `journal`)
- CrossRef `book-chapter` → `@incollection` (use `container_title` as `booktitle`, include `publisher`)
- CrossRef `book` / `edited-book` → `@book` (for `edited-book`, use `editor` instead of `author`)
- CrossRef `proceedings-article` → `@inproceedings` (use `container_title` as `booktitle`)

See `CROSSREF_TO_BIBTEX_TYPE` in `verify_paper.py` for the full mapping.

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

**@misc (arXiv preprint)** — template:
```bibtex
@misc{authorYYYYkeyword,
  author = {Last, First},
  title = {Title of Paper},
  year = {YYYY},
  howpublished = {arXiv:XXXX.XXXXX},
  note = {arXiv:XXXX.XXXXX. CORE ARGUMENT: ... RELEVANCE: ... POSITION: ...},
  keywords = {topic-tag, preprint, Medium}
}
```
Combine the arXiv ID and annotation in a **single `note` field**. Do NOT use separate `note` fields for the ID and the annotation.

### Field Uniqueness Rule

> Every field name must appear **at most once** per entry. Duplicate fields (e.g., two `note` fields) produce invalid BibTeX and will be rejected by validation hooks.

### DOI Field

- Only include verified DOIs from publisher sites or CrossRef
- Format: `doi = {10.XXXX/xxxxx}` (no URL prefix)
- If DOI unavailable, omit the field — never fabricate

### Venue Status Field (engine-stamped)

`venue_status = {low-visibility}` is added by the evidence barrier (Phase 3→4)
to entries whose `journal` resolves in OpenAlex as non-core, not DOAJ-listed,
and with an h-index below 15. It is a caveat for the synthesis writer, not a
claim about the work. Only flagged entries carry it — absence means "not
flagged, not evaluated, or vetting did not run" (vetting needs a free
`OPENALEX_API_KEY`). Agents must never write this field by hand.

### Year Suffix Field (engine-stamped)

`year_suffix = {a}` is added by the evidence barrier (Phase 3→4) when one
author has two or more works in the same year, following Chicago 15.18. The
`year` field itself is never modified: `2010a` in a `year` field would be
rejected by the `\d{4}` guards in `check_evidence.py` and `resolve_context.py`.
References render `2010a`; in-text citations must carry the same letter.
Letters are assigned once per run, over all domain bibliographies at once, so
the same work carries the same letter in every domain. They are packed
`a`, `b`, `c` with no gaps, and the barrier strips and re-derives them on every
run — so if the bibliography changes between runs, a work's letter can change.
That is safe within a review, because assignment happens at the Phase 3→4
barrier and every writer runs after it; it is only a hazard if a bib is edited
and the renderer re-run without re-running the writers. Agents must never write
this field by hand.

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
| `journal`/`booktitle` | CrossRef `container_title` (field name depends on `suggested_bibtex_type`: `journal` for articles, `booktitle` for incollection/inproceedings) | S2 `venue`, OpenAlex `source.name` | **Omit field entirely** |
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

### abstract Field

The paper's actual abstract. Must come from API sources only (S2, OpenAlex, CORE).

- Populated ONLY by `enrich_bibliography.py` (Stage 5.5) — researchers never write `abstract` or `abstract_source` by hand; the enrichment ledger attests source and text hash, and unattested abstracts earn no citability tier.
- Never written by agent from memory
- If missing from all sources: Omit field, add INCOMPLETE to keywords

### abstract_source Field

Indicates provenance of abstract content:
- `s2` — Semantic Scholar API
- `openalex` — OpenAlex API
- `core` — CORE API
- `ndpr` — Notre Dame Philosophical Reviews (first 8 substantive paragraphs extracted from book reviews — primarily descriptive of the book's content and arguments, but may include some reviewer evaluation; not author/publisher abstracts)

Example: `abstract_source = {openalex}`

### sep_context Field (Optional)

Citation context extracted from Stanford Encyclopedia of Philosophy entries.
Contains how the paper is discussed in authoritative SEP articles.

- Source: the evidence barrier (`evidence_barrier.py`) — sole author. No agent writes these fields; pre-existing values are stripped before acquisition.

Example:
```bibtex
sep_context = {Cited in 'freewill' entry: "Frankfurt (1971) argues that alternative possibilities are not required for moral responsibility."}
```

### iep_context Field (Optional)

Citation context extracted from Internet Encyclopedia of Philosophy entries.
Similar to sep_context but from IEP.

- Source: the evidence barrier (`evidence_barrier.py`) — sole author. No agent writes these fields; pre-existing values are stripped before acquisition.

### Evidence Tiers (EVIDENCE-* keyword)

The `EVIDENCE-*` token in `keywords` is the **single authority on citability**, stamped mechanically by the evidence barrier at the Phase 3-to-4 boundary (and re-stamped attestation-aware on dedup merge — the one sanctioned mutation after the barrier; no stage adds content-evidence fields after it):

- `EVIDENCE-ABSTRACT` — ledger-attested abstract: characterize/summarize/quote from the sourced abstract text
- `EVIDENCE-CONTEXT` — barrier-written `sep_context`/`iep_context`: characterize from that description only, attributed in prose
- `EVIDENCE-WEB` — a `@misc` web source that passed the barrier's **fetch gate**: the URL was corroborated this run (a same-domain 2xx, a same-domain bot-block, or an existing archive snapshot) AND a research-time capture written by `fetch_web.py` bound to that same URL passed all five checks (URL binding, HTTP status for script captures, boilerplate signatures, title anchor plus a length floor, and containment of every `web_span` the entry lists). Citable, with characterization grounded in the entry's `note`; no direct quotation of the work. Barrier-authored `urldate` and `archiveurl` are delivered alongside. Encyclopedia and index hosts (SEP and its mirrors, IEP, NDPR, PhilPapers) are excluded: `fetch_web.py` refuses them and the barrier buckets them as `excluded_host` without probing — SEP/IEP content reaches evidence through the encyclopedia context channel instead.
  - **Scoped amendment to the note doctrine.** Everywhere else a `note` licenses no content claim at any tier. Here, and only here, the CORE ARGUMENT note *is* the licensed basis for characterization. The justification is precise: the gate proves that a fetch of *this entry's* URL produced real, title-matching content in the workspace at research time, and that the note's `web_span` values occur verbatim in it. That the rest of the note derives from that content is an **assumption** — a good one under the divergence principle (fetching a page and summarizing it is native, constantly exercised behaviour), and one the acceptance audit measures rather than trusts. Measured (live acceptance, 2026-08-15): 1 of 4 promoted notes attributed a framing the page never states, and it reached the delivered prose — hence the researcher-side fidelity rule and the writer-side caution now in the agent prose.
- `EVIDENCE-EXISTENCE` — identity positively verified (cleaning-ledger API match + surviving identifier): existence and coverage claims only. A cleaner *abstention* (exact DOI match, contradictory year evidence) also attests existence — the ledger records `api_matched: true` plus a `cleaning_abstained` reason, and the refusal stays visible in the evidence report (`cleaning_abstained` list). Abstention never claims the year; cleaning behaviour is identical to no-match.
- `EVIDENCE-NONE` — no verified evidence: not citable; stays in the `.bib` for transparency

An entry with no `EVIDENCE-*` token is treated as `EVIDENCE-NONE` (fail-closed). Canonical keyword order: `topic-tags, Importance, EVIDENCE-*`, with any `METADATA_CLEANED:` marker last. Tier tokens are engine-internal — the delivered `.bib` has them stripped (`sanitize_bib.py`).

### INCOMPLETE Keyword Flag (Phase-3-only artifact)

`INCOMPLETE` / `no-abstract` are added by `enrich_bibliography.py` when no abstract is found. They exist only for Phase 3 reporting (NOTABLE_GAPS): the evidence barrier consumes and strips them when it stamps tiers. No downstream stage may key any decision off `INCOMPLETE`.

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
| Two authors sharing a surname | (F. Author Year) — add the first initial | (G. Johnson 2024) vs. (R. Johnson 2024) |
| One author, two works in one year | (Author Year+letter) — the entry's own `year_suffix` | (Menary 2010a) vs. (Menary 2010b) |

**Different people sharing a surname — always add the first initial, whatever
the years.** This is Chicago's own rule. When the years differ the citations
render fine but the reader is left guessing: citing Onora O'Neill (1987)
alongside Martin O'Neill and Williamson (2009), a bare `(O'Neill 1987)` does
not say which O'Neill is meant — write `(O. O'Neill 1987)` (the co-authored
cite is already told apart by "and Williamson"). When the two also share a
*year*, the initial is load-bearing rather than cosmetic: references are
rendered by matching *first-author surname near a year* in the prose, so given
a bare `Johnson (2024)` the renderer cannot tell which work was cited, keeps
**both** in the reference list, and warns — meaning a work you never cited is
listed as if you had. Writing `G. Johnson (2024)` resolves it.

**Where the same first author has two works in one year, the correct form is
already the disambiguator** — so use it exactly. A two-author work is
`Muldoon and Wu (2023)` and a three-or-more-author work is `Muldoon et al.
(2023)` (the rows above); those two forms are distinct, and that distinctness
is what lets the renderer tell the works apart. What breaks it is collapsing a
two-author work to `et al.` (wrong in Chicago regardless) or dropping to a bare
`Muldoon (2023)`. Note this only helps when the author *lists* differ — two
works by the same author(s) in the same year are disambiguated instead by a
barrier-assigned `year_suffix` letter that References render and prose must
match exactly, e.g. `Menary (2010a)` / `Menary (2010b)` (see the Year Suffix
Field section above).

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

Hooks validate BibTeX automatically at two points: `validate_bib_write.py` checks `.bib` content at write time (PreToolUse on Write, PostToolUse on Edit), and the `SubagentStop` hook validates the files written by `domain-literature-researcher`:

### 1. BibTeX Syntax Validation (`bib_validator.py`)
- UTF-8 encoding check
- BibTeX syntax validation
- No LaTeX commands for special characters
- No duplicate citation keys
- Required fields present per entry type
- No BibLaTeX fields

### 2. Metadata Provenance Cleaning (`metadata_cleaner.py`)

**Purpose**: Prevents LLM hallucination of bibliographic metadata by REMOVING field values that cannot be verified against API output.

This is a *fix*, not a block. An earlier blocking design (`metadata_validator.py`) was written but never wired into any hook, and was deleted 2026-08-02 rather than left as a re-armable trap: because it duplicated the cleaner's whole parser/index layer without sharing it, hardening effort landed on the dormant copy (`9aa473d`) while the live one still crashed on a single malformed file — which is how the `json.loads` failure fixed in `a30cde0` stayed hidden. Anything below that reads as "blocks the subagent" describes the cleaner's *removal* behaviour instead.

**Cleanable fields** (removed when unverifiable):
- `journal` / `booktitle`
- `volume`
- `number` (the BibTeX field; API `issue` values verify it)
- `pages`
- `publisher`
- `doi`

`year` is **corrected**, not removed — and only on entry-scoped evidence: a CrossRef result identified by envelope content (`api_source` is `crossref` AND the file carries exactly one result — the filename is deliberately NOT the test) that matches this entry's own DOI, carries a version-of-record `year_basis` (recorded by `verify_paper.py`; registration/created timestamps never overwrite), and is not contradicted by another entry-scoped record. On any same-DOI year conflict the cleaner abstains from the entry entirely (attesting existence in the cleaning ledger — see Evidence Tiers above). For the reprint-capable entry types (`@book`, `@incollection`, `@inbook`) a further **direction bound** applies: the year may only move earlier. A reprint edition has its own DOI whose print date is the reprint's year, not the work's original publication year — the year Chicago cites — so a later year is refused, as is a bib year the direction test cannot parse (`n.d.`, `[2021]`); every refusal is counted in the cleaning report rather than passing silently. `author` and `title` are identity fields and are never touched.

**Exempt fields** (LLM-generated or enrichment-added, not cleaned — `EXEMPT_FIELDS` in the cleaner):
- `note` (annotations)
- `keywords`
- `howpublished`
- `url`
- `abstract`
- `abstract_source`

`sep_context` / `iep_context` are also never cleaned, but not via this list — they are outside `CLEANABLE_FIELDS` and are owned end-to-end by the evidence barrier (see Evidence Tiers above).

**How it works**:
1. Scans the .bib's own directory AND `intermediate_files/json/` for API output files (S2, OpenAlex, CrossRef, arXiv, PhilPapers, CORE) — both feed ONE index, so directory shadowing cannot starve verification
2. Builds a presence-based index of all metadata values from API responses, each file ingested transactionally so one malformed file costs only its own records
3. Finds each entry's OWN API record (DOI, else normalized title+year); an entry with no affirmative match is left completely untouched
4. Removes a cleanable field only when it matches neither that record nor the global index, then downgrades the entry type if a required field is gone, and tags the entry `METADATA_CLEANED`

**Value normalization**: values are normalized before comparison:
- Pages: `"163 - 188"` matches `"163--188"` (handles space/dash variations)
- Journals: LaTeX/HTML-entity/accent decoding, then case-insensitive, strips "The" prefix
- DOIs: strips URL prefixes
- Years: exact string grammar (`2007`, `2007.0` and `0002007` are one value; `2007.9` and `n.d.` are not years)

**Circuit breaker**: if a .bib would lose fields from more than 30% of its entries and from at least 5, the cleaner writes NOTHING — a systemic index failure must not mass-strip verified data.

See `hooks/hooks.json` for hook configuration.
