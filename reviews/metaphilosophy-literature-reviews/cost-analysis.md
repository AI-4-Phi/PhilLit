# Cost and Efficiency Analysis: Literature Review on the Methodology and Ethics of Literature Reviews

**Date**: 2026-02-10
**Review**: `reviews/metaphilosophy-literature-reviews/`
**Model (main session)**: Claude Opus 4.6

---

## API Pricing (Feb 2026)

| Model | Input / MTok | Output / MTok |
|-------|-------------|---------------|
| **Opus 4.6** | $5.00 | $25.00 |
| **Sonnet 4.5** | $3.00 | $15.00 |
| **Haiku 4.5** | $1.00 | $5.00 |

Prompt caching: cache reads at 0.1x base input price. Extended context (>200K input): 2x input, 1.5x output.

Sources: [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Claude API Pricing Calculator](https://invertedstone.com/calculators/claude-pricing)

---

## Model Assignment per Component

| Component | Model | Reason |
|-----------|-------|--------|
| Orchestrator (main conversation) | **Opus 4.6** | User's session model |
| `literature-review-planner` | **Opus 4.6** (inherit) | Strategic decomposition |
| `domain-literature-researcher` | **Sonnet 4.5** (explicit) | High-volume API searches |
| `synthesis-planner` | **Opus 4.6** (inherit) | Cross-domain architectural decisions |
| `synthesis-writer` | **Opus 4.6** (inherit) | Academic prose quality |

---

## Token Breakdown by Phase

Measured values from subagent `usage` reports. Orchestrator is estimated.

| Phase | Component | Model | Tokens | Tool Uses | Duration |
|-------|-----------|-------|--------|-----------|----------|
| **2** | lit-review-planner | Opus | 16,372 | 4 | 1.9 min |
| **3** | domain-1 (metaphilosophy) | Sonnet | 126,300 | 26 | 5.2 min |
| **3** | domain-2 (lit review method) | Sonnet | 92,335 | 50 | 6.1 min |
| **3** | domain-3 (citation ethics) | Sonnet | 131,694 | 53 | 7.8 min |
| **3** | domain-4 (canon formation) | Sonnet | 134,292 | 33 | 5.5 min |
| **3** | domain-5 (hermeneutics) | Sonnet | 125,663 | 33 | 4.8 min |
| **3** | domain-6 (sociology) | Sonnet | 138,095 | 38 | 6.1 min |
| **3** | domain-7 (research ethics) | Sonnet | 148,487 | 32 | 7.3 min |
| | **Phase 3 subtotal** | | **896,866** | **265** | |
| **4** | synthesis-planner | Opus | 98,746 | 10 | 3.2 min |
| **5** | synthesis-writer-1 (intro) | Opus | 55,492 | 6 | 0.6 min |
| **5** | synthesis-writer-2 (methodology) | Opus | 52,254 | 8 | 1.6 min |
| **5** | synthesis-writer-3 (ethics) | Opus | 68,991 | 7 | 1.3 min |
| **5** | synthesis-writer-4 (gaps/conclusion) | Opus | 96,588 | 14 | 1.4 min |
| | **Phase 5 subtotal** | | **273,325** | **35** | |
| | **Subagent total** | | **1,285,309** | **314** | |
| **1,6** | Orchestrator (est.) | Opus | ~300,000 | ~21 turns | |
| | **GRAND TOTAL** | | **~1,585,000** | | |

---

## Cost Estimates by Phase

Input/output split estimated from tool-use intensity:

- High tool use (>10 uses): 85% input / 15% output
- Low tool use (<10 uses): 75% input / 25% output

| Phase | Component | Model | Tokens | Est. Input | Est. Output | Est. Cost |
|-------|-----------|-------|--------|------------|-------------|-----------|
| **2** | Planner | Opus | 16,372 | 12,279 | 4,093 | $0.16 |
| **3** | Domain 1 | Sonnet | 126,300 | 107,355 | 18,945 | $0.61 |
| **3** | Domain 2 | Sonnet | 92,335 | 78,485 | 13,850 | $0.44 |
| **3** | Domain 3 | Sonnet | 131,694 | 111,940 | 19,754 | $0.63 |
| **3** | Domain 4 | Sonnet | 134,292 | 114,148 | 20,144 | $0.64 |
| **3** | Domain 5 | Sonnet | 125,663 | 106,814 | 18,849 | $0.60 |
| **3** | Domain 6 | Sonnet | 138,095 | 117,381 | 20,714 | $0.66 |
| **3** | Domain 7 | Sonnet | 148,487 | 126,214 | 22,273 | $0.71 |
| | **Phase 3 subtotal** | | **896,866** | | | **$4.29** |
| **4** | Synth. planner | Opus | 98,746 | 78,997 | 19,749 | $0.89 |
| **5** | Writer 1 (intro) | Opus | 55,492 | 41,619 | 13,873 | $0.55 |
| **5** | Writer 2 (method) | Opus | 52,254 | 39,191 | 13,064 | $0.52 |
| **5** | Writer 3 (ethics) | Opus | 68,991 | 51,743 | 17,248 | $0.69 |
| **5** | Writer 4 (gaps) | Opus | 96,588 | 77,270 | 19,318 | $0.87 |
| | **Phase 5 subtotal** | | **273,325** | | | **$2.63** |
| **1,6** | Orchestrator (est.) | Opus | ~300,000 | ~255,000 | ~45,000 | ~$2.40 |
| | **GRAND TOTAL** | | **~1,585,000** | | | **~$10.37** |

With prompt caching (est. 70% of input cached at 0.1x), effective total: **~$8-9**.

---

## Cost Distribution

```
Phase 3: Domain researchers (Sonnet)  $4.29  ████████████████████  41%
Phase 5: Synthesis writers (Opus)     $2.63  █████████████          25%
Orchestrator (Opus)                   $2.40  ████████████           23%
Phase 4: Synthesis planner (Opus)     $0.89  ████                    9%
Phase 2: Lit-review planner (Opus)    $0.16  █                       2%
                                     ------
                                     $10.37                        100%
```

---

## Efficiency Analysis

### Token Yield per Paper by Domain

| Domain | Tokens | Papers | Tool Uses | Tokens/Paper |
|--------|--------|--------|-----------|--------------|
| Domain 1 (metaphilosophy) | 126,300 | 18 | 26 | 7,017 |
| Domain 2 (lit review method) | 92,335 | 6 | 50 | **15,389** |
| Domain 3 (citation ethics) | 131,694 | 18 | 53 | 7,316 |
| Domain 4 (canon formation) | 134,292 | 15 | 33 | 8,953 |
| Domain 5 (hermeneutics) | 125,663 | 12 | 26 | 10,472 |
| Domain 6 (sociology) | 138,095 | 18 | 38 | 7,672 |
| Domain 7 (research ethics) | 148,487 | 10 | 32 | **14,849** |

**Key finding**: Domain 2 consumed 92K tokens and 50 tool calls to find only 6 papers (15,389 tokens/paper) -- over 2x the cost of productive domains. The researcher kept trying different search strategies against a genuinely sparse literature.

---

## Recommendations

### Recommendation 1: Switch synthesis writers to Sonnet -- saves ~$1.05 (10%)

| | Current (Opus) | Proposed (Sonnet) | Saving |
|---|---|---|---|
| Phase 5 cost | $2.63 | ~$1.58 | **$1.05** |

**Risk**: Low. Sonnet 4.5 produces high-quality academic prose. Writers execute a detailed outline from the (Opus) synthesis planner -- the analytical decisions are already made. **Implementation**: Change `model: inherit` to `model: sonnet` in `.claude/agents/synthesis-writer.md`.

### Recommendation 2: Add early-stopping for sparse domains -- saves ~$0.30

Add guidance in `domain-literature-researcher` agent: after N unsuccessful search rounds, write BibTeX with what's found and report sparsity. **Risk**: None -- the sparsity finding is captured either way.

### Recommendation 3: Merge related domains (7 to 5) -- saves ~$1.35

For niche topics, merge closely related domains (e.g., citation ethics + canon formation; sociology + research ethics). Saves 2 researcher runs plus downstream overhead. **Risk**: Low-Moderate. Larger domains may miss niche papers.

### Recommendation 4: Run orchestrator on Sonnet -- saves ~$1.40

The orchestrator does coordination, not analysis. Sonnet can follow the detailed step-by-step skill instructions. **Risk**: Low but requires architectural change (refactor heavy work to subagent, or start session on Sonnet).

### Recommendation 5: Compress BibTeX for synthesis planner -- saves ~$0.20

Preprocess BibTeX to extract only keys, titles, authors, years, and importance. Reduces planner input by 50-70%. **Risk**: None.

### Summary

| Recommendation | Saving | Risk | Difficulty |
|---|---|---|---|
| 1. Writers to Sonnet | **$1.05** | Low | Trivial |
| 2. Sparse domain early-stop | **$0.30** | None | Low |
| 3. Merge domains (7 to 5) | **$1.35** | Low-Moderate | Medium |
| 4. Orchestrator to Sonnet | **$1.40** | Low | Medium |
| 5. Compress BibTeX for planner | **$0.20** | None | Low |
| **Total** | **$4.30** | | |

Combined savings: **~$10.37 to ~$6.07 (41% reduction)** with no expected impact on review accuracy, groundedness, or reliability.

---

## Wall-Clock Time

| Phase | Duration | Notes |
|-------|----------|-------|
| Phase 2 | 1.9 min | Sequential |
| Phase 3 | **7.8 min** | Parallel (7 agents); wall clock = slowest |
| Phase 4 | 3.2 min | Sequential |
| Phase 5 | 1.6 min | Parallel (4 agents); wall clock = slowest |
| Phase 6 | ~0.5 min | Python scripts |
| **Total** | **~15 min** | Plus orchestrator overhead |

Without parallelism, Phase 3 alone would take 43 minutes. Parallel architecture saves ~35 minutes.

---

## Content Enrichment Architecture & Token Analysis

### What Content Enrichment Is

Content enrichment is a 3-part system that augments BibTeX entries during Phase 3 (domain research) with data that helps downstream synthesis agents write better reviews:

| Component | Stage | What it adds | Script |
|-----------|-------|-------------|--------|
| **CrossRef metadata** | 5 | Corrected journal/volume/pages, entry type | `verify_paper.py` |
| **Abstract resolution** | 5.5 | `abstract` + `abstract_source` fields | `enrich_bibliography.py` -> `get_abstract.py` |
| **Encyclopedia context** | 5.6 | `sep_context` / `iep_context` fields | `get_sep_context.py`, `get_iep_context.py` |

### When & How It's Triggered

All enrichment happens **inside each domain-literature-researcher subagent** (Phase 3), running on Sonnet 4.5. The flow per domain:

```
Stages 1-4: Search & discover papers -> write initial .bib file
  |
Stage 5: CrossRef verification (verify_paper.py --doi for each paper with DOI)
  |
Stage 5.5: python enrich_bibliography.py literature-domain-N.bib
  -> For each entry without abstract:
    -> S2 API -> OpenAlex API -> CORE API (fallback chain)
    -> Found: add abstract + abstract_source fields
    -> Not found: add INCOMPLETE, no-abstract to keywords
  |
Stage 5.6: Encyclopedia context extraction
  -> For each High-importance paper matching SEP/IEP bibliography:
    -> get_sep_context.py / get_iep_context.py
    -> Add sep_context / iep_context fields
```

**Downstream impact:** The synthesis-planner (Phase 4) reads enriched BibTeX and excludes INCOMPLETE entries from the outline. The synthesis-writer (Phase 5) reads enriched BibTeX and uses abstracts for analysis, with a special rule: High-importance INCOMPLETE entries can be cited cautiously using their `note` field.

### BibTeX Content Breakdown

Measured from this review's domain files (294K chars total, ~73K tokens):

```
LLM-authored note fields (per-entry annotations)      ~50K tokens  ██████████████████
BibTeX abstract fields (from enrichment)               ~25K tokens  ██████████
Standard bibliographic fields (author, title, etc.)     ~8K tokens  ███
@comment domain overview blocks                         ~5K tokens  ██
SEP/IEP context fields                                  ~1K tokens
```

### Enrichment Token Cost: Where It Lands

Enrichment-added content (`abstract` + `sep_context`/`iep_context`) flows through three phases:

| Phase | Who reads it | Model | Enrichment tokens consumed |
|-------|-------------|-------|---------------------------|
| Phase 3 | Domain researcher writes & reads enriched .bib | Sonnet | ~25K per domain (part of 130K avg) |
| Phase 4 | Synthesis planner reads ALL .bib files | Opus | ~25K (abstracts across all domains) |
| Phase 5 | Each synthesis writer reads 1-3 .bib files | Opus | ~8-15K per writer |

**Total enrichment tokens across all phases: ~50-100K tokens**

| Pricing tier | Cost of enrichment tokens | % of total review cost |
|-------------|--------------------------|----------------------|
| Sonnet input ($3/MTok) | ~$0.15 (Phase 3 portion) | |
| Opus input ($5/MTok) | ~$0.35 (Phases 4-5 portion) | |
| **Total enrichment cost** | **~$0.50-$1.00** | **5-10%** |

### Comparison: Enriched vs. Pre-Fix Review

Compared against `reviews/nonideal-theory-justice/` which predated enrichment fixes:

| Metric | Nonideal-theory (pre-fix) | Metaphilosophy (post-fix) |
|--------|--------------------------|--------------------------|
| Domains | 7 | 7 |
| Total entries | ~114 | ~100 |
| Entries with abstract | ~85 (75%) | ~90 (90%) |
| INCOMPLETE entries | ~29-41 (25-30%) | ~10 (~10%) |
| `sep_context`/`iep_context` | Partial | Present on High-importance |
| Total .bib size | 291K chars | 294K chars |
| `literature-all.bib` | 247K chars | 288K chars |

The pre-fix review had 2-3x more INCOMPLETE entries due to missing S2 DOI lookups and unreliable SEP/IEP context extraction. File sizes are comparable because the nonideal-theory review had more entries compensating for less per-entry enrichment.

### What's Actually Expensive (and What Isn't)

**Not expensive -- enrichment itself:**
- Abstract resolution adds ~$0.50-$1.00 total (5-10% of review cost)
- The Python scripts (`enrich_bibliography.py`, `get_abstract.py`) make cheap HTTP API calls
- The LLM cost is in *reading* the enriched content, not generating it

**Actually expensive -- LLM-authored content in BibTeX:**
- `note` fields (CORE ARGUMENT + RELEVANCE + POSITION): ~50K tokens, ~42% of BibTeX content
- `@comment` blocks (DOMAIN_OVERVIEW, SYNTHESIS_GUIDANCE): ~5K tokens per domain
- These are written by the Sonnet domain researcher, not by enrichment scripts
- They're also the most valuable content for synthesis quality

**The real cost driver -- BibTeX re-reading in Phases 4-5:**
- Synthesis planner reads ALL ~73K tokens of BibTeX (74% of its 98K total tokens)
- Each synthesis writer reads 30-50K tokens of BibTeX
- This is where Recommendation 5 (compress BibTeX for planner) applies

### Enrichment Value Assessment

Abstract resolution provides high value at low cost:
- Raises abstract coverage from ~75% to ~90%
- Enables synthesis agents to write from paper content rather than note-field summaries alone
- The INCOMPLETE flagging system prevents low-confidence citations from entering the review
- Cost: ~$0.50-$1.00 per review (~5-10%)

Encyclopedia context extraction provides moderate value at negligible cost:
- Adds ~1K tokens total across all domains
- Gives synthesis agents expert framing of foundational works
- Only applies to High-importance papers found in SEP/IEP
- Cost: <$0.05 per review (<0.5%)
