"""Sample test module 3 for testing large PR reviews."""
import json
from typing import Dict, Any


def parse_json(data: str) -> Dict[str, Any]:
    """Parse JSON string."""
    return json.loads(data)


def serialize_json(data: Dict[str, Any]) -> str:
    """Serialize dict to JSON."""
    return json.dumps(data, indent=2)


class DataProcessor:
    """Data processing utilities."""
    
    def clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove null values from dict."""
        return {k: v for k, v in data.items() if v is not None}
    
    def merge_dicts(self, dict1: Dict, dict2: Dict) -> Dict:
        """Merge two dictionaries."""
        result = dict1.copy()
        result.update(dict2)
        return result
