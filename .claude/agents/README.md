# Research Proposal Literature Review Agents

**LiRA-Inspired Multi-Agent Workflow for State-of-the-Art Reviews**

## Overview

This directory contains a sophisticated 7-phase agent-based workflow for generating comprehensive, publication-ready state-of-the-art literature reviews for research proposals. The system is inspired by the LiRA (Literature Review Agents) framework but adapted specifically for philosophical research proposals.

## Agent Architecture

### Meta-Orchestrator
- **research-proposal-orchestrator.md** - Coordinates the entire 7-phase workflow

### Phase Agents

1. **literature-review-planner.md** - Plans review structure and domain decomposition
2. **domain-literature-researcher.md** - Conducts focused literature searches per domain
3. **citation-validator.md** - Validates citations, DOIs, and metadata accuracy
4. **synthesis-planner.md** - Designs narrative structure for the review
5. **synthesis-writer.md** - Writes publication-ready literature review
6. **sota-review-editor.md** - Reviews and polishes against best practices
7. **novelty-assessor.md** - Assesses originality and provides strategic recommendations

## Workflow Phases

### Phase 1: Planning & User Collaboration
- **Agent**: `@literature-review-planner`
- **Output**: `lit-review-plan.md`
- **Process**: Analyzes research idea, decomposes into 3-8 searchable domains
- **User Input**: Review and approve plan (human-in-the-loop)

### Phase 2: Parallel Literature Search
- **Agent**: `@domain-literature-researcher` (multiple instances in parallel)
- **Output**: `literature-domain-1.md`, `literature-domain-2.md`, etc.
- **Process**: Each agent searches a specific domain using isolated context
- **Key Feature**: Parallel execution for efficiency (5-8 simultaneous researchers)

### Phase 3: Validation
- **Agent**: `@citation-validator`
- **Output**: `validation-report.md`
- **Process**: Verifies all DOIs, checks metadata accuracy, identifies issues
- **Model**: Haiku (fast validation)

### Phase 4: Synthesis Planning
- **Agent**: `@synthesis-planner`
- **Output**: `synthesis-outline.md`
- **Process**: Designs narrative structure, organizes literature thematically, plans gap analysis

### Phase 5: Synthesis Writing
- **Agent**: `@synthesis-writer`
- **Output**: `state-of-the-art-review-draft.md`
- **Process**: Writes complete review with academic prose, proper citations, gap analysis

### Phase 6: Editorial Review
- **Agent**: `@sota-review-editor`
- **Output**: `state-of-the-art-review-final.md`, `editorial-notes.md`
- **Process**: Reviews against best practices, polishes prose, ensures publication readiness

### Phase 7: Novelty Assessment
- **Agent**: `@novelty-assessor`
- **Output**: `executive-assessment.md`
- **Process**: Assesses originality, competitive positioning, provides strategic recommendations

## Key Features

### Context Preservation
- **Isolated Contexts**: Each agent uses its own context window
- **Efficient Orchestration**: Orchestrator context stays <20k tokens
- **Heavy Lifting Delegated**: Literature searches (50k+ tokens) happen in isolated contexts

### Parallelization
- **Phase 2**: Multiple domain researchers execute simultaneously
- **Speed**: 5x faster than sequential for comprehensive reviews
- **Scalability**: Can deploy 2-8 researchers based on project scope

### Iterative Refinement
- **User Checkpoints**: Human-in-the-loop mode allows review at each phase
- **Quality Assurance**: Validation phase catches errors early
- **Editorial Polish**: Dedicated editing phase ensures quality

### Standardized Format
- **Literature Entries**: Consistent format with DOI, abstract, project-specific summary
- **Relevance Scoring**: High/Medium/Low for prioritization
- **Gap Integration**: Gaps identified throughout, not just at end

## Usage

### Invoking the Workflow

```
I need a comprehensive state-of-the-art literature review for my research proposal on [topic].
```

The `@research-proposal-orchestrator` will automatically activate and guide you through the workflow.

### Execution Modes

**Autopilot Mode**:
- Execute all 7 phases automatically
- Present complete package at end
- Typical duration: 60-90 minutes

**Human-in-the-Loop Mode**:
- Review and approve after each phase
- Iterate on plan, structure, or content as needed
- More interactive but ensures perfect alignment

## Output Structure

After complete workflow, you receive:

```
research-proposal-literature-review/
├── lit-review-plan.md                    # Phase 1
├── literature-domain-1.md                # Phase 2
├── literature-domain-2.md
├── ...
├── validation-report.md                  # Phase 3
├── synthesis-outline.md                  # Phase 4
├── state-of-the-art-review-draft.md     # Phase 5
├── state-of-the-art-review-final.md     # Phase 6
├── editorial-notes.md                    # Phase 6
└── executive-assessment.md               # Phase 7
```

## Integration with Existing Skills

These agents can reference your existing analytical philosophy skills:
- `philosophical-literature` skill provides search strategies
- `argument-reconstruction` skill guides argument analysis
- `conceptual-analysis` skill informs gap identification

The hybrid approach combines agent context isolation with skill domain knowledge.

## Comparison with Skill-Based Approach

### Skill-Based Meta-Orchestrator (Current)
- ✅ Excellent domain knowledge
- ✅ Task routing
- ❌ No context isolation
- ❌ No parallel execution
- ❌ Context window fills quickly

### Agent-Based Orchestrator (This System)
- ✅ Context isolation per agent
- ✅ Parallel execution
- ✅ Iterative loops possible
- ✅ Orchestrator context preserved
- ✅ Scalable to large projects
- ✅ Can still use skill knowledge

## Technical Details

### Models Used
- **Orchestrator**: Sonnet (strategic reasoning)
- **Researchers**: Sonnet (complex literature analysis)
- **Planner**: Sonnet (strategic planning)
- **Writer**: Sonnet (academic prose)
- **Editor**: Sonnet (quality assessment)
- **Validator**: Haiku (fast, efficient validation)
- **Assessor**: Sonnet (strategic analysis)

### Context Management
- Each phase agent: Isolated context (can use 50k+ tokens)
- Orchestrator: Maintains only summaries (<20k tokens)
- Communication: File-based (agents write, orchestrator reads summaries)

### File-Based Communication
- Agents write comprehensive results to files
- Orchestrator reads only what's needed
- Preserves all intermediate work for transparency
- Enables human review at any checkpoint

## Expected Performance

### Comprehensive Review (5-8 domains, 40-80 papers)
- **Duration**: 60-90 minutes
- **Output**: 6000-9000 word review
- **Citations**: 40-80 papers validated
- **Gaps**: 3-5 specific, actionable gaps identified

### Focused Review (3-4 domains, 20-40 papers)
- **Duration**: 30-45 minutes
- **Output**: 3000-5000 word review
- **Citations**: 20-40 papers validated
- **Gaps**: 2-3 specific gaps identified

## Quality Standards

All outputs meet:
- ✅ Publication-ready academic prose
- ✅ Proper citation integration (not just listing)
- ✅ Validated citations (>95% accuracy)
- ✅ Clear, specific gap analysis
- ✅ Explicit connection to research project
- ✅ Strategic positioning for funding/publication
- ✅ Honest novelty assessment

## Future Enhancements

Potential additions:
- Specialized agents for interdisciplinary research
- Integration with citation management tools
- Automated figure generation for literature maps
- Comparative analysis across multiple research ideas
- Funder-specific formatting agents

## References

**Inspired by**:
- LiRA Framework (arXiv:2510.05138) - Multi-agent literature review generation
- claude-code-heavy - Parallel research orchestration
- wshobson/agents - Sequential pipeline patterns
- Anthropic Agent SDK best practices

## Authors

Created for the analytical philosophy skills system.
Designed for academic philosophers, graduate students, and researchers.
