"""
Shared file-based rate limiter for cross-script coordination.

This module provides rate limiting that works across multiple script invocations,
preventing API bans when agents call multiple scripts in sequence.

Usage:
    from rate_limiter import get_limiter, ExponentialBackoff

    limiter = get_limiter("semantic_scholar")
    limiter.wait()  # Blocks until safe to make request
    response = requests.get(...)
    limiter.record()  # Record successful request

    # Or use convenience method:
    limiter.wait_and_record()

For retry logic with exponential backoff:
    backoff = ExponentialBackoff()
    for attempt in range(backoff.max_attempts):
        limiter.wait()
        response = requests.get(...)
        limiter.record()
        if response.status_code == 429:
            if not backoff.wait(attempt):
                break  # Max attempts exceeded
            continue
        break
"""

import random
import tempfile
import time
from pathlib import Path
from typing import Optional

# File locking: fcntl on Unix, no-op on Windows (rate limiting still works via timestamps)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


class RateLimiter:
    """
    File-based rate limiter that coordinates across script invocations.
    Uses file locking to prevent race conditions.
    """

    # Lock file directory - use system temp dir for cross-platform compatibility
    LOCK_DIR = Path(tempfile.gettempdir()) / "philosophy_research_ratelimits"

    def __init__(self, api_name: str, min_interval: float):
        """
        Initialize rate limiter for a specific API.

        Args:
            api_name: Identifier for the API (e.g., "semantic_scholar", "brave")
            min_interval: Minimum seconds between requests
        """
        self.api_name = api_name
        self.min_interval = min_interval
        self.LOCK_DIR.mkdir(exist_ok=True)
        self.lock_file = self.LOCK_DIR / f".ratelimit_{api_name}.lock"
        self._last_wait_time: Optional[float] = None

    def wait(self) -> float:
        """
        Block until it's safe to make a request. Call BEFORE each API request.

        Returns:
            The number of seconds waited (0 if no wait was needed)
        """
        with open(self.lock_file, "a+") as f:
            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                content = f.read().strip()
                last_request = float(content) if content else 0
            except ValueError:
                last_request = 0

            elapsed = time.time() - last_request
            wait_time = 0.0
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)

            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_UN)

        self._last_wait_time = wait_time
        return wait_time

    def record(self) -> None:
        """Record that a request was made. Call AFTER each successful API request."""
        with open(self.lock_file, "w") as f:
            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_EX)
            f.write(str(time.time()))
            if HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_UN)

    def wait_and_record(self) -> float:
        """
        Convenience method: wait, then record.
        Use when you don't need to check response before recording.

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

    def wait(self, attempt: int) -> bool:
        """
        Wait with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry, False if max attempts exceeded
        """
        if attempt >= self.max_attempts - 1:
            return False

        # Calculate delay with jitter
        delay = min((2**attempt) * self.base_delay + random.uniform(0, 1), self.max_delay)
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
    "brave": lambda: RateLimiter("brave", 1.1),
    "crossref": lambda: RateLimiter("crossref", 0.05),  # 50/sec but conservative
    "openalex": lambda: RateLimiter("openalex", 0.11),  # 10/sec
    "arxiv": lambda: RateLimiter("arxiv", 3.0),
    "sep_fetch": lambda: RateLimiter("sep_fetch", 1.0),
    "iep_fetch": lambda: RateLimiter("iep_fetch", 1.0),
    "core": lambda: RateLimiter("core", 2.0),  # 5 req/10 sec = 1 req/2 sec
}


def get_limiter(api_name: str) -> RateLimiter:
    """
    Get a pre-configured rate limiter for the specified API.

    Args:
        api_name: One of: semantic_scholar, brave, crossref, openalex, arxiv, sep_fetch, iep_fetch, core

    Returns:
        Configured RateLimiter instance

    Raises:
        ValueError: If api_name is not recognized
    """
    if api_name not in LIMITERS:
        valid = ", ".join(sorted(LIMITERS.keys()))
        raise ValueError(f"Unknown API: {api_name}. Valid options: {valid}")
    return LIMITERS[api_name]()


def list_active_limiters() -> list[str]:
    """
    List all lock files currently in use.

    Returns:
        List of API names with active lock files
    """
    lock_dir = Path(tempfile.gettempdir()) / "philosophy_research_ratelimits"
    if not lock_dir.exists():
        return []

    active = []
    for lock_file in lock_dir.glob(".ratelimit_*.lock"):
        api_name = lock_file.stem.replace(".ratelimit_", "")
        active.append(api_name)
    return sorted(active)


def clear_all_limiters() -> int:
    """
    Remove all lock files. Useful for testing or resetting state.

    Returns:
        Number of lock files removed
    """
    lock_dir = Path(tempfile.gettempdir()) / "philosophy_research_ratelimits"
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
