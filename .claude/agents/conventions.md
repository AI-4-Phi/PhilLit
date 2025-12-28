# Shared Conventions for Literature Review Agents

This file contains specifications shared across multiple agents. Reference this file rather than duplicating content.

---

## File Encoding: UTF-8

**All output files MUST use UTF-8 encoding.**

Requirements:
- Preserve diacritics in author names exactly (e.g., Kästner, Müller, García)
- Use proper special characters: ä ö ü é è ñ ç etc.
- Use typographic characters: em-dash (—), en-dash (–), curly quotes (" " ' ')
- Never convert special characters to ASCII approximations

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

Examples: `frankfurt1971freedom`, `fischerravizza1998responsibility`, `nelkin2011rational`

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
- If DOI unavailable, omit the field entirely — never fabricate

### Keywords Field

Format: `topic-tag, position-tag, Importance-level`

Importance levels:
- `High` — Core paper, must cite
- `Medium` — Important context
- `Low` — Peripheral but relevant

Example: `keywords = {compatibilism, free-will, hierarchical-agency, High}`

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
Fischer, John Martin, and Mark Ravizza. 1998. Responsibility and Control: A Theory of Moral Responsibility. Cambridge: Cambridge University Press. https://doi.org/10.1017/CBO9780511814594.
```

**Book Chapter**:
```
Nelkin, Dana Kay. 2011. "Freedom and Responsibility." In The Oxford Handbook of Free Will, edited by Robert Kane, 425–453. Oxford: Oxford University Press.
```

---

## Communication with Orchestrator

### Standard Return Message Format

```
[Task name] complete.

Results:
- [Key metric 1]: [value]
- [Key metric 2]: [value]
- [Key metric 3]: [value]

Status: [PASS | REVIEW | specific status]

Files:
- [filename1.ext] ([description])
- [filename2.ext] ([description])

[One-line next step or recommendation]
```

### Progress Updates During Execution

- Use clear phase indicators: "Phase 2/5: [description]..."
- Report completion with file references: "Section 1 complete → synthesis-section-1.md (450 words)"
- Track running totals: "Running total: 1800/3500 words"

---

## Quality Standards

### Citation Integrity

**Absolute Rules**:
- ❌ Never fabricate papers, authors, or publications
- ❌ Never create synthetic DOIs
- ❌ Never cite papers not verified through search
- ✅ Only cite papers found via skill scripts (s2_search, search_openalex, etc.)
- ✅ Papers from structured APIs are verified at search time
- ✅ Use `verify_paper.py` for DOI verification when needed
- ✅ If DOI unavailable, omit the field

### Citation Integration in Prose

**Good** (analytical):
> Fischer and Ravizza (1998) argue that guidance control—the ability to regulate behavior through reasons-responsive mechanisms—grounds moral responsibility. This differs crucially from libertarian views...

**Poor** (list-like):
> Many philosophers have written about this (Frankfurt 1971; Dennett 1984; Fischer and Ravizza 1998).

### Gap Specificity

**Good** (specific, evidence-based):
> While compatibilist frameworks are philosophically sophisticated, Vargas (2013) notes they "lack empirical operationalization" (p. 203). No study has measured neural mechanisms of reasons-responsiveness.

**Poor** (vague):
> More research is needed on free will and neuroscience.

---

## Annotation Quality

**Annotations are the core intellectual contribution of literature research.** This section defines quality standards for domain overviews and individual entry annotations.

### Writing Style

- **Concise and direct.** Short, clear sentences.
- **No academic jargon.** Write for clarity, not to impress.
- **No redundant phrases.** Cut "it is important to note that" and similar hedging.
- **Active voice.** "Craver argues X" not "It is argued by Craver that X"
- **Substantive claims.** State what the paper *actually argues*, not that it "addresses" or "explores" a topic.

### Anti-Patterns to Avoid

Never write:
- "Important contribution to the field"
- "Raises important questions"
- "Significant implications for"
- "This paper explores/examines/investigates"
- "Relevant to our project" (without saying *how*)
- Generic phrases that could apply to any paper

### Domain Overview Quality

The `@comment` section establishes context for synthesis agents. Each component:

**DOMAIN_OVERVIEW** (2-3 paragraphs):
- Name key authors and works that anchor the field
- Identify distinct positions or schools of thought
- Note recent developments or shifts in the debate
- Be specific: cite paper names, concepts, years

**RELEVANCE_TO_PROJECT** (2-3 sentences):
- State the *specific* connection to the research question
- Explain what this domain contributes that others don't

**NOTABLE_GAPS** (1-2 sentences):
- Identify concrete under-explored areas
- Be specific enough that a researcher could act on it

**SYNTHESIS_GUIDANCE** (1-2 sentences):
- Suggest how to use this domain in the review
- Note tensions or connections with other domains

### Individual Entry Annotations

The `note` field serves synthesis agents. Structure as CORE ARGUMENT, RELEVANCE, POSITION—but prioritize quality over rigid format. If a paper resists this structure, adapt.

**CORE ARGUMENT** (2-4 sentences):
- State the paper's central thesis
- Include key concepts, frameworks, or findings introduced
- Capture the argumentative structure, not just topic

**RELEVANCE** (2-3 sentences):
- Connect *specifically* to the research project
- Note what gap this fills or leaves open
- Identify tensions or complementarities with other papers

**POSITION** (1 sentence):
- Place in intellectual landscape
- Identify school, tradition, or debate position

### Exemplar: High-Quality Entry

```bibtex
@book{craver2007explaining,
  author = {Craver, Carl F.},
  title = {Explaining the Brain: Mechanisms and the Mosaic Unity of Neuroscience},
  publisher = {Oxford University Press},
  year = {2007},
  doi = {10.1093/acprof:oso/9780199299317.001.0001},
  note = {
  CORE ARGUMENT: Develops comprehensive mechanistic account of explanation in neuroscience, introducing "levels of mechanisms" defined by constitutive part-whole relationships rather than size or disciplinary boundaries. Argues neuroscience achieves unity through interlevel integration via mechanisms, not reduction to physics. Provides mutual manipulability (MM) criterion for constitutive relevance: X's φ-ing is constitutively relevant to S's ψ-ing when interventions on X change ψ-ing and vice versa.

  RELEVANCE: Central work for understanding levels of organization and mechanistic explanation criteria directly applicable to neural network interpretability. The MM criterion provides testable conditions for claims about component relevance in artificial neural networks. However, challenges arise when trying to identify genuine constitutive relationships versus mere correlations in learned representations.

  POSITION: New mechanist framework - develops levels of mechanisms and constitutive relevance criteria.
  },
  keywords = {mechanisms, levels-of-mechanisms, neuroscience, High}
}
```

**Why this works:**
- States specific thesis (levels defined by part-whole relations, not size)
- Names the key concept introduced (mutual manipulability criterion)
- Connects to research project with concrete application (testable conditions for component relevance)
- Notes a limitation (constitutive vs correlational challenge)
- Places in intellectual landscape (new mechanist framework)

### Exemplar: Domain Overview

```
DOMAIN_OVERVIEW:
The "new mechanistic" philosophy emerged in the late 1990s and early 2000s,
spearheaded by Machamer, Darden, and Craver (2000), Glennan (1996, 2017), and
Bechtel and Richardson (1993/2010). This framework shifted philosophical focus
from laws and covering-law explanation to mechanisms as the basic units of
scientific explanation across the life sciences. A mechanism is characterized as
entities and activities organized to produce regular changes from start to finish
conditions.

Central to mechanistic explanation is the concept of "levels of mechanisms"
(Craver 2007), which differ from traditional size-based or disciplinary levels.
Mechanistic levels are defined by constitutive part-whole relationships: lower-level
components constitute higher-level capacities when properly organized.

RELEVANCE_TO_PROJECT:
This domain provides theoretical grounding for what counts as "mechanistic" in
mechanistic interpretability of AI systems. The philosophical framework helps clarify
when interpretability efforts genuinely provide mechanistic understanding versus
superficial description.

NOTABLE_GAPS:
Systematic philosophical analysis of AI/ML systems through the mechanistic lens
remains sparse. Whether artificial neural networks satisfy the organization and
constitutive criteria for mechanisms is underexplored.
```

**Why this works:**
- Names specific authors and years
- Defines key terms concretely
- States relevance to project directly
- Identifies actionable gap

---

## Domain File Structure

### BibTeX Domain Files

```bibtex
@comment{
====================================================================
DOMAIN: [Domain Name]
SEARCH_DATE: [YYYY-MM-DD]
PAPERS_FOUND: [N total] (High: [X], Medium: [Y], Low: [Z])
SEARCH_SOURCES: SEP, PhilPapers, Google Scholar, [other]
====================================================================

DOMAIN_OVERVIEW:
[2-3 paragraphs on main debates, key papers, developments]

RELEVANCE_TO_PROJECT:
[2-3 sentences connecting to research idea]

NOTABLE_GAPS:
[1-2 sentences on under-explored areas]

SYNTHESIS_GUIDANCE:
[1-2 sentences with recommendations]

KEY_POSITIONS:
- [Position 1]: [X papers] - [Brief description]
- [Position 2]: [Y papers] - [Brief description]
====================================================================
}

@article{citationkey,
  author = {...},
  title = {...},
  ...
  note = {...},
  keywords = {...}
}
```

---

## Status Updates (User Visibility)

**Critical**: In Claude Code CLI, **text output is visible to the user in real-time**. Use this for progress updates.

### Principles

1. **Output text directly** — Don't rely solely on file writes; users see your text output immediately
2. **Update at natural boundaries** — After each phase, search, or significant step
3. **Be concise** — Status updates should be 1-2 lines, not verbose
4. **Show progress** — Include counts, percentages, or "X of Y" indicators
5. **Name what's happening** — Users should know which phase/step is active

### Status Update Format

**Phase start**:
```
📚 Phase 2: Domain Literature Search (3 of 5 domains)
```

**Step progress**:
```
→ Searching Semantic Scholar... found 24 papers
→ Searching OpenAlex... found 18 papers
→ Running citation chain on 3 seed papers...
```

**Phase completion**:
```
✓ Domain 3 complete: literature-domain-3.bib (15 papers)
```

**Error/retry**:
```
⚠ API timeout, retrying (attempt 2/3)...
```

### When to Update

| Agent | Update Points |
|-------|---------------|
| **orchestrator** | Phase transitions, domain completions, assembly steps |
| **domain-researcher** | Each search phase (SEP, PhilPapers, S2, OpenAlex, arXiv), citation chaining, file write |
| **lit-review-planner** | Domain identification progress, plan completion |
| **synthesis-planner** | Reading BibTeX files, outline section progress |
| **synthesis-writer** | Section start, word count milestones, section completion |

### Examples

**Domain researcher during search**:
```
📚 Searching domain: Compatibilist Free Will

→ Phase 1: SEP... found 2 relevant entries
→ Phase 2: PhilPapers... found 12 papers
→ Phase 3: Semantic Scholar... found 28 papers
→ Phase 3: OpenAlex... found 15 papers (running parallel)
→ Phase 4: Citation chaining on 5 seed papers... found 8 additional
→ Phase 5: Verifying 3 uncertain DOIs...

✓ Domain complete: 18 papers selected → literature-domain-1.bib
```

**Synthesis writer during section**:
```
📝 Writing Section 2: Key Theoretical Debates

→ Reading 12 relevant papers from 3 domain files...
→ Writing subsection 2.1: Compatibilist Accounts (target: 400 words)
→ Progress: 850/1200 words
→ Writing subsection 2.2: Libertarian Responses

✓ Section 2 complete: 1,180 words, 14 citations → synthesis-section-2.md
```

---

## File Assembly

### Combining Section Files

Use proper spacing for markdown parsing:

```bash
for f in synthesis-section-*.md; do cat "$f"; echo; echo; done > literature-review-final.md
```

Two blank lines between sections ensures pandoc parses headings correctly.
