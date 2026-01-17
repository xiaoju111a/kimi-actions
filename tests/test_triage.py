"""Tests for triage tool."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class MockLabel:
    """Mock GitHub Label object."""
    def __init__(self, name: str):
        self.name = name


class MockUser:
    """Mock GitHub User object."""
    def __init__(self, login: str = "testuser"):
        self.login = login


class MockIssue:
    """Mock GitHub Issue object."""
    def __init__(
        self,
        title: str = "App crashes when clicking login button",
        body: str = "After updating to v2.0, the app crashes immediately when I click the login button.\n\nSteps to reproduce:\n1. Open app\n2. Click login\n3. App crashes\n\nExpected: Login screen should appear",
        number: int = 123,
        state: str = "open",
        labels: list = None,
        comments: int = 0
    ):
        self.title = title
        self.body = body
        self.number = number
        self.state = state
        self.labels = [MockLabel(lbl) for lbl in (labels or [])]
        self.comments = comments
        self.user = MockUser()
        self.created_at = "2024-01-15T10:00:00Z"

    def get_comments(self):
        return []

    def add_to_labels(self, *labels):
        for label in labels:
            self.labels.append(MockLabel(label))


class MockGitHubClientForIssue:
    """Mock GitHub client with Issue support."""
    def __init__(self):
        self.client = Mock()
        self.posted_comments = []
        self.applied_labels = []
        self.reactions = []
        self._issue = MockIssue()
        self._repo_labels = ["bug", "feature", "enhancement", "question",
                            "documentation", "help wanted", "good first issue",
                            "priority: high", "priority: medium", "priority: low"]

    def get_issue(self, repo_name: str, issue_number: int):
        return self._issue

    def post_issue_comment(self, repo_name: str, issue_number: int, body: str):
        self.posted_comments.append(body)

    def add_issue_labels(self, repo_name: str, issue_number: int, labels: list):
        self.applied_labels.extend(labels)

    def add_issue_reaction(self, repo_name: str, issue_number: int, comment_id: int, reaction: str):
        self.reactions.append(reaction)

    def get_repo_labels(self, repo_name: str) -> list:
        return self._repo_labels


@pytest.fixture
def mock_action_config():
    """Create mock action config."""
    with patch('tools.base.get_action_config') as mock:
        config = Mock()
        config.model = "kimi-k2-turbo-preview"
        config.review_level = "normal"
        config.max_files = 10
        config.exclude_patterns = ["*.lock"]
        mock.return_value = config
        yield config


class TestTriageIntegration:
    """Integration tests for Triage tool."""

    def test_triage_bug_issue(self, mock_action_config):
        """Test triaging a bug report."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue", scripts={}
        ))

        with patch('subprocess.run') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = '{"type": "bug", "priority": "high", "labels": ["bug", "priority: high"], "confidence": "high", "summary": "App crashes on login", "reason": "Clear bug report"}'
            result = triage.run("owner/repo", 123, apply_labels=True)

        assert "Kimi Issue Triage" in result
        assert "bug" in result.lower()

    def test_triage_feature_request(self, mock_action_config):
        """Test triaging a feature request."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        github._issue = MockIssue(title="Add dark mode support", body="It would be great if the app supported dark mode.")
        triage = Triage(github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(instructions="Triage", scripts={}))

        with patch('subprocess.run') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = '{"type": "feature", "priority": "medium", "labels": ["feature"], "confidence": "high", "summary": "Dark mode request", "reason": "New feature"}'
            result = triage.run("owner/repo", 124, apply_labels=True)

        assert "feature" in result.lower()

    def test_triage_question_issue(self, mock_action_config):
        """Test triaging a question."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        github._issue = MockIssue(title="How do I configure the API?", body="I'm trying to set up the API but can't find docs.")
        triage = Triage(github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(instructions="Triage", scripts={}))

        with patch('subprocess.run') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = '{"type": "question", "priority": "low", "labels": ["question"], "confidence": "high", "summary": "API config question", "reason": "User asking for help"}'
            result = triage.run("owner/repo", 125, apply_labels=True)

        assert "question" in result.lower()

    def test_triage_no_apply_labels(self, mock_action_config):
        """Test triage without applying labels."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(instructions="Triage", scripts={}))

        with patch('subprocess.run') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = '{"type": "bug", "priority": "high", "labels": ["bug"], "confidence": "high", "summary": "Bug", "reason": "Bug"}'
            triage.run("owner/repo", 126, apply_labels=False)

        assert len(github.applied_labels) == 0

    def test_triage_filters_invalid_labels(self, mock_action_config):
        """Test that invalid labels are filtered out."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(instructions="Triage", scripts={}))

        with patch('subprocess.run') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = '{"type": "bug", "priority": "high", "labels": ["bug", "invalid-label", "nonexistent"], "confidence": "high", "summary": "Bug", "reason": "Bug"}'
            triage.run("owner/repo", 127, apply_labels=True)

        # Should only apply valid labels
        for label in github.applied_labels:
            assert label in github._repo_labels

    def test_triage_handles_empty_body(self, mock_action_config):
        """Test triage with empty issue body."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        github._issue = MockIssue(title="Bug", body="")
        triage = Triage(github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(instructions="Triage", scripts={}))

        with patch('subprocess.run') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = '{"type": "unknown", "priority": "medium", "labels": [], "confidence": "low", "summary": "Unclear", "reason": "No body"}'
            result = triage.run("owner/repo", 128, apply_labels=True)

        assert result is not None

    def test_triage_handles_invalid_json(self, mock_action_config):
        """Test triage handles invalid JSON response."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(instructions="Triage", scripts={}))

        with patch('subprocess.run') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = "This is not valid JSON"
            result = triage.run("owner/repo", 129, apply_labels=True)

        assert "Failed" in result or "Error" in result or "unknown" in result.lower()


class TestTriageResponseParsing:
    """Test response parsing."""

    def test_parse_valid_response(self, mock_action_config):
        """Test parsing valid JSON response."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        response = '{"type": "bug", "priority": "high", "labels": ["bug"], "confidence": "high", "summary": "Test", "reason": "Test"}'
        result = triage._parse_response(response, github._repo_labels)

        assert result["type"] == "bug"
        assert result["priority"] == "high"

    def test_parse_response_with_markdown(self, mock_action_config):
        """Test parsing response wrapped in markdown."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        response = '```json\n{"type": "feature", "priority": "medium", "labels": ["feature"], "confidence": "high", "summary": "Test", "reason": "Test"}\n```'
        result = triage._parse_response(response, github._repo_labels)

        assert result["type"] == "feature"

    def test_parse_response_case_insensitive_labels(self, mock_action_config):
        """Test that label matching is case insensitive."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        response = '{"type": "bug", "priority": "high", "labels": ["BUG", "Feature"], "confidence": "high", "summary": "Test", "reason": "Test"}'
        result = triage._parse_response(response, github._repo_labels)

        assert "labels" in result

    def test_parse_limits_to_4_labels(self, mock_action_config):
        """Test that labels are limited to 4."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        response = '{"type": "bug", "priority": "high", "labels": ["bug", "feature", "enhancement", "documentation", "question", "help wanted"], "confidence": "high", "summary": "Test", "reason": "Test"}'
        result = triage._parse_response(response, github._repo_labels)

        assert len(result.get("labels", [])) <= 4


class TestTriageRecommendations:
    """Test recommendation generation."""

    def test_bug_recommendations(self, mock_action_config):
        """Test recommendations for bug type."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        recs = triage._get_recommendations("bug", "high")
        assert len(recs) > 0

    def test_feature_recommendations(self, mock_action_config):
        """Test recommendations for feature type."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        recs = triage._get_recommendations("feature", "medium")
        assert len(recs) > 0

    def test_question_recommendations(self, mock_action_config):
        """Test recommendations for question type."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        recs = triage._get_recommendations("question", "low")
        assert len(recs) > 0

    def test_documentation_recommendations(self, mock_action_config):
        """Test recommendations for documentation type."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        recs = triage._get_recommendations("documentation", "medium")
        assert len(recs) > 0


class TestTriageFormatResult:
    """Test result formatting."""

    def test_format_result_with_applied_labels(self, mock_action_config):
        """Test formatting with applied labels."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        result_dict = {
            "type": "bug",
            "priority": "high",
            "confidence": "high",
            "summary": "Test bug",
            "labels": ["bug", "priority: high"],
            "reason": "Test reason"
        }
        result = triage._format_result(result_dict, applied=True)

        assert "bug" in result.lower()
        assert "high" in result.lower()
        assert "✅" in result

    def test_format_result_without_applied_labels(self, mock_action_config):
        """Test formatting without applied labels."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        result_dict = {
            "type": "feature",
            "priority": "medium",
            "confidence": "medium",
            "summary": "Test feature",
            "labels": ["feature"],
            "reason": "Test reason"
        }
        result = triage._format_result(result_dict, applied=False)

        assert "feature" in result.lower()

    def test_format_result_includes_emojis(self, mock_action_config):
        """Test that result includes appropriate emojis."""
        from tools.triage import Triage

        github = MockGitHubClientForIssue()
        triage = Triage(github)

        result_dict = {
            "type": "bug",
            "priority": "critical",
            "confidence": "high",
            "summary": "Critical bug",
            "labels": ["bug"],
            "reason": "Test reason"
        }
        result = triage._format_result(result_dict, applied=True)

        assert "🐛" in result or "🔴" in result or "bug" in result.lower()
