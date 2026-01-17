"""Tests for Reviewer tool."""

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
            base=Mock(ref="main"),
            get_commits=Mock(return_value=[
                Mock(sha="commit1", commit=Mock(message="First commit")),
                Mock(sha="commit2", commit=Mock(message="Second commit"))
            ])
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
    
    def create_review_with_comments(self, repo, pr_number, comments, body="", event="COMMENT"):
        self.reviews.append({
            "repo": repo,
            "pr_number": pr_number,
            "comments": comments,
            "body": body,
            "event": event
        })
    
    def get_last_bot_comment(self, repo, pr_number):
        return None
    
    def get_commits_since(self, repo, pr_number, sha):
        return []


@pytest.fixture
def mock_action_config():
    """Create mock action config."""
    with patch('tools.base.get_action_config') as mock:
        config = Mock()
        config.model = "kimi-k2-thinking"
        config.review_level = "normal"
        config.max_files = 50
        config.exclude_patterns = ["*.lock"]
        config.review = Mock(
            num_max_findings=10,
            extra_instructions=""
        )
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


class TestReviewerDiffProcessing:
    """Test diff processing in Reviewer."""
    
    def test_get_diff_success(self, mock_action_config):
        """Test successful diff retrieval."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        compressed, included, excluded = reviewer.get_diff("owner/repo", 123)
        
        assert compressed != ""
        assert len(included) > 0
        assert "src/main.py" in compressed
    
    def test_get_diff_empty(self, mock_action_config):
        """Test handling empty diff."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        github.get_pr_diff = Mock(return_value="")
        reviewer = Reviewer(github)
        
        compressed, included, excluded = reviewer.get_diff("owner/repo", 123)
        
        assert compressed == ""
        assert len(included) == 0


class TestReviewerSuggestionParsing:
    """Test suggestion parsing."""
    
    def test_parse_suggestions_valid_yaml(self, mock_action_config):
        """Test parsing valid YAML suggestions."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        response = """```yaml
suggestions:
  - relevant_file: "src/main.py"
    language: "python"
    severity: "medium"
    label: "bug"
    one_sentence_summary: "Fix the bug"
    suggestion_content: "This is a bug"
    existing_code: "old code"
    improved_code: "new code"
    relevant_lines_start: 10
    relevant_lines_end: 15
```"""
        
        suggestions = reviewer._parse_suggestions(response)
        
        assert len(suggestions) == 1
        assert suggestions[0].relevant_file == "src/main.py"
        assert suggestions[0].severity.value == "medium"
        assert suggestions[0].relevant_lines_start == 10
    
    def test_parse_suggestions_invalid_yaml(self, mock_action_config):
        """Test parsing invalid YAML."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        response = "not valid yaml"
        
        suggestions = reviewer._parse_suggestions(response)
        
        assert len(suggestions) == 0
    
    def test_parse_suggestions_empty(self, mock_action_config):
        """Test parsing empty suggestions."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        response = """```yaml
suggestions: []
```"""
        
        suggestions = reviewer._parse_suggestions(response)
        
        assert len(suggestions) == 0
    
    def test_parse_suggestions_with_line_numbers(self, mock_action_config):
        """Test parsing suggestions with line numbers."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        response = """```yaml
suggestions:
  - relevant_file: "test.py"
    severity: "high"
    suggestion_content: "Fix this"
    relevant_lines_start: 5
    relevant_lines_end: 10
```"""
        
        suggestions = reviewer._parse_suggestions(response)
        
        assert len(suggestions) == 1
        assert suggestions[0].relevant_lines_start == 5
        assert suggestions[0].relevant_lines_end == 10


class TestReviewerInlineComments:
    """Test inline comments functionality."""
    
    def test_post_inline_comments_success(self, mock_action_config):
        """Test successful inline comments posting."""
        from tools.reviewer import Reviewer
        from models import CodeSuggestion, SeverityLevel
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        suggestions = [
            CodeSuggestion(
                id="1",
                relevant_file="test.py",
                language="python",
                suggestion_content="Fix this",
                existing_code="old",
                improved_code="new",
                one_sentence_summary="Summary",
                relevant_lines_start=10,
                relevant_lines_end=15,
                label="bug",
                severity=SeverityLevel.MEDIUM
            )
        ]
        
        count = reviewer._post_inline_comments("owner/repo", 123, suggestions, "Summary")
        
        assert count == 1
        assert len(github.reviews) == 1
        assert "```suggestion" in github.reviews[0]["comments"][0]["body"]
    
    def test_post_inline_comments_empty(self, mock_action_config):
        """Test posting empty suggestions."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        count = reviewer._post_inline_comments("owner/repo", 123, [], "Summary")
        
        assert count == 0
        assert len(github.reviews) == 0


class TestReviewerFormatting:
    """Test formatting methods."""
    
    def test_format_inline_summary(self, mock_action_config):
        """Test inline summary formatting."""
        from tools.reviewer import Reviewer
        from models import CodeSuggestion, SeverityLevel
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        response = """```yaml
summary: "Good PR"
score: 85
file_summaries:
  - file: "test.py"
    description: "Added tests"
suggestions: []
```"""
        
        suggestions = [
            CodeSuggestion(
                id="1",
                relevant_file="test.py",
                language="python",
                suggestion_content="Fix this",
                existing_code="",
                improved_code="",
                one_sentence_summary="Fix the bug",
                relevant_lines_start=10,
                relevant_lines_end=15,
                label="bug",
                severity=SeverityLevel.HIGH
            )
        ]
        
        summary = reviewer._format_inline_summary(
            response, suggestions, 1,
            total_files=1, command_quote="/review"
        )
        
        assert "> /review" in summary
        assert "Pull request overview" in summary
        assert "Good PR" in summary
    
    def test_format_fallback(self, mock_action_config):
        """Test fallback formatting."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        response = """```yaml
summary: "No issues found"
score: 95
suggestions: []
```"""
        
        result = reviewer._format_fallback(response, current_sha="abc123")
        
        assert "No issues found" in result
        assert "95" in result
        assert "abc123" in result


class TestReviewerScripts:
    """Test system prompt building."""
    
    def test_build_system_prompt(self, mock_action_config):
        """Test system prompt building without script output."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        skill = Mock()
        skill.instructions = "Review the code carefully"
        
        prompt = reviewer._build_system_prompt(skill)
        
        assert "Review the code carefully" in prompt
        assert "Review Level" in prompt
        # Agent SDK will call scripts automatically, so no script output in prompt
        assert "Automated Check Results" not in prompt


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
        """Test successful run with mocked agent."""
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
        with patch.object(reviewer, 'clone_repo', return_value=True):
            # Mock asyncio.run to return YAML response
            with patch('asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = """```yaml
summary: "Good code"
score: 90
file_summaries:
  - file: "src/main.py"
    description: "Added feature"
suggestions:
  - relevant_file: "src/main.py"
    severity: "low"
    label: "style"
    one_sentence_summary: "Minor style issue"
    suggestion_content: "Consider using f-strings"
    relevant_lines_start: 5
```"""
                
                result = reviewer.run("owner/repo", 123, inline=False)
                
                assert "Good code" in result or "Pull request overview" in result


class TestReviewerIncrementalDiff:
    """Test incremental diff functionality."""
    
    def test_get_incremental_diff_no_last_review(self, mock_action_config):
        """Test incremental diff when no last review exists."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        reviewer = Reviewer(github)
        
        compressed, included, excluded, last_sha = reviewer._get_incremental_diff("owner/repo", 123)
        
        assert compressed != ""
        assert last_sha is None
    
    def test_get_incremental_diff_no_new_commits(self, mock_action_config):
        """Test incremental diff with no new commits."""
        from tools.reviewer import Reviewer
        
        github = MockGitHubClient()
        github.get_last_bot_comment = Mock(return_value={"sha": "abc123"})
        github.get_commits_since = Mock(return_value=[])
        reviewer = Reviewer(github)
        
        compressed, included, excluded, last_sha = reviewer._get_incremental_diff("owner/repo", 123)
        
        assert compressed is None
        assert last_sha == "abc123"
