"""
Data Processing Module - A comprehensive data processing library.

This module provides utilities for data transformation, validation,
caching, and analysis. It demonstrates various Python patterns and
includes intentional issues for code review testing.
"""

import json
import hashlib
import time
import threading
import logging
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from functools import wraps
from collections import defaultdict
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

T = TypeVar('T')


class DataType(Enum):
    """Supported data types for processing."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    NULL = "null"


class ProcessingError(Exception):
    """Base exception for processing errors."""
    pass


class ValidationError(ProcessingError):
    """Raised when data validation fails."""
    pass


class TransformationError(ProcessingError):
    """Raised when data transformation fails."""
    pass


@dataclass
class ProcessingResult:
    """Result of a data processing operation."""
    success: bool
    data: Any = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0


@dataclass
class CacheEntry:
    """Cache entry with expiration."""
    value: Any
    created_at: float
    ttl: int  # seconds
    hits: int = 0

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class DataCache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            entry.hits += 1
            self._stats["hits"] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        with self._lock:
            if len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl or self.default_ttl
            )
    
    def _evict_oldest(self) -> None:
        """Evict oldest entry from cache."""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), 
                        key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]
        self._stats["evictions"] += 1
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self._stats.copy()


class Validator(ABC):
    """Abstract base class for validators."""
    
    @abstractmethod
    def validate(self, data: Any) -> bool:
        """Validate data and return True if valid."""
        pass
    
    @abstractmethod
    def get_error_message(self) -> str:
        """Get error message for validation failure."""
        pass


class TypeValidator(Validator):
    """Validates data type."""
    
    def __init__(self, expected_type: type):
        self.expected_type = expected_type
        self._error_message = ""
    
    def validate(self, data: Any) -> bool:
        if isinstance(data, self.expected_type):
            return True
        self._error_message = f"Expected {self.expected_type.__name__}, got {type(data).__name__}"
        return False
    
    def get_error_message(self) -> str:
        return self._error_message


class RangeValidator(Validator):
    """Validates numeric range."""
    
    def __init__(self, min_val: Optional[float] = None, max_val: Optional[float] = None):
        self.min_val = min_val
        self.max_val = max_val
        self._error_message = ""
    
    def validate(self, data: Any) -> bool:
        if not isinstance(data, (int, float)):
            self._error_message = "Value must be numeric"
            return False
        
        if self.min_val is not None and data < self.min_val:
            self._error_message = f"Value {data} is below minimum {self.min_val}"
            return False
        
        if self.max_val is not None and data > self.max_val:
            self._error_message = f"Value {data} is above maximum {self.max_val}"
            return False
        
        return True
    
    def get_error_message(self) -> str:
        return self._error_message


class PatternValidator(Validator):
    """Validates string against regex pattern."""
    
    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern)
        self._error_message = ""
    
    def validate(self, data: Any) -> bool:
        if not isinstance(data, str):
            self._error_message = "Value must be a string"
            return False
        
        if not self.pattern.match(data):
            self._error_message = f"Value does not match pattern {self.pattern.pattern}"
            return False
        
        return True
    
    def get_error_message(self) -> str:
        return self._error_message


class SchemaValidator:
    """Validates data against a schema definition."""
    
    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.errors: List[str] = []
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate data against schema."""
        self.errors = []
        
        if not isinstance(data, dict):
            self.errors.append("Data must be a dictionary")
            return False
        
        # Check required fields
        required = self.schema.get("required", [])
        for field in required:
            if field not in data:
                self.errors.append(f"Missing required field: {field}")
        
        # Validate field types
        properties = self.schema.get("properties", {})
        for field, value in data.items():
            if field in properties:
                field_schema = properties[field]
                if not self._validate_field(field, value, field_schema):
                    pass  # Error already added
        
        return len(self.errors) == 0
    
    def _validate_field(self, field: str, value: Any, schema: Dict) -> bool:
        """Validate a single field against its schema."""
        expected_type = schema.get("type")
        
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        if expected_type and expected_type in type_map:
            if not isinstance(value, type_map[expected_type]):
                self.errors.append(
                    f"Field '{field}' expected {expected_type}, got {type(value).__name__}"
                )
                return False
        
        # Check enum values
        if "enum" in schema and value not in schema["enum"]:
            self.errors.append(
                f"Field '{field}' must be one of {schema['enum']}"
            )
            return False
        
        return True


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying failed operations."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}"
                    )
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator


def memoize(func: Callable[..., T]) -> Callable[..., T]:
    """Simple memoization decorator."""
    cache = {}
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        # BUG: kwargs not properly handled in cache key
        key = str(args)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    
    return wrapper


class DataTransformer:
    """Transforms data between different formats."""
    
    def __init__(self):
        self._transformers: Dict[str, Callable] = {}
        self._register_default_transformers()
    
    def _register_default_transformers(self):
        """Register default transformation functions."""
        self._transformers["uppercase"] = lambda x: x.upper() if isinstance(x, str) else x
        self._transformers["lowercase"] = lambda x: x.lower() if isinstance(x, str) else x
        self._transformers["trim"] = lambda x: x.strip() if isinstance(x, str) else x
        self._transformers["to_int"] = lambda x: int(x) if x else 0
        self._transformers["to_float"] = lambda x: float(x) if x else 0.0
        self._transformers["to_string"] = str
        self._transformers["to_bool"] = bool
    
    def register(self, name: str, transformer: Callable) -> None:
        """Register a custom transformer."""
        self._transformers[name] = transformer
    
    def transform(self, data: Any, transformations: List[str]) -> Any:
        """Apply a series of transformations to data."""
        result = data
        for transform_name in transformations:
            if transform_name not in self._transformers:
                raise TransformationError(f"Unknown transformation: {transform_name}")
            result = self._transformers[transform_name](result)
        return result
    
    def transform_dict(self, data: Dict, field_transforms: Dict[str, List[str]]) -> Dict:
        """Transform specific fields in a dictionary."""
        result = data.copy()
        for field, transforms in field_transforms.items():
            if field in result:
                result[field] = self.transform(result[field], transforms)
        return result


class DataProcessor:
    """Main data processing class."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.cache = DataCache(
            max_size=self.config.get("cache_size", 1000),
            default_ttl=self.config.get("cache_ttl", 3600)
        )
        self.transformer = DataTransformer()
        self.validators: Dict[str, Validator] = {}
        self._processing_hooks: List[Callable] = []
    
    def add_validator(self, name: str, validator: Validator) -> None:
        """Add a named validator."""
        self.validators[name] = validator
    
    def add_hook(self, hook: Callable) -> None:
        """Add a processing hook."""
        self._processing_hooks.append(hook)
    
    def process(self, data: Any, options: Optional[Dict] = None) -> ProcessingResult:
        """Process data with validation and transformation."""
        start_time = time.time()
        options = options or {}
        result = ProcessingResult(success=True)
        
        try:
            # Run pre-processing hooks
            for hook in self._processing_hooks:
                data = hook(data)
            
            # Validate if validators specified
            validators_to_run = options.get("validators", [])
            for validator_name in validators_to_run:
                if validator_name not in self.validators:
                    result.warnings.append(f"Unknown validator: {validator_name}")
                    continue
                
                validator = self.validators[validator_name]
                if not validator.validate(data):
                    result.errors.append(validator.get_error_message())
                    result.success = False
            
            if not result.success:
                return result
            
            # Transform if transformations specified
            transformations = options.get("transformations", [])
            if transformations:
                if isinstance(data, dict) and isinstance(transformations, dict):
                    data = self.transformer.transform_dict(data, transformations)
                elif isinstance(transformations, list):
                    data = self.transformer.transform(data, transformations)
            
            result.data = data
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.exception("Processing failed")
        
        result.processing_time = time.time() - start_time
        return result
    
    def process_batch(self, items: List[Any], options: Optional[Dict] = None) -> List[ProcessingResult]:
        """Process multiple items."""
        return [self.process(item, options) for item in items]
    
    def process_with_cache(self, data: Any, cache_key: str, 
                          options: Optional[Dict] = None) -> ProcessingResult:
        """Process data with caching."""
        cached = self.cache.get(cache_key)
        if cached is not None:
            return ProcessingResult(
                success=True,
                data=cached,
                metadata={"from_cache": True}
            )
        
        result = self.process(data, options)
        if result.success:
            self.cache.set(cache_key, result.data)
        
        return result


class DataAggregator:
    """Aggregates data from multiple sources."""
    
    def __init__(self):
        self._sources: Dict[str, Callable] = {}
        self._aggregation_rules: Dict[str, Callable] = {
            "sum": sum,
            "avg": lambda x: sum(x) / len(x) if x else 0,
            "min": min,
            "max": max,
            "count": len,
            "first": lambda x: x[0] if x else None,
            "last": lambda x: x[-1] if x else None,
        }
    
    def register_source(self, name: str, source: Callable) -> None:
        """Register a data source."""
        self._sources[name] = source
    
    def aggregate(self, source_names: List[str], rule: str = "sum") -> Any:
        """Aggregate data from multiple sources."""
        if rule not in self._aggregation_rules:
            raise ValueError(f"Unknown aggregation rule: {rule}")
        
        data = []
        for name in source_names:
            if name not in self._sources:
                logger.warning(f"Unknown source: {name}")
                continue
            
            try:
                source_data = self._sources[name]()
                if isinstance(source_data, list):
                    data.extend(source_data)
                else:
                    data.append(source_data)
            except Exception as e:
                logger.error(f"Failed to get data from source {name}: {e}")
        
        return self._aggregation_rules[rule](data)
    
    def group_by(self, data: List[Dict], key: str) -> Dict[Any, List[Dict]]:
        """Group data by a key."""
        result = defaultdict(list)
        for item in data:
            if key in item:
                result[item[key]].append(item)
        return dict(result)


class DataSerializer:
    """Serializes and deserializes data."""
    
    @staticmethod
    def to_json(data: Any, pretty: bool = False) -> str:
        """Serialize data to JSON."""
        indent = 2 if pretty else None
        return json.dumps(data, indent=indent, default=str)
    
    @staticmethod
    def from_json(json_str: str) -> Any:
        """Deserialize data from JSON."""
        return json.loads(json_str)
    
    @staticmethod
    def hash_data(data: Any) -> str:
        """Generate hash of data."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()


class QueryBuilder:
    """Builds and executes queries on data."""
    
    def __init__(self, data: List[Dict]):
        self._data = data
        self._filters: List[Callable] = []
        self._sort_key: Optional[str] = None
        self._sort_reverse: bool = False
        self._limit: Optional[int] = None
        self._offset: int = 0
        self._select_fields: Optional[List[str]] = None
    
    def where(self, condition: Callable[[Dict], bool]) -> 'QueryBuilder':
        """Add a filter condition."""
        self._filters.append(condition)
        return self
    
    def equals(self, field: str, value: Any) -> 'QueryBuilder':
        """Filter where field equals value."""
        return self.where(lambda x: x.get(field) == value)
    
    def contains(self, field: str, value: str) -> 'QueryBuilder':
        """Filter where field contains value."""
        return self.where(lambda x: value in str(x.get(field, "")))
    
    def greater_than(self, field: str, value: Any) -> 'QueryBuilder':
        """Filter where field is greater than value."""
        return self.where(lambda x: x.get(field, 0) > value)
    
    def less_than(self, field: str, value: Any) -> 'QueryBuilder':
        """Filter where field is less than value."""
        return self.where(lambda x: x.get(field, 0) < value)
    
    def order_by(self, field: str, reverse: bool = False) -> 'QueryBuilder':
        """Sort results by field."""
        self._sort_key = field
        self._sort_reverse = reverse
        return self
    
    def limit(self, count: int) -> 'QueryBuilder':
        """Limit number of results."""
        self._limit = count
        return self
    
    def offset(self, count: int) -> 'QueryBuilder':
        """Skip first N results."""
        self._offset = count
        return self
    
    def select(self, fields: List[str]) -> 'QueryBuilder':
        """Select specific fields."""
        self._select_fields = fields
        return self
    
    def execute(self) -> List[Dict]:
        """Execute the query and return results."""
        result = self._data.copy()
        
        # Apply filters
        for filter_func in self._filters:
            result = [item for item in result if filter_func(item)]
        
        # Apply sorting
        if self._sort_key:
            result.sort(key=lambda x: x.get(self._sort_key, ""), reverse=self._sort_reverse)
        
        # Apply offset and limit
        if self._offset:
            result = result[self._offset:]
        if self._limit:
            result = result[:self._limit]
        
        # Select fields
        if self._select_fields:
            result = [
                {k: v for k, v in item.items() if k in self._select_fields}
                for item in result
            ]
        
        return result
    
    def count(self) -> int:
        """Count matching results."""
        return len(self.execute())
    
    def first(self) -> Optional[Dict]:
        """Get first matching result."""
        results = self.limit(1).execute()
        return results[0] if results else None
    
    def exists(self) -> bool:
        """Check if any results exist."""
        return self.count() > 0


# Utility functions
def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """Flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: Dict, sep: str = '.') -> Dict:
    """Unflatten a dictionary with dotted keys."""
    result = {}
    for key, value in d.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """Split a list into chunks."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_get(data: Dict, path: str, default: Any = None, sep: str = '.') -> Any:
    """Safely get a nested value from a dictionary."""
    keys = path.split(sep)
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def safe_set(data: Dict, path: str, value: Any, sep: str = '.') -> Dict:
    """Safely set a nested value in a dictionary."""
    keys = path.split(sep)
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return data
