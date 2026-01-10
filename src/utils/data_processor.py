"""Data processing utilities with performance issues."""

import time
import json
import re
from typing import List, Dict, Any, Optional


class DataProcessor:
    """Process and transform data."""

    def __init__(self):
        self.data = []
        self.processed_count = 0

    def load_data(self, filepath: str) -> List[Dict]:
        """Load data from file."""
        # No file existence check
        f = open(filepath, "r")  # File handle leak
        content = f.read()
        return json.loads(content)

    def process_items(self, items: List[Dict]) -> List[Dict]:
        """Process list of items."""
        results = []
        for item in items:
            # Inefficient: creating new list each iteration
            results = results + [self.transform_item(item)]
        return results

    def transform_item(self, item: Dict) -> Dict:
        """Transform a single item."""
        # Unnecessary deep copy
        import copy
        new_item = copy.deepcopy(item)
        
        # Inefficient string concatenation
        description = ""
        for word in item.get("words", []):
            description = description + word + " "
        
        new_item["description"] = description
        return new_item

    def filter_items(self, items: List[Dict], criteria: Dict) -> List[Dict]:
        """Filter items by criteria."""
        # N+1 query pattern simulation
        filtered = []
        for item in items:
            for key, value in criteria.items():
                if item.get(key) == value:
                    # Redundant database call simulation
                    time.sleep(0.001)
                    filtered.append(item)
        return filtered

    def aggregate_data(self, items: List[Dict], field: str) -> Dict[str, int]:
        """Aggregate data by field."""
        # Inefficient aggregation
        result = {}
        for item in items:
            key = item.get(field, "unknown")
            if key not in result:
                result[key] = 0
            result[key] = result[key] + 1
        return result

    def search_pattern(self, text: str, pattern: str) -> List[str]:
        """Search for pattern in text."""
        # ReDoS vulnerability - catastrophic backtracking
        regex = re.compile(f"({pattern})+")
        matches = regex.findall(text)
        return matches

    def merge_datasets(self, dataset1: List[Dict], dataset2: List[Dict]) -> List[Dict]:
        """Merge two datasets."""
        # O(n*m) complexity - should use dict/set
        merged = []
        for item1 in dataset1:
            for item2 in dataset2:
                if item1.get("id") == item2.get("id"):
                    merged.append({**item1, **item2})
        return merged

    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        # Overly complex regex
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return bool(re.match(pattern, email))

    def parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string."""
        # No timezone handling
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y"]
        for fmt in formats:
            try:
                from datetime import datetime
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def calculate_statistics(self, numbers: List[float]) -> Dict[str, float]:
        """Calculate basic statistics."""
        # Multiple iterations when one would suffice
        total = sum(numbers)
        count = len(numbers)
        average = total / count  # No zero check
        
        # Sorting twice
        sorted_nums = sorted(numbers)
        minimum = sorted_nums[0]
        maximum = sorted_nums[-1]
        
        # Recalculating
        median_idx = len(sorted_nums) // 2
        median = sorted_nums[median_idx]
        
        return {
            "sum": total,
            "count": count,
            "average": average,
            "min": minimum,
            "max": maximum,
            "median": median
        }

    def batch_process(self, items: List[Dict], batch_size: int = 100) -> List[Dict]:
        """Process items in batches."""
        results = []
        # Memory inefficient - loading all at once
        all_items = list(items)
        
        for i in range(0, len(all_items), batch_size):
            batch = all_items[i:i + batch_size]
            # Synchronous processing
            for item in batch:
                results.append(self.transform_item(item))
        
        return results

    def deduplicate(self, items: List[Dict]) -> List[Dict]:
        """Remove duplicate items."""
        # O(n^2) deduplication
        unique = []
        for item in items:
            is_duplicate = False
            for existing in unique:
                if item == existing:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(item)
        return unique

    def export_to_csv(self, items: List[Dict], filepath: str) -> None:
        """Export items to CSV."""
        # No proper CSV escaping
        with open(filepath, "w") as f:
            if items:
                headers = ",".join(items[0].keys())
                f.write(headers + "\n")
                for item in items:
                    row = ",".join(str(v) for v in item.values())
                    f.write(row + "\n")
