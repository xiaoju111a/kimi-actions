"""Suggestion filtering and prioritization service."""

from typing import List, Tuple

from models import CodeSuggestion, SeverityLevel, SuggestionControl, ReviewOptions


class SuggestionService:
    """Service for filtering and prioritizing code suggestions."""

    SEVERITY_ORDER = {
        SeverityLevel.CRITICAL: 4,
        SeverityLevel.HIGH: 3,
        SeverityLevel.MEDIUM: 2,
        SeverityLevel.LOW: 1,
    }

    def __init__(self, control: SuggestionControl = None):
        self.control = control or SuggestionControl()

    def process_suggestions(
        self, suggestions: List[CodeSuggestion], options: ReviewOptions, patch: str = ""
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
        kept = [
            s for s in filtered if self.SEVERITY_ORDER.get(s.severity, 2) >= min_level
        ]
        discarded = [
            s for s in filtered if self.SEVERITY_ORDER.get(s.severity, 2) < min_level
        ]

        # 6. Limit count
        if len(kept) > self.control.max_suggestions:
            discarded = kept[self.control.max_suggestions :] + discarded
            kept = kept[: self.control.max_suggestions]

        return kept, discarded

    def _filter_by_category(
        self, suggestions: List[CodeSuggestion], options: ReviewOptions
    ) -> List[CodeSuggestion]:
        """Filter by enabled categories."""
        category_map = {
            "bug": options.bug,
            "performance": options.performance,
            "security": options.security,
        }
        return [s for s in suggestions if category_map.get(s.label.lower(), True)]

    def _validate_against_diff(
        self, suggestions: List[CodeSuggestion], patch: str
    ) -> List[CodeSuggestion]:
        """Keep only suggestions whose file AND line numbers are in the diff (strict validation)."""
        import logging
        import re

        logger = logging.getLogger(__name__)

        # Extract files and valid line numbers from diff
        diff_files = set()
        file_line_map = {}  # file -> set of valid line numbers

        current_file = None
        current_line = 0

        for line in patch.split("\n"):
            # Standard git diff format
            if line.startswith("+++ b/"):
                file_path = line.split("/", 1)[-1] if "/" in line else line[6:]
                current_file = file_path.strip()
                diff_files.add(current_file)
                file_line_map[current_file] = set()
            elif line.startswith("--- a/"):
                file_path = line.split("/", 1)[-1] if "/" in line else line[6:]
                diff_files.add(file_path.strip())
            # Custom format: ## File: path/to/file.py
            elif line.startswith("## File: "):
                file_path = line[9:].split(" (")[0].split(" [")[0].strip()
                current_file = file_path
                diff_files.add(current_file)
                file_line_map[current_file] = set()
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            elif line.startswith("@@"):
                hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if hunk_match and current_file:
                    current_line = int(hunk_match.group(1))
            # Track line numbers in the new file
            elif current_file and current_file in file_line_map:
                if line.startswith("-"):
                    # Deleted line, don't increment
                    continue
                elif line.startswith("+") or (
                    not line.startswith("\\") and current_line > 0
                ):
                    # Added or context line
                    file_line_map[current_file].add(current_line)
                    current_line += 1

        logger.debug(f"Files in diff: {diff_files}")
        logger.debug(
            f"Line map: {[(f, len(lines)) for f, lines in file_line_map.items()]}"
        )

        valid = []
        for s in suggestions:
            # Strict validation: check file AND line numbers
            if not s.relevant_file:
                logger.debug(
                    f"Suggestion has no file, keeping: {s.one_sentence_summary[:50]}"
                )
                valid.append(s)
                continue

            # Find matching file in diff
            matched_file = None
            if s.relevant_file in diff_files:
                matched_file = s.relevant_file
            else:
                # Try fuzzy matching
                for f in diff_files:
                    if s.relevant_file.endswith(f) or f.endswith(s.relevant_file):
                        matched_file = f
                        break

            if not matched_file:
                logger.warning(
                    f"File {s.relevant_file} NOT in diff files {diff_files}, discarding"
                )
                continue

            # Check if line numbers are in the diff
            if matched_file in file_line_map:
                valid_lines = file_line_map[matched_file]
                start_line = s.relevant_lines_start or 0
                end_line = s.relevant_lines_end or start_line

                # Check if any line in the range is in the diff
                suggestion_lines = (
                    set(range(start_line, end_line + 1)) if start_line > 0 else set()
                )

                if not suggestion_lines:
                    # No line numbers specified, keep it
                    logger.debug(f"No line numbers for {s.relevant_file}, keeping")
                    valid.append(s)
                elif suggestion_lines & valid_lines:
                    # At least one line overlaps with diff
                    logger.debug(
                        f"Lines {start_line}-{end_line} in {s.relevant_file} overlap with diff, keeping"
                    )
                    valid.append(s)
                else:
                    logger.warning(
                        f"Lines {start_line}-{end_line} in {s.relevant_file} NOT in diff (valid: {min(valid_lines) if valid_lines else 'none'}-{max(valid_lines) if valid_lines else 'none'}), discarding"
                    )
            else:
                # No line map for this file (shouldn't happen), keep it to be safe
                logger.debug(f"No line map for {matched_file}, keeping")
                valid.append(s)

        logger.info(
            f"Diff validation (strict): {len(suggestions)} -> {len(valid)} suggestions"
        )
        return valid

    def _remove_duplicates(
        self, suggestions: List[CodeSuggestion]
    ) -> List[CodeSuggestion]:
        """Remove duplicates based on file + lines + summary."""
        seen = set()
        unique = []
        for s in suggestions:
            key = (
                s.relevant_file,
                s.relevant_lines_start,
                s.relevant_lines_end,
                s.one_sentence_summary[:50],
            )
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    def _calculate_score(self, s: CodeSuggestion) -> float:
        """Calculate priority score."""
        severity_scores = {
            SeverityLevel.CRITICAL: 40,
            SeverityLevel.HIGH: 30,
            SeverityLevel.MEDIUM: 20,
            SeverityLevel.LOW: 10,
        }
        label_scores = {"security": 30, "bug": 25, "performance": 20}

        score = severity_scores.get(s.severity, 20) + label_scores.get(
            s.label.lower(), 10
        )

        if s.existing_code and s.improved_code:
            score += min(abs(len(s.improved_code) - len(s.existing_code)) / 10, 20)

        return score
