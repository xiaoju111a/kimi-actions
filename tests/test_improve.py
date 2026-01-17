"""Tests for Improve tool."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


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
            base=Mock(ref="main")
        )
    
    def get_pr_diff(self, repo, pr_number):
        return """diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,6 @@
 def main():
+    # TODO: improve this
     print("Hello")
     pass
"""
    
    def post_comment(self, repo, pr_number, body):
        self.posted_comments.append(body)
    
    def create_review_with_comments(self, repo, pr_number, comments, body="", event="COMMENT"):
        self.reviews.append({
            "repo": repo,
            "pr_number": pr_number,
            "comments": comments,
            "body": body,
            "event": event
        })


@pytest.fixture
def mock_action_config():
    """Create mock action config."""
    with patch('tools.base.get_action_config') as mock:
        config = Mock()
        config.model = "kimi-k2-thinking"
        config.review_level = "normal"
        config.max_files = 50
        config.exclude_patterns = ["*.lock"]
        config.improve = Mock(num_suggestions=5)
        mock.return_value = config
        yield config


class TestImproveBasic:
    """Test basic Improve functionality."""
    
    def test_improve_initialization(self, mock_action_config):
        """Test Improve initialization."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        assert improve.github == github
        assert improve.skill_name == "improve"
    
    def test_skill_name_property(self, mock_action_config):
        """Test skill_name property."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        assert improve.skill_name == "improve"
    
    def test_run_with_empty_diff(self, mock_action_config):
        """Test run with empty diff."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        github.get_pr_diff = Mock(return_value="")
        improve = Improve(github)
        improve.load_context = Mock()
        
        result = improve.run("owner/repo", 123)
        
        assert "No changes to improve" in result


class TestImproveSuggestionParsing:
    """Test suggestion parsing."""
    
    def test_parse_suggestions_valid_yaml(self, mock_action_config):
        """Test parsing valid YAML suggestions."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        response = """```yaml
suggestions:
  - relevant_file: "src/main.py"
    language: "python"
    severity: "medium"
    one_sentence_summary: "Use f-strings"
    suggestion_content: "Consider using f-strings for better readability"
    existing_code: "print('Hello')"
    improved_code: "print(f'Hello')"
    relevant_lines_start: 10
    relevant_lines_end: 10
```"""
        
        suggestions = improve._parse_suggestions(response)
        
        assert len(suggestions) == 1
        assert suggestions[0]["relevant_file"] == "src/main.py"
        assert suggestions[0]["relevant_lines_start"] == 10
    
    def test_parse_suggestions_with_code_block(self, mock_action_config):
        """Test parsing YAML with code block markers."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        response = """Here are the suggestions:
```yaml
suggestions:
  - relevant_file: "test.py"
    severity: "low"
    suggestion_content: "Add docstring"
    relevant_lines_start: 5
```
"""
        
        suggestions = improve._parse_suggestions(response)
        
        assert len(suggestions) == 1
        assert suggestions[0]["relevant_file"] == "test.py"
    
    def test_parse_suggestions_empty(self, mock_action_config):
        """Test parsing empty suggestions."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        response = """```yaml
suggestions: []
```"""
        
        suggestions = improve._parse_suggestions(response)
        
        assert len(suggestions) == 0
    
    def test_parse_suggestions_invalid_yaml(self, mock_action_config):
        """Test parsing invalid YAML."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        response = "not valid yaml at all"
        
        suggestions = improve._parse_suggestions(response)
        
        assert len(suggestions) == 0


class TestImproveInlineComments:
    """Test inline comments functionality."""
    
    def test_post_inline_comments_success(self, mock_action_config):
        """Test successful inline comments posting."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        suggestions = [
            {
                "relevant_file": "test.py",
                "relevant_lines_start": 10,
                "relevant_lines_end": 15,
                "suggestion_content": "Improve this",
                "improved_code": "better code"
            }
        ]
        
        count = improve._post_inline_comments("owner/repo", 123, suggestions, "Summary")
        
        assert count == 1
        assert len(github.reviews) == 1
        assert "```suggestion" in github.reviews[0]["comments"][0]["body"]
    
    def test_post_inline_comments_with_command_quote(self, mock_action_config):
        """Test inline comments with command quote in summary."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        suggestions = [
            {
                "relevant_file": "test.py",
                "relevant_lines_start": 10,
                "suggestion_content": "Fix this"
            }
        ]
        
        summary = "> /improve\n\nSummary here"
        count = improve._post_inline_comments("owner/repo", 123, suggestions, summary)
        
        assert count == 1
        assert "> /improve" in github.reviews[0]["body"]


class TestImproveFormatting:
    """Test formatting methods."""
    
    def test_format_summary_with_suggestions(self, mock_action_config):
        """Test summary formatting with suggestions."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        suggestions = [
            {
                "relevant_file": "test.py",
                "severity": "high",
                "one_sentence_summary": "Fix the bug"
            },
            {
                "relevant_file": "main.py",
                "severity": "medium",
                "one_sentence_summary": "Improve performance"
            }
        ]
        
        summary = improve._format_summary(suggestions, 2, command_quote="/improve")
        
        assert "> /improve" in summary
        assert "Kimi Code Suggestions" in summary
        assert "2 improvement suggestions" in summary or "2 suggestions" in summary
    
    def test_format_summary_empty(self, mock_action_config):
        """Test summary formatting with no suggestions."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        summary = improve._format_summary([], 0)
        
        assert "Code quality is good" in summary or "good" in summary.lower()
    
    def test_format_summary_with_command_quote(self, mock_action_config):
        """Test summary with command quote."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        suggestions = [{"relevant_file": "test.py", "severity": "low", "one_sentence_summary": "Minor"}]
        summary = improve._format_summary(suggestions, 1, command_quote="/improve --all")
        
        assert "> /improve --all" in summary
    
    def test_format_summary_severity_sorting(self, mock_action_config):
        """Test that suggestions are sorted by severity."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        
        suggestions = [
            {"relevant_file": "a.py", "severity": "low", "one_sentence_summary": "Low"},
            {"relevant_file": "b.py", "severity": "critical", "one_sentence_summary": "Critical"},
            {"relevant_file": "c.py", "severity": "medium", "one_sentence_summary": "Medium"}
        ]
        
        summary = improve._format_summary(suggestions, 3)
        
        # Critical should appear first in the summary
        critical_pos = summary.find("Critical")
        low_pos = summary.find("Low")
        assert critical_pos < low_pos


class TestImproveIntegration:
    """Integration tests for Improve."""
    
    def test_run_success_with_mock_agent(self, mock_action_config):
        """Test successful run with mocked agent."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        improve.load_context = Mock()
        
        # Mock skill
        skill = Mock()
        skill.instructions = "Provide improvements"
        improve.get_skill = Mock(return_value=skill)
        
        # Mock clone_repo
        with patch.object(improve, 'clone_repo', return_value=True):
            # Mock asyncio.run to return YAML response
            with patch('asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = """```yaml
suggestions:
  - relevant_file: "src/main.py"
    severity: "medium"
    one_sentence_summary: "Use type hints"
    suggestion_content: "Add type hints for better code clarity"
    relevant_lines_start: 5
    relevant_lines_end: 10
```"""
                
                result = improve.run("owner/repo", 123, inline=False)
                
                assert "Kimi Code Suggestions" in result or "suggestions" in result.lower()
    
    def test_run_with_inline_comments(self, mock_action_config):
        """Test run with inline comments enabled."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        improve.load_context = Mock()
        
        skill = Mock()
        skill.instructions = "Provide improvements"
        improve.get_skill = Mock(return_value=skill)
        
        with patch.object(improve, 'clone_repo', return_value=True):
            with patch('asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = """```yaml
suggestions:
  - relevant_file: "test.py"
    severity: "low"
    suggestion_content: "Minor improvement"
    relevant_lines_start: 1
```"""
                
                result = improve.run("owner/repo", 123, inline=True)
                
                # Should return empty string if inline comments posted successfully
                assert result == "" or "Kimi Code Suggestions" in result
    
    def test_run_clone_failure(self, mock_action_config):
        """Test run when clone fails."""
        from tools.improve import Improve
        
        github = MockGitHubClient()
        improve = Improve(github)
        improve.load_context = Mock()
        
        skill = Mock()
        skill.instructions = "Provide improvements"
        improve.get_skill = Mock(return_value=skill)
        
        with patch.object(improve, 'clone_repo', return_value=False):
            result = improve.run("owner/repo", 123)
            
            assert "Failed to clone repository" in result or "❌" in result
