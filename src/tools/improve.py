"""Code improvement suggestions tool using Agent SDK."""

import asyncio
import logging

import subprocess
import tempfile
import yaml
from typing import List

from tools.base import BaseTool, DIFF_LIMIT_IMPROVE

logger = logging.getLogger(__name__)


class Improve(BaseTool):
    """Code improvement suggestions tool using Agent SDK."""

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
        skill_instructions = skill.instructions if skill else "Provide code improvement suggestions."

        # Clone repo and run agent
        with tempfile.TemporaryDirectory() as work_dir:
            try:
                clone_url = f"https://github.com/{repo_name}.git"
                subprocess.run(
                    ["git", "clone", "--depth", "1", "-b", pr.head.ref, clone_url, work_dir],
                    check=True, capture_output=True
                )

                response = asyncio.run(self._run_agent_improve(
                    work_dir=work_dir,
                    diff=compressed_diff,
                    skill_instructions=skill_instructions,
                    num_suggestions=self.config.improve.num_suggestions
                ))

                return self._format_suggestions(response)

            except subprocess.CalledProcessError:
                # Fallback: clone default branch
                try:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", clone_url, work_dir],
                        check=True, capture_output=True
                    )
                    response = asyncio.run(self._run_agent_improve(
                        work_dir=work_dir,
                        diff=compressed_diff,
                        skill_instructions=skill_instructions,
                        num_suggestions=self.config.improve.num_suggestions
                    ))
                    return self._format_suggestions(response)
                except Exception as e:
                    logger.error(f"Improve failed: {e}")
                    return f"❌ Failed to generate suggestions: {str(e)}"
            except Exception as e:
                logger.error(f"Improve failed: {e}")
                return f"❌ Failed to generate suggestions: {str(e)}"

    async def _run_agent_improve(
        self,
        work_dir: str,
        diff: str,
        skill_instructions: str,
        num_suggestions: int
    ) -> str:
        """Run agent to generate improvement suggestions."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
        except ImportError:
            return '{"suggestions": []}'

        api_key = self.setup_agent_env()
        if not api_key:
            return '{"suggestions": []}'


        text_parts = []

        improve_prompt = f"""{skill_instructions}

最多提供 {num_suggestions} 个建议。

## Code Changes
```diff
{diff[:DIFF_LIMIT_IMPROVE]}
```

## Instructions
1. Analyze the code changes
2. If needed, read related files to understand context
3. Provide improvement suggestions

Return suggestions in YAML format:
```yaml
suggestions:
  - relevant_file: "path/to/file.py"
    language: "python"
    severity: "medium"
    one_sentence_summary: "Brief summary"
    suggestion_content: "Detailed suggestion"
    existing_code: "current code"
    improved_code: "suggested code"
```
"""

        try:
            async with await Session.create(
                work_dir=work_dir,
                model=self.AGENT_MODEL,
                yolo=True,
                max_steps_per_turn=100,
            ) as session:
                async for msg in session.prompt(improve_prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")

            return "".join(text_parts)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return '{"suggestions": []}'

    def _format_suggestions(self, response: str) -> str:
        """Format suggestions as markdown."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                # Find the first code block that looks like YAML
                parts = response.split("```")
                for i, part in enumerate(parts):
                    if i % 2 == 1:  # Odd indices are code blocks
                        # Skip language identifier if present
                        lines = part.strip().split('\n')
                        if lines and lines[0].strip() in ['yaml', 'yml', '']:
                            yaml_content = '\n'.join(lines[1:]) if lines[0].strip() else part
                            break
                        elif 'suggestions:' in part:
                            yaml_content = part
                            break

            data = yaml.safe_load(yaml_content)
            suggestions = data.get("suggestions", [])

            if not suggestions:
                return f"## 🌗 Kimi Code Suggestions\n\n✅ **Code quality is good!**\n\n{self.format_footer()}"

            return self._format_structured(suggestions)

        except Exception as e:
            logger.warning(f"Failed to parse YAML: {e}")
            # Try to extract suggestions from raw response
            if "suggestions:" in response:
                # Find YAML-like content
                start = response.find("suggestions:")
                yaml_like = response[start:]
                try:
                    data = yaml.safe_load(yaml_like)
                    if data and "suggestions" in data:
                        return self._format_structured(data["suggestions"])
                except Exception:
                    pass
            
            # Return raw response with header
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
            file_name = s.get('relevant_file', '')
            lines.append(f"| {i} | `{file_name}` | {severity_icons.get(sev, '⚪')} {sev} |")

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
