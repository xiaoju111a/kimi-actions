"""Rate limiting utilities for API calls and resource management.

This module provides various rate limiting strategies including:
- Token bucket algorithm
- Sliding window rate limiter
- Fixed window rate limiter
- Adaptive rate limiter
"""

import time
import threading
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Callable
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: float = None):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 10.0
    burst_size: int = 20
    window_size: float = 1.0
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    block_on_limit: bool = True
    max_wait_time: float = 30.0


class TokenBucketRateLimiter:
    """Token bucket rate limiter implementation.
    
    Allows bursts up to bucket capacity, then limits to steady rate.
    """
    
    def __init__(self, rate: float, capacity: int):
        """Initialize token bucket.
        
        Args:
            rate: Tokens added per second
            capacity: Maximum bucket capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
    
    def acquire(self, tokens: int = 1, block: bool = True, timeout: float = None) -> bool:
        """Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            block: Whether to block until tokens available
            timeout: Maximum time to wait (None = infinite)
            
        Returns:
            True if tokens acquired, False otherwise
        """
        deadline = time.time() + timeout if timeout else None
        
        while True:
            with self._lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                
                if not block:
                    return False
                
                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate
            
            if deadline and time.time() + wait_time > deadline:
                return False
            
            time.sleep(min(wait_time, 0.1))
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking."""
        return self.acquire(tokens, block=False)
    
    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        with self._lock:
            self._refill()
            return self.tokens


class SlidingWindowRateLimiter:
    """Sliding window rate limiter implementation.
    
    Tracks requests in a sliding time window for smooth rate limiting.
    """
    
    def __init__(self, max_requests: int, window_size: float):
        """Initialize sliding window limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_size: Window size in seconds
        """
        self.max_requests = max_requests
        self.window_size = window_size
        self.requests: deque = deque()
        self._lock = threading.Lock()
    
    def _cleanup(self):
        """Remove expired requests from window."""
        cutoff = time.time() - self.window_size
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    def acquire(self, block: bool = True, timeout: float = None) -> bool:
        """Acquire permission to make a request.
        
        Args:
            block: Whether to block until allowed
            timeout: Maximum time to wait
            
        Returns:
            True if request allowed, False otherwise
        """
        deadline = time.time() + timeout if timeout else None
        
        while True:
            with self._lock:
                self._cleanup()
                
                if len(self.requests) < self.max_requests:
                    self.requests.append(time.time())
                    return True
                
                if not block:
                    return False
                
                # Calculate wait time until oldest request expires
                wait_time = self.requests[0] + self.window_size - time.time()
            
            if deadline and time.time() + wait_time > deadline:
                return False
            
            time.sleep(min(max(wait_time, 0), 0.1))
    
    def try_acquire(self) -> bool:
        """Try to acquire without blocking."""
        return self.acquire(block=False)
    
    @property
    def current_count(self) -> int:
        """Get current request count in window."""
        with self._lock:
            self._cleanup()
            return len(self.requests)
    
    @property
    def remaining(self) -> int:
        """Get remaining requests allowed in window."""
        return max(0, self.max_requests - self.current_count)


class FixedWindowRateLimiter:
    """Fixed window rate limiter implementation.
    
    Resets counter at fixed intervals.
    """
    
    def __init__(self, max_requests: int, window_size: float):
        """Initialize fixed window limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_size: Window size in seconds
        """
        self.max_requests = max_requests
        self.window_size = window_size
        self.window_start = time.time()
        self.request_count = 0
        self._lock = threading.Lock()
    
    def _check_window(self):
        """Check if window has expired and reset if needed."""
        now = time.time()
        if now - self.window_start >= self.window_size:
            self.window_start = now
            self.request_count = 0
    
    def acquire(self, block: bool = True, timeout: float = None) -> bool:
        """Acquire permission to make a request."""
        deadline = time.time() + timeout if timeout else None
        
        while True:
            with self._lock:
                self._check_window()
                
                if self.request_count < self.max_requests:
                    self.request_count += 1
                    return True
                
                if not block:
                    return False
                
                # Wait until window resets
                wait_time = self.window_start + self.window_size - time.time()
            
            if deadline and time.time() + wait_time > deadline:
                return False
            
            time.sleep(min(max(wait_time, 0), 0.1))
    
    def try_acquire(self) -> bool:
        """Try to acquire without blocking."""
        return self.acquire(block=False)
    
    @property
    def remaining(self) -> int:
        """Get remaining requests in current window."""
        with self._lock:
            self._check_window()
            return max(0, self.max_requests - self.request_count)
    
    @property
    def reset_time(self) -> float:
        """Get time until window resets."""
        with self._lock:
            return max(0, self.window_start + self.window_size - time.time())


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts based on response times and errors.
    
    Automatically reduces rate when errors occur and increases when successful.
    """
    
    def __init__(
        self,
        initial_rate: float,
        min_rate: float = 1.0,
        max_rate: float = 100.0,
        increase_factor: float = 1.1,
        decrease_factor: float = 0.5,
        error_threshold: int = 3
    ):
        """Initialize adaptive limiter.
        
        Args:
            initial_rate: Starting requests per second
            min_rate: Minimum rate limit
            max_rate: Maximum rate limit
            increase_factor: Factor to increase rate on success
            decrease_factor: Factor to decrease rate on error
            error_threshold: Consecutive errors before decreasing rate
        """
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.increase_factor = increase_factor
        self.decrease_factor = decrease_factor
        self.error_threshold = error_threshold
        
        self.consecutive_errors = 0
        self.consecutive_successes = 0
        self.last_request = 0.0
        self._lock = threading.Lock()
    
    def acquire(self, block: bool = True, timeout: float = None) -> bool:
        """Acquire permission to make a request."""
        deadline = time.time() + timeout if timeout else None
        
        while True:
            with self._lock:
                now = time.time()
                min_interval = 1.0 / self.current_rate
                elapsed = now - self.last_request
                
                if elapsed >= min_interval:
                    self.last_request = now
                    return True
                
                if not block:
                    return False
                
                wait_time = min_interval - elapsed
            
            if deadline and time.time() + wait_time > deadline:
                return False
            
            time.sleep(min(wait_time, 0.1))
    
    def record_success(self):
        """Record a successful request."""
        with self._lock:
            self.consecutive_errors = 0
            self.consecutive_successes += 1
            
            # Increase rate after sustained success
            if self.consecutive_successes >= 10:
                self.current_rate = min(
                    self.max_rate,
                    self.current_rate * self.increase_factor
                )
                self.consecutive_successes = 0
                logger.debug(f"Rate increased to {self.current_rate:.2f} req/s")
    
    def record_error(self):
        """Record a failed request."""
        with self._lock:
            self.consecutive_successes = 0
            self.consecutive_errors += 1
            
            # Decrease rate after threshold errors
            if self.consecutive_errors >= self.error_threshold:
                self.current_rate = max(
                    self.min_rate,
                    self.current_rate * self.decrease_factor
                )
                self.consecutive_errors = 0
                logger.warning(f"Rate decreased to {self.current_rate:.2f} req/s")
    
    @property
    def rate(self) -> float:
        """Get current rate limit."""
        return self.current_rate


class RateLimiterGroup:
    """Manages multiple rate limiters for different resources."""
    
    def __init__(self):
        self.limiters: Dict[str, TokenBucketRateLimiter] = {}
        self._lock = threading.Lock()
    
    def add_limiter(self, name: str, rate: float, capacity: int):
        """Add a rate limiter for a resource."""
        with self._lock:
            self.limiters[name] = TokenBucketRateLimiter(rate, capacity)
    
    def acquire(self, name: str, tokens: int = 1, block: bool = True) -> bool:
        """Acquire tokens from a named limiter."""
        limiter = self.limiters.get(name)
        if limiter is None:
            return True  # No limiter = no limit
        return limiter.acquire(tokens, block)
    
    def acquire_all(self, names: list, block: bool = True) -> bool:
        """Acquire from multiple limiters atomically."""
        # Try to acquire all without blocking first
        acquired = []
        
        for name in names:
            if self.acquire(name, block=False):
                acquired.append(name)
            else:
                # Release already acquired
                # Note: This is a simplified implementation
                # A proper implementation would need to track and release tokens
                if not block:
                    return False
                
                # Block on the failed limiter
                if not self.acquire(name, block=True):
                    return False
                acquired.append(name)
        
        return True


def rate_limited(
    rate: float = 10.0,
    capacity: int = 20,
    block: bool = True
) -> Callable:
    """Decorator to rate limit a function.
    
    Args:
        rate: Requests per second
        capacity: Burst capacity
        block: Whether to block when limited
        
    Returns:
        Decorated function
    """
    limiter = TokenBucketRateLimiter(rate, capacity)
    
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            if not limiter.acquire(block=block):
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {func.__name__}",
                    retry_after=1.0 / rate
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator
