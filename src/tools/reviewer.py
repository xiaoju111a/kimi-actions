"""Code review tool for Kimi Actions.

Uses Skill-based architecture with script support.
Supports intelligent chunking and fallback models for large PRs.
Supports inline comments and incremental review.
"""

import logging
from typing import List, Tuple, Optional
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
        """Run code review on a PR.

        Args:
            incremental: Only review new commits since last review
            inline: Post inline comments (default: True)
        """
        incremental = kwargs.get("incremental", False)
        inline = kwargs.get("inline", True)  # Default to inline comments

        # Get PR info
        pr = self.github.get_pr(repo_name, pr_number)

        # Load context (config + custom skills)
        self.load_context(repo_name, ref=pr.head.sha)

        # Get diff (incremental or full)
        if incremental:
            compressed_diff, included_chunks, excluded_chunks, last_sha = self._get_incremental_diff(
                repo_name, pr_number
            )
            if compressed_diff is None:
                return "No new changes since last review."
        else:
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

            # Post inline comments if requested
            if inline and filtered:
                # Format summary for review body
                summary_comment = self._format_inline_summary(
                    response, filtered, len(filtered),
                    incremental=incremental, current_sha=pr.head.sha
                )
                
                # Post review with body (summary) + inline comments together
                inline_count = self._post_inline_comments(
                    repo_name, pr_number, filtered, summary_body=summary_comment
                )
                if inline_count > 0:
                    return ""  # Already posted, return empty to avoid duplicate
                
                # Fallback: return summary for main.py to post
                return summary_comment

            # Format and return full result (normal mode or inline fallback)
            result = self._format_review(
                response, filtered, discarded, excluded_chunks,
                incremental=incremental, current_sha=pr.head.sha
            )
            return result

        return self._format_fallback(response, pr.head.sha if incremental else None)

    def _get_incremental_diff(
        self, repo_name: str, pr_number: int
    ) -> Tuple[Optional[str], List[DiffChunk], List[DiffChunk], Optional[str]]:
        """Get diff only for new commits since last review."""
        # Find last review comment
        last_review = self.github.get_last_bot_comment(repo_name, pr_number)

        if not last_review:
            # No previous review, do full review
            diff, included, excluded = self.get_diff(repo_name, pr_number)
            return diff, included, excluded, None

        last_sha = last_review["sha"]

        # Get new commits
        new_commits = self.github.get_commits_since(repo_name, pr_number, last_sha)

        if not new_commits:
            return None, [], [], last_sha

        # Get diff for new commits
        commit_shas = [c.sha for c in new_commits]
        diff = self.github.get_diff_for_commits(repo_name, commit_shas)

        if not diff:
            return None, [], [], last_sha

        # Process through chunker
        included, excluded = self.chunker.chunk_diff(diff, max_files=self.config.max_files)
        compressed = self.chunker.build_diff_string(included)

        return compressed, included, excluded, last_sha

    def _post_inline_comments(
        self, repo_name: str, pr_number: int, suggestions: List[CodeSuggestion],
        summary_body: str = ""
    ):
        """Post inline comments with GitHub native suggestion format."""
        comments = []

        for s in suggestions:
            if not s.relevant_file or not s.relevant_lines_start:
                continue

            # Build comment body with description
            body = f"{s.suggestion_content}"

            # Use GitHub's native suggestion syntax for code changes
            if s.improved_code:
                body += f"\n\n```suggestion\n{s.improved_code.strip()}\n```"

            comment = {
                "path": s.relevant_file,
                "line": s.relevant_lines_end if s.relevant_lines_end else s.relevant_lines_start,
                "body": body,
                "side": "RIGHT"
            }
            
            # Add start_line for multi-line suggestions
            if s.relevant_lines_end and s.relevant_lines_end != s.relevant_lines_start:
                comment["start_line"] = s.relevant_lines_start
            
            comments.append(comment)

        if comments:
            try:
                self.github.create_review_with_comments(
                    repo_name, pr_number, comments,
                    body=summary_body,  # Summary as review body
                    event="COMMENT"
                )
                logger.info(f"Posted {len(comments)} inline comments with summary")
                return len(comments)
            except Exception as e:
                logger.error(f"Failed to post inline comments: {e}")
                return 0
        return 0

    def _format_inline_summary(
        self,
        response: str,
        suggestions: List[CodeSuggestion],
        inline_count: int,
        incremental: bool = False,
        current_sha: str = None
    ) -> str:
        """Format a short summary when inline comments were posted."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]
            data = yaml.safe_load(yaml_content)
            score = data.get("score", "N/A")
            summary = data.get("summary", "").strip()
        except Exception:
            score = "N/A"
            summary = ""

        lines = ["## 🤖 Kimi Code Review\n"]

        if incremental:
            lines.append("*📝 Incremental review (new commits only)*\n")

        lines.append(f"✅ Posted **{inline_count}** inline comments on specific code lines.\n")

        if summary:
            lines.append(f"**Summary**: {summary}\n")

        lines.append(f"**Code Score**: {score}/100\n")

        # List issues briefly
        if suggestions:
            lines.append("**Issues found:**")
            sev_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
            for s in suggestions[:5]:
                icon = sev_icons.get(s.severity.value, "⚪")
                lines.append(f"- {icon} `{s.relevant_file}`: {s.one_sentence_summary}")
            if len(suggestions) > 5:
                lines.append(f"- ... and {len(suggestions) - 5} more")
            lines.append("")

        lines.append(self.format_footer())

        if current_sha:
            lines.append(f"\n<!-- kimi-review:sha={current_sha[:12]} -->")

        return "\n".join(lines)

    def _run_scripts(self, skill, diff: str) -> str:
        """Run skill scripts and collect output."""
        if not skill.scripts:
            return ""

        output_parts = []
        lang = self._detect_language(diff)

        if "linter" in skill.scripts:
            result = skill.run_script("linter", lang=lang, code=diff[:5000])
            if result:
                output_parts.append(f"## Linter Output\n```text\n{result}\n```")

        if "security_scan" in skill.scripts:
            result = skill.run_script("security_scan", lang=lang, code=diff[:5000])
            if result:
                output_parts.append(f"## Security Scan Output\n```text\n{result}\n```")

        return "\n\n".join(output_parts)

    def _build_system_prompt(self, skill, script_output: str, diff: str) -> str:
        """Build system prompt from skill and context."""
        parts = [skill.instructions]

        # Review level
        level_text = {
            "strict": """Review Level: Strict - Perform thorough analysis including:
- Thread safety and race condition detection
- Stub/mock/simulation code detection
- Error handling completeness
- Cache key collision detection
- All items in the Strict Mode Checklist""",
            "normal": "Review Level: Normal - Focus on functional issues and common bugs",
            "gentle": "Review Level: Gentle - Only flag critical issues that would break functionality"
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
        excluded_files: List[DiffChunk] = None,
        incremental: bool = False,
        current_sha: str = None
    ) -> str:
        """Format review in Copilot-style format."""
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]
            data = yaml.safe_load(yaml_content)
        except Exception:
            return self._format_fallback(response, current_sha)

        lines = []

        # Pull request overview
        summary = data.get("summary", "").strip()
        lines.append("### Pull request overview")
        if summary:
            lines.append(f"{summary}\n")

        # Key Changes (extract from suggestions)
        if valid:
            lines.append("**Key Changes:**")
            # Group by file
            files_changed = set(s.relevant_file for s in valid if s.relevant_file)
            for f in list(files_changed)[:5]:
                lines.append(f"- `{f}`")
            lines.append("")

        # Reviewed changes summary
        total_files = len(set(s.relevant_file for s in valid + discarded if s.relevant_file))
        if excluded_files:
            total_files += len(excluded_files)
        lines.append("**Reviewed changes**")
        lines.append(f"Kimi reviewed {total_files} changed files and generated {len(valid)} comments.\n")

        # Comments section
        if valid:
            lines.append("---\n")
            
            for s in valid:
                # File and line location
                location = f"`{s.relevant_file}`"
                if s.relevant_lines_start:
                    location += f" line {s.relevant_lines_start}"
                    if s.relevant_lines_end and s.relevant_lines_end != s.relevant_lines_start:
                        location += f"-{s.relevant_lines_end}"

                lines.append(f"📍 {location}\n")
                
                # Issue description
                lines.append(f"{s.suggestion_content}\n")

                # Suggested change with diff
                if s.existing_code and s.improved_code:
                    lines.append("**Suggested change**")
                    lines.append("```diff")
                    for line in s.existing_code.strip().splitlines():
                        lines.append(f"- {line}")
                    for line in s.improved_code.strip().splitlines():
                        lines.append(f"+ {line}")
                    lines.append("```")
                
                lines.append("\n---\n")

        # Collapsed low-priority suggestions
        if discarded:
            lines.append(f"<details>\n<summary>📋 {len(discarded)} low-priority suggestions</summary>\n")
            for s in discarded[:3]:
                lines.append(f"- {s.one_sentence_summary} (`{s.relevant_file}`)")
            if len(discarded) > 3:
                lines.append(f"- ... and {len(discarded) - 3} more")
            lines.append("</details>\n")

        # Excluded files
        if excluded_files:
            lines.append(f"<details>\n<summary>📁 {len(excluded_files)} files not reviewed (token limit)</summary>\n")
            for chunk in excluded_files[:5]:
                lines.append(f"- `{chunk.filename}`")
            if len(excluded_files) > 5:
                lines.append(f"- ... and {len(excluded_files) - 5} more")
            lines.append("</details>\n")

        lines.append(self.format_footer())

        if current_sha:
            lines.append(f"\n<!-- kimi-review:sha={current_sha[:12]} -->")

        return "\n".join(lines)

    def _format_fallback(self, response: str, current_sha: str = None) -> str:
        """Fallback formatting when no suggestions found."""
        try:
            # Try to parse YAML and format nicely
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]
            
            data = yaml.safe_load(yaml_content)
            summary = data.get("summary", "").strip()
            score = data.get("score", "N/A")
            
            lines = ["## 🤖 Kimi Code Review\n"]
            lines.append("### ✅ No issues found\n")
            if summary:
                lines.append(f"**Summary**: {summary}\n")
            lines.append(f"**Code Score**: {score}/100\n")
            lines.append(self.format_footer())
            
            if current_sha:
                lines.append(f"\n<!-- kimi-review:sha={current_sha[:12]} -->")
            
            return "\n".join(lines)
        except Exception:
            # True fallback - just show raw response
            result = f"## 🤖 Kimi Code Review\n\n{response}\n\n{self.format_footer()}"
            if current_sha:
                result += f"\n<!-- kimi-review:sha={current_sha[:12]} -->"
            return result
