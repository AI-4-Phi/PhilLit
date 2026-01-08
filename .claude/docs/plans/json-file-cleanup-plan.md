# Fix JSON File Location in Review Directories

## Problem Summary

**Issue**: Domain researchers create ~30 JSON files in review directories (`reviews/project-name/*.json`) instead of dedicated locations.

**Root Cause**: Agent instructions (`.claude/agents/domain-literature-researcher.md` lines 220-268) use bash redirects with relative paths: `> s2_results.json`. These write to the shell's working directory, which ends up being the review directory.

**Impact**: Review directories cluttered with intermediate API response files.

---

## Recommended Solution

**Move JSON files to `intermediate_files/json/` subfolder during Phase 6 cleanup**

Based on Claude Code documentation review:
- ✅ Use absolute paths (required for reliable file operations)
- ✅ Avoid `rm` command (blocked by security permissions)
- ✅ Keep files for debugging/transparency
- ✅ Maintain existing parallel execution pattern

**Pattern**:
```bash
# In agent: Use absolute output paths
REVIEW_DIR="$PWD"  # Capture at start
python script.py "query" > "$REVIEW_DIR/s2_results.json" &

# In Phase 6: Move JSON files to subfolder
mkdir -p "reviews/[project-name]/intermediate_files/json"
mv "reviews/[project-name]"/*.json "reviews/[project-name]/intermediate_files/json/" 2>/dev/null || true
```

---

## Implementation Plan

### Files to Modify

1. **`.claude/agents/domain-literature-researcher.md`** (PRIMARY)
   - Lines 220-268: Update bash redirects to use absolute paths
   - Remove `2>&1` (separates JSON from errors)
   - Add `REVIEW_DIR` variable for explicit paths

2. **`.claude/skills/literature-review/SKILL.md`** (Phase 6)
   - Add JSON file cleanup step to move files to `intermediate_files/json/`

### Detailed Changes

#### Change 1: `.claude/agents/domain-literature-researcher.md`

**Location**: Lines 220-268 (Parallel Search Mode section)

**Changes**:
1. Add `REVIEW_DIR` variable to capture absolute path
2. Remove `2>&1` from redirects (keeps JSON clean, errors visible in Bash output)
3. Use absolute paths in redirects

**Before** (line 220):
```bash
# Stage 3: Run all API searches in parallel
python .claude/skills/philosophy-research/scripts/s2_search.py "free will compatibilism" --field Philosophy --year 2015-2025 --limit 30 > s2_results.json 2>&1 &
python .claude/skills/philosophy-research/scripts/search_openalex.py "free will compatibilism" --year 2015-2025 --limit 30 > openalex_results.json 2>&1 &
python .claude/skills/philosophy-research/scripts/search_arxiv.py "moral responsibility determinism" --category cs.AI --limit 20 > arxiv_results.json 2>&1 &
wait
```

**After**:
```bash
# Capture absolute review directory path
REVIEW_DIR="$PWD"

# Stage 3: Run all API searches in parallel
python .claude/skills/philosophy-research/scripts/s2_search.py "free will compatibilism" --field Philosophy --year 2015-2025 --limit 30 > "$REVIEW_DIR/s2_results.json" &
python .claude/skills/philosophy-research/scripts/search_openalex.py "free will compatibilism" --year 2015-2025 --limit 30 > "$REVIEW_DIR/openalex_results.json" &
python .claude/skills/philosophy-research/scripts/search_arxiv.py "moral responsibility determinism" --category cs.AI --limit 20 > "$REVIEW_DIR/arxiv_results.json" &
wait
```

**Before** (line 257):
```bash
# Launch all Stage 3 searches concurrently
python .claude/skills/philosophy-research/scripts/s2_search.py "mechanistic interpretability" --field Philosophy --year 2020-2025 --limit 40 > stage3_s2.json 2>&1 &
python .claude/skills/philosophy-research/scripts/search_openalex.py "mechanistic interpretability" --year 2020-2025 --min-citations 5 --limit 40 > stage3_openalex.json 2>&1 &
python .claude/skills/philosophy-research/scripts/search_arxiv.py "interpretability neural networks" --category cs.AI --recent --limit 30 > stage3_arxiv.json 2>&1 &
python .claude/skills/philosophy-research/scripts/search_arxiv.py "explainable AI" --category cs.AI --year 2023 --limit 20 > stage3_arxiv2.json 2>&1 &
wait
```

**After**:
```bash
# Capture absolute review directory path
REVIEW_DIR="$PWD"

# Launch all Stage 3 searches concurrently
python .claude/skills/philosophy-research/scripts/s2_search.py "mechanistic interpretability" --field Philosophy --year 2020-2025 --limit 40 > "$REVIEW_DIR/stage3_s2.json" &
python .claude/skills/philosophy-research/scripts/search_openalex.py "mechanistic interpretability" --year 2020-2025 --min-citations 5 --limit 40 > "$REVIEW_DIR/stage3_openalex.json" &
python .claude/skills/philosophy-research/scripts/search_arxiv.py "interpretability neural networks" --category cs.AI --recent --limit 30 > "$REVIEW_DIR/stage3_arxiv.json" &
python .claude/skills/philosophy-research/scripts/search_arxiv.py "explainable AI" --category cs.AI --year 2023 --limit 20 > "$REVIEW_DIR/stage3_arxiv2.json" &
wait
```

#### Change 2: `.claude/skills/literature-review/SKILL.md`

**Location**: Phase 6, step 3 (around line 280)

**Before**:
```bash
mkdir -p reviews/[project-name]/intermediate_files
mv reviews/[project-name]/task-progress.md reviews/[project-name]/lit-review-plan.md reviews/[project-name]/synthesis-outline.md reviews/[project-name]/intermediate_files/
mv reviews/[project-name]/synthesis-section-*.md reviews/[project-name]/literature-domain-*.bib reviews/[project-name]/intermediate_files/
```

**After**:
```bash
mkdir -p "reviews/[project-name]/intermediate_files/json"
mv "reviews/[project-name]"/*.json "reviews/[project-name]/intermediate_files/json/" 2>/dev/null || true
mv "reviews/[project-name]/task-progress.md" "reviews/[project-name]/lit-review-plan.md" "reviews/[project-name]/synthesis-outline.md" "reviews/[project-name]/intermediate_files/"
mv "reviews/[project-name]/synthesis-section-"*.md "reviews/[project-name]/literature-domain-"*.bib "reviews/[project-name]/intermediate_files/"
```

**Note**: Add before cleanup step:
"Move JSON API response files to `intermediate_files/json/` for archival (allows debugging while keeping review directory clean)"

---

## Rationale

**Key Decisions**:

1. **Absolute paths with `$REVIEW_DIR`**
   - Reliable file operations (Claude Code requirement)
   - Agents may have different working directories than expected
   - Explicit > implicit

2. **Remove `2>&1`**
   - Keeps JSON files clean (only stdout content)
   - Errors still visible in Bash tool output (stderr goes to terminal)
   - Easier JSON parsing

3. **Move to `intermediate_files/json/` not delete**
   - Avoid `rm` (blocked by security permissions)
   - Keep files for debugging/auditing
   - Organized archival pattern

4. **Phase 6 cleanup** (not agent cleanup)
   - Single location for cleanup logic
   - Consistent with existing workflow pattern
   - Agents stay focused on search task

---

## Verification

**After implementation**:
1. Run literature review (1-2 domains)
2. During Phase 3: JSON files appear in `reviews/project-name/`
3. After Phase 6: JSON files moved to `reviews/project-name/intermediate_files/json/`
4. Review directory contains only: `.md`, `.docx`, `.bib` files + `intermediate_files/` folder

**Expected final state**:
```
reviews/project-name/
├── literature-review-final.md
├── literature-all.bib
└── intermediate_files/
    ├── json/                           # JSON files archived here
    │   ├── s2_results.json
    │   ├── openalex_results.json
    │   └── stage3_*.json
    ├── task-progress.md
    ├── lit-review-plan.md
    └── literature-domain-*.bib
```

---

## Backward Compatibility

**No breaking changes**:
- Python scripts unchanged
- Cache/rate-limit files unchanged
- BibTeX output unchanged
- Existing workflow unchanged

**Rollback**: Revert 2 files if issues arise (domain-literature-researcher.md, SKILL.md)

---

## Implementation Checklist

- [ ] `.claude/agents/domain-literature-researcher.md` (lines 220-268)
  - [ ] Add `REVIEW_DIR="$PWD"` before parallel examples
  - [ ] Change `> file.json 2>&1 &` to `> "$REVIEW_DIR/file.json" &` (2 locations)
  - [ ] Remove `2>&1` from all redirects

- [ ] `.claude/skills/literature-review/SKILL.md` (Phase 6, step 3)
  - [ ] Add `mkdir -p "reviews/[project-name]/intermediate_files/json"`
  - [ ] Add `mv "reviews/[project-name]"/*.json` line
  - [ ] Add brief note about JSON archival

- [ ] Test
  - [ ] Run 1-2 domain review
  - [ ] Verify JSON in `intermediate_files/json/` after Phase 6

- [ ] Mark TODO.md item complete
