"""Tests for suggestion_service module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from suggestion_service import SuggestionService
from models import CodeSuggestion, SeverityLevel, SuggestionControl, ReviewOptions


class TestSuggestionService:
    """Tests for SuggestionService class."""

    @pytest.fixture
    def service(self):
        return SuggestionService()

    @pytest.fixture
    def sample_suggestions(self):
        return [
            CodeSuggestion(
                id="1",
                relevant_file="main.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Fix the bug",
                existing_code="old code",
                improved_code="new code",
                one_sentence_summary="Bug fix",
                label="bug",
                severity=SeverityLevel.HIGH
            ),
            CodeSuggestion(
                id="2",
                relevant_file="auth.py",
                language="python",
                relevant_lines_start=10,
                relevant_lines_end=15,
                suggestion_content="Security issue",
                existing_code="insecure",
                improved_code="secure",
                one_sentence_summary="Security fix",
                label="security",
                severity=SeverityLevel.CRITICAL
            ),
            CodeSuggestion(
                id="3",
                relevant_file="utils.py",
                language="python",
                relevant_lines_start=20,
                relevant_lines_end=25,
                suggestion_content="Performance tip",
                existing_code="slow",
                improved_code="fast",
                one_sentence_summary="Perf improvement",
                label="performance",
                severity=SeverityLevel.LOW
            ),
        ]

    def test_filter_by_category_all_enabled(self, service, sample_suggestions):
        options = ReviewOptions(bug=True, security=True, performance=True)
        filtered = service._filter_by_category(sample_suggestions, options)
        assert len(filtered) == 3

    def test_filter_by_category_bug_only(self, service, sample_suggestions):
        options = ReviewOptions(bug=True, security=False, performance=False)
        filtered = service._filter_by_category(sample_suggestions, options)
        assert len(filtered) == 1
        assert filtered[0].label == "bug"

    def test_filter_by_category_security_disabled(self, service, sample_suggestions):
        options = ReviewOptions(bug=True, security=False, performance=True)
        filtered = service._filter_by_category(sample_suggestions, options)
        assert len(filtered) == 2
        assert all(s.label != "security" for s in filtered)

    def test_remove_duplicates(self, service):
        suggestions = [
            CodeSuggestion(
                id="1",
                relevant_file="main.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Fix",
                existing_code="",
                improved_code="",
                one_sentence_summary="Same summary here",
                label="bug",
                severity=SeverityLevel.MEDIUM
            ),
            CodeSuggestion(
                id="2",
                relevant_file="main.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Fix again",
                existing_code="",
                improved_code="",
                one_sentence_summary="Same summary here",
                label="bug",
                severity=SeverityLevel.MEDIUM
            ),
        ]
        unique = service._remove_duplicates(suggestions)
        assert len(unique) == 1

    def test_remove_duplicates_different_files(self, service):
        suggestions = [
            CodeSuggestion(
                id="1",
                relevant_file="a.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Fix",
                existing_code="",
                improved_code="",
                one_sentence_summary="Same summary",
                label="bug",
                severity=SeverityLevel.MEDIUM
            ),
            CodeSuggestion(
                id="2",
                relevant_file="b.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Fix",
                existing_code="",
                improved_code="",
                one_sentence_summary="Same summary",
                label="bug",
                severity=SeverityLevel.MEDIUM
            ),
        ]
        unique = service._remove_duplicates(suggestions)
        assert len(unique) == 2

    def test_calculate_score_severity(self, service):
        critical = CodeSuggestion(
            id="1",
            relevant_file="a.py",
            language="python",
            relevant_lines_start=1,
            relevant_lines_end=5,
            suggestion_content="",
            existing_code="",
            improved_code="",
            one_sentence_summary="",
            label="bug",
            severity=SeverityLevel.CRITICAL
        )
        low = CodeSuggestion(
            id="2",
            relevant_file="b.py",
            language="python",
            relevant_lines_start=1,
            relevant_lines_end=5,
            suggestion_content="",
            existing_code="",
            improved_code="",
            one_sentence_summary="",
            label="bug",
            severity=SeverityLevel.LOW
        )

        assert service._calculate_score(critical) > service._calculate_score(low)

    def test_calculate_score_label(self, service):
        security = CodeSuggestion(
            id="1",
            relevant_file="a.py",
            language="python",
            relevant_lines_start=1,
            relevant_lines_end=5,
            suggestion_content="",
            existing_code="",
            improved_code="",
            one_sentence_summary="",
            label="security",
            severity=SeverityLevel.MEDIUM
        )
        perf = CodeSuggestion(
            id="2",
            relevant_file="b.py",
            language="python",
            relevant_lines_start=1,
            relevant_lines_end=5,
            suggestion_content="",
            existing_code="",
            improved_code="",
            one_sentence_summary="",
            label="performance",
            severity=SeverityLevel.MEDIUM
        )

        assert service._calculate_score(security) > service._calculate_score(perf)

    def test_validate_against_diff(self, service):
        suggestions = [
            CodeSuggestion(
                id="1",
                relevant_file="main.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Fix",
                existing_code="old_function()",
                improved_code="",
                one_sentence_summary="",
                label="bug",
                severity=SeverityLevel.MEDIUM
            ),
            CodeSuggestion(
                id="2",
                relevant_file="main.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Fix",
                existing_code="nonexistent_code()",
                improved_code="",
                one_sentence_summary="",
                label="bug",
                severity=SeverityLevel.MEDIUM
            ),
        ]

        patch = "+old_function()\n-something"
        valid = service._validate_against_diff(suggestions, patch)

        assert len(valid) == 1
        assert valid[0].existing_code == "old_function()"

    def test_validate_against_diff_no_existing_code(self, service):
        suggestions = [
            CodeSuggestion(
                id="1",
                relevant_file="main.py",
                language="python",
                relevant_lines_start=1,
                relevant_lines_end=5,
                suggestion_content="Add this",
                existing_code="",  # No existing code
                improved_code="",
                one_sentence_summary="",
                label="bug",
                severity=SeverityLevel.MEDIUM
            ),
        ]

        valid = service._validate_against_diff(suggestions, "any patch")
        assert len(valid) == 1  # Should be kept

    def test_process_suggestions_limits_count(self, service, sample_suggestions):
        service.control = SuggestionControl(max_suggestions=1)
        options = ReviewOptions()

        kept, discarded = service.process_suggestions(sample_suggestions, options)

        assert len(kept) <= 1

    def test_process_suggestions_filters_severity(self, service, sample_suggestions):
        service.control = SuggestionControl(severity_level_filter=SeverityLevel.HIGH)
        options = ReviewOptions()

        kept, discarded = service.process_suggestions(sample_suggestions, options)

        # Should only keep HIGH and CRITICAL
        for s in kept:
            assert s.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]

    def test_process_suggestions_sorts_by_score(self, service, sample_suggestions):
        options = ReviewOptions()
        kept, _ = service.process_suggestions(sample_suggestions, options)

        if len(kept) >= 2:
            # Should be sorted by score descending
            scores = [s.rank_score for s in kept]
            assert scores == sorted(scores, reverse=True)
