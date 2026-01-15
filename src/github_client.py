"""GitHub API client for PR operations."""

import os
import re
import logging
from typing import List, Dict, Optional
from github import Github, GithubException

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub PR operations."""

    def __init__(self, token: str = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required")

        self.client = Github(self.token)

    def get_pr(self, repo_name: str, pr_number: int):
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

        diff_parts = []
        for file in files:
            if file.patch:
                diff_parts.append(f"--- {file.filename}\n{file.patch}")

        return "\n\n".join(diff_parts)

    def get_pr_files(self, repo_name: str, pr_number: int) -> list:
        """Get list of changed files in PR."""
        pr = self.get_pr(repo_name, pr_number)
        return [f.filename for f in pr.get_files()]

    def post_comment(self, repo_name: str, pr_number: int, body: str):
        """Post a comment on the PR."""
        try:
            pr = self.get_pr(repo_name, pr_number)
            pr.create_issue_comment(body)
            logger.info(f"Posted comment to PR #{pr_number}")
        except GithubException as e:
            logger.error(f"Failed to post comment to PR #{pr_number}: {e}")
            raise

    def post_review(self, repo_name: str, pr_number: int, body: str, event: str = "COMMENT"):
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

    def add_reaction(self, repo_name: str, pr_number: int, comment_id: int, reaction: str = "eyes"):
        """Add reaction to a comment."""
        try:
            repo = self.client.get_repo(repo_name)
            comment = repo.get_issue(pr_number).get_comment(comment_id)
            comment.create_reaction(reaction)
        except GithubException as e:
            logger.warning(f"Failed to add reaction: {e}")

    def reply_to_review_comment(self, repo_name: str, pr_number: int, comment_id: int, body: str):
        """Reply to a review comment (inline comment)."""
        try:
            pr = self.get_pr(repo_name, pr_number)
            pr.create_review_comment_reply(comment_id, body)
            logger.info(f"Replied to review comment {comment_id}")
        except GithubException as e:
            logger.error(f"Failed to reply to review comment: {e}")
            raise

    # === Inline Comments (Review Comments) ===

    def create_review_with_comments(
        self,
        repo_name: str,
        pr_number: int,
        comments: List[Dict],
        body: str = "",
        event: str = "COMMENT"
    ):
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
            valid_comments = []
            diff_lines = self._get_diff_line_map(repo_name, pr_number)

            for c in comments:
                path = c.get("path", "")
                line = c.get("line", 0)
                side = c.get("side", "RIGHT")
                start_line = c.get("start_line")

                # Validate line is in diff
                if path in diff_lines and line in diff_lines[path]:
                    comment_data = {
                        "path": path,
                        "line": line,
                        "body": c.get("body", ""),
                        "side": side
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
                    commit=commit,
                    body=body,
                    event=event,
                    comments=valid_comments
                )
                logger.info(f"Posted review with {len(valid_comments)} inline comments")
            elif body:
                # No valid inline comments, just post body
                pr.create_review(body=body, event=event)
                logger.info("Posted review without inline comments")

        except GithubException as e:
            logger.error(f"Failed to create review: {e}")
            raise

    def _get_diff_line_map(self, repo_name: str, pr_number: int) -> Dict[str, set]:
        """Get map of file -> set of valid line numbers in diff."""
        pr = self.get_pr(repo_name, pr_number)
        files = pr.get_files()

        line_map = {}
        for file in files:
            if not file.patch:
                continue

            lines = set()
            current_line = 0

            for patch_line in file.patch.split('\n'):
                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                hunk_match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', patch_line)
                if hunk_match:
                    current_line = int(hunk_match.group(1))
                    continue

                if patch_line.startswith('-'):
                    # Deleted line, don't increment
                    continue
                elif patch_line.startswith('+') or not patch_line.startswith('\\'):
                    # Added or context line
                    lines.add(current_line)
                    current_line += 1

            line_map[file.filename] = lines

        return line_map

    # === Labels ===

    def add_labels(self, repo_name: str, pr_number: int, labels: List[str]):
        """Add labels to a PR."""
        try:
            pr = self.get_pr(repo_name, pr_number)
            pr.add_to_labels(*labels)
            logger.info(f"Added labels to PR #{pr_number}: {labels}")
        except GithubException as e:
            logger.error(f"Failed to add labels: {e}")
            raise

    def remove_labels(self, repo_name: str, pr_number: int, labels: List[str]):
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

    def get_commits_since(self, repo_name: str, pr_number: int, since_sha: str) -> List:
        """Get commits after a specific SHA."""
        pr = self.get_pr(repo_name, pr_number)
        commits = list(pr.get_commits())

        new_commits = []
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
        diff_parts = []

        for sha in commit_shas:
            try:
                commit = repo.get_commit(sha)
                for file in commit.files:
                    if file.patch:
                        diff_parts.append(f"--- {file.filename}\n{file.patch}")
            except GithubException as e:
                logger.warning(f"Failed to get diff for commit {sha}: {e}")

        return "\n\n".join(diff_parts)

    def get_last_bot_comment(self, repo_name: str, pr_number: int, bot_marker: str = "<!-- kimi-review -->") -> Optional[Dict]:
        """Find the last comment from this bot with review marker.

        Returns dict with 'sha' and 'comment_id' if found.
        """
        pr = self.get_pr(repo_name, pr_number)
        comments = list(pr.get_issue_comments())

        for comment in reversed(comments):
            if bot_marker in comment.body:
                # Extract SHA from marker: <!-- kimi-review:sha=abc123 -->
                sha_match = re.search(r'<!-- kimi-review:sha=([a-f0-9]+) -->', comment.body)
                if sha_match:
                    return {
                        "sha": sha_match.group(1),
                        "comment_id": comment.id,
                        "created_at": comment.created_at
                    }
        return None

    # === Issue Operations ===

    def get_issue(self, repo_name: str, issue_number: int):
        """Get issue object."""
        try:
            repo = self.client.get_repo(repo_name)
            return repo.get_issue(issue_number)
        except GithubException as e:
            logger.error(f"Failed to get Issue #{issue_number} from {repo_name}: {e}")
            raise

    def post_issue_comment(self, repo_name: str, issue_number: int, body: str):
        """Post a comment on an issue."""
        try:
            issue = self.get_issue(repo_name, issue_number)
            issue.create_comment(body)
            logger.info(f"Posted comment to Issue #{issue_number}")
        except GithubException as e:
            logger.error(f"Failed to post comment to Issue #{issue_number}: {e}")
            raise

    def add_issue_reaction(self, repo_name: str, issue_number: int, comment_id: int, reaction: str = "eyes"):
        """Add reaction to an issue comment."""
        try:
            repo = self.client.get_repo(repo_name)
            comment = repo.get_issue(issue_number).get_comment(comment_id)
            comment.create_reaction(reaction)
        except GithubException as e:
            logger.warning(f"Failed to add reaction to issue comment: {e}")

    def add_issue_labels(self, repo_name: str, issue_number: int, labels: List[str]):
        """Add labels to an issue."""
        try:
            issue = self.get_issue(repo_name, issue_number)
            issue.add_to_labels(*labels)
            logger.info(f"Added labels to Issue #{issue_number}: {labels}")
        except GithubException as e:
            logger.error(f"Failed to add labels to issue: {e}")
            raise
