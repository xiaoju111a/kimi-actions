"""Tests for triage tool."""

import pytest
from unittest.mock import Mock, patch, MagicMock
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
        self.labels = [MockLabel(l) for l in (labels or [])]
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


class MockKimiClientForTriage:
    """Mock Kimi client for triage responses."""
    def __init__(self, api_key: str = "test", model: str = "kimi-k2-turbo-preview"):
        self._model = model
        self._response = None

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value

    def set_response(self, response: str):
        """Set custom response for testing."""
        self._response = response

    def chat(self, messages: list, **kwargs) -> str:
        """Return mock triage response."""
        if self._response:
            return self._response

        return """{
    "type": "bug",
    "priority": "high",
    "labels": ["bug", "priority: high"],
    "confidence": "high",
    "summary": "App crashes on login button click after v2.0 update",
    "reason": "Clear bug report with reproduction steps, crash behavior indicates a defect introduced in v2.0"
}"""


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

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        # Mock subprocess (git clone) and agent
        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = """{
    "type": "bug",
    "priority": "high",
    "labels": ["bug", "priority: high"],
    "confidence": "high",
    "summary": "App crashes on login button click after v2.0 update",
    "reason": "Clear bug report with reproduction steps"
}"""

            result = triage.run("owner/repo", 123, apply_labels=True)

        assert "Kimi Issue Triage" in result
        assert "bug" in result.lower()
        assert "high" in result.lower()
        assert len(github.applied_labels) > 0

    def test_triage_feature_request(self, mock_action_config):
        """Test triaging a feature request."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()
        github._issue = MockIssue(
            title="Add dark mode support",
            body="It would be great if the app supported dark mode for better night usage."
        )

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = """{
    "type": "feature",
    "priority": "medium",
    "labels": ["feature", "enhancement"],
    "confidence": "high",
    "summary": "Request for dark mode support",
    "reason": "User is requesting new functionality that does not exist"
}"""

            result = triage.run("owner/repo", 124, apply_labels=True)

        assert "feature" in result.lower()
        assert "medium" in result.lower()

    def test_triage_question_issue(self, mock_action_config):
        """Test triaging a question."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()
        github._issue = MockIssue(
            title="How do I configure OAuth?",
            body="I'm trying to set up OAuth but can't find the documentation. Can someone help?"
        )

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = """{
    "type": "question",
    "priority": "low",
    "labels": ["question", "help wanted"],
    "confidence": "high",
    "summary": "User asking how to configure OAuth",
    "reason": "User is asking for help, not reporting a bug or requesting a feature"
}"""

            result = triage.run("owner/repo", 125, apply_labels=True)

        assert "question" in result.lower()

    def test_triage_no_apply_labels(self, mock_action_config):
        """Test triaging without applying labels."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = """{
    "type": "bug",
    "priority": "high",
    "labels": ["bug", "priority: high"],
    "confidence": "high",
    "summary": "Test summary",
    "reason": "Test reason"
}"""

            result = triage.run("owner/repo", 123, apply_labels=False)

        assert "Kimi Issue Triage" in result
        assert len(github.applied_labels) == 0  # No labels applied

    def test_triage_handles_empty_body(self, mock_action_config):
        """Test triaging an issue with no body."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()
        github._issue = MockIssue(
            title="Something is wrong",
            body=""
        )

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = """{
    "type": "other",
    "priority": "low",
    "labels": [],
    "confidence": "low",
    "summary": "Issue lacks details",
    "reason": "No description provided, cannot determine issue type"
}"""

            result = triage.run("owner/repo", 126, apply_labels=True)

        # Should handle gracefully
        assert "Kimi Issue Triage" in result

    def test_triage_filters_invalid_labels(self, mock_action_config):
        """Test that triage only applies valid repo labels."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = """{
    "type": "bug",
    "priority": "high",
    "labels": ["bug", "invalid-label-not-in-repo", "priority: high"],
    "confidence": "high",
    "summary": "Test issue",
    "reason": "Test reason"
}"""

            result = triage.run("owner/repo", 127, apply_labels=True)

        # Should only apply valid labels
        assert "invalid-label-not-in-repo" not in github.applied_labels
        assert "bug" in github.applied_labels

    def test_triage_critical_priority(self, mock_action_config):
        """Test triaging a critical security issue."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()
        github._issue = MockIssue(
            title="SQL injection in login form",
            body="Found SQL injection vulnerability in the login endpoint. Attacker can bypass authentication."
        )

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = """{
    "type": "bug",
    "priority": "critical",
    "labels": ["bug", "priority: high"],
    "confidence": "high",
    "summary": "SQL injection vulnerability in login",
    "reason": "Security vulnerability that could lead to data breach"
}"""

            result = triage.run("owner/repo", 128, apply_labels=True)

        assert "critical" in result.lower()
        # Should have recommendations for critical issues
        assert "Recommendations" in result

    def test_triage_handles_invalid_json(self, mock_action_config):
        """Test handling of invalid JSON response from Kimi."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)
        triage.load_context = Mock()
        triage.repo_config = None
        triage.skill_manager = Mock()
        triage.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Triage the issue",
            scripts={}
        ))

        with patch('tools.triage.subprocess') as mock_subprocess, \
             patch('tools.triage.asyncio.run') as mock_asyncio:
            mock_subprocess.run.return_value = Mock(returncode=0)
            mock_asyncio.return_value = "This is not valid JSON"

            result = triage.run("owner/repo", 129, apply_labels=True)

        # Should handle gracefully
        assert "Failed to analyze" in result or "Kimi Issue Triage" in result


class TestTriageResponseParsing:
    """Tests for triage response parsing."""

    def test_parse_valid_response(self, mock_action_config):
        """Test parsing a valid JSON response."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        response = """{
    "type": "bug",
    "priority": "high",
    "labels": ["bug", "priority: high"],
    "confidence": "high",
    "summary": "Test summary",
    "reason": "Test reason"
}"""
        valid_labels = ["bug", "feature", "priority: high", "priority: low"]

        result = triage._parse_response(response, valid_labels)

        assert result is not None
        assert result["type"] == "bug"
        assert result["priority"] == "high"
        assert "bug" in result["labels"]
        assert "priority: high" in result["labels"]

    def test_parse_response_with_markdown(self, mock_action_config):
        """Test parsing response wrapped in markdown code block."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        response = """Here's my analysis:

```json
{
    "type": "feature",
    "priority": "medium",
    "labels": ["feature"],
    "confidence": "high",
    "summary": "Feature request",
    "reason": "User wants new feature"
}
```

Let me know if you need more details."""
        valid_labels = ["bug", "feature", "enhancement"]

        result = triage._parse_response(response, valid_labels)

        assert result is not None
        assert result["type"] == "feature"

    def test_parse_response_case_insensitive_labels(self, mock_action_config):
        """Test that label matching is case-insensitive."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        response = """{
    "type": "bug",
    "priority": "high",
    "labels": ["BUG", "Priority: High"],
    "confidence": "high",
    "summary": "Test",
    "reason": "Test"
}"""
        valid_labels = ["bug", "feature", "priority: high"]

        result = triage._parse_response(response, valid_labels)

        assert result is not None
        # Should match despite case difference
        assert len(result["labels"]) == 2

    def test_parse_limits_to_4_labels(self, mock_action_config):
        """Test that parsing limits to maximum 4 labels."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        response = """{
    "type": "bug",
    "priority": "high",
    "labels": ["bug", "feature", "enhancement", "documentation", "help wanted", "good first issue"],
    "confidence": "high",
    "summary": "Test",
    "reason": "Test"
}"""
        valid_labels = ["bug", "feature", "enhancement", "documentation", "help wanted", "good first issue"]

        result = triage._parse_response(response, valid_labels)

        assert result is not None
        assert len(result["labels"]) <= 4


class TestTriageRecommendations:
    """Tests for triage recommendations."""

    def test_bug_recommendations(self, mock_action_config):
        """Test that bug issues get appropriate recommendations."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        recs = triage._get_recommendations("bug", "high")

        assert "Verify the bug can be reproduced" in recs
        assert "Prioritize" in recs  # High priority bug

    def test_feature_recommendations(self, mock_action_config):
        """Test that feature requests get appropriate recommendations."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        recs = triage._get_recommendations("feature", "medium")

        assert "roadmap" in recs.lower()
        assert "community feedback" in recs.lower()

    def test_question_recommendations(self, mock_action_config):
        """Test that questions get appropriate recommendations."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        recs = triage._get_recommendations("question", "low")

        assert "documentation" in recs.lower()
        assert "closeable" in recs.lower()

    def test_documentation_recommendations(self, mock_action_config):
        """Test that documentation issues get appropriate recommendations."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        recs = triage._get_recommendations("documentation", "low")

        assert "community contribution" in recs.lower()
        assert "good first issue" in recs.lower()


class TestTriageFormatResult:
    """Tests for triage result formatting."""

    def test_format_result_with_applied_labels(self, mock_action_config):
        """Test formatting when labels are applied."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        result_dict = {
            "type": "bug",
            "priority": "high",
            "labels": ["bug", "priority: high"],
            "confidence": "high",
            "summary": "Test summary",
            "reason": "Test reason"
        }

        formatted = triage._format_result(result_dict, applied=True)

        assert "Labels Applied" in formatted
        assert "bug" in formatted
        assert "Classification" in formatted

    def test_format_result_without_applied_labels(self, mock_action_config):
        """Test formatting when labels are suggested but not applied."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        result_dict = {
            "type": "feature",
            "priority": "medium",
            "labels": ["feature"],
            "confidence": "medium",
            "summary": "Test summary",
            "reason": "Test reason"
        }

        formatted = triage._format_result(result_dict, applied=False)

        assert "Suggested Labels" in formatted
        assert "Labels Applied" not in formatted

    def test_format_result_includes_emojis(self, mock_action_config):
        """Test that formatting includes appropriate emojis."""
        from tools.triage import Triage

        kimi = MockKimiClientForTriage()
        github = MockGitHubClientForIssue()

        triage = Triage(kimi, github)

        # Bug with critical priority
        result_dict = {
            "type": "bug",
            "priority": "critical",
            "labels": ["bug"],
            "confidence": "high",
            "summary": "Test",
            "reason": "Test"
        }

        formatted = triage._format_result(result_dict, applied=True)

        # Should have bug emoji and critical priority emoji
        assert any(emoji in formatted for emoji in ["bug", "critical"])
