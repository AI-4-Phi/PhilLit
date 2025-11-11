# Agent Orchestration Review and Recommendations

**Date**: 2024
**Project**: Philo-sota Research Proposal Literature Review System
**Based on**: Anthropic best practices, LiRA framework, and production agent patterns

---

## Executive Summary

Your multi-agent literature review system demonstrates solid architectural design with clear separation of concerns, good parallelization, and validation workflows. However, research into current best practices reveals several opportunities to improve reliability, debuggability, and efficiency.

**Key Strengths**:
- ✅ Well-structured 7-phase workflow
- ✅ Parallel execution in Phase 2
- ✅ Validation and self-correction loops
- ✅ Clear file-based communication
- ✅ Human-in-the-loop option

**Priority Improvements Needed**:
1. Add explicit error handling and retry logic
2. Simplify orchestrator complexity
3. Implement structured data handoffs (XML/JSON)
4. Add evaluator-optimizer loops
5. Clarify context management strategy

---

## Research Findings: Best Practices for Agent Orchestration

### 1. Anthropic's "Building Effective Agents" (Dec 2024)

**Core Principles**:
- **Simplicity First**: Start with simplest solution, add complexity only when needed
- **Transparency**: Explicitly show agent planning steps
- **Tool Design Matters**: Invest as much in Agent-Computer Interface (ACI) as Human-Computer Interface (HCI)

**Key Patterns Identified**:

#### Workflow Patterns (Predefined Paths)
1. **Prompt Chaining**: Sequential steps with programmatic checks
2. **Routing**: Classify and delegate to specialized tasks
3. **Parallelization**: Sectioning (independent subtasks) and Voting (multiple attempts)
4. **Orchestrator-Workers**: Dynamic task decomposition
5. **Evaluator-Optimizer**: Iterative refinement loops

#### Agent Patterns (Dynamic Decision-Making)
- Autonomous agents use tools in loops based on environmental feedback
- Best for open-ended problems where steps can't be predicted
- Require extensive testing and guardrails

**Tool Design Best Practices**:
- Give model enough tokens to "think" before writing
- Keep format close to naturally occurring text
- Minimize formatting overhead (no complex escaping, counting, etc.)
- Write excellent "docstrings" for tools
- Test extensively how models use tools
- "Poka-yoke" (mistake-proof) tool interfaces

### 2. Anthropic's Prompt Chaining Guide

**Key Insights**:
- Break tasks into distinct, sequential steps
- Use XML tags for clear handoffs between prompts
- Each subtask should have single, clear objective
- Run independent subtasks in parallel for speed
- Self-correction chains work well (generate → review → refine)

**When to Chain**:
- Multi-step tasks (research synthesis, document analysis, iterative content)
- Multiple transformations needed
- Need for citations or complex instructions

**Quality Patterns**:
```
Prompt 1: Generate content
Prompt 2: Review content and provide feedback
Prompt 3: Improve content based on feedback
```

### 3. LiRA Framework (arXiv:2510.05138)

**Architecture**:
- Multi-agent collaborative workflow for literature reviews
- Specialized agents: outlining, subsection writing, editing, reviewing
- Emphasis on reliability (citation validation) and readability
- Produces cohesive, comprehensive reviews

**Key Learnings**:
- Citation validation is critical (separate agent/phase)
- Editorial review improves quality significantly
- Structured workflows outperform single-shot generation
- Agent specialization improves output quality

---

## Current System Analysis

### Architecture Overview

Your system implements a sophisticated workflow with 7 phases:

```
Phase 1: Planning (literature-review-planner)
    ↓
Phase 2: Parallel Search (domain-literature-researcher × N)
    ↓
Phase 3: Validation (citation-validator)
    ↓
Phase 4: Synthesis Planning (synthesis-planner)
    ↓
Phase 5: Writing (synthesis-writer)
    ↓
Phase 6: Editorial Review (sota-review-editor)
    ↓
Phase 7: Novelty Assessment (novelty-assessor)
```

### Strengths

#### 1. **Well-Structured Workflow Pattern** ✅
- Clear phase separation aligns with Anthropic's "prompt chaining" pattern
- Each phase has single, clear objective
- Linear progression with logical dependencies

#### 2. **Parallelization Strategy** ✅
- Phase 2 explicitly uses parallel domain researchers
- Aligns with Anthropic's "sectioning" pattern
- Efficient use of isolated contexts

#### 3. **Self-Correction Loops** ✅
- Phase 3 validates citations (quality assurance)
- Phase 6 editor reviews Phase 5 draft (evaluator pattern)
- Phase 7 provides strategic assessment

#### 4. **Context Isolation** ✅
- Each agent operates in isolated context
- Orchestrator maintains only summaries
- Good for scalability (can handle 100k+ token workflows)

#### 5. **File-Based Communication** ✅
- Clear, persistent intermediate outputs
- Enables human review at checkpoints
- Transparent workflow

#### 6. **Human-in-the-Loop Option** ✅
- Autopilot vs. interactive modes
- User can approve/iterate at each phase
- Balances autonomy with control

#### 7. **Comprehensive Documentation** ✅
- Each agent has detailed instructions
- Clear output formats specified
- Quality standards defined

### Weaknesses and Gaps

#### 1. **Orchestrator Complexity** ⚠️

**Issue**: The orchestrator instructions are ~150+ lines with extensive detail.

**Why It Matters**: 
- Anthropic recommends simplicity for debuggability
- Complex orchestrators harder to maintain
- More prone to instruction-following errors

**Evidence**: 
> "We recommend finding the simplest solution possible, and only increasing complexity when needed." (Anthropic)

**Recommendation**: Simplify orchestrator to high-level coordination, move detailed instructions to individual agents.

#### 2. **Missing Error Handling** ⚠️⚠️

**Issue**: No explicit retry logic or error recovery patterns.

**Scenarios Not Addressed**:
- What if domain researcher fails to find papers?
- What if validation finds >50% invalid citations?
- What if synthesis-writer produces incoherent output?
- What if web search tools fail?

**Recommendation**: Add explicit error handling with retry logic and fallback strategies.

#### 3. **Loose Data Structures** ⚠️

**Issue**: File handoffs use markdown, which is human-readable but not strongly structured.

**Why It Matters**:
- Markdown parsing can be ambiguous
- Hard for downstream agents to reliably extract data
- No schema validation

**Anthropic Recommendation**: "Use XML tags for clear handoffs between prompts"

**Current**:
```markdown
### Fischer & Ravizza (1998) Responsibility and Control
**DOI**: 10.1017/CBO9780511814594
```

**Better**:
```xml
<paper>
  <authors>Fischer, J. M., &amp; Ravizza, M.</authors>
  <year>1998</year>
  <title>Responsibility and Control</title>
  <doi>10.1017/CBO9780511814594</doi>
</paper>
```

**Recommendation**: Use XML or JSON for structured data handoffs between agents.

#### 4. **Incomplete Evaluator-Optimizer Loop** ⚠️

**Issue**: Phase 6 editor reviews Phase 5 draft but doesn't create revision loop.

**Current Flow**:
```
Writer → Editor → Final Output
         (feedback)   (no revision)
```

**Better Flow**:
```
Writer → Editor → Writer (revise) → Editor (verify) → Final
         (feedback)    (apply feedback)    (approve)
```

**Recommendation**: Implement full evaluator-optimizer pattern where writer revises based on editor feedback.

#### 5. **No Adaptive Searching** ⚠️

**Issue**: If synthesis-planner identifies gaps in literature, no mechanism to go back to Phase 2.

**Example Scenario**:
- Phase 2 finds 30 papers
- Phase 4 synthesis-planner realizes key topic under-covered
- Currently: Continue with incomplete literature
- Better: Trigger targeted Phase 2 search for specific gap

**Recommendation**: Add back-loop from Phase 4 → Phase 2 for adaptive literature gathering.

#### 6. **Context Management Not Explicit** ⚠️

**Issue**: Orchestrator instructions say "maintains only summaries" but don't specify HOW.

**Questions**:
- Does orchestrator read full literature files or summaries?
- How are summaries extracted?
- What's the token budget for orchestrator context?

**Recommendation**: Document explicit context management strategy.

#### 7. **No Routing Pattern** ⚠️

**Issue**: All reviews go through all 7 phases regardless of complexity.

**Opportunity**:
- Simple review (3 domains, 20 papers): Could skip novelty assessment
- Comprehensive review (8 domains, 80 papers): Full workflow
- Update existing review: Could skip planning, go straight to Phase 2

**Recommendation**: Add routing logic based on review type/complexity.

#### 8. **Tool Interface Quality Unknown** ⚠️

**Issue**: Agents specify tool usage but actual tool definitions not visible.

**Anthropic Emphasis**: 
> "We actually spent more time optimizing our tools than the overall prompt." (SWE-bench case study)

**Questions**:
- Are tool descriptions clear and well-documented?
- Do tools have examples in their definitions?
- Are tools "poka-yoke'd" (mistake-proofed)?

**Recommendation**: Review and optimize all tool definitions following Anthropic's ACI guidelines.

#### 9. **No Prompt Caching Strategy** ⚠️

**Issue**: No mention of prompt caching to reduce costs/latency.

**Opportunities**:
- Cache agent system instructions (same for every invocation)
- Cache literature databases for synthesis phase
- Cache validation results

**Potential Savings**: 50-90% cost reduction for repeated operations

**Recommendation**: Implement prompt caching for static content.

#### 10. **Model Selection Not Optimized** ⚠️

**Current**:
- Most agents: Sonnet
- Validator: Haiku ✓

**Optimization Opportunities**:
- Use Haiku for simple routing/classification
- Use Sonnet for complex reasoning (planning, synthesis)
- Consider Opus for critical synthesis writing

**Recommendation**: Optimize model selection per agent based on task complexity.

#### 11. **No Checkpoint/Resume Capability** ⚠️

**Issue**: If workflow fails at Phase 5, must restart from beginning.

**Better**:
- Save state after each phase
- Allow resume from last successful phase
- Particularly important for 60-90 minute workflows

**Recommendation**: Implement state management and resume capability.

#### 12. **Limited Testing/Evaluation Framework** ⚠️

**Issue**: No systematic way to test or evaluate system performance.

**Anthropic Recommendation**: "Success in the LLM space... is about building the _right_ system for your needs."

**Questions**:
- How do you measure success?
- How do you test changes?
- How do you know if a modification improves performance?

**Recommendation**: Develop evaluation framework with test cases and success metrics.

---

## Prioritized Recommendations

### 🔴 HIGH PRIORITY (Critical for Reliability)

#### 1. Add Explicit Error Handling and Retry Logic

**Current**: Implicit assumption everything succeeds.

**Implement**:

```markdown
## Error Handling Protocol

### Phase 2: Literature Search Failures

**If <5 papers found in domain**:
1. Retry with broader search terms
2. If still <5: Flag to user with explanation
3. Option to merge with adjacent domain or continue

**If web search fails**:
1. Retry up to 3 times
2. Try alternative sources (SEP → PhilPapers → Google Scholar)
3. If all fail: Flag and continue with available sources

### Phase 3: Validation Failures

**If >20% citations invalid**:
1. Report specific issues to orchestrator
2. Re-invoke problematic domain researchers
3. If still high failure: Flag for human review

### Phase 5: Synthesis Quality Issues

**If editor identifies critical flaws**:
1. Provide specific feedback to synthesis-writer
2. Writer revises (not just new draft)
3. Re-submit for editorial review
4. Maximum 2 revision cycles
```

#### 2. Simplify Orchestrator Instructions

**Current**: 150+ lines of detailed instructions.

**Simplified Orchestrator**:

```markdown
# Research Proposal Literature Review Orchestrator

## Your Role
Coordinate 7-phase literature review workflow. Invoke specialized agents 
and handle their outputs. Maintain high-level coordination only.

## Workflow

1. **Plan** → @literature-review-planner
   - Input: Research idea
   - Output: lit-review-plan.md
   - User checkpoint: Approve plan

2. **Search (Parallel)** → @domain-literature-researcher × N
   - Input: Plan domains
   - Output: literature-domain-[N].md files
   - Error handling: Retry if <5 papers

3. **Validate** → @citation-validator
   - Input: All literature files
   - Output: validation-report.md
   - Error handling: Re-search if >20% invalid

4. **Plan Synthesis** → @synthesis-planner
   - Input: Validated literature + plan
   - Output: synthesis-outline.md

5. **Write** → @synthesis-writer
   - Input: Outline + literature
   - Output: state-of-the-art-review-draft.md

6. **Edit & Revise** → @sota-review-editor → @synthesis-writer
   - Loop until quality acceptable (max 2 cycles)
   - Output: state-of-the-art-review-final.md

7. **Assess** → @novelty-assessor
   - Input: Final review + research idea
   - Output: executive-assessment.md

## Context Management
- Read only summaries from agent outputs
- Maintain <20k token context
- Full files available to agents only

## Communication
- Show progress: "Phase X/7: [status]"
- Report agent outputs concisely
- Flag errors/issues immediately
```

**Move Details To**: Individual agent instructions (where they belong).

#### 3. Implement Structured Data Handoffs

**Add XML Wrapper to Literature Entries**:

```markdown
<literature_entry>
  <metadata>
    <authors>Fischer, J. M., &amp; Ravizza, M.</authors>
    <year>1998</year>
    <title>Responsibility and Control: A Theory of Moral Responsibility</title>
    <type>Book</type>
    <doi>10.1017/CBO9780511814594</doi>
  </metadata>
  
  <content>
    <abstract>
    Fischer and Ravizza develop a comprehensive account...
    </abstract>
    
    <project_summary>
    This book is foundational for understanding compatibilist accounts...
    </project_summary>
    
    <relevance_score>High</relevance_score>
  </content>
  
  <key_quotes>
    <quote page="31">We contend that moral responsibility is associated 
    with guidance control, not regulative control.</quote>
  </key_quotes>
</literature_entry>
```

**Benefits**:
- Unambiguous parsing for downstream agents
- Schema validation possible
- Easier to extract specific fields
- Aligns with Anthropic's recommendation

#### 4. Implement Full Evaluator-Optimizer Loop

**Current Phase 6**:
```
synthesis-writer → sota-review-editor → [END]
                   (produces final + notes)
```

**Improved Phase 6**:
```
synthesis-writer → sota-review-editor → [EVALUATE]
                                             ↓
                                         If issues:
                                             ↓
                   ← revision-request ←      
synthesis-writer (revise specific sections)
                   → revised-draft →    
                                   sota-review-editor [VERIFY]
                                             ↓
                                         Approved → [END]
```

**Implementation**:

Add to `sota-review-editor.md`:
```markdown
## Output Format

If draft is acceptable:
- Write: state-of-the-art-review-final.md
- Write: editorial-notes.md (minor suggestions only)
- Signal: "APPROVED"

If draft needs revision:
- Write: editorial-revision-request.md with:
  - Specific sections needing work
  - Concrete suggestions for improvement
  - Examples of good vs. problematic passages
- Signal: "REVISION_NEEDED"
- Maximum 2 revision cycles
```

Add to orchestrator:
```markdown
Phase 6: Editorial Review Loop

1. Invoke @sota-review-editor with draft
2. If APPROVED: Continue to Phase 7
3. If REVISION_NEEDED:
   a. Invoke @synthesis-writer with revision request
   b. Writer produces revised-draft.md
   c. Re-invoke @sota-review-editor
   d. Maximum 2 cycles; then proceed regardless
```

#### 5. Document Context Management Strategy

Add to orchestrator instructions:

```markdown
## Context Management Protocol

### Orchestrator Context Budget: <20k tokens

**What You Read Fully**:
- lit-review-plan.md (typically 2-4k tokens)
- validation-report.md (summary section only)
- synthesis-outline.md (4-6k tokens)

**What You Read as Summaries**:
- literature-domain-[N].md files:
  - Read only: Overview + Summary sections
  - ~500 tokens per domain
  - Full files available to synthesis agents
  
**Summary Extraction**:
```
Read literature-domain-1.md, extract:
1. Domain name
2. Paper count
3. Key positions covered (from Summary section)
4. Any notable gaps or issues
```

**Benefits**:
- Predictable token usage
- Orchestrator stays focused
- Agents get full context they need
```

### 🟡 MEDIUM PRIORITY (Improves Quality & Efficiency)

#### 6. Add Routing for Review Complexity

**Add Initial Classification**:

```markdown
## Phase 0: Review Type Classification

Ask user or auto-detect:
- **Focused**: 2-4 domains, 20-30 papers, 30-45 min
  - Skip: Phase 7 (Novelty Assessment) optional
  
- **Standard**: 4-6 domains, 30-50 papers, 45-60 min
  - Full workflow
  
- **Comprehensive**: 6-8 domains, 50-80 papers, 60-90 min
  - Full workflow + extended Phase 7
  
- **Update Existing**: Add to previous review
  - Skip: Phase 1 (reuse plan)
  - Start: Phase 2 with new domains only
  - Merge with existing literature
```

#### 7. Implement Adaptive Literature Gathering

**Add Back-Loop from Phase 4 → Phase 2**:

```markdown
## Phase 4: Synthesis Planning (Enhanced)

synthesis-planner produces:
- synthesis-outline.md
- gap-analysis.md (identifies under-covered topics)

If gap-analysis identifies significant gaps:
1. Orchestrator reviews gap-analysis.md
2. Present to user: "Gap detected in [topic]. Gather more literature?"
3. If yes: Create targeted search for gap
4. Invoke domain-literature-researcher with narrow focus
5. Re-invoke synthesis-planner with enhanced literature
```

#### 8. Optimize Model Selection

**Model Assignment Strategy**:

```markdown
| Agent | Current | Recommended | Rationale |
|-------|---------|-------------|-----------|
| Orchestrator | Sonnet | Sonnet | Complex coordination |
| Literature Planner | Sonnet | Sonnet | Strategic planning |
| Domain Researcher | Sonnet | Sonnet | Complex search/analysis |
| Citation Validator | Haiku | Haiku ✓ | Simple verification |
| Synthesis Planner | Sonnet | Sonnet | Strategic structure |
| Synthesis Writer | Sonnet | Opus/Sonnet | Critical writing task |
| Editor | Sonnet | Sonnet | Complex evaluation |
| Novelty Assessor | Sonnet | Sonnet | Strategic analysis |
```

**Consideration**: Use Opus for synthesis-writer if budget allows (highest quality prose).

#### 9. Implement Prompt Caching

**Cache Strategy**:

```markdown
## Caching Opportunities

### Agent System Instructions (Static)
- Cache entire system prompt for each agent
- Savings: 90% cost reduction per invocation
- Implementation: Add cache_control markers

### Literature Databases (Semi-Static)
- Cache validated literature files during synthesis
- Synthesis-writer and editor both reference same files
- Savings: 50% cost reduction in Phases 5-6

### Research Idea (Static per Session)
- Cache research idea across all agent invocations
- All agents reference the same project description
- Savings: Token cost reduction across workflow

### Example Implementation:
```
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "Research idea: ...",
      "cache_control": {"type": "ephemeral"}
    }
  ]
}
```
```

#### 10. Add Checkpoint/Resume Capability

**State Management**:

```markdown
## Workflow State File: .workflow-state.json

{
  "workflow_id": "uuid",
  "research_topic": "...",
  "start_time": "ISO-8601",
  "current_phase": 4,
  "completed_phases": [1, 2, 3],
  "phase_outputs": {
    "1": "lit-review-plan.md",
    "2": ["literature-domain-1.md", "literature-domain-2.md"],
    "3": "validation-report.md"
  },
  "last_error": null
}

## Resume Command:
"Resume literature review workflow from last checkpoint"

## Implementation:
1. Save state after each successful phase
2. On resume: Read state, skip completed phases
3. On error: Save error state, allow manual intervention
```

### 🟢 LOW PRIORITY (Nice to Have)

#### 11. Develop Evaluation Framework

**Test Suite Structure**:

```markdown
## Evaluation Test Cases

### Unit Tests (Individual Agents)
- domain-literature-researcher: Given topic, finds >10 relevant papers
- citation-validator: Detects invalid DOIs (false positives <5%)
- synthesis-writer: Produces coherent prose (human evaluation)

### Integration Tests (Full Workflow)
- Test Topic 1: "Free Will and Moral Responsibility"
  - Expected: 5-8 domains, 40-60 papers, 3-5 gaps identified
  - Success Criteria: >90% citations valid, coherent review
  
### Performance Benchmarks
- Time: 60-90 min for comprehensive review
- Cost: $X per comprehensive review
- Quality: Expert rating >4/5

### Regression Tests
- After changes, re-run test cases
- Compare outputs to baseline
- Flag degradations
```

#### 12. Enhanced Tool Definitions

**Tool Review Checklist**:

Following Anthropic's ACI guidelines, review each tool:

```markdown
## Tool Quality Assessment

For each tool (WebSearch, WebFetch, etc.):

✓ **Clear Description**: Would junior developer understand how to use?
✓ **Examples Included**: Shows typical usage patterns
✓ **Edge Cases Documented**: What happens with bad input?
✓ **Error Messages**: Clear failures, not cryptic
✓ **Poka-Yoke Design**: Hard to misuse
✓ **Format Simplicity**: No complex escaping needed
✓ **Natural Alignment**: Close to text model has seen

## Example: WebSearch Tool Definition

BAD:
{
  "name": "search",
  "description": "Search the web"
}

GOOD:
{
  "name": "web_search",
  "description": "Search academic databases and web for papers. Returns list of papers with titles, authors, abstracts, and links. Use specific philosophical terms for best results.",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query using philosophical terminology. Examples: 'compatibilism moral responsibility', 'Frankfurt hierarchical desires', 'neuroscience free will Libet'. Be specific."
    },
    "source": {
      "type": "string",
      "enum": ["SEP", "PhilPapers", "GoogleScholar", "auto"],
      "description": "Which source to search. 'auto' tries all sources. Default: auto"
    }
  }
}
```

#### 13. Progressive Disclosure in UI

**Instead of**:
```
"I will execute 7 phases: Phase 1 Planning, Phase 2 Parallel Search, 
Phase 3 Validation, Phase 4 Synthesis Planning, Phase 5 Writing, 
Phase 6 Editorial Review, Phase 7 Novelty Assessment"
```

**Use**:
```
"Starting literature review workflow...

Phase 1/7: Planning your review structure
[Complete] Created plan with 5 domains

Phase 2/7: Searching literature (parallel)
[In Progress] Researching domain 1/5: Compatibilism...
[In Progress] Researching domain 2/5: Neuroscience...
```

---

## Implementation Roadmap

### Sprint 1: Core Reliability (Week 1)
- [ ] Add error handling and retry logic
- [ ] Simplify orchestrator instructions
- [ ] Implement structured XML handoffs
- [ ] Document context management

### Sprint 2: Quality Improvements (Week 2)
- [ ] Implement evaluator-optimizer loop
- [ ] Add adaptive literature gathering
- [ ] Optimize model selection
- [ ] Add prompt caching

### Sprint 3: Robustness (Week 3)
- [ ] Add routing for review types
- [ ] Implement checkpoint/resume
- [ ] Review and optimize tool definitions
- [ ] Create basic evaluation framework

### Sprint 4: Polish (Week 4)
- [ ] Progressive disclosure UI
- [ ] Enhanced error messages
- [ ] Performance optimization
- [ ] Documentation updates

---

## Testing Strategy

### Phase 1 Testing (After Sprint 1)
1. Test with simple research topic
2. Deliberately break things:
   - Kill domain researcher mid-search
   - Provide invalid DOIs
   - Use obscure topic with no papers
3. Verify error handling works
4. Measure: Does it recover gracefully?

### Phase 2 Testing (After Sprint 2)
1. Test with complex interdisciplinary topic
2. Measure quality improvement from optimizer loop
3. Test adaptive gathering with gap-prone topic
4. Benchmark: Cost savings from caching

### Phase 3 Testing (After Sprint 3)
1. Test resume from each phase
2. Verify routing for different review types
3. Test with 5 diverse research topics
4. Collect metrics: time, cost, quality ratings

---

## Success Metrics

### Reliability
- [ ] 95% completion rate without errors
- [ ] Error recovery success >90%
- [ ] <5% false negatives in validation

### Quality
- [ ] Expert ratings >4/5 on final reviews
- [ ] >95% citation accuracy
- [ ] All reviews identify 3+ genuine gaps

### Efficiency
- [ ] 30-90 min execution (depending on scope)
- [ ] 50% cost reduction from caching
- [ ] Parallel execution 5x faster than sequential

### Usability
- [ ] Users can resume after failures
- [ ] Clear progress indicators
- [ ] Comprehensible error messages

---

## Conclusion

Your literature review system has a strong foundation with excellent architectural choices. The recommendations above focus on:

1. **Reliability**: Error handling and retry logic
2. **Simplicity**: Cleaner orchestrator, clearer handoffs
3. **Quality**: Optimizer loops and adaptive gathering
4. **Efficiency**: Caching and model optimization

These improvements align with Anthropic's best practices and production-proven patterns. Prioritize the HIGH PRIORITY items first—they provide the most value for reliability and debuggability.

The system is already production-quality; these enhancements make it production-hardened.

---

## References

1. Anthropic. (2024). "Building Effective Agents." https://www.anthropic.com/research/building-effective-agents
2. Anthropic. (2024). "Chain Complex Prompts." Claude Documentation.
3. Go, G. H. T., et al. (2024). "LiRA: A Multi-Agent Framework for Reliable and Readable Literature Review Generation." arXiv:2510.05138
4. Your existing system documentation in `.claude/agents/`

---

## Appendix: Quick Reference

### Error Handling Template
```
Try:
  Execute agent
Catch SpecificError:
  Retry with fallback strategy (max 3 times)
  If all fail: Log, flag to user, continue with degraded output
```

### XML Handoff Template
```xml
<agent_output phase="N">
  <metadata>
    <agent>agent-name</agent>
    <timestamp>ISO-8601</timestamp>
    <status>success|partial|failed</status>
  </metadata>
  <data>
    <!-- Structured data here -->
  </data>
  <summary>
    <!-- Human-readable summary -->
  </summary>
</agent_output>
```

### Context Management Template
```
Full Read: <5k tokens
Summary Read: 5-50k tokens (extract key points only)
Skip: >50k tokens (pass file reference to agents)
```
