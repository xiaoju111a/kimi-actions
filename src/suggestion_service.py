"""Suggestion filtering and prioritization service."""

import re
from typing import List, Tuple

from models import CodeSuggestion, SeverityLevel, SuggestionControl, ReviewOptions


class SuggestionService:
    """Service for filtering and prioritizing code suggestions."""

    SEVERITY_ORDER = {
        SeverityLevel.CRITICAL: 4,
        SeverityLevel.HIGH: 3,
        SeverityLevel.MEDIUM: 2,
        SeverityLevel.LOW: 1
    }

    def __init__(self, control: SuggestionControl = None):
        self.control = control or SuggestionControl()

    def process_suggestions(
        self,
        suggestions: List[CodeSuggestion],
        options: ReviewOptions,
        patch: str = ""
    ) -> Tuple[List[CodeSuggestion], List[CodeSuggestion]]:
        """Process suggestions: filter, dedupe, prioritize, limit."""

        # 1. Filter by category
        filtered = self._filter_by_category(suggestions, options)

        # 2. Validate against diff
        if patch:
            filtered = self._validate_against_diff(filtered, patch)

        # 3. Remove duplicates
        filtered = self._remove_duplicates(filtered)

        # 4. Calculate scores and sort
        for s in filtered:
            s.rank_score = self._calculate_score(s)
        filtered.sort(key=lambda x: x.rank_score, reverse=True)

        # 5. Filter by severity
        min_level = self.SEVERITY_ORDER.get(self.control.severity_level_filter, 2)
        kept = [s for s in filtered if self.SEVERITY_ORDER.get(s.severity, 2) >= min_level]
        discarded = [s for s in filtered if self.SEVERITY_ORDER.get(s.severity, 2) < min_level]

        # 6. Limit count
        if len(kept) > self.control.max_suggestions:
            discarded = kept[self.control.max_suggestions:] + discarded
            kept = kept[:self.control.max_suggestions]

        return kept, discarded

    def _filter_by_category(self, suggestions: List[CodeSuggestion], options: ReviewOptions) -> List[CodeSuggestion]:
        """Filter by enabled categories."""
        category_map = {"bug": options.bug, "performance": options.performance, "security": options.security}
        return [s for s in suggestions if category_map.get(s.label.lower(), True)]

    def _validate_against_diff(self, suggestions: List[CodeSuggestion], patch: str) -> List[CodeSuggestion]:
        """Keep only suggestions whose existing_code is in the diff."""
        normalized_patch = re.sub(r'\s+', ' ', patch).lower()

        valid = []
        for s in suggestions:
            if not s.existing_code:
                valid.append(s)
            elif re.sub(r'\s+', ' ', s.existing_code).lower() in normalized_patch:
                valid.append(s)
        return valid

    def _remove_duplicates(self, suggestions: List[CodeSuggestion]) -> List[CodeSuggestion]:
        """Remove duplicates based on file + lines + summary."""
        seen = set()
        unique = []
        for s in suggestions:
            key = (s.relevant_file, s.relevant_lines_start, s.relevant_lines_end, s.one_sentence_summary[:50])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    def _calculate_score(self, s: CodeSuggestion) -> float:
        """Calculate priority score."""
        severity_scores = {SeverityLevel.CRITICAL: 40, SeverityLevel.HIGH: 30, SeverityLevel.MEDIUM: 20, SeverityLevel.LOW: 10}
        label_scores = {"security": 30, "bug": 25, "performance": 20}

        score = severity_scores.get(s.severity, 20) + label_scores.get(s.label.lower(), 10)

        if s.existing_code and s.improved_code:
            score += min(abs(len(s.improved_code) - len(s.existing_code)) / 10, 20)

        return score
