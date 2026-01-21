"""Tests for Describe tool."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def mock_github():
    """Mock GitHub client."""
    return Mock()


@pytest.fixture
def mock_config():
    """Mock action config."""
    with patch("tools.base.get_action_config") as mock_cfg:
        config = Mock()
        config.model = "kimi-k2-thinking"
        config.exclude_patterns = []
        config.describe = Mock()
        config.describe.generate_title = True
        config.describe.generate_labels = True
        config.describe.enable_walkthrough = True
        mock_cfg.return_value = config
        yield config


@pytest.fixture
def mock_pr():
    """Mock PR object."""
    pr = Mock()
    pr.number = 123
    pr.title = "Original Title"
    pr.body = "Original description"
    pr.head.sha = "abc123"
    pr.head.ref = "feature-branch"
    pr.base.ref = "main"
    pr.edit = Mock()
    pr.set_labels = Mock()

    # Mock commits
    mock_commit = Mock()
    mock_commit.commit.message = "feat: add new feature"
    pr.get_commits.return_value = [mock_commit]

    return pr


class TestDescribeBasic:
    """Test basic Describe functionality."""

    def test_describe_initialization(self, mock_github, mock_config):
        """Test Describe tool initialization."""
        from tools.describe import Describe

        describe = Describe(github=mock_github)
        assert describe.skill_name == "describe"

    def test_skill_name_property(self, mock_github, mock_config):
        """Test skill_name property."""
        from tools.describe import Describe

        describe = Describe(github=mock_github)
        assert describe.skill_name == "describe"


class TestDescribePRGeneration:
    """Test PR description generation."""

    @patch("tools.describe.asyncio.run")
    def test_run_generates_description(
        self, mock_asyncio, mock_github, mock_pr, mock_config
    ):
        """Test successful description generation."""
        from tools.describe import Describe

        mock_github.get_pr.return_value = mock_pr
        mock_asyncio.return_value = """```yaml
title: "New Feature: Add user authentication"
type: "feature"
description: "Implements JWT-based authentication"
labels:
  - feature
  - security
```"""

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("diff content", {}, []))
        describe.get_skill = Mock(return_value=None)

        title, body = describe.run("owner/repo", 123)

        assert "New Feature" in title
        assert "authentication" in title
        assert "JWT" in body

    @patch("tools.describe.asyncio.run")
    def test_run_with_empty_diff(self, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test run with empty diff."""
        from tools.describe import Describe

        mock_github.get_pr.return_value = mock_pr

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("", {}, []))

        title, body = describe.run("owner/repo", 123)

        assert title == "Original Title"
        assert "No changes detected" in body


class TestDescribeYAMLParsing:
    """Test YAML response parsing."""

    def test_parse_response_valid_yaml(self, mock_github, mock_config):
        """Test parsing valid YAML response."""
        from tools.describe import Describe

        describe = Describe(github=mock_github)
        describe.format_footer = Mock(return_value="Footer")

        response = """```yaml
title: "Fix: Resolve memory leak"
type: "bug_fix"
description: "Fixed memory leak in cache"
labels:
  - bug
  - performance
```"""

        title, body, labels = describe._parse_response(response, "Default Title")

        assert "Fix: Resolve memory leak" == title
        assert "bug" in labels
        assert "performance" in labels
        assert "memory leak" in body

    def test_parse_response_without_code_block(self, mock_github, mock_config):
        """Test parsing YAML without code block."""
        from tools.describe import Describe

        describe = Describe(github=mock_github)
        describe.format_footer = Mock(return_value="Footer")

        response = """title: "Refactor: Clean up code"
type: "refactor"
description: "Improved code structure"
labels:
  - refactor
"""

        title, body, labels = describe._parse_response(response, "Default Title")

        assert "Refactor: Clean up code" == title
        assert "refactor" in labels

    def test_parse_response_invalid_yaml(self, mock_github, mock_config):
        """Test parsing invalid YAML."""
        from tools.describe import Describe

        describe = Describe(github=mock_github)
        describe.format_footer = Mock(return_value="Footer")

        response = "This is not valid YAML: {{{["

        title, body, labels = describe._parse_response(response, "Default Title")

        assert title == "Default Title"
        assert response in body
        assert labels == []


class TestDescribeTitleAndBody:
    """Test title and body formatting."""

    def test_parse_response_with_type_emoji(self, mock_github, mock_config):
        """Test that type gets emoji in body."""
        from tools.describe import Describe

        describe = Describe(github=mock_github)
        describe.format_footer = Mock(return_value="Footer")

        response = """```yaml
title: "New Feature"
type: "feature"
description: "Added new feature"
```"""

        title, body, labels = describe._parse_response(response, "Default")

        assert "✨" in body or "feature" in body.lower()

    def test_parse_response_with_files_walkthrough(self, mock_github, mock_config):
        """Test file walkthrough formatting."""
        from tools.describe import Describe

        describe = Describe(github=mock_github)
        describe.format_footer = Mock(return_value="Footer")

        response = """```yaml
title: "Update files"
description: "Updated multiple files"
files:
  - filename: "src/main.py"
    change_type: "modified"
    summary: "Added new function"
  - filename: "tests/test_main.py"
    change_type: "added"
    summary: "Added tests"
```"""

        title, body, labels = describe._parse_response(response, "Default")

        assert "Changed Files" in body or "src/main.py" in body
        assert "tests/test_main.py" in body


class TestDescribeLabelGeneration:
    """Test label generation."""

    @patch("tools.describe.asyncio.run")
    def test_run_applies_labels(self, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test that labels are applied to PR."""
        from tools.describe import Describe

        mock_github.get_pr.return_value = mock_pr
        mock_asyncio.return_value = """```yaml
title: "New Feature"
type: "feature"
labels:
  - feature
  - enhancement
```"""

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("diff content", {}, []))
        describe.get_skill = Mock(return_value=None)

        title, body = describe.run("owner/repo", 123, update_pr=True)

        mock_pr.set_labels.assert_called_once()

    @patch("tools.describe.asyncio.run")
    def test_run_without_label_generation(
        self, mock_asyncio, mock_github, mock_pr, mock_config
    ):
        """Test run without label generation."""
        from tools.describe import Describe

        mock_config.describe.generate_labels = False
        mock_github.get_pr.return_value = mock_pr
        mock_asyncio.return_value = """```yaml
title: "New Feature"
labels:
  - feature
```"""

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("diff content", {}, []))
        describe.get_skill = Mock(return_value=None)

        title, body = describe.run("owner/repo", 123, update_pr=True)

        mock_pr.set_labels.assert_not_called()


class TestDescribeUpdatePR:
    """Test PR update functionality."""

    @patch("tools.describe.asyncio.run")
    def test_run_updates_pr(self, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test that PR is updated."""
        from tools.describe import Describe

        mock_github.get_pr.return_value = mock_pr
        mock_asyncio.return_value = """```yaml
title: "Updated Title"
description: "Updated description"
```"""

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("diff content", {}, []))
        describe.get_skill = Mock(return_value=None)

        title, body = describe.run("owner/repo", 123, update_pr=True)

        mock_pr.edit.assert_called_once()
        call_args = mock_pr.edit.call_args
        assert call_args[1]["title"] == "Updated Title"

    @patch("tools.describe.asyncio.run")
    def test_run_without_update(self, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test run without updating PR."""
        from tools.describe import Describe

        mock_github.get_pr.return_value = mock_pr
        mock_asyncio.return_value = """```yaml
title: "New Title"
description: "New description"
```"""

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("diff content", {}, []))
        describe.get_skill = Mock(return_value=None)

        title, body = describe.run("owner/repo", 123, update_pr=False)

        mock_pr.edit.assert_not_called()

    @patch("tools.describe.asyncio.run")
    def test_run_handles_update_error(
        self, mock_asyncio, mock_github, mock_pr, mock_config
    ):
        """Test handling PR update errors."""
        from tools.describe import Describe

        mock_github.get_pr.return_value = mock_pr
        mock_pr.edit.side_effect = Exception("Update failed")
        mock_asyncio.return_value = """```yaml
title: "New Title"
description: "New description"
```"""

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("diff content", {}, []))
        describe.get_skill = Mock(return_value=None)

        # Should not raise exception
        title, body = describe.run("owner/repo", 123, update_pr=True)

        assert title == "New Title"


class TestDescribeCommentGeneration:
    """Test comment generation mode."""

    @patch("tools.describe.asyncio.run")
    def test_generate_comment(self, mock_asyncio, mock_github, mock_pr, mock_config):
        """Test generating description as comment."""
        from tools.describe import Describe

        mock_github.get_pr.return_value = mock_pr
        mock_asyncio.return_value = """```yaml
title: "Comment Title"
description: "Comment description"
```"""

        describe = Describe(github=mock_github)
        describe.load_context = Mock()
        describe.get_diff = Mock(return_value=("diff content", {}, []))
        describe.get_skill = Mock(return_value=None)

        comment = describe.generate_comment("owner/repo", 123)

        assert "Kimi PR Description" in comment
        assert "Suggested Title" in comment
        assert "Comment Title" in comment
