# Research Proposal Literature Review Agents

**LiRA-Inspired Multi-Agent Workflow for State-of-the-Art Reviews**

## Overview

This directory contains a 4-phase agent-based workflow for generating focused, insight-driven literature reviews for research proposals. The system is adapted specifically for philosophical research proposals, emphasizing analytical depth over comprehensive coverage.

**Key Features**:
- Domain researchers use the `philosophy-research` skill for structured API searches
- Output **valid BibTeX files** (`.bib`) for direct Zotero import
- Focused reviews emphasizing key debates and research gaps
- Papers verified at search time via structured APIs (no separate validation phase needed)

## Agent Architecture

### Meta-Orchestrator
- **research-proposal-orchestrator.md** - Coordinates the 4-phase workflow with task persistence

### Phase Agents

1. **literature-review-planner.md** - Plans review structure and domain decomposition
2. **domain-literature-researcher.md** - Uses `philosophy-research` skill to produce valid BibTeX files (`.bib`) per domain
3. **synthesis-planner.md** - Designs tight narrative structure for focused review
4. **synthesis-writer.md** - Writes focused, insight-driven literature review emphasizing key debates and gaps

### Optional Agents

- **sota-review-editor.md** - Editorial review and polish
- **novelty-assessor.md** - Strategic novelty assessment
- **citation-validator.md** - Validates external BibTeX files (not needed for in-workflow use)

## Workflow Phases

### Phase 1: Planning & User Collaboration
- **Agent**: `@literature-review-planner`
- **Output**: `lit-review-plan.md`
- **Process**: Analyzes research idea, decomposes into 3-8 searchable domains
- **User Input**: Review and approve plan (only for human-in-the-loop)

### Phase 2: Parallel Literature Search
- **Agent**: `@domain-literature-researcher` (multiple instances in parallel)
- **Skill**: `philosophy-research` (structured API searches)
- **Output**: `literature-domain-1.bib`, `literature-domain-2.bib`, etc. (BibTeX files)
- **Process**: Each agent uses skill scripts to search and produce BibTeX bibliography with:
  - Domain metadata in @comment entries (overview, gaps, synthesis guidance)
  - Standard BibTeX entries (@article, @book, etc.) with proper citation data
  - Content summary in `note` fields (Core Argument, Relevance, Position)
  - Importance levels in `keywords` fields (High/Medium/Low)
- **Key Feature**: Papers verified at search time via structured APIs (Semantic Scholar, OpenAlex, arXiv, CrossRef)
- **Architecture**: Multiple files (one per domain) created independently

### Phase 3: Synthesis Planning
- **Agent**: `@synthesis-planner`
- **Output**: `synthesis-outline.md`
- **Process**: Designs tight narrative structure (3-4 sections, 3000-4000 words), selects 15-25 papers to cite, emphasizes key debates and specific gaps
- **Key Feature**: Focus on analytical insight over comprehensive coverage

### Phase 4: Synthesis Writing (Multi-Section)
- **Agent**: `@synthesis-writer` (invoked once per section)
- **Output**: `synthesis-section-1.md`, `synthesis-section-2.md`, etc. → assembled into `literature-review-final.md`
- **Process**: Each section written to separate file with specific word targets; orchestrator assembles into final review
- **Key Feature**: Section-by-section writing with analytical depth
- **Architecture**: Multiple files (one per section) created independently, then concatenated

## Key Features

### Context Preservation
- **Isolated Contexts**: Each agent uses its own context window
- **Efficient Orchestration**: Orchestrator context stays minimal
- **BibTeX Output**: Domain researchers produce valid `.bib` files (not prose reviews)
- **Section-by-Section Writing**: Synthesis-writer reads only relevant papers per section (~5k words, not all 24k)
- **Zotero Integration**: BibTeX files can be directly imported into reference managers
- **Task Persistence**: `task-progress.md` enables resume across conversations if context limit hit

### Parallelization
- **Phase 2**: Multiple domain researchers execute simultaneously
- **Speed**: 5x faster than sequential for comprehensive reviews
- **Scalability**: Can deploy 2-8 researchers based on project scope

### Structured API Search
- **philosophy-research skill**: Domain researchers use structured API searches
- **Sources**: Semantic Scholar, OpenAlex, arXiv, SEP, PhilPapers, CrossRef
- **Verification**: Papers verified at search time (no separate validation phase)
- **Reliability**: Structured APIs return verified metadata with DOIs

### Standardized Format
- **BibTeX Format**: Valid `.bib` files with standard citation fields (author, title, journal, year, doi, etc.)
- **Rich Metadata**: Domain overview in @comment entries; paper analysis in note fields
- **Direct Import**: Users can import BibTeX files directly into Zotero
- **Agent-Readable**: Synthesis agents parse @comment and note fields for planning and writing
- **Section Files**: Each synthesis section written to separate file, then assembled (mirrors Phase 2 architecture)
- **Gap Integration**: Gaps identified throughout, not just at end

## Usage

### Invoking the Workflow

```
I need a comprehensive state-of-the-art literature review for my research proposal on [topic].
```

The `@research-proposal-orchestrator` will automatically activate and guide you through the workflow.

### Execution Modes

**Autopilot Mode**:
- Execute all 5 phases automatically
- Present focused literature review at end
- Typical duration: 45-60 minutes
- Saves task progress for resume capability

**Human-in-the-Loop Mode**:
- Review and approve after each phase
- Iterate on plan, structure, or content as needed
- More interactive but ensures perfect alignment

## Output Structure

After complete workflow, you receive:

```
reviews/[project-name]/
├── task-progress.md                      # Progress tracker (enables resume)
├── lit-review-plan.md                    # Phase 1
├── literature-domain-1.bib               # Phase 2 (BibTeX - import to Zotero)
├── literature-domain-2.bib               # Phase 2 (BibTeX - import to Zotero)
├── literature-domain-N.bib               # Phase 2 (BibTeX - import to Zotero)
├── synthesis-outline.md                  # Phase 3
├── synthesis-section-1.md                # Phase 4 (individual sections)
├── synthesis-section-2.md                # Phase 4 (individual sections)
├── synthesis-section-N.md                # Phase 4 (individual sections)
└── literature-review-final.md            # Phase 4 (assembled, 3000-4000 words)
```

## Philosophy-Research Skill

Domain researchers use the `philosophy-research` skill (`.claude/skills/philosophy-research/`) which provides structured API access:

| Script | Purpose |
|--------|---------|
| `s2_search.py` | Semantic Scholar paper discovery |
| `s2_citations.py` | Citation traversal |
| `search_openalex.py` | OpenAlex broad search (250M+ works) |
| `search_arxiv.py` | arXiv preprints |
| `search_sep.py` / `fetch_sep.py` | SEP discovery and content |
| `search_philpapers.py` | PhilPapers search |
| `verify_paper.py` | CrossRef DOI verification |

See `SKILL.md` in the skill folder for full documentation.

## Comparison with Skill-Based Approach

### Skill-Based Meta-Orchestrator (Current)
- ✅ Excellent domain knowledge
- ✅ Task routing
- ❌ No context isolation
- ❌ No parallel execution
- ❌ Context window fills quickly

### Agent-Based Orchestrator (This System)
- ✅ Context isolation per agent
- ✅ Parallel execution (Phase 2: domains, Phase 4: sections)
- ✅ Papers verified at search time via structured APIs
- ✅ Orchestrator context preserved
- ✅ Scalable to large projects
- ✅ Multi-file-then-assemble pattern (Phase 2 & 4)
- ✅ Can still use skill knowledge

## Technical Details

### Models Used
- **Orchestrator**: Sonnet (strategic reasoning + task persistence)
- **Researchers**: Sonnet (literature search + BibTeX generation)
- **Planner**: Sonnet/Opus (strategic planning for focused reviews)
- **Writer**: Sonnet (tight, analytical academic prose)

### Context Management
- Each phase agent: Isolated context (can use 50k+ tokens for search)
- Domain researchers: Output valid BibTeX files (`.bib`) with structured metadata
- Synthesis-writer: Reads only relevant BibTeX files per section (3-5 papers)
- Orchestrator: Maintains minimal context via task-progress.md
- Synthesis-planner: Can read all 7 BibTeX domain files comfortably
- Communication: File-based (agents write, orchestrator tracks progress and assembles)

### File-Based Communication
- Agents write comprehensive results to files
- Multi-file pattern: Phase 2 (domains) and Phase 4 (sections) write separate files
- Orchestrator assembles multi-file outputs (concatenation)
- BibTeX format: Phase 2 outputs are valid `.bib` files for Zotero import
- Preserves all intermediate work for transparency
- Enables human review at any checkpoint
- Easy to revise individual sections or domains
- Users can import BibTeX files to reference manager immediately

## Expected Performance

### Focused Review 
- **Citations**: 15-25 papers cited in review (selected from 40-80 found in domain search)
- **BibTeX**: 5-8 `.bib` files ready for Zotero import (all found papers)
- **Gaps**: 2-3 specific, well-defined gaps
- **Focus**: Analytical depth over comprehensive coverage
- **Resume**: Can continue from interruption via task-progress.md

### Quick Review (3-4 domains, 10-15 papers cited)
- **Duration**: 30-40 minutes
- **Output**: 2500-3000 word review
- **Citations**: 10-15 papers cited in review
- **BibTeX**: 3-4 `.bib` files ready for Zotero import
- **Gaps**: 1-2 specific gaps identified

## Quality Standards

All outputs meet:
- ✅ Focused, insight-driven prose 
- ✅ **Validated citations** (only verified papers in BibTeX files)
- ✅ Clear, specific gap analysis (2-3 gaps)
- ✅ Explicit connection to research project throughout
- ✅ Strategic positioning for funding/publication
- ✅ Analytical depth over comprehensive coverage
- ✅ Context-efficient (can complete without hitting limits)
- ✅ Modular architecture (easy to revise individual sections)

## Future Enhancements

Potential additions:
- Optional editorial review phase (for users who want 6000+ word comprehensive reviews)
- Optional novelty assessment phase (executive summary with strategic recommendations)
- Specialized agents for interdisciplinary research
- Enhanced Zotero integration (automated collection creation, tagging)
- Automated figure generation for literature maps
- Comparative analysis across multiple research ideas
- Funder-specific formatting agents
- Export to other formats (RIS, EndNote, etc.)

## References

**Inspired by**:
- LiRA Framework (arXiv:2510.05138) - Multi-agent literature review generation
- claude-code-heavy - Parallel research orchestration
- wshobson/agents - Sequential pipeline patterns
- Anthropic Agent SDK best practices

## Authors

Created for the analytical philosophy skills system.
Designed for academic philosophers, graduate students, and researchers.
