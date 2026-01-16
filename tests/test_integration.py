"""Integration tests with mocked GitHub and Kimi APIs."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class MockPR:
    """Mock GitHub PR object."""
    def __init__(self):
        self.title = "feat: add user authentication"
        self.body = "This PR adds JWT authentication"
        self.number = 42
        self.head = Mock(sha="abc123", ref="feature/auth")
        self.base = Mock(ref="main")

    def get_commits(self):
        commit = Mock()
        commit.commit.message = "feat: add login endpoint"
        return [commit]

    def edit(self, **kwargs):
        pass

    def set_labels(self, *labels):
        pass


class MockGitHubClient:
    """Mock GitHub client."""
    def __init__(self):
        self.client = Mock()
        self.posted_comments = []
        self.reactions = []

    def get_pr(self, repo_name: str, pr_number: int):
        return MockPR()

    def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        return """diff --git a/src/auth.py b/src/auth.py
new file mode 100644
--- /dev/null
+++ b/src/auth.py
@@ -0,0 +1,20 @@
+import jwt
+
+def login(username, password):
+    # TODO: validate credentials
+    user_id = username  # Bug: should lookup user
+    token = jwt.encode({"user_id": user_id}, "secret")
+    return token
+
+def verify(token):
+    try:
+        payload = jwt.decode(token, "secret", algorithms=["HS256"])
+        return payload
+    except:
+        return None
"""

    def post_comment(self, repo_name: str, pr_number: int, body: str):
        self.posted_comments.append(body)

    def add_reaction(self, repo_name: str, pr_number: int, comment_id: int, reaction: str):
        self.reactions.append(reaction)


class MockKimiClient:
    """Mock Kimi client."""
    def __init__(self, api_key: str = "test", model: str = "kimi-k2-turbo-preview"):
        self._model = model

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value

    def chat(self, messages: list, **kwargs) -> str:
        """Return mock review response."""
        return """```yaml
summary: Code adds JWT authentication with some security concerns.
score: 72
estimated_effort: 2
suggestions:
  - relevant_file: src/auth.py
    language: python
    one_sentence_summary: Hardcoded secret key is a security risk
    suggestion_content: The JWT secret should be loaded from environment variables, not hardcoded.
    existing_code: 'token = jwt.encode({"user_id": user_id}, "secret")'
    improved_code: 'token = jwt.encode({"user_id": user_id}, os.environ["JWT_SECRET"])'
    relevant_lines_start: 6
    relevant_lines_end: 6
    label: security
    severity: critical
  - relevant_file: src/auth.py
    language: python
    one_sentence_summary: Bare except clause catches all exceptions
    suggestion_content: Use specific exception types instead of bare except.
    existing_code: "except:"
    improved_code: "except jwt.InvalidTokenError:"
    relevant_lines_start: 13
    relevant_lines_end: 13
    label: bug
    severity: medium
```"""


@pytest.fixture
def mock_action_config():
    """Create mock action config."""
    with patch('tools.base.get_action_config') as mock:
        config = Mock()
        config.model = "kimi-k2-turbo-preview"
        config.review_level = "normal"
        config.max_files = 10
        config.exclude_patterns = ["*.lock"]
        config.review = Mock(
            num_max_findings=5,
            extra_instructions=""
        )
        config.describe = Mock(
            generate_title=True,
            generate_labels=True,
            enable_walkthrough=True,
            extra_instructions=""
        )
        config.improve = Mock(
            num_suggestions=5,
            extra_instructions=""
        )
        mock.return_value = config
        yield config


class TestReviewerIntegration:
    """Integration tests for Reviewer tool."""

    def test_review_generates_output(self, mock_action_config):
        """Test that reviewer generates proper output."""
        from tools.reviewer import Reviewer

        kimi = MockKimiClient()
        github = MockGitHubClient()

        reviewer = Reviewer(kimi, github)

        # Mock load_context to avoid GitHub API calls
        reviewer.load_context = Mock()
        reviewer.repo_config = None
        reviewer.skill_manager = Mock()
        reviewer.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Review the code",
            scripts={}
        ))

        # Mock subprocess and asyncio.run to skip git clone and agent calls
        mock_agent_response = """```yaml
summary: Code adds JWT authentication with some security concerns.
score: 72
suggestions:
  - relevant_file: src/auth.py
    language: python
    one_sentence_summary: Hardcoded secret key is a security risk
    suggestion_content: The JWT secret should be loaded from environment variables.
    existing_code: 'token = jwt.encode({"user_id": user_id}, "secret")'
    improved_code: 'token = jwt.encode({"user_id": user_id}, os.environ["JWT_SECRET"])'
    relevant_lines_start: 6
    relevant_lines_end: 6
    label: security
    severity: critical
```"""
        with patch('subprocess.run') as mock_run, \
             patch('asyncio.run', return_value=mock_agent_response):
            mock_run.return_value = Mock(returncode=0)
            result = reviewer.run("owner/repo", 42)

        # Result could be empty (inline posted) or summary (fallback)
        assert result == "" or "Pull request overview" in result

    def test_review_handles_empty_diff(self, mock_action_config):
        """Test reviewer handles empty diff gracefully."""
        from tools.reviewer import Reviewer

        kimi = MockKimiClient()
        github = MockGitHubClient()
        github.get_pr_diff = Mock(return_value="")

        reviewer = Reviewer(kimi, github)
        reviewer.load_context = Mock()
        reviewer.skill_manager = Mock()
        reviewer.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Review the code",
            scripts={}
        ))

        result = reviewer.run("owner/repo", 42)

        assert "No changes" in result


class TestDescribeIntegration:
    """Integration tests for Describe tool."""

    def test_describe_generates_title_and_body(self, mock_action_config):
        """Test that describe generates title and body."""
        from tools.describe import Describe

        kimi = MockKimiClient()
        kimi.chat = Mock(return_value="""```yaml
title: "feat(auth): add JWT authentication"
type: feature
description: This PR implements JWT-based authentication.
labels:
  - enhancement
  - security
files:
  - filename: src/auth.py
    change_type: added
    summary: JWT authentication module
```""")

        github = MockGitHubClient()

        describe = Describe(kimi, github)
        describe.load_context = Mock()
        describe.repo_config = None
        describe.skill_manager = Mock()
        describe.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Generate PR description"
        ))

        title, body = describe.run("owner/repo", 42, update_pr=False)

        assert "auth" in title.lower() or "jwt" in title.lower()
        assert "authentication" in body.lower() or "JWT" in body


class TestImproveIntegration:
    """Integration tests for Improve tool."""

    def test_improve_generates_suggestions(self, mock_action_config):
        """Test that improve generates suggestions."""
        from tools.improve import Improve

        kimi = MockKimiClient()
        github = MockGitHubClient()

        improve = Improve(kimi, github)
        improve.load_context = Mock()
        improve.repo_config = None
        improve.skill_manager = Mock()
        improve.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Provide improvements"
        ))

        # Mock subprocess and asyncio.run to skip git clone and agent calls
        mock_agent_response = """```yaml
suggestions:
  - relevant_file: src/auth.py
    one_sentence_summary: Use environment variable for secret
    suggestion_content: Move secret to environment variable for security.
    existing_code: '"secret"'
    improved_code: 'os.environ["JWT_SECRET"]'
    language: python
    severity: high
```"""
        with patch('subprocess.run') as mock_run, \
             patch('asyncio.run', return_value=mock_agent_response):
            mock_run.return_value = Mock(returncode=0)
            result = improve.run("owner/repo", 42)

        assert "Kimi Code Suggestions" in result
        assert "Suggestion" in result


class TestAskIntegration:
    """Integration tests for Ask tool."""

    def test_ask_answers_question(self, mock_action_config):
        """Test that ask answers questions."""
        from tools.ask import Ask

        kimi = MockKimiClient()
        github = MockGitHubClient()

        ask = Ask(kimi, github)
        ask.load_context = Mock()
        ask.repo_config = None
        ask.skill_manager = Mock()
        ask.skill_manager.get_skill = Mock(return_value=Mock(
            instructions="Answer questions"
        ))

        # Mock subprocess and asyncio.run to skip git clone and agent calls
        mock_agent_response = "The login function authenticates users using JWT tokens."
        with patch('subprocess.run') as mock_run, \
             patch('asyncio.run', return_value=mock_agent_response):
            mock_run.return_value = Mock(returncode=0)
            result = ask.run("owner/repo", 42, question="What does the login function do?")

        assert "Kimi Answer" in result
        assert "login" in result.lower() or "JWT" in result

    def test_ask_requires_question(self, mock_action_config):
        """Test that ask requires a question."""
        from tools.ask import Ask

        kimi = MockKimiClient()
        github = MockGitHubClient()

        ask = Ask(kimi, github)

        result = ask.run("owner/repo", 42)

        assert "Please provide a question" in result


class TestKimiClientIntegration:
    """Integration tests for Kimi client."""

    def test_retry_on_rate_limit(self):
        """Test that client retries on rate limit."""
        from kimi_client import KimiClient

        with patch('kimi_client.Kimi') as mock_kimi_class, \
             patch('kimi_client.generate') as mock_generate:
            mock_kimi = Mock()
            mock_kimi_class.return_value = mock_kimi

            # First call fails with rate limit, second succeeds
            mock_message = Mock()
            mock_message.extract_text.return_value = "Success"
            mock_result = Mock()
            mock_result.message = mock_message
            mock_result.usage = Mock(input=10, output=5)

            call_count = [0]
            async def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("429 rate limit exceeded")
                return mock_result

            mock_generate.side_effect = side_effect

            client = KimiClient("test-key")

            with patch('time.sleep'):  # Skip actual sleep
                result = client.chat([{"role": "user", "content": "test"}])

            assert result == "Success"
            assert call_count[0] == 2  # Retried once
