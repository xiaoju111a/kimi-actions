"""Tests for automatic incremental review detection."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.reviewer import Reviewer


class TestIncrementalReviewDetection:
    """Test automatic incremental review detection."""

    @pytest.fixture
    def reviewer(self):
        """Create a reviewer instance with mocked GitHub client."""
        github_mock = Mock()
        reviewer = Reviewer(github_mock)
        return reviewer

    def test_no_previous_review_uses_full_review(self, reviewer):
        """Test that full review is used when no previous review exists."""
        reviewer.github.get_last_bot_comment = Mock(return_value=None)

        result = reviewer._should_use_incremental_review("owner/repo", 123)

        assert result is False
        reviewer.github.get_last_bot_comment.assert_called_once_with("owner/repo", 123)

    def test_old_review_uses_full_review(self, reviewer):
        """Test that full review is used when previous review is too old (>7 days)."""
        old_date = datetime.now() - timedelta(days=8)
        reviewer.github.get_last_bot_comment = Mock(
            return_value={"sha": "abc123", "comment_id": 456, "created_at": old_date}
        )

        result = reviewer._should_use_incremental_review("owner/repo", 123)

        assert result is False

    def test_recent_review_with_new_commits_uses_incremental(self, reviewer):
        """Test that incremental review is used when there's a recent review with new commits."""
        recent_date = datetime.now() - timedelta(days=1)
        reviewer.github.get_last_bot_comment = Mock(
            return_value={"sha": "abc123", "comment_id": 456, "created_at": recent_date}
        )

        # Mock new commits
        commit_mock = Mock()
        commit_mock.sha = "def456"
        reviewer.github.get_commits_since = Mock(return_value=[commit_mock])

        result = reviewer._should_use_incremental_review("owner/repo", 123)

        assert result is True
        reviewer.github.get_commits_since.assert_called_once_with(
            "owner/repo", 123, "abc123"
        )

    def test_recent_review_without_new_commits_returns_true(self, reviewer):
        """Test that incremental review returns True even without new commits (will show 'no changes' message)."""
        recent_date = datetime.now() - timedelta(days=1)
        reviewer.github.get_last_bot_comment = Mock(
            return_value={"sha": "abc123", "comment_id": 456, "created_at": recent_date}
        )

        # No new commits
        reviewer.github.get_commits_since = Mock(return_value=[])

        result = reviewer._should_use_incremental_review("owner/repo", 123)

        assert result is True

    def test_error_handling_falls_back_to_full_review(self, reviewer):
        """Test that errors fall back to full review."""
        reviewer.github.get_last_bot_comment = Mock(side_effect=Exception("API error"))

        result = reviewer._should_use_incremental_review("owner/repo", 123)

        assert result is False


class TestIncrementalReviewMessage:
    """Test incremental review messaging."""

    @pytest.fixture
    def reviewer(self):
        """Create a reviewer instance."""
        github_mock = Mock()
        return Reviewer(github_mock)

    def test_no_changes_message(self, reviewer):
        """Test that appropriate message is shown when no new changes."""
        # Mock incremental diff returning None
        reviewer._get_incremental_diff = Mock(return_value=(None, "abc123"))
        reviewer._should_use_incremental_review = Mock(return_value=True)

        pr_mock = Mock()
        pr_mock.head.sha = "def456"
        pr_mock.head.ref = "feature-branch"
        pr_mock.base.ref = "main"
        reviewer.github.get_pr = Mock(return_value=pr_mock)
        reviewer.load_context = Mock()

        result = reviewer.run("owner/repo", 123)

        assert "No new changes since last review" in result
        assert "✅" in result
