# Philo-sota: Research Proposal Literature Review System

## Quick Start

This repository contains a sophisticated multi-agent workflow for generating comprehensive, publication-ready state-of-the-art literature reviews for research proposals in philosophy.

### To Generate a Literature Review

Simply say:

```
I need a comprehensive state-of-the-art literature review for my research proposal on [your topic].
```

Or more directly:

```
@research-proposal-orchestrator - I want to write a research proposal about [topic]. Can you help me generate a literature review?
```

The orchestrator will automatically activate and guide you through the 7-phase workflow.

## What This System Does

Coordinates specialized agents to produce:
- **Comprehensive literature search** across 3-8 research domains
- **Validated citations** with >95% accuracy
- **Publication-ready review** (3,000-9,000 words)
- **Gap analysis** identifying 2-5 specific research opportunities
- **Novelty assessment** with strategic recommendations

**Typical duration**: 30-90 minutes depending on scope

## Execution Modes

When you invoke the orchestrator, choose:

### 1. Autopilot Mode (Recommended for First-Time Users)
- Runs all 7 phases automatically
- Presents complete package at end
- Fastest option
- Best when you have a clear research idea

### 2. Human-in-the-Loop Mode
- Review and approve after each phase
- Iterate on plan, structure, or content
- More control over the process
- Best when exploring or refining an idea

## The 7-Phase Workflow

### Phase 1: Planning & User Collaboration
- **Agent**: `@literature-review-planner`
- **Output**: `lit-review-plan.md`
- **What it does**: Analyzes your research idea and decomposes it into 3-8 searchable domains
- **Your role**: Review and approve the plan

### Phase 2: Parallel Literature Search
- **Agent**: `@domain-literature-researcher` (multiple instances)
- **Output**: `literature-domain-1.md`, `literature-domain-2.md`, etc.
- **What it does**: Each agent searches a specific domain using SEP, PhilPapers, Google Scholar
- **Key feature**: Runs in parallel (5-8 simultaneous researchers)

### Phase 3: Validation
- **Agent**: `@citation-validator`
- **Output**: `validation-report.md`
- **What it does**: Verifies all DOIs and metadata accuracy

### Phase 4: Synthesis Planning
- **Agent**: `@synthesis-planner`
- **Output**: `synthesis-outline.md`
- **What it does**: Designs narrative structure and organizes literature thematically

### Phase 5: Synthesis Writing
- **Agent**: `@synthesis-writer`
- **Output**: `state-of-the-art-review-draft.md`
- **What it does**: Writes complete review with academic prose and proper citations

### Phase 6: Editorial Review
- **Agent**: `@sota-review-editor`
- **Output**: `state-of-the-art-review-final.md`, `editorial-notes.md`
- **What it does**: Reviews against best practices and polishes prose

### Phase 7: Novelty Assessment
- **Agent**: `@novelty-assessor`
- **Output**: `executive-assessment.md`
- **What it does**: Assesses originality and provides strategic recommendations

## Output File Organization

### Recommended Directory Structure

When starting a new literature review, outputs should be organized as:

```
research-proposal-literature-review-[topic-name]/
├── lit-review-plan.md                    # Phase 1: Your approved plan
├── literature-domain-1.md                # Phase 2: Domain-specific searches
├── literature-domain-2.md
├── literature-domain-N.md
├── validation-report.md                  # Phase 3: Citation validation
├── synthesis-outline.md                  # Phase 4: Review structure
├── state-of-the-art-review-draft.md     # Phase 5: Initial draft
├── state-of-the-art-review-final.md     # Phase 6: Final polished version
├── editorial-notes.md                    # Phase 6: Editor feedback
└── executive-assessment.md               # Phase 7: Novelty & strategy
```

### File Naming Convention

Use descriptive folder names based on your research topic:
- `research-proposal-literature-review-free-will-compatibilism/`
- `research-proposal-literature-review-epistemic-injustice/`
- `research-proposal-literature-review-moral-responsibility/`

### Where to Create Output Files

**Option 1: In this repository (recommended for development)**
```
Philo-sota/outputs/[project-name]/
```

**Option 2: In your research project directory**
```
/path/to/your-research-project/literature-review/
```

**Option 3: Standalone directory**
```
~/Documents/literature-reviews/[project-name]/
```

The orchestrator will ask you where you'd like files created, or you can specify upfront:

```
@research-proposal-orchestrator - Generate a literature review for [topic]. 
Create all output files in: Philo-sota/outputs/my-project/
```

## Key Features

### Context Preservation
- Each agent uses isolated context windows
- Orchestrator maintains only summaries (<20k tokens)
- Can handle 100k+ token workflows efficiently

### Parallelization
- Phase 2 runs multiple domain researchers simultaneously
- 5x faster than sequential execution
- Scalable to large, interdisciplinary projects

### Quality Assurance
- Dedicated validation phase catches citation errors
- Editorial review ensures publication readiness
- Strategic assessment provides genuine research insights

### Iterative Refinement
- Can re-run any phase if not satisfied
- All intermediate files preserved for transparency
- Easy to update specific domains without starting over

## Expected Performance

### Comprehensive Review
- **Scope**: 5-8 domains, 40-80 papers
- **Duration**: 60-90 minutes
- **Output**: 6,000-9,000 word review
- **Gaps**: 3-5 specific, actionable opportunities

### Focused Review
- **Scope**: 3-4 domains, 20-40 papers
- **Duration**: 30-45 minutes
- **Output**: 3,000-5,000 word review
- **Gaps**: 2-3 specific opportunities

## Quality Standards

All outputs meet:
- ✅ Publication-ready academic prose
- ✅ Proper citation integration (not just listing)
- ✅ Validated citations (>95% accuracy)
- ✅ Clear, specific gap analysis
- ✅ Explicit connection to your research project
- ✅ Strategic positioning for funding/publication
- ✅ Honest novelty assessment

## Example Invocations

### Basic Usage
```
I'm working on a research proposal about the relationship between free will and moral responsibility. 
I need a comprehensive literature review.
```

### With Output Location
```
@research-proposal-orchestrator - I need a literature review for my project on epistemic injustice in healthcare. 
Please create outputs in: Philo-sota/outputs/epistemic-injustice-healthcare/
```

### Focused Review
```
I need a focused literature review (3-4 domains) on recent work in experimental philosophy of causation.
```

### Interdisciplinary
```
I'm proposing research at the intersection of philosophy of mind and cognitive science on consciousness. 
I need a comprehensive interdisciplinary literature review covering both philosophical and empirical work.
```

## Agent Details

All agents are located in `.claude/agents/`:

- `research-proposal-orchestrator.md` - Meta-orchestrator (invoke this one)
- `literature-review-planner.md` - Phase 1 planner
- `domain-literature-researcher.md` - Phase 2 researcher (parallel)
- `citation-validator.md` - Phase 3 validator
- `synthesis-planner.md` - Phase 4 structure designer
- `synthesis-writer.md` - Phase 5 writer
- `sota-review-editor.md` - Phase 6 editor
- `novelty-assessor.md` - Phase 7 assessor

## Technical Details

### Models Used
- **Orchestrator**: Sonnet (strategic coordination)
- **Most Agents**: Sonnet (complex reasoning and writing)
- **Validator**: Haiku (fast, efficient checking)

### Context Management
- Each phase agent operates in isolated context
- Can use 50k+ tokens per agent without affecting orchestrator
- File-based communication between agents
- Orchestrator reads only summaries

### Tools Available
All agents have access to:
- **Task**: Invoke other agents
- **Read/Write**: File operations
- **Grep**: Search project files
- **Web Search**: Literature databases (SEP, PhilPapers, Google Scholar)

## Troubleshooting

### If literature search yields too few papers
The orchestrator will automatically:
- Re-invoke researchers with broader search terms
- Consider merging domains
- Flag if the topic is genuinely under-explored

### If validation finds many errors
The orchestrator will:
- Re-invoke problematic domain researchers
- Adjust search strategies
- Flag data quality issues

### If synthesis seems incomplete
You can:
- Request targeted literature searches for specific gaps
- Ask synthesis-writer to expand sections
- Loop back to planning phase

## Iteration and Refinement

After receiving your complete literature review, you can:

```
The review looks great, but I'd like more coverage of [specific topic]. 
Can you add a domain search for that?
```

```
The executive assessment suggests exploring [X]. 
Can you research that area and add it to the review?
```

```
I'd like to refine the gap analysis in section 3. 
Can the novelty assessor take another look?
```

## Repository Structure

```
Philo-sota/
├── Claude.md                           # This file - your guide
├── .claude/
│   └── agents/
│       ├── README.md                   # Agent architecture details
│       ├── research-proposal-orchestrator.md
│       ├── literature-review-planner.md
│       ├── domain-literature-researcher.md
│       ├── citation-validator.md
│       ├── synthesis-planner.md
│       ├── synthesis-writer.md
│       ├── sota-review-editor.md
│       └── novelty-assessor.md
└── outputs/                            # Recommended location for outputs
    └── [your-project-name]/
```

## Credits

**Inspired by**: LiRA Framework (arXiv:2510.05138) - Multi-agent literature review generation

**Designed for**: Academic philosophers, graduate students, and researchers needing comprehensive, publication-ready literature reviews for research proposals, grant applications, and dissertation planning.

## Getting Started Now

Ready to generate your literature review? Just say:

```
@research-proposal-orchestrator - I need a literature review for [your topic]
```

The orchestrator will guide you through the rest!