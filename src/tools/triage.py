"""Issue triage tool for Kimi Actions.

Automatically classify issues by type (bug, feature, question, docs, etc.)
and suggest appropriate labels and priority.
"""

import json
import logging
import re
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

# Area/component labels (common patterns)
AREA_LABELS = [
    "area: api",
    "area: ui",
    "area: docs",
    "area: testing",
    "area: build",
    "area: security",
    "area: performance",
]


class Triage(BaseTool):
    """Auto-triage issues by classifying type and suggesting labels/priority."""

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

        # Load skill and context
        self.load_context(repo_name)
        skill = self.get_skill()
        system_prompt = skill.instructions if skill else self._default_prompt()

        # Run codebase scan if script available
        code_context = ""
        if skill and "scan_codebase" in skill.scripts:
            scan_result = skill.run_script(
                "scan_codebase",
                title=issue.title,
                body=issue.body or "",
                repo_path=".",
                max_files=5,
                max_snippets=3
            )
            if scan_result:
                code_context = self._format_scan_result(scan_result)

        # Build user prompt
        user_prompt = self._build_prompt(issue, repo_labels, code_context)

        # Call Kimi
        response = self.call_kimi(system_prompt, user_prompt)

        # Parse response
        triage_result = self._parse_response(response, repo_labels)

        if not triage_result:
            return "## 🏷️ Kimi Triage\n\n❌ Failed to analyze this issue."

        # Apply labels if requested
        applied = False
        if apply_labels and triage_result.get("labels"):
            try:
                self.github.add_issue_labels(repo_name, issue_number, triage_result["labels"])
                applied = True
            except Exception as e:
                logger.error(f"Failed to apply labels: {e}")

        # Format result
        return self._format_result(triage_result, applied)

    def _default_prompt(self) -> str:
        return """You are an expert issue triage assistant for open source projects.

Your job is to:
1. Classify the issue type (bug, feature, question, docs, etc.)
2. Assess priority based on impact and urgency
3. Suggest appropriate labels from the available list
4. Provide a brief analysis

## Classification Guidelines

### Issue Types
- **bug**: Something isn't working as expected, errors, crashes, incorrect behavior
- **feature**: Request for new functionality that doesn't exist
- **enhancement**: Improvement to existing functionality
- **question**: User asking for help or clarification
- **documentation**: Documentation improvements or corrections
- **help wanted**: Issue needs community contribution
- **good first issue**: Suitable for newcomers

### Priority Assessment
- **P0/Critical**: System down, security vulnerability, data loss
- **P1/High**: Major feature broken, significant user impact
- **P2/Medium**: Important but not urgent, workarounds exist
- **P3/Low**: Minor issues, nice-to-have improvements

### Signals to Look For
- Bug: "error", "crash", "not working", "broken", "fails", stack traces
- Feature: "would be nice", "add support", "implement", "new feature"
- Question: "how to", "is it possible", "can I", "help", question marks
- Docs: "documentation", "readme", "example", "typo in docs"

Be conservative with labels. Only suggest labels you're confident about."""

    def _format_scan_result(self, scan_result: str) -> str:
        """Format codebase scan result for prompt."""
        try:
            data = json.loads(scan_result)

            parts = []

            # Summary
            summary = data.get("summary", "")
            if summary:
                parts.append(f"**Scan Summary**: {summary}")

            # Keywords found
            keywords = data.get("keywords", [])
            if keywords:
                parts.append(f"**Keywords extracted**: {', '.join(keywords[:8])}")

            # Ranked files (new format - aggregated and scored)
            ranked_files = data.get("ranked_files", [])
            if ranked_files:
                file_list = []
                for f in ranked_files[:8]:
                    keywords_str = ', '.join(f.get('keywords', [])[:3])
                    file_list.append(f"- `{f['file']}` (matches: {keywords_str})")
                parts.append("**Related files (ranked by relevance)**:\n" + "\n".join(file_list))
            else:
                # Fallback to old format
                files = data.get("files", {})
                if files:
                    file_list = []
                    seen = set()
                    for kw, matches in list(files.items())[:5]:
                        for m in matches[:3]:
                            if m['file'] not in seen:
                                file_list.append(f"- `{m['file']}` (keyword: {kw})")
                                seen.add(m['file'])
                    if file_list:
                        parts.append("**Related files**:\n" + "\n".join(file_list[:8]))

            # Code snippets
            snippets = data.get("snippets", [])
            if snippets:
                snippet_parts = []
                for s in snippets[:2]:
                    snippet_parts.append(f"**{s['file']}** (keyword: `{s['keyword']}`):\n```\n{s['code']}\n```")
                if snippet_parts:
                    parts.append("**Code snippets**:\n" + "\n\n".join(snippet_parts))

            return "\n\n".join(parts) if parts else ""

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse scan result: {e}")
            return ""

    def _build_prompt(self, issue, repo_labels: List[str], code_context: str = "") -> str:
        """Build the user prompt with issue details."""
        # Get issue body, truncate if too long
        body = issue.body or "(No description provided)"
        if len(body) > 6000:
            body = body[:6000] + "\n...(truncated)"

        # Get existing labels
        existing_labels = [label.name for label in issue.labels]

        # Get comments count and first few comments if any
        comments_info = ""
        if issue.comments > 0:
            try:
                comments = list(issue.get_comments())[:3]
                comments_text = "\n".join([
                    f"- @{c.user.login}: {c.body[:200]}..." if len(c.body) > 200 else f"- @{c.user.login}: {c.body}"
                    for c in comments
                ])
                comments_info = f"\n## Recent Comments ({issue.comments} total)\n{comments_text}"
            except Exception:
                pass

        # Add code context section if available
        code_section = ""
        if code_context:
            code_section = f"\n## Codebase Analysis\n{code_context}\n"

        return f"""## Issue Information
**Title**: {issue.title}
**Author**: @{issue.user.login}
**Created**: {issue.created_at}
**State**: {issue.state}
**Existing Labels**: {', '.join(existing_labels) if existing_labels else 'None'}
**Comments**: {issue.comments}

## Issue Body
{body}
{comments_info}
{code_section}
## Available Labels in Repository
{', '.join(repo_labels)}

---

Analyze this issue and return a JSON response with your classification:
```json
{{
    "type": "bug|feature|enhancement|question|documentation|other",
    "priority": "critical|high|medium|low",
    "labels": ["label1", "label2"],
    "confidence": "high|medium|low",
    "summary": "Brief one-line summary of the issue",
    "reason": "Brief explanation of your classification",
    "related_files": ["file1.py", "file2.js"]
}}
```

Rules:
- Only use labels from the available list
- Maximum 4 labels total (including type and priority if they exist as labels)
- Be conservative - only add labels you're confident about
- If the issue is unclear or needs more info, note that in the reason
- Include related_files if codebase analysis found relevant files"""

    def _parse_response(self, response: str, valid_labels: List[str]) -> Optional[Dict]:
        """Parse JSON response and validate labels."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                # Try to find JSON with nested braces
                json_match = re.search(r'\{.*\}', response, re.DOTALL)

            if json_match:
                data = json.loads(json_match.group())

                # Validate and filter labels
                suggested_labels = data.get("labels", [])
                valid = []

                # Case-insensitive matching
                valid_labels_lower = {v.lower(): v for v in valid_labels}
                for label in suggested_labels:
                    label_lower = label.lower()
                    if label_lower in valid_labels_lower:
                        valid.append(valid_labels_lower[label_lower])

                data["labels"] = valid[:4]  # Max 4 labels
                return data

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse triage response: {e}")

        return None

    def _format_result(self, result: Dict, applied: bool) -> str:
        """Format the triage result message."""
        lines = ["## 🌗 Kimi Issue Triage\n"]

        # Type and Priority
        issue_type = result.get("type", "unknown")
        priority = result.get("priority", "medium")
        confidence = result.get("confidence", "medium")

        # Type emoji mapping
        type_emoji = {
            "bug": "🐛",
            "feature": "✨",
            "enhancement": "💡",
            "question": "❓",
            "documentation": "📚",
            "other": "📋"
        }

        # Priority emoji mapping
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

        # Summary
        summary = result.get("summary", "")
        if summary:
            lines.append(f"### Summary\n{summary}\n")

        # Labels
        labels = result.get("labels", [])
        if labels:
            if applied:
                lines.append("### Labels Applied ✅\n")
            else:
                lines.append("### Suggested Labels\n")

            lines.append(" ".join([f"`{label}`" for label in labels]))
            lines.append("")

        # Reason
        reason = result.get("reason", "")
        if reason:
            lines.append(f"### Analysis\n{reason}\n")

        # Related files (from codebase scan) - collapsible section
        related_files = result.get("related_files", [])
        if related_files:
            lines.append("<details>")
            lines.append(f"<summary><strong>📁 Related Files</strong> ({len(related_files[:8])} files)</summary>")
            lines.append("")
            lines.append("Files that may be relevant to this issue:")
            lines.append("")
            for f in related_files[:8]:  # Show up to 8 files
                lines.append(f"- `{f}`")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        # Recommendations based on type
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
        elif issue_type == "feature":
            recs.append("- [ ] Evaluate feature fit with project roadmap")
            recs.append("- [ ] Gather community feedback")
            recs.append("- [ ] Consider breaking into smaller tasks")
        elif issue_type == "question":
            recs.append("- [ ] Check if answered in documentation")
            recs.append("- [ ] Consider adding to FAQ if common")
            recs.append("- [ ] May be closeable after answering")
        elif issue_type == "documentation":
            recs.append("- [ ] Good candidate for community contribution")
            recs.append("- [ ] Consider adding `good first issue` label")

        recs.append("")
        return "\n".join(recs)
