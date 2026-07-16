# Friendly-Fetching Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `philosophy-research` skill's three direct-scrape fetchers (SEP, IEP, NDPR) well-behaved: honor SEP's `crawl-delay`, stop disguising IEP 403s as a browser, and send one honest, contactable, overridable User-Agent everywhere.

**Architecture:** Three independent behavior corrections to existing fetcher scripts under `skills/philosophy-research/scripts/`. A single shared `USER_AGENT` constant is added to `rate_limiter.py` (already imported by every fetcher) and referenced from all four direct-fetch call sites. Each fix is pinned by regression tests that mock `requests.get` and inject mock rate limiters (no network, no real sleeps or lock-file I/O). No API-client scripts (Semantic Scholar, OpenAlex, CrossRef, CORE, Brave, arXiv) are touched.

**Tech Stack:** Python 3, `requests`, `pytest` with `unittest.mock`. Tests run via `uv run --locked pytest`.

## Source of Truth

This plan implements the verified spec `~/Downloads/2026-07-15-phillit-friendly-fetching-spec.md`. The spec's paths (`scripts/…`) map to this repo as `skills/philosophy-research/scripts/…`. All three issues, and the four-file scope, were confirmed present in this repo on 2026-07-15 (line numbers matched the spec within ±1).

## Global Constraints

- **Cross-platform file I/O:** any new `open()`/`read_text()`/`write_text()` must pass `encoding='utf-8'`. (No file I/O is added by this plan, but the rule stands.)
- **No non-ASCII in script output:** avoid characters like `→` in strings that may be piped through subprocesses (Windows `cp1252`).
- **Never invoke bare `python`:** run all Python through `bash bin/phillit-run <script>` or, for tests, `uv run --locked pytest`.
- **Default User-Agent string (verbatim, single source of truth):** `Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/AI-4-Phi/PhilLit)`
- **Env override variable name (verbatim):** `PHILLIT_FETCH_USER_AGENT`
- **Commit style (repo convention):** `Fetchers: <short description>` (component-prefixed, imperative — matches recent history like `Setup: …`, `Plugin: …`). End every commit message with the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Do not push.** Main is pushed manually by the user. Commit locally only.
- **Full suite must stay green:** `uv run --locked pytest` (767 tests before this work).

## Interfaces Introduced

- `rate_limiter.USER_AGENT: str` — module-level constant. Consumed by `fetch_sep.py`, `fetch_iep.py`, `fetch_ndpr.py`, `search_ndpr.py` via `from rate_limiter import USER_AGENT`.

## Task Ordering & Dependencies

- Task 1 (SEP delay) — independent.
- Task 2 (add `USER_AGENT` constant) — must precede Task 3 and Task 4.
- Task 3 (wire `USER_AGENT` into all four fetchers) — depends on Task 2; must precede Task 4 (Task 4's test asserts the IEP request carries `USER_AGENT`, which Task 3 establishes).
- Task 4 (remove IEP 403 disguise) — depends on Task 3.
- Task 5 (version bump) — last; release step.

---

### Task 1: Honor SEP's crawl-delay

SEP's `robots.txt` opens with `crawl-delay: 5`. The `sep_fetch` limiter currently runs at 1.0 s — five times too fast. IEP and NDPR request no delay and stay at 1.0 s.

**Files:**
- Modify: `skills/philosophy-research/scripts/rate_limiter.py:263`
- Test: `tests/test_rate_limiter.py`

**Interfaces:**
- Consumes: `LIMITERS` dict (already exported).
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

Append these two tests at **module level** (no enclosing class — they take no `self`) at the end of `tests/test_rate_limiter.py`:

```python
def test_sep_fetch_honors_crawl_delay():
    """SEP robots.txt asks for crawl-delay: 5; the limiter must match it."""
    assert LIMITERS["sep_fetch"]().min_interval == 5.0


def test_iep_and_ndpr_intervals_unchanged():
    """IEP and NDPR request no crawl-delay; both stay at the conservative 1.0s."""
    assert LIMITERS["iep_fetch"]().min_interval == 1.0
    assert LIMITERS["ndpr"]().min_interval == 1.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --locked pytest tests/test_rate_limiter.py::test_sep_fetch_honors_crawl_delay -v`
Expected: FAIL — `assert 1.0 == 5.0`.

- [ ] **Step 3: Change the SEP interval**

In `skills/philosophy-research/scripts/rate_limiter.py`, change line 263 from:

```python
    "sep_fetch": lambda: RateLimiter("sep_fetch", 1.0),
```

to:

```python
    "sep_fetch": lambda: RateLimiter("sep_fetch", 5.0),  # robots.txt crawl-delay: 5 (was 1.0)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --locked pytest tests/test_rate_limiter.py::test_sep_fetch_honors_crawl_delay tests/test_rate_limiter.py::test_iep_and_ndpr_intervals_unchanged -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add skills/philosophy-research/scripts/rate_limiter.py tests/test_rate_limiter.py
git commit -m "$(cat <<'EOF'
Fetchers: honor SEP crawl-delay (1.0s -> 5.0s)

SEP's robots.txt requests crawl-delay: 5. The sep_fetch limiter ran at
1.0s, fetching five times faster than asked. IEP/NDPR stay at 1.0s.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add the shared, overridable User-Agent constant

Introduce one honest, contactable User-Agent, read once at import and overridable via `PHILLIT_FETCH_USER_AGENT`. It lives in `rate_limiter.py` because all four fetchers already import from that module (zero new imports, no new file).

**Files:**
- Modify: `skills/philosophy-research/scripts/rate_limiter.py` (imports block; new constant after the `fcntl` import block)
- Test: `tests/test_rate_limiter.py`

**Interfaces:**
- Produces: `rate_limiter.USER_AGENT: str` — the default string above, or the value of `PHILLIT_FETCH_USER_AGENT` if set at import time.

- [ ] **Step 1: Write the failing tests**

At the top of `tests/test_rate_limiter.py`, add `import os` (the file already imports `time`, `patch`, `pytest`; it does NOT yet import `os`). Place it with the other stdlib imports, e.g. immediately above `import time`:

```python
import os
import time
```

Then add this helper plus two tests at module level at the end of `tests/test_rate_limiter.py`. The helper loads `rate_limiter.py` fresh **in isolation** (a private module object, not registered in `sys.modules`) so the `PHILLIT_FETCH_USER_AGENT` env is read at exec time without mutating the shared canonical `rate_limiter` module that every other test and the conftest fixture depend on:

```python
def _load_rate_limiter_isolated():
    """Exec rate_limiter.py into a throwaway module so USER_AGENT reflects the
    current os.environ without touching the shared sys.modules['rate_limiter']."""
    import importlib.util
    path = (
        Path(__file__).parent.parent
        / "skills" / "philosophy-research" / "scripts" / "rate_limiter.py"
    )
    spec = importlib.util.spec_from_file_location("rate_limiter_isolated", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_user_agent_default():
    """Default UA is the honest, contactable repo-linked bot string."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PHILLIT_FETCH_USER_AGENT", None)
        module = _load_rate_limiter_isolated()
        assert module.USER_AGENT == (
            "Mozilla/5.0 (compatible; PhiloResearchBot/1.0; "
            "+https://github.com/AI-4-Phi/PhilLit)"
        )


def test_user_agent_env_override():
    """PHILLIT_FETCH_USER_AGENT overrides the default UA at import time."""
    with patch.dict(
        os.environ,
        {"PHILLIT_FETCH_USER_AGENT": "PhilLitService/2.0 (+mailto:ops@example.org)"},
    ):
        module = _load_rate_limiter_isolated()
        assert module.USER_AGENT == "PhilLitService/2.0 (+mailto:ops@example.org)"
```

Notes:
- `Path` is already imported at the top of `tests/test_rate_limiter.py`.
- Executing `rate_limiter.py` is side-effect-free: `LOCK_DIR` is only a `Path` object at module scope (the `mkdir` happens in `RateLimiter.__init__`, never called here), so no disk is touched.
- The two-line assertion string, concatenated, is exactly `Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/AI-4-Phi/PhilLit)` (a single space follows `1.0;`, then `+https`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --locked pytest tests/test_rate_limiter.py::test_user_agent_default tests/test_rate_limiter.py::test_user_agent_env_override -v`
Expected: FAIL — `AttributeError: module 'rate_limiter_isolated' has no attribute 'USER_AGENT'`.

- [ ] **Step 3: Add `import os` and the constant to `rate_limiter.py`**

In `skills/philosophy-research/scripts/rate_limiter.py`, add `import os` to the imports block. Current block (lines 31-34):

```python
import random
import time
from pathlib import Path
from typing import Optional
```

becomes:

```python
import os
import random
import time
from pathlib import Path
from typing import Optional
```

Then, immediately AFTER the `fcntl` try/except block (the lines ending `    HAS_FCNTL = False`) and BEFORE `class RateLimiter:`, insert:

```python


# Honest, contactable User-Agent for direct fetches of scraped sites (SEP, IEP,
# NDPR). Read once at import; overridable via PHILLIT_FETCH_USER_AGENT so a
# downstream packaging (e.g. a hosted service) can identify itself distinctly
# with its own contact address. The default stays the repo-linked bot UA.
USER_AGENT = os.environ.get(
    "PHILLIT_FETCH_USER_AGENT",
    "Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/AI-4-Phi/PhilLit)",
)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --locked pytest tests/test_rate_limiter.py::test_user_agent_default tests/test_rate_limiter.py::test_user_agent_env_override -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add skills/philosophy-research/scripts/rate_limiter.py tests/test_rate_limiter.py
git commit -m "$(cat <<'EOF'
Fetchers: add shared overridable User-Agent constant

rate_limiter.USER_AGENT holds one honest, contactable UA, overridable via
PHILLIT_FETCH_USER_AGENT so downstream packagings can identify themselves.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Send one honest User-Agent from all four direct site fetches

Route every direct-fetch call site through `rate_limiter.USER_AGENT`. This is behavior-preserving for `fetch_iep.py` (primary request) and `search_ndpr.py`, which already send the full form; it upgrades `fetch_sep.py` and `fetch_ndpr.py` from the bare `PhiloResearchBot/1.0` (no contact URL) to the full contactable form.

**Files:**
- Modify: `skills/philosophy-research/scripts/fetch_sep.py` (import line 26; request headers line 236)
- Modify: `skills/philosophy-research/scripts/fetch_ndpr.py` (import line 33; request headers line 167)
- Modify: `skills/philosophy-research/scripts/search_ndpr.py` (import line 27; request headers line 134)
- Modify: `skills/philosophy-research/scripts/fetch_iep.py` (import line 25; primary request headers line 246 — the 403-branch UA at line 261 is removed in Task 4, not here)
- Test: `tests/test_fetch_sep.py`, `tests/test_fetch_ndpr.py`, `tests/test_search_ndpr.py`, `tests/test_fetch_iep.py`

**Interfaces:**
- Consumes: `rate_limiter.USER_AGENT` (Task 2).
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

Each test patches the fetcher module's `USER_AGENT` to a unique **sentinel** value, then asserts that exact sentinel reaches `requests.get`. This proves the request-header line is genuinely *routed through the constant* — a plain `assert ua == module.USER_AGENT` would pass for `fetch_iep`/`search_ndpr` even if the header line were never changed, because their old hardcoded string already equals the default. `patch.object(module, "USER_AGENT", …)` also fails cleanly (AttributeError) before Step 3 adds the import, giving a correct red. Rate limiters are injected as `MagicMock()` so the tests exercise no lock-file I/O and never sleep; a real `ExponentialBackoff` is passed only because the retry loop reads `backoff.max_attempts` (a `MagicMock` there would break `range(...)`). All four test files already import `patch` and `MagicMock` at module level; `fetch_*`/`search_ndpr` are importable (scripts dir is on `sys.path`).

Each test defines the same sentinel string locally (`sentinel = "SentinelUA/9.9 (+https://example.test/bot)"`).

Add to `tests/test_fetch_sep.py` (append at end of file, module level):

```python
@patch("fetch_sep.put_cache", return_value=True)
@patch("fetch_sep.get_cache", return_value=None)
@patch("fetch_sep.requests.get")
def test_fetch_sep_routes_request_through_user_agent(mock_get, _get_cache, _put_cache):
    import fetch_sep
    from rate_limiter import ExponentialBackoff
    mock_get.return_value = MagicMock(
        status_code=200, text="<html><body><h1>Free Will</h1></body></html>"
    )
    sentinel = "SentinelUA/9.9 (+https://example.test/bot)"
    with patch.object(fetch_sep, "USER_AGENT", sentinel):
        fetch_sep.fetch_sep_article("freewill", MagicMock(), ExponentialBackoff(max_attempts=2))
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == sentinel
```

Add to `tests/test_fetch_ndpr.py` (append at end, module level):

```python
@patch("fetch_ndpr.requests.get")
def test_fetch_ndpr_routes_request_through_user_agent(mock_get):
    import fetch_ndpr
    mock_get.return_value = MagicMock(
        status_code=200,
        text="<html><body><div class='entry-content'>"
        "<p>This substantive opening paragraph is well over fifty characters long "
        "so the extractor keeps it.</p></div></body></html>",
    )
    sentinel = "SentinelUA/9.9 (+https://example.test/bot)"
    with patch.object(fetch_ndpr, "USER_AGENT", sentinel):
        fetch_ndpr.fetch_ndpr_review("https://ndpr.nd.edu/reviews/example/", limiter=MagicMock())
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == sentinel
```

Add to `tests/test_search_ndpr.py` (append at end, module level):

```python
@patch("search_ndpr.requests.get")
def test_search_ndpr_sitemap_routes_request_through_user_agent(mock_get):
    import search_ndpr
    from rate_limiter import ExponentialBackoff
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://ndpr.nd.edu/reviews/being-and-time/</loc></url></urlset>"
    )
    mock_get.return_value = MagicMock(status_code=200, text=sitemap)
    sentinel = "SentinelUA/9.9 (+https://example.test/bot)"
    search_ndpr.clear_sitemap_cache()
    try:
        with patch.object(search_ndpr, "USER_AGENT", sentinel):
            search_ndpr.fetch_sitemap(MagicMock(), ExponentialBackoff(max_attempts=2))
        assert mock_get.call_args.kwargs["headers"]["User-Agent"] == sentinel
    finally:
        search_ndpr.clear_sitemap_cache()
```

Add to `tests/test_fetch_iep.py` (append at end, module level):

```python
@patch("fetch_iep.put_cache", return_value=True)
@patch("fetch_iep.get_cache", return_value=None)
@patch("fetch_iep.requests.get")
def test_fetch_iep_routes_request_through_user_agent(mock_get, _get_cache, _put_cache):
    import fetch_iep
    from rate_limiter import ExponentialBackoff
    mock_get.return_value = MagicMock(
        status_code=200, text="<html><body><h1>Free Will</h1></body></html>"
    )
    sentinel = "SentinelUA/9.9 (+https://example.test/bot)"
    with patch.object(fetch_iep, "USER_AGENT", sentinel):
        fetch_iep.fetch_iep_article("freewill", MagicMock(), ExponentialBackoff(max_attempts=2))
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == sentinel
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run --locked pytest \
  tests/test_fetch_sep.py::test_fetch_sep_routes_request_through_user_agent \
  tests/test_fetch_ndpr.py::test_fetch_ndpr_routes_request_through_user_agent \
  tests/test_search_ndpr.py::test_search_ndpr_sitemap_routes_request_through_user_agent \
  tests/test_fetch_iep.py::test_fetch_iep_routes_request_through_user_agent -v
```
Expected: FAIL — `AttributeError: <module 'fetch_sep' …> does not have the attribute 'USER_AGENT'` raised by `patch.object` (and likewise for the other three), because the `USER_AGENT` import is not added until Step 3.

- [ ] **Step 3: Wire `USER_AGENT` into all four fetchers**

**`fetch_sep.py`** — change the import (line 26) from:
```python
from rate_limiter import ExponentialBackoff, get_limiter
```
to:
```python
from rate_limiter import ExponentialBackoff, USER_AGENT, get_limiter
```
and change the request (line 236) from:
```python
            response = requests.get(url, timeout=30, headers={"User-Agent": "PhiloResearchBot/1.0"})
```
to:
```python
            response = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
```

**`fetch_ndpr.py`** — change the import (line 33) from:
```python
from rate_limiter import ExponentialBackoff, get_limiter
```
to:
```python
from rate_limiter import ExponentialBackoff, USER_AGENT, get_limiter
```
and change the request headers (line 167) from:
```python
                headers={"User-Agent": "PhiloResearchBot/1.0"},
```
to:
```python
                headers={"User-Agent": USER_AGENT},
```

**`search_ndpr.py`** — change the import (line 27) from:
```python
from rate_limiter import ExponentialBackoff, get_limiter
```
to:
```python
from rate_limiter import ExponentialBackoff, USER_AGENT, get_limiter
```
and change the request headers (line 134) from:
```python
                headers={"User-Agent": "Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/AI-4-Phi/PhilLit)"},
```
to:
```python
                headers={"User-Agent": USER_AGENT},
```

**`fetch_iep.py`** — change the import (line 25) from:
```python
from rate_limiter import ExponentialBackoff, get_limiter
```
to:
```python
from rate_limiter import ExponentialBackoff, USER_AGENT, get_limiter
```
and change the primary request headers (lines 245-247) from:
```python
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/AI-4-Phi/PhilLit)"
                }
```
to:
```python
                headers={"User-Agent": USER_AGENT}
```
(Leave the 403 branch at lines 253-268 untouched here; Task 4 removes it.)

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
uv run --locked pytest \
  tests/test_fetch_sep.py::test_fetch_sep_routes_request_through_user_agent \
  tests/test_fetch_ndpr.py::test_fetch_ndpr_routes_request_through_user_agent \
  tests/test_search_ndpr.py::test_search_ndpr_sitemap_routes_request_through_user_agent \
  tests/test_fetch_iep.py::test_fetch_iep_routes_request_through_user_agent -v
```
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add skills/philosophy-research/scripts/fetch_sep.py \
        skills/philosophy-research/scripts/fetch_ndpr.py \
        skills/philosophy-research/scripts/search_ndpr.py \
        skills/philosophy-research/scripts/fetch_iep.py \
        tests/test_fetch_sep.py tests/test_fetch_ndpr.py \
        tests/test_search_ndpr.py tests/test_fetch_iep.py
git commit -m "$(cat <<'EOF'
Fetchers: send one honest User-Agent from all direct site fetches

fetch_sep and fetch_ndpr sent a bare PhiloResearchBot/1.0 with no contact
URL; all four direct-fetch sites now use the shared, contactable USER_AGENT.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Stop disguising IEP 403s as a browser

On HTTP 403, `fetch_iep.py` currently re-requests with a spoofed desktop-browser User-Agent and browser `Accept` headers. That is circumvention (and dead code — IEP serves every UA 200 today). Remove the branch entirely so a 403 falls through to the generic non-200 error path, exactly like any other HTTP error. No second request with an altered identity is ever made.

**Files:**
- Modify: `skills/philosophy-research/scripts/fetch_iep.py` (delete the `elif response.status_code == 403:` branch, lines 253-268)
- Test: `tests/test_fetch_iep.py`

**Interfaces:**
- Consumes: `fetch_iep.USER_AGENT` (established in Task 3).
- Produces: nothing new. A 403 now raises `RuntimeError("HTTP error: 403")` via the existing `elif response.status_code != 200:` path.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_fetch_iep.py` (append at end, module level):

```python
@patch("fetch_iep.get_cache", return_value=None)
@patch("fetch_iep.requests.get")
def test_fetch_iep_403_no_disguise(mock_get, _get_cache):
    """A 403 is treated as any other HTTP error: one honest request, no browser disguise."""
    import fetch_iep
    from rate_limiter import ExponentialBackoff
    mock_get.return_value = MagicMock(status_code=403, text="Forbidden")
    limiter = MagicMock()
    with pytest.raises(RuntimeError) as exc_info:
        fetch_iep.fetch_iep_article(
            "freewill", limiter, ExponentialBackoff(max_attempts=3)
        )
    assert "403" in str(exc_info.value)
    # Exactly one request/wait cycle: the 403 must not trigger a second, disguised request.
    assert mock_get.call_count == 1
    limiter.wait.assert_called_once()
    # No request ever carries a browser-disguise UA; the honest UA is used throughout.
    for call in mock_get.call_args_list:
        ua = call.kwargs["headers"]["User-Agent"]
        assert ua == fetch_iep.USER_AGENT
        assert "Windows NT" not in ua
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --locked pytest tests/test_fetch_iep.py::test_fetch_iep_403_no_disguise -v`
Expected: FAIL — the current 403 branch issues a second, disguised `requests.get`, so the test trips on `assert mock_get.call_count == 1` (actual: 2). (`RuntimeError` is still raised and contains "403", so that earlier assertion passes; the count assertion is the one that fails.)

- [ ] **Step 3: Delete the 403 disguise branch**

In `skills/philosophy-research/scripts/fetch_iep.py`, delete the entire `elif response.status_code == 403:` branch. The current block (lines 251-276) reads:

```python
            if response.status_code == 404:
                raise LookupError(f"IEP entry not found: {entry_name}")
            elif response.status_code == 403:
                log_progress(f"Access denied (403), trying with different headers...")
                # Try with different headers (respect rate limiter)
                limiter.wait()
                response = requests.get(
                    url,
                    timeout=30,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                )
                limiter.record()
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP error: {response.status_code} (access denied)")
            elif response.status_code == 429:
                log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded after max retries")
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            elif response.status_code != 200:
                raise RuntimeError(f"HTTP error: {response.status_code}")
```

Remove the `elif response.status_code == 403:` branch so it becomes:

```python
            if response.status_code == 404:
                raise LookupError(f"IEP entry not found: {entry_name}")
            elif response.status_code == 429:
                log_progress(f"Rate limited, backing off (attempt {attempt+1}/{backoff.max_attempts})...")
                if not backoff.wait(attempt):
                    raise RuntimeError("Rate limit exceeded after max retries")
                log_progress(f"Retrying after {backoff.last_delay:.1f}s backoff...")
                continue
            elif response.status_code != 200:
                raise RuntimeError(f"HTTP error: {response.status_code}")
```

A 403 now matches `elif response.status_code != 200:` and raises `RuntimeError("HTTP error: 403")`, which propagates out (it is not a `requests.exceptions.RequestException`, so the retry loop does not swallow it) and is reported as a `parse_error` (exit 3) by `main()` — identical treatment to any other non-200/404/429 status.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --locked pytest tests/test_fetch_iep.py::test_fetch_iep_403_no_disguise -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/philosophy-research/scripts/fetch_iep.py tests/test_fetch_iep.py
git commit -m "$(cat <<'EOF'
Fetchers: stop disguising IEP 403s as a browser

On 403, fetch_iep re-requested with a spoofed desktop-browser UA -
circumvention, and dead code (IEP serves every UA 200). A 403 now falls
through to the generic HTTP-error path like any other status.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Bump plugin version to 0.2.4 (release step)

These are user-facing runtime behavior changes to the installed plugin. Per the repo's release policy (`CLAUDE.md` → Releasing), installed plugins are pinned to `plugin.json`'s `version`, and `/plugin update` only fires when it changes. `version` must NOT be duplicated in `marketplace.json`.

**Files:**
- Modify: `.claude-plugin/plugin.json:4`
- Test: `tests/test_plugin_manifest.py` (verify it still passes; no new test needed)

**Interfaces:** none.

- [ ] **Step 1: Bump the version**

In `.claude-plugin/plugin.json`, change line 4 from:
```json
  "version": "0.2.3",
```
to:
```json
  "version": "0.2.4",
```

- [ ] **Step 2: Confirm the manifest test still passes**

Run: `uv run --locked pytest tests/test_plugin_manifest.py -v`
Expected: PASS.

- [ ] **Step 3: Confirm marketplace.json does NOT also declare a version**

Run: `grep -q '"version"' .claude-plugin/marketplace.json && echo "FOUND — remove it" || echo "OK — absent"`
Expected: `OK — absent`. If it prints `FOUND — remove it`, delete the `version` key from `marketplace.json` (`plugin.json` silently wins — a duplicate is a stale-value trap) and include `marketplace.json` in the Step 4 `git add`.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "$(cat <<'EOF'
Plugin: bump version to 0.2.4 - friendly-fetching fixes

SEP crawl-delay honored, IEP 403 disguise removed, one honest overridable
User-Agent across all direct site fetches.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final Verification

- [ ] **Run the full suite:** `uv run --locked pytest`
  Expected: all tests pass (767 prior + 9 new = 776 collected; count is indicative, not asserted).

- [ ] **Manual smoke (optional, requires network + `BRAVE_API_KEY` not needed for direct fetch):**
  ```bash
  bash bin/phillit-run skills/philosophy-research/scripts/fetch_sep.py freewill --debug 2>&1 | head -20
  bash bin/phillit-run skills/philosophy-research/scripts/fetch_iep.py freewill --debug 2>&1 | head -20
  ```
  Confirm normal JSON output and (via `--debug`/a proxy) the honest `USER_AGENT` on the wire. Note the first SEP fetch of a session may now pause up to ~5 s on a repeat within the crawl-delay window; the 7-day pickle cache dedupes repeats.

- [ ] **Do not push.** Leave commits local for the user to push manually.

## Notes / Out of Scope (from the spec)

Caching layers, mirrors, runtime `robots.txt` parsing, SEP archived-edition URL switching, and any service-side machinery are explicitly **out of scope** — they are phillit-service concerns. This plan is only the three behavior corrections plus the release bump.
