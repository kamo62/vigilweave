"""Tests for rate limiting functionality."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from app.core.rate_limiter import (
    CSV_EXPORT_RATE_LIMIT,
    PDF_EXPORT_RATE_LIMIT,
    RateLimitConfig,
    RateLimiter,
    check_rate_limit,
)


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    def setup_method(self) -> None:
        """Reset rate limiter singleton between tests."""
        RateLimiter._instance = None
        RateLimiter._initialized = False

    def test_singleton_pattern(self) -> None:
        """Test that RateLimiter is a singleton."""
        limiter1 = RateLimiter()
        limiter2 = RateLimiter()
        assert limiter1 is limiter2

    def test_is_allowed_under_limit(self) -> None:
        """Test that requests are allowed when under the limit."""
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=5, window_seconds=60)

        # First 5 requests should be allowed
        for _ in range(5):
            assert limiter.is_allowed("test-key", config) is True

    def test_is_allowed_over_limit(self) -> None:
        """Test that requests are denied when over the limit."""
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=3, window_seconds=60)

        # First 3 requests should be allowed
        for _ in range(3):
            assert limiter.is_allowed("test-key", config) is True

        # 4th request should be denied
        assert limiter.is_allowed("test-key", config) is False

    def test_window_expiration(self) -> None:
        """Test that rate limit resets after window expires."""
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=2, window_seconds=1)

        # Use up the limit
        assert limiter.is_allowed("test-key", config) is True
        assert limiter.is_allowed("test-key", config) is True
        assert limiter.is_allowed("test-key", config) is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.is_allowed("test-key", config) is True

    def test_isolated_buckets(self) -> None:
        """Test that different keys have isolated rate limit buckets."""
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=2, window_seconds=60)

        # Use up limit for key1
        assert limiter.is_allowed("key1", config) is True
        assert limiter.is_allowed("key1", config) is True
        assert limiter.is_allowed("key1", config) is False

        # key2 should still have its own limit
        assert limiter.is_allowed("key2", config) is True
        assert limiter.is_allowed("key2", config) is True
        assert limiter.is_allowed("key2", config) is False

    def test_get_remaining(self) -> None:
        """Test getting remaining requests in window."""
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=5, window_seconds=60)

        assert limiter.get_remaining("test-key", config) == 5

        limiter.is_allowed("test-key", config)
        assert limiter.get_remaining("test-key", config) == 4

        # Use up all requests
        for _ in range(4):
            limiter.is_allowed("test-key", config)
        assert limiter.get_remaining("test-key", config) == 0

    def test_get_reset_time(self) -> None:
        """Test getting reset time for rate limit."""
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=5, window_seconds=60)

        now = time.time()
        reset_time = limiter.get_reset_time("test-key", config)
        # When no requests made, should return current time
        assert abs(reset_time - now) < 1

        # Make a request
        limiter.is_allowed("test-key", config)
        reset_time = limiter.get_reset_time("test-key", config)
        # Should be approximately window_seconds from now
        assert reset_time > now
        assert reset_time <= now + config.window_seconds + 1

    def test_thread_safety(self) -> None:
        """Test that rate limiter is thread-safe."""
        import threading

        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=100, window_seconds=60)
        results: list[bool] = []

        def make_requests() -> None:
            for _ in range(10):
                results.append(limiter.is_allowed("thread-test", config))

        threads = [threading.Thread(target=make_requests) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All 50 requests should have been tracked
        assert len(results) == 50
        # First 100 should be allowed, but we only made 50
        assert all(results)


class TestCheckRateLimit:
    """Test suite for check_rate_limit function."""

    def setup_method(self) -> None:
        """Reset rate limiter singleton between tests."""
        RateLimiter._instance = None
        RateLimiter._initialized = False

    def test_check_rate_limit_allows(self) -> None:
        """Test that check_rate_limit allows requests under limit."""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.url.path = "/test"

        config = RateLimitConfig(max_requests=5, window_seconds=60)

        # Should not raise
        check_rate_limit(request, config, resource_name="test resource")

    def test_check_rate_limit_denies(self) -> None:
        """Test that check_rate_limit raises HTTPException when over limit."""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.url.path = "/test"

        config = RateLimitConfig(max_requests=1, window_seconds=60)

        # First request should pass
        check_rate_limit(request, config, resource_name="test resource")

        # Second request should fail
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(request, config, resource_name="test resource")

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        assert "test resource" in exc_info.value.detail

        # Check headers
        headers = exc_info.value.headers
        assert headers["X-RateLimit-Limit"] == "1"
        assert headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) >= 1

    def test_check_rate_limit_different_ips(self) -> None:
        """Test that different IPs have separate rate limits."""
        config = RateLimitConfig(max_requests=1, window_seconds=60)

        # Request from IP 1
        request1 = MagicMock(spec=Request)
        request1.client.host = "127.0.0.1"
        request1.url.path = "/test"
        check_rate_limit(request1, config)

        # Request from IP 2 should be allowed
        request2 = MagicMock(spec=Request)
        request2.client.host = "127.0.0.2"
        request2.url.path = "/test"
        check_rate_limit(request2, config)  # Should not raise

    def test_check_rate_limit_different_paths(self) -> None:
        """Test that different paths have separate rate limits."""
        config = RateLimitConfig(max_requests=1, window_seconds=60)

        # Request to path 1
        request1 = MagicMock(spec=Request)
        request1.client.host = "127.0.0.1"
        request1.url.path = "/path1"
        check_rate_limit(request1, config)

        # Request to path 2 should be allowed
        request2 = MagicMock(spec=Request)
        request2.client.host = "127.0.0.1"
        request2.url.path = "/path2"
        check_rate_limit(request2, config)  # Should not raise


class TestDefaultRateLimits:
    """Test default rate limit configurations."""

    def test_pdf_export_rate_limit(self) -> None:
        """Test PDF export rate limit configuration."""
        assert PDF_EXPORT_RATE_LIMIT.max_requests == 10
        assert PDF_EXPORT_RATE_LIMIT.window_seconds == 60

    def test_csv_export_rate_limit(self) -> None:
        """Test CSV export rate limit configuration."""
        assert CSV_EXPORT_RATE_LIMIT.max_requests == 30
        assert CSV_EXPORT_RATE_LIMIT.window_seconds == 60
