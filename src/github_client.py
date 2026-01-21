"""GitHub API client for PR operations."""

import os
import re
import logging
from typing import List, Dict, Optional, Set, Any

from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Issue import Issue
from github.Commit import Commit

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub PR operations."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required")

        self.client: Github = Github(self.token)

    def get_pr(self, repo_name: str, pr_number: int) -> PullRequest:
        """Get pull request object."""
        try:
            repo = self.client.get_repo(repo_name)
            return repo.get_pull(pr_number)
        except GithubException as e:
            logger.error(f"Failed to get PR #{pr_number} from {repo_name}: {e}")
            raise

    def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        """Get PR diff content."""
        pr = self.get_pr(repo_name, pr_number)
        files = pr.get_files()

        diff_parts: List[str] = []
        for file in files:
            if file.patch:
                diff_parts.append(f"--- {file.filename}\n{file.patch}")

        return "\n\n".join(diff_parts)

    def get_pr_files(self, repo_name: str, pr_number: int) -> List[str]:
        """Get list of changed files in PR."""
        pr = self.get_pr(repo_name, pr_number)
        return [f.filename for f in pr.get_files()]

    def post_comment(self, repo_name: str, pr_number: int, body: str) -> None:
        """Post a comment on the PR."""
        try:
            pr = self.get_pr(repo_name, pr_number)
            pr.create_issue_comment(body)
            logger.info(f"Posted comment to PR #{pr_number}")
        except GithubException as e:
            logger.error(f"Failed to post comment to PR #{pr_number}: {e}")
            raise

    def post_review(
        self, repo_name: str, pr_number: int, body: str, event: str = "COMMENT"
    ) -> None:
        """Post a review on the PR.

        Args:
            event: APPROVE, REQUEST_CHANGES, or COMMENT
        """
        try:
            pr = self.get_pr(repo_name, pr_number)
            pr.create_review(body=body, event=event)
            logger.info(f"Posted review to PR #{pr_number} with event {event}")
        except GithubException as e:
            logger.error(f"Failed to post review to PR #{pr_number}: {e}")
            raise

    def add_reaction(
        self, repo_name: str, pr_number: int, comment_id: int, reaction: str = "eyes"
    ) -> None:
        """Add reaction to a comment."""
        try:
            repo = self.client.get_repo(repo_name)
            comment = repo.get_issue(pr_number).get_comment(comment_id)
            comment.create_reaction(reaction)
        except GithubException as e:
            logger.warning(f"Failed to add reaction: {e}")

    def reply_to_review_comment(
        self, repo_name: str, pr_number: int, comment_id: int, body: str
    ) -> None:
        """Reply to a review comment (inline comment)."""
        try:
            pr = self.get_pr(repo_name, pr_number)
            pr.create_review_comment_reply(comment_id, body)
            logger.info(f"Replied to review comment {comment_id}")
        except GithubException as e:
            logger.error(f"Failed to reply to review comment: {e}")
            raise

    def get_review_comment_context(
        self, repo_name: str, pr_number: int, comment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get context information for a review comment or a reply to review comment.

        This handles both:
        1. Direct review comments (pull_request_review_comment event)
        2. Replies to review comments (issue_comment event)

        Returns dict with:
        - path: File path
        - line: Line number
        - diff_hunk: Code context
        - body: Comment body
        - in_reply_to_id: Parent comment ID if this is a reply
        """
        try:
            repo = self.client.get_repo(repo_name)
            pr = self.get_pr(repo_name, pr_number)

            # First, check if this comment_id is a review comment
            for review_comment in pr.get_review_comments():
                if review_comment.id == comment_id:
                    return {
                        "path": review_comment.path,
                        "line": review_comment.line or review_comment.original_line,
                        "diff_hunk": review_comment.diff_hunk,
                        "body": review_comment.body,
                        "in_reply_to_id": review_comment.in_reply_to_id,
                    }

            # If not found, this might be an issue comment that's a reply to a review comment
            # GitHub's API doesn't directly expose the parent review comment for issue comments
            # We need to check if this is a conversation reply by looking at the comment HTML URL
            issue = repo.get_issue(pr_number)
            target_comment = None
            for issue_comment in issue.get_comments():
                if issue_comment.id == comment_id:
                    target_comment = issue_comment
                    break

            if not target_comment:
                logger.warning(f"Could not find comment {comment_id}")
                return None

            # Check if the comment URL indicates it's a review comment thread
            # Review comment URLs look like: .../pull/123#discussion_r456789
            # Issue comment URLs look like: .../pull/123#issuecomment-456789
            html_url = target_comment.html_url

            if "#discussion_r" in html_url:
                # This is a reply in a review comment thread
                # Extract the discussion ID
                discussion_id = html_url.split("#discussion_r")[-1]

                # Find the parent review comment by matching the discussion thread
                # The parent review comment will have the same discussion ID in its URL
                for review_comment in pr.get_review_comments():
                    if (
                        f"discussion_r{discussion_id}" in review_comment.html_url
                        or str(review_comment.id) == discussion_id
                    ):
                        return {
                            "path": review_comment.path,
                            "line": review_comment.line or review_comment.original_line,
                            "diff_hunk": review_comment.diff_hunk,
                            "body": target_comment.body,
                            "in_reply_to_id": review_comment.id,
                            "is_conversation_reply": True,
                        }

            logger.warning(
                f"Comment {comment_id} is not a review comment or reply to review comment"
            )
            return None

        except GithubException as e:
            logger.error(f"Failed to get review comment context: {e}")
            return None

    # === Inline Comments (Review Comments) ===

    def create_review_with_comments(
        self,
        repo_name: str,
        pr_number: int,
        comments: List[Dict[str, Any]],
        body: str = "",
        event: str = "COMMENT",
    ) -> None:
        """Submit a review with inline comments on specific lines.

        Args:
            comments: List of dicts with keys: path, line, body, side (optional), start_line (optional)
                      side: "RIGHT" for new code (default), "LEFT" for old code
                      start_line: For multi-line comments/suggestions
            body: Overall review body
            event: APPROVE, REQUEST_CHANGES, or COMMENT
        """
        try:
            pr = self.get_pr(repo_name, pr_number)
            commit = pr.get_commits().reversed[0]  # Latest commit

            # Filter valid comments (line must be in diff)
            valid_comments: List[Dict[str, Any]] = []
            diff_lines = self._get_diff_line_map(repo_name, pr_number)

            for c in comments:
                path: str = c.get("path", "")
                line: int = c.get("line", 0)
                side: str = c.get("side", "RIGHT")
                start_line: Optional[int] = c.get("start_line")

                # Validate line is in diff
                if path in diff_lines and line in diff_lines[path]:
                    comment_data: Dict[str, Any] = {
                        "path": path,
                        "line": line,
                        "body": c.get("body", ""),
                        "side": side,
                    }
                    # Add start_line for multi-line suggestions
                    if start_line and start_line != line:
                        comment_data["start_line"] = start_line
                        comment_data["start_side"] = side
                    valid_comments.append(comment_data)
                else:
                    logger.warning(f"Skipping comment: {path}:{line} not in diff")

            if valid_comments:
                pr.create_review(
                    commit=commit, body=body, event=event, comments=valid_comments
                )
                logger.info(f"Posted review with {len(valid_comments)} inline comments")
            elif body:
                # No valid inline comments, just post body
                pr.create_review(body=body, event=event)
                logger.info("Posted review without inline comments")

        except GithubException as e:
            logger.error(f"Failed to create review: {e}")
            raise

    def _get_diff_line_map(self, repo_name: str, pr_number: int) -> Dict[str, Set[int]]:
        """Get map of file -> set of valid line numbers in diff."""
        pr = self.get_pr(repo_name, pr_number)
        files = pr.get_files()

        line_map: Dict[str, Set[int]] = {}
        for file in files:
            if not file.patch:
                continue

            lines: Set[int] = set()
            current_line: int = 0

            for patch_line in file.patch.split("\n"):
                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                hunk_match = re.match(
                    r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", patch_line
                )
                if hunk_match:
                    current_line = int(hunk_match.group(1))
                    continue

                if patch_line.startswith("-"):
                    # Deleted line, don't increment
                    continue
                elif patch_line.startswith("+") or not patch_line.startswith("\\"):
                    # Added or context line
                    lines.add(current_line)
                    current_line += 1

            line_map[file.filename] = lines

        return line_map

    # === Labels ===

    def add_labels(self, repo_name: str, pr_number: int, labels: List[str]) -> None:
        """Add labels to a PR."""
        try:
            pr = self.get_pr(repo_name, pr_number)
            pr.add_to_labels(*labels)
            logger.info(f"Added labels to PR #{pr_number}: {labels}")
        except GithubException as e:
            logger.error(f"Failed to add labels: {e}")
            raise

    def remove_labels(self, repo_name: str, pr_number: int, labels: List[str]) -> None:
        """Remove labels from a PR."""
        try:
            pr = self.get_pr(repo_name, pr_number)
            for label in labels:
                try:
                    pr.remove_from_labels(label)
                except GithubException:
                    pass  # Label might not exist
            logger.info(f"Removed labels from PR #{pr_number}: {labels}")
        except GithubException as e:
            logger.error(f"Failed to remove labels: {e}")

    def get_repo_labels(self, repo_name: str) -> List[str]:
        """Get all available labels in the repo."""
        try:
            repo = self.client.get_repo(repo_name)
            return [label.name for label in repo.get_labels()]
        except GithubException as e:
            logger.error(f"Failed to get repo labels: {e}")
            return []

    # === Incremental Review ===

    def get_commits_since(
        self, repo_name: str, pr_number: int, since_sha: str
    ) -> List[Commit]:
        """Get commits after a specific SHA."""
        pr = self.get_pr(repo_name, pr_number)
        commits = list(pr.get_commits())

        new_commits: List[Commit] = []
        found = False
        for c in commits:
            if found:
                new_commits.append(c)
            if c.sha.startswith(since_sha):
                found = True

        return new_commits

    def get_diff_for_commits(self, repo_name: str, commit_shas: List[str]) -> str:
        """Get combined diff for specific commits."""
        repo = self.client.get_repo(repo_name)
        diff_parts: List[str] = []

        for sha in commit_shas:
            try:
                commit = repo.get_commit(sha)
                for file in commit.files:
                    if file.patch:
                        diff_parts.append(f"--- {file.filename}\n{file.patch}")
            except GithubException as e:
                logger.warning(f"Failed to get diff for commit {sha}: {e}")

        return "\n\n".join(diff_parts)

    def get_last_bot_comment(
        self, repo_name: str, pr_number: int, bot_marker: str = "<!-- kimi-review -->"
    ) -> Optional[Dict[str, Any]]:
        """Find the last comment from this bot with review marker.

        Returns dict with 'sha' and 'comment_id' if found.
        """
        pr = self.get_pr(repo_name, pr_number)
        comments = list(pr.get_issue_comments())

        for comment in reversed(comments):
            if bot_marker in comment.body:
                # Extract SHA from marker: <!-- kimi-review:sha=abc123 -->
                sha_match = re.search(
                    r"<!-- kimi-review:sha=([a-f0-9]+) -->", comment.body
                )
                if sha_match:
                    return {
                        "sha": sha_match.group(1),
                        "comment_id": comment.id,
                        "created_at": comment.created_at,
                    }
        return None

    # === Issue Operations ===

    def get_issue(self, repo_name: str, issue_number: int) -> Issue:
        """Get issue object."""
        try:
            repo = self.client.get_repo(repo_name)
            return repo.get_issue(issue_number)
        except GithubException as e:
            logger.error(f"Failed to get Issue #{issue_number} from {repo_name}: {e}")
            raise

    def post_issue_comment(self, repo_name: str, issue_number: int, body: str) -> None:
        """Post a comment on an issue."""
        try:
            issue = self.get_issue(repo_name, issue_number)
            issue.create_comment(body)
            logger.info(f"Posted comment to Issue #{issue_number}")
        except GithubException as e:
            logger.error(f"Failed to post comment to Issue #{issue_number}: {e}")
            raise

    def add_issue_reaction(
        self, repo_name: str, issue_number: int, comment_id: int, reaction: str = "eyes"
    ) -> None:
        """Add reaction to an issue comment."""
        try:
            repo = self.client.get_repo(repo_name)
            comment = repo.get_issue(issue_number).get_comment(comment_id)
            comment.create_reaction(reaction)
        except GithubException as e:
            logger.warning(f"Failed to add reaction to issue comment: {e}")

    def add_issue_labels(
        self, repo_name: str, issue_number: int, labels: List[str]
    ) -> None:
        """Add labels to an issue."""
        try:
            issue = self.get_issue(repo_name, issue_number)
            issue.add_to_labels(*labels)
            logger.info(f"Added labels to Issue #{issue_number}: {labels}")
        except GithubException as e:
            logger.error(f"Failed to add labels to issue: {e}")
            raise

    def create_pull_request(
        self, repo_name: str, title: str, body: str, head: str, base: str = "main"
    ) -> PullRequest:
        """Create a pull request.

        Args:
            repo_name: Repository name (owner/repo)
            title: PR title
            body: PR body/description
            head: Source branch name
            base: Target branch name (default: main)

        Returns:
            Created PullRequest object
        """
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.create_pull(title=title, body=body, head=head, base=base)
            logger.info(f"Created PR #{pr.number}: {title}")
            return pr
        except GithubException as e:
            logger.error(f"Failed to create PR: {e}")
            raise

    def get_pr_review_comments(
        self, repo_name: str, pr_number: int
    ) -> List[Dict[str, Any]]:
        """Get all review comments (inline comments) on a PR.

        Returns:
            List of dicts with: body, path, line, user, created_at
        """
        try:
            pr = self.get_pr(repo_name, pr_number)
            comments = []
            for comment in pr.get_review_comments():
                comments.append(
                    {
                        "body": comment.body,
                        "path": comment.path,
                        "line": comment.line or comment.original_line,
                        "user": comment.user.login,
                        "created_at": comment.created_at.isoformat(),
                    }
                )
            return comments
        except GithubException as e:
            logger.error(f"Failed to get review comments: {e}")
            return []

    def get_pr_issue_comments(
        self, repo_name: str, pr_number: int
    ) -> List[Dict[str, Any]]:
        """Get all issue comments (general comments) on a PR.

        Returns:
            List of dicts with: body, user, created_at
        """
        try:
            pr = self.get_pr(repo_name, pr_number)
            comments = []
            for comment in pr.get_issue_comments():
                comments.append(
                    {
                        "body": comment.body,
                        "user": comment.user.login,
                        "created_at": comment.created_at.isoformat(),
                    }
                )
            return comments
        except GithubException as e:
            logger.error(f"Failed to get issue comments: {e}")
            return []

    def get_linked_issue_number(self, repo_name: str, pr_number: int) -> Optional[int]:
        """Get the linked issue number from PR body (Closes #N pattern).

        Returns:
            Issue number if found, None otherwise
        """
        try:
            pr = self.get_pr(repo_name, pr_number)
            body = pr.body or ""
            # Match patterns like: Closes #123, Fixes #123, Resolves #123
            match = re.search(
                r"(?:closes|fixes|resolves)\s+#(\d+)", body, re.IGNORECASE
            )
            if match:
                return int(match.group(1))
            return None
        except GithubException as e:
            logger.error(f"Failed to get linked issue: {e}")
            return None
