"""Interactive Q&A tool for Kimi Actions using Agent SDK."""

import asyncio
import logging
import tempfile

from tools.base import BaseTool, DIFF_LIMIT_ASK

logger = logging.getLogger(__name__)


class Ask(BaseTool):
    """Interactive Q&A tool for PR discussions using Agent SDK."""

    @property
    def skill_name(self) -> str:
        return "ask"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Answer a question about the PR.
        
        Args:
            repo_name: Repository name
            pr_number: PR number
            question: The question to answer (required)
            inline: If True, use compact format for inline comments
        """
        question = kwargs.get("question", "")
        inline = kwargs.get("inline", False)
        
        if not question:
            return "Please provide a question. Use `/ask <question>` format."

        pr = self.github.get_pr(repo_name, pr_number)
        self.load_context(repo_name, ref=pr.head.sha)

        compressed_diff, _, _ = self.get_diff(repo_name, pr_number)
        if not compressed_diff:
            return "Unable to get PR changes."

        # Get skill
        skill = self.get_skill()
        skill_instructions = skill.instructions if skill else "Answer questions about the PR."

        # Clone repo and run agent
        with tempfile.TemporaryDirectory() as work_dir:
            if not self.clone_repo(repo_name, work_dir, branch=pr.head.ref):
                return "❌ Failed to clone repository"
            
            try:
                response = asyncio.run(self._run_agent_ask(
                    work_dir=work_dir,
                    pr_title=pr.title,
                    pr_body=pr.body or "",
                    diff=compressed_diff,
                    question=question,
                    skill_instructions=skill_instructions
                ))

                return self._format_response(response, inline)

            except Exception as e:
                logger.error(f"Ask failed: {e}")
                return f"❌ Failed to answer question: {str(e)}"

    async def _run_agent_ask(
        self,
        work_dir: str,
        pr_title: str,
        pr_body: str,
        diff: str,
        question: str,
        skill_instructions: str
    ) -> str:
        """Run agent to answer the question."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
        except ImportError:
            return "kimi-agent-sdk not installed."

        api_key = self.setup_agent_env()
        if not api_key:
            return "KIMI_API_KEY is required."

        text_parts = []

        ask_prompt = f"""{skill_instructions}

## PR Information
Title: {pr_title}
Description: {pr_body[:2000] if pr_body else "None"}

## Code Changes
```diff
{diff[:DIFF_LIMIT_ASK]}
```

## Question
{question}

## Instructions
Answer the question above. If needed, search the codebase to find relevant information.
Be concise and helpful.
"""

        try:
            # Use auto-detected skills_dir from BaseTool
            skills_path = self.get_skills_dir()
            
            async with await Session.create(
                work_dir=work_dir,
                model=self.AGENT_MODEL,
                yolo=True,
                max_steps_per_turn=100,
                skills_dir=skills_path,
            ) as session:
                async for msg in session.prompt(ask_prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")

            if skills_path:
                logger.info(f"Ask used skills from: {skills_path}")
            return "".join(text_parts)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f"Error: {str(e)}"

    def _format_response(self, response: str, inline: bool) -> str:
        """Format the response."""
        # Clean tokenization artifacts
        response = response

        if inline:
            return f"""## 🌗 Kimi Answer

{response}

{self.format_footer()}
"""

        return f"""## 🌗 Kimi Answer

{response}

{self.format_footer("Use `/ask <question>` to continue asking")}
"""
