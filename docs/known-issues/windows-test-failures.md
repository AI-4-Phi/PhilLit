# Windows: Test Failures on Git Bash + Python 3.12

## Environment

- Windows 11 (ARM64, VMware Fusion)
- Git Bash (Git for Windows)
- Python 3.12.10
- pytest 9.0.2

## Failing Tests (3 of 632)

### 1. `test_assemble_review.py::TestAssembleReview::test_utf8_preserved`

**Error**: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xdc in position 3: invalid continuation byte`

**Cause**: Windows temp files may use a different default encoding. The test writes UTF-8 content to a temp file and reads it back, but the round-trip fails on Windows.

**Fix direction**: Ensure explicit `encoding='utf-8'` on all `open()` calls in `assemble_review.py` and the test.

### 2. `test_lint_md.py::TestLintMarkdown::test_explanation_included`

**Error**: `assert 'Fix:' in 'C:\\Users\\johan\\AppData\\Local\\Temp\\...'`

**Cause**: pymarkdown outputs Windows-style backslash paths in its error messages. The test looks for `'Fix:'` in the output but the path string dominates the output and the parsing logic doesn't find the expected substring.

**Fix direction**: Normalize or strip file paths from pymarkdown output before checking for explanation text.

### 3. `test_lint_md.py::TestLintMarkdown::test_multiple_errors_multiple_explanations`

**Error**: `assert 0 >= 2`

**Cause**: Same pymarkdown output parsing issue as above — the lint result parser fails to extract errors when paths contain backslashes.

**Fix direction**: Same as above.

## Impact

These failures do not affect production behavior. All 632 tests pass on macOS/Linux.
