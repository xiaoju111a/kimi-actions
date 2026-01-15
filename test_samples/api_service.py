"""
API Service Module - RESTful API client and server utilities.

This module provides a comprehensive HTTP client, request/response handling,
authentication, rate limiting, and API endpoint management.
"""

import time
import json
import hashlib
import hmac
import base64
import threading
import logging
from typing import Any, Dict, List, Optional, Callable, Union, TypeVar
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from functools import wraps
from collections import deque
from urllib.parse import urlencode, urlparse, parse_qs
import re

logger = logging.getLogger(__name__)

T = TypeVar('T')


class HttpMethod(Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ContentType(Enum):
    """Common content types."""
    JSON = "application/json"
    FORM = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    XML = "application/xml"
    TEXT = "text/plain"
    HTML = "text/html"


class AuthType(Enum):
    """Authentication types."""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    HMAC = "hmac"


@dataclass
class HttpRequest:
    """HTTP request representation."""
    method: HttpMethod
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Any] = None
    timeout: int = 30
    retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HttpResponse:
    """HTTP response representation."""
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    elapsed_time: float = 0.0
    request: Optional[HttpRequest] = None
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    @property
    def is_client_error(self) -> bool:
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        return 500 <= self.status_code < 600

    def json(self) -> Any:
        """Parse body as JSON."""
        if isinstance(self.body, str):
            return json.loads(self.body)
        return self.body


class ApiError(Exception):
    """Base API error."""
    def __init__(self, message: str, status_code: int = 0, response: Optional[HttpResponse] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(ApiError):
    """Rate limit exceeded error."""
    pass


class AuthenticationError(ApiError):
    """Authentication failed error."""
    pass


class TimeoutError(ApiError):
    """Request timeout error."""
    pass


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, requests_per_second: float = 10.0, burst_size: int = 20):
        self.rate = requests_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait_for_token(self, timeout: float = 30.0) -> bool:
        """Wait until a token is available."""
        start = time.time()
        while time.time() - start < timeout:
            if self.acquire():
                return True
            time.sleep(0.1)
        return False


class SlidingWindowRateLimiter:
    """Sliding window rate limiter."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: deque = deque()
        self._lock = threading.Lock()
    
    def acquire(self) -> bool:
        """Try to acquire a request slot."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Remove old requests
            while self._requests and self._requests[0] < cutoff:
                self._requests.popleft()
            
            if len(self._requests) < self.max_requests:
                self._requests.append(now)
                return True
            return False
    
    def remaining(self) -> int:
        """Get remaining requests in current window."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            while self._requests and self._requests[0] < cutoff:
                self._requests.popleft()
            return self.max_requests - len(self._requests)


class AuthProvider(ABC):
    """Abstract authentication provider."""
    
    @abstractmethod
    def authenticate(self, request: HttpRequest) -> HttpRequest:
        """Add authentication to request."""
        pass
    
    @abstractmethod
    def refresh(self) -> bool:
        """Refresh authentication credentials."""
        pass


class BasicAuthProvider(AuthProvider):
    """HTTP Basic authentication."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
    
    def authenticate(self, request: HttpRequest) -> HttpRequest:
        credentials = base64.b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode()
        request.headers["Authorization"] = f"Basic {credentials}"
        return request
    
    def refresh(self) -> bool:
        return True  # Basic auth doesn't need refresh


class BearerAuthProvider(AuthProvider):
    """Bearer token authentication."""
    
    def __init__(self, token: str, refresh_callback: Optional[Callable[[], str]] = None):
        self.token = token
        self.refresh_callback = refresh_callback
    
    def authenticate(self, request: HttpRequest) -> HttpRequest:
        request.headers["Authorization"] = f"Bearer {self.token}"
        return request
    
    def refresh(self) -> bool:
        if self.refresh_callback:
            try:
                self.token = self.refresh_callback()
                return True
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return False
        return False


class ApiKeyAuthProvider(AuthProvider):
    """API key authentication."""
    
    def __init__(self, api_key: str, header_name: str = "X-API-Key", 
                 in_query: bool = False, query_param: str = "api_key"):
        self.api_key = api_key
        self.header_name = header_name
        self.in_query = in_query
        self.query_param = query_param
    
    def authenticate(self, request: HttpRequest) -> HttpRequest:
        if self.in_query:
            request.params[self.query_param] = self.api_key
        else:
            request.headers[self.header_name] = self.api_key
        return request
    
    def refresh(self) -> bool:
        return True  # API keys don't need refresh


class HmacAuthProvider(AuthProvider):
    """HMAC signature authentication."""
    
    def __init__(self, api_key: str, secret_key: str, 
                 algorithm: str = "sha256"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def authenticate(self, request: HttpRequest) -> HttpRequest:
        timestamp = str(int(time.time()))
        
        # Create signature payload
        payload = f"{request.method.value}\n{request.url}\n{timestamp}"
        if request.body:
            payload += f"\n{json.dumps(request.body, sort_keys=True)}"
        
        # Generate signature
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            self.algorithm
        ).hexdigest()
        
        request.headers["X-API-Key"] = self.api_key
        request.headers["X-Timestamp"] = timestamp
        request.headers["X-Signature"] = signature
        
        return request
    
    def refresh(self) -> bool:
        return True


class RequestMiddleware(ABC):
    """Abstract request middleware."""
    
    @abstractmethod
    def process_request(self, request: HttpRequest) -> HttpRequest:
        """Process request before sending."""
        pass
    
    @abstractmethod
    def process_response(self, response: HttpResponse) -> HttpResponse:
        """Process response after receiving."""
        pass


class LoggingMiddleware(RequestMiddleware):
    """Logs requests and responses."""
    
    def __init__(self, log_body: bool = False):
        self.log_body = log_body
    
    def process_request(self, request: HttpRequest) -> HttpRequest:
        logger.info(f"Request: {request.method.value} {request.url}")
        if self.log_body and request.body:
            logger.debug(f"Request body: {request.body}")
        return request
    
    def process_response(self, response: HttpResponse) -> HttpResponse:
        logger.info(f"Response: {response.status_code} ({response.elapsed_time:.2f}s)")
        if self.log_body and response.body:
            logger.debug(f"Response body: {response.body}")
        return response


class RetryMiddleware(RequestMiddleware):
    """Retries failed requests."""
    
    def __init__(self, max_retries: int = 3, retry_statuses: List[int] = None,
                 backoff_factor: float = 1.0):
        self.max_retries = max_retries
        self.retry_statuses = retry_statuses or [500, 502, 503, 504]
        self.backoff_factor = backoff_factor
    
    def process_request(self, request: HttpRequest) -> HttpRequest:
        request.metadata["retry_count"] = 0
        return request
    
    def process_response(self, response: HttpResponse) -> HttpResponse:
        # Retry logic would be handled by the client
        return response
    
    def should_retry(self, response: HttpResponse) -> bool:
        """Check if request should be retried."""
        retry_count = response.request.metadata.get("retry_count", 0) if response.request else 0
        return (
            response.status_code in self.retry_statuses and
            retry_count < self.max_retries
        )
    
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff."""
        return self.backoff_factor * (2 ** attempt)


class CacheMiddleware(RequestMiddleware):
    """Caches GET responses."""
    
    def __init__(self, ttl: int = 300, max_size: int = 100):
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.Lock()
    
    def _cache_key(self, request: HttpRequest) -> str:
        """Generate cache key from request."""
        return hashlib.md5(
            f"{request.method.value}:{request.url}:{json.dumps(request.params, sort_keys=True)}".encode()
        ).hexdigest()
    
    def process_request(self, request: HttpRequest) -> HttpRequest:
        if request.method != HttpMethod.GET:
            return request
        
        key = self._cache_key(request)
        with self._lock:
            if key in self._cache:
                cached_response, cached_time = self._cache[key]
                if time.time() - cached_time < self.ttl:
                    request.metadata["cached_response"] = cached_response
        
        return request
    
    def process_response(self, response: HttpResponse) -> HttpResponse:
        if response.request and response.request.method == HttpMethod.GET and response.is_success:
            key = self._cache_key(response.request)
            with self._lock:
                if len(self._cache) >= self.max_size:
                    # Remove oldest entry
                    oldest = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                    del self._cache[oldest]
                self._cache[key] = (response, time.time())
        
        return response


class ApiClient:
    """HTTP API client."""
    
    def __init__(self, base_url: str = "", auth_provider: Optional[AuthProvider] = None):
        self.base_url = base_url.rstrip("/")
        self.auth_provider = auth_provider
        self.rate_limiter: Optional[RateLimiter] = None
        self.middlewares: List[RequestMiddleware] = []
        self.default_headers: Dict[str, str] = {
            "Content-Type": ContentType.JSON.value,
            "Accept": ContentType.JSON.value,
        }
        self.timeout = 30
    
    def add_middleware(self, middleware: RequestMiddleware) -> None:
        """Add request middleware."""
        self.middlewares.append(middleware)
    
    def set_rate_limiter(self, limiter: RateLimiter) -> None:
        """Set rate limiter."""
        self.rate_limiter = limiter
    
    def _build_url(self, path: str, params: Optional[Dict] = None) -> str:
        """Build full URL with query parameters."""
        url = f"{self.base_url}/{path.lstrip('/')}" if self.base_url else path
        if params:
            query_string = urlencode(params)
            url = f"{url}?{query_string}"
        return url
    
    def _prepare_request(self, request: HttpRequest) -> HttpRequest:
        """Prepare request with headers and auth."""
        # Add default headers
        for key, value in self.default_headers.items():
            if key not in request.headers:
                request.headers[key] = value
        
        # Apply authentication
        if self.auth_provider:
            request = self.auth_provider.authenticate(request)
        
        # Apply middlewares
        for middleware in self.middlewares:
            request = middleware.process_request(request)
        
        return request
    
    def _process_response(self, response: HttpResponse) -> HttpResponse:
        """Process response through middlewares."""
        for middleware in reversed(self.middlewares):
            response = middleware.process_response(response)
        return response
    
    def request(self, method: HttpMethod, path: str, **kwargs) -> HttpResponse:
        """Make an HTTP request."""
        # Check rate limit
        if self.rate_limiter and not self.rate_limiter.wait_for_token():
            raise RateLimitError("Rate limit exceeded")
        
        request = HttpRequest(
            method=method,
            url=self._build_url(path, kwargs.get("params")),
            headers=kwargs.get("headers", {}),
            params=kwargs.get("params", {}),
            body=kwargs.get("body") or kwargs.get("json"),
            timeout=kwargs.get("timeout", self.timeout),
        )
        
        request = self._prepare_request(request)
        
        # Check for cached response
        if "cached_response" in request.metadata:
            return request.metadata["cached_response"]
        
        # Simulate HTTP request (in real implementation, use requests/httpx)
        start_time = time.time()
        response = self._simulate_request(request)
        response.elapsed_time = time.time() - start_time
        response.request = request
        
        return self._process_response(response)
    
    def _simulate_request(self, request: HttpRequest) -> HttpResponse:
        """Simulate HTTP request for testing."""
        # This would be replaced with actual HTTP client
        return HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"success": True, "method": request.method.value}
        )
    
    def get(self, path: str, **kwargs) -> HttpResponse:
        """Make GET request."""
        return self.request(HttpMethod.GET, path, **kwargs)
    
    def post(self, path: str, **kwargs) -> HttpResponse:
        """Make POST request."""
        return self.request(HttpMethod.POST, path, **kwargs)
    
    def put(self, path: str, **kwargs) -> HttpResponse:
        """Make PUT request."""
        return self.request(HttpMethod.PUT, path, **kwargs)
    
    def patch(self, path: str, **kwargs) -> HttpResponse:
        """Make PATCH request."""
        return self.request(HttpMethod.PATCH, path, **kwargs)
    
    def delete(self, path: str, **kwargs) -> HttpResponse:
        """Make DELETE request."""
        return self.request(HttpMethod.DELETE, path, **kwargs)


@dataclass
class Endpoint:
    """API endpoint definition."""
    path: str
    method: HttpMethod
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    body_schema: Optional[Dict] = None
    response_schema: Optional[Dict] = None
    auth_required: bool = True
    rate_limit: Optional[int] = None


class ApiRouter:
    """Routes API requests to handlers."""
    
    def __init__(self):
        self._routes: Dict[str, Dict[HttpMethod, Callable]] = {}
        self._middlewares: List[Callable] = []
    
    def route(self, path: str, method: HttpMethod = HttpMethod.GET):
        """Decorator to register a route handler."""
        def decorator(func: Callable) -> Callable:
            if path not in self._routes:
                self._routes[path] = {}
            self._routes[path][method] = func
            return func
        return decorator
    
    def get(self, path: str):
        """Register GET route."""
        return self.route(path, HttpMethod.GET)
    
    def post(self, path: str):
        """Register POST route."""
        return self.route(path, HttpMethod.POST)
    
    def put(self, path: str):
        """Register PUT route."""
        return self.route(path, HttpMethod.PUT)
    
    def delete(self, path: str):
        """Register DELETE route."""
        return self.route(path, HttpMethod.DELETE)
    
    def use(self, middleware: Callable) -> None:
        """Add middleware."""
        self._middlewares.append(middleware)
    
    def handle(self, request: HttpRequest) -> HttpResponse:
        """Handle incoming request."""
        # Find matching route
        path = urlparse(request.url).path
        
        if path not in self._routes:
            return HttpResponse(status_code=404, body={"error": "Not found"})
        
        if request.method not in self._routes[path]:
            return HttpResponse(status_code=405, body={"error": "Method not allowed"})
        
        handler = self._routes[path][request.method]
        
        try:
            # Apply middlewares
            for middleware in self._middlewares:
                request = middleware(request)
            
            # Call handler
            result = handler(request)
            
            if isinstance(result, HttpResponse):
                return result
            
            return HttpResponse(status_code=200, body=result)
            
        except Exception as e:
            logger.exception(f"Handler error: {e}")
            return HttpResponse(status_code=500, body={"error": str(e)})


class WebhookHandler:
    """Handles incoming webhooks."""
    
    def __init__(self, secret: Optional[str] = None):
        self.secret = secret
        self._handlers: Dict[str, List[Callable]] = {}
    
    def on(self, event_type: str):
        """Register event handler."""
        def decorator(func: Callable) -> Callable:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)
            return func
        return decorator
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """Verify webhook signature."""
        if not self.secret:
            return True
        
        expected = hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    def handle(self, event_type: str, payload: Any, signature: Optional[str] = None) -> List[Any]:
        """Handle webhook event."""
        # Verify signature if provided
        if signature and not self.verify_signature(json.dumps(payload), signature):
            raise AuthenticationError("Invalid webhook signature")
        
        if event_type not in self._handlers:
            logger.warning(f"No handlers for event type: {event_type}")
            return []
        
        results = []
        for handler in self._handlers[event_type]:
            try:
                result = handler(payload)
                results.append(result)
            except Exception as e:
                logger.error(f"Webhook handler error: {e}")
                results.append({"error": str(e)})
        
        return results


# Utility functions
def parse_link_header(header: str) -> Dict[str, str]:
    """Parse Link header for pagination."""
    links = {}
    for part in header.split(","):
        match = re.match(r'<([^>]+)>;\s*rel="([^"]+)"', part.strip())
        if match:
            links[match.group(2)] = match.group(1)
    return links


def build_query_string(params: Dict[str, Any]) -> str:
    """Build URL query string from parameters."""
    return urlencode({k: v for k, v in params.items() if v is not None})


def parse_content_type(header: str) -> tuple:
    """Parse Content-Type header."""
    parts = header.split(";")
    content_type = parts[0].strip()
    params = {}
    for part in parts[1:]:
        if "=" in part:
            key, value = part.strip().split("=", 1)
            params[key] = value.strip('"')
    return content_type, params
