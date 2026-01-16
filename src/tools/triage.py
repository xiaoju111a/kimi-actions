"""Issue triage tool using Kimi Agent SDK.

Automatically classify issues by type (bug, feature, question, docs, etc.)
and suggest appropriate labels and priority.
"""

import asyncio
import json
import logging
import os
import re
import tempfile
import subprocess
from typing import List, Dict, Optional

from tools.base import BaseTool

logger = logging.getLogger(__name__)

# Default issue type labels
ISSUE_TYPE_LABELS = [
    "bug",
    "feature",
    "enhancement",
    "question",
    "documentation",
    "help wanted",
    "good first issue",
    "wontfix",
    "duplicate",
    "invalid",
]

# Priority labels
PRIORITY_LABELS = [
    "priority: critical",
    "priority: high",
    "priority: medium",
    "priority: low",
    "P0",
    "P1",
    "P2",
    "P3",
]


class Triage(BaseTool):
    """Auto-triage issues using Agent SDK with codebase analysis."""

    @property
    def skill_name(self) -> str:
        return "triage"

    def run(
        self,
        repo_name: str,
        issue_number: int,
        apply_labels: bool = True,
        **kwargs
    ) -> str:
        """Analyze issue and suggest classification.

        Args:
            repo_name: Repository name (owner/repo)
            issue_number: Issue number
            apply_labels: Whether to automatically apply suggested labels

        Returns:
            Formatted triage result
        """
        # Get issue details
        issue = self.github.get_issue(repo_name, issue_number)
        if not issue:
            return "❌ Failed to get issue details."

        # Get available labels in repo
        repo_labels = self.github.get_repo_labels(repo_name)
        if not repo_labels:
            repo_labels = ISSUE_TYPE_LABELS + PRIORITY_LABELS

        # Load skill for prompt
        skill = self.get_skill()
        skill_instructions = skill.instructions if skill else self._default_instructions()

        logger.info(f"Triaging issue #{issue_number}: {issue.title}")

        # Clone repo and run agent
        with tempfile.TemporaryDirectory() as work_dir:
            try:
                # Clone the repo
                clone_url = f"https://github.com/{repo_name}.git"
                subprocess.run(
                    ["git", "clone", "--depth", "1", clone_url, work_dir],
                    check=True, capture_output=True
                )

                # Run agent triage
                result = asyncio.run(self._run_agent_triage(
                    work_dir=work_dir,
                    issue_title=issue.title,
                    issue_body=issue.body or "",
                    issue_author=issue.user.login,
                    repo_labels=repo_labels,
                    skill_instructions=skill_instructions
                ))

                # Parse result
                triage_result = self._parse_response(result, repo_labels)

                if not triage_result:
                    return f"## 🌗 Kimi Triage\n\n❌ Failed to analyze this issue.\n\n**Agent Response:**\n{result[:500]}"

                # Apply labels if requested
                applied = False
                if apply_labels and triage_result.get("labels"):
                    try:
                        self.github.add_issue_labels(repo_name, issue_number, triage_result["labels"])
                        applied = True
                    except Exception as e:
                        logger.error(f"Failed to apply labels: {e}")

                return self._format_result(triage_result, applied)

            except Exception as e:
                logger.error(f"Triage failed: {e}")
                return f"❌ Failed to triage issue: {str(e)}"

    async def _run_agent_triage(
        self,
        work_dir: str,
        issue_title: str,
        issue_body: str,
        issue_author: str,
        repo_labels: List[str],
        skill_instructions: str
    ) -> str:
        """Run agent to analyze the issue."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
        except ImportError:
            return '{"error": "kimi-agent-sdk not installed"}'

        # Ensure KIMI_API_KEY is set
        api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("INPUT_KIMI_API_KEY")
        if not api_key:
            return '{"error": "KIMI_API_KEY is required"}'

        os.environ["KIMI_API_KEY"] = api_key
        os.environ["KIMI_BASE_URL"] = "https://api.moonshot.cn/v1"
        os.environ["KIMI_MODEL_NAME"] = "kimi-k2-turbo-preview"

        # Collect agent output
        text_parts = []

        # Build prompt with skill instructions
        triage_prompt = f"""{skill_instructions}

---

## Issue to Triage

**Title**: {issue_title}
**Author**: @{issue_author}

**Body**:
{issue_body[:4000]}

## Available Labels
{', '.join(repo_labels)}

## Instructions

1. Read the issue carefully
2. If the issue mentions specific files, functions, or components, search the codebase to verify they exist
3. Based on your analysis, classify the issue

Return your analysis as JSON:
```json
{{
    "type": "bug|feature|enhancement|question|documentation|other",
    "priority": "critical|high|medium|low",
    "labels": ["label1", "label2"],
    "confidence": "high|medium|low",
    "summary": "One-line summary",
    "reason": "Brief explanation",
    "related_files": ["file1.py", "file2.js"]
}}
```

Rules:
- Only use labels from the available list
- Maximum 4 labels
- Be conservative - only add labels you're confident about
- Search the codebase if the issue mentions specific code
"""

        try:
            async with await Session.create(
                work_dir=work_dir,
                model="kimi-k2-turbo-preview",
                yolo=True,
                max_steps_per_turn=50,  # Triage shouldn't need many steps
            ) as session:
                async for msg in session.prompt(triage_prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                        logger.info(f"Agent: {msg.text[:100]}...")
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")

            return " ".join(text_parts)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f'{{"error": "{str(e)}"}}'

    def _default_instructions(self) -> str:
        """Default triage instructions if no skill loaded."""
        return """You are an expert issue triage assistant.

## Issue Type Classification
- **bug**: Something isn't working - errors, crashes, incorrect behavior
- **feature**: Request for new functionality
- **enhancement**: Improvement to existing functionality
- **question**: User asking for help or clarification
- **documentation**: Documentation improvements

## Priority Assessment
- **critical**: System down, security vulnerability, data loss
- **high**: Major feature broken, significant user impact
- **medium**: Important but not urgent, workarounds exist
- **low**: Minor issues, nice-to-have improvements

Be conservative with labels. Only suggest labels you're confident about."""

    def _parse_response(self, response: str, valid_labels: List[str]) -> Optional[Dict]:
        """Parse JSON response and validate labels."""
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{[^{}]*"type"[^{}]*\}', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)

            if json_match:
                json_str = json_match.group(1) if '```' in response else json_match.group()
                data = json.loads(json_str)

                # Validate and filter labels
                suggested_labels = data.get("labels", [])
                valid = []

                valid_labels_lower = {v.lower(): v for v in valid_labels}
                for label in suggested_labels:
                    label_lower = label.lower()
                    if label_lower in valid_labels_lower:
                        valid.append(valid_labels_lower[label_lower])

                data["labels"] = valid[:4]
                return data

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse triage response: {e}")

        return None

    def _format_result(self, result: Dict, applied: bool) -> str:
        """Format the triage result message."""
        lines = ["## 🌗 Kimi Issue Triage\n"]

        issue_type = result.get("type", "unknown")
        priority = result.get("priority", "medium")
        confidence = result.get("confidence", "medium")

        type_emoji = {
            "bug": "🐛",
            "feature": "✨",
            "enhancement": "💡",
            "question": "❓",
            "documentation": "📚",
            "other": "📋"
        }

        priority_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }

        lines.append("### Classification\n")
        lines.append("| Attribute | Value |")
        lines.append("|-----------|-------|")
        lines.append(f"| **Type** | {type_emoji.get(issue_type, '📋')} `{issue_type}` |")
        lines.append(f"| **Priority** | {priority_emoji.get(priority, '🟡')} `{priority}` |")
        lines.append(f"| **Confidence** | `{confidence}` |")
        lines.append("")

        summary = result.get("summary", "")
        if summary:
            lines.append(f"### Summary\n{summary}\n")

        labels = result.get("labels", [])
        if labels:
            if applied:
                lines.append("### Labels Applied ✅\n")
            else:
                lines.append("### Suggested Labels\n")
            lines.append(" ".join([f"`{label}`" for label in labels]))
            lines.append("")

        reason = result.get("reason", "")
        if reason:
            lines.append(f"### Analysis\n{reason}\n")

        related_files = result.get("related_files", [])
        if related_files:
            lines.append("<details>")
            lines.append(f"<summary><strong>📁 Related Files</strong> ({len(related_files[:8])} files)</summary>")
            lines.append("")
            for f in related_files[:8]:
                lines.append(f"- `{f}`")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        lines.append(self._get_recommendations(issue_type, priority))
        lines.append(self.format_footer())
        return "\n".join(lines)

    def _get_recommendations(self, issue_type: str, priority: str) -> str:
        """Get actionable recommendations based on classification."""
        recs = ["### Recommendations\n"]

        if issue_type == "bug":
            recs.append("- [ ] Verify the bug can be reproduced")
            recs.append("- [ ] Check for related issues")
            if priority in ["critical", "high"]:
                recs.append("- [ ] **Prioritize** - This appears to be a high-impact bug")
        elif issue_type in ["feature", "enhancement"]:
            recs.append("- [ ] Evaluate feature fit with project roadmap")
            recs.append("- [ ] Gather community feedback")
        elif issue_type == "question":
            recs.append("- [ ] Check if answered in documentation")
            recs.append("- [ ] May be closeable after answering")
        elif issue_type == "documentation":
            recs.append("- [ ] Good candidate for community contribution")
            recs.append("- [ ] Consider adding `good first issue` label")
        else:
            recs.append("- [ ] Review and categorize appropriately")

        recs.append("")
        return "\n".join(recs)
