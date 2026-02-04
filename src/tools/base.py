"""Base tool class for Kimi Actions.

Provides common functionality for all tools:
- Skill loading and management
- Agent SDK interaction
- Repository cloning
"""

import logging
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from action_config import get_action_config
from github_client import GitHubClient
from skill_loader import SkillManager, Skill
from repo_config import load_repo_config, RepoConfig

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all tools.

    Subclasses must implement:
    - skill_name: The default skill to use
    - run(): The main execution logic
    """

    def __init__(self, github: GitHubClient):
        self.github = github
        self.config = get_action_config()

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
