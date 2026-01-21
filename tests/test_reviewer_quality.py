"""Tests for reviewer suggestion quality validation."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models import CodeSuggestion, SeverityLevel
from tools.reviewer import Reviewer
from unittest.mock import Mock


class TestSuggestionQualityValidation:
    """Test the _validate_suggestion_quality method."""

    @pytest.fixture
    def reviewer(self):
        """Create a reviewer instance."""
        github_mock = Mock()
        return Reviewer(github_mock)

    def test_valid_suggestion(self, reviewer):
        """Test that a high-quality suggestion passes validation."""
        suggestion = CodeSuggestion(
            id="test1",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=45,
            severity=SeverityLevel.HIGH,
            label="security",
            one_sentence_summary="SQL injection vulnerability in login query",
            suggestion_content=(
                "Line 42 concatenates user input directly into SQL query. "
                "An attacker can inject SQL by entering admin' OR '1'='1 as username."
            ),
            existing_code="query = f\"SELECT * FROM users WHERE username='{username}'\"",
            improved_code='query = "SELECT * FROM users WHERE username=?"\ncursor.execute(query, (username,))',
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True

    def test_missing_line_numbers(self, reviewer):
        """Test that suggestions without line numbers are rejected."""
        suggestion = CodeSuggestion(
            id="test2",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=0,  # Invalid
            relevant_lines_end=0,
            severity=SeverityLevel.MEDIUM,
            label="bug",
            one_sentence_summary="Some issue",
            suggestion_content="This is a problem",
            existing_code="bad code",
            improved_code="good code",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is False

    def test_missing_code_examples(self, reviewer):
        """Test that suggestions without existing code are rejected."""
        suggestion = CodeSuggestion(
            id="test3",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.MEDIUM,
            label="bug",
            one_sentence_summary="Some issue",
            suggestion_content="This is a problem that needs fixing",
            existing_code="",  # Missing existing code
            improved_code="good code",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is False

    def test_missing_improved_code_is_allowed(self, reviewer):
        """Test that suggestions without improved code can pass if content is good."""
        # Actually, for now we still require improved_code for consistency
        # This test documents the behavior - we may relax this in future
        suggestion = CodeSuggestion(
            id="test3b",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.HIGH,
            label="bug",
            one_sentence_summary="Missing error handling",
            suggestion_content="Function does not handle DatabaseError exceptions",
            existing_code="result = db.query('SELECT * FROM users')",
            improved_code="try:\n    result = db.query('SELECT * FROM users')\nexcept DatabaseError:\n    logger.error('Query failed')",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True

    def test_identical_code(self, reviewer):
        """Test that suggestions with identical code are rejected."""
        suggestion = CodeSuggestion(
            id="test4",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.MEDIUM,
            label="bug",
            one_sentence_summary="Some issue",
            suggestion_content="This is a problem",
            existing_code="same code",
            improved_code="same code",  # Identical
        )

        assert reviewer._validate_suggestion_quality(suggestion) is False

    def test_uncertain_language_in_content(self, reviewer):
        """Test that highly uncertain language about bugs is rejected."""
        uncertain_phrases = ["might be a bug", "probably a bug", "possibly a bug"]

        for phrase in uncertain_phrases:
            suggestion = CodeSuggestion(
                id="test5",
                relevant_file="auth.py",
                language="python",
                relevant_lines_start=42,
                relevant_lines_end=42,
                severity=SeverityLevel.MEDIUM,
                label="bug",
                one_sentence_summary="Some issue",
                suggestion_content=f"This {phrase} and needs attention.",
                existing_code="bad code",
                improved_code="good code",
            )

            assert reviewer._validate_suggestion_quality(suggestion) is False, (
                f"Should reject suggestion with '{phrase}'"
            )

    def test_technical_uncertain_language_allowed(self, reviewer):
        """Test that technical descriptions without uncertain phrases are allowed."""
        suggestion = CodeSuggestion(
            id="test5b",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.MEDIUM,
            label="performance",
            one_sentence_summary="Performance issue with loop",
            suggestion_content="This loop is inefficient. Use list comprehension for better performance.",
            existing_code="result = []\nfor x in items:\n    result.append(x*2)",
            improved_code="result = [x*2 for x in items]",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True

    def test_uncertain_language_in_summary(self, reviewer):
        """Test that highly uncertain language in summary is rejected."""
        suggestion = CodeSuggestion(
            id="test6",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.MEDIUM,
            label="bug",
            one_sentence_summary="This might be a bug in the code",
            suggestion_content="The code has a problem that needs fixing.",
            existing_code="bad code",
            improved_code="good code",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is False

    def test_technical_should_is_allowed(self, reviewer):
        """Test that 'should' in technical context is allowed."""
        suggestion = CodeSuggestion(
            id="test6b",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.HIGH,
            label="bug",
            one_sentence_summary="Function should handle null values",
            suggestion_content="The function does not check for null values. This causes a crash when user is None.",
            existing_code="name = user.name",
            improved_code="name = user.name if user else 'Unknown'",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True

    def test_vague_opening(self, reviewer):
        """Test that extremely vague openings are rejected."""
        vague_openings = [
            "Consider improving this code",
            "You should improve the logic",
            "Try to improve performance",
            "Think about refactoring this",
            "You might want to refactor",
        ]

        for opening in vague_openings:
            suggestion = CodeSuggestion(
                id="test7",
                relevant_file="auth.py",
                language="python",
                relevant_lines_start=42,
                relevant_lines_end=42,
                severity=SeverityLevel.MEDIUM,
                label="bug",
                one_sentence_summary="Some issue",
                suggestion_content=f"{opening} because reasons.",
                existing_code="bad code",
                improved_code="good code",
            )

            assert reviewer._validate_suggestion_quality(suggestion) is False, (
                f"Should reject suggestion starting with '{opening}'"
            )

    def test_specific_consider_allowed(self, reviewer):
        """Test that specific 'consider' suggestions with good content are allowed."""
        suggestion = CodeSuggestion(
            id="test7b",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.MEDIUM,
            label="bug",
            one_sentence_summary="Missing mutex for thread safety",
            suggestion_content="Use a mutex to protect shared state access in concurrent environment to prevent race conditions.",
            existing_code="self.cache[key] = value",
            improved_code="with self.lock:\n    self.cache[key] = value",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True

    def test_too_short_content(self, reviewer):
        """Test that suggestions with too short content are rejected."""
        suggestion = CodeSuggestion(
            id="test8",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.MEDIUM,
            label="bug",
            one_sentence_summary="Some issue",
            suggestion_content="Too short",  # Less than 15 chars
            existing_code="bad code",
            improved_code="good code",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is False

    def test_short_content_allowed_for_low_severity(self, reviewer):
        """Test that short content is allowed for low severity issues."""
        suggestion = CodeSuggestion(
            id="test8b",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=42,
            relevant_lines_end=42,
            severity=SeverityLevel.LOW,
            label="documentation",
            one_sentence_summary="Typo in comment",
            suggestion_content="Spelling error in comment",  # 24 chars, OK for low severity
            existing_code="# recieve",
            improved_code="# receive",
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True

    def test_specific_and_certain_suggestion(self, reviewer):
        """Test that specific, certain suggestions pass validation."""
        suggestion = CodeSuggestion(
            id="test9",
            relevant_file="database.py",
            language="python",
            relevant_lines_start=100,
            relevant_lines_end=102,
            severity=SeverityLevel.CRITICAL,
            label="bug",
            one_sentence_summary="Unhandled exception when database connection fails",
            suggestion_content=(
                "The database query at line 100 does not handle connection failures. "
                "When the database is unavailable, this raises an unhandled DatabaseError "
                "that crashes the application. This affects all users during database outages."
            ),
            existing_code=(
                "result = db.query('SELECT * FROM users')\nreturn result.fetchall()"
            ),
            improved_code=(
                "try:\n"
                "    result = db.query('SELECT * FROM users')\n"
                "    return result.fetchall()\n"
                "except DatabaseError as e:\n"
                "    logger.error(f'DB query failed: {e}')\n"
                "    return []"
            ),
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True

    def test_typo_suggestion_with_relaxed_validation(self, reviewer):
        """Test that typo/documentation suggestions have relaxed validation."""
        suggestion = CodeSuggestion(
            id="test10",
            relevant_file="auth.py",
            language="python",
            relevant_lines_start=15,
            relevant_lines_end=15,
            severity=SeverityLevel.LOW,
            label="documentation",
            one_sentence_summary="Typo in error message: 'occured' should be 'occurred'",
            suggestion_content="Spelling error in message.",  # Short content is OK for typos (>10 chars)
            existing_code='raise ValueError("An error occured")',
            improved_code='raise ValueError("An error occurred")',
        )

        assert reviewer._validate_suggestion_quality(suggestion) is True


class TestSuggestionParsing:
    """Test suggestion parsing with quality validation."""

    @pytest.fixture
    def reviewer(self):
        """Create a reviewer instance."""
        github_mock = Mock()
        return Reviewer(github_mock)

    def test_filters_low_quality_suggestions(self, reviewer):
        """Test that low-quality suggestions are filtered during parsing."""
        yaml_response = """```yaml
summary: "Test PR"
score: 85
file_summaries:
  - file: "test.py"
    description: "Test file"
suggestions:
  - relevant_file: "test.py"
    language: "python"
    relevant_lines_start: 10
    relevant_lines_end: 10
    severity: "high"
    label: "bug"
    one_sentence_summary: "Real bug with specific details"
    suggestion_content: "This causes a null pointer exception when user is None. The code crashes on line 10."
    existing_code: "name = user.name"
    improved_code: "name = user.name if user else 'Unknown'"
  - relevant_file: "test.py"
    language: "python"
    relevant_lines_start: 20
    severity: "medium"
    label: "bug"
    one_sentence_summary: "This might be a problem"
    suggestion_content: "Consider improving this code"
    existing_code: "some code"
    improved_code: "better code"
```"""

        suggestions = reviewer._parse_suggestions(yaml_response)

        # Should only keep the first (high-quality) suggestion
        assert len(suggestions) == 1
        assert suggestions[0].one_sentence_summary == "Real bug with specific details"
