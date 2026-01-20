"""Auto-labeling tool for Kimi Actions using Agent SDK."""

import asyncio
import json
import logging

import re
from typing import List

from tools.base import BaseTool, DIFF_LIMIT_ASK

logger = logging.getLogger(__name__)

DEFAULT_LABELS = [
    "bug", "feature", "enhancement", "documentation", "refactor",
    "test", "chore", "breaking-change", "dependencies", "security", "performance",
]


class Labels(BaseTool):
    """Auto-generate and apply labels to PR using Agent SDK."""

    @property
    def skill_name(self) -> str:
        return "labels"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Analyze PR and apply appropriate labels."""
        pr = self.github.get_pr(repo_name, pr_number)

        repo_labels = self.github.get_repo_labels(repo_name)
        if not repo_labels:
            repo_labels = DEFAULT_LABELS

        diff = self.github.get_pr_diff(repo_name, pr_number)
        if not diff:
            return "No changes to analyze."

        skill = self.get_skill()
        skill_instructions = skill.instructions if skill else self._default_prompt()

        response = asyncio.run(self._run_agent_labels(
            skill_instructions=skill_instructions,
            pr_title=pr.title,
            pr_branch=pr.head.ref,
            repo_labels=repo_labels,
            diff=diff
        ))

        labels, reason = self._parse_response(response, repo_labels)

        if not labels:
            return "## 🏷️ Kimi Labels\n\nNo labels suggested for this PR."

        try:
            self.github.add_labels(repo_name, pr_number, labels)
            applied = True
        except Exception as e:
            logger.error(f"Failed to apply labels: {e}")
            applied = False

        return self._format_result(labels, reason, applied)

    async def _run_agent_labels(
        self, skill_instructions: str, pr_title: str, pr_branch: str,
        repo_labels: List[str], diff: str
    ) -> str:
        """Run agent to suggest labels (no git clone needed)."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
            from kaos.path import KaosPath
        except ImportError:
            return '{"labels": [], "reason": "kimi-agent-sdk not installed"}'

        api_key = self.setup_agent_env()
        if not api_key:
            return '{"labels": [], "reason": "KIMI_API_KEY required"}'

        text_parts = []
        labels_prompt = f"""{skill_instructions}

## PR Information
Title: {pr_title}
Branch: {pr_branch}

## Available Labels
{', '.join(repo_labels)}

## Code Changes
```diff
{diff[:DIFF_LIMIT_ASK]}
```

Analyze this PR and return appropriate labels as JSON:
{{"labels": ["label1", "label2"], "reason": "brief explanation"}}

Rules:
- Only use labels from the available list
- Maximum 3 labels
- Be conservative - only add labels you're confident about
"""

        try:
            # Use auto-detected skills_dir from BaseTool
            skills_path = self.get_skills_dir()
            
            # Convert to KaosPath for Agent SDK
            work_dir_kaos = KaosPath("/tmp")
            skills_dir_kaos = KaosPath(str(skills_path)) if skills_path else None
            
            async with await Session.create(
                work_dir=work_dir_kaos,
                model=self.AGENT_MODEL,
                yolo=True,
                max_steps_per_turn=100,
                skills_dir=skills_dir_kaos,
            ) as session:
                async for msg in session.prompt(labels_prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")
            
            if skills_path:
                logger.info(f"Labels used skills from: {skills_path}")
            return "".join(text_parts)
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f'{{"labels": [], "reason": "Error: {str(e)}"}}'

    def _default_prompt(self) -> str:
        return """You are a PR labeling assistant. Analyze the PR and suggest appropriate labels.

Label categories:
- bug: Bug fixes
- feature/enhancement: New features
- documentation: Doc changes only
- refactor: Code restructuring without behavior change
- test: Test additions/changes
- chore: Build, config, tooling changes
- breaking-change: Breaking API changes
- dependencies: Dependency updates
- security: Security fixes
- performance: Performance improvements

Be conservative. Only suggest labels you're confident about."""

    def _parse_response(self, response: str, valid_labels: List[str]) -> tuple:
        """Parse JSON response and validate labels."""
        try:
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                labels = data.get("labels", [])
                reason = data.get("reason", "")
                valid = [label for label in labels if label.lower() in [v.lower() for v in valid_labels]]
                return valid[:3], reason
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse labels response: {e}")
        return [], ""

    def _format_result(self, labels: List[str], reason: str, applied: bool) -> str:
        """Format the result message."""
        lines = ["## 🏷️ Kimi Labels\n"]
        if applied:
            lines.append(f"✅ Applied labels: {', '.join(f'`{label}`' for label in labels)}\n")
        else:
            lines.append(f"⚠️ Suggested labels: {', '.join(f'`{label}`' for label in labels)}\n")
            lines.append("(Failed to apply automatically)\n")
        if reason:
            lines.append(f"**Reason**: {reason}\n")
        lines.append(self.format_footer())
        return "\n".join(lines)
