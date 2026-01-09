"""Code review tool for Kimi Actions.

Uses Skill-based architecture with script support.
Supports intelligent chunking and fallback models for large PRs.
"""

import logging
from typing import List
import yaml
import uuid

from tools.base import BaseTool
from token_handler import DiffChunk
from models import CodeSuggestion, SeverityLevel, ReviewOptions, SuggestionControl
from suggestion_service import SuggestionService

logger = logging.getLogger(__name__)


class Reviewer(BaseTool):
    """Code review tool using Skill-based architecture."""

    @property
    def skill_name(self) -> str:
        return "code-review"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Run code review on a PR."""
        # Get PR info
        pr = self.github.get_pr(repo_name, pr_number)

        # Load context (config + custom skills)
        self.load_context(repo_name, ref=pr.head.sha)

        # Get and process diff
        compressed_diff, included_chunks, excluded_chunks = self.get_diff(repo_name, pr_number)
        if not compressed_diff:
            return "No changes to review."

        # Get skill (respects overrides)
        skill = self.get_skill()
        if not skill:
            return f"Error: {self.skill_name} skill not found."

        # Run scripts if available
        script_output = self._run_scripts(skill, compressed_diff)

        # Build system prompt
        system_prompt = self._build_system_prompt(skill, script_output, compressed_diff)

        # Build user prompt
        user_prompt = f"""## PR Information
Title: {pr.title}
Branch: {pr.head.ref} -> {pr.base.ref}

## Code Changes
```diff
{compressed_diff}
```

Please output review results in YAML format."""

        # Call Kimi
        response = self.call_kimi(system_prompt, user_prompt)

        # Parse and filter suggestions
        suggestions = self._parse_suggestions(response)
        if suggestions:
            review_options = ReviewOptions(
                bug=self.repo_config.enable_bug if self.repo_config else True,
                performance=self.repo_config.enable_performance if self.repo_config else True,
                security=self.repo_config.enable_security if self.repo_config else True
            )
            suggestion_service = SuggestionService(SuggestionControl(
                max_suggestions=self.config.review.num_max_findings,
                severity_level_filter=SeverityLevel.LOW
            ))
            filtered, discarded = suggestion_service.process_suggestions(
                suggestions, review_options, compressed_diff
            )
            return self._format_review(response, filtered, discarded, excluded_chunks)

        return self._format_fallback(response)

    def _run_scripts(self, skill, diff: str) -> str:
        """Run skill scripts and collect output."""
        if not skill.scripts:
            return ""

        output_parts = []
        lang = self._detect_language(diff)

        if "linter" in skill.scripts:
            result = skill.run_script("linter", lang=lang, code=diff[:5000])
            if result:
                output_parts.append(f"## Linter Output\n```\n{result}\n```")

        if "security_scan" in skill.scripts:
            result = skill.run_script("security_scan", lang=lang, code=diff[:5000])
            if result:
                output_parts.append(f"## Security Scan Output\n```\n{result}\n```")

        return "\n\n".join(output_parts)

    def _build_system_prompt(self, skill, script_output: str, diff: str) -> str:
        """Build system prompt from skill and context."""
        parts = [skill.instructions]

        # Review level
        level_text = {
            "strict": "Review Level: Strict - Check all issues",
            "normal": "Review Level: Normal - Focus on functional issues",
            "gentle": "Review Level: Gentle - Only flag critical issues"
        }
        parts.append(f"\n## {level_text.get(self.config.review_level, level_text['normal'])}")

        # Script output
        if script_output:
            parts.append(f"\n## Automated Check Results\n{script_output}")

        # Extra instructions
        if self.config.review.extra_instructions:
            parts.append(f"\n## Extra Instructions\n{self.config.review.extra_instructions}")

        return "\n".join(parts)

    def _detect_language(self, diff: str) -> str:
        """Detect primary language from diff."""
        patterns = {
            "python": [".py", "def ", "import "],
            "javascript": [".js", "const ", "function "],
            "typescript": [".ts", "interface ", ": string"],
            "go": [".go", "func ", "package "],
            "java": [".java", "public class"],
        }
        diff_lower = diff.lower()
        for lang, markers in patterns.items():
            if any(m.lower() in diff_lower for m in markers):
                return lang
        return "python"

    def _parse_suggestions(self, response: str) -> List[CodeSuggestion]:
        """Parse YAML response into CodeSuggestion objects."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]

            data = yaml.safe_load(yaml_content)
            suggestions_data = data.get("suggestions", [])

            suggestions = []
            for s in suggestions_data:
                severity_str = s.get("severity", "medium").lower()
                severity = SeverityLevel(severity_str) if severity_str in ["critical", "high", "medium", "low"] else SeverityLevel.MEDIUM

                suggestions.append(CodeSuggestion(
                    id=str(uuid.uuid4())[:8],
                    relevant_file=s.get("relevant_file", ""),
                    language=s.get("language", ""),
                    suggestion_content=s.get("suggestion_content", ""),
                    existing_code=s.get("existing_code", ""),
                    improved_code=s.get("improved_code", ""),
                    one_sentence_summary=s.get("one_sentence_summary", ""),
                    relevant_lines_start=s.get("relevant_lines_start", 0),
                    relevant_lines_end=s.get("relevant_lines_end", 0),
                    label=s.get("label", "bug"),
                    severity=severity
                ))
            return suggestions
        except Exception:
            return []

    def _format_review(
        self,
        response: str,
        valid: List[CodeSuggestion],
        discarded: List[CodeSuggestion],
        excluded_files: List[DiffChunk] = None
    ) -> str:
        """Format review with filtered suggestions."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]
            data = yaml.safe_load(yaml_content)
        except Exception:
            return self._format_fallback(response)

        lines = ["## 🤖 Kimi Code Review\n"]

        # Summary
        summary = data.get("summary", "").strip()
        score = data.get("score", "N/A")
        effort = data.get("estimated_effort", "N/A")

        lines.append(f"### 📊 Summary\n{summary}\n")
        lines.append(f"- **Code Score**: {score}/100")
        lines.append(f"- **Review Effort**: {effort}/5\n")

        # Suggestions
        if valid:
            lines.append(f"### 🔍 Issues Found ({len(valid)})\n")
            severity_icons = {SeverityLevel.CRITICAL: "🔴", SeverityLevel.HIGH: "🟠", SeverityLevel.MEDIUM: "🟡", SeverityLevel.LOW: "🔵"}
            label_icons = {"bug": "🐛", "performance": "⚡", "security": "🔒"}

            for i, s in enumerate(valid, 1):
                sev_icon = severity_icons.get(s.severity, "⚪")
                label_icon = label_icons.get(s.label.lower(), "💡")

                location = f"`{s.relevant_file}`"
                if s.relevant_lines_start:
                    location += f" (L{s.relevant_lines_start}"
                    if s.relevant_lines_end and s.relevant_lines_end != s.relevant_lines_start:
                        location += f"-{s.relevant_lines_end}"
                    location += ")"

                lines.append(f"#### {sev_icon} {label_icon} {i}. {s.one_sentence_summary}")
                lines.append(f"📍 {location} | Severity: **{s.severity.value}**\n")
                lines.append(f"{s.suggestion_content}\n")

                if s.existing_code and s.improved_code:
                    lines.append("<details>")
                    lines.append("<summary>View code comparison</summary>\n")
                    lines.append(f"**Current code:**\n```{s.language}\n{s.existing_code.strip()}\n```\n")
                    lines.append(f"**Suggested:**\n```{s.language}\n{s.improved_code.strip()}\n```")
                    lines.append("</details>\n")
        else:
            lines.append("### ✅ No major issues found\n")

        # Discarded suggestions
        if discarded:
            lines.append(f"<details>\n<summary>📋 {len(discarded)} low-priority suggestions collapsed</summary>\n")
            for s in discarded[:3]:
                lines.append(f"- {s.one_sentence_summary} (`{s.relevant_file}`)")
            if len(discarded) > 3:
                lines.append(f"- ... and {len(discarded) - 3} more")
            lines.append("</details>\n")

        # Excluded files
        if excluded_files:
            lines.append(f"<details>\n<summary>📁 {len(excluded_files)} files excluded due to token limit</summary>\n")
            for chunk in excluded_files[:5]:
                lines.append(f"- `{chunk.filename}` (~{chunk.tokens} tokens)")
            if len(excluded_files) > 5:
                lines.append(f"- ... and {len(excluded_files) - 5} more")
            lines.append("</details>\n")

        lines.append(self.format_footer())
        return "\n".join(lines)

    def _format_fallback(self, response: str) -> str:
        """Fallback formatting."""
        return f"## 🤖 Kimi Code Review\n\n{response}\n\n{self.format_footer()}"
