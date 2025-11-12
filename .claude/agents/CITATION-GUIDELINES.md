# Citation Integrity Guidelines

## Critical Requirements for Literature Review Agents

This document outlines **non-negotiable** requirements for citation integrity in the research proposal orchestrator workflow.

---

## For Domain Literature Researchers

### Absolute Rules: What You Must NEVER Do

❌ **NEVER make up papers, authors, or publications**
❌ **NEVER create synthetic or fake DOIs** (e.g., "10.xxxx/placeholder")
❌ **NEVER cite papers you haven't actually found through search**
❌ **NEVER assume a paper exists without verifying it**
❌ **NEVER guess at metadata** (author names, years, titles, journals)
❌ **NEVER include a paper if you're uncertain about its existence**

### What You MUST Do

✅ **ONLY cite papers you can actually access or verify through search**
✅ **Verify every paper exists** before including it (SEP, PhilPapers, Google Scholar)
✅ **Check all metadata is correct** (author names, year, title, journal/book, publisher)
✅ **Get real DOIs from actual sources** (publisher sites, CrossRef, paper pages)
✅ **If DOI not available, write "DOI: N/A"** (never fabricate one)
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

### Good Example

```markdown
### Frankfurt (1971) Freedom of the Will and the Concept of a Person

**Citation**: Frankfurt, Harry G. (1971). Freedom of the Will and the Concept of a Person. *The Journal of Philosophy*, 68(1), 5-20.

**DOI**: 10.2307/2024717

**Type**: Journal Article

**Core Argument**: Develops hierarchical model of agency where free will requires 
identification with first-order desires through second-order volitions.

**Relevance**: Foundational compatibilist account directly relevant to our discussion 
of control and responsibility.

**Position/Debate**: Compatibilist account of free will

**Importance**: High
```

**Why this is good**:
- Paper found through Google Scholar/JSTOR
- Author name verified: Harry G. Frankfurt ✓
- Year verified: 1971 ✓
- DOI verified on JSTOR: 10.2307/2024717 ✓
- All metadata correct ✓

### Bad Example (NEVER DO THIS)

```markdown
### Smith (2019) New Perspectives on Moral Responsibility

**Citation**: Smith, J. (2019). New Perspectives on Moral Responsibility. 
*Philosophy Today*, 45(2), 123-145.

**DOI**: 10.1234/philtoday2019.45.2.123

[Rest of entry...]
```

**Why this is WRONG**:
- No evidence this paper exists ❌
- DOI looks fabricated (suspicious pattern) ❌
- Can't verify through search ❌
- Metadata looks guessed ❌

**Correct approach**: If you can't find this paper, DON'T include it.

### When You Can't Find Expected Papers

If you search for papers you expect to exist but can't find them:

1. **Do NOT fabricate them**
2. **Note the gap in your domain summary**:
   ```
   "Expected to find recent empirical work on X, but searches yielded 
   limited results. This may indicate a genuine research gap."
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

---

## For Synthesis Writers

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

**Book Example**:
```
Dennett, Daniel C. 1984. Elbow Room: The Varieties of Free Will Worth Wanting. 
Cambridge, MA: MIT Press.
```

**Journal Article Example**:
```
Frankfurt, Harry G. 1971. "Freedom of the Will and the Concept of a Person." 
The Journal of Philosophy 68 (1): 5–20. https://doi.org/10.2307/2024717.
```

**Book Chapter Example**:
```
Fischer, John Martin. 2007. "Compatibilism." In Four Views on Free Will, 
edited by John Martin Fischer, Robert Kane, Derk Pereboom, and Manuel Vargas, 
44-84. Oxford: Blackwell.
```

**Multiple Authors Example**:
```
Fischer, John Martin, and Mark Ravizza. 1998. Responsibility and Control: 
A Theory of Moral Responsibility. Cambridge: Cambridge University Press. 
https://doi.org/10.1017/CBO9780511814594.
```

### Bibliography Checklist

✅ **All in-text citations have corresponding bibliography entries**
✅ **Alphabetized by author last name**
✅ **Consistent Chicago Author-Date format**
✅ **Include DOIs when available** (as URLs)
✅ **Full author names** (not just initials when avoidable)
✅ **Italicize** book and journal titles
✅ **Use quotation marks** for article and chapter titles
✅ **Include all required elements**: author, year, title, venue, publisher/pages

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

1. **Check domain literature files**: Do DOIs look real? Can papers be verified?
2. **Check synthesis draft**: Is (Author Year) format used consistently?
3. **Check bibliography**: Is it complete? Chicago style? All citations included?
4. **Flag suspicious citations**: Anything that looks fabricated or unverifiable

### Red Flags to Watch For

🚩 DOIs with patterns like "10.xxxx/placeholder" or "10.1234/journal.year"
🚩 Papers with suspiciously generic titles
🚩 Authors you can't verify through quick search
🚩 Papers cited in synthesis but not in domain literature files
🚩 Missing bibliography or incomplete entries
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

Period. No exceptions. No "probably exists." No "seems reasonable." No synthetic DOIs.

**Only real, verifiable papers with accurate metadata.**

This is non-negotiable.

---

## Quick Reference

### Domain Researchers: Before Including Any Paper

- [ ] Found through actual search (SEP/PhilPapers/Google Scholar)
- [ ] Author name(s) verified
- [ ] Publication year verified
- [ ] Title verified (exact, not paraphrased)
- [ ] Journal/book/publisher verified
- [ ] DOI verified (or marked "N/A" if none exists)
- [ ] All metadata accurate
- [ ] Can access or verify paper exists

### Synthesis Writers: Citation Checklist

- [ ] All in-text citations use (Author Year) format
- [ ] Complete Chicago-style bibliography at end
- [ ] Every in-text citation has bibliography entry
- [ ] Bibliography alphabetized by author last name
- [ ] All required metadata included in bibliography
- [ ] DOIs included when available
- [ ] Format consistent throughout

### Orchestrators: Quality Control

- [ ] Spot-check random DOIs (do they work?)
- [ ] Verify key papers exist through search
- [ ] Check citation format consistency
- [ ] Verify bibliography completeness
- [ ] Flag any suspicious-looking citations

---

**Remember**: Your reputation and the user's research credibility depend on citation integrity. When in doubt, leave it out.