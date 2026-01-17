"""Tests for Ask tool."""

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
    pr.title = "Test PR"
    pr.body = "Test description"
    pr.head.sha = "abc123"
    pr.head.ref = "feature-branch"
    return pr


class TestAskBasic:
    """Test basic Ask functionality."""
    
    def test_ask_initialization(self, mock_github, mock_config):
        """Test Ask tool initialization."""
        from tools.ask import Ask
        
        ask = Ask(github=mock_github)
        assert ask.skill_name == "ask"
    
    def test_skill_name_property(self, mock_github, mock_config):
        """Test skill_name property."""
        from tools.ask import Ask
        
        ask = Ask(github=mock_github)
        assert ask.skill_name == "ask"
    
    def test_run_without_question(self, mock_github, mock_pr, mock_config):
        """Test run without question parameter."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        ask = Ask(github=mock_github)
        
        result = ask.run("owner/repo", 123)
        
        assert "Please provide a question" in result
        assert "/ask" in result


class TestAskQuestionParsing:
    """Test question parsing and validation."""
    
    def test_run_with_empty_question(self, mock_github, mock_pr, mock_config):
        """Test run with empty question string."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        ask = Ask(github=mock_github)
        
        result = ask.run("owner/repo", 123, question="")
        
        assert "Please provide a question" in result
    
    def test_run_with_valid_question(self, mock_github, mock_pr, mock_config):
        """Test run with valid question."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        mock_github.get_pr_diff.return_value = "diff content"
        
        ask = Ask(github=mock_github)
        ask.load_context = Mock()
        ask.get_diff = Mock(return_value=("diff", {}, []))
        ask.get_skill = Mock(return_value=None)
        ask.clone_repo = Mock(return_value=False)
        
        result = ask.run("owner/repo", 123, question="What does this do?")
        
        assert "Failed to clone" in result


class TestAskAgentExecution:
    """Test agent execution."""
    
    @patch('tools.ask.asyncio.run')
    @patch('tools.ask.tempfile.TemporaryDirectory')
    def test_run_with_agent_success(self, mock_tempdir, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test successful agent execution."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_asyncio.return_value = "This is the answer to your question."
        
        ask = Ask(github=mock_github)
        ask.load_context = Mock()
        ask.get_diff = Mock(return_value=("diff content", {}, []))
        ask.get_skill = Mock(return_value=None)
        ask.clone_repo = Mock(return_value=True)
        
        result = ask.run("owner/repo", 123, question="What does this do?")
        
        assert "Kimi Answer" in result
        assert "This is the answer" in result
    
    @patch('tools.ask.asyncio.run')
    @patch('tools.ask.tempfile.TemporaryDirectory')
    def test_run_with_agent_error(self, mock_tempdir, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test agent execution with error."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_asyncio.side_effect = Exception("Agent failed")
        
        ask = Ask(github=mock_github)
        ask.load_context = Mock()
        ask.get_diff = Mock(return_value=("diff content", {}, []))
        ask.get_skill = Mock(return_value=None)
        ask.clone_repo = Mock(return_value=True)
        
        result = ask.run("owner/repo", 123, question="What does this do?")
        
        assert "Failed to answer question" in result


class TestAskResponseFormatting:
    """Test response formatting."""
    
    def test_format_response_inline(self, mock_github, mock_config):
        """Test inline response formatting."""
        from tools.ask import Ask
        
        ask = Ask(github=mock_github)
        ask.format_footer = Mock(return_value="Footer")
        
        result = ask._format_response("Test answer", inline=True)
        
        assert "Kimi Answer" in result
        assert "Test answer" in result
        assert "Footer" in result
    
    def test_format_response_regular(self, mock_github, mock_config):
        """Test regular response formatting."""
        from tools.ask import Ask
        
        ask = Ask(github=mock_github)
        ask.format_footer = Mock(return_value="Footer")
        
        result = ask._format_response("Test answer", inline=False)
        
        assert "Kimi Answer" in result
        assert "Test answer" in result
        # The footer contains the /ask instruction
        assert "Footer" in result


class TestAskErrorHandling:
    """Test error handling."""
    
    def test_run_with_empty_diff(self, mock_github, mock_pr, mock_config):
        """Test run with empty diff."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        
        ask = Ask(github=mock_github)
        ask.load_context = Mock()
        ask.get_diff = Mock(return_value=("", {}, []))
        
        result = ask.run("owner/repo", 123, question="What does this do?")
        
        assert "Unable to get PR changes" in result
    
    def test_run_with_clone_failure(self, mock_github, mock_pr, mock_config):
        """Test run with clone failure."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        
        ask = Ask(github=mock_github)
        ask.load_context = Mock()
        ask.get_diff = Mock(return_value=("diff content", {}, []))
        ask.get_skill = Mock(return_value=None)
        ask.clone_repo = Mock(return_value=False)
        
        result = ask.run("owner/repo", 123, question="What does this do?")
        
        assert "Failed to clone" in result
    
    @patch('tools.ask.asyncio.run')
    @patch('tools.ask.tempfile.TemporaryDirectory')
    def test_run_without_api_key(self, mock_tempdir, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test run without KIMI_API_KEY."""
        from tools.ask import Ask
        
        mock_github.get_pr.return_value = mock_pr
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_asyncio.return_value = "KIMI_API_KEY is required."
        
        ask = Ask(github=mock_github)
        ask.load_context = Mock()
        ask.get_diff = Mock(return_value=("diff content", {}, []))
        ask.get_skill = Mock(return_value=None)
        ask.clone_repo = Mock(return_value=True)
        
        result = ask.run("owner/repo", 123, question="What does this do?")
        
        assert "KIMI_API_KEY" in result
