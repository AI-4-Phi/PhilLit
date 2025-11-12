# BibTeX Format Integration

## Overview

Domain literature researchers output **valid BibTeX files** (`.bib`) that serve dual purposes:
1. **Direct Zotero import** - Users can import bibliographies with one click
2. **Agent-readable metadata** - Synthesis agents read rich metadata for planning and writing

This document explains the BibTeX format structure and how it's used throughout the workflow.

---

## Why BibTeX?

### Benefits

✅ **Standardized format** - Industry-standard bibliography format recognized by all reference managers
✅ **Direct import** - Users can import into Zotero, Mendeley, EndNote, etc. without conversion
✅ **No information loss** - All metadata preserved in standard fields
✅ **Agent-readable** - Synthesis agents parse BibTeX for planning and writing
✅ **Professional output** - Users get reference-manager-ready bibliographies
✅ **Tool integration** - Works with LaTeX, Pandoc, and other academic writing tools

### Replaces Previous Format

**Before**: Markdown files with structured entries
- Required manual import to reference managers
- Not machine-readable by standard tools
- Custom format only agents could read

**After**: BibTeX files with structured entries
- Zotero imports automatically
- Standard format all tools recognize
- Agents read same files users import

---

## BibTeX File Structure

Each domain file (e.g., `literature-domain-compatibilism.bib`) contains:

### 1. Domain Metadata (@comment entry)

**Purpose**: Preserve domain-level information that Zotero ignores but agents read

**Location**: Top of file in `@comment{}` block

**Contains**:
- Domain name and search metadata
- Domain overview (main debates, positions)
- Relevance to research project
- Recent developments
- Notable gaps
- Synthesis guidance
- Key positions summary

**Example**:
```bibtex
@comment{
====================================================================
DOMAIN: Compatibilist Theories of Moral Responsibility
SEARCH_DATE: 2024-01-15
PAPERS_FOUND: 14 (High: 6, Medium: 5, Low: 3)
SEARCH_SOURCES: SEP, PhilPapers, Google Scholar
====================================================================

DOMAIN_OVERVIEW:
The compatibilist tradition argues that moral responsibility is compatible 
with causal determinism. Key debates center on what conditions are necessary 
and sufficient for responsibility. Hierarchical mesh theories (Frankfurt 1971) 
focus on identification with desires, while reasons-responsiveness accounts 
(Fischer & Ravizza 1998) emphasize the quality of the mechanism producing action.

RELEVANCE_TO_PROJECT:
These theories provide sophisticated philosophical frameworks for moral 
responsibility that our research aims to operationalize in neuroscientific terms.

RECENT_DEVELOPMENTS:
Last decade has seen increased interest in empirical grounding of compatibilist 
concepts, with philosophers engaging neuroscience more directly.

NOTABLE_GAPS:
Limited work on empirical operationalization of "reasons-responsiveness." 
Few studies test whether neural mechanisms meet philosophical criteria.

SYNTHESIS_GUIDANCE:
Focus on Fischer & Ravizza (1998) and Nelkin (2011) as core frameworks. 
The tension between conceptual sophistication and empirical testability 
should be central to the review.

KEY_POSITIONS:
- Hierarchical mesh theories: 3 papers - Frankfurt's identification model
- Reasons-responsiveness: 5 papers - Fischer & Ravizza tradition
- Rational abilities: 2 papers - Nelkin's capacities approach
- Empirical compatibilism: 4 papers - Vargas, Nahmias integration work
====================================================================
}
```

**Why @comment**:
- Zotero and most reference managers completely ignore `@comment` entries
- Agents can parse and read them for domain context
- Clean separation between user-facing bibliography and agent metadata

### 2. BibTeX Entries (Individual Papers)

**Purpose**: Standard bibliography entries that Zotero imports AND agents read

**Entry types**:
- `@article` - Journal articles
- `@book` - Books
- `@incollection` - Book chapters
- `@inproceedings` - Conference papers
- `@phdthesis` - Dissertations
- `@misc` - Online resources, SEP entries

**Standard fields** (for Zotero):
- `author` - Author name(s)
- `title` - Paper/book title
- `journal` or `booktitle` - Venue
- `year` - Publication year
- `volume`, `number`, `pages` - Volume/issue/page info
- `publisher`, `address` - Publisher info
- `doi` - Digital Object Identifier

**Rich metadata fields** (for agents):
- `note` - Contains CORE ARGUMENT, RELEVANCE, POSITION analysis
- `keywords` - Contains topic tags and importance level (High/Medium/Low)

**Example**:
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
  note = {CORE ARGUMENT: Develops hierarchical model of agency where free will requires identification with first-order desires through second-order volitions. Agents are free when they have second-order desires about which first-order desires to act upon, and these align to form a "mesh." Argues this mesh is sufficient for moral responsibility even in a deterministic universe. RELEVANCE: Foundational compatibilist account directly relevant to our discussion of control and responsibility. Framework is philosophically sophisticated but leaves open how neuroscientific findings about unconscious processes affect judgments about identification and mesh formation, which is precisely the gap our research addresses. POSITION: Compatibilist account of free will and moral responsibility (hierarchical mesh theory).},
  keywords = {compatibilism, free-will, hierarchical-agency, identification, High}
}

@book{fischerravizza1998responsibility,
  author = {Fischer, John Martin and Ravizza, Mark},
  title = {Responsibility and Control: A Theory of Moral Responsibility},
  publisher = {Cambridge University Press},
  address = {Cambridge},
  year = {1998},
  doi = {10.1017/CBO9780511814594},
  note = {CORE ARGUMENT: Develops comprehensive account of moral responsibility based on "guidance control" rather than regulative control. Argues agents are responsible when actions flow from their own reasons-responsive mechanism, where mechanism must be both receptive to reasons and reactive to them. Does not require alternative possibilities. RELEVANCE: Provides sophisticated compatibilist framework with detailed criteria for responsibility-grounding control. Their concept of "reasons-responsiveness" is central to contemporary debates but remains operationally vague for empirical testing. Our research operationalizes this concept using neuroimaging measures. POSITION: Compatibilist reasons-responsiveness account of moral responsibility.},
  keywords = {compatibilism, moral-responsibility, reasons-responsiveness, guidance-control, High}
}
```

---

## Note Field Structure

**Format**: Structured text with three required components

```
CORE ARGUMENT: [2-3 sentences explaining what the paper argues/claims]

RELEVANCE: [2-3 sentences on how this connects to research project and what gaps it addresses]

POSITION: [1 sentence identifying theoretical position or debate]
```

**Purpose**:
- **For Zotero users**: Notes field imported with paper for reference
- **For synthesis-planner**: Understands paper's argument and relevance without reading full paper
- **For synthesis-writer**: Knows what to emphasize when citing the paper

**Example**:
```
note = {CORE ARGUMENT: Develops hierarchical model of agency where free will requires identification with first-order desires through second-order volitions. Creates distinction between wanting something and wanting to want it. RELEVANCE: Foundational compatibilist account directly relevant to our discussion of control. Framework leaves open how neuroscientific findings affect identification judgments. POSITION: Compatibilist account of free will (hierarchical mesh theory).}
```

---

## Keywords Field Structure

**Format**: Comma-separated tags ending with importance level

```
keywords = {topic-tag-1, topic-tag-2, position-tag, Importance-Level}
```

**Importance levels**:
- `High` - Core paper, must cite in review
- `Medium` - Important for context, should probably cite
- `Low` - Relevant but peripheral, cite if space permits

**Purpose**:
- **For Zotero users**: Tags/keywords for organizing library
- **For synthesis-planner**: Quick filtering by importance
- **For synthesis-writer**: Prioritization guidance

**Example**:
```
keywords = {compatibilism, free-will, hierarchical-agency, High}
```

---

## Citation Keys

**Format**: `authorYYYYkeyword`

**Guidelines**:
- Lowercase throughout
- No spaces or special characters
- Author last name (or first author if multiple)
- Four-digit year
- Distinctive keyword from title

**Examples**:
- `frankfurt1971freedom` - Frankfurt (1971) "Freedom of the Will..."
- `fischerravizza1998responsibility` - Fischer & Ravizza (1998) "Responsibility and Control"
- `nelkin2011rational` - Nelkin (2011) on rational abilities

**Purpose**:
- **For BibTeX**: Unique identifier for each entry
- **For synthesis-planner**: Can reference papers by key in outline
- **For synthesis-writer**: Internal reference (though cites as "Author Year" in prose)

---

## How Agents Read BibTeX Files

### Synthesis-Planner

**Reads**:
1. **@comment entry** - Gets domain overview, gaps, synthesis guidance
2. **All BibTeX entries** - Parses note fields for arguments and relevance
3. **Keywords fields** - Filters by importance (High/Medium/Low)

**Uses this to**:
- Understand landscape of each domain
- Identify key papers for each section
- Organize narrative structure
- Plan gap analysis

**Output**: Synthesis outline referencing papers by citation key or author-year

### Synthesis-Writer

**Reads**:
1. **@comment entry** - Domain context for section being written
2. **Relevant BibTeX entries** - Only papers needed for current section
3. **Note fields** - Gets arguments, relevance, position for citing
4. **Standard fields** - Gets author, year, title, journal for bibliography

**Uses this to**:
- Cite papers in (Author Year) format in prose
- Explain arguments using note field content
- Connect to project using relevance information
- Build Chicago-style bibliography from BibTeX fields

**Output**: Section markdown with in-text citations and bibliography

---

## User Workflow: Zotero Import

### Step 1: Receive BibTeX Files

After Phase 2 completes, user has:
```
literature-domain-1.bib
literature-domain-2.bib
literature-domain-3.bib
literature-domain-4.bib
literature-domain-5.bib
```

### Step 2: Import to Zotero

**Option A: Drag and drop**
1. Open Zotero
2. Drag `.bib` file onto Zotero collection
3. Papers imported with full metadata

**Option B: File import**
1. Zotero → File → Import
2. Select `.bib` file
3. Papers imported

**Option C: Merge all first**
```bash
cat literature-domain-*.bib > all-literature.bib
```
Then import `all-literature.bib`

### Step 3: Verify Import

Zotero imports:
- ✅ Author names
- ✅ Title
- ✅ Journal/book/publisher
- ✅ Year
- ✅ Volume, issue, pages
- ✅ DOI (clickable link)
- ✅ Note field (with CORE ARGUMENT, RELEVANCE, POSITION)
- ✅ Keywords/tags

Zotero ignores:
- ❌ @comment entries (domain metadata)

**Result**: Complete reference library ready for citing in papers

---

## Validation Requirements

### For Domain Researchers

**Must produce valid BibTeX**:
- ✅ Proper entry types (@article, @book, etc.)
- ✅ All required fields present
- ✅ Valid citation keys
- ✅ Proper comma placement
- ✅ Special characters escaped (LaTeX format)
- ✅ Matching braces
- ✅ Can be parsed by BibTeX tools
- ✅ Can be imported by Zotero without errors

**Test before submitting**:
```bash
# Validate BibTeX syntax
bibtex --validate literature-domain-1.bib

# Or attempt Zotero import
# File → Import → Select file → Check for errors
```

### Common Errors to Avoid

❌ **Missing commas between fields**
```bibtex
@article{key,
  author = {Name}  # Missing comma!
  title = {Title}
}
```

✅ **Correct**:
```bibtex
@article{key,
  author = {Name},
  title = {Title}
}
```

❌ **Unescaped special characters**
```bibtex
title = {Gödel's Theorem}  # Wrong!
```

✅ **Correct**:
```bibtex
title = {G{\"o}del's Theorem}
```

❌ **Invalid entry type**
```bibtex
@journalarticle{key,  # Not a valid type!
```

✅ **Correct**:
```bibtex
@article{key,  # Valid type
```

---

## Integration with Synthesis Draft

### How Citations Flow

1. **Domain researcher** creates BibTeX entry:
```bibtex
@article{frankfurt1971freedom,
  author = {Frankfurt, Harry G.},
  year = {1971},
  ...
}
```

2. **Synthesis-planner** references in outline:
```markdown
**Papers**: frankfurt1971freedom, dennett1984elbow
```

3. **Synthesis-writer** cites in prose:
```markdown
Frankfurt (1971) argues that free will requires identification...
```

4. **Synthesis-writer** builds bibliography from BibTeX:
```markdown
## References

Frankfurt, Harry G. 1971. "Freedom of the Will and the Concept of a Person." 
*The Journal of Philosophy* 68 (1): 5–20. https://doi.org/10.2307/2024717.
```

5. **User** imports BibTeX to Zotero for their own work

**Result**: Seamless flow from search → planning → writing → reference management

---

## Special Characters and Escaping

### LaTeX Escaping in BibTeX

BibTeX uses LaTeX escaping for special characters:

| Character | BibTeX Format | Example |
|-----------|---------------|---------|
| ä | `{\"a}` | `G{\"o}del` |
| ö | `{\"o}` | `Schr{\"o}dinger` |
| ü | `{\"u}` | `M{\"u}ller` |
| é | `{\'e}` | `Poincar{\'e}` |
| è | `{\`e}` | `Descartes` |
| ñ | `{\~n}` | `Espa{\~n}a` |
| — | `---` | `pages = {5--20}` |

**Example**:
```bibtex
@article{muller2015consciousness,
  author = {M{\"u}ller, Thomas and Esfeld, Michael},
  title = {Temporal Experience and the Specious Present},
  ...
}
```

### When to Escape

✅ **Always escape**:
- Diacritical marks (ä, ö, ü, é, è, ñ, etc.)
- Special symbols in author names
- Em dashes in page ranges (use `--`)

❌ **Don't escape**:
- Regular ASCII characters
- Apostrophes in English titles
- Quotation marks (use BibTeX style)

---

## Benefits Summary

### For Users

1. **Direct Zotero import** - No manual entry, no conversion needed
2. **Complete metadata** - All citation information preserved
3. **Notes included** - Paper summaries imported for reference
4. **Keywords/tags** - Organized library with searchable tags
5. **DOI links** - Clickable links to papers
6. **Standard format** - Works with all reference managers

### For Synthesis Agents

1. **Domain context** - @comment entries provide overview
2. **Rich metadata** - Note fields have arguments and relevance
3. **Importance filtering** - Keywords show priority papers
4. **Standard parsing** - BibTeX is well-documented format
5. **Citation data** - All fields needed for Chicago-style bibliography
6. **Efficient reading** - Structured format, easy to parse

### For Workflow

1. **No information loss** - Everything preserved in BibTeX
2. **Dual-purpose output** - Serves users AND agents
3. **Professional standard** - Industry-recognized format
4. **Tool compatibility** - Works with LaTeX, Pandoc, etc.
5. **Quality signal** - Valid BibTeX indicates thorough work
6. **Future-proof** - BibTeX has 40+ years of stability

---

## Troubleshooting

### Zotero Won't Import File

**Check**:
1. Valid BibTeX syntax (missing commas, braces?)
2. All required fields present for entry type
3. Special characters properly escaped
4. File encoding (should be UTF-8)
5. No invalid entry types

**Fix**:
```bash
# Validate syntax
bibtex --validate file.bib

# Check encoding
file -i file.bib  # Should show UTF-8
```

### @comment Entries Showing in Zotero

**This shouldn't happen** - Zotero ignores @comment

**If it does**:
- Check @comment syntax (should be `@comment{...}`)
- Ensure not using a different entry type

### Note Fields Not Importing

**Check**:
- Zotero preferences → Import → "Include notes"
- Note field format (should be plain text)
- Field not too long (rare Zotero limitation)

### Keywords Not Showing as Tags

**Check**:
- Zotero preferences → Import → "Include automatic tags"
- Keywords field format (comma-separated)
- Tag not too long

---

## Example Complete Domain File

See `domain-literature-researcher.md` for full example with:
- Complete @comment entry with all required sections
- Multiple BibTeX entries of different types
- Proper note field structure
- Proper keywords field format
- Valid syntax throughout

---

## Conclusion

BibTeX format integration provides:
- **For users**: Professional bibliography files ready for Zotero import
- **For agents**: Rich metadata for intelligent synthesis
- **For workflow**: No information loss, dual-purpose output
- **For quality**: Standard format enforces completeness

This is a **key architectural decision** that makes the orchestrator's output immediately useful while preserving all metadata needed for automated synthesis.