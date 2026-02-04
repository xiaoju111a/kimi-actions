"""Code review tool for Kimi Actions.

Uses Agent SDK with Skill-based architecture.
"""

import asyncio
import logging
import tempfile

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class Reviewer(BaseTool):
    """Code review tool using Agent SDK with Skill-based architecture."""

    @property
    def skill_name(self) -> str:
        return "code-review"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Run code review on a PR.

        Automatically detects if incremental review should be used based on:
        - Existence of previous review
        - Age of previous review (<7 days)
        - Presence of new commits
        """
        command_quote = kwargs.get("command_quote", "")

        pr = self.github.get_pr(repo_name, pr_number)
        self.load_context(repo_name, ref=pr.head.sha)

        # Check if there are new changes since last review
        last_review = self.github.get_last_bot_comment(repo_name, pr_number)
        if last_review:
            last_sha = last_review.get("sha")
            if last_sha == pr.head.sha:
                return "✅ No new changes since last review."

        # Get full diff - Agent SDK handles everything
        diff = self.github.get_pr_diff(repo_name, pr_number)

        if not diff:
            return "No changes to review."

        skill = self.get_skill()
        if not skill:
            return f"Error: {self.skill_name} skill not found."

        system_prompt = self._build_system_prompt(skill)

        with tempfile.TemporaryDirectory() as work_dir:
            logger.info(f"Cloning repository {repo_name} (branch: {pr.head.ref}) to {work_dir}")
            if not self.clone_repo(repo_name, work_dir, branch=pr.head.ref):
                return f"### 🌗 Pull request overview\n\n❌ Failed to clone repository\n\n{self.format_footer()}"
            
            logger.info("Repository cloned successfully, starting agent review")
            try:
                # Run agent review - it will return Markdown directly
                response = asyncio.run(
                    self._run_agent_review(
                        work_dir=work_dir,
                        system_prompt=system_prompt,
                        pr_title=pr.title,
                        pr_branch=f"{pr.head.ref} -> {pr.base.ref}",
                        diff=diff,
                        current_sha=pr.head.sha,
                        command_quote=command_quote,
                    )
                )
            except Exception as e:
                logger.error(f"Review failed: {e}")
                return f"### 🌗 Pull request overview\n\n❌ {str(e)}\n\n{self.format_footer()}"

        # Add footer and return the Markdown response directly
        if not response.strip():
            response = "### 🌗 Pull request overview\n\n✅ No issues found! The code looks good."
        
        # Add footer if not already present
        if self.format_footer() not in response:
            response = f"{response}\n\n{self.format_footer()}"
        
        # Add SHA marker to track last reviewed commit
        if pr.head.sha:
            response = f"{response}\n\n<!-- kimi-review:sha={pr.head.sha[:12]} -->"
        
        return response

    async def _run_agent_review(
        self,
        work_dir: str,
        system_prompt: str,
        pr_title: str,
        pr_branch: str,
        diff: str,
        current_sha: str,
        command_quote: str = "",
    ) -> str:
        """Run agent to perform code review and return Markdown directly."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
            from kaos.path import KaosPath
        except ImportError:
            return "### 🌗 Pull request overview\n\n❌ kimi-agent-sdk not installed"

        api_key = self.setup_agent_env()
        if not api_key:
            return "### 🌗 Pull request overview\n\n❌ KIMI_API_KEY is required"
        
        review_prompt = f"""{system_prompt}

## PR Information
- **Title**: {pr_title}
- **Branch**: {pr_branch}

## Code Changes
```diff
{diff}
```

## Your Task

Review the code changes above and provide feedback in Markdown format.

**CRITICAL REQUIREMENTS**:
1. Start IMMEDIATELY with `## 🌗 Pull Request Overview` - NO thinking or commentary
2. Include the file summary table with ALL files from the diff
3. Provide a SPECIFIC description for EVERY file - never write "Modified (not shown in diff)"
4. Use this exact text: "Kimi performed full review on X changed files and found Y issues."
5. For each issue, provide specific line numbers and code examples
6. Put code fixes in collapsible `<details>` sections

Follow the format shown in the instructions above.
"""

        try:
            text_parts = []
            skills_path = self.get_skills_dir()

            # Convert work_dir string to KaosPath for Agent SDK
            work_dir_kaos = KaosPath(work_dir) if work_dir else KaosPath.cwd()
            skills_dir_kaos = KaosPath(skills_path) if skills_path else None

            async with await Session.create(
                work_dir=work_dir_kaos,
                model=self.AGENT_MODEL,
                yolo=True,
                max_steps_per_turn=50,
                skills_dir=skills_dir_kaos,
            ) as session:
                async for msg in session.prompt(review_prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")

            if skills_path:
                logger.info(f"Review used skills from: {skills_path}")
            
            return "".join(text_parts)
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f"### 🌗 Pull request overview\n\n❌ Error: {str(e)}"

    def _build_system_prompt(self, skill) -> str:
        """Build system prompt from skill and context.

        Note: Agent SDK will automatically call skill scripts when needed,
        so we don't need to run them manually and include output in prompt.
        """
        parts = [skill.instructions]
        level_text = {
            "strict": """Review Level: Strict - Perform thorough analysis including:
- Thread safety and race condition detection
- Stub/mock/simulation code detection
- Error handling completeness
- Cache key collision detection
- All items in the Strict Mode Checklist""",
            "normal": "Review Level: Normal - Focus on functional issues and common bugs",
            "gentle": "Review Level: Gentle - Only flag critical issues that would break functionality",
        }
        parts.append(
            f"\n## {level_text.get(self.config.review_level, level_text['normal'])}"
        )
        if self.config.review.extra_instructions:
            parts.append(
                f"\n## Extra Instructions\n{self.config.review.extra_instructions}"
            )
        return "\n".join(parts)
