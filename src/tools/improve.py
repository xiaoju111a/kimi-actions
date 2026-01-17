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
        inline = kwargs.get("inline", True)
        
        pr = self.github.get_pr(repo_name, pr_number)
        self.load_context(repo_name, ref=pr.head.sha)

        compressed_diff, included_chunks, _ = self.get_diff(repo_name, pr_number)
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

                # Parse suggestions
                suggestions = self._parse_suggestions(response)
                
                # Try to post inline comments if enabled
                posted_count = 0
                if inline and suggestions:
                    summary = self._format_summary(suggestions, len(suggestions), included_chunks)
                    posted_count = self._post_inline_comments(repo_name, pr_number, suggestions, summary)
                    if posted_count > 0:
                        return ""  # Inline comments posted, no need for regular comment
                
                # Fallback to regular comment format
                summary = self._format_summary(suggestions, posted_count, included_chunks)
                return summary

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
                    
                    suggestions = self._parse_suggestions(response)
                    posted_count = 0
                    if inline and suggestions:
                        summary = self._format_summary(suggestions, len(suggestions), included_chunks)
                        posted_count = self._post_inline_comments(repo_name, pr_number, suggestions, summary)
                        if posted_count > 0:
                            return ""
                    
                    summary = self._format_summary(suggestions, posted_count, included_chunks)
                    return summary
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
3. Provide improvement suggestions with specific line numbers

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
    relevant_lines_start: 10
    relevant_lines_end: 15
```

**IMPORTANT**: Always include relevant_lines_start and relevant_lines_end to indicate the exact location of the issue.
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

    def _parse_suggestions(self, response: str) -> List[dict]:
        """Parse YAML response into suggestion dicts."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                parts = response.split("```")
                for i, part in enumerate(parts):
                    if i % 2 == 1:
                        lines = part.strip().split('\n')
                        if lines and lines[0].strip() in ['yaml', 'yml', '']:
                            yaml_content = '\n'.join(lines[1:]) if lines[0].strip() else part
                            break
                        elif 'suggestions:' in part:
                            yaml_content = part
                            break

            data = yaml.safe_load(yaml_content)
            return data.get("suggestions", []) if data else []
        except Exception as e:
            logger.warning(f"Failed to parse YAML: {e}")
            return []

    def _post_inline_comments(self, repo_name: str, pr_number: int, suggestions: List[dict], summary_body: str = "") -> int:
        """Post inline comments with GitHub suggestion format."""
        comments = []
        footer = "\n\n---\n<sub>Powered by [Kimi](https://kimi.moonshot.cn/) | Model: `kimi-k2-thinking`</sub>"
        skipped = []

        for s in suggestions:
            file_name = s.get("relevant_file", "")
            line_start = s.get("relevant_lines_start")
            line_end = s.get("relevant_lines_end")
            content = s.get("suggestion_content", "").strip()
            improved = s.get("improved_code", "").strip()

            if not file_name or not line_start:
                skipped.append(f"Missing file/line: {file_name}:{line_start}")
                continue

            # Build comment body with suggestion format
            body = f"{content}\n\n"
            if improved:
                body += "```suggestion\n"
                body += improved
                body += "\n```"
            body += footer

            comment = {
                "path": file_name,
                "line": line_end if line_end else line_start,
                "body": body,
                "side": "RIGHT"
            }
            if line_end and line_end != line_start:
                comment["start_line"] = line_start
            comments.append(comment)

        if skipped:
            logger.warning(f"Skipped {len(skipped)} suggestions: {skipped}")

        if comments:
            try:
                self.github.create_review_with_comments(
                    repo_name, pr_number, comments, body=summary_body, event="COMMENT"
                )
                return len(comments)
            except Exception as e:
                logger.error(f"Failed to post inline comments: {e}")
                return 0
        return 0

    def _format_summary(self, suggestions: List[dict], inline_count: int, included_chunks=None) -> str:
        """Format summary when inline comments are posted."""
        if not suggestions:
            return f"## 🌗 Kimi Code Suggestions\n\n✅ **Code quality is good!**\n\n{self.format_footer()}"

        lines = ["## 🌗 Kimi Code Suggestions\n"]
        
        severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions = sorted(suggestions, key=lambda x: severity_order.get(x.get("severity", "medium"), 2))

        files_reviewed = len(included_chunks) if included_chunks else len(set(s.get("relevant_file") for s in suggestions if s.get("relevant_file")))
        lines.append(f"Kimi analyzed {files_reviewed} changed files and generated {inline_count} improvement suggestions.\n")

        if suggestions:
            lines.append("**Top suggestions:**")
            for s in suggestions[:5]:
                icon = severity_icons.get(s.get("severity", "medium"), "⚪")
                file_name = s.get("relevant_file", "unknown")
                summary = s.get("one_sentence_summary", "").replace("\n", " ").strip()
                lines.append(f"- {icon} `{file_name}`: {summary}")
            if len(suggestions) > 5:
                lines.append(f"- ... and {len(suggestions) - 5} more")
            lines.append("")

        lines.append(self.format_footer(f"{len(suggestions)} suggestions"))
        return "\n".join(lines)

