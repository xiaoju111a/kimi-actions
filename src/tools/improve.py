"""Code improvement suggestions tool for Kimi Actions."""

import yaml
from typing import List

from tools.base import BaseTool


class Improve(BaseTool):
    """Code improvement suggestions tool."""

    @property
    def skill_name(self) -> str:
        return "improve"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Generate code improvement suggestions."""
        pr = self.github.get_pr(repo_name, pr_number)
        self.load_context(repo_name, ref=pr.head.sha)

        compressed_diff, _, _ = self.get_diff(repo_name, pr_number)
        if not compressed_diff:
            return "No changes to improve."

        # Get skill
        skill = self.get_skill()
        system_prompt = skill.instructions if skill else "Provide code improvement suggestions."
        system_prompt += f"\n\n最多提供 {self.config.improve.num_suggestions} 个建议。"

        user_prompt = f"""## Code Changes
```diff
{compressed_diff}
```

Please provide code improvement suggestions."""

        response = self.call_kimi(system_prompt, user_prompt)
        return self._format_suggestions(response)

    def _format_suggestions(self, response: str) -> str:
        """Format suggestions as markdown."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]

            data = yaml.safe_load(yaml_content)
            suggestions = data.get("suggestions", [])

            if not suggestions:
                return f"## 🌗 Kimi Code Suggestions\n\n✅ **Code quality is good!**\n\n{self.format_footer()}"

            return self._format_structured(suggestions)

        except Exception:
            return f"## 🌗 Kimi Code Suggestions\n\n{response}\n\n{self.format_footer()}"

    def _format_structured(self, suggestions: List[dict]) -> str:
        """Format structured suggestions."""
        lines = ["## 🌗 Kimi Code Suggestions\n"]

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions = sorted(suggestions, key=lambda x: severity_order.get(x.get("severity", "medium"), 2))

        severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}

        lines.append("| # | File | Severity |\n|---|------|----------|")
        for i, s in enumerate(suggestions, 1):
            sev = s.get("severity", "medium")
            lines.append(f"| {i} | `{s.get('relevant_file', '')}` | {severity_icons.get(sev, '⚪')} {sev} |")

        lines.append("\n---\n")

        for i, s in enumerate(suggestions, 1):
            summary = s.get("one_sentence_summary", "")
            content = s.get("suggestion_content", "").strip()
            existing = s.get("existing_code", "").strip()
            improved = s.get("improved_code", "").strip()
            language = s.get("language", "")

            lines.append(f"### Suggestion {i}: {summary}\n")
            lines.append(f"{content}\n")

            if existing:
                lines.append("<details>\n<summary>View code comparison</summary>\n")
                lines.append(f"**Current code:**\n```{language}\n{existing}\n```\n")
                if improved:
                    lines.append(f"**Suggested:**\n```{language}\n{improved}\n```")
                lines.append("</details>\n")

        lines.append(self.format_footer(f"{len(suggestions)} suggestions"))
        return "\n".join(lines)
