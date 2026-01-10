"""Interactive Q&A tool for Kimi Actions."""

from tools.base import BaseTool


class Ask(BaseTool):
    """Interactive Q&A tool for PR discussions."""

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
        system_prompt = skill.instructions if skill else "Answer questions about the PR."

        user_prompt = f"""## PR Information
Title: {pr.title}
Description: {pr.body or "None"}

## Code Changes
```diff
{compressed_diff}
```

## Question
{question}

Please answer the question above."""

        response = self.call_kimi(system_prompt, user_prompt)

        # Compact format for inline comments (GitHub UI already shows code context)
        if inline:
            return f"""## 🤖 Kimi Answer

{response}

{self.format_footer()}
"""

        # Full format for regular comments
        return f"""## 🤖 Kimi Answer

{response}

{self.format_footer("Use `/ask <question>` to continue asking")}
"""
