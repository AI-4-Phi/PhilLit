# Test Coverage Audit — March 2026

**Date:** 2026-03-07
**Scope:** All files under `tests/`, `.claude/skills/`, `.claude/hooks/`
**Status:** Audit complete. Fixes not yet applied.

This document is a handover for a fresh session to implement the recommended fixes.

---

## What Was Audited

The test suite comprises 27 test files covering scripts in three areas:

- `.claude/skills/philosophy-research/scripts/` — API search scripts, abstract resolution, caching, rate limiting
- `.claude/skills/literature-review/scripts/` — Assembly, bibliography generation, deduplication, enrichment, linting
- `.claude/hooks/` — BibTeX validation, metadata validation, metadata cleaning

---

## Coverage Map

### Well-Covered (dedicated, thorough tests)

| Script | Test File |
|--------|-----------|
| `hooks/bib_validator.py` | `test_bib_validator.py` |
| `hooks/metadata_validator.py` | `test_metadata_validator.py` |
| `hooks/metadata_cleaner.py` | `test_metadata_cleaner.py` |
| `literature-review/dedupe_bib.py` | `test_dedupe_bib.py` |
| `literature-review/assemble_review.py` | `test_assemble_review.py` |
| `literature-review/generate_bibliography.py` | `test_generate_bibliography.py` |
| `literature-review/enrich_bibliography.py` | `test_enrich_bibliography.py` + `test_enrich_ndpr.py` |
| `literature-review/normalize_headings.py` | `test_normalize_headings.py` |
| `literature-review/lint_md.py` | `test_lint_md.py` |
| `philosophy-research/s2_search.py` | `test_s2_search.py` |
| `philosophy-research/search_openalex.py` | `test_search_openalex.py` |
| `philosophy-research/search_core.py` | `test_search_core.py` |
| `philosophy-research/search_iep.py` | `test_search_iep.py` (via `brave_search.py`) |
| `philosophy-research/search_cache.py` | `test_search_cache.py` |
| `philosophy-research/rate_limiter.py` | `test_rate_limiter.py` |
| `philosophy-research/verify_paper.py` | `test_verify_paper.py` |
| `philosophy-research/get_abstract.py` | `test_get_abstract.py` |
| `philosophy-research/fetch_iep.py` | `test_fetch_iep.py` |
| `philosophy-research/fetch_ndpr.py` | `test_fetch_ndpr.py` |
| `philosophy-research/search_ndpr.py` | `test_search_ndpr.py` |
| `philosophy-research/get_sep_context.py` | `test_get_sep_context.py` |
| `philosophy-research/get_iep_context.py` | `test_get_iep_context.py` |
| `philosophy-research/citation_context.py` | `test_citation_context.py` |

### Partially Covered (schema compliance only, no logic tests)

These scripts appear in `test_output_schemas.py` which tests that `output_success` and `output_error` produce valid JSON schemas. No logic, parsing, or API integration tests exist for them.

| Script | Gap |
|--------|-----|
| `philosophy-research/search_arxiv.py` | No logic tests |
| `philosophy-research/search_sep.py` | No logic tests |
| `philosophy-research/search_philpapers.py` | No logic tests |
| `philosophy-research/s2_batch.py` | No logic tests |
| `philosophy-research/s2_citations.py` | No logic tests |
| `philosophy-research/s2_recommend.py` | No logic tests |

### Not Covered

| Script | Risk | Notes |
|--------|------|-------|
| `philosophy-research/fetch_sep.py` | **High** | Fetches and parses SEP articles with caching. Same complexity as `fetch_iep.py`, which has thorough tests. No test file exists. |
| `hooks/validate_bib_write.py` | Medium | PreToolUse hook that validates BibTeX before writes. No direct tests. |
| `hooks/block_background_bash.py` | Low | Simple hook blocking background bash. No tests. |
| `philosophy-research/output.py` | Low | Shared output formatting utility. Tested indirectly via all script tests. |
| `philosophy-research/s2_formatters.py` | Low | S2 result formatting helpers. Tested indirectly. |
| `philosophy-research/check_setup.py` | Low | Interactive setup checker. No tests needed. |

---

## Issues Found

### Issue 1 — Silent-passing tests in `test_output_schemas.py` [HIGH]

**File:** `tests/test_output_schemas.py`
**Lines:** `test_success_output_has_required_fields`, `test_error_output_fields`, `test_count_matches_results_length`, `test_error_field_structure`

All four parametrized test methods guard their assertions with `if output:`:

```python
if output:
    errors = validate_output_schema(output, "success")
    assert errors == [], f"{module_name}: {errors}"
    assert output["source"] == expected_source
```

If `output_success` doesn't exist on the module, or the call raises before `capture_print` is invoked, `output` stays `None` and the assertion is silently skipped — the test **passes** without checking anything.

This affects the six partially-covered scripts above. Their schema compliance is untested despite appearing to be tested.

**Fix:** Replace `if output:` with `assert output is not None, f"{module_name}: no output captured"` before the schema validation.

---

### Issue 2 — ~200 lines of duplicated test logic [MEDIUM]

**Files:** `tests/test_get_sep_context.py`, `tests/test_get_iep_context.py`

Both SEP and IEP context scripts delegate to the shared `citation_context.py` module. The test files are ~95% identical: `TestCitationPatterns`, `TestContextExtraction`, `TestClaimExtraction`, and `TestFindCitations` test the exact same underlying functions, just imported through different module names.

`test_citation_context.py` already covers the shared layer directly.

The duplicated tests add maintenance burden without adding coverage. Each file should keep only:
- `TestOutputSchema` (different `source` field: `sep_context` vs `iep_context`)
- `TestProgressOutput` (different script name in brackets)
- `TestCLI` (different help text)

The shared citation logic tests (`TestCitationPatterns`, `TestContextExtraction`, `TestClaimExtraction`, `TestFindCitations`) should be removed from both files since they're already in `test_citation_context.py`.

---

### Issue 3 — Fragile field-absence assertion in `test_metadata_cleaner.py` [MEDIUM]

**File:** `tests/test_metadata_cleaner.py`
**Lines:** ~286-287 in `TestCleanBibtex::test_removes_hallucinated_number`

```python
assert "number = " not in cleaned_content.lower().replace('"', '').replace('{', '').replace('}', '')
```

This attempts to detect the absence of a `number` BibTeX field by stripping braces and quotes from the raw file content. It is fragile because:
- pybtex may format the field as `number = {7729}`, `Number = {7729}`, or in other ways
- After stripping `{` and `}`, the string `number = 7729` might still appear in unrelated content (e.g., in a keyword tag that mentions the removed field)

The test's intent is to verify the `number` field was removed as a BibTeX field. The right approach is to parse the cleaned BibTeX and check field absence directly.

**Fix:** After `clean_bibtex`, parse the output `.bib` file using `pybtex.database.parse_file` and assert `'number' not in entry.fields` for the relevant entry key.

---

### Issue 4 — `tempfile.NamedTemporaryFile` + manual cleanup in `test_enrich_bibliography.py` [LOW]

**File:** `tests/test_enrich_bibliography.py`
**Affected tests:** `TestBatchProcessing` and `TestStats` — approximately 8 tests

These tests create temp files with `delete=False` and clean them up in `finally` blocks:

```python
with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
    f.write(content)
    input_path = Path(f.name)
output_path = input_path.with_suffix('.enriched.bib')
try:
    stats = enrich_bibliography.enrich_bibliography(...)
    ...
finally:
    input_path.unlink()
    if output_path.exists():
        output_path.unlink()
```

Problems:
- If the `import enrich_bibliography` line (which is inside the try block in some tests) fails, the finally block may not clean up `output_path`
- The pattern is verbose and inconsistent with the rest of the test suite, which uses pytest's `tmp_path` fixture throughout

**Fix:** Replace with `tmp_path` fixture. Write files to `tmp_path / "test.bib"` and pass `tmp_path / "output.bib"` as the output path. No manual cleanup needed.

---

### Issue 5 — Timing-sensitive assertion in `test_rate_limiter.py` [LOW]

**File:** `tests/test_rate_limiter.py`
**Test:** `TestRateLimiter::test_subsequent_request_waits` and `TestSlotReservation::test_consecutive_waits_without_record`

```python
assert elapsed >= 0.15  # Allow some tolerance
```

With a 0.2s `min_interval`, a 0.15s lower bound leaves only 25ms headroom. On a loaded CI machine this can flake. The `wait_time` return value from `limiter.wait()` is already tested (`assert wait_time > 0`) which doesn't require actual sleeping.

**Fix:** Keep the `wait_time > 0` assertion and drop the `elapsed >= ...` check, or use `patch("time.sleep")` and assert it was called with the right delay instead of measuring wall-clock time.

---

### Issue 6 — Missing test for `fetch_sep.py` [HIGH]

**File:** `.claude/skills/philosophy-research/scripts/fetch_sep.py`
**Missing test file:** `tests/test_fetch_sep.py`

`fetch_sep.py` fetches and parses Stanford Encyclopedia of Philosophy articles, with caching (via `search_cache`). It has equivalent complexity to `fetch_iep.py`, which has a thorough test file (`test_fetch_iep.py`).

**Fix:** Create `tests/test_fetch_sep.py` modelled on `test_fetch_iep.py`. See the recommended structure below.

---

### Issue 7 — Undocumented semantic gap in cache (`test_search_cache.py`) [LOW]

**File:** `tests/test_search_cache.py`
**Test:** `TestCacheEdgeCases::test_cache_handles_none_values`

The test acknowledges but doesn't resolve a real semantic issue:

```python
def test_cache_handles_none_values(self, clean_cache):
    """Cache should handle None values correctly."""
    key = cache_key(source="test", query="none")
    put_cache(key, None)
    assert get_cache(key) is None  # Can't distinguish from cache miss
```

`get_cache` returns `None` both for "key not found" and "key found but value is `None`". This means any code that uses `if result := get_cache(key):` will silently re-fetch if the cached result was `None`. This is a real bug risk for scripts that cache "not found" results.

This is a code quality issue in `search_cache.py` itself, not just the test. The recommended fix is to have `get_cache` return a sentinel (e.g., a `CacheMiss` object) or to document that caching `None` is unsupported and add a guard in `put_cache`.

---

## Recommended Fix Order

The fixes are independent and can be done in any order. Suggested sequence based on risk:

1. **Fix Issue 1** (`test_output_schemas.py` silent passes) — 5-minute fix, highest impact
2. **Create `tests/test_fetch_sep.py`** (Issue 6) — ~2 hours, highest coverage gap
3. **Fix Issue 3** (fragile assertion in `test_metadata_cleaner.py`) — 30 minutes
4. **Fix Issue 2** (duplicate SEP/IEP test logic) — 30 minutes
5. **Fix Issue 4** (`tempfile` → `tmp_path` in `test_enrich_bibliography.py`) — 30 minutes
6. **Fix Issue 5** (timing-sensitive rate limiter test) — 10 minutes
7. **Investigate Issue 7** (`None` cache gap) — requires design decision

---

## Recommended Structure for `tests/test_fetch_sep.py`

`fetch_sep.py` is expected to mirror `fetch_iep.py`. Use `test_fetch_iep.py` as the direct template. Key differences to verify before writing:

- The SEP URL pattern: `https://plato.stanford.edu/entries/{entry_name}/`
- The HTML structure SEP uses (different from IEP — check the actual `fetch_sep.py` implementation)
- The `source` field in output should be `"sep"` (verify against the script)
- Rate limiter key: check what `get_limiter(...)` call `fetch_sep.py` uses (likely `"sep_fetch"`)
- Whether `fetch_sep.py` uses the same `search_cache` caching pattern as `fetch_iep.py` (it was added in commit `e185772`)

Test classes to include (same as `test_fetch_iep.py`):
- `TestSEPOutputSchema` — `output_success`, `output_error` schema compliance
- `TestSEPParsing` — `extract_preamble`, `extract_sections`, `extract_bibliography` with sample HTML
- `TestSEPFetching` — mocked HTTP: success, 404, rate limit retry
- `TestSEPProgressOutput` — `log_progress` goes to stderr
- `TestSEPCLI` — `--help` works
- `TestSEPRateLimiter` — limiter is configured with `min_interval >= 1.0`

---

## How to Run Tests

```bash
pytest tests/
```

To run a specific file:
```bash
pytest tests/test_output_schemas.py -v
```

To run with output on failures:
```bash
pytest tests/ -v --tb=short
```
