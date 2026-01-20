"""Code review tool for Kimi Actions.

Uses Agent SDK with Skill-based architecture.
Supports intelligent chunking and fallback models for large PRs.
Supports inline comments and incremental review.
"""

import asyncio
import logging
import tempfile
from typing import List, Tuple, Optional
import uuid

from tools.base import BaseTool, DIFF_LIMIT_REVIEW
from diff_chunker import DiffChunk
from models import CodeSuggestion, SeverityLevel, ReviewOptions, SuggestionControl
from suggestion_service import SuggestionService

logger = logging.getLogger(__name__)


class Reviewer(BaseTool):
    """Code review tool using Agent SDK with Skill-based architecture."""

    @property
    def skill_name(self) -> str:
        return "code-review"

    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Run code review on a PR."""
        incremental = kwargs.get("incremental", False)
        inline = kwargs.get("inline", True)
        command_quote = kwargs.get("command_quote", "")

        pr = self.github.get_pr(repo_name, pr_number)
        self.load_context(repo_name, ref=pr.head.sha)

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

        skill = self.get_skill()
        if not skill:
            return f"Error: {self.skill_name} skill not found."

        system_prompt = self._build_system_prompt(skill)

        with tempfile.TemporaryDirectory() as work_dir:
            if not self.clone_repo(repo_name, work_dir, branch=pr.head.ref):
                return f"### 🌗 Pull request overview\n\n❌ Failed to clone repository\n\n{self.format_footer()}"
            
            try:
                response = asyncio.run(self._run_agent_review(
                    work_dir=work_dir, system_prompt=system_prompt,
                    pr_title=pr.title, pr_branch=f"{pr.head.ref} -> {pr.base.ref}",
                    diff=compressed_diff
                ))
            except Exception as e:
                logger.error(f"Review failed: {e}")
                return f"### 🌗 Pull request overview\n\n❌ {str(e)}\n\n{self.format_footer()}"

        suggestions = self._parse_suggestions(response)
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
        logger.info(f"Suggestions: {len(suggestions)} parsed, {len(filtered)} filtered")

        total_files = len(included_chunks) if included_chunks else len(set(s.relevant_file for s in filtered if s.relevant_file))
        posted_count = 0
        if inline and filtered:
            summary = self._format_inline_summary(
                response, filtered, len(filtered), total_files=total_files,
                included_chunks=included_chunks, incremental=incremental,
                current_sha=pr.head.sha, command_quote=command_quote
            )
            posted_count = self._post_inline_comments(repo_name, pr_number, filtered, summary_body=summary)
            if posted_count > 0:
                return ""

        summary = self._format_inline_summary(
            response, filtered, posted_count, total_files=total_files,
            included_chunks=included_chunks, incremental=incremental,
            current_sha=pr.head.sha, command_quote=command_quote
        )
        return summary


    async def _run_agent_review(
        self, work_dir: str, system_prompt: str, pr_title: str, pr_branch: str, diff: str
    ) -> str:
        """Run agent to perform code review."""
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
            from kaos.path import KaosPath
        except ImportError:
            return '```yaml\nsuggestions: []\nsummary: "kimi-agent-sdk not installed"\n```'

        api_key = self.setup_agent_env()
        if not api_key:
            return '```yaml\nsuggestions: []\nsummary: "KIMI_API_KEY is required"\n```'

        text_parts = []
        review_prompt = f"""{system_prompt}

## PR Information
Title: {pr_title}
Branch: {pr_branch}

## Code Changes
```diff
{diff[:DIFF_LIMIT_REVIEW]}
```

## Instructions
1. Analyze the code changes carefully
2. If needed, read related files to understand context
3. Identify bugs, security issues, and improvements
4. **CRITICAL**: For file_summaries, provide SPECIFIC descriptions based on actual code changes:
   - ❌ NEVER use: "New file added", "Modified", "Code changes", or generic descriptions
   - ✅ ALWAYS describe WHAT the code does: "Added JWT authentication with token validation"
   - ✅ Be specific: "Refactored database queries to use connection pooling"
   - ✅ Mention key functionality: "Fixed memory leak in image processing by closing file handles"
   - Read the diff and describe the actual functionality added/modified in each file

Please output review results in YAML format:
```yaml
summary: "Brief summary of the PR"
score: 85
file_summaries:
  - file: "path/to/file.py"
    description: "Specific description of functionality added/modified (NOT 'New file' or 'Modified')"
  - file: "path/to/another.js"
    description: "Specific description of what this file does or changes"
suggestions:
  - relevant_file: "path/to/file.py"
    language: "python"
    severity: "medium"
    label: "bug"
    one_sentence_summary: "Brief issue description"
    suggestion_content: "Detailed explanation"
    existing_code: "problematic code"
    improved_code: "fixed code"
    relevant_lines_start: 10
    relevant_lines_end: 15
```

**CRITICAL**: Every file in file_summaries MUST have a unique, meaningful description that explains what functionality was added or modified. Generic descriptions like "New file added" or "Modified" are NOT acceptable.
"""

        try:
            skills_path = self.get_skills_dir()
            
            # Convert work_dir string to KaosPath for Agent SDK
            work_dir_kaos = KaosPath(work_dir) if work_dir else KaosPath.cwd()
            skills_dir_kaos = KaosPath(skills_path) if skills_path else None
            
            async with await Session.create(
                work_dir=work_dir_kaos, model=self.AGENT_MODEL,
                yolo=True, max_steps_per_turn=50,
                skills_dir=skills_dir_kaos,
            ) as session:
                async for msg in session.prompt(review_prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")
            
            if skills_path:
                logger.info(f"Review used skills from: {skills_path}")
            return "".join(text_parts)
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f'```yaml\nsuggestions: []\nsummary: "Error: {str(e)}"\n```'

    def _get_incremental_diff(
        self, repo_name: str, pr_number: int
    ) -> Tuple[Optional[str], List[DiffChunk], List[DiffChunk], Optional[str]]:
        """Get diff only for new commits since last review."""
        last_review = self.github.get_last_bot_comment(repo_name, pr_number)
        if not last_review:
            diff, included, excluded = self.get_diff(repo_name, pr_number)
            return diff, included, excluded, None

        last_sha = last_review["sha"]
        new_commits = self.github.get_commits_since(repo_name, pr_number, last_sha)
        if not new_commits:
            return None, [], [], last_sha

        commit_shas = [c.sha for c in new_commits]
        diff = self.github.get_diff_for_commits(repo_name, commit_shas)
        if not diff:
            return None, [], [], last_sha

        included, excluded = self.chunker.chunk_diff(diff, max_files=self.config.max_files)
        compressed = self.chunker.build_diff_string(included)
        return compressed, included, excluded, last_sha

    def _post_inline_comments(
        self, repo_name: str, pr_number: int, suggestions: List[CodeSuggestion],
        summary_body: str = ""
    ):
        """Post inline comments with GitHub native suggestion format."""
        # Convert CodeSuggestion objects to dict format expected by BaseTool
        suggestion_dicts = []
        for s in suggestions:
            suggestion_dicts.append({
                "relevant_file": s.relevant_file,
                "relevant_lines_start": s.relevant_lines_start,
                "relevant_lines_end": s.relevant_lines_end,
                "suggestion_content": s.suggestion_content,
                "improved_code": s.improved_code
            })
        
        return self.post_inline_comments(
            repo_name, pr_number, suggestion_dicts,
            summary_body=summary_body, use_suggestion_format=True
        )


    def _format_inline_summary(
        self, response: str, suggestions: List[CodeSuggestion], inline_count: int,
        total_files: int = 0, included_chunks: List[DiffChunk] = None,
        incremental: bool = False, current_sha: str = None, command_quote: str = ""
    ) -> str:
        """Format a short summary when inline comments were posted."""
        data = self.parse_yaml_response(response) or {}
        summary = data.get("summary", "").strip()
        file_summaries = {}
        for fs in data.get("file_summaries", []):
            f = fs.get("file", "")
            desc = fs.get("description", "")
            if f and desc:
                file_summaries[f] = desc

        lines = []
        if command_quote:
            lines.append(f"> {command_quote}")
            lines.append("")

        lines.append("### 🌗 Pull request overview")
        if summary:
            lines.append(f"{summary}\n")
        else:
            lines.append("Code review completed.\n")

        files_reviewed = total_files if total_files > 0 else len(included_chunks) if included_chunks else 0
        lines.append("**Reviewed changes**")
        lines.append(f"Kimi reviewed {files_reviewed} changed files in this pull request and generated {inline_count} comments.\n")

        if included_chunks:
            lines.append("<details>")
            lines.append("<summary>Show a summary per file</summary>\n")
            lines.append("| File | Description |")
            lines.append("|------|-------------|")
            for chunk in included_chunks:
                if chunk.filename in file_summaries:
                    desc = file_summaries[chunk.filename]
                else:
                    # Generate more meaningful default descriptions
                    change_type_desc = {
                        "added": "New file added",
                        "deleted": "File removed",
                        "modified": "Modified",
                        "renamed": "File renamed"
                    }.get(chunk.change_type, "Modified")
                    
                    # Add language info if available
                    lang_info = f" ({chunk.language})" if chunk.language else ""
                    desc = f"{change_type_desc}{lang_info}"
                
                lines.append(f"| `{chunk.filename}` | {desc} |")
            lines.append("\n</details>\n")

        if suggestions:
            lines.append("**Issues found:**")
            sev_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
            for s in suggestions[:5]:
                icon = sev_icons.get(s.severity.value, "⚪")
                file_name = s.relevant_file or "unknown"
                issue_summary = (s.one_sentence_summary or "").replace("\n", " ").strip()
                lines.append(f"- {icon} `{file_name}`: {issue_summary}")
            if len(suggestions) > 5:
                lines.append(f"- ... and {len(suggestions) - 5} more")
            lines.append("")

        lines.append(self.format_footer())
        if current_sha:
            lines.append(f"\n<!-- kimi-review:sha={current_sha[:12]} -->")
        return "\n".join(lines)

    def _build_system_prompt(self, skill) -> str:
        """Build system prompt from skill and context.
        
        Note: Agent SDK will automatically call skill scripts when needed,
        so we don't need to run them manually and include output in prompt.
        """
        parts = [skill.instructions]
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
        if self.config.review.extra_instructions:
            parts.append(f"\n## Extra Instructions\n{self.config.review.extra_instructions}")
        return "\n".join(parts)

    def _parse_suggestions(self, response: str) -> List[CodeSuggestion]:
        """Parse YAML response into CodeSuggestion objects."""
        try:
            data = self.parse_yaml_response(response)
            if not data:
                logger.warning("YAML parsing returned None or empty data")
                return []
                
            suggestions_data = data.get("suggestions", [])
            if not suggestions_data:
                logger.info("No suggestions in YAML response")
                return []

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
            logger.info(f"Parsed {len(suggestions)} suggestions from response")
            return suggestions
        except Exception as e:
            logger.error(f"Failed to parse suggestions: {e}")
            return []


    def _format_review(
        self, response: str, valid: List[CodeSuggestion], discarded: List[CodeSuggestion],
        excluded_files: List[DiffChunk] = None, included_chunks: List[DiffChunk] = None,
        incremental: bool = False, current_sha: str = None
    ) -> str:
        """Format review in Copilot-style format."""
        data = self.parse_yaml_response(response)
        if not data:
            return self._format_fallback(response, current_sha)

        lines = []
        summary = data.get("summary", "").strip()
        lines.append("### Pull request overview")
        if summary:
            lines.append(f"{summary}\n")

        if valid:
            lines.append("**Key Changes:**")
            files_changed = set(s.relevant_file for s in valid if s.relevant_file)
            for f in list(files_changed)[:5]:
                lines.append(f"- `{f}`")
            lines.append("")

        total_files = len(included_chunks) if included_chunks else len(set(s.relevant_file for s in valid + discarded if s.relevant_file))
        if excluded_files:
            total_files += len(excluded_files)
        lines.append("**Reviewed changes**")
        lines.append(f"Kimi reviewed {total_files} changed files and generated {len(valid)} comments.\n")

        if valid:
            lines.append("---\n")
            for s in valid:
                location = f"`{s.relevant_file}`"
                if s.relevant_lines_start:
                    location += f" line {s.relevant_lines_start}"
                    if s.relevant_lines_end and s.relevant_lines_end != s.relevant_lines_start:
                        location += f"-{s.relevant_lines_end}"
                lines.append(f"📍 {location}\n")
                lines.append(f"{s.suggestion_content}\n")
                if s.existing_code and s.improved_code:
                    lines.append("**Suggested change**")
                    lines.append("```diff")
                    for line in s.existing_code.strip().splitlines():
                        lines.append(f"- {line}")
                    for line in s.improved_code.strip().splitlines():
                        lines.append(f"+ {line}")
                    lines.append("```")
                lines.append("\n---\n")

        if discarded:
            lines.append(f"<details>\n<summary>📋 {len(discarded)} low-priority suggestions</summary>\n")
            for s in discarded[:3]:
                lines.append(f"- {s.one_sentence_summary} (`{s.relevant_file}`)")
            if len(discarded) > 3:
                lines.append(f"- ... and {len(discarded) - 3} more")
            lines.append("</details>\n")

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
        data = self.parse_yaml_response(response)
        if data:
            summary = data.get("summary", "").strip()
            score = data.get("score", "N/A")
            
            lines = ["## 🌗 Kimi Code Review\n"]
            lines.append("### ✅ No issues found\n")
            if summary:
                lines.append(f"**Summary**: {summary}\n")
            lines.append(f"**Code Score**: {score}/100\n")
            lines.append(self.format_footer())
            
            if current_sha:
                lines.append(f"\n<!-- kimi-review:sha={current_sha[:12]} -->")
            return "\n".join(lines)
        
        result = f"## 🌗 Kimi Code Review\n\n{response}\n\n{self.format_footer()}"
        if current_sha:
            result += f"\n<!-- kimi-review:sha={current_sha[:12]} -->"
        return result
