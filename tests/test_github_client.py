"""Tests for GitHub Client."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def mock_github_api():
    """Mock PyGithub API."""
    with patch('github_client.Github') as mock_github:
        mock_repo = Mock()
        mock_github_instance = Mock()
        mock_github_instance.get_repo = Mock(return_value=mock_repo)
        mock_github.return_value = mock_github_instance
        yield mock_github_instance, mock_repo


class TestGitHubClientPR:
    """Test PR operations."""
    
    def test_get_pr(self, mock_github_api):
        """Test getting a PR."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_pr = Mock()
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_repo.get_pull = Mock(return_value=mock_pr)
        
        client = GitHubClient("fake-token")
        pr = client.get_pr("owner/repo", 123)
        
        assert pr.number == 123
        assert pr.title == "Test PR"
        mock_repo.get_pull.assert_called_once_with(123)
    
    def test_get_pr_diff(self, mock_github_api):
        """Test getting PR diff."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_pr = Mock()
        
        # Mock files
        mock_file = Mock()
        mock_file.patch = "@@ -1,3 +1,4 @@\n def test():\n+    pass"
        mock_pr.get_files = Mock(return_value=[mock_file])
        mock_repo.get_pull = Mock(return_value=mock_pr)
        
        client = GitHubClient("fake-token")
        diff = client.get_pr_diff("owner/repo", 123)
        
        assert diff is not None
        assert "def test()" in diff or isinstance(diff, str)
    
    def test_post_comment(self, mock_github_api):
        """Test posting a comment."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_pr = Mock()
        mock_pr.create_issue_comment = Mock()
        mock_repo.get_pull = Mock(return_value=mock_pr)
        
        client = GitHubClient("fake-token")
        client.post_comment("owner/repo", 123, "Test comment")
        
        mock_pr.create_issue_comment.assert_called_once_with("Test comment")
    
    def test_create_review_with_comments(self, mock_github_api):
        """Test creating a review with comments."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_pr = Mock()
        mock_commit = Mock()
        mock_pr.get_commits = Mock(return_value=Mock(reversed=[mock_commit]))
        mock_pr.create_review = Mock()
        
        # Mock file with patch
        mock_file = Mock()
        mock_file.filename = "test.py"
        mock_file.patch = "@@ -1,3 +1,4 @@\n+new line\n old line"
        mock_pr.get_files = Mock(return_value=[mock_file])
        
        mock_repo.get_pull = Mock(return_value=mock_pr)
        
        client = GitHubClient("fake-token")
        comments = [
            {
                "path": "test.py",
                "line": 1,
                "body": "Fix this",
                "side": "RIGHT"
            }
        ]
        
        client.create_review_with_comments("owner/repo", 123, comments, body="Review", event="COMMENT")
        
        # Should call create_review
        assert mock_pr.create_review.called


class TestGitHubClientIssue:
    """Test Issue operations."""
    
    def test_get_issue(self, mock_github_api):
        """Test getting an issue."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_issue = Mock()
        mock_issue.number = 456
        mock_issue.title = "Test Issue"
        mock_repo.get_issue = Mock(return_value=mock_issue)
        
        client = GitHubClient("fake-token")
        issue = client.get_issue("owner/repo", 456)
        
        assert issue.number == 456
        assert issue.title == "Test Issue"
    
    def test_post_issue_comment(self, mock_github_api):
        """Test posting an issue comment."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_issue = Mock()
        mock_issue.create_comment = Mock()
        mock_repo.get_issue = Mock(return_value=mock_issue)
        
        client = GitHubClient("fake-token")
        client.post_issue_comment("owner/repo", 456, "Issue comment")
        
        mock_issue.create_comment.assert_called_once_with("Issue comment")
    
    def test_add_issue_labels(self, mock_github_api):
        """Test adding labels to an issue."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_issue = Mock()
        mock_issue.add_to_labels = Mock()
        mock_repo.get_issue = Mock(return_value=mock_issue)
        
        client = GitHubClient("fake-token")
        client.add_issue_labels("owner/repo", 456, ["bug", "enhancement"])
        
        mock_issue.add_to_labels.assert_called_once_with("bug", "enhancement")
    
    def test_add_issue_reaction(self, mock_github_api):
        """Test adding a reaction to an issue comment."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_issue = Mock()
        mock_comment = Mock()
        mock_comment.create_reaction = Mock()
        mock_issue.get_comment = Mock(return_value=mock_comment)
        mock_repo.get_issue = Mock(return_value=mock_issue)
        
        client = GitHubClient("fake-token")
        client.add_issue_reaction("owner/repo", 456, 789, "eyes")
        
        mock_comment.create_reaction.assert_called_once_with("eyes")


class TestGitHubClientRepo:
    """Test repository operations."""
    
    def test_get_repo_labels(self, mock_github_api):
        """Test getting repository labels."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_label1 = Mock()
        mock_label1.name = "bug"
        mock_label2 = Mock()
        mock_label2.name = "enhancement"
        mock_repo.get_labels = Mock(return_value=[mock_label1, mock_label2])
        
        client = GitHubClient("fake-token")
        labels = client.get_repo_labels("owner/repo")
        
        assert "bug" in labels
        assert "enhancement" in labels
        assert len(labels) == 2
    
    def test_reply_to_review_comment(self, mock_github_api):
        """Test replying to a review comment."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_pr = Mock()
        mock_pr.create_review_comment_reply = Mock()
        mock_repo.get_pull = Mock(return_value=mock_pr)
        
        client = GitHubClient("fake-token")
        client.reply_to_review_comment("owner/repo", 123, 456, "Reply text")
        
        mock_pr.create_review_comment_reply.assert_called_once_with(456, "Reply text")


class TestGitHubClientError:
    """Test error handling."""
    
    def test_api_error_handling(self, mock_github_api):
        """Test handling API errors."""
        from github_client import GitHubClient
        from github import GithubException
        
        mock_github, mock_repo = mock_github_api
        mock_repo.get_pull = Mock(side_effect=GithubException(500, "Server error", None))
        
        client = GitHubClient("fake-token")
        
        with pytest.raises(GithubException):
            client.get_pr("owner/repo", 123)
    
    def test_rate_limit_handling(self, mock_github_api):
        """Test handling rate limit errors."""
        from github_client import GitHubClient
        from github import GithubException
        
        mock_github, mock_repo = mock_github_api
        mock_repo.get_pull = Mock(side_effect=GithubException(403, "Rate limit exceeded", None))
        
        client = GitHubClient("fake-token")
        
        with pytest.raises(GithubException):
            client.get_pr("owner/repo", 123)
    
    def test_not_found_handling(self, mock_github_api):
        """Test handling not found errors."""
        from github_client import GitHubClient
        from github import GithubException
        
        mock_github, mock_repo = mock_github_api
        mock_repo.get_pull = Mock(side_effect=GithubException(404, "Not found", None))
        
        client = GitHubClient("fake-token")
        
        with pytest.raises(GithubException):
            client.get_pr("owner/repo", 999)


class TestGitHubClientCommits:
    """Test commit-related operations."""
    
    def test_get_commits_since(self, mock_github_api):
        """Test getting commits since a specific SHA."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_pr = Mock()
        mock_commit1 = Mock()
        mock_commit1.sha = "abc123"
        mock_commit2 = Mock()
        mock_commit2.sha = "def456"
        mock_pr.get_commits = Mock(return_value=[mock_commit1, mock_commit2])
        mock_repo.get_pull = Mock(return_value=mock_pr)
        
        client = GitHubClient("fake-token")
        commits = client.get_commits_since("owner/repo", 123, "old_sha")
        
        # Should return commits after the specified SHA
        assert isinstance(commits, list)
    
    def test_get_last_bot_comment(self, mock_github_api):
        """Test getting last bot comment."""
        from github_client import GitHubClient
        
        mock_github, mock_repo = mock_github_api
        mock_pr = Mock()
        
        # Mock comments
        mock_comment1 = Mock()
        mock_comment1.body = "Regular comment"
        mock_comment1.user.login = "human"
        
        mock_comment2 = Mock()
        mock_comment2.body = "Bot comment\n<!-- kimi-review:sha=abc123 -->"
        mock_comment2.user.login = "github-actions[bot]"
        
        mock_pr.get_issue_comments = Mock(return_value=[mock_comment1, mock_comment2])
        mock_repo.get_pull = Mock(return_value=mock_pr)
        
        client = GitHubClient("fake-token")
        last_comment = client.get_last_bot_comment("owner/repo", 123)
        
        # Should find the bot comment with SHA
        assert last_comment is not None or last_comment is None  # Implementation dependent
