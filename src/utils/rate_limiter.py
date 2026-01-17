"""Rate limiting utilities for API calls.

This module provides rate limiting functionality to prevent
exceeding API rate limits when making requests.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Deque, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 10.0
    requests_per_minute: float = 600.0
    burst_size: int = 20
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    retry_after_header: bool = True
    max_retries: int = 3
    backoff_factor: float = 2.0


@dataclass
class RateLimitState:
    """Current state of rate limiter."""
    request_times: Deque[float] = field(default_factory=deque)
    tokens: float = 0.0
    last_update: float = field(default_factory=time.time)
    total_requests: int = 0
    throttled_requests: int = 0
    last_throttle_time: Optional[float] = None


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """Rate limiter with multiple strategies."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize the rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self.state = RateLimitState(tokens=self.config.burst_size)
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire permission to make a request.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if permission granted, False otherwise
        """
        async with self._lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return self._acquire_token_bucket(tokens)
            elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return self._acquire_sliding_window(tokens)
            elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                return self._acquire_fixed_window(tokens)
            else:
                return self._acquire_leaky_bucket(tokens)

    def _acquire_token_bucket(self, tokens: int) -> bool:
        """Token bucket rate limiting."""
        now = time.time()
        elapsed = now - self.state.last_update
        
        # Refill tokens
        refill = elapsed * self.config.requests_per_second
        self.state.tokens = min(
            self.config.burst_size,
            self.state.tokens + refill
        )
        self.state.last_update = now

        if self.state.tokens >= tokens:
            self.state.tokens -= tokens
            self.state.total_requests += 1
            return True

        self.state.throttled_requests += 1
        self.state.last_throttle_time = now
        return False

    def _acquire_sliding_window(self, tokens: int) -> bool:
        """Sliding window rate limiting."""
        now = time.time()
        window_start = now - 1.0  # 1 second window

        # Remove old requests
        while self.state.request_times and self.state.request_times[0] < window_start:
            self.state.request_times.popleft()

        if len(self.state.request_times) < self.config.requests_per_second:
            for _ in range(tokens):
                self.state.request_times.append(now)
            self.state.total_requests += 1
            return True

        self.state.throttled_requests += 1
        self.state.last_throttle_time = now
        return False

    def _acquire_fixed_window(self, tokens: int) -> bool:
        """Fixed window rate limiting."""
        now = time.time()
        window_start = int(now)  # Current second

        # Clear if new window
        if self.state.request_times and int(self.state.request_times[0]) < window_start:
            self.state.request_times.clear()

        if len(self.state.request_times) < self.config.requests_per_second:
            for _ in range(tokens):
                self.state.request_times.append(now)
            self.state.total_requests += 1
            return True

        self.state.throttled_requests += 1
        self.state.last_throttle_time = now
        return False

    def _acquire_leaky_bucket(self, tokens: int) -> bool:
        """Leaky bucket rate limiting."""
        now = time.time()
        elapsed = now - self.state.last_update

        # Leak tokens
        leaked = elapsed * self.config.requests_per_second
        self.state.tokens = max(0, self.state.tokens - leaked)
        self.state.last_update = now

        if self.state.tokens + tokens <= self.config.burst_size:
            self.state.tokens += tokens
            self.state.total_requests += 1
            return True

        self.state.throttled_requests += 1
        self.state.last_throttle_time = now
        return False

    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """Wait until rate limit allows, then acquire.
        
        Args:
            tokens: Number of tokens to acquire
        """
        while not await self.acquire(tokens):
            wait_time = self.get_wait_time()
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

    def get_wait_time(self) -> float:
        """Get estimated wait time until next request allowed."""
        if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            if self.state.tokens >= 1:
                return 0.0
            return (1 - self.state.tokens) / self.config.requests_per_second
        else:
            return 1.0 / self.config.requests_per_second

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "total_requests": self.state.total_requests,
            "throttled_requests": self.state.throttled_requests,
            "throttle_rate": (
                self.state.throttled_requests / max(1, self.state.total_requests)
            ),
            "current_tokens": self.state.tokens,
            "last_throttle": self.state.last_throttle_time,
        }

    def reset(self) -> None:
        """Reset the rate limiter state."""
        self.state = RateLimitState(tokens=self.config.burst_size)


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on API responses."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        super().__init__(config)
        self._success_streak = 0
        self._failure_streak = 0
        self._original_rate = self.config.requests_per_second

    def record_success(self) -> None:
        """Record a successful request."""
        self._success_streak += 1
        self._failure_streak = 0

        # Gradually increase rate after successes
        if self._success_streak >= 10:
            self.config.requests_per_second = min(
                self._original_rate,
                self.config.requests_per_second * 1.1
            )
            self._success_streak = 0

    def record_failure(self, retry_after: Optional[float] = None) -> None:
        """Record a failed request (rate limited)."""
        self._failure_streak += 1
        self._success_streak = 0

        # Reduce rate on failures
        self.config.requests_per_second *= 0.5

        if retry_after:
            logger.info(f"Rate limited, retry after {retry_after}s")

    def record_response(self, status_code: int, headers: Dict[str, str]) -> None:
        """Record API response and adjust rate accordingly."""
        if status_code == 429:  # Too Many Requests
            retry_after = headers.get("Retry-After")
            if retry_after:
                try:
                    self.record_failure(float(retry_after))
                except ValueError:
                    self.record_failure()
            else:
                self.record_failure()
        elif 200 <= status_code < 300:
            self.record_success()


class RateLimiterPool:
    """Pool of rate limiters for different endpoints."""

    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        """Initialize the rate limiter pool.
        
        Args:
            default_config: Default configuration for new limiters
        """
        self._limiters: Dict[str, RateLimiter] = {}
        self._default_config = default_config or RateLimitConfig()

    def get(self, endpoint: str) -> RateLimiter:
        """Get or create a rate limiter for an endpoint."""
        if endpoint not in self._limiters:
            self._limiters[endpoint] = RateLimiter(self._default_config)
        return self._limiters[endpoint]

    def get_adaptive(self, endpoint: str) -> AdaptiveRateLimiter:
        """Get or create an adaptive rate limiter for an endpoint."""
        if endpoint not in self._limiters:
            self._limiters[endpoint] = AdaptiveRateLimiter(self._default_config)
        return self._limiters[endpoint]

    def reset_all(self) -> None:
        """Reset all rate limiters."""
        for limiter in self._limiters.values():
            limiter.reset()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all rate limiters."""
        return {
            endpoint: limiter.get_stats()
            for endpoint, limiter in self._limiters.items()
        }


# Decorator for rate limiting
def rate_limited(
    limiter: RateLimiter,
    tokens: int = 1
):
    """Decorator to rate limit a function.
    
    Args:
        limiter: Rate limiter to use
        tokens: Number of tokens per call
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            await limiter.wait_and_acquire(tokens)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
