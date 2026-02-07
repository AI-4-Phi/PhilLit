# Plan: Generate Bibliography / Reference List for Final Literature Review

## Context

The final literature review (`literature-review-final.md`) contains in-text citations in Chicago Author-Date style (e.g., `(Frankfurt 1971)`, `Nyholm and Smids (2016)`) but no bibliography section. The aggregated `literature-all.bib` contains all researched works, including uncited ones. We need a `## References` section appended to the final review containing only works actually cited — formatted deterministically from verified BibTeX metadata, with zero AI involvement.

**Decision**: Python script approach (not Pandoc citeproc). No changes to synthesis-writer instructions. Intermediate markdown stays human-readable.

## Files to create/modify

### 1. New: `.claude/skills/literature-review/scripts/generate_bibliography.py`

**Matching strategy — BibTeX-driven lookup**: For each BibTeX entry, extract first author surname + year via pybtex, then search the review text for that surname appearing within 60 chars of that year.

Matching details:
- **Full surname construction**: Join `person.prelast_names + person.last_names` with spaces. Pybtex splits BibTeX names into `prelast_names` (von-part) and `last_names` separately — e.g., `Santoni de Sio, Filippo` → `prelast_names=['Santoni', 'de']`, `last_names=['Sio']`. Using only `last_names` would yield `"Sio"` instead of `"Santoni de Sio"`. The join produces the full surname: `"Santoni de Sio"`, `"De Freitas"`, etc.
- **Diacritical-normalized matching**: Before comparing the BibTeX surname against the review text, normalize both sides: apply Unicode NFKD decomposition and strip combining marks (`unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')`). This handles the review's systematic ASCII approximations — e.g., BibTeX `Hübner` matches review `Hubner`, BibTeX `Nida-Rümelin` matches review `Nida-Rumelin`. The normalized form is used **only for matching**, not for formatted output (output preserves full Unicode).
- **Word-boundary matching**: Use `\b` regex anchors around the (normalized) surname to prevent "Li" matching "liability"
- **Case-insensitive** surname matching (handles "de Freitas" vs "De Freitas"); case-sensitive year matching
- **Bidirectional search**: Check surname→year AND year→surname within the 60-char window
- **Editor fallback for matching**: If `entry.persons.get('author')` is empty, fall back to `entry.persons.get('editor')` to extract the first person's surname. This handles edited volumes like `michelfelder2022testdriving` (editors only, no authors), which the review cites as `Michelfelder and Rosenberger (2022)`.
- pybtex `@comment` entries are silently skipped (standard pybtex behavior) — this is correct since comments are domain metadata, not citable entries
- **Known limitation — same-surname ambiguity**: When multiple BibTeX entries share a first-author surname (e.g., two different authors named "Wang"), the script may match entries whose surname+year pair happens to co-occur in the text even if the entry is not actually cited. This is inherent to the BibTeX-driven approach (checking what *could be* cited, not parsing what *is* cited). The risk is low: false positives require an uncited entry whose first-author surname appears within 60 chars of its year in the review. Stderr reports all matched entries so users can spot-check.

**Text normalization before formatting** — a `clean_bibtex_str()` function applied to all `entry.fields` values **and** all author/editor name parts (`first_names`, `middle_names`, `prelast_names`, `last_names`). Pybtex stores name parts in `entry.persons`, not `entry.fields`, so both must be cleaned explicitly.

Conversion order (order matters for correctness):
1. **LaTeX diacritic→Unicode**: Convert accent-inside-braces patterns first (e.g., `Gr{\`e}ve` → `Grève`, `Jean-Fran\c{c}ois` → `Jean-François`). Reuse the `LATEX_ESCAPES` mapping from `.claude/hooks/bib_validator.py`. Must handle both braced (`{\`e}`) and unbraced (`\`e`) forms — strip the surrounding braces of the accent group before lookup.
2. **Strip remaining BibTeX braces**: `{AV}` → `AV`, `{Rawlsian}` → `Rawlsian` (after accent conversion, so `{\"o}` is already `ö` and won't be mangled)
3. **Convert `\&` → `&`**: Found in journal names (`Philosophy \& Public Affairs`) and publisher names (`Rowman \& Littlefield`) — applies to all fields, not just journals
4. **Strip `\url{...}` wrappers**: Extract the URL from `\url{https://...}` → `https://...` (found in `howpublished` fields, e.g., `sep2012computing`)

**Excluded fields**: `note` and `keywords` are never included in formatted output. These fields contain research metadata annotations (CORE ARGUMENT, RELEVANCE, POSITION), not bibliographic information.

**DOI-based deduplication**: Before formatting, deduplicate entries by DOI (case-insensitive, ignoring URL prefix variations like `https://doi.org/`). When two entries share a DOI, keep the one whose citation key appears first alphabetically. This prevents duplicate references from entries like `etienne2021dark`/`hubert2021dark` (same paper, different keys) and `gogoll2016autonomous`/`gogoll2017autonomous` (online-first vs print year). Log deduplicated entries to stderr.

**Chicago Author-Date formatting** from BibTeX fields only — never generates missing data:
- `@article`: `Surname, First. Year. "Title." *Journal* Vol (No): Pages. DOI-URL.`
- `@book`: `Surname, First. Year. *Title*. Place: Publisher.` (or `Surname, First, ed.` for edited volumes)
- `@incollection`: `Surname, First. Year. "Title." In *BookTitle*, edited by Editor, Pages. Place: Publisher.` If `booktitle` is missing but `journal` is present (mistyped entry), use `journal` as the container title with `@article`-style formatting instead.
- `@inproceedings`: `Surname, First. Year. "Title." In *BookTitle*.`
- `@phdthesis`: `Surname, First. Year. "Title." PhD diss., School.`
- `@misc` and **unknown types** (fallback): `Surname, First. Year. "Title." URL-or-howpublished.` If `howpublished` contains a URL (starts with `http`), format as a link. Never fall back to `note` or `keywords`.

Missing optional fields omitted (never fabricated). Entries sorted alphabetically by first author full surname (prelast + last), then year. DOI formatted as `https://doi.org/...` per Chicago 17th ed.

**Author formatting** (`format_author_list`):
- Single: `Surname, First.`
- Two: `Surname, First, and First2 Surname2.`
- Three to ten: `Surname, First, First2 Surname2, and First3 Surname3.` (list all)
- Eleven or more (Chicago 17th ed. §14.76): `Surname, First, First2 Surname2, First3 Surname3, First4 Surname4, First5 Surname5, First6 Surname6, First7 Surname7, et al.` (list first seven, then "et al.")
- Edited volumes (no author, only editor): append `ed.` / `eds.` after name(s)
- "Surname" throughout means the **full surname** (prelast + last), e.g., `Santoni de Sio`, `De Freitas`

**Idempotency**: If `## References` already exists (detected as `## References` at start of a line), replace everything from that heading to EOF. Only the exact heading `## References` is recognized.

**CLI**:
```bash
python .claude/skills/literature-review/scripts/generate_bibliography.py \
  "reviews/[project-name]/literature-review-final.md" \
  "reviews/[project-name]/literature-all.bib"
```

**Stderr output**: Summary of matched/unmatched counts, any warnings. Uses `errors='replace'` for Windows compatibility.

### 2. Modify: `.claude/skills/literature-review/SKILL.md` (Phase 6)

New Phase 6 step order:
1. Assemble final review (existing)
2. Deduplicate BibTeX → `literature-all.bib` (existing, moved up — **must precede** bibliography generation since the script reads this file)
3. **Generate bibliography and append to final review (NEW)**
4. Lint the final markdown (existing, moved after bibliography — the References section is now in scope for linting; verify no false positives from italicized journal names, DOI URLs, or other bibliography formatting before proceeding)
5. Clean up intermediate files (existing)
6. Report source issues (existing)
7. Optional DOCX conversion (existing — note: `--citeproc` is a no-op since the review uses prose citations, not `@key` syntax; the References section appears as plain formatted text in DOCX)

### 3. New: `tests/test_generate_bibliography.py`

Test cases:

*Matching:*
- Parenthetical citation `(Author Year)` is matched
- Narrative citation `Author (Year)` is matched
- Multi-author `(Author et al. Year)` matched via first author
- Semicolon-separated `(Author Year; Author Year)` both matched
- Uncited BibTeX entry is excluded
- Compound surnames with prelast (von-part): `Santoni de Sio` matched correctly (pybtex `prelast_names=['Santoni', 'de']` + `last_names=['Sio']` → full surname `Santoni de Sio`)
- Compound surnames without prelast: `De Freitas` matched correctly (`last_names=['De', 'Freitas']`)
- Short surnames with word boundaries: `Li` does NOT match `liability 2016`
- Same author, different years: only the cited year's entry matches
- Diacritical normalization: BibTeX `Hübner` matches review text `Hubner`; BibTeX `Nida-Rümelin` matches `Nida-Rumelin`
- Editor-only entries: `@book` with editors but no authors is matched via editor surname
- LaTeX in author names: `Gr{\`e}ve` cleaned to `Grève` before matching (then normalized to `Greve` for comparison)

*Deduplication:*
- Duplicate DOIs: two entries with the same DOI produce only one reference

*Formatting:*
- Chicago formatting correct for each entry type (@article, @book, @incollection, @inproceedings, @phdthesis, @misc)
- Unknown entry type falls back to @misc formatting
- Missing optional fields handled gracefully (no crash, no fabrication)
- Edited books use `ed.` / `eds.`
- `@incollection` with `journal` but no `booktitle` falls back gracefully
- Author count cap: 11+ authors → first 7 + "et al."
- Entries sorted alphabetically by full surname (prelast + last), then year
- `note` and `keywords` fields never appear in output

*Normalization:*
- LaTeX accent-inside-braces converted: `Gr{\`e}ve` → `Grève`, `Jean-Fran\c{c}ois` → `Jean-François`
- BibTeX braces stripped from titles: `{AV}` → `AV` (after accent conversion)
- `\&` converted to `&` in journal names and publisher names
- `\url{...}` stripped to bare URL in howpublished fields
- UTF-8 diacritics preserved in output (Müller, Lütge, Hübner)

*Idempotency:*
- Running twice doesn't duplicate the References section

### 4. No dependency changes needed

`pybtex` is already in `pyproject.toml` and checked by `setup-environment.sh`. No updates to `check_setup.py` (that's for the philosophy-research skill only). `unicodedata` (used for NFKD normalization during matching) is part of the Python standard library.

## Reliability guarantees

1. **No metadata generation** — only reads and formats existing BibTeX fields
2. **No AI involvement** — pure Python, deterministic
3. **Graceful degradation** — missing fields omitted, never guessed; mistyped entries (e.g., `@incollection` with `journal`) handled via fallback formatting
4. **Idempotent** — safe to re-run; replaces existing `## References` section
5. **Defensive normalization** — handles LaTeX remnants, braces, `\url{}`, and `\&` in all fields and name parts
6. **Diacritical-tolerant matching** — ASCII-approximated names in review text match Unicode names in BibTeX
7. **DOI deduplication** — duplicate BibTeX entries (same paper, different keys) produce a single reference

## Verification

1. Run against existing review: `python .claude/skills/literature-review/scripts/generate_bibliography.py reviews/av-trolley-ethics/literature-review-final.md reviews/av-trolley-ethics/literature-all.bib`
2. Spot-check formatted references against BibTeX source (verify author names, titles, journals, DOIs)
3. Confirm uncited BibTeX entries are excluded (literature-all.bib has ~81 entries; the review cites fewer)
4. Run `python .claude/skills/literature-review/scripts/lint_md.py reviews/av-trolley-ethics/literature-review-final.md`
5. Run `pytest tests/test_generate_bibliography.py`
6. Run full Phase 6 pipeline including DOCX conversion to verify no interaction issues

## Review assessment

### First review (REVIEW.md)

- **#1 (LaTeX in author names)**: Premise was incorrect — actual data uses Unicode, not LaTeX escapes. Added defensive normalization anyway.
- **#2 (Compound surnames)**: Valid. Fixed with `' '.join(person.last_names)` — but see second review #1 below.
- **#3 (DOCX interaction)**: Benign. Documented.
- **#4 (LaTeX in all fields)**: Partially valid — `\&` in journals needs conversion. Added `clean_bibtex_str()`.
- **#5 (Missing entry types)**: No current instances. Added `@phdthesis` and fallback to `@misc`.
- **#6 (Brace stripping)**: Valid. Added to `clean_bibtex_str()`.
- **#7 (Word-boundary matching)**: Valid. Added `\b` anchors.
- **#8 (Case sensitivity)**: Valid. Case-insensitive surname matching.
- **#9 (Idempotency)**: Valid. Specified exact replacement logic.
- **#10-14**: All addressed with documentation and minor additions.

### Second review (data-grounded)

All fixes integrated into the plan above.

- **#1 (prelast_names dropped)**: CRITICAL. `person.last_names` alone yields `"Sio"` for Santoni de Sio. Fixed: construct full surname from `prelast_names + last_names`.
- **#2 (diacritical mismatch)**: CRITICAL. Review uses `Hubner` for BibTeX `Hübner`. Fixed: NFKD normalization + strip combining marks for matching only.
- **#3 (clean_bibtex_str scope)**: CRITICAL. Pybtex stores names in `entry.persons`, not `entry.fields`. Fixed: apply cleaning to all name parts explicitly.
- **#4 (editor-only entries)**: CRITICAL. Edited volumes have no `author`. Fixed: fall back to `editor` for both matching and formatting.
- **#5 (duplicate entries)**: HIGH. Same DOI, different keys. Fixed: DOI-based deduplication before formatting.
- **#6 (`\url{}` not stripped)**: HIGH. `sep2012computing` has `\url{...}` in `howpublished`. Fixed: added to `clean_bibtex_str()`.
- **#7 (note field metadata)**: HIGH. Every entry's `note` contains CORE ARGUMENT etc. Fixed: explicitly excluded `note` and `keywords` from output.
- **#8 (@incollection with journal)**: HIGH. `otsuka2008double` is mistyped. Fixed: fall back to `journal` when `booktitle` absent.
- **#9 (`\&` in publisher)**: MEDIUM. Confirmed `clean_bibtex_str()` scope is all fields. Clarified in plan text.
- **#10 (same-surname ambiguity)**: MEDIUM. Documented as known limitation with explanation of low risk and stderr reporting.
- **#11 (author count cap)**: MEDIUM. Fixed: Chicago 17th ed. §14.76 — list up to 10 authors; 11+ → first 7 + "et al."
- **#12 (linter scope)**: MEDIUM. Bibliography now in scope for linting. Added verification note to Phase 6 step 4.
- **#13 (LaTeX accent-inside-braces)**: MEDIUM. `Gr{\`e}ve` must convert accent before stripping braces. Fixed: specified conversion order (accents → braces → `\&` → `\url{}`).
