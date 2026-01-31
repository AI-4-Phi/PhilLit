# Plan: Metadata Enrichment and Abstract Resolution System

## Overview

Add enrichment capabilities to the literature review workflow that ensures:
1. Complete bibliographic metadata for all entries
2. Abstracts (or authoritative context) for all entries
3. Grounded `note` field content based on abstracts and encyclopedia context

Entries without abstracts/context are flagged as unusable for the literature review.

---

## Problem Statement

1. **Incomplete bibliographic metadata**: APIs (S2, OpenAlex, arXiv) often return null/incomplete venue, volume, pages fields
2. **Missing abstracts**: Many philosophy works (especially books/chapters) lack abstracts in academic APIs
3. **Hallucination risk**: Agent may fill in missing fields from memory if not explicitly prevented
4. **Note field grounding**: The `note` field (CORE ARGUMENT, RELEVANCE, POSITION) is written by the agent at the end of discovery, potentially without grounded sources

---

## Key Finding: When Note Field is Created

The `note` field is created by domain-literature-researcher at the **END of Phase 3**, when the agent writes the final BibTeX file. This happens AFTER all discovery stages complete.

**Current workflow:**
```
Discovery: SEP → PhilPapers → S2/OpenAlex/arXiv → Citation chaining → CrossRef
    ↓
Agent writes BibTeX file (including note fields) based on gathered info
    ↓
Output: literature-domain-N.bib
```

**Key insight:** If we gather abstracts and encyclopedia context BEFORE the agent writes notes, the agent can use this grounded information to write accurate note fields.

---

## Solution Architecture

```
DISCOVERY PHASE (Phase 3 - within domain-literature-researcher)
├── Stage 1: SEP → bibliographies + preambles
├── Stage 2: PhilPapers → via Brave (snippets only)
├── Stage 3: S2, OpenAlex, arXiv → papers with abstracts
├── Stage 4: Citation chaining
├── Stage 5: CrossRef metadata enrichment (already implemented)
├── Stage 5.5: Abstract & Context Enrichment (NEW)
│   ├── For papers without abstract: get_abstract.py
│   │   ├── Check S2 abstract field
│   │   ├── Check OpenAlex abstract_inverted_index
│   │   ├── Check CORE API (new)
│   │   └── Return abstract + source attribution
│   ├── For all papers: get_sep_context.py (NEW)
│   │   ├── Search SEP for paper mentions
│   │   ├── Extract what SEP says about THIS paper
│   │   └── Return sep_context + source attribution
│   └── Optional: get_iep_context.py (same pattern)
└── Stage 6: Agent writes final BibTeX with grounded notes

BIBTEX OUTPUT
├── abstract field: From S2/OpenAlex/CORE (paper's actual abstract)
├── abstract_source field: Provenance of abstract
├── sep_context field: What SEP says about this paper (NEW)
├── iep_context field: What IEP says about this paper (NEW)
├── note field: CORE ARGUMENT (grounded in abstract), RELEVANCE, POSITION (grounded in context)
└── keywords: Include INCOMPLETE if abstract not found
```

---

## New Scripts to Create

### 1. `search_core.py`
**Location**: `.claude/skills/philosophy-research/scripts/search_core.py`

**Purpose**: Search CORE API (431M records, 46M full texts) for papers with abstracts

**Interface**:
```bash
python search_core.py "epistemic injustice"
python search_core.py --doi "10.1111/nous.12191"
python search_core.py --title "Freedom of the Will" --author "Frankfurt"
```

**Output**: Standard JSON schema with `abstract` field

**API Details**:
- Endpoint: `https://api.core.ac.uk/v3/search/works`
- Rate limit: 1 batch or 5 single requests per 10 seconds
- No API key required for basic access
- Returns: title, authors, abstract, doi, downloadUrl

---

### 2. `search_iep.py`
**Location**: `.claude/skills/philosophy-research/scripts/search_iep.py`

**Purpose**: Search Internet Encyclopedia of Philosophy via Brave (like SEP)

**Interface**:
```bash
python search_iep.py "compatibilism"
python search_iep.py "Frankfurt cases" --limit 10
```

**Implementation**: Use existing `brave_search.py` with new IEP_CONFIG

---

### 3. `fetch_iep.py`
**Location**: `.claude/skills/philosophy-research/scripts/fetch_iep.py`

**Purpose**: Extract structured content from IEP articles (like fetch_sep.py)

**Interface**:
```bash
python fetch_iep.py "compatibilism" --sections "1,2,bibliography"
```

---

### 4. `get_abstract.py`
**Location**: `.claude/skills/philosophy-research/scripts/get_abstract.py`

**Purpose**: Multi-source abstract resolution (paper's actual abstract only)

**Interface**:
```bash
python get_abstract.py --doi "10.1111/nous.12191"
python get_abstract.py --title "Freedom of the Will" --author "Frankfurt" --year 1971
python get_abstract.py --s2-id "abc123"
```

**Fallback Chain** (in order):
1. S2 `abstract` field (if S2 ID provided)
2. OpenAlex `abstract_inverted_index` (if DOI provided)
3. CORE API search (by DOI or title+author)

**Output**:
```json
{
  "status": "success|not_found",
  "abstract": "...",
  "abstract_source": "s2|openalex|core"
}
```

**Note**: This script returns the paper's ACTUAL abstract only. Encyclopedia context is handled separately by `get_sep_context.py`.

---

### 5. `get_sep_context.py` (NEW)
**Location**: `.claude/skills/philosophy-research/scripts/get_sep_context.py`

**Purpose**: Find what SEP says about a SPECIFIC paper (not general topic content)

**Interface**:
```bash
python get_sep_context.py --author "Frankfurt" --year 1971 --title "Freedom of the Will"
```

**How it works**:
```
1. Search SEP for relevant entries: search_sep.py "{author}"
   → Returns: "compatibilism", "free-will", "personal-autonomy"

2. For each relevant entry (top 3):
   a. Fetch bibliography: Does SEP cite this paper?
   b. Fetch article text: Search for "{Author} ({Year})" mentions
   c. Extract surrounding context (2-3 sentences)

3. Aggregate findings:
   - Which SEP entries cite/mention this paper
   - What SEP says ABOUT this paper (extracted quotes)
```

**Output**:
```json
{
  "status": "found|not_found",
  "mentions": [
    {
      "type": "bibliography",
      "entry": "compatibilism",
      "raw": "Frankfurt, Harry, 1971, 'Freedom of the Will...'"
    },
    {
      "type": "text_mention",
      "entry": "compatibilism",
      "section": "4.2",
      "context": "Frankfurt (1971) introduced his famous counterexamples to the principle of alternative possibilities. These 'Frankfurt cases' purport to show that an agent can be morally responsible even if they could not have done otherwise."
    }
  ],
  "source": "sep_mentions:compatibilism"
}
```

**Key distinction**: This returns what SEP says ABOUT the specific paper, not general topic content.

---

### 6. `get_iep_context.py` (NEW)
**Location**: `.claude/skills/philosophy-research/scripts/get_iep_context.py`

**Purpose**: Same as get_sep_context.py but for Internet Encyclopedia of Philosophy

**Interface**: Same pattern as get_sep_context.py

---

### 7. `enrich_bibliography.py`
**Location**: `.claude/skills/literature-review/scripts/enrich_bibliography.py`

**Purpose**: Batch orchestrator for metadata, abstract, and context enrichment

**Interface**:
```bash
python enrich_bibliography.py input.bib --output enriched.bib
python enrich_bibliography.py reviews/project/literature-domain-1.bib
```

**Processing**:
```python
for entry in bib_entries:
    # 1. Metadata enrichment (if DOI exists)
    if entry.has_doi and not entry.has_complete_metadata:
        metadata = resolve_metadata(entry.doi)
        entry.update(metadata)

    # 2. Abstract resolution (if abstract missing)
    if not entry.has_abstract:
        result = get_abstract(entry)
        if result.found:
            entry.abstract = result.abstract
            entry.abstract_source = result.source
        else:
            entry.keywords.add("INCOMPLETE")
            entry.keywords.add("no-abstract")

    # 3. SEP context (for all philosophy papers)
    sep_result = get_sep_context(entry.author, entry.year, entry.title)
    if sep_result.found:
        entry.sep_context = format_sep_mentions(sep_result.mentions)
        entry.sep_context_source = sep_result.source

    # 4. IEP context (optional additional source)
    iep_result = get_iep_context(entry.author, entry.year, entry.title)
    if iep_result.found:
        entry.iep_context = format_iep_mentions(iep_result.mentions)
        entry.iep_context_source = iep_result.source
```

**Output**: Modified BibTeX with:
- `abstract` field: Paper's actual abstract (from S2/OpenAlex/CORE)
- `abstract_source` field: Provenance of abstract
- `sep_context` field: What SEP says about this paper (NEW)
- `sep_context_source` field: SEP entry and section reference (NEW)
- `iep_context` field: What IEP says about this paper (NEW)
- `iep_context_source` field: IEP entry and section reference (NEW)
- `INCOMPLETE` keyword for entries without abstract

---

## Files to Modify

### 1. `.claude/agents/domain-literature-researcher.md`

**Key workflow change**: Enrichment happens BEFORE writing note fields, not after.

**Changes**:

1. **Add Stage 5.5: Abstract & Context Enrichment**
   - After discovery and CrossRef enrichment, BEFORE writing final BibTeX
   - Call `enrich_bibliography.py` on collected papers
   - This populates: abstract, abstract_source, sep_context, iep_context

2. **Update note field writing instructions**:
   - CORE ARGUMENT: Must be grounded in `abstract` field (if available)
   - POSITION: Can use `sep_context`/`iep_context` for authoritative framing
   - RELEVANCE: Agent's analysis connecting to research project (OK to use judgment)
   - If no abstract available: Note this explicitly, mark entry INCOMPLETE

3. **New note field format with grounding**:
```bibtex
note = {
  CORE ARGUMENT (grounded: abstract): Frankfurt argues that moral responsibility
  does not require alternative possibilities, using counterexamples where an
  agent is responsible despite being unable to do otherwise.

  RELEVANCE: This challenges traditional compatibilist assumptions and is
  foundational for understanding autonomy in AI systems where alternatives
  may be computationally constrained.

  POSITION (grounded: sep:compatibilism:4.2): Represents Frankfurt-style
  compatibilism, which denies the Principle of Alternative Possibilities.
}
```

4. **Document new fields**: abstract_source, sep_context, iep_context, INCOMPLETE flag

5. **Update quality checklist**:
   - [ ] Every entry has abstract OR is marked INCOMPLETE
   - [ ] CORE ARGUMENT is grounded in abstract (not agent knowledge)
   - [ ] POSITION uses sep_context/iep_context where available

### 2. `.claude/docs/conventions.md`

**Add new field specifications**:

#### abstract Field

The paper's actual abstract. Must come from API sources only.

#### abstract_source Field (NEW)

Indicates provenance of abstract content:
- `s2` — Semantic Scholar API
- `openalex` — OpenAlex API
- `core` — CORE API

#### sep_context Field (NEW)

What the Stanford Encyclopedia of Philosophy says about THIS specific paper.
NOT general topic content — only mentions of the specific work.

Format: Extracted quotes/context from SEP articles that mention this paper.

Example:
```bibtex
sep_context = {SEP (compatibilism, section 4.2): "Frankfurt (1971) introduced
his famous counterexamples to the principle of alternative possibilities.
These 'Frankfurt cases' purport to show that an agent can be morally
responsible even if they could not have done otherwise."}
```

#### sep_context_source Field (NEW)

Reference to SEP entry and section: `sep:compatibilism:4.2`

#### iep_context Field (NEW)

Same as sep_context but for Internet Encyclopedia of Philosophy.

#### iep_context_source Field (NEW)

Reference to IEP entry and section: `iep:free-will:section-3`

#### INCOMPLETE Keyword Flag (NEW)

Added to `keywords` field when entry lacks required content:
- `INCOMPLETE` — Entry missing critical metadata or abstract
- `no-abstract` — Specifically missing abstract

Entries with INCOMPLETE flag should NOT be used in literature review synthesis.

### 3. `.claude/hooks/bib_validator.py`

**Changes**:
- Add optional validation for `abstract_source` field format
- Recognize `INCOMPLETE` as valid keyword (no changes needed - keywords are free-form)

### 4. `.claude/skills/literature-review/scripts/dedupe_bib.py`

**Changes**:
- Preserve `abstract_source` field during deduplication
- When merging duplicates: prefer entry WITH abstract over entry WITHOUT
- Preserve `INCOMPLETE` flag only if BOTH entries have it

### 5. `.claude/agents/synthesis-planner.md` and `.claude/agents/synthesis-writer.md`

**Changes**:
- Document that entries with `INCOMPLETE` keyword should be excluded or flagged
- Add `abstract` field to list of fields agents should read
- Add `sep_context` and `iep_context` fields to list of fields agents should read
- Document how to use these fields:

```markdown
## Reading BibTeX Files

**Fields to extract:**
- Standard fields: author, title, journal/publisher, year, doi
- `note` field: CORE ARGUMENT, RELEVANCE, POSITION (primary source for synthesis)
- `abstract` field: Paper's actual abstract (if available)
- `sep_context` field: What SEP says about this paper
- `iep_context` field: What IEP says about this paper
- `keywords` field: Topic tags and importance level

**Using abstract and context fields:**
- `abstract`: Use to understand paper's methodology, findings, scope
- `sep_context`/`iep_context`: Use to understand paper's place in the field,
  how it's received, its key contributions as recognized by authoritative sources
- These fields SUPPLEMENT the `note` field, not replace it
- Prefer `note` for the agent's analysis of relevance to research project

**Handling INCOMPLETE entries:**
- If keywords contains `INCOMPLETE`: DO NOT use in synthesis
- Note the gap in the review if the paper would have been important
```

### 6. `.claude/skills/philosophy-research/SKILL.md`

**Add documentation for new scripts**:
- `search_core.py` usage and output
- `search_iep.py` usage and output
- `fetch_iep.py` usage and output
- `get_abstract.py` usage and fallback chain

---

## Interdependencies and Risk Mitigation

### Risk 1: Breaking BibTeX Validation
**Mitigation**: New fields (`abstract`, `abstract_source`) are standard optional BibTeX fields. The validator already allows optional fields. No changes needed to validation logic.

### Risk 2: Synthesis Agents Failing on New Fields
**Mitigation**: Synthesis agents read specific fields (note, keywords, standard biblio fields). New fields are additive and won't break existing parsing.

### Risk 3: Deduplication Losing Abstract Data
**Mitigation**: Update `dedupe_bib.py` to prefer entries with abstracts when merging duplicates.

### Risk 4: CORE API Rate Limits
**Mitigation**: Add CORE to `rate_limiter.py` with conservative limits (1 req/2 sec). Implement exponential backoff.

### Risk 5: SEP/IEP Context Misrepresented as Abstract
**Mitigation**: SEP/IEP context is now in SEPARATE fields (`sep_context`, `iep_context`), not in `abstract`. The `abstract` field contains only the paper's actual abstract from academic APIs.

### Risk 6: Batch Script Crashes Mid-Processing
**Mitigation**: `enrich_bibliography.py` writes incrementally and can resume from partial output.

### Risk 7: SEP/IEP Returns General Topic Info Instead of Paper-Specific
**Mitigation**: `get_sep_context.py` searches for specific paper mentions (Author + Year pattern) within SEP articles, not general topic content. Only returns text that explicitly references the paper.

### Risk 8: Note Field Still Hallucinated Despite Having Abstract
**Mitigation**: Updated agent instructions require CORE ARGUMENT to be "grounded" in abstract, with explicit notation. Quality checklist requires verification.

---

## Implementation Order

### Phase 1: Core Infrastructure
1. Add CORE rate limiter to `rate_limiter.py`
2. Create `search_core.py` with tests
3. Create `get_abstract.py` with tests

### Phase 2: IEP Support
4. Add IEP_CONFIG to `brave_search.py`
5. Create `search_iep.py` (minimal - uses brave_search)
6. Create `fetch_iep.py` (adapt from fetch_sep.py)

### Phase 3: Orchestration
7. Create `enrich_bibliography.py`
8. Update `dedupe_bib.py` for abstract handling
9. Add tests for deduplication changes

### Phase 4: Agent Updates
10. Update `domain-literature-researcher.md`
11. Update `conventions.md`
12. Update `synthesis-planner.md` and `synthesis-writer.md`
13. Update `SKILL.md` documentation

### Phase 5: Testing
14. Run existing tests (ensure no regressions)
15. Test full workflow with sample literature review

---

## Verification

### Unit Tests
- `test_search_core.py`: CORE API responses, rate limiting, error handling
- `test_get_abstract.py`: Fallback chain, source attribution, edge cases
- `test_enrich_bibliography.py`: Batch processing, incremental writes, flag handling
- Update `test_dedupe_bib.py`: Abstract preservation during merge

### Integration Test
Run full literature review workflow:
```bash
# 1. Start literature review
/literature-review "epistemic autonomy in AI systems"

# 2. Verify domain.bib files contain:
#    - abstract fields with abstract_source
#    - INCOMPLETE flags where appropriate

# 3. Verify synthesis agents handle new fields correctly
```

### Manual Verification
1. Import final `literature-all.bib` into Zotero - should parse without errors
2. Check that INCOMPLETE entries are excluded from synthesis
3. Verify `abstract_source` values are accurate

---

## Files Summary

**New Files**:
- `.claude/skills/philosophy-research/scripts/search_core.py`
- `.claude/skills/philosophy-research/scripts/search_iep.py`
- `.claude/skills/philosophy-research/scripts/fetch_iep.py`
- `.claude/skills/philosophy-research/scripts/get_abstract.py`
- `.claude/skills/philosophy-research/scripts/get_sep_context.py`
- `.claude/skills/philosophy-research/scripts/get_iep_context.py`
- `.claude/skills/literature-review/scripts/enrich_bibliography.py`
- `tests/test_search_core.py`
- `tests/test_get_abstract.py`
- `tests/test_enrich_bibliography.py`

**Modified Files**:
- `.claude/skills/philosophy-research/scripts/rate_limiter.py` (add CORE)
- `.claude/skills/philosophy-research/scripts/brave_search.py` (add IEP_CONFIG)
- `.claude/skills/literature-review/scripts/dedupe_bib.py` (abstract handling)
- `.claude/agents/domain-literature-researcher.md` (enrichment phase)
- `.claude/agents/synthesis-planner.md` (INCOMPLETE handling)
- `.claude/agents/synthesis-writer.md` (INCOMPLETE handling)
- `.claude/docs/conventions.md` (new field specs)
- `.claude/skills/philosophy-research/SKILL.md` (new script docs)
- `tests/test_dedupe_bib.py` (abstract preservation tests)
