"""Tests for Labels tool."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def mock_github():
    """Mock GitHub client."""
    return Mock()


@pytest.fixture
def mock_config():
    """Mock action config."""
    with patch('tools.base.get_action_config') as mock_cfg:
        config = Mock()
        config.model = "kimi-k2-thinking"
        config.exclude_patterns = []
        mock_cfg.return_value = config
        yield config


@pytest.fixture
def mock_pr():
    """Mock PR object."""
    pr = Mock()
    pr.number = 123
    pr.title = "Fix memory leak"
    pr.head.ref = "bugfix/memory-leak"
    return pr


class TestLabelsBasic:
    """Test basic Labels functionality."""
    
    def test_labels_initialization(self, mock_github):
        """Test Labels tool initialization."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        assert labels.skill_name == "labels"
    
    def test_skill_name_property(self, mock_github):
        """Test skill_name property."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        assert labels.skill_name == "labels"


class TestLabelsLabelSuggestion:
    """Test label suggestion generation."""
    
    @patch('tools.labels.asyncio.run')
    def test_run_suggests_labels(self, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test successful label suggestion."""
        from tools.labels import Labels
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_repo_labels.return_value = ["bug", "feature", "enhancement", "performance"]
        mock_github.get_pr_diff.return_value = "diff content"
        mock_asyncio.return_value = '{"labels": ["bug", "performance"], "reason": "Fixes memory leak"}'
        
        labels = Labels(github=mock_github)
        labels.get_skill = Mock(return_value=None)
        
        result = labels.run("owner/repo", 123)
        
        assert "Kimi Labels" in result
        assert "bug" in result
        # Note: Only first 3 labels are applied, and they must be in valid_labels
        # The test should check that at least bug is present
    
    @patch('tools.labels.asyncio.run')
    def test_run_with_no_labels(self, mock_asyncio, mock_github, mock_pr):
        """Test run with no labels suggested."""
        from tools.labels import Labels
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_repo_labels.return_value = ["bug", "feature"]
        mock_github.get_pr_diff.return_value = "diff content"
        mock_asyncio.return_value = '{"labels": [], "reason": "No clear category"}'
        
        labels = Labels(github=mock_github)
        labels.get_skill = Mock(return_value=None)
        
        result = labels.run("owner/repo", 123)
        
        assert "No labels suggested" in result


class TestLabelsLabelApplication:
    """Test label application."""
    
    @patch('tools.labels.asyncio.run')
    def test_run_applies_labels(self, mock_asyncio, mock_github, mock_pr):
        """Test that labels are applied to PR."""
        from tools.labels import Labels
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_repo_labels.return_value = ["bug", "feature", "enhancement"]
        mock_github.get_pr_diff.return_value = "diff content"
        mock_github.add_labels = Mock()
        mock_asyncio.return_value = '{"labels": ["bug"], "reason": "Bug fix"}'
        
        labels = Labels(github=mock_github)
        labels.get_skill = Mock(return_value=None)
        
        result = labels.run("owner/repo", 123)
        
        mock_github.add_labels.assert_called_once_with("owner/repo", 123, ["bug"])
        assert "Applied labels" in result
    
    @patch('tools.labels.asyncio.run')
    def test_run_handles_apply_error(self, mock_asyncio, mock_github, mock_pr):
        """Test handling label application errors."""
        from tools.labels import Labels
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_repo_labels.return_value = ["bug", "feature"]
        mock_github.get_pr_diff.return_value = "diff content"
        mock_github.add_labels.side_effect = Exception("API error")
        mock_asyncio.return_value = '{"labels": ["bug"], "reason": "Bug fix"}'
        
        labels = Labels(github=mock_github)
        labels.get_skill = Mock(return_value=None)
        
        result = labels.run("owner/repo", 123)
        
        assert "Suggested labels" in result
        assert "Failed to apply" in result


class TestLabelsRepoLabels:
    """Test repository label fetching."""
    
    @patch('tools.labels.asyncio.run')
    def test_run_uses_repo_labels(self, mock_asyncio, mock_github, mock_pr):
        """Test using repository labels."""
        from tools.labels import Labels
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_repo_labels.return_value = ["custom-bug", "custom-feature"]
        mock_github.get_pr_diff.return_value = "diff content"
        mock_asyncio.return_value = '{"labels": ["custom-bug"], "reason": "Bug fix"}'
        
        labels = Labels(github=mock_github)
        labels.get_skill = Mock(return_value=None)
        
        result = labels.run("owner/repo", 123)
        
        assert "custom-bug" in result
    
    @patch('tools.labels.asyncio.run')
    def test_run_uses_default_labels_when_empty(self, mock_asyncio, mock_github, mock_pr):
        """Test using default labels when repo has none."""
        from tools.labels import Labels, DEFAULT_LABELS
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_repo_labels.return_value = []
        mock_github.get_pr_diff.return_value = "diff content"
        mock_asyncio.return_value = '{"labels": ["bug"], "reason": "Bug fix"}'
        
        labels = Labels(github=mock_github)
        labels.get_skill = Mock(return_value=None)
        
        result = labels.run("owner/repo", 123)
        
        # Should use default labels
        assert "bug" in result


class TestLabelsResponseParsing:
    """Test response parsing."""
    
    def test_parse_response_valid_json(self, mock_github):
        """Test parsing valid JSON response."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        valid_labels = ["bug", "feature", "enhancement"]
        
        response = '{"labels": ["bug", "feature"], "reason": "Bug fix with new feature"}'
        
        parsed_labels, reason = labels._parse_response(response, valid_labels)
        
        assert "bug" in parsed_labels
        assert "feature" in parsed_labels
        assert "Bug fix" in reason
    
    def test_parse_response_filters_invalid_labels(self, mock_github):
        """Test that invalid labels are filtered out."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        valid_labels = ["bug", "feature"]
        
        response = '{"labels": ["bug", "invalid-label", "feature"], "reason": "Test"}'
        
        parsed_labels, reason = labels._parse_response(response, valid_labels)
        
        assert "bug" in parsed_labels
        assert "feature" in parsed_labels
        assert "invalid-label" not in parsed_labels
    
    def test_parse_response_limits_to_three(self, mock_github):
        """Test that labels are limited to 3."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        valid_labels = ["bug", "feature", "enhancement", "docs", "test"]
        
        response = '{"labels": ["bug", "feature", "enhancement", "docs"], "reason": "Test"}'
        
        parsed_labels, reason = labels._parse_response(response, valid_labels)
        
        assert len(parsed_labels) <= 3
    
    def test_parse_response_invalid_json(self, mock_github):
        """Test parsing invalid JSON."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        valid_labels = ["bug", "feature"]
        
        response = "This is not JSON"
        
        parsed_labels, reason = labels._parse_response(response, valid_labels)
        
        assert parsed_labels == []
        assert reason == ""
    
    def test_parse_response_case_insensitive(self, mock_github):
        """Test case-insensitive label matching."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        valid_labels = ["Bug", "Feature"]
        
        response = '{"labels": ["bug", "feature"], "reason": "Test"}'
        
        parsed_labels, reason = labels._parse_response(response, valid_labels)
        
        assert len(parsed_labels) == 2


class TestLabelsFormatResult:
    """Test result formatting."""
    
    def test_format_result_with_applied_labels(self, mock_github):
        """Test formatting with applied labels."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        labels.format_footer = Mock(return_value="Footer")
        
        result = labels._format_result(["bug", "feature"], "Bug fix", applied=True)
        
        assert "Applied labels" in result
        assert "bug" in result
        assert "feature" in result
        assert "Bug fix" in result
    
    def test_format_result_without_applied_labels(self, mock_github):
        """Test formatting without applied labels."""
        from tools.labels import Labels
        
        labels = Labels(github=mock_github)
        labels.format_footer = Mock(return_value="Footer")
        
        result = labels._format_result(["bug"], "Bug fix", applied=False)
        
        assert "Suggested labels" in result
        assert "Failed to apply" in result


class TestLabelsErrorHandling:
    """Test error handling."""
    
    def test_run_with_empty_diff(self, mock_github, mock_pr):
        """Test run with empty diff."""
        from tools.labels import Labels
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_pr_diff.return_value = ""
        
        labels = Labels(github=mock_github)
        
        result = labels.run("owner/repo", 123)
        
        assert "No changes to analyze" in result
    
    @patch('tools.labels.asyncio.run')
    def test_run_with_agent_error(self, mock_asyncio, mock_github, mock_pr):
        """Test run with agent execution error."""
        from tools.labels import Labels
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_repo_labels.return_value = ["bug", "feature"]
        mock_github.get_pr_diff.return_value = "diff content"
        mock_asyncio.return_value = '{"labels": [], "reason": "Error: Agent failed"}'
        
        labels = Labels(github=mock_github)
        labels.get_skill = Mock(return_value=None)
        
        result = labels.run("owner/repo", 123)
        
        assert "No labels suggested" in result
