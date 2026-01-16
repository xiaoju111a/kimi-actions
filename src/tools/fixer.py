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
            from kimi_agent_sdk import (
                Session, ApprovalRequest, TextPart, ThinkPart,
                ToolCallPart, ToolResult
            )
        except ImportError:
            return "❌ kimi-agent-sdk not installed. This feature requires the agent-fix branch."

        # Ensure KIMI_API_KEY is set for agent-sdk
        api_key = self.setup_agent_env()
        if not api_key:
            return "❌ KIMI_API_KEY is required for /fix command"
        
        # Set environment variables for agent-sdk (kimi-cli)

        # Track agent output - collect text parts and build complete messages
        text_parts = []  # Collect text fragments
        tool_actions = []  # Track tool calls for summary
        final_summary = ""  # Store the final summary

        # Define the prompt - focused and efficient
        fix_prompt = f"""You are a code fixing agent. Fix this GitHub issue.

## Issue #{issue_number}: {issue_title}

{issue_body}

## Instructions

1. Search for the relevant file(s) mentioned in the issue
2. Read the file and locate the problem
3. Make the fix
4. Done - do NOT verify or explore further

Be efficient. Make the fix quickly and stop.
"""

        try:
            async with await Session.create(
                work_dir=work_dir,
                model=self.AGENT_MODEL,
                yolo=True,  # Auto-approve tool calls
                max_steps_per_turn=100,
            ) as session:
                async for msg in session.prompt(fix_prompt):
                    # Handle different message types
                    if isinstance(msg, TextPart):
                        text = msg.text
                        text_parts.append(text)
                        logger.info(f"Agent text: {text[:100]}...")
                        
                        # Check if this contains the final summary
                        if "---SUMMARY---" in text or "**Problem**:" in text:
                            final_summary = text
                    elif isinstance(msg, ThinkPart):
                        # Thinking content - useful for debugging
                        logger.debug(f"Agent thinking: {msg.text[:100]}...")
                    elif isinstance(msg, ToolCallPart):
                        # Track tool calls for summary
                        tool_name = getattr(msg, 'name', None) or getattr(msg, 'function', {}).get('name', 'unknown')
                        tool_actions.append(tool_name)
                        logger.info(f"Agent tool call: {tool_name}")
                    elif isinstance(msg, ToolResult):
                        # Tool result - log but don't include in output
                        logger.debug("Tool result received")
                    elif isinstance(msg, ApprovalRequest):
                        # Should not happen with yolo=True, but handle anyway
                        msg.resolve("approve")
            
            # Build agent output from collected parts
            agent_output = self._build_agent_summary(text_parts, tool_actions, final_summary)

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

    def _build_agent_summary(self, text_parts: list, tool_actions: list, final_summary: str) -> str:
        """Build a clean summary from agent output.
        
        Args:
            text_parts: List of text fragments from agent
            tool_actions: List of tool names called
            final_summary: Explicit summary if found
            
        Returns:
            Clean summary string
        """
        # If we have an explicit summary, extract and use it
        if final_summary and "---SUMMARY---" in final_summary:
            # Extract content between markers
            start = final_summary.find("---SUMMARY---") + len("---SUMMARY---")
            end = final_summary.find("---END SUMMARY---")
            if end > start:
                return final_summary[start:end].strip()
        
        # If we have a summary with Problem/Solution format
        if final_summary and "**Problem**:" in final_summary:
            return final_summary.strip()
        
        # Otherwise, combine all text parts into a coherent summary
        full_text = "".join(text_parts)
        
        # Clean up the text - remove excessive whitespace
        import re
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        
        # If text is too long, take the last meaningful portion
        if len(full_text) > 500:
            # Try to find the last complete sentence
            sentences = full_text.split('. ')
            summary_parts = []
            char_count = 0
            for sentence in reversed(sentences):
                if char_count + len(sentence) < 500:
                    summary_parts.insert(0, sentence)
                    char_count += len(sentence)
                else:
                    break
            full_text = '. '.join(summary_parts)
        
        # Add tool action summary if we have it
        if tool_actions and not full_text:
            unique_tools = list(dict.fromkeys(tool_actions))  # Preserve order, remove duplicates
            full_text = f"Agent performed: {', '.join(unique_tools[:5])}"
        
        return full_text if full_text else "Fix applied successfully."

    def _format_no_changes(self, agent_summary: str, issue_number: int) -> str:
        """Format response when no changes were made."""
        return f"""### 🌗 Issue Fix Analysis

Unable to automatically fix issue #{issue_number}.

**Agent Analysis:**
{agent_summary}

**Possible reasons:**
- The issue may require manual investigation
- The problem might be in external dependencies
- More context may be needed

{self.format_footer()}
"""

    def _format_success(self, pr_number: int, pr_url: str, files: list, agent_summary: str) -> str:
        """Format success response."""
        files_list = "\n".join(f"- `{f}`" for f in files[:10])
        
        return f"""### 🌗 Issue Fixed!

Created PR #{pr_number} with the fix.

**Modified files:**
{files_list}

**Summary:**
{agent_summary}

👉 [Review the PR]({pr_url})

{self.format_footer()}
"""

    def _format_pr_body(self, issue_number: int, issue_title: str, files: list, agent_summary: str) -> str:
        """Format PR body."""
        files_list = "\n".join(f"- `{f}`" for f in files)
        
        return f"""## Summary

Automated fix for #{issue_number}: {issue_title}

## Changes

{files_list}

## Analysis

{agent_summary}

---
<sub>🌗 Generated by [Kimi Actions](https://github.com/MoonshotAI/kimi-actions) using Agent SDK</sub>

Closes #{issue_number}
"""

    def update(self, repo_name: str, pr_number: int, feedback: str = "", **kwargs) -> str:
        """Update an existing PR based on feedback.

        Args:
            repo_name: Repository name (owner/repo)
            pr_number: PR number to update
            feedback: User feedback/request for changes
        """
        # Get PR details
        pr = self.github.get_pr(repo_name, pr_number)
        branch_name = pr.head.ref
        
        logger.info(f"Updating PR #{pr_number} on branch {branch_name}")

        # Get linked issue number
        issue_number = self.github.get_linked_issue_number(repo_name, pr_number)
        
        # Get review comments and issue comments for context
        review_comments = self.github.get_pr_review_comments(repo_name, pr_number)
        issue_comments = self.github.get_pr_issue_comments(repo_name, pr_number)

        # Clone repo and checkout the PR branch
        with tempfile.TemporaryDirectory() as work_dir:
            try:
                # Clone the repo
                github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN")
                if github_token:
                    clone_url = f"https://x-access-token:{github_token}@github.com/{repo_name}.git"
                else:
                    clone_url = f"https://github.com/{repo_name}.git"
                
                subprocess.run(
                    ["git", "clone", "--branch", branch_name, "--depth", "10", clone_url, work_dir],
                    check=True, capture_output=True
                )
                
                # Run agent update
                result = asyncio.run(self._run_agent_update(
                    work_dir=work_dir,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    branch_name=branch_name,
                    issue_number=issue_number,
                    pr_title=pr.title,
                    pr_body=pr.body or "",
                    feedback=feedback,
                    review_comments=review_comments,
                    issue_comments=issue_comments
                ))
                
                return result
                
            except Exception as e:
                logger.error(f"Update failed: {e}")
                return f"❌ Failed to update PR: {str(e)}"

    async def _run_agent_update(
        self,
        work_dir: str,
        repo_name: str,
        pr_number: int,
        branch_name: str,
        issue_number: int | None,
        pr_title: str,
        pr_body: str,
        feedback: str,
        review_comments: list,
        issue_comments: list
    ) -> str:
        """Run agent to update the PR based on feedback."""
        try:
            from kimi_agent_sdk import (
                Session, ApprovalRequest, TextPart, ThinkPart,
                ToolCallPart, ToolResult
            )
        except ImportError:
            return "❌ kimi-agent-sdk not installed. This feature requires the agent-fix branch."

        # Ensure KIMI_API_KEY is set for agent-sdk
        api_key = self.setup_agent_env()
        if not api_key:
            return "❌ KIMI_API_KEY is required for /fixup command"
        
        # Set environment variables for agent-sdk (kimi-cli)

        # Track agent output
        text_parts = []
        tool_actions = []
        final_summary = ""

        # Format review comments for context
        review_context = ""
        if review_comments:
            review_context = "\n## Review Comments (inline feedback)\n"
            for c in review_comments[-10:]:  # Last 10 comments
                review_context += f"- **{c['path']}:{c['line']}** ({c['user']}): {c['body']}\n"

        # Format issue comments for context (skip bot comments)
        comment_context = ""
        if issue_comments:
            comment_context = "\n## Discussion Comments\n"
            for c in issue_comments[-5:]:  # Last 5 comments
                if "kimi" not in c['user'].lower():  # Skip bot comments
                    comment_context += f"- **{c['user']}**: {c['body'][:200]}\n"

        # Build the prompt - more focused for simple updates
        update_prompt = f"""You are a code fixing agent. Update this PR based on the feedback.

## PR #{pr_number}: {pr_title}

{review_context}

{comment_context}

## User Request

{feedback if feedback else "Please address the review comments and improve the code."}

## Instructions

1. Read ONLY the files mentioned in the feedback or review comments
2. Make the specific changes requested
3. Do NOT explore the entire codebase - focus on the requested changes only

Work in the current directory. Be efficient and make changes quickly.

After completing, provide a brief summary of what you changed.
"""

        try:
            async with await Session.create(
                work_dir=work_dir,
                model=self.AGENT_MODEL,
                yolo=True,
                max_steps_per_turn=100,
            ) as session:
                async for msg in session.prompt(update_prompt):
                    if isinstance(msg, TextPart):
                        text = msg.text
                        text_parts.append(text)
                        logger.info(f"Agent text: {text[:100]}...")
                        if "---SUMMARY---" in text or "**Changes Made**:" in text:
                            final_summary = text
                    elif isinstance(msg, ThinkPart):
                        logger.debug(f"Agent thinking: {msg.text[:100]}...")
                    elif isinstance(msg, ToolCallPart):
                        tool_name = getattr(msg, 'name', None) or getattr(msg, 'function', {}).get('name', 'unknown')
                        tool_actions.append(tool_name)
                        logger.info(f"Agent tool call: {tool_name}")
                    elif isinstance(msg, ToolResult):
                        logger.debug("Tool result received")
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")
            
            # Build agent output
            agent_output = self._build_agent_summary(text_parts, tool_actions, final_summary)

            # Check if any files were modified
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=work_dir, capture_output=True, text=True
            )
            
            if not result.stdout.strip():
                return self._format_no_update(agent_output, pr_number)

            # Get the changes
            modified_files = [
                line.split()[-1] for line in result.stdout.strip().split('\n')
                if line.strip()
            ]
            
            # Commit changes
            subprocess.run(["git", "add", "-A"], cwd=work_dir, check=True)
            commit_msg = f"fixup: address feedback on PR #{pr_number}"
            if feedback:
                commit_msg += f"\n\n{feedback[:100]}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=work_dir, check=True,
                env={**os.environ, "GIT_AUTHOR_NAME": "Kimi Bot", "GIT_AUTHOR_EMAIL": "kimi@moonshot.cn",
                     "GIT_COMMITTER_NAME": "Kimi Bot", "GIT_COMMITTER_EMAIL": "kimi@moonshot.cn"}
            )

            # Push to the same branch
            github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN")
            if github_token:
                push_url = f"https://x-access-token:{github_token}@github.com/{repo_name}.git"
                push_result = subprocess.run(
                    ["git", "push", push_url, branch_name],
                    cwd=work_dir, capture_output=True, text=True
                )
                if push_result.returncode != 0:
                    error_msg = (push_result.stderr or push_result.stdout or "Unknown error")
                    error_msg = error_msg.replace(github_token, "***")
                    logger.error(f"Git push failed: {error_msg}")
                    return f"❌ Failed to push changes: {error_msg}"
            else:
                return "❌ GITHUB_TOKEN required to push changes"

            return self._format_update_success(pr_number, modified_files, agent_output)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f"❌ Agent execution failed: {str(e)}"

    def _format_no_update(self, agent_summary: str, pr_number: int) -> str:
        """Format response when no changes were made during update."""
        return f"""### 🌗 PR Update Analysis

No changes were made to PR #{pr_number}.

**Agent Analysis:**
{agent_summary}

**Possible reasons:**
- The requested changes may already be addressed
- The feedback may need clarification
- Manual intervention may be required

{self.format_footer()}
"""

    def _format_update_success(self, pr_number: int, files: list, agent_summary: str) -> str:
        """Format success response for PR update."""
        files_list = "\n".join(f"- `{f}`" for f in files[:10])
        
        return f"""### 🌗 PR Updated!

Pushed new changes to PR #{pr_number}.

**Modified files:**
{files_list}

**Summary:**
{agent_summary}

{self.format_footer()}
"""
