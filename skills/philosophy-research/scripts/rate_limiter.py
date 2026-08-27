"""
Shared file-based rate limiter for cross-process coordination.

This module provides rate limiting that works across multiple concurrent processes,
preventing API bans when parallel agents call scripts simultaneously.

Slot reservation: wait() writes the projected request time to the lock file before
releasing the lock. This ensures the next process sees the reserved slot and queues
behind it, even if the current process hasn't made its request yet.

Usage:
    from rate_limiter import get_limiter, ExponentialBackoff

    limiter = get_limiter("semantic_scholar", authenticated=bool(api_key))
    limiter.wait()  # Blocks until safe to make request, reserves time slot
    response = requests.get(...)
    limiter.record()  # Optional: refine timestamp with actual request time

For retry logic with exponential backoff:
    backoff = ExponentialBackoff()
    for attempt in range(backoff.max_attempts):
        limiter.wait()
        response = requests.get(...)
        if response.status_code == 429:
            if not backoff.wait(attempt):
                break  # Max attempts exceeded
            continue
        break
"""

import os
import random
import time
from pathlib import Path
from typing import Optional

# File locking: fcntl on Unix, no-op on Windows (rate limiting still works via timestamps)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


def user_agent() -> str:
    """Honest, contactable User-Agent for direct fetches of scraped sites
    (SEP, IEP, NDPR). Overridable via PHILLIT_FETCH_USER_AGENT so a
    downstream packaging (e.g. a hosted service) can identify itself
    distinctly with its own contact address; the default is the repo-linked
    bot UA. Resolved at CALL time, never import time: the workspace .env is
    loaded in each CLI's main(), which runs after this module is imported -
    an import-time constant silently pins the default."""
    return (
        os.environ.get("PHILLIT_FETCH_USER_AGENT")
        or "Mozilla/5.0 (compatible; PhiloResearchBot/1.0; +https://github.com/AI-4-Phi/PhilLit)"
    )


class RateLimiter:
    """
    File-based rate limiter that coordinates across concurrent processes.

    Uses file locking (Unix) and slot reservation to prevent race conditions
    when multiple agents make API requests in parallel. Each call to wait()
    reserves a time slot by writing the projected request time, so subsequent
    callers queue behind it.
    """

    # Lock file directory - per-user, under home: a world-shared temp dir breaks
    # multi-user hosts (PermissionError on another user's lock files) and invites
    # name-squatting.
    LOCK_DIR = Path.home() / ".cache" / "phillit" / "ratelimits"

    def __init__(self, api_name: str, min_interval: float):
        """
        Initialize rate limiter for a specific API.

        Args:
            api_name: Identifier for the API (e.g., "semantic_scholar", "brave")
            min_interval: Minimum seconds between requests
        """
        self.api_name = api_name
        self.min_interval = min_interval
        self.LOCK_DIR.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.LOCK_DIR / f".ratelimit_{api_name}.lock"
        self._last_wait_time: Optional[float] = None

    def _read_timestamp(self, f) -> float:
        """Read the last request timestamp from the lock file."""
        try:
            f.seek(0)
            content = f.read().strip()
            return float(content) if content else 0
        except ValueError:
            return 0

    def _write_timestamp(self, f, timestamp: float) -> None:
        """Write a timestamp to the lock file."""
        f.seek(0)
        f.truncate()
        f.write(str(timestamp))
        f.flush()

    def wait(self) -> float:
        """
        Block until it's safe to make a request. Call BEFORE each API request.

        Reserves a time slot by writing the projected request time to the lock
        file before releasing the lock. This ensures concurrent processes queue
        properly even without calling record() afterwards.

        Under concurrent load, processes queue in order: if N processes contend,
        the Nth process waits approximately N * min_interval seconds.

        Returns:
            The number of seconds waited (0 if no wait was needed)
        """
        with open(self.lock_file, "a+") as f:
            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_EX)

            last_request = self._read_timestamp(f)
            now = time.time()

            # Guard against stale future timestamps (e.g., from crashed processes
            # or clock adjustments). Use 10x interval to allow normal queuing of
            # up to ~10 concurrent agents while still catching genuinely stale values.
            if last_request > now + 10 * self.min_interval:
                last_request = 0

            elapsed = now - last_request
            wait_time = 0.0
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed

            # Reserve the time slot: write projected request time BEFORE releasing
            # the lock, so the next process sees this reservation and queues behind it.
            projected_time = now + wait_time
            self._write_timestamp(f, projected_time)

            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_UN)

        # Sleep AFTER releasing lock so other processes can compute their own
        # queue position without waiting for our sleep to finish.
        if wait_time > 0:
            time.sleep(wait_time)

        self._last_wait_time = wait_time
        return wait_time

    def record(self) -> None:
        """
        Optionally refine the timestamp with the actual request time.

        wait() already reserves a slot by writing the projected time. This method
        updates the timestamp only if the actual time is later than what's recorded,
        preventing it from overwriting a later reservation by another process.
        """
        now = time.time()
        with open(self.lock_file, "a+") as f:
            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_EX)

            existing = self._read_timestamp(f)
            # Only write if our actual time is later than what's in the file,
            # to avoid overwriting a slot reserved by another process.
            if now > existing:
                self._write_timestamp(f, now)

            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_UN)

    def wait_and_record(self) -> float:
        """
        Convenience method: wait (reserving a slot), then record actual time.

        Returns:
            The number of seconds waited
        """
        wait_time = self.wait()
        self.record()
        return wait_time

    @property
    def last_wait_time(self) -> Optional[float]:
        """Return the wait time from the most recent wait() call."""
        return self._last_wait_time

    def reset(self) -> None:
        """Reset the rate limiter by removing the lock file."""
        if self.lock_file.exists():
            self.lock_file.unlink()


class ExponentialBackoff:
    """
    Exponential backoff for retry logic on rate limit errors.

    Usage:
        backoff = ExponentialBackoff()
        for attempt in range(backoff.max_attempts):
            response = requests.get(...)
            if response.status_code == 429:
                if not backoff.wait(attempt):
                    break  # Max attempts exceeded
                continue
            break
    """

    def __init__(self, max_attempts: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
        """
        Initialize backoff configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds (will be multiplied by 2^attempt)
            max_delay: Maximum delay cap in seconds
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._last_delay: Optional[float] = None

    def wait(self, attempt: int, retry_after: Optional[float] = None) -> bool:
        """
        Wait with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
            retry_after: Optional delay from Retry-After header (seconds).
                         If provided and larger than the computed delay, use it instead.

        Returns:
            True if should retry, False if max attempts exceeded
        """
        if attempt >= self.max_attempts - 1:
            return False

        # Calculate delay with jitter
        delay = min((2**attempt) * self.base_delay + random.uniform(0, 1), self.max_delay)

        # Respect Retry-After header if provided and larger
        if retry_after is not None and retry_after > delay:
            delay = min(retry_after, self.max_delay)

        self._last_delay = delay
        time.sleep(delay)
        return True

    def get_delay(self, attempt: int) -> float:
        """
        Calculate what the delay would be for a given attempt without waiting.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        return min((2**attempt) * self.base_delay, self.max_delay)

    @property
    def last_delay(self) -> Optional[float]:
        """Return the delay from the most recent wait() call."""
        return self._last_delay


# Pre-configured limiters for each API
# These are factory functions to ensure each caller gets a fresh instance
LIMITERS = {
    "semantic_scholar": lambda: RateLimiter("semantic_scholar", 1.1),
    "semantic_scholar_unauth": lambda: RateLimiter("semantic_scholar_unauth", 3.0),
    "brave": lambda: RateLimiter("brave", 1.5),
    "crossref": lambda: RateLimiter("crossref", 0.05),  # 50/sec but conservative
    "openalex": lambda: RateLimiter("openalex", 0.11),  # 10/sec
    "arxiv": lambda: RateLimiter("arxiv", 3.0),
    "sep_fetch": lambda: RateLimiter("sep_fetch", 5.0),  # robots.txt crawl-delay: 5 (was 1.0)
    "iep_fetch": lambda: RateLimiter("iep_fetch", 1.0),
    "core": lambda: RateLimiter("core", 2.0),  # 5 req/10 sec = 1 req/2 sec
    "ndpr": lambda: RateLimiter("ndpr", 1.0),  # 1 req/sec, conservative for web scraping
}


def get_limiter(api_name: str, authenticated: Optional[bool] = None) -> RateLimiter:
    """
    Get a pre-configured rate limiter for the specified API.

    Args:
        api_name: One of: semantic_scholar, brave, crossref, openalex, arxiv,
                  sep_fetch, iep_fetch, core, ndpr
        authenticated: For APIs with auth-aware tiers (e.g., semantic_scholar).
                       True/None = use default (authenticated) interval.
                       False = use slower unauthenticated interval.
                       Ignored for APIs without auth tiers.

    Returns:
        Configured RateLimiter instance

    Raises:
        ValueError: If api_name is not recognized
    """
    # Use unauthenticated variant if available and explicitly requested
    if authenticated is False and f"{api_name}_unauth" in LIMITERS:
        return LIMITERS[f"{api_name}_unauth"]()

    if api_name not in LIMITERS:
        valid = ", ".join(sorted(k for k in LIMITERS if not k.endswith("_unauth")))
        raise ValueError(f"Unknown API: {api_name}. Valid options: {valid}")
    return LIMITERS[api_name]()


def list_active_limiters() -> list[str]:
    """
    List all lock files currently in use.

    Returns:
        List of API names with active lock files
    """
    lock_dir = RateLimiter.LOCK_DIR
    if not lock_dir.exists():
        return []

    active = []
    for lock_file in lock_dir.glob(".ratelimit_*.lock"):
        api_name = lock_file.stem.replace(".ratelimit_", "")
        active.append(api_name)
    return sorted(active)


def parse_retry_after(header_value: Optional[str]) -> Optional[float]:
    """Parse a Retry-After header value (seconds) into a float.

    Args:
        header_value: The raw header value, or None if not present.

    Returns:
        Seconds to wait, or None if header absent or unparseable.
    """
    if header_value is None:
        return None
    try:
        return float(header_value)
    except (ValueError, TypeError):
        return None


def openalex_params(email: str = "") -> dict:
    """Query params every OpenAlex request should carry: `mailto` and, when
    available, `api_key`.

    OpenAlex began metering by daily spend in 2026 (see
    docs/known-issues/openalex-metering-2026-08-05.md). An unauthenticated
    client gets $0.10/day -- about 100 full-text searches, which one review's
    Phase 3 can approach on its own. A FREE key raises that to $1/day and
    makes single-entity lookups (`works/doi:...`, the abstract-resolution
    path) unmetered. The key is optional: without it every call behaves
    exactly as before.

    Resolved at CALL time, never import time -- same reason as user_agent():
    the workspace .env is loaded in each CLI's main(), which runs after this
    module is imported, so an import-time read would silently see no key.
    """
    params = {}
    if email:
        params["mailto"] = email
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    return params


def openalex_api_key() -> str:
    """The configured OpenAlex key, or "" -- the one owner of the env read.

    Resolved at CALL time, never import time -- same reason as user_agent():
    the workspace .env is loaded in each CLI's main(), which runs after this
    module is imported, so an import-time read would silently see no key.

    A value with characters outside printable ASCII reads as unset: real
    keys are short alphanumerics, and an embedded CR/LF would make requests
    raise InvalidHeader with the malformed value IN the exception message --
    re-opening the exact leak-to-stderr the header transport exists to close.
    """
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if key and all(33 <= ord(c) <= 126 for c in key):
        return key
    return ""


def openalex_headers() -> dict:
    """Auth header for OpenAlex requests, `{}` when no key is configured.

    Header transport keeps the key out of the URL, and therefore out of
    every exception message and log line that embeds one. The header is
    authoritative server-side (verified live 2026-08-27 with a registered
    key: header+param both 200; a bogus header 401s even with a valid
    param). Two known, accepted edges, both of which degrade to an UNKEYED
    request rather than a leak or an error: requests strips this header on
    a cross-host redirect (none of the endpoint shapes we call redirects --
    verified same day), and a user's ~/.netrc entry for api.openalex.org
    would replace it with Basic auth, which OpenAlex silently ignores
    (verified: Basic garbage -> 200). Either way the request runs on the
    $0.10/day unkeyed budget, and exhaustion is what the
    openalex_budget_exhausted detector reports loudly.
    """
    key = openalex_api_key()
    return {"Authorization": f"Bearer {key}"} if key else {}


_BUDGET_MARKERS = ("insufficient budget", "daily limit", "rate limit exceeded")


def openalex_budget_exhausted(response) -> bool:
    """True when a 429 means "your daily budget is gone", not "slow down".

    The two are not distinguishable by status code, and treating them alike is
    a real cost: exhaustion sets `Retry-After` to the seconds remaining until
    midnight UTC (observed: 81471), so an exponential backoff burns every
    attempt and then fails, once per call, for the rest of the day. Callers
    should stop retrying and say what happened instead.

    Never raises: any unexpected response shape reads as "not exhausted", so
    the caller falls back to ordinary backoff.
    """
    try:
        if getattr(response, "status_code", None) != 429:
            return False
        # A wait longer than any sane backoff is the unambiguous signal.
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        if retry_after is not None and retry_after > 300:
            return True
        body = (response.text or "").lower()
        return any(marker in body for marker in _BUDGET_MARKERS)
    except Exception:
        return False


def clear_all_limiters() -> int:
    """
    Remove all lock files. Useful for testing or resetting state.

    Returns:
        Number of lock files removed
    """
    lock_dir = RateLimiter.LOCK_DIR
    if not lock_dir.exists():
        return 0

    count = 0
    for lock_file in lock_dir.glob(".ratelimit_*.lock"):
        lock_file.unlink()
        count += 1
    return count


# For testing the module directly
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Testing rate limiter...")

        # Test basic functionality
        limiter = get_limiter("semantic_scholar")
        print(f"Lock file: {limiter.lock_file}")

        # First call should not wait
        wait1 = limiter.wait_and_record()
        print(f"First call wait time: {wait1:.3f}s")

        # Second call should wait ~1.1 seconds
        start = time.time()
        wait2 = limiter.wait_and_record()
        elapsed = time.time() - start
        print(f"Second call wait time: {wait2:.3f}s (elapsed: {elapsed:.3f}s)")

        # Test backoff
        backoff = ExponentialBackoff(max_attempts=3)
        for i in range(3):
            delay = backoff.get_delay(i)
            print(f"Backoff attempt {i}: delay would be {delay:.2f}s")

        # Cleanup
        limiter.reset()
        print("Test complete!")

    elif len(sys.argv) > 1 and sys.argv[1] == "--list":
        active = list_active_limiters()
        if active:
            print("Active rate limiters:")
            for name in active:
                print(f"  - {name}")
        else:
            print("No active rate limiters")

    elif len(sys.argv) > 1 and sys.argv[1] == "--clear":
        count = clear_all_limiters()
        print(f"Cleared {count} lock file(s)")

    else:
        print("Usage:")
        print("  python rate_limiter.py --test   Run basic tests")
        print("  python rate_limiter.py --list   List active limiters")
        print("  python rate_limiter.py --clear  Clear all lock files")
