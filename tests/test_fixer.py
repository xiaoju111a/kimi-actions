"""Tests for Fixer tool."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestFixer:
    """Test Fixer tool."""

    def test_fixer_import(self):
        """Test Fixer can be imported."""
        from tools.fixer import Fixer
        assert Fixer is not None

    def test_fixer_skill_name(self):
        """Test Fixer skill name."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        assert fixer.skill_name == "issue-fix"

    def test_format_no_changes(self):
        """Test _format_no_changes output."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        result = fixer._format_no_changes(
            agent_summary="Analyzed the code. No bug found.",
            issue_number=42
        )
        
        assert "Issue Fix Analysis" in result
        assert "#42" in result
        assert "No bug found" in result

    def test_format_success(self):
        """Test _format_success output."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        result = fixer._format_success(
            pr_number=123,
            pr_url="https://github.com/test/repo/pull/123",
            files=["src/main.py", "src/utils.py"],
            agent_summary="Fixed the bug in authentication logic."
        )
        
        assert "Issue Fixed" in result
        assert "#123" in result
        assert "src/main.py" in result
        assert "https://github.com/test/repo/pull/123" in result

    def test_format_pr_body(self):
        """Test _format_pr_body output."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        result = fixer._format_pr_body(
            issue_number=42,
            issue_title="Bug in login",
            files=["src/auth.py"],
            agent_summary="Fixed authentication issue by correcting the token validation."
        )
        
        assert "#42" in result
        assert "Bug in login" in result
        assert "src/auth.py" in result
        assert "Closes #42" in result

    @patch('tools.fixer.subprocess')
    def test_run_clone_failure(self, mock_subprocess):
        """Test run handles clone failure."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.title = "Test Issue"
        mock_issue.body = "Test body"
        mock_github.get_issue.return_value = mock_issue
        
        # Mock clone failure
        mock_subprocess.run.side_effect = Exception("Clone failed")
        
        fixer = Fixer(mock_kimi, mock_github)
        result = fixer.run("test/repo", 1)
        
        assert "Failed to fix issue" in result

    def test_run_without_agent_sdk(self):
        """Test run returns error when agent-sdk not installed."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.title = "Test Issue"
        mock_issue.body = "Test body"
        mock_github.get_issue.return_value = mock_issue
        
        fixer = Fixer(mock_kimi, mock_github)
        
        # Mock subprocess to succeed for clone
        with patch('tools.fixer.subprocess') as mock_subprocess:
            mock_subprocess.run.return_value = Mock(returncode=0)
            
            # Mock asyncio.run to simulate agent-sdk not installed
            with patch('tools.fixer.asyncio.run') as mock_asyncio:
                mock_asyncio.side_effect = ImportError("No module named 'kimi_agent_sdk'")
                
                result = fixer.run("test/repo", 1)
                
                # Should handle the error gracefully
                assert "Failed" in result or "Error" in result.lower() or "error" in result.lower()


class TestFixerIntegration:
    """Integration tests for Fixer (require agent-sdk)."""

    @pytest.mark.skip(reason="Requires kimi-agent-sdk installed")
    def test_agent_sdk_import(self):
        """Test agent-sdk can be imported."""
        from kimi_agent_sdk import Session, ApprovalRequest, TextPart
        assert Session is not None
        assert ApprovalRequest is not None
        assert TextPart is not None


class TestFixerUpdate:
    """Test Fixer update (fixup) functionality."""

    def test_format_no_update(self):
        """Test _format_no_update output."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        result = fixer._format_no_update(
            agent_summary="No changes needed based on feedback.",
            pr_number=123
        )
        
        assert "PR Update Analysis" in result
        assert "#123" in result
        assert "No changes" in result

    def test_format_update_success(self):
        """Test _format_update_success output."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        result = fixer._format_update_success(
            pr_number=123,
            files=["src/main.py"],
            agent_summary="Updated variable names as requested."
        )
        
        assert "PR Updated" in result
        assert "#123" in result
        assert "src/main.py" in result
        assert "Updated variable names" in result

    def test_build_agent_summary_with_explicit_summary(self):
        """Test _build_agent_summary extracts explicit summary."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        final_summary = """
---SUMMARY---
**Problem**: Typo in README
**Solution**: Fixed the typo
**Files Modified**: README.md
---END SUMMARY---
"""
        result = fixer._build_agent_summary([], [], final_summary)
        
        assert "Problem" in result
        assert "Typo" in result

    def test_build_agent_summary_fallback(self):
        """Test _build_agent_summary fallback when no explicit summary."""
        from tools.fixer import Fixer
        
        mock_kimi = Mock()
        mock_github = Mock()
        fixer = Fixer(mock_kimi, mock_github)
        
        text_parts = ["Analyzing code.", "Found the issue.", "Fixed it."]
        result = fixer._build_agent_summary(text_parts, [], "")
        
        assert "Analyzing" in result or "Found" in result or "Fixed" in result
