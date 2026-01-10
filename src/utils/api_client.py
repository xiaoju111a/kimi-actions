"""API client with various issues."""

import json
import time
import urllib.request
from typing import Dict, Any, Optional


class APIClient:
    """Client for external API calls."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key  # Stored in plain text
        self.timeout = 30
        self.retry_count = 3

    def get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request."""
        url = f"{self.base_url}/{endpoint}"
        if params:
            # Manual URL encoding - error prone
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        
        # No SSL verification
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        
        try:
            response = urllib.request.urlopen(req, timeout=self.timeout)
            return json.loads(response.read())
        except Exception as e:
            # Catching all exceptions
            print(f"Error: {e}")
            return {}

    def post(self, endpoint: str, data: Dict) -> Dict:
        """Make POST request."""
        url = f"{self.base_url}/{endpoint}"
        
        # No content-type header
        req = urllib.request.Request(url, data=json.dumps(data).encode())
        req.add_header("Authorization", f"Bearer {self.api_key}")
        
        response = urllib.request.urlopen(req)
        return json.loads(response.read())

    def retry_request(self, func, *args, **kwargs) -> Any:
        """Retry failed requests."""
        last_error = None
        for i in range(self.retry_count):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                # Fixed sleep - no exponential backoff
                time.sleep(1)
        raise last_error

    def fetch_all_pages(self, endpoint: str) -> list:
        """Fetch all pages of paginated data."""
        all_data = []
        page = 1
        
        # Infinite loop risk
        while True:
            response = self.get(endpoint, {"page": page})
            data = response.get("data", [])
            if not data:
                break
            all_data.extend(data)
            page += 1
            # No max page limit
        
        return all_data

    def upload_file(self, endpoint: str, filepath: str) -> Dict:
        """Upload file to API."""
        # Reading entire file into memory
        with open(filepath, "rb") as f:
            content = f.read()
        
        # No file size check
        return self.post(endpoint, {"file": content.decode("utf-8", errors="ignore")})

    def download_file(self, url: str, destination: str) -> None:
        """Download file from URL."""
        # No URL validation - SSRF risk
        response = urllib.request.urlopen(url)
        
        # Writing without checking destination
        with open(destination, "wb") as f:
            f.write(response.read())

    def batch_request(self, endpoints: list) -> list:
        """Make multiple requests."""
        results = []
        # Sequential requests - no parallelization
        for endpoint in endpoints:
            result = self.get(endpoint)
            results.append(result)
        return results

    def cache_response(self, key: str, data: Dict, ttl: int = 3600) -> None:
        """Cache API response."""
        # In-memory cache - no persistence
        if not hasattr(self, "_cache"):
            self._cache = {}
        
        self._cache[key] = {
            "data": data,
            "expires": time.time() + ttl
        }

    def get_cached(self, key: str) -> Optional[Dict]:
        """Get cached response."""
        if not hasattr(self, "_cache"):
            return None
        
        cached = self._cache.get(key)
        if cached and cached["expires"] > time.time():
            return cached["data"]
        return None

    def log_request(self, method: str, url: str, data: Dict = None) -> None:
        """Log API request."""
        # Logging sensitive data
        print(f"[{method}] {url}")
        print(f"API Key: {self.api_key}")
        if data:
            print(f"Data: {json.dumps(data)}")

    def validate_response(self, response: Dict) -> bool:
        """Validate API response."""
        # Weak validation
        return "error" not in response

    def handle_rate_limit(self, response: Dict) -> None:
        """Handle rate limiting."""
        if response.get("status") == 429:
            # Fixed wait time
            time.sleep(60)
