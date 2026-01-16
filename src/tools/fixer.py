"""Issue fix tool using Kimi Agent SDK.

Analyzes issue, locates problem, generates fix, and creates PR.
"""

import asyncio
import logging
import os
import subprocess
import tempfile

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class Fixer(BaseTool):
    """Fix issues using Agent SDK with tool calling."""

    @property
    def skill_name(self) -> str:
        return "issue-fix"

    def run(self, repo_name: str, issue_number: int, **kwargs) -> str:
        """Run fix on an issue.

        Args:
            repo_name: Repository name (owner/repo)
            issue_number: Issue number to fix
        """
        # Get issue details
        issue = self.github.get_issue(repo_name, issue_number)
        
        logger.info(f"Fixing issue #{issue_number}: {issue.title}")

        # Clone repo to temp directory
        with tempfile.TemporaryDirectory() as work_dir:
            try:
                # Clone the repo
                clone_url = f"https://github.com/{repo_name}.git"
                subprocess.run(
                    ["git", "clone", "--depth", "1", clone_url, work_dir],
                    check=True, capture_output=True
                )
                
                # Run agent fix
                result = asyncio.run(self._run_agent_fix(
                    work_dir=work_dir,
                    repo_name=repo_name,
                    issue_number=issue_number,
                    issue_title=issue.title,
                    issue_body=issue.body or ""
                ))
                
                return result
                
            except Exception as e:
                logger.error(f"Fix failed: {e}")
                return f"❌ Failed to fix issue: {str(e)}"

    async def _run_agent_fix(
        self,
        work_dir: str,
        repo_name: str,
        issue_number: int,
        issue_title: str,
        issue_body: str
    ) -> str:
        """Run agent to fix the issue."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
        except ImportError:
            return "❌ kimi-agent-sdk not installed. This feature requires the agent-fix branch."

        # Ensure KIMI_API_KEY is set for agent-sdk
        api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("INPUT_KIMI_API_KEY")
        if not api_key:
            return "❌ KIMI_API_KEY is required for /fix command"
        
        # Set environment variables for agent-sdk (kimi-cli)
        os.environ["KIMI_API_KEY"] = api_key
        os.environ["KIMI_BASE_URL"] = "https://api.moonshot.cn/v1"
        os.environ["KIMI_MODEL_NAME"] = "kimi-k2-turbo-preview"

        # Track agent output
        agent_output = []

        # Define the prompt
        fix_prompt = f"""You are a code fixing agent. Analyze this GitHub issue and fix it.

## Issue #{issue_number}: {issue_title}

{issue_body}

## Instructions

1. First, search the codebase to understand the problem
2. Read relevant files to locate the bug
3. Make the necessary code changes to fix the issue
4. Verify your changes are correct

Work in the current directory. Use the available tools to search, read, and modify files.

When done, summarize what you changed.
"""

        try:
            async with await Session.create(
                work_dir=work_dir,
                model="kimi-k2-turbo-preview",
                yolo=True,  # Auto-approve tool calls
                max_steps_per_turn=20,
            ) as session:
                async for msg in session.prompt(fix_prompt):
                    # Handle different message types
                    if isinstance(msg, TextPart):
                        agent_output.append(msg.text)
                        logger.info(f"Agent: {msg.text[:100]}...")
                    elif isinstance(msg, ApprovalRequest):
                        # Should not happen with yolo=True, but handle anyway
                        msg.resolve("approve")

            # Check if any files were modified
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=work_dir, capture_output=True, text=True
            )
            
            if not result.stdout.strip():
                return self._format_no_changes(agent_output, issue_number)

            # Get the changes
            modified_files = [
                line.split()[-1] for line in result.stdout.strip().split('\n')
                if line.strip()
            ]
            
            # Create branch and commit
            branch_name = f"fix/issue-{issue_number}"
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=work_dir, check=True)
            subprocess.run(["git", "add", "-A"], cwd=work_dir, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"fix: resolve issue #{issue_number}\n\n{issue_title}"],
                cwd=work_dir, check=True,
                env={**os.environ, "GIT_AUTHOR_NAME": "Kimi Bot", "GIT_AUTHOR_EMAIL": "kimi@moonshot.cn",
                     "GIT_COMMITTER_NAME": "Kimi Bot", "GIT_COMMITTER_EMAIL": "kimi@moonshot.cn"}
            )

            # Push branch (requires GITHUB_TOKEN with push access)
            github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN")
            if github_token:
                push_url = f"https://x-access-token:{github_token}@github.com/{repo_name}.git"
                # Force push in case branch exists from previous attempt
                push_result = subprocess.run(
                    ["git", "push", "-f", push_url, branch_name],
                    cwd=work_dir, capture_output=True, text=True
                )
                if push_result.returncode != 0:
                    # Sanitize error message to hide token
                    error_msg = (push_result.stderr or push_result.stdout or "Unknown error")
                    error_msg = error_msg.replace(github_token, "***")
                    logger.error(f"Git push failed: {error_msg}")
                    return f"❌ Failed to push branch: {error_msg}"
            else:
                return "❌ GITHUB_TOKEN required to push changes"

            # Create PR
            pr = self.github.create_pull_request(
                repo_name=repo_name,
                title=f"fix: resolve issue #{issue_number}",
                body=self._format_pr_body(issue_number, issue_title, modified_files, agent_output),
                head=branch_name,
                base="main"
            )

            return self._format_success(pr.number, pr.html_url, modified_files, agent_output)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f"❌ Agent execution failed: {str(e)}"

    def _format_no_changes(self, agent_output: list, issue_number: int) -> str:
        """Format response when no changes were made."""
        summary = "\n".join(agent_output[-3:]) if agent_output else "No analysis available"
        return f"""### 🌗 Issue Fix Analysis

Unable to automatically fix issue #{issue_number}.

**Agent Analysis:**
{summary}

**Possible reasons:**
- The issue may require manual investigation
- The problem might be in external dependencies
- More context may be needed

{self.format_footer()}
"""

    def _format_success(self, pr_number: int, pr_url: str, files: list, agent_output: list) -> str:
        """Format success response."""
        summary = "\n".join(agent_output[-3:]) if agent_output else ""
        files_list = "\n".join(f"- `{f}`" for f in files[:10])
        
        return f"""### 🌗 Issue Fixed!

Created PR #{pr_number} with the fix.

**Modified files:**
{files_list}

**Summary:**
{summary}

👉 [Review the PR]({pr_url})

{self.format_footer()}
"""

    def _format_pr_body(self, issue_number: int, issue_title: str, files: list, agent_output: list) -> str:
        """Format PR body."""
        summary = "\n".join(agent_output[-5:]) if agent_output else "Automated fix"
        files_list = "\n".join(f"- `{f}`" for f in files)
        
        return f"""## Summary

Automated fix for #{issue_number}: {issue_title}

## Changes

{files_list}

## Analysis

{summary}

---
<sub>🌗 Generated by [Kimi Actions](https://github.com/MoonshotAI/kimi-actions) using Agent SDK</sub>

Closes #{issue_number}
"""
