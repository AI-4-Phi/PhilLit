# Citation Integrity Guidelines

## Critical Requirements for Literature Review Agents

This document outlines **non-negotiable** requirements for citation integrity in the research proposal orchestrator workflow.

**Output Format**: Domain researchers produce **valid BibTeX files** (`.bib`) that can be imported directly into Zotero while preserving rich metadata for synthesis agents.

---

## For Domain Literature Researchers

### Absolute Rules: What You Must NEVER Do

❌ **NEVER make up papers, authors, or publications**
❌ **NEVER create synthetic or fake DOIs** (e.g., "10.xxxx/placeholder")
❌ **NEVER cite papers you haven't actually found through search**
❌ **NEVER assume a paper exists without verifying it**
❌ **NEVER guess at metadata** (author names, years, titles, journals)
❌ **NEVER include a paper if you're uncertain about its existence**
❌ **NEVER produce invalid BibTeX syntax**

### What You MUST Do

✅ **ONLY cite papers you can actually access or verify through search**
✅ **Verify every paper exists** before including it (SEP, PhilPapers, Google Scholar)
✅ **Check all metadata is correct** (author names, year, title, journal/book, publisher)
✅ **Get real DOIs from actual sources** (publisher sites, CrossRef, paper pages)
✅ **If DOI not available, omit the doi field** (never fabricate one)
✅ **Produce valid BibTeX syntax** that Zotero can import without errors
✅ **When in doubt, leave it out** (omit uncertain papers)

### Verification Workflow

**Before including ANY paper in your literature file:**

1. **Search**: Find through actual web search (SEP, PhilPapers, Google Scholar)
2. **Verify existence**: Confirm paper exists with correct metadata
3. **Check author(s)**: Verify spelling and initials
4. **Check year**: Confirm publication year
5. **Check title**: Get exact title (don't paraphrase)
6. **Check venue**: Verify journal/book name and publisher
7. **Get DOI**: Look on actual paper page, publisher site, or CrossRef
   - If no DOI exists, write "DOI: N/A"
   - NEVER create a placeholder or synthetic DOI
8. **Include**: Only if steps 1-7 successful

### Good Example (BibTeX Format)

```bibtex
@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971},
  volume = {68},
  number = {1},
  pages = {5--20},
  doi = {10.2307/2024717},
  note = {CORE ARGUMENT: Develops hierarchical model of agency where free will requires identification with first-order desires through second-order volitions. Agents are free when they have second-order desires about which first-order desires to act upon. RELEVANCE: Foundational compatibilist account directly relevant to our discussion of control and responsibility. Framework leaves open how neuroscientific findings affect identification judgments. POSITION: Compatibilist account of free will and moral responsibility (hierarchical mesh theory).},
  keywords = {compatibilism, free-will, hierarchical-agency, High}
}
```

**Why this is good**:
- Valid BibTeX syntax ✓
- Paper found through Google Scholar/JSTOR ✓
- Author name verified: Harry G. Frankfurt ✓
- Year verified: 1971 ✓
- DOI verified on JSTOR: 10.2307/2024717 ✓
- All metadata correct ✓
- Note field contains analysis for synthesis agents ✓
- Keywords include importance level (High) ✓
- Can be imported directly to Zotero ✓

### Bad Example (NEVER DO THIS)

```bibtex
@article{smith2019perspectives,
  author = {Smith, J.},
  title = {New Perspectives on Moral Responsibility},
  journal = {Philosophy Today},
  year = {2019},
  volume = {45},
  number = {2},
  pages = {123--145},
  doi = {10.1234/philtoday2019.45.2.123},
  note = {CORE ARGUMENT: [...] RELEVANCE: [...] POSITION: [...]},
  keywords = {moral-responsibility, High}
}
```

**Why this is WRONG**:
- No evidence this paper exists ❌
- DOI looks fabricated (suspicious pattern) ❌
- Can't verify through search ❌
- Metadata looks guessed ❌
- Would import fake citation into Zotero ❌

**Correct approach**: If you can't find this paper, DON'T include it.

### When You Can't Find Expected Papers

If you search for papers you expect to exist but can't find them:

1. **Do NOT fabricate them**
2. **Note the gap in your domain's @comment entry**:
   ```bibtex
   @comment{
   NOTABLE_GAPS:
   Expected to find recent empirical work on X, but searches yielded 
   limited results. This may indicate a genuine research gap.
   }
   ```
3. **Suggest alternative search strategies** to orchestrator
4. **Try broader search terms** or related topics
5. **If still nothing, report it as a gap** (this is valuable information!)

### Red Flags (Signs You Might Be Making It Up)

🚩 You can't remember where you found a paper
🚩 You're "pretty sure" someone wrote something but can't find it
🚩 You're filling in metadata from memory
🚩 The DOI doesn't work when you check it
🚩 You can't find the paper on Google Scholar
🚩 You're creating DOIs that "look right"
🚩 You're guessing at publication years or journals

**If any of these apply: STOP. Do not include the paper.**

### BibTeX Format Requirements

**Critical**: Your output must be **valid BibTeX syntax**

✅ **Valid BibTeX requirements**:
- Proper entry types (@article, @book, @incollection, etc.)
- All required fields present (author, title, year, etc.)
- Proper escaping of special characters
- Valid citation keys (e.g., `frankfurt1971freedom`)
- Proper comma placement and bracing
- @comment entries for domain metadata

❌ **Common BibTeX errors to avoid**:
- Missing commas between fields
- Unescaped special characters (use LaTeX escaping)
- Invalid entry types
- Missing required fields
- Mismatched braces
- Invalid citation key format

**Test your output**: 
- Validate BibTeX syntax before submitting
- Ensure Zotero can import without errors
- Check that @comment entries preserve metadata for agents

---

## For Synthesis Writers

### Reading BibTeX Files

When synthesis-writer agents receive BibTeX files:

1. **Parse @comment entries** for domain-level metadata:
   - DOMAIN_OVERVIEW
   - RELEVANCE_TO_PROJECT
   - NOTABLE_GAPS
   - SYNTHESIS_GUIDANCE
   - KEY_POSITIONS

2. **Parse BibTeX entries** for individual papers:
   - Standard fields: author, title, journal, year, etc.
   - `note` field: Contains CORE ARGUMENT, RELEVANCE, POSITION
   - `keywords` field: Contains topic tags and importance (High/Medium/Low)

3. **Extract citation information**:
   - Author names from `author` field
   - Year from `year` field
   - Title from `title` field
   - Journal/publisher from appropriate fields
   - DOI from `doi` field (if present)

### Citation Format Requirements

**In-text citations**: Use (Author Year) format throughout

**Examples**:
- Single author: (Frankfurt 1971)
- Two authors: (Fischer and Ravizza 1998)
- Three or more: (Smith et al. 2020)
- Multiple works: (Frankfurt 1971; Dennett 1984; Fischer and Ravizza 1998)
- With page numbers: (Fischer and Ravizza 1998, 31-45)

**NOT acceptable**:
- ❌ (Frankfurt, 1971) - no comma before year
- ❌ [1] - not numbered citations
- ❌ (Fischer & Ravizza 1998) - use "and" not "&" in narrative
- ❌ Frankfurt (1971, p. 45) - page reference format wrong

### Bibliography Format: Chicago Author-Date Style

**Required at end of paper**: Complete bibliography in Chicago Manual of Style (Author-Date system)
**Bibliography format**: Chicago Manual of Style (Author-Date system)

**Build bibliography from BibTeX data**:
- Extract author, title, year, journal, etc. from BibTeX fields
- Format according to Chicago Author-Date style
- Include DOI URLs when present in BibTeX

**Book Example** (from BibTeX):
```bibtex
@book{dennett1984elbow,
  author = {Dennett, Daniel C.},
  title = {Elbow Room: The Varieties of Free Will Worth Wanting},
  publisher = {MIT Press},
  address = {Cambridge, MA},
  year = {1984}
}
```
→ Formatted as: Dennett, Daniel C. 1984. *Elbow Room: The Varieties of Free Will Worth Wanting*. Cambridge, MA: MIT Press.

**Journal Article Example** (from BibTeX):
```bibtex
@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  title = {Freedom of the Will and the Concept of a Person},
  journal = {The Journal of Philosophy},
  year = {1971},
  volume = {68},
  number = {1},
  pages = {5--20},
  doi = {10.2307/2024717}
}
```
→ Formatted as: Frankfurt, Harry G. 1971. "Freedom of the Will and the Concept of a Person." *The Journal of Philosophy* 68 (1): 5–20. https://doi.org/10.2307/2024717.

### Bibliography Checklist

✅ **All in-text citations have corresponding bibliography entries**
✅ **Built from BibTeX data** (extract from provided `.bib` files)
✅ **Alphabetized by author last name**
✅ **Consistent Chicago Author-Date format**
✅ **Include DOIs when present in BibTeX** (as URLs)
✅ **Full author names** (extracted from BibTeX author field)
✅ **Italicize** book and journal titles
✅ **Use quotation marks** for article and chapter titles
✅ **Include all required elements**: author, year, title, venue, publisher/pages (from BibTeX fields)

### Integration Best Practices

**Good integration** (analyze, don't just cite):
```
Fischer and Ravizza (1998) argue that moral responsibility requires 
guidance control—the ability to regulate behavior through reasons-responsive 
mechanisms. Unlike libertarian accounts, their view does not require 
alternative possibilities; what matters is whether the actual mechanism 
responds appropriately to reasons. This framework has been influential 
but faces the challenge of operationalizing "reasons-responsiveness" 
in empirically testable ways.
```

**Poor integration** (just listing):
```
Many philosophers discuss free will (Frankfurt 1971; Dennett 1984; 
Fischer and Ravizza 1998; Nelkin 2011; Vargas 2013).
```

---

## For Orchestrators

### Monitoring Citation Integrity

When reviewing outputs:

1. **Check domain BibTeX files**: 
   - Valid BibTeX syntax? Can Zotero import them?
   - Do DOIs look real? Can papers be verified?
   - Are @comment entries present with domain metadata?
   - Are note fields populated with analysis?
2. **Check synthesis draft**: Is (Author Year) format used consistently?
3. **Check bibliography**: Is it complete? Chicago style? All citations included?
4. **Flag suspicious citations**: Anything that looks fabricated or unverifiable
5. **Test Zotero import**: Can BibTeX files be imported without errors?

### Red Flags to Watch For

🚩 DOIs with patterns like "10.xxxx/placeholder" or "10.1234/journal.year"
🚩 Papers with suspiciously generic titles
🚩 Authors you can't verify through quick search
🚩 Papers cited in synthesis but not in domain BibTeX files
🚩 Invalid BibTeX syntax (won't import to Zotero)
🚩 Missing @comment entries in BibTeX files
🚩 Empty or missing note fields in BibTeX entries
🚩 Missing bibliography or incomplete entries in synthesis
🚩 Inconsistent citation formats

---

## Why This Matters

### Academic Integrity

- Fabricated citations are **academic misconduct**
- They undermine the credibility of the entire review
- They can't be verified by reviewers or readers
- They constitute plagiarism/fraud if used in actual proposals

### Practical Consequences

- Grant reviewers **will check citations** for key claims
- Invalid DOIs are immediately obvious and raise red flags
- Made-up papers can derail entire grant applications
- Loss of credibility for researcher and research program

### Professional Standards

- Philosophy takes citation accuracy very seriously
- Synthetic data in literature reviews is unethical
- AI systems must maintain higher standards, not lower
- We build systems to **augment** human research, not deceive

---

## Summary: The Golden Rule

**If you can't verify it exists through actual search, DON'T cite it.**

Period. No exceptions. No "probably exists." No "seems reasonable." No synthetic DOIs. No invalid BibTeX.

**Only real, verifiable papers with accurate metadata in valid BibTeX format.**

This is non-negotiable.

---

## Quick Reference

### Domain Researchers: Before Including Any Paper in BibTeX File

- [ ] Found through actual search (SEP/PhilPapers/Google Scholar)
- [ ] Author name(s) verified
- [ ] Publication year verified
- [ ] Title verified (exact, not paraphrased)
- [ ] Journal/book/publisher verified
- [ ] DOI verified (or omit doi field if none exists)
- [ ] All metadata accurate
- [ ] Can access or verify paper exists
- [ ] Valid BibTeX syntax (proper entry type, required fields, citation key)
- [ ] Note field populated with CORE ARGUMENT, RELEVANCE, POSITION
- [ ] Keywords field includes importance level (High/Medium/Low)
- [ ] Domain @comment entry includes overview and synthesis guidance
- [ ] BibTeX file can be imported to Zotero without errors

### Synthesis Writers: Citation Checklist

- [ ] Read BibTeX files (@comment for overview, entries for papers)
- [ ] Extract citation data from BibTeX fields (author, year, title, etc.)
- [ ] All in-text citations use (Author Year) format
- [ ] Complete Chicago-style bibliography at end
- [ ] Bibliography built from BibTeX data
- [ ] Every in-text citation has bibliography entry
- [ ] Bibliography alphabetized by author last name
- [ ] All required metadata included in bibliography
- [ ] DOIs included when present in BibTeX
- [ ] Format consistent throughout

### Orchestrators: Quality Control

- [ ] Test BibTeX files (can Zotero import them?)
- [ ] Validate BibTeX syntax (proper format, required fields)
- [ ] Check @comment entries present in each domain file
- [ ] Spot-check random DOIs (do they work?)
- [ ] Verify key papers exist through search
- [ ] Check citation format consistency in synthesis
- [ ] Verify bibliography completeness in synthesis
- [ ] Flag any suspicious-looking citations
- [ ] Confirm note fields populated in BibTeX entries

---

**Remember**: Your reputation and the user's research credibility depend on citation integrity. When in doubt, leave it out. All BibTeX files must be valid and importable to Zotero.