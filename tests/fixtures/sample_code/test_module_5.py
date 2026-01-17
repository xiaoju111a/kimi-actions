"""Sample test module 5 for testing large PR reviews."""
import re
from typing import List


def extract_numbers(text: str) -> List[int]:
    """Extract all numbers from text."""
    return [int(n) for n in re.findall(r'\d+', text)]


def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text."""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)


class TextProcessor:
    """Text processing utilities."""
    
    def remove_html_tags(self, html: str) -> str:
        """Remove HTML tags from string."""
        return re.sub(r'<[^>]+>', '', html)
    
    def count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())
