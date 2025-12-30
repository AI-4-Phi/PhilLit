# Research Proposal Orchestrator Architecture

## Design Pattern: Multi-File-Then-Assemble

This orchestrator uses a consistent architectural pattern for computationally intensive phases: **multiple agents write to separate files, then orchestrator assembles the final output**.

## Philosophy-Research Skill

Domain researchers and citation validators use the `philosophy-research` skill (`.claude/skills/philosophy-research/`) which provides structured API access to academic sources:

| Script | Purpose | API |
|--------|---------|-----|
| `s2_search.py` | Paper discovery | Semantic Scholar |
| `s2_citations.py` | Citation traversal | Semantic Scholar |
| `search_openalex.py` | Broad academic search | OpenAlex (250M+ works) |
| `search_arxiv.py` | Preprint search | arXiv |
| `search_sep.py` | SEP discovery | Brave → SEP |
| `fetch_sep.py` | SEP content extraction | Direct SEP |
| `search_philpapers.py` | PhilPapers search | Brave → PhilPapers |
| `verify_paper.py` | DOI verification | CrossRef |

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

Sequential/Parallel Execution:
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
- After all sections complete:
  cat synthesis-section-*.md > state-of-the-art-review-draft.md
```

## Benefits of This Pattern

### 1. Context Efficiency
- **Phase 3**: Each researcher reads only what it searches (~10k tokens)
- **Phase 5**: Each writer reads only relevant papers (~5k words vs 24k)
- **Reduction**: 80% per invocation in Phase 5

### 2. Parallelization
- **Phase 3**: Can run all 7 researchers simultaneously
- **Phase 5**: Can run sections in parallel (though sequential usually fine)
- **Speed**: 5-7x faster for Phase 3

### 3. Modularity
- Each file is independent
- Can review individual domains/sections
- Can regenerate specific pieces without affecting others
- Easy to see what's complete

### 4. Resilience
- If interrupted, task-progress.md shows which files exist
- Resume by generating missing files only
- Partial progress preserved
- No monolithic failures

### 5. Architecture Consistency
- Same pattern used twice in workflow
- Predictable behavior
- Easy to understand and maintain
- Elegant repetition

## Alternative Considered: Monolithic Approach

### What We Could Have Done (But Didn't)

**Phase 3**: Single researcher agent reads all domains, writes one massive file
- ❌ Context: ~70k words input + output
- ❌ Time: 60-90 minutes sequential
- ❌ Fragile: One failure loses everything
- ❌ Not resumable

**Phase 5**: Single writer reads all domains, writes entire review in one pass
- ❌ Context: 24k input + 8k output = 33k words
- ❌ Quality degradation in long sessions
- ❌ No review points
- ❌ Fragile

### Why Multi-File Pattern Wins

| Aspect | Monolithic | Multi-File Pattern |
|--------|-----------|-------------------|
| **Context per task** | 70k words | 5-10k words |
| **Parallelization** | None | Full (Phase 3), Partial (Phase 5) |
| **Resumability** | Lost on failure | Perfect |
| **Modularity** | None | High |
| **Review points** | None | After each file |
| **Revision** | Regenerate all | Regenerate one file |

## Complete Workflow Context Analysis

```
Phase 2: Planning
├── Input: Research idea (~1k words)
├── Output: lit-review-plan.md (~2k words)
└── Context: ~3k words ✓

Phase 3: Domain Search (MULTI-FILE PATTERN)
├── Per researcher:
│   ├── Input: Plan excerpt (~500 words)
│   ├── Search: Skill scripts (structured APIs, isolated context)
│   └── Output: BibTeX file (~2.5k words including metadata)
├── Context per researcher: ~10k words ✓
└── Total output: 7 files × 2.5k = 17.5k words

Phase 4: Synthesis Planning
├── Input: All domain BibTeX files (~17.5k words) + plan (~2k)
├── Output: synthesis-outline.md (~2.5k words)
└── Context: ~20k words ✓

Phase 5: Synthesis Writing (MULTI-FILE PATTERN)
├── Per section:
│   ├── Input: Outline (~2.5k) + relevant BibTeX files (~5k)
│   ├── Output: section file (~1.5k words)
│   └── Context: ~9k words ✓
├── Assembly: cat synthesis-section-*.md > literature-review-final.md
└── Total output: 5 files × 1.5k = 7.5k words

(Optional) Editorial Review
├── Input: Draft (~7.5k words)
├── Output: Final (~8k words) + notes (~1k)
└── Context: ~16k words ✓

(Optional) Novelty Assessment
├── Input: Final review (~8k words) + idea (~1k)
├── Output: Executive assessment (~2k words)
└── Context: ~11k words ✓
```

**Maximum context in any phase: ~20k words (Phase 4)**
**Far below 200k token limit throughout**

**Note**: Citation validation phase removed. Domain researchers use structured API searches via the philosophy-research skill, which returns verified papers with accurate metadata.

## File Organization

**Final state** (after cleanup):
```
reviews/[project-name]/
├── literature-review-final.md            # Final review (pandoc-ready, YAML frontmatter)
├── literature-all.bib                    # Aggregated BibTeX (Zotero/pandoc)
│
├── intermediate_files/                   # Archived workflow artifacts
│   ├── task-progress.md
│   ├── lit-review-plan.md
│   ├── synthesis-outline.md
│   ├── synthesis-section-*.md
│   └── literature-domain-*.bib
│
├── state-of-the-art-review-final.md      # (Optional) Editorial output
├── editorial-notes.md
│
└── executive-assessment.md               # (Optional) Novelty output
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
```

.claude/skills/philosophy-research/
├── SKILL.md                              # Skill definition
└── scripts/
    ├── s2_search.py                      # Semantic Scholar search
    ├── s2_citations.py                   # Citation traversal
    ├── search_openalex.py                # OpenAlex search
    ├── search_arxiv.py                   # arXiv search
    ├── search_sep.py                     # SEP discovery
    ├── fetch_sep.py                      # SEP content extraction
    ├── search_philpapers.py              # PhilPapers search
    ├── verify_paper.py                   # CrossRef verification
    └── rate_limiter.py                   # Shared rate limiting
```

**Multi-file phases clearly visible**: Phase 3 (7 BibTeX files) and Phase 5 (5 section files)

## Key Design Decisions

### Why Separate Files vs. Appending?

**Considered**: Have synthesis-writer append sections to one file

**Rejected because**:
- Requires reading entire draft so far (context grows)
- Appending logic more complex
- Harder to revise individual sections
- Less consistent with Phase 3 pattern
- Can't parallelize

**Chosen**: Separate files, then assemble

**Benefits**:
- Each invocation is stateless (just write a complete section)
- Context stays constant (~9k words per section)
- Clean separation of concerns
- Mirrors Phase 3 architecture
- Simple concatenation for assembly

### Why Sequential Assembly vs. Streaming?

**Considered**: Have orchestrator stream sections as written

**Rejected because**:
- Adds complexity
- Harder to review individual sections
- Can't easily regenerate one section
- Premature optimization

**Chosen**: Write all sections, then assemble

**Benefits**:
- Simple: `cat synthesis-section-*.md > draft.md`
- All intermediate files preserved
- Can review before assembly
- Can regenerate any section
- Clear completion criteria

## Comparison to Other Orchestration Patterns

### Sequential Pipeline (e.g., wshobson/agents)

```
Agent A → complete → Agent B → complete → Agent C → complete
```

- ✅ Simple to reason about
- ❌ No parallelization
- ❌ Context accumulates

### Fan-Out-Fan-In (This System)

```
        ┌─ Agent 1 → file 1 ─┐
Input ──┼─ Agent 2 → file 2 ─┼── Assemble → Output
        └─ Agent 3 → file 3 ─┘
```

- ✅ Parallelization possible
- ✅ Context stays isolated
- ✅ Resilient to failures
- ✅ Modular outputs

### Monolithic (Traditional)

```
Single Agent → reads everything → writes everything
```

- ❌ Context explosion
- ❌ Fragile
- ❌ Long execution time
- ❌ Not resumable

## Performance Characteristics

### Time Complexity

**Phase 3 (parallel)**:
- Sequential: O(7n) where n = time per domain
- Parallel: O(n) with 7 workers
- **Speedup: 7x**

**Phase 5 (sequential in practice)**:
- Monolithic: O(5n) where n = time per section
- Multi-file: O(5n) but with much better context efficiency
- **Speedup: ~2x due to faster individual sections**

### Space Complexity

**Context usage**:
- Monolithic Phase 5: O(D + S) where D = all domains, S = output size
- Multi-file Phase 5: O(d + s) where d = relevant domains, s = section size
- **Reduction: 80% (24k → 5k words input)**

## Lessons Learned

1. **Multi-file patterns enable parallelization and resilience**
2. **Context efficiency comes from reading only what's needed**
3. **Simple assembly (concatenation) is sufficient**
4. **Architectural consistency (reusing patterns) aids understanding**
5. **Separate files are better than appending for complex workflows**
6. **Task persistence (task-progress.md) makes everything resumable**

## Future Extensions

### Potential Enhancements

1. **True parallel section writing**
   - Currently sequential for simplicity
   - Could parallelize with careful transition management
   - Task-progress.md already supports tracking

2. **Incremental assembly**
   - Stream sections as they complete
   - Would require more complex assembly logic
   - Current approach is sufficient

3. **Dependency graphs**
   - Some sections might depend on others
   - Could build DAG of section dependencies
   - Currently unnecessary (sections are independent)

4. **Caching**
   - Cache domain searches for similar projects
   - Cache section generation for iterative refinement
   - File-based architecture makes this natural

## Conclusion

The **multi-file-then-assemble** pattern is the key architectural insight that makes this orchestrator scalable and context-efficient. By breaking computationally intensive phases (Phase 3 and Phase 5) into multiple independent file outputs, we achieve:

- **80% context reduction** per invocation
- **Parallelization** where beneficial
- **Modularity** and easy revision
- **Resilience** to failures
- **Architectural consistency** across phases

This pattern should be the default for any multi-agent orchestration dealing with large knowledge synthesis tasks.