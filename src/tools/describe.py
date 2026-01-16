"""PR description generation tool for Kimi Actions using Agent SDK."""

import asyncio
import logging
import os
import re
import yaml
from typing import List, Tuple

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class Describe(BaseTool):
    """PR description generation tool using Agent SDK."""

    @property
    def skill_name(self) -> str:
        return "describe"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> Tuple[str, str]:
        """Generate PR description."""
        update_pr = kwargs.get("update_pr", True)

        pr = self.github.get_pr(repo_name, pr_number)
        self.load_context(repo_name, ref=pr.head.sha)

        compressed_diff, _, _ = self.get_diff(repo_name, pr_number)
        if not compressed_diff:
            return pr.title, "No changes detected."

        skill = self.get_skill()
        skill_instructions = skill.instructions if skill else "Generate a PR description."

        commits = list(pr.get_commits())
        commit_messages = "\n".join([f"- {c.commit.message.split(chr(10))[0]}" for c in commits[:10]])

        response = asyncio.run(self._run_agent_describe(
            skill_instructions=skill_instructions,
            pr_title=pr.title,
            pr_branch=f"{pr.head.ref} -> {pr.base.ref}",
            commit_messages=commit_messages,
            diff=compressed_diff
        ))

        title, body, labels = self._parse_response(response, pr.title)

        if update_pr and self.config.describe.generate_title:
            try:
                pr.edit(title=title, body=body)
                if labels and self.config.describe.generate_labels:
                    pr.set_labels(*labels)
            except Exception as e:
                logger.warning(f"Could not update PR: {e}")

        return title, body

    async def _run_agent_describe(
        self, skill_instructions: str, pr_title: str, pr_branch: str,
        commit_messages: str, diff: str
    ) -> str:
        """Run agent to generate PR description (no git clone needed)."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
        except ImportError:
            return f'```yaml\ntitle: "{pr_title}"\ndescription: "kimi-agent-sdk not installed"\n```'

        api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("INPUT_KIMI_API_KEY")
        if not api_key:
            return f'```yaml\ntitle: "{pr_title}"\ndescription: "KIMI_API_KEY required"\n```'

        os.environ["KIMI_API_KEY"] = api_key
        os.environ["KIMI_BASE_URL"] = "https://api.moonshot.cn/v1"
        os.environ["KIMI_MODEL_NAME"] = "kimi-k2-turbo-preview"

        text_parts = []
        describe_prompt = f"""{skill_instructions}

## PR Information
Original Title: {pr_title}
Branch: {pr_branch}

## Commit History
{commit_messages}

## Code Changes
```diff
{diff[:12000]}
```

Please generate PR description in YAML format:
```yaml
title: "concise PR title"
type: "feature|bug_fix|refactor|docs|test|chore"
description: "detailed description"
labels:
  - label1
  - label2
files:
  - filename: "path/to/file"
    change_type: "added|modified|deleted"
    summary: "what changed"
```
"""

        try:
            async with await Session.create(
                work_dir="/tmp",
                model="kimi-k2-turbo-preview",
                yolo=True,
                max_steps_per_turn=100,
            ) as session:
                async for msg in session.prompt(describe_prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")
            return self._clean_tokenization("".join(text_parts))
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f'```yaml\ntitle: "{pr_title}"\ndescription: "Error: {str(e)}"\n```'

    def _clean_tokenization(self, text: str) -> str:
        """Clean up tokenization artifacts."""
        if not text:
            return text
        text = re.sub(r'\s+([.,;:!?)])', r'\1', text)
        text = re.sub(r'([(])\s+', r'\1', text)
        text = re.sub(r'\s+/', '/', text)
        text = re.sub(r'/\s+', '/', text)
        text = re.sub(r'\s+_', '_', text)
        text = re.sub(r'_\s+', '_', text)
        text = re.sub(r'\s+\.py', '.py', text)
        text = re.sub(r'\s{2,}', ' ', text)
        return text.strip()

    def _parse_response(self, response: str, default_title: str) -> Tuple[str, str, List[str]]:
        """Parse YAML response."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]

            data = yaml.safe_load(yaml_content)

            title = self._clean_tokenization(data.get("title", default_title).strip())
            pr_type = data.get("type", "")
            labels = data.get("labels", [])
            description = self._clean_tokenization(data.get("description", "").strip())
            files = data.get("files", [])

            body_parts = []
            type_emojis = {"feature": "✨", "bug_fix": "🐛", "refactor": "♻️", "docs": "📝", "test": "🧪", "chore": "🔧"}
            if pr_type:
                emoji = type_emojis.get(pr_type, "📦")
                body_parts.append(f"## {emoji} {pr_type.replace('_', ' ').title()}\n")

            if description:
                body_parts.append(f"{description}\n")

            if files and self.config.describe.enable_walkthrough:
                body_parts.append("## 📁 Changed Files\n| File | Type | Summary |\n|------|------|---------|")
                change_icons = {"added": "➕", "modified": "📝", "deleted": "🗑️", "renamed": "📛"}
                for f in files:
                    icon = change_icons.get(f.get("change_type", ""), "📄")
                    filename = self._clean_tokenization(f.get('filename', ''))
                    summary = self._clean_tokenization(f.get('summary', ''))
                    body_parts.append(f"| `{filename}` | {icon} | {summary} |")
                body_parts.append("")

            body_parts.append(self.format_footer())
            return title, "\n".join(body_parts), labels

        except Exception:
            return default_title, self._clean_tokenization(response), []

    def generate_comment(self, repo_name: str, pr_number: int) -> str:
        """Generate description as a comment."""
        title, body = self.run(repo_name, pr_number, update_pr=False)
        return f"## 🌗 Kimi PR Description\n\n### Suggested Title\n{title}\n\n### Suggested Description\n{body}"
