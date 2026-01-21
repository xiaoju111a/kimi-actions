"""Type definitions for Kimi Actions."""

from dataclasses import dataclass
from enum import Enum


class SeverityLevel(Enum):
    """Severity levels for code suggestions."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CodeSuggestion:
    """A single code suggestion."""

    id: str
    relevant_file: str
    language: str
    suggestion_content: str
    existing_code: str
    improved_code: str
    one_sentence_summary: str
    relevant_lines_start: int
    relevant_lines_end: int
    label: str  # bug, performance, security
    severity: SeverityLevel = SeverityLevel.MEDIUM
    rank_score: float = 0.0


@dataclass
class ReviewOptions:
    """Review options configuration."""

    bug: bool = True
    performance: bool = True
    security: bool = True


@dataclass
class SuggestionControl:
    """Suggestion control configuration."""

    max_suggestions: int = 20
    severity_level_filter: SeverityLevel = SeverityLevel.MEDIUM
