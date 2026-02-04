"""Tests for Reviewer tool."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class MockGitHubClient:
    """Mock GitHub client for testing."""

    def __init__(self):
        self.posted_comments = []
        self.reviews = []

    def get_pr(self, repo, pr_number):
        return Mock(
            number=pr_number,
            title="Test PR",
            body="Test PR body",
            head=Mock(ref="feature-branch", sha="abc123"),
            base=Mock(ref="main"),
            get_commits=Mock(
                return_value=[
                    Mock(sha="commit1", commit=Mock(message="First commit")),
                    Mock(sha="commit2", commit=Mock(message="Second commit")),
                ]
            ),
        )

    def get_pr_diff(self, repo, pr_number):
        return """diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,6 @@
 def main():
+    # New comment
     print("Hello")
     pass
"""

    def post_comment(self, repo, pr_number, body):
        self.posted_comments.append(body)

    def create_review_with_comments(
        self, repo, pr_number, comments, body="", event="COMMENT"
    ):
        self.reviews.append(
            {
                "repo": repo,
                "pr_number": pr_number,
                "comments": comments,
                "body": body,
                "event": event,
            }
        )

    def get_last_bot_comment(self, repo, pr_number):
        return None

    def get_commits_since(self, repo, pr_number, sha):
        return []


@pytest.fixture
def mock_action_config():
    """Create mock action config."""
    with patch("tools.base.get_action_config") as mock:
        config = Mock()
        config.model = "kimi-k2-thinking"
        config.review_level = "normal"
        config.max_files = 50
        config.exclude_patterns = ["*.lock"]
        config.review = Mock(num_max_findings=10, extra_instructions="")
        mock.return_value = config
        yield config


class TestReviewerBasic:
    """Test basic Reviewer functionality."""

    def test_reviewer_initialization(self, mock_action_config):
        """Test Reviewer initialization."""
        from tools.reviewer import Reviewer

        github = MockGitHubClient()
        reviewer = Reviewer(github)

        assert reviewer.github == github
        assert reviewer.skill_name == "code-review"

    def test_skill_name_property(self, mock_action_config):
        """Test skill_name property."""
        from tools.reviewer import Reviewer

        github = MockGitHubClient()
        reviewer = Reviewer(github)

        assert reviewer.skill_name == "code-review"


class TestReviewerIntegration:
    """Integration tests for Reviewer."""

    def test_run_with_empty_diff(self, mock_action_config):
        """Test run with empty diff."""
        from tools.reviewer import Reviewer

        github = MockGitHubClient()
        github.get_pr_diff = Mock(return_value="")
        reviewer = Reviewer(github)
        reviewer.load_context = Mock()

        result = reviewer.run("owner/repo", 123)

        assert "No changes to review" in result

    def test_run_with_no_skill(self, mock_action_config):
        """Test run when skill is not found."""
        from tools.reviewer import Reviewer

        github = MockGitHubClient()
        reviewer = Reviewer(github)
        reviewer.load_context = Mock()
        reviewer.get_skill = Mock(return_value=None)

        result = reviewer.run("owner/repo", 123)

        assert "Error" in result
        assert "skill not found" in result.lower()

    def test_run_success_with_mock_agent(self, mock_action_config):
        """Test successful run with mocked agent - now returns Markdown directly."""
        from tools.reviewer import Reviewer

        github = MockGitHubClient()
        reviewer = Reviewer(github)
        reviewer.load_context = Mock()

        # Mock skill
        skill = Mock()
        skill.instructions = "Review code"
        skill.scripts = {}
        reviewer.get_skill = Mock(return_value=skill)

        # Mock clone_repo
        with patch.object(reviewer, "clone_repo", return_value=True):
            # Mock asyncio.run to return Markdown response
            with patch("asyncio.run") as mock_asyncio:
                mock_asyncio.return_value = """## 🌗 Pull Request Overview

Good code with no issues found.

**Reviewed Changes**
Kimi performed full review on 1 changed files and found 0 issues.

---

✅ **No issues found!** The code looks good."""

                result = reviewer.run("owner/repo", 123)

                assert "Pull request overview" in result or "Good code" in result


class TestReviewerIncrementalDiff:
    """Test incremental diff functionality - DEPRECATED."""

    def test_no_changes_message(self, mock_action_config):
        """Test that no changes message is returned when SHA matches."""
        from tools.reviewer import Reviewer

        github = MockGitHubClient()
        # Mock last review with same SHA as current PR
        github.get_last_bot_comment = Mock(return_value={"sha": "abc123"})
        
        reviewer = Reviewer(github)
        reviewer.load_context = Mock()

        result = reviewer.run("owner/repo", 123)

        assert "No new changes since last review" in result
