"""GitHub API client for PR operations."""

import os
import logging
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
