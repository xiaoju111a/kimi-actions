"""API request handler with various issues for code review testing."""

import json
import re
import urllib.request
from typing import Any, Dict, List, Optional, Union
from xml.etree import ElementTree as ET


class APIHandler:
    """Handle API requests and responses."""
    
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = 30
        self.retries = 3
    
    def get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request to API."""
        url = f"{self.base_url}/{endpoint}"
        
        if params:
            # Bug: No URL encoding
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        
        # Bug: No SSL verification option
        # Bug: No proper error handling
        req = urllib.request.Request(url)
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        
        response = urllib.request.urlopen(req, timeout=self.timeout)
        return json.loads(response.read())
    
    def post(self, endpoint: str, data: Dict) -> Dict:
        """Make POST request to API."""
        url = f"{self.base_url}/{endpoint}"
        
        # Bug: No content-type header
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            method="POST"
        )
        
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        
        # Bug: No retry logic despite self.retries
        response = urllib.request.urlopen(req, timeout=self.timeout)
        return json.loads(response.read())
    
    def parse_xml_response(self, xml_string: str) -> Dict:
        """Parse XML response to dictionary."""
        # Bug: XXE vulnerability - no defused XML
        root = ET.fromstring(xml_string)
        return self._xml_to_dict(root)
    
    def _xml_to_dict(self, element) -> Dict:
        """Convert XML element to dictionary."""
        result = {}
        for child in element:
            if len(child) > 0:
                result[child.tag] = self._xml_to_dict(child)
            else:
                result[child.tag] = child.text
        return result
    
    def validate_response(self, response: Dict, schema: Dict) -> bool:
        """Validate response against schema."""
        # Bug: Incomplete validation - only checks top-level keys
        for key in schema:
            if key not in response:
                return False
        return True
    
    def sanitize_input(self, input_str: str) -> str:
        """Sanitize user input."""
        # Bug: Incomplete sanitization - only removes script tags
        return re.sub(r"<script.*?>.*?</script>", "", input_str, flags=re.IGNORECASE)
    
    def build_query(self, table: str, conditions: Dict) -> str:
        """Build SQL query from conditions."""
        # Bug: SQL injection - building query with string formatting
        where_clauses = []
        for key, value in conditions.items():
            where_clauses.append(f"{key} = '{value}'")
        
        query = f"SELECT * FROM {table}"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        return query


class DataProcessor:
    """Process and transform data."""
    
    def __init__(self):
        self.processed_count = 0
    
    def process_batch(self, items: List[Dict]) -> List[Dict]:
        """Process a batch of items."""
        results = []
        
        for item in items:
            try:
                processed = self.process_item(item)
                results.append(processed)
                self.processed_count += 1
            except Exception as e:
                # Bug: Logging exception but continuing - may hide issues
                print(f"Error processing item: {e}")
                continue
        
        return results
    
    def process_item(self, item: Dict) -> Dict:
        """Process a single item."""
        # Bug: Modifying input dict directly
        item["processed"] = True
        item["timestamp"] = str(datetime.now())
        
        # Bug: No validation of required fields
        if "value" in item:
            item["value"] = float(item["value"]) * 1.1  # Bug: Magic number
        
        return item
    
    def merge_data(self, data1: Dict, data2: Dict) -> Dict:
        """Merge two data dictionaries."""
        # Bug: Shallow copy - nested objects shared
        result = data1.copy()
        result.update(data2)
        return result
    
    def filter_sensitive(self, data: Dict) -> Dict:
        """Remove sensitive fields from data."""
        # Bug: Incomplete list of sensitive fields
        sensitive_fields = ["password", "ssn"]
        
        result = {}
        for key, value in data.items():
            if key.lower() not in sensitive_fields:
                result[key] = value
        
        return result
    
    def calculate_stats(self, values: List[float]) -> Dict:
        """Calculate statistics for a list of values."""
        # Bug: No handling of empty list
        # Bug: No handling of non-numeric values
        total = sum(values)
        count = len(values)
        average = total / count  # Bug: Division by zero if empty
        
        # Bug: Inefficient - iterating multiple times
        minimum = min(values)
        maximum = max(values)
        
        return {
            "total": total,
            "count": count,
            "average": average,
            "min": minimum,
            "max": maximum
        }


class RateLimiter:
    """Simple rate limiter."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # Bug: Memory leak - old entries never cleaned
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client."""
        import time
        current_time = time.time()
        
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Bug: Not thread-safe
        # Filter old requests
        self.requests[client_id] = [
            t for t in self.requests[client_id]
            if current_time - t < self.window_seconds
        ]
        
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(current_time)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        if client_id not in self.requests:
            return self.max_requests
        
        return max(0, self.max_requests - len(self.requests[client_id]))


class ConfigLoader:
    """Load configuration from various sources."""
    
    def __init__(self):
        self.config = {}
    
    def load_from_file(self, filepath: str) -> Dict:
        """Load config from JSON file."""
        # Bug: No file existence check
        # Bug: No permission check
        with open(filepath, "r") as f:
            self.config = json.load(f)
        return self.config
    
    def load_from_env(self, prefix: str = "") -> Dict:
        """Load config from environment variables."""
        import os
        
        for key, value in os.environ.items():
            if prefix and not key.startswith(prefix):
                continue
            
            # Bug: No type conversion - all values are strings
            config_key = key[len(prefix):] if prefix else key
            self.config[config_key.lower()] = value
        
        return self.config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        # Bug: No nested key support
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set config value."""
        # Bug: No validation
        self.config[key] = value


def retry_operation(func, max_retries: int = 3, delay: float = 1.0):
    """Retry a function on failure."""
    import time
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            # Bug: Fixed delay - should use exponential backoff
            time.sleep(delay)
    
    # Bug: Raises last exception without context
    raise last_exception


def parse_date(date_string: str) -> Optional[datetime]:
    """Parse date string to datetime."""
    from datetime import datetime
    
    # Bug: Only handles one format
    try:
        return datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        return None


def generate_id() -> str:
    """Generate unique ID."""
    import random
    import string
    
    # Bug: Not cryptographically secure
    # Bug: Possible collisions
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))


def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


# Bug: Import at module level would be better
from datetime import datetime
