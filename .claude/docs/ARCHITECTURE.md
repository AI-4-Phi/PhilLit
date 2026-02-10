# Literature Review Architecture

## Orchestration: Skill-Based Design

The literature review workflow is coordinated by the `/literature-review` skill (`.claude/skills/literature-review/SKILL.md`), which runs in the main conversation context.

**Why a skill, not a subagent?**
- Subagents cannot spawn other subagents (Claude Code constraint)
- The orchestrator needs to invoke multiple specialized subagents via the Task tool
- Skills run in main conversation context, which has Task tool access
- This enables: skill → Task tool → specialized subagents

**Architecture**:
```
User request
    ↓
/literature-review skill (main conversation, has Task access)
    ↓ Task tool
    ├── literature-review-planner (subagent)
    ├── domain-literature-researcher ×N (subagents)
    ├── synthesis-planner (subagent)
    └── synthesis-writer ×N (subagents)
```

Specialized subagents (in `.claude/agents/`) are invoked via Task tool and cannot themselves invoke other subagents.

## Design Pattern: Multi-File-Then-Assemble

This workflow uses a consistent architectural pattern for computationally intensive phases: **multiple agents write to separate files, then the orchestrating skill assembles the final output**.

## Philosophy-Research Skill

Domain researchers and citation validators use the `philosophy-research` skill (`.claude/skills/philosophy-research/`) which provides structured API access to academic sources:

| Script | Purpose | API |
|--------|---------|-----|
| `s2_search.py` | Paper discovery | Semantic Scholar |
| `s2_citations.py` | Citation traversal | Semantic Scholar |
| `s2_batch.py` | Batch paper details | Semantic Scholar |
| `s2_recommend.py` | Find similar papers | Semantic Scholar |
| `search_openalex.py` | Broad academic search | OpenAlex (250M+ works) |
| `search_arxiv.py` | Preprint search | arXiv |
| `search_core.py` | Paper search with abstracts | CORE (431M papers) |
| `search_sep.py` | SEP discovery | Brave → SEP |
| `fetch_sep.py` | SEP content extraction | Direct SEP |
| `search_iep.py` | IEP discovery | Brave → IEP |
| `fetch_iep.py` | IEP content extraction | Direct IEP |
| `search_philpapers.py` | PhilPapers search | Brave → PhilPapers |
| `verify_paper.py` | DOI verification | CrossRef |
| `get_abstract.py` | Multi-source abstract resolution | S2 → OpenAlex → CORE |
| `get_sep_context.py` | SEP citation context extraction | Direct SEP |
| `get_iep_context.py` | IEP citation context extraction | Direct IEP |
| `brave_search.py` | Web search fallback | Brave Search |
| `search_cache.py` | Search result caching | — |
| `rate_limiter.py` | Shared rate limiting | — |
| `output.py` | Shared output utilities | — |
| `check_setup.py` | Environment verification | — |

**Key benefit**: Papers discovered via structured APIs are verified at search time, eliminating the need for a separate validation phase.

## Pattern Implementation

### Phase 3: Parallel Domain Literature Search

**Pattern**: Multiple researchers → Individual BibTeX files → Used by synthesis-planner

```
Input: lit-review-plan.md (identifies 7 domains)

Parallel Execution:
├── @domain-literature-researcher #1 → literature-domain-1.bib
├── @domain-literature-researcher #2 → literature-domain-2.bib
├── @domain-literature-researcher #3 → literature-domain-3.bib
├── @domain-literature-researcher #4 → literature-domain-4.bib
├── @domain-literature-researcher #5 → literature-domain-5.bib
├── @domain-literature-researcher #6 → literature-domain-6.bib
└── @domain-literature-researcher #7 → literature-domain-7.bib

Each agent:
- Isolated context
- Uses philosophy-research skill scripts for structured API searches
- Produces valid BibTeX file with rich metadata
- Papers verified at search time via APIs
- Independent of other researchers

Orchestrator:
- Tracks completion in task-progress.md
- All files used together by synthesis-planner
- No explicit assembly needed (planner reads all)
- No separate validation phase needed
```

### Phase 4 & 5: Synthesis Planning and Section-by-Section Writing

**Pattern**: Planner creates outline → Multiple writers → Individual section files → Assembled into draft

```
Input: synthesis-outline.md (identifies 5 sections)

Parallel Execution:
├── @synthesis-writer #1 → synthesis-section-1.md (Introduction)
├── @synthesis-writer #2 → synthesis-section-2.md (Theoretical Foundations)
├── @synthesis-writer #3 → synthesis-section-3.md (Current State-of-the-Art)
├── @synthesis-writer #4 → synthesis-section-4.md (Research Gaps)
└── @synthesis-writer #5 → synthesis-section-5.md (Conclusion)

Each invocation:
- Isolated context
- Reads only relevant domain files (~5k words, not all 24k)
- Writes one complete section
- Independent markdown file

Orchestrator:
- Tracks completion in task-progress.md
- After all sections complete: Use Glob+Read+Write to assemble synthesis-section-*.md into final review
```

## File Organization

**Final state** (after cleanup):
```
reviews/[project-name]/
├── literature-review-final.md            # Final review (pandoc-ready, YAML frontmatter)
├── literature-all.bib                    # Aggregated BibTeX
│
├── intermediate_files/                   # Archived workflow artifacts
│   ├── json/                             # API response files (archived)
│   ├── task-progress.md
│   ├── lit-review-plan.md
│   ├── synthesis-outline.md
│   ├── synthesis-section-*.md
│   └── literature-domain-*.bib
│
└── literature-review-final.docx          # (Optional) DOCX conversion
```

**During workflow** (before cleanup):
```
reviews/[project-name]/
├── task-progress.md                      # State tracker (CRITICAL for resume)
│
├── lit-review-plan.md                    # Phase 2 output
│
├── literature-domain-1.bib               # Phase 3 outputs (BibTeX, multi-file)
├── literature-domain-2.bib
├── literature-domain-3.bib
├── literature-domain-4.bib
├── literature-domain-5.bib
├── literature-domain-6.bib
├── literature-domain-7.bib
│
├── synthesis-outline.md                  # Phase 4 output
│
├── synthesis-section-1.md                # Phase 5 outputs (multi-file)
├── synthesis-section-2.md
├── synthesis-section-3.md
├── synthesis-section-4.md
├── synthesis-section-5.md
├── literature-all.bib                    # Phase 6: Aggregated BibTeX
└── literature-review-final.md            # Phase 6: Assembled with YAML frontmatter


.claude/skills/literature-review/
├── SKILL.md                              # Orchestration skill (main entry point)
└── scripts/
    ├── assemble_review.py                # Assemble sections into final review
    ├── dedupe_bib.py                     # Deduplicate and merge BibTeX
    ├── enrich_bibliography.py            # Batch abstract resolution for BibTeX
    ├── generate_bibliography.py          # Generate Chicago-style references
    └── lint_md.py                        # Lint markdown review files

.claude/skills/philosophy-research/
├── SKILL.md                              # API search skill
└── scripts/
    ├── s2_search.py                      # Semantic Scholar search
    ├── s2_citations.py                   # Citation traversal
    ├── s2_batch.py                       # Batch paper details
    ├── s2_recommend.py                   # Find similar papers
    ├── s2_formatters.py                  # S2 output formatting
    ├── search_openalex.py                # OpenAlex search
    ├── search_arxiv.py                   # arXiv search
    ├── search_core.py                    # CORE API search (abstracts)
    ├── search_sep.py                     # SEP discovery
    ├── fetch_sep.py                      # SEP content extraction
    ├── search_iep.py                     # IEP discovery
    ├── fetch_iep.py                      # IEP content extraction
    ├── search_philpapers.py              # PhilPapers search
    ├── brave_search.py                   # Brave web search
    ├── verify_paper.py                   # CrossRef verification
    ├── get_abstract.py                   # Multi-source abstract resolution
    ├── get_sep_context.py                # SEP citation context extraction
    ├── get_iep_context.py                # IEP citation context extraction
    ├── search_cache.py                   # Search result caching
    ├── rate_limiter.py                   # Shared rate limiting
    ├── output.py                         # Shared output utilities
    └── check_setup.py                    # Environment verification

.claude/hooks/
├── setup-environment.sh                  # SessionStart: activate venv
├── subagent_stop_bib.sh                  # SubagentStop: validate BibTeX
├── bib_validator.py                      # BibTeX validation logic
├── metadata_validator.py                 # Metadata provenance validation
└── metadata_cleaner.py                   # Metadata year/type cleanup

.claude/agents/
├── literature-review-planner.md          # Decomposes research into domains
├── domain-literature-researcher.md       # Searches and produces BibTeX
├── synthesis-planner.md                  # Creates review outline
└── synthesis-writer.md                   # Writes review sections
```