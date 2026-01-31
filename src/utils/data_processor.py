"""Data processing utilities for Kimi Actions.

This module provides comprehensive data processing capabilities including:
- JSON/YAML parsing and validation
- Text normalization and cleaning
- Data transformation pipelines
- Caching and memoization utilities
"""

import json
import logging
import hashlib
import functools
from typing import Any, Dict, List, Optional, Callable, TypeVar, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DataFormat(Enum):
    """Supported data formats."""
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    CSV = "csv"
    TEXT = "text"


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class TransformError(Exception):
    """Raised when data transformation fails."""
    pass


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """Merge another validation result into this one."""
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            metadata={**self.metadata, **other.metadata}
        )


@dataclass
class CacheEntry:
    """A cached data entry with expiration."""
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    hits: int = 0

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def touch(self) -> None:
        """Update the hit count."""
        self.hits += 1


class DataCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: Optional[int] = None):
        """Initialize the cache.
        
        Args:
            default_ttl: Default time-to-live in seconds
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._cache[key]
            return None
        entry.touch()
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache."""
        ttl = ttl or self._default_ttl
        expires_at = None
        if ttl is not None:
            expires_at = datetime.now() + timedelta(seconds=ttl)
        self._cache[key] = CacheEntry(
            value=value,
            created_at=datetime.now(),
            expires_at=expires_at
        )

    def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def cleanup(self) -> int:
        """Remove expired entries and return count of removed entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

    @property
    def size(self) -> int:
        """Return the number of entries in the cache."""
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total_hits = sum(e.hits for e in self._cache.values())
        return {
            "size": self.size,
            "total_hits": total_hits,
            "oldest_entry": min(
                (e.created_at for e in self._cache.values()),
                default=None
            )
        }


def memoize(ttl: Optional[int] = None) -> Callable:
    """Decorator to memoize function results.
    
    Args:
        ttl: Time-to-live in seconds for cached results
    """
    cache = DataCache(default_ttl=ttl)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Create a cache key from function arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            cached = cache.get(key)
            if cached is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached

            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache
        wrapper.cache_clear = cache.clear
        return wrapper

    return decorator


class TextNormalizer:
    """Utilities for normalizing and cleaning text."""

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace in text."""
        import re
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def remove_control_chars(text: str) -> str:
        """Remove control characters from text."""
        import re
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize unicode characters."""
        import unicodedata
        return unicodedata.normalize('NFKC', text)

    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to a maximum length."""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def extract_code_blocks(text: str) -> List[Dict[str, str]]:
        """Extract code blocks from markdown text."""
        import re
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)
        return [
            {"language": lang or "text", "code": code.strip()}
            for lang, code in matches
        ]

    @staticmethod
    def strip_markdown(text: str) -> str:
        """Remove markdown formatting from text."""
        import re
        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # Remove inline code
        text = re.sub(r'`[^`]+`', '', text)
        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # Remove bold/italic
        text = re.sub(r'\*+([^*]+)\*+', r'\1', text)
        text = re.sub(r'_+([^_]+)_+', r'\1', text)
        # Remove links
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        return text.strip()


class JsonProcessor:
    """Utilities for processing JSON data."""

    @staticmethod
    def safe_parse(text: str) -> Optional[Dict[str, Any]]:
        """Safely parse JSON, returning None on failure."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text that may contain other content."""
        import re
        # Try markdown code block first
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return JsonProcessor.safe_parse(match.group(1))

        # Try to find raw JSON object
        start = text.find('{')
        if start == -1:
            return None

        # Find matching closing brace
        depth = 0
        for i, char in enumerate(text[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return JsonProcessor.safe_parse(text[start:i + 1])

        return None

    @staticmethod
    def flatten(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
        """Flatten a nested dictionary."""
        result = {}

        def _flatten(obj: Any, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{prefix}{separator}{key}" if prefix else key
                    _flatten(value, new_key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_key = f"{prefix}{separator}{i}" if prefix else str(i)
                    _flatten(item, new_key)
            else:
                result[prefix] = obj

        _flatten(data)
        return result

    @staticmethod
    def unflatten(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
        """Unflatten a flattened dictionary."""
        result: Dict[str, Any] = {}

        for key, value in data.items():
            parts = key.split(separator)
            current = result

            for i, part in enumerate(parts[:-1]):
                if part.isdigit():
                    part = int(part)
                if part not in current:
                    # Check if next part is a digit to decide list vs dict
                    next_part = parts[i + 1]
                    current[part] = [] if next_part.isdigit() else {}
                current = current[part]

            final_key = parts[-1]
            if final_key.isdigit():
                final_key = int(final_key)
            current[final_key] = value

        return result

    @staticmethod
    def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = JsonProcessor.deep_merge(result[key], value)
            else:
                result[key] = value

        return result


class DataValidator:
    """Utilities for validating data structures."""

    @staticmethod
    def validate_required_fields(
        data: Dict[str, Any],
        required: List[str]
    ) -> ValidationResult:
        """Validate that required fields are present."""
        result = ValidationResult(valid=True)

        for field in required:
            if field not in data:
                result.add_error(f"Missing required field: {field}")
            elif data[field] is None:
                result.add_error(f"Required field is null: {field}")
            elif isinstance(data[field], str) and not data[field].strip():
                result.add_error(f"Required field is empty: {field}")

        return result

    @staticmethod
    def validate_field_types(
        data: Dict[str, Any],
        type_map: Dict[str, type]
    ) -> ValidationResult:
        """Validate field types."""
        result = ValidationResult(valid=True)

        for field, expected_type in type_map.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    result.add_error(
                        f"Field '{field}' has wrong type: "
                        f"expected {expected_type.__name__}, "
                        f"got {type(data[field]).__name__}"
                    )

        return result

    @staticmethod
    def validate_enum_values(
        data: Dict[str, Any],
        enum_map: Dict[str, List[str]]
    ) -> ValidationResult:
        """Validate that fields contain valid enum values."""
        result = ValidationResult(valid=True)

        for field, valid_values in enum_map.items():
            if field in data and data[field] is not None:
                value = data[field]
                if isinstance(value, str):
                    value = value.lower()
                if value not in [v.lower() if isinstance(v, str) else v for v in valid_values]:
                    result.add_error(
                        f"Invalid value for '{field}': {data[field]}. "
                        f"Valid values: {valid_values}"
                    )

        return result

    @staticmethod
    def validate_string_length(
        data: Dict[str, Any],
        length_map: Dict[str, Dict[str, int]]
    ) -> ValidationResult:
        """Validate string field lengths."""
        result = ValidationResult(valid=True)

        for field, constraints in length_map.items():
            if field in data and isinstance(data[field], str):
                value = data[field]
                min_len = constraints.get("min", 0)
                max_len = constraints.get("max", float("inf"))

                if len(value) < min_len:
                    result.add_error(
                        f"Field '{field}' is too short: "
                        f"minimum {min_len} characters"
                    )
                if len(value) > max_len:
                    result.add_error(
                        f"Field '{field}' is too long: "
                        f"maximum {max_len} characters"
                    )

        return result


class DataTransformer:
    """Utilities for transforming data structures."""

    @staticmethod
    def rename_keys(
        data: Dict[str, Any],
        key_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """Rename keys in a dictionary."""
        result = {}
        for key, value in data.items():
            new_key = key_map.get(key, key)
            result[new_key] = value
        return result

    @staticmethod
    def filter_keys(
        data: Dict[str, Any],
        keys: List[str],
        include: bool = True
    ) -> Dict[str, Any]:
        """Filter dictionary keys."""
        if include:
            return {k: v for k, v in data.items() if k in keys}
        return {k: v for k, v in data.items() if k not in keys}

    @staticmethod
    def apply_defaults(
        data: Dict[str, Any],
        defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply default values to missing keys."""
        result = defaults.copy()
        result.update(data)
        return result

    @staticmethod
    def transform_values(
        data: Dict[str, Any],
        transformers: Dict[str, Callable[[Any], Any]]
    ) -> Dict[str, Any]:
        """Apply transformations to specific fields."""
        result = data.copy()
        for field, transformer in transformers.items():
            if field in result:
                try:
                    result[field] = transformer(result[field])
                except Exception as e:
                    raise TransformError(
                        f"Failed to transform field '{field}': {e}"
                    )
        return result

    @staticmethod
    def to_snake_case(text: str) -> str:
        """Convert text to snake_case."""
        import re
        # Insert underscore before uppercase letters
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
        # Insert underscore before uppercase letters followed by lowercase
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @staticmethod
    def to_camel_case(text: str) -> str:
        """Convert text to camelCase."""
        components = text.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    @staticmethod
    def to_pascal_case(text: str) -> str:
        """Convert text to PascalCase."""
        return ''.join(x.title() for x in text.split('_'))


class Pipeline:
    """A data processing pipeline."""

    def __init__(self):
        """Initialize an empty pipeline."""
        self._steps: List[Callable[[Any], Any]] = []

    def add(self, step: Callable[[Any], Any]) -> 'Pipeline':
        """Add a processing step to the pipeline."""
        self._steps.append(step)
        return self

    def process(self, data: Any) -> Any:
        """Process data through all pipeline steps."""
        result = data
        for step in self._steps:
            result = step(result)
        return result

    def __call__(self, data: Any) -> Any:
        """Allow pipeline to be called as a function."""
        return self.process(data)

    def __len__(self) -> int:
        """Return the number of steps in the pipeline."""
        return len(self._steps)


# Convenience functions
def parse_json_safely(text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON safely, extracting from markdown if needed."""
    return JsonProcessor.extract_json(text)


def normalize_text(text: str) -> str:
    """Apply standard text normalization."""
    normalizer = TextNormalizer()
    text = normalizer.remove_control_chars(text)
    text = normalizer.normalize_unicode(text)
    text = normalizer.normalize_whitespace(text)
    return text


def validate_data(
    data: Dict[str, Any],
    required_fields: Optional[List[str]] = None,
    type_map: Optional[Dict[str, type]] = None,
    enum_map: Optional[Dict[str, List[str]]] = None
) -> ValidationResult:
    """Validate data with multiple validators."""
    result = ValidationResult(valid=True)

    if required_fields:
        result = result.merge(
            DataValidator.validate_required_fields(data, required_fields)
        )

    if type_map:
        result = result.merge(
            DataValidator.validate_field_types(data, type_map)
        )

    if enum_map:
        result = result.merge(
            DataValidator.validate_enum_values(data, enum_map)
        )

    return result
