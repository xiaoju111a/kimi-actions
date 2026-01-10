"""Auto-labeling tool for Kimi Actions."""

import json
import logging
import re
from typing import List

from tools.base import BaseTool

logger = logging.getLogger(__name__)

# Default labels that most repos have
DEFAULT_LABELS = [
    "bug",
    "feature",
    "enhancement",
    "documentation",
    "refactor",
    "test",
    "chore",
    "breaking-change",
    "dependencies",
    "security",
    "performance",
]


class Labels(BaseTool):
    """Auto-generate and apply labels to PR based on content."""

    @property
    def skill_name(self) -> str:
        return "labels"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Analyze PR and apply appropriate labels."""
        pr = self.github.get_pr(repo_name, pr_number)

        # Get available labels in repo
        repo_labels = self.github.get_repo_labels(repo_name)
        if not repo_labels:
            repo_labels = DEFAULT_LABELS

        # Get diff
        diff = self.github.get_pr_diff(repo_name, pr_number)
        if not diff:
            return "No changes to analyze."

        # Load skill
        skill = self.get_skill()
        system_prompt = skill.instructions if skill else self._default_prompt()

        # Build prompt
        user_prompt = f"""## PR Information
Title: {pr.title}
Branch: {pr.head.ref}

## Available Labels
{', '.join(repo_labels)}

## Code Changes
```diff
{diff[:8000]}
```

Analyze this PR and return appropriate labels as JSON:
{{"labels": ["label1", "label2"], "reason": "brief explanation"}}

Rules:
- Only use labels from the available list
- Maximum 3 labels
- Be conservative - only add labels you're confident about
"""

        # Call Kimi
        response = self.call_kimi(system_prompt, user_prompt)

        # Parse response
        labels, reason = self._parse_response(response, repo_labels)

        if not labels:
            return "## 🏷️ Kimi Labels\n\nNo labels suggested for this PR."

        # Apply labels
        try:
            self.github.add_labels(repo_name, pr_number, labels)
            applied = True
        except Exception as e:
            logger.error(f"Failed to apply labels: {e}")
            applied = False

        # Format result
        return self._format_result(labels, reason, applied)

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
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                labels = data.get("labels", [])
                reason = data.get("reason", "")

                # Filter to valid labels only
                valid = [label for label in labels if label.lower() in [v.lower() for v in valid_labels]]
                return valid[:3], reason  # Max 3 labels

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
