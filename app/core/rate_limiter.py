"""Rate limiting utilities for resource-intensive endpoints."""

from __future__ import annotations

import hashlib
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import ClassVar, Protocol

import redis
from fastapi import HTTPException, Request, status

from app.core.config import settings


@dataclass(slots=True)
class RateLimitConfig:
    """Configuration for a rate limit bucket."""

    max_requests: int
    window_seconds: int


class _RateLimitBackend(Protocol):
    def is_allowed(self, key: str, config: RateLimitConfig) -> bool: ...

    def get_remaining(self, key: str, config: RateLimitConfig) -> int: ...

    def get_reset_time(self, key: str, config: RateLimitConfig) -> float: ...


class _MemoryRateLimitBackend:
    """Thread-safe in-memory sliding-window limiter for local dev and tests."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._bucket_lock = Lock()
        self._call_count = 0

    def _cleanup(self, max_age_seconds: float = 120.0) -> None:
        now = time.time()
        cutoff = now - max_age_seconds
        stale_keys = [k for k, v in self._buckets.items() if not v or max(v) < cutoff]
        for key in stale_keys:
            del self._buckets[key]

    def is_allowed(self, key: str, config: RateLimitConfig) -> bool:
        now = time.time()
        window_start = now - config.window_seconds
        with self._bucket_lock:
            self._call_count += 1
            if self._call_count % settings.rate_limit_cleanup_interval == 0:
                self._cleanup()
            timestamps = [ts for ts in self._buckets[key] if ts > window_start]
            if len(timestamps) >= config.max_requests:
                self._buckets[key] = timestamps
                return False
            timestamps.append(now)
            self._buckets[key] = timestamps
            return True

    def get_remaining(self, key: str, config: RateLimitConfig) -> int:
        now = time.time()
        window_start = now - config.window_seconds
        with self._bucket_lock:
            timestamps = [ts for ts in self._buckets[key] if ts > window_start]
            return max(0, config.max_requests - len(timestamps))

    def get_reset_time(self, key: str, config: RateLimitConfig) -> float:
        now = time.time()
        window_start = now - config.window_seconds
        with self._bucket_lock:
            timestamps = [ts for ts in self._buckets[key] if ts > window_start]
            if not timestamps:
                return now
            return min(timestamps) + config.window_seconds


class _RedisRateLimitBackend:
    """Redis-backed sliding-window limiter for production deployments."""

    _SCRIPT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local member = ARGV[4]
local cutoff = now_ms - window_ms

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count >= max_requests then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local reset_at = now_ms
  if oldest[2] ~= nil then
    reset_at = tonumber(oldest[2]) + window_ms
  end
  return {0, max_requests - count, reset_at}
end

redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms)
count = redis.call('ZCARD', key)
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local reset_at = now_ms + window_ms
if oldest[2] ~= nil then
  reset_at = tonumber(oldest[2]) + window_ms
end
return {1, max_requests - count, reset_at}
"""

    def __init__(self) -> None:
        self._client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def _bucket_key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"vigilweave:ratelimit:{digest}"

    def _run(
        self, key: str, config: RateLimitConfig, *, add_request: bool
    ) -> tuple[bool, int, float]:
        bucket_key = self._bucket_key(key)
        now_ms = int(time.time() * 1000)
        member = uuid.uuid4().hex if add_request else "__probe__"

        if add_request:
            allowed, remaining, reset_at_ms = self._client.eval(
                self._SCRIPT,
                1,
                bucket_key,
                now_ms,
                config.window_seconds * 1000,
                config.max_requests,
                member,
            )
            return bool(int(allowed)), int(remaining), float(reset_at_ms) / 1000.0

        self._client.zremrangebyscore(bucket_key, "-inf", now_ms - config.window_seconds * 1000)
        count = int(self._client.zcard(bucket_key))
        oldest = self._client.zrange(bucket_key, 0, 0, withscores=True)
        reset_at = float(oldest[0][1]) / 1000.0 + config.window_seconds if oldest else time.time()
        return count < config.max_requests, max(0, config.max_requests - count), reset_at

    def is_allowed(self, key: str, config: RateLimitConfig) -> bool:
        allowed, _, _ = self._run(key, config, add_request=True)
        return allowed

    def get_remaining(self, key: str, config: RateLimitConfig) -> int:
        _, remaining, _ = self._run(key, config, add_request=False)
        return remaining

    def get_reset_time(self, key: str, config: RateLimitConfig) -> float:
        _, _, reset_at = self._run(key, config, add_request=False)
        return reset_at


class RateLimiter:
    """Singleton rate limiter that uses Redis in real deployments."""

    _instance: ClassVar[RateLimiter | None] = None
    _lock: ClassVar[Lock] = Lock()
    _initialized: ClassVar[bool] = False

    def __new__(cls) -> RateLimiter:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._backend = self._build_backend()

    def _build_backend(self) -> _RateLimitBackend:
        if settings.environment in {"development", "test"}:
            return _MemoryRateLimitBackend()

        try:
            backend = _RedisRateLimitBackend()
            backend.get_remaining(
                "startup-probe", RateLimitConfig(max_requests=1, window_seconds=1)
            )
            return backend
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Redis-backed rate limiting is required outside development/test environments"
            ) from exc

    def is_allowed(self, key: str, config: RateLimitConfig) -> bool:
        return self._backend.is_allowed(key, config)

    def get_remaining(self, key: str, config: RateLimitConfig) -> int:
        return self._backend.get_remaining(key, config)

    def get_reset_time(self, key: str, config: RateLimitConfig) -> float:
        return self._backend.get_reset_time(key, config)


PDF_EXPORT_RATE_LIMIT = RateLimitConfig(
    max_requests=settings.rate_limit_pdf_max_requests,
    window_seconds=settings.rate_limit_pdf_window_seconds,
)
CSV_EXPORT_RATE_LIMIT = RateLimitConfig(
    max_requests=settings.rate_limit_csv_max_requests,
    window_seconds=settings.rate_limit_csv_window_seconds,
)
AUTH_ENDPOINT_RATE_LIMIT = RateLimitConfig(
    max_requests=settings.rate_limit_auth_max_requests,
    window_seconds=settings.rate_limit_auth_window_seconds,
)
WEBHOOK_RATE_LIMIT = RateLimitConfig(
    max_requests=settings.rate_limit_webhook_max_requests,
    window_seconds=settings.rate_limit_webhook_window_seconds,
)


def check_rate_limit(
    request: Request,
    limit_config: RateLimitConfig,
    resource_name: str = "resource",
) -> None:
    """Check rate limit and raise HTTPException if exceeded."""

    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{request.url.path}"
    limiter = RateLimiter()

    if not limiter.is_allowed(key, limit_config):
        reset_time = limiter.get_reset_time(key, limit_config)
        retry_after = int(reset_time - time.time())

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {resource_name}. Please try again later.",
            headers={
                "X-RateLimit-Limit": str(limit_config.max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time)),
                "Retry-After": str(max(1, retry_after)),
            },
        )
