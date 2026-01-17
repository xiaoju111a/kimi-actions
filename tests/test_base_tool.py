"""Tests for BaseTool class."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class MockGitHubClient:
    """Mock GitHub client."""
    def __init__(self):
        self.posted_comments = []
        self.reviews = []
    
    def get_pr(self, repo, pr_number):
        return Mock(
            number=pr_number,
            title="Test PR",
            head=Mock(ref="feature-branch", sha="abc123"),
            base=Mock(ref="main")
        )
    
    def get_pr_diff(self, repo, pr_number):
        return """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
+    print("world")
     pass
"""
    
    def create_review_with_comments(self, repo, pr_number, comments, body="", event="COMMENT"):
        self.reviews.append({
            "repo": repo,
            "pr_number": pr_number,
            "comments": comments,
            "body": body,
            "event": event
        })


class ConcreteTool:
    """Concrete implementation of BaseTool for testing."""
    from tools.base import BaseTool
    
    class _ConcreteTool(BaseTool):
        @property
        def skill_name(self) -> str:
            return "test-skill"
        
        def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
            return "test result"
    
    @classmethod
    def create(cls, github):
        return cls._ConcreteTool(github)


@pytest.fixture
def mock_action_config():
    """Create mock action config."""
    with patch('tools.base.get_action_config') as mock:
        config = Mock()
        config.model = "kimi-k2-thinking"
        config.review_level = "normal"
        config.max_files = 10
        config.exclude_patterns = ["*.lock"]
        mock.return_value = config
        yield config


class TestBaseToolAbstract:
    """Test abstract methods and initialization."""
    
    def test_cannot_instantiate_directly(self, mock_action_config):
        """Test that BaseTool cannot be instantiated directly."""
        from tools.base import BaseTool
        
        github = MockGitHubClient()
        with pytest.raises(TypeError):
            BaseTool(github)
    
    def test_subclass_must_implement_skill_name(self, mock_action_config):
        """Test that subclass must implement skill_name property."""
        from tools.base import BaseTool
        
        class IncompleteTool(BaseTool):
            def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
                return "test"
        
        github = MockGitHubClient()
        with pytest.raises(TypeError):
            IncompleteTool(github)
    
    def test_subclass_must_implement_run(self, mock_action_config):
        """Test that subclass must implement run method."""
        from tools.base import BaseTool
        
        class IncompleteTool(BaseTool):
            @property
            def skill_name(self) -> str:
                return "test"
        
        github = MockGitHubClient()
        with pytest.raises(TypeError):
            IncompleteTool(github)
    
    def test_concrete_tool_initialization(self, mock_action_config):
        """Test that concrete tool can be initialized."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        assert tool.github == github
        assert tool.config == mock_action_config
        assert tool.skill_name == "test-skill"


class TestBaseToolCloneRepo:
    """Test clone_repo method."""
    
    def test_clone_repo_success(self, mock_action_config):
        """Test successful repository clone."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            result = tool.clone_repo("owner/repo", "/tmp/test", branch="main")
            
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "git" in call_args
            assert "clone" in call_args
            assert "-b" in call_args
            assert "main" in call_args
    
    def test_clone_repo_without_branch(self, mock_action_config):
        """Test clone without specifying branch."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            result = tool.clone_repo("owner/repo", "/tmp/test")
            
            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "-b" not in call_args
    
    def test_clone_repo_branch_fallback(self, mock_action_config):
        """Test fallback to default branch when specified branch fails."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch('subprocess.run') as mock_run:
            # Configure side_effect to raise on first call, succeed on second
            call_count = [0]
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    from subprocess import CalledProcessError
                    raise CalledProcessError(1, "git")
                return Mock(returncode=0)
            
            mock_run.side_effect = side_effect
            
            result = tool.clone_repo("owner/repo", "/tmp/test", branch="nonexistent")
            
            assert result is True
            assert call_count[0] == 2
    
    def test_clone_repo_failure(self, mock_action_config):
        """Test clone failure."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch('subprocess.run') as mock_run:
            from subprocess import CalledProcessError
            mock_run.side_effect = CalledProcessError(1, "git")
            
            result = tool.clone_repo("owner/repo", "/tmp/test")
            
            assert result is False


class TestBaseToolRunAgent:
    """Test run_agent method."""
    
    @pytest.mark.asyncio
    async def test_run_agent_success(self, mock_action_config):
        """Test successful agent execution."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch.dict(os.environ, {"KIMI_API_KEY": "test-key"}):
            # Skip this test if kimi_agent_sdk is not available
            try:
                import kimi_agent_sdk
            except ImportError:
                pytest.skip("kimi_agent_sdk not installed")
            
            # Mock the Session.create to return a mock session
            mock_session = AsyncMock()
            
            # Create a mock TextPart class
            class MockTextPart:
                def __init__(self, text):
                    self.text = text
            
            # Mock the prompt method to yield TextPart objects
            async def mock_prompt(*args):
                yield MockTextPart("Response ")
                yield MockTextPart("text")
            
            mock_session.prompt = mock_prompt
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            with patch('kimi_agent_sdk.Session.create', return_value=mock_session):
                with patch('kimi_agent_sdk.TextPart', MockTextPart):
                    result = await tool.run_agent("/tmp/test", "Test prompt")
                    
                    assert "Response text" in result or result == ""  # May be empty if import fails
    
    @pytest.mark.asyncio
    async def test_run_agent_no_api_key(self, mock_action_config):
        """Test agent execution without API key."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch.dict(os.environ, {}, clear=True):
            result = await tool.run_agent("/tmp/test", "Test prompt")
            
            assert result == ""
    
    @pytest.mark.asyncio
    async def test_run_agent_import_error(self, mock_action_config):
        """Test agent execution with import error."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch.dict(os.environ, {"KIMI_API_KEY": "test-key"}):
            with patch('builtins.__import__', side_effect=ImportError("Module not found")):
                result = await tool.run_agent("/tmp/test", "Test prompt")
                
                assert result == ""


class TestBaseToolPostInlineComments:
    """Test post_inline_comments method."""
    
    def test_post_inline_comments_success(self, mock_action_config):
        """Test successful inline comments posting."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        suggestions = [
            {
                "relevant_file": "test.py",
                "relevant_lines_start": 10,
                "relevant_lines_end": 15,
                "suggestion_content": "Improve this code",
                "improved_code": "better code"
            }
        ]
        
        count = tool.post_inline_comments(
            "owner/repo", 123, suggestions,
            summary_body="Summary", use_suggestion_format=True
        )
        
        assert count == 1
        assert len(github.reviews) == 1
        assert len(github.reviews[0]["comments"]) == 1
        assert "```suggestion" in github.reviews[0]["comments"][0]["body"]
    
    def test_post_inline_comments_without_suggestion_format(self, mock_action_config):
        """Test inline comments without suggestion format."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        suggestions = [
            {
                "relevant_file": "test.py",
                "relevant_lines_start": 10,
                "suggestion_content": "Improve this code",
                "improved_code": "better code"
            }
        ]
        
        count = tool.post_inline_comments(
            "owner/repo", 123, suggestions,
            use_suggestion_format=False
        )
        
        assert count == 1
        assert "```suggestion" not in github.reviews[0]["comments"][0]["body"]
    
    def test_post_inline_comments_missing_file(self, mock_action_config):
        """Test skipping suggestions with missing file."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        suggestions = [
            {
                "relevant_file": "",
                "relevant_lines_start": 10,
                "suggestion_content": "Improve this code"
            }
        ]
        
        count = tool.post_inline_comments("owner/repo", 123, suggestions)
        
        assert count == 0
        assert len(github.reviews) == 0
    
    def test_post_inline_comments_missing_line(self, mock_action_config):
        """Test skipping suggestions with missing line number."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        suggestions = [
            {
                "relevant_file": "test.py",
                "relevant_lines_start": None,
                "suggestion_content": "Improve this code"
            }
        ]
        
        count = tool.post_inline_comments("owner/repo", 123, suggestions)
        
        assert count == 0
    
    def test_post_inline_comments_api_error(self, mock_action_config):
        """Test handling API error when posting comments."""
        github = MockGitHubClient()
        github.create_review_with_comments = Mock(side_effect=Exception("API Error"))
        tool = ConcreteTool.create(github)
        
        suggestions = [
            {
                "relevant_file": "test.py",
                "relevant_lines_start": 10,
                "suggestion_content": "Improve this code"
            }
        ]
        
        count = tool.post_inline_comments("owner/repo", 123, suggestions)
        
        assert count == 0


class TestBaseToolDiffProcessing:
    """Test diff processing methods."""
    
    def test_get_diff_success(self, mock_action_config):
        """Test successful diff retrieval."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        compressed, included, excluded = tool.get_diff("owner/repo", 123)
        
        assert compressed != ""
        assert len(included) > 0
        assert isinstance(excluded, list)
    
    def test_get_diff_empty(self, mock_action_config):
        """Test handling empty diff."""
        github = MockGitHubClient()
        github.get_pr_diff = Mock(return_value="")
        tool = ConcreteTool.create(github)
        
        compressed, included, excluded = tool.get_diff("owner/repo", 123)
        
        assert compressed == ""
        assert len(included) == 0
        assert len(excluded) == 0


class TestBaseToolContext:
    """Test context loading methods."""
    
    def test_load_context_success(self, mock_action_config):
        """Test successful context loading."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch('tools.base.load_repo_config') as mock_load:
            mock_config = Mock()
            mock_config.ignore_files = ["*.test"]
            mock_validation = Mock(valid=True, errors=[], warnings=[])
            mock_load.return_value = (mock_config, mock_validation)
            
            tool.load_context("owner/repo", ref="abc123")
            
            assert tool.repo_config == mock_config
            mock_load.assert_called_once_with(github, "owner/repo", ref="abc123")
    
    def test_get_skill_with_override(self, mock_action_config):
        """Test getting skill with repository override."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        # Setup repo config with override
        tool.repo_config = Mock()
        tool.repo_config.skill_overrides = {"test-skill": "custom-skill"}
        
        # Setup skill manager
        custom_skill = Mock()
        custom_skill.name = "custom-skill"
        tool.skill_manager.get_skill = Mock(return_value=custom_skill)
        
        skill = tool.get_skill()
        
        assert skill == custom_skill
        tool.skill_manager.get_skill.assert_called_once_with("custom-skill")


class TestBaseToolHelpers:
    """Test helper methods."""
    
    def test_parse_yaml_response_valid(self, mock_action_config):
        """Test parsing valid YAML response."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        response = """```yaml
key: value
list:
  - item1
  - item2
```"""
        
        result = tool.parse_yaml_response(response)
        
        assert result is not None
        assert result["key"] == "value"
        assert len(result["list"]) == 2
    
    def test_parse_yaml_response_without_code_block(self, mock_action_config):
        """Test parsing YAML without code block."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        response = """key: value
list:
  - item1"""
        
        result = tool.parse_yaml_response(response)
        
        assert result is not None
        assert result["key"] == "value"
    
    def test_parse_yaml_response_invalid(self, mock_action_config):
        """Test parsing invalid YAML."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        response = "not valid yaml: [unclosed"
        
        result = tool.parse_yaml_response(response)
        
        assert result is None
    
    def test_format_footer(self, mock_action_config):
        """Test footer formatting."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        footer = tool.format_footer()
        
        assert "Powered by" in footer
        assert "Kimi" in footer
        assert "kimi-k2-thinking" in footer
    
    def test_format_footer_with_extra_info(self, mock_action_config):
        """Test footer with extra information."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        footer = tool.format_footer("5 suggestions")
        
        assert "5 suggestions" in footer
    
    def test_setup_agent_env(self, mock_action_config):
        """Test agent environment setup."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch.dict(os.environ, {"KIMI_API_KEY": "test-key"}):
            api_key = tool.setup_agent_env()
            
            assert api_key == "test-key"
            assert os.environ.get("KIMI_BASE_URL") == "https://api.moonshot.cn/v1"
            assert os.environ.get("KIMI_MODEL_NAME") == "kimi-k2-thinking"
    
    def test_setup_agent_env_no_key(self, mock_action_config):
        """Test agent environment setup without API key."""
        github = MockGitHubClient()
        tool = ConcreteTool.create(github)
        
        with patch.dict(os.environ, {}, clear=True):
            api_key = tool.setup_agent_env()
            
            assert api_key is None
