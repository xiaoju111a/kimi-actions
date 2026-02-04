"""Base tool class for Kimi Actions.

Provides common functionality for all tools:
- Diff processing with intelligent chunking
- Skill loading and management
- Agent SDK interaction
"""

import logging
import os
import subprocess
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, List

from action_config import get_action_config
from github_client import GitHubClient
from diff_chunker import DiffChunker, DiffChunk
from skill_loader import SkillManager, Skill
from repo_config import load_repo_config, RepoConfig

logger = logging.getLogger(__name__)

# Diff truncation limits (tokens)
DIFF_LIMIT_REVIEW = 15000  # Only used for non-Agent SDK modes
DIFF_LIMIT_IMPROVE = 10000
DIFF_LIMIT_ASK = 8000
DIFF_LIMIT_DESCRIBE = 12000


class BaseTool(ABC):
    """Abstract base class for all tools.

    Subclasses must implement:
    - skill_name: The default skill to use
    - run(): The main execution logic
    """

    def __init__(self, github: GitHubClient):
        self.github = github
        self.config = get_action_config()

        # Diff chunking
        self.chunker = DiffChunker(
            max_tokens=DIFF_LIMIT_REVIEW, exclude_patterns=self.config.exclude_patterns
        )

        # Skill management
        self.skill_manager = SkillManager()
        self.repo_config: Optional[RepoConfig] = None

    @property
    @abstractmethod
    def skill_name(self) -> str:
        """Default skill name for this tool."""
        pass

    @abstractmethod
    def run(self, repo_name: str, pr_number: int, **kwargs) -> str:
        """Execute the tool's main logic."""
        pass

    def load_context(self, repo_name: str, ref: str = None) -> None:
        """Load repository config and custom skills."""
        self.repo_config, validation = load_repo_config(self.github, repo_name, ref=ref)

        if not validation.valid:
            logger.error(f"Config validation failed: {validation.errors}")
        if validation.warnings:
            logger.warning(f"Config warnings: {validation.warnings}")

        self.skill_manager.load_from_repo(self.github, repo_name, ref=ref)

        if self.repo_config and self.repo_config.ignore_files:
            self.chunker.exclude_patterns = (
                list(self.chunker.exclude_patterns) + self.repo_config.ignore_files
            )

    def get_skill(self) -> Optional[Skill]:
        """Get the skill for this tool, respecting overrides."""
        skill_to_use = self.skill_name

        if self.repo_config and self.repo_config.skill_overrides:
            override = self.repo_config.skill_overrides.get(self.skill_name)
            if override:
                logger.info(f"Using skill override: {self.skill_name} -> {override}")
                skill_to_use = override

        skill = self.skill_manager.get_skill(skill_to_use)
        if not skill:
            logger.warning(f"Skill not found: {skill_to_use}")

        return skill

    def get_diff(
        self, repo_name: str, pr_number: int
    ) -> Tuple[str, List[DiffChunk], List[DiffChunk]]:
        """Get and process PR diff with intelligent chunking."""
        diff = self.github.get_pr_diff(repo_name, pr_number)
        if not diff:
            return "", [], []

        included, excluded = self.chunker.chunk_diff(
            diff, max_files=self.config.max_files
        )
        compressed = self.chunker.build_diff_string(included)

        total_tokens = sum(chunk.tokens for chunk in included)
        logger.info(
            f"Diff processed: {len(included)} files included, "
            f"{len(excluded)} excluded, ~{total_tokens} tokens"
        )

        return compressed, included, excluded

    def format_footer(self, extra_info: str = "") -> str:
        """Generate standard footer for tool output."""
        model_info = f"`{self.AGENT_MODEL}`"

        footer = f"---\n<sub>Powered by [Kimi](https://kimi.moonshot.cn/) | Model: {model_info}"
        if extra_info:
            footer += f" | {extra_info}"
        footer += "</sub>"

        return footer

    # Agent SDK configuration
    AGENT_MODEL = "kimi-k2.5"  # Latest model for best performance
    AGENT_BASE_URL = "https://api.moonshot.cn/v1"

    def setup_agent_env(self) -> Optional[str]:
        """Setup environment variables for Agent SDK.

        Returns:
            API key if available, None otherwise.
        """
        api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("INPUT_KIMI_API_KEY")
        if not api_key:
            return None

        # Get base URL from config or environment
        base_url = (
            self.config.kimi_base_url
            or os.environ.get("KIMI_BASE_URL")
            or self.AGENT_BASE_URL
        )

        os.environ["KIMI_API_KEY"] = api_key
        os.environ["KIMI_BASE_URL"] = base_url
        os.environ["KIMI_MODEL_NAME"] = self.AGENT_MODEL
        return api_key

    @staticmethod
    def parse_yaml_response(response: str) -> Optional[dict]:
        """Parse YAML from LLM response with error recovery.

        Handles common formats:
        - ```yaml ... ```
        - ``` ... ```
        - Raw YAML

        Returns:
            Parsed dict or None if parsing fails.
        """
        try:
            yaml_content = response
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]

            # Sanitize: Remove lines that look like Python code with type hints
            # These sometimes leak into YAML output and break parsing
            lines = yaml_content.split('\n')
            sanitized_lines = []
            for line in lines:
                # Skip lines that look like Python method signatures
                if ' -> ' in line and '(' in line and ')' in line:
                    logger.debug(f"Skipping Python code line: {line[:80]}")
                    continue
                sanitized_lines.append(line)
            yaml_content = '\n'.join(sanitized_lines)

            parsed = yaml.safe_load(yaml_content)
            if parsed is None:
                logger.warning(
                    f"YAML parsing returned None. Response preview: {response[:500]}"
                )
            return parsed
        except yaml.YAMLError as e:
            logger.warning(
                f"YAML parsing failed: {e}. Attempting to extract partial data..."
            )

            # Try to extract at least summary and file_summaries
            try:
                import re

                result = {}

                # Extract summary
                summary_match = re.search(
                    r'summary:\s*["\']?(.*?)["\']?\s*(?:score:|file_summaries:|\n\w+:)',
                    yaml_content,
                    re.DOTALL,
                )
                if summary_match:
                    result["summary"] = summary_match.group(1).strip().strip("\"'")

                # Extract score
                score_match = re.search(r"score:\s*(\d+)", yaml_content)
                if score_match:
                    result["score"] = int(score_match.group(1))

                # Extract file_summaries (simplified - just get file and description pairs)
                file_summaries = []
                file_pattern = r'-\s*file:\s*["\']?(.*?)["\']?\s*description:\s*["\']?(.*?)["\']?\s*(?=-\s*file:|\nsuggestions:|\Z)'
                for match in re.finditer(file_pattern, yaml_content, re.DOTALL):
                    file_summaries.append(
                        {
                            "file": match.group(1).strip().strip("\"'"),
                            "description": match.group(2).strip().strip("\"'"),
                        }
                    )

                if file_summaries:
                    result["file_summaries"] = file_summaries

                # Always include empty suggestions if parsing failed
                result["suggestions"] = []

                if result:
                    logger.info(
                        f"Extracted partial YAML data: {len(file_summaries)} file summaries"
                    )
                    return result

            except Exception as extract_error:
                logger.error(f"Failed to extract partial data: {extract_error}")

            logger.warning(
                f"Complete YAML parsing failure. Response preview: {response[:500]}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"YAML parsing failed: {e}. Response preview: {response[:500]}"
            )
            return None

    def clone_repo(self, repo_name: str, work_dir: str, branch: str = None) -> bool:
        """Clone repository with fallback logic.

        Args:
            repo_name: Repository name (owner/repo)
            work_dir: Directory to clone into
            branch: Branch name (optional, falls back to default branch)

        Returns:
            True if clone succeeded, False otherwise
        """
        clone_url = f"https://github.com/{repo_name}.git"

        try:
            if branch:
                subprocess.run(
                    ["git", "clone", "--depth", "1", "-b", branch, clone_url, work_dir],
                    check=True,
                    capture_output=True,
                )
                logger.info(f"Successfully cloned {repo_name} (branch: {branch})")
                return True

            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, work_dir],
                check=True,
                capture_output=True,
            )
            logger.info(f"Successfully cloned {repo_name}")
            return True
        except subprocess.CalledProcessError as e:
            if branch:
                # Fallback to default branch
                logger.warning(
                    f"Failed to clone branch {branch}, trying default branch"
                )
                try:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", clone_url, work_dir],
                        check=True,
                        capture_output=True,
                    )
                    logger.info(f"Successfully cloned {repo_name} (default branch)")
                    return True
                except subprocess.CalledProcessError:
                    logger.error(f"Failed to clone {repo_name}: {e}")
                    return False

            logger.error(f"Failed to clone {repo_name}: {e}")
            return False

    def get_skills_dir(self) -> Optional[Path]:
        """Get skills directory from current skill.

        Returns:
            Path to skills directory if skill has scripts, None otherwise
        """
        skill = self.get_skill()
        if skill and skill.skill_dir:
            return Path(skill.skill_dir)
        return None

    async def run_agent(
        self, work_dir: str, prompt: str, skills_dir: Optional[str] = None
    ) -> str:
        """Run agent with standard configuration.

        Args:
            work_dir: Working directory for agent
            prompt: Prompt to send to agent
            skills_dir: Optional path to skills directory. If None, auto-detects from current skill.

        Returns:
            Agent response text
        """
        try:
            from kimi_agent_sdk import Session, ApprovalRequest, TextPart
            from kaos.path import KaosPath
        except ImportError:
            logger.error("kimi-agent-sdk not installed")
            return ""

        api_key = self.setup_agent_env()
        if not api_key:
            logger.error("KIMI_API_KEY not found")
            return ""

        # Auto-detect skills_dir from current skill if not provided
        if skills_dir is None:
            skills_path = self.get_skills_dir()
        else:
            skills_path = Path(skills_dir) if skills_dir else None

        # Convert to KaosPath for Agent SDK
        work_dir_kaos = KaosPath(work_dir) if work_dir else KaosPath.cwd()
        skills_dir_kaos = KaosPath(str(skills_path)) if skills_path else None

        text_parts = []
        try:
            async with await Session.create(
                work_dir=work_dir_kaos,
                model=self.AGENT_MODEL,
                yolo=True,
                max_steps_per_turn=100,
                skills_dir=skills_dir_kaos,
            ) as session:
                async for msg in session.prompt(prompt):
                    if isinstance(msg, TextPart):
                        text_parts.append(msg.text)
                    elif isinstance(msg, ApprovalRequest):
                        msg.resolve("approve")

            response = "".join(text_parts)
            logger.info(
                f"Agent completed successfully, response length: {len(response)}"
            )
            if skills_path:
                logger.info(f"Agent used skills from: {skills_path}")
            return response
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return ""

    def post_inline_comments(
        self,
        repo_name: str,
        pr_number: int,
        suggestions: List[dict],
        summary_body: str = "",
        use_suggestion_format: bool = True,
    ) -> int:
        """Post inline comments with optional GitHub suggestion format.

        Args:
            repo_name: Repository name
            pr_number: PR number
            suggestions: List of suggestion dicts with keys:
                - relevant_file: File path
                - relevant_lines_start: Start line number
                - relevant_lines_end: End line number (optional)
                - suggestion_content: Description
                - improved_code: Suggested code (optional)
            summary_body: Summary comment body
            use_suggestion_format: Use ```suggestion format for improved_code

        Returns:
            Number of comments posted
        """
        comments = []
        footer = f"\n\n---\n<sub>Powered by [Kimi](https://kimi.moonshot.cn/) | Model: `{self.AGENT_MODEL}`</sub>"
        skipped = []

        for s in suggestions:
            file_name = s.get("relevant_file", "")
            line_start = s.get("relevant_lines_start")
            line_end = s.get("relevant_lines_end")
            content = s.get("suggestion_content", "").strip()
            improved = s.get("improved_code", "").strip()

            if not file_name or not line_start:
                reason = f"Missing file/line: file={file_name}, line_start={line_start}"
                skipped.append(reason)
                logger.warning(f"Skipping suggestion: {reason}")
                continue

            # Build comment body
            body = f"{content}\n\n"
            if improved and use_suggestion_format:
                body += "```suggestion\n"
                body += improved
                body += "\n```"
            elif improved:
                body += f"**Suggested code:**\n```\n{improved}\n```"
            body += footer

            comment = {
                "path": file_name,
                "line": line_end if line_end else line_start,
                "body": body,
                "side": "RIGHT",
            }
            if line_end and line_end != line_start:
                comment["start_line"] = line_start
            comments.append(comment)
            logger.debug(
                f"Prepared inline comment for {file_name}:{line_start}-{line_end or line_start}"
            )

        logger.info(f"Prepared {len(comments)} inline comments, skipped {len(skipped)}")
        if skipped:
            logger.warning(f"Skipped suggestions: {skipped[:3]}")

        if comments:
            try:
                logger.info(
                    f"Posting {len(comments)} inline comments to PR #{pr_number}"
                )
                self.github.create_review_with_comments(
                    repo_name, pr_number, comments, body=summary_body, event="COMMENT"
                )
                logger.info(f"Successfully posted {len(comments)} inline comments")
                return len(comments)
            except Exception as e:
                logger.error(f"Failed to post inline comments: {e}")
                if comments:
                    logger.error(f"First comment that failed: {comments[0]}")
                return 0

        logger.warning("No inline comments to post")
        return 0
