"""
Tests for the rate_limiter module.

Tests cover:
- Basic rate limiting functionality
- Slot reservation (race condition fix)
- File locking behavior
- Exponential backoff with Retry-After support
- Auth-aware rate limiting
- Multi-API support
- parse_retry_after utility
"""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "philosophy-research" / "scripts"))

from rate_limiter import (
    RateLimiter,
    ExponentialBackoff,
    get_limiter,
    list_active_limiters,
    clear_all_limiters,
    parse_retry_after,
    LIMITERS,
)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_init_creates_lock_dir(self):
        """Rate limiter should create lock directory if it doesn't exist."""
        limiter = RateLimiter("test_api", 0.1)
        assert limiter.LOCK_DIR.exists()

    def test_first_request_no_wait(self):
        """First request should not wait."""
        limiter = RateLimiter("test_first", 1.0)
        limiter.reset()  # Ensure clean state

        wait_time = limiter.wait()
        assert wait_time == 0.0

    def test_subsequent_request_waits(self):
        """Subsequent request should wait for min_interval."""
        limiter = RateLimiter("test_wait", 0.2)
        limiter.reset()

        # First request
        limiter.wait_and_record()

        # Second request should wait
        wait_time = limiter.wait()

        assert wait_time > 0

    def test_record_updates_lock_file(self):
        """Record should update the lock file with current time."""
        limiter = RateLimiter("test_record", 0.1)
        limiter.reset()

        before = time.time()
        limiter.record()
        after = time.time()

        # Read lock file
        content = limiter.lock_file.read_text().strip()
        recorded_time = float(content)

        assert before <= recorded_time <= after

    def test_reset_removes_lock_file(self):
        """Reset should remove the lock file."""
        limiter = RateLimiter("test_reset", 0.1)
        limiter.record()  # Create lock file
        assert limiter.lock_file.exists()

        limiter.reset()
        assert not limiter.lock_file.exists()

    def test_wait_and_record_convenience(self):
        """wait_and_record should call both methods."""
        limiter = RateLimiter("test_convenience", 0.1)
        limiter.reset()

        wait_time = limiter.wait_and_record()
        assert wait_time == 0.0
        assert limiter.lock_file.exists()

    def test_last_wait_time_property(self):
        """last_wait_time should reflect most recent wait."""
        limiter = RateLimiter("test_last_wait", 0.1)
        limiter.reset()

        assert limiter.last_wait_time is None

        limiter.wait()
        assert limiter.last_wait_time == 0.0

        limiter.record()
        limiter.wait()
        assert limiter.last_wait_time > 0


class TestSlotReservation:
    """Tests for the slot reservation mechanism (race condition fix)."""

    def test_wait_writes_projected_timestamp(self):
        """wait() should write projected timestamp to lock file without record()."""
        limiter = RateLimiter("test_slot_write", 0.5)
        limiter.reset()

        before = time.time()
        limiter.wait()
        after = time.time()

        # Lock file should exist and contain a timestamp
        assert limiter.lock_file.exists()
        content = limiter.lock_file.read_text().strip()
        recorded_time = float(content)

        # Projected time should be approximately now (first call, no wait)
        assert before <= recorded_time <= after

    def test_consecutive_waits_without_record(self):
        """Two wait() calls without record() should queue properly."""
        limiter = RateLimiter("test_slot_queue", 0.2)
        limiter.reset()

        # First call: no wait, writes projected_time ≈ now
        limiter.wait()

        # Second call: should see the first projected_time and wait
        wait_time = limiter.wait()

        assert wait_time > 0

    def test_record_does_not_overwrite_later_reservation(self):
        """record() should not overwrite a timestamp that is later than now."""
        limiter = RateLimiter("test_slot_nooverwrite", 0.5)
        limiter.reset()

        # First wait reserves a slot at ≈ now
        limiter.wait()

        # Second wait reserves a slot at ≈ now + 0.5
        limiter.wait()

        # Read the file — should contain a future timestamp
        content_before = float(limiter.lock_file.read_text().strip())

        # record() from the first caller's perspective (now < reserved future time)
        # Should NOT overwrite since now < existing
        limiter.record()

        content_after = float(limiter.lock_file.read_text().strip())

        # If the reserved timestamp was in the future relative to record()'s time.time(),
        # record() should not have overwritten it
        assert content_after >= content_before

    def test_staleness_guard_ignores_far_future_timestamps(self):
        """Timestamps far in the future should be treated as stale."""
        limiter = RateLimiter("test_slot_stale", 0.2)
        limiter.reset()

        # Write a timestamp 30 seconds in the future (simulating a crash)
        with open(limiter.lock_file, "w") as f:
            f.write(str(time.time() + 30))

        # wait() should ignore the stale timestamp (30s > 10 * 0.2s = 2s)
        wait_time = limiter.wait()
        assert wait_time == 0.0

    def test_staleness_guard_allows_normal_queue(self):
        """Timestamps within 10x interval should be respected (normal queuing)."""
        limiter = RateLimiter("test_slot_normal_queue", 0.2)
        limiter.reset()

        # Write a timestamp slightly in the future (within 10x interval)
        future_time = time.time() + 0.3  # 0.3s < 10 * 0.2s = 2.0s
        with open(limiter.lock_file, "w") as f:
            f.write(str(future_time))

        # wait() should respect this and wait
        wait_time = limiter.wait()
        assert wait_time > 0


class TestExponentialBackoff:
    """Tests for the ExponentialBackoff class."""

    def test_init_defaults(self):
        """Default initialization should have expected values."""
        backoff = ExponentialBackoff()
        assert backoff.max_attempts == 5
        assert backoff.base_delay == 1.0
        assert backoff.max_delay == 60.0

    def test_get_delay_exponential(self):
        """Delay should increase exponentially."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=100.0)

        assert backoff.get_delay(0) == 1.0
        assert backoff.get_delay(1) == 2.0
        assert backoff.get_delay(2) == 4.0
        assert backoff.get_delay(3) == 8.0

    def test_get_delay_capped_at_max(self):
        """Delay should not exceed max_delay."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=5.0)

        assert backoff.get_delay(10) == 5.0

    def test_wait_returns_false_on_max_attempts(self):
        """wait() should return False when max attempts reached."""
        backoff = ExponentialBackoff(max_attempts=3)

        assert backoff.wait(0) is True
        assert backoff.wait(1) is True
        assert backoff.wait(2) is False  # max_attempts - 1

    @patch("time.sleep")
    def test_wait_sleeps_with_jitter(self, mock_sleep):
        """wait() should sleep with jitter added."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=100.0)

        backoff.wait(0)

        # Should have slept between 1.0 and 2.0 (base + jitter)
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert 1.0 <= sleep_time <= 2.0

    def test_last_delay_property(self):
        """last_delay should reflect most recent wait delay."""
        backoff = ExponentialBackoff()
        assert backoff.last_delay is None

        with patch("time.sleep"):
            backoff.wait(0)

        assert backoff.last_delay is not None
        assert backoff.last_delay >= 1.0

    @patch("time.sleep")
    def test_retry_after_overrides_when_larger(self, mock_sleep):
        """retry_after should override computed delay when larger."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=100.0)

        # Attempt 0: base delay is ~1.0-2.0, retry_after=10.0 is larger
        backoff.wait(0, retry_after=10.0)

        sleep_time = mock_sleep.call_args[0][0]
        assert sleep_time == 10.0

    @patch("time.sleep")
    def test_retry_after_ignored_when_smaller(self, mock_sleep):
        """retry_after should be ignored when smaller than computed delay."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=100.0)

        # Attempt 0: base delay is ~1.0-2.0, retry_after=0.1 is smaller
        backoff.wait(0, retry_after=0.1)

        sleep_time = mock_sleep.call_args[0][0]
        assert sleep_time >= 1.0  # Should use computed delay, not retry_after

    @patch("time.sleep")
    def test_retry_after_none_has_no_effect(self, mock_sleep):
        """retry_after=None should not change behavior."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=100.0)

        backoff.wait(0, retry_after=None)

        sleep_time = mock_sleep.call_args[0][0]
        assert 1.0 <= sleep_time <= 2.0


class TestGetLimiter:
    """Tests for the get_limiter factory function."""

    def test_returns_configured_limiter(self):
        """get_limiter should return properly configured limiter."""
        limiter = get_limiter("semantic_scholar")

        assert isinstance(limiter, RateLimiter)
        assert limiter.api_name == "semantic_scholar"
        assert limiter.min_interval == 1.1

    def test_all_apis_have_limiters(self):
        """All configured APIs should return valid limiters."""
        for api_name in LIMITERS.keys():
            limiter = get_limiter(api_name)
            assert isinstance(limiter, RateLimiter)
            assert limiter.api_name == api_name

    def test_unknown_api_raises(self):
        """Unknown API name should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_limiter("unknown_api")

        assert "Unknown API" in str(exc_info.value)
        assert "unknown_api" in str(exc_info.value)

    def test_each_call_returns_fresh_instance(self):
        """Each call should return a new limiter instance."""
        limiter1 = get_limiter("semantic_scholar")
        limiter2 = get_limiter("semantic_scholar")

        assert limiter1 is not limiter2


class TestAuthAwareLimiter:
    """Tests for auth-aware rate limiter configuration."""

    def test_default_returns_authenticated_interval(self):
        """get_limiter without authenticated param returns authenticated interval."""
        limiter = get_limiter("semantic_scholar")
        assert limiter.min_interval == 1.1
        assert limiter.api_name == "semantic_scholar"

    def test_authenticated_true_returns_authenticated_interval(self):
        """authenticated=True returns same as default."""
        limiter = get_limiter("semantic_scholar", authenticated=True)
        assert limiter.min_interval == 1.1
        assert limiter.api_name == "semantic_scholar"

    def test_authenticated_false_returns_unauthenticated_interval(self):
        """authenticated=False returns slower unauthenticated interval."""
        limiter = get_limiter("semantic_scholar", authenticated=False)
        assert limiter.min_interval == 3.0
        assert limiter.api_name == "semantic_scholar_unauth"

    def test_auth_and_unauth_use_different_lock_files(self):
        """Auth and unauth limiters should use separate lock files."""
        auth_limiter = get_limiter("semantic_scholar", authenticated=True)
        unauth_limiter = get_limiter("semantic_scholar", authenticated=False)

        assert auth_limiter.lock_file != unauth_limiter.lock_file

    def test_authenticated_false_ignored_for_apis_without_unauth(self):
        """authenticated=False for APIs without an unauth variant returns default."""
        limiter = get_limiter("brave", authenticated=False)
        assert limiter.api_name == "brave"
        assert limiter.min_interval == 1.5

    def test_unknown_api_with_authenticated_false_raises(self):
        """Unknown API should raise even with authenticated=False."""
        with pytest.raises(ValueError):
            get_limiter("unknown_api", authenticated=False)

    def test_error_message_excludes_unauth_variants(self):
        """Error message for unknown API should not list _unauth variants."""
        with pytest.raises(ValueError) as exc_info:
            get_limiter("unknown_api")

        error_msg = str(exc_info.value)
        assert "semantic_scholar_unauth" not in error_msg
        assert "semantic_scholar" in error_msg


class TestParseRetryAfter:
    """Tests for the parse_retry_after utility."""

    def test_none_returns_none(self):
        assert parse_retry_after(None) is None

    def test_integer_string(self):
        assert parse_retry_after("120") == 120.0

    def test_float_string(self):
        assert parse_retry_after("3.5") == 3.5

    def test_zero(self):
        assert parse_retry_after("0") == 0.0

    def test_invalid_string_returns_none(self):
        assert parse_retry_after("not-a-number") is None

    def test_date_string_returns_none(self):
        """HTTP-date Retry-After values are not supported (returns None)."""
        assert parse_retry_after("Wed, 21 Oct 2025 07:28:00 GMT") is None

    def test_empty_string_returns_none(self):
        assert parse_retry_after("") is None


class TestLimiterManagement:
    """Tests for limiter listing and clearing."""

    def test_list_active_limiters_empty(self):
        """list_active_limiters should return empty list when no limiters active."""
        clear_all_limiters()
        active = list_active_limiters()
        assert active == []

    def test_list_active_limiters_shows_used(self):
        """list_active_limiters should show limiters that have been used."""
        clear_all_limiters()

        limiter = get_limiter("semantic_scholar")
        limiter.record()

        active = list_active_limiters()
        assert "semantic_scholar" in active

    def test_clear_all_limiters(self):
        """clear_all_limiters should remove all lock files."""
        # Create some limiters
        get_limiter("semantic_scholar").record()
        get_limiter("brave").record()

        count = clear_all_limiters()
        assert count >= 2

        active = list_active_limiters()
        assert len(active) == 0


class TestConcurrentAccess:
    """Tests for concurrent access behavior."""

    def test_multiple_limiters_independent(self):
        """Different API limiters should be independent."""
        limiter1 = get_limiter("semantic_scholar")
        limiter2 = get_limiter("brave")

        limiter1.reset()
        limiter2.reset()

        # Record on limiter1
        limiter1.wait_and_record()

        # limiter2 should not wait
        wait_time = limiter2.wait()
        assert wait_time == 0.0
