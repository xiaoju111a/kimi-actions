"""Data processing utilities for large-scale data operations.

This module provides comprehensive data processing capabilities including:
- Data validation and sanitization
- Batch processing with configurable chunk sizes
- Parallel processing support
- Error handling and recovery
- Metrics collection and reporting
"""

import logging
import time
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Iterator, TypeVar, Generic
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class ProcessingStatus(Enum):
    """Status of data processing operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class ValidationError(Exception):
    """Raised when data validation fails."""
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value


class ProcessingError(Exception):
    """Raised when data processing fails."""
    def __init__(self, message: str, item_id: str = None, cause: Exception = None):
        super().__init__(message)
        self.item_id = item_id
        self.cause = cause


@dataclass
class ProcessingMetrics:
    """Metrics for tracking processing performance."""
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    retried_items: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_items == 0:
            return 0.0
        return self.processed_items / self.total_items
    
    @property
    def duration(self) -> float:
        if self.end_time == 0:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def items_per_second(self) -> float:
        duration = self.duration
        if duration == 0:
            return 0.0
        return self.processed_items / duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "retried_items": self.retried_items,
            "success_rate": self.success_rate,
            "duration": self.duration,
            "items_per_second": self.items_per_second,
            "errors": self.errors[:10]  # Limit errors in output
        }


@dataclass
class ProcessingConfig:
    """Configuration for data processing operations."""
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    parallel_workers: int = 4
    skip_on_error: bool = False
    validate_input: bool = True
    collect_metrics: bool = True
    log_progress: bool = True
    progress_interval: int = 100


@dataclass
class DataItem(Generic[T]):
    """Wrapper for data items with metadata."""
    id: str
    data: T
    status: ProcessingStatus = ProcessingStatus.PENDING
    retries: int = 0
    error: Optional[str] = None
    result: Any = None
    processing_time: float = 0.0
    
    def mark_processing(self):
        self.status = ProcessingStatus.PROCESSING
    
    def mark_completed(self, result: Any = None):
        self.status = ProcessingStatus.COMPLETED
        self.result = result
    
    def mark_failed(self, error: str):
        self.status = ProcessingStatus.FAILED
        self.error = error
    
    def mark_skipped(self, reason: str = None):
        self.status = ProcessingStatus.SKIPPED
        self.error = reason
    
    def can_retry(self, max_retries: int) -> bool:
        return self.retries < max_retries


class DataValidator:
    """Validates data items before processing."""
    
    def __init__(self):
        self.rules: List[Callable[[Any], bool]] = []
        self.error_messages: Dict[int, str] = {}
    
    def add_rule(self, rule: Callable[[Any], bool], error_message: str):
        rule_id = len(self.rules)
        self.rules.append(rule)
        self.error_messages[rule_id] = error_message
    
    def validate(self, data: Any) -> List[str]:
        errors = []
        for i, rule in enumerate(self.rules):
            try:
                if not rule(data):
                    errors.append(self.error_messages.get(i, f"Validation rule {i} failed"))
            except Exception as e:
                errors.append(f"Validation error: {str(e)}")
        return errors
    
    def is_valid(self, data: Any) -> bool:
        return len(self.validate(data)) == 0


class StringValidator(DataValidator):
    """Validator for string data."""
    
    def __init__(self, min_length: int = 0, max_length: int = None, pattern: str = None):
        super().__init__()
        
        if min_length > 0:
            self.add_rule(
                lambda x: isinstance(x, str) and len(x) >= min_length,
                f"String must be at least {min_length} characters"
            )
        
        if max_length is not None:
            self.add_rule(
                lambda x: isinstance(x, str) and len(x) <= max_length,
                f"String must be at most {max_length} characters"
            )
        
        if pattern is not None:
            compiled = re.compile(pattern)
            self.add_rule(
                lambda x: isinstance(x, str) and compiled.match(x) is not None,
                f"String must match pattern: {pattern}"
            )


class NumberValidator(DataValidator):
    """Validator for numeric data."""
    
    def __init__(self, min_value: float = None, max_value: float = None, allow_none: bool = False):
        super().__init__()
        
        if not allow_none:
            self.add_rule(
                lambda x: x is not None,
                "Value cannot be None"
            )
        
        if min_value is not None:
            self.add_rule(
                lambda x: x is None or (isinstance(x, (int, float)) and x >= min_value),
                f"Value must be at least {min_value}"
            )
        
        if max_value is not None:
            self.add_rule(
                lambda x: x is None or (isinstance(x, (int, float)) and x <= max_value),
                f"Value must be at most {max_value}"
            )


class DictValidator(DataValidator):
    """Validator for dictionary data."""
    
    def __init__(self, required_keys: List[str] = None, optional_keys: List[str] = None):
        super().__init__()
        self.required_keys = required_keys or []
        self.optional_keys = optional_keys or []
        self.field_validators: Dict[str, DataValidator] = {}
        
        self.add_rule(
            lambda x: isinstance(x, dict),
            "Value must be a dictionary"
        )
        
        for key in self.required_keys:
            self.add_rule(
                lambda x, k=key: isinstance(x, dict) and k in x,
                f"Missing required key: {key}"
            )
    
    def add_field_validator(self, field: str, validator: DataValidator):
        self.field_validators[field] = validator
    
    def validate(self, data: Any) -> List[str]:
        errors = super().validate(data)
        
        if isinstance(data, dict):
            for field, validator in self.field_validators.items():
                if field in data:
                    field_errors = validator.validate(data[field])
                    errors.extend([f"{field}: {e}" for e in field_errors])
        
        return errors


class BatchProcessor(Generic[T, R]):
    """Processes data items in batches with configurable options."""
    
    def __init__(self, config: ProcessingConfig = None):
        self.config = config or ProcessingConfig()
        self.metrics = ProcessingMetrics()
        self.validator: Optional[DataValidator] = None
        self._lock = threading.Lock()
    
    def set_validator(self, validator: DataValidator):
        self.validator = validator
    
    def process_batch(
        self,
        items: List[T],
        processor: Callable[[T], R]
    ) -> List[DataItem[T]]:
        """Process a batch of items."""
        self.metrics = ProcessingMetrics()
        self.metrics.total_items = len(items)
        self.metrics.start_time = time.time()
        
        # Wrap items
        wrapped_items = [
            DataItem(id=self._generate_id(item), data=item)
            for item in items
        ]
        
        # Validate if enabled
        if self.config.validate_input and self.validator:
            for item in wrapped_items:
                errors = self.validator.validate(item.data)
                if errors:
                    item.mark_skipped("; ".join(errors))
                    self.metrics.skipped_items += 1
        
        # Process items
        pending_items = [i for i in wrapped_items if i.status == ProcessingStatus.PENDING]
        
        if self.config.parallel_workers > 1:
            self._process_parallel(pending_items, processor)
        else:
            self._process_sequential(pending_items, processor)
        
        self.metrics.end_time = time.time()
        
        if self.config.log_progress:
            logger.info(f"Processing complete: {self.metrics.to_dict()}")
        
        return wrapped_items
    
    def _process_sequential(
        self,
        items: List[DataItem[T]],
        processor: Callable[[T], R]
    ):
        """Process items sequentially."""
        for i, item in enumerate(items):
            self._process_item(item, processor)
            
            if self.config.log_progress and (i + 1) % self.config.progress_interval == 0:
                logger.info(f"Processed {i + 1}/{len(items)} items")
    
    def _process_parallel(
        self,
        items: List[DataItem[T]],
        processor: Callable[[T], R]
    ):
        """Process items in parallel using thread pool."""
        with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
            futures = {
                executor.submit(self._process_item, item, processor): item
                for item in items
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if self.config.log_progress and completed % self.config.progress_interval == 0:
                    logger.info(f"Processed {completed}/{len(items)} items")
    
    def _process_item(
        self,
        item: DataItem[T],
        processor: Callable[[T], R]
    ):
        """Process a single item with retry support."""
        item.mark_processing()
        start_time = time.time()
        
        while True:
            try:
                result = processor(item.data)
                item.mark_completed(result)
                
                with self._lock:
                    self.metrics.processed_items += 1
                
                break
                
            except Exception as e:
                item.retries += 1
                
                if item.can_retry(self.config.max_retries):
                    with self._lock:
                        self.metrics.retried_items += 1
                    
                    time.sleep(self.config.retry_delay)
                    continue
                
                item.mark_failed(str(e))
                
                with self._lock:
                    self.metrics.failed_items += 1
                    self.metrics.errors.append(f"{item.id}: {str(e)}")
                
                if not self.config.skip_on_error:
                    raise ProcessingError(str(e), item.id, e)
                
                break
        
        item.processing_time = time.time() - start_time
    
    def _generate_id(self, item: T) -> str:
        """Generate a unique ID for an item."""
        content = json.dumps(item, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()[:12]


class StreamProcessor(Generic[T, R]):
    """Processes data items as a stream with memory efficiency."""
    
    def __init__(self, config: ProcessingConfig = None):
        self.config = config or ProcessingConfig()
        self.metrics = ProcessingMetrics()
    
    def process_stream(
        self,
        items: Iterator[T],
        processor: Callable[[T], R]
    ) -> Iterator[R]:
        """Process items from a stream, yielding results."""
        self.metrics = ProcessingMetrics()
        self.metrics.start_time = time.time()
        
        batch = []
        
        for item in items:
            self.metrics.total_items += 1
            batch.append(item)
            
            if len(batch) >= self.config.batch_size:
                yield from self._process_batch(batch, processor)
                batch = []
        
        # Process remaining items
        if batch:
            yield from self._process_batch(batch, processor)
        
        self.metrics.end_time = time.time()
    
    def _process_batch(
        self,
        batch: List[T],
        processor: Callable[[T], R]
    ) -> Iterator[R]:
        """Process a batch of items."""
        for item in batch:
            try:
                result = processor(item)
                self.metrics.processed_items += 1
                yield result
            except Exception as e:
                self.metrics.failed_items += 1
                self.metrics.errors.append(str(e))
                
                if not self.config.skip_on_error:
                    raise


class DataTransformer:
    """Transforms data between different formats."""
    
    @staticmethod
    def flatten_dict(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
        """Flatten a nested dictionary."""
        result = {}
        
        def _flatten(obj: Any, prefix: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{prefix}{separator}{key}" if prefix else key
                    _flatten(value, new_key)
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    new_key = f"{prefix}{separator}{i}" if prefix else str(i)
                    _flatten(value, new_key)
            else:
                result[prefix] = obj
        
        _flatten(data)
        return result
    
    @staticmethod
    def unflatten_dict(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
        """Unflatten a flattened dictionary."""
        result = {}
        
        for key, value in data.items():
            parts = key.split(separator)
            current = result
            
            for i, part in enumerate(parts[:-1]):
                if part.isdigit():
                    part = int(part)
                
                if part not in current:
                    # Check if next part is a digit (list) or string (dict)
                    next_part = parts[i + 1]
                    current[part] = [] if next_part.isdigit() else {}
                
                current = current[part]
            
            final_key = parts[-1]
            if final_key.isdigit():
                final_key = int(final_key)
            current[final_key] = value
        
        return result
    
    @staticmethod
    def filter_keys(data: Dict[str, Any], keys: List[str], include: bool = True) -> Dict[str, Any]:
        """Filter dictionary keys."""
        if include:
            return {k: v for k, v in data.items() if k in keys}
        else:
            return {k: v for k, v in data.items() if k not in keys}
    
    @staticmethod
    def rename_keys(data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """Rename dictionary keys."""
        return {mapping.get(k, k): v for k, v in data.items()}
    
    @staticmethod
    def apply_defaults(data: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values to missing keys."""
        result = defaults.copy()
        result.update(data)
        return result


class DataAggregator:
    """Aggregates data from multiple sources."""
    
    def __init__(self):
        self.data: Dict[str, List[Any]] = defaultdict(list)
    
    def add(self, key: str, value: Any):
        """Add a value to a key."""
        self.data[key].append(value)
    
    def add_batch(self, key: str, values: List[Any]):
        """Add multiple values to a key."""
        self.data[key].extend(values)
    
    def get(self, key: str) -> List[Any]:
        """Get all values for a key."""
        return self.data.get(key, [])
    
    def count(self, key: str) -> int:
        """Count values for a key."""
        return len(self.data.get(key, []))
    
    def sum(self, key: str) -> float:
        """Sum numeric values for a key."""
        values = self.data.get(key, [])
        return sum(v for v in values if isinstance(v, (int, float)))
    
    def average(self, key: str) -> float:
        """Calculate average of numeric values for a key."""
        values = [v for v in self.data.get(key, []) if isinstance(v, (int, float))]
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    def min(self, key: str) -> Any:
        """Get minimum value for a key."""
        values = self.data.get(key, [])
        if not values:
            return None
        return min(values)
    
    def max(self, key: str) -> Any:
        """Get maximum value for a key."""
        values = self.data.get(key, [])
        if not values:
            return None
        return max(values)
    
    def unique(self, key: str) -> List[Any]:
        """Get unique values for a key."""
        return list(set(self.data.get(key, [])))
    
    def group_by(self, key: str, group_key: Callable[[Any], str]) -> Dict[str, List[Any]]:
        """Group values by a key function."""
        result = defaultdict(list)
        for value in self.data.get(key, []):
            group = group_key(value)
            result[group].append(value)
        return dict(result)
    
    def to_dict(self) -> Dict[str, List[Any]]:
        """Convert to regular dictionary."""
        return dict(self.data)
    
    def clear(self):
        """Clear all data."""
        self.data.clear()


class DataCache:
    """Simple in-memory cache for processed data."""
    
    def __init__(self, max_size: int = 1000, ttl: float = 300.0):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, tuple] = {}  # (value, timestamp)
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self._lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return value
                else:
                    del self.cache[key]
            return None
    
    def set(self, key: str, value: Any):
        """Set a value in cache."""
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]
            
            self.cache[key] = (value, time.time())
    
    def delete(self, key: str):
        """Delete a value from cache."""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self):
        """Clear all cached values."""
        with self._lock:
            self.cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)
    
    def cleanup(self):
        """Remove expired entries."""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                k for k, (_, ts) in self.cache.items()
                if current_time - ts >= self.ttl
            ]
            for key in expired_keys:
                del self.cache[key]


class DataPipeline:
    """Chains multiple processing steps together."""
    
    def __init__(self):
        self.steps: List[Callable[[Any], Any]] = []
        self.step_names: List[str] = []
    
    def add_step(self, step: Callable[[Any], Any], name: str = None):
        """Add a processing step."""
        self.steps.append(step)
        self.step_names.append(name or f"step_{len(self.steps)}")
        return self
    
    def process(self, data: Any) -> Any:
        """Process data through all steps."""
        result = data
        for i, step in enumerate(self.steps):
            try:
                result = step(result)
            except Exception as e:
                raise ProcessingError(
                    f"Pipeline failed at step '{self.step_names[i]}': {str(e)}",
                    cause=e
                )
        return result
    
    def process_batch(self, items: List[Any]) -> List[Any]:
        """Process multiple items through the pipeline."""
        return [self.process(item) for item in items]


# Utility functions

def chunk_list(items: List[T], chunk_size: int) -> Iterator[List[T]]:
    """Split a list into chunks of specified size."""
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> T:
    """Retry a function with exponential backoff."""
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                time.sleep(delay)
    
    raise last_error


def safe_get(data: Dict[str, Any], path: str, default: Any = None, separator: str = ".") -> Any:
    """Safely get a nested value from a dictionary."""
    keys = path.split(separator)
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and key.isdigit() and int(key) < len(current):
            current = current[int(key)]
        else:
            return default
    
    return current


def safe_set(data: Dict[str, Any], path: str, value: Any, separator: str = "."):
    """Safely set a nested value in a dictionary."""
    keys = path.split(separator)
    current = data
    
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value


def merge_dicts(*dicts: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
    """Merge multiple dictionaries."""
    result = {}
    
    for d in dicts:
        if deep:
            for key, value in d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value, deep=True)
                else:
                    result[key] = value
        else:
            result.update(d)
    
    return result


def hash_data(data: Any) -> str:
    """Generate a hash for any data."""
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()


def format_size(size_bytes: int) -> str:
    """Format byte size to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """Format duration to human readable string."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.2f}h"
