"""Suggestion filtering and prioritization service."""

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
        """Keep only suggestions whose file is in the diff (relaxed validation)."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract files from diff
        diff_files = set()
        for line in patch.split('\n'):
            if line.startswith('+++ b/') or line.startswith('--- a/'):
                file_path = line.split('/', 1)[-1] if '/' in line else line[6:]
                diff_files.add(file_path.strip())
        
        logger.debug(f"Files in diff: {diff_files}")

        valid = []
        for s in suggestions:
            # Relaxed validation: just check if file is in diff
            if not s.relevant_file:
                logger.debug(f"Suggestion has no file, keeping: {s.one_sentence_summary[:50]}")
                valid.append(s)
            elif s.relevant_file in diff_files or any(s.relevant_file.endswith(f) or f.endswith(s.relevant_file) for f in diff_files):
                logger.debug(f"File {s.relevant_file} found in diff, keeping")
                valid.append(s)
            else:
                logger.warning(f"File {s.relevant_file} NOT in diff files {diff_files}, discarding")
        
        logger.info(f"Diff validation: {len(suggestions)} -> {len(valid)} suggestions")
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
